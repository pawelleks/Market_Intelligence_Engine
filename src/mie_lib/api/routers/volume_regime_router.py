import io
import os
import httpx
import asyncio
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional

from mie_lib.analysis.volume_regime import compute_volume_metrics, classify_market_state
from mie_lib.db.volume_regime_db import get_signals, get_summary, get_db_health_stats

volume_regime_router = APIRouter()

THETA_HOST = os.getenv("THETA_HOST", "theta_terminal")
THETADATA_USERNAME = os.getenv("THETADATA_USERNAME") or os.getenv("THETA_USER", "default")
THETADATA_PASSWORD = os.getenv("THETADATA_PASSWORD") or os.getenv("THETA_PASS", "default")
THETA_PORT = "25510"

TIMEFRAMES = {
    "1m": 60000,
    "5m": 300000,
    "15m": 900000,
    "1h": 3600000,
    "4h": 14400000,
    "1d": 86400000
}

def is_market_open_now() -> bool:
    et_tz = pytz.timezone("America/New_York")
    now = datetime.now(et_tz)
    if now.weekday() >= 5: return False
    market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_start <= now <= market_end

async def fetch_thetadata_ohlc(ticker: str, ivl: int, days_back: int = 30) -> pd.DataFrame:
    """
    Fetch OHLCV data from Thetadata REST API for a given interval.

    Uses /v2/hist/stock/eod for daily data (ivl=86400000) since ThetaData's
    /ohlc endpoint doesn't support the daily interval. All intraday intervals
    use /v2/hist/stock/ohlc as before.
    """
    et_tz = pytz.timezone("America/New_York")
    et_now = datetime.now(et_tz)
    start_date = (et_now - timedelta(days=days_back)).strftime("%Y%m%d")
    end_date = et_now.strftime("%Y%m%d")

    is_daily = (ivl == 86400000)

    if is_daily:
        url = f"http://{THETA_HOST}:{THETA_PORT}/v2/hist/stock/eod"
        params = {
            "root": ticker.upper(),
            "start_date": start_date,
            "end_date": end_date,
        }
    else:
        url = f"http://{THETA_HOST}:{THETA_PORT}/v2/hist/stock/ohlc"
        params = {
            "root": ticker.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "ivl": str(ivl)
        }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise ValueError("Timeout connecting to Thetadata")
        except httpx.HTTPError as e:
            raise ValueError(f"HTTP Error: {e}")

    rows = data.get("response", [])
    if not rows:
        return pd.DataFrame()

    header = data.get("header", {}).get("format", [])
    records = []

    if is_daily:
        try:
            idx_open = header.index("open")
            idx_high = header.index("high")
            idx_low = header.index("low")
            idx_close = header.index("close")
            idx_vol = header.index("volume")
            idx_date = header.index("date")
        except ValueError:
            raise ValueError(f"EOD header missing expected fields: {header}")

        for r in rows:
            dt_str = str(r[idx_date])
            if len(dt_str) != 8:
                continue
            try:
                day = datetime(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
            except ValueError:
                continue

            naive_et = datetime(day.year, day.month, day.day, 16, 0, 0)
            aware_et = et_tz.localize(naive_et)

            records.append({
                "time": int(aware_et.timestamp()),
                "timestamp": aware_et.isoformat(),
                "open": float(r[idx_open]),
                "high": float(r[idx_high]),
                "low": float(r[idx_low]),
                "close": float(r[idx_close]),
                "volume": int(r[idx_vol])
            })
    else:
        for r in rows:
            ms_of_day, o, h, l, c, vol, cnt, dt_int = r
            dt_str = str(dt_int)
            if len(dt_str) != 8:
                continue
            try:
                day = datetime(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
            except ValueError:
                continue

            hours = ms_of_day // 3600000
            minutes = (ms_of_day % 3600000) // 60000
            seconds = (ms_of_day % 60000) // 1000
            naive_et = datetime(day.year, day.month, day.day, hours, minutes, seconds)
            aware_et = et_tz.localize(naive_et)

            records.append({
                "time": int(aware_et.timestamp()),
                "timestamp": aware_et.isoformat(),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": int(vol)
            })
        
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
    return df

@volume_regime_router.get("/api/volume-regime/historical/{ticker}")
async def get_volume_regime_historical(
    ticker: str,
    timeframe: str = Query("5m")
):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe. Allowed: {list(TIMEFRAMES.keys())}")

    ivl = TIMEFRAMES[timeframe]
    days_back = 75 if timeframe in ("1d", "4h") else 15

    try:
        df = await fetch_thetadata_ohlc(ticker, ivl, days_back=days_back)
    except ValueError as e:
        return {"ticker": ticker, "timeframe": timeframe, "state": "Unavailable", "error": str(e)}

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for ticker {ticker}")

    if len(df) < 20:
        return {"ticker": ticker, "timeframe": timeframe, "state": "Insufficient Data", "data": []}

    df = compute_volume_metrics(df)

    df = df.tail(50).copy()

    # Fill nan/inf
    import numpy as np
    df.replace([np.inf, -np.inf], 0, inplace=True)
    df.fillna(0, inplace=True)

    df["state"] = df.apply(classify_market_state, axis=1)

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "data": df.to_dict(orient="records")
    }

@volume_regime_router.get("/api/volume-regime/snapshot/{ticker}")
async def get_volume_regime_snapshot(ticker: str):
    market_open = is_market_open_now()

    start_time = time.time()
    results = {}
    valid_data_found = False

    # Sequential fetch — Theta Terminal is single-threaded.
    for tf, ivl in TIMEFRAMES.items():
        days_back = 75 if tf in ("1d", "4h") else 15
        try:
            df = await fetch_thetadata_ohlc(ticker, ivl, days_back=days_back)
        except Exception:
            results[tf] = {"state": "Unavailable", "market_open": market_open}
            continue

        if df.empty:
            results[tf] = {"state": "No Data", "market_open": market_open}
            continue

        if len(df) < 20:
            results[tf] = {"state": "Insufficient Data", "market_open": market_open}
            continue

        df = compute_volume_metrics(df)
        last_row = df.iloc[-1]
        state = classify_market_state(last_row)

        vol_mean = last_row.get("vol_mean_20d", 1)
        if pd.isna(vol_mean) or vol_mean == 0:
            vol_mean = 1

        results[tf] = {
            "state": state,
            "ud_vol_ratio": float(last_row.get("ud_vol_ratio", 1.0)) if pd.notna(last_row.get("ud_vol_ratio")) else 1.0,
            "price_change_20d": float(last_row.get("price_change_20d", 0)) if pd.notna(last_row.get("price_change_20d")) else 0,
            "volume_vs_avg": float(last_row.get("volume", 0) / vol_mean),
            "current_price": float(last_row.get("close", 0)),
            "market_open": market_open
        }
        if state not in ["Unavailable", "Insufficient Data", "No Data"]:
            valid_data_found = True

    duration = time.time() - start_time
    print(f"[Volume Regime] Snapshot for {ticker} fetched {len(TIMEFRAMES)} timeframes in {duration:.3f}s")

    if not valid_data_found and all(res.get("state") == "No Data" for res in results.values()):
        raise HTTPException(status_code=404, detail=f"No data found for ticker {ticker}")

    # Replace "No Data" with "Insufficient Data" for FE compatibility
    for key, val in results.items():
        if val.get("state") == "No Data":
            val["state"] = "Insufficient Data"

    return {
        "ticker": ticker,
        "snapshot": results
    }

@volume_regime_router.get("/api/volume-regime/signals/summary")
async def api_get_signals_summary():
    """Returns a coverage summary for all tracked tickers/timeframes."""
    return get_summary()

@volume_regime_router.get("/api/volume-regime/signals/health")
async def api_get_signals_health():
    """Returns health statistics for the signals database and background recorder status."""
    stats = get_db_health_stats()
    # While we cannot easily query the background task instance directly from inside the router
    # without global state, we can return the DB health.
    return {
        "database": stats,
        "status": "online"
    }

@volume_regime_router.get("/api/volume-regime/signals/export")
async def api_export_signals(
    ticker: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query(..., description="Timeframe (e.g., 1d, 1h)"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO8601)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO8601)")
):
    """Exports signal data as a Parquet file for backtesting use."""
    ticker = ticker.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe. Allowed: {list(TIMEFRAMES.keys())}")
        
    start_ts = None
    end_ts = None
    
    try:
        if start:
            start_ts = int(pd.to_datetime(start).timestamp())
        if end:
            end_ts = int(pd.to_datetime(end).timestamp())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format for start or end. Use ISO8601 or YYYY-MM-DD.")
        
    signals = get_signals(ticker, timeframe, start_time=start_ts, end_time=end_ts, limit=100000)
    
    if not signals:
        raise HTTPException(status_code=404, detail=f"No signals found for {ticker} {timeframe} in requested range")
        
    df = pd.DataFrame(signals)
    
    # Convert Unix timestamps back to readable datetime columns for the parquet export
    if "candle_time" in df.columns:
        df["candle_datetime"] = pd.to_datetime(df["candle_time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    if "recorded_at" in df.columns:
        df["recorded_datetime"] = pd.to_datetime(df["recorded_at"], unit="s", utc=True).dt.tz_convert("America/New_York")
        
    # Write to in-memory buffer
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)
    
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"vr_signals_{ticker}_{timeframe}_{date_str}.parquet"
    
    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@volume_regime_router.get("/api/volume-regime/signals/{ticker}")
async def api_get_signals(
    ticker: str,
    timeframe: str = Query(..., description="Timeframe (e.g., 1d, 1h)"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO8601)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO8601)"),
    limit: int = Query(1000, le=10000)
):
    """Retrieves stored signals for a specific ticker and timeframe."""
    ticker = ticker.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe. Allowed: {list(TIMEFRAMES.keys())}")
        
    start_ts = None
    end_ts = None
    
    try:
        if start:
            start_ts = int(pd.to_datetime(start).timestamp())
        if end:
            end_ts = int(pd.to_datetime(end).timestamp())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format for start or end. Use ISO8601 or YYYY-MM-DD.")
        
    signals = get_signals(ticker, timeframe, start_time=start_ts, end_time=end_ts, limit=limit)
    
    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "count": len(signals),
        "data": signals
    }
