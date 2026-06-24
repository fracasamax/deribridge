"""Unit tests for the canonical (exchange-agnostic) data models."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from deribridge.core.enums import AssetKind, OptionType, OrderState, OrderType, Side
from deribridge.core.models import (
    Order,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
    Symbol,
    Ticker,
)


def _spot_symbol() -> Symbol:
    return Symbol(raw="BTCUSDT", base="BTC", quote="USDT", kind=AssetKind.SPOT, exchange="binance")


def _option_symbol() -> Symbol:
    return Symbol(
        raw="BTC-26DEC25-60000-C",
        base="BTC",
        quote="USD",
        kind=AssetKind.OPTION,
        exchange="deribit",
        expiry=datetime(2025, 12, 26, tzinfo=timezone.utc),
        strike=Decimal("60000"),
        option_type=OptionType.CALL,
    )


# --------------------------------------------------------------------------- #
# Decimal coercion
# --------------------------------------------------------------------------- #
def test_prices_coerce_to_exact_decimal_from_string():
    lvl = OrderBookLevel(price="0.00001234", amount="1.5")
    assert lvl.price == Decimal("0.00001234")
    assert isinstance(lvl.price, Decimal)


def test_prices_coerce_losslessly_from_float():
    lvl = OrderBookLevel(price=0.1, amount=3)
    assert lvl.price == Decimal("0.1")  # not 0.1000000000000000055...


# --------------------------------------------------------------------------- #
# Symbol
# --------------------------------------------------------------------------- #
def test_symbol_str_is_raw_venue_string():
    assert str(_spot_symbol()) == "BTCUSDT"


def test_symbol_canonical_keys_are_cross_venue():
    assert _spot_symbol().canonical == "BTC/USDT:spot"
    assert _option_symbol().canonical == "BTC/USD:option:2025-12-26:60000:call"


def test_symbol_is_frozen():
    sym = _spot_symbol()
    with pytest.raises(Exception):
        sym.base = "ETH"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# OrderBook helpers
# --------------------------------------------------------------------------- #
def test_order_book_best_mid_spread():
    ob = OrderBook(
        symbol=_spot_symbol(),
        bids=[OrderBookLevel(price="100", amount="1"), OrderBookLevel(price="99", amount="2")],
        asks=[OrderBookLevel(price="101", amount="1"), OrderBookLevel(price="102", amount="2")],
        timestamp=datetime.now(timezone.utc),
    )
    assert ob.best_bid.price == Decimal("100")
    assert ob.best_ask.price == Decimal("101")
    assert ob.mid == Decimal("100.5")
    assert ob.spread == Decimal("1")


def test_order_book_one_sided_returns_none_helpers():
    ob = OrderBook(symbol=_spot_symbol(), bids=[], asks=[], timestamp=datetime.now(timezone.utc))
    assert ob.best_bid is None and ob.best_ask is None
    assert ob.mid is None and ob.spread is None


def test_order_book_normalizes_unsorted_levels():
    """Defensive invariant: even if an adapter passes unsorted levels, bids are
    sorted descending and asks ascending so the top of book is always correct."""
    ob = OrderBook(
        symbol=_spot_symbol(),
        bids=[
            OrderBookLevel(price="98", amount="1"),
            OrderBookLevel(price="100", amount="2"),
            OrderBookLevel(price="99", amount="3"),
        ],
        asks=[
            OrderBookLevel(price="103", amount="1"),
            OrderBookLevel(price="101", amount="2"),
            OrderBookLevel(price="102", amount="3"),
        ],
        timestamp=datetime.now(timezone.utc),
    )
    assert ob.best_bid.price == Decimal("100")  # highest bid
    assert ob.best_ask.price == Decimal("101")  # lowest ask
    assert [lvl.price for lvl in ob.bids] == [Decimal("100"), Decimal("99"), Decimal("98")]
    assert [lvl.price for lvl in ob.asks] == [Decimal("101"), Decimal("102"), Decimal("103")]
    assert ob.spread == Decimal("1")
    assert ob.spread >= 0
    assert ob.mid == Decimal("100.5")


# --------------------------------------------------------------------------- #
# raw passthrough
# --------------------------------------------------------------------------- #
def test_raw_passthrough_accessor():
    t = Ticker(
        symbol=_spot_symbol(),
        timestamp=datetime.now(timezone.utc),
        raw={"combo_id": "abc", "weird_field": 7},
    )
    assert t.x("combo_id") == "abc"
    assert t.x("missing", default=42) == 42


# --------------------------------------------------------------------------- #
# OrderRequest validation
# --------------------------------------------------------------------------- #
def test_limit_order_requires_price():
    with pytest.raises(ValueError, match="require a price"):
        OrderRequest(symbol="BTCUSDT", side=Side.BUY, type=OrderType.LIMIT, amount=Decimal("1"))


def test_market_order_needs_no_price():
    req = OrderRequest.market("BTCUSDT", Side.SELL, Decimal("1"))
    assert req.type == OrderType.MARKET and req.price is None


def test_conditional_order_requires_trigger():
    with pytest.raises(ValueError, match="trigger_price"):
        OrderRequest(
            symbol="BTCUSDT",
            side=Side.BUY,
            type=OrderType.STOP_MARKET,
            amount=Decimal("1"),
        )


# --------------------------------------------------------------------------- #
# Order state math
# --------------------------------------------------------------------------- #
def test_order_remaining_and_fill_percentage():
    o = Order(
        order_id="x1",
        symbol=_spot_symbol(),
        side=Side.BUY,
        type=OrderType.LIMIT,
        state=OrderState.PARTIALLY_FILLED,
        amount="10",
        filled_amount="4",
        price="100",
    )
    assert o.remaining == Decimal("6")
    assert o.fill_percentage == pytest.approx(40.0)
    assert o.is_active is True
