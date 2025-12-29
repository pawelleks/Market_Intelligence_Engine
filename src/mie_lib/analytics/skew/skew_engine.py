"""
⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
-----------------------------------------------------------
This module adheres to the strict "Split-Source" Data Strategy defined in agent_rules.md

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.

ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.

Any attempt to replace the flat-file ingest with an API call is a violation of project constraints. Fix logic errors only; do not change the data provider.
"""
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import logging
import json
from pathlib import Path

# Import the loader to reuse its logic (or we can use it to fetch data)
# Depending on architecture, we might just instantiate it or read files directly.
# Based on existing patterns, let's reuse valid data paths.
from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader

logger = logging.getLogger(__name__)

class SkewEngine:
    def __init__(self, data_base_dir: str = "data/analytics/skew"):
        self.data_dir = Path(data_base_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.loader = MassiveOptionsLoader()
        self.parquet_path = self.data_dir / "dataset.parquet"

    def _get_underlying_price(self, ticker: str, date_str: str) -> Optional[float]:
        """Fetches closing price from raw OHLC parquet."""
        try:
            path = Path(f"data/raw/{ticker}.parquet")
            if not path.exists():
                return None
            df = pd.read_parquet(path)
            # Ensure date column match
            row = df[df['date'].astype(str) == date_str]
            if not row.empty:
                return float(row.iloc[0]['close'])
        except Exception:
            return None
        return None

    def _generate_commentary(self, pcr_val: float, skew_val: Optional[float]) -> str:
        """Generates simple sentiment commentary."""
        sentiment = []
        if pcr_val > 1.2:
            sentiment.append("Bearish OI Positioning")
        elif pcr_val < 0.7:
             sentiment.append("Bullish OI Positioning")
        else:
             sentiment.append("Neutral OI")

        if skew_val is not None:
            if skew_val > 0.05: # Put IV much higher
                 sentiment.append("High Skew (Fear)")
            elif skew_val < -0.02:
                 sentiment.append("Call Skew (Greed)")
        
        return ", ".join(sentiment)

    def calculate_skew_and_pcr_for_date(self, ticker: str, date_str: str) -> Dict:
        """
        Calculates Skew and PCR metrics (OI & Vol) and saves to Parquet + JSON.
        """
        try:
            # Load Data
            df = self.loader.load_day_aggregates(date_str, tickers=[ticker])
            
            if df.empty:
                logger.warning(f"No options data found for {ticker} on {date_str}")
                return {}

            # Ensure required columns
            # Soft check for volume
            has_volume = 'volume' in df.columns
            
            if 'delta' not in df.columns:
                 logger.warning("Delta column missing in dataframe. Cannot calculate Skew.")
                 return {}

            # --- 1. PCR Calculation ---
            total_call_oi = df[df['type'] == 'call']['oi'].sum()
            total_put_oi = df[df['type'] == 'put']['oi'].sum()
            pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0

            pcr_vol = None
            if has_volume:
                # Fill Nan with 0
                df['volume'] = df['volume'].fillna(0)
                total_call_vol = df[df['type'] == 'call']['volume'].sum()
                total_put_vol = df[df['type'] == 'put']['volume'].sum()
                pcr_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0.0

            # --- 2. Skew Calculation (25-Delta, 30-45 Days) ---
            skew_metrics = {}
            
            today_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            def get_dte(expiry_str):
                try:
                    exp = datetime.strptime(str(expiry_str), "%Y-%m-%d").date()
                    return (exp - today_date).days
                except: return -1

            df['dte'] = df['expiration'].apply(get_dte)
            
            # Filter for 30-45 days (Standard Monthlys approx)
            target_mask = (df['dte'] >= 25) & (df['dte'] <= 45)
            subset = df[target_mask].copy()
            
            skew_25d = None
            if not subset.empty:
                # Find best expiry (closest to 30?)
                # Or just aggregate?
                # Usually Skew is term-specific. Let's take the expiry with most OI?
                # Or just closest to 30 DTE.
                subset['dte_diff'] = abs(subset['dte'] - 30)
                best_expiry = subset.sort_values('dte_diff').iloc[0]['expiration']
                expiry_data = subset[subset['expiration'] == best_expiry]

                iv_call_25 = self._get_iv_at_delta(expiry_data, 'call', 0.25)
                iv_put_25 = self._get_iv_at_delta(expiry_data, 'put', -0.25)
                
                if iv_call_25 and iv_put_25:
                    skew_25d = iv_put_25 - iv_call_25

            # --- 3. Underlying Price ---
            price = self._get_underlying_price(ticker, date_str)

            # --- 4. Commentary ---
            commentary = self._generate_commentary(pcr_oi, skew_25d)

            # Construct Record
            record = {
                "date": date_str,
                "ticker": ticker,
                "pcr_metrics": {
                    "total_oi_pcr": round(pcr_oi, 4),
                    "total_volume_pcr": round(pcr_vol, 4) if pcr_vol is not None else None,
                    "total_call_oi": int(total_call_oi),
                    "total_put_oi": int(total_put_oi)
                },
                "skew_metrics": {
                    "skew_25d_1m": skew_25d, # Roughly 30d
                },
                "underlying_price": price,
                "commentary": commentary,
                "meta": {
                    "data_source": "massive_flat_file_v1",
                    "record_created": datetime.now().isoformat()
                }
            }
            
            # --- 5. Save Parquet (Append/Partition) ---
            self._save_to_parquet(record)

            return record

        except Exception as e:
            logger.error(f"Error calculating Skew/PCR for {ticker} on {date_str}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _save_to_parquet(self, record: Dict):
        """
        Saves record to a partitioned parquet file.
        Strict Idempotency: Overwrites the specific file for Ticker/Date to prevent duplicates.
        Path: data/analytics/skew/dataset/ticker={ticker}/date={date}/data.parquet
        """
        try:
            # Flatten for Parquet
            row = {
                "date": record["date"],
                "ticker": record["ticker"],
                "pcr_vol": record["pcr_metrics"]["total_volume_pcr"],
                "pcr_oi": record["pcr_metrics"]["total_oi_pcr"],
                "skew_25d": record["skew_metrics"]["skew_25d_1m"],
                "underlying_price": record.get("underlying_price"),
                "commentary": record.get("commentary")
            }
            
            df_new = pd.DataFrame([row])
            
            # Manual Hive Partitioning for Idempotency
            # Construct Directory: .../ticker=SPY/date=2025-01-01/
            partition_dir = self.data_dir / "dataset" / f"ticker={record['ticker']}" / f"date={record['date']}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            
            # Deterministic Filename
            file_path = partition_dir / "data.parquet"
            
            # Write (Overwrite if exists)
            # We drop the partition columns from the dataframe itself if using Hive style structure implicitly,
            # BUT usually standard readers expect them? 
            # Actually pyarrow.parquet.read_table(dataset_dir) infers them from directory.
            # So we DROP ticker and date from the written file.
            
            df_to_write = df_new.drop(columns=['ticker', 'date'])
            
            df_to_write.to_parquet(file_path, index=False)
            
        except Exception as e:
            logger.error(f"Failed to save parquet for {record['ticker']}: {e}")

    def _get_iv_at_delta(self, df_expiry: pd.DataFrame, option_type: str, target_delta: float) -> Optional[float]:
        """
        Interpolates IV for a specific target delta.
        """
        try:
            # Filter by type
            subset = df_expiry[df_expiry['type'] == option_type].copy()
            if subset.empty:
                return None
                
            # Drop NaN deltas/IVs
            subset = subset.dropna(subset=['delta', 'iv'])
            if subset.empty:
                return None

            # Sort by Delta
            subset = subset.sort_values('delta')
            
            # Linear Interpolation
            # We want IV where Delta = target_delta
            # Using numpy interp
            # x = delta, y = iv
            
            # Check if target is within range
            min_d, max_d = subset['delta'].min(), subset['delta'].max()
            
            # Relaxed bounds check (extrapolation usually bad for volatility surfaces, but small range ok)
            # If target is slightly outside, clamp? Or return None?
            # Let's return nearest if within small tolerance, else None?
            # Actually np.interp extrapolates by "clamping" to edge values by default (constant extrapolation).
            # For robustness, we'll use it but log if far off? No, keep simple.
            
            iv = np.interp(target_delta, subset['delta'].values, subset['iv'].values)
            return float(iv)

        except Exception:
            return None

    def update_skew_history(self, ticker: str, lookback_days: int = 30):
        """
        Iterates back from today, calculates skew, and updates the historical JSON.
        """
        history_file = self.data_dir / f"{ticker}_skew.json"
        
        # Load existing history
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        # Create valid date set
        processed_dates = {r['date'] for r in history}
        
        # Determine dates to process
        today = date.today()
        dates_to_proc = []
        for i in range(lookback_days):
            d = today - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            
            # Skip if already processed? 
            # Maybe re-process "today" always?
            if d_str in processed_dates and i > 0:
                continue
                
            # Check if raw file exists
            if (self.loader.data_dir / f"options_{d_str}.csv").exists():
                 dates_to_proc.append(d_str)

        # Calculate and Append
        new_records = []
        for d_str in dates_to_proc:
            print(f"Processing Skew for {ticker} on {d_str}...") # Console Feedback
            rec = self.calculate_skew_and_pcr_for_date(ticker, d_str)
            if rec:
                # Remove old record for same date if exists (to update)
                history = [h for h in history if h['date'] != d_str]
                history.append(rec)
                
        # Sort by date
        history.sort(key=lambda x: x['date'])
        
        # Save
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
            
        logger.info(f"Updated Skew history for {ticker}. Total records: {len(history)}")

