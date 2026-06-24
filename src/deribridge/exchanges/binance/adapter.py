"""The Binance adapter (reference example).

Proves the canonical abstraction across a REST + WebSocket venue with a
completely different wire format from Deribit: string prices, concatenated
symbols, snapshot order books, and combined WS streams — all mapped to the same
canonical models. Public market data is implemented; private trading/account
endpoints are out of scope (see :data:`BINANCE_CAPABILITIES`).
"""
from __future__ import annotations

from typing import Awaitable, Callable, ClassVar, Optional

from ...core.adapter import ExchangeAdapter, SymbolLike
from ...core.capabilities import Capabilities
from ...core.enums import AssetKind, Interval
from ...core.models import Candle, Instrument, OrderBook, Symbol, Ticker
from ...core.transport.base import Request, StreamMessage, SubscriptionHandle
from .auth import BinanceHmacAuth
from .capabilities import BINANCE_CAPABILITIES
from .mapper import BinanceMapper
from .rest_transport import BinanceRestTransport
from .ws_transport import BinanceWsTransport


class BinanceAdapter(ExchangeAdapter):
    name: ClassVar[str] = "binance"
    capabilities: ClassVar[Capabilities] = BINANCE_CAPABILITIES

    def __init__(self, credentials=None, *, testnet: bool = False, rest=None, ws=None) -> None:
        super().__init__(credentials, testnet=testnet)
        self._mapper = BinanceMapper()
        self._auth = BinanceHmacAuth(credentials)
        self._rest = rest if rest is not None else BinanceRestTransport(testnet=testnet)
        self._ws = ws if ws is not None else BinanceWsTransport(testnet=testnet)

    @staticmethod
    def _raw(symbol: SymbolLike) -> str:
        return symbol.raw if isinstance(symbol, Symbol) else str(symbol)

    def _symbol(self, symbol: SymbolLike) -> Symbol:
        return symbol if isinstance(symbol, Symbol) else self._mapper.parse_symbol(str(symbol))

    # -- lifecycle ---------------------------------------------------------- #
    async def connect(self) -> None:
        await self._rest.connect()

    async def close(self) -> None:
        await self._rest.close()
        await self._ws.close()

    # -- market data -------------------------------------------------------- #
    async def get_instruments(
        self, *, base: Optional[str] = None, kind: Optional[AssetKind] = None
    ) -> list[Instrument]:
        if kind is not None and kind != AssetKind.SPOT:
            return []  # this reference adapter covers spot only
        resp = await self._rest.request(Request("GET", "/api/v3/exchangeInfo"))
        symbols = resp.data.get("symbols", [])
        out = [self._mapper.instrument(s) for s in symbols]
        if base:
            out = [i for i in out if i.symbol.base.upper() == base.upper()]
        return out

    async def get_order_book(self, symbol: SymbolLike, *, depth: int = 10) -> OrderBook:
        resp = await self._rest.request(
            Request("GET", "/api/v3/depth", {"symbol": self._raw(symbol), "limit": depth})
        )
        return self._mapper.order_book(resp.data, self._symbol(symbol))

    async def get_ticker(self, symbol: SymbolLike) -> Ticker:
        raw_name = self._raw(symbol)
        book = await self._rest.request(
            Request("GET", "/api/v3/ticker/bookTicker", {"symbol": raw_name})
        )
        stats = await self._rest.request(
            Request("GET", "/api/v3/ticker/24hr", {"symbol": raw_name})
        )
        merged = {**stats.data, **book.data}  # bookTicker bid/ask wins
        return self._mapper.ticker(merged, self._symbol(symbol))

    async def get_candles(
        self, symbol: SymbolLike, interval: Interval, *, limit: int = 500
    ) -> list[Candle]:
        resp = await self._rest.request(
            Request(
                "GET",
                "/api/v3/klines",
                {"symbol": self._raw(symbol), "interval": interval.value, "limit": limit},
            )
        )
        sym = self._symbol(symbol)
        return [self._mapper.candle(row, sym, interval) for row in resp.data]

    # -- streaming ---------------------------------------------------------- #
    async def subscribe_ticker(
        self, symbol: SymbolLike, handler: Callable[[Ticker], Awaitable[None]]
    ) -> SubscriptionHandle:
        sym = self._symbol(symbol)
        stream = f"{self._raw(symbol).lower()}@bookTicker"

        async def _wrap(msg: StreamMessage) -> None:
            if msg.data:
                await handler(self._mapper.ticker(msg.data, sym))

        return await self._ws.subscribe([stream], _wrap)

    async def subscribe_order_book(
        self,
        symbol: SymbolLike,
        handler: Callable[[OrderBook], Awaitable[None]],
        *,
        interval: str = "100ms",
    ) -> SubscriptionHandle:
        sym = self._symbol(symbol)
        stream = f"{self._raw(symbol).lower()}@depth20@{interval}"

        async def _wrap(msg: StreamMessage) -> None:
            if msg.data:
                await handler(self._mapper.order_book(msg.data, sym))

        return await self._ws.subscribe([stream], _wrap)

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        await self._ws.unsubscribe(handle)
