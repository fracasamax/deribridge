"""Canonical account & instrument-spec models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from ..enums import Side
from .base import CanonicalModel, Money, OptMoney
from .market import Greeks
from .symbol import Symbol


class Balance(CanonicalModel):
    """Per-currency balance — the spot/cash primitive."""

    currency: str
    total: Money
    available: Money
    reserved: OptMoney = None


class AccountSummary(CanonicalModel):
    """Account-level summary. Derivative venues populate the margin/PnL fields;
    spot venues may only populate ``balances``."""

    balances: list[Balance] = Field(default_factory=list)
    equity: OptMoney = None
    margin_balance: OptMoney = None
    initial_margin: OptMoney = None
    maintenance_margin: OptMoney = None
    total_unrealized_pnl: OptMoney = None
    portfolio_margin_enabled: Optional[bool] = None

    def balance_for(self, currency: str) -> Optional[Balance]:
        for b in self.balances:
            if b.currency.upper() == currency.upper():
                return b
        return None


class Position(CanonicalModel):
    symbol: Symbol
    side: Side
    size: Money  # absolute size; sign conveyed by ``side``
    average_price: Money
    mark_price: OptMoney = None
    liquidation_price: OptMoney = None
    unrealized_pnl: OptMoney = None
    realized_pnl: OptMoney = None
    leverage: OptMoney = None
    initial_margin: OptMoney = None
    maintenance_margin: OptMoney = None
    greeks: Optional[Greeks] = None  # options positions

    @property
    def signed_size(self) -> Decimal:
        return self.size * self.side.sign


class Instrument(CanonicalModel):
    """Contract specification / instrument metadata for one tradeable symbol."""

    symbol: Symbol
    is_active: bool = True
    contract_size: Money = Field(default=Decimal(1))
    tick_size: OptMoney = None
    min_amount: OptMoney = None
    amount_step: OptMoney = None
    maker_fee: OptMoney = None
    taker_fee: OptMoney = None
    max_leverage: OptMoney = None
    settlement: Optional[str] = None  # "linear" / "inverse" / None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
