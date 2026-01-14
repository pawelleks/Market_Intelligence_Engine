"""
Economic payload builder for AI insights
Follows pattern from mie_lib/analytics/llm_payload.py
"""

import pandas as pd
import json
from datetime import datetime
from typing import Dict, Optional, List, Tuple

def _safe_val(value, default="N/A", format_type=None):
    """
    Ensure no null values in payload
    Pattern from existing llm_payload.py
    """
    if pd.isna(value) or value is None:
        return default
    
    if format_type == "pct":
        return f"{value:+.2f}%"
    elif format_type == "dollars":
        return f"${value:,.0f}"
    elif format_type == "index":
        return f"{value:.2f}"
    
    return value


def _calculate_distance(current, reference, name):
    """
    Calculate distance with human-friendly label
    Pattern: Same as market data distance calculations
    """
    if pd.isna(current) or pd.isna(reference) or reference is None or current is None:
        return {
            "distance": None,
            "distance_pct": None,
            "label": "N/A"
        }
    
    distance = current - reference
    distance_pct = ((current - reference) / reference) * 100
    
    direction = "above" if distance > 0 else "below"
    label = f"{abs(distance_pct):.2f}% {direction} {name}"
    
    return {
        "distance": round(distance, 2),
        "distance_pct": round(distance_pct, 2),
        "label": label
    }


def _interpret_health_score(score):
    """
    Convert health score to status label
    Pattern: Similar to DCS score → status in market data
    """
    if pd.isna(score) or score is None:
        return "UNKNOWN"
    
    if score >= 80:
        return "HEALTHY"
    elif score >= 60:
        return "MODERATE"
    elif score >= 40:
        return "CAUTIOUS"
    elif score >= 20:
        return "CONCERNING"
    else:
        return "CRITICAL"


def _interpret_percentile(percentile):
    """
    Convert percentile rank to interpretation
    """
    if pd.isna(percentile) or percentile is None:
        return "Unknown"
    
    if percentile >= 90:
        return "Extremely High (Top 10%)"
    elif percentile >= 75:
        return "High (Top 25%)"
    elif percentile >= 50:
        return "Above Average"
    elif percentile >= 25:
        return "Below Average"
    elif percentile >= 10:
        return "Low (Bottom 25%)"
    else:
        return "Extremely Low (Bottom 10%)"


def _determine_momentum_direction(yoy, mom):
    """Interpret momentum from changes"""
    if yoy is None or pd.isna(yoy):
        return "Insufficient data"
    
    if yoy > 2:
        return "Accelerating upward"
    elif yoy > 0:
        return "Rising gradually"
    elif yoy > -2:
        return "Declining gradually"
    else:
        return "Accelerating downward"


def _get_last_recession_date(usrec_series):
    """Get most recent recession start date"""
    if usrec_series is None or len(usrec_series) == 0:
        return None
    
    recession_periods = usrec_series[usrec_series == 1]
    if len(recession_periods) > 0:
        return str(recession_periods.index[-1])
    return None


def _build_component_data(indicator_id: str, df: pd.DataFrame) -> Dict:
    """
    Build component breakdown for indicators that have sub-components
    Example: Inflation → Food, Energy, Core
    """
    components = {}
    
    component_series = INDICATOR_COMPONENTS.get(indicator_id, [])
    
    for series_id, series_name in component_series:
        if series_id in df.columns:
            series_data = df[series_id].dropna()
            if len(series_data) > 0:
                current = series_data.iloc[-1]
                year_ago = series_data.iloc[-13] if len(series_data) > 12 else None
                
                yoy = None
                if year_ago and not pd.isna(year_ago):
                    yoy = ((current - year_ago) / year_ago) * 100
                
                components[series_name] = {
                    "current": _safe_val(current),
                    "yoy_change": _safe_val(yoy, format_type="pct") if yoy is not None else "N/A"
                }
    
    return components


def build_economic_payload(
    indicator_id: str,
    df: pd.DataFrame,
    primary_series: str,
    metadata: Dict
) -> Dict:
    """
    Build Economic State Vector for AI analysis
    
    Args:
        indicator_id: 'gdp', 'labor-market', etc.
        df: DataFrame with indicator time series data
        primary_series: Main series ID (e.g., 'GDPC1', 'UNRATE')
        metadata: Additional context (health_score, percentile, etc.)
    
    Returns:
        JSON-serializable dict ready for OpenAI
    """
    
    # Get current data
    if primary_series not in df.columns:
        raise ValueError(f"Primary series {primary_series} not found in dataframe")
    
    series_data = df[primary_series].dropna()
    if len(series_data) == 0:
        raise ValueError(f"No data found for {primary_series}")
    
    current_value = float(series_data.iloc[-1])
    current_date = str(series_data.index[-1])[:10]
    
    # Historical reference points
    val_1m = float(series_data.iloc[-2]) if len(series_data) > 1 else None
    val_3m = float(series_data.iloc[-4]) if len(series_data) > 3 else None
    val_6m = float(series_data.iloc[-7]) if len(series_data) > 6 else None
    val_1y = float(series_data.iloc[-13]) if len(series_data) > 12 else None
    
    avg_5y = float(series_data.tail(60).mean()) if len(series_data) > 60 else None
    avg_10y = float(series_data.tail(120).mean()) if len(series_data) > 120 else None
    
    # Calculate changes
    yoy_change = None
    if val_1y and not pd.isna(val_1y):
        yoy_change = ((current_value - val_1y) / val_1y) * 100
    
    mom_change = None
    if val_1m and not pd.isna(val_1m):
        mom_change = ((current_value - val_1m) / val_1m) * 100
    
    # For GDP: calculate quarterly growth rate for clarity
    growth_rate = None
    growth_rate_unit = None
    if indicator_id == 'gdp' and val_1m and not pd.isna(val_1m):
        # QoQ annualized growth rate
        growth_rate = ((current_value - val_1m) / val_1m) * 400
        growth_rate_unit = "% QoQ Annualized"
    
    # Build payload structure
    payload = {
        "meta": {
            "indicator_id": indicator_id,
            "indicator_name": INDICATOR_NAMES.get(indicator_id, indicator_id),
            "date": current_date,
            "generated_at": datetime.now().isoformat()
        },
        
        "current_state": {
            "value": round(current_value, 2),
            "unit": INDICATOR_UNITS.get(indicator_id, ""),
            "growth_rate": round(growth_rate, 2) if growth_rate is not None else None,
            "growth_rate_unit": growth_rate_unit,
            "health_score": int(metadata.get('health_score', 0)),
            "health_status": _interpret_health_score(metadata.get('health_score', 0)),
            "percentile": round(float(metadata.get('percentile', 0)), 2),
            "percentile_interpretation": _interpret_percentile(metadata.get('percentile', 0)),
            "trend_direction": metadata.get('trend_direction', 'flat')
        },
        
        "historical_comparison": {
            "vs_1m_ago": _calculate_distance(current_value, val_1m, "1 month ago"),
            "vs_3m_ago": _calculate_distance(current_value, val_3m, "3 months ago"),
            "vs_6m_ago": _calculate_distance(current_value, val_6m, "6 months ago"),
            "vs_1y_ago": _calculate_distance(current_value, val_1y, "1 year ago"),
            "vs_5y_avg": _calculate_distance(current_value, avg_5y, "5-year average"),
            "vs_10y_avg": _calculate_distance(current_value, avg_10y, "10-year average")
        },
        
        "momentum": {
            "yoy_change_pct": _safe_val(yoy_change, format_type="pct") if yoy_change is not None else "N/A",
            "mom_change_pct": _safe_val(mom_change, format_type="pct") if mom_change is not None else "N/A",
            "direction": _determine_momentum_direction(yoy_change, mom_change)
        },
        
        "context": {
            "category": INDICATOR_CATEGORIES.get(indicator_id, "Economic"),
            "update_frequency": INDICATOR_FREQUENCIES.get(indicator_id, "Monthly"),
            "interpretation_guide": INDICATOR_INTERPRETATIONS.get(indicator_id, "")
        }
    }
    
    # Add indicator-specific components
    if indicator_id in INDICATOR_COMPONENTS:
        payload["components"] = _build_component_data(indicator_id, df)
    
    # Add recession context if available
    if 'USREC' in df.columns:
        usrec = df['USREC'].dropna()
        if len(usrec) > 0:
            payload["recession_context"] = {
                "currently_in_recession": bool(usrec.iloc[-1] == 1),
                "last_recession": _get_last_recession_date(usrec)
            }
    
    return payload


# Metadata dictionaries
INDICATOR_NAMES = {
    'gdp': 'GDP Growth',
    'consumer-spending': 'Consumer Spending',
    'labor-market': 'Labor Market & Unemployment',
    'interest-rates': 'Interest Rates',
    'inflation': 'Inflation & Consumer Prices',
    'business-confidence': 'Business Confidence',
    'stock-market': 'Stock Market',
    'trade-balance': 'Trade Balance',
    'housing': 'Housing Market',
    'policy': 'Monetary Policy & Rates'
}

INDICATOR_UNITS = {
    'gdp': 'Billions of Dollars',
    'consumer-spending': 'Billions of Dollars',
    'labor-market': 'Percent',
    'interest-rates': 'Percent',
    'inflation': 'Index (1982-84=100)',
    'business-confidence': 'Index',
    'stock-market': 'Points',
    'trade-balance': 'Millions of Dollars',
    'housing': 'Thousands of Units',
    'policy': 'Percent'
}

INDICATOR_CATEGORIES = {
    'gdp': 'Growth',
    'consumer-spending': 'Growth',
    'labor-market': 'Employment',
    'interest-rates': 'Monetary',
    'inflation': 'Prices',
    'business-confidence': 'Sentiment',
    'stock-market': 'Markets',
    'trade-balance': 'Trade',
    'housing': 'Real Estate',
    'policy': 'Monetary'
}

INDICATOR_FREQUENCIES = {
    'gdp': 'Quarterly',
    'consumer-spending': 'Monthly',
    'labor-market': 'Monthly',
    'interest-rates': 'Daily',
    'inflation': 'Monthly',
    'business-confidence': 'Monthly',
    'stock-market': 'Daily',
    'trade-balance': 'Monthly',
    'housing': 'Monthly',
    'policy': 'As Announced'
}

INDICATOR_INTERPRETATIONS = {
    'gdp': 'Level is measured in billions of dollars. Growth rate (QoQ annualized) above 2.5% is strong, below 0% suggests recession.',
    'consumer-spending': 'Higher is better. Drives 70% of GDP.',
    'labor-market': 'Lower unemployment is better. Below 5% is healthy, below 4% is very healthy, above 6% is concerning.',
    'interest-rates': 'Context-dependent. High rates slow economy, low rates stimulate.',
    'inflation': 'Target is 2% YoY. Too high or too low are both concerning.',
    'business-confidence': 'Higher is better. Above 80 is confident, below 60 is pessimistic.',
    'stock-market': 'Higher generally indicates economic confidence.',
    'trade-balance': 'Deficits are concerning if large. Smaller deficits are normal.',
    'housing': 'Higher starts indicate economic health. 1.5M+ is strong.',
    'policy': 'Fed adjusts rates to balance growth and inflation.'
}

INDICATOR_COMPONENTS = {
    'inflation': [
        ('CPILFESL', 'Core CPI (ex Food & Energy)'),
        ('CPIENGSL', 'Energy'),
        ('CPIFABSL', 'Food & Beverages')
    ],
    'labor-market': [
        ('U6RATE', 'U-6 Underemployment'),
        ('ICSA', 'Initial Jobless Claims'),
        ('JTSJOL', 'Job Openings (JOLTS)')
    ],
    'housing': [
        ('HSN1F', 'New Home Sales'),
        ('EXHOSLUSM495S', 'Existing Home Sales'),
        ('MORTGAGE30US', '30-Year Mortgage Rate')
    ]
}
