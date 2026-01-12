"""
API endpoint for Business Cycle data.
"""
from fastapi import APIRouter
from pathlib import Path
import pandas as pd

router = APIRouter()

# Paths
DATA_DIR = Path(__file__).parents[4] / "data"
MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"

from src.mie_lib.utils.paths import FRED_DATA_DIR

def get_recession_periods():
    """Load and process USREC data into recession periods."""
    usrec_path = FRED_DATA_DIR / "USREC.parquet"
    if not usrec_path.exists():
        return []
    
    try:
        df = pd.read_parquet(usrec_path)
        df = df.sort_values('date').reset_index(drop=True)
        df['recession'] = df['value'].fillna(0).astype(int)
        df['recession_start'] = (df['recession'] == 1) & (df['recession'].shift(1) != 1)
        df['recession_end'] = (df['recession'] == 1) & (df['recession'].shift(-1) != 1)
        
        recessions = []
        start_rows = df[df['recession_start']]
        end_rows = df[df['recession_end']]
        
        for i, (_, start_row) in enumerate(start_rows.iterrows()):
            if i < len(end_rows):
                end_row = end_rows.iloc[i]
                recessions.append({
                    "start": pd.to_datetime(start_row['date']).strftime('%Y-%m-%d'),
                    "end": pd.to_datetime(end_row['date']).strftime('%Y-%m-%d')
                })
        return recessions
    except Exception as e:
        # Log error in production
        print(f"Error loading recession data: {e}")
        return []

@router.get("/business-cycle")
async def get_business_cycle():
    """Get business cycle phase and indicator data."""
    file_path = MACRO_ANALYSIS_DIR / "processed_business_cycle.parquet"
    
    if not file_path.exists():
        return {
            "error": "Business cycle data not found. Please run the Economic Pipeline.",
            "data": [],
            "latest": None
        }
    
    df = pd.read_parquet(file_path)
    
    # Ensure date column
    if 'date' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        if 'index' in df.columns:
            df = df.rename(columns={'index': 'date'})
    
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Get latest row
    latest_row = df.iloc[-1]
    latest = {
        "date": latest_row['date'].strftime('%Y-%m-%d'),
        "cycle_phase": latest_row.get('Cycle_Phase', 'Unknown'),
        "lei_final": float(latest_row.get('LEI_Final', 0)),
        "coi_final": float(latest_row.get('COI_Final', 0)),
        "lag_composite": float(latest_row.get('LAG_Final', 0)),
        "recession_prob": float(latest_row.get('Recession_Prob', 0))
    }
    
    # Load recession data
    recessions = get_recession_periods()
    
    # Format data for frontend
    data = []
    for _, row in df.iterrows():
        data.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "cycle_phase": row.get('Cycle_Phase', 'Unknown'),
            "lei_final": float(row.get('LEI_Final', 0)),
            "coi_final": float(row.get('COI_Final', 0)),
            "lag_composite": float(row.get('LAG_Final', 0)),
            "recession_prob": float(row.get('Recession_Prob', 0))
        })
    
    return {
        "data": data,
        "latest": latest,
        "recessions": recessions
    }
