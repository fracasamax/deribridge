"""configure() must honour the documented python-dotenv loading behaviour."""

from unittest.mock import patch

from deribridge.api_client import deribit_api_interface as mod
from deribridge.api_client.deribit_api_interface import DeribitAPIInterface


def test_configure_loads_dotenv_by_default():
    with patch.object(mod, "load_dotenv") as ld:
        DeribitAPIInterface.configure(client_id="x", client_secret="y")
    ld.assert_called_once()


def test_configure_can_skip_dotenv():
    with patch.object(mod, "load_dotenv") as ld:
        DeribitAPIInterface.configure(
            client_id="x", client_secret="y", load_dotenv_file=False
        )
    ld.assert_not_called()
