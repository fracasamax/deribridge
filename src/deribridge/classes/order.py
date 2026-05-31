from enum import Enum
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, field_serializer

from ..classes.order_purpose import OrderPurpose


class OrderType(str, Enum):
    """
    Defines the type of order to be submitted to the exchange.
    
    Deribit supports various order types with different execution behaviors.
    """
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"
    TAKE_LIMIT = "take_limit"
    MARKET = "market"
    STOP_MARKET = "stop_market"
    TAKE_MARKET = "take_market"
    MARKET_LIMIT = "market_limit"
    TRAILING_STOP = "trailing_stop"

    def __str__(self) -> str:
        """Convert to lowercase string for API submission."""
        return self.value.lower()

    def is_market(self) -> bool:
        """Check if this is a market order type."""
        return self in _MARKET_ORDER_TYPES

    def is_limit(self) -> bool:
        """Check if this is a limit order type."""
        return self in _LIMIT_ORDER_TYPES

    def is_conditional(self) -> bool:
        """Check if this is a conditional order type."""
        return self in _CONDITIONAL_ORDER_TYPES

    def requires_price(self) -> bool:
        """Check if this order type requires a price parameter."""
        return self in _LIMIT_ORDER_TYPES

    def requires_trigger_price(self) -> bool:
        """Check if this order type requires a trigger price parameter."""
        return self in {
            OrderType.STOP_LIMIT,
            OrderType.TAKE_LIMIT,
            OrderType.STOP_MARKET,
            OrderType.TAKE_MARKET,
        }

    @classmethod
    def _validate(cls, value, info):
        """Validate and convert input to OrderType enum."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value.lower())
            except ValueError:
                raise ValueError(f"Invalid {cls.__name__} value: {value}")
        raise ValueError(f"Invalid {cls.__name__} value: {value}")


# Order-type groups, kept OUTSIDE the Enum body so they remain plain
# frozensets of members rather than being absorbed as enum members (which made
# the previous `self in self.MARKET_TYPES` checks do str substring matching).
_MARKET_ORDER_TYPES = frozenset({
    OrderType.MARKET,
    OrderType.STOP_MARKET,
    OrderType.TAKE_MARKET,
    OrderType.MARKET_LIMIT,
})
_LIMIT_ORDER_TYPES = frozenset({
    OrderType.LIMIT,
    OrderType.STOP_LIMIT,
    OrderType.TAKE_LIMIT,
})
_CONDITIONAL_ORDER_TYPES = frozenset({
    OrderType.STOP_LIMIT,
    OrderType.TAKE_LIMIT,
    OrderType.STOP_MARKET,
    OrderType.TAKE_MARKET,
    OrderType.TRAILING_STOP,
})


class TimeInForce(str, Enum):
    """
    Defines how long an order remains active before it is executed or expires.
    
    Attributes:
        GOOD_TIL_CANCELLED: Order remains active until explicitly cancelled
        FILL_OR_KILL: Order must be filled immediately in full or cancelled
        IMMEDIATE_OR_CANCEL: Order must be filled immediately (partial fills allowed) or cancelled
    """
    GOOD_TIL_CANCELLED = "good_til_cancelled"
    FILL_OR_KILL = "fill_or_kill"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"

    def __str__(self) -> str:
        """Convert to lowercase string for API submission."""
        return self.value.lower()

    @classmethod
    def _validate(cls, value, info):
        """Validate and convert input to TimeInForce enum."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            # Handle shorthand forms
            if value.upper() == "GTC":
                return cls.GOOD_TIL_CANCELLED
            elif value.upper() == "FOK":
                return cls.FILL_OR_KILL
            elif value.upper() == "IOC":
                return cls.IMMEDIATE_OR_CANCEL

            # Handle regular forms
            try:
                return cls(value.lower())
            except ValueError:
                raise ValueError(f"Invalid {cls.__name__} value: {value}")
        raise ValueError(f"Invalid {cls.__name__} value: {value}")


class OrderState(str, Enum):
    """
    Defines the current state of an order in the order lifecycle.
    
    Attributes:
        OPEN: Order is active and not fully filled
        FILLED: Order has been completely filled
        REJECTED: Order was rejected by the exchange
        CANCELLED: Order was cancelled by the user or system
        UNTRIGGERED: Conditional order that hasn't been triggered yet
    """
    OPEN = "open"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNTRIGGERED = "untriggered"

    def __str__(self) -> str:
        """Convert to lowercase string."""
        return self.value.lower()

    def is_active(self) -> bool:
        """Check if the order is still active in the market."""
        return self in {self.OPEN, self.UNTRIGGERED}

    def is_terminal(self) -> bool:
        """Check if the order has reached a terminal state."""
        return self in {self.FILLED, self.REJECTED, self.CANCELLED}


class Order(BaseModel):
    """
    Represents an order to be submitted to the Deribit exchange.
    
    This model includes all parameters needed for order submission
    and validates them according to exchange requirements.
    """
    # Required fields
    instrument_name: str

    # Order direction and size
    purpose: OrderPurpose = Field(..., description="Order direction (buy/sell)")
    amount: Optional[float] = Field(None, description="Order size in base currency units")
    contracts: Optional[float] = Field(None, description="Order size in contracts")

    # Order execution parameters
    order_type: OrderType = Field(OrderType.LIMIT, description="Order type")
    price: Optional[float] = Field(None, description="Order price (required for limit orders)")
    time_in_force: TimeInForce = Field(TimeInForce.GOOD_TIL_CANCELLED, description="Time in force policy")

    # Optional parameters
    post_only: Optional[bool] = Field(None, description="Whether order must be maker only")
    reduce_only: Optional[bool] = Field(None, description="Whether order should only reduce position")
    reject_post_only: Optional[bool] = Field(None, description="Whether to reject if post-only can't be met")

    # Advanced parameters
    advanced: Optional[Literal["usd", "implv"]] = Field(None, description="Advanced order type (options only)")
    valid_until: Optional[int] = Field(None, description="Timestamp until which the order is valid (UTC)")
    max_show: Optional[float] = Field(None, description="Maximum amount to be shown to other traders")

    # Trigger parameters for conditional orders
    trigger: Optional[Literal["index_price", "mark_price", "last_price"]] = Field(
        None, description="Price to trigger conditional orders"
    )
    trigger_price: Optional[float] = Field(None, description="Price at which to trigger the order")

    # Risk management
    max_slippage: Optional[float] = Field(None, description="Maximum allowed slippage for market orders in %")

    # Tracking fields (not sent to exchange)
    label: Optional[str] = Field(None, description="Custom order label for tracking")
    created_at: Optional[datetime] = Field(None, description="Order creation timestamp")

    # Order state fields (for received orders)
    order_id: Optional[str] = Field(None, description="Exchange order ID")
    order_state: Optional[OrderState] = Field(None, description="Current order state")
    filled_amount: Optional[float] = Field(0.0, description="Amount filled so far")
    average_price: Optional[float] = Field(None, description="Average fill price")
    last_update_timestamp: Optional[int] = Field(None, description="Last update timestamp from exchange")

    # Validation methods
    @field_validator('amount')
    def amount_must_be_positive_or_none(cls, v):
        """Validate that amount is positive or None."""
        if v is not None and v <= 0:
            raise ValueError('Amount must be positive or None')
        return v

    @field_validator('contracts')
    def contracts_must_be_positive_or_none(cls, v):
        """Validate that contracts is positive or None."""
        if v is not None and v <= 0:
            raise ValueError('Contracts must be positive or None')
        return v

    @model_validator(mode='after')
    def validate_order(self):
        """Validate the entire order structure for consistency."""
        # Ensure either amount or contracts is provided
        if self.amount is None and self.contracts is None:
            raise ValueError('Either amount or contracts must be provided')

        # Ensure price is provided for limit orders
        if self.order_type.is_limit() and self.price is None:
            raise ValueError(f'Price is required for {self.order_type} orders')

        # Ensure trigger price is provided for conditional orders that require it
        if (self.order_type.is_conditional() and
                not self.order_type.is_market() and
                self.order_type.requires_trigger_price() and
                self.trigger_price is None):
            raise ValueError(f'Trigger price is required for {self.order_type} orders')

        # Set created_at if not provided
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.now(timezone.utc))

        return self

    # Serialization methods
    @field_serializer('created_at')
    def serialize_dt(self, dt: Optional[datetime], _info):
        """Serialize datetime to ISO format."""
        if dt is None:
            return None
        return dt.isoformat()

    # Utility methods
    def to_json(self) -> str:
        """
        Convert the Order instance to a JSON string for API submission.
        The output will use field aliases.
        """
        return self.model_dump_json(by_alias=True)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Order instance to a dictionary suitable for API submission.
        The output will use field aliases.
        """
        return self.model_dump(by_alias=True)

    def api_params(self) -> Dict[str, Any]:
        """
        Get parameters for API submission, excluding None values and internal fields.
        """
        # Start with regular dict but exclude None values
        params = {k: v for k, v in self.to_dict().items() if v is not None}

        # Remove fields that shouldn't be sent to the API
        for field in ['created_at', 'order_id', 'order_state', 'filled_amount',
                      'average_price', 'last_update_timestamp']:
            params.pop(field, None)

        return params

    def remaining_amount(self) -> float:
        """Calculate remaining unfilled amount."""
        if self.amount is None:
            return 0.0
        return self.amount - (self.filled_amount or 0.0)

    def is_active(self) -> bool:
        """Check if the order is currently active in the market."""
        if self.order_state is None:
            return False
        return self.order_state.is_active()

    def is_filled(self) -> bool:
        """Check if the order has been filled."""
        return self.order_state == OrderState.FILLED

    def fill_percentage(self) -> float:
        """Calculate the percentage of the order that has been filled."""
        if self.amount is None or self.amount == 0:
            return 0.0
        return (self.filled_amount or 0.0) / self.amount * 100

    def would_execute_at(self, market_price: float) -> bool:
        """Check if the order would execute at the given market price."""
        if not self.price:
            return True  # Market orders always execute

        if self.purpose == OrderPurpose.BUY:
            return market_price <= self.price
        else:
            return market_price >= self.price

    @classmethod
    def market_buy(cls, instrument_name: str, amount: float, **kwargs) -> 'Order':
        """Create a market buy order."""
        return cls(
            instrument_name=instrument_name,
            purpose=OrderPurpose.BUY,
            amount=amount,
            order_type=OrderType.MARKET,
            **kwargs
        )

    @classmethod
    def market_sell(cls, instrument_name: str, amount: float, **kwargs) -> 'Order':
        """Create a market sell order."""
        return cls(
            instrument_name=instrument_name,
            purpose=OrderPurpose.SELL,
            amount=amount,
            order_type=OrderType.MARKET,
            **kwargs
        )

    @classmethod
    def limit_buy(cls, instrument_name: str, amount: float, price: float, **kwargs) -> 'Order':
        """Create a limit buy order."""
        return cls(
            instrument_name=instrument_name,
            purpose=OrderPurpose.BUY,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            **kwargs
        )

    @classmethod
    def limit_sell(cls, instrument_name: str, amount: float, price: float, **kwargs) -> 'Order':
        """Create a limit sell order."""
        return cls(
            instrument_name=instrument_name,
            purpose=OrderPurpose.SELL,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            **kwargs
        )

    # Pydantic configuration
    model_config = ConfigDict(
        populate_by_name=True,  # Allow population by alias
        str_strip_whitespace=True,  # Strip whitespace from string values
        validate_assignment=True,  # Validate when values are assigned
    )
