"""Tests for the Order model and OrderType enum.

Covers two Tier 0/1 bugs:
- ``OrderType.limit`` (lowercase) was referenced — the member is ``OrderType.LIMIT``.
- the ``MARKET_TYPES``/``LIMIT_TYPES`` group sets were absorbed as enum members,
  so ``self in self.MARKET_TYPES`` did str-substring matching and
  ``OrderType.LIMIT.is_market()`` wrongly returned True.
"""
import pytest

from deribridge.classes.order import Order, OrderType, TimeInForce
from deribridge.classes.order_purpose import OrderPurpose


def test_ordertype_members_are_uppercase():
    assert OrderType.LIMIT.value == "limit"
    assert OrderType.MARKET.value == "market"
    assert not hasattr(OrderType, "limit")


def test_ordertype_has_only_real_members():
    # The group sets must NOT appear as members any more.
    names = {m.name for m in OrderType}
    assert "MARKET_TYPES" not in names
    assert "LIMIT_TYPES" not in names
    assert "CONDITIONAL_TYPES" not in names
    assert OrderType.LIMIT in list(OrderType)


@pytest.mark.parametrize(
    "member,is_market,is_limit,is_conditional",
    [
        (OrderType.LIMIT, False, True, False),
        (OrderType.MARKET, True, False, False),
        (OrderType.STOP_LIMIT, False, True, True),
        (OrderType.STOP_MARKET, True, False, True),
        (OrderType.MARKET_LIMIT, True, False, False),
        (OrderType.TRAILING_STOP, False, False, True),
    ],
)
def test_ordertype_classification(member, is_market, is_limit, is_conditional):
    assert member.is_market() is is_market
    assert member.is_limit() is is_limit
    assert member.is_conditional() is is_conditional


def test_timeinforce_aliases_removed():
    # GTC/FOK/IOC shorthand was unused and polluted the enum.
    assert not hasattr(TimeInForce, "GTC")
    assert TimeInForce.GOOD_TIL_CANCELLED.value == "good_til_cancelled"


def test_orderpurpose_aliases_removed():
    assert not hasattr(OrderPurpose, "LONG")
    assert {m.name for m in OrderPurpose} == {"BUY", "SELL"}


def test_order_uses_order_type_keyword():
    order = Order(
        instrument_name="BTC-PERPETUAL",
        purpose=OrderPurpose.BUY,
        amount=1.0,
        order_type=OrderType.LIMIT,
        price=50000.0,
    )
    assert order.order_type == OrderType.LIMIT


def test_order_ignores_unknown_type_keyword():
    # Pydantic ignores extras by default, so the old ``Order(type=...)`` call
    # silently dropped the order type and fell back to the LIMIT default — a
    # silent bug. Document the behaviour so the correct ``order_type=`` is used.
    order = Order(
        instrument_name="BTC-PERPETUAL",
        purpose=OrderPurpose.BUY,
        amount=1.0,
        type=OrderType.MARKET,  # ignored
        price=50000.0,
    )
    assert order.order_type == OrderType.LIMIT  # default, NOT MARKET


def test_limit_order_requires_price():
    with pytest.raises(Exception):
        Order(
            instrument_name="BTC-PERPETUAL",
            purpose=OrderPurpose.BUY,
            amount=1.0,
            order_type=OrderType.LIMIT,
        )
