# Main API clients and interfaces
from .api_client import (
    DeribitWebSocketClient,
    DeribitAPIInterface,
    DeribitInstrument,
    EnhancedDeribitClient,
    RateLimiter
)

# Response models and data structures
from .api_client.deribit_response_models import (
    # Core response types
    DeribitBaseResponse,
    DeribitErrorResponse,
    DeribitResultResponse,
    DeribitSubscriptionResponse,
    DeribitResponseType,

    # Trading and order models
    Order,
    OrderBook,
    OrderBookEntry,
    Position,
    Trade,
    Ticker,

    # Market data models
    BookSummary,
    Instrument,
    Greeks,
    Stats,
    IndexPriceResponse,
    FundingRateValue,
    TickSizeStep,

    # Account models
    AccountSummary,
    AccountSummaries,
    AccountFee,

    # Response models
    OrderSubmitResponse,
    OrderCancelResponse,

    # Transaction log models
    TransactionLogEntry,
    TransactionLogResponse,
)

# Business logic classes
from .classes import (
    # Core trading classes
    Order as OrderClass,
    Instrument as InstrumentClass,

    # Trade planning
    TradePlan,
    TradePlanItem,

    # Enums and types
    Currency,
    InstrumentType,
    OptionType,
    OrderPurpose,
)

# Model definitions
from .models import (
    # Core model types
    Currency as CurrencyModel,
    InstrumentKind,
    Interval,
    OrderBook as OrderBookModel,
    OrderState,
    OrderType,
    Order as OrderModel,
    TimeInForce,
    Trade as TradeModel,
)

# Error handling
from .api_client.deribit_error_codes import DeribitError
from .api_client.websocket_api_client import DeribitWebSocketError


# Define what's available when using "from deribridge import *"
__all__ = [
    # Main API clients
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
    "TradePlan",
    "TradePlanItem",
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

    # Error handling
    "DeribitError",
    "DeribitWebSocketError",
]
