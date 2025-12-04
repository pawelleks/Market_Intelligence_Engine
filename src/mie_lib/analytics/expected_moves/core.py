"""
Core calculation logic for Expected Moves (EM).
"""
import math

def calculate_straddle_em(atm_call_mid: float, atm_put_mid: float) -> float:
    """
    Calculates the Straddle-based Expected Move.
    Formula: ATM Call Mid + ATM Put Mid
    """
    return atm_call_mid + atm_put_mid

def calculate_iv_em(underlying_price: float, atm_iv: float, days_to_expiry: float) -> float:
    """
    Calculates the IV-based Expected Move (for verification).
    Formula: Underlying Price * ATM IV * sqrt(Days / 365)
    
    Args:
        underlying_price: Price of the underlying asset.
        atm_iv: Implied Volatility (e.g., 0.20 for 20%).
        days_to_expiry: Number of days to expiration (can be fractional).
    """
    if days_to_expiry < 0:
        return 0.0
    return underlying_price * atm_iv * math.sqrt(days_to_expiry / 365.0)

def calculate_confidence_score(vix1d_value: float, min_vix: float = 5.0, max_vix: float = 30.0) -> int:
    """
    Calculates the Confidence Score based on VIX1D value.
    Normalized inverse relationship:
    - VIX1D <= min_vix -> 100% confidence
    - VIX1D >= max_vix -> 0% confidence
    - Linear interpolation in between.
    """
    if vix1d_value <= min_vix:
        return 100
    if vix1d_value >= max_vix:
        return 0
    
    # Linear interpolation
    # Score = 100 * (Max - VIX) / (Max - Min)
    score = 100 * (max_vix - vix1d_value) / (max_vix - min_vix)
    return int(round(score))
