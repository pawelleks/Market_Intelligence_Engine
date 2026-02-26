"""
python scripts/backfill_volume_regime.py
Optional args: --tickers SPY QQQ --timeframes 1d 1h (to run partial backfill)

Backfills historical Volume Regime signals into data/volume_regime_signals.db.
Fetches data from Thetadata in chunks to avoid timeouts, computes metrics for 
all candles, and uses bulk_insert to quickly write history. Resumes where it left off.
"""
import asyncio
import argparse
import time
import httpx
import logging
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mie_lib.analysis.volume_regime import compute_volume_metrics, classify_market_state
from src.mie_lib.api.routers.volume_regime_router import TIMEFRAMES, THETA_HOST, THETA_PORT
from src.mie_lib.db.volume_regime_db import bulk_insert, get_latest_candle_time, init_db

# Set up simple logging for the script
logging.basicConfig(level=logging.INFO, format='%(message)s')
LOG = logging.getLogger(__name__)

# Defaults
DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "AAPL", "TSLA"]
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

TIMEFRAME_DAYS_BACK = {
    "1m": 30,
    "5m": 30,
    "15m": 30,
    "1h": 30,
    "4h": 30,
    "1d": 365
}

# In terms of days, roughly 500 candles chunks:
# 1m (390/day) -> 1 day per chunk
# 5m (78/day)  -> 6 days per chunk
# 15m (26/day) -> 15 days per chunk
# 1h (7/day)   -> 60 days per chunk
# 4h (2/day)   -> 200 days per chunk
# 1d (1/day)   -> 500 days per chunk
CHUNK_DAYS = {
    "1m": 1,
    "5m": 6,
    "15m": 15,
    "1h": 60,
    "4h": 200,
    "1d": 30
}

async def fetch_chunk(client: httpx.AsyncClient, ticker: str, ivl: int, start_date_str: str, end_date_str: str) -> pd.DataFrame:
    """Fetch a specific date window from Thetadata and parse to DataFrame.

    Uses /v2/hist/stock/eod for daily data (ivl=86400000) since ThetaData's
    /ohlc endpoint doesn't support the daily interval. All intraday intervals
    use /v2/hist/stock/ohlc as before.
    """
    is_daily = (ivl == 86400000)

    if is_daily:
        url = f"http://{THETA_HOST}:{THETA_PORT}/v2/hist/stock/eod"
        params = {
            "root": ticker.upper(),
            "start_date": start_date_str,
            "end_date": end_date_str,
        }
    else:
        url = f"http://{THETA_HOST}:{THETA_PORT}/v2/hist/stock/ohlc"
        params = {
            "root": ticker.upper(),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "ivl": str(ivl)
        }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.get(url, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.RequestError as e:
            LOG.error(f"      Request failed {start_date_str}-{end_date_str} (Attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(5)
            else:
                return pd.DataFrame()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (472, 476):
                # 472/476 means no data (e.g. weekends/holidays). Not an error, just empty.
                return pd.DataFrame()
            LOG.error(f"      HTTP error {e.response.status_code} {start_date_str}-{end_date_str} (Attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(5)
            else:
                return pd.DataFrame()
        except Exception as e:
            LOG.error(f"      Unexpected error {start_date_str}-{end_date_str} (Attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(5)
            else:
                return pd.DataFrame()

    rows = data.get("response", [])
    if not rows:
        return pd.DataFrame()

    # Parse header to find column indices dynamically
    header = data.get("header", {}).get("format", [])

    et_tz = pytz.timezone("America/New_York")
    records = []

    if is_daily:
        # EOD format: [ms_of_day, ms_of_day2, open, high, low, close, volume, count, ..., date]
        # Find indices from header
        try:
            idx_open = header.index("open")
            idx_high = header.index("high")
            idx_low = header.index("low")
            idx_close = header.index("close")
            idx_vol = header.index("volume")
            idx_date = header.index("date")
        except ValueError as e:
            LOG.error(f"      EOD header missing expected field: {e}. Header: {header}")
            return pd.DataFrame()

        for r in rows:
            dt_int = r[idx_date]
            dt_str = str(dt_int)
            if len(dt_str) != 8:
                continue
            try:
                day = datetime(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
            except ValueError:
                continue

            # EOD candles get timestamp at market close (16:00 ET)
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
        # Intraday OHLC format: [ms_of_day, open, high, low, close, volume, count, date]
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

    return pd.DataFrame(records)

async def run_backfill(tickers: list, timeframes: list):
    init_db()
    from zoneinfo import ZoneInfo
    et_tz = ZoneInfo("America/New_York")
    
    # Base our "now" entirely on the current *date* to avoid floating intraday edge cases 
    # going forward past today's actual calendar date.
    now = datetime.now(et_tz)
    end_date_naive = now.date()
    end_dt = datetime.combine(end_date_naive, datetime.min.time(), tzinfo=et_tz)
    
    summary = []
    
    print("\nStarting Volume Regime Backfill...")
    print("==================================\n")
    
    try:
        async with httpx.AsyncClient() as client:
            for ticker in tickers:
                for tf in timeframes:
                    if tf not in TIMEFRAMES:
                        continue
                        
                    start_time = time.time()
                    ivl = TIMEFRAMES[tf]
                    total_days_back = TIMEFRAME_DAYS_BACK.get(tf, 30)
                    chunk_step = CHUNK_DAYS.get(tf, 1)
                    
                    latest_stored_time = get_latest_candle_time(ticker, tf)
                    
                    # Calculate fixed start dt using timedelta
                    target_start_dt = end_dt - timedelta(days=total_days_back)
                    
                    if latest_stored_time:
                        latest_dt = datetime.fromtimestamp(latest_stored_time, tz=et_tz)
                        # We resume slightly before the latest point to allow the 20-period moving average to season before we calculate new signals
                        # 25 candles is enough.
                        resume_dt = latest_dt - timedelta(days=10) # Overkill but safe buffer.
                        if resume_dt > target_start_dt:
                            target_start_dt = resume_dt
                            LOG.info(f"[{ticker} {tf}] Resuming from {latest_dt.strftime('%Y-%m-%d')} (fetching from {resume_dt.strftime('%Y-%m-%d')} for indicator seasoning)")
                        else:
                            LOG.info(f"[{ticker} {tf}] Full backfill taking precedence over older partial data")
                    else:
                        LOG.info(f"[{ticker} {tf}] No existing data. Starting fresh {total_days_back} days back.")
                        
                    df_list = []
                    curr_start = target_start_dt
                    
                    # Fetch in chunks going forward to now
                    while curr_start < end_dt:
                        curr_end = min(curr_start + timedelta(days=chunk_step), end_dt)
                        
                        start_str = curr_start.strftime("%Y%m%d")
                        end_str = curr_end.strftime("%Y%m%d")
                        
                        chunk_df = await fetch_chunk(client, ticker, ivl, start_str, end_str)
                        if not chunk_df.empty:
                            df_list.append(chunk_df)
                            
                        curr_start = curr_end
                        await asyncio.sleep(0.2) # 200ms rate limit respect
                        
                    if not df_list:
                        LOG.info(f"[{ticker} {tf}] No data returned from Thetadata.")
                        summary.append((ticker, tf, 0, "No data", round(time.time() - start_time, 2)))
                        continue
                        
                    # Combine all fetched chunks and deduplicate
                    full_df = pd.concat(df_list, ignore_index=True)
                    full_df = full_df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
                    
                    if len(full_df) < 20:
                        LOG.info(f"[{ticker} {tf}] Only {len(full_df)} candles fetched, skipping metrics.")
                        summary.append((ticker, tf, 0, "Too few candles", round(time.time() - start_time, 2)))
                        continue
                        
                    # We compute metrics for the FULL concatenated dataset
                    full_df = compute_volume_metrics(full_df)
                    
                    signals = []
                    write_count = 0
                    
                    for idx, row in full_df.iterrows():
                        # Skip early unseasoned rows where vol_mean is NaN
                        if pd.isna(row.get("vol_mean_20d")) or pd.isna(row.get("ud_vol_ratio")):
                            continue
                            
                        candle_time = int(row["time"])
                        
                        # Only generate new signals if they are newer than what is already stored
                        if latest_stored_time and candle_time <= latest_stored_time:
                            continue
                            
                        state = classify_market_state(row)
                        vol_mean = row.get("vol_mean_20d", 1)
                        if pd.isna(vol_mean) or vol_mean == 0:
                            vol_mean = 1
                            
                        signals.append({
                            "ticker": ticker,
                            "timeframe": tf,
                            "candle_time": candle_time,
                            "recorded_at": int(time.time()),
                            "state": state,
                            "ud_vol_ratio": float(row.get("ud_vol_ratio", 1.0)),
                            "price_change_20d": float(row.get("price_change_20d", 0)),
                            "volume_vs_avg": float(row.get("volume", 0) / vol_mean),
                            "current_price": float(row.get("close", 0))
                        })
                        
                    if signals:
                        bulk_insert(signals)
                        write_count = len(signals)
                    
                    dur = round(time.time() - start_time, 2)
                    date_rng = f"{target_start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
                    
                    LOG.info(f"{ticker} {tf}: {write_count} signals written in {dur}s")
                    summary.append((ticker, tf, write_count, date_rng, dur))
                    
    finally:
        print("\n==================================")
        print("BACKFILL SUMMARY")
        print(f"{'Ticker':<8} | {'TF':<5} | {'Signals Written':<15} | {'Date Range':<28} | {'Duration (s)'}")
        print("-" * 75)
        for s in summary:
            print(f"{s[0]:<8} | {s[1]:<5} | {s[2]:<15} | {s[3]:<28} | {s[4]:.2f}")
        print("==================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Volume Regime Signals")
    parser.add_argument("--tickers", nargs='+', default=DEFAULT_TICKERS, help="Tickers to run e.g. SPY QQQ")
    parser.add_argument("--timeframes", nargs='+', default=DEFAULT_TIMEFRAMES, help="Timeframes to run e.g. 1d 1h")
    
    args = parser.parse_args()
    
    # Run the backfill async event loop
    asyncio.run(run_backfill(tickers=args.tickers, timeframes=args.timeframes))
