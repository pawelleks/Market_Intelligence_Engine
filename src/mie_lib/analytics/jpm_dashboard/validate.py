"""
JPM Economic Dashboard - Data Validation Script

Validates the quality and freshness of aggregated indicator data.
Checks:
- All 10 indicator files exist
- No excessive staleness
- No excessive data gaps
- Calculated metrics are within reasonable bounds
- Recession periods align with USREC
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

from mie_lib.utils.paths import PROCESSED_DATA_DIR, FRED_DATA_DIR

LOG = logging.getLogger(__name__)


# Expected indicator files
EXPECTED_INDICATORS = [
    'gdp', 'consumer_spending', 'labor_market', 'interest_rates',
    'inflation', 'business_confidence', 'stock_market',
    'trade_balance', 'housing', 'policy'
]

# Staleness thresholds (days)
STALENESS_THRESHOLDS = {
    'stock_market': 3,      # Daily data
    'interest_rates': 3,    # Daily data
    'gdp': 90,              # Quarterly data
    'default': 45           # Monthly data
}


def check_file_exists(indicator: str, data_dir: Path) -> Tuple[bool, str]:
    """Check if aggregated file exists."""
    file_path = data_dir / f"{indicator}.parquet"
    
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    
    return True, "OK"


def check_staleness(df: pd.DataFrame, indicator: str) -> Tuple[bool, str]:
    """Check if data is fresh enough."""
    if df.empty:
        return False, "Empty dataset"
    
    latest_date = df['date'].max()
    days_old = (datetime.now() - latest_date).days
    
    threshold = STALENESS_THRESHOLDS.get(indicator, STALENESS_THRESHOLDS['default'])
    
    if days_old > threshold:
        return False, f"Data is {days_old} days old (threshold: {threshold})"
    
    return True, f"Data is {days_old} days old (OK)"


def check_data_gaps(df: pd.DataFrame, indicator: str) -> Tuple[bool, str]:
    """Check for excessive gaps in data."""
    if df.empty:
        return False, "Empty dataset"
    
    # Get all base columns (without suffixes)
    base_cols = [c for c in df.columns if not any(c.endswith(s) for s in ['_yoy', '_mom', '_qoq', '_zscore', '_pct', '_ma3', 'recession', 'last_updated'])]
    data_cols = [c for c in base_cols if c != 'date']
    
    issues = []
    
    for col in data_cols:
        if col not in df.columns:
            continue
        
        # Count consecutive NaN
        is_na = df[col].isna()
        consecutive_na = is_na.groupby((is_na != is_na.shift()).cumsum()).sum()
        max_consecutive = consecutive_na.max() if len(consecutive_na) > 0 else 0
        
        if max_consecutive > 3:
            issues.append(f"{col}: {max_consecutive} consecutive NaN values")
    
    if issues:
        return False, "; ".join(issues)
    
    return True, "No excessive gaps"


def check_metrics_bounds(df: pd.DataFrame, indicator: str) -> Tuple[bool, str]:
    """Check if calculated metrics are within reasonable bounds."""
    issues = []
    
    # Check z-scores (should be mostly within -3 to 3)
    zscore_cols = [c for c in df.columns if c.endswith('_zscore')]
    
    for col in zscore_cols:
        if col not in df.columns:
            continue
        
        zscores = df[col].dropna()
        if len(zscores) == 0:
            continue
        
        extreme = (zscores.abs() > 5).sum()
        if extreme > len(zscores) * 0.05:  # More than 5% extreme values
            issues.append(f"{col}: {extreme} extreme values (>5% of data)")
    
    # Check percentiles (should be 0-100)
    pct_cols = [c for c in df.columns if c.endswith('_pct')]
    
    for col in pct_cols:
        if col not in df.columns:
            continue
        
        pcts = df[col].dropna()
        if len(pcts) == 0:
            continue
        
        out_of_bounds = ((pcts < 0) | (pcts > 100)).sum()
        if out_of_bounds > 0:
            issues.append(f"{col}: {out_of_bounds} values out of [0, 100] range")
    
    if issues:
        return False, "; ".join(issues)
    
    return True, "Metrics within expected bounds"


def check_recession_alignment(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check if recession periods align with USREC."""
    if 'recession' not in df.columns:
        return True, "No recession column (OK)"
    
    usrec_path = FRED_DATA_DIR / "USREC.parquet"
    if not usrec_path.exists():
        return True, "USREC not available for comparison (skip)"
    
    try:
        usrec_df = pd.read_parquet(usrec_path)
        usrec_df['date'] = pd.to_datetime(usrec_df['date'])
        usrec_df = usrec_df.set_index('date').resample('M').last().reset_index()
        
        # Merge and compare
        merged = df.merge(usrec_df, on='date', suffixes=('_agg', '_usrec'))
        
        if 'value' in merged.columns:
            mismatch = (merged['recession'].fillna(0).astype(int) != merged['value'].fillna(0).astype(int)).sum()
            
            if mismatch > 0:
                return False, f"{mismatch} mismatches with USREC data"
        
        return True, "Recession periods align with USREC"
        
    except Exception as e:
        return True, f"Could not verify (skip): {e}"


def validate_indicator(indicator: str, data_dir: Path) -> Dict[str, any]:
    """Run all validation checks for an indicator."""
    results = {
        'indicator': indicator,
        'checks': {},
        'overall': 'pass'
    }
    
    # File exists
    exists, msg = check_file_exists(indicator, data_dir)
    results['checks']['file_exists'] = {'pass': exists, 'message': msg}
    
    if not exists:
        results['overall'] = 'fail'
        return results
    
    # Load data
    try:
        df = pd.read_parquet(data_dir / f"{indicator}.parquet")
        df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        results['checks']['load_data'] = {'pass': False, 'message': str(e)}
        results['overall'] = 'fail'
        return results
    
    results['checks']['load_data'] = {'pass': True, 'message': f"Loaded {len(df)} rows"}
    
    # Staleness
    fresh, msg = check_staleness(df, indicator)
    results['checks']['staleness'] = {'pass': fresh, 'message': msg}
    if not fresh:
        results['overall'] = 'warn'
    
    # Data gaps
    no_gaps, msg = check_data_gaps(df, indicator)
    results['checks']['data_gaps'] = {'pass': no_gaps, 'message': msg}
    if not no_gaps:
        results['overall'] = 'warn'
    
    # Metrics bounds
    valid_metrics, msg = check_metrics_bounds(df, indicator)
    results['checks']['metrics_bounds'] = {'pass': valid_metrics, 'message': msg}
    if not valid_metrics:
        results['overall'] = 'warn'
    
    # Recession alignment
    recessions_ok, msg = check_recession_alignment(df)
    results['checks']['recession_alignment'] = {'pass': recessions_ok, 'message': msg}
    if not recessions_ok:
        results['overall'] = 'warn'
    
    return results


def validate_all_indicators(data_dir: Path = None) -> Dict[str, Any]:
    """
    Validate all 10 indicators.
    
    Returns:
        Validation results for all indicators
    """
    if data_dir is None:
        data_dir = PROCESSED_DATA_DIR / "jpm_dashboard"
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_dir': str(data_dir),
        'indicators': {},
        'summary': {
            'total': len(EXPECTED_INDICATORS),
            'pass': 0,
            'warn': 0,
            'fail': 0
        }
    }
    
    for indicator in EXPECTED_INDICATORS:
        indicator_result = validate_indicator(indicator, data_dir)
        results['indicators'][indicator] = indicator_result
        
        # Update summary
        if indicator_result['overall'] == 'pass':
            results['summary']['pass'] += 1
        elif indicator_result['overall'] == 'warn':
            results['summary']['warn'] += 1
        else:
            results['summary']['fail'] += 1
    
    # Overall status
    if results['summary']['fail'] > 0:
        results['status'] = 'FAIL'
    elif results['summary']['warn'] > 0:
        results['status'] = 'WARN'
    else:
        results['status'] = 'PASS'
    
    return results


def print_validation_report(results: Dict[str, Any]):
    """Print formatted validation report."""
    print("=" * 70)
    print("JPM DASHBOARD DATA VALIDATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Data Directory: {results['data_dir']}")
    print(f"Overall Status: {results['status']}")
    print()
    
    print(f"Summary: {results['summary']['pass']} pass, {results['summary']['warn']} warn, {results['summary']['fail']} fail")
    print()
    
    for indicator, result in results['indicators'].items():
        status_symbol = "✓" if result['overall'] == 'pass' else ("⚠" if result['overall'] == 'warn' else "✗")
        print(f"{status_symbol} {indicator.upper()}: {result['overall'].upper()}")
        
        for check_name, check_result in result['checks'].items():
            check_symbol = "  ✓" if check_result['pass'] else "  ✗"
            print(f"{check_symbol} {check_name}: {check_result['message']}")
        
        print()


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run validation
    results = validate_all_indicators()
    
    # Print report
    print_validation_report(results)
    
    # Exit code based on status
    if results['status'] == 'FAIL':
        exit(1)
    elif results['status'] == 'WARN':
        exit(0)  # Warnings don't fail the build
    else:
        exit(0)
