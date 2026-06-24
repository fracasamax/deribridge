"""Canonical market-data models: order books, tickers, trades, candles."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, model_validator

from ..enums import Interval, Side
from .base import CanonicalModel, Money, OptMoney
from .symbol import Symbol


class OrderBookLevel(CanonicalModel):
    price: Money
    amount: Money


class Stats(CanonicalModel):
    """24h rolling statistics."""

    high: OptMoney = None
    low: OptMoney = None
    volume: OptMoney = None
    volume_quote: OptMoney = None  # volume in quote currency (was volume_usd)
    price_change: Optional[float] = None  # percent change — analytics, float


class Greeks(CanonicalModel):
    """Option sensitivities. Analytics values — float, not Decimal."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: Optional[float] = None
    iv: Optional[float] = None  # mark implied volatility, if provided


class OrderBook(CanonicalModel):
    """A canonical order book snapshot (or delta).

    Canonical ordering invariant: ``bids`` are sorted descending by price and
    ``asks`` ascending by price, so ``best_bid``/``best_ask`` are always the
    first element of each side and ``mid``/``spread`` are well-defined. Both
    built-in mappers already emit sorted levels; a defensive ``@model_validator``
    re-normalizes ordering so an adapter passing unsorted levels cannot silently
    corrupt the top of book.
    """

    symbol: Symbol
    bids: list[OrderBookLevel] = Field(default_factory=list)  # sorted desc by price
    asks: list[OrderBookLevel] = Field(default_factory=list)  # sorted asc by price
    timestamp: datetime
    change_id: Optional[int] = None  # venue sequence id (delta-applying venues)
    is_snapshot: bool = True

    @model_validator(mode="after")
    def _normalize_ordering(self) -> OrderBook:
        """Enforce the canonical ordering invariant defensively.

        A no-op for already-sorted input. Only the list order changes; the
        ``OrderBookLevel`` instances themselves are never mutated.
        """
        self.bids.sort(key=lambda lvl: lvl.price, reverse=True)
        self.asks.sort(key=lambda lvl: lvl.price)
        return self

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    @property
    def mid(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None

    @property
    def spread(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None


class Ticker(CanonicalModel):
    symbol: Symbol
    timestamp: datetime
    last: OptMoney = None
    best_bid: OptMoney = None
    best_bid_amount: OptMoney = None
    best_ask: OptMoney = None
    best_ask_amount: OptMoney = None
    mark_price: OptMoney = None  # None on pure spot
    index_price: OptMoney = None
    open_interest: OptMoney = None  # derivatives only
    funding_rate: Optional[float] = None  # perpetuals only — analytics, float
    stats: Optional[Stats] = None
    greeks: Optional[Greeks] = None  # options only
    state: Optional[str] = None  # venue-defined ("open"/"closed"/...)

    @property
    def mid(self) -> Optional[Decimal]:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[Decimal]:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


class Trade(CanonicalModel):
    symbol: Symbol
    trade_id: str
    price: Money
    amount: Money
    side: Side
    timestamp: datetime
    liquidation: bool = False
    iv: Optional[float] = None  # options trades


class Candle(CanonicalModel):
    symbol: Symbol
    open_time: datetime
    open: Money
    high: Money
    low: Money
    close: Money
    volume: Money
    interval: Interval


class FundingRate(CanonicalModel):
    symbol: Symbol
    rate: float  # rate as a fraction — analytics, float
    timestamp: datetime
    next_funding_time: Optional[datetime] = None
    interval_hours: Optional[int] = None
