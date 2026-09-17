"""Unit tests for cURL parser module."""

import os
import pytest
from pathlib import Path
from prism2api.transport.prism_web.curl_parser import parse_curl_command, import_curl_to_profile

SAMPLE_CURL = r"""
curl --url 'https://prism.openai.com/api/llm/response_with_tools_start' \
  -H 'accept: */*' \
  -b 'oaicom-stable-id=bebdca61; prism_session_token=mock_dummy_test_session_token_123' \
  -H 'origin: https://prism.openai.com' \
  --data-raw '{"input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"test"}]}],"metadata":{"projectId":"00000000-0000-0000-0000-000000000001","userId":"user-test123","model":"gpt-6-astra","sandbox_url":"https://prism.openai.com/s/sandboxes/proxy/","sandbox_token":"gAAAAABtesttoken"},"conversationId":"cdx1_00000000-0000-0000-0000-000000000001"}'
"""

def test_parse_curl_command():
    extracted = parse_curl_command(SAMPLE_CURL)
    assert "prism_session_token" in extracted["cookie_header"]
    assert extracted["user_id"] == "user-test123"
    assert extracted["project_id"] == "00000000-0000-0000-0000-000000000001"
    assert extracted["conversation_id"] == "cdx1_00000000-0000-0000-0000-000000000001"
    assert extracted["sandbox_token"] == "gAAAAABtesttoken"

def test_import_curl_to_profile(tmp_path):
    profile_path = tmp_path / "live-profile.json"
    context_path = tmp_path / "fixed-context.json"
    res = import_curl_to_profile(SAMPLE_CURL, profile_path=profile_path, context_path=context_path)
    assert res["status"] == "imported"
    assert res["profile"].user_id == "user-test123"
    assert profile_path.exists()
    assert context_path.exists()
    if os.name == "posix":
        assert oct(profile_path.stat().st_mode & 0o777) == "0o600"
        assert oct(context_path.stat().st_mode & 0o777) == "0o600"

