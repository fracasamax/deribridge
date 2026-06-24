"""Adapter-conformance suite.

A single contract that every registered adapter must satisfy, parametrized over
all adapters that build offline (fed recorded fixtures via mocked transports).
Adding a new adapter to the registry without a harness here fails
``test_every_registered_adapter_has_a_harness`` — so coverage cannot silently
lag behind the registry.

Run under the full install (``pip install -e ".[all]"``); adapters whose extra
is absent are skipped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Awaitable, Callable, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from deribridge.core.adapter import ExchangeAdapter
from deribridge.core.models import Instrument, OrderBook, Symbol, Ticker
from deribridge.core.registry import available_adapters
from deribridge.core.transport.base import Response, StreamMessage, SubscriptionHandle

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str):
    return json.loads((_FIXTURES / name).read_text())


# --------------------------------------------------------------------------- #
# Offline harnesses (one per adapter)
# --------------------------------------------------------------------------- #
@dataclass
class Harness:
    name: str
    adapter: ExchangeAdapter
    symbol: str
    instruments_base: Optional[str]
    # subscribes `handler` then pushes one synthetic ticker event through the
    # adapter's real map->dispatch path.
    dispatch_ticker: Callable[[Callable[[Ticker], Awaitable[None]]], Awaitable[None]]


class _FakeRest:
    def __init__(self, routes):
        self.routes = routes

    async def connect(self):
        pass

    async def close(self):
        pass

    async def request(self, req):
        data = self.routes[req.path]
        return Response(data=data, raw=data if isinstance(data, dict) else {}, status=200)


class _FakeWs:
    def __init__(self):
        self.handlers = {}

    async def subscribe(self, channels, handler):
        for ch in channels:
            self.handlers[ch] = handler
        return SubscriptionHandle(channels=tuple(channels))

    async def unsubscribe(self, handle):
        pass

    async def close(self):
        pass


def _build_deribit() -> Harness:
    from deribridge.exchanges.deribit.adapter import DeribitAdapter

    iface = MagicMock()
    iface.client = MagicMock()
    iface.client.get_ticker = AsyncMock(return_value=load_fixture("deribit/ticker.json"))
    iface.client.get_order_book = AsyncMock(return_value=load_fixture("deribit/order_book.json"))
    iface.client.get_instruments = AsyncMock(return_value=load_fixture("deribit/instruments.json"))
    iface.client.subscribe_ticker = AsyncMock()
    adapter = DeribitAdapter(interface=iface)

    async def dispatch(handler):
        await adapter.subscribe_ticker("BTC-PERPETUAL", handler)
        wrapper = iface.client.subscribe_ticker.call_args.args[1]
        await wrapper({"channel": "ticker.BTC-PERPETUAL.100ms", "data": load_fixture("deribit/ticker.json")})

    return Harness("deribit", adapter, "BTC-PERPETUAL", "BTC", dispatch)


def _build_binance() -> Harness:
    from deribridge.exchanges.binance.adapter import BinanceAdapter

    rest = _FakeRest(
        {
            "/api/v3/exchangeInfo": load_fixture("binance/exchange_info.json"),
            "/api/v3/depth": load_fixture("binance/depth.json"),
            "/api/v3/ticker/bookTicker": load_fixture("binance/book_ticker.json"),
            "/api/v3/ticker/24hr": load_fixture("binance/ticker_24hr.json"),
        }
    )
    ws = _FakeWs()
    adapter = BinanceAdapter(rest=rest, ws=ws)

    async def dispatch(handler):
        await adapter.subscribe_ticker("BTCUSDT", handler)
        wrapper = ws.handlers["btcusdt@bookTicker"]
        await wrapper(StreamMessage(channel="btcusdt@bookTicker", data={"b": "35000.0", "a": "35001.0"}))

    return Harness("binance", adapter, "BTCUSDT", "BTC", dispatch)


_BUILDERS: dict[str, Callable[[], Harness]] = {
    "deribit": _build_deribit,
    "binance": _build_binance,
}


@pytest.fixture(params=sorted(_BUILDERS))
def harness(request) -> Harness:
    try:
        return _BUILDERS[request.param]()
    except ImportError as exc:  # adapter extra not installed
        pytest.skip(f"{request.param} adapter unavailable: {exc}")


# --------------------------------------------------------------------------- #
# Completeness: registry and harnesses must not drift apart
# --------------------------------------------------------------------------- #
def test_every_registered_adapter_has_a_harness():
    missing = set(available_adapters()) - set(_BUILDERS)
    assert not missing, f"registered adapters without a conformance harness: {missing}"


# --------------------------------------------------------------------------- #
# The contract
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_ticker_returns_canonical(harness):
    t = await harness.adapter.get_ticker(harness.symbol)
    assert isinstance(t, Ticker)
    assert isinstance(t.symbol, Symbol)
    assert t.symbol.exchange == harness.name
    if t.best_bid is not None:
        assert isinstance(t.best_bid, Decimal)


@pytest.mark.asyncio
async def test_get_order_book_returns_canonical(harness):
    ob = await harness.adapter.get_order_book(harness.symbol, depth=5)
    assert isinstance(ob, OrderBook)
    assert ob.best_bid is not None and ob.best_ask is not None
    assert isinstance(ob.best_bid.price, Decimal)
    assert ob.spread is not None and ob.spread >= 0


@pytest.mark.asyncio
async def test_get_instruments_returns_canonical(harness):
    insts = await harness.adapter.get_instruments(base=harness.instruments_base)
    assert insts and all(isinstance(i, Instrument) for i in insts)
    assert all(i.symbol.exchange == harness.name for i in insts)


def test_capabilities_are_coherent(harness):
    caps = harness.adapter.capabilities
    assert caps.has_rest or caps.has_websocket
    assert caps.asset_kinds  # non-empty
    assert isinstance(caps.order_types, frozenset)


@pytest.mark.asyncio
async def test_subscribe_ticker_dispatches_canonical(harness):
    if not harness.adapter.capabilities.has_websocket:
        pytest.skip("adapter has no websocket support")
    received: list[Ticker] = []

    async def on_ticker(t: Ticker) -> None:
        received.append(t)

    await harness.dispatch_ticker(on_ticker)
    assert len(received) == 1
    assert isinstance(received[0], Ticker)
