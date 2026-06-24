"""deribridge core: the exchange-agnostic framework.

Canonical data models, the :class:`ExchangeAdapter` extension point, the
transport/auth protocols, the capability descriptor, and the error taxonomy.
Nothing here imports a concrete exchange adapter or any adapter's third-party
dependency.
"""
from .adapter import ExchangeAdapter, SymbolLike
from .capabilities import Capabilities
from .facade import ExchangeClient, available_adapters, connect, create
from .enums import (
    AssetKind,
    Interval,
    OptionType,
    OrderState,
    OrderType,
    Side,
    TimeInForce,
)
from .errors import (
    AuthenticationError,
    ExchangeError,
    IndeterminateOrderError,
    MissingExchangeExtra,
    OrderRejected,
    RateLimitError,
    UnknownExchangeError,
    UnsupportedOperation,
)
from .models import (
    AccountSummary,
    Balance,
    Candle,
    FundingRate,
    Greeks,
    Instrument,
    Order,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
    Position,
    Stats,
    Symbol,
    Ticker,
    Trade,
)
from .transport import Credentials

__all__ = [
    # facade
    "connect",
    "create",
    "available_adapters",
    "ExchangeClient",
    # adapter & capabilities
    "ExchangeAdapter",
    "SymbolLike",
    "Capabilities",
    # enums
    "Side",
    "AssetKind",
    "OptionType",
    "OrderType",
    "OrderState",
    "TimeInForce",
    "Interval",
    # errors
    "ExchangeError",
    "UnknownExchangeError",
    "MissingExchangeExtra",
    "AuthenticationError",
    "RateLimitError",
    "UnsupportedOperation",
    "OrderRejected",
    "IndeterminateOrderError",
    # models
    "Symbol",
    "OrderBook",
    "OrderBookLevel",
    "Ticker",
    "Trade",
    "Candle",
    "Stats",
    "Greeks",
    "FundingRate",
    "OrderRequest",
    "Order",
    "Balance",
    "AccountSummary",
    "Position",
    "Instrument",
    # transport
    "Credentials",
]
