"""Unit tests for PrismWireParser using sanitized Grade A protocol fixtures."""

import json
from pathlib import Path
from prism2api.transport.prism_web.parser import PrismWireParser


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prism_protocol"


def test_parse_start_request_fixture():
    """Verify start request fixture loads and parses accurately."""
    req_path = FIXTURES_DIR / "submit_success" / "request.json"
    with open(req_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["conversationId"] == "cdx1_fixture_conv_001"
    assert data["metadata"]["projectId"] == "proj_fixture_001"
    assert data["input"][1]["content"][0]["text"] == "Reply exactly: PRISM_PROBE_001"


def test_wire_parser_start_response():
    """Verify parse_start_response maps accepted response to SubmissionObserved."""
    response_data = {"status": "accepted", "async_job_id": "job_123"}
    events = PrismWireParser.parse_start_response(response_data, task_ref="task_999")
    
    assert len(events) == 1
    assert events[0]["type"] == "SubmissionObserved"
    assert events[0]["payload"]["task_ref"] == "task_999"


def test_wire_parser_status_response_completed():
    """Verify parse_status_response maps completed status payload to RunCompleted."""
    response_data = {
        "status": "completed",
        "finish_reason": "stop",
        "text": "PRISM_PROBE_001"
    }
    events = PrismWireParser.parse_status_response(response_data, task_ref="task_999")
    
    assert len(events) == 2
    assert events[0]["type"] == "TextDelta"
    assert events[0]["payload"]["text"] == "PRISM_PROBE_001"
    assert events[1]["type"] == "RunCompleted"
    assert events[1]["payload"]["text"] == "PRISM_PROBE_001"
