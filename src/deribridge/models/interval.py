from enum import Enum


class Interval(Enum):
    """Enum for notification intervals"""
    AGG2 = "agg2"
    MS100 = "100ms"
    RAW = "raw"