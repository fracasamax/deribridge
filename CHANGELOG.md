# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is pre-1.0, the public API may change between `0.x` releases.

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
- `TradePlan.from_csv()` gained a `strict` flag and a structured `errors` list
  instead of printing and silently dropping invalid rows.
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

[0.1.0]: https://github.com/fracasamax/deribridge/releases/tag/v0.1.0
