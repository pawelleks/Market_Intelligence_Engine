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
from datetime import datetime, date
import logging
import re
from pathlib import Path
from typing import Optional, List
import os
import gzip
import shutil

# Optional S3 dependencies (only needed for download_day_snapshot)
try:
    import boto3
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    Config = None
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)

class MassiveOptionsLoader:
    """
    Loader for Massive.com Options Flat Files (Day Aggregates).
    Expected CSV Schema includes:
    day, underlying_ticker, option_ticker, open_interest, implied_volatility, gamma, delta, ...
    """

    def __init__(self, data_dir: str = "data/raw/massive/options"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.full_dir = self.data_dir / "full"
        self.full_dir.mkdir(parents=True, exist_ok=True)

    def load_day_aggregates(self, date_str: str, tickers: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Loads the daily aggregate CSV for a specific date.
        
        Args:
            date_str: "YYYY-MM-DD"
            tickers: Optional list of underlying tickers to filter (e.g. ["SPY", "QQQ"])
            
        Returns:
            pd.DataFrame with standardized columns for GEX Engine.
        """
        filename = f"options_{date_str}.csv"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.error(f"Flat file not found: {filepath}")
            return pd.DataFrame()
            
        try:
            # Read CSV
            df = pd.read_csv(filepath)
            
            # Check columns (OHLC vs Greeks)
            # Remote file has: ['ticker', 'volume', 'open', 'close', 'high', 'low', 'window_start', 'transactions']
            if 'ticker' in df.columns and 'underlying_ticker' not in df.columns:
                df = df.rename(columns={'ticker': 'option_ticker'})
                
                # We need to extract underlying_ticker to filter
                # OSI Format: O:SPY251219C... or SPY...
                # Heuristic: Extract alpha prefix
                # Warning: indices like ^SPX vs SPXW might be tricky.
                
                # Optimized Filter for requested tickers
                if tickers:
                     # Create Regex pattern for tickers
                     # Match start of string, optional 'O:', then ticker, then digit
                     # e.g. ^(O:)?SPY\d
                     # CRITICAL: Strip ^ from indices (e.g. ^SPX -> SPX) because OSI doesn't use ^
                     target_list_clean = [t.upper().lstrip('^') for t in tickers]
                     t_list = [re.escape(t) for t in target_list_clean]
                     
                     # Handle Indices mapping if needed (e.g. ^SPX -> SPX in OSI?)
                     # Polygon OSI usually omits ^ for indices? or uses SPXW?
                     # Let's match roughly.
                     pattern = r'^(?:O:)?(' + '|'.join(t_list) + r')\d'
                     
                     df = df[df['option_ticker'].str.match(pattern, na=False)].copy()
                     
                     # Now verify/extract exact underlying
                     # Simple extraction for now: remove 'O:' and take chars until digit
                     df['underlying_ticker'] = df['option_ticker'].str.replace(r'^O:', '', regex=True).str.extract(r'^([A-Z\^]+)')[0]
                     
                else:
                     # Extract for all
                     df['underlying_ticker'] = df['option_ticker'].str.replace(r'^O:', '', regex=True).str.extract(r'^([A-Z\^]+)')[0]

            # Filter by Underlying Ticker (Secondary Check or Primary if logic above changed)
            if tickers and 'underlying_ticker' in df.columns:
                # CRITICAL: Strip ^ from target tickers because extracted file has normalized tickers (e.g. SPX not ^SPX)
                target_tickers = [t.upper().lstrip('^') for t in tickers]
                df = df[df['underlying_ticker'].isin(target_tickers)].copy()
                
            if df.empty:
                logger.warning(f"No data found for tickers {tickers} in {filename}")
                return pd.DataFrame()
                
            # Parse Option Ticker (OSI Format) if separate columns are missing
            if 'expiration' not in df.columns or 'type' not in df.columns or 'strike' not in df.columns:
                df = self._parse_osi_tickers(df)
            
            # Ensure IV column exists (even if empty, for engine compatibility)
            if 'iv' not in df.columns:
                df['iv'] = np.nan
            
            # Ensure proper renaming for engine
            # Engine expects: 'close' (or 'mid'). We have 'close'.
            # Engine expects: 'open_interest'? We have 'volume'? No OI in OHLC usually.
            # But Expected Moves uses PRICE. So 'close' is sufficient.
            
            return df
                
        except Exception as e:
            logger.error(f"Failed to load flat file {filepath}: {e}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to load flat file {filepath}: {e}")
            return pd.DataFrame()

    def _parse_osi_tickers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parses OSI compliant option tickers into expiry, type, and strike.
        Format: TTT...YYMMDD[C/P]SSSSSSSS
        Example: SPY251219C00500000 -> SPY, 2025-12-19, Call, 500.00
        """
        regex = r"([A-Z]+)(\d{6})([CP])(\d{8})"
        
        def parse_row(ticker):
            match = re.search(regex, ticker)
            if match:
                yymmdd = match.group(2)
                type_char = match.group(3) # C or P
                strike_str = match.group(4)
                
                # Expiry
                year = int("20" + yymmdd[:2])
                month = int(yymmdd[2:4])
                day = int(yymmdd[4:6])
                expiry = f"{year}-{month:02d}-{day:02d}"
                
                # Type
                otype = "call" if type_char == 'C' else "put"
                
                # Strike (divide by 1000)
                strike = float(strike_str) / 1000.0
                
                return pd.Series([expiry, otype, strike])
            return pd.Series([None, None, None])
        
        parsed = df['option_ticker'].apply(parse_row)
        parsed.columns = ['expiration', 'type', 'strike']
        
        return pd.concat([df, parsed], axis=1)

    def download_day_snapshot(self, date_str: str, force: bool = False) -> bool:
        """
        Downloads the daily aggregate CSV from Massive S3.
        Args:
            date_str: "YYYY-MM-DD"
            force: If True, overwrite existing file.
        Returns:
            True if successful or file exists, False on failure.
        """
        filename = f"options_{date_str}.csv"
        # Download to 'full/' subdirectory
        filepath = self.full_dir / filename
        
        if filepath.exists() and not force:
            logger.info(f"File {filename} already exists. Skipping download.")
            return True

        # Credentials (Hardcoded per user snippet)
        aws_access_key = os.environ.get("MASSIVE_ACCESS_KEY", 'a6fad976-77aa-4591-ba20-4528b70a05fe')
        aws_secret_key = os.environ.get("MASSIVE_SECRET_KEY", 'keXDhBdz5zuofjHkeiYMznzUiyDerXgu')
        endpoint_url = 'https://files.massive.com'
        bucket_name = 'flatfiles'
        
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            year = dt.strftime("%Y")
            month = dt.strftime("%m")
            
            # S3 Key Format: us_options_opra/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
            # Note: The bucket is 'flatfiles', so the key inside it does NOT start with 'flatfiles/'
            object_key = f"us_options_opra/day_aggs_v1/{year}/{month}/{date_str}.csv.gz"
            local_gz_path = self.full_dir / f"{filename}.gz"
            
            logger.info(f"Downloading {object_key} to {local_gz_path}...")
            
            session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )
            
            s3 = session.client(
                's3',
                endpoint_url=endpoint_url,
                config=Config(signature_version='s3v4'),
            )
            
            s3.download_file(bucket_name, object_key, str(local_gz_path))
            
            # Decompress
            logger.info(f"Decompressing {local_gz_path}...")
            with gzip.open(local_gz_path, 'rb') as f_in:
                with open(filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    
            # Cleanup GZ
            local_gz_path.unlink()
            
            logger.info(f"Successfully downloaded and extracted to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download snapshot for {date_str}: {e}")
            return False

    def extract_and_save_snapshot(self, date_str: str, tickers: List[str]) -> bool:
        """
        Reads the FULL snapshot from 'full/' dir, filters for tickers, 
        and saves the smaller extract to the main data_dir.
        """
        full_path = self.full_dir / f"options_{date_str}.csv"
        target_path = self.data_dir / f"options_{date_str}.parquet"
        
        if not full_path.exists():
            logger.error(f"Full snapshot not found at {full_path}. Cannot extract.")
            return False
            
        try:
            logger.info(f"Extracting data for {len(tickers)} tickers from {full_path}...")
            
            chunks = pd.read_csv(full_path, chunksize=500000)
            
            cleaned_tickers = [t.upper().lstrip('^') for t in tickers]
            # Pattern to match ANY of the tickers
            pattern = r'^(?:O:)?(' + '|'.join(map(re.escape, cleaned_tickers)) + r')\d'
            
            all_filtered = []
            total_rows = 0
            
            for chunk in chunks:
                if 'ticker' in chunk.columns and 'option_ticker' not in chunk.columns:
                    chunk = chunk.rename(columns={'ticker': 'option_ticker'})
                    
                # Filter
                filtered = chunk[chunk['option_ticker'].str.match(pattern, na=False)].copy()
                
                if not filtered.empty:
                    # Extract underlying for compatibility/verification
                    filtered['underlying_ticker'] = filtered['option_ticker'].str.replace(r'^O:', '', regex=True).str.extract(r'^([A-Z\^]+)')[0]
                    
                    # Only keep rows that match our specific list 
                    filtered = filtered[filtered['underlying_ticker'].isin(cleaned_tickers)]
                    
                    if not filtered.empty:
                        all_filtered.append(filtered)
                        total_rows += len(filtered)
            
            if all_filtered:
                final_df = pd.concat(all_filtered, ignore_index=True)
                final_df.to_parquet(target_path, engine='pyarrow', compression='snappy', index=False)
                logger.info(f"Extraction complete. Saved {total_rows} rows to {target_path}")
                return True
            else:
                logger.warning(f"No matching data found for tickers in {full_path}")
                return False
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return False
