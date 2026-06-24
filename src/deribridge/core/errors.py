"""Canonical, exchange-agnostic error taxonomy.

The order-safety trichotomy is part of the framework contract, not a Deribit
detail: order methods return a typed result on success, raise
:class:`OrderRejected` on a definite failure, and raise
:class:`IndeterminateOrderError` when the outcome is unknown (timeout /
mid-flight disconnect). Adapters MUST map their transport timeouts/disconnects
into :class:`IndeterminateOrderError` — a shared conformance test enforces it.
"""
from __future__ import annotations

from typing import Optional


class ExchangeError(Exception):
    """Base class for all deribridge framework errors."""


class UnknownExchangeError(ExchangeError):
    """Requested adapter name is not registered."""

    def __init__(self, name: str, known: list[str]) -> None:
        self.name = name
        self.known = known
        super().__init__(
            f"Unknown exchange adapter {name!r}. "
            f"Known adapters: {', '.join(sorted(known)) or '(none)'}."
        )


class MissingExchangeExtra(ExchangeError, ImportError):
    """An adapter's code is present but its third-party dependencies are not.

    Subclasses :class:`ImportError` so callers already guarding optional
    features with ``except ImportError`` keep working, while the message stays
    actionable.
    """

    def __init__(self, exchange: str, extra: str, missing: Optional[str] = None) -> None:
        self.exchange = exchange
        self.extra = extra
        self.missing = missing
        detail = f" (missing dependency: {missing!r})" if missing else ""
        super().__init__(
            f"The {exchange!r} adapter's dependencies are not installed{detail}.\n\n"
            f"    pip install 'deribridge[{extra}]'\n"
        )


class AuthenticationError(ExchangeError):
    """Authentication with the exchange failed or is required and missing."""


class RateLimitError(ExchangeError):
    """The exchange rejected a request due to rate limiting."""


class UnsupportedOperation(ExchangeError, NotImplementedError):
    """The selected adapter does not support the requested operation/feature."""

    def __init__(self, exchange: str, operation: str, detail: str = "") -> None:
        self.exchange = exchange
        self.operation = operation
        msg = f"{exchange!r} does not support {operation!r}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)


class OrderRejected(ExchangeError):
    """A definite order failure: the exchange rejected the request, or it was
    never sent (e.g. risk check). Safe to retry — the order is NOT live."""

    def __init__(
        self,
        operation: str,
        message: str,
        *,
        order_id: Optional[str] = None,
        code: Optional[int] = None,
    ) -> None:
        self.operation = operation
        self.order_id = order_id
        self.code = code
        super().__init__(message)


class IndeterminateOrderError(ExchangeError):
    """The outcome of an order request is unknown.

    A request timed out or the socket dropped mid-flight, so we cannot tell
    whether the exchange accepted, rejected, or never received the order. This
    is deliberately DISTINCT from a definite failure: the caller MUST reconcile
    the real state (e.g. via ``get_open_orders``) before retrying, or it risks
    duplicating a live order.

    The signature mirrors the original Deribit-internal exception so the
    Deribit adapter can adopt this class without changing call sites.
    """

    def __init__(
        self,
        operation: str,
        message: str,
        order_id: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        self.operation = operation
        self.order_id = order_id
        self.cause = cause
        super().__init__(message)
