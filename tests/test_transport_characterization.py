"""Characterization tests for the Deribit WebSocket transport.

These pin behavior that the multi-exchange refactor must preserve when the
WebSocket client is relocated and wrapped behind the generic transport
abstraction. They are deliberately behavior-level (no internals beyond the
public-ish surface the refactor will keep): request id sequencing, the timeout
contract that feeds the indeterminate-order signal, pending-request cleanup,
and resubscribe-on-reconnect.
"""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from deribridge.api_client.websocket_api_client import DeribitWebSocketError


# --------------------------------------------------------------------------- #
# Request id sequencing
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_send_request_increments_message_id(make_deribit_ws_client):
    client = make_deribit_ws_client(connected=True, authenticated=True)
    seen_ids = []

    async def _send(raw):
        message = json.loads(raw)
        seen_ids.append(message["id"])
        fut = client.pending_requests[message["id"]]
        if not fut.done():
            fut.set_result({"ok": True})

    client.ws.send = AsyncMock(side_effect=_send)

    await client.send_request("public/test", {})
    await client.send_request("public/test", {})
    await client.send_request("public/test", {})

    assert seen_ids == sorted(seen_ids)
    assert len(set(seen_ids)) == 3  # strictly increasing / unique


# --------------------------------------------------------------------------- #
# Timeout contract -> feeds IndeterminateOrderError upstream
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_send_request_timeout_raises_sentinel_and_cleans_up(
    make_deribit_ws_client, monkeypatch
):
    """A request whose reply never arrives must raise DeribitWebSocketError(-1)
    (the timeout sentinel the interface treats as INDETERMINATE) and must not
    leak the pending future."""
    client = make_deribit_ws_client(connected=True, authenticated=True)
    client.ws.send = AsyncMock()  # never resolves the future

    async def _instant_timeout(_fut, timeout):  # noqa: ANN001
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", _instant_timeout)

    with pytest.raises(DeribitWebSocketError) as ei:
        await client.send_request("private/buy", {}, auth_required=True)

    assert ei.value.code == -1
    assert "private/buy" in str(ei.value.message)
    assert client.pending_requests == {}  # cleaned up, no leak


# --------------------------------------------------------------------------- #
# Resubscribe on reconnect re-sends every tracked channel
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_resubscribe_resends_all_tracked_channels(make_deribit_ws_client):
    client = make_deribit_ws_client(connected=True, authenticated=True)
    client.subscription_channels = {
        "ticker.BTC-PERPETUAL.100ms",
        "book.ETH-PERPETUAL.100ms",
    }
    sent = AsyncMock(return_value={"ok": True})
    client.send_request = sent

    await client._resubscribe()

    sent.assert_awaited_once()
    method, params = sent.await_args.args[:2]
    assert method == "public/subscribe"
    assert set(params["channels"]) == client.subscription_channels


@pytest.mark.asyncio
async def test_resubscribe_noop_when_no_channels(make_deribit_ws_client):
    client = make_deribit_ws_client(connected=True, authenticated=True)
    client.subscription_channels = set()
    client.send_request = AsyncMock()

    await client._resubscribe()

    client.send_request.assert_not_called()
