"""End-to-end DeribitAPIInterface example.

Connects, reads market data, places and cancels a small test order, then
disconnects.

WARNING: this example can place a REAL order. It is gated behind an env flag and
should only ever be run against TESTNET credentials:

    DERIBRIDGE_ALLOW_EXAMPLE_ORDERS=1 python examples/run_api_interface.py
"""

import asyncio
import os

from deribridge import DeribitAPIInterface, configure_logging

if os.environ.get("DERIBRIDGE_ALLOW_EXAMPLE_ORDERS") != "1":
    raise SystemExit(
        "This example can place a REAL order. Set "
        "DERIBRIDGE_ALLOW_EXAMPLE_ORDERS=1 and use TESTNET credentials to run it."
    )


async def main() -> None:
    configure_logging()

    risk_config = {
        "max_position_size": {"BTC-PERPETUAL": 1.0},
        "max_order_size": {"BTC-PERPETUAL": 0.1},
        "max_daily_loss": 100.0,
        "sequential_loss_limit": 3,
    }
    api = DeribitAPIInterface.configure(use_test_env=True, risk_config=risk_config)

    if not await api.start_client():
        print("Connection failed")
        return

    await api.subscribe_to_order_book("BTC-PERPETUAL")
    await api.subscribe_to_ticker("BTC-PERPETUAL")

    ticker = await api.get_ticker("BTC-PERPETUAL")
    if ticker:
        print(f"Current BTC-PERPETUAL price: {ticker.mark_price}")

    order_result = await api.submit_limit_order(
        instrument_name="BTC-PERPETUAL",
        side="buy",
        amount=0.01,
        price=ticker.mark_price * 0.99 if ticker else 20000,
        post_only=True,
    )

    if order_result and order_result.order and order_result.order.order_id:
        order_id = order_result.order.order_id
        print(f"Order placed: {order_id}")
        await asyncio.sleep(5)
        print(f"Order cancelled: {await api.cancel_order(order_id)}")

    print(f"Performance metrics: {await api.get_performance_metrics()}")
    await api.stop_client()


if __name__ == "__main__":
    asyncio.run(main())
