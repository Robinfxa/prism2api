"""API Schemas for Native and OpenAI-compatible endpoints for M01."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from prism2api.runtime.context import ContextPolicy


class NativeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_text: str = Field(min_length=1)
    expected_context_revision: Optional[int] = Field(default=None, ge=1)
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
    model_config = ConfigDict(extra="forbid", strict=True)
    role: str
    content: str = Field(min_length=1)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    max_tokens: Optional[int] = None

    model_config = ConfigDict(extra="forbid", strict=True)


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
