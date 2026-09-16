"""RunSupervisor for M03 Lifecycle, Idempotency, and Crash Recovery."""

import uuid
import json
import time
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from prism2api.config import TimeoutsConfig
from prism2api.provider.models import CapabilityId
from prism2api.storage.journal import atomic_json
from prism2api.errors import (AdmissionBlockedError,UnsupportedRequestError,InputTooLargeError,
    QueueFullError,ResultUnavailableError,OutcomeError,WaitTimeoutError,ProtocolError)


def canonical(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from prism2api.config import Settings
from prism2api.provider.adapter import PrismAdapter
from prism2api.provider.models import RemoteHandle
from prism2api.runtime.context import ContextManager, ContextPolicy, ResourceLease, ContextBusyError
from prism2api.runtime.events import EventNormalizer, EventType
from prism2api.storage.journal import StorageJournal, EvidenceManifest, GenerationResult, get_iso_now


class RunState(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    SUBMITTING = "submitting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


class IdempotencyConflictError(UnsupportedRequestError):
    """Raised when the same Idempotency-Key is used with a different fingerprint."""
    code = "idempotency_conflict"
    http_status = 409


class RunRecord(BaseModel):
    run_id: str
    principal_id: str
    auth_profile_ref: str
    state: RunState
    state_version: int = 1
    input_ref: str
    request_fingerprint: str
    context_ref: Optional[str] = None
    capability_snapshot_ref: Optional[str] = None
    config_revision: str = "v0.1.0"
    created_at: str = Field(default_factory=get_iso_now)
    updated_at: str = Field(default_factory=get_iso_now)
    cancel_intent: bool = False
    terminal_evidence_ref: Optional[str] = None
    result_ref: Optional[str] = None
    error_code: Optional[str] = None


class SubmitAttempt(BaseModel):
    attempt_id: str
    run_id: str
    owner_epoch: int
    intent_committed_at: str = Field(default_factory=get_iso_now)
    dispatch_outcome: Optional[str] = None
    remote_handle: Optional[str] = None
    receipt_evidence_ref: Optional[str] = None


class RunSupervisor:
    """Single generation owner shared by SDK, worker and HTTP; no hidden retries."""

    def __init__(self, settings, journal, adapter=None):
        self.settings, self.journal, self.conn = settings, journal, journal.conn
        previous = journal.owner
        if previous is not None:
            if previous._generation_lock.locked() or (previous._worker and previous._worker.is_alive()):
                raise RuntimeError("Journal already owns an active supervisor")
            previous._superseded = True
        self._superseded = False
        self.context_mgr = ContextManager(self.conn)
        if adapter is None and settings.transport_mode == "mock":
            from prism2api.transport.mock_transport import MockTransport
            adapter = PrismAdapter(MockTransport())
        self.adapter = adapter if adapter is not None else PrismAdapter()
        self._generation_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._worker = None
        self._faulted = False
        self._transport_closed = False
        self.recover_on_startup()
        journal.owner = self

    @property
    def admission_latch(self):
        if self._faulted or self._superseded or self._stop.is_set() or self.journal.closed:
            return True
        try:
            with self.conn:
                return self.conn.execute("SELECT 1 FROM runs WHERE state='uncertain' LIMIT 1").fetchone() is not None
        except Exception:
            return True

    def _ensure_owner(self):
        if self._superseded or self._stop.is_set() or self.journal.closed:
            raise AdmissionBlockedError("Runtime is closed or superseded")

    def _admit(self):
        if self.admission_latch:
            raise AdmissionBlockedError("Resolve uncertain work before new generation")

    def recover_on_startup(self):
        """Never repeat an intent. Only locally queued, snapshotted work is resumable."""
        if self._generation_lock.locked() or (self._worker and self._worker.is_alive()):
            raise RuntimeError("Startup recovery cannot run over an active worker")
        with self.conn:
            rows = self.conn.execute("SELECT * FROM runs WHERE state IN ('queued','preparing','submitting','running','uncertain')").fetchall()
            for row in rows:
                rid = row['run_id']
                side_effect = self.conn.execute("SELECT 1 FROM submit_attempts WHERE run_id=?", (rid,)).fetchone()
                resource = self.conn.execute("SELECT 1 FROM resource_operations WHERE run_id=?", (rid,)).fetchone()
                if row['state'] in ('submitting','running','uncertain') or side_effect or resource:
                    self.conn.execute("UPDATE runs SET state='uncertain', error_code='restart_requires_lookup', state_version=state_version+1 WHERE run_id=?", (rid,))
                else:
                    snapshot = self.conn.execute("SELECT 1 FROM request_snapshots WHERE run_id=?", (rid,)).fetchone()
                    state = 'queued' if snapshot else 'failed'
                    code = None if snapshot else 'legacy_missing_input_snapshot'
                    self.conn.execute("UPDATE runs SET state=?, error_code=?, state_version=state_version+1 WHERE run_id=?", (state, code, rid))
                    self.conn.execute("UPDATE contexts SET busy_run_id=NULL WHERE busy_run_id=?", (rid,))
            return [r[0] for r in self.conn.execute("SELECT run_id FROM runs WHERE state='uncertain'").fetchall()]

    def enqueue_run(self, principal_id, input_text, model_alias='prism-default',
                    context_policy=ContextPolicy.ISOLATED, idempotency_key=None,
                    context_id=None, expected_context_revision=None):
        self._ensure_owner()
        context_policy = ContextPolicy(context_policy)
        if not isinstance(input_text, str) or not input_text:
            raise UnsupportedRequestError("Input must be nonempty text")
        if len(input_text.encode()) > self.settings.limits.max_text_bytes:
            raise InputTooLargeError()
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256):
            raise UnsupportedRequestError("Invalid idempotency key")
        if context_policy == ContextPolicy.EXPLICIT and not context_id:
            raise UnsupportedRequestError("Explicit continuation requires a context_id")
        if context_policy == ContextPolicy.ISOLATED and (context_id or expected_context_revision is not None):
            raise UnsupportedRequestError("Isolated requests cannot reuse a context")
        # Caller intent is compared against the original snapshot on idempotent replay.
        intent = dict(principal_id=principal_id, input_text=input_text, model_alias=model_alias,
                      context_policy=context_policy.value, context_id=context_id,
                      expected_context_revision=expected_context_revision)
        intent_json = canonical(intent)
        key_digest = self.journal.compute_fingerprint(idempotency_key, principal_id, 'idempotency-v1') if idempotency_key else None
        with self.conn:
            if key_digest:
                old = self.conn.execute("SELECT run_id FROM idempotency_records WHERE key_digest=?", (key_digest,)).fetchone()
                if old:
                    prior = self._snapshot(old['run_id'])
                    if canonical(prior['intent']) != intent_json or (prior['auth_profile_ref'] != self.adapter.auth_profile.profile_id or prior['account_scope'] != self.adapter.auth_profile.account_scope):
                        raise IdempotencyConflictError("Idempotency key conflicts with accepted request")
                    return self.get_run(old['run_id'])
            self._admit()
        # Capability discovery is contractually cached/local; it must never generate.
        caps = self.adapter.validate_request(model_alias, context_policy)
        with self.conn:
            self._admit()
            # Another caller can have won the key while capability validation ran.
            if key_digest:
                old = self.conn.execute("SELECT run_id FROM idempotency_records WHERE key_digest=?", (key_digest,)).fetchone()
                if old:
                    prior = self._snapshot(old['run_id'])
                    if canonical(prior['intent']) != intent_json or (prior['auth_profile_ref'] != self.adapter.auth_profile.profile_id or prior['account_scope'] != self.adapter.auth_profile.account_scope):
                        raise IdempotencyConflictError("Idempotency key conflicts with accepted request")
                    return self.get_run(old['run_id'])
            count = self.conn.execute("SELECT COUNT(*) FROM runs WHERE state='queued'").fetchone()[0]
            if count >= self.settings.limits.max_queue_size:
                raise QueueFullError()
            run_id = 'run_' + uuid.uuid4().hex
            if context_id:
                ctx = self.context_mgr.get_context(context_id, principal_id, self.adapter.auth_profile.profile_id)
                if ctx.context_policy != ContextPolicy.EXPLICIT:
                    raise UnsupportedRequestError("Context was not registered for explicit continuation")
                if ctx.busy_run_id or self.conn.execute("SELECT 1 FROM runs WHERE context_ref=? AND state='queued'", (context_id,)).fetchone():
                    raise ContextBusyError("Context already reserved")
                if expected_context_revision is not None and expected_context_revision != ctx.context_revision:
                    raise ContextBusyError("Context revision changed")
            else:
                ctx = self.context_mgr.create_context('ctx_' + run_id, principal_id, self.adapter.auth_profile.profile_id, context_policy)
            snapshot = dict(schema_version='request-v1', intent=intent, context=ctx.model_dump(mode='json'),
                            auth_profile_ref=self.adapter.auth_profile.profile_id,
                            account_scope=self.adapter.auth_profile.account_scope,
                            transport_kind=self.adapter.transport.kind,
                            config_revision='offline-core-v1',
                            timeouts=self.settings.timeouts.model_dump(), limits=self.settings.limits.model_dump(),
                            capabilities=[c.model_dump(mode='json') for c in caps])
            request_json = canonical(snapshot)
            fingerprint = self.journal.compute_fingerprint(request_json, model_alias, context_policy.value)
            record = RunRecord(run_id=run_id, principal_id=principal_id, auth_profile_ref=snapshot['auth_profile_ref'],
                               state=RunState.QUEUED, input_ref='request:' + run_id, request_fingerprint=fingerprint,
                               context_ref=ctx.context_id, capability_snapshot_ref='request:' + run_id,
                               config_revision=snapshot['config_revision'])
            data = record.model_dump(mode='json')
            columns = ','.join(data)
            self.conn.execute(f"INSERT INTO runs ({columns}) VALUES ({','.join('?' for _ in data)})", tuple(data.values()))
            self.conn.execute("INSERT INTO request_snapshots VALUES (?,?,?,?,?)", (run_id,'request-v1',intent_json,request_json,fingerprint))
            if key_digest:
                self.conn.execute("INSERT INTO idempotency_records VALUES (?,?,?,?,?)", (key_digest,principal_id,run_id,fingerprint,get_iso_now()))
        self._wake.set()
        return record

    def _snapshot(self, run_id):
        with self.conn:
            row = self.conn.execute("SELECT * FROM request_snapshots WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row['schema_version'] != 'request-v1':
                raise UnsupportedRequestError("Missing or unsupported frozen input", run_id=run_id)
            data = json.loads(row['request_json'])
            intent = data['intent']
            fp = self.journal.compute_fingerprint(row['request_json'], intent['model_alias'], intent['context_policy'])
            record = self.get_run(run_id)
            if fp != row['fingerprint'] or fp != record.request_fingerprint or canonical(intent) != row['input_json']:
                raise ProtocolError("Frozen input integrity failure", run_id=run_id)
            return data

    def get_run(self, run_id, principal_id=None):
        with self.conn:
            row = self.conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or (principal_id is not None and row['principal_id'] != principal_id):
                raise KeyError("Run not found")
            return RunRecord.model_validate(dict(row))

    def transition_state(self, run_id, expected_state, new_state):
        allowed = {
            RunState.QUEUED: {RunState.PREPARING,RunState.CANCELLED,RunState.FAILED},
            RunState.PREPARING: {RunState.SUBMITTING,RunState.CANCELLED,RunState.FAILED,RunState.UNCERTAIN},
            RunState.SUBMITTING: {RunState.RUNNING,RunState.UNCERTAIN,RunState.FAILED,RunState.CANCELLED},
            RunState.RUNNING: {RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED,RunState.UNCERTAIN},
            RunState.UNCERTAIN: {RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED},
        }
        expected_state,new_state = RunState(expected_state),RunState(new_state)
        if new_state not in allowed.get(expected_state,set()):
            raise RuntimeError("Illegal run state transition")
        with self.conn:
            cur = self.conn.execute("UPDATE runs SET state=?, state_version=state_version+1, updated_at=? WHERE run_id=? AND state=?",
                                    (new_state.value,get_iso_now(),run_id,expected_state.value))
            if cur.rowcount != 1:
                raise RuntimeError("Run state changed concurrently")
        return self.get_run(run_id)

    def _set_outcome(self, run_id, state, code=None, evidence_ref=None):
        with self.conn:
            record = self.get_run(run_id)
            if record.state in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED):
                return record
            if record.state != state:
                record = self.transition_state(run_id,record.state,state)
            self.conn.execute("UPDATE runs SET error_code=?, terminal_evidence_ref=COALESCE(?,terminal_evidence_ref) WHERE run_id=?",
                              (code,evidence_ref,run_id))
            return self.get_run(run_id)

    def _has_remote_intent(self, run_id):
        with self.conn:
            return bool(self.conn.execute("SELECT 1 FROM submit_attempts WHERE run_id=? UNION ALL SELECT 1 FROM resource_operations WHERE run_id=? LIMIT 1", (run_id,run_id)).fetchone())

    def execute_run(self, run_id, input_text=None, model_alias=None):
        # Legacy optional arguments can only validate, NEVER replace the frozen input.
        self._ensure_owner()
        record = self.get_run(run_id)
        try:
            snapshot = self._snapshot(run_id)
        except Exception:
            if record.state not in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED):
                self._set_outcome(run_id,RunState.UNCERTAIN if self._has_remote_intent(run_id) else RunState.FAILED,'invalid_input_snapshot')
            raise
        intent = snapshot['intent']
        if (input_text is not None and input_text != intent['input_text']) or (model_alias is not None and model_alias != intent['model_alias']):
            raise UnsupportedRequestError("Execution differs from accepted input", run_id=run_id)
        if record.state == RunState.SUCCEEDED:
            return self.get_result(run_id)
        if record.state in (RunState.FAILED,RunState.CANCELLED,RunState.UNCERTAIN):
            raise OutcomeError(record.state,run_id=run_id)
        acquired = self._generation_lock.acquire(timeout=self.settings.timeouts.queue_wait_seconds)
        if not acquired:
            raise WaitTimeoutError(run_id=run_id)
        lease = None
        try:
            self._admit()
            record = self.get_run(run_id)
            if record.state == RunState.SUCCEEDED:
                return self.get_result(run_id)
            if record.state != RunState.QUEUED:
                raise OutcomeError(record.state,run_id=run_id)
            if snapshot['auth_profile_ref'] != self.adapter.auth_profile.profile_id or snapshot['account_scope'] != self.adapter.auth_profile.account_scope or snapshot['transport_kind'] != self.adapter.transport.kind:
                raise UnsupportedRequestError("Transport or account changed since admission",run_id=run_id)
            self.adapter.validate_request(intent['model_alias'],intent['context_policy'])
            budgets = TimeoutsConfig.model_validate(snapshot['timeouts'])
            queue_age = (datetime.now(timezone.utc)-datetime.fromisoformat(record.created_at)).total_seconds()
            if queue_age > budgets.queue_wait_seconds:
                raise WaitTimeoutError("Queue wait budget exceeded",run_id=run_id)
            started = time.monotonic()
            self.adapter.session.deadline_monotonic = started + budgets.total_run_seconds
            self.adapter.session.io_timeout_seconds = budgets.preparation_seconds
            with self.conn:
                self._admit()
                ctx = self.context_mgr.get_context(record.context_ref,record.principal_id,record.auth_profile_ref)
                if ctx.context_revision != snapshot['context']['context_revision']:
                    raise ContextBusyError("Context revision changed before dispatch")
                lease = self.context_mgr.acquire_lease(record.context_ref,run_id)
                self.transition_state(run_id,RunState.QUEUED,RunState.PREPARING)
                count = self.conn.execute("SELECT COUNT(*) FROM resource_operations WHERE action_type='prepare_context'").fetchone()[0]
                if count >= snapshot['limits']['max_created_contexts']:
                    raise QueueFullError("Context operation budget reached")
                operation_id = 'prepare_' + run_id
                self.conn.execute("INSERT INTO resource_operations (operation_id,run_id,action_type,target_ref,intent_committed_at,is_uncertain) VALUES (?,?,?,?,?,1)",
                                  (operation_id,run_id,'prepare_context',ctx.context_id,get_iso_now()))
            prepared = self.adapter.transport.prepare_context(self.adapter.session,ctx,operation_id)
            if not isinstance(prepared,RemoteHandle) or not prepared.workspace_ref:
                raise ProtocolError("No verified workspace handle")
            with self.conn:
                ctx = self.context_mgr.bind_remote(lease,prepared)
                self.conn.execute("UPDATE resource_operations SET confirmed_handle=?,is_uncertain=0 WHERE operation_id=?", (prepared.model_dump_json(),operation_id))
            if time.monotonic()-started > budgets.preparation_seconds:
                raise TimeoutError("Preparation budget exceeded")
            attempt_id = 'attempt_' + run_id
            with self.conn:
                self.context_mgr.assert_lease(lease)
                if self.get_run(run_id).cancel_intent:
                    self._set_outcome(run_id,RunState.CANCELLED,'cancelled_before_generation')
                    raise OutcomeError(RunState.CANCELLED,run_id=run_id)
                self._admit()
                self.transition_state(run_id,RunState.PREPARING,RunState.SUBMITTING)
                self.conn.execute("INSERT INTO submit_attempts (attempt_id,run_id,owner_epoch,intent_committed_at) VALUES (?,?,?,?)", (attempt_id,run_id,lease.owner_epoch,get_iso_now()))
            self.adapter.session.context_binding = ctx.model_dump(mode='json')
            self.adapter.session.operation_id = attempt_id
            self.adapter.session.io_timeout_seconds = budgets.submit_ack_seconds
            receipt_started = time.monotonic()
            handle = self.adapter.submit_request(run_id,attempt_id,intent['input_text'],intent['model_alias'])
            if not isinstance(handle,RemoteHandle) or not (handle.task_ref or handle.message_ref):
                raise ProtocolError("Missing recoverable task/message handle")
            with self.conn:
                # Save the receipt before validating further, so failed validation is recoverable.
                self.conn.execute("UPDATE submit_attempts SET remote_handle=?,dispatch_outcome='accepted',receipt_evidence_ref=? WHERE attempt_id=?", (handle.model_dump_json(),attempt_id,attempt_id))
            with self.conn:
                self.context_mgr.bind_remote(lease,handle)
                self.transition_state(run_id,RunState.SUBMITTING,RunState.RUNNING)
            if time.monotonic()-receipt_started > budgets.submit_ack_seconds:
                raise TimeoutError("Submission receipt budget exceeded")
            self._observe_and_finalize(run_id,snapshot,handle,attempt_id,lease.owner_epoch,started,budgets)
            return self.get_result(run_id)
        except BaseException as exc:
            try:
                record = self.get_run(run_id)
                preserve_queue = isinstance(exc,AdmissionBlockedError) and record.state == RunState.QUEUED and self.admission_latch
                if not preserve_queue and record.state not in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED,RunState.UNCERTAIN):
                    state = RunState.UNCERTAIN if self._has_remote_intent(run_id) else RunState.FAILED
                    self._set_outcome(run_id,state,'execution_requires_lookup' if state == RunState.UNCERTAIN else 'local_pre_submit_error')
            except Exception:
                self._faulted = True
            raise
        finally:
            try:
                if lease is not None and self.get_run(run_id).state in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED):
                    self.context_mgr.release_lease(lease)
            except Exception:
                self._faulted = True
            self._generation_lock.release()
            self._wake.set()

    def _observe_and_finalize(self,run_id,snapshot,handle,attempt_id,epoch,started,budgets,raw_events=None):
        limits = snapshot['limits']
        normalizer = EventNormalizer(run_id,attempt_id=attempt_id,owner_epoch=epoch,
            max_event_count=limits['max_event_count'],max_text_bytes=limits['max_text_bytes'],max_event_bytes=limits['max_event_bytes'],max_total_event_bytes=limits.get('max_total_event_bytes',16*1024*1024))
        last = time.monotonic()
        observation_started = last
        self.adapter.session.io_timeout_seconds = min(budgets.inter_event_seconds,budgets.first_output_seconds)
        def before_event():
            nonlocal last
            now = time.monotonic()
            if self._stop.is_set() or now-started > budgets.total_run_seconds or now-last > budgets.inter_event_seconds:
                raise TimeoutError("Observation budget exceeded or runtime shutting down")
            if not normalizer.saw_text and normalizer.terminal is None and now-observation_started > budgets.first_output_seconds:
                raise TimeoutError("First output budget exceeded")
            last = now
            with self.conn:
                ctx = self.context_mgr.get_context(self.get_run(run_id).context_ref)
                if ctx.busy_run_id != run_id or ctx.lease_epoch != epoch:
                    raise ProtocolError("Observer lost context ownership")
                row = self.conn.execute("SELECT cancel_intent,cancel_dispatched FROM runs WHERE run_id=?", (run_id,)).fetchone()
                send_cancel = raw_events is None and row['cancel_intent'] and not row['cancel_dispatched']
                if send_cancel:
                    self.conn.execute("UPDATE runs SET cancel_dispatched=1 WHERE run_id=?", (run_id,))
            if send_cancel:
                # Receipt alone does not become CancellationConfirmed.
                self.adapter.request_cancel(handle)
        self.adapter.observe_normalized_events(run_id,handle,normalizer,raw_events=raw_events,before_event=before_event)
        if time.monotonic()-started > budgets.total_run_seconds:
            raise TimeoutError("Total run budget exceeded")
        terminal = normalizer.get_terminal_event()
        if terminal is None:
            raise ProtocolError("Stream ended without authoritative terminal",run_id=run_id)
        evidence = terminal.model_dump(mode='json')
        # Evidence logs never contain arbitrary transport header/error dictionaries.
        evidence['payload'] = {k:v for k,v in terminal.payload.items() if k in ('workspace_ref','conversation_ref','task_ref','message_ref','finish_reason')}
        if normalizer.final_text is not None:
            evidence['output_sha256'] = hashlib.sha256(normalizer.final_text.encode()).hexdigest()
        evidence['transport_kind'] = self.adapter.transport.kind
        path = self.settings.evidence_dir / (run_id + '-terminal.json')
        atomic_json(path,evidence)
        state = {EventType.RUN_COMPLETED:RunState.SUCCEEDED,EventType.RUN_FAILED:RunState.FAILED,EventType.CANCELLATION_CONFIRMED:RunState.CANCELLED}[terminal.event_type]
        if state != RunState.SUCCEEDED:
            self._set_outcome(run_id,state,'remote_' + state.value,str(path))
            raise OutcomeError(state,run_id=run_id)
        record = self.get_run(run_id)
        result = GenerationResult(run_id=run_id,requested_alias=snapshot['intent']['model_alias'],text=normalizer.final_text,
            finish_reason=terminal.payload.get('finish_reason','stop'),
            finish_reason_origin='upstream_mapping' if 'finish_reason' in terminal.payload else 'gateway_mapping',
            context_ref=record.context_ref,transport_kind=self.adapter.transport.kind)
        manifest = EvidenceManifest(run_id=run_id,request_fingerprint=record.request_fingerprint,
            requested_alias=snapshot['intent']['model_alias'],output_digest='',result_ref='res_' + run_id,
            capability_snapshot_ref=record.capability_snapshot_ref,context_binding_ref=record.context_ref,
            submit_attempt_ref=attempt_id,remote_handle_ref=attempt_id,completion_evidence=evidence,
            limitations=['Prism live protocol is not verified by offline tests.'] if self.adapter.transport.kind == 'mock' else [],
            context_limitations=['No claim of provider-side zero retention or account-wide zero memory.'])
        with self.conn:
            record = self.get_run(run_id)
            if record.state not in (RunState.RUNNING,RunState.UNCERTAIN):
                raise ProtocolError("State changed before publishing result")
            ctx = self.context_mgr.get_context(record.context_ref)
            if ctx.busy_run_id != run_id or ctx.lease_epoch != epoch:
                raise ProtocolError("Lease changed before publishing result")
            res_file,_ = self.journal.save_result_and_manifest(run_id,result,manifest)
            self.transition_state(run_id,record.state,RunState.SUCCEEDED)
            self.conn.execute("UPDATE runs SET result_ref=?,terminal_evidence_ref=?,error_code=NULL WHERE run_id=?", (str(res_file),str(path),run_id))
            self.conn.execute("UPDATE contexts SET context_revision=context_revision+1 WHERE context_id=?", (record.context_ref,))

    def get_result(self,run_id,principal_id=None):
        record = self.get_run(run_id,principal_id)
        if record.state != RunState.SUCCEEDED:
            raise OutcomeError(record.state,run_id=run_id)
        with self.conn:
            row = self.conn.execute("SELECT * FROM result_index WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ResultUnavailableError(run_id=run_id)
        try:
            res_path = Path(row['result_file_path'])
            man_path = Path(row['manifest_file_path'])
            if res_path.resolve().parent != self.settings.results_dir.resolve() or man_path.resolve().parent != self.settings.evidence_dir.resolve():
                raise ValueError('Result path mismatch')
            result = GenerationResult.model_validate_json(res_path.read_text())
            manifest = EvidenceManifest.model_validate_json(man_path.read_text())
            if result.run_id != run_id or manifest.run_id != run_id or result.manifest_ref != str(man_path) or result.compute_digest() != row['digest'] or manifest.output_digest != row['digest'] or result.result_digest != row['digest']:
                raise ValueError('Result integrity mismatch')
            return result
        except (OSError,ValueError) as exc:
            raise ResultUnavailableError(run_id=run_id) from exc

    def reconcile_run(self,run_id,principal_id=None):
        """Exact read-only lookup. Never clears an unknown task by re-submitting it."""
        self._ensure_owner()
        record = self.get_run(run_id,principal_id)
        if record.state != RunState.UNCERTAIN:
            return record
        if not self._generation_lock.acquire(blocking=False):
            raise ContextBusyError("Worker still owns generation")
        try:
            if not self.adapter.is_capability_usable(CapabilityId.TASK_LOOKUP):
                raise AdmissionBlockedError("Read-only task lookup not verified",run_id=run_id)
            with self.conn:
                row = self.conn.execute("SELECT * FROM submit_attempts WHERE run_id=?", (run_id,)).fetchone()
            if row is None or not row['remote_handle']:
                raise AdmissionBlockedError("Missing receipt: manual remote verification required",run_id=run_id)
            snapshot = self._snapshot(run_id)
            if snapshot['auth_profile_ref'] != self.adapter.auth_profile.profile_id or snapshot['account_scope'] != self.adapter.auth_profile.account_scope or snapshot['transport_kind'] != self.adapter.transport.kind:
                raise AdmissionBlockedError("Lookup requires original account and transport",run_id=run_id)
            handle = RemoteHandle.model_validate_json(row['remote_handle'])
            ctx = self.context_mgr.get_context(record.context_ref,record.principal_id,record.auth_profile_ref)
            for key in ('workspace_ref','conversation_ref'):
                expected = getattr(ctx,key)
                if expected is not None and expected != getattr(handle,key):
                    raise ProtocolError('Receipt conflicts with the bound context',run_id=run_id)
            budgets = TimeoutsConfig.model_validate(snapshot['timeouts'])
            started = time.monotonic()
            self.adapter.session.deadline_monotonic = started+budgets.total_run_seconds
            self.adapter.session.io_timeout_seconds = budgets.inter_event_seconds
            # This seam is explicitly read-only; cancellation is not sent during lookup.
            raw_events = self.adapter.transport.lookup_events(self.adapter.session,handle)
            self._observe_and_finalize(run_id,snapshot,handle,row['attempt_id'],row['owner_epoch'],started,budgets,raw_events)
        except OutcomeError:
            pass
        finally:
            try:
                record = self.get_run(run_id)
                if record.state in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED):
                    with self.conn:
                        self.conn.execute("UPDATE contexts SET busy_run_id=NULL WHERE busy_run_id=?", (run_id,))
            finally:
                self._generation_lock.release()
                self._wake.set()
        return self.get_run(run_id)

    def cancel_run(self,run_id,principal_id=None):
        self._ensure_owner()
        with self.conn:
            record = self.get_run(run_id,principal_id)
            if record.state in (RunState.SUCCEEDED,RunState.FAILED,RunState.CANCELLED):
                return record
            self.conn.execute("UPDATE runs SET cancel_intent=1,updated_at=? WHERE run_id=?", (get_iso_now(),run_id))
            if record.state == RunState.QUEUED or (record.state == RunState.PREPARING and not self._has_remote_intent(run_id)):
                self.transition_state(run_id,record.state,RunState.CANCELLED)
        self._wake.set()
        return self.get_run(run_id)

    def start_worker(self):
        if self._worker and self._worker.is_alive():
            return
        if self._stop.is_set() or self._superseded:
            raise AdmissionBlockedError("Runtime is closed")
        self._worker = threading.Thread(target=self._worker_loop,name='prism2api-worker',daemon=True)
        self._worker.start()

    def _worker_loop(self):
        while not self._stop.is_set():
            self._wake.clear()
            if not self.admission_latch:
                with self.conn:
                    row = self.conn.execute("SELECT run_id FROM runs WHERE state='queued' ORDER BY created_at,run_id LIMIT 1").fetchone()
                if row:
                    try:
                        self.execute_run(row['run_id'])
                    except AdmissionBlockedError:
                        if not self.admission_latch:
                            self._faulted = True
                    except Exception:
                        # State/evidence is durable; no raw provider exceptions in logs.
                        if self.get_run(row['run_id']).state == RunState.QUEUED:
                            self._faulted = True
                    continue
            self._wake.wait(0.1)

    def wait(self,run_id,timeout=None,principal_id=None):
        deadline = time.monotonic() + (timeout if timeout is not None else self.settings.timeouts.total_run_seconds+self.settings.timeouts.queue_wait_seconds)
        while True:
            record = self.get_run(run_id,principal_id)
            if record.state == RunState.SUCCEEDED:
                return self.get_result(run_id,principal_id)
            if record.state in (RunState.FAILED,RunState.CANCELLED,RunState.UNCERTAIN):
                raise OutcomeError(record.state,run_id=run_id)
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise WaitTimeoutError(run_id=run_id)
            time.sleep(min(0.01,remaining))

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._worker and self._worker is not threading.current_thread():
            self._worker.join(self.settings.timeouts.cleanup_seconds)
            if self._worker.is_alive():
                self._faulted = True
                raise RuntimeError("Worker has not stopped; home lock retained")
        if self._generation_lock.locked():
            raise RuntimeError("Generation in progress; home lock retained")
        if not self._transport_closed:
            self.adapter.transport.close()
            self._transport_closed = True
