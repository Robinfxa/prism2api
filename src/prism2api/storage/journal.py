"""Journal and Evidence Manifest storage manager for M06."""

import json
import hashlib
import hmac
import tempfile
from prism2api.runtime.locking import HomeLock
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from prism2api.config import Settings
from prism2api.storage.db import get_db_connection, init_db_schema


def get_iso_now() -> str:
    """Get UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def sanitize_text(text: str) -> str:
    """Sanitize secrets like Authorization headers, API keys, and tokens from prose/logs."""
    if not text:
        return ""
    import re
    # Mask common sensitive headers and tokens
    text = re.sub(r"(Authorization:\040*)[^\r\n]+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"(Cookie:\040*)[^\r\n]+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"(sk-[A-Za-z0-9_-]{20,})", r"[REDACTED_API_KEY]", text)
    text = re.sub(r"(gh[pousr]_[A-Za-z0-9]{20,})", r"[REDACTED_GITHUB_TOKEN]", text)
    return text


def atomic_json(path: Path, data):
    """fsync the file and directory; publication to SQL occurs separately."""
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        if os.name == "posix":
            dfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class EvidenceManifest(BaseModel):
    manifest_schema_version: str = "v0.1.0"
    run_id: str
    request_fingerprint: str
    requested_alias: str
    model_evidence: Optional[Dict[str, Any]] = None
    capability_snapshot_ref: Optional[str] = None
    context_binding_ref: Optional[str] = None
    context_limitations: List[str] = Field(default_factory=list)
    submit_attempt_ref: Optional[str] = None
    remote_handle_ref: Optional[str] = None
    completion_evidence: Optional[Dict[str, Any]] = None
    output_digest: str
    result_ref: str
    delivery_summary: Dict[str, Any] = Field(default_factory=dict)
    timings: Dict[str, Optional[float]] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    redaction_version: str = "v1.0"


class GenerationResult(BaseModel):
    run_id: str
    requested_alias: str
    provider_model_id_confirmed: Optional[str] = None
    text: str
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    finish_reason: str = "stop"
    finish_reason_origin: str = "gateway_mapping"
    context_ref: Optional[str] = None
    manifest_ref: Optional[str] = None
    result_digest: str = ""
    transport_kind: str = "unknown"

    def compute_digest(self) -> str:
        """Compute SHA-256 digest of normalized result text."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


class StorageJournal:
    """Manages SQLite storage and two-phase file persistence for runs & evidence."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.ensure_directories()
        self._home_lock = HomeLock(self.settings.lock_file_path)
        self.closed = False
        self.owner = None
        try:
            self.settings.load_local_secrets()
            self.conn = get_db_connection(self.settings.db_path)
            self.lock = self.conn.lock
            init_db_schema(self.conn)
        except BaseException:
            if getattr(self, "conn", None) is not None:
                self.conn.close()
            self._home_lock.close()
            raise

    def compute_fingerprint(self, input_data: str, model_alias: str, context_policy: str) -> str:
        """Compute salted SHA-256 request fingerprint."""
        raw = json.dumps([input_data, model_alias, context_policy], ensure_ascii=False, separators=(",", ":"))
        return hmac.new(self.settings.secret_salt.encode(), raw.encode(), hashlib.sha256).hexdigest()

    def save_result_and_manifest(
        self,
        run_id: str,
        result: GenerationResult,
        manifest: EvidenceManifest,
    ) -> tuple[Path, Path]:
        """Two-phase commit for result file and evidence manifest.
        
        1. Write temporary files.
        2. Flush and atomic rename.
        3. Record in SQLite index.
        """
        digest = result.compute_digest()
        result.result_digest = digest
        manifest.output_digest = digest

        man_final = self.settings.evidence_dir / f"{run_id}.json"
        result.manifest_ref = str(man_final)

        # Write result file
        res_tmp = self.settings.results_dir / f"{run_id}.tmp"
        res_final = self.settings.results_dir / f"{run_id}.json"
        atomic_json(res_final, result.model_dump(mode="json"))

        # Write manifest file
        man_tmp = self.settings.evidence_dir / f"{run_id}.tmp"
        atomic_json(man_final, manifest.model_dump(mode="json"))

        result_id = f"res_{run_id}"
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO result_index
                (result_id, run_id, digest, text_length, result_file_path, manifest_file_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    run_id,
                    digest,
                    len(result.text),
                    str(res_final),
                    str(man_final),
                    get_iso_now(),
                ),
            )

        return res_final, man_final

    def close(self) -> None:
        """Close SQLite database connection."""
        if self.closed:
            return
        if self.owner is not None:
            self.owner.close()  # A stuck worker must NOT release this process's lock.
        with self.lock:
            self.conn.close()
            self.closed = True
            self._home_lock.close()
