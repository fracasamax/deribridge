# deribridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Typed](https://img.shields.io/badge/typing-typed-brightgreen.svg)](https://peps.python.org/pep-0561/)

**Async, typed, multi-exchange bridge for crypto exchanges.**

`deribridge` turns each exchange's API into the *same* canonical, typed data
classes behind a common interface — so you build trading tooling against one
model instead of hand-parsing each venue's JSON. Pick an exchange by name; add
a new one by writing a single adapter that maps its API to the canonical model.

[Deribit](https://docs.deribit.com/) is the reference adapter (a hardened
WebSocket client with order-lifecycle tracking and rate limiting); Binance is a
worked REST + WebSocket example. Adapter code ships with the package; an
adapter's dependencies are gated behind extras and imported lazily.

It is also the open-source bridge behind **[deribook](https://deribook.com)**,
where Deribit data feeds real-time portfolio analytics, greeks, P&L, and risk
views. See [docs/architecture/multi-exchange.md](docs/architecture/multi-exchange.md).

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

Adapter code always ships; install the extras for the exchanges you use (this
pulls each adapter's transport dependencies):

```bash
pip install "deribridge[deribit]"     # Deribit (WebSocket)
pip install "deribridge[binance]"     # Binance (REST + WebSocket)
pip install "deribridge[all]"         # every bundled adapter
```

A bare `pip install deribridge` installs the framework core; calling an adapter
whose extra is missing raises an actionable error telling you what to install.

Until the first PyPI release you can install straight from GitHub:

```bash
pip install "deribridge[all] @ git+https://github.com/fracasamax/deribridge.git"
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

Canonical, exchange-agnostic API — the same code works across adapters:

```python
import asyncio
import deribridge


async def main():
    async with deribridge.create("deribit", testnet=True) as client:
        ticker = await client.get_ticker("BTC-PERPETUAL")
        print("Deribit mark price:", ticker.mark_price)  # Decimal

    async with deribridge.create("binance") as client:
        book = await client.get_order_book("BTCUSDT", depth=10)
        print("Binance best bid:", book.best_bid.price)  # Decimal


asyncio.run(main())
```

`deribridge.available_adapters()` lists installed adapters; `connect(...)` builds
and connects, `create(...)` builds for use with `async with`.

The Deribit-specific interface remains available unchanged:

```python
from deribridge import DeribitAPIInterface

api = DeribitAPIInterface.configure(use_test_env=True)
if await api.start_client():
    ticker = await api.get_ticker("BTC-PERPETUAL")  # Deribit response model (float)
    await api.stop_client()
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
├── core/         # exchange-agnostic framework: canonical models, ExchangeAdapter,
│                 #   transport protocols, registry, connect()/create() facade
├── exchanges/
│   ├── deribit/  # reference adapter (WebSocket)
│   └── binance/  # worked example (REST + WebSocket; needs the `binance` extra)
├── classes/      # legacy domain types (Order, Instrument, Currency, ...)
├── models/       # legacy enums / value models
└── api_client/   # deprecated re-export shim for old Deribit import paths
```

See [docs/architecture/multi-exchange.md](docs/architecture/multi-exchange.md)
for the design and [docs/MIGRATION.md](docs/MIGRATION.md) for upgrading from
0.1.x.

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

`deribridge` is **1.0** and follows [Semantic Versioning](https://semver.org):
the public API (the canonical models, the `ExchangeAdapter` interface, and the
`connect()`/`create()` facade) is stable, and breaking changes will bump the
major version. Legacy Deribit-specific names remain available behind deprecation
shims. Check the [CHANGELOG](CHANGELOG.md) and the
[migration guide](docs/MIGRATION.md) when upgrading.

- Each exchange is a pluggable adapter; Deribit (WebSocket JSON-RPC v2) is the
  reference adapter and Binance (REST + WebSocket) is a worked example. Both
  support test and production endpoints.
- Supported on **Python 3.12 and 3.13**.
- Exchanges may change their APIs at any time; tracking those changes may
  require updates to the affected adapter.

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
