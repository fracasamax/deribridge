"""Tests for BinanceHmacAuth.sign_request (review finding #6).

Locks down the signing contract: the signature is HMAC-SHA256 over the exact
query string that excludes the appended ``signature`` param, so a client that
serializes ``params`` in insertion order reproduces what was signed. Also
asserts the unauthenticated path is a no-op.
"""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from deribridge.core.transport.auth import Credentials
from deribridge.core.transport.base import Request
from deribridge.exchanges.binance.auth import BinanceHmacAuth


def test_sign_request_known_vector():
    secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0"
    auth = BinanceHmacAuth(Credentials(key="apikey", secret=secret))

    req = Request(
        method="POST",
        path="/api/v3/order",
        params={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "1",
            "price": "9000",
        },
        private=True,
    )
    now_ms = 1499827319559

    signed = auth.sign_request(req, now_ms)

    # timestamp and signature are present...
    assert signed.params["timestamp"] == now_ms
    assert "signature" in signed.params

    # ...and the signature equals an independently computed HMAC over the exact
    # query string that excludes the signature param (insertion order preserved).
    payload = dict(signed.params)
    sent_signature = payload.pop("signature")
    signed_query = urlencode(payload)
    expected = hmac.new(
        secret.encode(), signed_query.encode(), hashlib.sha256
    ).hexdigest()
    assert sent_signature == expected

    # The signed string is the timestamped params; signature is appended last so
    # the on-the-wire serialization is signed_query + "&signature=...".
    assert "signature" not in signed_query
    assert signed_query.endswith("timestamp=1499827319559")
    assert urlencode(signed.params) == f"{signed_query}&signature={expected}"

    # Original request is not mutated in place.
    assert "signature" not in req.params
    assert "timestamp" not in req.params


def test_sign_request_noop_without_credentials():
    # No credentials object at all.
    auth = BinanceHmacAuth(None)
    assert auth.is_authenticated is False
    req = Request(method="GET", path="/api/v3/account", params={"recvWindow": 5000})
    out = auth.sign_request(req, now_ms=123)
    assert out is req
    assert "signature" not in out.params
    assert "timestamp" not in out.params


def test_sign_request_noop_with_empty_credentials():
    # Credentials present but blank => not authenticated.
    auth = BinanceHmacAuth(Credentials(key=None, secret=None))
    assert auth.is_authenticated is False
    req = Request(method="GET", path="/api/v3/account", params={})
    out = auth.sign_request(req, now_ms=123)
    assert out is req
    assert out.params == {}


def test_sign_request_is_deterministic_and_order_stable():
    secret = "topsecret"
    auth = BinanceHmacAuth(Credentials(key="k", secret=secret))
    req = Request(method="GET", path="/x", params={"a": "1", "b": "2", "c": "3"})

    first = auth.sign_request(req, now_ms=1000)
    second = auth.sign_request(req, now_ms=1000)

    # Same inputs => identical signature (no dependence on dict iteration order
    # diverging between sign time and send time).
    assert first.params["signature"] == second.params["signature"]
    # Param insertion order is preserved through signing.
    assert list(first.params.keys()) == ["a", "b", "c", "timestamp", "signature"]
