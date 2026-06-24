"""Tests for BinanceMapper: Binance wire JSON -> canonical models.

Pure mapper tests — no httpx/websockets required.
"""
from decimal import Decimal

from deribridge.core.enums import AssetKind, Interval
from deribridge.exchanges.binance.mapper import BinanceMapper
from deribridge.exchanges.binance.symbols import parse_symbol

MAPPER = BinanceMapper()


def test_string_prices_become_exact_decimals(load_json):
    raw = load_json("binance/depth.json")
    ob = MAPPER.order_book(raw, parse_symbol("BTCUSDT"))
    assert ob.best_bid.price == Decimal("35000.00")
    assert isinstance(ob.best_bid.price, Decimal)
    assert ob.best_ask.amount == Decimal("0.80000000")
    assert ob.change_id == 123456789


def test_instrument_uses_authoritative_base_quote(load_json):
    info = load_json("binance/exchange_info.json")["symbols"][0]
    inst = MAPPER.instrument(info)
    assert inst.symbol.base == "BTC" and inst.symbol.quote == "USDT"
    assert inst.symbol.kind == AssetKind.SPOT
    assert inst.symbol.canonical == "BTC/USDT:spot"
    assert inst.tick_size == Decimal("0.01000000")
    assert inst.amount_step == Decimal("0.00001000")
    assert inst.is_active is True


def test_ticker_merges_book_and_24hr(load_json):
    merged = {**load_json("binance/ticker_24hr.json"), **load_json("binance/book_ticker.json")}
    t = MAPPER.ticker(merged, parse_symbol("BTCUSDT"))
    assert t.best_bid == Decimal("35000.00")
    assert t.best_ask == Decimal("35001.00")
    assert t.last == Decimal("35000.50")
    assert t.stats.volume_quote == Decimal("35000000.00000000")
    assert t.mark_price is None  # spot has no mark price


def test_ticker_handles_ws_stream_shape():
    ws_payload = {"s": "BTCUSDT", "b": "35000.0", "B": "1.5", "a": "35001.0", "A": "0.8"}
    t = MAPPER.ticker(ws_payload, parse_symbol("BTCUSDT"))
    assert t.best_bid == Decimal("35000.0")
    assert t.best_ask == Decimal("35001.0")


def test_candles_map_ohlcv(load_json):
    rows = load_json("binance/klines.json")
    candles = [MAPPER.candle(r, parse_symbol("BTCUSDT"), Interval.ONE_MINUTE) for r in rows]
    assert candles[0].open == Decimal("35000.0")
    assert candles[0].close == Decimal("35050.0")
    assert candles[0].interval == Interval.ONE_MINUTE


def test_symbol_quote_suffix_heuristic():
    assert parse_symbol("ETHBTC").quote == "BTC"
    assert parse_symbol("BTCFDUSD").quote == "FDUSD"  # longest-match wins over USD
    assert parse_symbol("BTCUSDT").base == "BTC"
