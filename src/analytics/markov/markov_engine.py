from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, timezone
import json

from src.utils.logging import get_logger

LOG = get_logger("markov")

DATA_DIR = Path("data")
FEATURES_DIR = DATA_DIR / "features"
ANALYTICS_DIR = DATA_DIR / "analytics" / "markov"


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


def _states_from_returns(ret: "pd.Series", cfg: MarkovConfig) -> "pd.Series":
    import numpy as np
    import pandas as pd

    th = cfg.threshold
    if cfg.state_mode == "tri":
        states = pd.Series(np.where(ret > th, "U", np.where(ret < -th, "D", "N")), index=ret.index)
    else:
        # binary with deadband handled by sign fallback
        states = pd.Series(
            np.where(ret >= th, "U", np.where(ret <= -th, "D", np.where(ret >= 0, "U", "D"))),
            index=ret.index,
        )
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

    df = _load_features(ticker)
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
