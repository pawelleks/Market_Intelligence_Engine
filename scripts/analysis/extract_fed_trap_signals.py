#!/usr/bin/env python3
"""
Extract Fed Trap Signal Timeline

Processes the Fed Trap Divergence model to extract signal timeline.

Output: 
- data/analysis/signal_timelines/fed_trap_signals.parquet
- data/analysis/signal_events/fed_trap_events.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from scripts.analysis.extract_all_signal_timelines import SignalExtractor

DATA_DIR = project_root / "data"
PROCESSED_DIR = DATA_DIR / "processed"


class FedTrapExtractor(SignalExtractor):
    """Extract signals from Fed Trap Divergence model."""
    
    def __init__(self):
        super().__init__(
            model_name='fed_trap',
            file_path=PROCESSED_DIR / 'fed_trap_divergence.parquet'
        )
        
    def classify_signal(self, row):
        # Need to check what columns exist in the Fed Trap model
        # This is a placeholder - will need to be refined based on actual data structure
        
        # Check if there's a signal or divergence column
        for col in ['trap_signal', 'divergence_score', 'policy_error']:
            if col in row.index:
                value = row.get(col, np.nan)
                if not pd.isna(value):
                    if isinstance(value, (bool, np.bool_)):
                        return 'TROUBLE' if value else 'CLEAR'
                    elif isinstance(value, (int, float)):
                        if value > 1.0:
                            return 'TROUBLE'
                        elif value > 0.5:
                            return 'WARNING'
                        else:
                            return 'CLEAR'
        
        return 'UNKNOWN'


def main():
    print("="*70)
    print("EXTRACTING FED TRAP SIGNAL TIMELINE")
    print("="*70)
    
    extractor = FedTrapExtractor()
    
    # Load data first to inspect columns
    extractor.load_data()
    
    print(f"\n  Available columns: {list(extractor.df.columns)}")
    print(f"\n  Sample data:")
    print(extractor.df.head())
    
    # Extract timeline
    timeline = extractor.extract_timeline()
    
    # Extract events
    events = extractor.extract_events(timeline)
    
    # Save outputs
    extractor.save_outputs(timeline, events)
    
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
