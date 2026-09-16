"""Auth Profile and Base Transport interface for M07."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from prism2api.provider.models import RemoteHandle, CapabilitySnapshot, CapabilityId, EvidenceState, ActivationState
from prism2api.storage.journal import get_iso_now


class AuthStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    READY = "ready"
    EXPIRED = "expired"
    INTERVENTION_REQUIRED = "intervention_required"
    QUARANTINED = "quarantined"


class AuthProfile(BaseModel):
    profile_id: str
    account_scope: str = "default_account"
    auth_status: AuthStatus = AuthStatus.NOT_CONFIGURED
    credential_locator: Optional[str] = None
    last_verified_at: Optional[str] = None
    expiry_evidence: Optional[str] = None


class TransportSession(BaseModel):
    session_id: str
    transport_type: str = "mock"
    auth_profile_id: str
    browser_generation: int = 1
    is_active: bool = True
    context_binding: Dict[str, Any] = Field(default_factory=dict)
    operation_id: Optional[str] = None
    deadline_monotonic: Optional[float] = None
    io_timeout_seconds: Optional[float] = None


class BaseTransport(ABC):
    """Adapter seam, not Prism's wire schema.

    Each network operation MUST bound its own blocking I/O using the supplied
    session/deadline budget. observe_events must yield periodically and stop at
    an evidenced terminal; never aggregate an unbounded upstream response.
    No internal retries of prepare/submit. Cancellation receipt != confirmation.
    """
    kind = "live"
    handle_scoped_events = False

    def prepare_context(self, session, context, operation_id):
        """Create/inspect ONLY the authorized binding; return observed identifiers."""
        raise NotImplementedError("Context preparation needs verified protocol evidence")

    def lookup_events(self, session, handle):
        """Read-only lookup for exactly this task; must never submit or create resources."""
        raise NotImplementedError("Read-only task lookup is not implemented")

    def close(self):
        """Close only resources owned by this transport instance."""
        return None

    @abstractmethod
    def inspect_capabilities(self, session: TransportSession) -> List[CapabilitySnapshot]:
        """Inspect available capabilities for current transport session."""
        pass

    @abstractmethod
    def submit(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Submit generation request to transport. Returns RemoteHandle."""
        pass

    @abstractmethod
    def observe_events(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Observe events from transport."""
        pass

    @abstractmethod
    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Request precise cancellation of transport task."""
        pass
