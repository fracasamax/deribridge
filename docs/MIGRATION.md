# Migration guide

## 0.1.x → 1.0.0

`deribridge` is now a multi-exchange framework. Existing Deribit code keeps
working; the changes below are opt-in except for the install command.

### Install (one required change)

`websockets` moved out of the core dependencies into the `deribit` extra. Install
the Deribit transport explicitly:

```bash
# before
pip install deribridge

# after
pip install "deribridge[deribit]"      # Deribit
pip install "deribridge[binance]"      # Binance (REST + WS)
pip install "deribridge[all]"          # everything
```

A core-only `pip install deribridge` still imports and can discover adapters;
calling an adapter whose extra is missing raises an actionable
`MissingExchangeExtra` telling you exactly what to install.

### Imports (unchanged, but new homes exist)

All existing names keep working:

```python
from deribridge import DeribitAPIInterface, EnhancedDeribitClient, RateLimiter
from deribridge.api_client.deribit_api_interface import IndeterminateOrderError
```

The Deribit code now lives under `deribridge.exchanges.deribit`; the
`deribridge.api_client.*` paths are **deprecated** re-export shims. Prefer:

```python
from deribridge.exchanges.deribit import DeribitAPIInterface
```

`IndeterminateOrderError` and `RateLimiter` are now defined in
`deribridge.core` / `deribridge.core.transport` and re-exported from their old
locations (same classes).

### New canonical API (opt-in)

```python
import asyncio, deribridge

async def main():
    async with deribridge.create("deribit", testnet=True) as client:
        ticker = await client.get_ticker("BTC-PERPETUAL")
        print(ticker.mark_price)          # Decimal

    async with deribridge.create("binance") as client:
        book = await client.get_order_book("BTCUSDT", depth=10)
        print(book.best_bid.price)        # Decimal

asyncio.run(main())
```

`deribridge.available_adapters()` lists installed adapters; `connect(...)` is the
async form (builds and connects), `create(...)` builds without connecting (for
`async with`).

### `Decimal` vs `float`

The **new canonical models** use `Decimal` for prices, amounts, balances, and
fees (lossless across exchanges; analytics like greeks/IV/funding stay `float`).
The **legacy `DeribitAPIInterface`** path is unchanged and still returns the
existing `float`-based Deribit response models — so current consumers (including
deribook) are unaffected until they migrate to the canonical API. When you do
migrate, expect `Decimal` where you previously got `float`.
