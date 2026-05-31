"""Tests for response-model derived properties.

Covers the Tier 1 bug where Ticker.spread / Ticker.mid_price did
``float - None`` arithmetic and crashed on a one-sided / empty book.
"""
from deribridge.api_client.deribit_response_models import Ticker


def _ticker(best_bid, best_ask):
    return Ticker.from_dict(
        {
            "instrument_name": "BTC-PERPETUAL",
            "best_bid_price": best_bid,
            "best_ask_price": best_ask,
        }
    )


def test_spread_and_mid_with_both_sides():
    t = _ticker(100.0, 102.0)
    assert t.spread == 2.0
    assert t.mid_price == 101.0


def test_spread_none_when_bid_missing():
    t = _ticker(None, 102.0)
    assert t.spread is None
    assert t.mid_price is None


def test_spread_none_when_ask_missing():
    t = _ticker(100.0, None)
    assert t.spread is None
    assert t.mid_price is None


def test_spread_none_when_both_missing():
    t = _ticker(None, None)
    assert t.spread is None
    assert t.mid_price is None


def test_to_typed_result_rejects_list():
    import pytest
    from pydantic import BaseModel
    from deribridge.api_client.deribit_response_models import DeribitResultResponse

    class _M(BaseModel):
        a: int

    resp = DeribitResultResponse(raw_response={"result": [{"a": 1}, {"a": 2}]})
    with pytest.raises(TypeError):
        resp.to_typed_result(_M)


def test_to_typed_list_returns_list():
    from pydantic import BaseModel
    from deribridge.api_client.deribit_response_models import DeribitResultResponse

    class _M(BaseModel):
        a: int

    resp = DeribitResultResponse(raw_response={"result": [{"a": 1}, {"a": 2}]})
    out = resp.to_typed_list(_M)
    assert isinstance(out, list) and len(out) == 2
    assert out[0].a == 1 and out[1].a == 2
