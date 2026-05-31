"""Build Order objects and inspect the parameters sent to the Deribit API.

Pure object construction — no network or credentials required.
"""

from deribridge.classes.order import Order


def main() -> None:
    order = Order.limit_buy(
        instrument_name="BTC-PERPETUAL",
        amount=0.1,
        price=50000,
        post_only=True,
    )
    print("Limit buy params:", order.api_params())

    market_order = Order.market_sell(
        instrument_name="BTC-PERPETUAL",
        amount=0.1,
        reduce_only=True,
    )
    print("Market sell params:", market_order.api_params())


if __name__ == "__main__":
    main()
