import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

def generate_llm_payload(df: pd.DataFrame, ticker: str, expected_moves_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a context-rich JSON payload for LLM analysis based on the latest market data.
    
    Args:
        df: DataFrame containing price features, technicals, GEX, and HMM states.
        ticker: Ticker symbol (e.g. "SPY").
        expected_moves_data: Optional dictionary containing Expected Moves analysis.
        
    Returns:
        Dictionary ready for json.dumps().
    """
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
    # Safely get GEX values, defaulting to 0.0
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
        "gamma_exposure_next_5_days": next5_net_gex
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
