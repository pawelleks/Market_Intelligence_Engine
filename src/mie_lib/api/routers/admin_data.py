from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

from mie_lib.api.dependencies import verify_admin
from mie_lib.db.models import User
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
             ticker = p.stem.upper()
             if ticker not in data:
                 rows = -1
                 try:
                     df_scan = pd.read_parquet(p, columns=[]) # Metadata scan only if supported, or read index
                     # Actually PyArrow/FastParquet might optimize columns=[]
                     # If that fails, read one column.
                     rows = pd.read_parquet(p).shape[0] # Fallback to standard read
                 except:
                     pass
                 
                 data[ticker] = {
                     "rows": rows, # Now calculated
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
    """Background task wrapper — streams output to docker logs."""
    logger = logging.getLogger("uvicorn")
    logger.info("API: Triggering orchestrator.sh ...")
    try:
        # Stream stdout/stderr to container logs instead of capturing
        # so pipeline [RUN]/[SKIP]/✅/❌ markers are visible in `docker logs`
        result = subprocess.run(
            ["bash", "cli/orchestrator.sh", "MANUAL"],
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Orchestrator finished with exit code {result.returncode}")
        else:
            logger.info("Orchestrator finished successfully.")
    except Exception as e:
        logger.error(f"Orchestrator Exception: {e}")

@router.post("/pipeline/start")
def start_pipeline(
    background_tasks: BackgroundTasks,
    force: bool = False
):
    """
    Triggers the Daily Pipeline (orchestrator.sh) in the background.
    """
    # Check if already running
    from mie_lib.services.audit_logger import get_audit_logger
    audit = get_audit_logger()
    if audit.data.get("status") == "RUNNING" and not force:
        raise HTTPException(
            status_code=409, 
            detail="Pipeline is already running. Use force=true to restart."
        )

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

# -----------------------------------------------------------------
# FRED / Macro Data Endpoints
# -----------------------------------------------------------------
import yaml

@router.get("/fred")
def get_fred_status() -> Dict[str, Any]:
    """Returns status of FRED data series."""
    config_path = Path("config") / "macro_series.yml"
    fred_dir = Path("data/raw/macro/fred")
    
    if not config_path.exists():
        return {"status": "error", "message": "FRED config missing", "data": []}
        
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        series_map = cfg.get("series", {})
        
        results = []
        for series_id, description in series_map.items():
            file_path = fred_dir / f"{series_id}.parquet"
            if file_path.exists():
                stat = file_path.stat()
                status = "ok"
                try:
                    # Read date column to find range
                    # Should be fast for macro data
                    df = pd.read_parquet(file_path, columns=["date"])
                    if not df.empty:
                        min_date = df["date"].min().strftime("%Y-%m-%d")
                        max_date = df["date"].max().strftime("%Y-%m-%d")
                        date_range = f"{min_date} to {max_date}"
                    else:
                        date_range = "empty"
                except Exception:
                    date_range = "error"

                last_updated = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                size = stat.st_size
            else:
                status = "missing"
                last_updated = None
                size = 0
                date_range = "-"
                
            results.append({
                "series_id": series_id,
                "description": description,
                "status": status,
                "last_updated": last_updated,
                "size_bytes": size,
                "date_range": date_range
            })
            
        return {"status": "ok", "data": sorted(results, key=lambda x: x['series_id'])}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}

def _run_fred_update_task():
    """Background task for FRED update."""
    logger = logging.getLogger("uvicorn")
    logger.info("API: Triggering FRED update...")
    try:
        from mie_lib.data_ingest.macro.providers.fred import update_fred_data
        update_fred_data()
        logger.info("FRED update completed.")
    except Exception as e:
        logger.error(f"FRED update failed: {e}")

@router.post("/fred/start")
def trigger_fred_update(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_admin)
):
    """Triggers the FRED data update pipeline in the background."""
    background_tasks.add_task(_run_fred_update_task)
    return {"status": "ok", "message": "FRED pipeline triggered in background"}

@router.get("/ai-context")
def get_ai_context() -> Dict[str, Any]:
    """Returns the latest AI context JSON."""
    context_path = Path("data/ai_context/spy_latest.json")
    if not context_path.exists():
        return {"status": "error", "message": "No context found"}
        
    try:
        data = json.loads(context_path.read_text())
        return {"status": "ok", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -----------------------------------------------------------------
# Computed Content / Reports
# -----------------------------------------------------------------

@router.get("/reports")
def list_reports() -> Dict[str, Any]:
    """List available AI reports (latest and archive)."""
    reports_dir = Path("data/reports")
    archive_dir = reports_dir / "archive"
    
    results = []
    
    # Latest
    latest_file = reports_dir / "daily_report_latest.json"
    if latest_file.exists():
        stat = latest_file.stat()
        results.append({
            "filename": latest_file.name,
            "path": "latest", # Logical path
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "type": "latest"
        })
        
    # Archive
    if archive_dir.exists():
        for f in archive_dir.glob("*.json"):
            stat = f.stat()
            results.append({
                "filename": f.name,
                "path": f"archive/{f.name}",
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "type": "archive"
            })
            
    return {"status": "ok", "data": sorted(results, key=lambda x: x['modified'], reverse=True)}

@router.get("/reports/{filename}")
def download_report(filename: str, current_user: User = Depends(verify_admin)):
    """Download a report file."""
    reports_dir = Path("data/reports")
    archive_dir = reports_dir / "archive"
    
    # Security check: filename should be just the name, no slashes (except 'archive/' prefix if we handle it that way?)
    # Actually, let's look for file in both places.
    
    # Try latest
    if filename == "daily_report_latest.json":
        file_path = reports_dir / filename
    else:
        # Check archive
        file_path = archive_dir / filename
        
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
        
    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type="application/json", filename=filename)


@router.get("/economic/insights-status")
def get_economic_insights_status() -> Dict[str, Any]:
    """
    Get status of AI insights for all 10 JPM indicators
    Shows which insights exist, when generated, file sizes
    """
    import os
    
    INSIGHTS_DIR = Path("/app/data/reports/economic")
    
    indicators = [
        'gdp', 'consumer-spending', 'labor-market', 'interest-rates',
        'inflation', 'business-confidence', 'stock-market', 
        'trade-balance', 'housing', 'policy'
    ]
    
    status_data = []
    
    for indicator_id in indicators:
        tier1_file = INSIGHTS_DIR / f"{indicator_id}_tier1_latest.json"
        tier2_file = INSIGHTS_DIR / f"{indicator_id}_tier2_latest.json"
        tier3_file = INSIGHTS_DIR / f"{indicator_id}_tier3_latest.json"
        
        tier1_status = "✅ Generated" if tier1_file.exists() else "❌ Missing"
        tier2_status = "✅ Generated" if tier2_file.exists() else "❌ Missing"
        tier3_status = "✅ Generated" if tier3_file.exists() else "⏳ On-demand"
        
        # Get timestamps
        tier1_time = None
        tier2_time = None
        
        if tier1_file.exists():
            try:
                with open(tier1_file, 'r') as f:
                    data = json.load(f)
                    tier1_time = data.get('generated_at', 'Unknown')
            except:
                pass
        
        if tier2_file.exists():
            try:
                with open(tier2_file, 'r') as f:
                    data = json.load(f)
                    tier2_time = data.get('generated_at', 'Unknown')
            except:
                pass
        
        status_data.append({
            'indicator_id': indicator_id,
            'indicator_name': indicator_id.replace('-', ' ').title(),
            'tier1': {
                'status': tier1_status,
                'generated_at': tier1_time,
                'file_size': os.path.getsize(tier1_file) if tier1_file.exists() else 0
            },
            'tier2': {
                'status': tier2_status,
                'generated_at': tier2_time,
                'file_size': os.path.getsize(tier2_file) if tier2_file.exists() else 0
            },
            'tier3': {
                'status': tier3_status
            }
        })
    
    return {
        'total_indicators': len(indicators),
        'tier1_complete': sum(1 for s in status_data if s['tier1']['status'] == "✅ Generated"),
        'tier2_complete': sum(1 for s in status_data if s['tier2']['status'] == "✅ Generated"),
        'insights_directory': str(INSIGHTS_DIR),
        'indicators': status_data
    }

