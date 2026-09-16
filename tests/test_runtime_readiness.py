"""Real core paths, synthetic boundary transport. No live Prism claims."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from prism2api.config import Settings, LimitsConfig, TimeoutsConfig
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import RunSupervisor, RunState, IdempotencyConflictError
from prism2api.runtime.context import ContextPolicy, ContextBusyError
from prism2api.provider.adapter import PrismAdapter
from prism2api.provider.models import RemoteHandle, CapabilityId
from prism2api.transport.mock_transport import MockTransport
from prism2api.errors import PrismError, OutcomeError, AdmissionBlockedError, ResultUnavailableError
from prism2api.client import SDKClient, ClientMode, SingleInstanceLockError
from prism2api.api.app import create_app


class CountingTransport(MockTransport):
    def __init__(self):
        super().__init__()
        self.calls=[]
        self.prepare_calls=[]
        self.lookups=[]
        self.cancel_calls=[]
        self.fail_prepare=False
        self.fail_observe=False
        self.events=None
        self.mutate_submit=None
    def prepare_context(self,session,context,operation_id):
        self.prepare_calls.append(operation_id)
        if self.fail_prepare:
            raise TimeoutError('possible remote resource created')
        return super().prepare_context(session,context,operation_id)
    def submit(self,**kwargs):
        self.calls.append(kwargs.copy())
        if self.mutate_submit:
            self.mutate_submit(kwargs)
        return super().submit(**kwargs)
    def observe_events(self,handle):
        if self.fail_observe:
            raise TimeoutError('observation lost')
        if self.events:
            return self.events(handle)
        return super().observe_events(handle)
    def lookup_events(self,session,handle):
        self.lookups.append(handle)
        return super().observe_events(handle)
    def request_cancel(self,handle):
        self.cancel_calls.append(handle)
        return super().request_cancel(handle)


@pytest.fixture
def env(tmp_path):
    settings=Settings(home_dir=tmp_path/'home',api_key='unit-test-key',transport_mode='mock')
    journal=StorageJournal(settings)
    transport=CountingTransport()
    sup=RunSupervisor(settings,journal,PrismAdapter(transport))
    yield settings,journal,transport,sup
    journal.close()


def accept(sup,text='input',key=None):
    return sup.enqueue_run('default_principal',text,idempotency_key=key)


def test_default_is_unconfigured_and_never_returns_mock(tmp_path):
    settings=Settings(home_dir=tmp_path/'fresh')
    with TestClient(create_app(settings)) as client:
        headers={'X-API-Key':settings.api_key}
        assert settings.api_key != 'prism-local-key'
        assert len(settings.api_key)>=32
        assert client.get('/health/ready').status_code==503
        assert client.get('/v1/models',headers=headers).json()['data']==[]
        response=client.post('/v1/chat/completions',headers=headers,json={'model':'prism-default','messages':[{'role':'user','content':'do not dispatch'}]})
        assert response.status_code==503


def test_native_worker_completes_and_idempotent_retry_is_read_only(env):
    settings,journal,transport,sup=env
    with TestClient(create_app(settings,sup)) as client:
        headers={'X-API-Key':settings.api_key,'Idempotency-Key':'native-repeat'}
        first=client.post('/prism/v1/runs',headers=headers,json={'input_text':'native text'})
        assert first.status_code==202
        rid=first.json()['run_id']
        sup.wait(rid,timeout=2)
        result=client.get(f'/prism/v1/runs/{rid}/result',headers=headers)
        assert result.status_code==200
        assert result.json()['transport_kind']=='mock'
        assert result.json()['usage'] is None
        assert 'manifest_ref' not in result.json()
        again=client.post('/prism/v1/runs',headers=headers,json={'input_text':'native text'})
        assert again.json()['run_id']==rid
        assert len(transport.calls)==1


def test_snapshot_contains_exact_input_and_replay_survives_config_change(env):
    settings,journal,transport,sup=env
    text='  é\n\r\nhello\t '
    run=accept(sup,text,'frozen')
    snap=sup._snapshot(run.run_id)
    assert snap['intent']['input_text']==text
    settings.timeouts.total_run_seconds=900
    repeated=accept(sup,text,'frozen')
    assert repeated.run_id==run.run_id
    sup.execute_run(run.run_id)
    assert transport.calls[0]['input_text']==text
    assert sup._snapshot(run.run_id)['timeouts']['total_run_seconds']==300


def test_changed_model_argument_cannot_replace_snapshot(env):
    _,_,transport,sup=env
    run=accept(sup)
    with pytest.raises(PrismError):sup.execute_run(run.run_id,model_alias='different')
    assert transport.calls==[]


def test_modified_snapshot_rejected_without_network(env):
    _,journal,transport,sup=env
    run=accept(sup)
    with journal.conn:
        row=journal.conn.execute('SELECT request_json FROM request_snapshots WHERE run_id=?',(run.run_id,)).fetchone()
        content=json.loads(row[0]);content['intent']['input_text']='tampered'
        journal.conn.execute('UPDATE request_snapshots SET request_json=? WHERE run_id=?',(json.dumps(content),run.run_id))
    with pytest.raises(PrismError):sup.execute_run(run.run_id)
    assert transport.calls==[]
    assert sup.get_run(run.run_id).state==RunState.FAILED


def test_concurrent_idempotent_calls_have_one_record_and_one_submit(env):
    _,journal,transport,sup=env
    sup.start_worker()
    with ThreadPoolExecutor(max_workers=8) as pool:
        records=list(pool.map(lambda _:accept(sup,'same','one-key'),range(16)))
    assert len({r.run_id for r in records})==1
    sup.wait(records[0].run_id,timeout=3)
    assert len(transport.calls)==1
    assert journal.conn.execute('SELECT COUNT(*) FROM submit_attempts').fetchone()[0]==1


def test_preparation_uncertainty_stops_without_generation_or_repeat(env):
    settings,journal,transport,sup=env
    transport.fail_prepare=True
    run=accept(sup)
    with pytest.raises(TimeoutError):sup.execute_run(run.run_id)
    assert sup.get_run(run.run_id).state==RunState.UNCERTAIN
    assert journal.conn.execute('SELECT is_uncertain FROM resource_operations').fetchone()[0]==1
    assert len(transport.prepare_calls)==1 and transport.calls==[]
    restarted=RunSupervisor(settings,journal,PrismAdapter(transport))
    with pytest.raises(AdmissionBlockedError):accept(restarted,'another')
    assert len(transport.prepare_calls)==1


@pytest.mark.parametrize('kind,state',[('RunCompleted',RunState.SUCCEEDED),('RunFailed',RunState.FAILED),('CancellationConfirmed',RunState.CANCELLED)])
def test_read_only_reconcile_never_resubmits_or_sends_cancel(env,kind,state):
    settings,journal,transport,sup=env
    run=accept(sup)
    transport.fail_observe=True
    with pytest.raises(TimeoutError):sup.execute_run(run.run_id)
    sup.cancel_run(run.run_id)  # Intention must not turn read-only lookup into a POST.
    original=transport.lookup_events
    def lookup(session,handle):
        transport.lookups.append(handle)
        return [{'type':kind,'payload':{'task_ref':handle.task_ref,'text':'recovered','finish_reason':'stop'}}]
    transport.lookup_events=lookup
    restarted=RunSupervisor(settings,journal,PrismAdapter(transport))
    record=restarted.reconcile_run(run.run_id)
    assert record.state==state
    assert len(transport.calls)==1 and len(transport.lookups)==1
    assert transport.cancel_calls==[]
    assert restarted.admission_latch is False
    assert restarted.context_mgr.get_context(record.context_ref).busy_run_id is None


def test_reconcile_uses_original_account(env):
    _,_,transport,sup=env
    run=accept(sup);transport.fail_observe=True
    with pytest.raises(TimeoutError):sup.execute_run(run.run_id)
    transport.auth_profile.account_scope='some-other-account'
    with pytest.raises(AdmissionBlockedError):sup.reconcile_run(run.run_id)
    assert transport.lookups==[] and len(transport.calls)==1


def test_resolved_run_cannot_be_executed_again_even_without_key(env):
    _,_,transport,sup=env
    run=accept(sup)
    a=sup.execute_run(run.run_id)
    b=sup.execute_run(run.run_id)
    assert a.model_dump()==b.model_dump()
    assert len(transport.calls)==1


def test_result_expiry_never_generates_replacement(env):
    _,_,transport,sup=env
    run=accept(sup)
    result=sup.execute_run(run.run_id)
    Path(sup.get_run(run.run_id).result_ref).unlink()
    with pytest.raises(ResultUnavailableError):sup.execute_run(run.run_id)
    assert len(transport.calls)==1
    assert sup.get_run(run.run_id).state==RunState.SUCCEEDED


def test_storage_failure_after_remote_success_is_uncertain_and_recoverable(env,monkeypatch):
    _,journal,transport,sup=env
    run=accept(sup)
    import prism2api.storage.journal as module
    original=module.atomic_json
    def fail(path,data):
        if path.parent.name=='results':raise OSError('disk failure')
        return original(path,data)
    monkeypatch.setattr(module,'atomic_json',fail)
    with pytest.raises(OSError):sup.execute_run(run.run_id)
    assert sup.get_run(run.run_id).state==RunState.UNCERTAIN
    assert journal.conn.execute('SELECT COUNT(*) FROM result_index').fetchone()[0]==0
    monkeypatch.setattr(module,'atomic_json',original)
    assert sup.reconcile_run(run.run_id).state==RunState.SUCCEEDED
    assert len(transport.calls)==1


def test_no_submit_when_intent_transaction_fails(env,monkeypatch):
    _,journal,transport,sup=env
    run=accept(sup)
    original=journal.conn.execute
    def fail(sql,*args,**kwargs):
        if sql.startswith('INSERT INTO submit_attempts'):raise OSError('intent disk failure')
        return original(sql,*args,**kwargs)
    monkeypatch.setattr(journal.conn,'execute',fail)
    with pytest.raises(OSError):sup.execute_run(run.run_id)
    assert transport.calls==[]


@pytest.mark.parametrize('field,value', [('task_ref','wrong'),('conversation_ref','wrong'),('run_id','foreign'),('attempt_id','old'),('owner_epoch',-1)])
def test_wrong_identity_or_epoch_never_finalizes(env,field,value):
    _,_,transport,sup=env
    transport.events=lambda h:[{'type':'RunCompleted','payload':{'task_ref':h.task_ref,'text':'x',field:value}}]
    run=accept(sup)
    with pytest.raises(PrismError):sup.execute_run(run.run_id)
    assert sup.get_run(run.run_id).state==RunState.UNCERTAIN


def test_identical_terminal_repeat_is_harmless(env):
    _,_,transport,sup=env
    def events(h):
        ev={'type':'RunCompleted','payload':{'task_ref':h.task_ref,'text':'same'}}
        return [ev,ev.copy()]
    transport.events=events
    run=accept(sup)
    assert sup.execute_run(run.run_id).text=='same'


def test_identical_text_deltas_are_not_deduplicated(env):
    _,_,transport,sup=env
    transport.events=lambda h:[{'type':'TextDelta','payload':{'text':'ha'}}]*2+[{'type':'RunCompleted','payload':{'task_ref':h.task_ref,'finish_reason':'stop'}}]
    run=accept(sup)
    assert sup.execute_run(run.run_id).text=='haha'


@pytest.mark.parametrize('limit', ['max_event_count','max_text_bytes','max_event_bytes'])
def test_output_budget_failure_never_truncates_into_success(env,limit):
    settings,_,transport,sup=env
    setattr(settings.limits,limit,2 if limit=='max_event_count' else 8)
    transport.events=lambda h:[{'type':'TextDelta','payload':{'text':'abcdefghij'}}]*3+[{'type':'RunCompleted','payload':{'task_ref':h.task_ref,'text':'final'}}]
    run=accept(sup,'x')
    with pytest.raises(PrismError):sup.execute_run(run.run_id)
    assert sup.get_run(run.run_id).state==RunState.UNCERTAIN


def test_foreign_profile_context_rejected(env):
    _,_,transport,sup=env
    sup.context_mgr.create_context('ctx-other-profile','default_principal','other-profile',ContextPolicy.EXPLICIT)
    with pytest.raises(KeyError):sup.enqueue_run('default_principal','x',context_policy=ContextPolicy.EXPLICIT,context_id='ctx-other-profile')
    assert transport.calls==[] and transport.prepare_calls==[]


def test_context_revision_and_remote_binding_enforced(env):
    _,_,transport,sup=env
    ctx=sup.context_mgr.create_context('explicit','default_principal',transport.auth_profile.profile_id,ContextPolicy.EXPLICIT,workspace_ref='ws-explicit',conversation_ref='conv-explicit')
    r=sup.enqueue_run('default_principal','first',context_policy=ContextPolicy.EXPLICIT,context_id=ctx.context_id,expected_context_revision=1)
    sup.execute_run(r.run_id)
    assert transport.calls[0]['session'].context_binding['workspace_ref']=='ws-explicit'
    with pytest.raises(ContextBusyError):sup.enqueue_run('default_principal','second',context_policy=ContextPolicy.EXPLICIT,context_id=ctx.context_id,expected_context_revision=1)


def test_unknown_nested_api_fields_do_not_dispatch(env):
    settings,journal,transport,sup=env
    with TestClient(create_app(settings,sup)) as client:
        headers={'X-API-Key':settings.api_key}
        for body in [dict(model='prism-default',messages=[dict(role='user',content='x',tool_calls=[])]),dict(model='prism-default',messages=[dict(role='user',content='x')],stop='SECRET_MUST_NOT_ECHO')]:
            r=client.post('/v1/chat/completions',headers=headers,json=body)
            assert r.status_code==422
            assert 'SECRET_MUST_NOT_ECHO' not in r.text
        r=client.post('/prism/v1/runs',headers=headers,json={'input_text':'x','principal_id':'spoofed'})
        assert r.status_code==422
    assert transport.calls==[]
    assert journal.conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0


def test_origin_and_oversize_body_rejected(env):
    settings,_,transport,sup=env
    settings.limits.max_http_body_bytes=128
    with TestClient(create_app(settings,sup)) as client:
        headers={'X-API-Key':settings.api_key}
        assert client.post('/prism/v1/runs',headers={**headers,'Origin':'https://untrusted.example'},json={'input_text':'x'}).status_code==403
        assert client.post('/prism/v1/runs',headers=headers,json={'input_text':'x'*256}).status_code==413
        assert client.post('/prism/v1/runs',headers={**headers,'Transfer-Encoding':'chunked'},content=iter([b'a'*100,b'b'*100])).status_code==413
    assert transport.calls==[]


def test_close_waits_for_worker_and_does_not_release_lock_early(env):
    settings,journal,transport,sup=env
    entered,release=threading.Event(),threading.Event()
    settings.timeouts.cleanup_seconds=.02
    def events(h):
        entered.set();release.wait(2)
        return MockTransport.observe_events(transport,h)
    transport.events=events
    sup.start_worker();run=accept(sup)
    assert entered.wait(1)
    try:
        with pytest.raises(RuntimeError,match='lock retained'):journal.close()
        with pytest.raises(SingleInstanceLockError):StorageJournal(Settings(home_dir=settings.home_dir))
    finally:
        release.set()
        sup._worker.join(1)
    assert not sup._worker.is_alive()
    assert sup.get_run(run.run_id).state==RunState.UNCERTAIN


def test_direct_parallel_calls_still_use_one_submitter(env):
    _,_,transport,sup=env
    active=0;peak=0;guard=threading.Lock()
    orig=transport.submit
    def submit(**kw):
        nonlocal active,peak
        with guard:active+=1;peak=max(peak,active)
        try:time.sleep(.01);return orig(**kw)
        finally:
            with guard:active-=1
    transport.submit=submit
    runs=[accept(sup,str(i)) for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda r:sup.execute_run(r.run_id),runs))
    assert peak==1 and len(transport.calls)==6


def test_nested_sqlite_failure_rolls_back_inner_only(env):
    _,journal,_,_=env
    with journal.conn:
        journal.conn.execute("CREATE TABLE IF NOT EXISTS nested_check (v INTEGER)")
        journal.conn.execute('INSERT INTO nested_check VALUES (1)')
        with pytest.raises(ValueError):
            with journal.conn:
                journal.conn.execute('INSERT INTO nested_check VALUES (2)')
                raise ValueError('rollback savepoint')
    assert [r[0] for r in journal.conn.execute('SELECT v FROM nested_check')]==[1]


def test_real_process_exit_after_submit_intent_never_resubmits(tmp_path):
    home=tmp_path/'crash-home'
    script='''
import os
from pathlib import Path
from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import RunSupervisor
from prism2api.transport.mock_transport import MockTransport
from prism2api.provider.adapter import PrismAdapter
class Crash(MockTransport):
 def submit(self,**kwargs):
  assert j.conn.execute("SELECT count(*) FROM submit_attempts WHERE run_id=?",(kwargs["run_id"],)).fetchone()[0]==1
  (s.home_dir/"dispatch-counter").write_text("1")
  os._exit(37)
s=Settings(home_dir=Path(os.environ["TEST_CRASH_HOME"]),transport_mode="mock")
j=StorageJournal(s);sup=RunSupervisor(s,j,PrismAdapter(Crash()))
r=sup.enqueue_run("default_principal","crash-fixture")
sup.execute_run(r.run_id)
'''
    env=os.environ.copy();env['TEST_CRASH_HOME']=str(home);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
    result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,timeout=10)
    assert result.returncode==37,result.stderr.decode()
    with SDKClient(settings=Settings(home_dir=home,transport_mode='mock')) as client:
        assert client.supervisor.admission_latch
        with pytest.raises(AdmissionBlockedError):client.submit('never resubmit')
        assert (home/'dispatch-counter').read_text()=='1'
        rows=client.journal.conn.execute('SELECT state FROM runs').fetchall()
        assert [r[0] for r in rows]==['uncertain']


@pytest.mark.loopback
def test_daemon_sdk_over_real_loopback_http_has_no_local_writer(tmp_path):
    import uvicorn
    settings=Settings(home_dir=tmp_path/'server',api_key='loopback-test-key',transport_mode='mock')
    app=create_app(settings)
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False,ws='none'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    deadline=time.monotonic()+3
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.01)
    try:
        assert server.started
        daemon_home=tmp_path/'must-not-create'
        with SDKClient(mode=ClientMode.DAEMON,settings=Settings(home_dir=daemon_home,api_key=settings.api_key),base_url=f'http://127.0.0.1:{port}') as client:
            result=client.execute_and_wait('through socket',idempotency_key='socket-once')
            assert result.transport_kind=='mock'
            assert not daemon_home.exists()
            repeated=client.execute_and_wait('through socket',idempotency_key='socket-once')
            assert repeated.run_id==result.run_id
    finally:
        server.should_exit=True;thread.join(3);listener.close()
        assert not thread.is_alive()


def test_failed_sql_commit_does_not_leave_uncommitted_changes_visible(env,monkeypatch):
    _,journal,_,_=env
    with journal.conn:journal.conn.execute('CREATE TABLE commit_probe (v INTEGER)')
    original=journal.conn.execute
    def fail_commit(sql,*args,**kwargs):
        if sql=='COMMIT':raise OSError('fsync/commit failure')
        return original(sql,*args,**kwargs)
    monkeypatch.setattr(journal.conn,'execute',fail_commit)
    with pytest.raises(OSError):
        with journal.conn:journal.conn.execute('INSERT INTO commit_probe VALUES (1)')
    monkeypatch.setattr(journal.conn,'execute',original)
    assert not journal.conn.in_transaction
    assert journal.conn.execute('SELECT COUNT(*) FROM commit_probe').fetchone()[0]==0


def test_superseded_supervisor_cannot_mutate_current_owner(env):
    settings,journal,transport,old=env
    run=accept(old)
    current=RunSupervisor(settings,journal,PrismAdapter(transport))
    with pytest.raises(AdmissionBlockedError):old.cancel_run(run.run_id)
    assert current.get_run(run.run_id).cancel_intent is False


def test_changed_account_scope_cannot_reuse_same_key(env):
    _,_,transport,sup=env
    accept(sup,'text','same')
    transport.auth_profile.account_scope='different-login'
    with pytest.raises(IdempotencyConflictError):accept(sup,'text','same')


def test_queue_wait_budget_is_enforced_before_remote_operations(env):
    _,journal,transport,sup=env
    run=accept(sup)
    with journal.conn:journal.conn.execute("UPDATE runs SET created_at='2000-01-01T00:00:00+00:00' WHERE run_id=?",(run.run_id,))
    with pytest.raises(PrismError):sup.execute_run(run.run_id)
    assert transport.prepare_calls==[] and transport.calls==[]


def test_recovery_scan_cannot_reclassify_active_worker(env):
    _,_,_,sup=env
    sup._generation_lock.acquire()
    try:
        with pytest.raises(RuntimeError):sup.recover_on_startup()
    finally:sup._generation_lock.release()


def test_receipt_survives_context_identity_validation_failure(env, monkeypatch):
    _, journal, transport, sup = env
    original = transport.submit
    def mismatched(**kwargs):
        handle = original(**kwargs)
        handle.workspace_ref = 'foreign-workspace'
        return handle
    monkeypatch.setattr(transport, 'submit', mismatched)
    run = accept(sup)
    with pytest.raises(Exception):
        sup.execute_run(run.run_id)
    assert sup.get_run(run.run_id).state == RunState.UNCERTAIN
    receipt = journal.conn.execute('SELECT remote_handle FROM submit_attempts WHERE run_id=?', (run.run_id,)).fetchone()[0]
    assert receipt is not None
    assert json.loads(receipt)['workspace_ref'] == 'foreign-workspace'
    assert len(transport.calls) == 1
    with pytest.raises(PrismError):
        sup.reconcile_run(run.run_id)
    assert transport.lookups == []
    assert sup.get_run(run.run_id).state == RunState.UNCERTAIN


def test_transport_closed_once_across_repeated_runtime_shutdown(env, monkeypatch):
    _, journal, transport, sup = env
    calls = []
    monkeypatch.setattr(transport, 'close', lambda: calls.append('close'))
    sup.close()
    journal.close()
    journal.close()
    assert calls == ['close']
