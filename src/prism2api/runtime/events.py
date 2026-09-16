"""Event Normalizer, Ingestion, and Delivery Manager for M05."""

from enum import Enum
import json
from prism2api.errors import ProtocolError
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

    def __init__(self, run_id: str, *, attempt_id=None, owner_epoch=0,
                 max_event_count=10000, max_text_bytes=10*1024*1024, max_event_bytes=1024*1024, max_total_event_bytes=16*1024*1024):
        self.run_id = run_id
        self.events: List[NormalizedEvent] = []
        self.text_buffer: str = ""
        self.seq_counter: int = 0
        self.attempt_id, self.owner_epoch = attempt_id, owner_epoch
        self.max_event_count, self.max_text_bytes = max_event_count, max_text_bytes
        self.max_event_bytes = max_event_bytes
        self.max_total_event_bytes = max_total_event_bytes
        self.total_event_bytes = 0
        self.saw_text = False
        self.terminal = None
        self.final_text = None
        self.conflict = False
        self.unknown = False

    def add_event(self, event_type: EventType, payload: Dict[str, Any]) -> NormalizedEvent:
        """Add and record normalized event with sequential FIFO sequence."""
        if not isinstance(payload, dict):
            raise ProtocolError("Event payload must be an object")
        if self.seq_counter >= self.max_event_count:
            raise ProtocolError("Event count limit")
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())
        self.total_event_bytes += size
        if self.total_event_bytes > self.max_total_event_bytes:
            raise ProtocolError("Total event byte limit")
        if size > self.max_event_bytes:
            raise ProtocolError("Event byte limit")
        self.seq_counter += 1
        ev = NormalizedEvent(
            run_id=self.run_id,
            attempt_id=self.attempt_id,
            owner_epoch=self.owner_epoch,
            local_seq=self.seq_counter,
            event_type=event_type,
            payload=payload,
        )
        self.events.append(ev)

        if event_type == EventType.PROTOCOL_UNKNOWN:
            self.unknown = True
        if event_type in (EventType.TEXT_DELTA, EventType.TEXT_SNAPSHOT):
            text = payload.get("text")
            if not isinstance(text, str):
                raise ProtocolError("Text must be a string")
            if self.terminal is not None:
                # A final snapshot duplicated after completion is harmless. Never append.
                if not (event_type == EventType.TEXT_SNAPSHOT and text == self.final_text):
                    self.conflict = True
            else:
                self.text_buffer = self.text_buffer + text if event_type == EventType.TEXT_DELTA else text
                self.saw_text = True
        terminal_types = {EventType.RUN_COMPLETED, EventType.RUN_FAILED, EventType.CANCELLATION_CONFIRMED}
        if event_type in terminal_types:
            if self.terminal is not None:
                if self.terminal.event_type != event_type or self.terminal.payload != payload:
                    self.conflict = True
            else:
                self.terminal = ev
                if event_type == EventType.RUN_COMPLETED:
                    if "text" in payload:
                        if not isinstance(payload["text"], str):
                            raise ProtocolError("Final text must be a string")
                        self.final_text = payload["text"]
                        self.saw_text = True
                    elif self.saw_text:
                        self.final_text = self.text_buffer
                    if payload.get("finish_reason", "stop") not in ("stop", "length", "content_filter"):
                        raise ProtocolError("Unsupported final reason")
        if max(len(self.text_buffer.encode()), len((self.final_text or "").encode())) > self.max_text_bytes:
            raise ProtocolError("Text byte limit")

        return ev

    def get_terminal_event(self) -> Optional[NormalizedEvent]:
        """Resolve all observed evidence; conflicts never become first/last-wins."""
        if self.conflict or self.unknown:
            raise ProtocolError("Conflicting or unknown execution evidence")
        if self.terminal is not None and self.terminal.event_type == EventType.RUN_COMPLETED:
            if self.final_text is None or not self.saw_text:
                raise ProtocolError("Completion name without output evidence")
        return self.terminal

    def validate_append_only(self, snapshot: str) -> bool:
        """Check if snapshot is append-only relative to buffer."""
        return snapshot.startswith(self.text_buffer)
