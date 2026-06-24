"""Map Binance wire JSON to canonical models.

Binance returns prices/quantities as strings (precisely to avoid float
rounding) — coerced losslessly to ``Decimal``. REST snapshots carry no
timestamp, so they are stamped at receipt. The same canonical ``Ticker`` comes
out of either the REST ``bookTicker`` shape (``bidPrice``/``askPrice``) or the
WS stream shape (``b``/``a``), which is the abstraction doing its job across a
completely different wire format from Deribit's.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core._util import ms_to_dt, now_utc, opt_decimal, to_decimal
from ...core.enums import Interval
from ...core.models import (
    Candle,
    Instrument,
    OrderBook,
    OrderBookLevel,
    Stats,
    Symbol,
    Ticker,
)
from .symbols import parse_symbol, symbol_from_info


def _filter(info: dict[str, Any], filter_type: str) -> dict[str, Any]:
    for f in info.get("filters", []):
        if f.get("filterType") == filter_type:
            return f
    return {}


class BinanceMapper:
    """Wire JSON -> canonical models for Binance spot."""

    def parse_symbol(self, raw: str) -> Symbol:
        return parse_symbol(raw)

    def instrument(self, info: dict[str, Any]) -> Instrument:
        price_filter = _filter(info, "PRICE_FILTER")
        lot_filter = _filter(info, "LOT_SIZE")
        return Instrument(
            symbol=symbol_from_info(info),
            is_active=info.get("status") == "TRADING",
            tick_size=opt_decimal(price_filter.get("tickSize")),
            min_amount=opt_decimal(lot_filter.get("minQty")),
            amount_step=opt_decimal(lot_filter.get("stepSize")),
            settlement="linear",
            raw=info,
        )

    def order_book(self, raw: dict[str, Any], symbol: Symbol) -> OrderBook:
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=p, amount=q) for p, q in raw.get("bids", [])],
            asks=[OrderBookLevel(price=p, amount=q) for p, q in raw.get("asks", [])],
            timestamp=now_utc(),  # REST depth snapshot has no timestamp
            change_id=raw.get("lastUpdateId"),
            is_snapshot=True,
            raw=raw,
        )

    def ticker(self, raw: dict[str, Any], symbol: Symbol) -> Ticker:
        def pick(*keys: str) -> Optional[Any]:
            for k in keys:
                if raw.get(k) is not None:
                    return raw[k]
            return None

        stats = None
        if any(k in raw for k in ("highPrice", "lowPrice", "volume", "quoteVolume")):
            stats = Stats(
                high=opt_decimal(raw.get("highPrice")),
                low=opt_decimal(raw.get("lowPrice")),
                volume=opt_decimal(raw.get("volume")),
                volume_quote=opt_decimal(raw.get("quoteVolume")),
                price_change=(
                    float(raw["priceChangePercent"])
                    if raw.get("priceChangePercent") is not None
                    else None
                ),
                raw=raw,
            )
        event_ms = raw.get("E")
        return Ticker(
            symbol=symbol,
            timestamp=ms_to_dt(event_ms) or now_utc(),
            last=opt_decimal(pick("lastPrice", "c")),
            best_bid=opt_decimal(pick("bidPrice", "b")),
            best_bid_amount=opt_decimal(pick("bidQty", "B")),
            best_ask=opt_decimal(pick("askPrice", "a")),
            best_ask_amount=opt_decimal(pick("askQty", "A")),
            stats=stats,
            raw=raw,
        )

    def candle(self, row: list[Any], symbol: Symbol, interval: Interval) -> Candle:
        # Binance kline: [openTime, open, high, low, close, volume, closeTime, ...]
        return Candle(
            symbol=symbol,
            open_time=ms_to_dt(row[0]) or now_utc(),
            open=to_decimal(row[1]),
            high=to_decimal(row[2]),
            low=to_decimal(row[3]),
            close=to_decimal(row[4]),
            volume=to_decimal(row[5]),
            interval=interval,
            raw={"kline": row},
        )
