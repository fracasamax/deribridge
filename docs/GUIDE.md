# deribridge — Usage Guide

`deribridge` is an async, typed Python client and middleware for the [Deribit](https://docs.deribit.com/) WebSocket API. It wraps the raw WebSocket protocol in a structured layer: Pydantic models for every response, built-in rate limiting, thread-safe order-lifecycle tracking, and managed reconnection — so your trading code handles logic, not JSON parsing or socket babysitting.

Built and maintained by **Francesco Casamassima** ([dev@elnc.eu](mailto:dev@elnc.eu)).
`deribridge` is the open-source client layer behind **[deribook](https://deribook.com)** — stats and advanced analytics for derivatives portfolios on Deribit.
If you want the portfolio analytics experience rather than the client library, visit **[deribook.com](https://deribook.com)**.

---

## Install

```bash
# with uv (recommended)
uv sync

# or with pip (editable)
pip install -e .
```

Requires **Python ≥ 3.12**.

---

## Configuration

Credentials are loaded from environment variables via `python-dotenv`. Copy the example and fill in your keys:

```bash
cp .env.example .env
```

```dotenv
# Production (www.deribit.com)
DERIBIT_API_CLIENT_ID=your_client_id
DERIBIT_API_SECRET=your_client_secret

# Test environment (test.deribit.com)
DERIBIT_API_CLIENT_ID_TEST=your_test_client_id
DERIBIT_API_SECRET_TEST=your_test_client_secret
```

`DeribitAPIInterface.configure(use_test_env=True)` picks up the `_TEST` keys automatically. Pass `use_test_env=False` (or omit it) for production.

> **Always develop and test against the test environment first.**

---

## Quick start

```python
import asyncio
from deribridge import DeribitAPIInterface


async def main():
    # Reads DERIBIT_API_CLIENT_ID_TEST / DERIBIT_API_SECRET_TEST from .env
    api = DeribitAPIInterface.configure(use_test_env=True)

    if await api.start_client():
        await api.subscribe_to_ticker("BTC-PERPETUAL")

        ticker = await api.get_ticker("BTC-PERPETUAL")
        if ticker:
            print(f"Mark price: {ticker.mark_price}")

        await api.stop_client()


asyncio.run(main())
```

`start_client()` connects, authenticates, and launches a background monitoring task. `stop_client()` cancels it, unsubscribes all channels, and closes the socket cleanly.

---

## Placing orders safely

### The three outcomes

Every order method (`submit_order`, `submit_limit_order`, `cancel_order`, `replace_order`) has exactly three outcomes:

| Outcome | What happened | Return / raise |
|---|---|---|
| **Success** | Exchange confirmed the order | Returns a typed response object |
| **Definite failure** | Request was rejected before or by the exchange | Returns `None` — safe to retry |
| **Indeterminate** | Timeout or socket drop mid-flight — exchange may or may not have seen it | Raises `IndeterminateOrderError` |

The indeterminate case is the dangerous one: retrying blindly can **duplicate a live order**. Always reconcile first.

### Submit a limit order

```python
from deribridge import DeribitAPIInterface, IndeterminateOrderError

api = DeribitAPIInterface.configure(use_test_env=True)
await api.start_client()

ticker = await api.get_ticker("BTC-PERPETUAL")
bid_price = ticker.mark_price * 0.99  # 1 % below mark

try:
    result = await api.submit_limit_order(
        instrument_name="BTC-PERPETUAL",
        side="buy",
        amount=0.01,
        price=bid_price,
        post_only=True,              # maker-only (default)
        time_in_force="good_til_cancelled",  # default
    )
    if result is None:
        print("Order definitively rejected — safe to retry or adjust.")
    else:
        order_id = result.order.order_id
        print(f"Order accepted: {order_id}")

except IndeterminateOrderError as err:
    # The socket timed out or dropped mid-flight.
    # We do NOT know whether the exchange accepted the order.
    print(f"Indeterminate outcome for {err.operation}: {err}")
    # MUST reconcile before retrying:
    open_orders = await api.get_open_orders(currency="BTC")
    # Inspect open_orders to decide whether to cancel, amend, or do nothing.
```

### Cancel and replace

```python
# Cancel — same three-outcome contract
try:
    cancel = await api.cancel_order(order_id)
    if cancel is None:
        print("Cancel definitively failed.")
    elif cancel.is_successful:
        print("Cancelled.")
except IndeterminateOrderError as err:
    # Cancel may or may not have applied — check get_order_state before acting.
    print(f"Cancel indeterminate: {err}")

# Replace (amend price / size in-place)
try:
    await api.replace_order(order_id, price=new_price, amount=new_amount)
except IndeterminateOrderError as err:
    # Amend may or may not have applied.
    print(f"Replace indeterminate: {err}")
```

### Using `submit_order` directly

For full control, build an `Order` object and pass it to `submit_order`:

```python
from deribridge import (
    DeribitAPIInterface,
    IndeterminateOrderError,
    Order,
    OrderPurpose,
    OrderType,
    TimeInForce,
)

order = Order(
    instrument_name="ETH-PERPETUAL",
    purpose=OrderPurpose.BUY,
    amount=1.0,
    order_type=OrderType.LIMIT,
    price=2000.0,
    time_in_force=TimeInForce("good_til_cancelled"),
    post_only=True,
)

try:
    result = await api.submit_order(order)
except IndeterminateOrderError as err:
    ...
```

---

## Key types

Imported directly from `deribridge`:

**Clients**
- `DeribitAPIInterface` — primary high-level entry point (configure → start → trade → stop)
- `DeribitWebSocketClient` — low-level typed WebSocket client
- `EnhancedDeribitClient` — mid-level client with model helpers; used internally by `DeribitAPIInterface`
- `RateLimiter` — standalone rate limiter (10 req/s default)

**Response models** (Pydantic)
- `Ticker`, `OrderBook`, `OrderBookEntry`, `Position`, `Trade`
- `Order`, `OrderSubmitResponse`, `OrderCancelResponse`
- `AccountSummary`, `AccountSummaries`, `AccountFee`
- `BookSummary`, `Instrument`, `Greeks`, `Stats`
- `TransactionLogEntry`, `TransactionLogResponse`

**Domain types**
- `Currency`, `InstrumentType`, `OptionType`, `OrderPurpose`
- `OrderState`, `OrderType`, `TimeInForce`, `InstrumentKind`, `Interval`

**Errors**
- `IndeterminateOrderError` — timeout / mid-flight disconnect on any order mutating call
- `DeribitWebSocketError` — lower-level WebSocket protocol error
- `DeribitError` — Deribit API error codes

---

## Further reading

See [`docs/AI_REFERENCE.md`](./AI_REFERENCE.md) for the full technical reference: method signatures, error codes, subscription channels, response model field definitions, and internal architecture notes.

To see `deribridge` in use as part of a real-time Deribit portfolio analytics product, visit [deribook.com](https://deribook.com).
