"""Fetch the same canonical data from two different exchanges.

Public market data only — no credentials needed. The same code path returns the
same canonical ``Ticker``/``OrderBook`` types regardless of venue; only the
symbol scheme differs.

Install the adapters first::

    pip install "deribridge[all]"
"""

import asyncio

import deribridge


async def show(exchange: str, symbol: str, *, testnet: bool = False) -> None:
    async with deribridge.create(exchange, testnet=testnet) as client:
        ticker = await client.get_ticker(symbol)
        book = await client.get_order_book(symbol, depth=5)
        print(
            f"[{exchange}] {ticker.symbol.canonical}  "
            f"mark={ticker.mark_price}  best_bid={book.best_bid.price}  "
            f"spread={book.spread}"
        )


async def main() -> None:
    print("available adapters:", deribridge.available_adapters())
    await show("deribit", "BTC-PERPETUAL", testnet=True)
    await show("binance", "BTCUSDT")


if __name__ == "__main__":
    asyncio.run(main())
