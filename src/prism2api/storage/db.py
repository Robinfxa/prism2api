"""SQLite Database connection and Schema setup for M06 Journal."""

import sqlite3
from pathlib import Path
import threading
from typing import Optional


class LockedConnection(sqlite3.Connection):
    """Short, serialized SQLite transactions with correct nested savepoints."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.RLock()
        self._local = threading.local()

    def __enter__(self):
        self.lock.acquire()
        stack = getattr(self._local, "stack", [])
        marker = f"nested_{len(stack)}" if self.in_transaction else None
        try:
            self.execute(f"SAVEPOINT {marker}" if marker else "BEGIN IMMEDIATE")
        except BaseException:
            self.lock.release()
            raise
        stack.append(marker)
        self._local.stack = stack
        return self

    def __exit__(self, typ, value, tb):
        marker = self._local.stack.pop()
        try:
            if marker:
                if typ:
                    self.execute(f"ROLLBACK TO {marker}")
                self.execute(f"RELEASE {marker}")
            else:
                try:
                    self.execute("ROLLBACK" if typ else "COMMIT")
                except BaseException:
                    if self.in_transaction:
                        self.rollback()
                    raise
        finally:
            self.lock.release()
        return False


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and busy timeout."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False, isolation_level=None, factory=LockedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = FULL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables for M06 Journal."""
    with conn.lock:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            auth_profile_ref TEXT NOT NULL,
            state TEXT NOT NULL,
            state_version INTEGER NOT NULL DEFAULT 1,
            input_ref TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            context_ref TEXT,
            capability_snapshot_ref TEXT,
            config_revision TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            cancel_intent INTEGER NOT NULL DEFAULT 0,
            terminal_evidence_ref TEXT,
            result_ref TEXT
        );

        CREATE TABLE IF NOT EXISTS submit_attempts (
            attempt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            owner_epoch INTEGER NOT NULL,
            intent_committed_at TEXT NOT NULL,
            dispatch_outcome TEXT,
            remote_handle TEXT,
            receipt_evidence_ref TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS resource_operations (
            operation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_ref TEXT,
            intent_committed_at TEXT NOT NULL,
            confirmed_handle TEXT,
            is_uncertain INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS idempotency_records (
            key_digest TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS contexts (
            context_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            auth_profile_id TEXT NOT NULL,
            context_policy TEXT NOT NULL,
            workspace_ref TEXT,
            conversation_ref TEXT,
            context_revision INTEGER NOT NULL DEFAULT 1,
            busy_run_id TEXT,
            lease_epoch INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_evidence (
            capability_id TEXT PRIMARY KEY,
            evidence_state TEXT NOT NULL,
            activation_state TEXT NOT NULL,
            account_scope TEXT,
            transport_revision TEXT NOT NULL,
            parser_revision TEXT NOT NULL,
            data_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_metadata (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            attempt_id TEXT,
            local_seq INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            received_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS deliveries (
            delivery_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            principal_id TEXT NOT NULL,
            protocol_version TEXT NOT NULL,
            state TEXT NOT NULL,
            bytes_sent INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            error_code TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS result_index (
            result_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            digest TEXT NOT NULL,
            text_length INTEGER NOT NULL,
            result_file_path TEXT NOT NULL,
            manifest_file_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS request_snapshots (
            run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
            schema_version TEXT NOT NULL,
            input_json TEXT NOT NULL,
            request_json TEXT NOT NULL,
            fingerprint TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_runs_state ON runs(state);
        CREATE INDEX IF NOT EXISTS idx_runs_principal ON runs(principal_id);
        CREATE INDEX IF NOT EXISTS idx_idempotency_principal ON idempotency_records(principal_id);
        """)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    with conn:
        if "error_code" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN error_code TEXT")
        if "cancel_dispatched" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN cancel_dispatched INTEGER NOT NULL DEFAULT 0")
