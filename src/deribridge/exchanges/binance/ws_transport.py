"""Binance WebSocket stream transport (websockets).

Implements the :class:`StreamTransport` protocol over Binance combined market
streams. This is a faithful-but-minimal reference: each ``subscribe`` opens a
combined-stream connection and dispatches messages to the handler. Production
hardening (multiplexing, reconnect/resubscribe) is intentionally out of scope
for the worked example — the Deribit transport demonstrates that machinery.
"""
from __future__ import annotations

import asyncio
import json
import logging

import websockets

from ...core.transport.base import StreamHandler, StreamMessage, SubscriptionHandle

_PROD_BASE = "wss://stream.binance.com:9443"
_TEST_BASE = "wss://testnet.binance.vision"

logger = logging.getLogger("deribridge.binance.ws")


class BinanceWsTransport:
    def __init__(self, *, testnet: bool = False) -> None:
        self.base_url = _TEST_BASE if testnet else _PROD_BASE
        self._tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:  # connections are opened per-subscription
        return None

    async def subscribe(
        self, channels: list[str], handler: StreamHandler
    ) -> SubscriptionHandle:
        url = f"{self.base_url}/stream?streams={'/'.join(channels)}"
        task = asyncio.create_task(self._run(url, handler))
        for ch in channels:
            self._tasks[ch] = task
        return SubscriptionHandle(channels=tuple(channels))

    async def _run(self, url: str, handler: StreamHandler) -> None:
        try:
            async with websockets.connect(url) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    if isinstance(msg, dict) and "stream" in msg:
                        channel, data = msg["stream"], msg.get("data")
                    else:
                        channel, data = "", msg
                    await handler(StreamMessage(channel=channel, data=data, raw=msg if isinstance(msg, dict) else {}))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Binance WS stream error for %s: %s", url, exc)

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        for ch in handle.channels:
            task = self._tasks.pop(ch, None)
            if task is not None and not task.done():
                task.cancel()

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with _suppress_cancelled():
                await task


class _suppress_cancelled:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, asyncio.CancelledError)
