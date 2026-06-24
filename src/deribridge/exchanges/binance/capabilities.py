"""Declared capabilities of the (reference) Binance adapter.

This adapter is a worked example proving the abstraction across a REST + WS
venue. It implements the public market-data surface; private trading and
account endpoints are intentionally out of scope and excluded from the
capability set (so the conformance suite does not require them).
"""
from __future__ import annotations

from ...core.capabilities import Capabilities
from ...core.enums import AssetKind, OrderType, TimeInForce

BINANCE_CAPABILITIES = Capabilities(
    asset_kinds=frozenset({AssetKind.SPOT.value}),
    has_rest=True,
    has_websocket=True,
    trading=False,  # private trading not implemented in this reference adapter
    options=False,
    funding_rate=False,
    portfolio_margin=False,
    candles=True,
    greeks=False,
    positions=False,
    user_data_stream=False,
    replace_order=False,
    order_types=frozenset({OrderType.LIMIT, OrderType.MARKET}),
    time_in_force=frozenset(
        {
            TimeInForce.GOOD_TIL_CANCELLED,
            TimeInForce.FILL_OR_KILL,
            TimeInForce.IMMEDIATE_OR_CANCEL,
        }
    ),
    max_order_book_depth=5000,
    rate_limit_per_second=20,
)
