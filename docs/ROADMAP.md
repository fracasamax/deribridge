# Roadmap

This is a direction-of-travel document for `deribridge`, not a commitment. It is
pre-1.0; priorities and timing may change.

## 0.1.x (current — beta)

- Stabilise the public surface based on real usage.
- Expand the testnet integration suite (`tests/integration/`).
- Documentation polish (guide, AI reference, examples).

## 0.2.0

- **Event-first order/position tracking.** Replace the ~2s polling loop with
  ingestion of `user.orders` / `user.trades` subscriptions, keeping polling as a
  reconciliation fallback. (Audit item #12.)

## Later (0.x → 1.0)

- Optional analytics primitives (greeks, P&L, risk helpers) that complement the
  transport layer — the kind of layer [deribook](https://deribook.com) builds on
  top of this client.
- Broader instrument/market coverage and helpers.
- Possible support for additional exchanges behind a common interface.

## Toward 1.0

- Public API stability guarantees and a documented deprecation policy.
- Comprehensive integration coverage on testnet.
- Performance and reconnection hardening under sustained load.
