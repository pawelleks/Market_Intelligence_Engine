"""
Core Engine for TSMOM Calculation.
"""
import logging
import pandas as pd
import numpy as np
import uuid
from datetime import date, datetime
from typing import List, Optional, Dict

from mie_lib.analytics.tsmom.storage import save_current_snapshot, append_signal_history
from mie_lib.analytics.tsmom.data_loader import load_ohlc_daily, load_all_tickers_ohlc, DataNotFoundError

LOG = logging.getLogger(__name__)


def calculate_tsmom_for_ticker(ticker: str, df: pd.DataFrame, lookback_days: int = 252) -> pd.DataFrame:
    """
    Computes TSMOM metrics for a single ticker dataframe.
    """
    if df.empty or len(df) <= lookback_days:
        return pd.DataFrame()
    
    # 1. Ret 12M
    # ret_12m(d) = close(d) / close(d - 252) - 1
    df["ret_12m"] = df["price"] / df["price"].shift(lookback_days) - 1
    
    # 2. Monthly Decision Gate
    # Identify Month-End Trading Days using BusinessDay offset
    from pandas.tseries.offsets import BusinessDay
    
    # Check if next business day is in a different month
    # We use the index (DatetimeIndex)
    next_bday_month = (df.index + BusinessDay(1)).month
    df["is_month_end"] = next_bday_month != df.index.month
    
    # Calculate Raw Signal (Daily)
    # 1 if > 0, -1 if < 0, else 0
    raw_signal = np.sign(df["ret_12m"].fillna(0)).astype(int)
    df["theoretical_signal"] = raw_signal
    
    # Apply Gate: Only keep signal on Month Ends
    df["monthly_signal"] = np.nan
    df.loc[df["is_month_end"], "monthly_signal"] = raw_signal.loc[df["is_month_end"]]
    
    # Forward Fill: Hold the month-end signal throughout the next month
    df["tsmom_dir"] = df["monthly_signal"].ffill().fillna(0).astype(int)
    
    # 3. Detect Changes
    # Change if dir != prev_dir AND dir != 0
    
    df["prev_dir"] = df["tsmom_dir"].shift(1).fillna(0).astype(int)
    
    conditions = [
        (df["tsmom_dir"] == 1) & (df["prev_dir"] != 1),
        (df["tsmom_dir"] == -1) & (df["prev_dir"] != -1)
    ]
    choices = ["BUY", "SELL"]
    
    df["signal_event"] = np.select(conditions, choices, default="")
    df["signal_changed"] = df["signal_event"] != ""
    
    return df

def run_tsmom_daily_update(asof_date: Optional[date] = None, lookback_days: int = 252, tickers: List[str] = None, backfill: bool = False):
    """
    Main Orchestrator.
    Args:
        asof_date: Target date for 'current' snapshot (default today).
        lookback_days: TSMOM lookback window.
        tickers: List of tickers (default from config).
        backfill: If True, generate signal events for full history of data. 
                  If False, only check for signal change on the LATEST available data point.
    """
    if asof_date is None:
        asof_date = date.today()
        
    LOG.info(f"Starting TSMOM Update for {asof_date} (Lookback={lookback_days}, Backfill={backfill})")
    
    if not tickers:
        # Load tickers from config
        from mie_lib.data_ingest.yfinance_loader import read_tickers 
        try:
            tickers = read_tickers()
        except:
             pass

    if not tickers:
         LOG.error("No tickers provided or found.")
         return { "status": "error", "message": "No tickers" }

    current_snapshot_rows = []
    new_signals_rows = []
    
    run_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    processed_count = 0
    
    LOG.info(f"Loading data for {len(tickers)} tickers...")
    ohlc_map = load_all_tickers_ohlc(tickers)
    
    # Pre-calculate common dates if needed (though ticker calendars vary)
    from pandas.tseries.offsets import BusinessDay, MonthEnd
    
    for ticker in tickers:
        try:
            df = ohlc_map.get(ticker)
            
            # Default values for placeholder
            # If we don't have data, we use asof_date for the record
            last_date = asof_date
            last_price = 0.0
            last_ret = 0.0
            last_dir = 0
            last_theo = 0
            is_me = False
            next_re = asof_date # Placeholder
            sig_today = "NO_DATA"
            sig_changed = False
            data_st = asof_date
            data_en = asof_date
            rows_n = 0
            
            valid_calc = False
            calc_df = pd.DataFrame()

            if df is not None and not df.empty:
                rows_n = len(df)
                data_st = df.index[0].date()
                data_en = df.index[-1].date()
                last_price = float(df["price"].iloc[-1])
                
                # Try Calculation
                calc_df = calculate_tsmom_for_ticker(ticker, df, lookback_days)
                
                if not calc_df.empty:
                    valid_calc = True
                    last_row = calc_df.iloc[-1]
                    last_date = last_row.name
                    if hasattr(last_date, "date"): last_date = last_date.date()
                    
                    last_ret = float(last_row["ret_12m"])
                    last_dir = int(last_row["tsmom_dir"])
                    last_theo = int(last_row["theoretical_signal"])
                    is_me = bool(last_row["is_month_end"])
                    sig_today = str(last_row["signal_event"])
                    sig_changed = bool(last_row["signal_changed"])
                else:
                    sig_today = "INSUFF_DATA"
            
            # Calculate Next Rebalance (Approximate if valid_calc failed)
            ts_asof = pd.Timestamp(asof_date)
            next_re = (ts_asof + MonthEnd(0)).date()
            if next_re < asof_date: 
                 next_re = (ts_asof + MonthEnd(1)).date()

            # performance since last signal
            last_sig_date = None
            last_sig_price = np.nan
            perf_since = np.nan
            
            if valid_calc:
                # Find rows where signal_changed is True
                sig_events = calc_df[calc_df["signal_changed"] == True]
                if not sig_events.empty:
                    last_evt = sig_events.iloc[-1]
                    last_sig_date = last_evt.name
                    if hasattr(last_sig_date, "date"): last_sig_date = last_sig_date.date()
                    
                    last_sig_price = float(last_evt["price"])
                    
                    entry_price = last_sig_price
                    curr_price = float(last_row["price"])
                    direction = int(last_evt["tsmom_dir"])
                    
                    if entry_price > 0:
                        raw_ret = (curr_price - entry_price) / entry_price
                        perf_since = raw_ret * direction

            # 1. Build Snapshot Row (Always Included)
            snapshot_row = {
                "asof_date": last_date,
                "ticker": ticker,
                "close": last_price,
                "ret_12m": last_ret if valid_calc else None,
                "tsmom_dir": last_dir,
                "theoretical_signal": last_theo,
                "is_rebalance_date": is_me,
                "next_rebalance_date": next_re,
                "last_signal_date": last_sig_date,
                "last_signal_price": float(last_sig_price) if not pd.isna(last_sig_price) else None,
                "perf_since_signal": float(perf_since) if not pd.isna(perf_since) else None,
                "signal_today": sig_today,
                "signal_changed": sig_changed,
                "lookback_days": lookback_days,
                "data_start": data_st,
                "data_end": data_en,
                "rows_used": rows_n
            }
            current_snapshot_rows.append(snapshot_row)
            
            # 2. Signal Events (Only if valid calc)
            if valid_calc:
                events_to_process = []
                if backfill:
                    event_df = calc_df[calc_df["signal_changed"] == True]
                    for idx, row in event_df.iterrows():
                        events_to_process.append((idx, row))
                else:
                    if last_row["signal_changed"]:
                        events_to_process.append((last_row.name, last_row))
                
                for evt_idx, evt_row in events_to_process:
                    evt_date = evt_idx
                    if hasattr(evt_date, "date"): evt_date = evt_date.date()
                        
                    sig_row = {
                        "event_date": evt_date,
                        "ticker": ticker,
                        "signal": str(evt_row["signal_event"]),
                        "close": float(evt_row["price"]),
                        "ret_12m": float(evt_row["ret_12m"]),
                        "tsmom_dir": int(evt_row["tsmom_dir"]),
                        "lookback_days": lookback_days,
                        "run_id": run_id,
                        "created_at": created_at
                    }
                    new_signals_rows.append(sig_row)
                
            processed_count += 1
            
        except Exception as e:
            LOG.error(f"Failed TSMOM calc for {ticker}: {e}")
            continue

    # Persistence
    if current_snapshot_rows:
        snap_df = pd.DataFrame(current_snapshot_rows)
        save_current_snapshot(snap_df)
        
    if new_signals_rows:
        sig_df = pd.DataFrame(new_signals_rows)
        # For backfill, we might generate many duplicates if run repeatedly, but append_signal_history handles dedup.
        append_signal_history(sig_df)
        
    summary = {
        "status": "success",
        "processed": processed_count,
        "signals_generated": len(new_signals_rows),
        "asof_date": str(asof_date),
        "backfill": backfill
    }
    LOG.info(f"TSMOM Update Complete: {summary}")
    return summary
