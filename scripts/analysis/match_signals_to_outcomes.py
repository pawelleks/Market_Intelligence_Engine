#!/usr/bin/env python3
"""
Phase 3: Signal-to-Outcome Matching

Matches each model's TROUBLE signals to:
1. NBER recessions (lead times, hit rates, false positives)
2. S&P 500 performance (post-signal returns, drawdowns)
3. Blow-off top patterns (rallies before declines)

Outputs:
- data/analysis/recession_prediction/{model}_recession_analysis.parquet
- data/analysis/market_performance/{model}_market_analysis.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTCOMES_DIR = DATA_DIR / "outcomes"
EVENTS_DIR = DATA_DIR / "analysis" / "signal_events"
OUTPUT_RECESSION_DIR = DATA_DIR / "analysis" / "recession_prediction"
OUTPUT_MARKET_DIR = DATA_DIR / "analysis" / "market_performance"

# Create output directories
OUTPUT_RECESSION_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_MARKET_DIR.mkdir(parents=True, exist_ok=True)


class OutcomeAnalyzer:
    """Analyzes signal performance against recessions and markets."""
    
    def __init__(self):
        # Load outcome datasets
        print("Loading outcome datasets...")
        self.recessions = pd.read_parquet(OUTCOMES_DIR / "nber_recessions.parquet")
        self.sp500 = pd.read_parquet(OUTCOMES_DIR / "sp500_returns.parquet")
        
        # Ensure datetime types
        self.recessions['start_date'] = pd.to_datetime(self.recessions['start_date'])
        self.recessions['end_date'] = pd.to_datetime(self.recessions['end_date'])
        self.sp500['date'] = pd.to_datetime(self.sp500['date'])
        
        print(f"  Loaded {len(self.recessions)} NBER recessions")
        print(f"  Loaded {len(self.sp500)} S&P 500 observations")
    
    def analyze_recession_prediction(self, model_name, events_df):
        """
        Analyze how well signals predict recessions.
        
        Returns DataFrame with:
        - recession_id
        - recession_start
        - signal_activated (bool)
        - signal_date
        - lead_time_months
        - signal_value_at_activation
        """
        print(f"\n  Analyzing recession prediction for {model_name}...")
        
        if events_df.empty:
            print(f"    No TROUBLE events for {model_name}")
            return pd.DataFrame()
        
        # Ensure datetime
        events_df['event_date'] = pd.to_datetime(events_df['event_date'])
        
        # Get recessions within model's date range
        model_start = events_df['event_date'].min()
        model_end = events_df['event_date'].max()
        
        # Filter recessions that fall within or near model's period
        # Include recessions that started within 2 years after model period
        # (to catch signals that might predict beyond data range)
        relevant_recessions = self.recessions[
            (self.recessions['start_date'] >= model_start - pd.DateOffset(years=2)) &
            (self.recessions['start_date'] <= model_end + pd.DateOffset(years=2))
        ].copy()
        
        print(f"    Found {len(relevant_recessions)} recessions in model period")
        
        results = []
        
        for _, recession in relevant_recessions.iterrows():
            recession_start = recession['start_date']
            recession_id = recession['recession_id']
            
            # Find signals that occurred BEFORE this recession
            # Look for signals up to 36 months before recession start
            lookback_window = recession_start - pd.DateOffset(months=36)
            
            prior_signals = events_df[
                (events_df['event_date'] >= lookback_window) &
                (events_df['event_date'] < recession_start)
            ]
            
            if len(prior_signals) > 0:
                # Take the LATEST signal before recession (most relevant)
                latest_signal = prior_signals.loc[prior_signals['event_date'].idxmax()]
                
                signal_date = latest_signal['event_date']
                lead_time_days = (recession_start - signal_date).days
                lead_time_months = round(lead_time_days / 30.44)
                
                results.append({
                    'recession_id': recession_id,
                    'recession_start': recession_start,
                    'recession_end': recession['end_date'],
                    'signal_activated': True,
                    'signal_date': signal_date,
                    'lead_time_days': lead_time_days,
                    'lead_time_months': lead_time_months,
                    'signal_duration_months': latest_signal.get('duration_months', np.nan)
                })
            else:
                # Recession not predicted
                results.append({
                    'recession_id': recession_id,
                    'recession_start': recession_start,
                    'recession_end': recession['end_date'],
                    'signal_activated': False,
                    'signal_date': pd.NaT,
                    'lead_time_days': np.nan,
                    'lead_time_months': np.nan,
                    'signal_duration_months': np.nan
                })
        
        results_df = pd.DataFrame(results)
        
        # Calculate summary statistics
        if len(results_df) > 0:
            hit_rate = (results_df['signal_activated'].sum() / len(results_df)) * 100
            avg_lead = results_df[results_df['signal_activated']]['lead_time_months'].mean()
            
            print(f"    Hit Rate: {hit_rate:.1f}% ({results_df['signal_activated'].sum()}/{len(results_df)} recessions)")
            if not np.isnan(avg_lead):
                print(f"    Avg Lead Time: {avg_lead:.1f} months")
        
        return results_df
    
    def calculate_false_positives(self, model_name, events_df, recession_analysis_df):
        """
        Identify false positive signals (no recession within 24 months).
        
        Returns: false positive count and rate
        """
        print(f"\n  Calculating false positives for {model_name}...")
        
        if events_df.empty:
            return 0, 0.0
        
        events_df['event_date'] = pd.to_datetime(events_df['event_date'])
        
        false_positives = 0
        total_signals = len(events_df)
        
        for _, signal in events_df.iterrows():
            signal_date = signal['event_date']
            
            # Check if ANY recession started within 24 months after signal
            future_recessions = self.recessions[
                (self.recessions['start_date'] > signal_date) &
                (self.recessions['start_date'] <= signal_date + pd.DateOffset(months=24))
            ]
            
            if len(future_recessions) == 0:
                false_positives += 1
        
        fp_rate = (false_positives / total_signals * 100) if total_signals > 0 else 0
        
        print(f"    False Positives: {false_positives}/{total_signals} signals ({fp_rate:.1f}%)")
        
        return false_positives, fp_rate
    
    def analyze_market_performance(self, model_name, events_df):
        """
        Analyze S&P 500 performance after each signal.
        
        Returns DataFrame with:
        - signal_date
        - sp500_at_signal
        - return_6m, return_12m, return_24m
        - max_drawdown
        - months_to_bottom
        """
        print(f"\n  Analyzing market performance for {model_name}...")
        
        if events_df.empty:
            print(f"    No TROUBLE events for {model_name}")
            return pd.DataFrame()
        
        events_df['event_date'] = pd.to_datetime(events_df['event_date'])
        
        results = []
        
        for _, signal in events_df.iterrows():
            signal_date = signal['event_date']
            
            # Find S&P 500 price at or near signal date
            # Allow 5-day window to handle weekends/holidays
            sp_at_signal = self.sp500[
                (self.sp500['date'] >= signal_date - timedelta(days=5)) &
                (self.sp500['date'] <= signal_date + timedelta(days=5))
            ]
            
            if len(sp_at_signal) == 0:
                print(f"    Warning: No S&P 500 data for signal on {signal_date}")
                continue
            
            # Take closest date
            sp_at_signal = sp_at_signal.iloc[0]
            signal_price = sp_at_signal['close']
            
            # Get forward returns from pre-calculated columns
            return_6m = sp_at_signal['return_6m']
            return_12m = sp_at_signal['return_12m']
            return_24m = sp_at_signal['return_24m']
            
            # Calculate max drawdown in next 24 months
            future_prices = self.sp500[
                (self.sp500['date'] > signal_date) &
                (self.sp500['date'] <= signal_date + pd.DateOffset(months=24))
            ]
            
            if len(future_prices) > 0:
                lowest_price = future_prices['close'].min()
                max_drawdown = ((lowest_price / signal_price) - 1) * 100
                
                # Find date of bottom
                bottom_idx = future_prices['close'].idxmin()
                bottom_date = future_prices.loc[bottom_idx, 'date']
                months_to_bottom = (bottom_date - signal_date).days / 30.44
                
                # Check for "blow-off top" - did market rally first?
                highest_price = future_prices['close'].max()
                peak_return = ((highest_price / signal_price) - 1) * 100
                
                if peak_return > 5:  # Rally of >5% before decline
                    peak_idx = future_prices['close'].idxmax()
                    peak_date = future_prices.loc[peak_idx, 'date']
                    months_to_peak = (peak_date - signal_date).days / 30.44
                else:
                    peak_return = np.nan
                    months_to_peak = np.nan
            else:
                max_drawdown = np.nan
                months_to_bottom = np.nan
                peak_return = np.nan
                months_to_peak = np.nan
            
            results.append({
                'signal_date': signal_date,
                'sp500_at_signal': signal_price,
                'return_6m': return_6m,
                'return_12m': return_12m,
                'return_24m': return_24m,
                'max_drawdown': max_drawdown,
                'months_to_bottom': months_to_bottom,
                'blowoff_peak_return': peak_return,
                'months_to_blowoff_peak': months_to_peak
            })
        
        results_df = pd.DataFrame(results)
        
        # Summary statistics
        if len(results_df) > 0:
            avg_12m = results_df['return_12m'].mean()
            avg_dd = results_df['max_drawdown'].mean()
            blowoffs = results_df['blowoff_peak_return'].notna().sum()
            
            print(f"    Avg 12m Return: {avg_12m:.1f}%")
            print(f"    Avg Max Drawdown: {avg_dd:.1f}%")
            print(f"    Blow-off Tops: {blowoffs}/{len(results_df)} signals")
        
        return results_df
    
    def process_model(self, model_name):
        """Process all analyses for a single model."""
        print(f"\n{'='*70}")
        print(f"ANALYZING: {model_name.upper()}")
        print(f"{'='*70}")
        
        # Load signal events
        events_file = EVENTS_DIR / f"{model_name}_events.parquet"
        
        if not events_file.exists():
            print(f"  Warning: Events file not found for {model_name}")
            return
        
        events_df = pd.read_parquet(events_file)
        print(f"  Loaded {len(events_df)} TROUBLE events")
        
        # 1. Recession Prediction Analysis
        recession_analysis = self.analyze_recession_prediction(model_name, events_df)
        
        # 2. False Positive Calculation
        fp_count, fp_rate = self.calculate_false_positives(model_name, events_df, recession_analysis)
        
        # 3. Market Performance Analysis
        market_analysis = self.analyze_market_performance(model_name, events_df)
        
        # Save outputs
        if not recession_analysis.empty:
            rec_file = OUTPUT_RECESSION_DIR / f"{model_name}_recession_analysis.parquet"
            recession_analysis.to_parquet(rec_file, index=False)
            print(f"\n  ✅ Saved recession analysis: {rec_file.name}")
        
        if not market_analysis.empty:
            mkt_file = OUTPUT_MARKET_DIR / f"{model_name}_market_analysis.parquet"
            market_analysis.to_parquet(mkt_file, index=False)
            print(f"  ✅ Saved market analysis: {mkt_file.name}")
        
        # Create summary stats file
        summary = {
            'model': model_name,
            'total_signals': len(events_df),
            'recessions_analyzed': len(recession_analysis),
            'recessions_caught': recession_analysis['signal_activated'].sum() if not recession_analysis.empty else 0,
            'hit_rate_pct': (recession_analysis['signal_activated'].sum() / len(recession_analysis) * 100) if len(recession_analysis) > 0 else np.nan,
            'avg_lead_time_months': recession_analysis[recession_analysis['signal_activated']]['lead_time_months'].mean() if not recession_analysis.empty else np.nan,
            'false_positives': fp_count,
            'false_positive_rate_pct': fp_rate,
            'avg_12m_return': market_analysis['return_12m'].mean() if not market_analysis.empty else np.nan,
            'avg_max_drawdown': market_analysis['max_drawdown'].mean() if not market_analysis.empty else np.nan,
            'blowoff_tops': market_analysis['blowoff_peak_return'].notna().sum() if not market_analysis.empty else 0
        }
        
        return summary


def main():
    print("="*70)
    print("PHASE 3: SIGNAL-TO-OUTCOME MATCHING")
    print("="*70)
    
    analyzer = OutcomeAnalyzer()
    
    # Process all models
    models = [
        'lei_coi',
        'abct',
        'recession_momentum',
        'hamilton',
        'hp_filter',
        'business_cycle',
        'minsky',
        'lag',
        'fed_trap'
    ]
    
    summaries = []
    
    for model in models:
        try:
            summary = analyzer.process_model(model)
            if summary:
                summaries.append(summary)
        except Exception as e:
            print(f"  ❌ Error processing {model}: {e}")
            continue
    
    # Create overall summary
    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE - SUMMARY")
    print(f"{'='*70}\n")
    
    summary_df = pd.DataFrame(summaries)
    summary_file = OUTPUT_RECESSION_DIR / "_overall_summary.parquet"
    summary_df.to_parquet(summary_file, index=False)
    
    # Print summary table
    print("Model Performance Summary:")
    print("-" * 70)
    for _, row in summary_df.iterrows():
        print(f"{row['model']:20s}: Hit Rate: {row['hit_rate_pct']:.1f}%, "
              f"Lead: {row['avg_lead_time_months']:.1f}mo, "
              f"FP: {row['false_positive_rate_pct']:.1f}%, "
              f"12m Return: {row['avg_12m_return']:.1f}%")
    
    print(f"\n✅ Overall summary saved: {summary_file}")
    print(f"\nOutput directories:")
    print(f"  Recession Analysis: {OUTPUT_RECESSION_DIR}")
    print(f"  Market Analysis: {OUTPUT_MARKET_DIR}")


if __name__ == "__main__":
    main()
