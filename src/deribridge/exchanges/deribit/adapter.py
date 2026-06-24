"""The Deribit adapter.

Implements the canonical :class:`ExchangeAdapter` by *delegating* to the
existing, production-hardened :class:`DeribitAPIInterface` (the 1700-line
WebSocket client is wrapped, never rewritten). Market data is mapped from raw
JSON-RPC results; orders go through the interface so the success / definite-
failure / indeterminate trichotomy is preserved exactly.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Awaitable, Callable, ClassVar, Optional

from ...classes.order import Order as DeribitOrder
from ...classes.order import OrderType as DeribitOrderType
from ...classes.order import TimeInForce as DeribitTIF
from ...classes.order_purpose import OrderPurpose
from ...core.adapter import ExchangeAdapter, SymbolLike
from ...core.capabilities import Capabilities
from ...core.enums import AssetKind, Side, TimeInForce
from ...core.errors import OrderRejected, UnsupportedOperation
from ...core.models import (
    AccountSummary,
    Instrument,
    Order,
    OrderBook,
    OrderRequest,
    Position,
    Symbol,
    Ticker,
)
from ...core.transport.base import SubscriptionHandle
from .capabilities import DERIBIT_CAPABILITIES
from .deribit_api_interface import DeribitAPIInterface
from .mapper import DeribitMapper

#: Currencies queried when a caller does not scope by ``base``.
DEFAULT_CURRENCIES = ("BTC", "ETH", "USDC")

_KIND_TO_DERIBIT = {
    AssetKind.OPTION: "option",
    AssetKind.FUTURE: "future",
    AssetKind.PERPETUAL: "future",  # Deribit lists perpetuals under "future"
    AssetKind.SPOT: "spot",
}

_TIF_TO_DERIBIT = {
    TimeInForce.GOOD_TIL_CANCELLED: DeribitTIF.GOOD_TIL_CANCELLED,
    TimeInForce.FILL_OR_KILL: DeribitTIF.FILL_OR_KILL,
    TimeInForce.IMMEDIATE_OR_CANCEL: DeribitTIF.IMMEDIATE_OR_CANCEL,
}


class DeribitAdapter(ExchangeAdapter):
    name: ClassVar[str] = "deribit"
    capabilities: ClassVar[Capabilities] = DERIBIT_CAPABILITIES

    def __init__(self, credentials=None, *, testnet: bool = False, interface=None) -> None:
        super().__init__(credentials, testnet=testnet)
        self._mapper = DeribitMapper()
        if interface is not None:
            # Injection seam for offline tests.
            self._iface = interface
        else:
            self._iface = DeribitAPIInterface.configure(
                client_id=credentials.key if credentials else None,
                client_secret=credentials.secret if credentials else None,
                use_test_env=testnet,
                load_dotenv_file=credentials is None,
            )

    @property
    def _client(self):
        return self._iface.client

    @staticmethod
    def _raw(symbol: SymbolLike) -> str:
        return symbol.raw if isinstance(symbol, Symbol) else str(symbol)

    def _symbol(self, symbol: SymbolLike) -> Symbol:
        return symbol if isinstance(symbol, Symbol) else self._mapper.parse_symbol(str(symbol))

    # -- lifecycle ---------------------------------------------------------- #
    async def connect(self) -> None:
        await self._iface.start_client()

    async def close(self) -> None:
        await self._iface.stop_client()

    # -- market data -------------------------------------------------------- #
    async def get_instruments(
        self, *, base: Optional[str] = None, kind: Optional[AssetKind] = None
    ) -> list[Instrument]:
        currencies = [base] if base else list(DEFAULT_CURRENCIES)
        deribit_kind = _KIND_TO_DERIBIT.get(kind) if kind else None
        out: list[Instrument] = []
        for currency in currencies:
            raw_list = await self._client.get_instruments(currency, kind=deribit_kind)
            for raw in raw_list:
                inst = self._mapper.instrument(raw)
                if kind is not None and inst.symbol.kind != kind:
                    continue  # disambiguate perpetual vs future (both "future" on Deribit)
                out.append(inst)
        return out

    async def get_order_book(self, symbol: SymbolLike, *, depth: int = 10) -> OrderBook:
        raw = await self._client.get_order_book(self._raw(symbol), depth)
        return self._mapper.order_book(raw, self._symbol(symbol))

    async def get_ticker(self, symbol: SymbolLike) -> Ticker:
        raw = await self._client.get_ticker(self._raw(symbol))
        return self._mapper.ticker(raw, self._symbol(symbol))

    # -- account / positions ----------------------------------------------- #
    async def get_account(self) -> AccountSummary:
        raw = await self._client.get_account_summaries(extended=True)
        return self._mapper.account(raw)

    async def get_positions(self, *, base: Optional[str] = None) -> list[Position]:
        raw_list = await self._client.get_positions(base)
        return [self._mapper.position(p) for p in raw_list]

    async def get_open_orders(self, symbol: Optional[SymbolLike] = None) -> list[Order]:
        currency = self._symbol(symbol).base if symbol is not None else None
        wire_orders = await self._iface.get_open_orders(currency)
        return [self._mapper.order(asdict(o)) for o in wire_orders]

    # -- trading (trichotomy preserved by the interface) -------------------- #
    async def submit_order(self, order: OrderRequest) -> Order:
        deribit_order = self._to_deribit_order(order)
        # IndeterminateOrderError (timeout/disconnect) propagates unchanged.
        resp = await self._iface.submit_order(deribit_order, check_risk=False)
        if resp is None:
            raise OrderRejected("submit_order", "order rejected or not sent")
        return self._mapper.order(asdict(resp.order))

    async def cancel_order(
        self, order_id: str, *, symbol: Optional[SymbolLike] = None
    ) -> Order:
        resp = await self._iface.cancel_order(order_id)
        if resp is None or not getattr(resp, "is_successful", False):
            raise OrderRejected("cancel_order", "cancel rejected", order_id=order_id)
        if getattr(resp, "order", None) is not None:
            return self._mapper.order(asdict(resp.order))
        raise OrderRejected(
            "cancel_order", "cancel acknowledged without order payload", order_id=order_id
        )

    def _to_deribit_order(self, req: OrderRequest) -> DeribitOrder:
        tif = _TIF_TO_DERIBIT.get(req.time_in_force)
        if tif is None:
            raise UnsupportedOperation(
                self.name, "time_in_force", f"{req.time_in_force.value} not supported"
            )
        return DeribitOrder(
            instrument_name=self._raw(req.symbol),
            purpose=OrderPurpose.BUY if req.side is Side.BUY else OrderPurpose.SELL,
            amount=float(req.amount) if req.amount is not None else None,
            order_type=DeribitOrderType(req.type.value),
            price=float(req.price) if req.price is not None else None,
            time_in_force=tif,
            post_only=req.post_only,
            reduce_only=req.reduce_only,
            trigger_price=float(req.trigger_price) if req.trigger_price is not None else None,
            label=req.label,
        )

    # -- streaming ---------------------------------------------------------- #
    async def subscribe_order_book(
        self,
        symbol: SymbolLike,
        handler: Callable[[OrderBook], Awaitable[None]],
        *,
        interval: str = "100ms",
    ) -> SubscriptionHandle:
        sym = self._symbol(symbol)
        raw_name = self._raw(symbol)

        async def _wrap(message: dict) -> None:
            data = message.get("data") if isinstance(message, dict) else None
            if data:
                await handler(self._mapper.order_book(data, sym))

        await self._client.subscribe_orderbook(raw_name, interval, _wrap)
        return SubscriptionHandle(channels=(f"book.{raw_name}.{interval}",))

    async def subscribe_ticker(
        self, symbol: SymbolLike, handler: Callable[[Ticker], Awaitable[None]]
    ) -> SubscriptionHandle:
        sym = self._symbol(symbol)
        raw_name = self._raw(symbol)

        async def _wrap(message: dict) -> None:
            data = message.get("data") if isinstance(message, dict) else None
            if data:
                await handler(self._mapper.ticker(data, sym))

        await self._client.subscribe_ticker(raw_name, _wrap)
        return SubscriptionHandle(channels=(f"ticker.{raw_name}.100ms",))

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        await self._client.unsubscribe(list(handle.channels))
