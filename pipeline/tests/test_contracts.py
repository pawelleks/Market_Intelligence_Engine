
import unittest
import tempfile
import shutil
import os
import time
import yaml
from pathlib import Path
from unittest.mock import patch

# Import the module under test
# adjusting sys.path might be needed if running as standalone script
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from pipeline import contracts

class TestPipelineContracts(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory structure
        self.test_dir = tempfile.mkdtemp()
        self.project_root_patch = patch('pipeline.contracts.PROJECT_ROOT', Path(self.test_dir))
        self.project_root_patch.start()
        
        # Create a mock stages.yml
        self.stages_yml_path = Path(self.test_dir) / "pipeline" / "stages.yml"
        os.makedirs(self.stages_yml_path.parent, exist_ok=True)
        
        self.mock_stages = {
            "version": "1.0",
            "stages": [
                {
                    "id": "test_stage_1",
                    "name": "Test Stage 1",
                    "inputs": ["data/input/*.csv"],
                    "outputs": ["data/output/*.parquet"],
                    "stale_after_hours": 24
                },
                {
                    "id": "test_stage_no_inputs",
                    "name": "No Inputs Stage",
                    "inputs": [],
                    "outputs": []
                }
            ]
        }
        with open(self.stages_yml_path, "w") as f:
            yaml.dump(self.mock_stages, f)
            
        # Patch STAGES_YML to point to our mock
        self.stages_yml_patch = patch('pipeline.contracts.STAGES_YML', self.stages_yml_path)
        self.stages_yml_patch.start()

        # Create data directories
        os.makedirs(Path(self.test_dir) / "data/input", exist_ok=True)
        os.makedirs(Path(self.test_dir) / "data/output", exist_ok=True)

    def tearDown(self):
        self.project_root_patch.stop()
        self.stages_yml_patch.stop()
        shutil.rmtree(self.test_dir)

    def test_validate_inputs_fresh(self):
        # Create a fresh file
        fresh_file = Path(self.test_dir) / "data/input/data.csv"
        fresh_file.touch()
        
        result = contracts.validate_inputs("test_stage_1")
        self.assertTrue(result.passed)
        self.assertEqual(len(result.missing), 0)
        self.assertEqual(len(result.stale), 0)

    def test_validate_inputs_stale(self):
        # Create a stale file (older than 24h)
        stale_file = Path(self.test_dir) / "data/input/data.csv"
        stale_file.touch()
        
        # Manually set mtime to 25 hours ago
        past_time = time.time() - (25 * 3600)
        os.utime(stale_file, (past_time, past_time))
        
        result = contracts.validate_inputs("test_stage_1")
        self.assertFalse(result.passed)
        self.assertEqual(len(result.stale), 1)
        # Note: glob match logic in contracts.py iterates all matches. 
        # If one is stale, it fails.

    def test_validate_inputs_missing(self):
        # No files created
        result = contracts.validate_inputs("test_stage_1")
        # Should fail because pattern doesn't match anything
        self.assertFalse(result.passed) 
        # missing list should contain the pattern
        self.assertIn("data/input/*.csv", result.missing)

    def test_validate_outputs_exists(self):
        # Create output file
        outfile = Path(self.test_dir) / "data/output/result.parquet"
        outfile.touch()
        
        result = contracts.validate_outputs("test_stage_1")
        self.assertTrue(result.passed)

    def test_validate_outputs_missing(self):
        # No output file
        result = contracts.validate_outputs("test_stage_1")
        self.assertFalse(result.passed)
        self.assertIn("data/output/*.parquet", result.missing)

    def test_no_inputs_pass(self):
        result = contracts.validate_inputs("test_stage_no_inputs")
        self.assertTrue(result.passed)

    def test_check_all_contracts(self):
        # Setup mixed state
        # Input fresh
        (Path(self.test_dir) / "data/input/data.csv").touch()
        # Output missing
        
        summary = contracts.check_all_contracts()
        
        self.assertTrue(summary["test_stage_1"]["inputs"]["passed"])
        self.assertFalse(summary["test_stage_1"]["outputs"]["passed"])
        self.assertTrue(summary["test_stage_no_inputs"]["inputs"]["passed"])

if __name__ == '__main__':
    unittest.main()
