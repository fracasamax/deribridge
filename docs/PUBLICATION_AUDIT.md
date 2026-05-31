# deribridge Public Release Audit

Audit date: 2026-05-31
Scope: full repository review for open publication as a Deribit bridge and as a credible deribook.com referral surface.

## Executive Summary

`deribridge` is close to publishable as a beta Python package, but I would not publish it unchanged. The core structure is good: typed exports, MIT license, README, guide, CI, tests, package metadata, explicit Deribit non-affiliation disclaimer, and strong documentation around indeterminate order outcomes for the main order methods.

The remaining blockers before public release are:

- Make documented `.env` behavior true. `README.md` says credentials are read via `python-dotenv`, but `DeribitAPIInterface.configure()` only reads `os.environ`.
- Remove unsafe constructor side effects. `DeribitWebSocketClient(auto_connect=True)` schedules `asyncio.create_task()` inside `__init__`, which is risky for a public library and can fail outside a running event loop.
- Extend the three-outcome order-safety contract beyond submit/cancel/edit to destructive helpers such as `cancel_all_orders()` and `close_position()`.
- Add public-repo governance files: `SECURITY.md`, `CHANGELOG.md`, release checklist, and optionally `CODE_OF_CONDUCT.md`.

Resolved during this cleanup:

- Upgraded `python-dotenv` to require `>=1.2.2`, refreshed `uv.lock`, and confirmed `pip-audit` reports no known vulnerabilities.
- Intentionally deleted the internal `docs/sweep-log.md` in favor of this public-facing audit.

## Verification Performed

Commands run during the audit:

```bash
uv run ruff check src tests
.venv/bin/python -m pytest -q
uv run --with mypy -- mypy src
uv run --with build python -m build
uv run --with pip-audit -- pip-audit
```

Results:

- Ruff: passed.
- Tests: 58 passed.
- Mypy: passed under current default settings, but it notes that untyped function bodies are not checked.
- Build: sdist and wheel built successfully.
- Dependency audit: initial audit found `python-dotenv 1.1.0` vulnerable as `CVE-2026-28684`; after upgrading to `>=1.2.2`, `pip-audit` reports no known vulnerabilities.

Local environment note: `uv run pytest -q` failed because `.venv/bin/pytest` has a stale shebang pointing at a previous repo path. `.venv/bin/python -m pytest -q` works. Recreate the local `.venv` before relying on local command reproducibility.

## Priority 0: Must Fix Before Publishing

### 1. Upgrade `python-dotenv` and refresh the lockfile

Evidence:

- `pyproject.toml` allows `python-dotenv>=1.0.0`.
- Current installed version is `1.1.0`.
- `pip-audit` reported `CVE-2026-28684`, fixed in `1.2.2`.

Status:

- Resolved in this cleanup by setting `python-dotenv>=1.2.2`, refreshing `uv.lock`, and re-running `pip-audit`, tests, and build.

### 2. Fix `.env` loading or correct the docs

Evidence:

- `README.md` says credentials are read from environment variables via `python-dotenv`.
- `DeribitAPIInterface.configure()` reads `os.environ` directly and does not call `load_dotenv()`.
- `client_management.get_credentials()` does call `load_dotenv()`, but the README quick start uses `DeribitAPIInterface.configure()`.

Recommended change:

- Preferred: make `DeribitAPIInterface.configure()` call `load_dotenv()` before reading credentials, or accept a `load_dotenv_file: bool = True` option.
- Alternative: remove the `python-dotenv` claim from README/GUIDE and tell users to export environment variables or call `load_dotenv()` themselves.

### 3. Remove `asyncio.create_task()` from the constructor path

Evidence:

- `DeribitWebSocketClient.__init__()` defaults `auto_connect=True`.
- If `auto_connect` is true, it calls `asyncio.create_task(self.connect())`.
- Public library constructors should not require a running event loop or start network connections implicitly.

Recommended change:

- Change `auto_connect` default to `False`.
- Make users call `await client.connect()` or use an async factory.
- Keep backward compatibility with a deprecation path if needed, but do not publish a new public API with implicit network side effects.

### 4. Fix double-connect risk in `connect_deribit_client()`

Evidence:

- `connect_deribit_client()` creates `EnhancedDeribitClient(...)` without `auto_connect=False`.
- It then immediately calls `await client.connect()`.
- With the inherited default `auto_connect=True`, this can schedule one connect task and then run a second connect explicitly.

Recommended change:

- Pass `auto_connect=False` when constructing `EnhancedDeribitClient` in `client_management.py`.
- Add a regression test that verifies only one connection attempt is made.

### 5. Extend indeterminate-operation handling to destructive helpers

Evidence:

- `submit_order()`, `cancel_order()`, and `replace_order()` now raise `IndeterminateOrderError` on timeout/disconnect.
- `cancel_all_orders()` catches all exceptions and returns `None`.
- `close_position()` catches all exceptions and returns `None`.
- These are exchange-mutating operations where timeout/disconnect leaves the result unknown.

Recommended change:

- Apply the same three-outcome contract to `cancel_all_orders()`, `close_position()`, and `close_all_positions()`.
- On timeout/disconnect, raise `IndeterminateOrderError` with enough context to reconcile.
- Document reconciliation steps: `get_open_orders`, `get_positions`, and relevant account/position snapshots.

### 6. Decide what to do with `docs/sweep-log.md`

Evidence:

- `docs/sweep-log.md` is tracked in Git but deleted in the working tree during this audit.
- It contains useful internal hardening history, but it is not ideal public-facing documentation.

Status:

- Resolved in this cleanup by intentionally deleting the internal sweep log and replacing it with this public-facing audit.

## Priority 1: Strongly Recommended Before Public Release

### 7. Add `SECURITY.md`

The contributing guide asks users to email security concerns, but public repos should have a dedicated `SECURITY.md` with:

- Supported versions.
- Private disclosure contact.
- Expected response timeline.
- Scope examples: auth, credential handling, order submission, order state reconciliation, and market-data integrity.

This matters because the package can place real orders.

### 8. Add `CHANGELOG.md` and release process

Recommended content:

- `0.1.0` initial beta release.
- Known limitations.
- Upgrade notes for any API-breaking changes.
- Release checklist: tests, ruff, mypy, build, pip-audit, README review, Deribit testnet smoke check.

### 9. Do not configure root logging from a library constructor

Evidence:

- `DeribitAPIInterface.__init__()` calls `logging.basicConfig(...)`.

Why this matters:

- Importing/instantiating a library should not mutate the host application logging setup.
- Public users may embed this in bots, services, notebooks, or analytics apps with their own logging policy.

Recommended change:

- Remove `basicConfig()` from the constructor.
- Use `logging.getLogger(__name__)` or `logging.getLogger("deribridge")`.
- Provide an optional helper such as `deribridge.configure_logging()` for examples only.

### 10. Move runnable `__main__` examples out of package modules

Evidence:

- `deribit_api_interface.py` has a large `if __name__ == "__main__"` block that connects, subscribes, submits an order, and cancels it.
- `websocket_api_client.py`, `client_management.py`, `classes/order.py`, and `deribit_instrument.py` also contain example blocks with `print()` output.

Recommended change:

- Move examples to an `examples/` directory.
- Keep package modules import-only.
- For any example that can place orders, require both testnet credentials and an explicit `DERIBRIDGE_ALLOW_EXAMPLE_ORDERS=1` guard.

### 11. Fix user wildcard subscription behavior

Evidence:

- `subscribe_user_orders(None)` registers `user.orders.*.raw`.
- `subscribe_user_trades(None)` registers `user.trades.*.raw`.
- The dispatcher only indexes channels ending in `*`, so mid-string wildcards are not handled.
- `docs/AI_REFERENCE.md` already documents this limitation.

Recommended change:

- Either implement mid-string wildcard matching, or change the helper to subscribe to Deribit-supported all-user channels that dispatch exactly.
- Add tests that `subscribe_user_orders(None)` and `subscribe_user_trades(None)` actually invoke callbacks.

### 12. Replace polling-based order tracking with private subscription ingestion

Evidence:

- `_monitor_orders_and_positions()` polls active orders every ~2 seconds.
- `_update_order_status()` calls `get_order_state()` per active order.
- Iceberg fill-wait also polls `get_order_state()`.

Why this matters:

- Public users will assume "real-time" order lifecycle tracking. Polling creates latency, rate-limit pressure, and missed timing detail.

Recommended change:

- Subscribe to `user.orders` and `user.trades` after authentication.
- Use subscription events as the primary tracker input.
- Keep polling as a reconciliation fallback.

### 13. Make response modeling consistent

Evidence:

- `DeribitResultResponse.to_typed_result()` is annotated as returning `T`, but returns `list[T]` for list results.
- The docs warn about this footgun.

Recommended change:

- Split into `to_typed_result(model_class) -> T` and `to_typed_list(model_class) -> list[T]`.
- Deprecate list behavior in `to_typed_result()`.
- Remove the need for type ignores around this helper.

### 14. Stop printing from library helpers

Evidence:

- `run_rate_limited_tasks()` prints success/error lines.
- `TradePlan.from_csv()` prints validation errors.

Recommended change:

- Replace prints with logger calls.
- Consider returning structured row errors from `TradePlan.from_csv()` rather than dropping invalid rows silently.
- Add an option such as `strict=True` to fail fast on invalid CSV rows.

### 15. Tighten CI to match the public promise

Current CI runs ruff, tests, build, wheel install, and import smoke test.

Recommended additions:

- `uv lock --check` or equivalent lock verification.
- `mypy src` once mypy is part of the dev group.
- `pip-audit` after the `python-dotenv` upgrade.
- Coverage reporting or at least branch coverage for order-mutating behavior.
- `python -m pytest -q` instead of relying on a potentially stale script path locally.

### 16. Add an integration-test strategy

Current tests are good mocked regression tests. Public users will also need confidence against Deribit testnet behavior.

Recommended change:

- Add opt-in integration tests guarded by environment variables, for example `DERIBRIDGE_RUN_INTEGRATION=1`.
- Test public endpoints without credentials.
- Test authenticated read-only endpoints with testnet credentials.
- Keep order placement tests disabled by default and guarded separately.

## Priority 2: Good Public-Repo Polish

### 17. Make installation docs public-package ready

Evidence:

- README installation currently says `pip install -e .`, which is a contributor install, not a user install.

Recommended change:

- Before PyPI publication: show `pip install deribridge`.
- Keep editable install under "Development".
- If not publishing to PyPI immediately, state `pip install git+https://github.com/fracasamax/deribridge.git`.

### 18. Add API examples that advertise deribook without feeling like an ad

The current deribook positioning is useful and appropriate. Improve it by showing why the bridge exists:

- Example: fetch positions and account summary, then mention that deribook provides hosted portfolio analytics over the same Deribit data.
- Add a short "From bridge to analytics" section linking to deribook.
- Keep deribook mentions factual and secondary to the library utility.

### 19. Add a public roadmap

Recommended roadmap items:

- Deribit testnet integration suite.
- Private subscription driven order tracker.
- Other crypto exchanges planned after Deribit.
- More portfolio analytics primitives that support deribook-style workflows.
- Stabilization goals for `1.0`.

### 20. Clarify API stability

Recommended change:

- Add a "Beta API stability" note to README.
- State that `0.x` may change public names and return types.
- Mark high-level trading helpers as beta if they are not fully hardened.

### 21. Decide whether `uv.lock` should ship

For an application, lockfiles are essential. For a library, publishing `uv.lock` is acceptable but optional.

Recommended change:

- Keep `uv.lock` if it is part of contributor reproducibility.
- Ensure CI checks it.
- If you keep it, refresh it after dependency security fixes.

### 22. Add issue templates

Recommended templates:

- Bug report.
- API endpoint/model mismatch.
- Order safety incident.
- Feature request.
- Documentation issue.

### 23. Add explicit Deribit API compatibility notes

Recommended content:

- Deribit WebSocket JSON-RPC API v2.
- Testnet and production endpoints.
- Supported Python versions.
- Known unsupported Deribit features.
- Statement that Deribit API changes can require package updates.

### 24. Add package classifiers and metadata refinements

Recommended additions:

- `Programming Language :: Python :: 3 :: Only`
- `Topic :: Internet :: WWW/HTTP :: Dynamic Content` is probably not needed.
- Consider `Development Status :: 3 - Alpha` if the high-level trading interface remains beta-quality.
- Add `Documentation` URL if docs move to GitHub Pages or ReadTheDocs.

## Code Architecture Observations

### Strengths

- Clear package layout under `src/`.
- `py.typed` is present.
- Main order methods distinguish success, definite failure, and indeterminate outcomes.
- Test suite covers several important trading safety regressions.
- README and guide clearly warn that the software can place real orders.
- The deribook.com positioning is already present without overwhelming the library purpose.

### Main risks

- Constructor side effects and logging configuration are not library-friendly.
- Some mutating helper methods still flatten unknown exchange outcomes.
- Order tracker is polling-first, not event-first.
- Several models are dataclasses with permissive defaults; schema drift from Deribit can be missed unless tests cover real payloads.
- Some docs describe behavior that is only true in one helper path, especially `.env` loading.

## Suggested Pre-Publication Checklist

1. Completed: upgrade `python-dotenv` to `>=1.2.2`, refresh `uv.lock`, and re-run `pip-audit`.
2. Fix `.env` loading behavior or correct docs.
3. Change `auto_connect` default to `False` and fix `connect_deribit_client()`.
4. Apply `IndeterminateOrderError` to `cancel_all_orders()` and `close_position()`.
5. Remove `logging.basicConfig()` from constructors.
6. Move runnable examples to `examples/`.
7. Add `SECURITY.md` and `CHANGELOG.md`.
8. Completed: resolve the `docs/sweep-log.md` deletion intentionally.
9. Add CI checks for mypy, pip-audit, and lockfile validity.
10. Add opt-in Deribit testnet integration tests.

## Publication Recommendation

Publish only after Priority 0 is complete. After that, it is reasonable to publish as `0.1.0` beta with clear API-stability and trading-risk warnings. Priority 1 items should follow quickly because this package operates in a high-consequence domain where unclear failures, stale state, and implicit side effects can cost users real money.
