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
  --data-raw '{"input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"test"}]}],"metadata":{"projectId":"82982e0a-aba1-4f60-991b-047ce491b54d","userId":"user-test123","model":"gpt-6-astra","sandbox_url":"https://prism.openai.com/s/sandboxes/proxy/","sandbox_token":"gAAAAABtesttoken"},"conversationId":"cdx1_b4b9105f-cc45-411c-a3ac-745b6cd8de40"}'
"""

def test_parse_curl_command():
    extracted = parse_curl_command(SAMPLE_CURL)
    assert "prism_session_token" in extracted["cookie_header"]
    assert extracted["user_id"] == "user-test123"
    assert extracted["project_id"] == "82982e0a-aba1-4f60-991b-047ce491b54d"
    assert extracted["conversation_id"] == "cdx1_b4b9105f-cc45-411c-a3ac-745b6cd8de40"
    assert extracted["sandbox_token"] == "gAAAAABtesttoken"

def test_import_curl_to_profile(tmp_path):
    target_path = tmp_path / "live-profile.json"
    profile = import_curl_to_profile(SAMPLE_CURL, target_path=target_path)
    assert profile.user_id == "user-test123"
    assert target_path.exists()
    if os.name == "posix":
        assert oct(target_path.stat().st_mode & 0o777) == "0o600"
