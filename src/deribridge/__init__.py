"""deribridge — async, typed, multi-exchange bridge for crypto exchanges.

Created and maintained by Francesco Casamassima <dev@elnc.eu>.

deribridge turns each exchange's API into the *same* canonical, typed data
classes behind a common interface. Deribit is the reference adapter (it powers
deribook — https://deribook.com — real-time derivatives portfolio analytics);
additional exchanges are added as adapters under ``deribridge.exchanges`` and
selected by name::

    import asyncio, deribridge

    async def main():
        async with deribridge.create("deribit", testnet=True) as client:
            ticker = await client.get_ticker("BTC-PERPETUAL")
            print(ticker.mark_price)

    asyncio.run(main())

Adapter *code* always ships; an adapter's third-party dependencies are gated by
extras (``pip install deribridge[binance]``) and imported lazily. Importing an
adapter whose extra is missing raises an actionable ``MissingExchangeExtra``.

Backward compatibility: the original Deribit-specific names
(``DeribitAPIInterface`` and friends) remain importable from the top level and
from ``deribridge.exchanges.deribit`` (and, deprecated, ``deribridge.api_client``).
"""
import importlib
from typing import Any

__version__ = "1.0.0"
__author__ = "Francesco Casamassima"
__email__ = "dev@elnc.eu"

# --------------------------------------------------------------------------- #
# Eager: framework facade, canonical errors/types — all pure, no transport deps
# --------------------------------------------------------------------------- #
from .core import (
    AuthenticationError,
    Capabilities,
    Credentials,
    ExchangeAdapter,
    ExchangeClient,
    ExchangeError,
    IndeterminateOrderError,
    MissingExchangeExtra,
    OrderRejected,
    RateLimitError,
    UnknownExchangeError,
    UnsupportedOperation,
    available_adapters,
    connect,
    create,
)
from .core.transport import RateLimiter

# Eager: shared business classes / enums (pure pydantic, no transport deps)
from .classes import (
    Currency,
    Instrument as InstrumentClass,
    InstrumentType,
    OptionType,
    Order as OrderClass,
    OrderPurpose,
)
from .models import (
    Currency as CurrencyModel,
    InstrumentKind,
    Interval,
    Order as OrderModel,
    OrderBook as OrderBookModel,
    OrderState,
    OrderType,
    TimeInForce,
    Trade as TradeModel,
)

# --------------------------------------------------------------------------- #
# Lazy: Deribit-flavored names. Resolving any of these imports the Deribit
# adapter (and therefore ``websockets``); on a core-only install that raises a
# friendly MissingExchangeExtra instead of a bare ModuleNotFoundError.
# --------------------------------------------------------------------------- #
_LAZY_DERIBIT = {
    # clients / helpers
    "DeribitWebSocketClient",
    "DeribitAPIInterface",
    "DeribitInstrument",
    "EnhancedDeribitClient",
    "DeribitWebSocketError",
    "DeribitError",
    "configure_logging",
    # wire response models
    "DeribitBaseResponse",
    "DeribitErrorResponse",
    "DeribitResultResponse",
    "DeribitSubscriptionResponse",
    "DeribitResponseType",
    "Order",
    "OrderBook",
    "OrderBookEntry",
    "Position",
    "Trade",
    "Ticker",
    "BookSummary",
    "Instrument",
    "Greeks",
    "Stats",
    "IndexPriceResponse",
    "FundingRateValue",
    "TickSizeStep",
    "AccountSummary",
    "AccountSummaries",
    "AccountFee",
    "OrderSubmitResponse",
    "OrderCancelResponse",
    "TransactionLogEntry",
    "TransactionLogResponse",
}
# Names whose source module is not re-exported by the deribit package namespace.
_LAZY_MODULE = {
    "configure_logging": "deribridge.exchanges.deribit.deribit_api_interface",
    "TransactionLogEntry": "deribridge.exchanges.deribit.deribit_response_models",
    "TransactionLogResponse": "deribridge.exchanges.deribit.deribit_response_models",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_DERIBIT:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path = _LAZY_MODULE.get(name, "deribridge.exchanges.deribit")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        missing = getattr(exc, "name", "") or ""
        if missing.startswith("deribridge"):
            raise
        raise MissingExchangeExtra("deribit", "deribit", missing) from exc
    return getattr(module, name)


__all__ = [
    # --- multi-exchange framework (new) ---
    "connect",
    "create",
    "available_adapters",
    "ExchangeClient",
    "ExchangeAdapter",
    "Capabilities",
    "Credentials",
    "ExchangeError",
    "UnknownExchangeError",
    "MissingExchangeExtra",
    "AuthenticationError",
    "RateLimitError",
    "UnsupportedOperation",
    "OrderRejected",
    "IndeterminateOrderError",
    # --- Deribit reference adapter (lazy) ---
    "configure_logging",
    "DeribitWebSocketClient",
    "DeribitAPIInterface",
    "DeribitInstrument",
    "EnhancedDeribitClient",
    "RateLimiter",
    # Response models
    "DeribitBaseResponse",
    "DeribitErrorResponse",
    "DeribitResultResponse",
    "DeribitSubscriptionResponse",
    "DeribitResponseType",
    "Order",
    "OrderBook",
    "OrderBookEntry",
    "Position",
    "Trade",
    "Ticker",
    "BookSummary",
    "Instrument",
    "Greeks",
    "Stats",
    "IndexPriceResponse",
    "FundingRateValue",
    "TickSizeStep",
    "AccountSummary",
    "AccountSummaries",
    "AccountFee",
    "OrderSubmitResponse",
    "OrderCancelResponse",
    "TransactionLogEntry",
    "TransactionLogResponse",
    # Business classes
    "OrderClass",
    "InstrumentClass",
    "Currency",
    "InstrumentType",
    "OptionType",
    "OrderPurpose",
    # Model types
    "CurrencyModel",
    "InstrumentKind",
    "Interval",
    "OrderBookModel",
    "OrderState",
    "OrderType",
    "OrderModel",
    "TimeInForce",
    "TradeModel",
    # Errors
    "DeribitError",
    "DeribitWebSocketError",
]
