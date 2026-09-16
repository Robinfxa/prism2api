"""Text-only local gateway. No inferred model capabilities or automatic retries."""
import asyncio
import hmac
import json
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from prism2api.config import Settings
from prism2api.errors import PrismError, AdmissionBlockedError, OutcomeError
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import RunSupervisor, RunState
from prism2api.runtime.context import ContextBusyError, ContextPolicy
from prism2api.api.models import NativeRunRequest, NativeRunResponse, ChatCompletionRequest, ChatCompletionResponse, ChatChoice, ChatChoiceMessage


class BodyLimitMiddleware:
    """Bound even chunked JSON before validation; never log rejected request bodies."""
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = -1
        if length < 0 or length > self.limit:
            return await JSONResponse({'error':{'code':'input_too_large'}},status_code=413)(scope,receive,send)
        messages, total = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            total += len(message.get('body',b''))
            if total > self.limit:
                return await JSONResponse({'error':{'code':'input_too_large'}},status_code=413)(scope,receive,send)
            messages.append(message)
            if not message.get('more_body',False):
                break
        async def replay():
            if messages:
                return messages.pop(0)
            return await receive()
        await self.app(scope,replay,send)


def create_app(settings=None, supervisor=None, *, adapter=None):
    app_settings = settings or (supervisor.settings if supervisor is not None else Settings())
    if supervisor is not None and adapter is not None:
        raise ValueError('Supply either supervisor or adapter, not both')
    owned = supervisor is None
    journal = StorageJournal(app_settings) if owned else supervisor.journal
    try:
        sup = supervisor or RunSupervisor(app_settings,journal,adapter)
    except BaseException:
        if owned:
            journal.close()
        raise

    @asynccontextmanager
    async def lifespan(app):
        sup.start_worker()
        try:
            yield
        finally:
            sup.close()
            if owned:
                journal.close()

    app = FastAPI(title='prism2api local gateway',version='0.1.1',lifespan=lifespan)
    app.state.supervisor = sup
    app.state.close = journal.close if owned else sup.close
    app.add_middleware(BodyLimitMiddleware,limit=app_settings.limits.max_http_body_bytes)

    @app.middleware('http')
    async def security(request:Request, call_next):
        try:
            host = urlsplit('//'+request.headers.get('host','')).hostname
        except ValueError:
            host = None
        if app_settings.loopback_only and host not in app_settings.allowed_hosts:
            return JSONResponse({'error':{'code':'forbidden_host'}},status_code=403)
        origin = request.headers.get('origin')
        if origin is not None and origin not in app_settings.allowed_origins:
            return JSONResponse({'error':{'code':'forbidden_origin'}},status_code=403)
        if request.url.path not in ('/health/live','/health/ready'):
            key = request.headers.get('X-API-Key') or request.headers.get('Authorization','')
            if key.startswith('Bearer '):
                key = key[7:]
            if not key or not app_settings.api_key or not hmac.compare_digest(key.encode(),app_settings.api_key.encode()):
                return JSONResponse({'error':{'code':'unauthorized'}},status_code=401)
        return await call_next(request)

    @app.exception_handler(PrismError)
    async def prism_error(request,exc):
        return JSONResponse({'error':{'type':'prism_error','code':exc.code,'message':exc.code,'run_id':exc.run_id}},status_code=exc.http_status)

    @app.exception_handler(ContextBusyError)
    async def context_error(request,exc):
        return JSONResponse({'error':{'code':'context_busy'}},status_code=409)

    @app.exception_handler(KeyError)
    async def not_found(request,exc):
        return JSONResponse({'error':{'code':'not_found'}},status_code=404)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        # Pydantic errors may include submitted secrets in 'input'. Do not echo them.
        return JSONResponse({'error':{'code':'invalid_request','fields':[list(e['loc']) for e in exc.errors()]}},status_code=422)

    @app.get('/health/live')
    def live():
        return {'status':'live','transport':sup.adapter.transport.kind}

    @app.get('/health/ready')
    def ready():
        ok = not sup.admission_latch and sup._worker is not None and sup._worker.is_alive()
        try:
            sup.adapter.validate_request('prism-default',ContextPolicy.ISOLATED)
        except (PrismError,RuntimeError):
            ok = False
        return JSONResponse({'status':'ready' if ok else 'not_ready','transport':sup.adapter.transport.kind},status_code=200 if ok else 503)

    def running_worker():
        if sup._worker is None or not sup._worker.is_alive():
            raise AdmissionBlockedError('Application lifespan has not started')

    @app.post('/prism/v1/runs',status_code=202,response_model=NativeRunResponse)
    def create_run(req:NativeRunRequest,request:Request):
        running_worker()
        key = request.headers.get('Idempotency-Key')
        if key is not None and req.idempotency_key is not None and key != req.idempotency_key:
            raise HTTPException(400,'Idempotency header/body conflict')
        record = sup.enqueue_run('default_principal',req.input_text,req.model_alias,req.context_policy,
                                 key if key is not None else req.idempotency_key,req.context_id,req.expected_context_revision)
        return NativeRunResponse(run_id=record.run_id,state=record.state.value,created_at=record.created_at,principal_id=record.principal_id)

    @app.get('/prism/v1/runs/{run_id}')
    def get_run(run_id:str):
        record = sup.get_run(run_id,'default_principal')
        # Internal input/result/credential paths are not an HTTP disclosure surface.
        return record.model_dump(mode='json',exclude={'input_ref','result_ref','terminal_evidence_ref','capability_snapshot_ref','request_fingerprint'})

    @app.get('/prism/v1/runs/{run_id}/result')
    def get_result(run_id:str):
        record = sup.get_run(run_id,'default_principal')
        if record.state in (RunState.QUEUED,RunState.PREPARING,RunState.SUBMITTING,RunState.RUNNING):
            return JSONResponse({'run_id':run_id,'state':record.state.value},status_code=202)
        return sup.get_result(run_id,'default_principal').model_dump(mode='json',exclude={'manifest_ref'})

    @app.post('/prism/v1/runs/{run_id}/cancel')
    def cancel(run_id:str):
        record = sup.cancel_run(run_id,'default_principal')
        return {'run_id':run_id,'state':record.state.value,'cancel_intent':record.cancel_intent}

    @app.post('/prism/v1/runs/{run_id}/reconcile')
    def reconcile(run_id:str):
        record = sup.reconcile_run(run_id,'default_principal')
        return {'run_id':run_id,'state':record.state.value}

    @app.get('/prism/v1/capabilities')
    def capabilities():
        return [c.model_dump(mode='json') for c in sup.adapter.inspect_capabilities()]

    @app.get('/v1/models')
    def models():
        try:
            sup.adapter.validate_request('prism-default',ContextPolicy.ISOLATED)
        except (PrismError,RuntimeError):
            return {'object':'list','data':[]}
        return {'object':'list','data':[{'id':'prism-default','object':'model','owned_by':'prism2api-'+sup.adapter.transport.kind}]}

    @app.post('/v1/chat/completions',response_model=ChatCompletionResponse,response_model_exclude_none=True)
    def completion(req:ChatCompletionRequest,request:Request):
        if req.model != 'prism-default':
            raise HTTPException(404,'Unknown model alias')
        if req.temperature is not None or req.top_p is not None or req.stream or req.n not in (None,1) or req.tools is not None or req.max_tokens is not None:
            raise HTTPException(400,'Unsupported parameter for chat-text-v1')
        if len(req.messages) != 1 or req.messages[0].role != 'user':
            raise HTTPException(400,'Only one user text message is supported')
        running_worker()
        record = sup.enqueue_run('default_principal',req.messages[0].content,req.model,
                                 idempotency_key=request.headers.get('Idempotency-Key'))
        result = sup.wait(record.run_id,principal_id='default_principal')
        return ChatCompletionResponse(id='chatcmpl-'+result.run_id,created=int(time.time()),model=result.requested_alias,
            choices=[ChatChoice(index=0,message=ChatChoiceMessage(content=result.text),finish_reason=result.finish_reason)],usage=result.usage)

    return app
