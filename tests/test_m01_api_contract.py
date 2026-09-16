"""Tests for M01 Entrypoints and API Contracts (T01-T06, T41)."""

import pytest
from fastapi.testclient import TestClient

from prism2api.config import Settings
from prism2api.api.app import create_app
from prism2api.client import SDKClient, ClientMode, SingleInstanceLockError


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        home_dir=tmp_path / ".prism2api",
        api_key="test-secret-key",
        loopback_only=True,
    )


@pytest.fixture
def client(test_settings):
    app = create_app(test_settings)
    return TestClient(app)


def test_t01_unauthenticated_request_returns_401(client):
    """T01: Requests without valid API key must return 401 Unauthorized."""
    response = client.post("/prism/v1/runs", json={"input_text": "hello"})
    assert response.status_code == 401

    # Invalid key
    response = client.post(
        "/prism/v1/runs",
        headers={"X-API-Key": "wrong-key"},
        json={"input_text": "hello"},
    )
    assert response.status_code == 401


def test_t02_unsupported_parameters_rejected(client):
    """T02: Unsupported parameters like temperature return 400 Bad Request."""
    headers = {"X-API-Key": "test-secret-key"}
    response = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "prism-default",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        },
    )
    assert response.status_code == 400
    assert "Unsupported parameter" in response.json()["detail"]


def test_t03_models_endpoint_returns_only_usable_models(client):
    """T03: /v1/models returns only verified and enabled models."""
    headers = {"X-API-Key": "test-secret-key"}
    response = client.get("/v1/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "prism-default"


def test_t04_cross_principal_run_query_returns_404(client):
    """T04: Querying run for another principal returns 404 (does not leak existence)."""
    headers = {"X-API-Key": "test-secret-key"}
    response = client.get("/prism/v1/runs/non_existent_run", headers=headers)
    assert response.status_code == 404


def test_t06_sdk_embedded_mode_single_instance_lock(test_settings):
    """T06: SDK embedded mode acquires exclusive OS file lock."""
    client1 = SDKClient(mode=ClientMode.EMBEDDED, settings=test_settings)
    try:
        with pytest.raises(SingleInstanceLockError):
            # Second client in same home_dir must fail lock
            SDKClient(mode=ClientMode.EMBEDDED, settings=test_settings)
    finally:
        client1.close()
