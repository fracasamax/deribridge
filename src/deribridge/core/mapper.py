"""Mapper protocol + coercion helpers.

The mapper is the *only* place a venue's wire JSON touches canonical models. It
owns ``Decimal`` coercion, epoch-ms -> datetime, :class:`Symbol` construction,
enum normalization, and ``raw`` passthrough. Each adapter provides a concrete
mapper; this Protocol documents the surface and is structurally checkable.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ._util import ms_to_dt, now_utc, opt_decimal, to_decimal
from .models import (
    AccountSummary,
    Instrument,
    Order,
    OrderBook,
    Position,
    Symbol,
    Ticker,
    Trade,
)

__all__ = ["Mapper", "to_decimal", "opt_decimal", "ms_to_dt", "now_utc"]


@runtime_checkable
class Mapper(Protocol):
    """Wire JSON -> canonical model conversion for one exchange."""

    def parse_symbol(self, raw: str) -> Symbol: ...
    def order_book(self, raw: dict[str, Any], symbol: Symbol) -> OrderBook: ...
    def ticker(self, raw: dict[str, Any], symbol: Symbol) -> Ticker: ...
    def trade(self, raw: dict[str, Any], symbol: Symbol) -> Trade: ...
    def instrument(self, raw: dict[str, Any]) -> Instrument: ...
    def order(self, raw: dict[str, Any]) -> Order: ...
    def position(self, raw: dict[str, Any]) -> Position: ...
    def account(self, raw: dict[str, Any]) -> AccountSummary: ...
