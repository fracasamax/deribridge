import csv
import math
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError, field_validator

from ..classes.instrument import Instrument
from ..classes.instrument_type import InstrumentType
from ..classes.order_purpose import OrderPurpose
from ..api_client.deribit_instrument import DeribitInstrument
from ..classes.order import Order, OrderType, TimeInForce


class TradePlanItem(BaseModel):
    # Required CSV fields (using aliases to map CSV column names)
    # instrument: str = Field(..., alias="Instrument")
    instrument: Instrument = Field(..., alias="Instrument")
    amount: float = Field(..., alias="Amount")

    # Optional CSV fields
    value: Optional[float] = Field(None, alias="Value")
    avg_price: Optional[float] = Field(None, alias="Avg. Price")
    mark_price: Optional[float] = Field(None, alias="Mark Price")
    pnl: Optional[float] = Field(None, alias="PNL")
    pnl_dollar: Optional[float] = Field(None, alias="PNL ($)")
    pnl_expiry: Optional[float] = Field(None, alias="PNL Expiry")
    iv: Optional[float] = Field(None, alias="IV")
    delta: Optional[float] = Field(None, alias="Delta")
    vega: Optional[float] = Field(None, alias="Vega")
    weighted_vega: Optional[float] = Field(None, alias="Weighted Vega")
    gamma: Optional[float] = Field(None, alias="Gamma")
    theta: Optional[float] = Field(None, alias="Theta")
    rho: Optional[float] = Field(None, alias="Rho")
    im: Optional[float] = Field(None, alias="IM")
    mm: Optional[float] = Field(None, alias="MM")
    one_percent_gamma_pnl: Optional[float] = Field(None, alias="1% Gamma PNL")
    index: Optional[float] = Field(None, alias="Index")
    forward: Optional[float] = Field(None, alias="Forward")

    # Extra fields not directly coming from the CSV.
    # If limit_price is not provided, it will be set equal to avg_price.
    limit_price: Optional[float] = None
    # Computed based on the sign of amount.
    purpose: Optional[OrderPurpose] = None

    @field_validator("instrument", mode="before")
    def parse_instrument_field(cls, v):
        """
        Convert the CSV string into an Instrument instance.
        If 'v' is a string, we assume it's a Deribit instrument name.
        """
        if isinstance(v, str):
            # Use the DeribitInstrument parser.
            return DeribitInstrument.parse_instrument(v)
        return v

    @model_validator(mode="after")
    def set_computed_fields(self) -> "TradePlanItem":
        # Set limit_price: if not provided, use avg_price.
        if self.limit_price is None:
            if self.avg_price is not None:
                object.__setattr__(self, "limit_price", self.avg_price)
            else:
                raise ValueError(
                    "limit_price is required (or must be derivable from avg_price) but both are missing."
                )
        # Compute purpose based on the sign of amount.
        if self.amount > 0:
            object.__setattr__(self, "purpose", OrderPurpose.BUY)
        elif self.amount < 0:
            object.__setattr__(self, "purpose", OrderPurpose.SELL)
        else:
            object.__setattr__(self, "purpose", None)
        return self

    @staticmethod
    def round_price(*, price, purpose, tick_size):
        if purpose == OrderPurpose.BUY:
            # Floor rounding: ensures price is at or below your calculated limit.
            return math.floor(price / tick_size) * tick_size
        elif purpose == OrderPurpose.SELL:
            # Ceiling rounding: ensures price is at or above your calculated limit.
            return math.ceil(price / tick_size) * tick_size
        else:
            raise ValueError("Side must be either 'buy' or 'sell'.")

    def to_order(self, *,
                 order_type: OrderType = OrderType.LIMIT,
                 time_in_force: TimeInForce = TimeInForce.GOOD_TIL_CANCELLED,
                 post_only: Optional[bool] = None,
                 reject_post_only: Optional[bool] = None,
                 advanced: Optional[Literal["usd", "implv"]] = None,
                 valid_until: Optional[int] = None,
                 ) -> Order:
        instrument_name = self.instrument.instrument_name if hasattr(self.instrument, "instrument_name") else str(
            self.instrument)

        # purpose must be non-None to build a directional order
        if self.purpose is None:
            raise ValueError(
                "Cannot create an order from a zero-amount TradePlanItem (purpose is undefined)."
            )

        # order price rounding
        rounded_price: float
        if self.instrument.instrument_type == InstrumentType.FUTURE:
            rounded_price = self.round_price(
                price=self.limit_price, purpose=self.purpose, tick_size=0.5)
        elif self.instrument.instrument_type == InstrumentType.OPTION:
            rounded_price = self.round_price(
                price=self.limit_price, purpose=self.purpose, tick_size=0.0005)
        else:
            raise ValueError("Unsupported instrument type for rounding.")

        # Create and return the Order instance.
        return Order(
            instrument_name=instrument_name,
            purpose=self.purpose,
            amount=abs(self.amount),
            contracts=None,
            order_type=order_type,
            price=rounded_price,
            time_in_force=time_in_force,
            post_only=post_only,
            reduce_only=None,
            reject_post_only=reject_post_only,
            advanced=advanced,
            valid_until=valid_until,
            max_show=None,
            trigger=None,
            trigger_price=None,
            max_slippage=None,
            label=None,
            created_at=None,
            order_id=None,
            order_state=None,
            filled_amount=None,
            average_price=None,
            last_update_timestamp=None,
        )

    model_config = ConfigDict(populate_by_name=True)  # Allow population using field names and aliases


class TradePlan(BaseModel):
    items: List[TradePlanItem]

    @classmethod
    def from_csv(cls, filepath: str) -> "TradePlan":
        """
        Create a TradePlan from a CSV file.
        Only 'Instrument' and 'Amount' are required; other fields are optional.
        """
        items: List[TradePlanItem] = []
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    item = TradePlanItem.model_validate(row)
                    items.append(item)
                except ValidationError as e:
                    # Log or handle validation errors for this row.
                    print(f"Validation error for row {row}: {e.json()}")
        return cls(items=items)

    def to_csv(self, filepath: str) -> None:
        """
        Writes the TradePlan items to a CSV file.
        The CSV will use the original field aliases as headers.
        """
        if not self.items:
            raise ValueError("Trade plan is empty.")
        # Use the first item's model_dump (with aliases) to extract header names.
        header = list(self.items[0].model_dump(by_alias=True).keys())
        with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header)
            writer.writeheader()
            for item in self.items:
                writer.writerow(item.model_dump(by_alias=True))
