# deribridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Typed](https://img.shields.io/badge/typing-typed-brightgreen.svg)](https://peps.python.org/pep-0561/)

**Async, typed Python client and middleware for the [Deribit](https://docs.deribit.com/) API.**

`deribridge` is a structured layer over Deribit's WebSocket API: a typed transport
client, a higher-level trading interface with order-lifecycle tracking, built-in rate
limiting, and Pydantic models for every response — so you can build trading tooling
without hand-parsing JSON or babysitting reconnects.

It is also the open-source bridge behind **[deribook](https://deribook.com)**,
where the same Deribit data feeds real-time portfolio analytics, greeks, P&L, and
risk views.

## Features

- ⚡ **Async-first** — built on `asyncio` and `websockets`
- 🧩 **Typed models** — Pydantic models for orders, order books, tickers, positions, trades, account summaries, and more
- 🛡️ **Thread-safe order tracking** — lifecycle tracking with an internal lock and order history
- 🔁 **Resilient** — managed background monitoring task with cancellation + auto-restart
- 🚦 **Rate limiting** — built-in `RateLimiter` to stay within Deribit limits
- 🧪 **Test & production environments** — switch with a single flag
- 📊 **Analytics-ready** — response models that work well for portfolio dashboards,
  risk monitors, and tools like [deribook](https://deribook.com)

## Installation

```bash
pip install deribridge
```

Until the first PyPI release you can install straight from GitHub:

```bash
pip install git+https://github.com/fracasamax/deribridge.git
```

Requires Python ≥ 3.12.

### Development install

```bash
git clone https://github.com/fracasamax/deribridge.git
cd deribridge
uv sync        # or: pip install -e .
```

## Configuration

Credentials are read from environment variables. `configure()` calls
`python-dotenv`'s `load_dotenv()` by default (pass `load_dotenv_file=False` to
disable any working-directory file read). Copy the example file and fill in your
Deribit API keys:

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

Fuller runnable examples live in [`examples/`](examples/) — instrument parsing
and order building (no credentials), connecting a client, and a full
connect → quote → place/cancel flow (gated behind an env flag, testnet only).

## Documentation

- **[docs/GUIDE.md](docs/GUIDE.md)** — compact usage guide for developers (install,
  config, quick start, placing orders safely).
- **[docs/AI_REFERENCE.md](docs/AI_REFERENCE.md)** — dense technical reference for
  building tooling (and for AI coding agents): full API surface, lifecycle &
  concurrency model, the three-outcome order contract, and known gotchas.

For a production example of the kind of analytics layer this bridge supports, see
[deribook.com](https://deribook.com).

> **Order safety:** order-mutating calls (`submit_order`, `submit_limit_order`,
> `cancel_order`, `replace_order`) have three outcomes — success, definite failure
> (`None`), and **indeterminate** (`IndeterminateOrderError`, raised on
> timeout/disconnect). On indeterminate, reconcile via `get_order_state` /
> `get_open_orders` before retrying — never resubmit blindly. See the guides above.

## Project layout

```
src/deribridge/
├── api_client/   # WebSocket client, API interface, rate limiter, response models
├── classes/      # Domain types (Order, Instrument, Currency, ...)
└── models/       # Enums / value models (OrderType, TimeInForce, Interval, ...)
```

## Key exports

`DeribitWebSocketClient`, `DeribitWebSocketError`, `DeribitAPIInterface`,
`EnhancedDeribitClient`, `RateLimiter`, plus response models (`Order`, `OrderBook`,
`Position`, `Trade`, `Ticker`, `AccountSummary`, `TransactionLogEntry`, …) and domain
types (`Instrument`, `Currency`, `OrderPurpose`). See `__all__` in the package
`__init__` for the full list.

## Used by

- **[deribook](https://deribook.com)** — stats and advanced analytics for
  derivatives portfolios on Deribit (greeks, P&L, risk, and more). `deribridge`
  is the open-source client layer it's built on. If you trade options or futures
  on Deribit and want a clearer view of your book, take a look.

Using `deribridge` in your own project? Open a PR adding it here.

## Stability & compatibility

`deribridge` is **beta** (`0.x`): public names and return types may change
between minor releases, and the high-level trading helpers in particular are
still evolving. Pin a version if you need stability, and check the
[CHANGELOG](CHANGELOG.md) for breaking changes.

- Targets the Deribit **WebSocket JSON-RPC v2** API, with both test and
  production endpoints (switch via `use_test_env`).
- Supported on **Python 3.12 and 3.13**.
- Deribit may change its API at any time; tracking those changes may require
  updates here.

## ⚠️ Disclaimer

This software interacts with live financial markets and can place real orders. It is
provided **as is**, without warranty of any kind. Trading derivatives carries
substantial risk of loss. Use the test environment first, and you are solely
responsible for any use in production. This project is **not affiliated with Deribit**.

## Author

Built and maintained by **Francesco Casamassima** ([dev@elnc.eu](mailto:dev@elnc.eu))
— also the developer behind [deribook](https://deribook.com). Contributions, issues,
and feedback are welcome.

## License

[MIT](LICENSE) © 2026 Francesco Casamassima
