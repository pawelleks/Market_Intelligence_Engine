
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Path to the status file. 
# We assume this runs in the container where CWD is /app or we use relative paths from project root.
# For safety, we'll try to resolve it relative to this file or use a fixed path if we know the env.
# In MIE context, data/ is usually at the project root.

def _get_status_file_path() -> Path:
    # Try to find the 'data' directory. 
    # This file is in src/mie_lib/services/
    # Project root is ../../../
    current = Path(__file__).resolve()
    project_root = current.parents[3]
    return project_root / "data" / "job_status.json"

class JobTracker:
    def __init__(self, job_name: str = "unknown"):
        self.job_name = job_name
        self.status_file = _get_status_file_path()
        
    def _write(self, data: Dict[str, Any]):
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.status_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[JobTracker] Warning: Failed to write status file: {e}")

    def start_job(self, name: str, total_steps: int):
        self.job_name = name
        data = {
            "job_id": name.lower().replace(" ", "_"),
            "status": "running",
            "current_step": 0,
            "total_steps": total_steps,
            "step_name": "Initializing...",
            "progress_percent": 0,
            "start_time": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat()
        }
        self._write(data)

    def update_progress(self, step: int, step_name: str):
        # Read existing to keep start_time (optional, but cleaner to just overwrite with cached self vars if we had them)
        # For simplicity, we just overwrite, keeping it stateless.
        # But we need total_steps. Ideally we read it or pass it. 
        # Let's read it to preserve job_id/start_time.
        current_data = self.get_status()
        
        if not current_data or current_data.get("status") != "running":
            # If no running job, maybe we shouldn't update? Or just force it.
            # Let's assume we are the owner.
            total_steps = 10 # Default fallback
        else:
            total_steps = current_data.get("total_steps", 10)
            
        timestamp = datetime.utcnow().isoformat()
        
        # Calculate pct
        pct = int((step / total_steps) * 100) if total_steps > 0 else 0
        
        data = current_data or {}
        data.update({
            "status": "running",
            "current_step": step,
            "step_name": step_name,
            "progress_percent": pct,
            "last_updated": timestamp
        })
        self._write(data)

    def finish_job(self, status: str = "completed", message: str = "Done"):
        current_data = self.get_status() or {}
        timestamp = datetime.utcnow().isoformat()
        
        current_data.update({
            "status": status,
            "current_step": current_data.get("total_steps", 1),
            "step_name": message,
            "progress_percent": 100,
            "end_time": timestamp,
            "last_updated": timestamp
        })
        self._write(current_data)

    @staticmethod
    def get_status() -> Optional[Dict[str, Any]]:
        path = _get_status_file_path()
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None
