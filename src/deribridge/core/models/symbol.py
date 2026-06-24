"""The canonical :class:`Symbol` value object.

A ``Symbol`` carries both the authoritative venue string (``raw`` — what API
calls actually use) and a structured, cross-venue decomposition. This lets the
same object serve two jobs that a bare string cannot: talk to the exchange,
and join the *same* economic instrument across exchanges via ``canonical``.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..enums import AssetKind, OptionType


class Symbol(BaseModel):
    """Structured instrument identifier.

    ``raw`` is what gets sent to the venue (authoritative). ``canonical`` is a
    stable cross-venue key for analytics that aggregate across exchanges.
    """

    model_config = ConfigDict(frozen=True)

    raw: str
    base: str
    quote: str
    kind: AssetKind
    exchange: str
    settle: Optional[str] = None
    expiry: Optional[datetime] = None
    strike: Optional[Decimal] = None
    option_type: Optional[OptionType] = None

    @property
    def canonical(self) -> str:
        """Exchange-agnostic key for the same economic instrument.

        Examples:
            ``BTC/USDT:spot``
            ``BTC/USD:perpetual``
            ``BTC/USD:future:2025-12-26``
            ``BTC/USD:option:2025-12-26:60000:call``
        """
        pair = f"{self.base}/{self.quote}"
        if self.kind in (AssetKind.SPOT, AssetKind.INDEX):
            return f"{pair}:{self.kind.value}"
        if self.kind == AssetKind.PERPETUAL:
            return f"{pair}:perpetual"
        date = self.expiry.date().isoformat() if self.expiry else "?"
        if self.kind == AssetKind.FUTURE:
            return f"{pair}:future:{date}"
        # OPTION
        strike = format(self.strike, "f") if self.strike is not None else "?"
        opt = self.option_type.value if self.option_type else "?"
        return f"{pair}:option:{date}:{strike}:{opt}"

    def __str__(self) -> str:
        return self.raw
