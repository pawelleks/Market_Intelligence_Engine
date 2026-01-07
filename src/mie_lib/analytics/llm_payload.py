import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

def _safe_val(val: Any, default: Any = 0.0, as_type: type = float) -> Any:
    """Helper to ensure NO fields are Null."""
    if pd.isna(val) or val is None or val == "None" or val == "" or str(val).lower() == "nan":
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

def _calc_relative_dist(level: float, close: float) -> tuple[str, str]:
    """Convert absolute levels into % distance from Close and a human label."""
    if not level or not close or close == 0:
        return "N/A", "Unknown"
    
    # Standard: (Close - Level) / Level
    # If Close > Level, dist is positive (Above)
    dist_pct = ((close - level) / level) * 100
    direction = "above" if dist_pct >= 0 else "below"
    
    return f"{dist_pct:+.2f}%", f"{abs(dist_pct):.2f}% {direction}"

def _get_dcs_status(score: float) -> str:
    """Logic Injection: Downtrend Confirmation Score status."""
    if score > 80:
        return f"{score} - Crisis (Critical Risk)"
    elif score > 60:
        return f"{score} - Strong Alert (Bearish)"
    elif score > 40:
        return f"{score} - Warning (Watch closely)"
    elif score > 0:
        return f"{score} - Healthy (Minor Pullback)"
    else:
        return "0 - No sign of downtrend"

def _get_pcr_conclusion(pcr: float) -> str:
    """Logic for PCR Sentiment."""
    if pcr > 1.4:
        return f"{pcr:.3f} (Defensive, Heavy Hedging)"
    elif pcr > 1.0:
        return f"{pcr:.3f} (Protective, Bearish Speculation)"
    elif pcr > 0.7:
        return f"{pcr:.3f} (Neutral/Balanced)"
    elif pcr > 0.4:
        return f"{pcr:.3f} (Bullish Speculation)"
    else:
        return f"{pcr:.3f} (Extremely Bullish)"

def generate_llm_payload(df: pd.DataFrame, ticker: str, expected_moves_data: Optional[Dict[str, Any]] = None, gex_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a comprehensive minified JSON payload for LLM analysis (Market State Vector).
    """
    from mie_lib.utils.paths import DATA_DIR, hmm_std_out_dir
    from mie_lib.analytics.downtrend_engine import compute_downtrend_score_latest, DEFAULT_WEIGHTS
    from mie_lib.data_ingest.data_aligner import fetch_and_align_dcs_assets
    
    # --- 1. Load Auxiliary Data (Lazy) ---
    # Load HMM Authentic Data (3-State, 10Y)
    hmm_authentic_state = None
    hmm_authentic_desc = None
    try:
        # Default Dashboard Config: 3-State, 10Y
        # FIX: Use hmm_states.parquet which has state IDs and NAMES
        hmm_path = hmm_std_out_dir(ticker, 10, 3) / "hmm_states.parquet"
        if hmm_path.exists():
            df_hmm = pd.read_parquet(hmm_path)
            if not df_hmm.empty:
                last_hmm = df_hmm.iloc[-1]
                hmm_authentic_state = int(last_hmm['hmm_state'])
                if 'hmm_state_name' in last_hmm:
                     hmm_authentic_desc = last_hmm['hmm_state_name']
    except Exception as e:
        print(f"LLM Payload HMM Load Error: {e}")
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
    tsmom_path = DATA_DIR / "tsmom" / "tsmom_current.parquet"
    if tsmom_path.exists():
        try:
            df_ts = pd.read_parquet(tsmom_path)
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
    # Or calculate if not present?    # Usually in df features: 'high_52w', 'sma_200'
    # Standard features usually include rolling max.
    
    high_52w = _safe_val(row.get('rolling_max_252'), 0.0) 
    low_52w = _safe_val(row.get('rolling_min_252'), 0.0)
    sma200 = _safe_val(tech_data.get('sma_200') or row.get('sma_200'), 0.0)
    
    dist_52w_pct, dist_52w_label = _calc_relative_dist(high_52w, close_price) if high_52w > 0 else ("N/A", "Unknown")
    dist_sma200_pct, dist_sma200_label = _calc_relative_dist(sma200, close_price) if sma200 > 0 else ("N/A", "Unknown")

    price_section = {
        "close": round(close_price, 2),
        "dist_52w_high_pct": dist_52w_pct,
        "dist_52w_high_label": dist_52w_label,
        "dist_sma200_pct": dist_sma200_pct,
        "dist_sma200_label": dist_sma200_label,
        "52w_high": round(high_52w, 2),
        "52w_low": round(low_52w, 2)
    }

    # --- 5. Construct "regime" ---
    # HMM
    # FIX: Use authentic loaded state if available, else fallback to row
    if hmm_authentic_state is not None:
        hmm_state = hmm_authentic_state
    else:
        hmm_state = int(_safe_val(row.get('hmm_state'), -1, int))

    # Naming Logic
    if hmm_authentic_desc:
        hmm_desc = hmm_authentic_desc
    else:
        # Strict Fallback: Use standard mapping aligned with dashboard
        # 0: Bear, 1: Neutral, 2: Bull (3-State Model 10Y)
        if hmm_state == 2:
            hmm_desc = "Bull"
        elif hmm_state == 1:
            hmm_desc = "Neutral"
        elif hmm_state == 0:
            hmm_desc = "Bear"
        else:
            hmm_desc = "Unknown"

    
    # Markov (Placeholder or existing logic)
    # Usually not in simple row, need separate Markov lookup or passed in. 
    # Current request didn't strictly ask to load separate Markov file, but said "Markov: verdict".
    # We will set defaults if not found.
    markov_verdict = "N/A" # TODO: Load from Markov snapshot if critical
    markov_next_bull = 0.0

    # Volatility
    atr_14 = round(_safe_val(vol_data.get('atr'), 0.0), 2)
    atr_rank = int(_safe_val(vol_data.get('atr_rank'), 0, int))
    vol_regime = _safe_val(vol_data.get('volatility_regime'), "Neutral", str)

    regime_section = {
        "hmm": { "state": str(hmm_state), "desc": hmm_desc },
        "markov": { "verdict": markov_verdict, "next_prob_bull": markov_next_bull },
        "vol": { "atr_14": atr_14, "rank_6m": atr_rank, "regime": vol_regime }
    }

    # --- 6. Construct "trend" ---
    # DCS
    # Logic: LOAD from precalculated latest.json (Single Source of Truth)
    # DO NOT calculate on the fly.
    dcs_score = 0
    dcs_status = "N/A"
    
    try:
        from mie_lib.utils.paths import DATA_DIR
        import json
        
        dcs_latest_path = DATA_DIR / "analytics" / "dcs" / f"{ticker}_latest.json"
        
        if dcs_latest_path.exists():
            with open(dcs_latest_path, "r") as f:
                dcs_data = json.load(f)
                dcs_score = int(dcs_data.get("latest_score_100", 0))
                # Status logic (can be shared or derived)
                if dcs_score >= 80: dcs_status = "CRISIS"
                elif dcs_score >= 60: dcs_status = "ALERT"
                elif dcs_score >= 40: dcs_status = "WARNING"
                else: dcs_status = "OK"
        else:
             dcs_status = "N/A (Missing Data)"
             
    except Exception as e:
        dcs_status = f"Error: {str(e)}"

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
    adx_val = round(_safe_val(tech_data.get('adx'), 0.0), 2)
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
    tsmom_sig = _safe_val(tsmom_data.get('signal_regime') or tsmom_data.get('signal_today'), "Neutral", str)
    if not tsmom_sig: tsmom_sig = "Neutral"
    tsmom_12m = f"{_safe_val(tsmom_data.get('ret_12m'), 0.0)*100:.1f}%"

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
                     cw_row = df_prof.loc[df_prof['total_call_gex'].idxmax()]
                     pw_row = df_prof.loc[df_prof['total_put_gex'].idxmin()]
                     cw = cw_row['strike']
                     pw = pw_row['strike']
                     cw_pct, cw_label = _calc_relative_dist(cw, close_price)
                     pw_pct, pw_label = _calc_relative_dist(pw, close_price)
                     call_wall_dist = f"${cw} ({cw_label})"
                     put_wall_dist = f"${pw} ({pw_label})"
            except: pass

    options_gex = { 
        "net_regime": f"{net_regime} (Dealer {'Long' if net_regime.startswith('Pos') else 'Short'} Gamma)", 
        "put_wall_dist": put_wall_dist, 
        "call_wall_dist": call_wall_dist 
    }

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
    
    options_em = { "0dte_range": f"${em_0dte:.2f}", "1w_range": em_1w }

    # Sentiment (PCR / Skew)
    pcr_val = _safe_val(skew_data.get('pcr_volume') or tech_data.get('pcr_volume') or tech_data.get('pcr'), 0.0)
    pcr_vol = _get_pcr_conclusion(pcr_val)
    
    skew_val = skew_data.get('skew_25d')
    if pd.isna(skew_val) or skew_val == 0:
        # Fallback to tech_data keys
        skew_val = tech_data.get('skew_25d') or tech_data.get('skew')

    skew_24d = "N/A"
    if pd.notna(skew_val) and skew_val != 0:
         skew_24d = f"{float(skew_val)*100:.2f}%" 

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
        # Forecast 10 days to ensure we find at least one valid trading day
        forecast = get_seasonality_forecast(ticker, start_date=datetime.now().date(), days=10)
        if forecast:
            # First found item is the "next" available historical day
            f0 = forecast[0]
            next_day_str = f"{f0.get('win_rate')}% Win, {f0.get('avg_return')}% Avg ({f0.get('month_day')})"
            
            # Next Week (Next 5 valid days)
            avg_rets = [f.get('avg_return', 0) for f in forecast[:5]]
            avg_5d = sum(avg_rets)
            next_week_str = f"Cum Return (5d): {avg_5d:+.2f}%"
    except Exception as e:
        import logging
        logging.getLogger("mie_lib.analytics.llm_payload").warning(f"Seasonality forecast failed: {e}")
    
    seasonality_section = { "next_day": next_day_str, "next_week": next_week_str }


    # --- 9. Performance ---
    perf_section = {
        "1d": f"{_safe_val(row.get('ret_1d'), 0)*100:+.2f}%",
        "1w": f"{_safe_val(row.get('ret_5d'), 0)*100:+.2f}%",
        "1m": f"{_safe_val(row.get('ret_21d'), 0)*100:+.2f}%",
        "3m": f"{_safe_val(row.get('ret_63d'), 0)*100:+.2f}%",
        "6m": f"{_safe_val(row.get('ret_126d'), 0)*100:+.2f}%",
        "1y": f"{_safe_val(row.get('ret_252d'), 0)*100:+.2f}%",
    }

    # --- Final Assembly ---
    payload = {
        "meta": meta,
        "price": price_section,
        "performance": perf_section,
        "regime": regime_section,
        "trend": trend_section,
        "options": options_section,
        "seasonality": seasonality_section
    }
    
    return payload
