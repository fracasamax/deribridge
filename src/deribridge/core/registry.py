"""Adapter registry with lazy, extras-aware resolution.

A static name -> ``"module:attr"`` table is the source of truth for built-in
adapters. It answers "does this adapter exist?" with zero imports; the adapter
class is imported only when actually requested. When an adapter's third-party
dependencies are missing, the import failure is translated into a friendly,
actionable :class:`MissingExchangeExtra`.

Out-of-tree adapters can also register via the ``deribridge.exchanges``
entry-point group without modifying this table.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from .errors import MissingExchangeExtra, UnknownExchangeError


@dataclass(frozen=True)
class _Entry:
    module: str  # dotted module path, imported lazily
    attr: str  # adapter class attribute within that module
    extra: str  # pip extra that supplies this adapter's dependencies


#: Built-in adapters. No imports happen by reading this table.
_BUILTIN: dict[str, _Entry] = {
    "deribit": _Entry("deribridge.exchanges.deribit.adapter", "DeribitAdapter", "deribit"),
    "binance": _Entry("deribridge.exchanges.binance.adapter", "BinanceAdapter", "binance"),
}

_ENTRY_POINT_GROUP = "deribridge.exchanges"


def available_adapters() -> list[str]:
    """Names of all known adapters, without importing any of them."""
    names = set(_BUILTIN) | set(_entry_point_names())
    return sorted(names)


def resolve(name: str) -> type:
    """Return the adapter class for ``name``.

    Raises:
        UnknownExchangeError: the name is not registered.
        MissingExchangeExtra: the adapter exists but its dependencies are not
            installed.
    """
    key = name.lower()
    entry = _BUILTIN.get(key)
    extra = entry.extra if entry else key
    module_path = entry.module if entry else None
    attr = entry.attr if entry else None

    if entry is None:
        # Fall back to the entry-point overlay for out-of-tree adapters.
        ep = _entry_point(key)
        if ep is None:
            raise UnknownExchangeError(name, available_adapters())
        return ep.load()

    try:
        module = importlib.import_module(module_path)  # type: ignore[arg-type]
    except ImportError as exc:
        missing = getattr(exc, "name", "") or ""
        # A failure importing deribridge's own code is a real bug, not a
        # missing optional dependency — surface it unchanged.
        if missing.startswith("deribridge"):
            raise
        raise MissingExchangeExtra(key, extra, missing) from exc
    return getattr(module, attr)  # type: ignore[arg-type]


def _entry_points():
    from importlib.metadata import entry_points

    try:
        return entry_points(group=_ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - very old importlib.metadata
        return entry_points().get(_ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]


def _entry_point_names() -> list[str]:
    try:
        return [ep.name for ep in _entry_points()]
    except Exception:  # pragma: no cover - defensive
        return []


def _entry_point(name: str):
    for ep in _entry_points():
        if ep.name == name:
            return ep
    return None
