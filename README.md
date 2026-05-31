# deribridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Typed](https://img.shields.io/badge/typing-typed-brightgreen.svg)](https://peps.python.org/pep-0561/)

**Async, typed Python client and middleware for the [Deribit](https://docs.deribit.com/) API.**

`deribridge` is a structured layer over Deribit's WebSocket API: a typed transport
client, a higher-level trading interface with order-lifecycle tracking, built-in rate
limiting, and Pydantic models for every response — so you can build trading tooling
without hand-parsing JSON or babysitting reconnects.

## Features

- ⚡ **Async-first** — built on `asyncio` and `websockets`
- 🧩 **Typed models** — Pydantic models for orders, order books, tickers, positions, trades, account summaries, and more
- 🛡️ **Thread-safe order tracking** — lifecycle tracking with an internal lock and order history
- 🔁 **Resilient** — managed background monitoring task with cancellation + auto-restart
- 🚦 **Rate limiting** — built-in `RateLimiter` to stay within Deribit limits
- 🧪 **Test & production environments** — switch with a single flag

## Installation

```bash
pip install -e .
# or, with uv
uv sync
```

Requires Python ≥ 3.12.

## Configuration

Credentials are read from environment variables (via `python-dotenv`). Copy the example
file and fill in your Deribit API keys:

```bash
cp .env.example .env
```

```dotenv
DERIBIT_API_CLIENT_ID=your_client_id
DERIBIT_API_SECRET=your_client_secret
# Optional test-environment keys
DERIBIT_API_CLIENT_ID_TEST=your_test_client_id
DERIBIT_API_SECRET_TEST=your_test_client_secret
```

## Quick start

```python
import asyncio
from deribridge import DeribitAPIInterface


async def main():
    api = DeribitAPIInterface.configure(use_test_env=True)

    if await api.start_client():
        await api.subscribe_to_ticker("BTC-PERPETUAL")
        ticker = await api.get_ticker("BTC-PERPETUAL")
        print(f"BTC-PERPETUAL mark price: {ticker.mark_price}")
        await api.stop_client()


asyncio.run(main())
```

A fuller runnable example lives in the `__main__` block of
`src/deribridge/api_client/deribit_api_interface.py`.

## Project layout

```
src/deribridge/
├── api_client/   # WebSocket client, API interface, rate limiter, response models
├── classes/      # Domain types (Order, TradePlan, Instrument, Currency, ...)
└── models/       # Enums / value models (OrderType, TimeInForce, Interval, ...)
```

## Key exports

`DeribitWebSocketClient`, `DeribitWebSocketError`, `DeribitAPIInterface`,
`EnhancedDeribitClient`, `RateLimiter`, plus response models (`Order`, `OrderBook`,
`Position`, `Trade`, `Ticker`, `AccountSummary`, `TransactionLogEntry`, …) and domain
types (`TradePlan`, `TradePlanItem`, `Instrument`, `Currency`). See `__all__` in the
package `__init__` for the full list.

## Used by

- **deribook** — built on top of `deribridge`.

## ⚠️ Disclaimer

This software interacts with live financial markets and can place real orders. It is
provided **as is**, without warranty of any kind. Trading derivatives carries
substantial risk of loss. Use the test environment first, and you are solely
responsible for any use in production. This project is **not affiliated with Deribit**.

## License

[MIT](LICENSE) © 2026 fracasamax
