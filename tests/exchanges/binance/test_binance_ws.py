"""Tests for BinanceWsTransport bookkeeping and handler-error isolation.

No real network: ``websockets.connect`` is patched with an async context
manager yielding a fake socket whose message stream the test controls. This
exercises the two review fixes deterministically:

* #3 a buggy *user handler* must not kill the stream and must be logged as a
  handler failure (not a network error);
* #4 two ``subscribe`` calls are fully independent — unsubscribing one (even
  when channels overlap) must not tear down the other.
"""
from __future__ import annotations

import asyncio
import json
import logging

import pytest

from deribridge.core.transport.base import StreamMessage, SubscriptionHandle
from deribridge.exchanges.binance import ws_transport as ws_mod
from deribridge.exchanges.binance.ws_transport import BinanceWsTransport


class _FakeSocket:
    """Async-iterable fake websocket.

    Yields each queued raw frame, then blocks forever (mimicking a live socket
    waiting for more server pushes) until the consuming task is cancelled.
    """

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self.closed = False

    def __aiter__(self) -> "_FakeSocket":
        return self

    async def __anext__(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        # No more frames: emulate an open, idle connection.
        await asyncio.Event().wait()
        raise AssertionError("unreachable")  # pragma: no cover


class _FakeConnect:
    """Stand-in for ``websockets.connect`` usable as an async context manager."""

    def __init__(self, socket: _FakeSocket) -> None:
        self._socket = socket

    async def __aenter__(self) -> _FakeSocket:
        return self._socket

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._socket.closed = True
        return False


def _patch_connect(monkeypatch, socket: _FakeSocket) -> None:
    monkeypatch.setattr(ws_mod.websockets, "connect", lambda url: _FakeConnect(socket))


async def _wait_until(predicate, timeout: float = 1.0) -> None:
    """Poll ``predicate`` cooperatively until true or the timeout elapses."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not reached within timeout")
        await asyncio.sleep(0)


# --------------------------------------------------------------------------- #
# #3 handler-error isolation
# --------------------------------------------------------------------------- #


async def test_handler_exception_does_not_kill_stream_and_is_logged(
    monkeypatch, caplog
):
    frames = [
        json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "1"}}),
        json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "2"}}),
    ]
    socket = _FakeSocket(frames)
    _patch_connect(monkeypatch, socket)

    seen: list[StreamMessage] = []

    async def handler(msg: StreamMessage) -> None:
        seen.append(msg)
        if len(seen) == 1:
            raise ValueError("boom in user handler")

    transport = BinanceWsTransport()
    with caplog.at_level(logging.ERROR, logger="deribridge.binance.ws"):
        handle = await transport.subscribe(["btcusdt@bookTicker"], handler)
        # Both frames must reach the handler: the first raises, the second
        # still arrives because the stream was not torn down.
        await _wait_until(lambda: len(seen) == 2)

    assert [m.data["b"] for m in seen] == ["1", "2"]

    # The failure is attributed to the message handler, not the network.
    handler_errors = [r for r in caplog.records if "handler" in r.getMessage()]
    assert handler_errors, "expected a handler-attributed log record"
    rec = handler_errors[0]
    assert rec.exc_info is not None  # logger.exception captured the traceback
    assert "stream error" not in rec.getMessage().lower()

    await transport.unsubscribe(handle)


async def test_malformed_frame_does_not_kill_stream(monkeypatch, caplog):
    # A single non-JSON frame between two valid ones must be dropped (logged as
    # a wire oddity, not a fatal transport error) without ending the stream.
    frames = [
        json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "1"}}),
        "this is not json{",
        json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "2"}}),
    ]
    socket = _FakeSocket(frames)
    _patch_connect(monkeypatch, socket)

    seen: list[StreamMessage] = []

    async def handler(msg: StreamMessage) -> None:
        seen.append(msg)

    transport = BinanceWsTransport()
    with caplog.at_level(logging.WARNING, logger="deribridge.binance.ws"):
        handle = await transport.subscribe(["btcusdt@bookTicker"], handler)
        await _wait_until(lambda: len(seen) == 2)

    # Both valid frames arrived; the malformed one was skipped, not fatal.
    assert [m.data["b"] for m in seen] == ["1", "2"]
    non_json = [r for r in caplog.records if "non-JSON frame" in r.getMessage()]
    assert non_json, "expected a dropped-frame warning"
    assert all("stream error" not in r.getMessage().lower() for r in non_json)

    await transport.unsubscribe(handle)


async def test_handler_cancelled_error_propagates(monkeypatch):
    """A CancelledError raised inside the handler must not be swallowed."""
    started = asyncio.Event()

    async def handler(msg: StreamMessage) -> None:
        started.set()
        raise asyncio.CancelledError

    frames = [json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "1"}})]
    socket = _FakeSocket(frames)
    _patch_connect(monkeypatch, socket)

    transport = BinanceWsTransport()
    handle = await transport.subscribe(["btcusdt@bookTicker"], handler)
    task = transport._tasks[transport._handle_ids[id(handle)]]
    await started.wait()
    # The run task ends (it does not loop forever) because CancelledError was
    # re-raised out of the message loop rather than being caught and ignored.
    with pytest.raises(asyncio.CancelledError):
        await task


# --------------------------------------------------------------------------- #
# #4 subscription independence
# --------------------------------------------------------------------------- #


async def test_two_subscriptions_are_independent(monkeypatch):
    monkeypatch.setattr(
        ws_mod.websockets,
        "connect",
        lambda url: _FakeConnect(_FakeSocket([])),
    )

    async def handler(msg: StreamMessage) -> None:  # pragma: no cover - never fed
        pass

    transport = BinanceWsTransport()
    h1 = await transport.subscribe(["btcusdt@bookTicker"], handler)
    h2 = await transport.subscribe(["ethusdt@bookTicker"], handler)

    assert len(transport._tasks) == 2
    id1 = transport._handle_ids[id(h1)]
    id2 = transport._handle_ids[id(h2)]
    assert id1 != id2
    task1 = transport._tasks[id1]
    task2 = transport._tasks[id2]

    await transport.unsubscribe(h1)
    await _wait_until(lambda: task1.done())

    # h1's task is gone; h2's task is untouched.
    assert task1.cancelled()
    assert id1 not in transport._tasks
    assert id(h1) not in transport._handle_ids
    assert not task2.done()
    assert id2 in transport._tasks

    await transport.close()


async def test_overlapping_channels_do_not_clobber(monkeypatch):
    """Two subscriptions sharing a channel name stay fully independent."""
    monkeypatch.setattr(
        ws_mod.websockets,
        "connect",
        lambda url: _FakeConnect(_FakeSocket([])),
    )

    async def handler(msg: StreamMessage) -> None:  # pragma: no cover - never fed
        pass

    transport = BinanceWsTransport()
    # Both subscriptions include "btcusdt@trade".
    h1 = await transport.subscribe(["btcusdt@trade", "btcusdt@depth"], handler)
    h2 = await transport.subscribe(["btcusdt@trade", "ethusdt@depth"], handler)

    assert len(transport._tasks) == 2
    task2 = transport._tasks[transport._handle_ids[id(h2)]]

    # Unsubscribing the first must not affect the second despite the shared
    # "btcusdt@trade" channel.
    await transport.unsubscribe(h1)
    await _wait_until(lambda: len(transport._tasks) == 1)

    assert id(h1) not in transport._handle_ids
    assert id(h2) in transport._handle_ids
    assert not task2.done()

    await transport.close()


async def test_unsubscribe_unknown_handle_is_noop(monkeypatch):
    monkeypatch.setattr(
        ws_mod.websockets,
        "connect",
        lambda url: _FakeConnect(_FakeSocket([])),
    )

    transport = BinanceWsTransport()
    # A handle that was never produced by this transport must be ignored.
    await transport.unsubscribe(SubscriptionHandle(channels=("ghost@trade",)))
    assert transport._tasks == {}


async def test_close_cancels_all_subscriptions(monkeypatch):
    monkeypatch.setattr(
        ws_mod.websockets,
        "connect",
        lambda url: _FakeConnect(_FakeSocket([])),
    )

    async def handler(msg: StreamMessage) -> None:  # pragma: no cover - never fed
        pass

    transport = BinanceWsTransport()
    await transport.subscribe(["a@trade"], handler)
    await transport.subscribe(["b@trade"], handler)
    tasks = list(transport._tasks.values())

    await transport.close()

    assert transport._tasks == {}
    assert transport._handle_ids == {}
    assert all(t.done() for t in tasks)
