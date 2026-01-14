"""
JPM Economic Dashboard - FastAPI Router

Provides REST API endpoints for economic indicator data:
- GET /overview - Latest snapshot of all 10 indicators
- GET /indicators/{category} - Detailed data for specific indicator
- GET /series/{series_id} - Single FRED series with all metrics
- GET /health - Data freshness status

All endpoints serve from pre-aggregated parquet files in data/processed/jpm_dashboard/
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Dict, List, Any, Optional, Literal
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

from mie_lib.utils.paths import PROCESSED_DATA_DIR, FRED_DATA_DIR
from scipy.stats import percentileofscore
import json

router = APIRouter()
LOG = logging.getLogger(__name__)

# Insights cache directory
INSIGHTS_DIR = Path("/app/data/reports/economic")

def _load_cached_insights(indicator_id: str, tier: int) -> Optional[Dict]:
    """Load cached AI insights from file"""
    # Try both /app path and relative path
    possible_dirs = [
        Path("/app/data/reports/economic"),
        Path("data/reports/economic")
    ]
    
    for insights_dir in possible_dirs:
        insight_file = insights_dir / f"{indicator_id}_tier{tier}_latest.json"
        if insight_file.exists():
            try:
                import json
                with open(insight_file, 'r') as f:
                    data = json.load(f)
                return data.get('insights', {})
            except Exception as e:
                LOG.error(f"Error loading insights from {insight_file}: {e}")
            return None
    
    LOG.debug(f"No cached insights found for {indicator_id} tier {tier}")
    return None

# Category to file mapping
CATEGORIES = {
    'gdp': 'gdp.parquet',
    'consumer-spending': 'consumer_spending.parquet',
    'labor-market': 'labor_market.parquet',
    'interest-rates': 'interest_rates.parquet',
    'inflation': 'inflation.parquet',
    'business-confidence': 'business_confidence.parquet',
    'stock-market': 'stock_market.parquet',
    'trade-balance': 'trade_balance.parquet',
    'housing': 'housing.parquet',
    'policy': 'policy.parquet'
}

# Primary series for each indicator
PRIMARY_SERIES = {
    'gdp': 'GDPC1',
    'consumer-spending': 'PCE',
    'labor-market': 'UNRATE',
    'interest-rates': 'FEDFUNDS',
    'inflation': 'CPIAUCSL',
    'business-confidence': 'BSCICP02USM460S',
    'stock-market': 'sp500',
    'trade-balance': 'BOPGSTB',
    'housing': 'HOUST',
    'policy': 'FEDFUNDS'
}

# Display names
DISPLAY_NAMES = {
    'gdp': 'GDP Growth',
    'consumer-spending': 'Consumer Spending',
    'labor-market': 'Labor Market',
    'interest-rates': 'Interest Rates',
    'inflation': 'Inflation',
    'business-confidence': 'Business Confidence',
    'stock-market': 'Stock Market',
    'trade-balance': 'Trade Balance',
    'housing': 'Housing Market',
    'policy': 'Policy & Rates'
}

# Units for primary series
UNITS = {
    'GDPC1': '% QoQ Ann.',
    'PCE': 'Billions $',
    'UNRATE': '%',
    'FEDFUNDS': '%',
    'CPIAUCSL': 'Index',
    'BSCICP02USM460S': 'Index',
    'sp500': 'Points',
    'BOPGSTB': 'Millions $',
    'HOUST': 'K'
}

# Mapping for Human-Friendly Series Names
SERIES_MAPPING = {
    'CPIAUCSL': 'Consumer Price Index (Headline CPI)',
    'CPILFESL': 'Core CPI (Ex-Food & Energy)',
    'PCEPI': 'PCE Price Index (Headline)',
    'PCEPILFE': 'Core PCE Price Index',
    'PPIFIS': 'Producer Price Index (PPI)',
    'T5YIE': '5-Year Breakeven Inflation Rate',
    'MICH': 'UMich Inflation Expectations',
    'UNRATE': 'Unemployment Rate',
    'PAYEMS': 'Nonfarm Payrolls (Total Nonfarm)',
    'ICSA': 'Initial Jobless Claims',
    'CCSA': 'Continued Claims (Insured Unemployment)',
    'JTSJOL': 'Job Openings (JOLTS)',
    'JTSQUR': 'Quits Rate (JOLTS)',
    'CIVPART': 'Labor Force Participation Rate',
    'CES0500000003': 'Average Hourly Earnings',
    'AWHMAN': 'Avg Weekly Hours (Mfg)',
    'ECIALLCIV': 'Employment Cost Index (ECI)',
    'SAHMREALTIME': 'Sahm Rule Recession Indicator',
    'GDPC1': 'Real GDP',
    'GDP': 'Gross Domestic Product (Nominal)',
    'PCEC96': 'Real Personal Consumption',
    'PCE': 'Personal Consumption Expenditures',
    'RSAFS': 'Retail Sales',
    'INDPRO': 'Industrial Production',
    'DSPIC96': 'Real Disposable Personal Income',
    'TOTALSL': 'Consumer Credit Outstanding',
    'NEWORDER': 'Durable Goods New Orders',
    'DFF': 'Federal Funds Effective Rate',
    'FEDFUNDS': 'Effective Federal Funds Rate',
    'DGS10': '10-Year Treasury Yield',
    'DGS5': '5-Year Treasury Yield',
    'DGS2': '2-Year Treasury Yield',
    'DGS1MO': '1-Month Treasury Yield',
    'DGS2MO': '2-Month Treasury Yield',
    'TB3MS': '3-Month Treasury Yield',
    'DGS3MO': '3-Month Treasury Yield',
    'DGS6MO': '6-Month Treasury Yield',
    'DGS30': '30-Year Treasury Yield',
    'T10Y2Y': '10Y-2Y Treasury Spread',
    'SPREAD30Y5Y': '30Y-5Y Treasury Spread',
    'T10Y3M': '10Y-3M Treasury Spread',
    'MORTGAGE30US': '30-Year Fixed Mortgage Rate',
    'HOUST': 'Housing Starts',
    'PERMIT': 'New Housing Permits',
    'HSN1F': 'New Home Sales',
    'EXHOSLUSM495S': 'Existing Home Sales',
    'CSUSHPINSA': 'Case-Shiller Home Price Index',
    'MSACSR': 'Monthly Supply of Houses',
    'M2SL': 'M2 Money Supply',
    'NFCI': 'National Financial Conditions Index',
    'USREC': 'NBER Recession Indicator',
    'SP500': 'S&P 500 Index',
    'UMCSENT': 'UMich Consumer Sentiment',
    'GACDFSA066MSFRBPHI': 'Philly Fed Business Outlook',
    'GACDISA066MSFRBNY': 'Empire State Mfg Survey',
    'BCNSDODNS': 'Nonfinancial Corporate Debt',
    'NCBCMDPMVCE': 'Corporate Debt to Equity Ratio',
    'QUSPAM770A': 'Total Private Credit (% of GDP)',
    'CPATAX': 'Corporate Profits After Tax',
    'PSAVERT': 'Personal Savings Rate',
    'TOTLL': 'Total Loans and Leases',
    'BOPGSTB': 'Trade Balance (Goods & Services)',
    'EXPGS': 'Exports (Goods & Services)',
    'IMPGS': 'Imports (Goods & Services)',
    'DTWEXBGS': 'Trade Weighted US Dollar Index',
    'FYFSD': 'Federal Surplus or Deficit',
    'GFDEGDQ188S': 'Public Debt as % of GDP',
    'DGDSRG3Q086SBEA': 'Real PCE - Goods',
    'DSERRG3Q086SBEA': 'Real PCE - Services',
    'RRSFS': 'Real Retail & Food Sales',
    'RSXFS': 'Retail Sales ex-Food Services',
    'ULCMFG': 'Unit Labor Cost (Mfg)',
    'CUSR0000SAH1': 'CPI Shelter',
    'CPIENGSL': 'CPI Energy',
    'CUSR0000SASLE': 'CPI Services Less Energy',
    'WALCL': 'Fed Total Assets',
    'STLFSI': 'St. Louis Fed Financial Stress Index',
    'CFNAI': 'Chicago Fed National Activity Index',
    'ECBASSETS': 'ECB Total Assets',
    'JPNASSETS': 'BoJ Total Assets',
    'DEXUSEU': 'USD/EUR Exchange Rate',
    'DEXJPUS': 'JPY/USD Exchange Rate',
    'CSCICP03USM665S': 'Consumer Confidence Index (OECD)',
    'BSCICP02USM460S': 'Business Confidence (Manufacturing)',
    'BUSLOANS': 'Commercial & Industrial Loans',
    'BAMLC0A4CBBB': 'BBB Corporate Bond Spread'
}

# Series that should always be positive (prevent negative display issues)
POSITIVE_SERIES = ['ICSA', 'CCSA', 'JTSJOL', 'JTSQUR', 'PAYEMS', 'HOUST', 'PERMIT', 'HSN1F', 'EXHOSLUSM495S']

# Specific units for proper frontend formatting
SERIES_UNITS_METADATA = {
    'JTSJOL': 'K',
    'ICSA': 'K', 
    'CCSA': 'K',
    'PAYEMS': 'K',
    'HOUST': 'K',
    'PERMIT': 'K',
    'HSN1F': 'K',
    'EXHOSLUSM495S': 'M',
    'DGS30': '%',
    'DGS10': '%',
    'DGS5': '%',
    'DGS2': '%',
    'DGS1MO': '%',
    'DGS2MO': '%',
    'DGS6MO': '%',
    'DGS3MO': '%',
    'TB3MS': '%',
    'T10Y2Y': '%',
    'T10Y3M': '%',
    'SPREAD30Y5Y': '%',
    'MORTGAGE30US': '%'
}

def standardize_unit(series_id: str, original_unit: str) -> str:
    """
    Convert verbose units to standard abbreviations.
    """
    # Check manual metadata first
    if series_id in SERIES_UNITS_METADATA:
        return SERIES_UNITS_METADATA[series_id]
        
    # Generic conversions
    if not original_unit or not isinstance(original_unit, str):
        return original_unit
        
    unit_lower = original_unit.lower()
    
    if 'thousand' in unit_lower:
        return 'K'
    elif 'billion' in unit_lower:
        return '$B' if '$' in original_unit else 'B'
    elif 'million' in unit_lower:
        return 'M'
    elif 'percent' in unit_lower or '%' in original_unit:
        return '%'
    elif 'index' in unit_lower:
        return 'Index'
        
    return original_unit


def load_indicator_data(category: str) -> pd.DataFrame:
    """Load aggregated indicator data from parquet file."""
    file_path = PROCESSED_DATA_DIR / "jpm_dashboard" / CATEGORIES[category]
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Indicator data not found for category: {category}"
        )
    
    try:
        df = pd.read_parquet(file_path)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        LOG.error(f"Error loading {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")


def check_data_freshness(df: pd.DataFrame, max_days: int = 7) -> Dict[str, Any]:
    """Check if data is fresh enough."""
    if df.empty:
        return {'status': 'error', 'message': 'No data available'}
    
    latest_date = df['date'].max()
    days_old = (datetime.now() - latest_date).days
    
    if days_old > max_days:
        return {
            'status': 'stale',
            'days_old': days_old,
            'latest_date': latest_date.strftime('%Y-%m-%d')
        }
    
    return {
        'status': 'ok',
        'days_old': days_old,
        'latest_date': latest_date.strftime('%Y-%m-%d')
    }


def determine_trend(series: pd.Series, lookback: int = 3) -> str:
    """Determine trend direction from recent values."""
    recent = series.tail(lookback).dropna()
    
    if len(recent) < 2:
        return 'flat'
    
    slope = np.polyfit(range(len(recent)), recent.values, 1)[0]
    threshold = abs(recent.mean()) * 0.01  # 1% threshold
    
    if slope > threshold:
        return 'up'
    elif slope < -threshold:
        return 'down'
    else:
        return 'flat'



# --- Health Score and Logic Helpers ---

def calculate_gdp_health(current_value, percentile, yoy_change):
    score = 100
    
    # Percentile component (50% weight)
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
        return int(percentile * 0.7 + (30 if yoy_change and yoy_change > 0 else 0))
    elif indicator_id == 'housing':
        return calculate_housing_health(current_value, percentile, yoy_change)
    elif indicator_id == 'business-confidence':
        return calculate_business_confidence_health(current_value, percentile, yoy_change)
    elif indicator_id == 'trade-balance':
        # Closer to zero is better (large deficits are bad)
        if current_value is not None:
            # Invert percentile if deficit
            return int((100 - percentile) if current_value < 0 else percentile)
        return 50
    elif indicator_id == 'policy':
        # Use rates calculation
        return calculate_rates_health(percentile, current_value)
    else:
        # Default: use percentile
        return int(percentile)

def classify_signal(zscore: float) -> str:
    """Classify economic signal based on z-score."""
    if pd.isna(zscore):
        return 'unknown'
    
    if zscore >= 0.5:
        return 'expansion'
    elif zscore <= -0.5:
        return 'recession'
    else:
        return 'slowdown'


# Indicator update frequencies
INDICATOR_FREQUENCIES = {
    'gdp': 'quarterly',
    'consumer-spending': 'monthly',
    'labor-market': 'monthly',
    'interest-rates': 'daily',
    'inflation': 'monthly',
    'business-confidence': 'monthly',
    'stock-market': 'daily',
    'trade-balance': 'monthly',
    'housing': 'monthly',
    'policy': 'daily'
}


def calculate_6month_trend(series_data: pd.Series, frequency: str = 'monthly') -> str:
    """
    Calculate trend direction over consistent 6-month period
    
    Args:
        series_data: Pandas Series with numeric values
        frequency: 'daily', 'monthly', or 'quarterly'
    
    Returns:
        trend_direction: 'up', 'down', or 'flat'
    """
    if len(series_data) < 2:
        return 'flat'
        
    # Special handling for unemployment (absolute change)
    if frequency == 'unemployment':
        current = series_data.iloc[-1]
        six_months_ago = series_data.iloc[-6] if len(series_data) >= 6 else series_data.iloc[0]
        
        abs_change = current - six_months_ago
        if abs_change > 0.15:
            return 'up'
        elif abs_change < -0.15:
            return 'down'
        else:
            return 'flat'
    
    # Determine lookback based on frequency
    if frequency == 'quarterly':
        lookback = 2  # 2 quarters = 6 months
    elif frequency == 'monthly':
        lookback = 6  # 6 months
    elif frequency == 'daily':
        lookback = 126  # ~6 months of trading days
    else:
        lookback = 6  # default to 6 periods
    
    if len(series_data) < lookback:
        lookback = len(series_data)
    
    current = series_data.iloc[-1]
    six_months_ago = series_data.iloc[-lookback]
    
    # Calculate percentage change
    if six_months_ago == 0:
        return 'flat'
    
    pct_change = ((current - six_months_ago) / abs(six_months_ago)) * 100
    
    # Determine direction with threshold
    if pct_change > 1.0:  # More than 1% change = trend
        return 'up'
    elif pct_change < -1.0:
        return 'down'
    else:
        return 'flat'


def calculate_growth_rates(series_data: pd.Series, frequency: str = 'monthly') -> Dict[str, Any]:
    """
    Calculate YoY and last-period growth rates
    
    Args:
        series_data: Pandas Series with numeric values
        frequency: 'daily', 'monthly', or 'quarterly'
    
    Returns:
        dict with yoy_pct, last_period_pct, last_period_label
    """
    if len(series_data) < 2:
        return {
            'yoy_pct': None,
            'last_period_pct': None,
            'last_period_label': None
        }
    
    current = series_data.iloc[-1]
    
    # YoY calculation
    yoy_pct = None
    if frequency == 'quarterly' and len(series_data) >= 5:
        year_ago = series_data.iloc[-5]  # 4 quarters ago
        if year_ago != 0:
            yoy_pct = ((current - year_ago) / abs(year_ago)) * 100
    elif frequency == 'monthly' and len(series_data) >= 13:
        year_ago = series_data.iloc[-13]  # 12 months ago
        if year_ago != 0:
            yoy_pct = ((current - year_ago) / abs(year_ago)) * 100
    elif frequency == 'daily' and len(series_data) >= 252:
        year_ago = series_data.iloc[-252]  # ~252 trading days
        if year_ago != 0:
            yoy_pct = ((current - year_ago) / abs(year_ago)) * 100
    
    # Last period calculation
    previous = series_data.iloc[-2]
    if previous == 0:
        return {
            'yoy_pct': round(yoy_pct, 2) if yoy_pct is not None else None,
            'last_period_pct': None,
            'last_period_label': None
        }
    
    last_period_pct = ((current - previous) / abs(previous)) * 100
    
    # Label for last period
    if frequency == 'quarterly':
        # For quarterly, annualize the QoQ change
        last_period_pct_annualized = last_period_pct * 4
        last_period_label = 'QoQ Ann'
        last_period_value = last_period_pct_annualized
    elif frequency == 'monthly':
        last_period_label = 'MoM'
        last_period_value = last_period_pct
    elif frequency == 'daily':
        last_period_label = 'DoD'
        last_period_value = last_period_pct
    else:
        last_period_label = 'Last'
        last_period_value = last_period_pct
    
    return {
        'yoy_pct': round(yoy_pct, 2) if yoy_pct is not None else None,
        'last_period_pct': round(last_period_value, 2) if last_period_value is not None else None,
        'last_period_label': last_period_label
    }


def calculate_moving_average(series: pd.Series, window_size: int) -> List[Dict[str, Any]]:
    """
    Calculate moving average for time series
    
    Args:
        series: Pandas Series with datetime index and numeric values
        window_size: Number of periods for MA (e.g., 40 quarters = 10 years)
    
    Returns:
        List of {date, value} dicts with MA values
    """
    ma_values = []
    
    for i in range(len(series)):
        date = series.index[i]
        
        if i < window_size - 1:
            # Not enough data yet for full window
            ma_values.append({'date': str(date), 'value': None})
        else:
            # Calculate average of last N periods
            window_data = series.iloc[i - window_size + 1 : i + 1]
            ma = float(window_data.mean ())
            ma_values.append({'date': str(date), 'value': ma})
    
    return ma_values


def calculate_distribution(series: pd.Series, current_value: float, num_bins: int = 30) -> Dict[str, Any]:
    """
    Calculate histogram distribution for time series
    
    Args:
        series: Pandas Series with historical values
        current_value: Current value to mark on distribution
        num_bins: Number of histogram bins
    
    Returns:
        Dict with histogram data and current position
    """
    import numpy as np
    
    values = series.dropna().values
    
    if len(values) < 2:
        return None
    
    # Calculate histogram
    counts, bin_edges = np.histogram(values, bins=num_bins)
    
    # Bin centers for x-axis
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Calculate percentile of current value
    percentile = float(percentileofscore(values, current_value))
    
    # Find which bin the current value falls into
    current_bin_index = int(np.digitize([current_value], bin_edges)[0] - 1)
    current_bin_index = max(0, min(current_bin_index, len(bin_centers) - 1))
    
    return {
        'bins': [float(x) for x in bin_centers],
        'counts': [int(x) for x in counts],
        'current_value': float(current_value),
        'current_bin': current_bin_index,
        'percentile': percentile,
        'min_value': float(values.min()),
        'max_value': float(values.max()),
        'mean_value': float(values.mean()),
        'median_value': float(np.median(values)),
        'std_value': float(np.std(values))  # Add standard deviation for Gaussian curve
    }


@router.get("/overview")
async def get_overview(response: Response) -> Dict[str, Any]:
    """
    Get overview of all 10 indicators with latest values and sparklines.
    
    Returns:
        - last_updated: Timestamp
        - indicators: Array of 10 indicators with current values and sparklines
    """
    # Add cache headers (15 min)
    response.headers["Cache-Control"] = "public, max-age=900"
    
    indicators = []
    
    for category in CATEGORIES.keys():
        try:
            df = load_indicator_data(category)
            
            # Get primary series
            primary_col = PRIMARY_SERIES[category]
            
            if primary_col not in df.columns:
                LOG.warning(f"Primary series {primary_col} not found in {category}")
                continue
            
            # --- METRIC CALCULATION (Dynamic) ---
            
            # Latest value
            clean_df = df[df[primary_col].notna()].copy()
            if len(clean_df) == 0:
                continue
                
            latest_row = clean_df.iloc[-1]
            current_value = latest_row[primary_col]
            current_date = latest_row['date'].strftime('%Y-%m-%d')
            
            # Calculate YoY change (Dynamic)
            # Find closest date 1 year ago (approx 252 trading days or 365 days)
            # Since data frequency varies (monthly, daily), use date logic
            one_year_ago_date = latest_row['date'] - timedelta(days=365)
            # Find row closest to one_year_ago_date
            # Simple approach: use index if datetime index, or filter
            past_df = clean_df[clean_df['date'] <= one_year_ago_date]
            
            yoy_change = None
            yoy_absolute_change = None
            
            if not past_df.empty:
                year_ago_val = past_df.iloc[-1][primary_col]
                
                # Calculate absolute change (needed for Labor Market)
                yoy_absolute_change = current_value - year_ago_val
                
                # Calculate relative change
                if year_ago_val != 0:
                    yoy_change = ((current_value - year_ago_val) / abs(year_ago_val)) * 100
            
            # Calculate Percentile Rank (Dynamic)
            # Compare current value to entire history
            percentile = 0.0
            if len(clean_df) > 1:
                # Use scipy specific function or simple numpy
                # Note: scipy.stats.percentileofscore requires (array, score)
                # rank is 0-100
                percentile = float(percentileofscore(clean_df[primary_col], current_value))
            
            # Calculate Health Score (Dynamic)
            health_score = calculate_health_score(
                category,
                float(current_value) if current_value is not None else None,
                float(percentile),
                float(yoy_change) if yoy_change is not None else None,
                float(yoy_absolute_change) if yoy_absolute_change is not None else None
            )

            # --- Calculate 30-Day Historical Health Score ---
            health_score_30d = None
            date_30d = latest_row['date'] - timedelta(days=30)
            df_30d = clean_df[clean_df['date'] <= date_30d]
            
            if not df_30d.empty:
                row_30d = df_30d.iloc[-1]
                val_30d = float(row_30d[primary_col])
                
                # 30d YoY
                date_1y_30d = row_30d['date'] - timedelta(days=365)
                df_1y_30d = clean_df[clean_df['date'] <= date_1y_30d]
                yoy_30d = None
                yoy_abs_30d = None
                
                if not df_1y_30d.empty:
                    val_1y_30d = float(df_1y_30d.iloc[-1][primary_col])
                    yoy_abs_30d = val_30d - val_1y_30d
                    if val_1y_30d != 0:
                        yoy_30d = ((val_30d - val_1y_30d) / abs(val_1y_30d)) * 100
                
                # 30d Percentile (using full history as reference distribution)
                pct_30d = float(percentileofscore(clean_df[primary_col], val_30d))
                
                health_score_30d = calculate_health_score(
                    category,
                    val_30d,
                    pct_30d,
                    yoy_30d,
                    yoy_abs_30d
                )

            # Sparkline (last 12 months or 90 days for daily data)
            lookback = 90 if category in ['stock-market', 'interest-rates'] else 12
            sparkline_data = clean_df.tail(lookback)
            
            sparkline = [
                {
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'value': float(row[primary_col])
                }
                for _, row in sparkline_data.iterrows()
            ]
            
            # Get indicator frequency
            frequency = INDICATOR_FREQUENCIES.get(category, 'monthly')
            
            # Calculate 6-month trend (consistent across all indicators)
            trend_direction = calculate_6month_trend(clean_df[primary_col], frequency)
            
            # Calculate growth rates (YoY and last period)
            growth_rates = calculate_growth_rates(clean_df[primary_col], frequency)
            
            # Determine signal from health score
            if health_score >= 60:
                signal = 'expansion'
            elif health_score <= 40:
                signal = 'recession'
            else:
                signal = 'slowdown'
            
            # Determine unit
            raw_unit = UNITS.get(primary_col, 'Index')
            unit = standardize_unit(primary_col, raw_unit)

            # Load Tier 1 AI insights from cache
            tier1_insights = _load_cached_insights(category, 1)
            one_line_insight = tier1_insights.get('one_line_insight', 'Analysis pending...') if tier1_insights else 'Analysis pending...'
            
            indicators.append({
                'id': category,
                'name': DISPLAY_NAMES[category],
                'category': category,
                'tier': 1,
                'current_value': float(current_value) if pd.notna(current_value) else None,
                'current_date': current_date,
                'unit': unit,
                'trend_direction': trend_direction,
                'trend_period': '6M',  # Consistent 6-month trend period
                'sparkline': sparkline,
                'yoy_change': growth_rates['yoy_pct'],  # Use calculated YoY from growth_rates
                'last_period_change': growth_rates['last_period_pct'],  # NEW: Last period change
                'last_period_label': growth_rates['last_period_label'],  # NEW: Label (QoQ Ann, MoM, etc)
                'percentile': float(percentile),
                'signal': signal,
                'health_score': health_score,
                'health_score_30d': health_score_30d,
                'one_line_insight': one_line_insight
            })
            
        except Exception as e:
            LOG.error(f"Error processing {category} for overview: {e}")
            continue
    
    # Calculate overall health score
    valid_scores = [ind['health_score'] for ind in indicators if ind['health_score'] is not None]
    overall_health = int(sum(valid_scores) / len(valid_scores)) if valid_scores else 0

    # Calculate overall health score 30d
    valid_scores_30d = [ind['health_score_30d'] for ind in indicators if ind['health_score_30d'] is not None]
    overall_health_30d = int(sum(valid_scores_30d) / len(valid_scores_30d)) if valid_scores_30d else 0

    return {
        'last_updated': datetime.now().isoformat(),
        'overall_health': overall_health,
        'overall_health_30d': overall_health_30d,
        'indicators': indicators
    }


@router.get("/indicators/{category}")
async def get_indicator_detail(
    category: str,
    response: Response,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    include_recessions: bool = Query(True, description="Include recession periods")
) -> Dict[str, Any]:
    """
    Get detailed data for a specific indicator category.
    
    Args:
        category: Indicator category (gdp, inflation, etc.)
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_recessions: Whether to include recession period overlay
    
    Returns:
        Detailed indicator data with primary/secondary metrics and historical data
    """
    # Validate category
    if category not in CATEGORIES:
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category. Must be one of: {', '.join(CATEGORIES.keys())}"
        )
    
    # Add cache headers (5 min)
    response.headers["Cache-Control"] = "public, max-age=300"
    
    # Load data
    df = load_indicator_data(category)
    
    # Filter by date range if provided
    if start_date:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['date'] <= pd.to_datetime(end_date)]
    
    # Get primary series
    primary_col = PRIMARY_SERIES[category]
    
    # Extract all series from columns (base columns without _yoy, _mom, etc suffixes)
    all_cols = [c for c in df.columns if not any(c.endswith(suffix) for suffix in ['_yoy', '_mom', '_qoq', '_zscore', '_pct', '_ma3'])]
    series_cols = [c for c in all_cols if c not in ['date', 'recession', 'last_updated']]
    
    # Build primary metric
    primary_data = []
    for _, row in df.iterrows():
        primary_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'value': float(row[primary_col]) if pd.notna(row[primary_col]) else None,
            'yoy': float(row.get(f"{primary_col}_yoy")) if pd.notna(row.get(f"{primary_col}_yoy")) else None,
            'zscore': float(row.get(f"{primary_col}_zscore")) if pd.notna(row.get(f"{primary_col}_zscore")) else None
        })
    
    # --- METRIC CALCULATION (Dynamic) ---
    clean_df = df[df[primary_col].notna()].copy()
    latest = clean_df.iloc[-1]
    
    current_value = latest[primary_col]
    current_date = latest['date'].strftime('%Y-%m-%d')
    
    # Calculate YoY change (Dynamic)
    one_year_ago_date = latest['date'] - timedelta(days=365)
    past_df = clean_df[clean_df['date'] <= one_year_ago_date]
    yoy_change = None
    if not past_df.empty:
        year_ago_val = past_df.iloc[-1][primary_col]
        if year_ago_val != 0:
            yoy_change = ((current_value - year_ago_val) / abs(year_ago_val)) * 100
    
    # Calculate absolute YoY change (for Labor Market compatibility)
    yoy_absolute_change = None
    if not past_df.empty:
        year_ago_val = past_df.iloc[-1][primary_col]
        yoy_absolute_change = current_value - year_ago_val
            
    # Calculate Percentile Rank (Dynamic)
    percentile = 0.0
    if len(clean_df) > 1:
        percentile = float(percentileofscore(clean_df[primary_col], current_value))
        
    # Calculate Health Score (Dynamic)
    # Calculate Health Score (Dynamic)
    health_score = calculate_health_score(
        category,
        float(current_value) if current_value is not None else None,
        float(percentile),
        float(yoy_change) if yoy_change is not None else None,
        float(yoy_absolute_change) if yoy_absolute_change is not None else None
    )
    
    trend_direction = determine_trend(clean_df[primary_col])
    
    # Calculate 10-year historical average for context
    ten_years_ago = latest['date'] - timedelta(days=365*10)
    hist_10y = clean_df[clean_df['date'] >= ten_years_ago][primary_col]
    historical_avg = float(hist_10y.mean()) if not hist_10y.empty else None
    
    # Calculate 10year moving average for trend line
    frequency = INDICATOR_FREQUENCIES.get(category, 'monthly')
    if frequency == 'quarterly':
        ma_window = 40  # 10 years
    elif frequency == 'monthly':
        ma_window = 120  # 10 years
    elif frequency == 'daily':
        ma_window = 2520  # ~10 years of trading days
    else:
        ma_window = 120
    
    # Calculate MA on the full series with date index
    series_with_index = clean_df.set_index('date')[primary_col]
    moving_average_10y = calculate_moving_average(series_with_index, ma_window)
    
    # Calculate distribution
    distribution = calculate_distribution(clean_df[primary_col], float(current_value))
    
    # Determine unit for primary metric
    raw_primary_unit = UNITS.get(primary_col, 'Index')
    primary_unit = standardize_unit(primary_col, raw_primary_unit)

    # Build primary metric
    primary_metric = {
        'series_id': primary_col,
        'name': DISPLAY_NAMES[category],
        'current': float(current_value) if pd.notna(current_value) else None,
        'current_date': current_date,
        'unit': primary_unit,
        'yoy_change': float(yoy_change) if yoy_change is not None else None,
        'yoy_absolute_change': float(yoy_absolute_change) if yoy_absolute_change is not None else None,
        'percentile': float(percentile),
        'health_score': health_score,
        'trend_direction': trend_direction,
        'historical_avg': historical_avg,
        'data': primary_data,
        'moving_average_10y': moving_average_10y,  # NEW
        'distribution': distribution  # NEW
    }
    
    # Build secondary metrics
    secondary_metrics = []
    for col in series_cols:
        if col != primary_col:
            sec_data = []
            for _, row in df.iterrows():
                sec_data.append({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'value': float(row[col]) if pd.notna(row[col]) else None
                })
            
            # Get last valid value for this specific series
            valid_series = df[col].dropna()
            current_val = valid_series.iloc[-1] if not valid_series.empty else None
            
            # Force positive if required
            if col in POSITIVE_SERIES and current_val is not None:
                current_val = abs(current_val)
            
            # Determine unit (override default if needed)
            # Use the series_id itself as the original_unit if not found in UNITS,
            # then standardize it.
            raw_secondary_unit = UNITS.get(col, '') # Default to empty string if not in UNITS
            secondary_unit = standardize_unit(col, raw_secondary_unit)
            
            # --- Enhanced Metrics for Related Card ---
            # Calculate 6-month trend
            frequency = INDICATOR_FREQUENCIES.get(category, 'monthly') # Use category frequency as proxy
            trend_6m = calculate_6month_trend(valid_series, frequency)
            
            # Calculate Changes (YoY, Period)
            growth = calculate_growth_rates(valid_series, frequency)
            
            # Sparkline Data (Last 24 periods)
            sparkline_lookback = 24
            sparkline_data = []
            
            # Filter original df to keep date context
            valid_df = df[['date', col]].dropna()
            
            if not valid_df.empty:
                sl_df = valid_df.tail(sparkline_lookback)
                sparkline_data = [
                    {'date': row['date'].strftime('%Y-%m-%d'), 'value': float(row[col])}
                    for _, row in sl_df.iterrows()
                ]

            secondary_metrics.append({
                'series_id': col,
                'series_id_raw': col, 
                'display_name': SERIES_MAPPING.get(col, col.replace('_', ' ').title()),
                'current_value': float(current_val) if pd.notna(current_val) else None,
                'current': float(current_val) if pd.notna(current_val) else None, # key for backward compatibility
                'unit': secondary_unit,
                'yoy_change_pct': growth['yoy_pct'],
                'period_change_pct': growth['last_period_pct'],
                'period_label': growth['last_period_label'],
                'trend_6m': trend_6m,
                'frequency': frequency,
                'historical_data': sparkline_data,
                'data': sec_data 
            })
            
    # Custom Sorting for Interest Rates
    if category == 'interest-rates':
        # Order: Bills (Short), Notes/Bonds (Long), Spreads, Mortgages
        RATE_ORDER = [
            'DGS1MO', 'DGS2MO', 'TB3MS', 'DGS3MO', 'DGS6MO', 
            'DGS2', 'DGS5', 'DGS10', 'DGS30',
            'T10Y2Y', 'T10Y3M', 'SPREAD30Y5Y',
            'MORTGAGE30US'
        ]
        secondary_metrics.sort(key=lambda x: RATE_ORDER.index(x['series_id']) if x['series_id'] in RATE_ORDER else 999)
    
    # Recession periods
    # Recession periods
    recessions = []
    if include_recessions and 'recession' in df.columns:
        # Find recession periods (where recession == 1)
        in_recession = False
        start_date = None
        
        # Safe iteration using date column directly
        for date, value in zip(df['date'], df['recession'].fillna(0)):
            if value == 1 and not in_recession:
                # Recession starts
                in_recession = True
                start_date = str(date.date() if hasattr(date, 'date') else date)
            elif value == 0 and in_recession:
                # Recession ends
                in_recession = False
                recessions.append({
                    'start': start_date,
                    'end': str(date.date() if hasattr(date, 'date') else date)
                })
        
        # Handle ongoing recession
        if in_recession:
            recessions.append({
                'start': start_date,
                'end': str(df.index[-1].date())
            })
            
    # Load Tier 2 AI insights from cache
    tier2_insights = _load_cached_insights(category, 2)
    # Load Tier 3 AI insights from cache
    tier3_insights = _load_cached_insights(category, 3)
    
    if tier2_insights:
        insights = {
            'detailed_insight': tier2_insights.get('detailed_insight', 'Analysis pending...'),
            'key_takeaways': tier2_insights.get('key_takeaways', []),
            'business_impact': tier2_insights.get('business_impact', 'Analysis pending...')
        }
    else:
        insights = {
            'detailed_insight': 'Analysis pending...',
            'key_takeaways': [],
            'business_impact': 'Analysis pending...'
        }
        
    # Add Tier 3 if available
    if tier3_insights:
        insights.update({
            'comprehensive_insight': tier3_insights.get('comprehensive_insight', 'Deep analysis pending...'),
            'component_analysis': tier3_insights.get('component_analysis', {}),
            'forward_looking': tier3_insights.get('forward_looking', 'Assessment pending...'),
            'historical_context': tier3_insights.get('historical_context', 'Historical context pending...'),
            'recession_signal': tier3_insights.get('recession_signal', 'Signal pending...')
        })
            
    # Add top-level health score for frontend access
    return {
        'category': category,
        'name': DISPLAY_NAMES[category], # Ensure name is present at top level
        'last_updated': latest.get('last_updated', datetime.now()).isoformat(),
        'health_score': health_score, # Explicitly add health score
        'trend_direction': trend_direction,
        'primary_metric': primary_metric,
        'secondary_metrics': secondary_metrics,
        'recessions': recessions,
        'insights': insights,  # Add Tier 2 insights
        'metadata': {
            'update_frequency': 'monthly',
            'rows': len(df)
        }
    }


@router.get("/series/{series_id}")
async def get_series_detail(
    series_id: str,
    response: Response,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get detailed data for a specific FRED series.
    
    Args:
        series_id: FRED series ID
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        Full series data with all calculated metrics
    """
    # Add cache headers (10 min)
    response.headers["Cache-Control"] = "public, max-age=600"
    
    # Search for series across all indicator files
    series_data = None
    found_in = None
    
    for category, filename in CATEGORIES.items():
        try:
            df = load_indicator_data(category)
            
            if series_id in df.columns:
                series_data = df
                found_in = category
                break
        except:
            continue
    
    if series_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Series {series_id} not found in any indicator category"
        )
    
    # Filter by date
    if start_date:
        series_data = series_data[series_data['date'] >= pd.to_datetime(start_date)]
    if end_date:
        series_data = series_data[series_data['date'] <= pd.to_datetime(end_date)]
    
    # Extract series and metrics
    data = []
    for _, row in series_data.iterrows():
        data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'value': float(row[series_id]) if pd.notna(row[series_id]) else None,
            'yoy': float(row.get(f"{series_id}_yoy")) if pd.notna(row.get(f"{series_id}_yoy")) else None,
            'mom': float(row.get(f"{series_id}_mom")) if pd.notna(row.get(f"{series_id}_mom")) else None,
            'zscore': float(row.get(f"{series_id}_zscore")) if pd.notna(row.get(f"{series_id}_zscore")) else None,
            'percentile': float(row.get(f"{series_id}_pct")) if pd.notna(row.get(f"{series_id}_pct")) else None
        })
    
    latest = series_data.iloc[-1]
    
    return {
        'series_id': series_id,
        'category': found_in,
        'current_value': float(latest[series_id]) if pd.notna(latest[series_id]) else None,
        'current_date': latest['date'].strftime('%Y-%m-%d'),
        'data': data,
        'metadata': {
            'rows': len(series_data),
            'start_date': series_data['date'].min().strftime('%Y-%m-%d'),
            'end_date': series_data['date'].max().strftime('%Y-%m-%d')
        }
    }


@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    """
    Check data freshness and availability for all indicators.
    
    Returns:
        Health status for each indicator
    """
    indicators_status = {}
    overall_status = 'healthy'
    
    for category, filename in CATEGORIES.items():
        try:
            df = load_indicator_data(category)
            freshness = check_data_freshness(df, max_days=7)
            
            indicators_status[category] = {
                'last_updated': freshness['latest_date'],
                'staleness_days': freshness['days_old'],
                'status': freshness['status'],
                'rows': len(df)
            }
            
            if freshness['status'] != 'ok':
                overall_status = 'degraded'
                
        except HTTPException:
            indicators_status[category] = {
                'status': 'missing',
                'error': 'Data file not found'
            }
            overall_status = 'degraded'
        except Exception as e:
            indicators_status[category] = {
                'status': 'error',
                'error': str(e)
            }
            overall_status = 'degraded'
    
    return {
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'indicators': indicators_status
    }

# -----------------------------------------------------------------
# Upcoming Releases Endpoint
# -----------------------------------------------------------------

CALENDAR_FILE = Path("data/calendar/fred_release_calendar.json")
MAPPINGS_FILE = Path("frontend/src/data/tier2_release_mappings.json")

def load_tier2_mappings():
    """Load the series mappings for Tier 2 pages."""
    # Try multiple paths for robustness (Docker vs Local)
    paths = [
        MAPPINGS_FILE,
        Path("src/mie_lib/data/tier2_release_mappings.json"),
        Path("/app/frontend/src/data/tier2_release_mappings.json") # Docker specific?
    ]
    
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    
    # Fallback: if file missing, return empty or hardcoded?
    # LOG.warning("Tier 2 mappings file not found.")
    return {}

def calculate_hours_until(date_str: str, time_str: str = "08:30") -> float:
    """Calculate hours until the release from now."""
    try:
        release_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        diff = release_dt - now
        return diff.total_seconds() / 3600.0
    except Exception:
        return 0.0

@router.get("/indicators/{indicator_id}/upcoming-releases")
def get_upcoming_releases(indicator_id: str):
    """
    Get upcoming data releases for the specific indicator.
    Combines mapped series with the FRED release calendar.
    """
    # 1. Load Mappings
    mappings = load_tier2_mappings()
    
    # Normalise ID (URL might uses dashes, mapping uses underscores/keys)
    # e.g. labor-market -> labor_market
    mapped_id = indicator_id.replace("-", "_")
    
    if mapped_id not in mappings:
        # Try finding key that matches display name or fuzzy match?
        # For now, just return empty if not found.
        return {"upcoming": [], "recent": []}
        
    config = mappings[mapped_id]
    target_series = set(config.get("primary_series", []) + config.get("related_series", []))
    
    # 2. Load Calendar
    if not CALENDAR_FILE.exists():
        return {"upcoming": [], "recent": [], "error": "Calendar data not available"}
        
    try:
        with open(CALENDAR_FILE, "r") as f:
            calendar_events = json.load(f)
    except Exception as e:
        LOG.error(f"Failed to load calendar: {e}")
        return {"upcoming": [], "recent": []}
        
    # 3. Filter Events
    relevant_events = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for event in calendar_events:
        # Check intersection
        event_series = set(event.get('series_ids', []))
        if not event_series.isdisjoint(target_series):
            # This event contains at least one series from our page
            relevant_events.append(event)
            
    # 4. Group and Sort
    # Split into 'Today' and 'Upcoming' (Future)
    # Actually, user wants "Upcoming" (including Today).
    # We can separate them in the frontend or here.
    # Let's return a flat list sorted by date, and the frontend groups them.
    # But filtering for PAST events?
    # We keep events from TODAY onwards.
    
    future_events = [e for e in relevant_events if e['release_date'] >= today_str]
    future_events.sort(key=lambda x: (x['release_date'], x.get('release_time', '23:59')))
    
    # Limit to next 5-7 distinct releases?
    # User said "Display next 5-7 releases".
    
    # Enrich with computed fields
    final_events = []
    seen_keys = set()
    
    for e in future_events:
        # Deduplicate by (ReleaseID, Date)? 
        # Sometimes same release ID appears multiple times? No, unique per date usually.
        # But maybe different times?
        key = f"{e['release_id']}_{e['release_date']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        
        # Calculate time
        hours = calculate_hours_until(e['release_date'], e.get('release_time', '08:30'))
        
        # Check if it's primary
        is_primary = not set(config.get("primary_series", [])).isdisjoint(set(e.get('series_ids', [])))
        
        final_events.append({
            "id": e['release_id'],
            "name": e['release_name'],
            "date": e['release_date'],
            "time": e.get('release_time', '08:30'),
            "hours_until": round(hours, 1),
            "is_primary": is_primary,
            "series_count": len(e.get('series_ids', []))
        })
        
        if len(final_events) >= 10: # Return 10, let frontend truncate
            break
            
    return {"releases": final_events}
