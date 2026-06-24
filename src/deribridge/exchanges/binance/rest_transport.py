"""Binance REST transport (httpx).

Implements the :class:`RequestTransport` protocol over HTTPS. ``httpx`` is
imported at module top so that, on a core-only install, importing this module
fails with ``ModuleNotFoundError: httpx`` — which the registry translates into
a friendly ``MissingExchangeExtra``.
"""
from __future__ import annotations

from typing import Optional

import httpx

from ...core.transport.base import Request, Response

_PROD_BASE = "https://api.binance.com"
_TEST_BASE = "https://testnet.binance.vision"


class BinanceRestTransport:
    """Request/response transport over the Binance REST API."""

    def __init__(self, *, testnet: bool = False, timeout: float = 10.0) -> None:
        self.base_url = _TEST_BASE if testnet else _PROD_BASE
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(self, req: Request) -> Response:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        resp = await self._client.request(req.method, req.path, params=req.params or None)
        resp.raise_for_status()
        data = resp.json()
        raw = data if isinstance(data, dict) else {"data": data}
        return Response(data=data, raw=raw, status=resp.status_code)
