"""Binance adapter (reference REST + WebSocket example).

Requires the ``binance`` extra (``pip install deribridge[binance]``); importing
this package without it raises ``ModuleNotFoundError`` for the missing
transport dependency, which the registry surfaces as a friendly
``MissingExchangeExtra``.
"""
from .adapter import BinanceAdapter
from .capabilities import BINANCE_CAPABILITIES

__all__ = ["BinanceAdapter", "BINANCE_CAPABILITIES"]
