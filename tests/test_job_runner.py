
import pytest
import subprocess
from unittest.mock import MagicMock, patch
from pathlib import Path
from mie_lib.services.job_runner import JobRunner

class TestJobRunner:
    @pytest.fixture
    def runner(self, tmp_path):
        return JobRunner(log_dir=str(tmp_path))

    @patch("subprocess.Popen")
    def test_run_job_daily_pipeline(self, mock_popen, runner):
        """
        Validates that 'daily-pipeline' job:
        1. Correctly resolves to 'bash scripts/nightly_update.sh'
        2. Sets correct CWD (local or /app)
        3. Writes to correct log file
        """
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Running
        mock_process.pid = 1234
        mock_popen.return_value = mock_process
        
        success = runner.run_job("daily-pipeline")
        
        assert success is True
        
        # Verify call args
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        
        # 1. Command Check
        assert cmd == ["bash", "scripts/nightly_update.sh"]
        
        # 2. CWD Check
        # Should be os.getcwd() in this test env (local)
        import os
        assert kwargs["cwd"] == os.getcwd()
        
        # 3. Log File Check
        # Popen should receive a writable file handle for stdout
        assert "stdout" in kwargs
        file_handle = kwargs["stdout"]
        # The file handle is closed by the with block by now, so we can't check 'not closed'
        # But we can verify its name
        assert file_handle.name == str(runner._get_log_path())
        
    @patch("subprocess.Popen")
    def test_run_job_invalid(self, mock_popen, runner):
        success = runner.run_job("fake-job")
        assert success is False
        mock_popen.assert_not_called()
