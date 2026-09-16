"""Mock Transport implementation for offline deterministic contract & unit testing."""

from typing import List, Dict, Any, Optional
from prism2api.transport.base import BaseTransport, TransportSession, AuthProfile, AuthStatus
from prism2api.provider.models import (
    CapabilitySnapshot,
    CapabilityId,
    EvidenceState,
    ActivationState,
    RemoteHandle,
)


class MockTransport(BaseTransport):
    """Deterministic Mock Transport for testing offline contracts without network."""

    def __init__(self, auth_profile: Optional[AuthProfile] = None):
        self.auth_profile = auth_profile or AuthProfile(
            profile_id="mock_auth_01",
            account_scope="local_mock",
            auth_status=AuthStatus.READY,
        )
        self.cancelled_handles: set[str] = set()

    def inspect_capabilities(self, session: TransportSession) -> List[CapabilitySnapshot]:
        """Return verified capabilities for mock environment."""
        if self.auth_profile.auth_status != AuthStatus.READY:
            return [
                CapabilitySnapshot(
                    capability_id=CapabilityId.TEXT_GENERATION,
                    evidence_state=EvidenceState.UNSUPPORTED,
                    activation_state=ActivationState.DISABLED,
                )
            ]

        return [
            CapabilitySnapshot(
                capability_id=CapabilityId.TEXT_GENERATION,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.ISOLATED_CONTEXT,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.DELTA_STREAM,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
            ),
        ]

    def submit(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Simulate submission and return RemoteHandle."""
        if self.auth_profile.auth_status != AuthStatus.READY:
            raise RuntimeError("Authentication profile is expired or not ready.")

        handle_id = f"handle_mock_{run_id}"
        return RemoteHandle(
            workspace_ref=f"ws_{run_id}",
            conversation_ref=f"conv_{run_id}",
            task_ref=handle_id,
            message_ref=f"msg_{attempt_id}",
            server_event_cursor="seq_0",
        )

    def observe_events(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Return simulated event payloads for a submitted handle."""
        task_ref = handle.task_ref or "unknown"
        if task_ref in self.cancelled_handles:
            return [
                {"type": "CancellationConfirmed", "payload": {"task_ref": task_ref}}
            ]

        return [
            {
                "type": "SubmissionObserved",
                "payload": {"task_ref": task_ref, "status": "accepted"},
            },
            {
                "type": "TextDelta",
                "payload": {"text": "Hello, this is a verified response from prism2api."},
            },
            {
                "type": "RunCompleted",
                "payload": {"finish_reason": "stop", "text": "Hello, this is a verified response from prism2api."},
            },
        ]

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Cancel task handle."""
        if handle.task_ref:
            self.cancelled_handles.add(handle.task_ref)
            return True
        return False
