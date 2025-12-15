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

@router.get("/signals/{ticker}/{n_states}/{window_years}")
async def get_hmm_signals(ticker: str, n_states: int, window_years: str):
    """
    Returns the list of signals (Buy/Sell) for a specific HMM configuration.
    """
    from mie_lib.utils.paths import HMM_DIR
    import pandas as pd
    
    # Path: data/analytics/hmm/{ticker}/signals/signals_{n_states}_{window}.parquet
    path = HMM_DIR / ticker / "signals" / f"signals_{n_states}_{window_years}.parquet"
    
    if not path.exists():
        # It might be possible that no signals were generated (e.g. short history), 
        # or the backtest hasn't run.
        # Check if backtest exists at all to give better error?
        # For now, 404 is appropriate.
        return []
        
    try:
        df = pd.read_parquet(path)
        # Format dates
        if "date" in df.columns:
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load signals: {e}")
