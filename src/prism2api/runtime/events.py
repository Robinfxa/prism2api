"""Event Normalizer, Ingestion, and Delivery Manager for M05."""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from prism2api.storage.journal import get_iso_now


class EventType(str, Enum):
    SUBMISSION_OBSERVED = "SubmissionObserved"
    TEXT_DELTA = "TextDelta"
    TEXT_SNAPSHOT = "TextSnapshot"
    ARTIFACT_OBSERVED = "ArtifactObserved"
    USAGE_OBSERVED = "UsageObserved"
    RUN_COMPLETED = "RunCompleted"
    RUN_FAILED = "RunFailed"
    CANCELLATION_CONFIRMED = "CancellationConfirmed"
    PROTOCOL_UNKNOWN = "ProtocolUnknown"


class DeliveryState(str, Enum):
    NOT_STARTED = "not_started"
    STREAMING = "streaming"
    COMPLETED = "completed"
    DISCONNECTED = "disconnected"
    TRUNCATED = "truncated"


class NormalizedEvent(BaseModel):
    run_id: str
    attempt_id: Optional[str] = None
    owner_epoch: int = 0
    local_seq: int
    received_at: str = Field(default_factory=get_iso_now)
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    source_event_ref: Optional[str] = None
    parser_revision: str = "v0.1.0"


class DeliveryRecord(BaseModel):
    delivery_id: str
    run_id: str
    principal_id: str
    protocol_version: str = "v0.1.0"
    state: DeliveryState = DeliveryState.NOT_STARTED
    bytes_sent: int = 0
    started_at: str = Field(default_factory=get_iso_now)
    ended_at: Optional[str] = None
    error_code: Optional[str] = None


class EventNormalizer:
    """Accumulates NormalizedEvents and validates text delta continuity."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[NormalizedEvent] = []
        self.text_buffer: str = ""
        self.seq_counter: int = 0

    def add_event(self, event_type: EventType, payload: Dict[str, Any]) -> NormalizedEvent:
        """Add and record normalized event with sequential FIFO sequence."""
        self.seq_counter += 1
        ev = NormalizedEvent(
            run_id=self.run_id,
            local_seq=self.seq_counter,
            event_type=event_type,
            payload=payload,
        )
        self.events.append(ev)

        # Handle text deltas & snapshots
        if event_type == EventType.TEXT_DELTA:
            delta = payload.get("text", "")
            self.text_buffer += delta
        elif event_type == EventType.TEXT_SNAPSHOT:
            snapshot = payload.get("text", "")
            # Authoritative snapshot update (handles both append-only and non-prefix rewrites)
            self.text_buffer = snapshot

        return ev

    def get_terminal_event(self) -> Optional[NormalizedEvent]:
        """Return the first terminal event if observed."""
        terminal_types = {
            EventType.RUN_COMPLETED,
            EventType.RUN_FAILED,
            EventType.CANCELLATION_CONFIRMED,
            EventType.PROTOCOL_UNKNOWN,
        }
        for ev in self.events:
            if ev.event_type in terminal_types:
                return ev
        return None

    def validate_append_only(self, snapshot: str) -> bool:
        """Check if snapshot is append-only relative to buffer."""
        return snapshot.startswith(self.text_buffer)
