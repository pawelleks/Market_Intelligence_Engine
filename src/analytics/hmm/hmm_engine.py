from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from datetime import datetime, timezone
import json

from src.utils.logging import get_logger

LOG = get_logger("hmm")

DATA_DIR = Path("data")
FEATURES_DIR = DATA_DIR / "features"
ANALYTICS_DIR = DATA_DIR / "analytics" / "hmm"


def _std_out_dir(ticker: str, window_years: int, n_states: int) -> Path:
    return ANALYTICS_DIR / f"{ticker}" / f"win{int(window_years)}y" / f"states{int(n_states)}"


def _compute_input_hash(df, feature_cols: list[str]) -> str:
    import hashlib
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
    model.fit(X)
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


def build_hmm_for_ticker(ticker: str, cfg: HMMConfig) -> Dict[str, str]:
    import numpy as np
    import pandas as pd

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = ANALYTICS_DIR / f"{ticker}"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _load_features_for_hmm(ticker)

    # training window: last N years
    last_date = df["date"].max()
    start_cut = last_date - pd.DateOffset(years=int(cfg.train_window_years))
    df_win = df[df["date"] >= start_cut].reset_index(drop=True)

    if len(df_win) < 500:
        LOG.warning("HMM: insufficient samples for %s (%d < 500), writing NA outputs", ticker, len(df_win))
        # write placeholder files with NA
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"date": df["date"], "hmm_prob_bull": np.nan, "hmm_prob_bear": np.nan}).to_parquet(out_dir / "hmm_probs.parquet", index=False)
        pd.DataFrame({"date": df["date"], "hmm_state_name": pd.NA, "hmm_state": pd.NA}).to_parquet(out_dir / "hmm_states.parquet", index=False)
        pd.DataFrame({"metric": [], "value": []}).to_parquet(out_dir / "hmm_metrics.parquet", index=False)
        (out_dir / "hmm_metadata.json").write_text(json.dumps({
            "ticker": ticker,
            "n_states": cfg.n_states,
            "train_window_years": cfg.train_window_years,
            "random_seed": cfg.random_seed,
            "generated_timestamp": datetime.now(timezone.utc).isoformat(),
            "insufficient_samples": True,
        }, indent=2))
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
    probs_df.to_parquet(out_dir / "hmm_probs.parquet", index=False)
    states_df.to_parquet(out_dir / "hmm_states.parquet", index=False)
    metrics_df.to_parquet(out_dir / "hmm_metrics.parquet", index=False)

    meta = {
        "ticker": ticker,
        "n_states": int(cfg.n_states),
        "train_window_years": int(cfg.train_window_years),
        "random_seed": int(cfg.random_seed),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_columns": feature_names,
        "rows": int(len(df_win)),
    }
    (out_dir / "hmm_metadata.json").write_text(json.dumps(meta, indent=2))

    LOG.info("HMM outputs written for %s to %s", ticker, out_dir)
    return {
        "probs": str(out_dir / "hmm_probs.parquet"),
        "states": str(out_dir / "hmm_states.parquet"),
        "metrics": str(out_dir / "hmm_metrics.parquet"),
        "metadata": str(out_dir / "hmm_metadata.json"),
    }


def build_hmm_standardized_for_ticker(ticker: str, n_states: int = 2, train_window_years: int = 5, random_seed: int = 42) -> Dict[str, str]:
    """Standardized offline HMM precompute with nested paths and idempotent hashing.
    Writes under data/analytics/hmm/{T}/win5y/states{N}/.
    Returns dict with paths and 'skipped' flag if unchanged.
    """
    import numpy as np
    import pandas as pd

    out_dir = _std_out_dir(ticker, train_window_years, n_states)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _load_features_for_hmm(ticker)
    # training window last N years
    last_date = df["date"].max()
    start_cut = last_date - pd.DateOffset(years=int(train_window_years))
    df_win = df[df["date"] >= start_cut].reset_index(drop=True)

    meta_path = out_dir / "hmm_metadata.json"
    feature_names = ["ret_1d", "rv_20d"]
    inp_hash = _compute_input_hash(df_win, feature_names)
    if meta_path.exists():
        try:
            old = json.loads(meta_path.read_text())
            if old.get("input_hash") == inp_hash and int(old.get("n_states", 0)) == int(n_states) and int(old.get("train_window_years", 0)) == int(train_window_years):
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
        pd.DataFrame({"date": df_win["date"], "hmm_prob_bull": np.nan, "hmm_prob_bear": np.nan}).to_parquet(out_dir / "hmm_probs.parquet", index=False)
        pd.DataFrame({"date": df_win["date"], "hmm_state_name": pd.NA, "hmm_state": pd.NA}).to_parquet(out_dir / "hmm_states.parquet", index=False)
        pd.DataFrame({"metric": [], "value": []}).to_parquet(out_dir / "hmm_metrics.parquet", index=False)
        meta = {
            "ticker": ticker,
            "n_states": int(n_states),
            "train_window_years": int(train_window_years),
            "random_seed": int(random_seed),
            "generated_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_columns": feature_names,
            "rows": int(len(df_win)),
            "input_hash": inp_hash,
            "insufficient_samples": True,
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        return {
            "probs": str(out_dir / "hmm_probs.parquet"),
            "states": str(out_dir / "hmm_states.parquet"),
            "metrics": str(out_dir / "hmm_metrics.parquet"),
            "metadata": str(meta_path),
            "skipped": False,
        }

    # Fit as before using windowed data
    X = df_win[feature_names].to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    model = _fit_hmm_gaussian(X, n_states=int(n_states), random_seed=int(random_seed))

    post = model.predict_proba(X)
    name_map, mean_returns = _map_state_names_by_mean_return(model, feature_names)
    z = post.argmax(axis=1)
    z_named = [name_map[int(si)] for si in z]

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

    probs_df.to_parquet(out_dir / "hmm_probs.parquet", index=False)
    states_df.to_parquet(out_dir / "hmm_states.parquet", index=False)
    metrics_df.to_parquet(out_dir / "hmm_metrics.parquet", index=False)
    meta = {
        "ticker": ticker,
        "n_states": int(n_states),
        "train_window_years": int(train_window_years),
        "random_seed": int(random_seed),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_columns": feature_names,
        "rows": int(len(df_win)),
        "input_hash": inp_hash,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return {
        "probs": str(out_dir / "hmm_probs.parquet"),
        "states": str(out_dir / "hmm_states.parquet"),
        "metrics": str(out_dir / "hmm_metrics.parquet"),
        "metadata": str(meta_path),
        "skipped": False,
    }
