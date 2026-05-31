from enum import Enum
from pydantic_core import CoreSchema, core_schema


class OrderPurpose(str, Enum):
    """
    Defines the purpose (direction) of an order in the market.

    Attributes:
        BUY: Buy order (long position)
        SELL: Sell order (short position)
    """
    BUY = "buy"
    SELL = "sell"

    def __str__(self) -> str:
        """Convert to lowercase string for API submission."""
        return self.value.lower()

    def opposite(self) -> 'OrderPurpose':
        """Return the opposite purpose (BUY -> SELL, SELL -> BUY)."""
        return OrderPurpose.SELL if self == OrderPurpose.BUY else OrderPurpose.BUY

    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self == OrderPurpose.BUY

    def is_sell(self) -> bool:
        """Check if this is a sell order."""
        return self == OrderPurpose.SELL

    def direction_multiplier(self) -> int:
        """
        Return the direction multiplier:
        - 1 for buy (long)
        - -1 for sell (short)

        Useful for calculations where direction matters.
        """
        return 1 if self == OrderPurpose.BUY else -1

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler) -> CoreSchema:
        """Used by Pydantic v2 for schema generation and validation."""
        return core_schema.with_info_plain_validator_function(
            cls._validate,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: instance.value.lower() if instance else None
            ),
        )

    @classmethod
    def _validate(cls, value, info):
        """Validate and convert input to OrderPurpose enum."""
        # If already an OrderPurpose instance, return it
        if isinstance(value, cls):
            return value
        # If it's a string, convert it in a case-insensitive manner
        if isinstance(value, str):
            try:
                return cls(value.lower())
            except ValueError:
                raise ValueError(f"Invalid {cls.__name__} value: {value}. Must be 'buy' or 'sell'.")
        raise ValueError(f"Invalid {cls.__name__} value: {value}. Must be a string or OrderPurpose.")

    @classmethod
    def from_direction(cls, direction: str) -> 'OrderPurpose':
        """Create an OrderPurpose from a direction string."""
        return cls._validate(direction, None)

    @classmethod
    def from_position_sign(cls, size: float) -> 'OrderPurpose':
        """
        Determine purpose from position size sign.

        Args:
            size: Position size (positive for long, negative for short)

        Returns:
            OrderPurpose.BUY for positive size, OrderPurpose.SELL for negative
        """
        return OrderPurpose.BUY if size >= 0 else OrderPurpose.SELL