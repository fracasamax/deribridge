"""Map Deribit wire JSON to canonical models.

The mapper is the only place Deribit's field names and shapes touch the
canonical layer. Everything here is pure (dict in, canonical model out), which
makes it trivially testable against recorded payloads.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from ...core._util import ms_to_dt, now_utc, opt_decimal, to_decimal
from ...core.enums import AssetKind, OrderState, OrderType, Side, TimeInForce
from ...core.models import (
    AccountSummary,
    Balance,
    FundingRate,
    Greeks,
    Instrument,
    Order,
    OrderBook,
    OrderBookLevel,
    Position,
    Stats,
    Symbol,
    Ticker,
)
from .symbols import parse_symbol

_ORDER_TYPE = {
    "limit": OrderType.LIMIT,
    "market": OrderType.MARKET,
    "stop_limit": OrderType.STOP_LIMIT,
    "stop_market": OrderType.STOP_MARKET,
    "take_limit": OrderType.TAKE_LIMIT,
    "take_market": OrderType.TAKE_MARKET,
    "trailing_stop": OrderType.TRAILING_STOP,
    "market_limit": OrderType.MARKET,
}
_ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "rejected": OrderState.REJECTED,
    "cancelled": OrderState.CANCELLED,
    "untriggered": OrderState.UNTRIGGERED,
}


def _maybe_decimal(value: Any) -> Optional[Decimal]:
    """Coerce to Decimal, but tolerate Deribit's non-numeric price sentinels
    (e.g. ``"market_price"``) by returning ``None``."""
    if value is None:
        return None
    try:
        return to_decimal(value)
    except (ValueError, InvalidOperation):
        return None


class DeribitMapper:
    """Wire JSON -> canonical models for Deribit."""

    def parse_symbol(self, raw: str) -> Symbol:
        return parse_symbol(raw)

    # -- market data -------------------------------------------------------- #
    def stats(self, raw: Optional[dict[str, Any]]) -> Optional[Stats]:
        if not raw:
            return None
        return Stats(
            high=opt_decimal(raw.get("high")),
            low=opt_decimal(raw.get("low")),
            volume=opt_decimal(raw.get("volume")),
            volume_quote=opt_decimal(raw.get("volume_usd")),
            price_change=raw.get("price_change"),
            raw=raw,
        )

    def greeks(self, raw: Optional[dict[str, Any]], iv: Optional[float] = None) -> Optional[Greeks]:
        if not raw:
            return None
        return Greeks(
            delta=raw.get("delta", 0.0),
            gamma=raw.get("gamma", 0.0),
            vega=raw.get("vega", 0.0),
            theta=raw.get("theta", 0.0),
            rho=raw.get("rho"),
            iv=iv,
            raw=raw,
        )

    def order_book(self, raw: dict[str, Any], symbol: Symbol) -> OrderBook:
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=p, amount=a) for p, a in raw.get("bids", [])],
            asks=[OrderBookLevel(price=p, amount=a) for p, a in raw.get("asks", [])],
            timestamp=ms_to_dt(raw.get("timestamp")) or now_utc(),
            change_id=raw.get("change_id"),
            is_snapshot=raw.get("type", "snapshot") != "change",
            raw=raw,
        )

    def ticker(self, raw: dict[str, Any], symbol: Symbol) -> Ticker:
        return Ticker(
            symbol=symbol,
            timestamp=ms_to_dt(raw.get("timestamp")) or now_utc(),
            last=opt_decimal(raw.get("last_price")),
            best_bid=opt_decimal(raw.get("best_bid_price")),
            best_bid_amount=opt_decimal(raw.get("best_bid_amount")),
            best_ask=opt_decimal(raw.get("best_ask_price")),
            best_ask_amount=opt_decimal(raw.get("best_ask_amount")),
            mark_price=opt_decimal(raw.get("mark_price")),
            index_price=opt_decimal(raw.get("index_price")),
            open_interest=opt_decimal(raw.get("open_interest")),
            funding_rate=raw.get("current_funding"),
            stats=self.stats(raw.get("stats")),
            greeks=self.greeks(raw.get("greeks"), iv=raw.get("mark_iv")),
            state=raw.get("state"),
            raw=raw,
        )

    def instrument(self, raw: dict[str, Any]) -> Instrument:
        symbol = parse_symbol(raw["instrument_name"])
        expires = raw.get("expiration_timestamp")
        return Instrument(
            symbol=symbol,
            is_active=raw.get("is_active", True),
            contract_size=to_decimal(raw.get("contract_size", 1)),
            tick_size=opt_decimal(raw.get("tick_size")),
            min_amount=opt_decimal(raw.get("min_trade_amount")),
            maker_fee=opt_decimal(raw.get("maker_commission")),
            taker_fee=opt_decimal(raw.get("taker_commission")),
            max_leverage=opt_decimal(raw.get("max_leverage")),
            settlement=raw.get("settlement_period"),
            created_at=ms_to_dt(raw.get("creation_timestamp")),
            expires_at=(
                ms_to_dt(expires)
                if expires and symbol.kind in (AssetKind.FUTURE, AssetKind.OPTION)
                else None
            ),
            raw=raw,
        )

    def funding_rate(self, raw: dict[str, Any], symbol: Symbol) -> FundingRate:
        """Map a Deribit ticker payload to a canonical point-in-time funding rate.

        Deribit exposes the current funding as the ``current_funding`` field
        (a float fraction) on the public/ticker result, timestamped by the
        ticker's ``timestamp`` (epoch ms). The rate stays a float (analytics).

        Raises:
            ValueError: if the payload carries no ``current_funding``. Deribit
                reports it only for perpetuals, so a missing field means funding
                does not apply to this instrument — surfaced explicitly rather
                than fabricated as ``0.0`` (which is a valid rate in its own
                right and must stay distinguishable from "absent").
        """
        current = raw.get("current_funding")
        if current is None:
            raise ValueError(
                f"no funding rate for {symbol.raw!r}: Deribit reports "
                "current_funding only for perpetual instruments"
            )
        return FundingRate(
            symbol=symbol,
            rate=float(current),
            timestamp=ms_to_dt(raw.get("timestamp")) or now_utc(),
            raw=raw,
        )

    # -- account / positions ----------------------------------------------- #
    def position(self, raw: dict[str, Any]) -> Position:
        greeks = None
        if raw.get("delta") is not None:
            greeks = Greeks(
                delta=raw.get("delta", 0.0),
                gamma=raw.get("gamma", 0.0) or 0.0,
                vega=raw.get("vega", 0.0) or 0.0,
                theta=raw.get("theta", 0.0) or 0.0,
            )
        return Position(
            symbol=parse_symbol(raw["instrument_name"]),
            side=Side.from_str(raw.get("direction", "buy")),
            size=to_decimal(abs(raw.get("size", 0.0))),
            average_price=to_decimal(raw.get("average_price", 0.0)),
            mark_price=opt_decimal(raw.get("mark_price")),
            liquidation_price=opt_decimal(raw.get("estimated_liquidation_price")),
            unrealized_pnl=opt_decimal(raw.get("floating_profit_loss")),
            realized_pnl=opt_decimal(raw.get("realized_profit_loss")),
            leverage=opt_decimal(raw.get("leverage")),
            initial_margin=opt_decimal(raw.get("initial_margin")),
            maintenance_margin=opt_decimal(raw.get("maintenance_margin")),
            greeks=greeks,
            raw=raw,
        )

    def account(self, raw: dict[str, Any]) -> AccountSummary:
        """Map a Deribit account-summary payload to a canonical account summary.

        Per-currency ``balances`` always come from the ``summaries`` list (or
        the top-level payload itself when ``summaries`` is absent, i.e. a
        single-currency non-extended summary).

        Portfolio-level fields (``equity``/``margin_balance``/``initial_margin``/
        ``maintenance_margin``) are read from the *top-level* payload, which is
        where Deribit places the cross-currency aggregate in an extended,
        multi-currency ``get_account_summaries`` response. For a single-currency
        summary the same fields live at the top level too, so the single-summary
        behavior is preserved without special-casing ``len(summaries) == 1``.
        """
        summaries = raw.get("summaries") or [raw]
        balances = [
            Balance(
                currency=s.get("currency", ""),
                total=to_decimal(s.get("equity", s.get("balance", 0.0))),
                available=to_decimal(s.get("available_funds", 0.0)),
                raw=s,
            )
            for s in summaries
            if s.get("currency")
        ]
        first = summaries[0] if summaries else {}
        return AccountSummary(
            balances=balances,
            equity=opt_decimal(raw.get("equity")),
            margin_balance=opt_decimal(raw.get("margin_balance")),
            initial_margin=opt_decimal(raw.get("initial_margin")),
            maintenance_margin=opt_decimal(raw.get("maintenance_margin")),
            portfolio_margin_enabled=raw.get(
                "portfolio_margining_enabled", first.get("portfolio_margining_enabled")
            ),
            raw=raw,
        )

    # -- orders ------------------------------------------------------------- #
    def order(self, raw: dict[str, Any]) -> Order:
        tif_value = raw.get("time_in_force")
        try:
            tif = TimeInForce(tif_value) if tif_value else None
        except ValueError:
            tif = None
        return Order(
            order_id=str(raw.get("order_id", "")),
            symbol=parse_symbol(raw["instrument_name"]),
            side=Side.from_str(raw.get("direction", "buy")),
            type=_ORDER_TYPE.get(raw.get("order_type", "limit"), OrderType.LIMIT),
            state=_ORDER_STATE.get(raw.get("order_state", "open"), OrderState.OPEN),
            amount=to_decimal(raw.get("amount", 0.0)),
            filled_amount=to_decimal(raw.get("filled_amount", 0.0) or 0.0),
            price=_maybe_decimal(raw.get("price")),
            average_price=_maybe_decimal(raw.get("average_price")),
            time_in_force=tif,
            label=raw.get("label") or None,
            created_at=ms_to_dt(raw.get("creation_timestamp")),
            updated_at=ms_to_dt(raw.get("last_update_timestamp")),
            raw=raw,
        )
