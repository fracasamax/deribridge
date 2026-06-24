# Multi-exchange architecture

## Why

`deribridge` began as a Deribit-only client. Its value is returning **structured,
typed data** instead of raw JSON, plus a safe order contract. This design keeps
that value while generalizing across exchanges: the same canonical objects come
back regardless of venue, and a new exchange is added by writing one adapter
that maps its API shapes and protocols to the canonical model — without touching
the core.

Design decisions (settled with the maintainer):

1. Keep the name `deribridge`, rebranded as a general framework; Deribit is the
   first adapter.
2. Adapters live in this repo, gated by optional dependency **extras**
   (`pip install deribridge[binance]`) and **lazy-imported**; a registry selects
   an adapter by name.
3. Binance is a second worked adapter (REST + WebSocket) proving the abstraction
   beyond Deribit's WS-only protocol.
4. Canonical models use `Decimal` for price/amount/balance/fee; `float` for
   analytics (greeks, implied vol, funding, PnL ratios).

## Layers

```
caller → connect(name) → ExchangeClient (= ExchangeAdapter)
                           ├ Transport   (RequestTransport / StreamTransport: REST and/or WS)
                           ├ Authenticator (per-venue auth/signing)
                           ├ Mapper       (raw/wire JSON → canonical models)
                           └ Capabilities (declarative feature descriptor)
canonical models  ←  Mapper  ←  wire JSON  ←  Transport
```

The key separation: **transport** (how bytes move), **wire shapes** (a venue's
JSON), and **canonical models** (the public contract) are distinct. A per-adapter
mapper is the only place wire JSON touches canonical models.

## Package layout

```
src/deribridge/
├── __init__.py              # facade re-exports + lazy __getattr__ back-compat shim
├── core/                    # exchange-agnostic framework (pure; no transport deps)
│   ├── models/              # Symbol, OrderBook, Ticker, Trade, Candle, Order,
│   │                        #   OrderRequest, Position, Balance, AccountSummary,
│   │                        #   Instrument, Greeks, Stats, FundingRate
│   ├── enums.py             # Side, AssetKind, OptionType, OrderType, OrderState,
│   │                        #   TimeInForce, Interval
│   ├── errors.py            # ExchangeError, OrderRejected, IndeterminateOrderError,
│   │                        #   UnsupportedOperation, MissingExchangeExtra, ...
│   ├── adapter.py           # ExchangeAdapter ABC (the extension point)
│   ├── capabilities.py      # Capabilities descriptor
│   ├── registry.py          # name → adapter, lazy importlib, extras-aware
│   ├── facade.py            # connect() / create() / available_adapters()
│   ├── mapper.py            # Mapper protocol + coercion helpers
│   └── transport/           # Request/Response, RequestTransport, StreamTransport,
│                            #   Authenticator, Credentials, RateLimiter, env loader
├── exchanges/
│   ├── deribit/             # reference adapter (existing WS client wrapped, not rewritten)
│   │   ├── adapter.py  mapper.py  symbols.py  capabilities.py
│   │   └── websocket_api_client.py  deribit_api_interface.py  ...  (delegate)
│   └── binance/             # worked REST + WS example (binance extra)
│       ├── adapter.py  rest_transport.py  ws_transport.py
│       └── auth.py  mapper.py  symbols.py  capabilities.py
├── classes/  models/        # legacy business types/enums (kept for back-compat)
└── api_client/              # deprecated re-export shim for the old import paths
```

## Canonical data model

- **Pydantic v2** for canonical models (validation, JSON, the public contract).
  Each adapter keeps its own internal **wire** layer (Deribit's
  `deribit_response_models` dataclasses) and the mapper bridges wire → canonical.
- **`Decimal`** for `price`, `amount`, `balance`, `fee`, `tick_size`, `strike`;
  coerced losslessly via `Decimal(str(x))` so string-price venues (Binance) are
  exact. **`float`** for analytics (`Greeks`, `iv`, funding rate, PnL %).
- **`Symbol`** carries the authoritative venue string (`raw`, used for API calls)
  plus a structured decomposition and a cross-venue `canonical` key
  (e.g. `BTC/USDT:perpetual`, `BTC/USD:option:2025-12-26:60000:call`).
- **`AssetKind`** = `SPOT | PERPETUAL | FUTURE | OPTION | INDEX` (distinguishing
  perpetuals from dated futures, which the old `InstrumentType` conflated).
- **`raw` passthrough**: every canonical model keeps the untouched wire payload
  and an `.x(key)` accessor, so venue-specific fields are never lost without
  bloating the canonical surface.

## Adapter interface

`ExchangeAdapter` (ABC) is the public extension point. Market-data, trading,
account, and streaming methods that an adapter can't support default to raising
`UnsupportedOperation`, so an adapter only overrides what it does — and its
`Capabilities` stay honest. `Transport`, `Authenticator`, and `Mapper` are
`typing.Protocol`s the adapter composes.

The **order-safety trichotomy** is a framework-level contract:

- success → returns a canonical `Order`;
- definite failure → raises `OrderRejected` (safe to retry; order is not live);
- indeterminate (timeout / mid-flight disconnect) → raises
  `IndeterminateOrderError` (reconcile before retrying — may already be live).

A shared **conformance suite** (`tests/conformance/`) runs the same contract
against every registered adapter; adding an adapter without a harness fails a
completeness check, so coverage can't silently lag the registry.

## Packaging, discovery, back-compat

- **Extras gate dependencies, not code.** Every adapter's source ships in the
  wheel; only its third-party deps are optional
  (`[project.optional-dependencies]`). Core depends on `pydantic` +
  `python-dotenv` only; `websockets`/`httpx` live under the adapter extras.
- **Lazy registry.** A static `name → "module:attr"` table answers "does this
  adapter exist?" with zero imports; the class is imported only on
  `connect()/create()`. A missing extra surfaces as `MissingExchangeExtra`
  (`pip install deribridge[binance]`), not a bare `ModuleNotFoundError`. An
  `importlib.metadata` entry-point overlay (`deribridge.exchanges`) keeps the
  door open for out-of-tree adapters.
- **Backward compatibility.** `import deribridge` stays light: pure
  enums/classes/canonical types import eagerly; Deribit-flavored names resolve
  lazily via PEP 562 `__getattr__`. Old paths
  (`from deribridge import DeribitAPIInterface`, `deribridge.api_client.*`) keep
  working through re-export shims (module identity preserved, so string-based
  patch targets still work). `__all__` only grows.

## Adding an exchange

1. Create `src/deribridge/exchanges/<name>/` with `adapter.py`, `mapper.py`,
   `symbols.py`, `capabilities.py`, and transport(s).
2. Subclass `ExchangeAdapter`, set `name` and `capabilities`, and map the wire
   format to canonical models in the mapper.
3. Add `<name>` to `core/registry._BUILTIN` and an extra in `pyproject.toml`.
4. Add a harness to `tests/conformance/` and fixture-based mapper/adapter tests.
