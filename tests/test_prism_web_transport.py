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


def test_prism_context_manager():
    """Test PrismContextManager context preparation."""
    mgr = PrismContextManager()
    session = TransportSession(session_id="s1", auth_profile_id="p1")
    handle = mgr.prepare_context(session, {"workspace_ref": "ws_123"}, operation_id="op_1")

    assert handle.workspace_ref == "ws_123"
    assert handle.conversation_ref == "conv_op_1"


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


def test_prism_web_transport_unconfigured_blocks_submit():
    """Test PrismWebTransport blocks submission when auth status is not READY."""
    transport = create_prism_web_transport()
    session = TransportSession(session_id="s1", auth_profile_id="unconfigured")

    caps = transport.inspect_capabilities(session)
    for cap in caps:
        assert not cap.is_usable

    with pytest.raises(RuntimeError):
        transport.submit(
            run_id="r1",
            attempt_id="att1",
            session=session,
            input_text="hi",
            model_alias="prism-default",
        )


def test_prism_web_transport_ready_submit_and_observe():
    """Test PrismWebTransport submission and event observation when auth status is READY."""
    auth = AuthProfile(profile_id="p_ready", auth_status=AuthStatus.READY)
    transport = create_prism_web_transport(auth_profile=auth)
    session = TransportSession(session_id="s1", auth_profile_id="p_ready")

    caps = transport.inspect_capabilities(session)
    for cap in caps:
        assert cap.is_usable

    handle = transport.submit(
        run_id="r1",
        attempt_id="att1",
        session=session,
        input_text="Hello Prism Web",
        model_alias="prism-default",
    )

    assert handle.task_ref == "prism_task_r1_att1"
    assert handle.raw_metadata["endpoint"] == "/api/llm/response_with_tools_start"

    events = transport.observe_events(handle)
    assert len(events) > 0

    lookup = transport.lookup_events(session, handle)
    assert lookup["status"] == "completed"
    assert lookup["endpoint"] == "/api/llm/response_with_tools_status"
