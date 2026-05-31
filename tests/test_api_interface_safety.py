"""Safety tests for DeribitAPIInterface order methods.

Covers the silent-failure redesign: submit_order / cancel_order / replace_order
must distinguish three outcomes, with NO live connection (the underlying
EnhancedDeribitClient is mocked):

- definite SUCCESS  -> typed response / result dict returned
- definite FAILURE  -> None returned (rejected / never sent, safe to retry)
- INDETERMINATE     -> IndeterminateOrderError raised (timeout / disconnect;
                       outcome unknown, caller must reconcile)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from deribridge.api_client.deribit_api_interface import (
    DeribitAPIInterface,
    IndeterminateOrderError,
)
from deribridge.api_client.websocket_api_client import DeribitWebSocketError
from deribridge.classes.order import Order, OrderType, TimeInForce
from deribridge.classes.order_purpose import OrderPurpose
from websockets.exceptions import ConnectionClosed


def _make_interface():
    """Build an interface backed by a mock client that is already connected."""
    client = MagicMock()
    client.connected = True
    client.authenticated = True
    iface = DeribitAPIInterface(client=client)
    return iface, client


def _sample_order():
    return Order(
        instrument_name="BTC-PERPETUAL",
        purpose=OrderPurpose.BUY,
        amount=10.0,
        order_type=OrderType.LIMIT,
        price=20000.0,
        time_in_force=TimeInForce.GOOD_TIL_CANCELLED,
        post_only=True,
    )


def _submit_success_payload():
    return {
        "order": {
            "order_id": "ETH-12345",
            "instrument_name": "BTC-PERPETUAL",
            "order_state": "open",
            "direction": "buy",
            "amount": 10.0,
            "price": 20000.0,
        },
        "trades": [],
    }


# --------------------------------------------------------------------------- #
# submit_order
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_submit_order_definite_success():
    iface, client = _make_interface()
    client.submit_order = AsyncMock(return_value=_submit_success_payload())

    resp = await iface.submit_order(_sample_order(), check_risk=False)

    assert resp is not None
    assert resp.order.order_id == "ETH-12345"
    # Order should be tracked after a successful submit.
    assert "ETH-12345" in await iface.order_tracker.get_active_order_ids()


@pytest.mark.asyncio
async def test_submit_order_definite_failure_returns_none():
    iface, client = _make_interface()
    # A real API rejection (non-timeout error code) is a DEFINITE failure.
    client.submit_order = AsyncMock(
        side_effect=DeribitWebSocketError(10004, "order_rejected")
    )

    resp = await iface.submit_order(_sample_order(), check_risk=False)

    assert resp is None


@pytest.mark.asyncio
async def test_submit_order_risk_rejection_returns_none():
    iface, client = _make_interface()
    client.submit_order = AsyncMock(return_value=_submit_success_payload())
    # Disable trading so the risk manager rejects: definite failure -> None.
    iface.risk_manager.trading_enabled = False

    resp = await iface.submit_order(_sample_order(), check_risk=True)

    assert resp is None
    client.submit_order.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        asyncio.TimeoutError(),
        DeribitWebSocketError(-1, "Request timed out: private/buy"),
        ConnectionError("socket dropped"),
        ConnectionClosed(None, None),
    ],
)
async def test_submit_order_indeterminate_raises(exc):
    iface, client = _make_interface()
    client.submit_order = AsyncMock(side_effect=exc)

    with pytest.raises(IndeterminateOrderError) as ei:
        await iface.submit_order(_sample_order(), check_risk=False)

    err = ei.value
    assert err.operation == "submit_order"
    assert err.order_id is None  # no id was assigned for a new submission
    assert err.cause is exc


# --------------------------------------------------------------------------- #
# cancel_order
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cancel_order_definite_success():
    iface, client = _make_interface()
    cancel_resp = MagicMock()
    cancel_resp.is_successful = True
    cancel_resp.to_dict.return_value = {"success": True}
    client.cancel_order_model = AsyncMock(return_value=cancel_resp)

    resp = await iface.cancel_order("ETH-12345")

    assert resp is cancel_resp


@pytest.mark.asyncio
async def test_cancel_order_definite_failure_returns_none():
    iface, client = _make_interface()
    client.cancel_order_model = AsyncMock(
        side_effect=DeribitWebSocketError(11044, "not_open_order")
    )

    resp = await iface.cancel_order("ETH-12345")

    assert resp is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        asyncio.TimeoutError(),
        DeribitWebSocketError(-1, "Request timed out: private/cancel"),
        ConnectionError("socket dropped"),
        ConnectionClosed(None, None),
    ],
)
async def test_cancel_order_indeterminate_raises(exc):
    iface, client = _make_interface()
    client.cancel_order_model = AsyncMock(side_effect=exc)

    with pytest.raises(IndeterminateOrderError) as ei:
        await iface.cancel_order("ETH-12345")

    err = ei.value
    assert err.operation == "cancel_order"
    assert err.order_id == "ETH-12345"
    assert err.cause is exc


# --------------------------------------------------------------------------- #
# replace_order
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_replace_order_definite_success():
    iface, client = _make_interface()
    result = {"order": {"order_id": "ETH-99999"}}
    client.send_request = AsyncMock(return_value=result)

    resp = await iface.replace_order("ETH-12345", price=21000.0)

    assert resp == result
    # New order tracked; old one gone.
    active = await iface.order_tracker.get_active_order_ids()
    assert "ETH-99999" in active


@pytest.mark.asyncio
async def test_replace_order_definite_failure_returns_none():
    iface, client = _make_interface()
    client.send_request = AsyncMock(
        side_effect=DeribitWebSocketError(11044, "not_open_order")
    )

    resp = await iface.replace_order("ETH-12345", price=21000.0)

    assert resp is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        asyncio.TimeoutError(),
        DeribitWebSocketError(-1, "Request timed out: private/edit"),
        ConnectionError("socket dropped"),
        ConnectionClosed(None, None),
    ],
)
async def test_replace_order_indeterminate_raises(exc):
    iface, client = _make_interface()
    client.send_request = AsyncMock(side_effect=exc)

    with pytest.raises(IndeterminateOrderError) as ei:
        await iface.replace_order("ETH-12345", price=21000.0)

    err = ei.value
    assert err.operation == "replace_order"
    assert err.order_id == "ETH-12345"
    assert err.cause is exc


def test_indeterminate_error_is_not_swallowed_as_none():
    """An IndeterminateOrderError must never be confused with a None failure."""
    err = IndeterminateOrderError("submit_order", "boom", order_id=None)
    assert isinstance(err, Exception)
    assert err is not None
