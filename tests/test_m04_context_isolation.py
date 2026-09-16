"""Tests for M04 Context Isolation and Lease Management (T20-T26)."""

import pytest
from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.context import ContextManager, ContextPolicy, ContextBusyError


@pytest.fixture
def context_mgr(tmp_path):
    settings = Settings(home_dir=tmp_path / ".prism2api")
    journal = StorageJournal(settings)
    return ContextManager(journal.conn)


def test_t20_context_isolation_nonce_verification(context_mgr):
    """T20: Context A and Context B text isolated; nonces do not bleed."""
    ctx_a_text = "Project A secret nonce: 987654"
    ctx_b_text = "Project B secret nonce: 123456"

    assert ContextManager.verify_isolation(
        ctx_a_text, ctx_b_text, nonce_a="987654", nonce_b="123456"
    )
    # Bleed test
    ctx_bleed_text = "Project B text with leaked nonce: 987654"
    assert not ContextManager.verify_isolation(
        ctx_a_text, ctx_bleed_text, nonce_a="987654", nonce_b="123456"
    )


def test_t22_context_busy_lease_collision(context_mgr):
    """T22: Second acquire on active context raises ContextBusyError without damaging first winner."""
    binding = context_mgr.create_context(
        context_id="ctx_shared",
        principal_id="user1",
        auth_profile_id="p1",
        policy=ContextPolicy.ISOLATED,
    )

    lease1 = context_mgr.acquire_lease("ctx_shared", run_id="run_winner")
    assert lease1.is_active

    with pytest.raises(ContextBusyError):
        context_mgr.acquire_lease("ctx_shared", run_id="run_loser")

    # Release winner
    assert context_mgr.release_lease(lease1)

    # Winner release allows new acquire
    lease2 = context_mgr.acquire_lease("ctx_shared", run_id="run_loser")
    assert lease2.is_active
