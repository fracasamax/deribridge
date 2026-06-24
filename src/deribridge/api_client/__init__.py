"""Backward-compatibility shim for the relocated Deribit client.

The Deribit transport, interface, response models, and helpers moved to
``deribridge.exchanges.deribit`` in the multi-exchange refactor. This package
re-exports the old public names and aliases the old submodule paths
(``deribridge.api_client.websocket_api_client`` etc.) onto the relocated
modules so existing imports — and string-based patch targets — keep working
unchanged.

New code should import from ``deribridge.exchanges.deribit`` or use the
top-level facade (``deribridge.connect(...)``).
"""
import sys as _sys

from ..core.transport import rate_limiter  # relocated to core/transport in the refactor
from ..exchanges.deribit import (  # noqa: F401
    client_management,
    deribit_api_interface,
    deribit_error_codes,
    deribit_instrument,
    deribit_response_models,
    enhanced_api_client,
    websocket_api_client,
)

# Alias the old dotted module paths onto the relocated module objects. Using
# the *same* module object (not a re-import) means identity holds and
# string-based monkeypatch targets such as
# "deribridge.api_client.websocket_api_client.websockets" resolve to the real
# module, so patches take effect where the code actually runs.
_RELOCATED = {
    "client_management": client_management,
    "deribit_api_interface": deribit_api_interface,
    "deribit_error_codes": deribit_error_codes,
    "deribit_instrument": deribit_instrument,
    "deribit_response_models": deribit_response_models,
    "enhanced_api_client": enhanced_api_client,
    "rate_limiter": rate_limiter,
    "websocket_api_client": websocket_api_client,
}
for _name, _mod in _RELOCATED.items():
    _sys.modules[f"{__name__}.{_name}"] = _mod

# Re-export the same public surface this package exposed before the move.
from ..exchanges.deribit import *  # noqa: F401,F403,E402
from ..exchanges.deribit import __all__ as __all__  # noqa: F401,E402
