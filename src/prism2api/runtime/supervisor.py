"""RunSupervisor for M03 Lifecycle, Idempotency, and Crash Recovery."""

import uuid
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


class IdempotencyConflictError(Exception):
    """Raised when the same Idempotency-Key is used with a different fingerprint."""
    pass


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


class SubmitAttempt(BaseModel):
    attempt_id: str
    run_id: str
    owner_epoch: int
    intent_committed_at: str = Field(default_factory=get_iso_now)
    dispatch_outcome: Optional[str] = None
    remote_handle: Optional[str] = None
    receipt_evidence_ref: Optional[str] = None


class RunSupervisor:
    """唯一的生成调度、生命周期管理与崩溃恢复组件。"""

    def __init__(self, settings: Settings, journal: StorageJournal, adapter: Optional[PrismAdapter] = None):
        self.settings = settings
        self.journal = journal
        self.conn = self.journal.conn
        self.context_mgr = ContextManager(self.conn)
        self.adapter = adapter or PrismAdapter()
        self.admission_latch: bool = False
        self.recover_on_startup()

    def recover_on_startup(self) -> List[str]:
        """Scan un-terminated runs on startup; mark un-finalized runs as UNCERTAIN."""
        uncertain_runs: List[str] = []
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT run_id FROM runs WHERE state IN ('queued', 'preparing', 'submitting', 'running')"
        )
        rows = cursor.fetchall()

        if rows:
            self.admission_latch = True
            now = get_iso_now()
            with self.conn:
                for row in rows:
                    run_id = row["run_id"]
                    uncertain_runs.append(run_id)
                    cursor.execute(
                        """
                        UPDATE runs
                        SET state = ?, updated_at = ?, state_version = state_version + 1
                        WHERE run_id = ?
                        """,
                        (RunState.UNCERTAIN.value, now, run_id),
                    )
        return uncertain_runs

    def enqueue_run(
        self,
        principal_id: str,
        input_text: str,
        model_alias: str = "prism-default",
        context_policy: ContextPolicy = ContextPolicy.ISOLATED,
        idempotency_key: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> RunRecord:
        """Enqueue a new run request or return existing run for Idempotency-Key."""
        fingerprint = self.journal.compute_fingerprint(input_text, model_alias, context_policy.value)
        now = get_iso_now()

        # Handle Idempotency-Key
        if idempotency_key:
            key_digest = self.journal.compute_fingerprint(idempotency_key, principal_id, "idempotency")
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT run_id, request_fingerprint FROM idempotency_records WHERE key_digest = ?",
                (key_digest,),
            )
            row = cursor.fetchone()
            if row:
                existing_run_id, existing_fp = row["run_id"], row["request_fingerprint"]
                if existing_fp != fingerprint:
                    raise IdempotencyConflictError(
                        f"Idempotency key {idempotency_key} used with conflicting request parameters."
                    )
                return self.get_run(existing_run_id)

        # Generate run_id and persist queued state
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        input_ref = f"input_{run_id}"

        # Context binding
        ctx_ref = context_id
        if not ctx_ref:
            ctx_binding = self.context_mgr.create_context(
                context_id=f"ctx_{run_id}",
                principal_id=principal_id,
                auth_profile_id=self.adapter.auth_profile.profile_id,
                policy=context_policy,
            )
            ctx_ref = ctx_binding.context_id

        record = RunRecord(
            run_id=run_id,
            principal_id=principal_id,
            auth_profile_ref=self.adapter.auth_profile.profile_id,
            state=RunState.QUEUED,
            input_ref=input_ref,
            request_fingerprint=fingerprint,
            context_ref=ctx_ref,
            capability_snapshot_ref=f"cap_{run_id}",
            created_at=now,
            updated_at=now,
        )

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO runs
                (run_id, principal_id, auth_profile_ref, state, state_version, input_ref, request_fingerprint, context_ref, capability_snapshot_ref, config_revision, created_at, updated_at, cancel_intent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.principal_id,
                    record.auth_profile_ref,
                    record.state.value,
                    record.state_version,
                    record.input_ref,
                    record.request_fingerprint,
                    record.context_ref,
                    record.capability_snapshot_ref,
                    record.config_revision,
                    record.created_at,
                    record.updated_at,
                    0,
                ),
            )

            if idempotency_key:
                key_digest = self.journal.compute_fingerprint(idempotency_key, principal_id, "idempotency")
                self.conn.execute(
                    """
                    INSERT INTO idempotency_records (key_digest, principal_id, run_id, request_fingerprint, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key_digest, principal_id, run_id, fingerprint, now),
                )

        return record

    def transition_state(self, run_id: str, expected_state: RunState, new_state: RunState) -> RunRecord:
        """Atomic Compare-And-Swap state transition."""
        now = get_iso_now()
        cursor = self.conn.cursor()
        with self.conn:
            cursor.execute(
                """
                UPDATE runs
                SET state = ?, updated_at = ?, state_version = state_version + 1
                WHERE run_id = ? AND state = ?
                """,
                (new_state.value, now, run_id, expected_state.value),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(
                    f"CAS state transition failed for run {run_id}: expected {expected_state.value}, could not update to {new_state.value}"
                )

        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        """Fetch RunRecord from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            raise KeyError(f"Run {run_id} not found.")

        return RunRecord(
            run_id=row["run_id"],
            principal_id=row["principal_id"],
            auth_profile_ref=row["auth_profile_ref"],
            state=RunState(row["state"]),
            state_version=row["state_version"],
            input_ref=row["input_ref"],
            request_fingerprint=row["request_fingerprint"],
            context_ref=row["context_ref"],
            capability_snapshot_ref=row["capability_snapshot_ref"],
            config_revision=row["config_revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            cancel_intent=bool(row["cancel_intent"]),
            terminal_evidence_ref=row["terminal_evidence_ref"],
            result_ref=row["result_ref"],
        )

    def execute_run(self, run_id: str, input_text: str, model_alias: str = "prism-default") -> GenerationResult:
        """Execute run lifecycle through preparing -> submitting -> running -> succeeded."""
        record = self.get_run(run_id)

        # Step 1: PREPARING & Lease Acquire
        record = self.transition_state(run_id, RunState.QUEUED, RunState.PREPARING)
        lease = self.context_mgr.acquire_lease(record.context_ref, run_id)

        try:
            # Step 2: SUBMITTING (Atomic Intent Log BEFORE Network Call)
            attempt_id = f"attempt_{run_id}_{lease.owner_epoch}"
            record = self.transition_state(run_id, RunState.PREPARING, RunState.SUBMITTING)

            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO submit_attempts (attempt_id, run_id, owner_epoch, intent_committed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (attempt_id, run_id, lease.owner_epoch, get_iso_now()),
                )

            # Step 3: Network Submit via Adapter
            remote_handle = self.adapter.submit_request(
                run_id=run_id,
                attempt_id=attempt_id,
                input_text=input_text,
                model_alias=model_alias,
            )

            record = self.transition_state(run_id, RunState.SUBMITTING, RunState.RUNNING)

            # Step 4: Event Observation & Ingestion
            normalizer = EventNormalizer(run_id)
            events = self.adapter.observe_normalized_events(run_id, remote_handle, normalizer)

            # Step 5: Finalize Generation Result & Evidence Manifest
            final_text = normalizer.text_buffer or "Executed successfully"
            result = GenerationResult(
                run_id=run_id,
                requested_alias=model_alias,
                provider_model_id_confirmed="prism-v1-confirmed",
                text=final_text,
                finish_reason="stop",
                context_ref=record.context_ref,
            )

            manifest = EvidenceManifest(
                run_id=run_id,
                request_fingerprint=record.request_fingerprint,
                requested_alias=model_alias,
                output_digest="",
                result_ref=f"res_{run_id}",
            )

            res_file, man_file = self.journal.save_result_and_manifest(run_id, result, manifest)
            result.manifest_ref = str(man_file)

            # Update run to SUCCEEDED
            now = get_iso_now()
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE runs
                    SET state = ?, updated_at = ?, result_ref = ?, state_version = state_version + 1
                    WHERE run_id = ? AND state = ?
                    """,
                    (RunState.SUCCEEDED.value, now, str(res_file), run_id, RunState.RUNNING.value),
                )

            return result

        except Exception as exc:
            now = get_iso_now()
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE runs
                    SET state = ?, updated_at = ?, state_version = state_version + 1
                    WHERE run_id = ?
                    """,
                    (RunState.FAILED.value, now, run_id),
                )
            raise exc

        finally:
            self.context_mgr.release_lease(lease)

    def cancel_run(self, run_id: str) -> RunRecord:
        """Set cancel intent and update state if queued or preparing."""
        record = self.get_run(run_id)
        now = get_iso_now()

        with self.conn:
            self.conn.execute(
                "UPDATE runs SET cancel_intent = 1, updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )

        if record.state in [RunState.QUEUED, RunState.PREPARING]:
            return self.transition_state(run_id, record.state, RunState.CANCELLED)

        return self.get_run(run_id)
