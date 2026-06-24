"""Lazy-import, adapter discovery, and friendly missing-extra behavior.

These run in both the full ``[all]`` env and the core-only env. The
missing-dependency assertion only fires when the Deribit extra is absent
(core-only), so it is skipped when ``websockets`` is installed.
"""
import asyncio
import importlib.util

import pytest

import deribridge
from deribridge import MissingExchangeExtra, UnknownExchangeError
from deribridge.core import registry

_DERIBIT_EXTRA_INSTALLED = importlib.util.find_spec("websockets") is not None


class _FakeEntryPoint:
    """A stand-in for an out-of-tree ``deribridge.exchanges`` entry point."""

    def __init__(self, name: str, exc: Exception) -> None:
        self.name = name
        self._exc = exc

    def load(self):
        raise self._exc


def test_adapters_discoverable_without_importing_them():
    names = set(deribridge.available_adapters())
    assert {"deribit", "binance"} <= names


def test_unknown_adapter_raises():
    with pytest.raises(UnknownExchangeError):
        deribridge.create("does-not-exist")


def test_new_generic_api_is_exported():
    for name in ("connect", "create", "available_adapters", "ExchangeClient"):
        assert name in deribridge.__all__
        assert hasattr(deribridge, name)


@pytest.mark.skipif(
    _DERIBIT_EXTRA_INSTALLED,
    reason="deribit extra installed; the missing-dependency path is not exercised",
)
def test_connect_without_extra_raises_friendly_error():
    with pytest.raises(MissingExchangeExtra) as ei:
        asyncio.run(deribridge.connect("deribit"))
    assert "pip install" in str(ei.value)


@pytest.mark.skipif(
    _DERIBIT_EXTRA_INSTALLED,
    reason="deribit extra installed; the legacy lazy-name path resolves normally",
)
def test_legacy_name_without_extra_raises_friendly_error():
    with pytest.raises(MissingExchangeExtra):
        deribridge.DeribitAPIInterface  # noqa: B018 - attribute access triggers lazy import


def test_out_of_tree_missing_dependency_raises_friendly_error(monkeypatch):
    """An out-of-tree adapter whose third-party dep is missing must be
    translated into MissingExchangeExtra, not a bare ImportError."""
    ep = _FakeEntryPoint("acme", ImportError("No module named 'some_missing_dep'", name="some_missing_dep"))
    monkeypatch.setattr(registry, "_entry_point", lambda key: ep if key == "acme" else None)
    monkeypatch.setattr(registry, "_entry_points", lambda: [ep])

    with pytest.raises(MissingExchangeExtra) as ei:
        registry.resolve("acme")
    assert ei.value.exchange == "acme"
    # The adapter name is used as the extra hint for out-of-tree adapters.
    assert ei.value.extra == "acme"
    assert ei.value.missing == "some_missing_dep"
    assert "pip install" in str(ei.value)


def test_out_of_tree_internal_import_error_propagates_unchanged(monkeypatch):
    """A deribridge-internal ImportError from an out-of-tree adapter is a real
    bug and must surface unchanged, not be masked as a missing extra."""
    exc = ImportError("boom", name="deribridge.core.something")
    ep = _FakeEntryPoint("acme", exc)
    monkeypatch.setattr(registry, "_entry_point", lambda key: ep if key == "acme" else None)
    monkeypatch.setattr(registry, "_entry_points", lambda: [ep])

    with pytest.raises(ImportError) as ei:
        registry.resolve("acme")
    assert not isinstance(ei.value, MissingExchangeExtra)
    assert ei.value is exc
