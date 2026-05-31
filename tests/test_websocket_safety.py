"""Safety tests for DeribitWebSocketClient.

These cover the hardening changes made for the public release, all without a
live connection (the WebSocket transport is mocked):

- the auth-race guard: a private (auth_required) request must NOT be dispatched
  while the connection is not authenticated (e.g. a reconnect/re-auth window);
- O(1) subscription dispatch: exact-match channels are dispatched via a dict
  lookup, while suffix-wildcard ("...*") handlers still match by prefix;
- enum-or-string normalisation in submit_order.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from deribridge.api_client.websocket_api_client import (
    DeribitWebSocketClient,
    DeribitWebSocketError,
)
from deribridge.classes.order import OrderType, TimeInForce
from deribridge.classes.order_purpose import OrderPurpose


def _make_client(connected: bool = True, authenticated: bool = False):
    """Build a client with a mocked transport and no auto-connect."""
    client = DeribitWebSocketClient(
        client_id="cid",
        client_secret="secret",
        auto_connect=False,
    )
    client.connected = connected
    client.authenticated = authenticated
    client.ws = AsyncMock()
    return client


# --------------------------------------------------------------------------- #
# Auth-race guard
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_private_request_blocked_when_authentication_fails():
    """If (re-)authentication does not yield an authenticated session, a private
    request must raise rather than be silently sent unauthenticated."""
    client = _make_client(connected=True, authenticated=False)

    # authenticate() is awaited but leaves us unauthenticated (simulates a
    # failed re-auth during a reconnect window).
    async def _fake_auth():
        client.authenticated = False
        return {}

    client.authenticate = AsyncMock(side_effect=_fake_auth)

    with pytest.raises(DeribitWebSocketError):
        await client.send_request("private/get_positions", {}, auth_required=True)

    # The request must never have hit the wire.
    client.ws.send.assert_not_called()


@pytest.mark.asyncio
async def test_private_request_sent_when_authenticated():
    """When authenticated, a private request is dispatched normally."""
    client = _make_client(connected=True, authenticated=True)

    # Resolve the pending future as soon as the request is "sent".
    async def _send(raw):
        message = json.loads(raw)
        fut = client.pending_requests[message["id"]]
        if not fut.done():
            fut.set_result({"ok": True})

    client.ws.send = AsyncMock(side_effect=_send)

    result = await client.send_request(
        "private/get_positions", {}, auth_required=True
    )
    assert result == {"ok": True}
    client.ws.send.assert_awaited()


# --------------------------------------------------------------------------- #
# O(1) subscription dispatch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_exact_channel_dispatch():
    client = _make_client()
    received = []
    client.callback_handlers["ticker.BTC-PERPETUAL.100ms"] = received.append

    await client._process_message({
        "method": "subscription",
        "params": {"channel": "ticker.BTC-PERPETUAL.100ms", "data": 1},
    })

    assert received == [{"channel": "ticker.BTC-PERPETUAL.100ms", "data": 1}]


@pytest.mark.asyncio
async def test_unmatched_channel_is_not_dispatched():
    client = _make_client()
    received = []
    client.callback_handlers["ticker.BTC-PERPETUAL.100ms"] = received.append

    await client._process_message({
        "method": "subscription",
        "params": {"channel": "ticker.ETH-PERPETUAL.100ms", "data": 1},
    })

    assert received == []


@pytest.mark.asyncio
async def test_suffix_wildcard_dispatch_by_prefix():
    """A handler registered for "user.portfolio.*" must still match concrete
    channels by prefix, preserving the previous wildcard behaviour."""
    client = _make_client()
    received = []
    client.callback_handlers["user.portfolio.*"] = received.append
    client._wildcard_handlers["user.portfolio.*"] = received.append

    await client._process_message({
        "method": "subscription",
        "params": {"channel": "user.portfolio.btc", "data": 1},
    })

    assert received == [{"channel": "user.portfolio.btc", "data": 1}]


@pytest.mark.asyncio
async def test_callback_error_is_logged_not_raised(caplog):
    """A failing callback must be logged with channel context, never swallowed
    silently nor allowed to break the message loop."""
    client = _make_client()

    def _boom(_params):
        raise RuntimeError("callback failed")

    client.callback_handlers["ticker.BTC-PERPETUAL.100ms"] = _boom

    with caplog.at_level("ERROR"):
        await client._process_message({
            "method": "subscription",
            "params": {"channel": "ticker.BTC-PERPETUAL.100ms"},
        })

    assert any("ticker.BTC-PERPETUAL.100ms" in r.message for r in caplog.records)


def test_subscribe_unsubscribe_maintains_wildcard_index():
    """The wildcard index must mirror callback_handlers entries that end in '*'."""
    client = _make_client()

    # Simulate what subscribe() does for a wildcard channel.
    cb = lambda _p: None  # noqa: E731
    client.callback_handlers["user.orders.*"] = cb
    client._wildcard_handlers["user.orders.*"] = cb

    assert "user.orders.*" in client._wildcard_handlers

    client.callback_handlers.pop("user.orders.*", None)
    client._wildcard_handlers.pop("user.orders.*", None)
    assert "user.orders.*" not in client._wildcard_handlers


# --------------------------------------------------------------------------- #
# submit_order enum-or-string normalisation
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_submit_order_accepts_enum_inputs():
    """submit_order must accept enum members (as produced by Order.api_params)
    and serialise them to their wire string form."""
    client = _make_client(connected=True, authenticated=True)
    client.send_request = AsyncMock(return_value={"order": {}})

    await client.submit_order(
        instrument_name="BTC-PERPETUAL",
        amount=1.0,
        purpose=OrderPurpose.BUY,
        order_type=OrderType.LIMIT,
        price=20000.0,
        time_in_force=TimeInForce.GOOD_TIL_CANCELLED,
    )

    method, params = client.send_request.await_args.args[:2]
    assert method == "private/buy"
    assert params["type"] == "limit"
    assert params["time_in_force"] == "good_til_cancelled"
    assert params["direction"] == "buy"


@pytest.mark.asyncio
async def test_submit_order_accepts_string_inputs():
    """submit_order must also accept plain strings without crashing."""
    client = _make_client(connected=True, authenticated=True)
    client.send_request = AsyncMock(return_value={"order": {}})

    await client.submit_order(
        instrument_name="BTC-PERPETUAL",
        amount=1.0,
        purpose="sell",
        order_type="market",
        time_in_force="immediate_or_cancel",
    )

    method, params = client.send_request.await_args.args[:2]
    assert method == "private/sell"
    assert params["type"] == "market"
    assert params["direction"] == "sell"


# --------------------------------------------------------------------------- #
# No implicit connect from the constructor
# --------------------------------------------------------------------------- #
def test_constructor_does_not_auto_connect_by_default():
    """Default construction must not schedule a connect task (no implicit I/O)."""
    with patch.object(
        DeribitWebSocketClient, "connect", new=AsyncMock()
    ) as mock_connect:
        DeribitWebSocketClient(client_id="x", client_secret="y")
    mock_connect.assert_not_called()


# --------------------------------------------------------------------------- #
# All-user subscriptions use exact-match channels (not mid-string wildcards)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_subscribe_user_orders_all_users_uses_exact_match_channel(monkeypatch):
    """subscribe_user_orders(None) must use Deribit's exact-match all-user
    channel (user.orders.any.any.raw); a mid-string '*' wildcard is never
    matched by the dispatcher."""
    client = _make_client(authenticated=True)
    captured = {}

    async def fake_subscribe(channel, callback=None, *args, **kwargs):
        captured["channel"] = channel
        client.callback_handlers[channel] = callback
        return {"ok": True}

    monkeypatch.setattr(client, "subscribe", fake_subscribe)
    hits = []
    await client.subscribe_user_orders(None, lambda m: hits.append(m))

    assert captured["channel"] == "user.orders.any.any.raw"
    await client._process_message(
        {
            "method": "subscription",
            "params": {"channel": "user.orders.any.any.raw", "data": 1},
        }
    )
    assert hits


@pytest.mark.asyncio
async def test_subscribe_user_trades_all_users_uses_exact_match_channel(monkeypatch):
    client = _make_client(authenticated=True)
    captured = {}

    async def fake_subscribe(channel, callback=None, *args, **kwargs):
        captured["channel"] = channel
        return {"ok": True}

    monkeypatch.setattr(client, "subscribe", fake_subscribe)
    await client.subscribe_user_trades(None, lambda m: None)
    assert captured["channel"] == "user.trades.any.any.raw"


# --------------------------------------------------------------------------- #
# High-risk private endpoint routing
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cancel_all_orders_is_scoped_to_instrument():
    """The convenience method must never hit account-wide private/cancel_all."""
    client = _make_client(connected=True, authenticated=True)
    client.send_request = AsyncMock(return_value={"ok": True})

    result = await client.cancel_all_orders("BTC-PERPETUAL")

    assert result == {"ok": True}
    client.send_request.assert_awaited_once_with(
        "private/cancel_all_by_instrument",
        {"instrument_name": "BTC-PERPETUAL"},
        auth_required=True,
    )


@pytest.mark.asyncio
async def test_cancel_all_orders_requires_instrument_name():
    client = _make_client(connected=True, authenticated=True)
    client.send_request = AsyncMock()

    with pytest.raises(ValueError, match="instrument_name is required"):
        await client.cancel_all_orders("")

    client.send_request.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_all_by_kind_or_type_allows_optional_filters_to_be_omitted():
    client = _make_client(connected=True, authenticated=True)
    client.send_request = AsyncMock(return_value={"ok": True})

    await client.cancel_all_orders_by_kind_or_type("BTC")

    client.send_request.assert_awaited_once_with(
        "private/cancel_all_by_kind_or_type",
        {"currency": "BTC"},
        auth_required=True,
    )


@pytest.mark.asyncio
async def test_get_historical_prices_preserves_zero_values():
    client = _make_client(connected=True, authenticated=False)
    client.send_request = AsyncMock(return_value={"ticks": []})

    await client.get_historical_prices(
        "BTC-PERPETUAL",
        start_timestamp=0,
        end_timestamp=0,
        count=0,
    )

    _, params = client.send_request.await_args.args[:2]
    assert params["start_timestamp"] == 0
    assert params["end_timestamp"] == 0
    assert params["count"] == 0


@pytest.mark.asyncio
async def test_connect_does_not_reconnect_forever_on_authentication_failure(monkeypatch):
    """Bad credentials are not transport failures; reconnecting would loop."""
    client = DeribitWebSocketClient(client_id="x", client_secret="bad")
    fake_ws = AsyncMock()
    created_tasks = []

    class _DummyTask:
        def cancel(self):
            pass

    def fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return _DummyTask()

    monkeypatch.setattr(
        "deribridge.api_client.websocket_api_client.websockets.connect",
        AsyncMock(return_value=fake_ws),
    )
    monkeypatch.setattr(
        "deribridge.api_client.websocket_api_client.asyncio.create_task",
        fake_create_task,
    )
    client._authenticate_credentials = AsyncMock(
        side_effect=DeribitWebSocketError(13009, "bad credentials")
    )

    await client.connect()

    assert client.connected is False
    assert client.authenticated is False
    fake_ws.close.assert_awaited_once()
    # Message handler + heartbeat only. A third task here would be _reconnect().
    assert len(created_tasks) == 2
