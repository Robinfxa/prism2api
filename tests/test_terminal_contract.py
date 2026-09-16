"""Second-review terminal contract checks for prism2api @59aad2f.

Synthetic transport events only. No claim about Prism's actual wire schema.
Core adapter, normalizer, supervisor, SQLite and file persistence are not mocked.
Positive controls make blanket failure an invalid solution.
"""
from contextlib import contextmanager
import pytest
from prism2api.config import Settings
from prism2api.provider.adapter import PrismAdapter
from prism2api.runtime.supervisor import RunSupervisor, RunState
from prism2api.storage.journal import StorageJournal
from prism2api.transport.mock_transport import MockTransport


class EventScript(MockTransport):
    def __init__(self, make_events):
        super().__init__()
        self.make_events = make_events
        self.submissions = []

    def submit(self, **kwargs):
        self.submissions.append(kwargs.copy())
        return super().submit(**kwargs)

    def observe_events(self, handle):
        return self.make_events(handle)


def ev(kind, **payload):
    return {"type": kind, "payload": payload}


@contextmanager
def environment(tmp_path, make_events):
    settings = Settings(home_dir=tmp_path / 'home', api_key='audit-only-key')
    journal = StorageJournal(settings)
    transport = EventScript(make_events)
    supervisor = RunSupervisor(settings, journal, PrismAdapter(transport))
    run = supervisor.enqueue_run('default_principal', 'synthetic audit input')
    try:
        yield supervisor, transport, run
    finally:
        journal.close()


def execute_and_record(supervisor, run):
    result = error = None
    try:
        result = supervisor.execute_run(run.run_id, 'synthetic audit input')
    except Exception as exc:
        error = exc
    return supervisor.get_run(run.run_id), result, error


@pytest.mark.parametrize('partial', [False, True], ids=['empty-eof','partial-eof'])
def test_post_submit_eof_is_uncertain_not_failed(tmp_path, partial):
    def events(handle):
        return [ev('TextDelta', text='partial')] if partial else []
    with environment(tmp_path, events) as (sup, transport, run):
        state, result, error = execute_and_record(sup, run)
        assert len(transport.submissions) == 1
        assert result is None and error is not None
        assert state.state == RunState.UNCERTAIN, state.model_dump()
        assert sup.admission_latch is True


@pytest.mark.parametrize('other', ['RunFailed','CancellationConfirmed','ProtocolUnknown'])
def test_conflicting_terminal_evidence_is_not_first_wins(tmp_path, other):
    def events(handle):
        return [ev('RunCompleted', task_ref=handle.task_ref, text='draft'),
                ev(other, task_ref=handle.task_ref, error='contradictory terminal')]
    with environment(tmp_path, events) as (sup, _, run):
        state, result, _ = execute_and_record(sup, run)
        assert state.state == RunState.UNCERTAIN, state.model_dump()
        assert result is None


@pytest.mark.parametrize('kind', ['RunCompleted','RunFailed','CancellationConfirmed'])
def test_explicit_foreign_task_cannot_decide_this_run(tmp_path, kind):
    def events(handle):
        return [ev(kind, task_ref='FOREIGN_TASK', text='unrelated result')]
    with environment(tmp_path, events) as (sup, _, run):
        state, result, _ = execute_and_record(sup, run)
        assert state.state == RunState.UNCERTAIN, state.model_dump()
        assert result is None


def test_bare_completed_name_is_not_complete_output_evidence(tmp_path):
    # No text, finish reason, source binding or evidence of legitimate empty output.
    with environment(tmp_path, lambda handle: [ev('RunCompleted')]) as (sup, _, run):
        state, result, _ = execute_and_record(sup, run)
        assert state.state != RunState.SUCCEEDED, state.model_dump()
        assert result is None


def test_explicit_empty_final_text_must_not_restore_old_buffer(tmp_path):
    def events(handle):
        return [ev('TextDelta', text='STALE'),
                ev('RunCompleted', task_ref=handle.task_ref, text='', finish_reason='stop')]
    with environment(tmp_path, events) as (sup, _, run):
        state, result, _ = execute_and_record(sup, run)
        # Legitimate empty output can be delivered, or unsupported evidence rejected;
        # neither permits returning the stale buffer as the authoritative final text.
        if result is not None:
            assert result.text == '', result.model_dump()
        else:
            assert state.state != RunState.SUCCEEDED


def test_text_after_completion_is_not_appended_to_success(tmp_path):
    def events(handle):
        return [ev('TextDelta', text='FINAL'),
                ev('RunCompleted', task_ref=handle.task_ref, finish_reason='stop'),
                ev('TextDelta', text='UNEXPLAINED_POST_TERMINAL_TEXT')]
    with environment(tmp_path, events) as (sup, _, run):
        state, result, _ = execute_and_record(sup, run)
        # Freeze a proven terminal result, or reject inconsistent input; no corruption.
        if result is not None:
            assert result.text == 'FINAL', result.model_dump()
        else:
            assert state.state != RunState.SUCCEEDED


@pytest.mark.parametrize('kind,expected', [
    ('RunCompleted', RunState.SUCCEEDED),
    ('RunFailed', RunState.FAILED),
    ('CancellationConfirmed', RunState.CANCELLED),
    ('ProtocolUnknown', RunState.UNCERTAIN),
])
def test_positive_control_matching_terminal_classification(tmp_path, kind, expected):
    def events(handle):
        return [ev(kind, task_ref=handle.task_ref, text='FINAL', finish_reason='stop')]
    with environment(tmp_path, events) as (sup, _, run):
        state, result, error = execute_and_record(sup, run)
        assert state.state == expected
        if expected == RunState.SUCCEEDED:
            assert error is None and result.text == 'FINAL'
        else:
            assert result is None and error is not None
