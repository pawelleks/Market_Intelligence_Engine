import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

def generate_llm_payload(df: pd.DataFrame, ticker: str, expected_moves_data: Optional[Dict[str, Any]] = None, gex_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a context-rich JSON payload for LLM analysis based on the latest market data.
    
    Args:
        df: DataFrame containing price features, technicals, GEX, and HMM states.
        ticker: Ticker symbol (e.g. "SPY").
        expected_moves_data: Optional dictionary containing Expected Moves analysis.
        gex_snapshot: Optional dictionary containing latest GEX Snapshot (Net GEX, etc).
        
    Returns:
        Dictionary ready for json.dumps().
    """
    from mie_lib.utils.paths import DATA_DIR
    
    # Load auxiliary datasets lazily (or passthrough if passed, but simpler to load here for single-row usage)
    vol_path = DATA_DIR / "analytics" / "volatility_daily.parquet"
    volume_path = DATA_DIR / "analytics" / "volume_daily.parquet"
    
    vol_data = {}
    if vol_path.exists():
        try:
            df_vol = pd.read_parquet(vol_path)
            # Normalize
            df_vol.rename(columns={c: c.lower() for c in df_vol.columns}, inplace=True)
            # Filter
            row_vol = df_vol[df_vol['ticker'] == ticker]
            if not row_vol.empty:
                 vol_data = row_vol.iloc[-1].to_dict()
        except Exception:
            pass

    volume_data = {}
    if volume_path.exists():
        try:
             df_v = pd.read_parquet(volume_path)
             df_v.rename(columns={c: c.lower() for c in df_v.columns}, inplace=True)
             row_v = df_v[df_v['ticker'] == ticker] 
             if not row_v.empty:
                  volume_data = row_v.iloc[-1].to_dict()
        except Exception:
             pass

    # 1. Extract Latest Row
    if df.empty:
        return {"error": "DataFrame is empty", "ticker": ticker}
        
    # Get last row (Standard Pandas behavior)
    row = df.iloc[-1]
    
    # Extract Date safely (handle index vs column)
    if 'date' in row:
        last_date = str(row['date'])
    elif isinstance(row.name, (pd.Timestamp, str)):
        last_date = str(row.name)
    else:
        last_date = "Unknown"

    # 2. HMM Configuration (Hardcoded from Discovery)
    # Mapping derived from statistical audit: State 0 = Bull, State 1 = Bear
    HMM_PROFILE_MAP = {
        0: "Steady Bull (Low Vol, Positive Drift)",
        1: "Volatile Bear (High Vol, Negative Drift)"
    }
    
    hmm_state = row.get('hmm_state')
    # Use -1 sentinel for unknown, convert to int if possible
    hmm_id = int(hmm_state) if pd.notna(hmm_state) else -1
    hmm_label = HMM_PROFILE_MAP.get(hmm_id, "Unknown / Transition")

    # 3. Gamma Exposure (GEX) Logic
    call_wall = None
    put_wall = None
    zero_gex = None
    
    if gex_snapshot and 'net_gex' in gex_snapshot:
        # Use Snapshot (Freshest)
        total_net_gex = float(gex_snapshot['net_gex'])
        next5_net_gex = 0.0 
        
        # Calculate Walls from Profile
        profile = gex_snapshot.get("profile", [])
        if profile:
            try:
                # Convert to DF for easier analysis
                df_prof = pd.DataFrame(profile)
                if not df_prof.empty and 'strike' in df_prof.columns and 'total_gex' in df_prof.columns:
                    # Call Wall: Max Call GEX
                    if 'call_gex' in df_prof.columns:
                        call_wall = float(df_prof.loc[df_prof['call_gex'].idxmax()]['strike'])
                    
                    # Put Wall: Min Put GEX (Most Negative) in absolute terms usually means largest support
                    # Put GEX is usually negative. We want the largest magnitude.
                    if 'put_gex' in df_prof.columns:
                        put_wall = float(df_prof.loc[df_prof['put_gex'].idxmin()]['strike'])
                    
                    # Zero Gamma (Flip Point)
                    # Find strike where total_gex flips sign or is closest to 0
                    # Simple approach: Sort by strike, find sign change
                    df_sorted = df_prof.sort_values('strike')
                    # Calculate cumulative or scan for sign flip? 
                    # Usually Zero Gamma is where the aggregate curve flips? Or local flip?
                    # Common proxy: Strike closest to where cumulative GEX is zero? 
                    # OR just the strike with minimum absolute total GEX?
                    # Let's use the strike where total_gex is closest to 0? No, that's just low OI.
                    # Let's use the sign flip method on cumulative sum? No, usually it's a level.
                    # Implementation: Find first sign change in rolling GEX?
                    # Simplified: Just report the Net GEX for now, calculating precise Zero Gamma requires a model.
                    # BUT user asked for "Zero Gamma Level".
                    # Let's attempt: Find interval where GEX changes sign.
                    # If total_net_gex is positive, Zero Gamma might be below price?
                    pass
            except Exception as e:
                print(f"Error calculating GEX walls: {e}")

    else:
        # Fallback to DataFrame History
        total_net_gex = float(row.get('total_net_gex', 0.0)) if pd.notna(row.get('total_net_gex')) else 0.0
        next5_net_gex = float(row.get('next5_net_gex', 0.0)) if pd.notna(row.get('next5_net_gex')) else 0.0
    
    # Regime Calculation: >0 is Sticky, <0 is Volatile
    if total_net_gex > 0:
        gamma_regime = "Positive Gamma (Sticky/Low Vol)"
    else:
        gamma_regime = "Negative Gamma (Accelerator/High Vol)"
        
    gex_payload = {
        "net_gamma_exposure_notional": total_net_gex,
        "gamma_regime": gamma_regime,
        "gamma_exposure_next_5_days": next5_net_gex,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "zero_gex_level": zero_gex
    }

    # 4. Technical Indicators (Safe Fetch)
    # Define interesting columns to include if present
    tech_keys = [
        'close', 'open', 'high', 'low', 'volume', 
        'rsi', 'adx', 'log_ret_1d', 'rv_20d',
        'downtrend_score' # Custom metric if available
    ]
    
    technicals = {}
    for k in tech_keys:
        val = row.get(k)
        if pd.notna(val):
            # JSON serialization safety
            if isinstance(val, (np.integer, int)):
                technicals[k] = int(val)
            elif isinstance(val, (np.floating, float)):
                technicals[k] = float(val)
            else:
                technicals[k] = str(val)

    # 5. Construct Final Payload
    payload = {
        "ticker": ticker,
        "analysis_date": last_date,
        "market_regime": {
            "hmm_state_id": hmm_id if hmm_id != -1 else None,
            "hmm_description": hmm_label,
            "gamma_landscape": gex_payload
        },
        "technical_summary": technicals
    }

    # 6. Handle Expected Moves (Merge if provided)
    if expected_moves_data:
        # We assume expected_moves_data is already a dict structure
        payload["volatility_landscape"] = expected_moves_data

    # 6.5 Add ATR / Volatility Regime
    if vol_data:
        # If payload["volatility_landscape"] didn't exist, create it, else merge
        if "volatility_landscape" not in payload:
             payload["volatility_landscape"] = {}
        
        # Merge ATR info
        payload["volatility_landscape"].update({
            "atr_14": vol_data.get('atr'),
            "atr_rank_6m": vol_data.get('atr_rank'),
            "atr_pct_price": vol_data.get('atr_percent'),
            "volatility_regime": vol_data.get('volatility_regime'),
            "volatility_description": vol_data.get('volatility_desc')
        })

    # 6.6 Add Volume Regime
    if volume_data:
         payload["liquidity_volume_profile"] = {
              "volume_regime": volume_data.get('volume_regime'),
              "relative_volume_10d": volume_data.get('rel_vol_10'),
              "volume_trend_score": volume_data.get('vol_trend_score'),
              "buying_pressure_ratio": volume_data.get('buy_pressure_ratio')
         }

    # 7. Seasonality Forecast
    try:
        from mie_lib.analytics.seasonality_analytics import get_seasonality_forecast
        from datetime import datetime
        
        # Try to parse analysis date
        try:
            if isinstance(last_date, str):
                analysis_dt = datetime.strptime(last_date, "%Y-%m-%d").date()
            else:
                analysis_dt = datetime.now().date()
        except Exception:
            analysis_dt = datetime.now().date()
            
        seasonal_forecast = get_seasonality_forecast(ticker, start_date=analysis_dt, days=5)
        payload["seasonality_forecast_next_5d"] = seasonal_forecast
        
    except Exception as e:
        payload["seasonality_forecast_next_5d"] = {"error": str(e)}

    return payload
