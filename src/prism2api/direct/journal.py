"""Small persistent fixed-chat journal. Receipts are private, not API/log payloads."""
import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from .errors import DirectError
from .secure import read_private


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class Journal:
    def __init__(self, home: Path):
        path = home / 'direct.sqlite3'
        # A private regular file exists before SQLite sees it.
        if path.exists() or path.is_symlink():
            read_private(path, limit=512*1024*1024)
        else:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            os.close(fd)
        self.conn = sqlite3.connect(path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA synchronous=FULL')
        self.conn.execute('PRAGMA journal_mode=DELETE')
        self.conn.execute('''CREATE TABLE IF NOT EXISTS direct_runs (
            run_id TEXT PRIMARY KEY, key_hash TEXT UNIQUE, fingerprint TEXT NOT NULL,
            scope TEXT NOT NULL, import_id TEXT NOT NULL, state TEXT NOT NULL,
            receipt_json TEXT, text TEXT, error_code TEXT,
            start_count INTEGER NOT NULL DEFAULT 0,
            status_count INTEGER NOT NULL DEFAULT 0,
            heartbeat_count INTEGER NOT NULL DEFAULT 0,
            created REAL NOT NULL, updated REAL NOT NULL)''')
        # No browser or upstream requests during startup/recovery classification.
        self.conn.execute("UPDATE direct_runs SET state='uncertain',error_code='process_interrupted',updated=? WHERE state IN ('submitting','running')", (time.time(),))
        self.conn.execute("UPDATE direct_runs SET state='failed',error_code='interrupted_before_submit',updated=? WHERE state='preparing'", (time.time(),))

    def get(self, run_id: str) -> dict:
        row = self.conn.execute('SELECT * FROM direct_runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None: raise DirectError('run_not_found', 'Run not found.', 404)
        return dict(row)

    def pending(self) -> dict | None:
        row = self.conn.execute("SELECT * FROM direct_runs WHERE state IN ('submitting','running','uncertain') LIMIT 1").fetchone()
        return dict(row) if row else None

    def accept(self, prompt: str, import_id: str, scope: str, idempotency_key: str | None) -> tuple[dict, bool]:
        fp = digest(import_id + '\0' + scope + '\0' + prompt)
        kh = digest(idempotency_key) if idempotency_key else None
        if kh:
            row = self.conn.execute('SELECT * FROM direct_runs WHERE key_hash=?', (kh,)).fetchone()
            if row:
                row = dict(row)
                if row['fingerprint'] != fp:
                    raise DirectError('idempotency_conflict', 'Idempotency key refers to a different request or imported context.', 409)
                return row, False
        pending = self.pending()
        if pending:
            raise DirectError('unresolved_run', 'A prior task may still be running. Inspect/reconcile it before another submit.', 409, run_id=pending['run_id'])
        rid = 'run_' + uuid.uuid4().hex
        now = time.time()
        self.conn.execute('INSERT INTO direct_runs(run_id,key_hash,fingerprint,scope,import_id,state,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                          (rid, kh, fp, scope, import_id, 'preparing', now, now))
        return self.get(rid), True

    def update(self, run_id: str, **fields):
        allowed = {'state','receipt_json','text','error_code'}
        if not fields or not set(fields) <= allowed: raise ValueError('Invalid journal fields')
        fields['updated'] = time.time()
        self.conn.execute('UPDATE direct_runs SET '+','.join(f'{k}=?' for k in fields)+' WHERE run_id=?', [*fields.values(), run_id])

    def count(self, run_id: str, field: str):
        if field not in {'start_count','status_count','heartbeat_count'}: raise ValueError('Invalid counter')
        self.conn.execute(f'UPDATE direct_runs SET {field}={field}+1,updated=? WHERE run_id=?', (time.time(),run_id))

    def save_receipt(self, run_id: str, receipt: dict):
        self.update(run_id, receipt_json=json.dumps(receipt, ensure_ascii=False, allow_nan=False))

    def public(self, run_id: str) -> dict:
        row = self.get(run_id)
        return {k: row[k] for k in ('run_id','state','error_code','start_count','status_count','heartbeat_count','created','updated')}

    def close(self): self.conn.close()
