#!/usr/bin/env python3
"""
Test script to check alternative credit series availability on FRED
for extending HP Filter historical data back to 1990 or 1980.
"""

import pandas as pd
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from mie_lib.data_ingest.macro.providers.fred import FredProvider

def test_series(provider, series_id, description):
    """Test a FRED series and report availability."""
    print(f"\n{'='*60}")
    print(f"Testing: {series_id} ({description})")
    print('='*60)
    try:
        df = provider.fetch_series(series_id, start_date=None)
        if df.empty:
            print(f"❌ {series_id}: No data returned")
            return None
        
        print(f"✅ {series_id} AVAILABLE")
        print(f"   Start Date: {df['date'].min()}")
        print(f"   End Date: {df['date'].max()}")
        print(f"   Total Observations: {len(df)}")
        print(f"   Years of History: {(df['date'].max() - df['date'].min()).days / 365.25:.1f}")
        return df
    except Exception as e:
        print(f"❌ {series_id}: {str(e)}")
        return None

def main():
    print("FRED CREDIT SERIES AVAILABILITY TEST")
    print("="*60)
    
    provider = FredProvider()
    
    # Current series (baseline)
    print("\n🔍 CURRENT SERIES (Baseline)")
    current = test_series(provider, 'TOTDTEUSQ163N', 'Total Debt Non-Financial Sector')
    
    # Alternative single series
    print("\n\n🔍 ALTERNATIVE SINGLE SERIES")
    tcmdo = test_series(provider, 'TCMDO', 'Total Credit Market Debt Outstanding')
    totdtl = test_series(provider, 'TOTDTLQQ027S', 'Total Debt Securities')
    cmdebt = test_series(provider, 'CMDEBT', 'Credit Market Debt Outstanding')
    
    # Component series
    print("\n\n🔍 COMPONENT SERIES (For Constructing Total)")
    household = test_series(provider, 'HHMSDODNS', 'Household Debt')
    corporate = test_series(provider, 'BCNSDODNS', 'Corporate Debt')
    federal = test_series(provider, 'GFDEBTN', 'Federal Government Debt')
    state_local = test_series(provider, 'SLGSDODNS', 'State/Local Government Debt')
    
    # Check GDP for reference
    print("\n\n🔍 GDP SERIES (For Reference)")
    gdp = test_series(provider, 'GDPC1', 'Real GDP')
    
    # Summary
    print("\n\n" + "="*60)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*60)
    
    if current is not None:
        current_start = current['date'].min()
        print(f"\nCurrent series (TOTDTEUSQ163N) starts: {current_start}")
        
        # Check which alternatives extend further back
        alternatives = []
        if tcmdo is not None and tcmdo['date'].min() < current_start:
            alternatives.append(('TCMDO', tcmdo['date'].min(), len(tcmdo)))
        if totdtl is not None and totdtl['date'].min() < current_start:
            alternatives.append(('TOTDTLQQ027S', totdtl['date'].min(), len(totdtl)))
        if cmdebt is not None and cmdebt['date'].min() < current_start:
            alternatives.append(('CMDEBT', cmdebt['date'].min(), len(cmdebt)))
        
        if alternatives:
            print("\n🎯 RECOMMENDED ALTERNATIVES (extend further back):")
            for series_id, start_date, obs_count in sorted(alternatives, key=lambda x: x[1]):
                years_gained = (current_start - start_date).days / 365.25
                print(f"   {series_id}: {start_date} (+{years_gained:.1f} years, {obs_count} obs)")
        else:
            print("\n⚠️  No single alternative series extends further back.")
        
        # Check component approach
        all_components = [household, corporate, federal, state_local]
        if all(c is not None for c in all_components):
            earliest_component = min(c['date'].min() for c in all_components)
            if earliest_component < current_start:
                years_gained = (current_start - earliest_component).days / 365.25
                print(f"\n🔧 COMPONENT APPROACH:")
                print(f"   Combined start: {earliest_component} (+{years_gained:.1f} years)")
                print(f"   Components: Household + Corporate + Federal + State/Local")

if __name__ == "__main__":
    main()
