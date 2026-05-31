"""Library logging hygiene.

A library must not reconfigure the host's root logger on import or on
instantiation. Constructing the interface must not call logging.basicConfig;
an explicit opt-in helper (configure_logging) is provided for scripts.
"""

import logging
from unittest.mock import MagicMock, patch

import deribridge
from deribridge.api_client.deribit_api_interface import DeribitAPIInterface


def test_constructor_does_not_call_basicconfig():
    client = MagicMock()
    client.connected = True
    with patch.object(logging, "basicConfig") as bc:
        DeribitAPIInterface(client=client)
    bc.assert_not_called()


def test_configure_logging_is_exported_and_callable():
    assert hasattr(deribridge, "configure_logging")
    assert callable(deribridge.configure_logging)
