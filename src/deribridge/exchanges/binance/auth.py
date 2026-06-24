"""Binance HMAC-SHA256 request signing.

Implemented for completeness (and to exercise the :class:`Authenticator`
protocol with a stateless, per-request signer, in contrast to Deribit's
session-token auth). Private trading endpoints are not wired up in this
reference adapter, so this signer is currently unused by the public surface.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional
from urllib.parse import urlencode

from ...core.transport.auth import Credentials
from ...core.transport.base import Request, RequestTransport


class BinanceHmacAuth:
    """Per-request HMAC signer (Binance ``X-MBX-APIKEY`` + ``signature``)."""

    def __init__(self, credentials: Optional[Credentials]) -> None:
        self.credentials = credentials

    @property
    def is_authenticated(self) -> bool:
        return self.credentials is not None and self.credentials.is_present

    def sign_request(self, req: Request, now_ms: int) -> Request:
        if not self.is_authenticated:
            return req
        assert self.credentials is not None and self.credentials.secret is not None
        # Build the exact query string once and sign *that* string, then append
        # the signature as a final param. The signed bytes are fully determined
        # here (urlencode emits params in insertion order), so the signature can
        # never silently diverge from however the caller/httpx later serializes
        # the dict: a correct client must send ``signed_query + "&signature=..."``.
        params = dict(req.params)
        params["timestamp"] = now_ms
        signed_query = urlencode(params)
        signature = hmac.new(
            self.credentials.secret.encode(), signed_query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return Request(
            method=req.method,
            path=req.path,
            params=params,
            private=req.private,
            weight=req.weight,
        )

    async def authenticate(self, transport: RequestTransport) -> None:
        # Stateless: nothing to establish ahead of time.
        return None
