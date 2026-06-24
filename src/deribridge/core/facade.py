"""User-facing entry points: ``connect`` and ``create``.

``ExchangeClient`` is the canonical client type callers program against — it is
the :class:`ExchangeAdapter` interface. ``connect`` resolves an adapter by
name, instantiates it, and (by default) opens its transport; ``create`` builds
without connecting, for ``async with`` use.
"""
from __future__ import annotations

from typing import Any, Optional

from .adapter import ExchangeAdapter
from .registry import available_adapters, resolve
from .transport.auth import Credentials

#: The canonical client type. An adapter *is* the client.
ExchangeClient = ExchangeAdapter

__all__ = ["connect", "create", "available_adapters", "ExchangeClient"]


def create(
    exchange: str,
    *,
    credentials: Optional[Credentials] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    passphrase: Optional[str] = None,
    testnet: bool = False,
    **adapter_kwargs: Any,
) -> ExchangeClient:
    """Build (but do not connect) the adapter for ``exchange``.

    Use with ``async with``::

        async with deribridge.create("deribit", testnet=True) as client:
            ticker = await client.get_ticker("BTC-PERPETUAL")
    """
    if credentials is None and (api_key or api_secret or passphrase):
        credentials = Credentials(key=api_key, secret=api_secret, passphrase=passphrase)
    adapter_cls = resolve(exchange)
    return adapter_cls(credentials, testnet=testnet, **adapter_kwargs)


async def connect(
    exchange: str,
    *,
    credentials: Optional[Credentials] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    passphrase: Optional[str] = None,
    testnet: bool = False,
    autostart: bool = True,
    **adapter_kwargs: Any,
) -> ExchangeClient:
    """Resolve, build, and (by default) connect the adapter for ``exchange``.

    Raises:
        UnknownExchangeError: unknown adapter name.
        MissingExchangeExtra: adapter present but its extra is not installed
            (e.g. ``pip install deribridge[binance]``).
    """
    client = create(
        exchange,
        credentials=credentials,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        testnet=testnet,
        **adapter_kwargs,
    )
    if autostart:
        await client.connect()
    return client
