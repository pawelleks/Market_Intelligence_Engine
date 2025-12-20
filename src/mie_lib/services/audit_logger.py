import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

AUDIT_FILE_PATH = Path("data/system/audit/pipeline_latest.json")
HISTORY_FILE_PATH = Path("data/system/audit/pipeline_history.jsonl")

class AuditLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditLogger, cls).__new__(cls)
            cls._instance._ensure_dir()
            # Try to load existing state to support multi-process pipeline jobs
            if AUDIT_FILE_PATH.exists():
                try:
                    with open(AUDIT_FILE_PATH, 'r') as f:
                        cls._instance.data = json.load(f)
                except Exception:
                    cls._instance._reset_data()
            else:
                cls._instance._reset_data()
        return cls._instance

    def _reset_data(self):
        self.data = {
            "job_name": "Unknown",
            "start_time": None,
            "end_time": None,
            "status": "IDLE",  # RUNNING, COMPLETED, FAILED
            "run_type": "MANUAL", # or CRON
            "stages": {}
        }

    def _ensure_dir(self):
        AUDIT_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    def start_job(self, job_name: str, run_type: str = "MANUAL"):
        self.data = {
            "job_name": job_name,
            "run_type": run_type,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "RUNNING",
            "stages": {}
        }
        self._save()

    def start_stage(self, stage_name: str):
        self.data["stages"][stage_name] = {
            "status": "RUNNING",
            "start_time": datetime.now().isoformat(),
            "details": {}
        }
        self._save()

    def update_stage(self, stage_name: str, status: str, details: Dict[str, Any]):
        if stage_name not in self.data["stages"]:
            self.start_stage(stage_name)
        
        stage = self.data["stages"][stage_name]
        stage["status"] = status
        if details:
            stage["details"].update(details)
        if status in ["COMPLETED", "FAILED", "SKIPPED"]:
             stage["end_time"] = datetime.now().isoformat()
        
        self._save()

    def finish_job(self, status: str = "COMPLETED", error: str = None):
        self.data["status"] = status
        self.data["end_time"] = datetime.now().isoformat()
        if error:
            self.data["error"] = error
        self._save()
        self._append_history()

    def _append_history(self):
        try:
            # Append current state as a single line JSON
            with open(HISTORY_FILE_PATH, "a") as f:
                f.write(json.dumps(self.data) + "\n")
        except Exception as e:
            print(f"FAILED TO APPEND HISTORY: {e}")

    def _save(self):
        try:
            with open(AUDIT_FILE_PATH, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"FAILED TO SAVE AUDIT LOG: {e}")

# Global instance accessor
_audit_logger = AuditLogger()

def get_audit_logger():
    return _audit_logger
