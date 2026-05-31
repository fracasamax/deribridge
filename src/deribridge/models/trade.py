from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class Trade:
    """Represents a single trade"""
    trade_id: str
    instrument_name: str
    timestamp: int
    direction: str  # buy or sell
    price: float
    amount: float
    fee: float
    fee_currency: str
    order_id: str
    order_type: str  # limit, market, or liquidation
    liquidity: str  # M (maker) or T (taker)
    index_price: float
    mark_price: Optional[float] = None
    profit_loss: Optional[float] = None
    tick_direction: Optional[int] = None
    contracts: Optional[float] = None
    iv: Optional[float] = None  # Options only
    underlying_price: Optional[float] = None  # Options only
    label: Optional[str] = None
    api: bool = False
    post_only: bool = False
    reduce_only: bool = False
    mmp: bool = False
    risk_reducing: bool = False
    state: Optional[str] = None
    advanced: Optional[str] = None
    quote_id: Optional[str] = None
    quote_set_id: Optional[str] = None
    block_trade_id: Optional[str] = None
    block_rfq_id: Optional[int] = None
    block_rfq_quote_id: Optional[int] = None
    combo_id: Optional[str] = None
    combo_trade_id: Optional[int] = None
    liquidation: Optional[str] = None
    trade_seq: Optional[int] = None
    legs: Optional[List[Dict]] = None

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime"""
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def is_buy(self) -> bool:
        """Check if trade is a buy"""
        return self.direction == "buy"

    @property
    def is_maker(self) -> bool:
        """Check if trade was maker"""
        return self.liquidity == "M"

    @property
    def total_cost(self) -> float:
        """Calculate total cost including fees"""
        cost = self.price * self.amount
        if self.fee_currency == self.instrument_name.split('-')[0]:
            # Fee in base currency
            return cost + self.fee
        return cost  # Fee in different currency, not included

    def to_dict(self) -> dict:
        """Convert to dictionary for Redis storage"""
        return {
            "trade_id": self.trade_id,
            "instrument_name": self.instrument_name,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "price": self.price,
            "amount": self.amount,
            "fee": self.fee,
            "fee_currency": self.fee_currency,
            "order_id": self.order_id,
            "order_type": self.order_type,
            "liquidity": self.liquidity,
            "index_price": self.index_price,
            "mark_price": self.mark_price,
            "profit_loss": self.profit_loss,
            "tick_direction": self.tick_direction,
            "contracts": self.contracts,
            "iv": self.iv,
            "underlying_price": self.underlying_price,
            "label": self.label,
            "api": self.api,
            "post_only": self.post_only,
            "reduce_only": self.reduce_only,
            "mmp": self.mmp,
            "risk_reducing": self.risk_reducing,
            "state": self.state,
            "advanced": self.advanced,
            "quote_id": self.quote_id,
            "quote_set_id": self.quote_set_id,
            "block_trade_id": self.block_trade_id,
            "block_rfq_id": self.block_rfq_id,
            "block_rfq_quote_id": self.block_rfq_quote_id,
            "combo_id": self.combo_id,
            "combo_trade_id": self.combo_trade_id,
            "liquidation": self.liquidation,
            "trade_seq": self.trade_seq,
            "legs": self.legs
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Trade':
        """Create Trade from dictionary"""
        return cls(**data)
