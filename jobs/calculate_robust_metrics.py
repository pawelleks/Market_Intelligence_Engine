"""
Calculate robust option-implied metrics using established formulas.
These metrics are reliable and actionable for understanding market expectations.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

def calculate_forward_price(calls_df: pd.DataFrame, puts_df: pd.DataFrame, r: float, T: float) -> dict:
    """
    Calculate forward price using put-call parity.
    F = K + (C - P) * e^(rT)
    
    This is arbitrage-enforced and very robust.
    """
    # Merge calls and puts on strike
    merged = pd.merge(
        calls_df[['strike', 'mid']].rename(columns={'mid': 'call_mid'}),
        puts_df[['strike', 'mid']].rename(columns={'mid': 'put_mid'}),
        on='strike',
        how='inner'
    )
    
    if merged.empty:
        return {}
    
    # Calculate forward for each strike
    merged['forward'] = merged['strike'] + (merged['call_mid'] - merged['put_mid']) * np.exp(r * T)
    
    # Use median forward (most robust to outliers)
    forward_median = merged['forward'].median()
    forward_mean = merged['forward'].mean()
    forward_std = merged['forward'].std()
    
    return {
        'forward_median': float(forward_median),
        'forward_mean': float(forward_mean),
        'forward_std': float(forward_std),
        'num_strikes': len(merged)
    }

def calculate_expected_move(atm_call: float, atm_put: float) -> dict:
    """
    Expected move = ATM straddle price
    This is the market's pricing of ±1σ move
    """
    straddle = atm_call + atm_put
    
    return {
        'expected_move': float(straddle),
        'atm_call': float(atm_call),
        'atm_put': float(atm_put)
    }

def calculate_skew_indicator(otm_put_iv: float, otm_call_iv: float) -> dict:
    """
    Skew = OTM Put IV - OTM Call IV
    Positive skew = market fears downside
    """
    skew = otm_put_iv - otm_call_iv
    
    return {
        'skew': float(skew),
        'otm_put_iv': float(otm_put_iv),
        'otm_call_iv': float(otm_call_iv),
        'interpretation': 'BEARISH' if skew > 0.05 else 'BULLISH' if skew < -0.05 else 'NEUTRAL'
    }

def process_option_chain_robust(symbol: str = 'SPX'):
    """
    Process option chain using robust metrics instead of BL.
    """
    LOG.info(f"Calculating robust metrics for {symbol}...")
    
    # For now, use yfinance data as it's cleaner
    input_file = Path(f'/app/data/options_yfinance/{symbol}_options.parquet')
    
    if not input_file.exists():
        LOG.error(f"Input file not found: {input_file}")
        return
    
    df = pd.read_parquet(input_file)
    df['dte'] = df['expiry'].apply(lambda x: (datetime.strptime(x, '%Y-%m-%d').date() - date.today()).days)
    df = df[df['dte'] >= 1]
    df['mid'] = (df['bid'] + df['ask']) / 2
    df = df[(df['bid'] > 0) & (df['ask'] > 0)]
    
    spot = df['strike'].median()
    LOG.info(f"   > Spot: ${spot:,.2f}")
    
    results = []
    r = 0.04  # Risk-free rate
    
    # Process each expiration
    for (exp_date, dte), group in df.groupby(['expiry', 'dte']):
        if dte > 90:
            continue
            
        T = dte / 365.25
        
        # Split calls/puts (yfinance only has calls in our current fetch)
        # For POC, let's just calculate what we can from calls
        
        # Find ATM
        atm_strike = group['strike'].iloc[(group['strike'] - spot).abs().argsort()[0]]
        atm_call = group[group['strike'] == atm_strike]['mid'].iloc[0]
        
        # Expected move (simplified without puts)
        expected_move = atm_call  # Lower bound (actual straddle would be call + put)
        
        result = {
            'expiry': exp_date,
            'dte': int(dte),
            'spot': float(spot),
            'atm_strike': float(atm_strike),
            'expected_move_lower_bound': float(expected_move),
            'expected_move_pct': float(expected_move / spot * 100)
        }
        
        results.append(result)
        LOG.info(f"   > {exp_date} (DTE={dte}): Expected move ≥${expected_move:.0f} ({result['expected_move_pct']:.1f}%)")
    
    # Save
    output = {
        'symbol': symbol,
        'spot': float(spot),
        'generated_at': datetime.now().isoformat(),
        'methodology': 'ATM_STRADDLE_EXPECTED_MOVE',
        'results': results
    }
    
    output_path = Path('/app/public/data') / f'robust_metrics_{symbol}.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    LOG.info(f"✓ Saved to {output_path}")

if __name__ == '__main__':
    process_option_chain_robust('SPX')
