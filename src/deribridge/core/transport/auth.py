"""Authentication abstraction.

Credentials are carried in a small, venue-neutral :class:`Credentials` object.
Each adapter supplies an :class:`Authenticator` strategy: stateless per-request
signing (Binance/OKX HMAC) via :meth:`sign_request`, or session-based auth
(Deribit's ``public/auth`` token flow) via :meth:`authenticate`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from .base import Request, RequestTransport


@dataclass(frozen=True)
class Credentials:
    """Venue-neutral API credentials.

    ``key``/``secret`` are the common pair; ``passphrase`` is used by venues
    like OKX. Any venue-specific extras can be carried by the adapter.
    """

    key: Optional[str] = None
    secret: Optional[str] = None
    passphrase: Optional[str] = None

    @property
    def is_present(self) -> bool:
        return bool(self.key and self.secret)


@runtime_checkable
class Authenticator(Protocol):
    """Per-adapter authentication strategy."""

    @property
    def is_authenticated(self) -> bool: ...

    def sign_request(self, req: Request, now_ms: int) -> Request:
        """Return ``req`` with venue auth applied (REST: headers/query/body)."""
        ...

    async def authenticate(self, transport: RequestTransport) -> None:
        """Establish a session (WS token auth). No-op for stateless venues."""
        ...
