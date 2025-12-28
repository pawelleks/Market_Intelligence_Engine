from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Optional
import logging
from pathlib import Path
import json

from mie_lib.analytics.skew.skew_engine import SkewEngine

router = APIRouter(
    prefix="/api/v1/analytics/skew",
    tags=["Analytics - Skew & PCR"]
)

logger = logging.getLogger(__name__)

# Helper to get engine (could be dependency injected)
def get_engine():
    return SkewEngine()

@router.get("/{ticker}/latest")
def get_latest_skew(ticker: str):
    """
    Get the most recent Skew and PCR record for a ticker.
    """
    try:
        engine = get_engine()
        history_file = engine.data_dir / f"{ticker.upper()}_skew.json"
        
        if not history_file.exists():
            # Trigger Calculation if missing?
            # Or just return 404. Let's return empty/404 for now to avoid blocking.
            return {}

        with open(history_file, 'r') as f:
            history = json.load(f)
            
        if not history:
            return {}
            
        # Return last record (assumed sorted)
        return history[-1]
        
    except Exception as e:
        logger.error(f"Error fetching latest skew for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ticker}/history")
def get_skew_history(ticker: str):
    """
    Get full historical Skew and PCR data for charts.
    """
    try:
        engine = get_engine()
        history_file = engine.data_dir / f"{ticker.upper()}_skew.json"
        
        if not history_file.exists():
            return []

        with open(history_file, 'r') as f:
            history = json.load(f)
            
        return history
        
    except Exception as e:
        logger.error(f"Error fetching skew history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{ticker}/refresh")
def refresh_skew(ticker: str, background_tasks: BackgroundTasks):
    """
    Trigger a backfill/refresh of Skew data.
    """
    engine = get_engine()
    background_tasks.add_task(engine.update_skew_history, ticker.upper())
    return {"status": "Refresh triggered", "ticker": ticker}
