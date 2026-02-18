#!/usr/bin/env python3
"""
Skew and PCR Processing Pipeline

Generates:
1. Volatility Smile (IV vs Strike) for key tenors.
2. Put-Call Ratio (Volume and OI) stats.
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, datetime
from scipy.stats import norm
from scipy.optimize import newton

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("process_skew")

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_DIR = Path(os.getcwd()) / "public" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ['SPX', 'SPY', 'QQQ', 'IWM']
RISK_FREE_RATE = 0.045

# =============================================================================
# FINANCIAL MATH (Black-Scholes)
# =============================================================================

def black_scholes_price(S, K, T, r, sigma, option_type='C'):
    """Calculate Black-Scholes option price."""
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K) if option_type == 'C' else max(0.0, K - S)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'C':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def black_scholes_vega(S, K, T, r, sigma):
    """Calculate option Vega."""
    if T <= 0 or sigma <= 0: return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return S * norm.pdf(d1) * np.sqrt(T)

def implied_volatility(market_price, S, K, T, r, option_type='C'):
    """Solve for Implied Volatility using Newton-Raphson."""
    if market_price <= 0 or T <= 0: return 0.0
    
    # Initial guess (Brenner-Subrahmanyam)
    sigma = np.sqrt(2 * np.pi / T) * (market_price / S)
    if sigma <= 0: sigma = 0.2
    
    for _ in range(20):
        price = black_scholes_price(S, K, T, r, sigma, option_type)
        vega = black_scholes_vega(S, K, T, r, sigma)
        if vega < 1e-6: break
        
        diff = market_price - price
        if abs(diff) < 1e-4: return float(sigma)
        
        sigma = sigma + diff / vega
        if sigma <= 0: sigma = 0.001; break
        if sigma > 5.0: sigma = 5.0; break
        
    return float(sigma)

# =============================================================================
# PROCESSING
# =============================================================================

def get_anchor_price(symbol):
    """Simple anchor price from existing probability surface file if possible, or fallback."""
    try:
        prob_file = OUTPUT_DIR / f"probability_surface_{symbol}.json"
        if prob_file.exists():
            with open(prob_file, 'r') as f:
                data = json.load(f)
                return float(data.get('ref_price', 0))
    except Exception:
        pass
    return 0.0

def process_symbol(symbol):
    LOG.info(f"Processing Skew for {symbol}...")
    
    # Find latest chain file
    files = list(RAW_DIR.glob(f"chain_{symbol}_*.parquet"))
    if not files:
        LOG.warning(f"  No chain files for {symbol}")
        return
    
    latest_file = max(files, key=lambda f: f.name)
    df = pd.read_parquet(latest_file)
    LOG.info(f"  Loaded {latest_file.name} ({len(df)} rows)")
    
    spot = get_anchor_price(symbol)
    if spot <= 0:
        # Try to infer spot from ATM strike or something? 
        # For indices, we need a good spot.
        LOG.warning(f"  No anchor price for {symbol}. Skipping skew calculation.")
        return

    df['exp_date'] = pd.to_datetime(df['expiration'])
    # Fix: Strip .parquet extension from the date string
    date_str = latest_file.name.split('_')[2].replace('.parquet', '')
    today = pd.Timestamp(date_str) 
    
    # 1. PCR Stats
    calls = df[df['right'] == 'C']
    puts = df[df['right'] == 'P']
    
    total_call_vol = int(calls['volume'].sum())
    total_put_vol = int(puts['volume'].sum())
    total_call_oi = int(calls['open_interest'].sum())
    total_put_oi = int(puts['open_interest'].sum())
    
    pcr_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0
    pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
    
    # 2. Volatility Smile (Pick 30D and 60D tenors)
    unique_exps = sorted(df['exp_date'].unique())
    target_dtes = [30, 60]
    smile_data = {}
    
    for target in target_dtes:
        best_exp = None
        min_diff = 999
        for exp in unique_exps:
            dte = (exp - today).days
            diff = abs(dte - target)
            if diff < min_diff:
                min_diff = diff
                best_exp = exp
        
        if not best_exp: continue
        
        dte = (best_exp - today).days
        T = dte / 365.25
        exp_df = df[df['exp_date'] == best_exp].copy()
        
        # Filter for relevant strikes (±20%)
        exp_df = exp_df[(exp_df['strike'] >= spot * 0.8) & (exp_df['strike'] <= spot * 1.2)]
        
        curves = []
        for _, row in exp_df.iterrows():
            iv = implied_volatility(row['mid_price'], spot, row['strike'], T, RISK_FREE_RATE, row['right'])
            if iv > 0.05 and iv < 2.0:
                curves.append({
                    "strike": float(row['strike']),
                    "iv": round(float(iv), 4),
                    "right": row['right'],
                    "volume": int(row['volume']),
                    "oi": int(row['open_interest'])
                })
        
        if curves:
            # Sort by strike
            curves.sort(key=lambda x: x['strike'])
            
            # Apply light smoothing to the IVs to remove jitter
            from scipy.ndimage import gaussian_filter1d
            vals_iv = np.array([c['iv'] for c in curves])
            # Sigma=1.0 is enough for light smoothing
            smoothed_iv = gaussian_filter1d(vals_iv, sigma=1.0)
            
            for i, c in enumerate(curves):
                c['iv'] = round(float(smoothed_iv[i]), 4)

            smile_data[f"{target}d"] = {
                "expiration": best_exp.strftime('%Y-%m-%d'),
                "dte": dte,
                "data": curves
            }

    # Save output
    output_data = {
        "ticker": symbol,
        "as_of": today.strftime('%Y-%m-%d'),
        "spot_price": spot,
        "pcr": {
            "volume": round(pcr_vol, 4),
            "oi": round(pcr_oi, 4),
            "total_call_vol": total_call_vol,
            "total_put_vol": total_put_vol,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi
        },
        "smile": smile_data
    }
    
    output_file = OUTPUT_DIR / f"skew_{symbol}.json"
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    LOG.info(f"  Saved skew results to {output_file.name}")

def main():
    for symbol in SYMBOLS:
        try:
            process_symbol(symbol)
        except Exception as e:
            LOG.error(f"Error processing {symbol}: {e}")

if __name__ == "__main__":
    main()
