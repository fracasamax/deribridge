"""Tests for DeribitMapper: Deribit wire JSON -> canonical models."""
from decimal import Decimal

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
