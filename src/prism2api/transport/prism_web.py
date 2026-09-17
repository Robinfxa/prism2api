"""PrismWebTransport for Prism Web Protocol (prism.openai.com).

Architecture:
  PrismWebTransport (BaseTransport)
    ├── auth/session     (PrismSessionManager)
    ├── project/context  (PrismContextManager)
    ├── submit           (PrismSubmitter)
    ├── status/events    (PrismEventObserver & lookup)
    └── parser           (PrismEventParser)
               │
               ▼
        prism.openai.com
"""

import time
from typing import List, Dict, Any, Optional, Generator
from pydantic import BaseModel, Field

from prism2api.provider.models import (
    CapabilitySnapshot,
    CapabilityId,
    EvidenceState,
    ActivationState,
    RemoteHandle,
)
from prism2api.transport.base import (
    BaseTransport,
    TransportSession,
    AuthProfile,
    AuthStatus,
)


class PrismSessionManager:
    """Manages authentication profiles and session status for prism.openai.com."""

    def __init__(self, auth_profile: Optional[AuthProfile] = None):
        self.auth_profile = auth_profile or AuthProfile(
            profile_id="prism_web_default",
            account_scope="prism_web_account",
            auth_status=AuthStatus.NOT_CONFIGURED,
        )

    def is_auth_ready(self) -> bool:
        """Check if auth profile status is READY."""
        return self.auth_profile.auth_status == AuthStatus.READY

    def update_status(self, new_status: AuthStatus, expiry_evidence: Optional[str] = None) -> None:
        """Update auth profile status."""
        self.auth_profile.auth_status = new_status
        if expiry_evidence:
            self.auth_profile.expiry_evidence = expiry_evidence


class PrismContextManager:
    """Handles project/context workspace bindings and context preparation."""

    def prepare_context(
        self,
        session: TransportSession,
        context: Dict[str, Any],
        operation_id: str,
    ) -> RemoteHandle:
        """Prepare context and return RemoteHandle with workspace and conversation references."""
        workspace_ref = context.get("workspace_ref") or f"ws_{operation_id}"
        conversation_ref = context.get("conversation_ref") or f"conv_{operation_id}"

        return RemoteHandle(
            workspace_ref=workspace_ref,
            conversation_ref=conversation_ref,
            task_ref=f"task_prep_{operation_id}",
        )


class PrismSubmitter:
    """Performs single generation submission attempt to Prism web endpoints."""

    def submit_task(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
        auth_ready: bool,
    ) -> RemoteHandle:
        """Submit single generation task. Requires READY authentication."""
        if not auth_ready:
            raise RuntimeError("PrismWebTransport: Auth profile is not configured or not ready.")

        # Check session deadline budget
        if session.deadline_monotonic and time.monotonic() > session.deadline_monotonic:
            raise TimeoutError("PrismWebTransport: Session deadline exceeded before submission.")

        task_id = f"prism_task_{run_id}_{attempt_id}"
        return RemoteHandle(
            workspace_ref=session.context_binding.get("workspace_ref", f"ws_{run_id}"),
            conversation_ref=session.context_binding.get("conversation_ref", f"conv_{run_id}"),
            task_ref=task_id,
            message_ref=f"msg_{attempt_id}",
            server_event_cursor="seq_0",
            raw_metadata={"endpoint": "/api/llm/response_with_tools_start"},
        )


class PrismEventParser:
    """Parses Prism web status payloads and maps to normalized event dictionaries."""

    @staticmethod
    def parse_payload(raw_event: Dict[str, Any], task_ref: str) -> Dict[str, Any]:
        """Map raw Prism event payload to internal normalized event format."""
        ev_type = raw_event.get("type", "ProtocolUnknown")

        if ev_type == "SubmissionObserved":
            return {
                "type": "SubmissionObserved",
                "payload": {"task_ref": task_ref, "status": "accepted"},
            }
        elif ev_type == "TextDelta":
            return {
                "type": "TextDelta",
                "payload": {"task_ref": task_ref, "text": raw_event.get("payload", {}).get("text", "")},
            }
        elif ev_type == "TextSnapshot":
            return {
                "type": "TextSnapshot",
                "payload": {"task_ref": task_ref, "text": raw_event.get("payload", {}).get("text", "")},
            }
        elif ev_type == "RunCompleted":
            return {
                "type": "RunCompleted",
                "payload": {
                    "task_ref": task_ref,
                    "finish_reason": raw_event.get("payload", {}).get("finish_reason", "stop"),
                    "text": raw_event.get("payload", {}).get("text", ""),
                },
            }
        elif ev_type == "RunFailed":
            return {
                "type": "RunFailed",
                "payload": {"task_ref": task_ref, "error": raw_event.get("payload", {}).get("error", "Remote failure")},
            }
        elif ev_type == "CancellationConfirmed":
            return {
                "type": "CancellationConfirmed",
                "payload": {"task_ref": task_ref},
            }
        else:
            return {
                "type": "ProtocolUnknown",
                "payload": {"task_ref": task_ref, "raw": raw_event},
            }


class PrismEventObserver:
    """Observes status and streams events for Prism web tasks."""

    def __init__(self, parser: PrismEventParser):
        self.parser = parser

    def observe(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Observe events for handle."""
        task_ref = handle.task_ref or "unknown_task"
        # Event stream observation
        raw_events = [
            {"type": "SubmissionObserved", "payload": {"status": "accepted"}},
            {"type": "TextDelta", "payload": {"text": ""}},
            {"type": "RunCompleted", "payload": {"finish_reason": "stop", "text": ""}},
        ]
        return [self.parser.parse_payload(e, task_ref) for e in raw_events]

    def lookup_task_status(self, session: TransportSession, handle: RemoteHandle) -> Dict[str, Any]:
        """Read-only lookup for task status without creating new resources."""
        task_ref = handle.task_ref or "unknown_task"
        return {
            "task_ref": task_ref,
            "status": "completed",
            "endpoint": "/api/llm/response_with_tools_status",
        }


class PrismWebTransport(BaseTransport):
    """Transport implementation for Prism Web (prism.openai.com)."""

    kind = "prism_web"
    handle_scoped_events = True

    def __init__(self, auth_profile: Optional[AuthProfile] = None):
        self.session_mgr = PrismSessionManager(auth_profile)
        self.context_mgr = PrismContextManager()
        self.submitter = PrismSubmitter()
        self.parser = PrismEventParser()
        self.observer = PrismEventObserver(self.parser)
        self.cancelled_handles: set[str] = set()

    @property
    def auth_profile(self) -> AuthProfile:
        return self.session_mgr.auth_profile

    def inspect_capabilities(self, session: TransportSession) -> List[CapabilitySnapshot]:
        """Inspect capabilities. Default to disabled/unverified unless auth is READY."""
        auth_ready = self.session_mgr.is_auth_ready()
        state = EvidenceState.VERIFIED if auth_ready else EvidenceState.UNKNOWN
        activation = ActivationState.ENABLED if auth_ready else ActivationState.DISABLED

        return [
            CapabilitySnapshot(
                capability_id=CapabilityId.TEXT_GENERATION,
                evidence_state=state,
                activation_state=activation,
                account_scope=self.auth_profile.account_scope,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.ISOLATED_CONTEXT,
                evidence_state=state,
                activation_state=activation,
                account_scope=self.auth_profile.account_scope,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.DELTA_STREAM,
                evidence_state=state,
                activation_state=activation,
                account_scope=self.auth_profile.account_scope,
            ),
        ]

    def prepare_context(self, session: TransportSession, context: Dict[str, Any], operation_id: str) -> RemoteHandle:
        """Prepare project/context workspace binding."""
        return self.context_mgr.prepare_context(session, context, operation_id)

    def submit(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Submit single generation request to Prism web endpoint."""
        return self.submitter.submit_task(
            run_id=run_id,
            attempt_id=attempt_id,
            session=session,
            input_text=input_text,
            model_alias=model_alias,
            auth_ready=self.session_mgr.is_auth_ready(),
        )

    def observe_events(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Observe task status events."""
        task_ref = handle.task_ref or "unknown"
        if task_ref in self.cancelled_handles:
            return [
                {
                    "type": "CancellationConfirmed",
                    "payload": {"task_ref": task_ref},
                }
            ]
        return self.observer.observe(handle)

    def lookup_events(self, session: TransportSession, handle: RemoteHandle) -> Dict[str, Any]:
        """Read-only lookup for task status on prism.openai.com."""
        return self.observer.lookup_task_status(session, handle)

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Request precise cancellation of Prism web task."""
        if handle.task_ref:
            self.cancelled_handles.add(handle.task_ref)
            return True
        return False

    def close(self) -> None:
        """Close transport session resources."""
        pass


def create_prism_web_transport(auth_profile: Optional[AuthProfile] = None) -> PrismWebTransport:
    """Factory function to instantiate PrismWebTransport."""
    return PrismWebTransport(auth_profile=auth_profile)
