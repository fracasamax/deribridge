# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
As of 1.0.0 the public API is stable; breaking changes bump the major version.

## [1.0.0] — Unreleased

Rebrands `deribridge` from a Deribit-only client into a **multi-exchange
bridge framework**: one canonical, typed data model and a common interface
across exchanges, with Deribit as the reference adapter. This release also marks
the first stable public API. See
[docs/architecture/multi-exchange.md](docs/architecture/multi-exchange.md) and
the [migration guide](docs/MIGRATION.md).

### Added
- **Canonical, exchange-agnostic data model** (`deribridge.core.models`):
  `Symbol`, `OrderBook`, `Ticker`, `Trade`, `Candle`, `Order`, `OrderRequest`,
  `Position`, `Balance`, `AccountSummary`, `Instrument`, plus `Greeks`/`Stats`/
  `FundingRate`. Prices/amounts/balances/fees are `Decimal` (lossless across
  string-price venues); analytics values (greeks, IV, funding) are `float`.
  Every model carries a `raw` passthrough for venue-specific fields.
- **`ExchangeAdapter` interface** and a **`Capabilities`** descriptor for
  feature discovery; the order-safety trichotomy (success / `OrderRejected` /
  `IndeterminateOrderError`) is now a framework-level contract enforced by a
  shared conformance suite.
- **Facade + registry:** `deribridge.connect(name, ...)` / `create(name, ...)`
  and `available_adapters()`. Adapters are resolved lazily by name.
- **Binance adapter** (reference REST + WebSocket example) under the `binance`
  extra: public market data (`get_instruments`, `get_order_book`, `get_ticker`,
  `get_candles`) and a `bookTicker` WS subscription.
- Optional dependency **extras**: `deribridge[deribit]`, `deribridge[binance]`,
  `deribridge[all]`. A missing extra raises an actionable `MissingExchangeExtra`.

### Changed
- **Breaking (install):** `websockets` moved out of the core dependencies into
  the `deribit` (and `binance`) extras. Existing Deribit users should install
  `pip install deribridge[deribit]`. The framework core now depends only on
  `pydantic` and `python-dotenv`.
- The Deribit client moved to `deribridge.exchanges.deribit`. Old import paths
  (`from deribridge import DeribitAPIInterface`, `deribridge.api_client.*`) keep
  working via lazy re-export shims; `deribridge.api_client` is deprecated.
- `IndeterminateOrderError` is now defined in `deribridge.core.errors` and
  re-exported from its previous locations (same class, same signature).
- `RateLimiter` moved to `deribridge.core.transport` (re-exported for
  compatibility).

### Notes
- The new canonical models use `Decimal` for monetary fields. The legacy
  `DeribitAPIInterface` path is unchanged and still returns the existing
  (`float`-based) Deribit response models, so current consumers are unaffected
  until they opt into the canonical API.

## [0.1.0] — Unreleased

Initial public beta.

### Added
- Async, typed Deribit WebSocket client (`DeribitWebSocketClient`), higher-level
  trading interface (`DeribitAPIInterface`), rate limiting (`RateLimiter`), and
  Pydantic response models.
- Three-outcome contract for order-mutating calls: success, definite failure
  (`None`), and **indeterminate** (`IndeterminateOrderError`, raised on
  timeout/disconnect) — extended to `cancel_all_orders`, `close_position`, and
  `close_all_positions` (the batch records indeterminate closes per-position and
  continues instead of aborting).
- `configure()` honours documented `.env` loading via `python-dotenv`
  (`load_dotenv_file=True` by default; pass `False` to disable cwd file reads).
- Opt-in `configure_logging()` helper for scripts/examples.
- `examples/` directory with runnable scripts (instrument parsing, order
  building, client connection, and a gated end-to-end order flow).
- Governance docs: `SECURITY.md`, this changelog, and a release checklist.

### Changed
- **Breaking:** `DeribitWebSocketClient(..., auto_connect=...)` now defaults to
  `False`. Construction no longer performs implicit network I/O; call
  `connect()` explicitly (or pass `auto_connect=True` from within a running
  event loop).
- **Breaking:** `DeribitResultResponse.to_typed_result()` now returns a single
  typed object and raises `TypeError` on a list result; use the new
  `to_typed_list()` for array results.
- `connect_deribit_client()` now connects exactly once (was double-connecting).
- Library code no longer configures the root logger: `DeribitAPIInterface`
  uses the namespaced logger `deribridge.api`, and helper modules log instead
  of printing to stdout.
- Importing the package (or its modules) has no side effects; runnable examples
  moved out of `__main__` blocks into `examples/`.

### Security
- Bumped `python-dotenv` to `>=1.2.2`; `pip-audit` reports no known
  vulnerabilities.

### Known limitations
- **Order/position tracking is polling-based** (~2s). Event-first tracking via
  `user.orders`/`user.trades` subscriptions is planned for `0.2.0`.

[1.0.0]: https://github.com/fracasamax/deribridge/releases/tag/v1.0.0
[0.1.0]: https://github.com/fracasamax/deribridge/releases/tag/v0.1.0
