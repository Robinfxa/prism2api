"""PrismAdapter for M02 Provider & Capability Management."""

from typing import List, Optional, Dict, Any
from prism2api.provider.models import (
    CapabilitySnapshot,
    CapabilityId,
    EvidenceState,
    ActivationState,
    RemoteHandle,
)
from prism2api.transport.base import BaseTransport, TransportSession, AuthProfile
from prism2api.transport.unconfigured import UnconfiguredTransport
from prism2api.errors import AdmissionBlockedError, ProtocolError, UnsupportedRequestError
from prism2api.transport.base import AuthStatus
import uuid
import time
from prism2api.runtime.events import EventNormalizer, EventType, NormalizedEvent


class PrismAdapter:
    """唯一理解 Prism 产品语义与能力调度的组件。"""

    def __init__(self, transport: Optional[BaseTransport] = None):
        self.transport = transport if transport is not None else UnconfiguredTransport()
        self.auth_profile = getattr(self.transport, "auth_profile", AuthProfile(profile_id="default"))
        self.session = TransportSession(
            session_id="session_" + uuid.uuid4().hex,
            transport_type=self.transport.kind,
            auth_profile_id=self.auth_profile.profile_id,
        )

    def inspect_capabilities(self) -> List[CapabilitySnapshot]:
        """Query capabilities snapshot from current transport."""
        return self.transport.inspect_capabilities(self.session)

    def validate_request(self, model_alias, context_policy):
        if model_alias != "prism-default":
            raise UnsupportedRequestError("Unknown model alias")
        if self.auth_profile.auth_status != AuthStatus.READY:
            raise AdmissionBlockedError("Upstream authentication is not ready")
        needed = [CapabilityId.TEXT_GENERATION,
                  CapabilityId.ISOLATED_CONTEXT if str(getattr(context_policy, "value", context_policy)) == "isolated"
                  else CapabilityId.EXPLICIT_CONTINUATION]
        caps = self.inspect_capabilities()
        for cap_id in needed:
            cap = next((c for c in caps if c.capability_id == cap_id), None)
            if cap is None or not cap.is_usable:
                raise AdmissionBlockedError("Required capability is not verified and enabled")
            if self.transport.kind != "mock" and (
                not cap.evidence_refs or not cap.tested_at or not cap.review_due_at or
                cap.account_scope != self.auth_profile.account_scope
            ):
                raise AdmissionBlockedError("Missing live capability evidence or account scope")
        return caps

    def is_capability_usable(self, cap_id: CapabilityId) -> bool:
        """Check if capability is verified and enabled."""
        for cap in self.inspect_capabilities():
            if cap.capability_id == cap_id and cap.is_usable:
                return True
        return False

    def submit_request(
        self,
        run_id: str,
        attempt_id: str,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Submit generation request via transport layer."""
        if not self.is_capability_usable(CapabilityId.TEXT_GENERATION):
            raise RuntimeError("Capability text_generation is unsupported or unverified.")

        return self.transport.submit(
            run_id=run_id,
            attempt_id=attempt_id,
            session=self.session,
            input_text=input_text,
            model_alias=model_alias,
        )

    def observe_normalized_events(self, run_id, handle, normalizer, *, raw_events=None, before_event=None):
        """Validate canonical event ownership. Wire-to-canonical mapping belongs to transport.

        Missing identifiers are allowed ONLY for a verified handle-scoped source.
        Explicit contradictions can never be overwritten by local run labels.
        """
        source = self.transport.observe_events(handle) if raw_events is None else raw_events
        try:
            for raw in source:
                if before_event:
                    before_event()
                if not isinstance(raw, dict) or not isinstance(raw.get("payload", {}), dict):
                    raise ProtocolError("Malformed event")
                payload = dict(raw.get("payload", {}))
                expected = {key: getattr(handle, key) for key in
                            ("workspace_ref", "conversation_ref", "task_ref", "message_ref")}
                expected.update(run_id=run_id, attempt_id=normalizer.attempt_id, owner_epoch=normalizer.owner_epoch)
                matched_task = False
                for obj in (raw, payload):
                    for key, value in expected.items():
                        if key in obj:
                            if value is None or type(obj[key]) is not type(value) or obj[key] != value:
                                raise ProtocolError("Event identity/epoch mismatch")
                            if key in ("task_ref", "message_ref"):
                                matched_task = True
                if not matched_task and not self.transport.handle_scoped_events:
                    raise ProtocolError("Unbound event source")
                try:
                    kind = EventType(raw.get("type", "ProtocolUnknown"))
                except (ValueError, TypeError):
                    kind = EventType.PROTOCOL_UNKNOWN
                normalizer.add_event(kind, payload)
        finally:
            close = getattr(source, "close", None)
            if close:
                close()
        return normalizer.events

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Send cancellation request for active remote handle."""
        return self.transport.request_cancel(handle)
