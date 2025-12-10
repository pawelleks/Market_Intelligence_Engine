from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from datetime import datetime


router = APIRouter()
LATEST_JSON = Path("data/analytics/gaf/latest.json")

@router.get("/latest")
async def get_latest_gaf_prediction():
    """Returns the latest GAF prediction, probability, and base64 image."""
    if not LATEST_JSON.exists():
        raise HTTPException(status_code=404, detail="No GAF prediction found. Please run 'build-gaf-daily' CLI.")
        
    try:
        with open(LATEST_JSON, 'r') as f:
            data = json.load(f)
            
        # Inject Metadata on the fly
        # 1. Analysis Date (File Creation/Mod Time)
        mtime = LATEST_JSON.stat().st_mtime
        data["analysis_date"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # 2. Last Trading Day (from OHLC data)
        if "ohlc_data" in data and data["ohlc_data"]:
            data["last_trading_day"] = data["ohlc_data"][-1].get("time", "Unknown")
        else:
            data["last_trading_day"] = "Unknown"
            
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load GAF data: {str(e)}")

BACKTEST_JSON = Path("data/analytics/gaf/backtest_latest.json")

@router.get("/backtest")
async def get_latest_backtest_results():
    """Returns the latest Backtest results."""
    if not BACKTEST_JSON.exists():
        # RETURN MOCK/EMPTY instead of 404 to prevent UI crashes if never run
        return {"status": "no_run", "message": "No backtest run yet."}
        
    try:
        with open(BACKTEST_JSON, 'r') as f:
            data = json.load(f)
        data["status"] = "ok"
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Backtest data: {str(e)}")
