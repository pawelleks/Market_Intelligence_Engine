from fastapi import APIRouter, HTTPException
from mie_lib.utils.paths import DATA_DIR
import json

router = APIRouter(tags=["hmm"])

@router.get("/backtest/{ticker}")
async def get_hmm_backtest_results(ticker: str):
    """
    Returns the latest backtest results for a ticker.
    Results include summary metrics and equity curves for all grid configurations.
    """
    path = DATA_DIR / "analytics" / "hmm" / f"backtest_results_{ticker}.json"
    
    if not path.exists():
        # Fallback: Check if we have results for SPY as a default demo
        # Or return 404
        raise HTTPException(status_code=404, detail=f"No backtest results found for {ticker}. Run 'mie backtest-hmm --ticker {ticker}' first.")
        
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load backtest results: {e}")
