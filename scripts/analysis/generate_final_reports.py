#!/usr/bin/env python3
"""
Phase 5: Visualization & Reporting

Generates:
1. Individual model reports (markdown)
2. Comparative dashboard data (JSON)

Outputs:
- docs/analysis/model_reports/{model}_PREDICTION_REPORT.md (9 files)
- data/analysis/dashboard/model_comparison.json
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PUBLIC_DOCS_DIR = PROJECT_ROOT / "public_docs"  # Updated to public_docs
ANALYSIS_DIR = DATA_DIR / "analysis"
RECESSION_DIR = ANALYSIS_DIR / "recession_prediction"
MARKET_DIR = ANALYSIS_DIR / "market_performance"
COMPARISON_DIR = ANALYSIS_DIR / "model_comparison"
TIMELINES_DIR = ANALYSIS_DIR / "signal_timelines"
EVENTS_DIR = ANALYSIS_DIR / "signal_events"

OUTPUT_REPORTS_DIR = PUBLIC_DOCS_DIR / "analysis" / "model_reports"
OUTPUT_DASHBOARD_DIR = ANALYSIS_DIR / "dashboard"

# Create output directories
OUTPUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)


class ReportGenerator:
    """Generates model reports and dashboard data."""
    
    def __init__(self):
        print("Loading all analysis data...")
        
        # Load scorecard
        self.scorecard = pd.read_parquet(COMPARISON_DIR / "performance_scorecard.parquet")
        
        # Store model data
        self.model_data = {}
        
        for model in self.scorecard['model']:
            data = {'model': model}
            
            # Load recession analysis
            rec_file = RECESSION_DIR / f"{model}_recession_analysis.parquet"
            if rec_file.exists():
                data['recession_analysis'] = pd.read_parquet(rec_file)
            
            # Load market analysis
            mkt_file = MARKET_DIR / f"{model}_market_analysis.parquet"
            if mkt_file.exists():
                data['market_analysis'] = pd.read_parquet(mkt_file)
            
            # Load events
            evt_file = EVENTS_DIR / f"{model}_events.parquet"
            if evt_file.exists():
                data['events'] = pd.read_parquet(evt_file)
            
            # Load timeline
            tl_file = TIMELINES_DIR / f"{model}_signals.parquet"
            if tl_file.exists():
                data['timeline'] = pd.read_parquet(tl_file)
            
            self.model_data[model] = data
        
        print(f"  Loaded data for {len(self.model_data)} models")
    
    def generate_model_report(self, model_name):
        """Generate detailed markdown report for a single model."""
        
        print(f"\n  Generating report for {model_name}...")
        
        # Get model data
        data = self.model_data.get(model_name, {})
        scorecard_row = self.scorecard[self.scorecard['model'] == model_name].iloc[0]
        
        # Create report content
        report = f"""# {model_name.upper().replace('_', ' ')} - Prediction Analysis Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**Analysis Period**: {scorecard_row.get('period_start', 'N/A')} to {scorecard_row.get('period_end', 'N/A')}  
**Data Coverage**: {scorecard_row.get('years_coverage', 0):.1f} years

---

## Executive Summary

**Overall Performance Rank**: #{scorecard_row['rank']:.0f} out of 9 models  
**Overall Score**: {scorecard_row['overall_score']:.1f}/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | {scorecard_row['hit_rate_pct']:.1f}% | {"✅ Excellent" if scorecard_row['hit_rate_pct'] > 60 else "⚠️ Good" if scorecard_row['hit_rate_pct'] > 40 else "❌ Poor"} |
| **False Positive Rate** | {scorecard_row['false_positive_rate_pct']:.1f}% | {"✅ Excellent" if scorecard_row['false_positive_rate_pct'] < 55 else "⚠️ Acceptable" if scorecard_row['false_positive_rate_pct'] < 75 else "❌ High"} |
| **Average Lead Time** | {scorecard_row['avg_lead_time_months']:.1f} months | {"✅ Optimal" if 8 <= scorecard_row['avg_lead_time_months'] <= 15 else "⚠️ Acceptable" if scorecard_row['avg_lead_time_months'] < 20 else "❌ Too Early"} |
| **Avg 12m Return After Signal** | {scorecard_row['avg_12m_return']:.1f}% | {"✅ Predictive" if scorecard_row['avg_12m_return'] < 0 else "⚠️ Blow-off Top Pattern"} |
| **Total Signals Generated** | {scorecard_row['total_signals']:.0f} | - |
| **Recessions Analyzed** | {scorecard_row['recessions_analyzed']:.0f} | - |
| **Recessions Caught** | {scorecard_row['recessions_caught']:.0f} | - |

---

## Recession Prediction Performance

"""
        
        # Add recession analysis section
        if 'recession_analysis' in data and not data['recession_analysis'].empty:
            rec_df = data['recession_analysis']
            
            report += f"""### Summary Statistics

- **Hit Rate**: {scorecard_row['hit_rate_pct']:.1f}% ({scorecard_row['recessions_caught']:.0f} of {scorecard_row['recessions_analyzed']:.0f} recessions predicted)
- **Average Lead Time**: {scorecard_row['avg_lead_time_months']:.1f} months
- **Lead Time Range**: {rec_df[rec_df['signal_activated']]['lead_time_months'].min():.0f} to {rec_df[rec_df['signal_activated']]['lead_time_months'].max():.0f} months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
"""
            
            for _, row in rec_df.iterrows():
                signal_status = "✅ Yes" if row['signal_activated'] else "❌ No"
                lead_time = f"{row['lead_time_months']:.0f}mo" if row['signal_activated'] else "N/A"
                assessment = ""
                
                if row['signal_activated']:
                    if row['lead_time_months'] < 6:
                        assessment = "Late warning"
                    elif row['lead_time_months'] <= 15:
                        assessment = "Good timing"
                    else:
                        assessment = "Very early"
                else:
                    assessment = "Missed"
                
                report += f"| {row['recession_id']} | {row['recession_start'].strftime('%Y-%m')} | {signal_status} | {lead_time} | {assessment} |\n"
            
            report += "\n"
        else:
            report += "No recession analysis data available.\n\n"
        
        # Add false positives section
        report += f"""### False Positive Analysis

**False Positive Rate**: {scorecard_row['false_positive_rate_pct']:.1f}% ({scorecard_row['false_positives']:.0f} of {scorecard_row['total_signals']:.0f} signals)

"""
        
        if scorecard_row['false_positive_rate_pct'] < 55:
            report += "**Assessment**: ✅ **Excellent precision** - This model has the lowest false positive rate, making it highly reliable for actionable signals.\n\n"
        elif scorecard_row['false_positive_rate_pct'] < 75:
            report += "**Assessment**: ⚠️ **Acceptable precision** - False positive rate is moderate. Use in combination with other models for confirmation.\n\n"
        else:
            report += "**Assessment**: ❌ **High false positive rate** - This model triggers frequently without recessions. Best used as an early warning system, not a definitive signal.\n\n"
        
        # Add market performance section
        report += """---

## Market Performance After Signals

"""
        
        if 'market_analysis' in data and not data['market_analysis'].empty:
            mkt_df = data['market_analysis']
            
            report += f"""### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | {mkt_df['return_6m'].mean():.1f}% | {mkt_df['return_6m'].min():.1f}% | {mkt_df['return_6m'].max():.1f}% |
| **12 Months** | {mkt_df['return_12m'].mean():.1f}% | {mkt_df['return_12m'].min():.1f}% | {mkt_df['return_12m'].max():.1f}% |
| **24 Months** | {mkt_df['return_24m'].mean():.1f}% | {mkt_df['return_24m'].min():.1f}% | {mkt_df['return_24m'].max():.1f}% |

### Drawdown Analysis

- **Average Max Drawdown**: {mkt_df['max_drawdown'].mean():.1f}%
- **Worst Drawdown**: {mkt_df['max_drawdown'].min():.1f}%
- **Average Time to Bottom**: {mkt_df['months_to_bottom'].mean():.1f} months

### Blow-off Top Analysis

"""
            
            blowoff_count = mkt_df['blowoff_peak_return'].notna().sum()
            blowoff_rate = (blowoff_count / len(mkt_df) * 100) if len(mkt_df) > 0 else 0
            
            report += f"""**Blow-off Tops Detected**: {blowoff_count} out of {len(mkt_df)} signals ({blowoff_rate:.1f}%)

"""
            
            if blowoff_rate > 80:
                avg_peak = mkt_df['blowoff_peak_return'].mean()
                avg_time = mkt_df['months_to_blowoff_peak'].mean()
                report += f"""⚠️ **High Blow-off Top Rate**: Markets rallied **{avg_peak:.1f}% on average** in the **{avg_time:.1f} months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

"""
            elif blowoff_rate > 50:
                report += f"""⚠️ **Moderate Blow-off Top Risk**: About half of signals were followed by market rallies before eventual declines.

**Implication**: Mixed behavior - some signals led to immediate declines, others had blow-off tops.

**Trading Strategy**: Monitor other models for confirmation before taking action.

"""
            else:
                report += f"""✅ **Low Blow-off Top Risk**: This model's signals tend to be followed by actual market declines without significant rallies.

**Implication**: More directly predictive of market downturns.

**Trading Strategy**: Can be used more tactically for market timing and hedging.

"""
        else:
            report += "No market performance data available.\n\n"
            blowoff_rate = 0  # Default value when no market data
        
        # Add signal characteristics section
        report += f"""---

## Signal Characteristics

**Total Observations**: {scorecard_row['total_observations']:.0f}  
**TROUBLE Periods**: {scorecard_row['trouble_periods']:.0f} ({scorecard_row['trouble_pct']:.1f}% of time)  
**WARNING Periods**: {scorecard_row['warning_periods']:.0f}  
**CLEAR Periods**: {scorecard_row['clear_periods']:.0f}

"""
        
        # Add recommendations section
        report += """---

## Key Findings & Recommendations

"""
        
        # Customize recommendations based on model performance
        if scorecard_row['rank'] <= 3:
            report += f"""### ⭐ Top Performer

This model ranks in the **top 3** of all tested models. 

"""
        
        if scorecard_row['false_positive_rate_pct'] < 55:
            report += """### Strength: Low False Positive Rate

- ✅ Best used for **high-conviction signals**
- ✅ Suitable for tactical trading and risk reduction
- ✅ When this model signals TROUBLE, take it seriously

"""
        
        if scorecard_row['hit_rate_pct'] > 60:
            report += """### Strength: High Hit Rate

- ✅ Captures majority of recessions
- ✅ Reliable for recession forecasting
- ✅ Good for strategic asset allocation

"""
        
        if scorecard_row['avg_lead_time_months'] < 10:
            report += """### Strength: Actionable Lead Time

- ✅ Short lead time means timely signals
- ✅ Less risk of "too early" positioning
- ✅ Better for tactical trading

"""
        elif scorecard_row['avg_lead_time_months'] > 20:
            report += """### Weakness: Very Long Lead Time

- ⚠️ Signals may be too early for tactical trading
- ⚠️ High risk of blow-off tops
- ✅ Good for strategic planning and policy analysis

"""
        
        if scorecard_row['avg_12m_return'] < 0:
            report += """### Strength: Predictive of Market Declines

- ✅ Negative average returns show this model actually predicts market downturns
- ✅ Rare among tested models
- ✅ Can be used for market timing

"""
        
        # Add use case recommendations
        report += """### Recommended Use Cases

"""
        
        if scorecard_row['overall_score'] > 35:
            report += "- **Primary Signal**: Use as your main recession indicator\n"
        elif scorecard_row['overall_score'] > 25:
            report += "- **Secondary Confirmation**: Use to confirm signals from other models\n"
        else:
            report += "- **Supporting Indicator**: Use as part of a broader ensemble\n"
        
        if scorecard_row['avg_lead_time_months'] > 15:
            report += "- **Strategic Planning**: Good for long-term portfolio allocation\n"
        else:
            report += "- **Tactical Trading**: Suitable for near-term positioning\n"
        
        if scorecard_row['false_positive_rate_pct'] < 60:
            report += "- **Risk Management**: Trigger defensive actions when signal activates\n"
        
        # Add limitations
        report += f"""
### Limitations

"""
        
        if scorecard_row['hit_rate_pct'] < 50:
            report += f"- ⚠️ Misses {100 - scorecard_row['hit_rate_pct']:.0f}% of recessions - don't rely on this model alone\n"
        
        if scorecard_row['false_positive_rate_pct'] > 70:
            report += f"- ⚠️ High false positive rate ({scorecard_row['false_positive_rate_pct']:.0f}%) - many signals don't lead to recessions\n"
        
        if scorecard_row['years_coverage'] < 30:
            report += f"- ⚠️ Limited historical data ({scorecard_row['years_coverage']:.0f} years) - fewer recessions to validate against\n"
        
        if blowoff_rate > 80:
            report += f"- ⚠️ Very high blow-off top rate ({blowoff_rate:.0f}%) - signals don't mean immediate market crashes\n"
        
        # Footer
        report += f"""
---

**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
"""
        
        # Save report
        output_file = OUTPUT_REPORTS_DIR / f"{model_name}_PREDICTION_REPORT.md"
        output_file.write_text(report)
        
        print(f"    ✅ Saved: {output_file.name}")
        
        return output_file
    
    def create_dashboard_json(self):
        """Create JSON data for comparative dashboard visualization."""
        
        print("\n  Creating dashboard JSON...")
        
        dashboard_data = {
            'generated': datetime.now().isoformat(),
            'summary': {
                'total_models': len(self.scorecard),
                'total_signals': int(self.scorecard['total_signals'].sum()),
                'total_recessions_analyzed': int(self.scorecard['recessions_analyzed'].max()),
                'avg_hit_rate': float(self.scorecard['hit_rate_pct'].mean()),
                'avg_fp_rate': float(self.scorecard['false_positive_rate_pct'].mean()),
                'best_model': self.scorecard.iloc[0]['model'],
                'best_score': float(self.scorecard.iloc[0]['overall_score'])
            },
            'scorecard': [],
            'correlation_matrix': [],
            'timeline_data': {}
        }
        
        # Add scorecard data
        for _, row in self.scorecard.iterrows():
            dashboard_data['scorecard'].append({
                'model': row['model'],
                'rank': int(row['rank']) if not pd.isna(row['rank']) else None,
                'overall_score': float(row['overall_score']) if not pd.isna(row['overall_score']) else None,
                'hit_rate': float(row['hit_rate_pct']) if not pd.isna(row['hit_rate_pct']) else None,
                'false_positive_rate': float(row['false_positive_rate_pct']) if not pd.isna(row['false_positive_rate_pct']) else None,
                'avg_lead_time': float(row['avg_lead_time_months']) if not pd.isna(row['avg_lead_time_months']) else None,
                'avg_12m_return': float(row['avg_12m_return']) if not pd.isna(row['avg_12m_return']) else None,
                'total_signals': int(row['total_signals']) if not pd.isna(row['total_signals']) else 0,
                'years_coverage': float(row['years_coverage']) if not pd.isna(row['years_coverage']) else None
            })
        
        # Add simplified timeline data for charting
        for model, data in self.model_data.items():
            if 'timeline' in data:
                tl = data['timeline']
                # Sample every 3 months to reduce size
                sampled = tl[::3] if len(tl) > 100 else tl
                
                dashboard_data['timeline_data'][model] = {
                    'dates': sampled['date'].dt.strftime('%Y-%m-%d').tolist(),
                    'states': sampled['signal_state'].tolist()
                }
        
        # Save JSON
        output_file = OUTPUT_DASHBOARD_DIR / "model_comparison.json"
        with open(output_file, 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        print(f"    ✅ Saved: {output_file.name}")
        print(f"    Size: {output_file.stat().st_size / 1024:.1f} KB")
        
        return output_file


def main():
    print("="*70)
    print("PHASE 5: VISUALIZATION & REPORTING")
    print("="*70)
    
    generator = ReportGenerator()
    
    # Task 5.1: Generate individual model reports
    print("\n" + "="*70)
    print("TASK 5.1: GENERATING INDIVIDUAL MODEL REPORTS")
    print("="*70)
    
    report_files = []
    for model in generator.scorecard['model']:
        try:
            report_file = generator.generate_model_report(model)
            report_files.append(report_file)
        except Exception as e:
            print(f"    ❌ Error generating report for {model}: {e}")
    
    print(f"\n✅ Generated {len(report_files)} model reports")
    
    # Task 5.2: Create dashboard JSON
    print("\n" + "="*70)
    print("TASK 5.2: CREATING DASHBOARD DATA")
    print("="*70)
    
    dashboard_file = generator.create_dashboard_json()
    
    # Final summary
    print("\n" + "="*70)
    print("PHASE 5 COMPLETE")
    print("="*70)
    print(f"\nOutput directories:")
    print(f"  Model Reports: {OUTPUT_REPORTS_DIR}")
    print(f"  Dashboard Data: {OUTPUT_DASHBOARD_DIR}")
    print(f"\nFiles created:")
    print(f"  - {len(report_files)} markdown reports")
    print(f"  - 1 dashboard JSON file")
    
    print("\n" + "="*70)
    print("PATH B: PREDICTION ANALYSIS FRAMEWORK - COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
