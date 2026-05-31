# Codebase Health Sweep Log

## Sweep 2026-05-31

**Commit at sweep start:** `993f8ae` (clean rebrand baseline)
**Scope:** full pre-publication hardening of `src/deribridge` (~7.7k LOC)

### Baseline (before)
| Signal | Count |
|--------|-------|
| Lint (ruff) | 8 |
| Type (mypy, `--ignore-missing-imports`) | 83 |
| Security (bandit) | 0 |
| Tests | 0 (no suite) |

### Baseline (after)
| Signal | Count |
|--------|-------|
| Lint (ruff) | **0** |
| Type (mypy) | **74** (annotation-quality only; functional type bugs fixed) |
| Security (bandit) | 0 |
| Tests | **23 passing** |

### Discovery
6 parallel category agents (security, bugs, type-safety, error-handling,
performance, dead-code) over the whole package. ~50 findings.

### Fixed (committed)

**Tier 0 — broken on every call**
- `trade_plan.py`: mangled `@staticmethod` (`return self @ staticmethod`); `round_price`/`set_computed_fields` raised.
- `trade_plan.py`: `Order(type=...)` → `order_type=...` (keyword was silently dropped).
- `deribit_api_interface.py`: `OrderType.limit` → `OrderType.LIMIT` (broke submit_limit_order/TWAP/iceberg).
- `deribit_api_interface.py`: `.get("order_id")` on an `OrderSubmitResponse` dataclass → `.order.order_id`.
- `OrderType` group sets were absorbed as enum members → `self in self.MARKET_TYPES` did str-substring matching, so `LIMIT.is_market()` returned True. Moved to module-level frozensets.

**Tier 1 — correctness / financial safety**
- `Ticker.spread`/`mid_price`: guard None (one-sided book) instead of `float - None` crash.
- `_wait_for_rate_limit`: lock the prune/check/append; `deque` for O(1) trim (was a check-then-act race that could exceed the exchange limit).
- `replace_order`: read the new order from `result["order"]` (Deribit shape), so replaced orders are tracked.
- `close_all_positions`: no longer reports `success=True` when `close_position` returns None.
- Auth: validate `access_token`/`expires_in` before `authenticated=True`; do not auto-reconnect on credential failure; recompute clock after sleep in the refresh loop.
- Silent failures on `send_request`/`authenticate` now log with context.

**Tier 2 — packaging hygiene**
- Added `py.typed` (PEP 561; verified in wheel).
- Removed `main()` stub, 2 empty modules, unused imports, dead locals, unreachable return.
- Renamed `RateLimiter.py` → `rate_limiter.py`.
- Removed a `__main__` example leaking a personal Windows path.

**Tests added:** `tests/test_trade_plan.py`, `tests/test_order.py`, `tests/test_response_models.py` (23 tests).

### Carried over (next sweep)
- **Type annotations (74 mypy):** None-initialized attributes used as concrete types in `websocket_api_client.py`; dict-value type drift in request builders; LSP-violating overrides + `to_typed_result` misuse in `enhanced_api_client.py`; `TaskGroup` not `Generic[T]` in `rate_limiter.py`; implicit-Optional defaults. Mechanical but voluminous; none are runtime crashes.
- **Silent-failure redesign (deeper):** `submit_order`/`cancel_order`/`replace_order` still collapse indeterminate timeout/disconnect outcomes to `None` — a definite redesign (distinct "indeterminate" result so callers can reconcile via `get_order_state`) is recommended before real trading use. Now logged, but contract unchanged.
- **Performance (architectural):** order/position monitoring and iceberg fill-wait poll `get_order_state` instead of consuming the `user.orders` subscription; subscription dispatch is O(handlers) per message.
- **`run_rate_limited_tasks`:** results stored by completion order, so positional `get_result(index)` can mismatch.
- **Reconnect auth race:** connect+auth not fully held under the connection lock; private sends gated only by an `authenticated` flag.
