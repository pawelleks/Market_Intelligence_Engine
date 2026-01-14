"""
Economic Pipeline API Router

Provides endpoints for:
- Monitoring economic data pipeline status
- Manually triggering pipeline runs
- Viewing pipeline logs
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
import sys

from mie_lib.api.dependencies import verify_admin
from mie_lib.db.models import User

LOG = logging.getLogger(__name__)

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
STATUS_FILE = REPO_ROOT / "data" / "pipeline_status" / "economic_pipeline.json"
LOGS_DIR = REPO_ROOT / "logs"
SCRIPT_PATH = REPO_ROOT / "scripts" / "economic_pipeline.py"

router = APIRouter(
    prefix="/admin/data/economic",
    tags=["admin_data", "economic_pipeline"],
    dependencies=[Depends(verify_admin)]
)


def _load_status() -> Dict[str, Any]:
    """Load pipeline status from JSON file."""
    if not STATUS_FILE.exists():
        return {
            "status": "idle",
            "last_run": None,
            "next_run": None,
            "steps": []
        }
    
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        LOG.error(f"Failed to load status file: {e}")
        return {"error": str(e), "status": "unknown"}


@router.get("/status")
async def get_pipeline_status():
    """
    Get current economic pipeline status.
    
    Returns:
        - Pipeline state (running/idle/failed)
        - Last run timestamp
        - Next scheduled run (if applicable)
        - Progress for each step (FRED fetch, model calculations)
        - Output file information
    """
    status = _load_status()
    
    # Calculate next run (2 AM daily)
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=1, minute=0, second=0, microsecond=0)  # 2 AM local = 1 AM UTC
    if now.hour >= 1:
        next_run = next_run.replace(day=next_run.day + 1)
    status["next_run"] = next_run.isoformat()
    
    return {
        "status": "ok",
        "data": status
    }



def _run_pipeline_task():
    """Background task to run the economic pipeline."""
    try:
        LOG.info("Starting economic pipeline (background task)...")
        # Ensure status is set to running even if script is slow to start
        _update_status_file({"status": "running", "last_run": datetime.now(timezone.utc).isoformat()})
        
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        LOG.info(f"Pipeline completed: {result.stdout}")
        
    except subprocess.CalledProcessError as e:
        LOG.error(f"Pipeline failed: {e.stderr}")
        _update_status_file({
            "status": "failed", 
            "error": f"Process failed: {e.stderr[:500]}", 
            "last_run": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        LOG.error(f"Pipeline error: {e}", exc_info=True)
        _update_status_file({
            "status": "failed", 
            "error": str(e),
            "last_run": datetime.now(timezone.utc).isoformat()
        })

def _update_status_file(updates: Dict[str, Any]):
    """Helper to update status file safely."""
    try:
        current = _load_status()
        current.update(updates)
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        LOG.error(f"Failed to update status file: {e}")

@router.post("/start")
async def start_pipeline(
    background_tasks: BackgroundTasks,
    force: bool = False,
    current_user: User = Depends(verify_admin)
):
    """
    Manually trigger the economic pipeline.
    
    Runs in the background and updates the status file as it progresses.
    Use GET /status to monitor progress.
    """
    # Check if already running (unless forced)
    status = _load_status()
    if not force and status.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Please wait for it to complete."
        )
    
    # Queue background task
    background_tasks.add_task(_run_pipeline_task)
    
    return {
        "status": "ok",
        "message": "Economic pipeline started successfully. Monitor progress via GET /status."
    }


@router.get("/logs/{date}")
async def get_pipeline_logs(date: str):
    """
    Retrieve pipeline logs for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        Log file content
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    log_file = LOGS_DIR / f"economic_pipeline_{date}.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found for {date}")
    
    return FileResponse(str(log_file), media_type="text/plain")


@router.get("/logs")
async def list_pipeline_logs():
    """
    List all available pipeline log files.
    
    Returns:
        List of log file names and metadata
    """
    if not LOGS_DIR.exists():
        return {"status": "ok", "data": []}
    
    log_files = sorted(LOGS_DIR.glob("economic_pipeline_*.log"), reverse=True)
    
    logs_info = []
    for log_file in log_files[:30]:  # Last 30 days
        stat = log_file.stat()
        logs_info.append({
            "filename": log_file.name,
            "date": log_file.stem.replace("economic_pipeline_", ""),
            "size_kb": round(stat.st_size / 1024, 2),
            "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        })
    
    return {
        "status": "ok",
        "data": logs_info
    }
