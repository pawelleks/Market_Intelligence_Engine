import os
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any, Optional

from mie_lib.utils.paths import RAW_DATA_DIR
import yaml



LOG = logging.getLogger(__name__)

class FredProvider:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED_API_KEY not found in environment variables.")
        
        self.output_dir = RAW_DATA_DIR / "macro" / "fred"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_series(self, series_id: str, start_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch series observations from FRED API.
        Returns DataFrame with 'date' and 'value'.
        If start_date is None, fetches full available history.
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        if start_date:
            params["observation_start"] = start_date

        LOG.info(f"Fetching FRED series: {series_id}...")
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
            
            return df
        
        except httpx.HTTPStatusError as e:
            LOG.error(f"HTTP error fetching {series_id}: {e}")
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
