"""Unit tests for PrismLiveProfile loading and 0600 file permission validation."""

import os
import json
import tempfile
from pathlib import Path
import pytest

from prism2api.transport.prism_web.live_profile import PrismLiveProfile
from prism2api.errors import AdmissionBlockedError


def test_prism_live_profile_load_valid():
    """Verify PrismLiveProfile loads correctly from json file with 0600 permissions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = Path(tmpdir) / "live-profile.json"
        data = {
            "user_id": "user_fixture_123",
            "sandbox_url": "https://prism.openai.com/s/sandboxes/proxy/",
            "sandbox_token": "gAAAAA_sandbox_token_fixture",
            "cookie_header": "prism_session_token=valid; prism_oai_access_token=valid",
        }
        profile_path.write_text(json.dumps(data), encoding="utf-8")
        if os.name == "posix":
            profile_path.chmod(0o600)

        profile = PrismLiveProfile.load(profile_path)
        assert profile.user_id == "user_fixture_123"
        assert profile.sandbox_url == "https://prism.openai.com/s/sandboxes/proxy/"
        assert profile.sandbox_token == "gAAAAA_sandbox_token_fixture"
        assert profile.cookie_header == "prism_session_token=valid; prism_oai_access_token=valid"


def test_prism_live_profile_missing_file_raises():
    """Verify loading from non-existent path raises AdmissionBlockedError."""
    with pytest.raises(AdmissionBlockedError, match="file not found"):
        PrismLiveProfile.load(Path("/tmp/nonexistent_live_profile_path_123.json"))
