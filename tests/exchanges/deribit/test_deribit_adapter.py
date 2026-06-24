"""Tests for DeribitAdapter: canonical surface + order-safety trichotomy.

The adapter is built with an injected mock interface so no socket is opened.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from deribridge.core.enums import OrderType, Side
from deribridge.core.errors import IndeterminateOrderError, OrderRejected
from deribridge.core.models import FundingRate, Order, OrderRequest, Ticker
from deribridge.exchanges.deribit.adapter import DeribitAdapter
from deribridge.exchanges.deribit.deribit_response_models import Order as WireOrder


def _make_adapter():
    iface = MagicMock()
    iface.client = MagicMock()
    return DeribitAdapter(interface=iface), iface


def _wire_order(**overrides):
    data = {
        "order_id": "ETH-123",
        "instrument_name": "BTC-PERPETUAL",
        "direction": "buy",
        "amount": 10.0,
        "price": 35000.0,
        "order_state": "open",
        "order_type": "limit",
        "filled_amount": 0.0,
        "time_in_force": "good_til_cancelled",
        "creation_timestamp": 1700000000000,
        "last_update_timestamp": 1700000000000,
    }
    data.update(overrides)
    return WireOrder.from_dict(data)


def _sample_request():
    return OrderRequest(
        symbol="BTC-PERPETUAL",
        side=Side.BUY,
        type=OrderType.LIMIT,
        amount=Decimal("10"),
        price=Decimal("35000"),
    )


# --------------------------------------------------------------------------- #
# market data
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_ticker_returns_canonical(load_json):
    adapter, iface = _make_adapter()
    iface.client.get_ticker = AsyncMock(return_value=load_json("deribit/ticker.json"))

    ticker = await adapter.get_ticker("BTC-PERPETUAL")

    assert isinstance(ticker, Ticker)
    assert ticker.mark_price == Decimal("35000.25")
    iface.client.get_ticker.assert_awaited_once_with("BTC-PERPETUAL")


@pytest.mark.asyncio
async def test_get_order_book_honors_depth(load_json):
    adapter, iface = _make_adapter()
    iface.client.get_order_book = AsyncMock(return_value=load_json("deribit/order_book.json"))

    ob = await adapter.get_order_book("BTC-PERPETUAL", depth=5)

    assert ob.best_ask.price == Decimal("35001.0")
    iface.client.get_order_book.assert_awaited_once_with("BTC-PERPETUAL", 5)


@pytest.mark.asyncio
async def test_get_funding_rate_reads_current_funding():
    adapter, iface = _make_adapter()
    iface.client.get_ticker = AsyncMock(
        return_value={
            "instrument_name": "BTC-PERPETUAL",
            "current_funding": 0.0001,
            "timestamp": 1700000000000,
        }
    )

    fr = await adapter.get_funding_rate("BTC-PERPETUAL")

    assert isinstance(fr, FundingRate)
    assert fr.rate == 0.0001
    assert isinstance(fr.rate, float)  # analytics stays float
    assert fr.symbol.canonical == "BTC/USD:perpetual"
    iface.client.get_ticker.assert_awaited_once_with("BTC-PERPETUAL")


# --------------------------------------------------------------------------- #
# streaming: user-order dispatch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_subscribe_orders_dispatches_canonical_order():
    adapter, iface = _make_adapter()
    iface.client.subscribe_user_orders = AsyncMock()

    received: list[Order] = []

    async def on_order(o: Order) -> None:
        received.append(o)

    handle = await adapter.subscribe_orders(on_order)
    assert handle.channels == ("user.orders.any.any.raw",)

    # Capture the callback the adapter registered with the ws client and push a
    # raw user.orders message through the real map->dispatch path.
    callback = iface.client.subscribe_user_orders.call_args.kwargs["callback"]
    raw_order = {
        "order_id": "ETH-999",
        "instrument_name": "BTC-PERPETUAL",
        "direction": "sell",
        "amount": 5.0,
        "price": 36000.0,
        "order_state": "open",
        "order_type": "limit",
        "filled_amount": 0.0,
    }
    await callback({"channel": "user.orders.any.any.raw", "data": raw_order})

    assert len(received) == 1
    assert isinstance(received[0], Order)
    assert received[0].order_id == "ETH-999"
    assert received[0].side is Side.SELL


@pytest.mark.asyncio
async def test_subscribe_orders_handles_batched_list_payload():
    adapter, iface = _make_adapter()
    iface.client.subscribe_user_orders = AsyncMock()

    received: list[Order] = []

    async def on_order(o: Order) -> None:
        received.append(o)

    await adapter.subscribe_orders(on_order)
    callback = iface.client.subscribe_user_orders.call_args.kwargs["callback"]
    raws = [
        {"order_id": "A-1", "instrument_name": "BTC-PERPETUAL", "direction": "buy"},
        {"order_id": "A-2", "instrument_name": "BTC-PERPETUAL", "direction": "sell"},
    ]
    await callback({"channel": "user.orders.any.any.raw", "data": raws})

    assert [o.order_id for o in received] == ["A-1", "A-2"]


# --------------------------------------------------------------------------- #
# submit_order trichotomy
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_submit_order_success_returns_canonical_order():
    adapter, iface = _make_adapter()
    iface.submit_order = AsyncMock(return_value=SimpleNamespace(order=_wire_order(), trades=[]))

    order = await adapter.submit_order(_sample_request())

    assert isinstance(order, Order)
    assert order.order_id == "ETH-123"
    assert order.side is Side.BUY
    assert order.price == Decimal("35000.0")


@pytest.mark.asyncio
async def test_submit_order_definite_failure_raises_order_rejected():
    adapter, iface = _make_adapter()
    iface.submit_order = AsyncMock(return_value=None)  # interface signals definite failure

    with pytest.raises(OrderRejected):
        await adapter.submit_order(_sample_request())


@pytest.mark.asyncio
async def test_submit_order_indeterminate_propagates():
    adapter, iface = _make_adapter()
    iface.submit_order = AsyncMock(
        side_effect=IndeterminateOrderError("submit_order", "timeout", order_id=None)
    )

    with pytest.raises(IndeterminateOrderError):
        await adapter.submit_order(_sample_request())


# --------------------------------------------------------------------------- #
# cancel_order trichotomy
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cancel_order_success_returns_canonical_order():
    adapter, iface = _make_adapter()
    resp = SimpleNamespace(is_successful=True, order=_wire_order(order_state="cancelled"))
    iface.cancel_order = AsyncMock(return_value=resp)

    order = await adapter.cancel_order("ETH-123")
    assert order.order_id == "ETH-123"


@pytest.mark.asyncio
async def test_cancel_order_definite_failure_raises():
    adapter, iface = _make_adapter()
    iface.cancel_order = AsyncMock(return_value=None)

    with pytest.raises(OrderRejected):
        await adapter.cancel_order("ETH-123")


@pytest.mark.asyncio
async def test_cancel_order_indeterminate_propagates():
    adapter, iface = _make_adapter()
    # The interface raises IndeterminateOrderError on timeout/disconnect; the
    # adapter must propagate it, never collapse it into an OrderRejected.
    iface.cancel_order = AsyncMock(
        side_effect=IndeterminateOrderError("cancel_order", "timeout", order_id="ETH-123")
    )

    with pytest.raises(IndeterminateOrderError):
        await adapter.cancel_order("ETH-123")
