"""Unit tests for PrismWebTransport (M07 Transport for prism.openai.com)."""

import pytest
from prism2api.transport.base import AuthProfile, AuthStatus, TransportSession
from prism2api.transport.prism_web import (
    PrismWebTransport,
    PrismSessionManager,
    PrismContextManager,
    PrismSubmitter,
    PrismEventParser,
    PrismEventObserver,
    create_prism_web_transport,
)
from prism2api.provider.models import CapabilityId, EvidenceState, ActivationState


def test_prism_session_manager():
    """Test PrismSessionManager auth status updates."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.NOT_CONFIGURED)
    mgr = PrismSessionManager(auth)
    assert not mgr.is_auth_ready()

    mgr.update_status(AuthStatus.READY)
    assert mgr.is_auth_ready()


def test_prism_context_manager_unverified_blocks():
    """Test PrismContextManager raises NotImplementedError without Grade A evidence."""
    mgr = PrismContextManager()
    session = TransportSession(session_id="s1", auth_profile_id="p1")
    with pytest.raises(NotImplementedError):
        mgr.prepare_context(session, {"workspace_ref": "ws_123"}, operation_id="op_1")


def test_prism_event_parser():
    """Test PrismEventParser mapping raw status events to internal event schemas."""
    parser = PrismEventParser()

    raw_completed = {
        "type": "RunCompleted",
        "payload": {"finish_reason": "stop", "text": "Generated text"},
    }
    parsed = parser.parse_payload(raw_completed, task_ref="task_100")
    assert parsed["type"] == "RunCompleted"
    assert parsed["payload"]["task_ref"] == "task_100"
    assert parsed["payload"]["text"] == "Generated text"

    raw_unknown = {"type": "CustomUnregisteredEvent", "payload": {}}
    parsed_unknown = parser.parse_payload(raw_unknown, task_ref="task_100")
    assert parsed_unknown["type"] == "ProtocolUnknown"


def test_prism_web_transport_demotes_capabilities_to_unknown_disabled():
    """Test PrismWebTransport demotes capabilities to UNKNOWN + DISABLED without Grade A evidence."""
    auth = AuthProfile(profile_id="p_ready", auth_status=AuthStatus.READY)
    transport = create_prism_web_transport(auth_profile=auth)
    session = TransportSession(session_id="s1", auth_profile_id="p_ready")

    caps = transport.inspect_capabilities(session)
    for cap in caps:
        assert cap.evidence_state == EvidenceState.UNKNOWN
        assert cap.activation_state == ActivationState.DISABLED
        assert not cap.is_usable


def test_prism_web_transport_unverified_blocks_submit_and_observe():
    """Test PrismWebTransport blocks submit and observe when unverified."""
    auth = AuthProfile(profile_id="p_ready", auth_status=AuthStatus.READY)
    transport = create_prism_web_transport(auth_profile=auth)
    session = TransportSession(session_id="s1", auth_profile_id="p_ready")

    with pytest.raises(RuntimeError, match="Unverified transport"):
        transport.submit(
            run_id="r1",
            attempt_id="att1",
            session=session,
            input_text="hi",
            model_alias="prism-default",
        )

    with pytest.raises(RuntimeError, match="Event observation requires Grade A live protocol evidence"):
        transport.observe_events(None)

    with pytest.raises(NotImplementedError, match="unverified"):
        transport.lookup_events(session, None)

