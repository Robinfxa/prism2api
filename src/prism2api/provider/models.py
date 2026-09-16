"""Capability and Provider models for M02 Adapter."""

from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EvidenceState(str, Enum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    STALE = "stale"


class ActivationState(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"
    QUARANTINED = "quarantined"


class CapabilityId(str, Enum):
    TEXT_GENERATION = "text_generation"
    ISOLATED_CONTEXT = "isolated_context"
    EXPLICIT_CONTINUATION = "explicit_continuation"
    TASK_LOOKUP = "task_lookup"
    CANCEL_CONFIRMATION = "cancel_confirmation"
    DELTA_STREAM = "delta_stream"
    MODEL_SELECTION = "model_selection"
    ROLE_MAPPING = "role_mapping"
    USAGE_REPORTING = "usage_reporting"
    READ_ONLY_MODE = "read_only_mode"


class CapabilitySnapshot(BaseModel):
    capability_id: CapabilityId
    evidence_state: EvidenceState = EvidenceState.UNKNOWN
    activation_state: ActivationState = ActivationState.DISABLED
    account_scope: Optional[str] = None
    transport_revision: str = "v0.1.0"
    parser_revision: str = "v0.1.0"
    tested_at: Optional[str] = None
    review_due_at: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """Capability is usable if verified and enabled with no quarantine."""
        if self.review_due_at is not None:
            try:
                if datetime.fromisoformat(self.review_due_at).astimezone(timezone.utc) <= datetime.now(timezone.utc):
                    return False
            except (ValueError, TypeError):
                return False
        return (
            self.evidence_state == EvidenceState.VERIFIED
            and self.activation_state == ActivationState.ENABLED
        )


class RemoteHandle(BaseModel):
    workspace_ref: Optional[str] = None
    conversation_ref: Optional[str] = None
    task_ref: Optional[str] = None
    message_ref: Optional[str] = None
    server_event_cursor: Optional[str] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
