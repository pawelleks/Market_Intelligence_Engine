#!/usr/bin/env python3
"""
Update Economy Data (Enhanced Version)

Strict implementation of the 3-factor LEI (Housing, Labor, Financials) and 2-factor COI.

LEI Components:
- HOUST (Housing Starts)
- AWHMAN (Mfg Labor Hours)
- NFCI (Financial Conditions) - Inverted

COI Components:
- INDPRO (Industrial Production)
- PAYEMS (Nonfarm Payrolls)

Methodology:
1. Resample to Month-End.
2. Calculate YoY growth for all except NFCI (which is inverted).
3. Standardize (Z-Score) with 120-month rolling window (min 60).
4. Aggregate LEI (Weighted Sum -> Smooth 9m -> Z-Score 180m).
5. Aggregate COI (Weighted Sum -> Smooth 12m -> Z-Score 120m).
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mie_lib.utils.paths import RAW_DATA_DIR, DATA_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"
MACRO_RAW_DIR = RAW_DATA_DIR / "macro" / "fred"

def load_and_resample(series_id: str) -> pd.Series:
    """Load FRED series and resample to Month-End."""
    file_path = MACRO_RAW_DIR / f"{series_id}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Series {series_id} not found at {file_path}")
    
    df = pd.read_parquet(file_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    
    # Resample to Month-End
    series = df['value'].resample('ME').last()
    return series

def calculate_z_score(series: pd.Series, window: int = 120, min_periods: int = 60) -> pd.Series:
    """Calculate Rolling Z-Score."""
    roll_mean = series.rolling(window=window, min_periods=min_periods).mean()
    roll_std = series.rolling(window=window, min_periods=min_periods).std()
    return (series - roll_mean) / roll_std

def run_enhanced_update():
    LOG.info("Starting Enhanced Economy Data Update...")
    MACRO_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Data Fetching & Resampling
    try:
        s_houst = load_and_resample("HOUST")
        s_awhman = load_and_resample("AWHMAN")
        s_nfci = load_and_resample("NFCI")
        s_indpro = load_and_resample("INDPRO")
        s_payems = load_and_resample("PAYEMS")
    except Exception as e:
        LOG.error(f"Failed to load data: {e}")
        raise

    # Align dates (intersection)
    # Actually, pandas operations align on index automatically, but good to be aware.
    
    # 2. Transformations (Step A)
    # Houst_YoY = HOUST / HOUST.shift(12) - 1
    houst_yoy = s_houst / s_houst.shift(12) - 1
    
    # Hours_YoY = AWHMAN / AWHMAN.shift(12) - 1
    hours_yoy = s_awhman / s_awhman.shift(12) - 1
    
    # NFCI_Inv = NFCI * (-1)
    nfci_inv = s_nfci * -1.0
    
    # IndPro_YoY = INDPRO / INDPRO.shift(12) - 1
    indpro_yoy = s_indpro / s_indpro.shift(12) - 1
    
    # Payems_YoY = PAYEMS / PAYEMS.shift(12) - 1
    payems_yoy = s_payems / s_payems.shift(12) - 1

    # 3. Component Standardization (Step B)
    # Z-Score to ALL transformed series above. Window: 120 Months (min_periods=60).
    z_houst = calculate_z_score(houst_yoy, window=120, min_periods=60)
    z_hours = calculate_z_score(hours_yoy, window=120, min_periods=60)
    z_nfci = calculate_z_score(nfci_inv, window=120, min_periods=60)
    
    z_indpro = calculate_z_score(indpro_yoy, window=120, min_periods=60)
    z_payems = calculate_z_score(payems_yoy, window=120, min_periods=60)

    # 4. LEI Aggregation & Finalizing (Step C)
    # LEI_Raw = (0.333 * Z_houst) + (0.333 * Z_hours) + (0.334 * Z_nfci)
    lei_raw = (0.333 * z_houst) + (0.333 * z_hours) + (0.334 * z_nfci)
    
    # LEI_Smooth = Rolling Mean of LEI_Raw (Window 9)
    lei_smooth = lei_raw.rolling(window=9).mean()
    
    # LEI_Final = Z-Score of LEI_Smooth (Window 180)
    lei_final = calculate_z_score(lei_smooth, window=180, min_periods=60) # Assuming standard min_periods for robustness

    # 5. COI Aggregation & Finalizing (Step D)
    # COI_Raw = (0.50 * Z_indpro) + (0.50 * Z_payems)
    coi_raw = (0.50 * z_indpro) + (0.50 * z_payems)
    
    # COI_Smooth = Rolling Mean of COI_Raw (Window 12)
    coi_smooth = coi_raw.rolling(window=12).mean()
    
    # COI_Final = Z-Score of COI_Smooth (Window 120)
    coi_final = calculate_z_score(coi_smooth, window=120, min_periods=60)

    # Calculate 17-month SMA for LEI (and COI for consistency)
    lei_sma_17 = lei_final.rolling(window=17).mean()
    coi_sma_17 = coi_final.rolling(window=17).mean()

    # 6. Output (Step 3)
    # Save to processed_lei_coi_enhanced.parquet.
    
    output_df = pd.DataFrame({
        'LEI_Final': lei_final,
        'COI_Final': coi_final,
        'LEI_SMA_17': lei_sma_17,
        'COI_SMA_17': coi_sma_17,
        # Components (LEI)
        'Z_HOUST': z_houst,
        'Z_AWHMAN': z_hours,
        'Z_NFCI': z_nfci,
        # Components (COI)
        'Z_INDPRO': z_indpro,
        'Z_PAYEMS': z_payems
    })
    
    
    # Three-tier signal system based on user's backtest thresholds
    # CLEAR: > 0.4, WARNING: -0.4 to 0.4, TROUBLE: < -0.4
    output_df['LEI_Status'] = pd.cut(
        output_df['LEI_Final'],
        bins=[-np.inf, -0.4, 0.4, np.inf],
        labels=['TROUBLE', 'WARNING', 'CLEAR']
    )
    
    # Binary flag for backward compatibility (trouble state)
    output_df['Recession_Signal_Active'] = output_df['LEI_Final'] < -0.4
    
    # Add COI three-tier signal
    output_df['COI_Status'] = pd.cut(
        output_df['COI_Final'],
        bins=[-np.inf, -0.4, 0.4, np.inf],
        labels=['TROUBLE', 'WARNING', 'CLEAR']
    )
    
    output_df['COI_Signal_Active'] = output_df['COI_Final'] < -0.4
     
    
    output_df = output_df.reset_index() # make date a column
    
    output_file = MACRO_ANALYSIS_DIR / "processed_lei_coi_enhanced.parquet"
    output_df.to_parquet(output_file, index=False)
    
    LOG.info(f"Enhanced Economy Data saved to {output_file}")
    LOG.info(f"Shape: {output_df.shape}")
    LOG.info(f"Last Row:\n{output_df.iloc[-1]}")

if __name__ == "__main__":
    run_enhanced_update()
