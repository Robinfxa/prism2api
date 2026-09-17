"""Protocol models representing raw wire schemas for prism.openai.com."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class PrismMessageContent(BaseModel):
    type: str = "input_text"
    text: str


class PrismMessage(BaseModel):
    type: str = "message"
    role: str
    content: List[PrismMessageContent]


class PrismStartMetadata(BaseModel):
    projectId: str
    userId: str
    model: str = "gpt-6-astra"
    reasoning_effort: str = "medium"
    frontend_origin: str = "https://prism.openai.com"


class PrismStartRequest(BaseModel):
    input: List[PrismMessage]
    metadata: PrismStartMetadata
    conversationId: str


class PrismTurnState(BaseModel):
    version: int = 1
    conversation_id: str
    prompt: str
    reasoning_effort: str = "medium"
    user_id: str
    project_id: str
    async_job_id: Optional[str] = None


class PrismStatusRequest(BaseModel):
    request_id: str
    turn_state: PrismTurnState
