#!/usr/bin/env python3
"""
Phase 4: Comparative Analysis

Creates:
1. Model Performance Scorecard - consolidated metrics for all models
2. Signal Correlation Matrix - how often models agree on TROUBLE signals

Outputs:
- data/analysis/model_comparison/performance_scorecard.parquet
- data/analysis/model_comparison/signal_correlation.parquet
- data/analysis/model_comparison/model_clusters.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from itertools import combinations

# Load environment variables
load_dotenv()

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
TIMELINES_DIR = ANALYSIS_DIR / "signal_timelines"
RECESSION_DIR = ANALYSIS_DIR / "recession_prediction"
MARKET_DIR = ANALYSIS_DIR / "market_performance"
OUTPUT_DIR = ANALYSIS_DIR / "model_comparison"

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ComparativeAnalyzer:
    """Analyzes model performance comparatively."""
    
    def __init__(self):
        print("Loading analysis results...")
        
        # Load Phase 3 summary
        self.summary = pd.read_parquet(RECESSION_DIR / "_overall_summary.parquet")
        print(f"  Loaded summary for {len(self.summary)} models")
        
        # Load all signal timelines
        self.timelines = {}
        for model_file in TIMELINES_DIR.glob("*_signals.parquet"):
            model_name = model_file.stem.replace('_signals', '')
            df = pd.read_parquet(model_file)
            df['date'] = pd.to_datetime(df['date'])
            self.timelines[model_name] = df
            print(f"  Loaded timeline for {model_name}: {len(df)} observations")
    
    def create_performance_scorecard(self):
        """
        Create comprehensive performance scorecard.
        
        Includes:
        - Recession prediction metrics
        - Market performance metrics
        - Data coverage
        - Signal characteristics
        """
        print("\n" + "="*70)
        print("CREATING PERFORMANCE SCORECARD")
        print("="*70)
        
        scorecard = self.summary.copy()
        
        # Add data coverage metrics
        coverage_stats = []
        for model in scorecard['model']:
            if model in self.timelines:
                timeline = self.timelines[model]
                coverage_stats.append({
                    'model': model,
                    'total_observations': len(timeline),
                    'period_start': timeline['date'].min(),
                    'period_end': timeline['date'].max(),
                    'years_coverage': (timeline['date'].max() - timeline['date'].min()).days / 365.25,
                    'trouble_periods': (timeline['signal_state'] == 'TROUBLE').sum(),
                    'warning_periods': (timeline['signal_state'] == 'WARNING').sum(),
                    'clear_periods': (timeline['signal_state'] == 'CLEAR').sum(),
                    'trouble_pct': (timeline['signal_state'] == 'TROUBLE').sum() / len(timeline) * 100
                })
        
        coverage_df = pd.DataFrame(coverage_stats)
        
        # Merge with summary
        scorecard = scorecard.merge(coverage_df, on='model', how='left')
        
        # Calculate composite scores
        # Score 1: Precision Score (inverse of FP rate, weighted by hit rate)
        scorecard['precision_score'] = (
            (100 - scorecard['false_positive_rate_pct']) * 
            (scorecard['hit_rate_pct'] / 100)
        ) / 100
        
        # Score 2: Lead Time Score (normalized to 0-100, optimal = 12 months)
        scorecard['lead_time_score'] = scorecard['avg_lead_time_months'].apply(
            lambda x: 100 - abs(x - 12) * 5 if not pd.isna(x) else np.nan
        )
        scorecard['lead_time_score'] = scorecard['lead_time_score'].clip(0, 100)
        
        # Score 3: Market Impact Score (how predictive of market decline)
        # Negative returns = good prediction, positive = blow-off top issue
        scorecard['market_impact_score'] = scorecard['avg_12m_return'].apply(
            lambda x: max(0, -x * 5) if not pd.isna(x) else np.nan
        )
        scorecard['market_impact_score'] = scorecard['market_impact_score'].clip(0, 100)
        
        # Overall Composite Score (average of sub-scores)
        scorecard['overall_score'] = scorecard[
            ['precision_score', 'lead_time_score', 'market_impact_score']
        ].mean(axis=1)
        
        # Rank models
        scorecard['rank'] = scorecard['overall_score'].rank(ascending=False)
        
        # Sort by rank
        scorecard = scorecard.sort_values('rank')
        
        # Save scorecard
        output_file = OUTPUT_DIR / "performance_scorecard.parquet"
        scorecard.to_parquet(output_file, index=False)
        
        print(f"\n✅ Performance Scorecard saved: {output_file.name}")
        print("\nTop 5 Models by Overall Score:")
        print("-" * 70)
        for _, row in scorecard.head(5).iterrows():
            print(f"  {row['rank']:.0f}. {row['model']:20s} - Score: {row['overall_score']:.1f} "
                  f"(Hit: {row['hit_rate_pct']:.1f}%, FP: {row['false_positive_rate_pct']:.1f}%)")
        
        return scorecard
    
    def create_signal_correlation_matrix(self):
        """
        Analyze how often models agree on TROUBLE signals.
        
        Creates correlation matrix showing % agreement between models.
        """
        print("\n" + "="*70)
        print("CREATING SIGNAL CORRELATION MATRIX")
        print("="*70)
        
        # Find common date range across all models
        print("\n  Finding common date range...")
        all_dates = set()
        for model, timeline in self.timelines.items():
            all_dates.update(timeline['date'].dt.date)
        
        # Create date range from min to max
        min_date = min(all_dates)
        max_date = max(all_dates)
        
        # For each model, create a binary TROUBLE indicator by date
        model_signals = {}
        
        for model, timeline in self.timelines.items():
            # Create date-indexed series
            timeline_indexed = timeline.set_index('date')
            timeline_indexed['is_trouble'] = (timeline_indexed['signal_state'] == 'TROUBLE').astype(int)
            
            # Resample to monthly frequency to align all models
            monthly = timeline_indexed['is_trouble'].resample('MS').max()
            model_signals[model] = monthly
        
        # Combine all model signals into a DataFrame
        signals_df = pd.DataFrame(model_signals)
        
        # Fill NaN with 0 (no signal if model doesn't have data for that period)
        signals_df = signals_df.fillna(0)
        
        print(f"  Analyzing {len(signals_df)} months across {len(model_signals)} models")
        
        # Calculate pairwise correlation (agreement rate)
        correlation_results = []
        
        model_list = list(model_signals.keys())
        
        for model_a, model_b in combinations(model_list, 2):
            # Get signals for both models
            sig_a = signals_df[model_a]
            sig_b = signals_df[model_b]
            
            # Only consider months where both models have data (not NaN before filling)
            valid_mask = (sig_a.notna()) & (sig_b.notna())
            
            if valid_mask.sum() == 0:
                continue
            
            # Calculate agreement
            both_trouble = ((sig_a == 1) & (sig_b == 1)).sum()
            both_clear = ((sig_a == 0) & (sig_b == 0)).sum()
            total_months = valid_mask.sum()
            
            agreement_pct = (both_trouble + both_clear) / total_months * 100
            
            # Calculate conditional probability: P(B=TROUBLE | A=TROUBLE)
            a_trouble_count = (sig_a == 1).sum()
            if a_trouble_count > 0:
                p_b_given_a = both_trouble / a_trouble_count * 100
            else:
                p_b_given_a = np.nan
            
            correlation_results.append({
                'model_a': model_a,
                'model_b': model_b,
                'overlap_months': total_months,
                'both_trouble': both_trouble,
                'agreement_pct': agreement_pct,
                'p_b_trouble_given_a_trouble': p_b_given_a
            })
        
        correlation_df = pd.DataFrame(correlation_results)
        
        # Save correlation matrix
        output_file = OUTPUT_DIR / "signal_correlation.parquet"
        correlation_df.to_parquet(output_file, index=False)
        
        print(f"\n✅ Signal Correlation Matrix saved: {output_file.name}")
        print(f"  Analyzed {len(correlation_df)} model pairs")
        
        # Identify highly correlated pairs (>70% agreement)
        high_correlation = correlation_df[correlation_df['agreement_pct'] > 70].sort_values('agreement_pct', ascending=False)
        
        if len(high_correlation) > 0:
            print("\nHighly Correlated Model Pairs (>70% agreement):")
            print("-" * 70)
            for _, row in high_correlation.head(10).iterrows():
                print(f"  {row['model_a']:20s} <-> {row['model_b']:20s}: {row['agreement_pct']:.1f}% "
                      f"({row['both_trouble']} shared TROUBLE periods)")
        
        # Identify independent pairs (<50% agreement)
        independent = correlation_df[correlation_df['agreement_pct'] < 50].sort_values('agreement_pct')
        
        if len(independent) > 0:
            print("\nIndependent Model Pairs (<50% agreement - good for diversification):")
            print("-" * 70)
            for _, row in independent.head(10).iterrows():
                print(f"  {row['model_a']:20s} <-> {row['model_b']:20s}: {row['agreement_pct']:.1f}%")
        
        return correlation_df
    
    def identify_model_clusters(self, correlation_df):
        """
        Identify clusters of models that tend to signal together.
        
        Uses agreement percentages to group models.
        """
        print("\n" + "="*70)
        print("IDENTIFYING MODEL CLUSTERS")
        print("="*70)
        
        # Simple clustering based on average agreement
        model_list = list(self.timelines.keys())
        
        # Calculate average agreement for each model
        model_avg_agreement = []
        
        for model in model_list:
            # Get all pairs involving this model
            pairs = correlation_df[
                (correlation_df['model_a'] == model) | 
                (correlation_df['model_b'] == model)
            ]
            
            avg_agreement = pairs['agreement_pct'].mean() if len(pairs) > 0 else np.nan
            
            model_avg_agreement.append({
                'model': model,
                'avg_agreement_with_others': avg_agreement,
                'high_correlation_pairs': len(pairs[pairs['agreement_pct'] > 70]),
                'independent_pairs': len(pairs[pairs['agreement_pct'] < 50])
            })
        
        clusters_df = pd.DataFrame(model_avg_agreement)
        clusters_df = clusters_df.sort_values('avg_agreement_with_others', ascending=False)
        
        # Classify models
        clusters_df['cluster_type'] = clusters_df['avg_agreement_with_others'].apply(
            lambda x: 'Highly Correlated (>60%)' if x > 60 
            else 'Moderately Correlated (40-60%)' if x > 40
            else 'Independent (<40%)'
        )
        
        # Save clusters
        output_file = OUTPUT_DIR / "model_clusters.parquet"
        clusters_df.to_parquet(output_file, index=False)
        
        print(f"\n✅ Model Clusters saved: {output_file.name}")
        print("\nModel Classification:")
        print("-" * 70)
        for _, row in clusters_df.iterrows():
            print(f"  {row['model']:20s}: {row['cluster_type']:30s} "
                  f"(avg: {row['avg_agreement_with_others']:.1f}%)")
        
        return clusters_df
    
    def recommend_composite_strategy(self, scorecard, correlation_df, clusters_df):
        """
        Recommend optimal model combinations for composite signals.
        """
        print("\n" + "="*70)
        print("COMPOSITE SIGNAL RECOMMENDATIONS")
        print("="*70)
        
        # Strategy 1: Best single model (highest overall score)
        best_model = scorecard.iloc[0]
        print(f"\n1. SINGLE MODEL STRATEGY:")
        print(f"   Use: {best_model['model']}")
        print(f"   Score: {best_model['overall_score']:.1f}")
        print(f"   Hit Rate: {best_model['hit_rate_pct']:.1f}%, FP Rate: {best_model['false_positive_rate_pct']:.1f}%")
        
        # Strategy 2: Dual confirmation (best model + most independent)
        best_independent_pair = correlation_df.sort_values('agreement_pct').head(1).iloc[0]
        print(f"\n2. DUAL CONFIRMATION STRATEGY (Most Independent):")
        print(f"   Use: {best_independent_pair['model_a']} + {best_independent_pair['model_b']}")
        print(f"   Agreement: {best_independent_pair['agreement_pct']:.1f}%")
        print(f"   Rationale: Low correlation = independent confirmation")
        
        # Strategy 3: Ensemble of top performers
        top3 = scorecard.head(3)
        print(f"\n3. ENSEMBLE STRATEGY (Top 3 Performers):")
        print(f"   Use: {', '.join(top3['model'].tolist())}")
        print(f"   Avg Score: {top3['overall_score'].mean():.1f}")
        print(f"   Trigger: 2 out of 3 models signal TROUBLE")
        
        # Strategy 4: Early warning + Late confirmation
        early_models = scorecard[scorecard['avg_lead_time_months'] > 15].head(2)
        late_models = scorecard[scorecard['avg_lead_time_months'] < 10].head(2)
        
        if len(early_models) > 0 and len(late_models) > 0:
            print(f"\n4. TIERED STRATEGY (Early Warning + Late Confirmation):")
            print(f"   Early Warning: {', '.join(early_models['model'].tolist())}")
            print(f"   Late Confirmation: {', '.join(late_models['model'].tolist())}")
            print(f"   Rationale: Early signals for positioning, late signals for action")


def main():
    print("="*70)
    print("PHASE 4: COMPARATIVE ANALYSIS")
    print("="*70)
    
    analyzer = ComparativeAnalyzer()
    
    # Task 4.1: Create Performance Scorecard
    scorecard = analyzer.create_performance_scorecard()
    
    # Task 4.2: Create Signal Correlation Matrix
    correlation = analyzer.create_signal_correlation_matrix()
    
    # Bonus: Identify Model Clusters
    clusters = analyzer.identify_model_clusters(correlation)
    
    # Bonus: Recommend Composite Strategies
    analyzer.recommend_composite_strategy(scorecard, correlation, clusters)
    
    print("\n" + "="*70)
    print("PHASE 4 COMPLETE")
    print("="*70)
    print(f"\nOutput files:")
    print(f"  - performance_scorecard.parquet")
    print(f"  - signal_correlation.parquet")
    print(f"  - model_clusters.parquet")


if __name__ == "__main__":
    main()
