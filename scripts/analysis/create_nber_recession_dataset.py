#!/usr/bin/env python3
"""
Create NBER Recession Dataset

Fetches USREC (US Recession Indicators) from FRED and processes it into
a structured dataset with recession start/end dates and metadata.

Output: data/outcomes/nber_recessions.parquet
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

from mie_lib.data_ingest.macro.providers.fred import FredProvider

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "outcomes"
OUTPUT_FILE = OUTPUT_DIR / "nber_recessions.parquet"


def identify_recession_periods(usrec_data):
    """
    Identify recession start and end dates from USREC binary series.
    
    USREC: 1 = recession, 0 = expansion
    Recession starts when value changes from 0 to 1
    Recession ends when value changes from 1 to 0
    
    Args:
        usrec_data: DataFrame with 'date' and 'value' columns
        
    Returns:
        List of recession period dicts
    """
    recessions = []
    
    # Sort by date
    usrec_data = usrec_data.sort_values('date').reset_index(drop=True)
    
    in_recession = False
    recession_start = None
    
    for idx, row in usrec_data.iterrows():
        date = row['date']
        value = row['value']
        
        # Recession starts (0 → 1 transition)
        if value == 1 and not in_recession:
            in_recession = True
            recession_start = date
            
        # Recession ends (1 → 0 transition)
        elif value == 0 and in_recession:
            in_recession = False
            recession_end = date
            
            # Calculate duration
            duration_days = (recession_end - recession_start).days
            duration_months = round(duration_days / 30.44)  # Average days per month
            
            # Create recession ID (e.g., "2008-09")
            start_year = recession_start.year
            end_year = recession_end.year
            if start_year == end_year:
                recession_id = str(start_year)
            else:
                recession_id = f"{start_year}-{str(end_year)[-2:]}"
            
            recessions.append({
                'recession_id': recession_id,
                'start_date': recession_start,
                'end_date': recession_end,
                'duration_months': duration_months,
                'peak_date': recession_start,  # USREC uses peak as start
                'trough_date': recession_end    # USREC uses trough as end
            })
    
    # Handle case where dataset ends during a recession
    if in_recession and recession_start is not None:
        print(f"WARNING: Dataset ends during active recession starting {recession_start}")
        # Don't include incomplete recessions
    
    return recessions


def main():
    print("Creating NBER Recession Dataset")
    print("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Fetch USREC from FRED
    print("\n1. Fetching USREC from FRED...")
    provider = FredProvider()
    usrec_data = provider.fetch_series('USREC', start_date=None)  # Get full history
    
    print(f"   Fetched {len(usrec_data)} monthly observations")
    print(f"   Period: {usrec_data['date'].min()} to {usrec_data['date'].max()}")
    
    # Identify recession periods
    print("\n2. Identifying recession periods...")
    recessions = identify_recession_periods(usrec_data)
    
    print(f"   Found {len(recessions)} recession periods:")
    for rec in recessions:
        print(f"   - {rec['recession_id']}: {rec['start_date'].strftime('%Y-%m')} to "
              f"{rec['end_date'].strftime('%Y-%m')} ({rec['duration_months']} months)")
    
    # Convert to DataFrame
    print("\n3. Creating structured dataset...")
    df = pd.DataFrame(recessions)
    
    # Save to parquet
    print(f"\n4. Saving to {OUTPUT_FILE}...")
    df.to_parquet(OUTPUT_FILE, index=False)
    
    print("\n" + "=" * 60)
    print("✅ NBER Recession Dataset created successfully!")
    print(f"   Output: {OUTPUT_FILE}")
    print(f"   Recessions: {len(df)}")
    print(f"   Period: {df['start_date'].min().year} - {df['end_date'].max().year}")
    
    return df


if __name__ == "__main__":
    df = main()
