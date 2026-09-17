"""PrismWebTransport (EXPERIMENTAL / UNVERIFIED SCAFFOLD).

IMPORTANT:
This implementation is an unverified draft scaffold.
Without Grade A live wire protocol evidence captured from prism.openai.com,
all capabilities MUST remain UNKNOWN + DISABLED and submit requests MUST be rejected.
No synthetic completion events, fake task IDs, or fake lookups are permitted.
"""

import time
from typing import List, Dict, Any, Optional
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
    """Manages authentication profiles and session status for prism.openai.com (unverified scaffold)."""

    def __init__(self, auth_profile: Optional[AuthProfile] = None):
        self.auth_profile = auth_profile or AuthProfile(
            profile_id="prism_web_unverified",
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
    """Handles project/context workspace bindings (unverified scaffold)."""

    def prepare_context(
        self,
        session: TransportSession,
        context: Dict[str, Any],
        operation_id: str,
    ) -> RemoteHandle:
        """Prepare context (unverified scaffold)."""
        raise NotImplementedError("PrismWebTransport: Context preparation requires Grade A live protocol evidence.")


class PrismSubmitter:
    """Generation submission attempt to Prism web endpoints (unverified scaffold)."""

    def submit_task(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Reject generation submission until Grade A live protocol evidence is collected."""
        raise RuntimeError("PrismWebTransport: Unverified transport. Live Prism web protocol evidence required before submitting requests.")


class PrismEventParser:
    """Parses Prism web status payloads and maps to normalized event dictionaries (experimental scaffold)."""

    @staticmethod
    def parse_payload(raw_event: Dict[str, Any], task_ref: str) -> Dict[str, Any]:
        """Map raw Prism event payload to internal normalized event format."""
        ev_type = raw_event.get("type", "ProtocolUnknown")

        if ev_type == "SubmissionObserved":
            return {
                "type": "SubmissionObserved",
                "payload": {"task_ref": task_ref, "status": raw_event.get("payload", {}).get("status", "accepted")},
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
    """Observes status and streams events for Prism web tasks (unverified scaffold)."""

    def __init__(self, parser: PrismEventParser):
        self.parser = parser

    def observe(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Observation disabled without Grade A live wire protocol streams."""
        raise RuntimeError("PrismWebTransport: Event observation requires Grade A live protocol evidence.")

    def lookup_task_status(self, session: TransportSession, handle: RemoteHandle) -> Dict[str, Any]:
        """Read-only lookup disabled without Grade A live wire protocol endpoints."""
        raise NotImplementedError("PrismWebTransport: Task lookup endpoint is unverified.")


class PrismWebTransport(BaseTransport):
    """Transport implementation for Prism Web (prism.openai.com - UNVERIFIED SCAFFOLD)."""

    kind = "prism_web"
    handle_scoped_events = False  # Set to False until handle-scoped live event streams are verified

    def __init__(self, auth_profile: Optional[AuthProfile] = None):
        self.session_mgr = PrismSessionManager(auth_profile)
        self.context_mgr = PrismContextManager()
        self.submitter = PrismSubmitter()
        self.parser = PrismEventParser()
        self.observer = PrismEventObserver(self.parser)

    @property
    def auth_profile(self) -> AuthProfile:
        return self.session_mgr.auth_profile

    def inspect_capabilities(self, session: TransportSession) -> List[CapabilitySnapshot]:
        """Inspect capabilities.

        Without Grade A live wire protocol evidence, all capabilities MUST remain
        UNKNOWN + DISABLED regardless of auth_profile.auth_status.
        """
        return [
            CapabilitySnapshot(
                capability_id=CapabilityId.TEXT_GENERATION,
                evidence_state=EvidenceState.UNKNOWN,
                activation_state=ActivationState.DISABLED,
                account_scope=self.auth_profile.account_scope,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.ISOLATED_CONTEXT,
                evidence_state=EvidenceState.UNKNOWN,
                activation_state=ActivationState.DISABLED,
                account_scope=self.auth_profile.account_scope,
            ),
            CapabilitySnapshot(
                capability_id=CapabilityId.DELTA_STREAM,
                evidence_state=EvidenceState.UNKNOWN,
                activation_state=ActivationState.DISABLED,
                account_scope=self.auth_profile.account_scope,
            ),
        ]

    def prepare_context(self, session: TransportSession, context: Dict[str, Any], operation_id: str) -> RemoteHandle:
        """Prepare project/context workspace binding (unverified scaffold)."""
        return self.context_mgr.prepare_context(session, context, operation_id)

    def submit(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Reject generation submit until Grade A live protocol evidence is collected."""
        return self.submitter.submit_task(
            run_id=run_id,
            attempt_id=attempt_id,
            session=session,
            input_text=input_text,
            model_alias=model_alias,
        )

    def observe_events(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Observe task status events (unverified scaffold)."""
        return self.observer.observe(handle)

    def lookup_events(self, session: TransportSession, handle: RemoteHandle) -> Dict[str, Any]:
        """Read-only lookup for task status on prism.openai.com (unverified scaffold)."""
        return self.observer.lookup_task_status(session, handle)

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Request cancellation (unverified scaffold). Returns False as remote endpoint is unverified."""
        return False

    def close(self) -> None:
        """Close transport session resources."""
        pass


def create_prism_web_transport(auth_profile: Optional[AuthProfile] = None) -> PrismWebTransport:
    """Factory function to instantiate PrismWebTransport (unverified scaffold)."""
    return PrismWebTransport(auth_profile=auth_profile)

