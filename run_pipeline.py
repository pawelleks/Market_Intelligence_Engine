
import argparse
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))
from pipeline.runner import PipelineRunner
from pipeline.health import write_health_report, print_cli_summary, get_pipeline_health
from mie_lib.services.audit_logger import get_audit_logger

def run_command(cmd, shell=False):
    """Run a shell command and return exit code."""
    try:
        if shell:
            subprocess.run(cmd, shell=True, check=True, cwd=PROJECT_ROOT)
        else:
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        return 0
    except subprocess.CalledProcessError as e:
        return e.returncode

def main():
    parser = argparse.ArgumentParser(description="MIE Daily Pipeline Entry Point")
    parser.add_argument("--stages", help="Comma-separated list of stages to run")
    parser.add_argument("--run-type", default="MANUAL", choices=["MANUAL", "CRON", "RETRY"], help="Type of run (default: MANUAL)")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan only")
    parser.add_argument("--name", help="Custom job name for audit log")
    args = parser.parse_args()

    # Define Python executable
    python_exe = sys.executable

    # 1. Initialize Audit Log
    # We use the CLI command to ensure the singleton in mie_lib is correctly initialized/reset
    # and to keep consistent with old orchestrator behavior.
    if not args.dry_run:
        job_name = args.name or f"Daily Pipeline {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"🚀 Initializing Pipeline Job: {job_name} ({args.run_type})")
        
        # Primary: Direct Audit Logger Call
        try:
            logger = get_audit_logger()
            logger._reset_data()
            logger.start_job(job_name, run_type=args.run_type)
        except Exception as e:
            print(f"⚠️ Direct Audit Init Failed: {e}")

        # Fallback: CLI Command
        init_cmd = [python_exe, "-m", "mie_lib.cli.mie", "start-pipeline-job", 
                    "--name", job_name, "--type", args.run_type]
        if run_command(init_cmd) != 0:
            print("❌ Failed to initialize audit log. Aborting.")
            sys.exit(1)

    # 2. Run Pipeline
    target_ids = [t.strip() for t in args.stages.split(",")] if args.stages else None
    
    runner = PipelineRunner()
    
    pipeline_success = False
    try:
        runner.run(target_ids=target_ids, dry_run=args.dry_run)
        pipeline_success = True
    except SystemExit as e:
        # runner.run() calls sys.exit(), we catch it to perform cleanup
        pipeline_success = (e.code == 0)
    except Exception as e:
        print(f"❌ Pipeline Exception: {e}")
        pipeline_success = False

    # 3. Health Report
    if not args.dry_run:
        print("\n🏥 Generating Health Report...")
        try:
            write_health_report()
            health = get_pipeline_health()
            print_cli_summary(health)
            
            # Check overall status for final exit code
            # If pipeline_success is True but health is CRITICAL, should we fail?
            # Contracts are checked inside runner. If runner succeeded, it means
            # no 'fail' policy stages failed.
            # So runner success is the primary success metric.
        except Exception as e:
            print(f"⚠️ Failed to generate health report: {e}")

    # 4. Finalize Audit Log
    if not args.dry_run:
        status = "COMPLETED" if pipeline_success else "FAILED"
        print(f"\n🏁 Finalizing Pipeline Job (Status: {status})...")
        
        # We assume publishing analytics data stage is done by the pipeline stages themselves 
        # or we just mark the job finished.
        
        # Primary: Direct Audit Logger Call
        try:
            get_audit_logger().finish_job(status)
        except Exception as e:
            print(f"⚠️ Direct Audit Finish Failed: {e}")

        # Fallback: CLI Command
        finish_cmd = [python_exe, "-m", "mie_lib.cli.mie", "finish-pipeline-job", "--status", status]
        run_command(finish_cmd)

    if pipeline_success:
        print("\n✅ Pipeline Finished Successfully.")
        sys.exit(0)
    else:
        print("\n❌ Pipeline Failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
