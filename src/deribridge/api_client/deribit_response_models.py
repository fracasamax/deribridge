from __future__ import annotations
from typing import Dict, List, Optional, Union, Any, TypeVar, cast
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json

T = TypeVar('T')


class DeribitResponseType(Enum):
    """Types of responses from the Deribit API."""
    RESULT = "result"
    SUBSCRIPTION = "subscription"
    ERROR = "error"


@dataclass
class DeribitBaseResponse:
    """Base class for all Deribit API responses."""
    raw_response: Dict[str, Any]

    @property
    def response_type(self) -> DeribitResponseType:
        """Determine the type of response."""
        if "error" in self.raw_response:
            return DeribitResponseType.ERROR
        elif "method" in self.raw_response and self.raw_response.get("method") == "subscription":
            return DeribitResponseType.SUBSCRIPTION
        else:
            return DeribitResponseType.RESULT

    @property
    def id(self) -> Optional[int]:
        """Get the ID of the response, if available."""
        return self.raw_response.get("id")

    @classmethod
    def from_json(cls, json_str: str) -> 'DeribitBaseResponse':
        """Create a response object from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeribitBaseResponse':
        """Create appropriate response object from dict."""
        if "error" in data:
            return DeribitErrorResponse(data)
        elif "method" in data and data.get("method") == "subscription":
            return DeribitSubscriptionResponse(data)
        else:
            return DeribitResultResponse(data)

    def is_error(self) -> bool:
        """Check if this is an error response."""
        return self.response_type == DeribitResponseType.ERROR

    def is_subscription(self) -> bool:
        """Check if this is a subscription update."""
        return self.response_type == DeribitResponseType.SUBSCRIPTION

    def is_result(self) -> bool:
        """Check if this is a normal result response."""
        return self.response_type == DeribitResponseType.RESULT

    def as_error(self) -> 'DeribitErrorResponse':
        """Cast this response to an error response."""
        if not self.is_error():
            raise TypeError("Response is not an error response")
        return cast(DeribitErrorResponse, self)

    def as_subscription(self) -> 'DeribitSubscriptionResponse':
        """Cast this response to a subscription response."""
        if not self.is_subscription():
            raise TypeError("Response is not a subscription response")
        return cast(DeribitSubscriptionResponse, self)

    def as_result(self) -> 'DeribitResultResponse':
        """Cast this response to a result response."""
        if not self.is_result():
            raise TypeError("Response is not a result response")
        return cast(DeribitResultResponse, self)


@dataclass
class DeribitErrorResponse(DeribitBaseResponse):
    """Represents an error response from the Deribit API."""

    @property
    def error_code(self) -> int:
        """Get the error code."""
        return self.raw_response.get("error", {}).get("code", -1)

    @property
    def error_message(self) -> str:
        """Get the error message."""
        return self.raw_response.get("error", {}).get("message", "Unknown error")

    @property
    def error_data(self) -> Optional[Dict[str, Any]]:
        """Get additional error data if available."""
        return self.raw_response.get("error", {}).get("data")


@dataclass
class DeribitResultResponse(DeribitBaseResponse):
    """Represents a successful result response from the Deribit API."""

    @property
    def result(self) -> Any:
        """Get the result data."""
        return self.raw_response.get("result")

    def to_typed_result(self, model_class: type[T]) -> T:
        """Convert the result to a specific model type."""
        if self.result is None:
            raise ValueError("Response contains no result")

        # Handle list results
        if isinstance(self.result, list):
            if hasattr(model_class, 'from_dict'):
                return [model_class.from_dict(item) for item in self.result]  # type: ignore
            else:
                return [model_class(**item) for item in self.result]  # type: ignore

        # Handle dict results
        if hasattr(model_class, 'from_dict'):
            return model_class.from_dict(self.result)  # type: ignore
        else:
            return model_class(**self.result)  # type: ignore


@dataclass
class DeribitSubscriptionResponse(DeribitBaseResponse):
    """Represents a subscription update from the Deribit API."""

    @property
    def params(self) -> Dict[str, Any]:
        """Get the parameters of the subscription update."""
        return self.raw_response.get("params", {})

    @property
    def channel(self) -> str:
        """Get the channel name."""
        return self.params.get("channel", "")

    @property
    def data(self) -> Any:
        """Get the data payload."""
        return self.params.get("data")

    def to_typed_data(self, model_class: type[T]) -> T:
        """Convert the data to a specific model type."""
        if self.data is None:
            raise ValueError("Subscription update contains no data")

        # Handle list data
        if isinstance(self.data, list):
            if hasattr(model_class, 'from_dict'):
                return [model_class.from_dict(item) for item in self.data]  # type: ignore
            else:
                return [model_class(**item) for item in self.data]  # type: ignore

        # Handle dict data
        if hasattr(model_class, 'from_dict'):
            return model_class.from_dict(self.data)  # type: ignore
        else:
            return model_class(**self.data)  # type: ignore


# Specific Response Data Models

@dataclass
class OrderBookEntry:
    """Represents an entry in the order book."""
    price: float
    amount: float
    action: Optional[str] = None  # "new", "change", or "delete"

    @classmethod
    def from_dict(cls, data: List[Any]) -> 'OrderBookEntry':
        """Create from API data format.

        Handles both formats:
        - [price, amount] - static order book response format
        - [action, price, amount] - subscription update format
        """
        if len(data) == 2:
            # Static order book format: [price, amount]
            return cls(price=data[0], amount=data[1], action=None)
        elif len(data) == 3:
            # Subscription update format: [action, price, amount]
            return cls(price=data[1], amount=data[2], action=data[0])
        else:
            raise ValueError(f"Invalid order book entry format: {data}")

    def is_new(self) -> bool:
        """Check if this is a new price level."""
        return self.action == "new" if self.action else False

    def is_change(self) -> bool:
        """Check if this is a change to existing price level."""
        return self.action == "change" if self.action else False

    def is_delete(self) -> bool:
        """Check if this price level is being deleted."""
        return self.action == "delete" if self.action else False


@dataclass
class OrderBook:
    ask_iv: Optional[float]
    best_ask_amount: float
    best_ask_price: Optional[float]
    best_bid_amount: float
    best_bid_price: Optional[float]
    bid_iv: Optional[float]
    current_funding: float
    delivery_price: Optional[float]
    funding_8h: float
    greeks: Optional[Greeks]
    index_price: float
    instrument_name: str
    last_price: float
    mark_iv: Optional[float]
    mark_price: float
    max_price: Optional[float]
    min_price: Optional[float]
    open_interest: float
    settlement_price: Optional[float]
    state: str
    stats: Optional[Stats]
    timestamp: int
    underlying_index: Optional[str]
    underlying_price: Optional[float]
    asks: List[OrderBookEntry]
    bids: List[OrderBookEntry]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBook':
        return cls(
            ask_iv=data.get("ask_iv"),
            best_ask_amount=data.get("best_ask_amount", 0.0),
            best_ask_price=data.get("best_ask_price"),
            best_bid_amount=data.get("best_bid_amount", 0.0),
            best_bid_price=data.get("best_bid_price"),
            bid_iv=data.get("bid_iv"),
            current_funding=data.get("current_funding", 0.0),
            delivery_price=data.get("delivery_price"),
            funding_8h=data.get("funding_8h", 0.0),
            greeks=Greeks.from_dict(data["greeks"]) if data.get("greeks") else None,
            index_price=data.get("index_price", 0.0),
            instrument_name=data.get("instrument_name", ""),
            last_price=data.get("last_price", 0.0),
            mark_iv=data.get("mark_iv"),
            mark_price=data.get("mark_price", 0.0),
            max_price=data.get("max_price"),
            min_price=data.get("min_price"),
            open_interest=data.get("open_interest", 0.0),
            settlement_price=data.get("settlement_price"),
            state=data.get("state", ""),
            stats=Stats.from_dict(data["stats"]) if data.get("stats") else None,
            timestamp=data.get("timestamp", 0),
            underlying_index=data.get("underlying_index"),
            underlying_price=data.get("underlying_price"),
            asks=[OrderBookEntry.from_dict(a) for a in data.get("asks", [])],
            bids=[OrderBookEntry.from_dict(b) for b in data.get("bids", [])],
        )

    @property
    def best_ask(self) -> Optional[OrderBookEntry]:
        """Get the best (lowest) ask price."""
        return self.asks[0] if self.asks else None

    @property
    def best_bid(self) -> Optional[OrderBookEntry]:
        """Get the best (highest) bid price."""
        return self.bids[0] if self.bids else None

    @property
    def spread(self) -> Optional[float]:
        """Calculate the bid-ask spread."""
        if self.best_ask and self.best_bid:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate the mid price."""
        if self.best_ask and self.best_bid:
            return (self.best_ask.price + self.best_bid.price) / 2
        return None


@dataclass
class OrderBookEvent:
    """Represents an order book update event from subscriptions."""
    asks: List[List[Any]]  # List of [action, price, amount] entries
    bids: List[List[Any]]  # List of [action, price, amount] entries
    change_id: int
    instrument_name: str
    timestamp: int
    type: str  # "snapshot" or "change"
    prev_change_id: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookEvent':
        """Create from API subscription data."""
        return cls(
            asks=data.get("asks", []),
            bids=data.get("bids", []),
            change_id=data.get("change_id", 0),
            instrument_name=data.get("instrument_name", ""),
            timestamp=data.get("timestamp", 0),
            type=data.get("type", ""),
            prev_change_id=data.get("prev_change_id")
        )

    @property
    def is_snapshot(self) -> bool:
        """Check if this is the initial snapshot."""
        return self.type == "snapshot"

    @property
    def is_change(self) -> bool:
        """Check if this is an incremental change."""
        return self.type == "change"


@dataclass
class Trade:
    """Represents a trade."""
    amount: float
    block_rfq_id: Optional[int]
    block_trade_id: Optional[str]
    block_trade_leg_count: Optional[int]
    combo_id: Optional[str]
    combo_trade_id: Optional[int]
    contracts: Optional[float]
    direction: str  # "buy" or "sell"
    index_price: float
    instrument_name: str
    iv: Optional[float]
    liquidation: Optional[str]
    mark_price: float
    price: float
    tick_direction: int  # 0=Plus,1=Zero-Plus,2=Minus,3=Zero-Minus
    timestamp: int
    trade_id: str
    trade_seq: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """Create from API response."""
        return cls(
            amount=data.get("amount", 0.0),
            block_rfq_id=data.get("block_rfq_id"),
            block_trade_id=data.get("block_trade_id"),
            block_trade_leg_count=data.get("block_trade_leg_count"),
            combo_id=data.get("combo_id"),
            combo_trade_id=data.get("combo_trade_id"),
            contracts=data.get("contracts"),
            direction=data.get("direction", ""),
            index_price=data.get("index_price", 0.0),
            instrument_name=data.get("instrument_name", ""),
            iv=data.get("iv"),
            liquidation=data.get("liquidation"),
            mark_price=data.get("mark_price", 0.0),
            price=data.get("price", 0.0),
            tick_direction=data.get("tick_direction", 0),
            timestamp=data.get("timestamp", 0),
            trade_id=data.get("trade_id", ""),
            trade_seq=data.get("trade_seq", 0),
        )

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp / 1000)


@dataclass
class Greeks:
    delta: float
    gamma: float
    rho: float
    theta: float
    vega: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Greeks':
        return cls(
            delta=data.get("delta", 0.0),
            gamma=data.get("gamma", 0.0),
            rho=data.get("rho", 0.0),
            theta=data.get("theta", 0.0),
            vega=data.get("vega", 0.0),
        )


@dataclass
class Stats:
    high: float
    low: float
    price_change: Optional[float]
    volume: float
    volume_usd: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Stats':
        return cls(
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            price_change=data.get("price_change"),
            volume=data.get("volume", 0.0),
            volume_usd=data.get("volume_usd"),
        )


@dataclass
class IndexPriceResponse:
    estimated_delivery_price: Optional[float]
    index_price: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndexPriceResponse':
        """Create from API response."""
        return cls(
            estimated_delivery_price=data.get("estimated_delivery_price"),
            index_price=data.get("index_price"),
        )


@dataclass
class Ticker:
    ask_iv: Optional[float]
    best_ask_amount: float
    best_ask_price: Optional[float]
    best_bid_amount: float
    best_bid_price: Optional[float]
    bid_iv: Optional[float]
    current_funding: float
    delivery_price: Optional[float]
    estimated_delivery_price: Optional[float]
    greeks: Optional[Greeks]
    index_price: float
    instrument_name: str
    interest_rate: Optional[float]
    interest_value: Optional[float]
    last_price: float
    mark_iv: Optional[float]
    mark_price: float
    max_price: Optional[float]
    min_price: Optional[float]
    open_interest: float
    settlement_price: Optional[float]
    state: str
    stats: Optional[Stats]
    timestamp: int
    underlying_index: Optional[str]
    underlying_price: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Ticker':
        return cls(
            ask_iv=data.get("ask_iv"),
            best_ask_amount=data.get("best_ask_amount", 0.0),
            best_ask_price=data.get("best_ask_price"),
            best_bid_amount=data.get("best_bid_amount", 0.0),
            best_bid_price=data.get("best_bid_price"),
            bid_iv=data.get("bid_iv"),
            current_funding=data.get("current_funding", 0.0),
            delivery_price=data.get("delivery_price"),
            estimated_delivery_price=data.get("estimated_delivery_price"),
            greeks=Greeks.from_dict(data["greeks"]) if data.get("greeks") else None,
            index_price=data.get("index_price", 0.0),
            instrument_name=data.get("instrument_name", ""),
            interest_rate=data.get("interest_rate"),
            interest_value=data.get("interest_value"),
            last_price=data.get("last_price", 0.0),
            mark_iv=data.get("mark_iv"),
            mark_price=data.get("mark_price", 0.0),
            max_price=data.get("max_price"),
            min_price=data.get("min_price"),
            open_interest=data.get("open_interest", 0.0),
            settlement_price=data.get("settlement_price"),
            state=data.get("state", ""),
            stats=Stats.from_dict(data["stats"]) if data.get("stats") else None,
            timestamp=data.get("timestamp", 0),
            underlying_index=data.get("underlying_index"),
            underlying_price=data.get("underlying_price"),
        )

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread, or None if either side is missing (e.g. one-sided book)."""
        if self.best_ask_price is None or self.best_bid_price is None:
            return None
        return self.best_ask_price - self.best_bid_price

    @property
    def mid_price(self) -> Optional[float]:
        """Mid price, or None if either side is missing (e.g. one-sided book)."""
        if self.best_ask_price is None or self.best_bid_price is None:
            return None
        return (self.best_ask_price + self.best_bid_price) / 2


@dataclass
class FundingRateValue:
    """Represents a funding rate value for a perpetual instrument."""
    instrument_name: str
    start_timestamp: int
    end_timestamp: int
    value: float

    @classmethod
    def from_dict(cls, value: float, instrument_name: str, start_timestamp: int,
                  end_timestamp: int) -> 'FundingRateValue':
        """Create from API response value with additional context."""
        return cls(
            instrument_name=instrument_name,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            value=float(value)
        )

    @property
    def start_datetime(self) -> datetime:
        """Convert start timestamp to datetime."""
        return datetime.fromtimestamp(self.start_timestamp / 1000)

    @property
    def end_datetime(self) -> datetime:
        """Convert end timestamp to datetime."""
        return datetime.fromtimestamp(self.end_timestamp / 1000)


@dataclass
class TickSizeStep:
    above_price: float
    tick_size: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TickSizeStep':
        return cls(
            above_price=data.get("above_price", 0.0),
            tick_size=data.get("tick_size", 0.0),
        )


@dataclass
class Instrument:
    instrument_id: int
    instrument_name: str
    kind: str
    base_currency: str
    counter_currency: str
    quote_currency: str
    price_index: Optional[str]
    contract_size: int
    future_type: Optional[str]
    instrument_type: str
    block_trade_commission: float
    block_trade_min_trade_amount: float
    block_trade_tick_size: float
    tick_size: float
    tick_size_steps: Optional[List[TickSizeStep]]
    settlement_currency: Optional[str]
    settlement_period: Optional[str]
    creation_timestamp: int
    expiration_timestamp: int
    is_active: bool
    maker_commission: float
    taker_commission: float
    max_leverage: Optional[int]
    max_liquidation_commission: Optional[float]
    min_trade_amount: float
    option_type: Optional[str]
    strike: Optional[float]
    rfq: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Instrument':
        return cls(
            instrument_id=data.get("instrument_id", 0),
            instrument_name=data.get("instrument_name", ""),
            kind=data.get("kind", ""),
            base_currency=data.get("base_currency", ""),
            counter_currency=data.get("counter_currency", ""),
            quote_currency=data.get("quote_currency", data.get("counter_currency", "")),
            price_index=data.get("price_index"),
            contract_size=data.get("contract_size", 0),
            future_type=data.get("future_type"),
            instrument_type=data.get("instrument_type", ""),
            block_trade_commission=data.get("block_trade_commission", 0.0),
            block_trade_min_trade_amount=data.get("block_trade_min_trade_amount", 0.0),
            block_trade_tick_size=data.get("block_trade_tick_size", 0.0),
            tick_size=data.get("tick_size", 0.0),
            tick_size_steps=[TickSizeStep.from_dict(ts) for ts in data.get("tick_size_steps", [])] if data.get(
                "tick_size_steps") else None,
            settlement_currency=data.get("settlement_currency"),
            settlement_period=data.get("settlement_period"),
            creation_timestamp=data.get("creation_timestamp", 0),
            expiration_timestamp=data.get("expiration_timestamp", 0),
            is_active=data.get("is_active", True),
            maker_commission=data.get("maker_commission", 0.0),
            taker_commission=data.get("taker_commission", 0.0),
            max_leverage=data.get("max_leverage"),
            max_liquidation_commission=data.get("max_liquidation_commission"),
            min_trade_amount=data.get("min_trade_amount", 0.0),
            option_type=data.get("option_type"),
            strike=data.get("strike"),
            rfq=data.get("rfq", False),
        )

    @property
    def creation_datetime(self) -> datetime:
        """Convert creation timestamp to datetime."""
        return datetime.fromtimestamp(self.creation_timestamp / 1000)

    @property
    def expiration_datetime(self) -> datetime:
        """Convert expiration timestamp to datetime."""
        return datetime.fromtimestamp(self.expiration_timestamp / 1000)

    @property
    def is_option(self) -> bool:
        """Check if instrument is an option."""
        return self.kind == "option"

    @property
    def is_future(self) -> bool:
        """Check if instrument is a future."""
        return self.kind == "future"

    @property
    def is_perpetual(self) -> bool:
        """Check if instrument is a perpetual contract."""
        return self.is_future and self.settlement_period == "perpetual"


@dataclass
class Position:
    """Represents a position."""
    average_price: float
    average_price_usd: Optional[float]
    delta: float
    direction: str
    estimated_liquidation_price: float
    floating_profit_loss: float
    floating_profit_loss_usd: Optional[float]
    gamma: Optional[float]
    index_price: float
    initial_margin: float
    instrument_name: str
    interest_value: Optional[float]
    kind: str
    leverage: Optional[int]
    maintenance_margin: float
    mark_price: float
    open_orders_margin: float
    realized_funding: Optional[float]
    realized_profit_loss: float
    settlement_price: Optional[float]
    size: float
    size_currency: float
    theta: Optional[float]
    total_profit_loss: float
    vega: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create from API response."""
        return cls(
            average_price=data.get("average_price", 0.0),
            average_price_usd=data.get("average_price_usd"),
            delta=data.get("delta", 0.0),
            direction=data.get("direction", ""),
            estimated_liquidation_price=data.get("estimated_liquidation_price", 0.0),
            floating_profit_loss=data.get("floating_profit_loss", 0.0),
            floating_profit_loss_usd=data.get("floating_profit_loss_usd"),
            gamma=data.get("gamma"),
            index_price=data.get("index_price", 0.0),
            initial_margin=data.get("initial_margin", 0.0),
            instrument_name=data.get("instrument_name", ""),
            interest_value=data.get("interest_value"),
            kind=data.get("kind", ""),
            leverage=data.get("leverage"),
            maintenance_margin=data.get("maintenance_margin", 0.0),
            mark_price=data.get("mark_price", 0.0),
            open_orders_margin=data.get("open_orders_margin", 0.0),
            realized_funding=data.get("realized_funding"),
            realized_profit_loss=data.get("realized_profit_loss", 0.0),
            settlement_price=data.get("settlement_price"),
            size=data.get("size", 0.0),
            size_currency=data.get("size_currency", 0.0),
            theta=data.get("theta"),
            total_profit_loss=data.get("total_profit_loss", 0.0),
            vega=data.get("vega"),
        )

    @property
    def is_long(self) -> bool:
        """Check if the position is long."""
        return self.direction == "buy"

    @property
    def is_short(self) -> bool:
        """Check if the position is short."""
        return self.direction == "sell"

    @property
    def unrealized_pnl(self) -> float:
        """Get the unrealized PnL."""
        return self.floating_profit_loss


@dataclass
class Order:
    """Comprehensive representation of a Deribit order."""
    # Core order identifiers
    order_id: str
    instrument_name: str

    # Order parameters
    amount: float
    price: Union[float, str]  # Can be "market_price" for trigger orders
    direction: str  # "buy" or "sell"
    order_type: str  # "limit", "market", "stop_limit", "stop_market"
    order_state: str  # "open", "filled", "rejected", "cancelled", "untriggered"
    time_in_force: str  # "good_til_cancelled", "good_til_day", "fill_or_kill", "immediate_or_cancel"

    # Execution state
    filled_amount: float
    average_price: float

    # Timestamps
    creation_timestamp: int
    last_update_timestamp: int

    # Order flags
    reduce_only: bool = False
    post_only: bool = False
    max_show: Optional[float] = None

    # Advanced options
    contracts: Optional[float] = None
    advanced: Optional[str] = None  # "usd" or "implv"
    usd: Optional[float] = None
    implv: Optional[float] = None

    # Trigger-related fields
    trigger: Optional[str] = None  # "index_price", "mark_price", "last_price"
    trigger_price: Optional[float] = None
    trigger_offset: Optional[float] = None
    trigger_reference_price: Optional[float] = None
    triggered: Optional[bool] = None

    # Order relations
    original_order_type: Optional[str] = None
    trigger_order_id: Optional[str] = None
    primary_order_id: Optional[str] = None
    oco_ref: Optional[str] = None
    oto_order_ids: Optional[List[str]] = None
    trigger_fill_condition: Optional[str] = None  # "first_hit", "complete_fill", "incremental"

    # Order source and flags
    api: Optional[bool] = None
    web: Optional[bool] = None
    mobile: Optional[bool] = None
    app_name: Optional[str] = None
    label: Optional[str] = None

    # Order properties
    is_liquidation: Optional[bool] = None
    is_rebalance: Optional[bool] = None
    risk_reducing: Optional[bool] = None
    replaced: Optional[bool] = None
    auto_replaced: Optional[bool] = None
    reject_post_only: Optional[bool] = None

    # Order relationship types
    is_primary_otoco: Optional[bool] = None
    is_secondary_oto: Optional[bool] = None

    # Market maker protection
    mmp: Optional[bool] = None
    mmp_cancelled: Optional[bool] = None
    mmp_group: Optional[str] = None

    # Mass quote fields
    quote: Optional[bool] = None
    quote_id: Optional[str] = None
    quote_set_id: Optional[str] = None

    # Block trade
    block_trade: Optional[bool] = None

    # Cancellation
    cancel_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Create an Order from the API response dictionary."""
        # Handle "price" which can be a number or "market_price" string
        price = data.get("price", 0.0)

        return cls(
            # Core fields
            order_id=data.get("order_id", ""),
            instrument_name=data.get("instrument_name", ""),
            amount=data.get("amount", 0.0),
            price=price,
            direction=data.get("direction", ""),
            order_type=data.get("order_type", ""),
            order_state=data.get("order_state", ""),
            time_in_force=data.get("time_in_force", "good_til_cancelled"),
            filled_amount=data.get("filled_amount", 0.0),
            average_price=data.get("average_price", 0.0),
            creation_timestamp=data.get("creation_timestamp", 0),
            last_update_timestamp=data.get("last_update_timestamp", 0),

            # Basic flags
            reduce_only=data.get("reduce_only", False),
            post_only=data.get("post_only", False),
            max_show=data.get("max_show"),

            # Advanced options
            contracts=data.get("contracts"),
            advanced=data.get("advanced"),
            usd=data.get("usd"),
            implv=data.get("implv"),

            # Trigger fields
            trigger=data.get("trigger"),
            trigger_price=data.get("trigger_price"),
            trigger_offset=data.get("trigger_offset"),
            trigger_reference_price=data.get("trigger_reference_price"),
            triggered=data.get("triggered"),

            # Order relations
            original_order_type=data.get("original_order_type"),
            trigger_order_id=data.get("trigger_order_id"),
            primary_order_id=data.get("primary_order_id"),
            oco_ref=data.get("oco_ref"),
            oto_order_ids=data.get("oto_order_ids"),
            trigger_fill_condition=data.get("trigger_fill_condition"),

            # Source flags
            api=data.get("api"),
            web=data.get("web"),
            mobile=data.get("mobile"),
            app_name=data.get("app_name"),
            label=data.get("label"),

            # Order properties
            is_liquidation=data.get("is_liquidation"),
            is_rebalance=data.get("is_rebalance"),
            risk_reducing=data.get("risk_reducing"),
            replaced=data.get("replaced"),
            auto_replaced=data.get("auto_replaced"),
            reject_post_only=data.get("reject_post_only"),

            # Relationship types
            is_primary_otoco=data.get("is_primary_otoco"),
            is_secondary_oto=data.get("is_secondary_oto"),

            # Market maker protection
            mmp=data.get("mmp"),
            mmp_cancelled=data.get("mmp_cancelled"),
            mmp_group=data.get("mmp_group"),

            # Mass quote fields
            quote=data.get("quote"),
            quote_id=data.get("quote_id"),
            quote_set_id=data.get("quote_set_id"),

            # Block trade
            block_trade=data.get("block_trade"),

            # Cancellation
            cancel_reason=data.get("cancel_reason"),
        )

    @property
    def creation_datetime(self) -> datetime:
        """Convert creation timestamp to datetime."""
        return datetime.fromtimestamp(self.creation_timestamp / 1000)

    @property
    def last_update_datetime(self) -> datetime:
        """Convert last update timestamp to datetime."""
        return datetime.fromtimestamp(self.last_update_timestamp / 1000)

    @property
    def is_buy(self) -> bool:
        """Check if order is a buy order."""
        return self.direction == "buy"

    @property
    def is_sell(self) -> bool:
        """Check if order is a sell order."""
        return self.direction == "sell"

    @property
    def is_open(self) -> bool:
        """Check if order is open."""
        return self.order_state in ["open", "untriggered"]

    @property
    def is_filled(self) -> bool:
        """Check if order is filled."""
        return self.order_state == "filled"

    @property
    def is_cancelled(self) -> bool:
        """Check if order is cancelled."""
        return self.order_state == "cancelled"

    @property
    def is_limit(self) -> bool:
        """Check if order is a limit order."""
        return self.order_type == "limit"

    @property
    def is_market(self) -> bool:
        """Check if order is a market order."""
        return self.order_type == "market"

    @property
    def is_oco(self) -> bool:
        """Check if this is part of an OCO pair."""
        return self.oco_ref is not None

    @property
    def is_oto(self) -> bool:
        """Check if this is part of an OTO setup."""
        return self.is_primary_otoco is True or self.is_secondary_oto is True

    @property
    def is_advanced_order(self) -> bool:
        """Check if this is an advanced order (implv or usd)."""
        return self.advanced is not None

    @property
    def is_mmp_order(self) -> bool:
        """Check if this is a market maker protection order."""
        return self.mmp is True

    @property
    def is_quote(self) -> bool:
        """Check if this is a quote order."""
        return self.quote is True

    @property
    def is_stop_order(self) -> bool:
        """Check if order is a stop order."""
        return self.order_type in ["stop_limit", "stop_market"]

    @property
    def remaining_amount(self) -> float:
        """Calculate remaining amount to be filled."""
        return self.amount - self.filled_amount

    @property
    def fill_percentage(self) -> float:
        """Calculate percentage filled."""
        return (self.filled_amount / self.amount * 100) if self.amount != 0 else 0

    @property
    def has_trigger(self) -> bool:
        """Check if this is a triggered order."""
        return self.trigger is not None

    def __str__(self) -> str:
        """Human-readable representation of the order."""
        status = self.order_state.upper()
        side = self.direction.upper()
        type_str = self.order_type.upper()

        if isinstance(self.price, str):
            price_str = self.price
        else:
            price_str = f"{self.price:.2f}"

        return f"{status} {side} {type_str} {self.instrument_name}: {self.filled_amount}/{self.amount} @ {price_str}"


@dataclass
class AccountFee:
    """Represents a user fee structure in Deribit."""
    currency: str
    fee_type: str  # "relative" or "fixed"
    instrument_type: str  # "future", "perpetual", "option"
    maker_fee: float
    taker_fee: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountFee':
        """Create from API response dict."""
        return cls(
            currency=data.get("currency", ""),
            fee_type=data.get("fee_type", ""),
            instrument_type=data.get("instrument_type", ""),
            maker_fee=data.get("maker_fee", 0.0),
            taker_fee=data.get("taker_fee", 0.0)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert AccountFee object to a dictionary."""
        return {
            "currency": self.currency,
            "fee_type": self.fee_type,
            "instrument_type": self.instrument_type,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee
        }


@dataclass
class AccountSummary:
    """Comprehensive representation of a Deribit account summary."""
    # Basic account balance info
    currency: str
    balance: float
    equity: float
    available_funds: float
    available_withdrawal_funds: float
    margin_balance: float
    initial_margin: float
    maintenance_margin: float
    fee_balance: float

    # Profit and loss fields
    total_pl: float
    session_rpl: float
    session_upl: float
    futures_pl: float
    futures_session_rpl: float
    futures_session_upl: float

    # Options-related fields
    options_pl: float
    options_session_rpl: float
    options_session_upl: float
    options_value: float
    options_delta: float
    options_gamma: float
    options_vega: float
    options_theta: float

    # Reserves and limits
    spot_reserve: float
    additional_reserve: float
    delta_total: float
    projected_delta_total: float

    # Margin-related fields
    projected_initial_margin: float
    projected_maintenance_margin: float
    estimated_liquidation_ratio: Optional[float] = None
    margin_model: Optional[str] = None

    # Cross-collateral fields
    cross_collateral_enabled: Optional[bool] = None
    portfolio_margining_enabled: Optional[bool] = None
    total_equity_usd: Optional[float] = None
    total_initial_margin_usd: Optional[float] = None
    total_maintenance_margin_usd: Optional[float] = None
    total_margin_balance_usd: Optional[float] = None
    total_delta_total_usd: Optional[float] = None

    # User-specific fields
    type: Optional[str] = None
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    system_name: Optional[str] = None
    creation_timestamp: Optional[int] = None
    deposit_address: Optional[str] = None

    # Settings and capabilities
    login_enabled: Optional[bool] = None
    security_keys_enabled: Optional[bool] = None
    interuser_transfers_enabled: Optional[bool] = None
    mmp_enabled: Optional[bool] = None
    self_trading_reject_mode: Optional[str] = None
    self_trading_extended_to_subaccounts: Optional[str] = None
    referrer_id: Optional[str] = None
    has_non_block_chain_equity: Optional[bool] = None

    # Complex nested objects
    options_gamma_map: Optional[Dict[str, float]] = None
    options_vega_map: Optional[Dict[str, float]] = None
    options_theta_map: Optional[Dict[str, float]] = None
    limits: Optional[Dict[str, Any]] = None
    fees: Optional[List[AccountFee]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountSummary':
        """Create an AccountSummary from the API response dictionary."""
        # Parse fees if present
        fees = None
        if data.get("fees"):
            fees = [AccountFee.from_dict(fee) for fee in data.get("fees", [])]

        return cls(
            # Basic account values
            currency=data.get("currency", ""),
            balance=data.get("balance", 0.0),
            equity=data.get("equity", 0.0),
            available_funds=data.get("available_funds", 0.0),
            available_withdrawal_funds=data.get("available_withdrawal_funds", 0.0),
            margin_balance=data.get("margin_balance", 0.0),
            initial_margin=data.get("initial_margin", 0.0),
            maintenance_margin=data.get("maintenance_margin", 0.0),
            fee_balance=data.get("fee_balance", 0.0),

            # PnL fields
            total_pl=data.get("total_pl", 0.0),
            session_rpl=data.get("session_rpl", 0.0),
            session_upl=data.get("session_upl", 0.0),
            futures_pl=data.get("futures_pl", 0.0),
            futures_session_rpl=data.get("futures_session_rpl", 0.0),
            futures_session_upl=data.get("futures_session_upl", 0.0),

            # Options fields
            options_pl=data.get("options_pl", 0.0),
            options_session_rpl=data.get("options_session_rpl", 0.0),
            options_session_upl=data.get("options_session_upl", 0.0),
            options_value=data.get("options_value", 0.0),
            options_delta=data.get("options_delta", 0.0),
            options_gamma=data.get("options_gamma", 0.0),
            options_vega=data.get("options_vega", 0.0),
            options_theta=data.get("options_theta", 0.0),

            # Reserves
            spot_reserve=data.get("spot_reserve", 0.0),
            additional_reserve=data.get("additional_reserve", 0.0),
            delta_total=data.get("delta_total", 0.0),
            projected_delta_total=data.get("projected_delta_total", 0.0),

            # Margin fields
            projected_initial_margin=data.get("projected_initial_margin", 0.0),
            projected_maintenance_margin=data.get("projected_maintenance_margin", 0.0),
            estimated_liquidation_ratio=data.get("estimated_liquidation_ratio"),
            margin_model=data.get("margin_model"),

            # Cross-collateral fields
            cross_collateral_enabled=data.get("cross_collateral_enabled"),
            portfolio_margining_enabled=data.get("portfolio_margining_enabled"),
            total_equity_usd=data.get("total_equity_usd"),
            total_initial_margin_usd=data.get("total_initial_margin_usd"),
            total_maintenance_margin_usd=data.get("total_maintenance_margin_usd"),
            total_margin_balance_usd=data.get("total_margin_balance_usd"),
            total_delta_total_usd=data.get("total_delta_total_usd"),

            # User fields
            type=data.get("type"),
            id=data.get("id"),
            username=data.get("username"),
            email=data.get("email"),
            system_name=data.get("system_name"),
            creation_timestamp=data.get("creation_timestamp"),
            deposit_address=data.get("deposit_address"),

            # Settings
            login_enabled=data.get("login_enabled"),
            security_keys_enabled=data.get("security_keys_enabled"),
            interuser_transfers_enabled=data.get("interuser_transfers_enabled"),
            mmp_enabled=data.get("mmp_enabled"),
            self_trading_reject_mode=data.get("self_trading_reject_mode"),
            self_trading_extended_to_subaccounts=data.get("self_trading_extended_to_subaccounts"),
            referrer_id=data.get("referrer_id"),
            has_non_block_chain_equity=data.get("has_non_block_chain_equity"),

            # Complex objects
            options_gamma_map=data.get("options_gamma_map"),
            options_vega_map=data.get("options_vega_map"),
            options_theta_map=data.get("options_theta_map"),
            limits=data.get("limits"),
            fees=fees
        )

    def to_json(self) -> Dict[str, Any]:
        """
        Converts the AccountSummary object to a JSON-serializable dictionary.
        Handles nested dataclasses and datetime objects.
        """
        # Start with a dictionary representation of the dataclass fields
        data = asdict(self)

        # Handle special types for JSON serialization
        if self.creation_timestamp:
            # The creation_timestamp is already an int (Unix timestamp), which is JSON serializable.
            # If you wanted a datetime string instead, you would convert self.creation_datetime.
            # For consistency with the input, we'll keep creation_timestamp as is.
            pass

        # Convert nested AccountFee objects to dictionaries
        if self.fees:
            data['fees'] = [fee.to_dict() for fee in self.fees]

        return data

    @property
    def creation_datetime(self) -> Optional[datetime]:
        """Convert creation timestamp to datetime if available."""
        if self.creation_timestamp:
            return datetime.fromtimestamp(self.creation_timestamp / 1000)
        return None

    @property
    def margin_level(self) -> float:
        """Calculate margin level (equity / initial_margin)."""
        return self.equity / self.initial_margin if self.initial_margin > 0 else float('inf')

    @property
    def free_collateral(self) -> float:
        """Calculate free collateral (equity - initial_margin)."""
        return self.equity - self.initial_margin

    @property
    def margin_usage_percent(self) -> float:
        """Calculate margin usage as percentage."""
        return (self.initial_margin / self.equity * 100) if self.equity > 0 else 0.0

    @property
    def withdrawal_limit(self) -> float:
        """Maximum amount that can be withdrawn."""
        return min(self.available_withdrawal_funds, self.available_funds)

    @property
    def total_session_pnl(self) -> float:
        """Calculate total session PnL (realized + unrealized)."""
        return self.session_rpl + self.session_upl


@dataclass
class AccountSummaries:
    """Comprehensive representation of account summaries across all currencies."""
    # Account-level fields
    block_rfq_self_match_prevention: Optional[str] = None
    creation_timestamp: Optional[int] = None
    email: Optional[str] = None
    id: Optional[int] = None
    interuser_transfers_enabled: Optional[bool] = None
    login_enabled: Optional[bool] = None
    mmp_enabled: Optional[bool] = None
    referrer_id: Optional[str] = None
    security_keys_enabled: Optional[bool] = None
    self_trading_extended_to_subaccounts: Optional[str] = None
    self_trading_reject_mode: Optional[str] = None
    system_name: Optional[str] = None
    type: Optional[str] = None
    username: Optional[str] = None

    # The list of account summaries, one per currency
    summaries: List[AccountSummary] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountSummaries':
        """Create an AccountSummaries from the API response dictionary."""
        # Parse summaries if present
        summaries = []
        if data.get("summaries"):
            summaries = [AccountSummary.from_dict(summary) for summary in data.get("summaries", [])]

        return cls(
            block_rfq_self_match_prevention=data.get("block_rfq_self_match_prevention"),
            creation_timestamp=data.get("creation_timestamp"),
            email=data.get("email"),
            id=data.get("id"),
            interuser_transfers_enabled=data.get("interuser_transfers_enabled"),
            login_enabled=data.get("login_enabled"),
            mmp_enabled=data.get("mmp_enabled"),
            referrer_id=data.get("referrer_id"),
            security_keys_enabled=data.get("security_keys_enabled"),
            self_trading_extended_to_subaccounts=data.get("self_trading_extended_to_subaccounts"),
            self_trading_reject_mode=data.get("self_trading_reject_mode"),
            system_name=data.get("system_name"),
            type=data.get("type"),
            username=data.get("username"),
            summaries=summaries
        )

    @property
    def creation_datetime(self) -> Optional[datetime]:
        """Convert creation timestamp to datetime if available."""
        if self.creation_timestamp:
            return datetime.fromtimestamp(self.creation_timestamp / 1000)
        return None

    def get_summary_by_currency(self, currency: str) -> Optional[AccountSummary]:
        """Find and return a specific currency summary."""
        for summary in self.summaries:
            if summary.currency == currency:
                return summary
        return None

    def get_total_equity_usd(self) -> float:
        """Calculate total equity across all currencies in USD."""
        total = 0.0
        for summary in self.summaries:
            if summary.total_equity_usd is not None:
                total += summary.total_equity_usd
        return total


@dataclass
class BookSummary:
    ask_price: Optional[float]
    base_currency: str
    bid_price: Optional[float]
    creation_timestamp: int
    current_funding: Optional[float]
    estimated_delivery_price: Optional[float]
    funding_8h: Optional[float]
    high: Optional[float]
    instrument_name: str
    interest_rate: Optional[float]
    last: Optional[float]
    low: Optional[float]
    mark_iv: Optional[float]
    mark_price: float
    mid_price: Optional[float]
    open_interest: Optional[float]
    price_change: Optional[float]
    quote_currency: str
    underlying_index: Optional[str]
    underlying_price: Optional[float]
    volume: float
    volume_notional: Optional[float]
    volume_usd: Optional[float]

    @classmethod
    def from_dict(cls, data: dict) -> "BookSummary":
        return cls(
            ask_price=data.get("ask_price"),
            base_currency=data["base_currency"],
            bid_price=data.get("bid_price"),
            creation_timestamp=data["creation_timestamp"],
            current_funding=data.get("current_funding"),
            estimated_delivery_price=data.get("estimated_delivery_price"),
            funding_8h=data.get("funding_8h"),
            high=data.get("high"),
            instrument_name=data["instrument_name"],
            interest_rate=data.get("interest_rate"),
            last=data.get("last"),
            low=data.get("low"),
            mark_iv=data.get("mark_iv"),
            mark_price=data["mark_price"],
            mid_price=data.get("mid_price"),
            open_interest=data.get("open_interest"),
            price_change=data.get("price_change"),
            quote_currency=data["quote_currency"],
            underlying_index=data.get("underlying_index"),
            underlying_price=data.get("underlying_price"),
            volume=data["volume"],
            volume_notional=data.get("volume_notional"),
            volume_usd=data.get("volume_usd"),
        )


@dataclass
class OrderSubmitResponse:
    """Response from submitting an order (buy/sell) to Deribit."""
    order: Order  # Using the existing Order model
    trades: List[Trade]  # Using the existing Trade model

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderSubmitResponse':
        """Create from API response dictionary."""
        return cls(
            order=Order.from_dict(data["order"]),
            trades=[Trade.from_dict(trade) for trade in data.get("trades", [])]
        )


@dataclass
class OrderCancelResponse:
    """Response from cancelling an order via the 'private/cancel' endpoint."""
    order: Optional[Order] = None  # The cancelled order, if successful
    error: Optional[Dict[str, Any]] = None  # Error information if the cancellation failed

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderCancelResponse':
        """Create from API response dictionary."""
        # Check if the response contains an error
        if "error" in data:
            return cls(order=None, error=data["error"])

        # If no error, process the successful cancellation
        return cls(
            order=Order.from_dict(data),
            error=None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response model to a dictionary."""
        result = {
            "success": self.is_successful,
        }

        if self.is_successful and self.order:
            # For successful cancellations, include order details
            # Use any existing to_dict method on the Order class if available
            if hasattr(self.order, "to_dict"):
                result["order"] = self.order.to_dict()
            else:
                # Fallback: manually convert order to dict
                order_dict = {
                    "order_id": self.order.order_id,
                    "instrument_name": self.order.instrument_name,
                    "order_state": self.order.order_state,
                    "direction": self.order.direction,
                    "amount": self.order.amount,
                    "price": self.order.price,
                    "filled_amount": self.order.filled_amount,
                    "average_price": self.order.average_price,
                    "cancel_reason": self.order.cancel_reason,
                    "creation_timestamp": self.order.creation_timestamp,
                    "last_update_timestamp": self.order.last_update_timestamp,
                }
                result["order"] = order_dict

        if not self.is_successful and self.error:
            # For failed cancellations, include error details
            result["error"] = {
                "code": self.error_code,
                "message": self.error_message,
                # Include any other error fields
                **{k: v for k, v in self.error.items() if k not in ["code", "message"]}
            }

        return result

    @property
    def is_successful(self) -> bool:
        """Check if the cancellation was successful."""
        return self.order is not None and self.error is None

    @property
    def order_id(self) -> Optional[str]:
        """Get the ID of the cancelled order."""
        return self.order.order_id if self.order else None

    @property
    def error_message(self) -> Optional[str]:
        """Get the error message if the cancellation failed."""
        return self.error.get("message") if self.error else None

    @property
    def error_code(self) -> Optional[int]:
        """Get the error code if the cancellation failed."""
        return self.error.get("code") if self.error else None


@dataclass
class TransactionLogEntry:
    """Represents a single entry in the transaction log."""
    # Core fields
    id: int
    timestamp: int
    currency: str
    type: str
    user_seq: int

    # Balance fields
    cashflow: float
    balance: float
    change: float
    equity: Optional[float] = None

    # User info
    user_id: Optional[int] = None
    username: Optional[str] = None

    # Trade-related fields (optional)
    instrument_name: Optional[str] = None
    trade_id: Optional[str] = None
    order_id: Optional[str] = None
    side: Optional[str] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    position: Optional[float] = None

    # Fee and P&L fields
    commission: Optional[float] = None
    interest_pl: Optional[float] = None
    session_rpl: Optional[float] = None
    session_upl: Optional[float] = None
    settlement_price: Optional[float] = None

    # Additional info (can be dict or string from Deribit API)
    info: Optional[Union[Dict[str, Any], str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransactionLogEntry':
        """Create from API response dictionary."""
        return cls(
            id=data.get("id", 0),
            timestamp=data.get("timestamp", 0),
            currency=data.get("currency", ""),
            type=data.get("type", ""),
            user_seq=data.get("user_seq", 0),
            cashflow=data.get("cashflow", 0.0),
            balance=data.get("balance", 0.0),
            change=data.get("change", 0.0),
            equity=data.get("equity"),
            user_id=data.get("user_id"),
            username=data.get("username"),
            instrument_name=data.get("instrument_name"),
            trade_id=data.get("trade_id"),
            order_id=data.get("order_id"),
            side=data.get("side"),
            amount=data.get("amount"),
            price=data.get("price"),
            position=data.get("position"),
            commission=data.get("commission"),
            interest_pl=data.get("interest_pl"),
            session_rpl=data.get("session_rpl"),
            session_upl=data.get("session_upl"),
            settlement_price=data.get("settlement_price"),
            info=data.get("info"),
        )

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def is_trade(self) -> bool:
        """Check if this entry is a trade."""
        return self.type == "trade"

    @property
    def is_deposit(self) -> bool:
        """Check if this entry is a deposit."""
        return self.type == "deposit"

    @property
    def is_withdrawal(self) -> bool:
        """Check if this entry is a withdrawal."""
        return self.type == "withdrawal"

    @property
    def is_transfer(self) -> bool:
        """Check if this entry is a transfer."""
        return self.type == "transfer"

    @property
    def is_settlement(self) -> bool:
        """Check if this entry is a settlement."""
        return self.type == "settlement"

    @property
    def is_delivery(self) -> bool:
        """Check if this entry is a delivery."""
        return self.type == "delivery"


@dataclass
class TransactionLogResponse:
    """Response from get_transaction_log containing logs and pagination info."""
    logs: List[TransactionLogEntry]
    continuation: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransactionLogResponse':
        """Create from API response dictionary."""
        logs = [TransactionLogEntry.from_dict(log) for log in data.get("logs", [])]
        return cls(
            logs=logs,
            continuation=data.get("continuation"),
        )

    @property
    def has_more(self) -> bool:
        """Check if there are more results to fetch."""
        return self.continuation is not None

    @property
    def count(self) -> int:
        """Get the number of log entries."""
        return len(self.logs)
