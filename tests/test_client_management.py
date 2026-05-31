"""Safety-focused tests for the high-level client-management helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deribridge.api_client import client_management


@pytest.mark.asyncio
async def test_connect_deribit_client_connects_exactly_once():
    """The helper must disable constructor auto-connect and connect once.

    With ``auto_connect`` left at its default, the constructor would schedule a
    background connect *and* the helper would await a second ``connect()`` —
    a double-connect. The helper must pass ``auto_connect=False`` and connect
    exactly once itself.
    """
    fake = MagicMock()
    fake.connect = AsyncMock()
    fake.connected = True
    fake.authenticate = AsyncMock()
    fake.authenticated = True
    with patch.object(
        client_management, "EnhancedDeribitClient", return_value=fake
    ) as ctor:
        await client_management.connect_deribit_client(
            client_id="x", client_secret="y", authenticate=False
        )
    assert ctor.call_args.kwargs.get("auto_connect") is False
    fake.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_constructor_failure_propagates_original_error():
    """A failure constructing the client must surface the real exception.

    The cleanup branch in ``connect_deribit_client`` references ``client``; if
    the constructor raises before ``client`` is bound, that branch must not
    shadow the original error with an ``UnboundLocalError``.
    """
    boom = RuntimeError("ctor blew up")
    with patch.object(
        client_management, "EnhancedDeribitClient", side_effect=boom
    ):
        with pytest.raises(RuntimeError) as ei:
            await client_management.connect_deribit_client(
                client_id="x", client_secret="y", authenticate=False
            )
    assert ei.value is boom
