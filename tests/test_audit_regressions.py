"""Independent audit regressions for prism2api @53a228b.
These assert desired safety behavior and intentionally expose defects in that commit.
Only the external transport is replaced. Core/API/SQLite paths are real.
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from prism2api.config import Settings, LimitsConfig
from prism2api.api.app import create_app
from prism2api.client import SDKClient
from prism2api.provider.adapter import PrismAdapter
from prism2api.runtime.context import ContextPolicy
from prism2api.runtime.supervisor import RunSupervisor, RunState, IdempotencyConflictError
from prism2api.storage.journal import StorageJournal
from prism2api.transport.mock_transport import MockTransport


class ScriptedTransport(MockTransport):
    def __init__(self, events=None, failure_at=None):
        super().__init__()
        self.scripted_events = events
        self.failure_at = failure_at
        self.submit_calls = []

    def submit(self, **kwargs):
        self.submit_calls.append(kwargs.copy())
        if self.failure_at == "submit":
            raise TimeoutError("Receipt lost: remote acceptance is unknown")
        return super().submit(**kwargs)

    def observe_events(self, handle):
        if self.failure_at == "observe":
            raise TimeoutError("Connection lost after acceptance")
        if self.scripted_events is not None:
            return self.scripted_events
        return super().observe_events(handle)


@pytest.fixture
def make_env(tmp_path):
    journals = []
    def factory(events=None, failure_at=None, limits=None):
        settings = Settings(home_dir=tmp_path / f"home-{len(journals)}",
                            api_key="audit-only-key",
                            limits=limits or LimitsConfig())
        journal = StorageJournal(settings)
        journals.append(journal)
        transport = ScriptedTransport(events, failure_at)
        supervisor = RunSupervisor(settings, journal, PrismAdapter(transport))
        return settings, journal, transport, supervisor
    yield factory
    for journal in journals:
        journal.close()


def run_once(supervisor, text="synthetic audit input"):
    run = supervisor.enqueue_run(principal_id="default_principal", input_text=text)
    result = supervisor.execute_run(run.run_id, text)
    return run, result


@pytest.mark.parametrize("events", [
    [],
    [{"type": "TextDelta", "payload": {"text": "partial"}}],
    [{"type": "RunFailed", "payload": {"error": "upstream failed"}}],
    [{"type": "CancellationConfirmed", "payload": {"task_ref": "synthetic"}}],
    [{"type": "UnexpectedTerminal", "payload": {"status": "unknown"}}],
], ids=["empty", "partial-eof", "remote-failed", "remote-cancelled", "unknown-terminal"])
def test_no_false_success(make_env, events):
    _, _, _, sup = make_env(events=events)
    run = sup.enqueue_run(principal_id="default_principal", input_text="synthetic")
    try:
        sup.execute_run(run.run_id, "synthetic")
    except Exception:
        pass
    assert sup.get_run(run.run_id).state != RunState.SUCCEEDED


def test_missing_model_evidence_remains_unknown(make_env):
    _, _, _, sup = make_env()
    _, result = run_once(sup)
    assert result.provider_model_id_confirmed is None


@pytest.mark.parametrize("failure_at", ["submit", "observe"])
def test_ambiguous_transport_failure_is_uncertain(make_env, failure_at):
    _, _, transport, sup = make_env(failure_at=failure_at)
    run = sup.enqueue_run(principal_id="default_principal", input_text="synthetic")
    with pytest.raises(TimeoutError):
        sup.execute_run(run.run_id, "synthetic")
    assert len(transport.submit_calls) == 1
    assert sup.get_run(run.run_id).state == RunState.UNCERTAIN
    assert sup.admission_latch is True


def seed_interrupted_run(sup):
    # A persisted interrupted-state fixture, NOT a claim to test a real process kill.
    run = sup.enqueue_run(principal_id="default_principal", input_text="interrupted")
    sup.transition_state(run.run_id, RunState.QUEUED, RunState.PREPARING)
    sup.transition_state(run.run_id, RunState.PREPARING, RunState.SUBMITTING)
    return run


def test_recovery_latch_blocks_new_dispatch(make_env):
    settings, journal, transport, sup = make_env()
    seed_interrupted_run(sup)
    restarted = RunSupervisor(settings, journal, PrismAdapter(transport))
    assert restarted.admission_latch is True
    try:
        run_once(restarted, "must not be submitted")
    except Exception:
        pass
    assert transport.submit_calls == []


def test_existing_uncertain_survives_second_recovery(make_env):
    settings, journal, transport, sup = make_env()
    run = seed_interrupted_run(sup)
    first_restart = RunSupervisor(settings, journal, PrismAdapter(transport))
    assert first_restart.get_run(run.run_id).state == RunState.UNCERTAIN
    second_restart = RunSupervisor(settings, journal, PrismAdapter(transport))
    assert second_restart.get_run(run.run_id).state == RunState.UNCERTAIN
    assert second_restart.admission_latch is True


def test_execution_cannot_replace_accepted_input(make_env):
    _, _, transport, sup = make_env()
    run = sup.enqueue_run(principal_id="default_principal", input_text="ORIGINAL")
    try:
        sup.execute_run(run.run_id, "DIFFERENT")
    except Exception:
        pass
    assert not transport.submit_calls or transport.submit_calls[0]["input_text"] == "ORIGINAL"


def test_remote_handle_is_persisted(make_env):
    _, journal, _, sup = make_env()
    run, _ = run_once(sup)
    row = journal.conn.execute("SELECT remote_handle FROM submit_attempts WHERE run_id=?",
                               (run.run_id,)).fetchone()
    assert row is not None and row["remote_handle"] is not None


def test_saved_result_keeps_manifest_reference(make_env):
    _, _, _, sup = make_env()
    run, result = run_once(sup)
    saved = json.loads(Path(sup.get_run(run.run_id).result_ref).read_text())
    assert result.manifest_ref is not None
    assert saved["manifest_ref"] == result.manifest_ref


def test_success_has_completion_evidence(make_env):
    _, _, _, sup = make_env()
    _, result = run_once(sup)
    manifest = json.loads(Path(result.manifest_ref).read_text())
    assert manifest["completion_evidence"] is not None


def test_same_key_different_context_is_conflict(make_env):
    _, _, _, sup = make_env()
    for context_id in ["context-a", "context-b"]:
        sup.context_mgr.create_context(context_id, "default_principal",
                                       sup.adapter.auth_profile.profile_id, ContextPolicy.EXPLICIT)
    sup.enqueue_run("default_principal", "same input", context_policy=ContextPolicy.EXPLICIT,
                    context_id="context-a", idempotency_key="same-key")
    with pytest.raises(IdempotencyConflictError):
        sup.enqueue_run("default_principal", "same input", context_policy=ContextPolicy.EXPLICIT,
                        context_id="context-b", idempotency_key="same-key")


def test_foreign_context_cannot_be_used(make_env):
    _, _, transport, sup = make_env()
    sup.context_mgr.create_context("owned-by-A", "principal-A",
                                   sup.adapter.auth_profile.profile_id, ContextPolicy.EXPLICIT)
    try:
        run = sup.enqueue_run("principal-B", "synthetic", context_policy=ContextPolicy.EXPLICIT,
                              context_id="owned-by-A")
        sup.execute_run(run.run_id, "synthetic")
    except Exception:
        pass
    assert transport.submit_calls == []


def test_nonprefix_rewrite_cannot_return_stale_success(make_env):
    events = [
        {"type": "TextSnapshot", "payload": {"text": "OLD"}},
        {"type": "TextSnapshot", "payload": {"text": "CORRECTED"}},
        {"type": "RunCompleted", "payload": {"text": "CORRECTED", "finish_reason": "stop"}},
    ]
    _, _, _, sup = make_env(events=events)
    run = sup.enqueue_run("default_principal", "synthetic")
    try:
        result = sup.execute_run(run.run_id, "synthetic")
    except Exception:
        assert sup.get_run(run.run_id).state != RunState.SUCCEEDED
    else:
        assert result.text == "CORRECTED"


@pytest.mark.parametrize("extra", [
    {"stream": True},
    {"n": 2},
    {"tools": [{"type": "function", "function": {"name": "audit"}}]},
    {"max_tokens": 1},
], ids=["stream", "n", "tools", "max-tokens"])
def test_unsupported_api_fields_rejected_before_submit(make_env, extra):
    settings, _, transport, sup = make_env()
    with TestClient(create_app(settings, sup)) as client:
        response = client.post("/v1/chat/completions", headers={"X-API-Key": settings.api_key},
                               json={"model": "prism-default",
                                     "messages": [{"role": "user", "content": "synthetic"}], **extra})
    assert response.status_code in (400, 422)
    assert transport.submit_calls == []


def test_multiple_messages_not_silently_discarded(make_env):
    settings, _, transport, sup = make_env()
    with TestClient(create_app(settings, sup)) as client:
        response = client.post("/v1/chat/completions", headers={"X-API-Key": settings.api_key},
                               json={"model": "prism-default", "messages": [
                                   {"role": "user", "content": "old turn"},
                                   {"role": "assistant", "content": "old answer"},
                                   {"role": "user", "content": "actual question"}]})
    # Current declared subset supports one user message only.
    assert response.status_code in (400, 422)
    assert transport.submit_calls == []


def test_unlisted_model_not_accepted(make_env):
    settings, _, transport, sup = make_env()
    with TestClient(create_app(settings, sup)) as client:
        response = client.post("/v1/chat/completions", headers={"X-API-Key": settings.api_key},
                               json={"model": "nonexistent-model",
                                     "messages": [{"role": "user", "content": "synthetic"}]})
    assert response.status_code in (400, 404, 422)
    assert transport.submit_calls == []


def test_unknown_usage_not_fabricated(make_env):
    settings, _, _, sup = make_env()
    with TestClient(create_app(settings, sup)) as client:
        response = client.post("/v1/chat/completions", headers={"X-API-Key": settings.api_key},
                               json={"model": "prism-default",
                                     "messages": [{"role": "user", "content": "synthetic"}]})
    assert response.status_code == 200
    assert response.json().get("usage") is None


def test_cross_principal_cancel_is_rejected(make_env):
    settings, _, _, sup = make_env()
    run = sup.enqueue_run("another-principal", "synthetic")
    # Hold dispatch only while checking auth. This is a scheduling fixture,
    # not a mock of authorization; query/cancel and the SQLite row are real.
    sup._generation_lock.acquire()
    with TestClient(create_app(settings, sup)) as client:
        try:
            headers = {"X-API-Key": settings.api_key}
            assert client.get(f"/prism/v1/runs/{run.run_id}", headers=headers).status_code == 404
            response = client.post(f"/prism/v1/runs/{run.run_id}/cancel", headers=headers)
            assert response.status_code == 404
            assert sup.get_run(run.run_id).state == RunState.QUEUED
            assert sup.get_run(run.run_id).cancel_intent is False
        finally:
            sup._generation_lock.release()


def test_http_writer_cannot_bypass_embedded_lock(tmp_path):
    settings = Settings(home_dir=tmp_path / "single-owner", api_key="audit-only-key")
    owner = SDKClient(settings=settings)
    rejected = False
    try:
        try:
            create_app(settings)
        except Exception:
            rejected = True
        assert rejected, "HTTP factory created another writer while SDK held the HOME lock"
    finally:
        owner.close()


def test_queue_budget_enforced(make_env):
    _, _, _, sup = make_env(limits=LimitsConfig(max_queue_size=1))
    sup.enqueue_run("default_principal", "one")
    rejected = False
    try:
        sup.enqueue_run("default_principal", "two")
    except Exception:
        rejected = True
    assert rejected


def test_guard_itself_blocks_network():
    import socket
    with pytest.raises(RuntimeError, match="AUDIT_NETWORK_DISABLED"):
        socket.create_connection(("example.invalid", 443))
