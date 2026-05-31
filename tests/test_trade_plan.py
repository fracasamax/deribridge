"""Regression tests for TradePlanItem rounding and order construction.

These cover the Tier 0 bugs where:
- a mangled ``@staticmethod`` turned ``round_price`` / ``set_computed_fields``
  into a ``self @ staticmethod`` expression that raised at runtime, and
- ``to_order`` built ``Order(type=...)`` with a non-existent keyword.
"""
import inspect

import pytest

from deribridge.classes.trade_plan import TradePlanItem
from deribridge.classes.order import OrderType
from deribridge.classes.order_purpose import OrderPurpose


def test_round_price_is_staticmethod():
    # The decorator was previously destroyed; guard it stays a staticmethod.
    assert isinstance(
        inspect.getattr_static(TradePlanItem, "round_price"), staticmethod
    )


def test_round_price_floors_for_buy():
    # Buys floor to stay at or below the limit.
    assert TradePlanItem.round_price(
        price=100.3, purpose=OrderPurpose.BUY, tick_size=0.5
    ) == pytest.approx(100.0)


def test_round_price_ceils_for_sell():
    # Sells ceil to stay at or above the limit.
    assert TradePlanItem.round_price(
        price=100.3, purpose=OrderPurpose.SELL, tick_size=0.5
    ) == pytest.approx(100.5)


def test_round_price_rejects_unknown_purpose():
    with pytest.raises(ValueError):
        TradePlanItem.round_price(price=100.0, purpose=None, tick_size=0.5)


def test_to_order_builds_valid_limit_order():
    # Previously raised on every call (mangled decorator + Order(type=...)).
    item = TradePlanItem(instrument="BTC-PERPETUAL", amount=1.0, avg_price=50000.3)
    order = item.to_order()
    assert order.order_type == OrderType.LIMIT
    assert order.purpose == OrderPurpose.BUY
    assert order.amount == pytest.approx(1.0)
    # Future tick size is 0.5 → floored for a buy.
    assert order.price == pytest.approx(50000.0)


def test_to_order_sell_ceils_price():
    item = TradePlanItem(instrument="BTC-PERPETUAL", amount=-1.0, avg_price=50000.3)
    order = item.to_order()
    assert order.purpose == OrderPurpose.SELL
    assert order.amount == pytest.approx(1.0)  # abs() applied
    assert order.price == pytest.approx(50000.5)
