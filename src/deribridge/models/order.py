from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from .order_state import OrderState


@dataclass
class Order:
    """Represents a single order"""
    order_id: str
    instrument_name: str
    order_type: str
    order_state: str
    direction: str
    amount: float
    price: float  # Can be market price
    filled_amount: float
    average_price: Optional[float]
    creation_timestamp: int
    last_update_timestamp: int
    time_in_force: str
    max_show: float
    post_only: bool = False
    reduce_only: bool = False
    reject_post_only: bool = False
    label: Optional[str] = None

    # Advanced order fields
    advanced: Optional[str] = None
    usd: Optional[float] = None
    implv: Optional[float] = None

    # Trigger order fields
    trigger: Optional[str] = None
    trigger_price: Optional[float] = None
    trigger_offset: Optional[float] = None
    trigger_reference_price: Optional[float] = None
    trigger_fill_condition: Optional[str] = None
    triggered: bool = False
    trigger_order_id: Optional[str] = None

    # Order relationships
    oco_ref: Optional[str] = None
    oto_order_ids: Optional[List[str]] = None
    is_primary_otoco: bool = False
    is_secondary_oto: bool = False
    primary_order_id: Optional[str] = None

    # Execution info
    contracts: Optional[float] = None
    cancel_reason: Optional[str] = None
    replaced: bool = False
    auto_replaced: bool = False
    original_order_type: Optional[str] = None

    # Source info
    api: bool = False
    web: bool = False
    mobile: bool = False
    app_name: Optional[str] = None
    quote: bool = False
    quote_id: Optional[str] = None
    quote_set_id: Optional[str] = None

    # Risk management
    mmp: bool = False
    mmp_group: Optional[str] = None
    mmp_cancelled: bool = False
    risk_reducing: bool = False
    is_liquidation: bool = False
    is_rebalance: bool = False
    block_trade: bool = False

    @property
    def datetime_created(self) -> datetime:
        """Convert creation timestamp to datetime"""
        return datetime.fromtimestamp(self.creation_timestamp / 1000)

    @property
    def datetime_updated(self) -> datetime:
        """Convert update timestamp to datetime"""
        return datetime.fromtimestamp(self.last_update_timestamp / 1000)

    @property
    def is_open(self) -> bool:
        """Check if order is open"""
        return self.order_state == OrderState.OPEN.value

    @property
    def is_filled(self) -> bool:
        """Check if order is filled"""
        return self.order_state == OrderState.FILLED.value

    @property
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.order_state == OrderState.CANCELLED.value

    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage"""
        if self.amount == 0:
            return 0
        return (self.filled_amount / self.amount) * 100

    @property
    def remaining_amount(self) -> float:
        """Calculate remaining amount"""
        return self.amount - self.filled_amount

    def to_dict(self) -> dict:
        """Convert to dictionary for Redis storage"""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Order':
        """Create Order from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
