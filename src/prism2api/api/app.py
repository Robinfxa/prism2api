"""FastAPI Application for prism2api HTTP Gateway."""

import time
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Security, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware

from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import RunSupervisor, RunState, IdempotencyConflictError
from prism2api.api.models import (
    NativeRunRequest,
    NativeRunResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatChoiceMessage,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(settings: Optional[Settings] = None, supervisor: Optional[RunSupervisor] = None) -> FastAPI:
    app_settings = settings or Settings()
    journal = StorageJournal(app_settings)
    app_supervisor = supervisor or RunSupervisor(app_settings, journal)

    app = FastAPI(title="prism2api Gateway", version="0.1.0")

    # Host & Security Middleware
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # Host validation
        host = request.headers.get("host", "").split(":")[0]
        if app_settings.loopback_only and host not in app_settings.allowed_hosts:
            return JSONResponse(status_code=403, content={"detail": "Forbidden host"})

        # Check API Key for non-health endpoints
        if not request.url.path.startswith("/health"):
            auth_header = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                auth_header = auth_header[7:]
            if auth_header != app_settings.api_key:
                return JSONResponse(status_code=401, content={"detail": "Invalid API Key"})

        return await call_next(request)

    @app.get("/health/live")
    def health_live():
        return {"status": "live"}

    @app.get("/health/ready")
    def health_ready():
        ready = not app_supervisor.admission_latch
        return {"status": "ready" if ready else "not_ready", "latch": app_supervisor.admission_latch}

    @app.post("/prism/v1/runs", status_code=status.HTTP_202_ACCEPTED, response_model=NativeRunResponse)
    def create_native_run(req: NativeRunRequest, request: Request):
        principal_id = "default_principal"
        try:
            record = app_supervisor.enqueue_run(
                principal_id=principal_id,
                input_text=req.input_text,
                model_alias=req.model_alias,
                context_policy=req.context_policy,
                idempotency_key=req.idempotency_key,
                context_id=req.context_id,
            )
            return NativeRunResponse(
                run_id=record.run_id,
                state=record.state.value,
                created_at=record.created_at,
                principal_id=record.principal_id,
            )
        except IdempotencyConflictError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.get("/prism/v1/runs/{run_id}")
    def get_native_run(run_id: str):
        try:
            record = app_supervisor.get_run(run_id)
            if record.principal_id != "default_principal":
                raise HTTPException(status_code=404, detail="Run not found")
            return record.model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="Run not found")

    @app.post("/prism/v1/runs/{run_id}/cancel")
    def cancel_native_run(run_id: str):
        try:
            record = app_supervisor.cancel_run(run_id)
            return {"run_id": run_id, "state": record.state.value, "cancel_intent": record.cancel_intent}
        except KeyError:
            raise HTTPException(status_code=404, detail="Run not found")

    @app.get("/prism/v1/capabilities")
    def get_capabilities():
        caps = app_supervisor.adapter.inspect_capabilities()
        return [c.model_dump() for c in caps]

    @app.get("/v1/models")
    def list_models():
        caps = app_supervisor.adapter.inspect_capabilities()
        models = []
        for c in caps:
            if c.capability_id == "text_generation" and c.is_usable:
                models.append({"id": "prism-default", "object": "model", "owned_by": "prism2api"})
        return {"object": "list", "data": models}

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    def create_chat_completion(req: ChatCompletionRequest):
        # Pre-submit Model Validation
        available_models = [m["id"] for m in list_models()["data"]]
        if req.model not in available_models:
            raise HTTPException(status_code=404, detail=f"Model '{req.model}' not found.")

        # Pre-submit Parameter Validation
        if req.temperature is not None or req.top_p is not None:
            raise HTTPException(status_code=400, detail="Unsupported parameter: temperature and top_p are not supported.")

        if req.stream:
            raise HTTPException(status_code=400, detail="Unsupported parameter: stream=True is not supported.")

        if req.n is not None and req.n != 1:
            raise HTTPException(status_code=400, detail="Unsupported parameter: n != 1 is not supported.")

        if req.tools is not None:
            raise HTTPException(status_code=400, detail="Unsupported parameter: tools are not supported.")

        if req.max_tokens is not None:
            raise HTTPException(status_code=400, detail="Unsupported parameter: max_tokens is not supported.")

        # Pre-submit Payload Validation
        if len(req.messages) != 1 or req.messages[0].role != "user":
            raise HTTPException(status_code=400, detail="Only single user message is supported in chat-text-v1.")

        input_text = req.messages[0].content
        principal_id = "default_principal"

        record = app_supervisor.enqueue_run(
            principal_id=principal_id,
            input_text=input_text,
            model_alias=req.model,
        )

        result = app_supervisor.execute_run(record.run_id, input_text=input_text, model_alias=req.model)

        return ChatCompletionResponse(
            id=f"chatcmpl-{result.run_id}",
            created=int(time.time()),
            model=req.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatChoiceMessage(role="assistant", content=result.text),
                    finish_reason=result.finish_reason,
                )
            ],
            usage=result.usage,
        )

    return app
