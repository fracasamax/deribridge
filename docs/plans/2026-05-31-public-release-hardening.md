# Public Release Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `deribridge` safe to publish as a `0.1.0` beta Python package by closing the publication blockers and recommended hardening items from `docs/PUBLICATION_AUDIT.md`, validated against the actual source.

**Architecture:** Small, surgical, test-first changes to the existing `src/deribridge/` package. No architectural rewrites in this plan — the polling→subscription order tracker (audit #12) is explicitly deferred to `0.2.0`. Every behavior change to a money-moving code path (order submit/cancel/close) ships with a regression test using the existing mocked-client pattern (no live network).

**Tech Stack:** Python 3.12/3.13, `uv`, `pytest` + `pytest-asyncio` (`asyncio_mode=auto`), `ruff`, `mypy`, `hatchling`, `websockets`, `pydantic`, `python-dotenv`.

**Required skills while executing:**
- @superpowers:test-driven-development — every code task is RED → GREEN → commit.
- @superpowers:using-git-worktrees — Phase 0 isolates this work.
- @superpowers:verification-before-completion — run the listed command and read the output before claiming any task done.

---

## ⚠️ Pre-flight: concurrency hazard (read before Phase 0)

At plan-authoring time, **multiple Claude Code sessions were editing this working tree concurrently** (one in `acceptEdits` mode). That already caused `pyproject.toml` to change mid-analysis. Consequences baked into this plan:

- **Audit #1 (`python-dotenv>=1.2.2`) is already applied** in the working tree (`pyproject.toml:41`, `uv.lock` refreshed, installed = `1.2.2`). Phase 1 only re-verifies and commits it.
- **Audit #18 (deribook positioning)** is partially applied across `README.md`, `docs/GUIDE.md`, `docs/AI_REFERENCE.md`, `src/deribridge/__init__.py`. Phase 4 only finishes/audits it.

**Do not start Phase 1 until the other editing sessions are stopped or have committed.** Phase 0 isolates into a worktree off a clean commit to prevent clobbering.

---

## Phase 0 — Isolation & baseline

### Task 0.1: Consolidate the working tree onto a commit

**Files:** none (git only)

**Step 1:** Confirm no other session is mid-edit (ask the user / check `ps aux | grep claude`).

**Step 2:** Decide what to do with the current uncommitted working-tree changes (dotenv bump, lock, deribook docs polish, `.gitignore`/`.env.example` tidy, `docs/sweep-log.md` deletion). Recommended: commit them as a baseline so the worktree starts clean.

```bash
git add -A
git commit -m "chore: pre-hardening baseline (dotenv 1.2.2, lockfile, deribook docs, sweep-log removal)"
```

Expected: clean tree (`git status --short` empty except untracked `docs/plans/`).

**Step 3:** Commit this plan.

```bash
git add docs/plans/2026-05-31-public-release-hardening.md
git commit -m "docs: add public-release hardening plan"
```

### Task 0.2: Create an isolated worktree

**Files:** none (git only). Use @superpowers:using-git-worktrees.

**Step 1:** Create a worktree on a fresh branch.

```bash
git worktree add ../deribridge-hardening -b release-hardening
cd ../deribridge-hardening
```

**Step 2:** Recreate the virtualenv (the audit noted a stale `.venv/bin/pytest` shebang).

```bash
uv sync
```

Expected: `.venv` created, deps resolved from `uv.lock`.

### Task 0.3: Record the green baseline

**Files:** none

**Step 1:** Run the full gate and record results.

```bash
uv run ruff check src tests
uv run python -m pytest -q
uv run --with mypy -- mypy src
uv run --with build python -m build
uv run --with pip-audit -- pip-audit
```

Expected: ruff pass; **58 passed**; mypy pass (notes untyped bodies); sdist+wheel build; **pip-audit reports no known vulnerabilities** (confirms #1). Record the pytest count — every later phase must keep it monotonically rising and never regressing.

---

## Phase 1 — Priority 0: publication blockers (TDD, money-moving paths)

### Task 1.1 (Audit #3 + #4): No implicit connect from constructor; fix `connect_deribit_client()` double-connect

**Validated facts:**
- `DeribitWebSocketClient.__init__(..., auto_connect=True, ...)` → `asyncio.create_task(self.connect())` at `src/deribridge/api_client/websocket_api_client.py:46,103-104`. Requires a running loop; does implicit network I/O from a constructor.
- `DeribitAPIInterface.__init__` **already** passes `auto_connect=False` (`deribit_api_interface.py:386`) — no change needed there.
- `connect_deribit_client()` constructs `EnhancedDeribitClient(...)` **without** `auto_connect=False` then awaits `connect()` (`client_management.py:67-74`) → schedules one connect task **and** runs a second connect.

**Files:**
- Modify: `src/deribridge/api_client/websocket_api_client.py:46` (default) and `:102-104` (guard)
- Modify: `src/deribridge/api_client/client_management.py:67-71`
- Test: `tests/test_websocket_safety.py` (extend), `tests/test_client_management.py` (create)

**Step 1: Write the failing test — constructor must not auto-connect.**

```python
# tests/test_websocket_safety.py
from unittest.mock import AsyncMock, patch
from deribridge.api_client.websocket_api_client import DeribitWebSocketClient

def test_constructor_does_not_auto_connect_by_default():
    """Default construction must not schedule a connect task (no implicit I/O)."""
    with patch.object(DeribitWebSocketClient, "connect", new=AsyncMock()) as mock_connect:
        DeribitWebSocketClient(client_id="x", client_secret="y")
    mock_connect.assert_not_called()
```

**Step 2: Run it — expect FAIL.**

Run: `uv run python -m pytest tests/test_websocket_safety.py::test_constructor_does_not_auto_connect_by_default -v`
Expected: FAIL (current default `auto_connect=True` calls `create_task`). Note: under `asyncio_mode=auto` this test runs without a loop, so the current code may raise `RuntimeError: no running event loop` — that is still a failing test, which is the point.

**Step 3: Make the minimal change.**

In `websocket_api_client.py`, change the default:

```python
            auto_connect: bool = False,
```

and update the docstring line for `auto_connect` to read `(default: False)`. Leave the `if auto_connect:` block as-is.

**Step 4: Run it — expect PASS.**

Run: `uv run python -m pytest tests/test_websocket_safety.py::test_constructor_does_not_auto_connect_by_default -v`
Expected: PASS.

**Step 5: Write the failing test — single connect in `connect_deribit_client()`.**

```python
# tests/test_client_management.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from deribridge.api_client import client_management

@pytest.mark.asyncio
async def test_connect_deribit_client_connects_exactly_once():
    fake = MagicMock()
    fake.connect = AsyncMock()
    fake.connected = True
    fake.authenticate = AsyncMock()
    fake.authenticated = True
    with patch.object(client_management, "EnhancedDeribitClient", return_value=fake) as ctor:
        await client_management.connect_deribit_client(
            client_id="x", client_secret="y", authenticate=False
        )
    # Constructed with auto_connect disabled, and connect awaited exactly once.
    assert ctor.call_args.kwargs.get("auto_connect") is False
    fake.connect.assert_awaited_once()
```

**Step 6: Run it — expect FAIL.**

Run: `uv run python -m pytest tests/test_client_management.py -v`
Expected: FAIL on the `auto_connect is False` assertion.

**Step 7: Make the minimal change** in `client_management.py:67-71`:

```python
        client = EnhancedDeribitClient(
            client_id=client_id,
            client_secret=client_secret,
            use_test_env=use_test_env,
            auto_connect=False,
        )
```

**Step 8: Run it — expect PASS.**

Run: `uv run python -m pytest tests/test_client_management.py -v`
Expected: PASS.

**Step 9: Full suite + commit.**

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/websocket_api_client.py \
        src/deribridge/api_client/client_management.py \
        tests/test_websocket_safety.py tests/test_client_management.py
git commit -m "fix(safety): no implicit connect in constructor; single connect in connect_deribit_client"
```

> Compatibility note for the PR/CHANGELOG: this flips the `auto_connect` default `True`→`False`. Document it as a breaking change for any caller relying on auto-connect.

---

### Task 1.2 (Audit #5): Indeterminate-outcome contract for destructive helpers

**Validated facts:**
- `cancel_all_orders()` (`deribit_api_interface.py:1101-1103`) and `close_position()` (`:1212-1214`) catch **all** exceptions and return `None` — collapsing timeouts/disconnects (unknown outcome) into "definite failure".
- `close_all_positions()` (`:1216-1267`) iterates `close_position()` and already treats `None` as not-success; it must now also handle the new `IndeterminateOrderError` per item without aborting the batch.
- Existing pattern to mirror: `submit_order`/`cancel_order`/`replace_order` use `_is_indeterminate_error(e)` (`:56-67`) then `raise IndeterminateOrderError(...)` (e.g. `:1170-1182`). `IndeterminateOrderError` is defined at `:25-53`.

**Files:**
- Modify: `src/deribridge/api_client/deribit_api_interface.py` — `cancel_all_orders` (~`:1101`), `close_position` (~`:1212`), `close_all_positions` (~`:1236-1262`)
- Test: `tests/test_api_interface_safety.py` (extend)

**Step 1: Write the failing tests.**

```python
# tests/test_api_interface_safety.py  (add to the existing file; helpers _make_interface already exist)
import pytest
from deribridge.api_client.deribit_api_interface import IndeterminateOrderError

@pytest.mark.asyncio
async def test_cancel_all_orders_raises_indeterminate_on_timeout():
    iface, client = _make_interface()
    client.send_request = AsyncMock(side_effect=asyncio.TimeoutError())
    iface._wait_for_rate_limit = AsyncMock()
    with pytest.raises(IndeterminateOrderError) as ei:
        await iface.cancel_all_orders()
    assert ei.value.operation == "cancel_all_orders"

@pytest.mark.asyncio
async def test_cancel_all_orders_returns_none_on_definite_failure():
    iface, client = _make_interface()
    client.send_request = AsyncMock(side_effect=ValueError("rejected"))
    iface._wait_for_rate_limit = AsyncMock()
    assert await iface.cancel_all_orders() is None

@pytest.mark.asyncio
async def test_close_position_raises_indeterminate_on_disconnect():
    iface, client = _make_interface()
    client.send_request = AsyncMock(side_effect=ConnectionError("dropped"))
    iface._wait_for_rate_limit = AsyncMock()
    with pytest.raises(IndeterminateOrderError) as ei:
        await iface.close_position("BTC-PERPETUAL")
    assert ei.value.operation == "close_position"

@pytest.mark.asyncio
async def test_close_all_positions_records_indeterminate_without_aborting():
    iface, client = _make_interface()
    # Two open positions; first close is indeterminate, batch must continue.
    pos = [MagicMock(size=1, instrument_name="BTC-PERPETUAL"),
           MagicMock(size=1, instrument_name="ETH-PERPETUAL")]
    iface.get_positions = AsyncMock(return_value=pos)
    iface.close_position = AsyncMock(side_effect=[
        IndeterminateOrderError(operation="close_position", message="x"),
        {"ok": True},
    ])
    results = await iface.close_all_positions()
    assert len(results) == 2
    assert results[0]["indeterminate"] is True and results[0]["success"] is False
    assert results[1]["success"] is True
```

**Step 2: Run — expect FAIL.**

Run: `uv run python -m pytest tests/test_api_interface_safety.py -k "indeterminate or definite_failure" -v`
Expected: FAIL (current helpers swallow to `None`; `close_all_positions` doesn't catch the new error).

**Step 3: Implement** — replace the `except` in `cancel_all_orders` (`:1101-1103`):

```python
        except Exception as e:
            if _is_indeterminate_error(e):
                self.logger.error(
                    f"cancel_all_orders outcome INDETERMINATE: {e}. Some/all "
                    "cancels may have applied — reconcile via get_open_orders "
                    "before retrying.")
                raise IndeterminateOrderError(
                    operation="cancel_all_orders",
                    message=(f"cancel_all_orders timed out or disconnected "
                             f"mid-flight; outcome unknown: {e}"),
                    order_id=None,
                    cause=e,
                ) from e
            self.logger.error(f"Error cancelling all orders: {e}")
            return None
```

Replace the `except` in `close_position` (`:1212-1214`):

```python
        except Exception as e:
            if _is_indeterminate_error(e):
                self.logger.error(
                    f"close_position outcome INDETERMINATE for {instrument_name}: "
                    f"{e}. The position may or may not have been closed — reconcile "
                    "via get_positions before acting.")
                raise IndeterminateOrderError(
                    operation="close_position",
                    message=(f"close_position for {instrument_name} timed out or "
                             f"disconnected mid-flight; outcome unknown: {e}"),
                    order_id=None,
                    cause=e,
                ) from e
            self.logger.error(f"Error closing position: {e}")
            return None
```

In `close_all_positions`, change the per-item `try/except` (`:1236-1262`) so an indeterminate close is recorded distinctly and does not abort the loop:

```python
                try:
                    result = await self.close_position(instrument)
                    if result is not None:
                        results.append({
                            "instrument": instrument,
                            "success": True,
                            "result": result,
                        })
                    else:
                        self.logger.error(
                            f"close_position returned no result for {instrument}; "
                            f"position may still be open")
                        results.append({
                            "instrument": instrument,
                            "success": False,
                            "error": "close_position returned no result (state unknown)",
                        })
                except IndeterminateOrderError as e:
                    self.logger.error(
                        f"close_position INDETERMINATE for {instrument}: {e}. "
                        "Position state unknown; not retrying in-batch.")
                    results.append({
                        "instrument": instrument,
                        "success": False,
                        "indeterminate": True,
                        "error": str(e),
                    })
                except Exception as e:
                    results.append({
                        "instrument": instrument,
                        "success": False,
                        "error": str(e),
                    })
```

**Step 4: Run — expect PASS.**

Run: `uv run python -m pytest tests/test_api_interface_safety.py -v`
Expected: PASS (all, including the existing submit/cancel/replace tests).

**Step 5: Update docstrings** of the three helpers to document the `Raises: IndeterminateOrderError` contract and the reconciliation endpoints (`get_open_orders`, `get_positions`), mirroring the wording already on `replace_order` (`:1125-1129`).

**Step 6: Commit.**

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/deribit_api_interface.py tests/test_api_interface_safety.py
git commit -m "fix(safety): indeterminate-outcome contract for cancel_all_orders/close_position/close_all_positions"
```

---

### Task 1.3 (Audit #2): Make documented `.env` behavior true

**Validated facts:**
- `README.md:41` says credentials are read "via `python-dotenv`".
- `DeribitAPIInterface.configure()` reads `os.environ` directly (`deribit_api_interface.py:443-448`); it never calls `load_dotenv()`.
- `client_management.get_credentials()` does call `load_dotenv()` (`client_management.py:16`).

**Design choice (validated):** add an explicit opt-in `load_dotenv_file: bool = True` to `configure()` rather than an unconditional `load_dotenv()` — a library should let the host disable cwd file reads.

**Files:**
- Modify: `src/deribridge/api_client/deribit_api_interface.py` — `configure()` signature (`:420-428`) and body (`:442-448`); ensure `from dotenv import load_dotenv` import exists at top
- Modify: `README.md:41` (state the opt-in flag)
- Test: `tests/test_api_interface_safety.py` (extend) or new `tests/test_configure_env.py`

**Step 1: Write the failing test.**

```python
# tests/test_configure_env.py
from unittest.mock import patch
from deribridge.api_client import deribit_api_interface as mod
from deribridge.api_client.deribit_api_interface import DeribitAPIInterface

def test_configure_loads_dotenv_by_default():
    with patch.object(mod, "load_dotenv") as ld:
        DeribitAPIInterface.configure(client_id="x", client_secret="y")
    ld.assert_called_once()

def test_configure_can_skip_dotenv():
    with patch.object(mod, "load_dotenv") as ld:
        DeribitAPIInterface.configure(client_id="x", client_secret="y",
                                      load_dotenv_file=False)
    ld.assert_not_called()
```

**Step 2: Run — expect FAIL** (`load_dotenv` not imported/called; unknown kwarg).

Run: `uv run python -m pytest tests/test_configure_env.py -v`

**Step 3: Implement.** Ensure the import near the top of `deribit_api_interface.py`:

```python
from dotenv import load_dotenv
```

Add the parameter to `configure()` and load before reading env:

```python
    @classmethod
    def configure(
            cls,
            client: Optional[EnhancedDeribitClient] = None,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            use_test_env: bool = True,
            log_level: int = logging.INFO,
            risk_config: Optional[Dict[str, Any]] = None,
            load_dotenv_file: bool = True,
    ) -> 'DeribitAPIInterface':
        ...
        if load_dotenv_file:
            load_dotenv()
        if not client and not client_id:
            client_id = os.environ.get(
                "DERIBIT_API_CLIENT_ID" + ("_TEST" if use_test_env else ""))
            client_secret = os.environ.get(
                "DERIBIT_API_SECRET" + ("_TEST" if use_test_env else ""))
```

Add a `load_dotenv_file` line to the `configure()` docstring Args.

**Step 4: Run — expect PASS.**

Run: `uv run python -m pytest tests/test_configure_env.py -v`

**Step 5: Update `README.md:41`** to state the behavior precisely, e.g.: "Credentials are read from environment variables; `configure()` calls `python-dotenv`'s `load_dotenv()` by default (pass `load_dotenv_file=False` to disable)."

**Step 6: Commit.**

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/deribit_api_interface.py tests/test_configure_env.py README.md
git commit -m "fix(config): configure() honors documented .env loading via opt-in load_dotenv_file"
```

---

### Task 1.4 (Audit #1): Finalize dependency-security fix

**Validated facts:** `pyproject.toml:41` already `python-dotenv>=1.2.2`; `uv.lock` refreshed; installed `1.2.2`. (Baseline commit in Task 0.1 carried this.)

**Step 1:** Re-run the audit to confirm clean.

```bash
uv run --with pip-audit -- pip-audit
```

Expected: no known vulnerabilities. If anything is still flagged, `uv lock --upgrade-package <pkg>` and re-run.

**Step 2:** No commit needed unless the lock changed; if it did:

```bash
git add uv.lock pyproject.toml
git commit -m "chore(deps): refresh lockfile after pip-audit verification"
```

---

### Task 1.5 (Audit #6): Resolve `docs/sweep-log.md` intentionally

**Validated facts:** `docs/sweep-log.md` was tracked and is deleted in the working tree; references to it were already removed from `docs/AI_REFERENCE.md`. The baseline commit (Task 0.1) staged the deletion.

**Step 1:** Confirm it is gone from the tree and from history references.

```bash
git ls-files docs/sweep-log.md   # expect: empty (no longer tracked)
grep -rn "sweep-log" docs README.md || echo "no references"
```

Expected: not tracked; no dangling references. The internal hardening history it held will be re-expressed publicly in `CHANGELOG.md` (Task 2.4). No further action.

---

## Phase 2 — Library hygiene & governance (Priority 0/1)

### Task 2.1 (Audit #9): Remove `logging.basicConfig()` from the constructor

**Validated facts:** `DeribitAPIInterface.__init__` calls `logging.basicConfig(...)` at `deribit_api_interface.py:372-378`, mutating host logging on instantiation. It then does `self.logger = logging.getLogger("DeribitAPI")` (`:379`).

**Files:**
- Modify: `src/deribridge/api_client/deribit_api_interface.py:371-379`
- Add: `configure_logging()` helper (module-level, opt-in, for examples only)
- Export: `src/deribridge/__init__.py` (add `configure_logging`)
- Test: `tests/test_logging_hygiene.py` (create)

**Step 1: Failing test.**

```python
# tests/test_logging_hygiene.py
import logging
from unittest.mock import patch
from deribridge.api_client.deribit_api_interface import DeribitAPIInterface
from unittest.mock import MagicMock

def test_constructor_does_not_call_basicconfig():
    client = MagicMock(); client.connected = True
    with patch.object(logging, "basicConfig") as bc:
        DeribitAPIInterface(client=client)
    bc.assert_not_called()
```

**Step 2: Run — expect FAIL.**

Run: `uv run python -m pytest tests/test_logging_hygiene.py -v`

**Step 3: Implement.** Delete the `logging.basicConfig(...)` block (`:372-378`) and use a namespaced logger:

```python
        # Library code must not configure the root logger. Use a namespaced
        # logger and respect whatever logging policy the host app has set.
        self.logger = logging.getLogger("deribridge.api")
```

Add a module-level opt-in helper (near the top of the module, after imports) and export it:

```python
def configure_logging(level: int = logging.INFO) -> None:
    """Opt-in convenience for examples/scripts. Libraries should NOT call this;
    it mutates the root logger. Provided so example code stays one line."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
```

In `src/deribridge/__init__.py`, add `configure_logging` to the imports and `__all__`.

**Step 4: Run — expect PASS** + import smoke.

Run: `uv run python -m pytest tests/test_logging_hygiene.py -v && uv run python -c "import deribridge; deribridge.configure_logging"`

**Step 5: Commit.**

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/deribit_api_interface.py src/deribridge/__init__.py tests/test_logging_hygiene.py
git commit -m "fix(logging): drop basicConfig from constructor; add opt-in configure_logging()"
```

---

### Task 2.2 (Audit #14): Stop printing from library helpers

**Validated facts:**
- `run_rate_limited_tasks()` prints success/error at `rate_limiter.py:184` and `:203`.
- `TradePlan.from_csv()` prints validation errors and silently drops invalid rows at `trade_plan.py:158-163`.

**Files:**
- Modify: `src/deribridge/api_client/rate_limiter.py:184,203` (module logger)
- Modify: `src/deribridge/classes/trade_plan.py` — `from_csv` (`:148-164`) add `strict` + structured errors
- Test: `tests/test_trade_plan.py` (extend), `tests/test_rate_limiter.py` (extend)

**Step 1: Failing tests.**

```python
# tests/test_trade_plan.py
import pytest
from deribridge.classes.trade_plan import TradePlan

def test_from_csv_strict_raises_on_bad_row(tmp_path):
    p = tmp_path / "plan.csv"
    p.write_text("Instrument,Amount\nBTC-PERPETUAL,notanumber\n")
    with pytest.raises(ValueError):
        TradePlan.from_csv(str(p), strict=True)

def test_from_csv_nonstrict_collects_errors(tmp_path):
    p = tmp_path / "plan.csv"
    p.write_text("Instrument,Amount\nBTC-PERPETUAL,notanumber\nETH-PERPETUAL,1\n")
    plan = TradePlan.from_csv(str(p))          # default non-strict
    assert len(plan.items) == 1
    assert plan.errors and plan.errors[0]["row"] == 1
```

```python
# tests/test_rate_limiter.py  — assert no stdout printing
import asyncio
from deribridge.api_client.rate_limiter import RateLimiter  # adjust import to actual API

def test_run_rate_limited_tasks_does_not_print(capsys):
    # build a trivial successful task set per the module's real signature, run it
    ...  # invoke run_rate_limited_tasks(...) with one no-op task
    out = capsys.readouterr().out
    assert "✓" not in out and "✗" not in out
```

> Adjust the rate-limiter test to the real `run_rate_limited_tasks` signature found at `rate_limiter.py` before writing it.

**Step 2: Run — expect FAIL.**

Run: `uv run python -m pytest tests/test_trade_plan.py tests/test_rate_limiter.py -v`

**Step 3: Implement.**

`rate_limiter.py` — add `logger = logging.getLogger("deribridge.rate_limiter")` at module top (and `import logging`), replace the two `print(...)` calls:

```python
            logger.debug("%s task %s completed in %.3fs", group_name, task_id, elapsed)
            ...
            logger.error("Error in %s task %s: %s", group_name, task_id, e)
```

`trade_plan.py` — give `TradePlan` an `errors` field and rework `from_csv`:

```python
class TradePlan(BaseModel):
    items: List[TradePlanItem]
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_csv(cls, filepath: str, strict: bool = False) -> "TradePlan":
        items: List[TradePlanItem] = []
        errors: List[Dict[str, Any]] = []
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                try:
                    items.append(TradePlanItem.model_validate(row))
                except ValidationError as e:
                    if strict:
                        raise ValueError(f"Invalid trade plan row {i}: {e}") from e
                    errors.append({"row": i, "data": row, "error": e.errors()})
        return cls(items=items, errors=errors)
```

(Add `Field`/`Dict`/`Any` imports as needed.)

**Step 4: Run — expect PASS.**

Run: `uv run python -m pytest tests/test_trade_plan.py tests/test_rate_limiter.py -v`

**Step 5: Commit.**

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/rate_limiter.py src/deribridge/classes/trade_plan.py tests/test_trade_plan.py tests/test_rate_limiter.py
git commit -m "fix: replace prints with logging; from_csv gains strict mode + structured errors"
```

---

### Task 2.3 (Audit #10): Move runnable examples out of package modules

**Validated facts:** `if __name__ == "__main__"` blocks exist in `deribit_api_interface.py:1522`, `client_management.py:103`, `deribit_instrument.py:137`, `classes/order.py:372`. (The audit also named `websocket_api_client.py` — it has **no** such block; ignore that one.) The `deribit_api_interface.py` block **submits a live order**.

**Files:**
- Create: `examples/run_api_interface.py`, `examples/connect_client.py`, `examples/parse_instrument.py`, `examples/build_order.py`, `examples/README.md`
- Modify: remove the `__main__` blocks from the four modules above

**Step 1:** Create `examples/` and move each block's body into a script. For the order-placing example, guard it:

```python
# examples/run_api_interface.py
import os, asyncio
if os.environ.get("DERIBRIDGE_ALLOW_EXAMPLE_ORDERS") != "1":
    raise SystemExit(
        "This example can place a real order. Set DERIBRIDGE_ALLOW_EXAMPLE_ORDERS=1 "
        "and use TESTNET credentials to run it.")
# ... moved body, using deribridge.configure_logging() for log setup ...
```

**Step 2:** Delete the four `if __name__ == "__main__":` blocks from the package modules. Keep modules import-only.

**Step 3:** Verify package import has no side effects and modules still import:

```bash
uv run python -c "import deribridge, deribridge.api_client.deribit_api_interface, deribridge.classes.order, deribridge.api_client.deribit_instrument, deribridge.api_client.client_management; print('ok')"
uv run python -m pytest -q
uv run ruff check src tests examples
```

Expected: `ok`; 58+ pass; ruff clean.

**Step 4:** Reference `examples/` from `README.md` (replace the "fuller runnable example lives in the `__main__` block of ..." line) and commit.

```bash
git add examples src/deribridge README.md
git commit -m "refactor: move runnable examples to examples/; gate order example behind env flag"
```

---

### Task 2.4 (Audit #7 + #8): Governance files

**Files:** Create `SECURITY.md`, `CHANGELOG.md`, `docs/RELEASE_CHECKLIST.md` at repo root/docs.

**Step 1: `SECURITY.md`** — supported versions; private disclosure contact (`dev@elnc.eu`, matching `CONTRIBUTING.md`); expected response timeline; scope examples (auth, credential handling, order submission, order-state reconciliation, market-data integrity); note the package can place real orders.

**Step 2: `CHANGELOG.md`** — Keep-a-Changelog format. `0.1.0` initial beta entry seeded from the removed `sweep-log.md` history (silent-failure redesign, indeterminate-outcome contract, rate-limit hardening, auth validation). Include a **Breaking changes** note for `auto_connect` default flip (Task 1.1) and the `to_typed_result` split (Task 3.2). Add Known limitations: polling-based order tracking, wildcard-channel caveat (until Task 3.1).

**Step 3: `docs/RELEASE_CHECKLIST.md`** — the gate: ruff, pytest, mypy, build, pip-audit, `uv lock --check`, README review, Deribit **testnet** smoke check, tag.

**Step 4:** Commit.

```bash
git add SECURITY.md CHANGELOG.md docs/RELEASE_CHECKLIST.md
git commit -m "docs: add SECURITY.md, CHANGELOG.md, release checklist"
```

---

## Phase 3 — Priority 1: correctness

### Task 3.1 (Audit #11): Fix user wildcard subscription dispatch

**Validated facts:**
- `subscribe_user_orders(None)` → channel `user.orders.*.raw` (`websocket_api_client.py:1408`); `subscribe_user_trades(None)` → `user.trades.*.raw` (`:1426`).
- Dispatch only matches **trailing**-`*` wildcards; a mid-string `*` never fires (`:433`). Documented as a known limitation in `docs/AI_REFERENCE.md:306`.

**Chosen approach (validated):** subscribe to Deribit's real all-user channels that dispatch by **exact match** — `user.orders.any.any.raw` / `user.trades.any.any.raw` — instead of building a mid-string matcher.

**Files:**
- Modify: `src/deribridge/api_client/websocket_api_client.py:1408,1426`
- Modify: `docs/AI_REFERENCE.md:306` (update the limitation note)
- Test: `tests/test_websocket_safety.py` (extend)

**Step 1: Failing test** — `subscribe_user_orders(None)` registers an exact-match channel and the dispatcher routes a matching update to the callback.

```python
@pytest.mark.asyncio
async def test_subscribe_user_orders_all_users_dispatches(monkeypatch):
    client = DeribitWebSocketClient(client_id="x", client_secret="y")  # auto_connect now False
    sent = {}
    async def fake_subscribe(channel, cb):
        client.callback_handlers[channel] = cb  # mimic real registration
        sent["channel"] = channel
        return {"ok": True}
    monkeypatch.setattr(client, "subscribe", fake_subscribe)
    hits = []
    await client.subscribe_user_orders(None, callback=lambda m: hits.append(m))
    assert sent["channel"] == "user.orders.any.any.raw"
    # an incoming update on that exact channel must reach the callback
    await client._dispatch_subscription("user.orders.any.any.raw", {"foo": 1})  # use real dispatch entrypoint name
    assert hits
```

> Replace `_dispatch_subscription` with the actual dispatch method name found near `websocket_api_client.py:433`.

**Step 2: Run — expect FAIL.**

Run: `uv run python -m pytest tests/test_websocket_safety.py -k user_orders_all_users -v`

**Step 3: Implement** — change the two channel templates:

```python
        channel = f"user.orders.{instrument_name}.raw" if instrument_name else "user.orders.any.any.raw"
        ...
        channel = f"user.trades.{instrument_name}.raw" if instrument_name else "user.trades.any.any.raw"
```

**Step 4: Run — expect PASS.**

**Step 5:** Update `docs/AI_REFERENCE.md:306` to note all-user subscriptions now use exact-match `*.any.any.raw` channels (remove the "never fires" caveat for this case), and commit.

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/websocket_api_client.py docs/AI_REFERENCE.md tests/test_websocket_safety.py
git commit -m "fix(ws): route all-user order/trade subscriptions via exact-match any.any channels"
```

---

### Task 3.2 (Audit #13): Split `to_typed_result` / `to_typed_list`

**Validated facts:** `DeribitResultResponse.to_typed_result()` is annotated `-> T` but returns `list[T]` for list results, with `# type: ignore` (`deribit_response_models.py:114-130`).

**Files:**
- Modify: `src/deribridge/api_client/deribit_response_models.py:114-130`
- Update callers: `grep -rn "to_typed_result" src tests`
- Test: `tests/test_response_models.py` (extend)

**Step 1: Failing tests.**

```python
# tests/test_response_models.py
def test_to_typed_result_rejects_list():
    resp = DeribitResultResponse(raw_response={"result": [{"a": 1}, {"a": 2}]})
    with pytest.raises(TypeError):
        resp.to_typed_result(SomeModel)

def test_to_typed_list_returns_list():
    resp = DeribitResultResponse(raw_response={"result": [{"a": 1}, {"a": 2}]})
    out = resp.to_typed_list(SomeModel)
    assert isinstance(out, list) and len(out) == 2
```

**Step 2: Run — expect FAIL.**

**Step 3: Implement** — single-object `to_typed_result` (raises on list) + new `to_typed_list`:

```python
    def to_typed_result(self, model_class: type[T]) -> T:
        """Convert a single-object result to a typed model. Use to_typed_list for arrays."""
        if self.result is None:
            raise ValueError("Response contains no result")
        if isinstance(self.result, list):
            raise TypeError("Result is a list; call to_typed_list() instead")
        if hasattr(model_class, "from_dict"):
            return model_class.from_dict(self.result)  # type: ignore[no-any-return]
        return model_class(**self.result)

    def to_typed_list(self, model_class: type[T]) -> list[T]:
        """Convert a list result to a list of typed models."""
        if self.result is None:
            raise ValueError("Response contains no result")
        if not isinstance(self.result, list):
            raise TypeError("Result is not a list; call to_typed_result() instead")
        if hasattr(model_class, "from_dict"):
            return [model_class.from_dict(item) for item in self.result]
        return [model_class(**item) for item in self.result]
```

**Step 4:** Update every caller from `grep` to use `to_typed_list` where the endpoint returns an array (e.g. instrument lists). Run mypy to confirm the `type: ignore` count dropped.

**Step 5: Run — expect PASS** + `uv run --with mypy -- mypy src`.

**Step 6: Commit** (note the breaking change in `CHANGELOG.md`).

```bash
uv run python -m pytest -q
git add src/deribridge/api_client/deribit_response_models.py tests/test_response_models.py CHANGELOG.md
git commit -m "refactor(models): split to_typed_result (object) from to_typed_list (array)"
```

---

### Task 3.3 (Audit #15): Tighten CI

**Validated facts:** `.github/workflows/ci.yml` runs ruff + pytest + build smoke. `mypy` is not in the dev group (`pyproject.toml:60-64`).

**Files:**
- Modify: `pyproject.toml` dev group (add `mypy`, `pip-audit`)
- Modify: `.github/workflows/ci.yml`

**Step 1:** Add to the dev group:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
    "mypy>=1.10",
    "pip-audit>=2.7",
]
uv lock
```

**Step 2:** In `ci.yml` test job add steps after the existing lint/test:

```yaml
      - run: uv run mypy src
      - run: uv run pip-audit
      - run: uv lock --check
```

(Coverage on order-mutating paths is optional polish — add `pytest --cov=deribridge` if the team wants a gate.)

**Step 3:** Validate locally as CI would.

```bash
uv run mypy src && uv run pip-audit && uv lock --check && uv run python -m pytest -q
```

**Step 4: Commit.**

```bash
git add pyproject.toml uv.lock .github/workflows/ci.yml
git commit -m "ci: add mypy, pip-audit, and lockfile check"
```

---

## Phase 4 — Priority 2 polish (pre-publish; mostly docs/metadata)

These are non-blocking. Do them as small commits; no TDD red/green needed for pure docs.

- **Task 4.1 (Audit #16): Integration-test scaffold.** Create `tests/integration/` gated by `DERIBRIDGE_RUN_INTEGRATION=1`: public endpoints (no creds), authenticated read-only (testnet creds), order placement disabled by default behind a second flag. Skip-collect when the env var is unset.
- **Task 4.2 (Audit #17): Installation docs.** `README.md` install section → `pip install deribridge` (or `pip install git+https://github.com/fracasamax/deribridge.git` until PyPI); keep editable install under a "Development" heading.
- **Task 4.3 (Audit #20): Beta API-stability note** in `README.md` — `0.x` may change public names/return types; high-level trading helpers are beta.
- **Task 4.4 (Audit #19): Roadmap** — `docs/ROADMAP.md`: testnet integration suite; subscription-driven order tracker (0.2.0, see Deferred); more exchanges; analytics primitives; `1.0` stabilization goals.
- **Task 4.5 (Audit #23): Compatibility notes** — `README.md`/`docs`: Deribit WS JSON-RPC v2, testnet/prod endpoints, supported Python versions, known-unsupported features, "Deribit API changes may require updates".
- **Task 4.6 (Audit #24): Metadata** — `pyproject.toml` classifiers: add `Programming Language :: Python :: 3 :: Only`; consider `Development Status :: 3 - Alpha`; add a `Documentation` URL if docs get hosted.
- **Task 4.7 (Audit #22): Issue templates** — `.github/ISSUE_TEMPLATE/`: bug report, API endpoint/model mismatch, order-safety incident, feature request, docs issue.
- **Task 4.8 (Audit #21): `uv.lock` decision** — it is currently tracked. Either keep it (and CI checks it via Task 3.3 — recommended) or untrack via `.gitignore`. Record the decision in `CONTRIBUTING.md`.
- **Task 4.9 (Audit #18): Finish deribook positioning** — audit the in-flight edits across `README.md`, `docs/GUIDE.md`, `docs/AI_REFERENCE.md`, `src/deribridge/__init__.py` for consistency (one canonical tagline), ensure mentions stay factual/secondary. Add the "From bridge to analytics" example if desired.

Commit each task separately, e.g. `docs: <task>` / `chore(meta): <task>`.

---

## Deferred to 0.2.0 (NOT in this plan)

- **Audit #12: Event-first order tracking.** Replace the ~2s polling loop (`_monitor_orders_and_positions`, `deribit_api_interface.py:618,626,642`; iceberg fill-wait `:1458`) with `user.orders`/`user.trades` subscription ingestion, keeping polling as reconciliation fallback. This is an architectural change, not a publication blocker; 0.1.0 ships with the documented polling limitation (`docs/AI_REFERENCE.md` §7).

---

## Final gate before tagging 0.1.0

Use @superpowers:verification-before-completion. Run and read every output:

```bash
uv run ruff check src tests examples
uv run python -m pytest -q
uv run mypy src
uv run --with build python -m build
uv run --with pip-audit -- pip-audit
uv lock --check
```

Then: README/CHANGELOG review, a Deribit **testnet** smoke check (public + authenticated read-only), and `git tag v0.1.0`. Merge `release-hardening` per @superpowers:finishing-a-development-branch.

---

## Task summary (mapping to audit numbers)

| Phase | Tasks | Audit items |
|---|---|---|
| 0 | Worktree + baseline | (setup) |
| 1 | 1.1–1.5 | #3, #4, #5, #2, #1, #6 |
| 2 | 2.1–2.4 | #9, #14, #10, #7, #8 |
| 3 | 3.1–3.3 | #11, #13, #15 |
| 4 | 4.1–4.9 | #16, #17, #20, #19, #23, #24, #22, #21, #18 |
| Deferred | — | #12 |
