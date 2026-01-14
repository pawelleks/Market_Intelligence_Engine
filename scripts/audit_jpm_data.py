
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from mie_lib.analytics.jpm_dashboard.aggregate_indicators import INDICATOR_SERIES as INDICATORS
    from mie_lib.utils.paths import FRED_DATA_DIR, RAW_DATA_DIR
except ImportError as e:
    # Fallback if mie_lib not in path properly
    print(f"Error importing mie_lib: {e}")
    sys.path.append("/app/src")
    try:
        from mie_lib.analytics.jpm_dashboard.aggregate_indicators import INDICATOR_SERIES as INDICATORS
        from mie_lib.utils.paths import FRED_DATA_DIR, RAW_DATA_DIR
    except ImportError as e2:
        print(f"Retry failed: {e2}")
        sys.exit(1)

def audit_series():
    print(f"\nJPM Dashboard Data Series Audit Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    print(f"{'Indicator':<20} | {'Type':<10} | {'Series ID':<15} | {'Found':<5} | {'Start':<10} | {'End':<10} | {'Freq':<5} | {'Rows':<6}")
    print("-" * 100)

    for indicator, config in INDICATORS.items():
        # Collect all series
        all_series = []
        for s in config.get('primary', []): all_series.append((s, 'Primary'))
        for s in config.get('secondary', []): all_series.append((s, 'Secondary'))
        for s in config.get('components', []): all_series.append((s, 'Component'))
        
        for series_id, s_type in all_series:
            # Determine path
            file_path = FRED_DATA_DIR / f"{series_id}.parquet"
            
            # Special handling for stock market
            if indicator == 'stock_market':
                if series_id == 'SP500':
                    file_path = RAW_DATA_DIR / "SPY.parquet"
                elif series_id == 'VIX':
                     file_path = RAW_DATA_DIR / "^VIX.parquet"
            
            found = "No"
            start = "-"
            end = "-"
            count = "-"
            freq = "-"
            
            if file_path.exists():
                try:
                    df = pd.read_parquet(file_path)
                    found = "Yes"
                    if not df.empty:
                        # Handle varied column names
                        date_col = 'date' if 'date' in df.columns else 'Date'
                        if date_col in df.columns:
                            df[date_col] = pd.to_datetime(df[date_col])
                            df = df.sort_values(date_col)
                            start = df[date_col].min().strftime('%Y-%m-%d')
                            end = df[date_col].max().strftime('%Y-%m-%d')
                            count = len(df)
                            
                            # Estimate frequency
                            if count > 1:
                                diff = (df[date_col].iloc[1] - df[date_col].iloc[0]).days
                                if diff < 5: freq = "D"
                                elif diff < 10: freq = "W"
                                elif diff < 35: freq = "M"
                                elif diff < 100: freq = "Q"
                                else: freq = "Y"
                except Exception as e:
                    found = "Err"
                    print(f"Error reading {file_path}: {e}")
            
            print(f"{indicator:<20} | {s_type:<10} | {series_id:<15} | {found:<5} | {start:<10} | {end:<10} | {freq:<5} | {count:<6}")

if __name__ == "__main__":
    audit_series()
