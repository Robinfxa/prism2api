"""API Schemas for Native and OpenAI-compatible endpoints for M01."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from prism2api.runtime.context import ContextPolicy


class NativeRunRequest(BaseModel):
    input_text: str
    model_alias: str = "prism-default"
    context_policy: ContextPolicy = ContextPolicy.ISOLATED
    context_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class NativeRunResponse(BaseModel):
    run_id: str
    state: str
    created_at: str
    principal_id: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False


class ChatChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Optional[Dict[str, int]] = None
