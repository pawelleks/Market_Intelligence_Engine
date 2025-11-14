from pathlib import Path
import pandas as pd
from mie_lib.analytics.seasonality.preprocess import build_seasonality_base, SEAS_BASE_DIR


def test_seasonality_preprocess_basic(tmp_path, monkeypatch):
    # Create minimal features parquet
    base = tmp_path/"data"
    feat_dir = base/"features"
    raw_dir = base/"raw"
    seas_dir = base/"seasonality"/"base"
    feat_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    seas_dir.mkdir(parents=True, exist_ok=True)

    # 5 rows synthetic close
    dates = pd.date_range("2020-01-01", periods=5, freq="B", tz="UTC")
    df = pd.DataFrame({"date": dates, "ticker": "TST", "close": [100,101,100,102,103]})
    p = feat_dir/"TST.parquet"
    df.to_parquet(p, index=False)

    # Monkeypatch module paths to tmp
    import mie_lib.analytics.seasonality.preprocess as mod
    mod.FEATURES_DIR = feat_dir
    mod.RAW_DIR = raw_dir
    mod.SEAS_BASE_DIR = seas_dir

    out = build_seasonality_base("TST")
    assert out.exists()
    res = pd.read_parquet(out)
    # Columns
    expect_cols = {"ticker","date","year","doy_trading","open","high","low","close","r","lr"}
    assert expect_cols.issubset(set(res.columns))
    # doy_trading resets per year
    assert res.loc[0, "doy_trading"] == 1
    # no duplicate dates
    assert not res["date"].duplicated().any()
