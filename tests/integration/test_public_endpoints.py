"""Live public-endpoint integration tests (no credentials required).

Skipped unless DERIBRIDGE_RUN_INTEGRATION=1.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DERIBRIDGE_RUN_INTEGRATION") != "1",
    reason="set DERIBRIDGE_RUN_INTEGRATION=1 to run integration tests",
)


@pytest.mark.asyncio
async def test_public_ticker_btc_perpetual():
    from deribridge import DeribitAPIInterface

    api = DeribitAPIInterface.configure(use_test_env=True, load_dotenv_file=False)
    assert await api.start_client()
    try:
        ticker = await api.get_ticker("BTC-PERPETUAL")
        assert ticker is not None
    finally:
        await api.stop_client()
