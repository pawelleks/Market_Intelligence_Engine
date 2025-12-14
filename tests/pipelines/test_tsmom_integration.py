import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Import main from mie.py
# Since mie.py is a script, we might import it as a module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src")))
from mie_lib.cli.mie import main

class TestPipelineIntegration(unittest.TestCase):

    @patch("mie_lib.cli.mie._load_yaml_tickers")
    @patch("subprocess.run")
    @patch("sys.exit") # Prevent exit(0)
    def test_update_everything_calls_tsmom(self, mock_exit, mock_run, mock_load_tickers):
        # Setup
        mock_load_tickers.return_value = ["SPY", "TLT"]
        
        # Test Args
        test_args = ["mie.py", "update-everything"]
        
        with patch.object(sys, 'argv', test_args):
            try:
                main()
            except SystemExit:
                pass # Expected
            except Exception as e:
                self.fail(f"Pipeline crashed: {e}")

        # Assertions
        # Check if build-tsmom-daily was called
        # mock_run calls are with `cmd` list
        tsmom_called = False
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0] # First arg is the command list
            # cmd is like ['python', '.../mie.py', 'build-tsmom-daily', ...]
            if "build-tsmom-daily" in cmd:
                tsmom_called = True
                break
        
        self.assertTrue(tsmom_called, "TSMOM build command was not triggered in pipeline")

if __name__ == '__main__':
    unittest.main()
