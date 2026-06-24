"""Unit tests for the canonical error taxonomy, enums, and capabilities."""
import pytest

from deribridge.core.capabilities import Capabilities
from deribridge.core.enums import AssetKind, OptionType, OrderType, Side
from deribridge.core.errors import (
    ExchangeError,
    IndeterminateOrderError,
    MissingExchangeExtra,
    OrderRejected,
    UnsupportedOperation,
)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
def test_side_helpers():
    assert Side.BUY.opposite is Side.SELL
    assert Side.SELL.sign == -1
    assert Side.from_str("BID") is Side.BUY
    assert Side.from_str("short") is Side.SELL
    with pytest.raises(ValueError):
        Side.from_str("sideways")


def test_asset_kind_derivative_flag():
    assert AssetKind.SPOT.is_derivative is False
    assert AssetKind.PERPETUAL.is_derivative is True
    # perpetual and future are distinct (the original InstrumentType conflated them)
    assert AssetKind.PERPETUAL is not AssetKind.FUTURE


def test_option_type_parsing():
    assert OptionType.from_str("C") is OptionType.CALL
    assert OptionType.from_str("put") is OptionType.PUT


def test_order_type_semantics():
    assert OrderType.MARKET.is_market is True
    assert OrderType.LIMIT.requires_price is True
    assert OrderType.STOP_MARKET.is_conditional is True


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
def test_missing_extra_is_importerror_with_actionable_message():
    err = MissingExchangeExtra("binance", "binance", missing="httpx")
    assert isinstance(err, ImportError)  # callers catching ImportError keep working
    assert isinstance(err, ExchangeError)
    assert "pip install 'deribridge[binance]'" in str(err)


def test_unsupported_operation_is_notimplemented():
    err = UnsupportedOperation("binance", "get_positions")
    assert isinstance(err, NotImplementedError)
    assert "get_positions" in str(err)


def test_indeterminate_error_signature_is_backward_compatible():
    # Positional (operation, message) — as the original Deribit code used.
    e1 = IndeterminateOrderError("submit_order", "boom", order_id=None)
    assert e1.operation == "submit_order" and e1.order_id is None
    # Keyword form also used in the codebase.
    e2 = IndeterminateOrderError(operation="close_position", message="x")
    assert e2.operation == "close_position"


def test_order_rejected_carries_context():
    err = OrderRejected("submit_order", "rejected", order_id="o1", code=10004)
    assert err.order_id == "o1" and err.code == 10004


# --------------------------------------------------------------------------- #
# Capabilities
# --------------------------------------------------------------------------- #
def test_capabilities_is_frozen_and_introspectable():
    caps = Capabilities(
        asset_kinds=frozenset({"spot"}),
        has_rest=True,
        trading=False,
        order_types=frozenset({OrderType.LIMIT, OrderType.MARKET}),
    )
    assert caps.supports("has_rest") is True
    assert caps.supports("trading") is False
    assert caps.supports("nonexistent") is False
    with pytest.raises(Exception):
        caps.has_rest = False  # type: ignore[misc]
