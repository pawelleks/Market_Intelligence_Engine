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
from mie_lib.utils.paths import features_parquet_path, options_latest_json_path, options_expected_moves_path
import json
import yfinance as yf

# Price Viewer Imports
from mie_lib.core.state_classification import classify_tri_state
from mie_lib.analytics.minervini import run_minervini_template
from mie_lib.utils.ticker_service import get_tickers_for_analysis
from mie_lib.analytics.seasonality_analytics import get_seasonal_curves, get_calendar_heatmap, get_day_drilldown
from mie_lib.analytics.downtrend_engine import compute_downtrend_score_latest, compute_downtrend_score_historical, compute_downtrend_signals_historical
from mie_lib.data_ingest.data_aligner import fetch_and_align_dcs_assets
from mie_lib.analytics.expected_moves.api_endpoints import router as reliability_router
from mie_lib.analytics.gex.api_endpoints import router as gex_router
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

# ... (rest of imports are fine, just updating the specific block if needed, but replace_file_content works on blocks)
# Actually, I'll just update the endpoint and the import line separately or together if they are close.
# The import is at line 27. The endpoint is at the end.
# I'll do two edits or one large one if I can.
# Let's do the import first.

# Wait, I can't do multiple edits in one replace_file_content call unless I use multi_replace.
# I'll use multi_replace_file_content.

# -----------------------------------------------------------------
# FastAPI Initialization
# -----------------------------------------------------------------

app = FastAPI(
    title="MIE Analytics API",
    description="Serves pre-computed Markov and HMM data as JSON/REST endpoints.",
    version="1.0.0",
)

# Include Routers
app.include_router(reliability_router)
app.include_router(gex_router)
from mie_lib.analytics.scanner.api_endpoints import router as minervini_router
app.include_router(minervini_router)
from mie_lib.analytics.gaf.api_endpoints import router as gaf_router
app.include_router(gaf_router, prefix="/api/v1/gaf", tags=["gaf"])
from mie_lib.analytics.hmm.api_endpoints import router as hmm_router
app.include_router(hmm_router, prefix="/api/v1/hmm", tags=["hmm"])

# Configure CORS
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


@app.get("/api/v1/hmm/regime/{ticker}")
def get_hmm_regime(
    ticker: str,
    n_states: int = HMMConfig.n_states,
    window_years: Union[int, str] = HMMConfig.train_window_years,
) -> JSONResponse:
    """Retrieves the pre-computed HMM regime sequence (State IDs and Names)."""
    
    ticker = ticker.upper()
    
    # 1. Determine the standardized path 
    out_dir = hmm_std_out_dir(ticker, window_years, n_states)
    path = out_dir / "hmm_states.parquet"
    
    # 2. Read and format the data
    data = _read_parquet_and_format(path)
    
    if data is None:
        raise HTTPException(
            status_code=404, 
            detail=(
                f"HMM Regime not found for {ticker} (States={n_states}, Window={window_years}y). "
                f"Run the CLI job (e.g., build-hmm) first."
            )
        )
    
    return JSONResponse(content={
        "ticker": ticker,
        "n_states": n_states,
        "window_years": window_years,
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


# -----------------------------------------------------------------
# Seasonality Endpoints
# -----------------------------------------------------------------



@app.get("/api/v1/seasonality/curves/{ticker}")
def api_get_seasonal_curves(ticker: str, lookbacks: str = "10,20") -> JSONResponse:
    """Returns cumulative return curves. 'lookbacks' is a comma-separated string (e.g. '10,20')."""
    try:
        lbs = [int(x.strip()) for x in lookbacks.split(",") if x.strip()]
        data = get_seasonal_curves(ticker.upper(), lbs)
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Seasonality data not found for {ticker}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/seasonality/heatmap/{ticker}")
def api_get_calendar_heatmap(ticker: str, lookback: int = 20) -> JSONResponse:
    """Returns 12x31 matrix of average returns."""
    try:
        data = get_calendar_heatmap(ticker.upper(), lookback)
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Seasonality data not found for {ticker}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/seasonality/drilldown/{ticker}/{month}/{day}")
def api_get_day_drilldown(ticker: str, month: int, day: int, lookback: int = 50) -> JSONResponse:
    """Returns historical records for a specific day."""
    try:
        data = get_day_drilldown(ticker.upper(), month, day, lookback)
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Seasonality data not found for {ticker}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/dcs/latest/{ticker}")
def get_dcs_latest_status(ticker: str) -> JSONResponse:
    """Returns the latest Downtrend Confirmation Score (DCS) and signal breakdown."""
    try:
        # 1. Fetch and align all assets
        df_aligned, weights = fetch_and_align_dcs_assets(ticker, lookback_days=500)
        
        if df_aligned.empty:
            raise HTTPException(status_code=404, detail="Multi-asset data alignment failed.")

        # 2. Run the core scoring engine
        score_data = compute_downtrend_score_latest(df_aligned, weights=weights, ticker=ticker)
        
        return JSONResponse(content={
            "ticker": ticker,
            "results": score_data,
            "config_summary": {
                "weights": weights, 
                "thresholds": {"Warning": 40, "Alert": 60, "Crisis": 80}
            }
        })
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Data required for DCS missing: {e}")
    except Exception as e:
        print(f"FATAL ERROR IN DCS ENDPOINT: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error running DCS analysis: {e}")

@app.get("/api/v1/dcs/history/{ticker}")
def get_dcs_history(ticker: str) -> JSONResponse:
    try:
        # Fetch data aligned over 30 years for a long-term chart window
        df_aligned, weights = fetch_and_align_dcs_assets(ticker, lookback_days=30*365)
        
        if df_aligned.empty:
            raise HTTPException(status_code=404, detail="Multi-asset data alignment failed for history.")

        # Compute historical scores AND signals
        history_records = compute_downtrend_signals_historical(df_aligned, weights=weights, ticker=ticker)
        
        return JSONResponse(content={"ticker": ticker, "data": history_records})
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Data required for DCS missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error running DCS analysis: {e}")

# -----------------------------------------------------------------
# Expected Moves Endpoints
# -----------------------------------------------------------------

@app.get("/api/v1/expected_moves/latest")
def get_latest_expected_moves() -> JSONResponse:
    """
    Returns the latest Expected Moves calculation results.
    """
    path = options_latest_json_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="No latest Expected Moves data found. Please run build-expected-moves.")
        
    try:
        with open(path, "r") as f:
            data = json.load(f)
            
        # Filter by Scope
        try:
            import yaml
            from mie_lib.utils.paths import ROOT
            scope_path = ROOT / "config" / "analysis_scope.yml"
            if scope_path.exists():
                with open(scope_path, "r") as f:
                    scope_cfg = yaml.safe_load(f)
                    allowed_tickers = scope_cfg.get("scope", {}).get("Expected_Moves_Reliability", [])
                    
                if allowed_tickers:
                    # Filter existing tickers
                    filtered_tickers = {k: v for k, v in data.get("tickers", {}).items() if k in allowed_tickers}
                    data["tickers"] = filtered_tickers
        except Exception as e:
            print(f"Error filtering EM data by scope: {e}")
            # Fallback to returning all data if filter fails
            
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error reading latest EM json: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading data: {e}")

@app.get("/api/v1/expected_moves/history/{ticker}")
def get_expected_moves_history(ticker: str) -> JSONResponse:
    """
    Returns the historical Expected Moves data for a ticker.
    """
    path = options_expected_moves_path(ticker)
    if not path.exists():
        # Return empty list if no history yet
        return JSONResponse(content=[])
        
    try:
        df = pd.read_parquet(path)
        # Convert dates to strings
        if "date" in df.columns:
            df["date"] = df["date"].astype(str)
        if "expiry_date" in df.columns:
            df["expiry_date"] = df["expiry_date"].astype(str)
            
        data = df.to_dict(orient="records")
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error reading EM history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading history: {e}")

@app.get("/api/v1/market/candles/{ticker}")
def get_market_candles(ticker: str, interval: str = "1d", range: str = "max") -> JSONResponse:
    """
    Fetches candle data from yfinance.
    Intervals: 1h, 4h, 1d.
    Range: max (default), 2y, 5y, etc.
    """
    try:
        # 1. Try Massive.com Provider first (Better data, 15min delayed usually)
        try:
            provider = MassiveOptionChainProvider()
            if provider.api_key:
                # Calculate start date based on range
                end_date = date.today()
                start_date = end_date.replace(year=end_date.year - 2) # Default 2y
                
                if range == "5y":
                    start_date = end_date.replace(year=end_date.year - 5)
                elif range == "1y":
                    start_date = end_date.replace(year=end_date.year - 1)
                elif range == "max":
                    start_date = date(2000, 1, 1) # Reasonable max
                
                df_massive = provider.fetch_candles(ticker, interval=interval, start_date=start_date, end_date=end_date)
                
                if not df_massive.empty:
                    # Format for frontend
                    if "Date" in df_massive.columns:
                        df_massive["Date"] = df_massive["Date"].astype(str)
                    
                    cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
                    data = df_massive[cols].to_dict(orient="records")
                    return JSONResponse(content=data)
                    
        except Exception as e:
            print(f"Massive Candle Fetch Failed (falling back to yfinance): {e}")

        # 2. Fallback to yfinance
        # Validate interval
        valid_intervals = {"1h", "1d", "5d", "1wk", "1mo"} 
        
        yf_interval = interval
        if interval == "4h":
            yf_interval = "1h" # Fetch 1h base
            
        t = yf.Ticker(ticker)
        
        # yfinance limit for 1h is 730 days (~2y). If user asks for 'max' with 1h, yfinance might error or truncate.
        # Let's handle it gracefully.
        req_range = range
        if (interval == "1h" or interval == "4h") and range == "max":
            req_range = "2y"
            
        df = t.history(period=req_range, interval=yf_interval)
        
        if df.empty:
             return JSONResponse(content=[])
             
        # Resample if 4h
        if interval == "4h":
            # Resample logic
            agg_dict = {
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }
            # Resample to 4H, offset to market open if possible, but simple '4H' is okay
            df = df.resample('4h').agg(agg_dict).dropna()
            
        # Format for frontend
        df.reset_index(inplace=True)
        
        # yfinance returns datetime with timezone usually
        # Convert to string
        if "Date" in df.columns:
            df["Date"] = df["Date"].astype(str)
        elif "Datetime" in df.columns:
             df["Date"] = df["Datetime"].astype(str)
             
        # Select columns
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        data = df[cols].to_dict(orient="records")
        
        return JSONResponse(content=data)
        
    except Exception as e:
        # print(f"Error fetching candles: {e}")
        return JSONResponse(content=[], status_code=500)

# -----------------------------------------------------------------
# Massive.com Integration (Experimental)
# -----------------------------------------------------------------
# Force Reload Trigger: 0DTE Fix
from mie_lib.data_ingest.providers.massive import MassiveOptionChainProvider
from mie_lib.analytics.expected_moves.data_ingest import get_target_expirations, fetch_vix1d_close

@app.get("/api/v1/expected_moves/massive/latest")
async def get_expected_moves_massive():
    """
    Fetches 'Live' (Delayed) Expected Moves using yfinance.
    (Massive.com API key does not support real-time data, so we fallback to yfinance for 'Live' view).
    """
    import yfinance as yf
    import pandas as pd
    from datetime import datetime, timedelta
    import numpy as np

    try:
        # Load scope from config
        import yaml
        from mie_lib.utils.paths import ROOT
        scope_path = ROOT / "config" / "analysis_scope.yml"
        
        tickers = ["SPY", "QQQ", "IWM", "DIA"] # Default fallback
        if scope_path.exists():
            try:
                with open(scope_path, "r") as f:
                    scope_cfg = yaml.safe_load(f)
                    tickers = scope_cfg.get("scope", {}).get("Expected_Moves_Reliability", tickers)
            except Exception as e:
                print(f"Error loading scope: {e}")

        as_of = date.today()
        
        # 1. Fetch VIX1D (still from yfinance)
        vix1d_val = fetch_vix1d_close(as_of)
        
        results = {
            "as_of": as_of.isoformat(),
            "vix1d": vix1d_val,
            "confidence_score": 80, 
            "tickers": {}
        }
        
        for ticker in tickers:
            yf_ticker = yf.Ticker(ticker)
            
            # 1. Fetch Live Spot (1m history)
            # Try to get the absolute latest price
            try:
                hist = yf_ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    spot = float(hist.iloc[-1]['Close'])
                else:
                    # Fallback to daily if market closed or no 1m data
                    hist_day = yf_ticker.history(period="1d")
                    if not hist_day.empty:
                        spot = float(hist_day.iloc[-1]['Close'])
                    else:
                        continue # Cannot get spot
            except Exception:
                continue

            # 2. Determine Expirations
            # We need to match the logic: ODTE, Weekly, Monthly
            # To ensure alignment with EOD data, we try to read the target dates from latest.json
            
            target_dates = {}
            try:
                from mie_lib.utils.paths import options_latest_json_path
                import json
                path = options_latest_json_path()
                if path.exists():
                    with open(path, "r") as f:
                        latest_data = json.load(f)
                        if ticker in latest_data.get("tickers", {}):
                            t_exps = latest_data["tickers"][ticker].get("expirations", {})
                            for k in ["ODTE", "WEEKLY", "MONTHLY"]:
                                if k in t_exps and "expiry_date" in t_exps[k]:
                                    target_dates[k] = datetime.strptime(t_exps[k]["expiry_date"], "%Y-%m-%d").date()
            except Exception as e:
                print(f"Failed to read target dates from latest.json: {e}")

            # yfinance expirations are strings 'YYYY-MM-DD'
            avail_expirations = yf_ticker.options
            if not avail_expirations:
                continue
                
            # Helper to find closest expiration to target date
            def find_closest_expiry(target_date, options):
                # options is list of date strings
                # target_date is datetime.date
                min_diff = 9999
                best_exp = None
                target_str = target_date.isoformat()
                
                # First try exact match
                if target_str in options:
                    return target_str
                
                # Else find closest future date
                for exp_str in options:
                    exp_d = datetime.strptime(exp_str, "%Y-%m-%d").date()
                    diff = (exp_d - target_date).days
                    if 0 <= diff < min_diff:
                        min_diff = diff
                        best_exp = exp_str
                return best_exp

            # Target Dates
            # Use shared logic to determine target dates (consistent with EOD)
            odte_target, weekly_target, monthly_target = get_target_expirations(date.today())
            
            # Helper to find closest expiry to target date
            def find_closest_expiry(target_date, options):
                # options is list of date strings
                # target_date is datetime.date
                min_diff = 9999
                best_exp = None
                target_str = target_date.isoformat()
                
                # First try exact match
                if target_str in options:
                    return target_str
                
                # Else find closest future date
                for exp_str in options:
                    exp_d = datetime.strptime(exp_str, "%Y-%m-%d").date()
                    diff = (exp_d - target_date).days
                    if 0 <= diff < min_diff:
                        min_diff = diff
                        best_exp = exp_str
                return best_exp

            # ODTE
            odte_exp = find_closest_expiry(odte_target, avail_expirations)
            
            # Weekly
            weekly_exp = find_closest_expiry(weekly_target, avail_expirations)
            
            # Monthly
            monthly_exp = find_closest_expiry(monthly_target, avail_expirations)
            
            t_data = {
                "spot_price": spot,
                "expirations": {}
            }
            
            # Process each
            # Map our keys to the found expirations
            exp_map = {
                "ODTE": odte_exp,
                "WEEKLY": weekly_exp,
                "MONTHLY": monthly_exp
            }
            
            for label, exp_date_str in exp_map.items():
                if not exp_date_str:
                    continue
                    
                try:
                    chain = yf_ticker.option_chain(exp_date_str)
                    calls = chain.calls
                    puts = chain.puts
                    
                    # Find ATM Strike
                    # Minimize |strike - spot|
                    # We can merge calls and puts or just look at one. 
                    # Ideally we find the strike where strike is closest to spot.
                    
                    # Let's use calls to find strikes
                    if calls.empty:
                        continue
                        
                    # Calculate distance to spot
                    calls['dist'] = abs(calls['strike'] - spot)
                    atm_row = calls.loc[calls['dist'].idxmin()]
                    atm_strike = atm_row['strike']
                    
                    # Get Call Price (lastPrice or (bid+ask)/2)
                    # Prefer mid if bid/ask available and non-zero, else lastPrice
                    def get_price(row):
                        bid = row.get('bid', 0)
                        ask = row.get('ask', 0)
                        last = row.get('lastPrice', 0)
                        if bid > 0 and ask > 0:
                            return (bid + ask) / 2
                        return last
                        
                    call_price = get_price(atm_row)
                    
                    # Find corresponding Put
                    put_row = puts[puts['strike'] == atm_strike]
                    if put_row.empty:
                        # Try to find closest put if exact match missing (unlikely for ATM)
                        puts['dist'] = abs(puts['strike'] - spot)
                        put_row = puts.loc[puts['dist'].idxmin()]
                        
                    if isinstance(put_row, pd.DataFrame):
                         put_row = put_row.iloc[0]
                         
                    put_price = get_price(put_row)
                    
                    straddle = call_price + put_price
                    
                    t_data["expirations"][label] = {
                        "expiry_date": exp_date_str,
                        "lower_range": spot - straddle,
                        "upper_range": spot + straddle,
                        "em_dollars": straddle,
                        "debug": {
                            "atm_strike": float(atm_strike),
                            "call_ticker": f"C_{atm_strike}",
                            "call_price": float(call_price),
                            "put_ticker": f"P_{atm_strike}",
                            "put_price": float(put_price)
                        }
                    }
                    
                except Exception as e:
                    # print(f"Error processing {label} for {ticker}: {e}")
                    continue

            results["tickers"][ticker] = t_data
            
        return JSONResponse(content=results)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

        
    except Exception as e:
        print(f"Error fetching candles for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching candles: {e}")