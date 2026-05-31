from enum import Enum


class TimeInForce(Enum):
    """Enum for time in force"""
    GTC = "good_til_cancelled"
    GTD = "good_til_day"
    FOK = "fill_or_kill"
    IOC = "immediate_or_cancel"
