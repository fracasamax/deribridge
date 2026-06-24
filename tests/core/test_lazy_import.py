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

_DERIBIT_EXTRA_INSTALLED = importlib.util.find_spec("websockets") is not None


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
