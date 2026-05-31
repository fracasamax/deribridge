from enum import Enum


class InstrumentType(Enum):
    SPOT = "spot"
    FUTURE = "future"
    OPTION = "option"
