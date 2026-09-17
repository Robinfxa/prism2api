"""Unit tests for OpenAI-compatible browser_server endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from prism2api.server.browser_server import create_browser_app
from prism2api.errors import ProtocolError, AdmissionBlockedError


@pytest.fixture
def mock_transport():
    transport = MagicMock()
    transport.is_ready = True
    transport.project_id = "test-proj-uuid"
    transport.conversation_id = "cdx1_test_conv"
    transport.submit_and_poll = AsyncMock(return_value="Hello from Prism!")
    return transport


@pytest.fixture
def client(mock_transport):
    app = create_browser_app(mock_transport)
    return TestClient(app)


def test_healthz(client, mock_transport):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["browser_ready"] is True
    assert data["project_id"] == "test-proj-uuid"


def test_chat_completions_success(client, mock_transport):
    payload = {
        "model": "prism-default",
        "messages": [
            {"role": "user", "content": "hello"}
        ]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["object"] == "chat.completion"
    assert data["model"] == "prism-default"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello from Prism!"
    assert data["choices"][0]["finish_reason"] == "stop"

    mock_transport.submit_and_poll.assert_awaited_once_with(prompt="hello", timeout=60.0)


def test_invalid_model(client):
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hi"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    assert "Unsupported model" in response.json()["detail"]


def test_streaming_unsupported(client):
    payload = {
        "model": "prism-default",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    assert "Streaming is not supported" in response.json()["detail"]


def test_transport_unready(mock_transport):
    mock_transport.is_ready = False
    app = create_browser_app(mock_transport)
    c = TestClient(app)

    payload = {
        "model": "prism-default",
        "messages": [{"role": "user", "content": "hi"}]
    }
    response = c.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"]


def test_transport_timeout(client, mock_transport):
    mock_transport.submit_and_poll.side_effect = TimeoutError("Generation timed out")
    payload = {
        "model": "prism-default",
        "messages": [{"role": "user", "content": "hi"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


def test_upstream_error(client, mock_transport):
    mock_transport.submit_and_poll.side_effect = ProtocolError("Prism start failed")
    payload = {
        "model": "prism-default",
        "messages": [{"role": "user", "content": "hi"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 502
    assert "execution error" in response.json()["detail"]
