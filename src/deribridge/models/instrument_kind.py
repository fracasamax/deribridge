from enum import Enum


class InstrumentKind(Enum):
    """Enum for instrument kinds"""
    FUTURE = "future"
    OPTION = "option"
    SPOT = "spot"
    FUTURE_COMBO = "future_combo"
    OPTION_COMBO = "option_combo"
    COMBO = "combo"
    ANY = "any"