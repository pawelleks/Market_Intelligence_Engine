import subprocess
import logging
import threading
from pathlib import Path
from datetime import date
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class JobRunner:
    """
    Manages execution of background CLI jobs and log monitoring.
    """
    
    # Allowed jobs mapping to commands
    # We execute them relative to project root. 
    # In Docker API container, root is /app, so 'cli/orchestrator.sh' works if cwd=/app.
    JOBS = {
        "daily-pipeline": ["bash", "cli/orchestrator.sh"],
        "update-raw": ["python", "cli/mie.py", "update-raw"],
        "fetch-options": ["python", "cli/mie.py", "fetch-options-snapshot"],
        "build-features": ["python", "cli/mie.py", "build-features", "--mode", "update"],
        "rebuild-features": ["python", "cli/mie.py", "build-features", "--mode", "full"],
        "build-gex": ["python", "cli/mie.py", "build-gex-daily", "--date", "today"], # 'today' needs handling or pass actual date
        "update-expected-moves": ["python", "cli/mie.py", "build-expected-moves", "--ticker", "@config", "--start", "today"]
    }

    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        
    def _get_log_path(self, run_date: Optional[date] = None) -> Path:
        if run_date is None:
            run_date = date.today()
        # Orchestrator writes to pipeline_YYYY-MM-DD.log
        # But individual commands might write to stdout/stderr.
        # We should redirect their output to the same log file for consistency in this UI.
        return self.log_dir / f"pipeline_{run_date}.log"

    def run_job(self, job_name: str) -> bool:
        """
        Starts a job if no other job is running.
        Returns True if started, False if busy or invalid job.
        """
        if job_name not in self.JOBS:
            logger.error(f"Invalid job name: {job_name}")
            return False

        with self.lock:
            # Check if current process is alive
            if self.current_process and self.current_process.poll() is None:
                logger.warning(f"Job already running. Cannot start {job_name}")
                return False
            
            cmd = self.JOBS[job_name].copy()
            
            # Handle 'today' replacement
            today_str = date.today().strftime("%Y-%m-%d")
            cmd = [arg.replace("today", today_str) for arg in cmd]
            
            log_path = self._get_log_path()
            
            try:
                # Open log file for appending
                with open(log_path, "a") as f:
                    f.write(f"\n\n{'='*30}\n")
                    f.write(f"MANUAL TRIGGER: {job_name} at {datetime.now()}\n")
                    f.write(f"{'='*30}\n\n")
                    
                    # Spawn process
                    self.current_process = subprocess.Popen(
                        cmd,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        cwd="/app" # Docker container root
                    )
                    
                logger.info(f"Started job {job_name} PID={self.current_process.pid}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start job {job_name}: {e}")
                return False

    def is_running(self) -> bool:
        with self.lock:
            return self.current_process is not None and self.current_process.poll() is None

    def get_logs(self, lines: int = 100) -> str:
        """Reads the last N lines from today's log file."""
        log_path = self._get_log_path()
        if not log_path.exists():
            return "Log file not found."
            
        try:
            # Simple tail implementation
            # For large files, seeking from end is better, but logs aren't huge yet.
            # using 'tail' command is easiest if available in container (it is).
            return subprocess.check_output(["tail", "-n", str(lines), str(log_path)]).decode("utf-8")
        except Exception as e:
            return f"Error reading logs: {e}"

# Singleton instance
from datetime import datetime
job_runner = JobRunner()
