"""
Process yfinance option data through the probability pipeline.
Generates probability surfaces for comparison with ThetaData results.
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, date
import logging
import sys

# Import existing probability math
sys.path.insert(0, '/app/src')
from mie_lib.utils.probability_math import BreedenLitzenberger

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

INPUT_FILE = Path('/app/data/options_yfinance/SPX_options.parquet')
OUTPUT_DIR = Path('/app/public/data')
SYMBOL = 'SPX'

def calculate_dte(expiry_str: str, anchor_date: date) -> int:
    """Calculate days to expiration."""
    exp_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
    return (exp_date - anchor_date).days

def process_yfinance_options():
    """Process yfinance options through BL pipeline."""
    
    if not INPUT_FILE.exists():
        LOG.error(f"Input file not found: {INPUT_FILE}")
        return
    
    LOG.info(f"Loading yfinance option data from {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    
    LOG.info(f"   > Total contracts: {len(df)}")
    LOG.info(f"   > Expirations: {df['expiry'].nunique()}")
    
    # Get anchor date (today)
    anchor_date = date.today()
    LOG.info(f"   > Anchor date: {anchor_date}")
    
    # Calculate DTEs
    df['dte'] = df['expiry'].apply(lambda x: calculate_dte(x, anchor_date))
    
    # Filter out expired or same-day
    df = df[df['dte'] >= 1]
    
    # Get spot price from ATM calls
    spot_approx = df['strike'].median()
    LOG.info(f"   > Estimated spot from strikes: ${spot_approx:,.2f}")
    
    # Initialize Breeden-Litzenberger
    bl = BreedenLitzenberger(risk_free_rate=0.04, equity_risk_premium=0.04)
    
    results = []
    expirations = df.groupby(['expiry', 'dte'])
    
    for (exp_date, dte), group in expirations:
        if dte > 90:  # Limit to ~3 months
            continue
            
        LOG.info(f"   > Processing {exp_date} (DTE={dte})...")
        
        # Prepare call prices
        group = group.copy()
        group['mid'] = (group['bid'] + group['ask']) / 2
        
        # Filter valid prices
        group = group[(group['bid'] > 0) & (group['ask'] > 0) & (group['mid'] > 0)]
        
        if len(group) < 10:
            LOG.warning(f"      Insufficient data ({len(group)} contracts)")
            continue
        
        # Sort by strike
        group = group.sort_values('strike')
        
        strikes = group['strike'].tolist()
        call_prices = group['mid'].tolist()
        
        # Calculate PDF
        distribution = bl.calculate_pdf(
            strikes=strikes,
            call_prices=call_prices,
            dte_days=float(dte),
            smooth_factor=None
        )
        
        if not distribution:
            LOG.warning(f"      PDF calculation failed")
            continue
        
        # Check median
        import numpy as np
        strikes_arr = np.array(distribution['strikes'])
        prob_above_arr = np.array(distribution['prob_above'])
        idx_50 = np.argmin(np.abs(prob_above_arr - 0.5))
        median = strikes_arr[idx_50]
        
        LOG.info(f"      ✓ Median: ${median:,.0f} ({len(strikes)} strikes)")
        
        results.append({
            'expiry': exp_date,
            'dte': int(dte),
            'distribution': distribution,
            'num_contracts': len(group)
        })
    
    if not results:
        LOG.error("No results generated")
        return
    
    # Create output JSON
    output = {
        'symbol': SYMBOL,
        'data_source': 'yfinance',
        'spot_price': float(spot_approx),
        'anchor_date': anchor_date.isoformat(),
        'generated_at': datetime.now().isoformat(),
        'results': results,
        'erp': 0.04
    }
    
    # Save
    output_path = OUTPUT_DIR / f'probability_surface_{SYMBOL}_yfinance.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    LOG.info(f"✓ Saved to {output_path}")
    LOG.info(f"   > Processed {len(results)} expirations")
    
    # Print median comparison
    print("\n=== YFINANCE MEDIAN COMPARISON ===")
    print(f"Spot price: ${spot_approx:,.2f}")
    print("\nMedian prices by DTE:")
    for res in results[:8]:
        dte = res['dte']
        dist = res['distribution']
        strikes_arr = np.array(dist['strikes'])
        prob_above_arr = np.array(dist['prob_above'])
        idx_50 = np.argmin(np.abs(prob_above_arr - 0.5))
        median = strikes_arr[idx_50]
        offset = median - spot_approx
        print(f"DTE={dte:2d}: Median=${median:7,.0f} (offset: ${offset:+7,.0f})")

if __name__ == '__main__':
    process_yfinance_options()
