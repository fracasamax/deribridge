"""Back-compatibility guarantees for the top-level package surface.

Runs under the full install (the Deribit extra is present). Ensures every name
advertised in ``deribridge.__all__`` actually resolves — including the lazily
re-exported Deribit-flavored names — so ``from deribridge import *`` never
breaks and old import paths keep working.
"""
import importlib

import pytest

import deribridge


def test_every_all_name_resolves():
    unresolved = []
    for name in deribridge.__all__:
        try:
            getattr(deribridge, name)
        except AttributeError:
            unresolved.append(name)
    assert not unresolved, f"names in __all__ that do not resolve: {unresolved}"


def test_import_star_succeeds():
    ns: dict = {}
    exec("from deribridge import *", ns)
    assert "DeribitAPIInterface" in ns  # legacy
    assert "connect" in ns  # new framework API


@pytest.mark.parametrize(
    "path,attr",
    [
        ("deribridge.api_client.deribit_api_interface", "DeribitAPIInterface"),
        ("deribridge.api_client.deribit_api_interface", "IndeterminateOrderError"),
        ("deribridge.api_client.websocket_api_client", "DeribitWebSocketClient"),
        ("deribridge.api_client.deribit_response_models", "Ticker"),
        ("deribridge.api_client.rate_limiter", "RateLimiter"),
        ("deribridge.api_client.client_management", "connect_deribit_client"),
        ("deribridge.exchanges.deribit", "DeribitAPIInterface"),
    ],
)
def test_legacy_and_new_import_paths_resolve(path, attr):
    module = importlib.import_module(path)
    assert hasattr(module, attr)


def test_indeterminate_error_identity_unified():
    from deribridge import IndeterminateOrderError as top
    from deribridge.core.errors import IndeterminateOrderError as core
    from deribridge.exchanges.deribit.deribit_api_interface import (
        IndeterminateOrderError as iface,
    )

    assert top is core is iface
