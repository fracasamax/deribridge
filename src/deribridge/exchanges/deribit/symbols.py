"""Parse Deribit instrument names into canonical :class:`Symbol` objects.

Deribit naming (see also the legacy ``DeribitInstrument`` parser, kept for
back-compat):
    Option:    BTC-26DEC25-60000-C   (underlying-expiry-strike-C/P)
    Perpetual: BTC-PERPETUAL          (also linear: BTC_USDC-PERPETUAL)
    Future:    BTC-26DEC25            (underlying-expiry)
    DVOL/index BTCDVOL_USDC-26DEC25
    Spot:      BTC_USDC               (base_quote)

Inverse instruments are quoted in USD and settle in the base asset; linear
instruments carry their quote in the underlying token (``BTC_USDC``).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from ...core.enums import AssetKind, OptionType
from ...core.models import Symbol

_OPTION = re.compile(
    r"^(?P<u>[A-Z0-9]+(?:_[A-Z]+)?)-(?P<exp>\d{1,2}[A-Z]{3}\d{2})-(?P<strike>\d+(?:\.\d+)?)-(?P<opt>[CP])$"
)
_PERPETUAL = re.compile(r"^(?P<u>[A-Z0-9]+(?:_[A-Z]+)?)-PERPETUAL$")
_DVOL = re.compile(r"^(?P<u>[A-Z]+DVOL_[A-Z]+)-(?P<exp>\d{1,2}[A-Z]{3}\d{2})$")
_FUTURE = re.compile(r"^(?P<u>[A-Z0-9]+(?:_[A-Z]+)?)-(?P<exp>\d{1,2}[A-Z]{3}\d{2})$")
_SPOT = re.compile(r"^(?P<base>[A-Z0-9]+)_(?P<quote>[A-Z]+)$")
_BARE = re.compile(r"^(?P<base>[A-Z0-9]+)$")

EXCHANGE = "deribit"


def _parse_expiry(value: str) -> datetime:
    # Deribit dated instruments expire at 08:00 UTC.
    dt = datetime.strptime(value, "%d%b%y")
    return dt.replace(hour=8, minute=0, second=0, tzinfo=timezone.utc)


def _split_underlying(token: str) -> tuple[str, str, str | None]:
    """Return (base, quote, settle) for an underlying token.

    Linear ``BASE_QUOTE`` -> quote/settle = QUOTE; inverse ``BASE`` -> quote USD,
    settled in the base asset.
    """
    if "_" in token:
        base, quote = token.split("_", 1)
        return base, quote, quote
    return token, "USD", token


def parse_symbol(raw: str) -> Symbol:
    """Parse a Deribit instrument name into a canonical :class:`Symbol`."""
    if m := _OPTION.match(raw):
        base, quote, settle = _split_underlying(m.group("u"))
        return Symbol(
            raw=raw, base=base, quote=quote, settle=settle, kind=AssetKind.OPTION,
            exchange=EXCHANGE, expiry=_parse_expiry(m.group("exp")),
            strike=Decimal(m.group("strike")), option_type=OptionType.from_str(m.group("opt")),
        )
    if m := _PERPETUAL.match(raw):
        base, quote, settle = _split_underlying(m.group("u"))
        return Symbol(
            raw=raw, base=base, quote=quote, settle=settle,
            kind=AssetKind.PERPETUAL, exchange=EXCHANGE,
        )
    if m := _DVOL.match(raw):
        base, quote, settle = _split_underlying(m.group("u"))
        return Symbol(
            raw=raw, base=base, quote=quote, settle=settle, kind=AssetKind.INDEX,
            exchange=EXCHANGE, expiry=_parse_expiry(m.group("exp")),
        )
    if m := _FUTURE.match(raw):
        base, quote, settle = _split_underlying(m.group("u"))
        return Symbol(
            raw=raw, base=base, quote=quote, settle=settle, kind=AssetKind.FUTURE,
            exchange=EXCHANGE, expiry=_parse_expiry(m.group("exp")),
        )
    if m := _SPOT.match(raw):
        return Symbol(
            raw=raw, base=m.group("base"), quote=m.group("quote"),
            kind=AssetKind.SPOT, exchange=EXCHANGE,
        )
    if m := _BARE.match(raw):
        return Symbol(
            raw=raw, base=m.group("base"), quote="USD", kind=AssetKind.SPOT, exchange=EXCHANGE,
        )
    raise ValueError(f"unrecognized Deribit instrument name: {raw!r}")
