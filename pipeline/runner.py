
import argparse
import json
import subprocess
import sys
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional

# Add project root to sys.path to import contracts
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
from pipeline import contracts
from mie_lib.services.audit_logger import get_audit_logger

STAGES_YML = PROJECT_ROOT / "pipeline" / "stages.yml"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

class StageNode:
    def __init__(self, config: Dict):
        self.id = config["id"]
        self.config = config
        self.status = "PENDING"  # PENDING, RUNNING, SUCCESS, FAILED, SKIPPED, WARNING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.error: Optional[str] = None
        self.parents: List[str] = config.get("depends_on", [])
        self.children: List[str] = []

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time) if self.end_time and self.start_time else None,
            "error": self.error,
        }

class PipelineRunner:
    def __init__(self, stages_file: Path = STAGES_YML):
        with open(stages_file, "r") as f:
            data = yaml.safe_load(f)
        
        self.stages_config = {s["id"]: s for s in data["stages"]}
        self.nodes: Dict[str, StageNode] = {sid: StageNode(cfg) for sid, cfg in self.stages_config.items()}
        self._build_graph()
        self.run_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stages": {}
        }
        
    def _build_graph(self):
        # Populate children and check for missing parents
        for sid, node in self.nodes.items():
            for pid in node.parents:
                if pid not in self.nodes:
                    raise ValueError(f"Stage '{sid}' depends on unknown stage '{pid}'")
                self.nodes[pid].children.append(sid)
        
        # Cycle detection
        visited = set()
        path = set()
        
        def visit(n: str):
            if n in path:
                raise ValueError(f"Cycle detected involving stage '{n}'")
            if n in visited:
                return
            
            path.add(n)
            for child in self.nodes[n].children:
                visit(child)
            path.remove(n)
            visited.add(n)
            
        for sid in self.nodes:
            visit(sid)

    def get_execution_order(self, target_ids: Optional[List[str]] = None) -> List[str]:
        """
        Return topologically sorted list of stage IDs to run.
        If target_ids provided, only include them and their ancestors.
        """
        if target_ids:
            # Resolve ancestors
            to_run = set(target_ids)
            queue = list(target_ids)
            while queue:
                curr = queue.pop(0)
                if curr not in self.nodes:
                    raise ValueError(f"Unknown target stage '{curr}'")
                for pid in self.nodes[curr].parents:
                    if pid not in to_run:
                        to_run.add(pid)
                        queue.append(pid)
        else:
            to_run = set(self.nodes.keys())
            
        # Topological sort (Kahn's algorithm restricted to to_run set)
        in_degree = {sid: 0 for sid in to_run}
        for sid in to_run:
            for child in self.nodes[sid].children:
                if child in to_run:
                    in_degree[child] += 1
                    
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []
        
        while queue:
            curr = queue.pop(0)
            order.append(curr)
            
            for child in self.nodes[curr].children:
                if child in to_run:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)
                        
        if len(order) != len(to_run):
            # Should be caught by cycle check, but safety net
            raise ValueError("Graph cycle detected during sort")
            
        return order

    def _should_skip(self, sid: str) -> bool:
        """
        Determine if stage should be skipped based on parent status.
        If a parent failed (and its policy was NOT 'warn'), we skip.
        If parent failed but policy was 'warn', we proceed.
        """
        for pid in self.nodes[sid].parents:
            parent = self.nodes[pid]
            parent_policy = parent.config.get("on_failure", "fail")
            
            if parent.status == "SKIPPED":
                return True
            if parent.status == "FAILED" and parent_policy != "warn":
                return True
                
        return False

    def run_stage(self, sid: str, dry_run: bool = False) -> bool:
        """
        Execute a single stage. Returns True if successful (or warning), False if failed hard.
        """
        node = self.nodes[sid]
        
        # 1. Start
        node.status = "RUNNING"
        node.start_time = time.time()
        print(f"\n[RUN] {sid} ({node.config['name']})...")
        
        if not dry_run:
            try:
                get_audit_logger().update_stage(node.id, "RUNNING", {})
            except Exception as e:
                print(f"  ⚠️ Failed to update audit log (RUNNING): {e}")
        
        if dry_run:
            print(f"  [DRY-RUN] Would execute: mie {node.config['command']} {' '.join(node.config['args'])}")
            node.status = "SUCCESS"
            node.end_time = time.time()
            return True

        # 2. Input Contracts
        print(f"  > Checking inputs...")
        input_res = contracts.validate_inputs(sid)
        if not input_res.passed:
            node.error = f"Input contract failed: missing={input_res.missing}, stale={input_res.stale}"
            node.end_time = time.time()
            print(f"  ❌ INPUT CONTRACT FAILED: {node.error}")

            policy = node.config.get("on_failure", "fail")

            if policy == "warn":
                print(f"  ⚠️ INPUT CONTRACT FAILED (Policy: warn). Continuing...")
                node.status = "WARNING"
                if not dry_run:
                    try:
                        get_audit_logger().update_stage(node.id, "WARNING", {
                            "runner": "new",
                            "duration_seconds": node.end_time - node.start_time,
                            "error": node.error
                        })
                    except Exception as e:
                        print(f"  ⚠️ Failed to update audit log (WARNING): {e}")
                return True
            else:
                node.status = "FAILED"
                if not dry_run:
                    try:
                        get_audit_logger().update_stage(node.id, "FAILED", {
                            "runner": "new",
                            "duration_seconds": node.end_time - node.start_time,
                            "error": node.error
                        })
                    except Exception as e:
                        print(f"  ⚠️ Failed to update audit log (FAILED): {e}")
                return False

        # 3. Execution (with Retry)
        cmd = [sys.executable, "-m", "mie_lib.cli.mie", node.config["command"]] + node.config["args"]
        max_retries = node.config.get("retry", 0)
        attempt = 0
        success = False
        
        while attempt <= max_retries:
            try:
                print(f"  > Executing (Attempt {attempt+1}/{max_retries+1})...")
                # We use check=True to raise CalledProcessError on non-zero exit
                subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
                success = True
                break
            except subprocess.CalledProcessError as e:
                print(f"  ⚠️ Attempt {attempt+1} failed with code {e.returncode}")
                # Backoff if retries remain
                if attempt < max_retries:
                    print("  > Waiting 30s before retry...")
                    time.sleep(30)
                attempt += 1

        if not success:
            node.status = "FAILED"
            node.error = "Command execution failed (max retries exhausted)"
            node.end_time = time.time()
            
            policy = node.config.get("on_failure", "fail")
            
            # Helper to log status
            def log_audit(status_code, err_msg):
                if not dry_run:
                    try:
                        get_audit_logger().update_stage(node.id, status_code, {
                            "runner": "new",
                            "duration_seconds": node.end_time - node.start_time,
                            "error": err_msg
                        })
                    except Exception as e:
                        print(f"  ⚠️ Failed to update audit log ({status_code}): {e}")

            if policy == "warn":
                print(f"  ⚠️ STAGE FAILED (Policy: warn). Continuing...")
                node.status = "WARNING" # Mark as warning but treated as non-blocking
                log_audit("WARNING", node.error)
                return True
            elif policy == "skip":
                 # skip policy on failure means "skip DEPENDENTS", but for this node it is effectively failed/skipped
                 # We mark as FAILED so dependents see it failed.
                 print(f"  ❌ STAGE FAILED (Policy: skip dependents).")
                 log_audit("FAILED", node.error)
                 return False
            else:
                print(f"  ❌ STAGE FAILED (Policy: fail). Stopping pipeline.")
                log_audit("FAILED", node.error)
                return False

        # 4. Output Contracts
        # We check outputs but failure here depends on policy? 
        # Usually if command succeeded but output is missing, it's a failure.
        print(f"  > Checking outputs...")
        output_res = contracts.validate_outputs(sid)
        if not output_res.passed:
            node.status = "FAILED"
            node.error = f"Output contract failed: missing={output_res.missing}"
            node.end_time = time.time()
            
            policy = node.config.get("on_failure", "fail")
            
            # Helper to log status (reused from above logic effectively)
            def log_audit_out(status_code, err_msg):
                if not dry_run:
                    try:
                        get_audit_logger().update_stage(node.id, status_code, {
                            "runner": "new",
                            "duration_seconds": node.end_time - node.start_time,
                            "error": err_msg
                        })
                    except Exception:
                        pass

            if policy == "warn":
                print(f"  ⚠️ OUTPUT CONTRACT FAILED (Policy: warn). Missing: {output_res.missing}")
                node.status = "WARNING"
                log_audit_out("WARNING", node.error)
                return True
            else:
                print(f"  ❌ OUTPUT CONTRACT FAILED. Missing: {output_res.missing}")
                log_audit_out("FAILED", node.error)
                return False

        # 5. Success
        node.status = "SUCCESS"
        node.end_time = time.time()
        print(f"  ✅ STAGE COMPLETED ({node.end_time - node.start_time:.1f}s)")
        
        if not dry_run:
            try:
                get_audit_logger().update_stage(node.id, "COMPLETED", {
                    "runner": "new",
                    "duration_seconds": node.end_time - node.start_time
                })
            except Exception as e:
                print(f"  ⚠️ Failed to update audit log (COMPLETED): {e}")

        return True

    def run(self, target_ids: Optional[List[str]] = None, dry_run: bool = False):
        order = self.get_execution_order(target_ids)
        print(f"Pipeline Execution Plan: {len(order)} stages")
        print(" -> ".join(order))
        print("="*60)
        
        failure_stop = False
        
        for sid in order:
            node = self.nodes[sid]

            # Check dependency status
            if self._should_skip(sid):
                print(f"[SKIP] {sid} (dependencies unsatisfied)")
                node.status = "SKIPPED"
                self.run_log["stages"][sid] = node.to_dict()
                continue

            # If a previous hard fail occurred, skip remaining stages
            if failure_stop:
                print(f"[SKIP] {sid} (pipeline aborted)")
                node.status = "SKIPPED"
                self.run_log["stages"][sid] = node.to_dict()
                continue

            # Run
            ok = self.run_stage(sid, dry_run=dry_run)

            # Record log
            self.run_log["stages"][sid] = node.to_dict()

            if not ok:
                policy = node.config.get("on_failure", "fail")
                if policy != "warn":
                    failure_stop = True

        self._save_log()
        
        if failure_stop:
            print("\n❌ Pipeline finished with ERRORS.")
            sys.exit(1)
        else:
            print("\n✅ Pipeline finished SUCCESSFULLY.")
            sys.exit(0)

    def _save_log(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"pipeline_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        with open(LOG_DIR / filename, "w") as f:
            json.dump(self.run_log, f, indent=2)
        print(f"\nExecution log saved to {LOG_DIR / filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MIE Pipeline Runner")
    parser.add_argument("--stages", help="Comma-separated list of stages to run (runs dependencies too)")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan without running commands")
    args = parser.parse_args()
    
    targets = [t.strip() for t in args.stages.split(",")] if args.stages else None
    
    runner = PipelineRunner()
    try:
        runner.run(target_ids=targets, dry_run=args.dry_run)
    except Exception as e:
        print(f"\n❌ Pipeline Crashed: {e}")
        sys.exit(1)
