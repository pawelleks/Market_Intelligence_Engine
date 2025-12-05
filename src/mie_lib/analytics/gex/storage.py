import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Directory for GEX persistence
GEX_DATA_DIR = Path("data/analytics/gex")
GEX_DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_gex_paths(ticker: str):
    base = GEX_DATA_DIR / f"{ticker.upper()}_gex"
    return {
        "meta": base.with_suffix(".json"),
        "profile": base.with_name(f"{ticker.upper()}_profile.parquet")
    }

def save_gex_profile(ticker: str, data: Dict) -> None:
    """Saves GEX profile to disk (Profile -> Parquet, Meta -> JSON)."""
    try:
        paths = get_gex_paths(ticker)
        
        # 1. Separate Profile Data
        profile_data = data.get("profile", [])
        
        # 2. Save Metadata (everything except profile)
        meta_data = {k: v for k, v in data.items() if k != "profile"}
        
        with open(paths["meta"], 'w') as f:
            json.dump(meta_data, f, indent=2, default=str)
            
        # 3. Save Profile as Parquet
        if profile_data:
            df = pd.DataFrame(profile_data)
            df.to_parquet(paths["profile"], index=False)
            
        logger.info(f"Saved GEX profile for {ticker} (Meta -> JSON, Profile -> Parquet)")
    except Exception as e:
        logger.error(f"Failed to save GEX profile for {ticker}: {e}")

def load_gex_profile(ticker: str) -> Optional[Dict]:
    """Loads GEX profile from disk (combining JSON meta and Parquet profile)."""
    try:
        paths = get_gex_paths(ticker)
        
        if not paths["meta"].exists():
            return None
            
        # 1. Load Metadata
        with open(paths["meta"], 'r') as f:
            data = json.load(f)
            
        # 2. Load Profile
        if paths["profile"].exists():
            df = pd.read_parquet(paths["profile"])
            data["profile"] = df.to_dict(orient="records")
        else:
            data["profile"] = []
            
        return data
    except Exception as e:
        logger.warning(f"Failed to load GEX profile for {ticker}: {e}")
        return None
