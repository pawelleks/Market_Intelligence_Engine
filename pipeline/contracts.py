
import glob
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import yaml

# Path to the stages registry
STAGES_YML = Path(__file__).parent / "stages.yml"
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class ContractResult:
    """Result of a contract validation check."""
    stage_id: str
    passed: bool
    missing: List[str] = field(default_factory=list)
    stale: List[str] = field(default_factory=list)
    details: str = ""


def _load_stages() -> List[Dict]:
    """Load stages from the YAML registry."""
    if not STAGES_YML.exists():
        raise FileNotFoundError(f"Pipeline registry not found at {STAGES_YML}")
    
    with open(STAGES_YML, "r") as f:
        data = yaml.safe_load(f)
    return data.get("stages", [])


def _resolve_paths(patterns: List[str]) -> List[str]:
    """Resolve glob patterns to actual file paths."""
    resolved = []
    for pattern in patterns:
        # Handle relative patterns from project root
        full_pattern = str(PROJECT_ROOT / pattern)
        matches = glob.glob(full_pattern, recursive=True)
        if not matches:
            # If no matches, we keep the pattern to report it as missing/checked
            # But for existence check, we need to know if it expanded to nothing.
            pass
        resolved.extend(matches)
    return resolved


def _check_freshness(filepath: str, age_hours: int) -> bool:
    """Check if a file is newer than age_hours."""
    if not os.path.exists(filepath):
        return False
    
    mtime = os.path.getmtime(filepath)
    age_seconds = time.time() - mtime
    return age_seconds < (age_hours * 3600)


def validate_inputs(stage_id: str) -> ContractResult:
    """
    Validate that a stage's inputs exist and are fresh.
    Default freshness threshold is 48 hours unless overridden by 'stale_after_hours' in stage config.
    """
    stages = _load_stages()
    stage = next((s for s in stages if s["id"] == stage_id), None)
    
    if not stage:
        return ContractResult(stage_id, False, details=f"Stage ID {stage_id} not found in registry")

    inputs = stage.get("inputs", [])
    stale_threshold = stage.get("stale_after_hours", 48)
    
    missing_patterns = []
    stale_files = []
    
    if not inputs:
        return ContractResult(stage_id, True, details="No inputs defined")

    has_at_least_one_file = False

    for pattern in inputs:
        full_pattern = str(PROJECT_ROOT / pattern)
        matches = glob.glob(full_pattern, recursive=True)
        
        if not matches:
            missing_patterns.append(pattern)
            continue
            
        # New logic: A glob input is satisfied if AT LEAST ONE matched file is fresh.
        # This allows archives (many old files) to exist as long as the latest one is there.
        any_fresh = False
        for fpath in matches:
            if _check_freshness(fpath, stale_threshold):
                any_fresh = True
                break
        
        if not any_fresh:
            # All matched files are stale
            for fpath in matches:
                stale_files.append(str(Path(fpath).relative_to(PROJECT_ROOT)))

    # Contract: All defined input patterns must resolve to at least one file
    # AND those files must be fresh.
    
    passed = len(missing_patterns) == 0 and len(stale_files) == 0
    
    return ContractResult(
        stage_id=stage_id,
        passed=passed,
        missing=missing_patterns,
        stale=stale_files,
        details=f"Checked {len(inputs)} patterns. Stale Check: >{stale_threshold}h"
    )


def validate_outputs(stage_id: str) -> ContractResult:
    """
    Validate that a stage's outputs exist.
    Outputs are just checked for existence (they are the result of THIS run).
    """
    stages = _load_stages()
    stage = next((s for s in stages if s["id"] == stage_id), None)
    
    if not stage:
        return ContractResult(stage_id, False, details=f"Stage ID {stage_id} not found in registry")

    outputs = stage.get("outputs", [])
    missing_patterns = []
    
    if not outputs:
        return ContractResult(stage_id, True, details="No outputs defined")

    for pattern in outputs:
        full_pattern = str(PROJECT_ROOT / pattern)
        matches = glob.glob(full_pattern, recursive=True)
        
        if not matches:
            missing_patterns.append(pattern)

    passed = len(missing_patterns) == 0
    
    return ContractResult(
        stage_id=stage_id,
        passed=passed,
        missing=missing_patterns,
        details=f"Checked {len(outputs)} patterns."
    )


def check_all_contracts() -> Dict[str, Dict]:
    """
    Run validation for all stages in the registry.
    Returns a dictionary summary.
    """
    stages = _load_stages()
    results = {}
    
    for stage in stages:
        sid = stage["id"]
        input_res = validate_inputs(sid)
        output_res = validate_outputs(sid)
        
        results[sid] = {
            "inputs": {
                "passed": input_res.passed,
                "missing": input_res.missing,
                "stale": input_res.stale
            },
            "outputs": {
                "passed": output_res.passed,
                "missing": output_res.missing
            }
        }
        
    return results

if __name__ == "__main__":
    # Simple CLI check
    summary = check_all_contracts()
    for sid, res in summary.items():
        print(f"[{sid}]")
        print(f"  Inputs: {'OK' if res['inputs']['passed'] else 'FAIL'}")
        if not res['inputs']['passed']:
            if res['inputs']['missing']: print(f"    Missing: {res['inputs']['missing']}")
            if res['inputs']['stale']: print(f"    Stale: {res['inputs']['stale']}")
        print(f"  Outputs: {'OK' if res['outputs']['passed'] else 'FAIL'}")
        if not res['outputs']['passed']:
            if res['outputs']['missing']: print(f"    Missing: {res['outputs']['missing']}")
    print("-" * 40)
