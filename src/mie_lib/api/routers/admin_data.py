from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

from mie_lib.api.dependencies import verify_admin
from mie_lib.utils.paths import META_DIR, FEATURES_DIR, OPTIONS_DIR, HMM_DIR
# Using relative imports or known paths for GEX as it's not in paths.py yet
GEX_DIR = Path("data/analytics/gex")

router = APIRouter(
    prefix="/admin/data",
    tags=["admin_data"],
    dependencies=[Depends(verify_admin)]
)

@router.get("/ohlc")
def get_ohlc_status() -> Dict[str, Any]:
    """
    Returns status of OHLC Data Ingestion.
    Reads from dataset_registry.json and checks Features existence.
    """
    registry_path = META_DIR / "dataset_registry.json"
    
    if not registry_path.exists():
        return {"status": "no_registry", "data": []}
        
    try:
        data = json.loads(registry_path.read_text())
        # Convert dict to list
        # registry structure: { "TICKER": { ...metadata... } }
        
        results = []
        for ticker, info in data.items():
            # Check Features status
            feat_path = FEATURES_DIR / f"{ticker}.parquet"
            has_features = feat_path.exists()
            features_updated = None
            if has_features:
                features_updated = datetime.fromtimestamp(feat_path.stat().st_mtime, timezone.utc).isoformat()
            
            results.append({
                "ticker": ticker,
                "rows": info.get("rows", 0),
                "data_range": info.get("data_range", []),
                "last_update": info.get("last_update_timestamp"),
                "source": info.get("source", "unknown"), # New field
                "has_features": has_features,
                "features_updated": features_updated
            })
            
        return {"status": "ok", "data": results}
        
    except Exception as e:
        return {"status": "error", "error": str(e), "data": []}

@router.get("/options")
def get_options_status() -> Dict[str, Any]:
    """
    Returns status of Options and Expected Moves.
    Reads options/latest.json and checks parquet files.
    """
    latest_path = OPTIONS_DIR / "latest.json"
    
    manifest_info = {}
    if latest_path.exists():
        try:
            latest_data = json.loads(latest_path.read_text())
            # latest.json typically has top level keys like "tickers", "last_updated"
            # tickers is a dict of ticker -> data
            # But we want to iterate over all files too.
            
            # Let's list the parquet files in OPTIONS_DIR
            expected_moves_files = list(OPTIONS_DIR.glob("*_expected_moves.parquet"))
            
            # Helper to parse filename
            # SPY_expected_moves.parquet
            
            found_tickers = set()
            
            results = []
            
            for p in expected_moves_files:
                name_parts = p.name.split("_expected_moves.parquet")
                if len(name_parts) > 0:
                    ticker = name_parts[0].upper()
                    found_tickers.add(ticker)
                    
                    last_mod = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()
                    
                    # Check if in latest.json
                    in_latest = False
                    latest_entry_ts = None
                    if latest_data and "tickers" in latest_data and ticker in latest_data["tickers"]:
                        in_latest = True
                        # Maybe extract timestamp from json if available
                        latest_entry_ts = latest_data["last_updated"] # Global timestamp usually
                        
                    results.append({
                        "ticker": ticker,
                        "has_em_history": True,
                        "history_last_mod": last_mod,
                        "in_latest_json": in_latest,
                        "latest_json_ts": latest_entry_ts
                    })
            
            return {"status": "ok", "data": results}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    return {"status": "no_data", "data": []}

@router.get("/gex")
def get_gex_status() -> Dict[str, Any]:
    """
    Returns status of Gamma Exposure (GEX) data.
    Scans data/analytics/gex/*.json
    """
    if not GEX_DIR.exists():
        return {"status": "no_dir", "data": []}
        
    try:
        # Look for *_gex.json metadata files
        meta_files = list(GEX_DIR.glob("*_gex.json"))
        
        results = []
        for p in meta_files:
            # Filename: TICKER_gex.json
            name_parts = p.name.split("_gex.json")
            if len(name_parts) > 0:
                ticker = name_parts[0].upper()
                
                try:
                    meta = json.loads(p.read_text())
                    # Expecting "timestamp", "spot_price", etc.
                    ts = meta.get("timestamp")
                    spot = meta.get("spot_price")
                    algo = meta.get("gex_algo", "unknown")
                    
                    # Check for profile parquet
                    profile_path = p.with_name(f"{ticker}_profile.parquet")
                    has_profile = profile_path.exists()
                    
                    results.append({
                        "ticker": ticker,
                        "timestamp": ts,
                        "spot_price": spot,
                        "algo": algo,
                        "has_profile": has_profile
                    })
                except Exception:
                    # corrupted file or read error
                    results.append({
                        "ticker": ticker,
                        "error": "corrupted_metadata"
                    })
                    
        return {"status": "ok", "data": results}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}
