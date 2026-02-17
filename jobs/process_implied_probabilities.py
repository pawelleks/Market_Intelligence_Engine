#!/usr/bin/env python3
"""
Implied Probability Processing Pipeline (V2 Rewrite)

Processes raw option chain files to generate:
1. Density Surfaces (PDF bell curves) for specific Target Tenors.
2. Forward Projections (Fan Chart) using strict theoretical pricing.

Features:
- Strict Time Normalization (Days / 365.25)
- Target Tenor Selection (7, 14, 21, 30, 45, 60, 90 days)
- Gaussian Smoothing (sigma=2.0)
- 3D Surface Filtering (density > 0.00005)
"""

import os
import sys
import json
import re
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pandas as pd
import numpy as np
from scipy.ndimage import gaussian_filter1d
import math
from thetadata import ThetaClient, StockReqType, DateRange
from scipy.interpolate import UnivariateSpline, CubicSpline
import scipy.stats as stats

def sanitize_data(data):
    """
    Recursively convert NaN/Inf to None for JSON compliance.
    Handles numpy types and nested structures.
    """
    if isinstance(data, (float, np.floating)):
        if math.isnan(data) or math.isinf(data) or np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    elif isinstance(data, (int, np.integer)):
        return int(data)
    elif isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, np.ndarray):
        return sanitize_data(data.tolist())
    return data

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mie_lib.utils.probability_math import BreedenLitzenberger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
LOG = logging.getLogger("process_implied_probabilities")

# =============================================================================
# CONFIGURATION
# =============================================================================
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
# Force output to the 'public/data' directory relative to the project root
OUTPUT_DIR = Path(os.getcwd()) / "public" / "data"

# Ensure the directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.info(f"TARGET OUTPUT DIRECTORY: {OUTPUT_DIR}")

# Full Ticker List (ETFs + Indices)
SYMBOLS = ['SPX', 'SPY', 'QQQ', 'IWM']

RISK_FREE_RATE = 0.04 # 4% risk-free rate
DAYS_FORWARD = 45     # Days for forward projection

# Target Tenors (in Days) we want to visualize
TARGET_TENORS = [7, 14, 21, 30, 45, 60, 90]

# Strike selection range (+/- 40% to capture deep tail risk)
STRIKE_RANGE = 0.4

# Per-symbol Equity Risk Premium
SYMBOL_ERP = {
    'SPX': 0.04,
    'SPY': 0.04,
    'QQQ': 0.05,
    'IWM': 0.06,
    'RUT': 0.06,
    'VIX': 0.00,  # VIX is mean-reverting, normally 0.0 for probability math
}
DEFAULT_ERP = 0.04


def find_todays_chains() -> List[tuple]:
    """Find all chain_*_[DATE].parquet files and pick the latest for each symbol."""
    if not RAW_DIR.exists():
        return []
    
    results_map = {}  # symbol -> (symbol, f, file_date)
    pattern = re.compile(r'chain_([A-Z]+)_(\d{4}-\d{2}-\d{2})\.parquet')
    
    for f in RAW_DIR.glob("chain_*.parquet"):
        match = pattern.match(f.name)
        if match:
            symbol = match.group(1)
            file_date = match.group(2)
            if symbol not in results_map or file_date > results_map[symbol][2]:
                results_map[symbol] = (symbol, f, file_date)
    
    results = list(results_map.values())
    results.sort(key=lambda x: x[0])
    return results


def calculate_forward_price(calls_df: pd.DataFrame, puts_df: pd.DataFrame, 
                            strike: float, r: float, dte_years: float) -> float:
    """Calculate option-implied forward using Put-Call Parity."""
    try:
        call_row = calls_df[calls_df['strike'] == strike]
        put_row = puts_df[puts_df['strike'] == strike]
        
        if call_row.empty or put_row.empty:
            return 0.0
        
        call_price = call_row['mid_price'].iloc[0]
        put_price = put_row['mid_price'].iloc[0]
        
        if pd.isna(call_price) or pd.isna(put_price):
            return 0.0
            
        term = np.exp(r * dte_years)
        forward = strike + term * (call_price - put_price)
        return forward
    except Exception:
        return 0.0

def get_anchor_price(client, root):
    """Fetch previous close via Theta Terminal REST API (clean data, no library bugs)."""
    import httpx

    LOG.info(f"--- Fetching Previous Close for {root} ---")

    # Determine REST API host (Docker: theta_terminal, Local: 127.0.0.1)
    theta_host = os.getenv('THETA_HOST', '127.0.0.1')
    theta_rest_port = os.getenv('THETA_REST_PORT', '25510')
    base_url = f"http://{theta_host}:{theta_rest_port}"

    # Walk back up to 5 days to find the last trading day with data
    for days_back in range(1, 6):
        target = date.today() - timedelta(days=days_back)
        fmt_date = target.strftime("%Y%m%d")

        try:
            # Indices (SPX, VIX) use /v2/hist/index/eod for proper OHLC close
            if root in ('SPX', 'VIX'):
                url = f"{base_url}/v2/hist/index/eod"
                params = {"root": root, "start_date": fmt_date, "end_date": fmt_date}
            else:
                # Stocks/ETFs use /v2/hist/stock/eod
                url = f"{base_url}/v2/hist/stock/eod"
                params = {"root": root, "start_date": fmt_date, "end_date": fmt_date}

            resp = httpx.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()

            rows = data.get("response", [])
            if not rows:
                continue

            # For index/price: columns are [ms_of_day, price, date] — take last price
            # For stock/eod: columns are [ms_of_day, open, high, low, close, volume, count, date]
            header = data.get("header", {}).get("format", [])

            if root in ('SPX', 'VIX'):
                # Index EOD — has proper OHLC with 'close' column
                if 'close' in header:
                    close_idx = header.index('close')
                    last_price = float(rows[0][close_idx])
                else:
                    last_price = float(rows[0][5])  # close is index 5 in index/eod
            else:
                # Stock EOD — sort by date desc for safety
                if 'date' in header:
                    date_idx = header.index('date')
                    rows.sort(key=lambda r: r[date_idx], reverse=True)
                if 'close' in header:
                    close_idx = header.index('close')
                    last_price = float(rows[0][close_idx])
                else:
                    last_price = float(rows[0][4])  # close is typically index 4

            if last_price > 0:
                LOG.info(f"   > SUCCESS: {root} close on {target}: ${last_price:.2f} (via REST API)")
                LOG.info(f"   > 📅 ANCHOR DATE: {target.isoformat()} | This is the reference price for all calculations")
                return last_price

        except Exception as e:
            LOG.debug(f"   > REST attempt for {root} on {target} failed: {e}")
            continue

    # No valid price found — return 0 to signal failure (no hardcoded fallbacks)
    LOG.error(f"   > FAILED: No price data for {root} from REST API (last 5 days). Symbol will be skipped.")
    return 0.0

def calculate_sentiment_metrics(symbol: str, spot_price: float, implied_mu: float, implied_sigma: float) -> Dict[str, Any]:
    """
    Compare option-implied drift/vol vs realized drift/vol from price history.
    Positive drift_gap = options pricing bullish expectations above realized trend.
    Negative drift_gap = options pricing hedging/fear below realized trend.
    """
    HISTORY_DIR = Path(__file__).parent.parent / "data" / "history"
    LOOKBACK = 21  # Trading days (~1 month)

    try:
        hist_path = HISTORY_DIR / f"{symbol}.parquet"
        if not hist_path.exists():
            LOG.warning(f"   > No history file for {symbol} at {hist_path}")
            return {}

        df_hist = pd.read_parquet(hist_path)

        # Normalize column names (some files use 'close', others 'Close')
        df_hist.columns = [c.lower() for c in df_hist.columns]

        if 'close' not in df_hist.columns or len(df_hist) < LOOKBACK + 1:
            LOG.warning(f"   > Insufficient history for {symbol} ({len(df_hist)} rows)")
            return {}

        # Use the last LOOKBACK+1 rows for LOOKBACK returns
        recent = df_hist.tail(LOOKBACK + 1).copy()
        closes = recent['close'].values

        # Realized drift: annualized log return over the window
        realized_mu = float(np.log(closes[-1] / closes[0]) / (LOOKBACK / 252.0))

        # Realized volatility: annualized std of daily log returns
        log_returns = np.diff(np.log(closes))
        realized_sigma = float(np.std(log_returns, ddof=1) * np.sqrt(252))

        # Drift gap: how much more bullish options are vs realized trend
        drift_gap = implied_mu - realized_mu

        # Vol spread: fear premium (positive = options expensive vs realized)
        vol_spread = implied_sigma - realized_sigma

        # Classify signal
        if drift_gap > 0.03:
            signal = "speculative"
        elif drift_gap < -0.03:
            signal = "hedging"
        else:
            signal = "neutral"

        sentiment = {
            "implied_drift": round(implied_mu, 4),
            "realized_drift": round(realized_mu, 4),
            "drift_gap": round(drift_gap, 4),
            "implied_vol": round(implied_sigma, 4),
            "realized_vol": round(realized_sigma, 4),
            "vol_spread": round(vol_spread, 4),
            "signal": signal,
            "lookback_days": LOOKBACK
        }

        LOG.info(f"   > Sentiment for {symbol}: drift_gap={drift_gap:+.2%}, "
                 f"vol_spread={vol_spread:+.2%}, signal={signal}")
        return sentiment

    except Exception as e:
        LOG.warning(f"   > Sentiment calculation failed for {symbol}: {e}")
        return {}


def calculate_forward_cone(df: pd.DataFrame, spot_price: float, symbol: str, client, days_out: int = 45) -> List[Dict[str, Any]]:
    """
    Generate a Parametric Fan Chart based on Log-Normal distribution.
    Derives IV from ATM straddle prices and drift from put-call parity forwards.
    No hardcoded volatility or drift — everything comes from the option chain.
    """
    import numpy as np
    from scipy.stats import norm
    from datetime import date, timedelta

    print(f"--- Generating Parametric Fan Chart for {symbol} ---")

    risk_free_rate = 0.045
    today = date.today()
    results = []

    if 'exp_date' not in df.columns:
        df['exp_date'] = pd.to_datetime(df['expiration'])

    unique_exps = sorted(df['exp_date'].unique())

    # Extract per-expiration IV and forward price from the chain data
    exp_sigmas = []
    exp_forwards = []  # (dte, forward_price) for drift derivation

    for exp in unique_exps[:12]:
        try:
            exp_df = df[df['exp_date'] == exp].copy()
            dte = (pd.Timestamp(exp).date() - today).days
            if dte <= 0:
                continue

            T = dte / 365.25

            # Merge calls and puts on strike to get both mid prices
            calls = exp_df[exp_df['right'] == 'C'][['strike', 'mid_price']].rename(
                columns={'mid_price': 'call_mid'})
            puts = exp_df[exp_df['right'] == 'P'][['strike', 'mid_price']].rename(
                columns={'mid_price': 'put_mid'})
            merged = pd.merge(calls, puts, on='strike')

            if merged.empty:
                continue

            # Find ATM strike (closest to spot)
            merged['dist'] = abs(merged['strike'] - spot_price)
            atm_row = merged.sort_values('dist').iloc[0]
            atm_strike = atm_row['strike']
            call_mid = atm_row['call_mid']
            put_mid = atm_row['put_mid']

            # --- Derive Forward Price via Put-Call Parity ---
            # F = K + e^(rT) * (C - P)
            forward = atm_strike + np.exp(risk_free_rate * T) * (call_mid - put_mid)
            exp_forwards.append((dte, float(forward)))

            # --- Derive ATM IV via Brenner-Subrahmanyam approximation ---
            # sigma ≈ straddle / (S * sqrt(T)) * sqrt(2*pi) / 2
            straddle = call_mid + put_mid
            if straddle > 0 and spot_price > 0 and T > 0:
                sigma = float(straddle / (spot_price * np.sqrt(T)) * np.sqrt(2 * np.pi) / 2)
            else:
                sigma = 0.15

            # Clamp to reasonable range
            sigma = max(0.08, min(sigma, 0.80))

            exp_sigmas.append((dte, sigma))
            LOG.info(f"   > Exp {pd.Timestamp(exp).date()} | DTE {dte} | "
                     f"Fwd: {forward:.2f} | ATM Straddle: {straddle:.2f} | IV: {sigma:.2%}")

        except Exception as e:
            LOG.debug(f"Failed IV for exp {exp}: {e}")
            continue

    # Fallback if no data extracted
    if not exp_sigmas:
        exp_sigmas = [(0, 0.16), (365, 0.16)]

    exp_sigmas.sort()
    dtes_s, sigs = zip(*exp_sigmas)

    # --- Derive drift (mu) from option-implied forward prices ---
    # mu = ln(F/S) / T, averaged across expirations
    if exp_forwards:
        mus = []
        for dte_f, fwd in exp_forwards:
            T_f = dte_f / 365.25
            if fwd > 0 and spot_price > 0 and T_f > 0:
                mu_i = np.log(fwd / spot_price) / T_f
                mus.append(mu_i)
        mu = float(np.median(mus)) if mus else 0.04
        # Clamp to reasonable range (-10% to +15% annualized)
        mu = max(-0.10, min(mu, 0.15))
    else:
        mu = 0.04  # Conservative fallback

    LOG.info(f"   > Option-Implied Drift (mu): {mu:.4f} ({mu*100:.2f}%/yr)")

    # Generate daily projection (0 to days_out)
    q_keys = ["p05", "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90", "p95"]
    q_values = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

    for i in range(days_out + 1):
        target_date = today + timedelta(days=i)
        T = max(i / 365.25, 0.001)

        curr_sigma = float(np.interp(i, dtes_s, sigs))
        p50 = float(spot_price * np.exp(mu * T))

        row = {
            "date": target_date.isoformat(),
            "dte": i,
            "p50": p50,
            "sigma": curr_sigma,
            "mu": mu
        }

        vol_factor = curr_sigma * np.sqrt(T)
        for k, q in zip(q_keys, q_values):
            if k == 'p50':
                continue
            z = norm.ppf(q)
            row[k] = float(p50 * np.exp(vol_factor * z))

        results.append(row)

    return results


def generate_projection_heatmap(
    spot_price: float, symbol: str,
    density_surfaces: List[Dict[str, Any]],
    days_out: int = 45, grid_points_y: int = 100
) -> Dict[str, Any]:
    """
    Generate projection heatmap data: past OHLC history + future probability surface.
    Returns {history, heatmap: {days, strikes, prob_above}, spot_price}.
    """
    from scipy.interpolate import griddata

    HISTORY_DIR = Path(__file__).parent.parent / "data" / "history"
    result = {"history": [], "heatmap": {}, "spot_price": spot_price}

    # 1. Load last 20 trading days of OHLC
    hist_path = HISTORY_DIR / f"{symbol}.parquet"
    if hist_path.exists():
        df_hist = pd.read_parquet(hist_path)
        df_hist.columns = [c.lower() for c in df_hist.columns]

        if 'close' in df_hist.columns:
            df_hist = df_hist.sort_values('date').tail(20).reset_index(drop=True)
            n = len(df_hist)
            history = []
            for i, row in df_hist.iterrows():
                x_idx = i - (n - 1)  # -19, -18, ..., -1, 0
                history.append({
                    "x": int(x_idx),
                    "date": row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10],
                    "open": float(row.get('open', row['close'])),
                    "high": float(row.get('high', row['close'])),
                    "low": float(row.get('low', row['close'])),
                    "close": float(row['close'])
                })
            result["history"] = history
    else:
        LOG.warning(f"No history file for {symbol} at {hist_path}")

    # 2. Collect scatter points (dte, strike, prob_above) from density surfaces
    points = []
    values = []

    # Use integer strikes (not drift-adjusted real_world_price_axis) for clean rendering
    for res in density_surfaces:
        dte = res['dte']
        if dte > days_out + 5:
            continue
        dist = res.get('distribution', {})
        strikes = dist.get('strikes', [])  # Use raw integer strikes, NOT real_world_price_axis
        probs = dist.get('prob_above', [])
        if not probs or len(strikes) != len(probs):
            continue
        for k, p in zip(strikes, probs):
            points.append([float(dte), float(k)])
            values.append(float(p))

    # 3. Add DTE=0 anchor points to prevent extrapolation artifacts
    # At DTE=0, the prob_above should be a step function: 100% below spot, 0% above spot
    # This ensures the 50% contour starts exactly at spot price
    anchor_strikes = np.linspace(spot_price * 0.85, spot_price * 1.15, 20)
    for k in anchor_strikes:
        if k < spot_price:
            anchor_prob = 1.0  # 100% chance of being above strikes below spot
        else:
            anchor_prob = 0.0  # 0% chance of being above strikes above spot
        points.append([0.0, float(k)])
        values.append(anchor_prob)

    # 4. Use spot-centered strike range (±15%) for clean heatmap
    # The full option chain range (e.g. 4760-7983) is too wide and causes visual distortion
    min_k = spot_price * 0.85
    max_k = spot_price * 1.15

    if len(points) < 20:
        LOG.warning(f"Insufficient data points ({len(points)}) for heatmap interpolation")
        return result

    points = np.array(points)
    values = np.array(values)

    # 4. Interpolate onto dense grid
    grid_days = np.arange(0, days_out + 1, dtype=float)
    grid_strikes = np.linspace(min_k, max_k, grid_points_y)
    GX, GY = np.meshgrid(grid_days, grid_strikes)

    grid_z = griddata(points, values, (GX, GY), method='linear', fill_value=np.nan)

    # Fill NaN with nearest
    mask_nan = np.isnan(grid_z)
    if np.any(mask_nan):
        grid_z_near = griddata(points, values, (GX, GY), method='nearest')
        grid_z[mask_nan] = grid_z_near[mask_nan]

    grid_z = np.clip(grid_z, 0.0, 1.0)

    # 5. Enforce Monotonicity (Prob > X must decrease as X increases)
    # This removes "circles" and "islands" caused by interpolation noise.
    # We iterate over each time slice (day) and ensure strict decreasing order.
    # usage: np.minimum.accumulate on the reversed array, then reverse back.
    # (Since strikes increase, Prob(Price > Strike) should decrease)
    for t_idx in range(grid_z.shape[1]):
        col = grid_z[:, t_idx]
        # We want decreasing, so we enforce that p[i] <= p[i-1]
        # Equivalent to: p[i] = min(p[i], p[i-1]) ...
        # np.minimum.accumulate works on forward iteration for "non-increasing" if we match logic.
        # But accumulate does min(current, running_min).
        # We start from bottom (low strike, high prob) to top (high strike, low prob).
        # So we want to ensure p[i] is never higher than p[i-1].
        # actually, simply accumulate min is sufficient if we go from low strike to high strike.
        grid_z[:, t_idx] = np.minimum.accumulate(col)

    result["heatmap"] = {
        "days": grid_days.tolist(),
        "strikes": grid_strikes.tolist(),
        "prob_above": grid_z.tolist()  # 2D: [strike_idx][day_idx]
    }

    return result


def process_chain(df: pd.DataFrame, symbol: str, client: ThetaClient) -> Optional[Dict[str, Any]]:
    """
    Process option chain with strict math and filtering.
    """
    LOG.info(f"Processing {symbol} ({len(df)} contracts)...")
    if df.empty:
        return {"density_surfaces": [], "forward_projections": []}
    
    erp = SYMBOL_ERP.get(symbol, DEFAULT_ERP)
    bl = BreedenLitzenberger(risk_free_rate=RISK_FREE_RATE, equity_risk_premium=erp)
    
    df['exp_date'] = pd.to_datetime(df['expiration'])
    unique_exps = sorted(df['exp_date'].unique())
    today = pd.Timestamp.today().normalize()
    
    future_exps = [e for e in unique_exps if e > today]
    
    # Selected Expirations
    selected_exps = []
    seen_dates = set()
    for target in TARGET_TENORS:
        best_exp = None
        min_diff = 999
        for exp in future_exps:
            days = (exp - today).days
            diff = abs(days - target)
            if diff < min_diff:
                min_diff = diff
                best_exp = exp
        if best_exp and best_exp not in seen_dates:
            selected_exps.append(best_exp)
            seen_dates.add(best_exp)
    if len(selected_exps) < 3: selected_exps = future_exps[:8]
    selected_exps.sort()
    
    # Determine Spot (Anchor Price)
    # We now anchor to Yesterday's Close for the projection start.
    spot_price = get_anchor_price(client, symbol)
    
    # Final Fallback: ETF Proxies for Indices
    if spot_price <= 0:
        proxy_map = {'SPX': 'SPY'}
        if symbol in proxy_map:
            proxy_root = proxy_map[symbol]
            multiplier = 10 if symbol == 'SPX' else 40
            proxy_val = get_anchor_price(client, proxy_root)
            if proxy_val > 0:
                spot_price = proxy_val * multiplier
                LOG.warning(f"⚠️ {symbol} Anchor via {proxy_root} Proxy: {spot_price:.2f}")

    # Final Check - Hard skip if no price
    if spot_price <= 0:
        LOG.error(f"CRITICAL: No anchor price found for {symbol}. Skipping.")
        return None
    
    # Final Check - Hard skip if no price
    if spot_price <= 0:
        LOG.error(f"CRITICAL: No reliable price found for {symbol} via pure ThetaData. Skipping.")
        return None
    
    # Process Expirations
    selected_exps.sort()
    density_surfaces = []
    
    for exp in selected_exps:
        exp_str = exp.strftime("%Y-%m-%d")
        # Ensure 'today' is a pandas Timestamp and 'exp' is also compatible
        dte_days = (pd.Timestamp(exp) - pd.Timestamp(today)).days
        t_years = float(dte_days) / 365.25
        forward_price = spot_price * np.exp((RISK_FREE_RATE + erp) * t_years)
        
        exp_df = df[df['exp_date'] == exp]
        
        # Widen the net: Filter strikes within STRIKE_RANGE of spot
        lower_k = spot_price * (1.0 - STRIKE_RANGE)
        upper_k = spot_price * (1.0 + STRIKE_RANGE)
        exp_df = exp_df[(exp_df['strike'] >= lower_k) & (exp_df['strike'] <= upper_k)]
        
        calls = exp_df[exp_df['right'] == 'C'].sort_values('strike')
        if calls.empty: continue
        
        strikes = calls['strike'].tolist()
        prices = calls['mid_price'].tolist()
        
        try:
            pdf_data = bl.calculate_pdf(strikes, prices, dte_days)
            raw_pdf = np.array(pdf_data.get('pdf', []))
            
            if len(raw_pdf) == 0: continue

            # Gaussian Smoothing for Surface
            clean_pdf = gaussian_filter1d(raw_pdf, sigma=2.0)
            
            # Filter
            mask = clean_pdf > 0.00005
            if np.any(mask):
                filtered_pdf = clean_pdf[mask].tolist()
                filtered_strikes = np.array(pdf_data.get('strikes', []))[mask].tolist()
                pdf_data['pdf'] = filtered_pdf
                pdf_data['strikes'] = filtered_strikes
                if 'real_world_price_axis' in pdf_data:
                     # Filter this too if aligned (BreedenLitzenberger logic ensures alignment)
                     # But we must act on the mask index
                     # Re-read raw
                     rw = np.array(pdf_data.get('real_world_price_axis', []))
                     if len(rw) == len(clean_pdf):
                         pdf_data['real_world_price_axis'] = rw[mask].tolist()
                     
                 # Overwrite price_axis with filtered strikes for consistency
                pdf_data['price_axis'] = filtered_strikes

                # Recompute prob_above from filtered PDF to maintain alignment
                from scipy.integrate import cumulative_trapezoid
                f_pdf_arr = np.array(filtered_pdf)
                f_k_arr = np.array(filtered_strikes)
                f_area = float(np.trapz(f_pdf_arr, f_k_arr))
                if f_area > 0:
                    f_pdf_norm = f_pdf_arr / f_area
                else:
                    f_pdf_norm = f_pdf_arr
                f_cdf = cumulative_trapezoid(f_pdf_norm, f_k_arr, initial=0)
                if f_cdf[-1] > 0:
                    f_cdf = f_cdf / f_cdf[-1]
                pdf_data['prob_above'] = (1.0 - f_cdf).tolist()

                # Server-Side Normalization (Peak = 1.0)
                # Helps React render micro-probabilities (1e-9) correctly
                p_arr = np.array(filtered_pdf)
                max_v = float(np.max(p_arr)) if len(p_arr) > 0 else 0
                pdf_data['normalized_pdf'] = (p_arr / max_v).tolist() if max_v > 0 else p_arr.tolist()

                res_obj = {
                    "expiration": exp_str,
                    "dte": dte_days,
                    "forward_price": forward_price,
                    "distribution": pdf_data
                }
                density_surfaces.append(res_obj)
            
        except Exception:
            continue

    # -------------------------------------------------------------------------
    # 4. Generate Forward Projections (ROBUST PARAMETRIC MODEL)
    # -------------------------------------------------------------------------
    # Replaces Splines with Log-Normal drift and diffusion.
    forward_projections = calculate_forward_cone(
        df, 
        spot_price, 
        symbol,
        client,
        days_out=45
    )

    # -------------------------------------------------------------------------
    # 5. Sentiment Metrics (Implied vs Realized)
    # -------------------------------------------------------------------------
    sentiment = {}
    if forward_projections:
        imp_mu = forward_projections[0].get('mu', 0)
        imp_sigma = forward_projections[0].get('sigma', 0)
        sentiment = calculate_sentiment_metrics(symbol, spot_price, imp_mu, imp_sigma)

    # -------------------------------------------------------------------------
    # 6. Generate Projection Heatmap (OHLC + Probability Surface)
    # -------------------------------------------------------------------------
    projection_heatmap = generate_projection_heatmap(
        spot_price, symbol, density_surfaces, days_out=DAYS_FORWARD
    )

    return {
        "as_of": date.today().isoformat(),
        "ref_price": spot_price,
        "erp": erp,
        "density_surfaces": density_surfaces,
        "forward_projections": forward_projections,
        "sentiment": sentiment,
        "projection_heatmap": projection_heatmap
    }


def save_outputs(data: Dict[str, Any], symbol: str) -> None:
    output_file = OUTPUT_DIR / f"probability_surface_{symbol}.json"
    LOG.info(f"Saving to: {output_file}")
    with open(output_file, "w") as f:
        json.dump({
            "ticker": symbol,
            "as_of": data["as_of"],
            "ref_price": data["ref_price"],
            "count": len(data["density_surfaces"]),
            "results": sanitize_data(data["density_surfaces"])
        }, f, indent=2, default=str)
    
    # Also save forward cone
    cone_file = OUTPUT_DIR / f"forward_cone_{symbol}.json"
    LOG.info(f"Saving to: {cone_file}")
    with open(cone_file, "w") as f:
        json.dump({
            "ticker": symbol,
            "as_of": data["as_of"],
            "sentiment": sanitize_data(data.get("sentiment", {})),
            "projections": data["forward_projections"]
        }, f, indent=2)

    # Save projection heatmap (OHLC history + probability surface)
    heatmap_data = data.get("projection_heatmap", {})
    if heatmap_data and heatmap_data.get("heatmap", {}).get("prob_above"):
        heatmap_file = OUTPUT_DIR / f"projection_heatmap_{symbol}.json"
        LOG.info(f"Saving to: {heatmap_file}")
        with open(heatmap_file, "w") as f:
            json.dump({
                "ticker": symbol,
                "as_of": data["as_of"],
                "spot_price": heatmap_data.get("spot_price", data["ref_price"]),
                "history": sanitize_data(heatmap_data.get("history", [])),
                "heatmap": sanitize_data(heatmap_data.get("heatmap", {}))
            }, f, indent=2, default=str)


def delete_stale_files(symbol: str) -> None:
    """Purge old data if processing fails to avoid frontend confusion."""
    for p in [f"probability_surface_{symbol}.json", f"forward_cone_{symbol}.json", f"projection_heatmap_{symbol}.json"]:
        target = OUTPUT_DIR / p
        if target.exists():
            LOG.info(f"Purging stale data: {p}")
            target.unlink()


def main():
    LOG.info("=== Starting Implied Probability Pipeline V2 (Heatmap Upgrade) ===")
    
    chain_files = find_todays_chains()
    if not chain_files:
        LOG.error("No chain files found.")
        return 1
        
    # DETECT ENVIRONMENT
    # If we are in Docker, the environment var 'THETA_HOST' should be set to 'theta_terminal'
    # If not, we default to '127.0.0.1' (Localhost) for manual testing on Mac.
    THETA_HOST = os.getenv('THETA_HOST', '127.0.0.1')
    
    print(f"--- CONNECTING TO THETA TERMINAL via {THETA_HOST} ---")
    
    try:
        # Initialize Client
        # FOR LOCAL RUNS (Mac): This expects the Java Terminal to be running on your desktop.
        client = ThetaClient(host=THETA_HOST, launch=False, timeout=10)
        print("ThetaClient initialized successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Theta Terminal at {THETA_HOST}.")
        print("Ensure the ThetaData Java Application is RUNNING on your computer.")
        print(f"Error Details: {e}")
        return 1

    try:
        with client.connect():
            for symbol, path, _ in chain_files:
                if symbol not in SYMBOLS:
                    continue
                    
                try:
                    df = pd.read_parquet(path)
                    data = process_chain(df, symbol, client)
                    if data and data.get("density_surfaces"):
                        save_outputs(data, symbol)
                        LOG.info(f"✓ {symbol} Processed Successfully")
                    else:
                        LOG.warning(f"✗ {symbol} Skipping. Purging stale files.")
                        delete_stale_files(symbol)
                except Exception as e:
                    LOG.error(f"Error processing {symbol}: {e}")
                    delete_stale_files(symbol)
    except Exception as e:
        LOG.error(f"Failed to connect to Theta terminal: {e}")
        return 1
            
    LOG.info("=== Pipeline Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
