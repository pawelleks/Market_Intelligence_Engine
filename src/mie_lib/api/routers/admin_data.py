from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import subprocess
import logging
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
    Reads from dataset_registry.json, falling back to direct file scan if registry missing.
    """
    registry_path = META_DIR / "dataset_registry.json"
    data = {}
    
    # 1. Load Registry if available
    if registry_path.exists():
        try:
            data = json.loads(registry_path.read_text())
        except Exception:
            pass # corrupted registry, ignore

    # 2. Add fallback for tickers present in RAW_DIR but not in registry
    # Scan raw dir for *.parquet (OHLC data only)
    try:
         for p in Path("data/raw").glob("*.parquet"):
             ticker = p.stem.upper()
             if ticker not in data:
                 data[ticker] = {
                     "rows": -1, # Unknown without opening
                     "data_range": ["?", "?"],
                     "last_update_timestamp": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                     "source": "raw_scan"
                 }
    except Exception:
         pass

    if not data:
        return {"status": "no_data", "data": []}
        
    try:
        results = []
        for ticker, info in data.items():
            results.append({
                "ticker": ticker,
                "rows": info.get("rows", 0),
                "data_range": info.get("data_range", []),
                "last_update": info.get("last_update_timestamp"),
                "source": info.get("source", "unknown"),
            })
            
        return {"status": "ok", "data": sorted(results, key=lambda x: x['ticker'])}
        
    except Exception as e:
        return {"status": "error", "error": str(e), "data": []}


@router.get("/features")
def get_features_status() -> Dict[str, Any]:
    """
    Returns status of Features data.
    Scans data/features/*.parquet
    """
    if not FEATURES_DIR.exists():
        return {"status": "no_dir", "data": []}

    try:
        results = []
        for p in FEATURES_DIR.glob("*.parquet"):
            ticker = p.stem.upper()
            stat = p.stat()
            results.append({
                "ticker": ticker,
                "has_features": True,
                "size_bytes": stat.st_size,
                "last_updated": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
            
        return {"status": "ok", "data": sorted(results, key=lambda x: x['ticker'])}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}

@router.get("/em")
def get_em_status() -> Dict[str, Any]:
    """
    Returns status of Expected Moves (EM) data.
    Scans data/analytics/options/*_expected_moves.parquet
    """
    if not OPTIONS_DIR.exists():
        return {"status": "no_dir", "data": []}

    try:
        em_files = list(OPTIONS_DIR.glob("*_expected_moves.parquet"))
        results = []
        for p in em_files:
            ticker = p.name.replace("_expected_moves.parquet", "").upper()
            stat = p.stat()
            results.append({
                "ticker": ticker,
                "has_em": True,
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": stat.st_size
            })
            
        return {"status": "ok", "data": sorted(results, key=lambda x: x['ticker'])}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/options")
def get_options_status() -> Dict[str, Any]:
    """
    Returns status of Raw Options data from Massive flat files.
    Scans data/raw/massive/options/*.csv or *.parquet
    """
    massive_opts_dir = Path("data/raw/massive/options")
    
    # Also check for individual CSV files if directory structure differs
    if not massive_opts_dir.exists():
        massive_opts_dir = Path("data/raw/massive")
    
    if not massive_opts_dir.exists():
        return {"status": "no_dir", "message": "Massive options directory not found", "data": []}

    try:
        # Scan for CSV and Parquet files (Massive flat files)
        files = list(massive_opts_dir.glob("*.csv")) + list(massive_opts_dir.glob("*.parquet"))
        
        if not files:
            # Check subdirectories
            files = list(massive_opts_dir.glob("**/*.csv")) + list(massive_opts_dir.glob("**/*.parquet"))
        
        results = []
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:50]:  # Last 50 files
            stat = f.stat()
            results.append({
                "filename": f.name,
                "path": str(f.relative_to(Path("data"))),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024*1024), 2),
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
            
        return {"status": "ok", "count": len(files), "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}

@router.get("/gex")
def get_gex_status() -> Dict[str, Any]:
    """
    Returns status of Gamma Exposure (GEX) data.
    Scans data/analytics/gex/{TICKER}_gex.json
    """
    if not GEX_DIR.exists():
        return {"status": "no_dir", "data": []}
        
    try:
        results = []
        for json_path in GEX_DIR.glob("*_gex.json"):
            ticker = json_path.stem.replace("_gex", "").upper()
            try:
                meta = json.loads(json_path.read_text())
                ts = meta.get("timestamp")
                spot = meta.get("spot_price") or meta.get("last_price")
                
                results.append({
                    "ticker": ticker,
                    "timestamp": ts,
                    "spot_price": spot,
                    "algo": "BlackScholes",
                    "has_profile": True,
                    "profile_date": ts.split("T")[0] if ts else "unknown"
                })
            except Exception:
                 results.append({
                     "ticker": ticker,
                     "has_profile": False,
                     "error": "corrupted_profile"
                 })
                    
        return {"status": "ok", "data": sorted(results, key=lambda x: x['ticker'])}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}

def _run_orchestrator_task():
    """Background task wrapper"""
    logger = logging.getLogger("uvicorn")
    logger.info("API: Triggering orchestrator.sh ...")
    try:
        # Assumes /app/cli/orchestrator.sh exists and we are in /app
        result = subprocess.run(
            ["bash", "cli/orchestrator.sh", "MANUAL"], 
            capture_output=True, 
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Orchestrator Failed: {result.stderr}")
        else:
            logger.info(f"Orchestrator Success: {result.stdout[:200]}...") # Log first 200 chars
    except Exception as e:
        logger.error(f"Orchestrator Exception: {e}")

@router.post("/pipeline/start")
def start_pipeline(background_tasks: BackgroundTasks):
    """
    Triggers the Daily Pipeline (orchestrator.sh) in the background.
    """
    background_tasks.add_task(_run_orchestrator_task)
    return {"status": "ok", "message": "Pipeline started. Check Audit Log for progress."}

@router.get("/pipeline/history")
def get_pipeline_history(limit: int = 10) -> Dict[str, Any]:
    """
    Returns the history of pipeline runs from pipeline_history.jsonl.
    """
    from mie_lib.services.audit_logger import HISTORY_FILE_PATH
    
    if not HISTORY_FILE_PATH.exists():
        return {"status": "ok", "data": []}
        
    try:
        lines = []
        # Read file efficiently (it might be large eventually, but for now just readlines)
        # Use simple readlines for now.
        with open(HISTORY_FILE_PATH, "r") as f:
            lines = f.readlines()
            
        # Parse last N lines
        history = []
        for line in reversed(lines):
            if len(history) >= limit:
                break
            try:
                if line.strip():
                    history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
                
        return {"status": "ok", "data": history}
        
    except Exception as e:
        return {"status": "error", "error": str(e), "data": []}
