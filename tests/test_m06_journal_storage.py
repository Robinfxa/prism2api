"""Tests for M06 Journal, Persistence, and Evidence Manifest (T35-T40)."""

import pytest
from prism2api.config import Settings
from prism2api.storage.journal import (
    StorageJournal,
    GenerationResult,
    EvidenceManifest,
    sanitize_text,
)


def test_t35_two_phase_result_and_manifest_commit(tmp_path):
    """T35: Results & manifests saved to disk with SHA-256 digest and indexed in DB."""
    settings = Settings(home_dir=tmp_path / ".prism2api")
    journal = StorageJournal(settings)

    run_id = "run_test_35"
    with journal.conn:
        journal.conn.execute(
            """
            INSERT INTO runs (run_id, principal_id, auth_profile_ref, state, state_version, input_ref, request_fingerprint, config_revision, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, "user1", "p1", "running", 1, "in1", "fp_12345", "v0.1.0", "now", "now")
        )

    result = GenerationResult(
        run_id=run_id,
        requested_alias="prism-default",
        text="Verified output content for test 35",
    )
    manifest = EvidenceManifest(
        run_id=run_id,
        request_fingerprint="fp_12345",
        requested_alias="prism-default",
        output_digest="",
        result_ref=f"res_{run_id}",
    )

    res_path, man_path = journal.save_result_and_manifest(run_id, result, manifest)

    assert res_path.is_file()
    assert man_path.is_file()
    assert result.result_digest != ""
    assert manifest.output_digest == result.result_digest

    cursor = journal.conn.cursor()
    cursor.execute("SELECT * FROM result_index WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["digest"] == result.result_digest
    journal.close()


def test_t38_sanitization_masks_api_keys():
    """T38: Sanitizer removes Authorization headers and API keys from text."""
    raw = "Header: Authorization: Bearer secret-auth-token and key sk-proj-1234567890abcdef1234567890"
    sanitized = sanitize_text(raw)
    assert "[REDACTED]" in sanitized
    assert "secret-auth-token" not in sanitized
    assert "sk-proj-1234567890" not in sanitized
