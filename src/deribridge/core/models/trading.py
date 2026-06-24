"""Canonical trading models: order requests (input) and orders (state)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import Field, model_validator

from ..enums import OrderState, OrderType, Side, TimeInForce
from .base import CanonicalModel, Money, OptMoney
from .symbol import Symbol


class OrderRequest(CanonicalModel):
    """A request to place an order. The caller-facing input model.

    Accepts a :class:`Symbol` or a raw venue string. ``extra`` carries
    venue-specific parameters straight through to the adapter.
    """

    symbol: Union[Symbol, str]
    side: Side
    type: OrderType = OrderType.LIMIT
    amount: OptMoney = None
    price: OptMoney = None
    time_in_force: TimeInForce = TimeInForce.GOOD_TIL_CANCELLED
    post_only: Optional[bool] = None
    reduce_only: Optional[bool] = None
    trigger_price: OptMoney = None
    label: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_invariants(self) -> "OrderRequest":
        if self.type.requires_price and self.price is None:
            raise ValueError(f"{self.type.value} orders require a price")
        if self.type.is_conditional and self.trigger_price is None:
            raise ValueError(f"{self.type.value} orders require a trigger_price")
        return self

    # Convenience constructors -------------------------------------------------
    @classmethod
    def market(cls, symbol: Union[Symbol, str], side: Side, amount: Decimal, **kw: Any) -> "OrderRequest":
        return cls(symbol=symbol, side=side, type=OrderType.MARKET, amount=amount, **kw)

    @classmethod
    def limit(
        cls, symbol: Union[Symbol, str], side: Side, amount: Decimal, price: Decimal, **kw: Any
    ) -> "OrderRequest":
        return cls(symbol=symbol, side=side, type=OrderType.LIMIT, amount=amount, price=price, **kw)


class Order(CanonicalModel):
    """The state of an order as reported by the exchange (output model)."""

    order_id: str
    symbol: Symbol
    side: Side
    type: OrderType
    state: OrderState
    amount: Money
    filled_amount: Money = Field(default=Decimal(0))
    price: OptMoney = None
    average_price: OptMoney = None
    time_in_force: Optional[TimeInForce] = None
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.filled_amount

    @property
    def fill_percentage(self) -> float:
        if self.amount == 0:
            return 0.0
        return float(self.filled_amount / self.amount) * 100.0

    @property
    def is_active(self) -> bool:
        return self.state.is_active
