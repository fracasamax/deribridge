from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class OrderBookLevel:
    """Represents a single level in the order book"""
    price: float
    amount: float


@dataclass
class OrderBook:
    """Represents the full order book for an instrument"""
    instrument_name: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    change_id: Optional[int] = None

    def update(self, bids: List[List[float]], asks: List[List[float]], change_id: Optional[int] = None):
        """Update the order book with new data"""
        self.bids = [OrderBookLevel(price=p, amount=a) for p, a in bids]
        self.asks = [OrderBookLevel(price=p, amount=a) for p, a in asks]
        self.timestamp = datetime.now(timezone.utc)
        if change_id:
            self.change_id = change_id

    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """Get the best bid (highest price)"""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """Get the best ask (lowest price)"""
        return self.asks[0] if self.asks else None

    def get_spread(self) -> Optional[float]:
        """Get the spread between best bid and ask"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None
