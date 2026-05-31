from enum import    Enum

class OrderState(Enum):
    """Enum for order states"""
    OPEN = "open"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNTRIGGERED = "untriggered"