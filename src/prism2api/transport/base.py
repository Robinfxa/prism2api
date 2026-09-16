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


class BaseTransport(ABC):
    """Abstract base class for all Prism transport layers."""

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
