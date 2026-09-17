"""Unit tests for PrismHttpTransport enforcing hardened protocol contracts, identity validation, and capabilities lockdown."""

import pytest
import httpx
from prism2api.transport.base import AuthProfile, AuthStatus, TransportSession
from prism2api.transport.prism_web.http_transport import PrismHttpTransport
from prism2api.errors import AdmissionBlockedError, ProtocolError
from prism2api.provider.models import CapabilityId, EvidenceState, ActivationState


def test_prism_http_transport_unconfigured_blocks_submit():
    """Test PrismHttpTransport blocks submission when cookie is missing."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.NOT_CONFIGURED, credential_locator="/tmp/nonexistent_cred_locator.json")
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = None
    transport._auth_profile.auth_status = AuthStatus.NOT_CONFIGURED
    session = TransportSession(session_id="s1", auth_profile_id="p1")

    caps = transport.inspect_capabilities(session)
    assert not caps[0].is_usable

    with pytest.raises(AdmissionBlockedError):
        transport.submit(
            run_id="r1",
            attempt_id="att1",
            session=session,
            input_text="hi",
            model_alias="prism-default",
        )


def test_capability_states_hardened():
    """Verify TEXT_GENERATION is VERIFIED and all other capabilities including EXPLICIT_CONTINUATION are UNKNOWN + DISABLED."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    from prism2api.transport.prism_web.live_profile import PrismLiveProfile
    transport.live_profile = PrismLiveProfile(
        user_id="u1", sandbox_url="https://sb", sandbox_token="tok", cookie_header="c=1"
    )
    transport.cookie_header = "c=1"
    session = TransportSession(session_id="s1", auth_profile_id="p1")

    caps = transport.inspect_capabilities(session)
    cap_dict = {c.capability_id: c for c in caps}

    assert cap_dict[CapabilityId.TEXT_GENERATION].evidence_state == EvidenceState.VERIFIED
    assert cap_dict[CapabilityId.TEXT_GENERATION].activation_state == ActivationState.ENABLED

    for cid in [
        CapabilityId.ISOLATED_CONTEXT,
        CapabilityId.TASK_LOOKUP,
        CapabilityId.EXPLICIT_CONTINUATION,
        CapabilityId.DELTA_STREAM,
        CapabilityId.CANCEL_CONFIRMATION,
        CapabilityId.MODEL_SELECTION,
        CapabilityId.USAGE_REPORTING,
    ]:
        assert cap_dict[cid].evidence_state == EvidenceState.UNKNOWN
        assert cap_dict[cid].activation_state == ActivationState.DISABLED


def test_legacy_credentials_and_env_cookies_ignored(monkeypatch, tmp_path):
    """Verify legacy credentials.json and PRISM_COOKIE env vars DO NOT enable live transport."""
    monkeypatch.setenv("PRISM_COOKIE", "prism_session_token=fake")
    monkeypatch.setenv("PRISM_SESSION_COOKIE", "prism_session_token=fake")
    monkeypatch.setenv("PRISM_LIVE_PROFILE", str(tmp_path / "nonexistent.json"))

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.NOT_CONFIGURED)
    transport = PrismHttpTransport(auth_profile=auth)

    assert transport.auth_profile.auth_status == AuthStatus.NOT_CONFIGURED
    assert transport.live_profile is None
    assert transport.cookie_header is None


def test_secrets_in_context_binding_ignored():
    """Verify secrets passed in context_binding are IGNORED when live_profile is missing."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "c=1"
    transport.live_profile = None  # Ensure live_profile is None

    session = TransportSession(
        session_id="s1",
        auth_profile_id="p1",
        context_binding={
            "workspace_ref": "proj_1",
            "conversation_ref": "cdx_1",
            "user_id": "secret_user_in_context",
            "sandbox_url": "https://secret_sb_in_context",
            "sandbox_token": "secret_token_in_context",
        }
    )

    with pytest.raises(AdmissionBlockedError, match="PrismLiveProfile is missing/invalid"):
        transport.submit("r1", "att1", session, "hi", "prism-default")


def test_prism_http_transport_submit_and_observe_mocked():
    """Test PrismHttpTransport submit and observe_events via httpx MockTransport with PrismLiveProfile."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/response_with_tools_start"):
            return httpx.Response(
                200,
                json={
                    "request_id": "job_999",
                    "turn_state": {"async_job_id": "job_999", "conversation_id": "cdx1_fixture_001"},
                }
            )
        elif request.url.path.endswith("/response_with_tools_status"):
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "request_id": "job_999",
                    "codex_async_job_id": "job_999",
                    "conversationId": "cdx1_fixture_001",
                    "response": {
                        "status": "success",
                        "payload": {
                            "conversationId": "cdx1_fixture_001",
                            "output": [
                                {
                                    "content": [
                                        {"type": "output_text", "text": "PRISM_PROBE_002"}
                                    ]
                                }
                            ]
                        }
                    }
                }
            )
        return httpx.Response(404)

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    from prism2api.transport.prism_web.live_profile import PrismLiveProfile
    transport.live_profile = PrismLiveProfile(
        user_id="user_fixture_001",
        sandbox_url="https://prism.openai.com/s/sandboxes/proxy/",
        sandbox_token="sandbox_fixture_token_valid_123",
        cookie_header="prism_session_token=valid; prism_oai_access_token=valid"
    )
    transport.cookie_header = transport.live_profile.cookie_header

    session = TransportSession(
        session_id="s1",
        auth_profile_id="p1",
        context_binding={
            "workspace_ref": "proj_fixture_001",
            "conversation_ref": "cdx1_fixture_001",
        }
    )

    original_client = httpx.Client
    def custom_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        return original_client(*args, **kwargs)

    httpx.Client = custom_client
    try:
        handle = transport.submit(
            run_id="r1",
            attempt_id="att1",
            session=session,
            input_text="Reply exactly: PRISM_PROBE_002",
            model_alias="prism-default",
        )

        assert handle.task_ref == "job_999"
        assert handle.message_ref is None
        assert handle.server_event_cursor is None
        assert "turn_state" in handle.raw_metadata

        events = transport.observe_events(handle)
        assert len(events) == 2
        assert events[0]["type"] == "TextDelta"
        assert events[0]["payload"]["text"] == "PRISM_PROBE_002"
        assert events[1]["type"] == "RunCompleted"
        assert events[1]["payload"]["text"] == "PRISM_PROBE_002"
    finally:
        httpx.Client = original_client



def test_status_identity_mismatch_raises_protocol_error():
    """Verify status response identity mismatch raises ProtocolError."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "request_id": "WRONG_JOB_ID",
                "codex_async_job_id": "job_999",
                "conversationId": "cdx1_fixture_001",
                "response": {"status": "success", "payload": {"output": []}}
            }
        )

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "prism_session_token=valid"

    from prism2api.provider.models import RemoteHandle
    handle = RemoteHandle(
        workspace_ref="proj_fixture_001",
        conversation_ref="cdx1_fixture_001",
        task_ref="job_999",
        raw_metadata={"turn_state": {"async_job_id": "job_999"}}
    )

    original_client = httpx.Client
    def custom_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        return original_client(*args, **kwargs)

    httpx.Client = custom_client
    try:
        with pytest.raises(ProtocolError, match="Identity mismatch in status response"):
            transport.observe_events(handle)
    finally:
        httpx.Client = original_client


def test_status_missing_request_id_raises_protocol_error():
    """Verify status response missing request_id raises ProtocolError."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "codex_async_job_id": "job_999",
                "conversationId": "cdx1_fixture_001",
                "response": {"status": "success", "payload": {"output": []}}
            }
        )

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "prism_session_token=valid"

    from prism2api.provider.models import RemoteHandle
    handle = RemoteHandle(
        workspace_ref="proj_fixture_001",
        conversation_ref="cdx1_fixture_001",
        task_ref="job_999",
        raw_metadata={"turn_state": {"async_job_id": "job_999"}}
    )

    original_client = httpx.Client
    def custom_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        return original_client(*args, **kwargs)

    httpx.Client = custom_client
    try:
        with pytest.raises(ProtocolError, match="Missing required request_id in status response"):
            transport.observe_events(handle)
    finally:
        httpx.Client = original_client


def test_submit_missing_request_id_or_turn_state_raises_protocol_error():
    """Verify submit response missing request_id or turn_state raises ProtocolError and does not fallback to async_job_id."""
    def mock_missing_request_id(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "async_job_id": "async_job_123",
                "turn_state": {"async_job_id": "async_job_123"}
            }
        )

    def mock_missing_turn_state(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "req_123",
            }
        )

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    from prism2api.transport.prism_web.live_profile import PrismLiveProfile
    transport.live_profile = PrismLiveProfile(
        user_id="u1", sandbox_url="https://sb", sandbox_token="tok", cookie_header="c=1"
    )
    transport.cookie_header = "c=1"

    session = TransportSession(
        session_id="s1",
        auth_profile_id="p1",
        context_binding={"workspace_ref": "proj_1", "conversation_ref": "cdx_1"}
    )

    original_client = httpx.Client

    # Test missing request_id
    def client_missing_req_id(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_missing_request_id)
        return original_client(*args, **kwargs)

    httpx.Client = client_missing_req_id
    try:
        with pytest.raises(ProtocolError, match="Submit response missing required remote request_id"):
            transport.submit("r1", "att1", session, "hello", "prism-default")
    finally:
        httpx.Client = original_client

    # Test missing turn_state
    def client_missing_turn_state(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_missing_turn_state)
        return original_client(*args, **kwargs)

    httpx.Client = client_missing_turn_state
    try:
        with pytest.raises(ProtocolError, match="Submit response missing required remote turn_state"):
            transport.submit("r1", "att1", session, "hello", "prism-default")
    finally:
        httpx.Client = original_client



