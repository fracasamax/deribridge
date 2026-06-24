"""Transport abstraction.

Two orthogonal protocols an adapter composes. A request/response venue
implements :class:`RequestTransport`; a streaming venue implements
:class:`StreamTransport`. Deribit implements *both* over a single WebSocket
(JSON-RPC); Binance/OKX implement :class:`RequestTransport` over HTTPS and
:class:`StreamTransport` over a separate WebSocket. The canonical layer never
sees which is which.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol, runtime_checkable


@dataclass
class Request:
    """A single request. ``method`` is an HTTP verb for REST, or a JSON-RPC
    method name for RPC venues; ``path`` is the REST path (empty for RPC)."""

    method: str
    path: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    private: bool = False  # requires authentication
    weight: int = 1  # cost units, for weighted rate limiting (e.g. Binance)


@dataclass
class Response:
    """A parsed response: ``data`` is the meaningful payload (REST body or the
    JSON-RPC ``result``); ``raw`` is the untouched envelope."""

    data: Any
    raw: dict[str, Any] = field(default_factory=dict)
    status: Optional[int] = None


@dataclass
class StreamMessage:
    """A single message pushed on a subscribed channel."""

    channel: str
    data: Any
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriptionHandle:
    """Opaque handle returned by ``subscribe`` and passed to ``unsubscribe``."""

    channels: tuple[str, ...]


StreamHandler = Callable[[StreamMessage], Awaitable[None]]


@runtime_checkable
class RequestTransport(Protocol):
    """Request/response transport."""

    async def request(self, req: Request) -> Response: ...
    async def connect(self) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class StreamTransport(Protocol):
    """Streaming / subscription transport. Concrete implementations own
    reconnect, heartbeat, and resubscribe-on-reconnect."""

    async def connect(self) -> None: ...
    async def subscribe(
        self, channels: list[str], handler: StreamHandler
    ) -> SubscriptionHandle: ...
    async def unsubscribe(self, handle: SubscriptionHandle) -> None: ...
    async def close(self) -> None: ...
