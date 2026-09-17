"""Unit tests for PrismBrowserTransport logic."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from prism2api.transport.prism_browser import PrismBrowserTransport
from prism2api.errors import ProtocolError, AdmissionBlockedError


@pytest.mark.asyncio
async def test_prism_browser_transport_not_ready():
    transport = PrismBrowserTransport(
        project_id="proj-123",
        conversation_id="cdx1_456",
        headless=True
    )
    assert not transport.is_ready

    with pytest.raises(AdmissionBlockedError, match="not ready"):
        await transport.submit_and_poll("hello")


@pytest.mark.asyncio
async def test_prism_browser_transport_submit_and_poll_success():
    transport = PrismBrowserTransport(
        project_id="proj-123",
        conversation_id="cdx1_456",
        headless=True
    )
    transport._is_ready = True
    mock_page = MagicMock()
    mock_page.is_closed.return_value = False
    transport._page = mock_page

    # Mock evaluate calls: 1st call for start, 2nd call for status
    start_payload = {
        "data": {
            "request_id": "req-999",
            "turn_state": "turn-888"
        }
    }
    status_payload = {
        "data": {
            "status": "completed",
            "response": {
                "status": "success",
                "payload": {
                    "output": [
                        {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "Hello from mock Prism!"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }

    mock_page.evaluate = AsyncMock(side_effect=[start_payload, status_payload])

    result = await transport.submit_and_poll("MVP_001", timeout=5.0)
    assert result == "Hello from mock Prism!"
    assert mock_page.evaluate.await_count == 2


@pytest.mark.asyncio
async def test_prism_browser_transport_missing_ids():
    transport = PrismBrowserTransport(
        project_id="proj-123",
        conversation_id="cdx1_456",
        headless=True
    )
    transport._is_ready = True
    mock_page = MagicMock()
    mock_page.is_closed.return_value = False
    transport._page = mock_page

    # Missing request_id/turn_state
    mock_page.evaluate = AsyncMock(return_value={"data": {}})

    with pytest.raises(ProtocolError, match="missing required request_id"):
        await transport.submit_and_poll("hello", timeout=5.0)
