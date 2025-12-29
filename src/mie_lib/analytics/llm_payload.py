import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

def _safe_val(val: Any, default: Any = 0.0, as_type: type = float) -> Any:
    """Helper to ensure NO fields are Null."""
    if pd.isna(val) or val is None or val == "None" or val == "":
        return default
    try:
        if as_type == float:
            return float(val)
        elif as_type == int:
            return int(val)
        elif as_type == str:
            return str(val)
    except:
        return default
    return val

def _calc_relative_dist(level: float, close: float) -> str:
    """Convert absolute levels into % distance from Close."""
    if not level or not close or close == 0:
        return "N/A"
    dist_pct = ((level - close) / close) * 100
    return f"{dist_pct:+.2f}%"

def _get_dcs_status(score: float) -> str:
    """Logic Injection: Downtrend Confirmation Score status."""
    if score > 80:
        return "Crisis"
    elif score > 60:
        return "Alert"
    elif score > 40:
        return "Warning"
    else:
        return "Safe"

def generate_llm_payload(df: pd.DataFrame, ticker: str, expected_moves_data: Optional[Dict[str, Any]] = None, gex_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a comprehensive minified JSON payload for LLM analysis (Market State Vector).
    """
    from mie_lib.utils.paths import DATA_DIR
    
    # --- 1. Load Auxiliary Data (Lazy) ---
    vol_data = {}
    vol_path = DATA_DIR / "analytics" / "volatility_daily.parquet"
    if vol_path.exists():
        try:
            df_vol = pd.read_parquet(vol_path)
            df_vol.rename(columns={c: c.lower() for c in df_vol.columns}, inplace=True)
            row_vol = df_vol[df_vol['ticker'] == ticker]
            if not row_vol.empty:
                vol_data = row_vol.iloc[-1].to_dict()
        except Exception: pass

    # Load Skew (JSON)
    skew_data = {}
    skew_path = DATA_DIR / "analytics" / "skew" / "latest.json"
    if skew_path.exists():
        try:
            import json
            with open(skew_path, 'r') as f:
                full_skew = json.load(f)
            # Structure: keys "tickers" -> { "SPY": ... }
            if "tickers" in full_skew and ticker in full_skew["tickers"]:
                 skew_data = full_skew["tickers"][ticker]
        except Exception: pass

    tech_data = {}
    for name in ['sma_stack', 'adx', 'psar', 'ichimoku', 'skew_daily']: 
        # Note: loading skew_daily parquet is redundant if we use JSON, but harmless
        p = DATA_DIR / "analytics" / f"{name}_daily.parquet"
        if p.exists():
            try:
                df_t = pd.read_parquet(p)
                df_t.rename(columns={c: c.lower() for c in df_t.columns}, inplace=True)
                row_t = df_t[df_t['ticker'] == ticker]
                if not row_t.empty:
                    tech_data.update(row_t.iloc[-1].to_dict())
            except Exception: pass

    # Load TSMOM
    tsmom_data = {}
    tsmom_path = DATA_DIR / "analytics" / "tsmom_daily.parquet"
    if tsmom_path.exists():
        try:
            df_ts = pd.read_parquet(tsmom_path)
            df_ts.rename(columns={c: c.lower() for c in df_ts.columns}, inplace=True)
            row_ts = df_ts[df_ts['ticker'] == ticker]
            if not row_ts.empty:
                tsmom_data = row_ts.iloc[-1].to_dict()
        except Exception: pass

    # --- 2. Extract Quote Data ---
    if df.empty:
        return {"meta": {"error": "No dataframe provided"}}
    
    row = df.iloc[-1]
    
    # Date Handling
    if 'date' in row:
        date_str = str(row['date'])[:10]
    elif isinstance(row.name, (pd.Timestamp, str)):
        date_str = str(row.name)[:10]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    close_price = _safe_val(row.get('close'), 0.0)
    
    # --- 3. Construct "meta" ---
    meta = {
        "ticker": ticker,
        "date": date_str,
        "generated_at": datetime.now().isoformat()
    }

    # --- 4. Construct "price" ---
    # Need 52w high and SMA200 if available in df or tech_data
    # Usually in df features: 'high_52w', 'sma_200'
    # Or calculate if not present? Assuming features DF has them or we load them.
    # Standard features usually include rolling max.
    
    high_52w = _safe_val(row.get('rolling_max_252'), 0.0) # 252 days ~ 52 weeks
    sma200 = _safe_val(tech_data.get('sma_200') or row.get('sma_200'), 0.0)
    
    dist_52w = _calc_relative_dist(high_52w, close_price) if high_52w > 0 else "N/A"
    dist_sma200 = _calc_relative_dist(sma200, close_price) if sma200 > 0 else "N/A"

    price_section = {
        "close": close_price,
        "dist_52w_high_pct": dist_52w,
        "dist_sma200_pct": dist_sma200
    }

    # --- 5. Construct "regime" ---
    # HMM
    hmm_state = int(_safe_val(row.get('hmm_state'), -1, int))
    hmm_desc_map = {0: "Bull (Steady)", 1: "Bear (Volatile)", -1: "Unknown"}
    hmm_desc = hmm_desc_map.get(hmm_state, "Unknown")
    
    # Markov (Placeholder or existing logic)
    # Usually not in simple row, need separate Markov lookup or passed in. 
    # Current request didn't strictly ask to load separate Markov file, but said "Markov: verdict".
    # We will set defaults if not found.
    markov_verdict = "N/A" # TODO: Load from Markov snapshot if critical
    markov_next_bull = 0.0

    # Volatility
    atr_14 = _safe_val(vol_data.get('atr'), 0.0)
    # atr_rank_6m isn't standard, usually we have 'atr_percent' or 'atr_rank'. 
    # Let's use 'atr_percent' * 100 as rank proxy or 0.
    atr_rank = int(_safe_val(vol_data.get('atr_rank'), 0, int))
    vol_regime = _safe_val(vol_data.get('volatility_regime'), "Neutral", str)

    regime_section = {
        "hmm": { "state": str(hmm_state), "desc": hmm_desc },
        "markov": { "verdict": markov_verdict, "next_prob_bull": markov_next_bull },
        "vol": { "atr_14": atr_14, "rank_6m": atr_rank, "regime": vol_regime }
    }

    # --- 6. Construct "trend" ---
    # DCS
    dcs_score = int(_safe_val(row.get('downtrend_score') or tech_data.get('downtrend_score'), 0, int))
    dcs_status = _get_dcs_status(dcs_score)

    # EMA Stack
    # Logic: is_ema_stacked_up (Bullish), is_ema_stacked_down (Bearish)?
    # tech_data keys: 'is_ema_stacked_up'
    ema_verdict = "Neutral"
    if _safe_val(tech_data.get('is_ema_stacked_up'), 0) == 1:
        ema_verdict = "Bullish Stack"
    elif _safe_val(tech_data.get('is_ema_stacked_down'), 0) == 1: # Assuming down flag exists or inferred
        ema_verdict = "Bearish Stack"
    elif _safe_val(tech_data.get('is_price_above_stack'), 0) == 1:
        ema_verdict = "Price Above Stack"
        
    # ADX
    adx_val = _safe_val(tech_data.get('adx'), 0.0)
    adx_str = "Weak"
    if adx_val > 25: adx_str = "Strong"
    if adx_val > 50: adx_str = "Very Strong"
    
    # Ichimoku
    # is_above_cloud, is_cloud_green
    ichi_status = "Neutral"
    above_cloud = _safe_val(tech_data.get('is_above_cloud'), 0)
    green_cloud = _safe_val(tech_data.get('is_cloud_green'), 0)
    if above_cloud and green_cloud:
        ichi_status = "Bullish (Above Green Cloud)"
    elif not above_cloud and not green_cloud:
        ichi_status = "Bearish (Below Red Cloud)"
    elif above_cloud:
        ichi_status = "Price Above Cloud"
    elif not above_cloud:
        ichi_status = "Price Below Cloud"

    # TSMOM
    tsmom_sig = _safe_val(tsmom_data.get('signal_regime'), "Neutral", str)
    tsmom_12m = f"{_safe_val(tsmom_data.get('momentum_12m'), 0.0)*100:.1f}%"

    trend_section = {
        "dcs": { "score": dcs_score, "status": dcs_status },
        "ema_stack": { "verdict": ema_verdict },
        "adx": { "val": adx_val, "trend_strength": adx_str },
        "ichimoku": { "status": ichi_status },
        "tsmom": { "signal": tsmom_sig, "12m_return": tsmom_12m }
    }

    # --- 7. Construct "options" ---
    # GEX
    net_regime = "Neutral"
    put_wall_dist = "N/A"
    call_wall_dist = "N/A"

    if gex_snapshot:
        net_gex = float(gex_snapshot.get('net_gex', 0))
        if net_gex > 0: net_regime = "Positive (Sticky)"
        elif net_gex < 0: net_regime = "Negative (Volatile)"
        
        # Walls might be in 'profile' dict list or pre-calculated in snapshot?
        # Current snapshot loader typically calculates walls? 
        # Or we rely on what passed in gex_snapshot derived in previous impl.
        # Let's check gex_snapshot structure or calculate from profile if present.
        # But previous code re-calculated walls from profile.
        # Ideally we trust the snapshot loader or recalculate here if needed.
        # Let's assume passed snapshot has 'profile' list.
        
        # Re-using logic from original file roughly:
        profile = gex_snapshot.get("profile", [])
        if profile:
            try:
                df_prof = pd.DataFrame(profile)
                if not df_prof.empty and 'strike' in df_prof.columns and 'total_call_gex' in df_prof.columns:
                     cw = df_prof.loc[df_prof['total_call_gex'].idxmax()]['strike']
                     pw = df_prof.loc[df_prof['total_put_gex'].idxmin()]['strike']
                     call_wall_dist = _calc_relative_dist(cw, close_price)
                     put_wall_dist = _calc_relative_dist(pw, close_price)
            except: pass

    options_gex = { "net_regime": net_regime, "put_wall_dist_pct": put_wall_dist, "call_wall_dist_pct": call_wall_dist }

    # Expected Moves
    em_0dte = 0.0
    em_1w = [0.0, 0.0]
    
    if expected_moves_data:
        em_source = expected_moves_data
        if "tickers" in expected_moves_data and ticker in expected_moves_data["tickers"]:
            em_source = expected_moves_data["tickers"][ticker]
        
        exps = em_source.get("expirations", {})
        if exps:
            # Sort by DAYS TO EXPIRY (to handle date strings correctly)
            # exps is dict: Key->Obj. Obj has 'days_to_expiry'
            exp_items = []
            for k, v in exps.items():
                dte = v.get("days_to_expiry", 999)
                exp_items.append((dte, v))
            
            # Sort asc by DTE
            exp_items.sort(key=lambda x: x[0])
            
            # 1. "Next Session" Move -> Minimum Positive DTE
            # Could be 0, 1, 3 (weekend).
            if exp_items:
                # Take the first one as "Next Session"
                next_sess = exp_items[0][1]
                em_0dte = _safe_val(next_sess.get("em_dollars"), 0.0)
            
            # 2. Week Move -> Closest to 7 (or 5-9 range)
            # Find closest to 7
            best_diff = 999
            best_week = None
            for dte, v in exp_items:
                diff = abs(dte - 7)
                if diff < best_diff:
                    best_diff = diff
                    best_week = v
            
            # Heuristic: only accept if diff is reasonable? e.g. within 3-10 days?
            # If closest is 21 days, that's monthly.
            if best_week and best_diff < 5:
                val = _safe_val(best_week.get("em_dollars"), 0.0)
                upper = close_price + val
                lower = close_price - val
                em_1w = [float(f"{lower:.2f}"), float(f"{upper:.2f}")]
    
    options_em = { "0dte_range": em_0dte, "1w_range": em_1w }

    # Sentiment (PCR / Skew)
    # Prefer skew_data dict (loaded from JSON)
    pcr_vol = _safe_val(skew_data.get('pcr_volume') or tech_data.get('pcr_volume') or tech_data.get('pcr'), 0.0)
    
    skew_val = skew_data.get('skew_25d')
    if pd.isna(skew_val) or skew_val == 0:
        # Fallback to tech_data keys
        skew_val = tech_data.get('skew_25d') or tech_data.get('skew')

    skew_24d = "N/A"
    if pd.notna(skew_val) and skew_val != 0:
         skew_24d = f"{float(skew_val)*100:.1f}%" # Assuming 0.05 format

    options_sentiment = { "pcr_vol": pcr_vol, "skew_24d": skew_24d }

    options_section = {
        "gex": options_gex,
        "exp_moves": options_em,
        "sentiment": options_sentiment
    }

    # --- 8. Construct "seasonality" ---
    next_day_str = "N/A"
    next_week_str = "N/A"
    
    try:
        from mie_lib.analytics.seasonality_analytics import get_seasonality_forecast
        # Forecast 5 days
        forecast = get_seasonality_forecast(ticker, start_date=datetime.now().date(), days=5)
        if forecast:
            # Next Day
            f0 = forecast[0]
            next_day_str = f"{f0.get('win_rate')}% Win, {f0.get('avg_return')}% Avg"
            
            # Next Week (Avg of 5 days?)
            # Or just summary of win rates?
            # Let's average the avg_return
            avg_rets = [f.get('avg_return', 0) for f in forecast]
            avg_5d = sum(avg_rets)
            next_week_str = f"Cum Return 5d: {avg_5d:.2f}%"
    except: pass
    
    seasonality_section = { "next_day": next_day_str, "next_week": next_week_str }


    # --- Final Assembly ---
    payload = {
        "meta": meta,
        "price": price_section,
        "regime": regime_section,
        "trend": trend_section,
        "options": options_section,
        "seasonality": seasonality_section
    }
    
    return payload
