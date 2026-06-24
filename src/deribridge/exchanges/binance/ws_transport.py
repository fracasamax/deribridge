"""Binance WebSocket stream transport (websockets).

Implements the :class:`StreamTransport` protocol over Binance combined market
streams. This is a faithful-but-minimal reference: each ``subscribe`` opens a
combined-stream connection and dispatches messages to the handler. Production
hardening (multiplexing, reconnect/resubscribe) is intentionally out of scope
for the worked example — the Deribit transport demonstrates that machinery.
"""
from __future__ import annotations

import asyncio
import itertools
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
        # Each subscribe() call is one independent unit of work: a single
        # connection task keyed by a monotonic subscription id. The handle's
        # channels are *not* used as task keys, so two subscriptions that share
        # a channel name (or that overlap) never clobber or tear down each
        # other. unsubscribe(handle) cancels exactly the subscription it owns.
        self._tasks: dict[int, asyncio.Task] = {}
        self._handle_ids: dict[int, int] = {}
        self._ids = itertools.count(1)

    async def connect(self) -> None:  # connections are opened per-subscription
        return None

    async def subscribe(
        self, channels: list[str], handler: StreamHandler
    ) -> SubscriptionHandle:
        url = f"{self.base_url}/stream?streams={'/'.join(channels)}"
        sub_id = next(self._ids)
        task = asyncio.create_task(self._run(url, handler))
        self._tasks[sub_id] = task
        # Drop the entry once the task finishes on its own (stream closed /
        # transport error), so done tasks don't accumulate on a long-lived
        # transport. unsubscribe()/close() remain responsible for cancellation.
        def _drop(_task: object, _sid: int = sub_id) -> None:
            self._tasks.pop(_sid, None)

        task.add_done_callback(_drop)
        handle = SubscriptionHandle(channels=tuple(channels))
        self._handle_ids[id(handle)] = sub_id
        return handle

    async def _run(self, url: str, handler: StreamHandler) -> None:
        try:
            async with websockets.connect(url) as ws:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        # A single malformed/non-JSON frame must not kill the
                        # stream: log it (a wire-level oddity, not a fatal
                        # transport error) and keep consuming the next frames.
                        logger.warning(
                            "Binance WS received a non-JSON frame for %s; "
                            "dropping it and continuing the stream",
                            url,
                        )
                        continue
                    if isinstance(msg, dict) and "stream" in msg:
                        channel, data = msg["stream"], msg.get("data")
                    else:
                        channel, data = "", msg
                    message = StreamMessage(
                        channel=channel,
                        data=data,
                        raw=msg if isinstance(msg, dict) else {},
                    )
                    try:
                        await handler(message)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # A bug in the *user handler* must not kill the stream:
                        # log it (clearly attributed to the handler, not the
                        # network) and keep consuming subsequent messages.
                        logger.exception(
                            "Binance WS message handler raised for channel %r; "
                            "dropping this message and continuing the stream",
                            channel,
                        )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - network errors
            # Genuine transport/parse failure. This reference transport does not
            # reconnect: the subscription ends here (documented behavior).
            logger.error("Binance WS stream error for %s: %s", url, exc)

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        sub_id = self._handle_ids.pop(id(handle), None)
        if sub_id is None:
            return
        task = self._tasks.pop(sub_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        self._handle_ids.clear()
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
