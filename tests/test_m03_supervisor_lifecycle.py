"""Tests for M03 RunSupervisor Lifecycle and Idempotency (T12-T19)."""

import pytest
from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import (
    RunSupervisor,
    RunState,
    IdempotencyConflictError,
)


@pytest.fixture
def supervisor(tmp_path):
    settings = Settings(home_dir=tmp_path / ".prism2api", transport_mode="mock")
    journal = StorageJournal(settings)
    return RunSupervisor(settings, journal)


def test_t12_idempotency_same_key_same_fingerprint(supervisor):
    """T12: Submitting same Idempotency-Key with same input returns existing run_id."""
    r1 = supervisor.enqueue_run(
        principal_id="user1",
        input_text="hello world",
        idempotency_key="key-abc",
    )
    r2 = supervisor.enqueue_run(
        principal_id="user1",
        input_text="hello world",
        idempotency_key="key-abc",
    )
    assert r1.run_id == r2.run_id


def test_t13_idempotency_same_key_different_fingerprint(supervisor):
    """T13: Submitting same Idempotency-Key with different input raises IdempotencyConflictError."""
    supervisor.enqueue_run(
        principal_id="user1",
        input_text="hello world",
        idempotency_key="key-abc",
    )
    with pytest.raises(IdempotencyConflictError):
        supervisor.enqueue_run(
            principal_id="user1",
            input_text="different input text",
            idempotency_key="key-abc",
        )


def test_t14_intent_logged_before_dispatch_and_crash_recovery(tmp_path):
    """T14: Process crash after intent write leaves un-finalized run in UNCERTAIN state."""
    settings = Settings(home_dir=tmp_path / ".prism2api", transport_mode="mock")
    journal1 = StorageJournal(settings)
    sup1 = RunSupervisor(settings, journal1)

    r1 = sup1.enqueue_run(principal_id="user1", input_text="crash test")
    # Transition to SUBMITTING (intent logged)
    sup1.transition_state(r1.run_id, RunState.QUEUED, RunState.PREPARING)
    sup1.transition_state(r1.run_id, RunState.PREPARING, RunState.SUBMITTING)
    journal1.close()

    # Simulate process restart (new supervisor instance on same DB)
    journal2 = StorageJournal(settings)
    sup2 = RunSupervisor(settings, journal2)
    restarted_run = sup2.get_run(r1.run_id)

    assert restarted_run.state == RunState.UNCERTAIN
    assert sup2.admission_latch is True
    journal2.close()


def test_t17_cancel_queued_run(supervisor):
    """T17: Cancelling queued run transitions state to CANCELLED."""
    r1 = supervisor.enqueue_run(principal_id="user1", input_text="cancel test")
    cancelled_r1 = supervisor.cancel_run(r1.run_id)
    assert cancelled_r1.state == RunState.CANCELLED
    assert cancelled_r1.cancel_intent is True
