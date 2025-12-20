from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
import hashlib

from mie_lib.utils.logging import get_logger
from mie_lib.utils.paths import FEATURES_DIR, HMM_DIR, hmm_std_out_dir as _std_out_dir
# --- NEW IMPORT ---
from mie_lib.utils.io import atomic_write_parquet, atomic_write_json
# --- END NEW IMPORT ---
import sys
from contextlib import contextmanager
import os
import signal
from contextlib import contextmanager

from mie_lib.utils.logging import get_logger
LOG = get_logger("hmm")

class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

ANALYTICS_DIR = HMM_DIR


def _compute_input_hash(df, feature_cols: list[str]) -> str:
    import numpy as np
    arr = df[feature_cols].to_numpy(dtype=float)
    h = hashlib.sha1(arr.tobytes()).hexdigest()
    h2 = hashlib.sha1(str(df["date"].iloc[-1]).encode()).hexdigest()
    return hashlib.sha1((h + h2 + str(len(df))).encode()).hexdigest()


@dataclass
class HMMConfig:
    n_states: int = 2  # 2 or 3
    train_window_years: int = 5
    random_seed: int = 42


def _load_features_for_hmm(ticker: str):
    import pandas as pd

    p = FEATURES_DIR / f"{ticker}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"Features parquet not found for {ticker}: {p}")
    df = pd.read_parquet(p)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    needed = ["ret_1d", "rv_20d"]
    for c in needed:
        if c not in df.columns:
            # We will now attempt to compute or log the missing feature instead of raising an error here.
            # However, for a quick fix, let's just ensure the error message is clean.
            raise ValueError(f"Missing required feature: {c}")
    # coerce numeric
    for c in needed:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _fit_hmm_gaussian(X, n_states: int, random_seed: int):
    import numpy as np
    from hmmlearn.hmm import GaussianHMM

    # Use diagonal covariance with small regularizer for robustness
    model = GaussianHMM(
        n_components=n_states,
        covariance_type="diag",
        random_state=random_seed,
        n_iter=200,
        min_covar=1e-6,
    )
    try:
        # Prevent indefinite hangs with a 60s timeout
        with time_limit(60): 
            model.fit(X)
    except TimeoutException:
        raise ValueError(f"HMM Fit Timed Out after 60s (n_states={n_states})")
        
    return model


def _map_state_names_by_mean_return(model, feature_names):
    import numpy as np

    # means shape: (n_states, n_features)
    means = model.means_
    # index of ret_1d feature
    if "ret_1d" in feature_names:
        ret_idx = feature_names.index("ret_1d")
    else:
        ret_idx = 0
    mean_returns = means[:, ret_idx]
    order = np.argsort(mean_returns)  # ascending: lowest=0 .. highest=last
    # map: highest -> Bull, lowest -> Bear, middle -> Neutral (only for 3-state)
    name_map = {}
    name_map[int(order[0])] = "Bear"
    if len(order) == 3:
        name_map[int(order[1])] = "Neutral"
    name_map[int(order[-1])] = "Bull"
    return name_map, mean_returns


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout output, used during external model fitting."""
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


def _calculate_annualized_metrics(stats_raw: pd.DataFrame, n_trading_days: int = 252) -> pd.DataFrame:
    """Calculates annualized return, volatility, and Sharpe ratio for each HMM state."""
    import numpy as np
    import pandas as pd
    
    stats = stats_raw.copy()
    
    def _ann(m: float, s: float, days: int) -> pd.Series:
        """Helper to calculate annualized return, volatility, and Sharpe."""
        # Annualized Return = Mean Daily Return * Trading Days
        ann_return = m * n_trading_days
        # Annualized Volatility = Daily StDev * Sqrt(Trading Days)
        ann_vol = s * np.sqrt(n_trading_days)
        # Sharpe Ratio (assuming risk-free rate is zero for simplicity)
        sharpe = (ann_return / ann_vol) if ann_vol > 1e-9 else np.nan
        
        return pd.Series({
            "ann_return": ann_return, 
            "ann_vol": ann_vol, 
            "sharpe": sharpe,
            "days_in_regime": days
        })

    # Group by state index and calculate mean daily return/std/count
    stats = stats_raw.groupby("hmm_state").ret.agg(["count", "mean", "std"]).rename(
        columns={"mean": "mean_daily_ret", "std": "std_daily_ret", "count": "total_days"}
    )
    
    # Calculate annualized metrics for each state
    annualized = stats.apply(
        lambda r: _ann(r["mean_daily_ret"], r["std_daily_ret"], r["total_days"]), 
        axis=1
    )
    
    # Combine daily and annualized metrics
    return pd.concat([stats, annualized], axis=1).reset_index()


def _calculate_expected_duration(trans_matrix: np.ndarray, state_map: Dict[int, str]) -> Dict[str, float]:
    """Calculates the expected number of days a regime persists (1 / (1 - P_ii))."""
    import numpy as np
    
    durations = {}
    n_states = trans_matrix.shape[0]
    
    for i in range(n_states):
        # P_ii is the probability of staying in state i
        p_ii = trans_matrix[i, i]
        
        # Duration = 1 / (1 - P_ii)
        duration_days = (1.0 / (1.0 - p_ii)) if (1.0 - p_ii) > 1e-9 else np.inf
        
        # Map raw index to state name
        state_name = state_map.get(i, f'State {i}')
        durations[state_name] = float(duration_days)
        
    return durations


def build_hmm_for_ticker(ticker: str, cfg: HMMConfig) -> Dict[str, str]:
    import numpy as np
    import pandas as pd

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = ANALYTICS_DIR / f"{ticker}"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _load_features_for_hmm(ticker)

    # training window: last N years
    # training window: handle 'Max' string or integer years
    last_date = df["date"].max()
    train_years_str = str(cfg.train_window_years).lower()
    
    if train_years_str == 'max':
        # Use full history if 'Max' is specified
        df_win = df.copy()
    else:
        try:
            years = int(train_years_str)
            start_cut = last_date - pd.DateOffset(years=years)
            df_win = df[df["date"] >= start_cut].reset_index(drop=True)
        except ValueError:
            LOG.error("Invalid train_window_years value: %s. Using default 5 years.", train_years_str)
            start_cut = last_date - pd.DateOffset(years=5)
            df_win = df[df["date"] >= start_cut].reset_index(drop=True)

    if len(df_win) < 500:
        LOG.warning("HMM: insufficient samples for %s (%d < 500), writing NA outputs", ticker, len(df_win))
        # write placeholder files with NA
        out_dir.mkdir(parents=True, exist_ok=True)
        # --- ATOMIC REPLACEMENT START ---
        atomic_write_parquet(pd.DataFrame({"date": df["date"], "hmm_prob_bull": np.nan, "hmm_prob_bear": np.nan}), out_dir / "hmm_probs.parquet")
        atomic_write_parquet(pd.DataFrame({"date": df["date"], "hmm_state_name": pd.NA, "hmm_state": pd.NA}), out_dir / "hmm_states.parquet")
        atomic_write_parquet(pd.DataFrame({"metric": [], "value": []}), out_dir / "hmm_metrics.parquet")
        atomic_write_json({
            "ticker": ticker,
            "n_states": cfg.n_states,
            "train_window_years": cfg.train_window_years,
            "random_seed": cfg.random_seed,
            "generated_timestamp": datetime.now(timezone.utc).isoformat(),
            "insufficient_samples": True,
        }, out_dir / "hmm_metadata.json")
        # --- ATOMIC REPLACEMENT END ---
        return {
            "probs": str(out_dir / "hmm_probs.parquet"),
            "states": str(out_dir / "hmm_states.parquet"),
            "metrics": str(out_dir / "hmm_metrics.parquet"),
            "metadata": str(out_dir / "hmm_metadata.json"),
        }

    # Prepare features matrix X
    feature_names = ["ret_1d", "rv_20d"]
    X = df_win[feature_names].to_numpy(dtype=float)
    # Replace infs and NaNs
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Fit model
    model = _fit_hmm_gaussian(X, n_states=int(cfg.n_states), random_seed=int(cfg.random_seed))

    # Posteriors on full (window) dates
    post = model.predict_proba(X)  # shape (T, n_states)
    assert post.shape[1] == int(cfg.n_states)

    # Map names by mean return ordering
    name_map, mean_returns = _map_state_names_by_mean_return(model, feature_names)
    # predicted most likely state
    z = post.argmax(axis=1)
    z_named = [name_map[int(si)] for si in z]

    # Build probs per date with named columns
    probs_df = pd.DataFrame({"date": df_win["date"].values})
    if cfg.n_states == 2:
        # map columns to bear/bull by name_map ordering
        # Build columns with zeros then fill
        probs_df["hmm_prob_bull"] = np.nan
        probs_df["hmm_prob_bear"] = np.nan
        for state_idx, name in name_map.items():
            col = "hmm_prob_bull" if name == "Bull" else "hmm_prob_bear"
            probs_df[col] = post[:, state_idx]
    else:
        probs_df["hmm_prob_bull"] = 0.0
        probs_df["hmm_prob_bear"] = 0.0
        probs_df["hmm_prob_neutral"] = 0.0
        for state_idx, name in name_map.items():
            if name == "Bull":
                probs_df["hmm_prob_bull"] = post[:, state_idx]
            elif name == "Bear":
                probs_df["hmm_prob_bear"] = post[:, state_idx]
            else:
                probs_df["hmm_prob_neutral"] = post[:, state_idx]

    # States
    states_df = pd.DataFrame({
        "date": df_win["date"].values,
        "hmm_state": z,
        "hmm_state_name": z_named,
    })

    # Metrics: state means/stds and transition matrix
    import numpy as np
    means = model.means_
    covars = model.covars_
    stds = np.sqrt(np.diagonal(covars, axis1=1, axis2=2))
    trans = model.transmat_

    metrics_rows = []
    for i in range(cfg.n_states):
        metrics_rows.append({
            "metric": f"state_{i}_mean_ret",
            "value": float(means[i, 0]),
        })
        metrics_rows.append({
            "metric": f"state_{i}_std_ret",
            "value": float(stds[i, 0]),
        })
    # flatten transition matrix
    for i in range(cfg.n_states):
        for j in range(cfg.n_states):
            metrics_rows.append({
                "metric": f"trans_{i}_{j}",
                "value": float(trans[i, j]),
            })

    metrics_df = pd.DataFrame(metrics_rows)

    # Write artifacts
    out_dir.mkdir(parents=True, exist_ok=True)
    # --- ATOMIC REPLACEMENT START ---
    atomic_write_parquet(probs_df, out_dir / "hmm_probs.parquet")
    atomic_write_parquet(states_df, out_dir / "hmm_states.parquet")
    atomic_write_parquet(metrics_df, out_dir / "hmm_metrics.parquet")
    
    meta = {
        "ticker": ticker,
        "n_states": int(cfg.n_states),
        "train_window_years": int(cfg.train_window_years),
        "random_seed": int(cfg.random_seed),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_columns": feature_names,
        "rows": int(len(df_win)),
    }
    atomic_write_json(meta, out_dir / "hmm_metadata.json")
    # --- ATOMIC REPLACEMENT END ---

    LOG.info("HMM outputs written for %s to %s", ticker, out_dir)
    return {
        "probs": str(out_dir / "hmm_probs.parquet"),
        "states": str(out_dir / "hmm_states.parquet"),
        "metrics": str(out_dir / "hmm_metrics.parquet"),
        "metadata": str(out_dir / "hmm_metadata.json"),
    }




def describe_hmm_run(
    ticker: str,
    window: str | int,
    n_states: int,
    df_full: pd.DataFrame,
    df_train: pd.DataFrame,
    model,
    name_map: Dict[int, str],
    out_dir: Any
):
    """
    Outputs a debug JSON with detailed HMM run info for comparison/fingerprinting.
    """
    import numpy as np
    import json
    
    # 1. Data Ranges
    data_start = df_full["date"].min().isoformat()
    data_end = df_full["date"].max().isoformat()
    
    train_start = df_train["date"].min().isoformat()
    train_end = df_train["date"].max().isoformat()
    
    # 2. Model Details
    means = model.means_ # (n_states, n_features)
    
    # Handle covariance shape based on type
    if model.covariance_type == "diag":
        # covars_ is (n_states, n_features) - variances
        stds = np.sqrt(model.covars_)
    else:
        # Assume full: (n_states, n_features, n_features)
        # Extract diagonal for stds
        covars = model.covars_
        stds = np.sqrt(np.diagonal(covars, axis1=1, axis2=2))

    state_details = {}
    for sid in range(n_states):
        sname = name_map.get(sid, f"State_{sid}")
        state_details[sname] = {
            "id": int(sid),
            "mean_vector": means[sid].tolist(),
            "std_vector": stds[sid].tolist(),
        }
        
    trans_mat = model.transmat_.tolist()
    
    bull_state_id = [k for k, v in name_map.items() if v == "Bull"][0]
    bear_state_id = [k for k, v in name_map.items() if v == "Bear"][0]
    
    debug_info = {
        "ticker": ticker,
        "window": str(window),
        "n_states": n_states,
        "data_range": {
            "start": data_start,
            "end": data_end,
            "n_samples": len(df_full)
        },
        "train_range": {
            "start": train_start,
            "end": train_end,
            "n_samples": len(df_train)
        },
        "settings": {
            "frequency": "Daily",
            "returns_type": "ret_1d (Simple Returns)",
            "scaling": "None",
            "bull_threshold": "N/A (Frontend Setting)",
            "bear_threshold": "N/A (Frontend Setting)"
        },
        "model_parameters": {
            "state_definitions": state_details,
            "transition_matrix": trans_mat,
            "bull_state_id": int(bull_state_id),
            "bear_state_id": int(bear_state_id),
            "sorting_rule": "States sorted by mean of first feature (ret_1d). Lowest=Bear, Highest=Bull."
        }
    }
    
    fname = f"hmm_debug_{ticker}_{window}_{n_states}.json"
    debug_path = out_dir / fname
    
    with open(debug_path, "w") as f:
        json.dump(debug_info, f, indent=4, default=str)
        
    return debug_path


import warnings
def build_hmm_standardized_for_ticker(ticker: str, n_states: int = 2, train_window_years: int = 5, random_seed: int = 42) -> Dict[str, str | bool]:
    # Inside the function, add the filter right at the start:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    
    # And specifically filter the DeprecationWarning
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    import numpy as np
    import pandas as pd

    out_dir = _std_out_dir(ticker, train_window_years, n_states)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _load_features_for_hmm(ticker)
    # training window last N years
    # training window: handle 'Max' string or integer years
    last_date = df["date"].max()
    train_years_str = str(train_window_years).lower()
    
    if train_years_str == 'max':
        # Use full history if 'Max' is specified
        df_win = df.copy()
    else:
        try:
            years = int(train_years_str)
            start_cut = last_date - pd.DateOffset(years=years)
            df_win = df[df["date"] >= start_cut].reset_index(drop=True)
        except ValueError:
            LOG.error("Invalid train_window_years value: %s. Using default 5 years.", train_years_str)
            start_cut = last_date - pd.DateOffset(years=5)
            df_win = df[df["date"] >= start_cut].reset_index(drop=True)

    meta_path = out_dir / "hmm_metadata.json"
    feature_names = ["ret_1d", "rv_20d"]
    inp_hash = _compute_input_hash(df_win, feature_names)
    if meta_path.exists():
        try:
            old: Dict[str, Any] = json.loads(meta_path.read_text())
            if old.get("input_hash") == inp_hash and int(old.get("n_states", 0)) == int(n_states) and str(old.get("train_window_years", 0)) == str(train_window_years):
                # idempotent skip
                return {
                    "probs": str(out_dir / "hmm_probs.parquet"),
                    "states": str(out_dir / "hmm_states.parquet"),
                    "metrics": str(out_dir / "hmm_metrics.parquet"),
                    "metadata": str(meta_path),
                    "skipped": True,
                }
        except Exception:
            pass

    if len(df_win) < 500:
        LOG.warning("HMM std: insufficient samples for %s (%d < 500)", ticker, len(df_win))
        # write minimal placeholders in standardized path
        # --- ATOMIC REPLACEMENT START ---
        atomic_write_parquet(pd.DataFrame({"date": df_win["date"], "hmm_prob_bull": np.nan, "hmm_prob_bear": np.nan}), out_dir / "hmm_probs.parquet")
        atomic_write_parquet(pd.DataFrame({"date": df_win["date"], "hmm_state_name": pd.NA, "hmm_state": pd.NA}), out_dir / "hmm_states.parquet")
        atomic_write_parquet(pd.DataFrame({"metric": [], "value": []}), out_dir / "hmm_metrics.parquet")
        meta = {
            "ticker": ticker,
            "n_states": int(n_states),
            "train_window_years": train_window_years,
            "random_seed": int(random_seed),
            "generated_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_columns": feature_names,
            "rows": int(len(df_win)),
            "input_hash": inp_hash,
            "insufficient_samples": True,
            "performance_stats": [], # Placeholder for insufficient samples
        }
        atomic_write_json(meta, meta_path)
        # --- ATOMIC REPLACEMENT END ---
        return {
            "probs": str(out_dir / "hmm_probs.parquet"),
            "states": str(out_dir / "hmm_states.parquet"),
            "metrics": str(out_dir / "hmm_metrics.parquet"),
            "metadata": str(meta_path),
            "skipped": False,
        }

    # Fit as before using windowed data
    X = df_win[feature_names].to_numpy(dtype=float)
    # Temporarily suppress warnings/prints during nan_to_num conversion
    # warnings imported at module level or top of function

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    warnings.filterwarnings("default", category=RuntimeWarning) # Restore default
    # ------------------ WARNING SUPPRESSION FIX ------------------
    # warnings imported at module level or top of function

    
    # We must suppress warnings during fit/predict that might contaminate stdout
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", 
            category=RuntimeWarning, 
            message="Internal S..."
        )
        warnings.filterwarnings(
            "ignore", 
            category=DeprecationWarning,
            message="The default value of `n_init` will change from 10 to auto in 1.4"
        )
        
        # ------------------ FIT AND PREDICT WITH STDOUT SUPPRESSION ------------------
        # Fit model and predict probabilities, suppressing any toxic stdout contamination
        with suppress_stdout():
            model = _fit_hmm_gaussian(X, n_states=int(n_states), random_seed=int(random_seed))
            post = model.predict_proba(X)  # shape (T, n_states)
        # ------------------ END STDOUT SUPPRESSION ------------------
    
    # ------------------ END WARNING SUPPRESSION FIX ------------------

    assert post.shape[1] == int(n_states)

    # Map names by mean return ordering
    name_map, mean_returns = _map_state_names_by_mean_return(model, feature_names)
    # predicted most likely state
    z = post.argmax(axis=1)
    z_named = [name_map[int(si)] for si in z]

    # --- DEBUG / FINGERPRINT ---
    try:
        debug_file = describe_hmm_run(
            ticker=ticker,
            window=train_window_years,
            n_states=int(n_states),
            df_full=df,
            df_train=df_win,
            model=model,
            name_map=name_map,
            out_dir=out_dir
        )
        LOG.info("HMM Debug Fingerprint written to: %s", debug_file)
    except Exception as e:
        LOG.error("Failed to write HMM debug fingerprint: %s", e)
    # ---------------------------

    # --- PERFORMANCE METRICS CALCULATION (NEW) ---
    df_metrics_input = pd.DataFrame({
        "hmm_state": z, 
        "ret": df_win["ret_1d"].values
    })
    
    performance_metrics_df = _calculate_annualized_metrics(df_metrics_input)

    # --- NEW: Calculate Expected Duration ---
    # Need the transition matrix (model.transmat_) and state map (name_map)
    expected_durations = _calculate_expected_duration(model.transmat_, name_map)

    # Reindex and clean up for JSON persistence
    metrics_list = []
    for _, row in performance_metrics_df.iterrows():
        state_name = name_map[int(row["hmm_state"])]
        
        metrics_list.append({
            "state": state_name,
            "mean_daily_ret": float(row["mean_daily_ret"]),
            "ann_return": float(row["ann_return"]),
            "ann_vol": float(row["ann_vol"]),
            "sharpe": float(row["sharpe"]),
            "days_in_regime": int(row["total_days"]),
        })

    # --- END PERFORMANCE METRICS CALCULATION ---

    probs_df = pd.DataFrame({"date": df_win["date"].values})
    if n_states == 2:
        probs_df["hmm_prob_bull"] = np.nan
        probs_df["hmm_prob_bear"] = np.nan
        for state_idx, name in name_map.items():
            col = "hmm_prob_bull" if name == "Bull" else "hmm_prob_bear"
            probs_df[col] = post[:, state_idx]
    else:
        probs_df["hmm_prob_bull"] = 0.0
        probs_df["hmm_prob_bear"] = 0.0
        probs_df["hmm_prob_neutral"] = 0.0
        for state_idx, name in name_map.items():
            if name == "Bull":
                probs_df["hmm_prob_bull"] = post[:, state_idx]
            elif name == "Bear":
                probs_df["hmm_prob_bear"] = post[:, state_idx]
            else:
                probs_df["hmm_prob_neutral"] = post[:, state_idx]

    states_df = pd.DataFrame({
        "date": df_win["date"].values,
        "hmm_state": z,
        "hmm_state_name": z_named,
    })

    means = model.means_
    covars = model.covars_
    stds = np.sqrt(np.diagonal(covars, axis1=1, axis2=2))
    trans = model.transmat_
    metrics_rows = []
    for i in range(int(n_states)):
        metrics_rows.append({"metric": f"state_{i}_mean_ret", "value": float(means[i, 0])})
        metrics_rows.append({"metric": f"state_{i}_std_ret", "value": float(stds[i, 0])})
    for i in range(int(n_states)):
        for j in range(int(n_states)):
            metrics_rows.append({"metric": f"trans_{i}_{j}", "value": float(trans[i, j])})
    metrics_df = pd.DataFrame(metrics_rows)

    # --- ATOMIC REPLACEMENT START ---
    atomic_write_parquet(probs_df, out_dir / "hmm_probs.parquet")
    atomic_write_parquet(states_df, out_dir / "hmm_states.parquet")
    atomic_write_parquet(metrics_df, out_dir / "hmm_metrics.parquet")
    
    meta = {
        "ticker": ticker,
        "n_states": int(n_states),
        "train_window_years": train_window_years,
        "random_seed": int(random_seed),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_columns": feature_names,
        "rows": int(len(df_win)),
        "input_hash": inp_hash,
        "expected_durations": expected_durations,
        "performance_stats": metrics_list,
    }
    atomic_write_json(meta, meta_path)
    # --- ATOMIC REPLACEMENT END ---

    return {
        "probs": str(out_dir / "hmm_probs.parquet"),
        "states": str(out_dir / "hmm_states.parquet"),
        "metrics": str(out_dir / "hmm_metrics.parquet"),
        "metadata": str(meta_path),
        "skipped": False,
    }