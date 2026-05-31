"""Library logging hygiene.

A library must not reconfigure the host's root logger on import or on
instantiation. Constructing the interface must not call logging.basicConfig;
an explicit opt-in helper (configure_logging) is provided for scripts.
"""

import logging
import re
from pathlib import Path
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


def test_package_logs_via_namespaced_logger_not_root():
    """Shipped modules must log through a namespaced logger, never the root.

    Calling ``logging.error``/``logging.warning``/etc. at module level emits
    on the root logger, which forces output onto the host application. Library
    code must use ``self.logger``/``logging.getLogger(__name__)`` instead. The
    opt-in ``configure_logging`` helper (which calls ``basicConfig``) is the
    only sanctioned root-logger touchpoint and uses no level functions.
    """
    src_root = Path(__file__).resolve().parents[1] / "src"
    level_call = re.compile(
        r"\blogging\.(error|warning|warn|info|debug|critical|exception)\s*\("
    )
    offenders = []
    for path in src_root.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            code = line.split("#", 1)[0]
            if level_call.search(code):
                offenders.append(f"{path.relative_to(src_root.parent)}:{lineno}")
    assert offenders == [], f"root-logger level calls in shipped code: {offenders}"
