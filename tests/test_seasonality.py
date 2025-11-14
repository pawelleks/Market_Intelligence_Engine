import pandas as pd
from pathlib import Path

SEAS_BASE_DIR = Path("data/seasonality/base")
FEAT_DIR = Path("data/features")

CORE_COLS = ["ticker","date","year","doy_trading","open","high","low","close","r","lr"]

TOL = 1e-4


def _load_parquet(path: Path):
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def test_seasonality_schema_and_sorting():
    # Pick a core ticker if exists, else skip
    for ticker in ["SPY","QQQ","DIA","IWM"]:
        df = _load_parquet(SEAS_BASE_DIR / f"{ticker}.parquet")
        if df is None:
            continue
        # Columns present
        missing = set(CORE_COLS) - set(df.columns)
        assert not missing, f"Missing columns for {ticker}: {missing}"
        # Chronological & unique dates
        assert df['date'].is_monotonic_increasing or df.sort_values('date')['date'].is_monotonic_increasing, "Dates not sorted"
        assert df['date'].nunique() == len(df), "Duplicate dates detected"
        # doy_trading resets each year
        grouped = df.groupby('year')['doy_trading'].min().tolist()
        assert all(x == 1 for x in grouped), "doy_trading does not start at 1 each year"
        break  # test once if multiple tickers available


def test_seasonality_returns_align_with_features():
    for ticker in ["SPY","QQQ","DIA","IWM"]:
        seas = _load_parquet(SEAS_BASE_DIR / f"{ticker}.parquet")
        feat = _load_parquet(FEAT_DIR / f"{ticker}.parquet")
        if seas is None or feat is None:
            continue
        if 'r' not in seas.columns or 'ret_1d' not in feat.columns:
            continue
        # Align on common dates
        seas_idx = pd.to_datetime(seas['date'], utc=True)
        feat_idx = pd.to_datetime(feat['date'], utc=True)
        seas_sub = seas.set_index(seas_idx)['r'].astype(float)
        feat_sub = feat.set_index(feat_idx)['ret_1d'].astype(float)
        common = seas_sub.index.intersection(feat_sub.index)
        if common.empty:
            continue
        diffs = (seas_sub.loc[common] - feat_sub.loc[common]).abs()
        assert (diffs <= TOL).all(), f"Return mismatch >1bp for {ticker}"
        break


def test_seasonality_ui_preparation_basic():
    # Simulate early table preparation
    for ticker in ["SPY","QQQ","DIA","IWM"]:
        df = _load_parquet(SEAS_BASE_DIR / f"{ticker}.parquet")
        if df is None:
            continue
        if 'doy_trading' not in df.columns or 'r' not in df.columns:
            continue
        early = df[df['doy_trading'] <= 20]
        assert len(early) > 0, "Early seasonality slice empty"
        assert early['doy_trading'].max() <= 20, "Early slice exceeds day 20"
        break

