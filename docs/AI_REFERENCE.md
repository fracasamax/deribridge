# deribridge — Technical Reference for AI Coding Agents

> Maintained by **Francesco Casamassima** (dev@elnc.eu). `deribridge` is the open-source client layer powering **deribook** (https://deribook.com) — real-time stats and advanced analytics for Deribit derivatives portfolios.

This document is written for an LLM/agent that will read it as context and then generate code against `deribridge`. It states the library's contracts, invariants, and gotchas precisely. Everything below is grounded in the current source (`src/deribridge/`, package version `0.1.0`). Prefer the exact symbol names and signatures given here over assumptions.

`deribridge` is an **async, typed Python client + middleware** for the [Deribit](https://docs.deribit.com) crypto-derivatives exchange WebSocket API (JSON-RPC 2.0 over `wss://`). All network-facing methods are coroutines and MUST be `await`ed inside a running event loop.

---

## 1. Overview & architecture

Three layers, each subclass/wrapper of the one below:

```
                 application code (your trading tooling)
                                |
   ┌────────────────────────────────────────────────────────┐
   │  DeribitAPIInterface           (high-level interface)    │
   │  - configure() / start_client() / stop_client()         │
   │  - OrderTracker, RiskManager, MarketDataCache           │
   │  - submit_order / submit_limit_order / cancel_order /   │
   │    replace_order  → 3-outcome contract                  │
   │  - background _monitor_orders_and_positions task        │
   └────────────────────────────────────────────────────────┘
                                | wraps / holds a
   ┌────────────────────────────────────────────────────────┐
   │  EnhancedDeribitClient(DeribitWebSocketClient)          │
   │  - *_model / *_value typed wrappers around raw methods  │
   │  - returns dataclass models instead of dicts            │
   └────────────────────────────────────────────────────────┘
                                | extends
   ┌────────────────────────────────────────────────────────┐
   │  DeribitWebSocketClient        (transport)              │
   │  - connect / authenticate / send_request / subscribe   │
   │  - connection lock, auth gate, reconnect, heartbeat    │
   │  - O(1) channel dispatch                                │
   └────────────────────────────────────────────────────────┘
                                |
                       wss://www.deribit.com/ws/api/v2  (or test.deribit.com)
```

- **`DeribitWebSocketClient`** (`websocket_api_client.py`): raw transport. Every method returns the raw JSON-RPC `result` (`dict`/`list`/scalar). Owns the socket, the connection lock, the authentication state machine, reconnect/heartbeat/token-refresh background tasks, and subscription dispatch.
- **`EnhancedDeribitClient`** (`enhanced_api_client.py`): subclass that adds `*_model` / `*_value` methods returning typed dataclass models (see §6). The raw methods remain available (inherited).
- **`DeribitAPIInterface`** (`deribit_api_interface.py`): the recommended entry point. Holds an `EnhancedDeribitClient` (`self.client`), adds order-lifecycle tracking (`OrderTracker`), risk circuit breakers (`RiskManager`), a TTL market-data cache (`MarketDataCache`), local rate limiting, callbacks, and the **3-outcome order contract** (§4).

For most tooling, instantiate `DeribitAPIInterface`. Drop to `EnhancedDeribitClient` / `DeribitWebSocketClient` only when you need methods the interface does not re-expose (most read-only market/account endpoints live on the client; call them via `interface.client.<method>`).

---

## 2. Public API surface (`deribridge.__all__`)

Enumerated from the live import (`uv run python -c "import deribridge; print(sorted(deribridge.__all__))"`). 49 names. Note the **alias collisions**: several names are deliberately re-exported under suffixed names because two layers define a same-named type.

### Clients & interfaces
| Name | Purpose |
|------|---------|
| `DeribitWebSocketClient` | Low-level async WebSocket transport; raw dict/list results. |
| `EnhancedDeribitClient` | Subclass adding typed `*_model`/`*_value` wrappers. |
| `DeribitAPIInterface` | High-level interface: order tracking, risk, caching, 3-outcome order contract. **Recommended entry point.** |
| `DeribitInstrument` | Instrument-name parser/helper (e.g. parse `"BTC-31JAN25-100000-C"`). |
| `RateLimiter` | Token-bucket async rate limiter (see §5). |

### Response models (dataclasses, from `deribit_response_models.py`)
| Name | Purpose |
|------|---------|
| `DeribitBaseResponse` | Base of the raw-response wrapper hierarchy; `from_dict` dispatches by shape. |
| `DeribitResultResponse` | A successful `result` response; `.result`, `.to_typed_result(Model)`. |
| `DeribitErrorResponse` | An `error` response; `.error_code`, `.error_message`, `.error_data`. |
| `DeribitSubscriptionResponse` | A subscription update; `.channel`, `.data`, `.to_typed_data(Model)`. |
| `DeribitResponseType` | Enum: `RESULT` / `SUBSCRIPTION` / `ERROR`. |
| `Order` | Comprehensive **received-order** dataclass (exchange shape). NOT the submission model — see `OrderClass`. |
| `OrderBook` | Full order-book / ticker-shaped snapshot with `best_bid/ask`, `spread`, `mid_price`. |
| `OrderBookEntry` | One `[price, amount]` (or `[action, price, amount]`) book level. |
| `Position` | Open position with greeks, margins, PnL helpers. |
| `Trade` | Single trade/fill. |
| `Ticker` | Ticker snapshot; `spread`/`mid_price` return `None` on a one-sided book. |
| `BookSummary` | Per-instrument book summary. |
| `Instrument` | Instrument metadata (tick size, expiry, kind, greeks-relevant flags). |
| `Greeks` | `delta/gamma/rho/theta/vega`. |
| `Stats` | 24h `high/low/volume/...`. |
| `IndexPriceResponse` | `index_price`, `estimated_delivery_price`. |
| `FundingRateValue` | Funding-rate value with instrument/time context. |
| `TickSizeStep` | A `(above_price, tick_size)` step. |
| `AccountSummary` | One-currency account summary with margin/PnL helper properties. |
| `AccountSummaries` | Multi-currency wrapper (`.summaries`, `.get_summary_by_currency`). |
| `AccountFee` | Maker/taker fee row. |
| `OrderSubmitResponse` | Result of submit: `.order: Order`, `.trades: List[Trade]`. |
| `OrderCancelResponse` | Result of cancel: `.order`, `.error`, `.is_successful`. |
| `TransactionLogEntry` | One transaction-log row. |
| `TransactionLogResponse` | `.logs`, `.continuation`, `.has_more`. |

### Domain classes & enums (from `classes/`)
| Name | Kind | Purpose |
|------|------|---------|
| `OrderClass` (alias of `classes.Order`) | Pydantic `BaseModel` | **Order-submission model.** This is what you build and pass to `submit_order`. |
| `InstrumentClass` (alias of `classes.Instrument`) | class | Instrument domain object used by Deribit instrument parsing. |
| `Currency` | `Enum` | `BTC, ETH, USDC, USDT, EURR, SOL, XRP, PAXG, BNB, USDE, STETH, ETHW, USYC`. |
| `InstrumentType` | `Enum` | `SPOT, FUTURE, OPTION`. |
| `OptionType` | `Enum` | `CALL="C"`, `PUT="P"`. |
| `OrderPurpose` | `str, Enum` | `BUY="buy"`, `SELL="sell"`; `.opposite()`, `.direction_multiplier()`. |

### Model types & enums (from `models/`)
| Name | Kind | Purpose |
|------|------|---------|
| `OrderModel` (alias of `models.Order`) | dataclass | Lightweight received-order dataclass used by `get_open_orders`. |
| `OrderBookModel` (alias of `models.OrderBook`) | dataclass | Alternate order-book model. |
| `CurrencyModel` (alias of `models.Currency`) | `Enum` | Currency enum used by the models layer. |
| `OrderState` | `str, Enum` | `OPEN, FILLED, REJECTED, CANCELLED, UNTRIGGERED`; `.is_active()`, `.is_terminal()`. |
| `OrderType` | `str, Enum` | `LIMIT, STOP_LIMIT, TAKE_LIMIT, MARKET, STOP_MARKET, TAKE_MARKET, MARKET_LIMIT, TRAILING_STOP`; `.is_market()`, `.is_limit()`, `.is_conditional()`, `.requires_price()`, `.requires_trigger_price()`. |
| `TimeInForce` | `str, Enum` | `GOOD_TIL_CANCELLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL`; accepts `"GTC"/"FOK"/"IOC"` shorthands via its validator. |
| `InstrumentKind` | `Enum` | `FUTURE, OPTION, SPOT, FUTURE_COMBO, OPTION_COMBO, COMBO, ANY`. |
| `Interval` | `Enum` | `AGG2="agg2"`, `MS100="100ms"`, `RAW="raw"`. |
| `TradeModel` (alias of `models.Trade`) | dataclass | Models-layer trade dataclass. |

### Errors
| Name | Purpose |
|------|---------|
| `DeribitWebSocketError` | Raised on API errors and transport faults. Carries `.code: int`, `.message: str`, `.short_message`, `.data`. **A timeout is encoded as `code == -1`.** |
| `DeribitError` | Error-code lookup helper (`deribit_error_codes`). |
| `IndeterminateOrderError` | Raised by order methods when the outcome is **unknown** (timeout/disconnect mid-flight). Carries `.operation`, `.order_id`, `.cause`. See §4 — this is the most important error to handle. |

**Naming traps for code generation:**
- `Order` (top-level export) is the **received-order dataclass** from `deribit_response_models`, *not* the submission model. To build an order to submit, import the alias **`OrderClass`** (`from deribridge import OrderClass`) — that is the Pydantic submission model from `classes/order.py`.
- `OrderType` / `TimeInForce` / `OrderState` enums exported at top level come from the **`models/`** package (these are the ones `classes/order.py` actually imports and uses).

---

## 3. Lifecycle & concurrency model

Everything is `asyncio`. There is no sync API. All client/interface I/O methods are coroutines.

### Standard interface lifecycle
```python
api = DeribitAPIInterface.configure(use_test_env=True)   # classmethod factory, not async
ok = await api.start_client()                            # connect (+authenticate if creds), returns bool
# ... use api ...
await api.stop_client()                                  # cancels monitoring, unsubscribes, closes
```

- `DeribitAPIInterface.configure(...)` is a **classmethod factory** (not async). If neither `client` nor `client_id` is given, it reads credentials from env vars: `DERIBIT_API_CLIENT_ID[_TEST]` and `DERIBIT_API_SECRET[_TEST]` (the `_TEST` suffix is appended when `use_test_env=True`). **Default `use_test_env=True` on `configure`** (vs `False` on the raw constructors) — set it explicitly.
- `start_client()` connects, waits up to 5s for `connected`, authenticates if credentials are present, sets `is_running=True`, and **spawns the background `_monitor_orders_and_positions` task**. Returns `False` (does not raise) on connect/auth failure.
- `stop_client()` cancels the monitoring task, unsubscribes from all tracked channels, closes the socket. Returns `bool`.

### Connection lock + authenticated-gate invariant
The transport holds a single `asyncio.Lock` (`_connection_lock`). The guarantees you can rely on:

1. **Connect→resubscribe→authenticate is atomic.** `connect()` performs the entire sequence while holding the lock, so the `authenticated` flag and the live socket are published together. A concurrent reconnect cannot observe a half-open socket.
2. **Private sends are gated.** In `send_request(..., auth_required=True)`, after ensuring authentication the client re-checks `connected and authenticated` *under the lock*; if a reconnect/re-auth window is in progress it **raises `DeribitWebSocketError(code=-1, ...)` rather than sending**. Consequence: during reconnection, private requests (including order ops) can raise — your code must handle this (see §4; it manifests as an indeterminate outcome for order methods).
3. `authenticate()` acquires the lock and validates the response: it only sets `authenticated=True` if a non-empty `access_token` and `expires_in > 0` are present. Bad credentials raise and do **not** trigger an auto-reconnect loop (transport-level errors do reconnect).

### Background tasks
- **Heartbeat loop** — sends `public/test` every `heartbeat_interval` (default 30s).
- **Auth-refresh loop** — refreshes the token at ~70% of its lifetime (min 60s); re-reads the clock after sleeping; falls back to full re-auth if the refresh token expired.
- **Reconnect** — exponential backoff with jitter, capped at 60s; resubscribes and re-authenticates on success.
- **Monitoring task** (interface only) — polls order states and account/positions every ~2s (see §7, gotcha). Has a done-callback that logs failures and restarts the task while `is_running and connected`.

### Request timeout
Every `send_request` waits at most **30s** for its reply; on timeout it pops the pending future and raises `DeribitWebSocketError(-1, "Request timed out: <method>")`. This `-1` code is exactly what the order layer treats as **indeterminate**.

---

## 4. Order semantics — THE critical contract

`submit_order`, `submit_limit_order`, `cancel_order`, and `replace_order` on `DeribitAPIInterface` have **three distinct outcomes**. Treating "no exception" as success, or `None` as "definitely failed and safe to retry" without distinguishing the indeterminate case, will eventually duplicate live orders. Handle all three.

| Outcome | Signal | Meaning | Correct action |
|---------|--------|---------|----------------|
| **(a) Success** | Returns a typed/object result (`OrderSubmitResponse`, `OrderCancelResponse`, or a `dict` for `replace_order`) | The exchange accepted and acknowledged the operation. | Use the result. For submit, the order id is `resp.order.order_id`. |
| **(b) Definite failure** | Returns **`None`** | The request was rejected, blocked by the local risk manager, or never sent — the exchange did **not** act on it. | Safe to retry / treat as not-done. |
| **(c) Indeterminate** | **Raises `IndeterminateOrderError`** | The request timed out or the socket dropped mid-flight. The exchange *may or may not* have received/applied it. Outcome unknown. | **Do NOT blindly retry.** Catch it, then **reconcile** real state via `get_order_state` / `get_open_orders` before deciding. |

What counts as indeterminate is decided by `_is_indeterminate_error`: `asyncio.TimeoutError`, `ConnectionError`, `websockets.exceptions.ConnectionClosed`, or a `DeribitWebSocketError` whose `.code == -1` (the timeout sentinel). Any other exception is logged and collapsed to the definite-failure `None` path.

`IndeterminateOrderError` attributes:
- `.operation: str` — `"submit_order"`, `"cancel_order"`, or `"replace_order"`.
- `.order_id: Optional[str]` — the id involved if known; **`None` for new submissions** (no id had been assigned yet — this is the dangerous case: you must reconcile by instrument/label, not by id).
- `.cause: Optional[BaseException]` — the underlying exception (chained via `raise ... from`).

### Method signatures (interface layer)
```python
async def submit_order(self, order: OrderClass, check_risk: bool = True) -> Optional[OrderSubmitResponse]
async def submit_limit_order(self, instrument_name: str, side: str, amount: float, price: float,
                             post_only: bool = True, time_in_force: str = "good_til_cancelled",
                             reduce_only: bool = False, client_id: Optional[str] = None
                             ) -> Optional[OrderSubmitResponse]
async def cancel_order(self, order_id: str) -> Optional[OrderCancelResponse]
async def replace_order(self, order_id: str, price: float, amount: Optional[float] = None,
                        post_only: Optional[bool] = None) -> Optional[Dict[str, Any]]
```
- `submit_limit_order` raises `ValueError` if `side` is not `"buy"`/`"sell"`. `client_id` maps to the order `label`.
- `submit_order` accepts an `OrderClass` (the Pydantic submission model). With `check_risk=True` (default), an order blocked by the local `RiskManager` returns `None` (outcome b) — it never reached the exchange.
- On success of `submit_order`, the order is registered in the local `OrderTracker` keyed by `resp.order.order_id`.

### REQUIRED reconciliation pattern
```python
from deribridge import DeribitAPIInterface, IndeterminateOrderError, OrderClass

async def place_limit_safely(api: DeribitAPIInterface, instrument: str, side: str,
                             amount: float, price: float, label: str):
    try:
        resp = await api.submit_limit_order(
            instrument_name=instrument, side=side, amount=amount,
            price=price, post_only=True, client_id=label,
        )
    except IndeterminateOrderError as e:
        # Outcome (c): the order MAY be live. Never re-submit blindly.
        # Reconcile against the exchange. The submission had no id, so match by
        # label/instrument among open orders (and recent trades if needed).
        open_orders = await api.get_open_orders()  # List[OrderModel]
        existing = [o for o in open_orders
                    if o.instrument_name == instrument and o.label == label]
        if existing:
            return existing[0]          # it DID land; adopt it, do not resubmit
        # Not found open — it may still have filled. Check fills/positions before
        # resubmitting; only resubmit once you are sure nothing landed.
        raise  # or perform a deliberate, idempotent retry after reconciliation

    if resp is None:
        # Outcome (b): definite failure (rejected / risk-blocked / not sent). Retry is safe.
        return None

    # Outcome (a): success.
    return resp.order  # resp.order.order_id is the exchange id
```

For `cancel_order` indeterminate, reconcile with `await api.client.get_order_state(order_id)` — the order may already be gone or may still be live. For `replace_order` indeterminate, the amend may or may not have applied; check `get_order_state` / `get_open_orders` before retrying (a blind retry can double-amend).

---

## 5. Rate limiting

Two mechanisms exist; do not confuse them.

1. **`DeribitAPIInterface._wait_for_rate_limit()`** (internal) — a lock-guarded sliding-window limiter (default 10 req/s) automatically applied before the interface's own API calls. You don't call it directly.

2. **`RateLimiter` + `run_rate_limited_tasks` + `TaskGroup[T]`** (`rate_limiter.py`) — public helpers for batching your own concurrent calls under a shared token bucket.

```python
class RateLimiter:
    def __init__(self, rate_limit: int): ...        # tokens/second
    async def acquire(self) -> None: ...            # await before each rate-limited op

class TaskGroup(Generic[T]):                        # results/errors indexed by INPUT position
    def get_result(self, task_id: int | str) -> Optional[T]: ...
    def get_error(self, task_id: int | str) -> Optional[Exception]: ...

async def run_rate_limited_tasks(
    task_groups: Dict[str, List[Tuple[Callable[..., Awaitable[T]], Dict[str, Any]]      # (fn, kwargs)
                               | Tuple[Callable[..., Awaitable[T]], Dict[str, Any], str]]],  # (fn, kwargs, name)
    rate_limit: int = 5,
    error_handler: Optional[Callable[[str, Exception], None]] = None,
) -> Dict[str, TaskGroup[T]]: ...
```

**Index mapping guarantee (do not get this wrong):** results and errors are **keyed by the task's ORIGINAL input index**, not completion order. `group.get_result(2)` returns the result of the 3rd task you supplied, even if it finished first or last. Named tasks (3-tuples) are also retrievable by name via `get_result("name")`. Each task's exception is captured into `group.get_error(index)` and the result slot is set to `None`; `run_rate_limited_tasks` itself does not raise on individual task failures.

```python
groups = await run_rate_limited_tasks(
    {"tickers": [
        (api.get_ticker, {"instrument_name": "BTC-PERPETUAL"}, "btc"),
        (api.get_ticker, {"instrument_name": "ETH-PERPETUAL"}, "eth"),
    ]},
    rate_limit=5,
)
btc_ticker = groups["tickers"].get_result(0)        # or .get_result("btc")
err = groups["tickers"].get_error(0)                # None if it succeeded
```

---

## 6. Typed models & enums

### Two model styles
- **Response/result models** in `deribit_response_models.py` are **`@dataclass`** types with a classmethod **`from_dict(data)`** that defensively `.get(...)`s every field with safe defaults (missing fields don't raise). Optional fields are `None`. Timestamps are integer ms-since-epoch; several models expose `.datetime`/`*_datetime` properties that divide by 1000.
- **Submission/domain models** in `classes/order.py` (`OrderClass`, `OrderType`, `TimeInForce`) are **Pydantic v2 `BaseModel`/`str, Enum`**. `OrderClass` validates on construction: it requires `amount` *or* `contracts`, requires `price` for limit-family types, requires `trigger_price` for stop/take types, and auto-sets `created_at`. Serialization uses `ConfigDict(populate_by_name=True, str_strip_whitespace=True, validate_assignment=True)` and a `@field_serializer` that renders `created_at` to ISO-8601. (Pydantic-v1-style `Config`/`json_encoders` have been removed in favor of `ConfigDict` + `@field_serializer`.)

### Building & submitting an order
`OrderClass` has **defaults for every field except `instrument_name` and `purpose`**, so positional-arg type checkers may misflag construction — the library scopes a `# type: ignore[call-arg]` at its own call site. Prefer the convenience constructors when generating code:
```python
from deribridge import OrderClass            # the Pydantic submission model
order = OrderClass.limit_buy("BTC-PERPETUAL", amount=0.1, price=50000, post_only=True)
# also: OrderClass.limit_sell / market_buy / market_sell
await api.submit_order(order)
```
`order.api_params()` is what gets sent: it drops `None` values and strips tracking-only fields (`created_at, order_id, order_state, filled_amount, average_price, last_update_timestamp`). The raw `DeribitWebSocketClient.submit_order` normalizes enum-or-string `purpose`/`order_type`/`time_in_force` to their wire string, routes to `private/buy` or `private/sell` (from `purpose`), and sets `direction` accordingly.

### Raw → typed conversion via `to_typed_result`
`DeribitResultResponse.to_typed_result(model_class)` and `DeribitSubscriptionResponse.to_typed_data(model_class)` convert a raw `result`/`data` into a model (using `model_class.from_dict` if present, else `model_class(**item)`). The `*_model` methods on `EnhancedDeribitClient` do this for you, e.g. `get_ticker_model` → `Ticker`, `get_order_book_model` → `OrderBook`, `get_positions_model` → `List[Position]`, `get_account_summary_model` → `AccountSummary`, `cancel_order_model` → `OrderCancelResponse`.

**Footgun:** `to_typed_result` is annotated `-> T` (a single model) but **returns a `list` when the underlying `result` is a JSON array**. Its type signature lies for list results. When you call a raw method that returns a list and want models, **do not** rely on `to_typed_result`'s declared type — use an explicit comprehension instead:
```python
items = [Instrument.from_dict(x) for x in raw_list]   # correct for lists
```
The library's own list-returning wrappers already use comprehensions (`get_instruments_model`, `get_positions_model`, etc.); follow that pattern.

---

## 7. Gotchas & known limitations

Known limitations from the current implementation. An agent must NOT rely on behavior that isn't there.

1. **Order/position monitoring POLLS, it does not stream.** `_monitor_orders_and_positions` (and the iceberg fill-wait loop) call `private/get_order_state` on a ~2s timer rather than consuming the `user.orders` subscription. So `OrderTracker` / `on_order_update` updates are **delayed by polling latency**, not real-time. If you need low-latency fills, subscribe to `user.orders`/`user.trades` yourself via `EnhancedDeribitClient.subscribe_user_orders_model` / `subscribe_user_trades_model` and drive your own state.

2. **Mid-string wildcard channels are NOT matched.** Subscription dispatch is O(1) exact-match plus a small set of **trailing-`*`** prefix matchers. A channel registered as `user.orders.any.any.raw` (wildcard in the middle) will **never** fire its callback — only suffix wildcards like `user.orders.BTC-PERPETUAL.*` are matched (by prefix). The built-in `subscribe_user_orders(instrument_name=None)` constructs `user.orders.any.any.raw`, which falls into this unmatched mid-string case. To receive per-instrument user-order updates reliably, subscribe with a concrete instrument name (yielding an exact channel) rather than relying on the `*` form.

3. **`to_typed_result` list footgun** — see §6. Declared `-> T`; returns a `list` for array results. Use comprehensions for lists.

4. **PnL in the monitor is a placeholder.** When the monitor sees a `filled` order it records `0.0` PnL into `RiskManager` (no cost-basis wiring). Do not trust `RiskManager.daily_pnl` / sequential-loss circuit breakers as a real PnL signal.

5. **`replace_order` returns the raw `dict`, not a model.** The new order is under `result["order"]` (Deribit shape). The tracker is updated, but the return value is an unwrapped dict — parse it yourself if you need a typed `Order`.

6. **Definite-failure methods swallow errors and return `None`.** `close_position`, `cancel_all_orders`, `get_positions`, `get_open_orders`, `get_ticker`, `get_order_book` log and return `None`/`[]` on error rather than raising. `close_all_positions` correctly reports `success=False` when `close_position` returns `None` (it does not falsely claim success), but you must inspect each per-instrument result.

7. **`get_ticker` / `get_order_book` on the interface are cached** (`MarketDataCache`, 1s TTL). A returned value can be up to ~1s stale. For a fresh read bypass the cache via `await api.client.get_ticker_model(...)`.

8. **`Ticker.spread` / `Ticker.mid_price` return `None`** when either side of the book is missing (one-sided book). Always None-check before arithmetic.

9. **`configure(use_test_env=...)` defaults to `True`**, but the raw `DeribitWebSocketClient`/`EnhancedDeribitClient`/`DeribitAPIInterface.__init__` default to `False`. Be explicit about which environment you want.

10. **Submitted-order id can be absent on success.** If a submit reports success but yields no `order.order_id`, downstream tracking/polling is impossible; the iceberg helper logs and skips such slices rather than passing a `None` id to `get_order_state`. Check `resp.order and resp.order.order_id` before using the id.

---

## 8. Idiomatic end-to-end example

A complete, compilable async flow: configure → start → subscribe → submit a limit order with full three-outcome handling → cancel → stop. Assumes `DERIBIT_API_CLIENT_ID_TEST` / `DERIBIT_API_SECRET_TEST` are set in the environment.

```python
import asyncio
import logging

from deribridge import (
    DeribitAPIInterface,
    IndeterminateOrderError,
    Ticker,
)


async def main() -> None:
    api = DeribitAPIInterface.configure(use_test_env=True, log_level=logging.INFO)

    started = await api.start_client()      # connect + authenticate; returns bool (does not raise)
    if not started:
        raise SystemExit("failed to connect/authenticate")

    try:
        instrument = "BTC-PERPETUAL"

        # Real-time ticker callback (typed Ticker objects).
        def on_ticker(name: str, t: Ticker) -> None:
            print(f"{name} mark={t.mark_price} mid={t.mid_price}")  # mid may be None
        api.on_ticker_update = on_ticker
        await api.subscribe_to_ticker(instrument)

        # Snapshot read (cached up to ~1s); for a fresh read use api.client.get_ticker_model(...).
        ticker = await api.get_ticker(instrument)
        ref_price = ticker.mark_price if ticker else 20000.0
        price = round(ref_price * 0.90, 1)   # well below market so it rests (post-only)
        label = "demo-1"

        # ---- Submit with the mandatory 3-outcome handling ----
        order_id = None
        try:
            resp = await api.submit_limit_order(
                instrument_name=instrument, side="buy",
                amount=10, price=price, post_only=True, client_id=label,
            )
        except IndeterminateOrderError as e:        # (c) outcome UNKNOWN — reconcile, never blind-retry
            print(f"INDETERMINATE {e.operation}: {e}; reconciling…")
            open_orders = await api.get_open_orders()
            match = next((o for o in open_orders
                          if o.instrument_name == instrument and o.label == label), None)
            order_id = match.order_id if match else None
            # If still unknown, also check fills/positions before any resubmission.
        else:
            if resp is None:                        # (b) definite failure — safe to retry
                print("submit failed definitively (rejected / risk-blocked / not sent)")
            elif resp.order and resp.order.order_id:  # (a) success
                order_id = resp.order.order_id
                print(f"order live: {order_id}")

        # ---- Cancel (same 3-outcome shape) ----
        if order_id:
            try:
                cancel = await api.cancel_order(order_id)
            except IndeterminateOrderError as e:
                state = await api.client.get_order_state(e.order_id or order_id)
                print(f"cancel indeterminate; current state={state.get('order_state')}")
            else:
                if cancel is None:
                    print("cancel failed definitively")
                elif cancel.is_successful:
                    print(f"cancelled {cancel.order_id}")
    finally:
        await api.stop_client()


if __name__ == "__main__":
    asyncio.run(main())
```

---

*Maintained by Francesco Casamassima (dev@elnc.eu). `deribridge` is the open-source client layer powering [deribook](https://deribook.com) — real-time stats and advanced analytics for Deribit derivatives portfolios.*
