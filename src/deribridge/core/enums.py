"""Canonical, exchange-agnostic enumerations.

These are the single source of truth across the framework. Adapters map their
venue-specific strings onto these in their mapper layer. Values are stable,
lowercase, cross-venue tokens — they are NOT guaranteed to equal any single
exchange's wire strings.
"""
from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    """Order / trade / position direction."""

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        """+1 for BUY, -1 for SELL (handy for signed position math)."""
        return 1 if self is Side.BUY else -1

    @classmethod
    def from_str(cls, value: str) -> "Side":
        """Parse common venue spellings (buy/sell, bid/ask, long/short)."""
        v = value.strip().lower()
        if v in ("buy", "bid", "long", "b"):
            return cls.BUY
        if v in ("sell", "ask", "short", "s"):
            return cls.SELL
        raise ValueError(f"cannot parse Side from {value!r}")


class AssetKind(str, Enum):
    """Instrument category. Distinguishes perpetuals from dated futures, which
    Deribit's original ``InstrumentType`` conflated under ``future``."""

    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"
    INDEX = "index"

    @property
    def is_derivative(self) -> bool:
        return self is not AssetKind.SPOT


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

    @classmethod
    def from_str(cls, value: str) -> "OptionType":
        v = value.strip().lower()
        if v in ("call", "c"):
            return cls.CALL
        if v in ("put", "p"):
            return cls.PUT
        raise ValueError(f"cannot parse OptionType from {value!r}")


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"
    TAKE_LIMIT = "take_limit"
    TAKE_MARKET = "take_market"
    TRAILING_STOP = "trailing_stop"

    @property
    def is_market(self) -> bool:
        return self in (OrderType.MARKET, OrderType.STOP_MARKET, OrderType.TAKE_MARKET)

    @property
    def requires_price(self) -> bool:
        return self in (OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_LIMIT)

    @property
    def is_conditional(self) -> bool:
        return self in (
            OrderType.STOP_LIMIT,
            OrderType.STOP_MARKET,
            OrderType.TAKE_LIMIT,
            OrderType.TAKE_MARKET,
            OrderType.TRAILING_STOP,
        )


class OrderState(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNTRIGGERED = "untriggered"
    PARTIALLY_FILLED = "partially_filled"

    @property
    def is_active(self) -> bool:
        return self in (OrderState.OPEN, OrderState.UNTRIGGERED, OrderState.PARTIALLY_FILLED)

    @property
    def is_terminal(self) -> bool:
        return self in (OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED)


class TimeInForce(str, Enum):
    GOOD_TIL_CANCELLED = "good_til_cancelled"
    GOOD_TIL_DAY = "good_til_day"
    FILL_OR_KILL = "fill_or_kill"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"


class Interval(str, Enum):
    """Candle / kline intervals (cross-venue tokens)."""

    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
