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
from prism2api.transport.mock_transport import MockTransport
from prism2api.runtime.events import EventNormalizer, EventType, NormalizedEvent


class PrismAdapter:
    """唯一理解 Prism 产品语义与能力调度的组件。"""

    def __init__(self, transport: Optional[BaseTransport] = None):
        self.transport = transport or MockTransport()
        self.auth_profile = getattr(self.transport, "auth_profile", AuthProfile(profile_id="default"))
        self.session = TransportSession(
            session_id="session_01",
            auth_profile_id=self.auth_profile.profile_id,
        )

    def inspect_capabilities(self) -> List[CapabilitySnapshot]:
        """Query capabilities snapshot from current transport."""
        return self.transport.inspect_capabilities(self.session)

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

    def observe_normalized_events(
        self,
        run_id: str,
        handle: RemoteHandle,
        normalizer: EventNormalizer,
    ) -> List[NormalizedEvent]:
        """Observe raw events from transport and feed into EventNormalizer."""
        raw_events = self.transport.observe_events(handle)
        normalized_events: List[NormalizedEvent] = []

        for raw in raw_events:
            ev_type_str = raw.get("type", "ProtocolUnknown")
            try:
                ev_type = EventType(ev_type_str)
            except ValueError:
                ev_type = EventType.PROTOCOL_UNKNOWN

            payload = raw.get("payload", {})
            ev = normalizer.add_event(ev_type, payload)
            normalized_events.append(ev)

        return normalized_events

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Send cancellation request for active remote handle."""
        return self.transport.request_cancel(handle)
