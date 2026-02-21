"""
JPM Economic Dashboard - Aggregation Script

Combines individual FRED parquet files into 10 indicator-specific aggregated datasets.
Each aggregated file includes:
- All relevant series for that indicator
- Calculated metrics (YoY, MoM, z-scores, percentiles)
- Recession period overlay
- Metadata (last_updated timestamp)

Output: data/processed/jpm_dashboard/{indicator}.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

from mie_lib.utils.paths import RAW_DATA_DIR, PROCESSED_DATA_DIR, FRED_DATA_DIR
from mie_lib.analytics.jpm_dashboard.metrics import (
    calculate_all_metrics,
    align_to_monthly,
    handle_missing_data
)

LOG = logging.getLogger(__name__)


# Indicator series mapping
INDICATOR_SERIES = {
    'gdp': {
        'primary': ['GDPC1'],
        'secondary': ['GDP', 'A939RX0Q048SBEA', 'PCEC96'],
        'components': ['PCE', 'GPDI', 'GCE'],
        'freq': 'quarterly'
    },
    'consumer_spending': {
        'primary': ['PCE', 'PCEC96'],
        'secondary': ['RSAFS', 'RSXFS', 'TOTALSL', 'PSAVERT'],
        'components': ['DGDSRG3Q086SBEA', 'DSERRG3Q086SBEA'],
        'freq': 'monthly'
    },
    'labor_market': {
        'primary': ['UNRATE'],
        'secondary': ['U6RATE', 'ICSA', 'CCSA', 'PAYEMS'],
        'components': ['JTSJOL', 'JTSQUR', 'JTSLDL', 'CIVPART', 'AWHMAN'],
        'freq': 'monthly'
    },
    'interest_rates': {
        'primary': ['FEDFUNDS'],
        'secondary': ['DGS30', 'DGS10', 'DGS5', 'DGS2', 'DGS6MO', 'DGS3MO', 'DGS1MO', 'MORTGAGE30US'],
        'components': ['T10Y2Y', 'T10Y3M', 'AAA', 'BAA', 'TB3MS'],
        'freq': 'daily'
    },
    'inflation': {
        'primary': ['CPIAUCSL'],
        'secondary': ['CPILFESL', 'PCEPI', 'PCEPILFE'],
        'components': ['CPIFABSL', 'CUSR0000SAH', 'CPIENGSL', 'CUSR0000SASLE', 'CUSR0000SAC'],
        'freq': 'monthly'
    },
    'business_confidence': {
        'primary': ['BSCICP02USM460S'],
        'secondary': ['CFNAI', 'GACDISA066MSFRBNY'],
        'components': ['BUSLOANS', 'BAMLC0A4CBBB'],
        'freq': 'monthly'
    },
    'stock_market': {
        'primary': ['SP500'],
        'secondary': [],  # Will add VIX from yfinance data
        'components': [],
        'freq': 'daily'
    },
    'trade_balance': {
        'primary': ['BOPGSTB'],
        'secondary': ['EXPGS', 'IMPGS', 'NETFI'],
        'components': ['DTWEXBGS'],
        'freq': 'monthly'
    },
    'housing': {
        'primary': ['HOUST'],
        'secondary': ['EXHOSLUSM495S', 'HSN1F', 'CSUSHPINSA', 'CSUSHPISA'],
        'components': ['PERMIT', 'MSACSR', 'MORTGAGE30US'],
        'freq': 'monthly'
    },
    'policy': {
        'primary': ['FEDFUNDS'],
        'secondary': ['WALCL', 'TREAST', 'WSHOMCB', 'DGS10', 'T10Y2Y', 'MORTGAGE30US'],
        'components': ['DFEDTARU', 'FYFSD', 'GFDEGDQ188S'],
        'freq': 'daily'  # Changed to daily to capture DGS10, T10Y2Y properly
    }
}


def load_fred_series(series_id: str) -> Optional[pd.DataFrame]:
    """
    Load a FRED series from parquet file.
    
    Args:
        series_id: FRED series ID
    
    Returns:
        DataFrame with 'date' and 'value' columns, or None if not found
    """
    file_path = FRED_DATA_DIR / f"{series_id}.parquet"
    
    if not file_path.exists():
        LOG.warning(f"FRED series {series_id} not found at {file_path}")
        return None
    
    try:
        df = pd.read_parquet(file_path)
        
        # Ensure consistent column names
        if 'date' not in df.columns and df.index.name == 'date':
            df = df.reset_index()
        
        # Ensure date column is datetime
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    except Exception as e:
        LOG.error(f"Error loading {series_id}: {e}")
        return None


def load_stock_market_data() -> Optional[pd.DataFrame]:
    """
    Load S&P 500 and VIX data from yfinance parquet files.
    
    Returns:
        DataFrame with date, close, and vix columns
    """
    try:
        # Load SPY
        spy_path = RAW_DATA_DIR / "SPY.parquet"
        vix_path = RAW_DATA_DIR / "^VIX.parquet"
        
        stock_data = {}
        
        if spy_path.exists():
            spy_df = pd.read_parquet(spy_path)
            # Handle case sensitivity
            date_col = 'date' if 'date' in spy_df.columns else 'Date'
            close_col = 'close' if 'close' in spy_df.columns else 'Close'
            
            if date_col in spy_df.columns:
                spy_df['date'] = pd.to_datetime(spy_df[date_col])
            else:
                spy_df['date'] = pd.to_datetime(spy_df.index)
                
            stock_data['sp500'] = spy_df.set_index('date')[close_col]
        
        if vix_path.exists():
            vix_df = pd.read_parquet(vix_path)
            # Handle case sensitivity
            date_col = 'date' if 'date' in vix_df.columns else 'Date'
            close_col = 'close' if 'close' in vix_df.columns else 'Close'
            
            if date_col in vix_df.columns:
                vix_df['date'] = pd.to_datetime(vix_df[date_col])
            else:
                vix_df['date'] = pd.to_datetime(vix_df.index)
                
            stock_data['vix'] = vix_df.set_index('date')[close_col]
        
        if stock_data:
            df = pd.DataFrame(stock_data).reset_index()
            return df
        
        return None
    except Exception as e:
        LOG.error(f"Error loading stock market data: {e}")
        return None


def load_recession_periods() -> pd.DataFrame:
    """
    Load USREC recession indicator.
    
    Returns:
        DataFrame with date and recession columns
    """
    usrec_df = load_fred_series('USREC')
    
    if usrec_df is None:
        LOG.warning("USREC data not found, recession overlay will be disabled")
        return pd.DataFrame(columns=['date', 'recession'])
    
    usrec_df['recession'] = usrec_df['value'].fillna(0).astype(int)
    return usrec_df[['date', 'recession']]


def aggregate_indicator(
    indicator_name: str,
    series_config: Dict,
    output_dir: Path
) -> bool:
    """
    Aggregate all series for a single indicator into one parquet file.
    
    Args:
        indicator_name: Name of the indicator (e.g., 'gdp', 'inflation')
        series_config: Configuration dict with series IDs and frequency
        output_dir: Directory to save aggregated file
    
    Returns:
        True if successful, False otherwise
    """
    LOG.info(f"Aggregating indicator: {indicator_name}")
    
    # Collect all series IDs
    all_series = (
        series_config.get('primary', []) +
        series_config.get('secondary', []) +
        series_config.get('components', [])
    )
    
    if not all_series:
        LOG.warning(f"No series defined for {indicator_name}")
        return False
    
    # Special handling for stock market
    if indicator_name == 'stock_market':
        combined_df = load_stock_market_data()
        if combined_df is None:
            return False
        
        # Calculate metrics for each series
        combined_df['date'] = pd.to_datetime(combined_df['date'])
        combined_df = combined_df.set_index('date')
        
        result_df = pd.DataFrame(index=combined_df.index)
        
        for col in combined_df.columns:
            metrics = calculate_all_metrics(
                combined_df[col],
                col,
                freq='daily'
            )
            result_df = pd.concat([result_df, metrics], axis=1)
        
        result_df = result_df.reset_index()
    else:
        # Load all series
        series_data = {}
        for series_id in all_series:
            df = load_fred_series(series_id)
            if df is not None:
                series_data[series_id] = df
        
        if not series_data:
            LOG.error(f"No data loaded for {indicator_name}")
            return False
        
        # Align all series to monthly frequency
        freq = series_config.get('freq', 'monthly')
        aligned_series = {}
        
        for series_id, df in series_data.items():
            # Set date as index
            df = df.set_index('date')
            
            # Resample based on frequency
            if freq == 'quarterly':
                # Forward fill quarterly to monthly
                monthly = df.resample('M').ffill()
            elif freq == 'daily':
                # Take end-of-month values
                monthly = df.resample('M').last()
            else:
                # Already monthly
                monthly = df.resample('M').last()
            
            aligned_series[series_id] = monthly['value']
        
        # Combine all series into single DataFrame
        combined_df = pd.DataFrame(aligned_series)
        
        # Special calculation for Interest Rate Spreads if missing
        if indicator_name == 'interest_rates':
            # 5Y-30Y Spread (30Y - 5Y)
            if 'DGS30' in combined_df.columns and 'DGS5' in combined_df.columns:
                combined_df['SPREAD30Y5Y'] = combined_df['DGS30'] - combined_df['DGS5']
        
        # Calculate metrics for each series
        result_df = pd.DataFrame(index=combined_df.index)
        
        for series_id in combined_df.columns:
            metrics = calculate_all_metrics(
                combined_df[series_id],
                series_id,
                freq='monthly' if freq != 'quarterly' else 'quarterly'
            )
            result_df = pd.concat([result_df, metrics], axis=1)
        
        result_df = result_df.reset_index()
        result_df.rename(columns={'index': 'date'}, inplace=True)
    
    # Add recession periods
    usrec_df = load_recession_periods()
    if not usrec_df.empty:
        # Align recession to monthly
        usrec_df['date'] = pd.to_datetime(usrec_df['date'])
        usrec_df = usrec_df.set_index('date').resample('M').last().reset_index()
        
        result_df = result_df.merge(usrec_df, on='date', how='left')
        result_df['recession'] = result_df['recession'].fillna(0).astype(int)
    
    # Add metadata
    result_df['last_updated'] = datetime.now()
    
    # Save to parquet
    output_path = output_dir / f"{indicator_name}.parquet"
    result_df.to_parquet(output_path, index=False)
    
    LOG.info(f"Saved {indicator_name} to {output_path} ({len(result_df)} rows, {len(result_df.columns)} columns)")
    
    return True


def aggregate_all_indicators(output_dir: Optional[Path] = None) -> Dict[str, bool]:
    """
    Aggregate all 10 indicators.
    
    Args:
        output_dir: Output directory (default: PROCESSED_DATA_DIR/jpm_dashboard)
    
    Returns:
        Dict mapping indicator names to success status
    """
    if output_dir is None:
        output_dir = PROCESSED_DATA_DIR / "jpm_dashboard"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for indicator_name, series_config in INDICATOR_SERIES.items():
        try:
            success = aggregate_indicator(indicator_name, series_config, output_dir)
            results[indicator_name] = success
        except Exception as e:
            LOG.error(f"Failed to aggregate {indicator_name}: {e}")
            results[indicator_name] = False
    
    # Summary
    successful = sum(results.values())
    total = len(results)
    
    LOG.info(f"Aggregation complete: {successful}/{total} indicators successful")
    
    if successful < total:
        failed = [k for k, v in results.items() if not v]
        LOG.warning(f"Failed indicators: {', '.join(failed)}")
    
    return results


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run aggregation
    results = aggregate_all_indicators()
    
    # Exit with error code if any failed
    if not all(results.values()):
        exit(1)
    
    exit(0)
