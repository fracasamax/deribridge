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


def test_to_order_zero_amount_raises():
    # A zero-amount item has purpose=None; calling to_order() must raise rather
    # than silently passing None to Order (which would fail in round_price or
    # produce an invalid order).  This guards the fix added in trade_plan.py.
    item = TradePlanItem(instrument="BTC-PERPETUAL", amount=0.0, avg_price=50000.0)
    assert item.purpose is None
    with pytest.raises(ValueError, match="zero-amount"):
        item.to_order()


def test_from_csv_strict_raises_on_bad_row(tmp_path):
    import pytest
    from deribridge.classes.trade_plan import TradePlan

    p = tmp_path / "plan.csv"
    p.write_text("Instrument,Amount\nBTC-PERPETUAL,notanumber\n")
    with pytest.raises(ValueError):
        TradePlan.from_csv(str(p), strict=True)


def test_from_csv_nonstrict_collects_errors(tmp_path):
    from deribridge.classes.trade_plan import TradePlan

    p = tmp_path / "plan.csv"
    p.write_text("Instrument,Amount\nBTC-PERPETUAL,notanumber\n")
    plan = TradePlan.from_csv(str(p))
    assert plan is not None
    assert plan.errors and plan.errors[0]["row"] == 1
