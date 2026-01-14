import os
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any, Optional
import time

from mie_lib.utils.paths import RAW_DATA_DIR
import yaml



LOG = logging.getLogger(__name__)

class FredProvider:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    TRANSFORMATIONS = {
        "ICSA": lambda x: x * -1  # Invert Claims: higher (less negative) is better
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED_API_KEY not found in environment variables.")
        
        self.output_dir = RAW_DATA_DIR / "macro" / "fred"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_series(self, series_id: str, start_date: Optional[str] = "1970-01-01") -> pd.DataFrame:
        """
        Fetch series observations from FRED API.
        Returns DataFrame with 'date' and 'value'.
        If start_date is None, fetches full available history.
        Defaults to 1970-01-01 for Business Cycle Model consistency.
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        if start_date:
            params["observation_start"] = start_date

        LOG.info(f"Fetching FRED series: {series_id} (from {start_date})...")
        try:
            response = httpx.get(self.BASE_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            observations = data.get("observations", [])
            if not observations:
                LOG.warning(f"No observations found for {series_id}")
                return pd.DataFrame()

            df = pd.DataFrame(observations)
            # Filter and clean
            df = df[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"])
            # Handle '.' as NaN (FRED uses '.' for missing values)
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)

            # Apply transformations
            if series_id in self.TRANSFORMATIONS:
                LOG.info(f"Applying transformation to {series_id}...")
                df["value"] = self.TRANSFORMATIONS[series_id](df["value"])
            
            # Rate limiting: Add 0.5 second delay to avoid hitting FRED API limits
            time.sleep(0.5)
            
            return df
        
        except httpx.HTTPStatusError as e:
            LOG.error(f"HTTP error fetching {series_id}: {e}")
            # Add delay even on errors to avoid hammering the API
            time.sleep(1.0)
            raise
        except Exception as e:
            LOG.error(f"Error fetching {series_id}: {e}")
            raise

    def save_series(self, series_id: str, df: pd.DataFrame):
        """Save dataframe to Parquet."""
        if df.empty:
            return
            
        file_path = self.output_dir / f"{series_id}.parquet"
        df.to_parquet(file_path, index=False)
        LOG.info(f"Saved {series_id} to {file_path}")

    def get_last_date(self, series_id: str) -> Optional[datetime]:
        """Get the last date in existing parquet file."""
        file_path = self.output_dir / f"{series_id}.parquet"
        if not file_path.exists():
            return None
        
        try:
            df = pd.read_parquet(file_path)
            if df.empty or 'date' not in df.columns:
                return None
            return pd.to_datetime(df['date']).max()
        except Exception as e:
            LOG.warning(f"Could not read existing {series_id}: {e}")
            return None

    def fetch_series_incremental(self, series_id: str, min_start_date: str = "1960-01-01") -> pd.DataFrame:
        """
        Fetch series with incremental update logic.
        
        Args:
            series_id: FRED series ID
            min_start_date: Minimum acceptable start date for historical data (default: 1960)
        
        Returns:
            pd.DataFrame: Updated complete series data
        """
        last_date = self.get_last_date(series_id)
        file_path = self.output_dir / f"{series_id}.parquet"
        
        if last_date is None:
            # No existing data - fetch full history
            LOG.info(f"{series_id}: No existing data, fetching full history from {min_start_date}")
            return self.fetch_series(series_id, start_date=min_start_date)
        
        # Calculate dates
        next_date = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if update is needed
        if next_date >= today:
            LOG.info(f"{series_id}: Already up to date (last: {last_date.strftime('%Y-%m-%d')})")
            return pd.read_parquet(file_path)
        
        # Fetch only new data
        LOG.info(f"{series_id}: Fetching incremental data from {next_date}")
        new_data = self.fetch_series(series_id, start_date=next_date)
        
        if new_data.empty:
            LOG.info(f"{series_id}: No new data available")
            return pd.read_parquet(file_path)
        
        # Load existing and merge
        existing_data = pd.read_parquet(file_path)
        combined = pd.concat([existing_data, new_data], ignore_index=True)
        
        # Remove duplicates and sort
        combined = combined.drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
        
        LOG.info(f"{series_id}: Added {len(new_data)} new observations (total: {len(combined)})")
        return combined

    def verify_historical_coverage(self, series_id: str, required_start_year: int = 1970) -> tuple[bool, str]:
        """
        Verify that historical data meets minimum requirements.
        
        Args:
            series_id: FRED series ID
            required_start_year: Minimum year that data should start from
        
        Returns:
            tuple: (is_valid, message)
        """
        file_path = self.output_dir / f"{series_id}.parquet"
        
        if not file_path.exists():
            return False, f"File does not exist"
        
        try:
            df = pd.read_parquet(file_path)
            if df.empty:
                return False, "Empty dataset"
            
            start_date = pd.to_datetime(df['date']).min()
            end_date = pd.to_datetime(df['date']).max()
            obs_count = len(df)
            
            # Check if data starts early enough
            if start_date.year > required_start_year:
                return False, f"Data starts {start_date.year}, required ≤ {required_start_year}"
            
            # Check if data is recent (within last 60 days)
            days_old = (datetime.now() - end_date).days
            if days_old > 60:
                return False, f"Data is {days_old} days old"
            
            # Basic validation passed
            return True, f"OK: {obs_count} obs, {start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def run_bulk_download(self):
        """Load series from config and download all."""
        config_path = Path("config") / "macro_series.yml"
        if not config_path.exists():
            LOG.error(f"Config not found: {config_path}")
            return
        
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        series_map = cfg.get("series", {})
        
        success_count = 0
        for series_id in series_map.keys():
            try:
                df = self.fetch_series(series_id)
                if not df.empty:
                    self.save_series(series_id, df)
                    success_count += 1
            except Exception as e:
                LOG.error(f"Failed to process {series_id}: {e}")
        
        LOG.info(f"FRED Download Complete: {success_count}/{len(series_map)} series processed.")

def update_fred_data():
    """Entry point for shared usage."""
    try:
        provider = FredProvider()
        provider.run_bulk_download()
    except ValueError as e:
        LOG.error(f"Configuration Error: {e}")
    except Exception as e:
        LOG.exception(f"Unexpected Error in FRED update: {e}")
