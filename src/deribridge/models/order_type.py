from enum import Enum


class OrderType(Enum):
    """Enum for order types"""
    LIMIT = "limit"
    MARKET = "market"
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"
