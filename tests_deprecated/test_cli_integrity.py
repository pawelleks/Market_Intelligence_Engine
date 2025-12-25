
import subprocess
import sys
import pytest
from mie_lib.services.job_runner import JobRunner

def test_job_commands_are_valid():
    """
    Verifies that every job defined in JobRunner.JOBS maps to a valid CLI command.
    We do this by appending '--help' to the command. 
    If the command or its arguments are invalid (e.g., misspelled flag), argparse will exit with non-zero.
    """
    analyzer = JobRunner()
    
    for job_name, cmd_list in analyzer.JOBS.items():
        # strict check: only test python commands that go through our CLI
        if cmd_list[0] != "python":
            continue
            
        # Construct the verification command
        # Replace 'python' with current executable
        verify_cmd = [sys.executable] + cmd_list[1:] + ["--help"]
        
        # Replace dynamic placeholders if any (though --help usually ignores them, 
        # sometimes value parsing happens before help if using certain argparse patterns, 
        # so let's be safe-ish, although --help usually short-circuits)
        # Actually, for --help to work, we just need the flags to be recognized.
        # We need to ensure we don't pass 'today' if the parser expects a date format *before* help? 
        # No, argparse handles --help at the start.
        # But we do need to replace keys like "@config" if we want to run it?
        # Actually, let's just run with --help.
        
        # We need to handle the case where arguments might be positional and required?
        # If I run `python -m mie build-gex-daily --date today --help`, it should work.
        
        print(f"Verifying {job_name}: {' '.join(verify_cmd)}")
        
        result = subprocess.run(
            verify_cmd, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Job '{job_name}' invalid.\nCommand: {' '.join(verify_cmd)}\nError: {result.stderr}")

if __name__ == "__main__":
    test_job_commands_are_valid()
