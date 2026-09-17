"""OpenAI-compatible HTTP API server for prism2api v0.1 Browser MVP."""

import time
import uuid
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from prism2api.transport.prism_browser import PrismBrowserTransport
from prism2api.errors import AdmissionBlockedError, ProtocolError

logger = logging.getLogger(__name__)


class ChatCompletionMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    stream: Optional[bool] = False


def create_browser_app(transport: PrismBrowserTransport) -> FastAPI:
    """Create a FastAPI application bound to a PrismBrowserTransport instance."""
    app = FastAPI(title="prism2api Browser MVP", version="0.1.1")

    @app.post("/v1/chat/completions")
    async def create_chat_completion(req: ChatCompletionRequest):
        # 1. Model validation
        if req.model != "prism-default":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported model '{req.model}'. Only 'prism-default' is allowed in v0.1 MVP."
            )

        if req.stream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Streaming is not supported in v0.1 MVP. Please set stream=false."
            )

        # 2. Extract user prompt
        user_prompt: Optional[str] = None
        for msg in reversed(req.messages):
            if msg.role == "user" and msg.content.strip():
                user_prompt = msg.content.strip()
                break

        if not user_prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No non-empty user prompt found in messages array."
            )

        # 3. Check transport ready state
        if not transport.is_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Prism browser runtime is not ready. Please verify project/conversation setup."
            )

        # 4. Execute generation via page context
        try:
            output_text = await transport.submit_and_poll(prompt=user_prompt, timeout=60.0)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Prism upstream generation timed out: {exc}"
            )
        except (ProtocolError, AdmissionBlockedError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Prism upstream execution error: {exc}"
            )
        except Exception as exc:
            logger.exception("Unexpected error during chat completion")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {exc}"
            )

        # 5. Format OpenAI-compatible response
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "prism-default",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": output_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": None
        }

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok" if transport.is_ready else "unavailable",
            "browser_ready": transport.is_ready,
            "project_id": transport.project_id,
            "conversation_id": transport.conversation_id
        }

    return app
