
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from mie_lib.services.job_runner import job_runner
from mie_lib.services.job_tracker import JobTracker

router = APIRouter(prefix="/api/v1/system", tags=["system"])

class JobRequest(BaseModel):
    job_name: str

class StatusResponse(BaseModel):
    running: bool
    logs: str
    available_jobs: list[str]

@router.post("/jobs/{job_name}")
def trigger_job(job_name: str):
    """
    Triggers a background job.
    """
    success = job_runner.run_job(job_name)
    if not success:
        # returns 409 Conflict if busy, or 400 if invalid
        if job_runner.is_running():
             raise HTTPException(status_code=409, detail="A job is already running.")
        else:
             raise HTTPException(status_code=400, detail=f"Invalid job name: {job_name}")
             
    return {"status": "started", "job": job_name}

@router.get("/jobs/status", response_model=StatusResponse)
def get_status(lines: int = 50):
    """
    Returns current running status and recent logs.
    """
    is_running = job_runner.is_running()
    logs = job_runner.get_logs(lines=lines)
    
    return {
        "running": is_running,
        "logs": logs,
        "available_jobs": list(job_runner.JOBS.keys())
    }

@router.get("/status")
def get_system_status():
    """Returns the current status of background jobs (e.g. update-everything progress)."""
    status = JobTracker.get_status()
    if not status:
        return JSONResponse({"status": "idle"})
        
    # Optional logic: if last_updated is too old (>1h), consider it idle/failed
    # For now, just return raw status
    return JSONResponse(status)

@router.get("/config/ticker-groups")
def get_ticker_groups():
    """
    Returns the raw structure of ticker_groups.yml
    """
    import yaml
    from pathlib import Path
    
    # Path relative to project root (assuming running from root)
    config_path = Path("config/ticker_groups.yml")
    
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="ticker_groups.yml not found")
        
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing config: {str(e)}")
