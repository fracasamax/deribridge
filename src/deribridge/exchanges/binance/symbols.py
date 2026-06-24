"""Parse Binance spot symbols into canonical :class:`Symbol` objects.

Binance concatenates base and quote with no delimiter (``BTCUSDT``), so a bare
symbol string is ambiguous. The authoritative split comes from ``exchangeInfo``
(``baseAsset``/``quoteAsset``); :func:`symbol_from_info` uses it. For a bare
string with no metadata, :func:`parse_symbol` falls back to a quote-suffix
heuristic over common Binance quote assets.
"""
from __future__ import annotations

from typing import Any

from ...core.enums import AssetKind
from ...core.models import Symbol

EXCHANGE = "binance"

# Ordered longest-first so e.g. FDUSD matches before USD.
_COMMON_QUOTES = (
    "FDUSD", "USDT", "USDC", "BUSD", "TUSD", "DAI",
    "TRY", "EUR", "GBP", "BRL", "BTC", "ETH", "BNB", "USD",
)


def symbol_from_info(info: dict[str, Any]) -> Symbol:
    """Build a Symbol from an ``exchangeInfo`` symbol entry (authoritative)."""
    return Symbol(
        raw=info["symbol"],
        base=info["baseAsset"],
        quote=info["quoteAsset"],
        kind=AssetKind.SPOT,
        exchange=EXCHANGE,
    )


def parse_symbol(raw: str) -> Symbol:
    """Best-effort parse of a bare Binance spot symbol via quote-suffix match."""
    s = raw.upper()
    for quote in _COMMON_QUOTES:
        if s.endswith(quote) and len(s) > len(quote):
            return Symbol(
                raw=raw, base=s[: -len(quote)], quote=quote,
                kind=AssetKind.SPOT, exchange=EXCHANGE,
            )
    # Unknown quote: keep the raw string usable; leave quote empty.
    return Symbol(raw=raw, base=s, quote="", kind=AssetKind.SPOT, exchange=EXCHANGE)
