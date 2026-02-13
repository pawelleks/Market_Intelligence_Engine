"""
Debug Breeden-Litzenberger calculation step-by-step.
Shows intermediate values to identify where the math goes wrong.
"""
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d
import json
from pathlib import Path

def debug_bl_manually():
    """Step through BL calculation manually with actual data."""
    
    print("="*80)
    print("BREEDEN-LITZENBERGER DEBUG - STEP BY STEP")
    print("="*80)
    
    # Load yfinance data (cleaner, easier to debug)
    yf_file = Path('/app/data/options_yfinance/SPX_options.parquet')
    df = pd.read_parquet(yf_file)
    
    # Get DTE=7 expiration
    from datetime import datetime, date
    anchor = date.today()
    df['dte'] = df['expiry'].apply(lambda x: (datetime.strptime(x, '%Y-%m-%d').date() - anchor).days)
    
    dte7 = df[df['dte'] == 7].copy()
    dte7['mid'] = (dte7['bid'] + dte7['ask']) / 2
    dte7 = dte7[(dte7['bid'] > 0) & (dte7['ask'] > 0) & (dte7['mid'] > 0)]
    dte7 = dte7.sort_values('strike')
    
    K_arr = dte7['strike'].values
    C_arr = dte7['mid'].values
    
    print(f"\n1. INPUT DATA (DTE=7)")
    print(f"   Number of strikes: {len(K_arr)}")
    print(f"   Strike range: ${K_arr[0]:.0f} - ${K_arr[-1]:.0f}")
    print(f"   Call price range: ${C_arr.min():.2f} - ${C_arr.max():.2f}")
    
    # Spot price (estimate from ATM)
    spot = 6833.0  # Known SPX close
    atm_idx = np.argmin(np.abs(K_arr - spot))
    print(f"\n   Estimated spot: ${spot:.2f}")
    print(f"   ATM strike: ${K_arr[atm_idx]:.0f}, Call price: ${C_arr[atm_idx]:.2f}")
    
    # Parameters
    r = 0.04  # Risk-free rate
    T = 7 / 365.25
    print(f"\n2. PARAMETERS")
    print(f"   Risk-free rate (r): {r:.4f}")
    print(f"   Time to expiration (T): {T:.6f} years ({7} days)")
    print(f"   Discount factor e^(rT): {np.exp(r*T):.6f}")
    
    # Fit PCHIP interpolator
    print(f"\n3. INTERPOLATION (PCHIP)")
    pchip = PchipInterpolator(K_arr, C_arr)
    
    # Test at ATM
    K_test = spot
    C_interp = pchip(K_test)
    print(f"   At K=${K_test:.0f}:")
    print(f"     C(K) = ${C_interp:.4f}")
    
    # First derivative
    dC_dK = pchip.derivative(nu=1)(K_test)
    print(f"     dC/dK = {dC_dK:.6f}")
    
    # Second derivative
    d2C_dK2 = pchip.derivative(nu=2)(K_test)
    print(f"     d²C/dK² = {d2C_dK2:.8f}")
    
    # Probability Above (our formula)
    prob_above_raw = -np.exp(r * T) * dC_dK
    print(f"\n4. PROBABILITY ABOVE CALCULATION")
    print(f"   Formula: P(S_T > K) = -e^(rT) * dC/dK")
    print(f"   At K=${K_test:.0f}:")
    print(f"     P(S_T > {K_test:.0f}) = -{np.exp(r*T):.6f} * {dC_dK:.6f}")
    print(f"     P(S_T > {K_test:.0f}) = {prob_above_raw:.6f}")
    
    if prob_above_raw < 0 or prob_above_raw > 1:
        print(f"   ⚠️  WARNING: Probability outside [0,1] range!")
    
    # Calculate prob_above for all strikes
    dC_dK_all = pchip.derivative(nu=1)(K_arr)
    prob_above_all = -np.exp(r * T) * dC_dK_all
    prob_above_all = np.clip(prob_above_all, 0, 1)
    prob_above_all = gaussian_filter1d(prob_above_all, sigma=1.0)
    prob_above_all = np.clip(prob_above_all, 0, 1)
    
    # Find 50% crossing
    idx_50 = np.argmin(np.abs(prob_above_all - 0.5))
    K_50 = K_arr[idx_50]
    
    print(f"\n5. MEDIAN (50% PROBABILITY)")
    print(f"   Median strike: ${K_50:.2f}")
    print(f"   Spot price: ${spot:.2f}")
    print(f"   Offset: ${K_50 - spot:+.2f}")
    print(f"   Expected: Offset should be ~$0 at DTE=7 if no drift")
    
    # Show prob_above around spot
    print(f"\n6. PROB_ABOVE AROUND SPOT")
    print(f"   K        | P(S>K) | dC/dK")
    print(f"   ---------|--------|--------")
    for offset in [-100, -50, 0, 50, 100]:
        K_check = spot + offset
        idx = np.argmin(np.abs(K_arr - K_check))
        K_actual = K_arr[idx]
        p = prob_above_all[idx]
        deriv = dC_dK_all[idx]
        print(f"   ${K_actual:7.0f} | {p:6.4f} | {deriv:8.6f}")
    
    # Theoretical check
    print(f"\n7. THEORETICAL CHECK")
    print(f"   At spot (K=S), we expect:")
    print(f"     - Call price C ≈ intrinsic value + time value")
    print(f"     - dC/dK ≈ -N(d2) ≈ -0.5 for ATM")
    print(f"     - P(S>K) ≈ 0.5 for ATM")
    print(f"   ")
    print(f"   Our result at K=${K_test:.0f}:")
    print(f"     - dC/dK = {dC_dK:.6f}")
    print(f"     - P(S>K) = {prob_above_raw:.6f}")
    
    if dC_dK > -0.3 or dC_dK < -0.7:
        print(f"   ⚠️  dC/dK is outside expected range [-0.7, -0.3]")
        print(f"   This suggests either:")
        print(f"     1. Call prices are not monotonically decreasing")
        print(f"     2. Interpolation is creating artifacts")
        print(f"     3. Data quality issues")
    
    # Plot call prices vs strike
    print(f"\n8. CALL PRICE CURVE SHAPE")
    # Check monotonicity
    price_diffs = np.diff(C_arr)
    decreasing_count = (price_diffs < 0).sum()
    total_count = len(price_diffs)
    print(f"   Monotonically decreasing: {decreasing_count}/{total_count} intervals")
    
    if decreasing_count < total_count:
        print(f"   ⚠️  Call prices are NOT strictly decreasing!")
        print(f"   Non-monotonic points:")
        for i in range(len(price_diffs)):
            if price_diffs[i] >= 0:
                print(f"     K=${K_arr[i]:.0f}: C=${C_arr[i]:.4f} -> K=${K_arr[i+1]:.0f}: C=${C_arr[i+1]:.4f}")


if __name__ == '__main__':
    debug_bl_manually()
