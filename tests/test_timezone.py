import pandas as pd
from datetime import timezone

from mie_lib.features.build_features import build_features_for_ticker, FEATURES_DIR, RAW_DIR


def _make_raw_one_day(ticker: str = "TZT"):
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=5, freq="B")
    prices = pd.Series(range(len(dates)), index=dates).astype(float) + 100.0
    df = pd.DataFrame({
        "date": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "adj_close": prices,
        "volume": 1000,
        "ticker": ticker,
    })
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW_DIR / f"{ticker}.parquet", index=False)


def test_as_of_timezone_serialization():
    ticker = "TZT"
    _make_raw_one_day(ticker)
    build_features_for_ticker(ticker, mode="full", lookback=10, write_csv=False)
    df_feat = pd.read_parquet(FEATURES_DIR / f"{ticker}.parquet")
    assert "as_of" in df_feat.columns
    # Expect timezone-aware ISO8601: contains 'Z' or '+00:00'
    as_of_str = str(df_feat.loc[0, "as_of"])  # string from parquet
    assert ("+00:00" in as_of_str) or (as_of_str.endswith("Z"))

    # Cleanup
    (RAW_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    (FEATURES_DIR / f"{ticker}.parquet").unlink(missing_ok=True)

