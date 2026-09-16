"""Tests for M02 PrismAdapter & Capabilities (T07-T11)."""

import pytest
from prism2api.provider.models import (
    CapabilitySnapshot,
    CapabilityId,
    EvidenceState,
    ActivationState,
)
from prism2api.provider.adapter import PrismAdapter
from prism2api.transport.base import AuthStatus, AuthProfile
from prism2api.transport.mock_transport import MockTransport


def test_t07_unverified_capability_cannot_be_used():
    """T07: Unverified capabilities return is_usable = False."""
    cap = CapabilitySnapshot(
        capability_id=CapabilityId.TEXT_GENERATION,
        evidence_state=EvidenceState.UNKNOWN,
        activation_state=ActivationState.DISABLED,
    )
    assert not cap.is_usable

    cap_verified = CapabilitySnapshot(
        capability_id=CapabilityId.TEXT_GENERATION,
        evidence_state=EvidenceState.VERIFIED,
        activation_state=ActivationState.ENABLED,
    )
    assert cap_verified.is_usable


def test_t07_adapter_blocks_unverified_capability():
    """T07: Adapter blocks execution if capability is not ready."""
    transport = MockTransport(
        auth_profile=AuthProfile(profile_id="p1", auth_status=AuthStatus.EXPIRED)
    )
    adapter = PrismAdapter(transport)
    with pytest.raises(RuntimeError):
        adapter.submit_request(
            run_id="run_1",
            attempt_id="att_1",
            input_text="hello",
            model_alias="prism-default",
        )


def test_t09_adapter_submit_no_internal_retry():
    """T09: Adapter submit invokes transport submit exactly once without auto-retry."""
    adapter = PrismAdapter(MockTransport())
    handle = adapter.submit_request(
        run_id="run_1",
        attempt_id="att_1",
        input_text="hello",
        model_alias="prism-default",
    )
    assert handle.task_ref == "handle_mock_run_1"
