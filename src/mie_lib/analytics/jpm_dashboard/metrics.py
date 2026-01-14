"""
JPM Economic Dashboard - Metrics Calculation Library

Provides standardized calculations for economic indicator metrics:
- YoY and MoM percentage changes
- Z-scores and percentile ranks
- Moving averages
- Trend direction classification
- Economic signal classification
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional
import logging

LOG = logging.getLogger(__name__)


def calculate_yoy_change(series: pd.Series, periods: int = 12) -> pd.Series:
    """
    Calculate year-over-year percentage change.
    
    Args:
        series: Time series data (must have DatetimeIndex)
        periods: Number of periods for YoY (default 12 for monthly data)
    
    Returns:
        Series of YoY % changes
    """
    return ((series / series.shift(periods)) - 1) * 100


def calculate_mom_change(series: pd.Series) -> pd.Series:
    """
    Calculate month-over-month percentage change.
    
    Args:
        series: Time series data
    
    Returns:
        Series of MoM % changes
    """
    return series.pct_change() * 100


def calculate_qoq_change(series: pd.Series, annualized: bool = True) -> pd.Series:
    """
    Calculate quarter-over-quarter percentage change.
    
    Args:
        series: Time series data (quarterly frequency)
        annualized: If True, annualize the quarterly rate
    
    Returns:
        Series of QoQ % changes
    """
    qoq = series.pct_change() * 100
    if annualized:
        # Annualize: (1 + r)^4 - 1, approximated as r * 4 for small r
        qoq = qoq * 4
    return qoq


def calculate_zscore(
    series: pd.Series, 
    window: int = 120,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling z-score (standardized values).
    
    Args:
        series: Time series data
        window: Rolling window size in periods (default 120 months = 10 years)
        min_periods: Minimum observations required (default: window // 2)
    
    Returns:
        Series of z-scores
    """
    if min_periods is None:
        min_periods = window // 2
    
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    
    # Avoid division by zero
    zscore = (series - rolling_mean) / rolling_std.replace(0, np.nan)
    
    return zscore


def calculate_percentile_rank(
    series: pd.Series,
    window: int = 120,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling percentile rank (0-100).
    
    Args:
        series: Time series data
        window: Rolling window size in periods
        min_periods: Minimum observations required
    
    Returns:
        Series of percentile ranks (0-100)
    """
    if min_periods is None:
        min_periods = window // 2
    
    def percentile_rank(x):
        """Calculate percentile rank of last value in window"""
        if len(x) < min_periods:
            return np.nan
        return (x < x.iloc[-1]).sum() / len(x) * 100
    
    return series.rolling(window=window, min_periods=min_periods).apply(
        percentile_rank, raw=False
    )


def calculate_moving_average(
    series: pd.Series,
    window: int = 3,
    min_periods: int = 1
) -> pd.Series:
    """
    Calculate simple moving average.
    
    Args:
        series: Time series data
        window: Window size (default 3)
        min_periods: Minimum observations required
    
    Returns:
        Series of moving average values
    """
    return series.rolling(window=window, min_periods=min_periods).mean()


def determine_trend_direction(
    series: pd.Series,
    lookback: int = 3
) -> str:
    """
    Determine trend direction based on recent values.
    
    Args:
        series: Time series data
        lookback: Number of periods to analyze
    
    Returns:
        "up", "down", or "flat"
    """
    if len(series) < lookback + 1:
        return "flat"
    
    recent = series.iloc[-lookback:]
    
    # Remove NaN values
    recent = recent.dropna()
    
    if len(recent) < 2:
        return "flat"
    
    # Calculate trend: positive slope = up, negative = down
    slope = np.polyfit(range(len(recent)), recent.values, 1)[0]
    
    # Use threshold of 1% of mean value to avoid noise
    threshold = abs(recent.mean()) * 0.01
    
    if slope > threshold:
        return "up"
    elif slope < -threshold:
        return "down"
    else:
        return "flat"


def classify_signal(
    value: float,
    threshold_expansion: float = 0.5,
    threshold_recession: float = -0.5
) -> str:
    """
    Classify economic signal based on value thresholds.
    
    Args:
        value: Current value (typically z-score or growth rate)
        threshold_expansion: Threshold for expansion signal
        threshold_recession: Threshold for recession signal
    
    Returns:
        "expansion", "slowdown", or "recession"
    """
    if pd.isna(value):
        return "unknown"
    
    if value >= threshold_expansion:
        return "expansion"
    elif value <= threshold_recession:
        return "recession"
    else:
        return "slowdown"


def align_to_monthly(
    df: pd.DataFrame,
    date_col: str = 'date',
    value_col: str = 'value',
    freq: Literal['daily', 'weekly', 'monthly', 'quarterly'] = 'monthly',
    method: Literal['last', 'forward_fill'] = 'last'
) -> pd.DataFrame:
    """
    Align time series to monthly frequency.
    
    Args:
        df: DataFrame with date and value columns
        date_col: Name of date column
        value_col: Name of value column
        freq: Original frequency of the data
        method: Alignment method ('last' for end-of-month, 'forward_fill' for quarterly)
    
    Returns:
        DataFrame aligned to monthly frequency
    """
    # Ensure date column is datetime
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)
    
    # Set date as index
    df = df.set_index(date_col)
    
    if freq == 'daily' or freq == 'weekly':
        # Resample to monthly, taking last value of month
        monthly = df.resample('M').last()
    elif freq == 'quarterly':
        if method == 'forward_fill':
            # Forward fill quarterly values across 3 months
            monthly = df.resample('M').ffill()
        else:
            # Keep quarterly values only at quarter-end months
            quarterly_months = df.index.month.isin([3, 6, 9, 12])
            monthly = df[quarterly_months].resample('M').last()
    else:
        # Already monthly
        monthly = df.resample('M').last()
    
    return monthly.reset_index()


def handle_missing_data(
    series: pd.Series,
    method: Literal['drop', 'ffill', 'interpolate'] = 'ffill',
    limit: int = 3
) -> pd.Series:
    """
    Handle missing data in time series.
    
    Args:
        series: Time series with potential NaN values
        method: Method to handle missing data
        limit: Maximum number of consecutive NaN to fill
    
    Returns:
        Series with missing data handled
    """
    if method == 'drop':
        return series.dropna()
    elif method == 'ffill':
        return series.fillna(method='ffill', limit=limit)
    elif method == 'interpolate':
        return series.interpolate(method='linear', limit=limit)
    else:
        return series


def calculate_all_metrics(
    series: pd.Series,
    series_name: str,
    freq: Literal['daily', 'weekly', 'monthly', 'quarterly'] = 'monthly'
) -> pd.DataFrame:
    """
    Calculate all standard metrics for a series.
    
    Args:
        series: Time series data (with DatetimeIndex)
        series_name: Name for the series (used in column names)
        freq: Frequency of the data
    
    Returns:
        DataFrame with original series and all calculated metrics
    """
    df = pd.DataFrame({series_name: series})
    
    # YoY change
    if freq == 'quarterly':
        df[f'{series_name}_yoy'] = calculate_yoy_change(series, periods=4)
    else:
        df[f'{series_name}_yoy'] = calculate_yoy_change(series, periods=12)
    
    # MoM or QoQ change
    if freq == 'quarterly':
        df[f'{series_name}_qoq'] = calculate_qoq_change(series, annualized=True)
    else:
        df[f'{series_name}_mom'] = calculate_mom_change(series)
    
    # Z-score
    df[f'{series_name}_zscore'] = calculate_zscore(series, window=120)
    
    # Percentile rank
    df[f'{series_name}_pct'] = calculate_percentile_rank(series, window=120)
    
    # 3-month moving average
    df[f'{series_name}_ma3'] = calculate_moving_average(series, window=3)
    
    return df


if __name__ == '__main__':
    # Example usage and testing
    import matplotlib.pyplot as plt
    
    # Create sample data
    dates = pd.date_range('2010-01-01', '2025-01-01', freq='M')
    np.random.seed(42)
    values = 100 + np.cumsum(np.random.randn(len(dates)) * 2)
    series = pd.Series(values, index=dates, name='test_series')
    
    # Calculate metrics
    metrics = calculate_all_metrics(series, 'test', freq='monthly')
    
    print("Metrics calculated:")
    print(metrics.tail(12))
    
    print(f"\nLatest trend direction: {determine_trend_direction(series)}")
    print(f"Latest signal: {classify_signal(metrics['test_zscore'].iloc[-1])}")
