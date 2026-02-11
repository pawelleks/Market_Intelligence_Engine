
import pytest
import datetime
from unittest.mock import MagicMock, AsyncMock
from mie_lib.analytics.expected_moves.theta_expected_moves_engine import ThetaExpectedMovesEngine

@pytest.fixture
def engine():
    return ThetaExpectedMovesEngine()


def test_run_mocked(engine):
    import asyncio
    
    async def run_test():
        # Mock httpx client
        mock_client = AsyncMock()
        engine.client = mock_client
        
        # Mock Spot Price Response
        # [ms, bid_size, bid_cond, bid, bid_ex, ask_size, ask_cond, ask, ask_ex]
        # Price = (500 + 500.10) / 2 = 500.05
        spot_resp = MagicMock()
        spot_resp.status_code = 200
        spot_resp.json.return_value = {"response": [0, 10, 0, 500.00, 0, 10, 0, 500.10, 0]}
        
        # Mock Strikes Response
        strikes_resp = MagicMock()
        strikes_resp.status_code = 200
        strikes_resp.json.return_value = {"response": [490.0, 500.0, 510.0]}
        
        # Mock Option Quote Response
        # Call: Bid 2.0, Ask 2.10 -> Mid 2.05
        call_resp = MagicMock()
        call_resp.status_code = 200
        call_resp.json.return_value = {"response": [0, 10, 0, 2.00, 0, 10, 0, 2.10, 0]}
        
        # Put: Bid 1.90, Ask 2.00 -> Mid 1.95
        put_resp = MagicMock()
        put_resp.status_code = 200
        put_resp.json.return_value = {"response": [0, 10, 0, 1.90, 0, 10, 0, 2.00, 0]}
        
        # Configure Side Effects
        async def side_effect(url, params=None):
            if "stock/quote" in url or "index/quote" in url:
                return spot_resp
            if "list/strikes" in url:
                return strikes_resp
            if "option/quote" in url:
                if params.get("right") == "C": return call_resp
                if params.get("right") == "P": return put_resp
            return MagicMock(status_code=404)
            
        mock_client.get.side_effect = side_effect
        
        # Run
        res = await engine.run("SPY")
        
        # Verify
        assert res["ticker"] == "SPY"
        assert res["current_price"] == 500.05
        
        # Check Ranges
        # Straddle = 2.05 + 1.95 = 4.00
        # EM = 4.00 * 0.85 = 3.40
        # High = 500.05 + 3.40 = 503.45
        # Low = 500.05 - 3.40 = 496.65
        
        # 0DTE
        r0 = res["0dte_range"]
        assert r0 is not None
        assert abs(r0["plus_minus"] - 3.40) < 0.001
        assert abs(r0["high"] - 503.45) < 0.001
        assert abs(r0["low"] - 496.65) < 0.001

    asyncio.run(run_test())


