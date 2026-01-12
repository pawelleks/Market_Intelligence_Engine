#!/usr/bin/env python3
"""
Extract Signal Timelines for All 9 Economic Models

This script processes each model's data and creates:
1. Signal timeline (CLEAR/WARNING/TROUBLE over time)
2. Signal activation events (when TROUBLE turns on)

Uses thresholds from docs/audits/SIGNAL_DEFINITIONS.md
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYTICS_DIR = DATA_DIR / "analytics" / "macro"
OUTPUT_TIMELINE_DIR = DATA_DIR / "analysis" / "signal_timelines"
OUTPUT_EVENTS_DIR = DATA_DIR / "analysis" / "signal_events"

# Create output directories
OUTPUT_TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_EVENTS_DIR.mkdir(parents=True, exist_ok=True)


class SignalExtractor:
    """Base class for extracting signals from economic models."""
    
    def __init__(self, model_name, file_path, date_column='date'):
        self.model_name = model_name
        self.file_path = file_path
        self.date_column = date_column
        self.df = None
        
    def load_data(self):
        """Load model data from parquet file."""
        print(f"\n  Loading {self.model_name} data...")
        self.df = pd.read_parquet(self.file_path)
        
        # Handle DateTimeIndex
        if self.date_column not in self.df.columns:
            if isinstance(self.df.index, pd.DatetimeIndex):
                self.df = self.df.reset_index()
                if 'index' in self.df.columns:
                    self.df = self.df.rename(columns={'index': self.date_column})
        
        # Ensure date column is datetime
        if self.date_column in self.df.columns:
            self.df[self.date_column] = pd.to_datetime(self.df[self.date_column])
            self.df = self.df.sort_values(self.date_column).reset_index(drop=True)
        
        print(f"    Loaded {len(self.df)} observations")
        print(f"    Period: {self.df[self.date_column].min()} to {self.df[self.date_column].max()}")
        
    def classify_signal(self, row):
        """Override this method for each model's specific logic."""
        raise NotImplementedError("Subclass must implement classify_signal")
    
    def extract_timeline(self):
        """Create timeline with signal states."""
        timeline = pd.DataFrame()
        timeline['date'] = self.df[self.date_column]
        
        # Apply classification
        signals = self.df.apply(self.classify_signal, axis=1)
        timeline['signal_state'] = signals
        
        # Detect state changes
        timeline['signal_changed'] = timeline['signal_state'] != timeline['signal_state'].shift(1)
        timeline.loc[0, 'signal_changed'] = False  # First observation is not a change
        
        return timeline
    
    def extract_events(self, timeline):
        """Identify TROUBLE signal activation events."""
        events = []
        
        in_trouble = False
        trouble_start = None
        
        for idx, row in timeline.iterrows():
            date = row['date']
            state = row['signal_state']
            
            # TROUBLE signal activates
            if state == 'TROUBLE' and not in_trouble:
                in_trouble = True
                trouble_start = date
                
            # TROUBLE signal deactivates
            elif state != 'TROUBLE' and in_trouble:
                in_trouble = False
                duration_days = (date - trouble_start).days
                duration_months = round(duration_days / 30.44)
                
                events.append({
                    'event_date': trouble_start,
                    'end_date': date,
                    'duration_months': duration_months
                })
        
        # Handle case where dataset ends during TROUBLE
        if in_trouble and trouble_start is not None:
            end_date = timeline['date'].iloc[-1]
            duration_days = (end_date - trouble_start).days
            duration_months = round(duration_days / 30.44)
            
            events.append({
                'event_date': trouble_start,
                'end_date': end_date,
                'duration_months': duration_months,
                'ongoing': True
            })
        
        return pd.DataFrame(events)
    
    def save_outputs(self, timeline, events):
        """Save timeline and events to parquet files."""
        timeline_file = OUTPUT_TIMELINE_DIR / f"{self.model_name}_signals.parquet"
        events_file = OUTPUT_EVENTS_DIR / f"{self.model_name}_events.parquet"
        
        timeline.to_parquet(timeline_file, index=False)
        events.to_parquet(events_file, index=False)
        
        print(f"    ✅ Saved timeline: {len(timeline)} observations")
        print(f"    ✅ Saved events: {len(events)} TROUBLE periods")
        
        return timeline_file, events_file


class LEI_COI_Extractor(SignalExtractor):
    """Extract signals from Enhanced LEI/COI model."""
    
    def __init__(self):
        super().__init__(
            model_name='lei_coi',
            file_path=ANALYTICS_DIR / 'processed_lei_coi_enhanced.parquet'
        )
        
    def classify_signal(self, row):
        lei = row.get('LEI_Final', np.nan)
        
        if pd.isna(lei):
            return 'UNKNOWN'
        elif lei < -0.4:
            return 'TROUBLE'
        elif lei <= 0.4:
            return 'WARNING'
        else:
            return 'CLEAR'


class BusinessCycleExtractor(SignalExtractor):
    """Extract signals from Business Cycle Phase model."""
    
    def __init__(self):
        super().__init__(
            model_name='business_cycle',
            file_path=ANALYTICS_DIR / 'processed_business_cycle.parquet'
        )
        
    def classify_signal(self, row):
        phase = row.get('Cycle_Phase', None)
        
        if phase == 'Recession':
            return 'TROUBLE'
        elif phase == 'Slowdown':
            return 'WARNING'
        elif phase in ['Recovery', 'Expansion']:
            return 'CLEAR'
        else:
            return 'UNKNOWN'


class RecessionMomentumExtractor(SignalExtractor):
    """Extract signals from Recession Momentum (Stall Speed) model."""
    
    def __init__(self):
        super().__init__(
            model_name='recession_momentum',
            file_path=PROCESSED_DIR / 'recession_momentum.parquet'
        )
        
    def classify_signal(self, row):
        nfp_sma = row.get('nfp_sma_12m', np.nan)
        
        if pd.isna(nfp_sma):
            return 'UNKNOWN'
        elif nfp_sma < 97000:
            return 'TROUBLE'
        elif nfp_sma < 150000:
            return 'WARNING'
        else:
            return 'CLEAR'


class HamiltonExtractor(SignalExtractor):
    """Extract signals from Hamilton Markov Switching model."""
    
    def __init__(self):
        super().__init__(
            model_name='hamilton',
            file_path=PROCESSED_DIR / 'hamilton_model.parquet'
        )
        
    def classify_signal(self, row):
        prob = row.get('recession_prob', np.nan)
        
        if pd.isna(prob):
            return 'UNKNOWN'
        elif prob > 0.50:
            return 'TROUBLE'
        elif prob >= 0.25:
            return 'WARNING'
        else:
            return 'CLEAR'


class HPFilterExtractor(SignalExtractor):
    """Extract signals from HP Filter (Output Gaps) model."""
    
    def __init__(self):
        super().__init__(
            model_name='hp_filter',
            file_path=PROCESSED_DIR / 'hp_model.parquet'
        )
        
    def classify_signal(self, row):
        output_gap = row.get('output_gap', np.nan)
        credit_gap = row.get('credit_gap', np.nan)
        
        if pd.isna(output_gap) or pd.isna(credit_gap):
            return 'UNKNOWN'
        
        # TROUBLE: Large negative gaps
        if output_gap < -2.0 or credit_gap < -2.0:
            return 'TROUBLE'
        
        # WARNING: Moderate concerns
        if output_gap < -1.0 or output_gap > 1.5:
            return 'WARNING'
        
        # CLEAR: Stable
        return 'CLEAR'


class MinskyExtractor(SignalExtractor):
    """Extract signals from Minsky Financial Instability model."""
    
    def __init__(self):
        super().__init__(
            model_name='minsky',
            file_path=PROCESSED_DIR / 'minsky_model.parquet'
        )
        
    def classify_signal(self, row):
        instability_gap = row.get('minsky_instability_gap', np.nan)
        debt_service = row.get('debt_service_proxy', np.nan)
        risk_complacency = row.get('risk_complacency_index', np.nan)
        
        if pd.isna(instability_gap) or pd.isna(debt_service):
            return 'UNKNOWN'
        
        # TROUBLE: High financial fragility
        if instability_gap > 5.0 or debt_service > 30.0 or (not pd.isna(risk_complacency) and risk_complacency > 0.75):
            return 'TROUBLE'
        
        # WARNING: Speculative conditions
        if (0 < instability_gap < 5.0) or (25.0 < debt_service < 30.0):
            return 'WARNING'
        
        # CLEAR: Hedge finance
        return 'CLEAR'


class ABCTExtractor(SignalExtractor):
    """Extract signals from ABCT (Austrian Business Cycle Theory) model."""
    
    def __init__(self):
        super().__init__(
            model_name='abct',
            file_path=PROCESSED_DIR / 'abct_model.parquet'
        )
        
    def classify_signal(self, row):
        boom_score = row.get('abct_boom_score', np.nan)
        
        if pd.isna(boom_score):
            return 'UNKNOWN'
        elif boom_score > 1.0:
            return 'TROUBLE'
        elif boom_score > 0.5:
            return 'WARNING'
        else:
            return 'CLEAR'


class LAGExtractor(SignalExtractor):
    """Extract signals from LAG Index (Lagging Indicators) model."""
    
    def __init__(self):
        super().__init__(
            model_name='lag',
            file_path=PROCESSED_DIR / 'lag_model.parquet'
        )
        
    def classify_signal(self, row):
        lag_composite = row.get('lag_composite', np.nan)
        
        if pd.isna(lag_composite):
            return 'UNKNOWN'
        elif lag_composite > 1.0:
            return 'TROUBLE'
        elif lag_composite > 0.5:
            return 'WARNING'
        else:
            return 'CLEAR'


class FedTrapExtractor(SignalExtractor):
    """Extract signals from Fed Trap Divergence model.
    
    Fed Trap measures LEI vs LAG divergence:
    - Negative risk_spread = LEI falling faster than LAG = trouble brewing
    - This indicates leading indicators are deteriorating while lagging
      indicators haven't caught up yet (classic Fed Trap scenario)
    """
    
    def __init__(self):
        super().__init__(
            model_name='fed_trap',
            file_path=PROCESSED_DIR / 'fed_trap_divergence.parquet'
        )
        
    def classify_signal(self, row):
        risk_spread = row.get('risk_spread', np.nan)
        
        if pd.isna(risk_spread):
            return 'UNKNOWN'
        elif risk_spread < -0.5:  # Significant divergence
            return 'TROUBLE'
        elif risk_spread < 0:     # Mild divergence
            return 'WARNING'
        else:
            return 'CLEAR'


def main():
    print("="*70)
    print("EXTRACTING SIGNAL TIMELINES FOR ALL 9 ECONOMIC MODELS")
    print("="*70)
    
    # Define extractors in priority order (longest history first)
    extractors = [
        LEI_COI_Extractor(),
        ABCTExtractor(),
        RecessionMomentumExtractor(),
        HamiltonExtractor(),
        HPFilterExtractor(),
        BusinessCycleExtractor(),
        MinskyExtractor(),
        LAGExtractor(),
        FedTrapExtractor()
    ]
    
    results = []
    
    for extractor in extractors:
        print(f"\n{'='*70}")
        print(f"Processing: {extractor.model_name.upper()}")
        print(f"{'='*70}")
        
        try:
            # Load data
            extractor.load_data()
            
            # Extract timeline
            timeline = extractor.extract_timeline()
            
            # Extract events
            events = extractor.extract_events(timeline)
            
            # Add signal value for reference
            if 'LEI_Final' in extractor.df.columns:
                timeline = timeline.merge(
                    extractor.df[['date', 'LEI_Final']].rename(columns={'LEI_Final': 'signal_value'}),
                    on='date', how='left'
                )
            
            # Save outputs
            timeline_file, events_file = extractor.save_outputs(timeline, events)
            
            # Track progress
            results.append({
                'model': extractor.model_name,
                'observations': len(timeline),
                'trouble_events': len(events),
                'period_start': timeline['date'].min(),
                'period_end': timeline['date'].max()
            })
            
        except Exception as e:
            print(f"    ❌ Error processing {extractor.model_name}: {e}")
            continue
    
    # Print summary
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    
    summary_df = pd.DataFrame(results)
    print(f"\nProcessed {len(summary_df)} models:")
    for _, row in summary_df.iterrows():
        years = (row['period_end'] - row['period_start']).days / 365.25
        print(f"  {row['model']:20s}: {row['observations']:4d} obs, "
              f"{row['trouble_events']:2d} TROUBLE events, "
              f"{years:.1f} years")
    
    print(f"\nOutput directories:")
    print(f"  Timelines: {OUTPUT_TIMELINE_DIR}")
    print(f"  Events:    {OUTPUT_EVENTS_DIR}")


if __name__ == "__main__":
    main()
