from __future__ import annotations
"""Build seasonality facts per ARCHITECT_BIBLE.
Offline-only; invoked via CLI mie build-seasonality-facts.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import yaml

SEAS_BASE_DIR = Path("data")/"seasonality"/"base"
SEAS_FACTS_DIR = Path("data")/"analytics"/"seasonality"
SEAS_FACTS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path("config")/"seasonality.yml"

DEFAULT_LOOKBACKS = [5,10,15,20,50,"ALL"]


def load_seasonality_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return yaml.safe_load(CONFIG_PATH.read_text()) or {}
        except Exception:
            return {}
    return {}


def _load_base(ticker: str) -> pd.DataFrame:
    p = SEAS_BASE_DIR / f"{ticker.upper()}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"Missing seasonality base {p}")
    df = pd.read_parquet(p)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


def _compute_facts(df: pd.DataFrame, lookback: str | int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = df.copy().sort_values("date")
    
    # Ensure derived columns exist
    if "year" not in d.columns:
        d["year"] = d["date"].dt.year
    if "doy_trading" not in d.columns:
        # Calculate trading day of year (1..252 approx)
        d["doy_trading"] = d.groupby("year")["date"].rank().astype(int)

    if lookback != "ALL":
        max_year = int(d["year"].max())
        try:
            L = int(lookback)
            d = d[d["year"] >= (max_year - L)]
        except Exception:
            pass
    # Filter out first row with NaN returns if present
    d = d.dropna(subset=["lr"]).copy()
    # Cumulative log path per year
    d["cum_lr"] = d.groupby("year")["lr"].cumsum()
    # Stats per trading day across years
    g = d.groupby("doy_trading")
    mean_ret = g["lr"].mean()
    median_ret = g["lr"].median()
    std_ret = g["lr"].std(ddof=0)
    hit_ratio = (g["lr"].apply(lambda s: (s>0).mean())).astype(float)

    mean_cum = g["cum_lr"].mean()
    std_cum = g["cum_lr"].std(ddof=0)
    q25_cum = g["cum_lr"].quantile(0.25)
    q75_cum = g["cum_lr"].quantile(0.75)

    out = pd.DataFrame({
        "ticker": d["ticker"].iloc[0],
        "lookback": str(lookback if lookback != "ALL" else "ALL"),
        "doy_trading": mean_ret.index,
        "mean_ret": mean_ret.values,
        "median_ret": median_ret.values,
        "std_ret": std_ret.values,
        "hit_ratio": hit_ratio.values,
        "mean_cum": mean_cum.values,
        "std_cum": std_cum.values,
        "q25_cum": q25_cum.values,
        "q75_cum": q75_cum.values,
    })
    # Cumulative values are log-based; convert to exp - 1 for path semantics if needed in UI later.
    return out


def build_facts_for_ticker(ticker: str, horizons=None, dry_run: bool=False) -> list[Path]:
    horizons = horizons or DEFAULT_LOOKBACKS
    base = _load_base(ticker)
    written = []
    rows = []
    for h in horizons:
        facts = _compute_facts(base, h)
        if facts.empty:
            continue
        rows.append(facts)
    if not rows:
        return []
    full = pd.concat(rows, ignore_index=True)
    # Enforce dtypes
    float_cols = [c for c in ["mean_ret","median_ret","std_ret","hit_ratio","mean_cum","std_cum","q25_cum","q75_cum"] if c in full.columns]
    for c in float_cols:
        full[c] = full[c].astype("float32")
    # Atomic write
    out_dir = SEAS_FACTS_DIR / ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir/"facts.parquet.tmp"
    final = out_dir/"facts.parquet"
    if not dry_run:
        full.to_parquet(tmp, index=False)
        tmp.replace(final)
        written.append(final)
    return written

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lookbacks", default="")
    a = ap.parse_args()
    looks = [x.strip() for x in a.lookbacks.split(",") if x.strip()] if a.lookbacks else None
    res = build_facts_for_ticker(a.ticker, horizons=looks, dry_run=a.dry_run)
    print({"written": [str(p) for p in res]})

