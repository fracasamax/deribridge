"""Tests for DeribitMapper: Deribit wire JSON -> canonical models."""
from decimal import Decimal

import pytest

from deribridge.core.enums import AssetKind, OptionType
from deribridge.exchanges.deribit.mapper import DeribitMapper
from deribridge.exchanges.deribit.symbols import parse_symbol

MAPPER = DeribitMapper()


def test_ticker_maps_to_canonical_with_decimal_prices(load_json):
    raw = load_json("deribit/ticker.json")
    sym = parse_symbol(raw["instrument_name"])
    t = MAPPER.ticker(raw, sym)

    assert t.symbol.canonical == "BTC/USD:perpetual"
    assert t.mark_price == Decimal("35000.25")
    assert isinstance(t.mark_price, Decimal)
    assert t.best_bid == Decimal("35000.0")
    assert t.funding_rate == 0.0001  # analytics stays float
    assert t.stats.volume_quote == Decimal("35000000.0")
    assert t.x("instrument_name") == "BTC-PERPETUAL"  # raw passthrough


def test_order_book_maps_levels_and_helpers(load_json):
    raw = load_json("deribit/order_book.json")
    sym = parse_symbol(raw["instrument_name"])
    ob = MAPPER.order_book(raw, sym)

    assert ob.best_bid.price == Decimal("35000.0")
    assert ob.best_ask.price == Decimal("35001.0")
    assert ob.spread == Decimal("1.0")
    assert ob.change_id == 123456
    assert ob.is_snapshot is True
    assert len(ob.bids) == 2 and len(ob.asks) == 2


def test_funding_rate_maps_current_funding_as_float(load_json):
    raw = load_json("deribit/ticker.json")
    sym = parse_symbol(raw["instrument_name"])
    fr = MAPPER.funding_rate(raw, sym)

    assert fr.symbol.canonical == "BTC/USD:perpetual"
    assert fr.rate == 0.0001
    assert isinstance(fr.rate, float)  # analytics stays float
    assert fr.timestamp is not None
    assert fr.x("instrument_name") == "BTC-PERPETUAL"  # raw passthrough


def test_funding_rate_raises_when_absent():
    # Deribit omits current_funding for non-perpetuals; the mapper must surface
    # that explicitly rather than fabricate a 0.0 rate.
    sym = parse_symbol("BTC-PERPETUAL")
    with pytest.raises(ValueError, match="current_funding"):
        MAPPER.funding_rate({"timestamp": 1700000000000}, sym)


def test_funding_rate_preserves_explicit_zero():
    # A genuine 0.0 funding rate is valid and must stay distinguishable from
    # "absent" (which raises).
    sym = parse_symbol("BTC-PERPETUAL")
    fr = MAPPER.funding_rate({"current_funding": 0.0, "timestamp": 1700000000000}, sym)
    assert fr.rate == 0.0


def test_account_single_currency_populates_portfolio_fields():
    raw = {
        "currency": "BTC",
        "equity": 1.5,
        "balance": 1.6,
        "available_funds": 1.2,
        "margin_balance": 1.55,
        "initial_margin": 0.1,
        "maintenance_margin": 0.05,
        "portfolio_margining_enabled": True,
    }
    acct = MAPPER.account(raw)

    assert acct.equity == Decimal("1.5")
    assert acct.margin_balance == Decimal("1.55")
    assert acct.initial_margin == Decimal("0.1")
    assert acct.maintenance_margin == Decimal("0.05")
    assert acct.portfolio_margin_enabled is True
    assert acct.balance_for("BTC").total == Decimal("1.5")


def test_account_multi_currency_extended_populates_top_level_aggregate():
    # Extended account_summaries: per-currency rows under "summaries", with the
    # cross-currency aggregate at the top level.
    raw = {
        "equity": 2.0,
        "margin_balance": 1.95,
        "initial_margin": 0.3,
        "maintenance_margin": 0.15,
        "portfolio_margining_enabled": True,
        "summaries": [
            {"currency": "BTC", "equity": 1.5, "available_funds": 1.2},
            {"currency": "ETH", "equity": 0.5, "available_funds": 0.4},
        ],
    }
    acct = MAPPER.account(raw)

    # portfolio-level fields no longer dropped for multi-currency summaries
    assert acct.equity == Decimal("2.0")
    assert acct.margin_balance == Decimal("1.95")
    assert acct.initial_margin == Decimal("0.3")
    assert acct.maintenance_margin == Decimal("0.15")
    assert acct.portfolio_margin_enabled is True
    assert {b.currency for b in acct.balances} == {"BTC", "ETH"}
    assert acct.balance_for("ETH").available == Decimal("0.4")


def test_instruments_map_kind_and_specs(load_json):
    raws = load_json("deribit/instruments.json")
    insts = [MAPPER.instrument(r) for r in raws]

    perp = insts[0]
    assert perp.symbol.kind == AssetKind.PERPETUAL
    assert perp.expires_at is None  # perpetuals do not expire
    assert perp.tick_size == Decimal("0.5")
    assert perp.contract_size == Decimal("10")

    opt = insts[1]
    assert opt.symbol.kind == AssetKind.OPTION
    assert opt.symbol.option_type == OptionType.CALL
    assert opt.symbol.strike == Decimal("60000")
    assert opt.expires_at is not None
