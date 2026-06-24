"""Tests for BinanceAdapter using injected fake transports (no network).

Importing the adapter pulls httpx (the binance extra); these tests run under
the full ``[all]`` install.
"""
from decimal import Decimal

import pytest

from deribridge.core.enums import AssetKind, Interval
from deribridge.core.errors import UnsupportedOperation
from deribridge.core.models import OrderBook, Ticker
from deribridge.core.transport.base import Response, StreamMessage, SubscriptionHandle
from deribridge.exchanges.binance.adapter import BinanceAdapter


class FakeRest:
    """Routes requests to fixture data by path."""

    def __init__(self, routes):
        self.routes = routes

    async def connect(self):
        pass

    async def close(self):
        pass

    async def request(self, req):
        data = self.routes[req.path]
        raw = data if isinstance(data, dict) else {"data": data}
        return Response(data=data, raw=raw, status=200)


class FakeWs:
    """Records subscriptions and exposes the wrapped handler for invocation."""

    def __init__(self):
        self.handlers = {}

    async def subscribe(self, channels, handler):
        for ch in channels:
            self.handlers[ch] = handler
        return SubscriptionHandle(channels=tuple(channels))

    async def unsubscribe(self, handle):
        for ch in handle.channels:
            self.handlers.pop(ch, None)

    async def close(self):
        self.handlers.clear()


def _adapter(load_json, ws=None):
    rest = FakeRest(
        {
            "/api/v3/exchangeInfo": load_json("binance/exchange_info.json"),
            "/api/v3/depth": load_json("binance/depth.json"),
            "/api/v3/ticker/bookTicker": load_json("binance/book_ticker.json"),
            "/api/v3/ticker/24hr": load_json("binance/ticker_24hr.json"),
            "/api/v3/klines": load_json("binance/klines.json"),
        }
    )
    return BinanceAdapter(rest=rest, ws=ws or FakeWs())


@pytest.mark.asyncio
async def test_get_instruments_maps_and_filters(load_json):
    adapter = _adapter(load_json)
    all_inst = await adapter.get_instruments()
    assert {i.symbol.raw for i in all_inst} == {"BTCUSDT", "ETHUSDT"}

    btc = await adapter.get_instruments(base="BTC")
    assert [i.symbol.raw for i in btc] == ["BTCUSDT"]

    # spot-only adapter returns nothing for a derivatives kind
    assert await adapter.get_instruments(kind=AssetKind.OPTION) == []


@pytest.mark.asyncio
async def test_get_order_book_returns_canonical(load_json):
    adapter = _adapter(load_json)
    ob = await adapter.get_order_book("BTCUSDT", depth=10)
    assert isinstance(ob, OrderBook)
    assert ob.best_bid.price == Decimal("35000.00")
    assert ob.spread == Decimal("1.00")


@pytest.mark.asyncio
async def test_get_ticker_merges_rest_calls(load_json):
    adapter = _adapter(load_json)
    t = await adapter.get_ticker("BTCUSDT")
    assert isinstance(t, Ticker)
    assert t.best_bid == Decimal("35000.00")
    assert t.last == Decimal("35000.50")


@pytest.mark.asyncio
async def test_get_candles(load_json):
    adapter = _adapter(load_json)
    candles = await adapter.get_candles("BTCUSDT", Interval.ONE_MINUTE, limit=2)
    assert len(candles) == 2
    assert candles[0].open == Decimal("35000.0")


@pytest.mark.asyncio
async def test_subscribe_ticker_dispatches_canonical(load_json):
    ws = FakeWs()
    adapter = _adapter(load_json, ws=ws)
    received = []

    async def on_ticker(t):
        received.append(t)

    handle = await adapter.subscribe_ticker("BTCUSDT", on_ticker)
    assert handle.channels == ("btcusdt@bookTicker",)
    # The adapter registered a wrapper under the bookTicker stream; feed it a
    # WS-shaped payload and confirm the user handler gets a canonical Ticker.
    wrapper = ws.handlers["btcusdt@bookTicker"]
    await wrapper(StreamMessage(channel="btcusdt@bookTicker", data={"b": "35000.0", "a": "35001.0"}))

    assert len(received) == 1
    assert isinstance(received[0], Ticker)
    assert received[0].best_bid == Decimal("35000.0")


@pytest.mark.asyncio
async def test_private_endpoints_are_unsupported(load_json):
    adapter = _adapter(load_json)
    assert adapter.capabilities.trading is False
    with pytest.raises(UnsupportedOperation):
        await adapter.get_account()
    with pytest.raises(UnsupportedOperation):
        await adapter.get_positions()
