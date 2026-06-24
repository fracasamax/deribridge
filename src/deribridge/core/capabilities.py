"""Declarative capability descriptor for adapters.

Not every exchange supports options, funding, portfolio margin, or even both
transports. A frozen :class:`Capabilities` descriptor lets callers branch
*before* calling; :class:`~deribridge.core.errors.UnsupportedOperation` is the
runtime safety net for operations an adapter does not implement.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import OrderType, TimeInForce


class Capabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_kinds: frozenset[str] = Field(default_factory=frozenset)

    # transports
    has_rest: bool = False
    has_websocket: bool = False

    # features
    trading: bool = False
    options: bool = False
    funding_rate: bool = False
    portfolio_margin: bool = False
    candles: bool = False
    greeks: bool = False
    positions: bool = False
    user_data_stream: bool = False
    replace_order: bool = False

    # order semantics
    order_types: frozenset[OrderType] = Field(default_factory=frozenset)
    time_in_force: frozenset[TimeInForce] = Field(default_factory=frozenset)

    # hints
    max_order_book_depth: int | None = None
    rate_limit_per_second: int | None = None

    def supports(self, feature: str) -> bool:
        return bool(getattr(self, feature, False))
