"""Live authenticated read-only integration tests (TESTNET credentials).

Skipped unless DERIBRIDGE_RUN_INTEGRATION=1, and skipped if testnet credentials
are not present in the environment. These calls are read-only — no orders.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DERIBRIDGE_RUN_INTEGRATION") != "1",
    reason="set DERIBRIDGE_RUN_INTEGRATION=1 to run integration tests",
)

_HAS_TESTNET_CREDS = bool(
    os.environ.get("DERIBIT_API_CLIENT_ID_TEST")
    and os.environ.get("DERIBIT_API_SECRET_TEST")
)


@pytest.mark.skipif(not _HAS_TESTNET_CREDS, reason="no testnet credentials in env")
@pytest.mark.asyncio
async def test_authenticated_get_positions_readonly():
    from deribridge import DeribitAPIInterface

    api = DeribitAPIInterface.configure(use_test_env=True)
    assert await api.start_client()
    try:
        positions = await api.get_positions()
        assert positions is not None
    finally:
        await api.stop_client()
