#!/usr/bin/env python3
"""
Verify FRED series availability for Business Confidence Migration.

This script checks the availability and data quality of proposed series
for replacing UMCSENT with proper business confidence indicators.
"""

import os
import json
import requests
from datetime import datetime, timedelta

FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    print("ERROR: FRED_API_KEY environment variable not set")
    exit(1)

# Series to verify
SERIES_TO_CHECK = {
    # Current - for comparison
    'UMCSENT': 'Current Primary - UMich Consumer Sentiment',
    
    # Proposed Primary
    'BSCICP03USM665S': 'PROPOSED Primary - OECD Business Confidence Composite',
    
    # ISM Manufacturing PMI candidates
    'NAPM': 'ISM Manufacturing PMI (NAPM)',
    'MANBUSIND': 'ISM Manufacturing Business Index',
    
    # Supporting series
    'BSCICP02USM460S': 'Business Tendency Survey (Manufacturing)',
    'BAMLC0A4CBBB': 'BBB Corporate Bond Spread',
    'BUSLOANS': 'Commercial & Industrial Loans',
    
    # Additional candidates
    'CSCICP03USM665S': 'OECD Consumer Confidence (for comparison)',
    'CFNAI': 'Chicago Fed National Activity Index',
    'GACDISA066MSFRBNY': 'Empire State Manufacturing Survey',
}


def check_series(series_id: str) -> dict:
    """Check if a FRED series exists and get metadata."""
    result = {
        'series_id': series_id,
        'exists': False,
        'title': None,
        'frequency': None,
        'frequency_short': None,
        'units': None,
        'observation_start': None,
        'observation_end': None,
        'last_updated': None,
        'data_points': 0,
        'missing_values': 0,
        'error': None
    }
    
    # Get series metadata
    url = "https://api.stlouisfed.org/fred/series"
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        
        if 'seriess' in data and len(data['seriess']) > 0:
            series = data['seriess'][0]
            result['exists'] = True
            result['title'] = series.get('title')
            result['frequency'] = series.get('frequency')
            result['frequency_short'] = series.get('frequency_short')
            result['units'] = series.get('units')
            result['observation_start'] = series.get('observation_start')
            result['observation_end'] = series.get('observation_end')
            result['last_updated'] = series.get('last_updated')
        else:
            result['error'] = data.get('error_message', 'Series not found')
            return result
            
    except Exception as e:
        result['error'] = str(e)
        return result
    
    # Get observation count and check for missing values
    obs_url = "https://api.stlouisfed.org/fred/series/observations"
    obs_params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'limit': 5000
    }
    
    try:
        obs_response = requests.get(obs_url, params=obs_params, timeout=30)
        obs_data = obs_response.json()
        
        observations = obs_data.get('observations', [])
        result['data_points'] = len(observations)
        result['missing_values'] = sum(1 for obs in observations if obs.get('value') == '.')
        
        if observations:
            result['first_value'] = observations[0].get('value')
            result['last_value'] = observations[-1].get('value')
            
    except Exception as e:
        result['error'] = f"Metadata OK but observations failed: {e}"
    
    return result


def format_result(result: dict, description: str) -> str:
    """Format a single series result for display."""
    lines = []
    
    if result['exists']:
        status = "✅ AVAILABLE"
        lines.append(f"\n{status}: {result['series_id']}")
        lines.append(f"   Description: {description}")
        lines.append(f"   Title: {result['title']}")
        lines.append(f"   Frequency: {result['frequency']} ({result['frequency_short']})")
        lines.append(f"   Units: {result['units']}")
        lines.append(f"   Data Range: {result['observation_start']} to {result['observation_end']}")
        lines.append(f"   Last Updated: {result['last_updated']}")
        lines.append(f"   Data Points: {result['data_points']}")
        lines.append(f"   Missing Values: {result['missing_values']}")
        
        # Calculate years of data
        if result['observation_start'] and result['observation_end']:
            start = datetime.strptime(result['observation_start'], '%Y-%m-%d')
            end = datetime.strptime(result['observation_end'], '%Y-%m-%d')
            years = (end - start).days / 365.25
            lines.append(f"   Years of Data: {years:.1f}")
            
            # Check if data is recent (within 3 months)
            days_old = (datetime.now() - end).days
            if days_old <= 90:
                lines.append(f"   Data Freshness: ✅ Current (updated {days_old} days ago)")
            else:
                lines.append(f"   Data Freshness: ⚠️ Stale ({days_old} days since last update)")
    else:
        status = "❌ NOT FOUND"
        lines.append(f"\n{status}: {result['series_id']}")
        lines.append(f"   Description: {description}")
        lines.append(f"   Error: {result['error']}")
    
    return '\n'.join(lines)


def main():
    print("=" * 80)
    print("FRED SERIES VERIFICATION FOR BUSINESS CONFIDENCE MIGRATION")
    print(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    available = []
    not_found = []
    
    for series_id, description in SERIES_TO_CHECK.items():
        print(f"Checking {series_id}...", end=" ", flush=True)
        result = check_series(series_id)
        results[series_id] = result
        
        if result['exists']:
            print("✅")
            available.append(series_id)
        else:
            print("❌")
            not_found.append(series_id)
    
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for series_id, description in SERIES_TO_CHECK.items():
        print(format_result(results[series_id], description))
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nAvailable Series ({len(available)}):")
    for s in available:
        print(f"  ✅ {s}")
    
    print(f"\nNot Found ({len(not_found)}):")
    for s in not_found:
        print(f"  ❌ {s}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    # Check primary candidate
    primary = results.get('BSCICP03USM665S', {})
    if primary.get('exists'):
        print("\n✅ PRIMARY SERIES AVAILABLE: BSCICP03USM665S")
        print("   This can be used as the primary business confidence indicator.")
    else:
        print("\n❌ PRIMARY CANDIDATE NOT AVAILABLE: BSCICP03USM665S")
        print("   Need to find alternative primary series.")
    
    # Check ISM PMI
    napm = results.get('NAPM', {})
    if napm.get('exists'):
        print("\n✅ ISM PMI AVAILABLE: NAPM")
        print("   This can be used for ISM Manufacturing PMI.")
    else:
        print("\n⚠️ NAPM not found - need to search for alternative ISM PMI series")
    
    # Save detailed results to JSON
    output = {
        'run_date': datetime.now().isoformat(),
        'results': results,
        'available': available,
        'not_found': not_found
    }
    
    output_path = 'reports/business_confidence_series_verification.json'
    os.makedirs('reports', exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n\nDetailed results saved to: {output_path}")


if __name__ == '__main__':
    main()
