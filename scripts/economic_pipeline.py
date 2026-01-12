#!/usr/bin/env python3
"""
Economic Data Pipeline Orchestrator

This script coordinates the full economic data update pipeline:
1. Fetch latest FRED macro series data
2. Run economic model calculations (LEI, COI, LAG)
3. Track progress and status for monitoring via API

Used by:
- CRON (scheduled daily at 2 AM)
- CLI (`mie update-economic`)
- Manual API trigger via admin panel
"""

import sys
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any
import pandas as pd
import yaml
from dotenv import load_dotenv

load_dotenv()

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mie_lib.data_ingest.macro.providers.fred import FredProvider
from mie_lib.utils.paths import RAW_DATA_DIR, DATA_DIR

# Define macro analysis directory
MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"
MACRO_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Status file location
STATUS_DIR = REPO_ROOT / "data" / "pipeline_status"
STATUS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATUS_DIR / "economic_pipeline.json"


class EconomicPipeline:
    """Orchestrates economic data updates and model calculations."""
    
    def __init__(self):
        self.status = {
            "status": "idle",
            "last_run": None,
            "next_run": None,
            "steps": []
        }
        self.load_status()
    
    def load_status(self):
        """Load existing status from JSON file."""
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, 'r') as f:
                    self.status = json.load(f)
            except Exception as e:
                LOG.warning(f"Failed to load status file: {e}")
    
    def save_status(self):
        """Save current status to JSON file."""
        try:
            with open(STATUS_FILE, 'w') as f:
                json.dump(self.status, f, indent=2)
        except Exception as e:
            LOG.error(f"Failed to save status file: {e}")
    
    def update_step(self, name: str, status: str, **kwargs):
        """Update or add a step in the status."""
        # Find existing step or create new
        step = next((s for s in self.status["steps"] if s["name"] == name), None)
        if step is None:
            step = {"name": name}
            self.status["steps"].append(step)
        
        step["status"] = status
        step.update(kwargs)
        
        if status == "running":
            step["started_at"] = datetime.now(timezone.utc).isoformat()
        elif status in ["completed", "failed"]:
            step["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        self.save_status()
    
    def run(self):
        """Execute the full economic pipeline."""
        LOG.info("="*60)
        LOG.info("Starting Economic Data Pipeline")
        LOG.info("="*60)
        
        self.status["status"] = "running"
        self.status["last_run"] = datetime.now(timezone.utc).isoformat()
        self.status["steps"] = []
        self.save_status()
        
        try:
            # Step 1: Fetch FRED Data
            self.fetch_fred_data()
            
            # Step 2 & 3: Calculate Enhanced LEI & COI
            # Step A: Enhanced LEI/COI
            self.run_enhanced_calculations()
            
            # Step B: Business Cycle (LAG + Phases)
            self.run_business_cycle_calculation()
            
            # Step 4: Calculate LAG
            self.run_lag_calculation()
            
            # Step 5: Calculate Minsky Model
            self.run_minsky_calculation()
            
            # Step 6: Calculate ABCT Model
            self.run_abct_calculation()
            
            # Step 7: Calculate HP Filter
            self.run_hp_filter_calculation()
            
            # Step 8: Calculate Hamilton Model
            self.run_hamilton_calculation()
            
            # Step 9: Calculate Liquidity Impulse
            self.run_liquidity_impulse_calculation()
            
            # Step 10: Calculate Recession Momentum
            self.run_recession_momentum_calculation()
            
            # Step 11: Generate Prediction Analysis
            self.run_prediction_analysis()
            
            # All steps completed
            self.status["status"] = "idle"
            LOG.info("="*60)
            LOG.info("Economic Pipeline Completed Successfully")
            LOG.info("="*60)
            
        except Exception as e:
            LOG.error(f"Pipeline failed: {e}", exc_info=True)
            self.status["status"] = "failed"
            raise
        finally:
            self.save_status()
    
    def fetch_fred_data(self):
        """Fetch all FRED series from config (incremental updates)."""
        step_name = "Fetch FRED Data"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            # Load series config
            config_path = REPO_ROOT / "config" / "macro_series.yml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            series_dict = config.get("series", {})
            series_count = len(series_dict)
            series_updated = 0
            series_skipped = 0
            errors = []
            validation_warnings = []
            
            LOG.info(f"Processing {series_count} FRED series (incremental update mode)...")
            
            # Initialize FRED provider
            provider = FredProvider()
            
            # Fetch each series incrementally
            for series_id, description in series_dict.items():
                try:
                    # Use incremental fetch
                    df = provider.fetch_series_incremental(series_id, min_start_date="1960-01-01")
                    
                    if df.empty:
                        LOG.warning(f"  {series_id}: No data returned")
                        errors.append(f"{series_id}: No data")
                        continue
                    
                    # Save updated data
                    provider.save_series(series_id, df)
                    series_updated += 1
                    
                    # Verify historical coverage
                    is_valid, msg = provider.verify_historical_coverage(series_id, required_start_year=1970)
                    if not is_valid:
                        validation_warnings.append(f"{series_id}: {msg}")
                        LOG.warning(f"  {series_id}: VALIDATION WARNING - {msg}")
                    else:
                        LOG.info(f"  {series_id}: {msg}")
                        
                except Exception as e:
                    error_msg = f"{series_id}: {str(e)}"
                    LOG.warning(f"  Failed to fetch {error_msg}")
                    errors.append(error_msg)
            
            LOG.info(f"FRED data fetch complete: {series_updated}/{series_count} series updated")
            if validation_warnings:
                LOG.warning(f"Validation warnings: {len(validation_warnings)} series")
            
            self.update_step(
                step_name,
                "completed",
                series_count=series_count,
                series_updated=series_updated,
                errors=errors[:5] if errors else [],  # Limit to first 5 errors
                validation_warnings=validation_warnings[:5] if validation_warnings else []
            )
            
        except Exception as e:
            LOG.error(f"FRED fetch failed: {e}")
            self.update_step(step_name, "failed", error=str(e))
            raise
    
    def run_enhanced_calculations(self):
        """Run Enhanced LEI & COI model calculations."""
        step_name = "Calculate Enhanced LEI/COI"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "update_economy_data_enhanced.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            # Get output file info
            output_file = MACRO_ANALYSIS_DIR / "processed_lei_coi_enhanced.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Enhanced calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_business_cycle_calculation(self):
        """Run Business Cycle Phase calculation."""
        step_name = "Calculate Business Cycle"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "calculate_business_cycle.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            # Get output file info
            output_file = MACRO_ANALYSIS_DIR / "processed_business_cycle.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Business Cycle calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_lag_calculation(self):
        """Run LAG model calculation."""
        step_name = "Calculate LAG Index"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "calculate_lag_index.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            # Get output file info
            output_file = MACRO_ANALYSIS_DIR / "lag_model.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"LAG calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_minsky_calculation(self):
        """Run Minsky Financial Instability model calculation."""
        step_name = "Calculate Minsky Model"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "calculate_minsky_model.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "minsky_model.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Minsky calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_abct_calculation(self):
        """Run Austrian Business Cycle Theory (ABCT) model calculation."""
        step_name = "Calculate ABCT Model"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "calculate_abct_model.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "abct_model.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"ABCT calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_hp_filter_calculation(self):
        """Run Hodrick-Prescott (HP) Filter calculation."""
        step_name = "Calculate HP Filter"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "hp_model_generator.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "hp_output_gap.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"HP Filter calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_hamilton_calculation(self):
        """Run Hamilton Markov Switching model calculation."""
        step_name = "Calculate Hamilton Model"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "hamilton_model_generator.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "hamilton_gdp_regimes.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Hamilton calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_liquidity_impulse_calculation(self):
        """Run Global Liquidity Impulse calculation."""
        step_name = "Calculate Liquidity Impulse"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "liquidity_impulse_generator.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "liquidity_impulse.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Liquidity Impulse calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_recession_momentum_calculation(self):
        """Run Macro-Momentum Recession model calculation."""
        step_name = "Calculate Recession Momentum"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            script_path = REPO_ROOT / "scripts" / "recession_momentum_generator.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            
            LOG.info(result.stdout)
            
            output_file = MACRO_ANALYSIS_DIR / "recession_momentum.parquet"
            file_info = self._get_file_info(output_file)
            
            self.update_step(
                step_name,
                "completed",
                output_file=str(output_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Recession Momentum calculation failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def run_prediction_analysis(self):
        """Run the full Prediction Analysis framework."""
        step_name = "Generate Prediction Analysis"
        LOG.info(f"Step: {step_name}")
        self.update_step(step_name, "running")
        
        try:
            # Analysis scripts in order of execution
            analysis_scripts = [
                "extract_all_signal_timelines.py",
                "create_nber_recession_dataset.py",
                "create_sp500_returns_dataset.py",
                "match_signals_to_outcomes.py",
                "create_comparative_analysis.py",
                "generate_final_reports.py"
            ]
            
            outputs = []
            for script_name in analysis_scripts:
                script_path = REPO_ROOT / "scripts" / "analysis" / script_name
                LOG.info(f"  Running {script_name}...")
                
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                LOG.info(f"  ✓ {script_name} completed")
                outputs.append(script_name)
            
            # Check output files
            output_dir = REPO_ROOT / "data" / "analysis" / "dashboard"
            dashboard_file = output_dir / "model_comparison.json"
            
            file_info = {}
            if dashboard_file.exists():
                file_info = self._get_file_info(dashboard_file)
            
            self.update_step(
                step_name,
                "completed",
                scripts_run=len(outputs),
                output_file=str(dashboard_file),
                **file_info
            )
            
        except subprocess.CalledProcessError as e:
            LOG.error(f"Prediction Analysis failed: {e.stderr}")
            self.update_step(step_name, "failed", error=e.stderr)
            raise
    
    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get file metadata (size, modification time)."""
        if not file_path.exists():
            return {}
        
        stat = file_path.stat()
        return {
            "file_size_kb": round(stat.st_size / 1024, 2),
            "last_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        }


def main():
    """Main entry point."""
    pipeline = EconomicPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
