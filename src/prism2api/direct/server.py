"""Authenticated, loopback-only, non-streaming fixed-context API."""
from contextlib import asynccontextmanager
import hmac
import json
import time
from typing import Literal
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, StrictStr
from . import __version__
from .bootstrap import strict_json
from .engine import DirectEngine
from .errors import DirectError


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Literal['user']
    content: StrictStr = Field(min_length=1, max_length=262144)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    model: Literal['prism-default']
    messages: list[Message] = Field(min_length=1, max_length=1)
    stream: Literal[False] = False
    n: Literal[1] = 1


def create_app(engine: DirectEngine) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        yield
        await engine.close()

    app = FastAPI(title='prism2api Direct HTTP', version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        host = request.headers.get('host', '')
        # Reject host rebinding and cross-origin browser use. No anonymous localhost gateway.
        h = host.split(']')[0][1:] if host.startswith('[') else host.partition(':')[0]
        if h not in ('127.0.0.1', '::1', 'localhost'):
            return JSONResponse({'error':{'code':'invalid_host','message':'Loopback Host required.'}}, status_code=400)
        if request.headers.get('origin'):
            return JSONResponse({'error':{'code':'browser_origin_rejected','message':'This is not a browser-facing API.'}},status_code=403)
        if request.url.path != '/healthz':
            supplied = request.headers.get('authorization', '')
            if not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer '+engine.key).encode('utf-8')):
                return JSONResponse({'error':{'code':'unauthorized','message':'Local API key required.'}},status_code=401)
        return await call_next(request)

    @app.exception_handler(DirectError)
    async def direct_error(_request, exc):
        return JSONResponse(exc.public(),status_code=exc.status)

    @app.get('/healthz')
    async def health():
        pending=engine.journal.pending()
        return {'status':'blocked' if pending else 'configured', 'transport':'direct-http',
                'context_mode':'fixed-shared', 'browser_required_by_client':False,
                'upstream_generation_verified_this_startup':engine.successful_runs > 0,
                'active':engine.lock.locked(), 'unresolved_run':pending['run_id'] if pending else None}

    @app.get('/v1/models')
    async def models():
        return {'object':'list','data':[{'id':'prism-default','object':'model','owned_by':'local-alias'}]}

    @app.get('/v1/runs/{run_id}')
    async def run_status(run_id: str):
        return engine.journal.public(run_id)

    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        if not request.headers.get('content-type','').lower().startswith('application/json'):
            raise DirectError('content_type','Use Content-Type: application/json.',415)
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>1024*1024:
                raise DirectError('input_too_large','Request exceeds 1 MiB.',413)
        try:
            obj=strict_json(data.decode('utf-8'))
            req=ChatRequest.model_validate(obj)
            # bool is a Python int: reject JSON true for n and 0 for stream.
            if ('stream' in obj and obj['stream'] is not False) or ('n' in obj and type(obj['n']) is not int):
                raise ValueError()
        except (ValidationError,ValueError,UnicodeError,DirectError):
            raise DirectError('unsupported_request','Accepts model=prism-default, one user text message, stream=false, n=1 only. No tools or extra fields.',400) from None
        result=await engine.generate(req.messages[0].content,idempotency_key=request.headers.get('idempotency-key'))
        return JSONResponse({'id':'chatcmpl-'+result['run_id'][4:], 'object':'chat.completion',
            'created':int(time.time()), 'model':'prism-default',
            'choices':[{'index':0,'message':{'role':'assistant','content':result['text']},'finish_reason':'stop'}],
            'usage':None}, headers={'X-Prism2API-Run':result['run_id'], 'X-Prism2API-Context':'fixed-shared'})

    return app
