# Roadmap

This is a direction-of-travel document for `deribridge`, not a commitment.
Priorities and timing may change.

## 1.0.0 (current)

- **Multi-exchange framework.** A canonical, exchange-agnostic data model and
  `ExchangeAdapter` interface, selected by name via
  `deribridge.connect("deribit", ...)`. Deribit is the reference adapter;
  Binance is a worked REST + WebSocket example. Adapter code ships with the
  package; an adapter's dependencies are gated behind extras
  (`pip install deribridge[binance]`) and imported lazily. See
  [docs/architecture/multi-exchange.md](architecture/multi-exchange.md) and the
  [migration guide](MIGRATION.md).
- **Stable public API** with a documented deprecation policy; legacy Deribit
  import paths remain available behind deprecation shims.

## Next

- **Event-first order/position tracking.** Replace the ~2s polling loop with
  ingestion of `user.orders` / `user.trades` subscriptions, keeping polling as a
  reconciliation fallback.
- More exchange adapters on the common interface (e.g. OKX, Bybit), and a
  documented contributor guide for writing one.
- Optional analytics primitives (greeks, P&L, risk helpers) that complement the
  transport layer — the kind of layer [deribook](https://deribook.com) builds on
  top of this client.
- Broader instrument/market coverage and helpers.

## Ongoing

- Comprehensive integration coverage on testnet.
- Performance and reconnection hardening under sustained load.
