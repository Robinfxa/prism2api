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

    kind = "mock"
    handle_scoped_events = True  # Synthetic guarantee, never a live protocol claim.

    def prepare_context(self, session, context, operation_id):
        return RemoteHandle(workspace_ref=context.workspace_ref or "ws_" + context.context_id,
                            conversation_ref=context.conversation_ref or "conv_" + context.context_id)

    def lookup_events(self, session, handle):
        return self.observe_events(handle)

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
            CapabilitySnapshot(capability_id=CapabilityId.EXPLICIT_CONTINUATION,
                evidence_state=EvidenceState.VERIFIED, activation_state=ActivationState.ENABLED,
                account_scope="local_mock", evidence_refs=["synthetic:contract-tests"]),
            CapabilitySnapshot(capability_id=CapabilityId.CANCEL_CONFIRMATION,
                evidence_state=EvidenceState.VERIFIED, activation_state=ActivationState.ENABLED,
                account_scope="local_mock", evidence_refs=["synthetic:contract-tests"]),
            CapabilitySnapshot(
                capability_id=CapabilityId.TEXT_GENERATION,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
                account_scope="local_mock",
                evidence_refs=["synthetic:contract-tests"],
                limitations=["Mock-only. Does not establish Prism capability."],
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.ISOLATED_CONTEXT,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
                account_scope="local_mock",
                evidence_refs=["synthetic:contract-tests"],
                limitations=["Mock-only. Does not establish Prism capability."],
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.TASK_LOOKUP,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=ActivationState.ENABLED,
                account_scope="local_mock",
                evidence_refs=["synthetic:contract-tests"],
                limitations=["Mock-only. Does not establish Prism capability."],
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
        context = session.context_binding
        return RemoteHandle(
            workspace_ref=context.get("workspace_ref") or f"ws_{run_id}",
            conversation_ref=context.get("conversation_ref") or f"conv_{run_id}",
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
                "payload": {"text": "[MOCK] Synthetic response; no Prism request was sent."},
            },
            {
                "type": "RunCompleted",
                "payload": {"finish_reason": "stop", "text": "[MOCK] Synthetic response; no Prism request was sent."},
            },
        ]

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Cancel task handle."""
        if handle.task_ref:
            self.cancelled_handles.add(handle.task_ref)
            return True
        return False
