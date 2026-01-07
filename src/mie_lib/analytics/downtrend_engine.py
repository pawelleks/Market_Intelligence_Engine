import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

DEFAULT_WEIGHTS = {
    'price_lt_ema50': 0.15,
    'ema20_lt_ema50': 0.10,
    'mom21_lt_0': 0.10,
    'atr_gt_sma63': 0.10,
    'rv20_gt_rv63': 0.10,
    'vix_term_pos': 0.15,
    'rsp_spy_63_neg': 0.15,
    'hyg_lqd_21_neg': 0.10,
    'hmm_bear_prob': 0.15
}

# --- Core Logic Functions (Refactored for alignment robustness) ---

def _prepare_df(df_aligned: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Standardizes columns for the scoring engine (close, high, low, base price, base return)."""
    
    if df_aligned.empty:
        return df_aligned
        
    df = df_aligned.copy()
    
    # 1. Ensure Date is index
    if 'Date' in df.columns:
        df = df.set_index('Date')
    
    # 2. Standardize OHLC columns for ATR calculation
    # Note: data_aligner returns lowercase columns. We check for them.
    # If duplicates exist (e.g. High and high), we drop duplicates to avoid DataFrame return.
    df = df.loc[:, ~df.columns.duplicated()]

    for col in ['high', 'low', 'close', 'adj_close']:
        if col not in df.columns:
            # Try capitalized version if lowercase missing
            if col.capitalize() in df.columns:
                df[col] = df[col.capitalize()]
            else:
                df[col] = np.nan
            
    # 3. Standardize Base Price and Return
    # The data aligner returns ticker_Price (e.g., SPY_Price). We need 'Price' and 'ret'.
    
    # Check if we have the specific ticker price
    price_col = f'{ticker}_Price'
    # Also check for SPY_Price as fallback or if ticker is SPY
    if price_col in df.columns:
        df['Price'] = df[price_col].astype('float32')
        df['ret'] = df[price_col].pct_change().astype('float32')
    elif 'SPY_Price' in df.columns: 
        df['Price'] = df['SPY_Price'].astype('float32')
        df['ret'] = df['SPY_Price'].pct_change().astype('float32')
    
    # 4. Standardize Auxiliary Price Columns (rename VIX_Price -> ^VIX_Price if necessary, ensure lowercase)
    df.columns = [c.lower() for c in df.columns]
    
    return df.dropna(subset=['price']) # Drop rows where we can't calculate a score


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates 9 technical/structural signals across all historical dates."""

    out = pd.DataFrame(index=df.index)
    price = df['price'].astype('float32') # Uses standardized 'price'
    ret = df['ret'].astype('float32')

    # --- Trend Signals ---
    ema50 = price.ewm(span=50, adjust=False).mean()
    ema20 = price.ewm(span=20, adjust=False).mean()
    mom21 = price.diff(21)
    
    out['price_lt_ema50'] = (price < ema50).astype(float)
    out['ema20_lt_ema50'] = (ema20 < ema50).astype(float)
    out['mom21_lt_0'] = (mom21 < 0).astype(float)

    # --- Volatility/ATR Signals ---
    if all(c in df.columns for c in ['high', 'low', 'close']):
        h = df['high'].astype('float32')
        l = df['low'].astype('float32')
        c = df['close'].astype('float32')
        prev_c = c.shift(1)
        tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        atr63 = atr14.rolling(63).mean()
        out['atr_gt_sma63'] = ((atr14 / price) > (atr63 / price.replace(0, np.nan))).astype(float)
    else: out['atr_gt_sma63'] = np.nan
        
    rv20 = ret.rolling(20).std()
    rv63 = ret.rolling(63).std()
    out['rv20_gt_rv63'] = (rv20 > rv63).astype(float)

    # --- Market Structure Signals ---
    # NOTE: Auxiliary tickers are now lowercase, e.g., '^vix_price'
    if all(c in df.columns for c in ['^vix_price', '^vix3m_price']):
        term_diff = df['^vix_price'] - df['^vix3m_price']
        out['vix_term_pos'] = (term_diff > 0).astype(float)
    else: out['vix_term_pos'] = np.nan

    if all(c in df.columns for c in ['rsp_price']):
        rsp_price = df['rsp_price'].astype('float32')
        # Ensure alignment
        ratio = pd.Series(rsp_price.values / price.values, index=df.index)
        ratio_return63 = ratio.pct_change(63)
        
        # Handle NaN propagation correctly
        mask = ratio_return63.notna()
        out.loc[mask, 'rsp_spy_63_neg'] = (ratio_return63[mask] < 0).astype(float)
        out.loc[~mask, 'rsp_spy_63_neg'] = np.nan
    else: out['rsp_spy_63_neg'] = np.nan

    if all(c in df.columns for c in ['hyg_price', 'lqd_price']):
        hyg_a = df['hyg_price'].astype('float32')
        lqd_a = df['lqd_price'].astype('float32')
        credit_ratio21 = (hyg_a / lqd_a).pct_change(21)
        
        mask = credit_ratio21.notna()
        out.loc[mask, 'hyg_lqd_21_neg'] = (credit_ratio21[mask] < 0).astype(float)
        out.loc[~mask, 'hyg_lqd_21_neg'] = np.nan
    else: out['hyg_lqd_21_neg'] = np.nan
        
    if 'hmm_bear_prob' in df.columns:
        out['hmm_bear_prob'] = df['hmm_bear_prob'].astype(float)
    else: out['hmm_bear_prob'] = np.nan

    return out.astype('float32')


def compute_weighted_scores(signals_df: pd.DataFrame, weights_map: Dict[str, float]) -> pd.Series:
    """Calculates the final weighted score (0-100) per row, renormalizing weights for missing data."""
    comp_names = signals_df.columns.tolist()
    base_w = np.array([weights_map.get(c, 0.0) for c in comp_names], dtype=float)
    vals = signals_df.values.astype(float)
    
    valid = ~np.isnan(vals)
    W = np.zeros_like(vals, dtype=float)
    
    for i in range(len(vals)):
        active = valid[i].astype(float)
        w = base_w * active
        s = w.sum()
        if s <= 0:
            w = active / active.sum() if active.sum() > 0 else np.zeros_like(w)
        else:
            w = w / s
        W[i, :] = w

    contrib = np.nan_to_num(vals, nan=0.0) * W
    score01 = contrib.sum(axis=1)
    score100 = (score01 * 100.0).astype(float)
    
    return pd.Series(score100, index=signals_df.index)


# --- Public API Wrapper Functions ---

def compute_downtrend_score_historical(
    df_aligned: pd.DataFrame, 
    weights: Dict[str, float] = DEFAULT_WEIGHTS,
    ticker: str = 'SPY'
) -> List[Dict[str, Any]]:
    """Computes the score for every date in the historical DataFrame and returns (Date, Score) records."""
    
    df = _prepare_df(df_aligned, ticker) 
    signals_df = compute_signals(df) 
    score_series = compute_weighted_scores(signals_df, weights)
    
    # Format for frontend plotting
    out_df = pd.DataFrame({
        "date": df.index,
        "score": score_series.values
    }).dropna()
    
    out_df['date'] = out_df['date'].dt.strftime('%Y-%m-%d')
    
    return out_df[['date', 'score']].to_dict(orient='records')

def compute_downtrend_signals_historical(
    df_aligned: pd.DataFrame, 
    weights: Dict[str, float] = DEFAULT_WEIGHTS,
    ticker: str = 'SPY'
) -> List[Dict[str, Any]]:
    """Computes the score AND individual signals for every date in history."""
    
    df = _prepare_df(df_aligned, ticker) 
    signals_df = compute_signals(df) 
    score_series = compute_weighted_scores(signals_df, weights)
    
    # Combine score with signals
    out_df = signals_df.copy()
    out_df['score'] = score_series
    out_df['date'] = df.index
    
    # Drop rows with NaN score (meaning insufficient data)
    out_df = out_df.dropna(subset=['score'])
    
    out_df['date'] = out_df['date'].dt.strftime('%Y-%m-%d')
    
    # Replace NaN signals with None for JSON compliance
    out_df = out_df.replace({np.nan: None})
    
    # Move date to front
    cols = ['date', 'score'] + [c for c in out_df.columns if c not in ['date', 'score']]
    out_df = out_df[cols]
    
    return out_df.to_dict(orient='records')

def compute_downtrend_score_latest(
    df_aligned: pd.DataFrame, 
    weights: Dict[str, float] = DEFAULT_WEIGHTS,
    ticker: str = 'SPY'
) -> Dict[str, Any]:
    """Computes the score for the latest date and returns the component breakdown."""
    
    df = _prepare_df(df_aligned, ticker) # Prep data
    
    if df.empty:
         return {
            "latest_score_100": 0.0,
            "check_date": "N/A",
            "breakdown": []
        }

    # Compute signals on FULL history to ensure rolling windows work
    signals_full = compute_signals(df)
    score_series = compute_weighted_scores(signals_full, weights)
    
    # Now slice the latest result
    latest_score = float(score_series.iloc[-1])
    latest_signals = signals_full.iloc[-1].to_dict()
    latest_date = df.index[-1]
    
    # Renormalize weights based on active signals for the latest date
    final_weights = {}
    total_weight_norm = 0.0
    
    for key in signals_full.columns:
        if not np.isnan(latest_signals.get(key, np.nan)):
            total_weight_norm += weights.get(key, 0.0)
    
    breakdown = []
    for key, val in latest_signals.items():
        w_base = weights.get(key, 0.0)
        w_final = w_base / total_weight_norm if total_weight_norm > 0 else 0.0
        
        breakdown.append({
            "signal": key,
            "raw_value": float(val) if not np.isnan(val) else None,
            "weight": float(w_final),
            "contribution": float(val * w_final) if not np.isnan(val) else 0.0,
            "active": bool(val >= 0.5)
        })

    # Calculate Confidence (Percentage of available signals)
    total_signals_count = len(weights)
    available_signals_count = sum(1 for k, v in latest_signals.items() if not np.isnan(v))
    confidence = (available_signals_count / total_signals_count * 100.0) if total_signals_count > 0 else 0.0

    return {
        "latest_score_100": latest_score,
        "check_date": latest_date.strftime('%Y-%m-%d'),
        "confidence": confidence,
        "breakdown": breakdown
    }

def calculate_and_save_dcs(ticker: str = "SPY"):
    """
    Batch job: Calculates full history and latest snapshot for DCS.
    Saves to:
      - data/analytics/dcs/{ticker}_history.parquet
      - data/analytics/dcs/{ticker}_latest.json
    """
    from mie_lib.utils.paths import DATA_DIR
    from mie_lib.utils.io import atomic_write_parquet, atomic_write_json
    from mie_lib.data_ingest.data_aligner import fetch_and_align_dcs_assets
    import pandas as pd
    
    dcs_dir = DATA_DIR / "analytics" / "dcs"
    dcs_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch & Align
    # Use long lookback for history (e.g. 50 years to catch everything)
    df_aligned, weights = fetch_and_align_dcs_assets(ticker, lookback_days=50*365)
    
    if df_aligned.empty:
        print(f"DCS: No data aligned for {ticker}. Skipping.")
        return

    # 2. Compute History
    # This returns List[Dict]
    history_records = compute_downtrend_signals_historical(df_aligned, weights=weights, ticker=ticker)
    if not history_records:
        print(f"DCS: No metrics computed for {ticker}.")
        return

    # Convert history back to DF for Parquet storage
    # history_records has 'date' as string, 'score', and boolean signals
    df_hist = pd.DataFrame(history_records)
    
    atomic_write_parquet(df_hist, dcs_dir / f"{ticker}_history.parquet")
    
    # 3. Compute Latest
    # Calling latest ensures we get the 'breakdown' format required by the UI
    latest_data = compute_downtrend_score_latest(df_aligned, weights=weights, ticker=ticker)
    
    atomic_write_json(latest_data, dcs_dir / f"{ticker}_latest.json")
    
    print(f"DCS: Saved {ticker} history ({len(df_hist)} rows) and latest score ({latest_data.get('latest_score_100')})")
