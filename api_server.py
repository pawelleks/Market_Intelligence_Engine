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

# Data Freshness Imports
from mie_lib.utils.trading_calendar import is_up_to_date, coerce_to_date
from mie_lib.utils.paths import features_parquet_path

# Price Viewer Imports
from mie_lib.core.state_classification import classify_tri_state
from mie_lib.analytics.minervini import run_minervini_template
from mie_lib.utils.ticker_service import get_tickers_for_analysis
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

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

def _process_price_data(df_raw: pd.DataFrame, state_mode: str, threshold_bps: int, rows: int) -> List[Dict[str, Any]]:
    """Performs normalization, return calculation, state classification, and styling."""
    
    if df_raw.empty:
        return []

    # 1. Normalization and Returns
    out = df_raw.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out = out.sort_values("date").reset_index(drop=True)
    out["close"] = pd.to_numeric(out["close"], downcast="float")
    out["daily_return_pct"] = (out["close"].pct_change() * 100.0).astype("float32") # Percentage change
    
    out.rename(columns={c: c.lower() for c in out.columns}, inplace=True)
    if "volume" not in out.columns and "Volume" in df_raw.columns:
        out["volume"] = df_raw["Volume"] # Assume Volume is present in raw data
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce", downcast="integer")
    out["volume"].fillna(0, inplace=True) # Fill missing volume with 0

    out = out.dropna(subset=["daily_return_pct"]).reset_index(drop=True)

    # 2. Classification
    threshold = float(threshold_bps) / 10000.0 # Convert bps to decimal (e.g., 10 bps -> 0.001)

    def classify_state_wrapper(ret_pct: float):
        ret_val = ret_pct / 100.0 # Convert back to decimal for classification logic
        if pd.isna(ret_val): return ""
        
        # Use existing core classification logic
        state_raw = classify_tri_state(ret_val, threshold_bps) 
        
        if state_mode == "binary":
            # NEW LOGIC: Map Neutral to Green in Binary Mode.
            return "Red" if state_raw == "Red" else ("Green" if state_raw in {"Green", "Neutral"} else "")
        return state_raw
        
    out["State"] = out["daily_return_pct"].apply(classify_state_wrapper)

    # 3. Final Formatting and Selection
    out = out.sort_values("date", ascending=False).head(rows).reset_index(drop=True)
    
    # Format the required columns for display
    out["Date"] = out["date"].dt.strftime("%Y-%m-%d")
    out["Daily Change (%)"] = out["daily_return_pct"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "")
    out.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
    
    final_cols = ["Date", "Open", "High", "Low", "Close", "Volume", "Daily Change (%)", "State"]
    return out[final_cols].to_dict(orient="records")


# -----------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------

@app.get("/api/v1/data/freshness/{ticker}")
def get_data_freshness_status(ticker: str) -> JSONResponse:
    """Checks the freshness of the primary features parquet file."""
    
    ticker = ticker.upper()
    path = features_parquet_path(ticker)
    
    if not path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Features data not found for {ticker}."
        )
        
    try:
        # Load features file and get the latest date
        df = pd.read_parquet(path, columns=['date'])
        last_date_raw = df['date'].max()
        last_date = coerce_to_date(last_date_raw)
        
        # Calculate status using the new utility
        is_fresh, days_missing = is_up_to_date(last_date)
        
        status_text = "Up-to-date" if is_fresh else f"Warning - {days_missing} trading day(s) missing"
        
        return JSONResponse(content={
            "ticker": ticker,
            "last_date": last_date.isoformat(),
            "is_fresh": is_fresh,
            "days_missing": days_missing,
            "status_text": status_text
        })
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking freshness: {e}"
        )

@app.get("/api/v1/tickers/{analysis_key}")
def get_available_tickers_for_analysis(analysis_key: str) -> JSONResponse:
    """Retrieves the list of tickers allowed for a specific analytical page scope."""
    
    tickers = get_tickers_for_analysis(analysis_key)
    
    return JSONResponse(content={
        "analysis_key": analysis_key,
        "tickers": tickers
    })

@app.get("/api/v1/data/prices/{ticker}")
def get_price_returns_viewer_data(
    ticker: str, 
    rows: int = 50,
    state_mode: str = "tri",
    threshold_bps: int = 10,
) -> JSONResponse:
    """Retrieves OHLC data, calculates returns and state classification for display."""
    
    ticker = ticker.upper()
    path = Path(f"data/raw/{ticker}.parquet") # Using raw parquet for full OHLC data
    
    if not path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Raw price data not found for {ticker} at {path}."
        )
        
    try:
        df_raw = pd.read_parquet(path)
        
        # Check for required columns before processing
        required = ['date', 'open', 'high', 'low', 'close']
        if not all(c.lower() in [col.lower() for col in df_raw.columns] for c in required):
            raise ValueError("Raw data missing required OHLC columns.")

        processed_data = _process_price_data(df_raw, state_mode, threshold_bps, rows)
        
        return JSONResponse(content={
            "ticker": ticker,
            "data": processed_data,
            "metadata": {
                "rows_displayed": len(processed_data)
            }
        })
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing price data: {e}"
        )

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
    threshold_bps: int, # NEW: Threshold is required for file uniqueness
    order: int = 1, 
) -> JSONResponse:
    """Retrieves the pre-computed multi-step forecast probabilities."""
    
    ticker = ticker.upper()
    
    # 1. Determine the path to the multi-step file
    path = markov_out_dir(ticker) / f"multi_step_order{order}_{state_mode}_thr{threshold_bps}.parquet"
    
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


@app.get("/api/v1/template/minervini/{ticker}")
def get_minervini_template(
    ticker: str,
    check_date: Optional[date] = None
) -> JSONResponse:
    """Calculates and returns the Minervini Trend Template checklist status."""
    
    ticker = ticker.upper()
    
    # Determine the check date (default to yesterday for most recent market data)
    final_check_date = check_date or (date.today() - timedelta(days=1))
    
    # 1. Load the necessary RAW price data file (contains OHLC for Minervini checks)
    # We use raw data because features data lacks the absolute price columns (High, Low, Adj Close)
    path = Path(f"data/raw/{ticker}.parquet")
    
    if not path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Raw price data not found for {ticker} at {path}. Cannot run template."
        )
        
    try:
        df_full = pd.read_parquet(path)
        
        # 2. Run the template check
        results = run_minervini_template(df_full, final_check_date)
        
        return JSONResponse(content={
            "ticker": ticker,
            "results": results
        })
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error running template analysis: {e}"
        )


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