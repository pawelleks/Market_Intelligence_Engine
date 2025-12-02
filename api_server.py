from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

import pandas as pd

# Assume the project root is on the path or FastAPI is run from root.
from mie_lib.utils.paths import markov_matrix_path_flat, markov_out_dir
from mie_lib.analytics.markov.markov_engine import MarkovConfig # Used for default config values

# HMM Imports
from mie_lib.utils.paths import hmm_std_out_dir 
from mie_lib.analytics.hmm.hmm_engine import HMMConfig # Used for HMM configuration defaults

# -----------------------------------------------------------------
# FastAPI Initialization
# -----------------------------------------------------------------

app = FastAPI(
    title="MIE Analytics API",
    description="Serves pre-computed Markov and HMM data as JSON/REST endpoints.",
    version="1.0.0",
)

origins = [
    # Allow the default React development port (Vite, CRA) to access the API
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # We can add more origins here as needed (e.g., Vercel, specific staging URLs)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers (Authorization, Content-Type, etc.)
)


# -----------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------

import numpy as np

def _read_parquet_and_format(path: Path) -> Optional[List[Dict[str, Any]]]:
    """Reads a Parquet file and converts to records for JSON output."""
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        # Ensure dates are JSON serializable
        if "date" in df.columns:
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        
        # Replace NaN with None for JSON compliance
        df = df.replace({np.nan: None})
        
        return df.to_dict(orient="records")
    except Exception as e:
        # In a production app, log the error but return 404/500
        print(f"Error reading {path}: {e}")
        return None


# -----------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------

@app.get("/api/v1/markov/matrix/{ticker}")
def get_markov_matrix(
    ticker: str,
    order: int = MarkovConfig.order,
    state_mode: str = MarkovConfig.state_mode,
    threshold_bps: int = MarkovConfig.threshold_bps,
    window_key: str = "MAX", 
) -> JSONResponse:
    """Retrieves the pre-computed Markov transition matrix (counts and probabilities)."""
    
    ticker = ticker.upper()
    
    # 1. Determine the path using the grid path function
    # This ensures we fetch the specific matrix for the requested configuration
    from mie_lib.utils.paths import markov_matrix_grid_path
    path = markov_matrix_grid_path(ticker, state_mode, threshold_bps, order, window_key)
    
    # 2. Read and format the data
    data = _read_parquet_and_format(path)
    
    if data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Markov Matrix not found for {ticker} (Mode={state_mode}, Thr={threshold_bps}, Order={order}, Win={window_key}). Run the CLI job first."
        )
    
    return JSONResponse(content={
        "ticker": ticker,
        "order": order,
        "state_mode": state_mode,
        "threshold_bps": threshold_bps,
        "window_key": window_key,
        "data": data
    })


@app.get("/api/v1/markov/multistep/{ticker}/{state_mode}")
def get_markov_multistep(
    ticker: str,
    state_mode: str,
    order: int = 1, # Multi-step forecast only works robustly for Order 1
) -> JSONResponse:
    """Retrieves the pre-computed multi-step forecast probabilities."""
    
    ticker = ticker.upper()
    
    # 1. Determine the path to the multi-step file
    path = markov_out_dir(ticker) / f"multi_step_order{order}_{state_mode}.parquet"
    
    # 2. Read and format the data
    data = _read_parquet_and_format(path)
    
    if data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Multi-Step Forecast not found for {ticker} (Order {order}, Mode {state_mode}). Run the CLI job first."
        )
    
    return JSONResponse(content={
        "ticker": ticker,
        "order": order,
        "state_mode": state_mode,
        "data": data
    })


@app.get("/api/v1/hmm/probabilities/{ticker}")
def get_hmm_probabilities(
    ticker: str,
    n_states: int = HMMConfig.n_states,
    window_years: Union[int, str] = HMMConfig.train_window_years,
) -> JSONResponse:
    """Retrieves the pre-computed HMM state probabilities (Bull/Neutral/Bear)."""
    
    ticker = ticker.upper()
    
    # 1. Determine the standardized path 
    out_dir = hmm_std_out_dir(ticker, window_years, n_states)
    path = out_dir / "hmm_probs.parquet"
    
    # 2. Read and format the data
    data = _read_parquet_and_format(path)
    
    if data is None:
        raise HTTPException(
            status_code=404, 
            detail=(
                f"HMM Probabilities not found for {ticker} (States={n_states}, Window={window_years}y). "
                f"Run the CLI job (e.g., build-hmm) first."
            )
        )
    
    return JSONResponse(content={
        "ticker": ticker,
        "n_states": n_states,
        "window_years": window_years,
        "data": data
    })


@app.get("/api/v1/hmm/stats/{ticker}")
def get_hmm_performance_stats(
    ticker: str,
    n_states: int = HMMConfig.n_states,
    window_years: int = HMMConfig.train_window_years,
) -> JSONResponse:
    """Retrieves the pre-computed HMM performance statistics (Sharpe, Annualized Return)."""
    
    ticker = ticker.upper()
    
    # 1. Determine the standardized path for the metadata JSON
    out_dir = hmm_std_out_dir(ticker, window_years, n_states)
    path = out_dir / "hmm_metadata.json"
    
    if not path.exists():
        raise HTTPException(
            status_code=404, 
            detail=(
                f"HMM Metadata not found for {ticker}. Run the CLI job first to generate statistics."
            )
        )
    
    # 2. Read and parse the JSON metadata
    try:
        import json
        with open(path, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to read HMM metadata: {e}"
        )
    
    # 3. Extract and return the performance statistics list
    stats = metadata.get("performance_stats", [])
    durations = metadata.get("expected_durations", None)
    
    if not stats:
        raise HTTPException(
            status_code=404, 
            detail="Performance statistics not found in metadata. Rebuild HMM."
        )

    return JSONResponse(content={
        "ticker": ticker,
        "n_states": n_states,
        "window_years": window_years,
        "data": stats,
        "expected_durations": durations
    })


@app.get("/api/v1/features/price/{ticker}")
def get_price_features(ticker: str) -> JSONResponse:
    """Retrieves the pre-computed price and features data for charting."""
    
    ticker = ticker.upper()
    
    # 1. Load Features (for returns)
    feat_path = Path(f"data/features/{ticker}.parquet")
    df_feat = None
    if feat_path.exists():
        try:
            df_feat = pd.read_parquet(feat_path)
        except Exception as e:
            print(f"Error reading features: {e}")

    # 2. Load Raw (for price)
    raw_path = Path(f"data/raw/{ticker}.parquet")
    df_raw = None
    if raw_path.exists():
        try:
            df_raw = pd.read_parquet(raw_path)
        except Exception as e:
            print(f"Error reading raw data: {e}")
    
    if df_feat is None and df_raw is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Price/Features not found for {ticker}. Run the pipeline jobs."
        )
    
    # 3. Merge
    if df_feat is not None and df_raw is not None:
        # Ensure dates are datetime for merging
        df_feat["date"] = pd.to_datetime(df_feat["date"])
        df_raw["date"] = pd.to_datetime(df_raw["date"])
        
        # We only need price columns from raw to add to features
        # Check which columns exist in raw
        raw_cols = df_raw.columns.tolist()
        cols_to_merge = ["date"]
        if "adj_close" in raw_cols:
            cols_to_merge.append("adj_close")
        if "close" in raw_cols:
            cols_to_merge.append("close")
            
        df_raw_subset = df_raw[cols_to_merge]
        
        # Merge left on features to keep feature rows (which might be a subset or same)
        # Actually, raw might be longer. Let's use outer or just align. 
        # Usually features are derived from raw, so they share dates.
        df = pd.merge(df_feat, df_raw_subset, on="date", how="left")
        
    elif df_raw is not None:
        df = df_raw # Fallback if features missing
    else:
        df = df_feat # Fallback if raw missing (chart will be empty but stats might work)

    # 4. Format
    if "date" in df.columns:
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    
    # Replace NaN with None
    df = df.replace({np.nan: None})
    
    data = df.to_dict(orient="records")
    
    return JSONResponse(content={
        "ticker": ticker,
        "data": data
    })


@app.get("/api/v1/hmm/metrics/{ticker}")
def get_hmm_metrics(
    ticker: str,
    n_states: int = HMMConfig.n_states,
    window_years: Union[int, str] = HMMConfig.train_window_years,
) -> JSONResponse:
    """Retrieves the pre-computed HMM metrics (Transition Matrix, etc.)."""
    
    ticker = ticker.upper()
    
    # 1. Determine the standardized path 
    out_dir = hmm_std_out_dir(ticker, window_years, n_states)
    path = out_dir / "hmm_metrics.parquet"
    
    # 2. Read and format the data
    data = _read_parquet_and_format(path)
    
    if data is None:
        raise HTTPException(
            status_code=404, 
            detail=(
                f"HMM Metrics not found for {ticker} (States={n_states}, Window={window_years}y). "
                f"Run the CLI job (e.g., build-hmm) first."
            )
        )
    
    return JSONResponse(content={
        "ticker": ticker,
        "n_states": n_states,
        "window_years": window_years,
        "data": data
    })