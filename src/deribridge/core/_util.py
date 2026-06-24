"""Internal coercion helpers shared by the canonical models and adapters.

These are the conversions every mapper needs when turning a venue's wire JSON
into canonical models: lossless ``Decimal`` coercion and epoch-millisecond ->
timezone-aware ``datetime``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def to_decimal(value: Any) -> Decimal:
    """Coerce ``value`` to ``Decimal`` losslessly.

    Uses ``Decimal(str(value))`` so float inputs do not pick up binary-float
    artifacts (``Decimal(0.1)`` -> ``0.1000000000000000055...``). String inputs
    — how spot venues like Binance return prices — convert exactly.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise ValueError("cannot convert None to Decimal")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"cannot convert {value!r} to Decimal") from exc


def opt_decimal(value: Any) -> Optional[Decimal]:
    """Like :func:`to_decimal` but passes ``None`` through unchanged."""
    if value is None:
        return None
    return to_decimal(value)


def ms_to_dt(ms: Optional[int]) -> Optional[datetime]:
    """Convert epoch milliseconds to a timezone-aware UTC ``datetime``."""
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def now_utc() -> datetime:
    """Current time as a timezone-aware UTC ``datetime``."""
    return datetime.now(timezone.utc)
