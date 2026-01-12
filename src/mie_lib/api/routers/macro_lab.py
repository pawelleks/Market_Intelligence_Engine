from fastapi import APIRouter, HTTPException, Body
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.mie_lib.utils.paths import RAW_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("macro_lab_api")

# --- Global In-Memory Cache ---
# Stores the PRE-CALCULATED Z-SCORES of all components
# Structure: pd.DataFrame with datetime index and columns like 'z_spread_10y2y', 'z_permit', etc.
DATA_CACHE: Dict[str, Any] = {
    "z_scores": None,
    "raw": None
}

class CalculationRequest(BaseModel):
    index_type: str = "LEI" # LEI, COI, LAG
    weights: Dict[str, float] # e.g. {"z_spread_10y2y": 0.3, "z_permit": 0.2}

def rolling_z_score(series, window_years=10, min_periods=24):
    """Calculate rolling Z-score with expanding window fallback."""
    window = window_years * 12
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    return (series - rolling_mean) / rolling_std

@router.on_event("startup")
async def load_macro_lab_data():
    """
    Pre-load and pre-process all Macro Lab components into memory.
    This ensures sub-millisecond access for the interactive sandbox.
    """
    LOG.info("Loading Macro Lab Sandbox Data...")
    
    # 1. Define Series Map (Source ID -> Internal Name)
    series_map = {
        # LEI Components
        'DGS10': 'yield_10y',
        'DGS2': 'yield_2y',
        'TB3MS': 'yield_3m',
        'PERMIT': 'permit',
        'DGORDER': 'orders',
        'AWHMAN': 'hours',
        'ICSA': 'claims',
        'UMCSENT': 'sentiment_curr',
        'UMCSENT1': 'sentiment_hist',
        
        # COI Components (Industrial Production, Payrolls, Income, Sales, GDP)
        'INDPRO': 'indpro',
        'PAYEMS': 'payrolls',
        'W875RX1': 'income', # Real Personal Income ex Transfer
        'RSXFS': 'sales',    # Retail Sales ex Food
        'GDPC1': 'gdp',      # Real GDP (Quarterly)
        
        # Lagging Components (CPI, Unemployment, Labor Const, Rates, Credit)
        # 'CUSR0000SAS4': 'cpi_services', # Need to verify if we have this
        'UNRATE': 'unrate',
        # 'ULCNFB': 'labor_cost', # Need verify
        # 'BUSLOANS': 'credit'    # Need verify
    }

    # 2. Load Raw Parquet Files
    dfs = []
    # Set RAW_DIR based on project structure relative to this file or import
    # Assuming standard project structure: data/raw/macro/fred
    
    # Verify Raw Dir
    fred_dir = RAW_DATA_DIR / "macro" / "fred"
    
    for sid, name in series_map.items():
        p = fred_dir / f"{sid}.parquet"
        if p.exists():
            try:
                df = pd.read_parquet(p)
                df.set_index('date', inplace=True)
                # Resample to Monthly Start (MS)
                df = df.resample('MS').last().rename(columns={'value': name})
                dfs.append(df)
            except Exception as e:
                LOG.error(f"Failed to load {sid}: {e}")
        else:
            LOG.warning(f"Macro Lab: Missing raw series {sid}")

    if not dfs:
        LOG.error("Macro Lab: No data loaded.")
        return

    # 3. Merge into Single DataFrame
    data = dfs[0]
    for df in dfs[1:]:
        data = data.join(df, how='outer')
    
    data = data.sort_index().ffill()
    data = data[data.index >= '1960-01-01']

    # 4. Transformations (Replicating Production Logic)
    
    # --- LEI ---
    # Yield Spreads
    if 'yield_10y' in data.columns and 'yield_2y' in data.columns:
        data['spread_10y2y'] = data['yield_10y'] - data['yield_2y']
    if 'yield_10y' in data.columns and 'yield_3m' in data.columns:
        data['spread_10y3m'] = data['yield_10y'] - data['yield_3m']
        
    # Sentiment Splice
    if 'sentiment_curr' in data.columns and 'sentiment_hist' in data.columns:
        data['sentiment'] = data['sentiment_curr'].combine_first(data['sentiment_hist'])
    elif 'sentiment_curr' in data.columns:
        data['sentiment'] = data['sentiment_curr']

    # YoY Transformations
    for col in ['permit', 'orders', 'hours', 'indpro', 'payrolls', 'income', 'sales', 'gdp']:
        if col in data.columns:
            data[f'{col}_yoy'] = data[col].pct_change(periods=12)

    # Inverted Claims
    if 'claims' in data.columns:
        data['claims_inv'] = data['claims'] * -1
        data['claims_yoy'] = data['claims_inv'].pct_change(periods=12)

    if 'sentiment' in data.columns:
        data['sentiment_yoy'] = data['sentiment'].pct_change(periods=12)
        
    if 'unrate' in data.columns:
        # Unemployment usually inverted for momentum (Lower is better)
        # But Lagging indicator logic might be different. 
        # For Sandbox, let's provide standard YoY of Inverted? Or just Level?
        # Typically UnRate is used as Level or YoY.
        # Let's just do Level and YoY (Inverted)
        data['unrate_inv'] = data['unrate'] * -1
        data['unrate_yoy'] = data['unrate_inv'].pct_change(periods=12)

    # 5. Normalization (Z-Scores)
    # Define the "Menu" of available Z-scores for the Lab
    z_map = {
        'spread_10y2y': 'z_spread_10y2y',
        'spread_10y3m': 'z_spread_10y3m',
        'permit_yoy':   'z_permit',
        'orders_yoy':   'z_orders',
        'hours_yoy':    'z_hours',
        'claims_yoy':   'z_claims',
        'sentiment_yoy':'z_sentiment',
        
        # COI
        'indpro_yoy':   'z_indpro',
        'payrolls_yoy': 'z_payrolls',
        'income_yoy':   'z_income',
        'sales_yoy':    'z_sales',
        'gdp_yoy':      'z_gdp',
        
        # Lagging
        'unrate_yoy':   'z_unrate'
    }

    # Calculate Z-Scores
    for col, z_col in z_map.items():
        if col in data.columns:
            data[z_col] = rolling_z_score(data[col], window_years=10, min_periods=24)

    # Store in Cache (Only keep the z_cols and date index)
    z_cols = [c for c in z_map.values() if c in data.columns]
    DATA_CACHE['z_scores'] = data[z_cols].copy()
    
    LOG.info(f"Macro Lab Data Loaded. {len(z_cols)} Z-Score components ready.")


@router.post("/api/macro/lab/calculate")
async def calculate_custom_index(req: CalculationRequest):
    """
    Calculate an index on-the-fly based on user weights.
    Efficiently handles jagged starts (ragged weights).
    """
    if DATA_CACHE['z_scores'] is None:
        raise HTTPException(status_code=503, detail="Macro Lab data not loaded yet.")
    
    df = DATA_CACHE['z_scores'].copy()
    
    # Validate requested columns exist
    valid_weights = {k: v for k, v in req.weights.items() if k in df.columns}
    
    if not valid_weights:
        return {"error": "No valid components found in request", "data": []}

    # --- Ragged Weighting Logic (Optimized) ---
    # Vectorization is tough with dynamic NaNs per column.
    # We'll use apply(), which is fast enough for <1000 rows.
    
    def calc_row(row):
        val_sum = 0.0
        weight_sum = 0.0
        
        for col, w in valid_weights.items():
            val = row[col]
            if pd.notnull(val): # Check NaN
                val_sum += val * w
                weight_sum += w
        
        if weight_sum == 0:
            return None
        
        # Re-normalize to 100% of available weights
        # Formula: (Sum of Weighted Values) / (Sum of Active Weights)
        # e.g. If 20% weight is missing, we divide by 0.80, effectively boosting others.
        return val_sum / weight_sum

    # 1. Calc Raw Composite
    df['composite_raw'] = df.apply(calc_row, axis=1)
    
    # 2. Amplitude Fix (Z-Score the Composite)
    # Re-using the rolling function logic
    df['final_index'] = rolling_z_score(df['composite_raw'], window_years=10, min_periods=24)
    
    # 3. Scalar (2.0x match production)
    df['final_index'] = df['final_index'] * 2.0
    
    # 4. Filter and Format
    # Drop leading NaNs
    df = df.dropna(subset=['final_index'])
    
    # Format for chart (List of dicts)
    output = []
    for date, row in df.iterrows():
        output.append({
            "date": date.strftime('%Y-%m-%d'),
            "value": row['final_index'] if pd.notnull(row['final_index']) else None
        })
        
    return {"data": output}
