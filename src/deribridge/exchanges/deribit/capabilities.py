"""Declared capabilities of the Deribit adapter."""
from __future__ import annotations

from ...core.capabilities import Capabilities
from ...core.enums import AssetKind, OrderType, TimeInForce

DERIBIT_CAPABILITIES = Capabilities(
    asset_kinds=frozenset(
        {
            AssetKind.OPTION.value,
            AssetKind.FUTURE.value,
            AssetKind.PERPETUAL.value,
            AssetKind.SPOT.value,
            AssetKind.INDEX.value,
        }
    ),
    has_rest=False,
    has_websocket=True,
    trading=True,
    options=True,
    funding_rate=True,
    portfolio_margin=True,
    candles=False,
    greeks=True,
    positions=True,
    user_data_stream=True,
    # No canonical replace/amend method exists on ExchangeAdapter, so the
    # framework cannot expose it — declaring it would be dishonest.
    replace_order=False,
    order_types=frozenset(
        {
            OrderType.LIMIT,
            OrderType.MARKET,
            OrderType.STOP_LIMIT,
            OrderType.STOP_MARKET,
            OrderType.TAKE_LIMIT,
            OrderType.TAKE_MARKET,
            OrderType.TRAILING_STOP,
        }
    ),
    time_in_force=frozenset(
        {
            TimeInForce.GOOD_TIL_CANCELLED,
            TimeInForce.GOOD_TIL_DAY,
            TimeInForce.FILL_OR_KILL,
            TimeInForce.IMMEDIATE_OR_CANCEL,
        }
    ),
    rate_limit_per_second=10,
)
