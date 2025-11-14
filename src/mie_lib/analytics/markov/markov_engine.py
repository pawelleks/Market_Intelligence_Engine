from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
from typing import TYPE_CHECKING
from datetime import datetime, timezone
import json

if TYPE_CHECKING:  # hint-only imports to satisfy linters without runtime cost
    import pandas as pd  # noqa: F401
    import numpy as np  # noqa: F401

from mie_lib.utils.logging import get_logger
from mie_lib.utils.paths import FEATURES_DIR, MARKOV_DIR

LOG = get_logger("markov")

ANALYTICS_DIR = MARKOV_DIR


@dataclass
class MarkovConfig:
    order: int = 1
    state_mode: str = "tri"  # "tri" or "binary"
    threshold_bps: int = 10
    min_samples_per_state: int = 30

    @property
    def threshold(self) -> float:
        return float(self.threshold_bps) / 10000.0

    @property
    def possible_states(self) -> List[str]:
        if self.state_mode == "tri":
            return ["U", "N", "D"]
        return ["U", "D"]


def _load_features(ticker: str):
    import pandas as pd

    p = FEATURES_DIR / f"{ticker}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"Features parquet not found for {ticker}: {p}")
    df = pd.read_parquet(p)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    if "ret_1d" not in df.columns:
        raise ValueError("ret_1d column missing in features")
    return df


# NEW unified robust loader (per ARCHITECT_BIBLE) used by UI & state builders
# Returns DataFrame or None without raising for missing/invalid files.

def load_features_for_markov(ticker: str):
    """Load features parquet for Markov usage.

    Behavior:
    - Path: data/features/{ticker}.parquet
    - If missing => return None
    - Ensure 'date' parsed (naive), ascending sort, drop duplicate dates keeping last
    - Ensure 'ret_1d'. If absent but lr/log_ret_1d present, derive: ret_1d = exp(lr) - 1
    - Drop rows with NaN ret_1d
    - Return DataFrame or None if empty after cleaning
    """
    import pandas as pd
    p = FEATURES_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    # Derive ret_1d if missing
    if "ret_1d" not in df.columns:
        lr_col = None
        for c in ["lr", "log_ret_1d", "lr_1d"]:
            if c in df.columns:
                lr_col = c
                break
        if lr_col is not None:
            try:
                df["ret_1d"] = (df[lr_col].astype(float)).apply(lambda x: (float("nan") if pd.isna(x) else (pow(2.718281828459045, x) - 1.0)))
            except Exception:
                pass
    # Final validation
    if "ret_1d" not in df.columns:
        return None  # cannot proceed without primary return column
    df["ret_1d"] = pd.to_numeric(df["ret_1d"], errors="coerce").astype("float64")
    df = df.dropna(subset=["ret_1d"]).reset_index(drop=True)
    if df.empty:
        return None
    return df


# Unified classification imports
from .states_model import classify_tri_state, classify_binary_state  # local import to avoid circular at module import time


def _states_from_returns(ret: "pd.Series", cfg: MarkovConfig) -> "pd.Series":
    import pandas as pd

    # Vectorized apply using unified helpers to ensure boundary consistency
    mode = cfg.state_mode
    thr = cfg.threshold_bps
    if mode == "tri":
        states = ret.apply(lambda r: classify_tri_state(r, thr))
    else:
        states = ret.apply(lambda r: classify_binary_state(r, thr))
    return states


def _context_series(states: "pd.Series", order: int) -> "pd.Series":
    import pandas as pd

    if order < 1:
        raise ValueError("order must be >=1")
    s = states.astype(str)
    if order == 1:
        return s.copy()
    parts = [s.shift(i) for i in range(order - 1, -1, -1)]
    # join parts row-wise to form context strings
    context = pd.concat(parts, axis=1).astype(str).apply(lambda row: "".join(row.values.tolist()), axis=1)
    # Set insufficient history to NA
    context.iloc[: order - 1] = pd.NA
    return context


def _compute_counts_and_probs(context: "pd.Series", next_state: "pd.Series", cfg: MarkovConfig):
    import pandas as pd
    import numpy as np

    # Consider only rows where both context and next_state are non-null
    mask = context.notna() & next_state.notna()
    ctx = context[mask]
    nxt = next_state[mask]

    # Counts per (context, next_state)
    ct_table = pd.crosstab(ctx, nxt)
    # Ensure all state columns present
    for st in cfg.possible_states:
        if st not in ct_table.columns:
            ct_table[st] = 0
    # Reorder columns and name the index
    ct_table = ct_table.reindex(columns=cfg.possible_states, fill_value=0)
    ct_table.index.name = "context"
    ct = ct_table.reset_index()

    # Raw counts total per row
    ct["total_count"] = ct[cfg.possible_states].sum(axis=1)

    # Laplace smoothing: +1 to each state count
    smoothed = ct.copy()
    for st in cfg.possible_states:
        smoothed[st] = smoothed[st].astype(float) + 1.0

    denom = smoothed[cfg.possible_states].sum(axis=1)
    probs = smoothed[cfg.possible_states].div(denom, axis=0)

    # Build probability frame with explicit columns
    prob_cols = {}
    prob_cols["U"] = "mc_prob_up"
    if "N" in cfg.possible_states:
        prob_cols["N"] = "mc_prob_neutral"
    prob_cols["D"] = "mc_prob_down"

    prob_df = pd.DataFrame({"context": ct["context"]})
    for st, colname in prob_cols.items():
        prob_df[colname] = probs[st].astype(float)

    counts_df = ct[["context"] + cfg.possible_states + ["total_count"]].copy()
    counts_df = counts_df.rename(columns={"U": "count_up", "D": "count_down", "N": "count_neutral"})
    return counts_df, prob_df


def _predictions_for_dates(dates: "pd.Series", contexts: "pd.Series", prob_df, counts_df, cfg: MarkovConfig):
    import pandas as pd

    # Map context -> probabilities
    prob_map = prob_df.set_index("context").to_dict(orient="index")
    cnt_map = counts_df.set_index("context")["total_count"].to_dict()

    rows = []
    for date_val, ctx in zip(dates, contexts):
        if pd.isna(ctx):
            continue
        rec = {"date": date_val}
        probs = prob_map.get(ctx)
        if not probs:
            # unseen context, uniform with smoothing effect (all states equal)
            if cfg.state_mode == "tri":
                mc_neutral = float("nan")
                rec.update({"mc_prob_up_next": 1 / 3, "mc_prob_neutral_next": 1 / 3, "mc_prob_down_next": 1 / 3})
            else:
                rec.update({"mc_prob_up_next": 0.5, "mc_prob_down_next": 0.5})
            total = 0
        else:
            # rename columns from prob_df to next_*
            if cfg.state_mode == "tri":
                rec["mc_prob_up_next"] = float(probs.get("mc_prob_up", 0.0))
                rec["mc_prob_neutral_next"] = float(probs.get("mc_prob_neutral", 0.0))
                rec["mc_prob_down_next"] = float(probs.get("mc_prob_down", 0.0))
            else:
                rec["mc_prob_up_next"] = float(probs.get("mc_prob_up", 0.0))
                rec["mc_prob_down_next"] = float(probs.get("mc_prob_down", 0.0))
            total = int(cnt_map.get(ctx, 0))
        rec["context"] = ctx
        rec["low_confidence"] = bool(total < int(cfg.min_samples_per_state))
        rows.append(rec)

    if not rows:
        return None
    pred = pd.DataFrame(rows)
    pred = pred.sort_values("date").reset_index(drop=True)
    return pred


def build_markov_for_ticker(ticker: str, cfg: MarkovConfig) -> Dict[str, str]:
    import pandas as pd

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = ANALYTICS_DIR / f"{ticker}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Use unified loader (returns None if missing) and fallback to legacy strict loader for backward compatibility
    df = load_features_for_markov(ticker)
    if df is None:
        try:
            df = _load_features(ticker)
        except Exception as e:
            raise FileNotFoundError(f"Cannot load features for {ticker}: {e}")

    # compute states
    states = _states_from_returns(df["ret_1d"], cfg)
    # Build context for this order
    ctx = _context_series(states, cfg.order)

    # Save states
    states_df = pd.DataFrame({
        "date": df["date"],
        "mc_state_today": states,
        "mc_state_window": ctx,
    })
    states_df.to_parquet(out_dir / "states.parquet", index=False)

    # For transition counts/probs, we consider pairs (context_t, state_{t+1}) for t with full context and not last row
    next_states = states.shift(-1)
    counts_df, prob_df = _compute_counts_and_probs(ctx, next_states, cfg)

    # Save counts and probability matrices for given order
    counts_df.to_parquet(out_dir / f"counts_order{cfg.order}.parquet", index=False)
    prob_df.to_parquet(out_dir / f"matrix_order{cfg.order}.parquet", index=False)

    # Build predictions for all dates with context (including last date)
    pred_df = _predictions_for_dates(df["date"], ctx, prob_df, counts_df, cfg)
    if pred_df is None:
        pred_df = pd.DataFrame(columns=["date"])  # empty
    pred_df.to_parquet(out_dir / "predictions.parquet", index=False)

    # Metadata
    meta = {
        "ticker": ticker,
        "order": int(cfg.order),
        "state_mode": cfg.state_mode,
        "threshold_bps": int(cfg.threshold_bps),
        "min_samples_per_state": int(cfg.min_samples_per_state),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_features_path": str(FEATURES_DIR / f"{ticker}.parquet"),
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    LOG.info("Markov outputs written for %s to %s", ticker, out_dir)
    # Legacy compatibility write (tests expect matrix_order{order}.parquet at root ticker dir)
    legacy_matrix = out_dir / f"matrix_order{cfg.order}.parquet"
    if not legacy_matrix.exists():
        try:
            prob_path = out_dir / f"matrix_order{cfg.order}.parquet"
            if prob_path.exists():
                pass  # already same path
        except Exception:
            LOG.warning("legacy matrix write skipped for %s order=%s", ticker, cfg.order)
    return {
        "out_dir": str(out_dir),
        "states": str(out_dir / "states.parquet"),
        "matrix": str(out_dir / f"matrix_order{cfg.order}.parquet"),
        "counts": str(out_dir / f"counts_order{cfg.order}.parquet"),
        "predictions": str(out_dir / "predictions.parquet"),
        "metadata": str(out_dir / "metadata.json"),
    }


def build_markov_order_sweep(
    ticker: str,
    orders: list[int],
    state_mode: str = "tri",
    threshold_bps: int = 10,
    min_samples_per_state: int = 30,
) -> str:
    """Run an order sweep for the given ticker and write a compact CSV with latest-context forecasts.

    Returns the path to the written CSV.
    """
    import pandas as pd
    import numpy as np

    # Ensure output dir
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = ANALYTICS_DIR / f"{ticker}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load features
    df = _load_features(ticker)

    # Validate orders
    orders = sorted({int(o) for o in orders if int(o) >= 1 and int(o) <= 10})
    if not orders:
        raise ValueError("orders must contain integers in [1, 10]")

    rows = []
    for k in orders:
        cfg = MarkovConfig(order=k, state_mode=state_mode, threshold_bps=threshold_bps, min_samples_per_state=min_samples_per_state)
        # states and context
        states = _states_from_returns(df["ret_1d"], cfg)
        ctx = _context_series(states, cfg.order)
        # counts and matrix
        next_states = states.shift(-1)
        counts_df, prob_df = _compute_counts_and_probs(ctx, next_states, cfg)
        # predictions per date
        preds = _predictions_for_dates(df["date"], ctx, prob_df, counts_df, cfg)

        # Latest date with valid context
        if preds is None or preds.empty:
            # No valid contexts
            latest_date = df["date"].max()
            latest_context = None
            if state_mode == "tri":
                mc_up = mc_neutral = mc_down = np.nan
            else:
                mc_up = mc_down = np.nan
                mc_neutral = float("nan")
            support = 0
            valid_contexts = 0
        else:
            latest_row = preds.iloc[-1]
            latest_date = latest_row["date"]
            latest_context = latest_row.get("context")
            if state_mode == "tri":
                mc_up = float(latest_row.get("mc_prob_up_next", np.nan))
                mc_neutral = float(latest_row.get("mc_prob_neutral_next", np.nan))
                mc_down = float(latest_row.get("mc_prob_down_next", np.nan))
            else:
                mc_up = float(latest_row.get("mc_prob_up_next", np.nan))
                mc_down = float(latest_row.get("mc_prob_down_next", np.nan))
                mc_neutral = float("nan")
            # support count for latest context
            if latest_context is not None and not counts_df.empty:
                match = counts_df[counts_df["context"] == latest_context]
                support = int(match["total_count"].iloc[0]) if not match.empty else 0
            else:
                support = 0
            # coverage
            valid_contexts = preds.shape[0]

        total_after_warmup = max(0, len(df) - (cfg.order - 1))
        coverage = float(valid_contexts) / total_after_warmup if total_after_warmup > 0 else 0.0
        coverage = min(max(coverage, 0.0), 1.0)
        low_conf = bool(support < int(cfg.min_samples_per_state))

        rec = {
            "ticker": ticker,
            "order": int(cfg.order),
            "state_mode": cfg.state_mode,
            "threshold_bps": int(cfg.threshold_bps),
            "latest_date": latest_date,
            "latest_context": latest_context,
            "support_count": int(support),
            "coverage_pct": float(coverage),
            "low_confidence": low_conf,
        }
        if state_mode == "tri":
            rec.update({
                "mc_prob_up_next": mc_up,
                "mc_prob_neutral_next": mc_neutral,
                "mc_prob_down_next": mc_down,
            })
        else:
            rec.update({
                "mc_prob_up_next": mc_up,
                "mc_prob_down_next": mc_down,
            })
        rows.append(rec)

    # Build DataFrame with stable column ordering
    if state_mode == "tri":
        cols = [
            "ticker", "order", "state_mode", "threshold_bps", "latest_date", "latest_context",
            "mc_prob_up_next", "mc_prob_neutral_next", "mc_prob_down_next",
            "support_count", "coverage_pct", "low_confidence",
        ]
    else:
        cols = [
            "ticker", "order", "state_mode", "threshold_bps", "latest_date", "latest_context",
            "mc_prob_up_next", "mc_prob_down_next",
            "support_count", "coverage_pct", "low_confidence",
        ]

    sweep_df = pd.DataFrame(rows)
    sweep_df = sweep_df.sort_values("order").reset_index(drop=True)
    # ensure date is isoformat string for deterministic CSV
    if "latest_date" in sweep_df.columns:
        sweep_df["latest_date"] = pd.to_datetime(sweep_df["latest_date"]).dt.strftime("%Y-%m-%d")
    sweep_df = sweep_df.loc[:, cols]

    out_csv = out_dir / "order_sweep.csv"
    sweep_df.to_csv(out_csv, index=False)

    LOG.info("Markov order sweep written for %s orders=%s to %s", ticker, orders, out_csv)
    return str(out_csv)


# ---------------- Alignment helper for UI warnings ----------------

def get_markov_features_alignment(
    ticker: str,
    state_mode: str,
    threshold_bps: int,
    order: int,
    window_key: str,
) -> Dict[str, object]:
    """Compute basic alignment metadata between features and Markov analytics.

    Returns dict with keys:
      - features_last_date (str YYYY-MM-DD or None)
      - states_last_date (str YYYY-MM-DD or None)  # after window slice
      - lag_days (int)  # positive if features are ahead
      - is_lagging (bool)
      - details (dict) with raw paths where possible
    No exceptions are raised; failures return empty/None fields.
    """
    import pandas as pd
    from .states_model import states_for as _states_for
    from .states_model import _window_key_from_arg as _wk
    from .states_model import _slice_window as _slice

    try:
        # Features last date
        fdf = load_features_for_markov(ticker)
        feat_last = None
        if fdf is not None and not fdf.empty and "date" in fdf.columns:
            feat_last = pd.to_datetime(fdf["date"]).max()
        # States last date for given config (windowed)
        s_last = None
        try:
            sdf = _states_for(ticker.upper(), int(threshold_bps), state_mode.lower().strip())
            sdf = _slice(sdf, _wk(window_key))
            if not sdf.empty and "date" in sdf.columns:
                s_last = pd.to_datetime(sdf["date"]).max()
        except Exception:
            s_last = None
        # Compute lag in calendar days (approx; trading-day aware can be added later)
        lag = None
        if feat_last is not None and s_last is not None:
            lag = int((feat_last.normalize() - s_last.normalize()).days)
        is_lag = bool(lag is not None and lag > 0)
        return {
            "features_last_date": (feat_last.strftime("%Y-%m-%d") if isinstance(feat_last, pd.Timestamp) else None),
            "states_last_date": (s_last.strftime("%Y-%m-%d") if isinstance(s_last, pd.Timestamp) else None),
            "lag_days": (lag if lag is not None else 0),
            "is_lagging": is_lag,
            "details": {
                "features_path": str(FEATURES_DIR / f"{ticker}.parquet"),
                "states_path": str(ANALYTICS_DIR / ticker.upper() / f"states_thr{int(threshold_bps)}_{state_mode.lower().strip()}.parquet"),
                "window": str(window_key),
                "order": int(order),
            },
        }
    except Exception:
        return {
            "features_last_date": None,
            "states_last_date": None,
            "lag_days": 0,
            "is_lagging": False,
            "details": {},
        }


# === New grid matrix loader (UI consumption only; pure read, no compute) ===
# Per ARCHITECT_BIBLE: offline artifacts are read-only inside Streamlit.
# Path pattern: data/analytics/markov/{ticker}/matrices/{state_mode}/thr{threshold_bps}/order{order}/{window_key}.parquet
# Companion metadata file (if present): matrix_metadata.json inside the same order directory.

def load_markov_matrix_grid(
    ticker: str,
    state_mode: str,
    threshold_bps: int,
    order: int,
    window_key: str,
):
    """Load a precomputed Markov transition matrix from the grid directory structure.

    Returns (df, meta) where:
      - df is a pandas DataFrame or None if missing.
      - meta is a dict with keys: path, exists (bool), state_mode, threshold_bps, order, window, mtime (float), metadata_json (dict or {}).

    No analytics computation performed here. Strictly file I/O.
    Does not raise if file missing; returns (None, meta) with exists=False.
    """
    import pandas as pd, json

    sm = str(state_mode).strip().lower()
    win = str(window_key).strip().upper()
    thr_i = int(threshold_bps)
    ord_i = int(order)

    base_dir = ANALYTICS_DIR / ticker / "matrices" / sm / f"thr{thr_i}" / f"order{ord_i}"
    path = base_dir / f"{win}.parquet"
    meta_path = base_dir / "matrix_metadata.json"
    meta: Dict[str, object] = {
        "path": str(path),
        "exists": False,
        "state_mode": sm,
        "threshold_bps": thr_i,
        "order": ord_i,
        "window": win,
        "mtime": None,
        "metadata_json": {},
    }
    if not path.exists():
        return None, meta
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None, meta
    try:
        st_stat = path.stat()
        meta["mtime"] = float(st_stat.st_mtime)
        meta["exists"] = True
    except Exception:
        pass
    if meta_path.exists():
        try:
            meta_json = json.loads(meta_path.read_text())
            if isinstance(meta_json, dict):
                meta["metadata_json"] = meta_json
        except Exception:
            pass
    return df, meta

