"""Shared test fixtures for deribridge.

Centralises the fake-WebSocket / recorded-payload helpers that were previously
inlined per test. These are reused by the Deribit safety tests, the transport
characterization tests, and (later) the adapter-conformance suite.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from unittest.mock import AsyncMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """Load a recorded JSON payload from tests/fixtures/.

    Args:
        name: file name relative to tests/fixtures (e.g. "deribit/ticker.json").
    """
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


@pytest.fixture
def load_json() -> Callable[[str], Any]:
    """Fixture returning the recorded-payload loader."""
    return load_fixture


@pytest.fixture
def make_deribit_ws_client() -> Callable[..., Any]:
    """Factory fixture building a DeribitWebSocketClient with a mocked transport.

    No live connection and no implicit connect. Mirrors the helper that the
    safety tests use, exposed once so multiple test modules can share it.
    """
    from deribridge.api_client.websocket_api_client import DeribitWebSocketClient

    def _make(connected: bool = True, authenticated: bool = False):
        client = DeribitWebSocketClient(
            client_id="cid",
            client_secret="secret",
            auto_connect=False,
        )
        client.connected = connected
        client.authenticated = authenticated
        client.ws = AsyncMock()
        return client

    return _make
