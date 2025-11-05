import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.build_features import (
    build_features_for_ticker,
    FEATURES_DIR,
    RAW_DIR,
    _get_windows,
)


def _make_synthetic_raw(ticker: str, days: int = 400) -> Path:
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="B")
    price = 100 + np.cumsum(np.random.normal(0, 0.5, size=len(dates)))
    df = pd.DataFrame(
        {
            "date": dates,
            "open": price + np.random.normal(0, 0.1, size=len(dates)),
            "high": price + np.random.normal(0.1, 0.2, size=len(dates)),
            "low": price - np.random.normal(0.1, 0.2, size=len(dates)),
            "close": price + np.random.normal(0, 0.1, size=len(dates)),
            "adj_close": price,
            "volume": np.random.randint(1_000_000, 5_000_000, size=len(dates)),
            "ticker": ticker,
        }
    )
    p = RAW_DIR / f"{ticker}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return p


def _hash_last_n_rows(df: pd.DataFrame, n: int = 10) -> str:
    # Hash only stable columns; exclude volatile metadata like 'as_of'
    cols = [c for c in df.columns if c != "as_of"]
    tail_csv = df[cols].tail(n).to_csv(index=False)
    return hashlib.sha256(tail_csv.encode("utf-8")).hexdigest()


def test_update_overlap_and_idempotency(tmp_path):
    ticker = "TESTU"

    # 1) Create synthetic raw base
    _make_synthetic_raw(ticker, days=400)

    # FULL build
    res_full = build_features_for_ticker(ticker, mode="full", lookback=90, write_csv=False)
    assert res_full.get("rows") is not None

    p_feat = FEATURES_DIR / f"{ticker}.parquet"
    assert p_feat.exists()
    df_before = pd.read_parquet(p_feat)
    rows_before = len(df_before)

    # Keep a checksum of the last 10 rows after full build
    checksum_before = _hash_last_n_rows(df_before, 10)

    # 2) Append 45 new business days to raw
    raw_df = pd.read_parquet(RAW_DIR / f"{ticker}.parquet")
    last_date = pd.to_datetime(raw_df["date"]).max()
    new_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=45)
    last_price = raw_df["adj_close"].iloc[-1]
    new_price = last_price + np.cumsum(np.random.normal(0, 0.6, size=len(new_dates)))
    new_rows = pd.DataFrame(
        {
            "date": new_dates,
            "open": new_price + np.random.normal(0, 0.1, size=len(new_dates)),
            "high": new_price + np.random.normal(0.1, 0.2, size=len(new_dates)),
            "low": new_price - np.random.normal(0.1, 0.2, size=len(new_dates)),
            "close": new_price + np.random.normal(0, 0.1, size=len(new_dates)),
            "adj_close": new_price,
            "volume": np.random.randint(1_000_000, 5_000_000, size=len(new_dates)),
            "ticker": ticker,
        }
    )
    appended = (
        pd.concat([raw_df, new_rows], ignore_index=True)
        .drop_duplicates(subset=["date"])  # just in case
        .sort_values("date")
        .reset_index(drop=True)
    )
    appended.to_parquet(RAW_DIR / f"{ticker}.parquet", index=False)

    # 3) UPDATE with lookback=90
    res_update = build_features_for_ticker(ticker, mode="update", lookback=90, write_csv=False)
    assert res_update.get("rows") is not None

    df_after = pd.read_parquet(p_feat)
    rows_after = len(df_after)

    # Schema/dates
    assert df_after["date"].is_monotonic_increasing
    assert not df_after["date"].duplicated().any()

    # Rows increased roughly by number of new dates appended
    assert rows_after == rows_before + len(new_rows)

    # No NaNs in ret_1d beyond global warm-up (max rolling window)
    windows = _get_windows()
    max_window = max(
        max(windows.get("sma", [0])) if windows.get("sma") else 0,
        max(windows.get("ema", [0])) if windows.get("ema") else 0,
        max(windows.get("vol", [0])) if windows.get("vol") else 0,
    )
    if rows_after > max_window + 1:
        assert not df_after["ret_1d"].iloc[max_window + 1 :].isna().any()

    # 4) UPDATE again with no new data (idempotent)
    res_update2 = build_features_for_ticker(ticker, mode="update", lookback=90, write_csv=False)
    df_after2 = pd.read_parquet(p_feat)

    # Row count unchanged
    assert len(df_after2) == rows_after

    # Last 10 rows checksum unchanged
    checksum_after = _hash_last_n_rows(df_after, 10)
    checksum_after2 = _hash_last_n_rows(df_after2, 10)
    assert checksum_after == checksum_after2

    # Cleanup
    (RAW_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    (FEATURES_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
