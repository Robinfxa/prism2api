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
    """Verify TEXT_GENERATION is VERIFIED and all other capabilities are UNKNOWN + DISABLED."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "prism_session_token=valid; prism_oai_access_token=valid"
    session = TransportSession(session_id="s1", auth_profile_id="p1")

    caps = transport.inspect_capabilities(session)
    cap_dict = {c.capability_id: c for c in caps}

    assert cap_dict[CapabilityId.TEXT_GENERATION].evidence_state == EvidenceState.VERIFIED
    assert cap_dict[CapabilityId.TEXT_GENERATION].activation_state == ActivationState.ENABLED

    for cid in [
        CapabilityId.ISOLATED_CONTEXT,
        CapabilityId.TASK_LOOKUP,
        CapabilityId.DELTA_STREAM,
        CapabilityId.CANCEL_CONFIRMATION,
        CapabilityId.MODEL_SELECTION,
        CapabilityId.USAGE_REPORTING,
    ]:
        assert cap_dict[cid].evidence_state == EvidenceState.UNKNOWN
        assert cap_dict[cid].activation_state == ActivationState.DISABLED


def test_missing_context_raises_admission_blocked():
    """Verify submit raises AdmissionBlockedError when context binding or sandbox material is missing."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "prism_session_token=valid; prism_oai_access_token=valid"

    # Empty context
    session = TransportSession(session_id="s1", auth_profile_id="p1", context_binding={})
    with pytest.raises(AdmissionBlockedError, match="Missing required live context identity"):
        transport.submit("r1", "att1", session, "hello", "prism-default")

    # Incomplete context (missing sandbox material)
    session2 = TransportSession(
        session_id="s2",
        auth_profile_id="p1",
        context_binding={
            "workspace_ref": "proj_fix_1",
            "conversation_ref": "cdx_fix_1",
            "user_id": "user_fix_1",
        }
    )
    with pytest.raises(AdmissionBlockedError, match="Missing required live context sandbox material"):
        transport.submit("r1", "att1", session2, "hello", "prism-default")


def test_prism_http_transport_submit_and_observe_mocked():
    """Test PrismHttpTransport submit and observe_events via httpx MockTransport with strict identity validation."""
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
    transport.cookie_header = "prism_session_token=valid; prism_oai_access_token=valid"

    session = TransportSession(
        session_id="s1",
        auth_profile_id="p1",
        context_binding={
            "workspace_ref": "proj_fixture_001",
            "conversation_ref": "cdx1_fixture_001",
            "user_id": "user_fixture_001",
            "sandbox_url": "https://prism.openai.com/s/sandboxes/proxy/",
            "sandbox_token": "sandbox_fixture_token_valid_123",
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

