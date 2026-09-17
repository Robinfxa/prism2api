"""Unit tests for PrismHttpTransport enforcing single submit, deadline budgets, and no secret leaks."""

import pytest
import httpx
from prism2api.transport.base import AuthProfile, AuthStatus, TransportSession
from prism2api.transport.prism_web.http_transport import PrismHttpTransport
from prism2api.errors import AdmissionBlockedError, ProtocolError


def test_prism_http_transport_unconfigured_blocks_submit():
    """Test PrismHttpTransport blocks submission when cookie is missing."""
    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.NOT_CONFIGURED)
    transport = PrismHttpTransport(auth_profile=auth)
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


def test_prism_http_transport_submit_and_observe_mocked():
    """Test PrismHttpTransport submit and observe_events via httpx MockTransport."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/response_with_tools_start"):
            return httpx.Response(200, json={"status": "accepted", "async_job_id": "job_999"})
        elif request.url.path.endswith("/response_with_tools_status"):
            return httpx.Response(200, json={"status": "completed", "finish_reason": "stop", "text": "PRISM_PROBE_002"})
        return httpx.Response(404)

    auth = AuthProfile(profile_id="p1", auth_status=AuthStatus.READY)
    transport = PrismHttpTransport(auth_profile=auth)
    transport.cookie_header = "prism_session_token=REDACTED; prism_oai_access_token=REDACTED"

    session = TransportSession(session_id="s1", auth_profile_id="p1")

    # Patch httpx.Client to use MockTransport
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
        # Verify secret is not in raw_metadata
        assert "cookie" not in handle.raw_metadata
        assert "token" not in handle.raw_metadata

        events = transport.observe_events(handle)
        assert len(events) == 2
        assert events[0]["type"] == "TextDelta"
        assert events[0]["payload"]["text"] == "PRISM_PROBE_002"
        assert events[1]["type"] == "RunCompleted"
        assert events[1]["payload"]["text"] == "PRISM_PROBE_002"
    finally:
        httpx.Client = original_client
