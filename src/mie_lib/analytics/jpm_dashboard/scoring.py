"""
JPM Economic Dashboard - Health Scoring Logic

Shared logic for calculating health scores (0-100) for economic indicators.
Used by both the API (for UI display) and the AI Analyst (for generating insights).
"""

from typing import Optional

def calculate_gdp_health(current_value, percentile, yoy_change):
    score = 100
    
    # Percentile component (50% weight)
    # Handle potentially missing percentile
    if percentile is None:
        percentile = 50
    score = percentile * 0.5
    
    # Growth rate component (50% weight)
    if yoy_change is not None:
        if yoy_change > 2.5:  # Strong growth
            score += 50
        elif yoy_change > 1.5:  # Moderate growth
            score += 35
        elif yoy_change > 0:  # Weak growth
            score += 20
        else:  # Contraction
            score += 0
    else:
        # Default if no YoY data
        score += 25
    
    return int(max(0, min(100, score)))

def calculate_unemployment_health(current_value, percentile, yoy_change, yoy_absolute_change=None):
    """
    Calculate health score for unemployment.
    
    CRITICAL: Must consider BOTH absolute level AND trend direction:
    - Low unemployment (< 5%) is good
    - BUT rising unemployment is a leading recession indicator
    - Trend matters MORE than level for forecasting
    """
    score = 0
    
    if percentile is None:
        percentile = 50
    
    # Component 1: Inverted percentile (40% weight)
    # Lower unemployment = higher score, so invert
    score = (100 - percentile) * 0.4
    
    # Component 2: Absolute level (40% weight)
    if current_value < 3.5:  # Extremely low
        score += 40
    elif current_value < 4.0:  # Very low
        score += 35
    elif current_value < 4.5:  # Low (4.4% falls here)
        score += 30
    elif current_value < 5.0:  # Moderate
        score += 20
    elif current_value < 6.0:  # Elevated
        score += 10
    else:  # High
        score += 0
    
    # Component 3: Trend penalty (20% weight)
    # Rising unemployment is a CRITICAL recession warning
    # We use ABSOLUTE change (percentage points) if available, otherwise relative
    
    if yoy_absolute_change is not None:
        # Using absolute point change (e.g. +0.2 points)
        if yoy_absolute_change > 1.0:
            score -= 30  # Spike (crisis)
        elif yoy_absolute_change > 0.5:
            score -= 25  # Rising significantly
        elif yoy_absolute_change > 0.3:
            score -= 15  # Rising moderately
        elif yoy_absolute_change > 0.1:
            score -= 5   # Rising slightly (0.2 falls here -> -5)
        elif yoy_absolute_change < -0.5:
            score += 10  # Falling
        elif yoy_absolute_change < -0.1:
            score += 5   # Falling slightly
        # else stable
    elif yoy_change is not None:
        # Fallback to relative change
        if yoy_change > 10:
            score -= 30
        elif yoy_change > 5:
            score -= 25
        elif yoy_change > 2:
            score -= 15
        elif yoy_change > 0:
            score -= 5
        elif yoy_change < -5:
            score += 10
        elif yoy_change < 0:
            score += 5
    
    return int(max(0, min(100, score)))

def calculate_inflation_health(yoy_change):
    score = 100
    
    if yoy_change is None:
        return 50
    
    # Distance from 2% target
    distance = abs(yoy_change - 2.0)
    
    if distance < 0.5:  # Very close to target
        score = 100
    elif distance < 1.0:  # Close to target
        score = 85
    elif distance < 2.0:  # Moderate deviation
        score = 65
    elif distance < 3.0:  # Large deviation
        score = 40
    else:  # Very large deviation
        score = 20
    
    return int(score)

def calculate_stock_health(percentile, yoy_change):
    if percentile is None:
        percentile = 50
    score = percentile * 0.6  # Weight historical position
    
    if yoy_change is not None:
        if yoy_change > 15:  # Strong gains
            score += 40
        elif yoy_change > 5:  # Moderate gains
            score += 30
        elif yoy_change > 0:  # Slight gains
            score += 20
        elif yoy_change > -10:  # Moderate losses
            score += 10
        else:  # Large losses
            score += 0
    
    return int(max(0, min(100, score)))

def calculate_rates_health(percentile, current_value):
    # Neutral is around 50th percentile
    # Extremely high or low rates are concerning
    
    if percentile is None:
        percentile = 50
    
    if percentile < 10 or percentile > 90:
        score = 40  # Extreme levels
    elif percentile < 25 or percentile > 75:
        score = 65  # Elevated
    else:
        score = 85  # Normal range
    
    return int(score)


def calculate_business_confidence_health(current_value, percentile, yoy_change):
    """
    BSCICP02USM460S: OECD Business Tendency Survey (Manufacturing)
    Centered around 100 (100 = neutral)
    >100 = Positive business sentiment
    <100 = Negative business sentiment
    Typical range: 98-102
    """
    score = 0
    
    if percentile is None:
        percentile = 50
        
    # Percentile component (50% weight)
    score += percentile * 0.5
    
    # Absolute level component (50% weight)
    if current_value >= 101.5:
        score += 50  # Very optimistic
    elif current_value >= 100.5:
        score += 45  # Optimistic
    elif current_value >= 100.0:
        score += 40  # Neutral-positive
    elif current_value >= 99.5:
        score += 30  # Neutral-negative
    elif current_value >= 99.0:
        score += 15  # Cautious
    elif current_value >= 98.0:
        score += 5   # Pessimistic
    else:
        score += 0   # Very pessimistic
    
    return int(max(0, min(100, score)))

def calculate_housing_health(current_value, percentile, yoy_change):
    """
    Housing Starts historical context:
    1.8M+ = Boom
    1.5-1.8M = Strong
    1.2-1.5M = Moderate (current: 1.25M)
    1.0-1.2M = Weak
    800K-1M = Recession
    <800K = Crisis
    """
    score = 0
    
    if percentile is None:
        percentile = 50
        
    # Percentile component (40% weight)
    score += percentile * 0.4
    
    # Absolute level component (40% weight)
    if current_value >= 1.8:
        score += 40  # Boom
    elif current_value >= 1.5:
        score += 35  # Strong
    elif current_value >= 1.2:
        score += 25  # Moderate (1.25M should land here)
    elif current_value >= 1.0:
        score += 15  # Weak
    elif current_value >= 0.8:
        score += 5   # Recession
    else:
        score += 0   # Crisis
    
    # Trend component (20% weight)
    if yoy_change is not None:
        if yoy_change > 5:
            score += 20  # Improving
        elif yoy_change > 0:
            score += 10  # Slight improvement
        elif yoy_change > -10:
            score += 5   # Slight decline
        else:
            score += 0   # Sharp decline
    
    return int(max(0, min(100, score)))

def calculate_health_score(indicator_id: str, current_value: float, percentile: float, yoy_change: Optional[float], yoy_absolute_change: Optional[float] = None) -> int:
    """Calculate health score (0-100) for each indicator"""
    
    if current_value is None:
        return 0
    
    # Map to appropriate calculation function
    if indicator_id == 'gdp':
        return calculate_gdp_health(current_value, percentile, yoy_change)
    elif indicator_id == 'labor-market':
        # Now passing yoy_absolute_change correctly
        return calculate_unemployment_health(current_value, percentile, yoy_change, yoy_absolute_change)
    elif indicator_id == 'inflation':
        return calculate_inflation_health(yoy_change)
    elif indicator_id == 'stock-market':
        return calculate_stock_health(percentile, yoy_change)
    elif indicator_id == 'interest-rates':
        return calculate_rates_health(percentile, current_value)
    elif indicator_id == 'consumer-spending':
        # Higher is generally better
        if percentile is None: percentile = 50
        return int(percentile * 0.7 + (30 if yoy_change and yoy_change > 0 else 0))
    elif indicator_id == 'housing':
        return calculate_housing_health(current_value, percentile, yoy_change)
    elif indicator_id == 'business-confidence':
        return calculate_business_confidence_health(current_value, percentile, yoy_change)
    elif indicator_id == 'trade-balance':
        # Closer to zero is better (large deficits are bad)
        if current_value is not None:
            if percentile is None: percentile = 50
            # Invert percentile if deficit
            return int((100 - percentile) if current_value < 0 else percentile)
        return 50
    elif indicator_id == 'policy':
        # Use rates calculation
        return calculate_rates_health(percentile, current_value)
    else:
        # Default: use percentile
        return int(percentile if percentile is not None else 50)
