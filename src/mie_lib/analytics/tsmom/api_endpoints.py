from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import date, datetime
import pandas as pd
import numpy as np
import logging

from mie_lib.analytics.tsmom.storage import load_current_snapshot, load_signal_history
from mie_lib.analytics.tsmom.engine import run_tsmom_daily_update
from mie_lib.analytics.tsmom.data_loader import load_ohlc_daily, DataNotFoundError

router = APIRouter()
LOG = logging.getLogger(__name__)

# --- Models ---

class TsmomSnapshotRow(BaseModel):
    asof_date: date
    ticker: str
    close: float
    ret_12m: float
    tsmom_dir: int
    signal_today: str
    signal_changed: bool
    lookback_days: int
    data_start: date
    data_end: date
    rows_used: int

class TsmomSignalRow(BaseModel):
    event_date: date
    ticker: str
    signal: str
    close: float
    ret_12m: float
    tsmom_dir: int
    lookback_days: int
    run_id: str
    created_at: Optional[datetime] = None

class TsmomChartData(BaseModel):
    ticker: str
    ohlc: List[Dict[str, Any]]
    signals: List[Dict[str, Any]]

# --- Endpoints ---

@router.get("/current", response_model=List[TsmomSnapshotRow])
def get_current_snapshot(signal_only: bool = False):
    """
    Returns the latest TSMOM snapshot for all tickers.
    If signal_only=True, filters for tickers with a signal change today.
    """
    df = load_current_snapshot()
    if df.empty:
        return []
        
    if signal_only:
        # Filter for signal_today != ""
        df = df[df["signal_today"] != ""]
        
    return df.to_dict(orient="records")

@router.get("/signals", response_model=List[TsmomSignalRow])
def get_signal_history(ticker: Optional[str] = None):
    """
    Returns the history of signal events.
    Optional filter by ticker.
    """
    df = load_signal_history()
    if df.empty:
        return []
        
    if ticker:
        df = df[df["ticker"] == ticker]
        
    # Sort by date desc
    df = df.sort_values("event_date", ascending=False)
    
    # Handle NaN
    df = df.replace({np.nan: None})
    
    return df.to_dict(orient="records")

@router.get("/chart/{ticker}", response_model=TsmomChartData)
def get_tsmom_chart_data(ticker: str):
    """
    Returns OHLC data and Signal events for a specific ticker to plot.
    """
    ticker = ticker.upper()
    try:
        # Load OHLC
        df_ohlc = load_ohlc_daily(ticker)
        
        # Load Signals
        df_all_signals = load_signal_history()
        signals = []
        if not df_all_signals.empty:
            df_sig = df_all_signals[df_all_signals["ticker"] == ticker]
            if not df_sig.empty:
                # Format signals
                signals = df_sig.to_dict(orient="records")
        
        # Format OHLC
        # Ensure dates are strings for JSON
        df_ohlc = df_ohlc.reset_index() # date move to column
        if "date" in df_ohlc.columns:
            df_ohlc["date_str"] = df_ohlc["date"].dt.strftime("%Y-%m-%d")
        
        ohlc_data = df_ohlc.replace({np.nan: None}).to_dict(orient="records")
            
        return {
            "ticker": ticker,
            "ohlc": ohlc_data,
            "signals": signals
        }
        
    except DataNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found for {ticker}")
    except Exception as e:
        LOG.error(f"Chart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run")
async def trigger_run_tsmom(
    background_tasks: BackgroundTasks, 
    lookback_days: int = 252, 
    backfill: bool = False
):
    """
    Triggers the TSMOM update process in the background.
    """
    def _run_task():
        try:
            run_tsmom_daily_update(lookback_days=lookback_days, backfill=backfill)
        except Exception as e:
            LOG.error(f"Background TSMOM run failed: {e}")
            
    background_tasks.add_task(_run_task)
    return {"status": "triggered", "message": "TSMOM update started in background"}
