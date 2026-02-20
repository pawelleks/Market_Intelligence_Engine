
import json
import sys
import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
import yaml

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
from pipeline import contracts

STAGES_YML = PROJECT_ROOT / "pipeline" / "stages.yml"
HEALTH_REPORT_PATH = PROJECT_ROOT / "data" / "pipeline_health.json"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

@dataclass
class StageHealth:
    stage_id: str
    name: str
    last_run: Optional[str]  # ISO timestamp of last run from logs
    last_status: Optional[str] # SUCCESS, FAILED, etc from logs
    output_freshness: str  # "FRESH", "STALE", "MISSING", "NO_OUTPUTS"
    input_status: str      # "OK", "MISSING", "STALE"
    policy: str            # fail, warn, skip

@dataclass
class PipelineHealth:
    as_of: str
    overall_status: str # OK, DEGRADED, CRITICAL
    stages: List[StageHealth]

def _get_latest_log_entry(stage_id: str) -> Dict:
    """
    Scan the latest log file to find the last run info for a stage.
    This is a bit expensive if many logs, so we just check the most recent few.
    """
    log_files = sorted(LOG_DIR.glob("pipeline_*.json"), reverse=True)
    
    for log_file in log_files[:5]: # Check last 5 logs
        try:
            with open(log_file, "r") as f:
                data = json.load(f)
            
            if stage_id in data.get("stages", {}):
                stage_data = data["stages"][stage_id]
                return {
                    "last_run": stage_data.get("end_time"), # Timestamp float
                    "last_status": stage_data.get("status")
                }
        except Exception:
            continue
            
    return {"last_run": None, "last_status": "UNKNOWN"}

def get_pipeline_health() -> PipelineHealth:
    """
    Assess the health of the pipeline.
    """
    with open(STAGES_YML, "r") as f:
        config = yaml.safe_load(f)
        
    stages_health = []
    critical_errors = 0
    degraded_errors = 0
    
    for stage_conf in config.get("stages", []):
        sid = stage_conf["id"]
        name = stage_conf["name"]
        policy = stage_conf.get("on_failure", "fail")
        
        # 1. Inputs Check
        input_res = contracts.validate_inputs(sid)
        if not input_res.passed:
            input_status = "MISSING" if input_res.missing else "STALE"
        else:
            input_status = "OK"

        # 2. Outputs Check (Freshness)
        # contracts.validate_outputs mainly checks existence.
        # We need to check freshness specifically for health reporting.
        outputs = stage_conf.get("outputs", [])
        stale_threshold = stage_conf.get("stale_after_hours", 48)
        
        output_status = "FRESH"
        if not outputs:
            output_status = "NO_OUTPUTS"
        else:
            # We assume contracts._resolve_paths or similar logic
            # Re-implementing simplified freshness check here or usage of internal Contract logic?
            # contracts.validate_outputs doesn't check freshness, only existence.
            # We should probably check freshness here manually as per requirement.
            
            missing_outputs = []
            stale_outputs = []
            has_files = False
            
            for pattern in outputs:
                full_pattern = str(PROJECT_ROOT / pattern)
                # We need glob
                import glob
                matches = glob.glob(full_pattern, recursive=True)
                
                if not matches:
                    missing_outputs.append(pattern)
                else:
                    has_files = True
                    for fpath in matches:
                        if not contracts._check_freshness(fpath, stale_threshold):
                            stale_outputs.append(pattern)
                            
            if missing_outputs:
                output_status = "MISSING"
            elif stale_outputs:
                output_status = "STALE"
        
        # 3. Last Run Info
        log_info = _get_latest_log_entry(sid)
        last_run_ts = log_info["last_run"]
        last_run_str = datetime.fromtimestamp(last_run_ts, timezone.utc).isoformat() if last_run_ts else None
        last_status = log_info["last_status"]
        
        # 4. Determine Health Impact
        if output_status in ("MISSING", "STALE"):
            if policy == "fail":
                # Critical stage missing/stale outputs -> CRITICAL impact
                critical_errors += 1
            elif policy == "warn":
                # Warn stage missing/stale outputs -> DEGRADED impact
                degraded_errors += 1
        
        stages_health.append(StageHealth(
            stage_id=sid,
            name=name,
            last_run=last_run_str,
            last_status=last_status,
            output_freshness=output_status,
            input_status=input_status,
            policy=policy
        ))

    # Overall Status Rule
    if critical_errors > 0:
        overall = "CRITICAL"
    elif degraded_errors > 0:
        overall = "DEGRADED"
    else:
        overall = "OK"
        
    return PipelineHealth(
        as_of=datetime.now(timezone.utc).isoformat(),
        overall_status=overall,
        stages=stages_health
    )

def write_health_report(path: Path = HEALTH_REPORT_PATH):
    health = get_pipeline_health()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(health), f, indent=2)
    print(f"Health report written to {path}")

def print_cli_summary(health: PipelineHealth):
    print("\n=== MIE Pipeline Health Report ===")
    print(f"As of: {health.as_of}")
    
    color_map = {
        "OK": "\033[92mOK\033[0m",
        "DEGRADED": "\033[93mDEGRADED\033[0m",
        "CRITICAL": "\033[91mCRITICAL\033[0m"
    }
    status_fmt = color_map.get(health.overall_status, health.overall_status)
    print(f"Overall Status: {status_fmt}")
    print("-" * 60)
    print(f"{'STAGE':<30} | {'STATUS':<10} | {'OUTPUTS':<10} | {'LAST RUN':<20}")
    print("-" * 60)
    
    for s in health.stages:
        # Shorten name
        name = (s.stage_id[:27] + '..') if len(s.stage_id) > 29 else s.stage_id
        
        # Output Color
        out_color = "\033[92m" # Green
        if s.output_freshness == "STALE": out_color = "\033[93m" # Yellow
        elif s.output_freshness == "MISSING": out_color = "\033[91m" # Red
        elif s.output_freshness == "NO_OUTPUTS": out_color = "\033[90m" # Grey
        
        out_fmt = f"{out_color}{s.output_freshness}\033[0m"
        
        # Last Status Color
        ls_color = "\033[0m"
        if s.last_status == "SUCCESS": ls_color = "\033[92m"
        elif s.last_status == "FAILED": ls_color = "\033[91m"
        elif s.last_status == "WARNING": ls_color = "\033[93m"
        
        ls_fmt = f"{ls_color}{s.last_status}\033[0m"
        
        last_run_short = s.last_run[:19].replace("T", " ") if s.last_run else "N/A"
        
        print(f"{name:<30} | {ls_fmt:<19} | {out_fmt:<19} | {last_run_short:<20}")
    print("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MIE Pipeline Health Check")
    parser.add_argument("--json", action="store_true", help="Output JSON only (to stdout)")
    parser.add_argument("--save", action="store_true", help="Save report to default path")
    args = parser.parse_args()
    
    health = get_pipeline_health()
    
    if args.save:
        write_health_report()
        
    if args.json:
        print(json.dumps(asdict(health), indent=2))
    else:
        print_cli_summary(health)
