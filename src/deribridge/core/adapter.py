"""The :class:`ExchangeAdapter` ABC — the public extension point.

A new exchange is added by subclassing this and mapping its API to the
canonical models. Market-data, trading, account, and streaming methods that an
adapter cannot support default to raising
:class:`~deribridge.core.errors.UnsupportedOperation`, so an adapter only
overrides what it actually does — and :attr:`capabilities` stays honest.

Order methods carry the framework safety contract: return a canonical
:class:`~deribridge.core.models.Order` on success, raise
:class:`~deribridge.core.errors.OrderRejected` on a definite failure, and raise
:class:`~deribridge.core.errors.IndeterminateOrderError` when the outcome is
unknown (timeout / mid-flight disconnect).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, ClassVar, Optional, Union

from .capabilities import Capabilities
from .errors import UnsupportedOperation
from .enums import AssetKind, Interval
from .models import (
    AccountSummary,
    Candle,
    FundingRate,
    Instrument,
    Order,
    OrderBook,
    OrderRequest,
    Position,
    Symbol,
    Ticker,
    Trade,
)
from .transport.auth import Credentials
from .transport.base import SubscriptionHandle

SymbolLike = Union[Symbol, str]


class ExchangeAdapter(ABC):
    """Canonical async surface that every exchange adapter implements."""

    #: Short adapter name, e.g. ``"deribit"``. Set on each subclass.
    name: ClassVar[str]
    #: Declarative feature descriptor. Set on each subclass.
    capabilities: ClassVar[Capabilities]

    def __init__(
        self,
        credentials: Optional[Credentials] = None,
        *,
        testnet: bool = False,
    ) -> None:
        self.credentials = credentials
        self.testnet = testnet

    # -- lifecycle ---------------------------------------------------------- #
    @abstractmethod
    async def connect(self) -> None:
        """Establish transport(s) and authenticate if credentials are present."""

    @abstractmethod
    async def close(self) -> None:
        """Tear down transport(s) and background tasks."""

    async def __aenter__(self) -> "ExchangeAdapter":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # -- market data -------------------------------------------------------- #
    @abstractmethod
    async def get_instruments(
        self, *, base: Optional[str] = None, kind: Optional[AssetKind] = None
    ) -> list[Instrument]: ...

    @abstractmethod
    async def get_order_book(self, symbol: SymbolLike, *, depth: int = 10) -> OrderBook: ...

    @abstractmethod
    async def get_ticker(self, symbol: SymbolLike) -> Ticker: ...

    async def get_trades(self, symbol: SymbolLike, *, limit: int = 100) -> list[Trade]:
        raise UnsupportedOperation(self.name, "get_trades")

    async def get_candles(
        self, symbol: SymbolLike, interval: Interval, *, limit: int = 500
    ) -> list[Candle]:
        raise UnsupportedOperation(self.name, "get_candles")

    async def get_funding_rate(self, symbol: SymbolLike) -> FundingRate:
        raise UnsupportedOperation(self.name, "get_funding_rate")

    # -- trading (private) -------------------------------------------------- #
    async def submit_order(self, order: OrderRequest) -> Order:
        raise UnsupportedOperation(self.name, "submit_order")

    async def cancel_order(
        self, order_id: str, *, symbol: Optional[SymbolLike] = None
    ) -> Order:
        raise UnsupportedOperation(self.name, "cancel_order")

    async def get_open_orders(self, symbol: Optional[SymbolLike] = None) -> list[Order]:
        raise UnsupportedOperation(self.name, "get_open_orders")

    async def get_order(self, order_id: str) -> Order:
        raise UnsupportedOperation(self.name, "get_order")

    # -- account (private) -------------------------------------------------- #
    async def get_account(self) -> AccountSummary:
        raise UnsupportedOperation(self.name, "get_account")

    async def get_positions(self, *, base: Optional[str] = None) -> list[Position]:
        raise UnsupportedOperation(self.name, "get_positions")

    # -- streaming ---------------------------------------------------------- #
    async def subscribe_order_book(
        self,
        symbol: SymbolLike,
        handler: Callable[[OrderBook], Awaitable[None]],
        *,
        interval: str = "100ms",
    ) -> SubscriptionHandle:
        raise UnsupportedOperation(self.name, "subscribe_order_book")

    async def subscribe_ticker(
        self, symbol: SymbolLike, handler: Callable[[Ticker], Awaitable[None]]
    ) -> SubscriptionHandle:
        raise UnsupportedOperation(self.name, "subscribe_ticker")

    async def subscribe_trades(
        self, symbol: SymbolLike, handler: Callable[[Trade], Awaitable[None]]
    ) -> SubscriptionHandle:
        raise UnsupportedOperation(self.name, "subscribe_trades")

    async def subscribe_orders(
        self, handler: Callable[[Order], Awaitable[None]]
    ) -> SubscriptionHandle:
        raise UnsupportedOperation(self.name, "subscribe_orders")

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        raise UnsupportedOperation(self.name, "unsubscribe")
