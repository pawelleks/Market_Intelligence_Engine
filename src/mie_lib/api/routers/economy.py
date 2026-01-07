from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import pandas as pd
import json
import yaml
from datetime import datetime
from mie_lib.api.dependencies import get_current_user

router = APIRouter(
    prefix="/economy",
    tags=["economy"],
    dependencies=[Depends(get_current_user)]
)

MACRO_CONFIG_PATH = Path("config/macro_series.yml")
FRED_DATA_DIR = Path("data/raw/macro/fred")

@router.get("/macro/structure")
def get_macro_structure() -> Dict[str, Any]:
    """
    Parses macro_series.yml to return series grouped by category (comments).
    """
    if not MACRO_CONFIG_PATH.exists():
        return {"status": "error", "message": "Config not found"}

    categories = {}
    current_category = "Uncategorized"
    
    # Simple parser for line-based comments
    try:
        with open(MACRO_CONFIG_PATH, "r") as f:
            lines = f.readlines()
            
        # First load valid keys to filter
        with open(MACRO_CONFIG_PATH, "r") as f:
            yaml_content = yaml.safe_load(f)
            valid_series = yaml_content.get("series", {})

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Detect Category Header
            # Format: # --- Category Name ---
            if stripped.startswith("# ---") and stripped.endswith("---"):
                cat_name = stripped.replace("# ---", "").replace("---", "").strip()
                current_category = cat_name
                if current_category not in categories:
                    categories[current_category] = []
            
            # Detect Series Line
            # Format: SERIES_ID: Description
            elif ":" in stripped and not stripped.startswith("#"):
                key = stripped.split(":")[0].strip()
                if key in valid_series:
                    if current_category not in categories:
                         categories[current_category] = []
                    
                    # Avoid duplicates if multiple lines match (unlikely in valid yaml but possible)
                    if not any(item["id"] == key for item in categories[current_category]):
                        categories[current_category].append({
                            "id": key,
                            "name": valid_series[key]
                        })

        # Convert to list for frontend
        result = []
        for cat, items in categories.items():
            if items:
                result.append({"category": cat, "series": items})
                
        return {"status": "ok", "data": result}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/macro/series/{series_id}")
def get_macro_series(series_id: str) -> Dict[str, Any]:
    """
    Returns time series data for a specific ID, PLUS recession data (USREC).
    """
    series_path = FRED_DATA_DIR / f"{series_id}.parquet"
    usrec_path = FRED_DATA_DIR / "USREC.parquet"
    
    if not series_path.exists():
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found. Run ingestion first.")
        
    try:
        # Load Series
        df_series = pd.read_parquet(series_path)
        
        # Normalize columns: Ensure we have 'date' and 'value'
        # FRED ingestion usually results in 'date' and {SERIES_ID}
        # We rename the column that is not 'date' to 'value'
        cols = df_series.columns.tolist()
        if "date" in cols:
            cols.remove("date")
        
        if len(cols) == 1:
            df_series = df_series.rename(columns={cols[0]: "value"})
        
        df_series["date"] = df_series["date"].dt.strftime("%Y-%m-%d")
        series_data = df_series.to_dict(orient="records")
        
        # Calculate metadata
        latest_observation = None
        last_updated = None
        if len(series_data) > 0:
            # Sort by date to get latest
            sorted_data = sorted(series_data, key=lambda x: x["date"], reverse=True)
            latest = sorted_data[0]
            latest_observation = {
                "date": latest["date"],
                "value": latest["value"]
            }
            # Use latest date as last_updated (FRED doesn't provide actual update timestamp in parquet)
            last_updated = latest["date"]
        
        # Load Recession Data
        recessions = []
        if usrec_path.exists():
            df_rec = pd.read_parquet(usrec_path)
            # Filter for rows where USREC == 1
            df_rec = df_rec[df_rec["value"] == 1].copy()
            df_rec["date"] = df_rec["date"].dt.strftime("%Y-%m-%d")
            # We want ranges or just a list of dates? 
            # TradingView needs ranges for efficient drawing usually, OR we pass all dates.
            # Passing all dates is easier for now, frontend can process into areas or histogram.
            recessions = df_rec[["date", "value"]].to_dict(orient="records")

        return {
            "status": "ok", 
            "data": {
                "series": series_data,
                "recessions": recessions,
                "meta": {
                    "id": series_id,
                    "latest_observation": latest_observation,
                    "last_updated": last_updated
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/macro/overlay/stock/{ticker}")
def get_stock_overlay_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch stock price data for chart overlay (SPY, DIA, IWM, QQQ).
    Returns closing prices in the same format as FRED series data.
    """
    ticker = ticker.upper()
    
    # Validate ticker
    valid_tickers = ['SPY', 'DIA', 'IWM', 'QQQ']
    if ticker not in valid_tickers:
        raise HTTPException(status_code=400, detail=f"Invalid ticker. Must be one of: {valid_tickers}")
    
    stock_path = Path(f"data/raw/{ticker}.parquet")
    
    if not stock_path.exists():
        raise HTTPException(status_code=404, detail=f"Stock data for {ticker} not found at {stock_path}")
    
    try:
        df_stock = pd.read_parquet(stock_path)
        
        # Normalize columns: expect 'date' and 'close'
        if 'date' not in df_stock.columns or 'close' not in df_stock.columns:
            raise ValueError("Stock data must contain 'date' and 'close' columns")
        
        # Format as series data (same structure as FRED)
        df_stock['date'] = pd.to_datetime(df_stock['date']).dt.strftime("%Y-%m-%d")
        series_data = df_stock[['date', 'close']].rename(columns={'close': 'value'}).to_dict(orient="records")
        
        return {
            "status": "ok",
            "data": {
                "series": series_data,
                "meta": {"id": ticker, "type": "stock"}
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def advance_to_future_date(past_date: str, frequency: str) -> str:
    """
    Advance a past release date to the next future occurrence based on frequency.
    """
    from datetime import datetime, timedelta
    
    try:
        date_dt = datetime.strptime(past_date, "%Y-%m-%d")
    except:
        return None
    
    # Frequency mappings to approximate days
    freq_map = {
        "D": 1,      # Daily
        "W": 7,      # Weekly
        "BW": 14,    # Biweekly
        "M": 30,     # Monthly
        "Q": 90,     # Quarterly
        "SA": 180,   # Semiannual
        "A": 365,    # Annual
    }
    
    days_ahead = freq_map.get(frequency, 30)  # Default to monthly
    today = datetime.now()
    
    # Keep advancing until we get a future date
    while date_dt <= today:
        date_dt += timedelta(days=days_ahead)
    
    return date_dt.strftime("%Y-%m-%d")

@router.get("/macro/series/{series_id}/release")
def get_series_release_info(series_id: str) -> Dict[str, Any]:
    """
    Fetch next release date for a FRED series from cache or FRED API.
    Cache is stored in data/raw/macro/fred_releases.parquet
    """
    import os
    import requests
    
    cache_path = Path("data/raw/macro/fred_releases.parquet")
    fred_api_key = os.getenv("FRED_API_KEY")
    
    if not fred_api_key:
        return {
            "status": "error",
            "message": "FRED API key not configured"
        }
    
    # Try to load from cache first
    next_release = None
    release_name = None
    frequency = None
    
    if cache_path.exists():
        try:
            df_cache = pd.read_parquet(cache_path)
            # Filter for this series
            series_releases = df_cache[df_cache["series_id"] == series_id]
            
            if len(series_releases) > 0:
                latest_row = series_releases.iloc[0]
                next_release = latest_row.get("release_date")
                release_name = latest_row.get("release_name", "")
                frequency = latest_row.get("frequency", "")
                
                # If cached date is in the past, recalculate
                if next_release and frequency:
                    try:
                        release_dt = datetime.strptime(next_release, "%Y-%m-%d")
                        if release_dt <= datetime.now():
                            next_release = advance_to_future_date(next_release, frequency)
                    except:
                        pass
        except Exception as e:
            print(f"Error reading cache: {e}")
    
    # If not in cache, try FRED API for basic metadata
    if not next_release:
        try:
            series_url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={fred_api_key}&file_type=json"
            series_resp = requests.get(series_url, timeout=10)
            
            if series_resp.status_code == 200:
                series_data = series_resp.json()
                
                if "seriess" in series_data and len(series_data["seriess"]) > 0:
                    series_info = series_data["seriess"][0]
                    frequency = series_info.get("frequency_short", "Unknown")
                    release_name = series_info.get("title", "")
        except Exception as e:
            print(f"Error fetching from FRED API: {e}")
    
    return {
        "status": "ok",
        "data": {
            "next_release": next_release,
            "release_name": release_name,
            "frequency": frequency
        }
    }


@router.get("/macro/calendar")
def get_macro_calendar(
    filter: str = "month",  # "today", "week", "month"
    month_offset: int = 0,   # 0 = current month, 1 = next month, -1 = previous month
    only_tracked: bool = False
) -> Dict[str, Any]:
    """
    Fetch economic releases calendar data.
    
    Args:
        filter: Filter type - "today", "week", or "month"
        month_offset: Month offset for pagination (0 = current, 1 = next, -1 = previous)
        only_tracked: If true, return only releases associated with tracked series
    
    Returns:
        Calendar data grouped by date
    """
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    from collections import defaultdict
    
    cache_path = Path("data/raw/macro/fred_calendar.parquet")
    releases_info_path = Path("data/raw/macro/fred_releases.parquet")
    
    if not cache_path.exists():
        raise HTTPException(
            status_code=404, 
            detail="Calendar data not found. Run 'python scripts/fetch_fred_calendar.py' first."
        )
    
    try:
        # Load tracked releases mapping if it exists
        tracked_releases = {}  # release_id -> list of series_ids
        if releases_info_path.exists():
            df_releases = pd.read_parquet(releases_info_path)
            # Group series by release_id
            for _, row in df_releases.iterrows():
                rid = row.get("release_id")
                sid = row.get("series_id")
                if rid and not pd.isna(rid):
                    rid = int(rid)
                    if rid not in tracked_releases:
                        tracked_releases[rid] = []
                    tracked_releases[rid].append(sid)

        # Load cached calendar data
        df = pd.read_parquet(cache_path)
        
        # Calculate date range based on filter and month_offset
        today = datetime.now().date()
        
        if filter == "today":
            start_date = today
            end_date = today
            period_label = f"Today - {today.strftime('%B %d, %Y')}"
            
        elif filter == "week":
            # Current week (Monday to Sunday)
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            period_label = f"This Week - {start_date.strftime('%b %d')} to {end_date.strftime('%b %d, %Y')}"
            
        else:  # month
            # Calculate month with offset
            target_month = today.replace(day=1) + relativedelta(months=month_offset)
            start_date = target_month
            end_date = (target_month + relativedelta(months=1)) - timedelta(days=1)
            period_label = target_month.strftime("%B %Y")
        
        # Filter releases by date range
        df['release_date'] = pd.to_datetime(df['release_date']).dt.date
        mask = (df['release_date'] >= start_date) & (df['release_date'] <= end_date)
        filtered = df[mask].copy()
        
        # Group by date
        releases_by_date = defaultdict(list)
        total_count = 0
        
        for _, row in filtered.iterrows():
            rid = int(row['release_id'])
            is_tracked = rid in tracked_releases
            
            if only_tracked and not is_tracked:
                continue
                
            date_str = row['release_date'].strftime("%Y-%m-%d")
            releases_by_date[date_str].append({
                "release_id": rid,
                "release_name": row['release_name'],
                "time": row['release_time'],
                "is_tracked": is_tracked,
                "series_ids": tracked_releases.get(rid, [])
            })
            total_count += 1
        
        # Sort releases within each date by time
        for date_str in releases_by_date:
            releases_by_date[date_str] = sorted(
                releases_by_date[date_str], 
                key=lambda x: x['time']
            )
        
        # Convert to list format sorted by date
        releases = [
            {
                "date": date_str,
                "releases": releases_by_date[date_str]
            }
            for date_str in sorted(releases_by_date.keys())
        ]
        
        return {
            "status": "ok",
            "data": {
                "releases": releases,
                "period": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d"),
                    "label": period_label
                },
                "total_releases": total_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


