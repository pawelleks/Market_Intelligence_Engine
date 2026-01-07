from typing import List, Dict, Tuple, Any, Optional
import pandas as pd
import numpy as np
import pandas as pd
import numpy as np
# import talib  # Removed to avoid dependency issues
from mie_lib.utils.logging import get_logger
from mie_lib.features.build_features import build_features_for_ticker
from datetime import datetime

LOG = get_logger("ema_respect")

def calculate_ma(df: pd.DataFrame, period: int, ma_type: str = "EMA") -> pd.Series:
    """Calculate Moving Average based on type"""
    try:
        # Check if we have enough data
        if len(df) < period:
            return pd.Series(index=df.index, dtype=float)
        
        prices = df['close'].astype(float)
        
        if ma_type == "EMA":
             # Pandas ewm adjust=False matches standard EMA definition
             return prices.ewm(span=period, adjust=False).mean()
        
        elif ma_type == "SMA":
             return prices.rolling(window=period).mean()
             
        elif ma_type == "WMA":
             # Weighted MA: weights [1, 2, ..., n]
             weights = np.arange(1, period + 1)
             return prices.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
             
        elif ma_type == "VWMA":
             if 'volume' not in df.columns:
                 return pd.Series(index=df.index, dtype=float)
             
             v = df['volume'].astype(float)
             # VWMA = SMA(Price * Volume) / SMA(Volume)
             pv = prices * v
             return pv.rolling(window=period).mean() / v.rolling(window=period).mean()
             
        else:
            LOG.error(f"Unknown MA type: {ma_type}")
            return pd.Series(index=df.index, dtype=float)

    except Exception as e:
        LOG.error(f"Error calculating {ma_type} {period}: {e}")
        return pd.Series(index=df.index, dtype=float)

def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Legacy wrapper"""
    return calculate_ma(df, period, "EMA")

def detect_bounces(
    df: pd.DataFrame, 
    ema_series: pd.Series, 
    ema_period: int,
    tolerance_pct: float = 0.5, 
    proximity_pct: float = 1.5,
    confirm_candles: int = 1
) -> Dict[str, Any]:
    """
    Detect bullish and bearish bounces off an EMA.
    
    Logic:
    1. Approach: Price must get within `proximity_pct` of EMA (or cross it).
    2. Respect: Close price must be within `tolerance_pct` beyond the EMA (not a full break).
       - Bullish: EMA > Low, Close >= EMA * (1 - tolerance)
       - Bearish: EMA < High, Close <= EMA * (1 + tolerance)
    3. Confirmation: Next `confirm_candles` must show movement away.
       - Bullish: Close[t+1] > Close[t]
       - Bearish: Close[t+1] < Close[t]
    """
    
    if len(df) != len(ema_series):
        return {"bullish": [], "bearish": [], "total": 0, "score": 0}

    # Prepare data for faster iteration
    dates = df['date'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    emas = ema_series.values
    
    bullish_bounces = []
    bearish_bounces = []
    
    # Start loop after EMA is stable (give it some buffer, e.g. period * 2)
    start_idx = ema_period * 2 if len(df) > ema_period * 2 else ema_period
    
    # We need confirmation candles ahead, so stop before the end
    end_idx = len(df) - confirm_candles
    
    for i in range(start_idx, end_idx):
        close_p = closes[i]
        low_p = lows[i]
        high_p = highs[i]
        ema_v = emas[i]
        date_v = dates[i]
        
        if np.isnan(ema_v):
            continue

        # --- Bullish Bounce Detection ---
        # Condition 1: Price dips near or below EMA (Proximity)
        # We check if Low is near EMA from above or has crossed it
        dist_low = (low_p - ema_v) / ema_v * 100
        
        # Must be close enough (within proximity) OR have penetrated
        if dist_low <= proximity_pct: 
            # Condition 2: Respect (Close is maintained relative to tolerance)
            # Allowed penetration: Close can be slightly below EMA
            # Close >= EMA * (1 - tolerance/100)
            allowed_floor = ema_v * (1 - tolerance_pct / 100)
            
            # Additional check: It should actually be a "dip" bounce, so ideally Open or Prev Close was higher?
            # Or simplified: Low < EMA (touched) or Low within 1% above
            
            # Let's refine "Bounce":
            # 1. Low <= EMA * (1 + proximity/100)  -> Touched or came close
            # 2. Close >= allowed_floor            -> Didn't break significantly
            # 3. Close > Low                       -> Rebounded intraday (optional but good signal)
            
            check_touch = low_p <= ema_v * (1 + proximity_pct/100)
            check_respect = close_p >= allowed_floor
            
            # Filter: Ensure it's not just floating way above
            # If Low is > EMA, it's a "near miss" bounce. If Low < EMA, it's a "pierce" bounce.
            
            if check_touch and check_respect:
                # Condition 3: Confirmation
                # Next n candles should close higher than *this* close (or simply move up)
                confirmed = True
                curr_ref = close_p
                for k in range(1, confirm_candles + 1):
                    if closes[i+k] <= curr_ref:
                        confirmed = False
                        break
                    curr_ref = closes[i+k] # Chain higher highs? Or just higher than bounce?
                    # Let's use simpler: Close[i+k] > Close[i] is minimal confirmation
                
                if confirmed:
                    bullish_bounces.append({
                        "date": str(date_v),
                        "price": float(close_p),
                        "ema": float(ema_v),
                        "type": "bullish"
                    })

        # --- Bearish Bounce Detection ---
        # Condition 1: Price rallies near or above EMA
        # Interaction check for opportunity count
        is_bearish_opportunity = False
        if high_p >= ema_v * (1 - proximity_pct/100):
            is_bearish_opportunity = True
        
        # High must be >= EMA * (1 - proximity) -> Touched or close
        check_touch_bear = high_p >= ema_v * (1 - proximity_pct/100)
        
        # Condition 2: Respect
        # Close <= EMA * (1 + tolerance/100)
        allowed_ceiling = ema_v * (1 + tolerance_pct / 100)
        check_respect_bear = close_p <= allowed_ceiling
        
        if check_touch_bear and check_respect_bear:
             # Condition 3: Confirmation
            confirmed = True
            curr_ref = close_p
            for k in range(1, confirm_candles + 1):
                if closes[i+k] >= curr_ref: # Failed to go lower
                    confirmed = False
                    break
            
            if confirmed:
                bearish_bounces.append({
                    "date": str(date_v),
                    "price": float(close_p),
                    "ema": float(ema_v),
                    "type": "bearish"
                })

    # Calculate opportunities (This is an approximation using touch logic)
    # Ideally we'd track every unique "approach" event, but for now let's use a simpler heuristic or just count bars within proximity?
    # User said: "Normalize... shorter EMAs naturally touch price more often"
    # So "Rate = Bounces / Opportunities" seems best.
    # We need to count opportunities correctly.
    # An opportunity is a bar where Low/High entered the proximity zone?
    # Let's count bars where price interacted with EMA.
    
    # Re-scan for simple interaction count (or do it inside loop)
    # Interaction = Low <= EMA*(1+prox) OR High >= EMA*(1-prox)
    # But strictly speaking, Bullish Opp is when Price is ABOVE and dips.
    # Bearish Opp is when Price is BELOW and rallies.
    # This stateful tracking is better.
    
    # Simple proxy: Total bars where range overlaps EMA proximity zone?
    touch_count = 0
    for i in range(start_idx, end_idx):
        e_v = emas[i]
        if np.isnan(e_v): continue
        l_p = lows[i]
        h_p = highs[i]
        lower_zone = e_v * (1 - proximity_pct/100)
        upper_zone = e_v * (1 + proximity_pct/100)
        
        # If bar touches the zone
        if l_p <= upper_zone and h_p >= lower_zone:
            touch_count += 1
            
    total_bounces = len(bullish_bounces) + len(bearish_bounces)
    bounce_rate = (total_bounces / touch_count * 100) if touch_count > 0 else 0.0

    return {
        "bullish": bullish_bounces,
        "bearish": bearish_bounces,
        "total": total_bounces,
        "opportunities": touch_count,
        "bounce_rate": round(bounce_rate, 2),
        "ema_period": ema_period
    }

def analyze_ticker(
    ticker: str,
    tolerance: float = 0.5,
    proximity: float = 1.0,
    min_period: int = 10,
    max_period: int = 300,
    ranges: Optional[Dict[str, Dict[str, int]]] = None,
    ma_type: str = "EMA"
) -> Dict[str, Any]:
    """
    Run EMA bounce analysis for a range of periods.
    """
    
    # 1. Load Data
    try:
        from mie_lib.utils.paths import DATA_DIR
        parquet_path = DATA_DIR / "raw" / f"{ticker}.parquet"
        
        if not parquet_path.exists():
             return {"error": f"Data not found for {ticker} at {parquet_path}"}
             
        df = pd.read_parquet(parquet_path)
        
        # Ensure we have required columns
        required = ['date', 'open', 'high', 'low', 'close']
        missing = [c for c in required if c not in df.columns]
        
        if missing:
            # Try lowercase
            df.columns = [c.lower() for c in df.columns]
            missing = [c for c in required if c not in df.columns]
        
        if missing:
             return {"error": f"Missing columns {missing} in data for {ticker}"}

        # Ensure minimum length
        if len(df) < 700:
             return {"error": f"Insufficient data for {ticker} (found {len(df)}, need 700)"}

        # Sort by date
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
    except Exception as e:
        return {"error": f"Failed to load data: {str(e)}"}

    results = []
    
    # Ranges
    # Ranges
    if ranges is None:
        ranges = {
            'short': {'min': 10, 'max': 60},
            'medium': {'min': 61, 'max': 140},
            'long': {'min': 141, 'max': 300}
        }
    
    periods = range(min_period, max_period + 1)
    
    periods = range(min_period, max_period + 1)
    
    for p in periods:
        ema_series = calculate_ma(df, p, ma_type)
        stats = detect_bounces(df, ema_series, p, tolerance, proximity)
        
        # Determine range
        p_range = "unknown"
        if 10 <= p <= 60: p_range = "short"
        elif 61 <= p <= 140: p_range = "medium"
        elif 141 <= p <= 300: p_range = "long"
        
        # Scoring: Score = Total Bounces.
        # Use Bounce Rate as tie-breaker or secondary metric? 
        # For now, primary score is Count.
        score = stats["total"]
        
        results.append({
            "period": p,
            "range": p_range,
            "score": score,
            "bounces": stats["total"],
            "opportunities": stats["opportunities"],
            "bounce_rate": stats["bounce_rate"],
            "bullish": len(stats["bullish"]),
            "bearish": len(stats["bearish"]),
            "details": stats 
        })
    
    # Select Winner per Range
    segmented_winners = {}
    
    for r_key, r_def in ranges.items():
        # Filter for this range
        candidates = [x for x in results if x['range'] == r_key]
        if not candidates:
            # Fallback if no periods scanned in this range?
            continue
            
        # Sort by Score DESC, then Rate DESC
        candidates.sort(key=lambda x: (x['score'], x['bounce_rate']), reverse=True)
        winner = candidates[0]
        
        segmented_winners[r_key] = winner

    # Prepare Chart Data for the 3 Winners
    chart_data = []
    winner_periods = [w['period'] for w in segmented_winners.values()]
    ema_map = {}
    for p in winner_periods:
        ema_map[p] = calculate_ma(df, p, ma_type)
        
    bounce_map = {}
    for w in segmented_winners.values():
        p = w['period']
        bounce_map[p] = {}
        for b in w['details']['bullish']:
            bounce_map[p][b['date']] = 'bullish'
        for b in w['details']['bearish']:
            bounce_map[p][b['date']] = 'bearish'
            
    # Chart Loop
    dates = df['date'].dt.strftime('%Y-%m-%d').values
    closes = df['close'].values
    opens = df['open'].values if 'open' in df.columns else closes
    highs = df['high'].values if 'high' in df.columns else closes
    lows = df['low'].values if 'low' in df.columns else closes
    ema_arrays = {p: ema_map[p].values for p in winner_periods}
    
    for i in range(len(df)):
        d_str = dates[i]
        record = {
            "date": d_str,
            "open": float(opens[i]) if not np.isnan(opens[i]) else None,
            "high": float(highs[i]) if not np.isnan(highs[i]) else None,
            "low": float(lows[i]) if not np.isnan(lows[i]) else None,
            "close": float(closes[i]) if not np.isnan(closes[i]) else None,
        }
        for p in winner_periods:
            val = ema_arrays[p][i]
            record[f"ema_{p}"] = float(val) if not np.isnan(val) else None
             # Check bounce
            if d_str in bounce_map[p]:
                record[f"bounce_{p}"] = bounce_map[p][d_str]
        chart_data.append(record)
    
    # Full Table (Top 50 overall? or Top 10 per range?)
    # Let's return Top 50 Overall sorted by Score still, but frontend can filter.
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    full_table = []
    for item in sorted_results:
        clean_item = {k:v for k,v in item.items() if k != 'details'}
        full_table.append(clean_item)
        
    return {
        "ticker": ticker,
        "scanned_periods": f"{min_period}-{max_period}",
        "winners": segmented_winners, 
        "rankings": full_table,
        "data_points": len(df),
        "chart_data": chart_data,
        "ma_type": ma_type
    }

if __name__ == "__main__":
    import sys
    # Load config if needed, or just run for SPY
    ticker = "SPY"
    if len(sys.argv) > 1:
        ticker = sys.argv[1]
    
    print(f"Analyzing {ticker}...")
    res = analyze_ticker(ticker)
    
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        print(f"Top {res.get('ma_type', 'EMA')}s per Range for {ticker}:")
        winners = res.get('winners', {})
        for r_name in ['short', 'medium', 'long']:
            if r_name in winners:
                item = winners[r_name]
                print(f"Range {r_name.upper()}: {res.get('ma_type', 'EMA')} {item['period']} - Score {item['score']}, Rate {item['bounce_rate']}%")
