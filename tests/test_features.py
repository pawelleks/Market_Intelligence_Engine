import pandas as pd
from pathlib import Path
import numpy as np
import pytest

from mie_lib.utils.paths import RAW_DIR, FEATURES_DIR
from mie_lib.features.build_features import build_features_for_ticker


def make_synthetic_raw(ticker: str, days: int = 400):
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq='B')
    # create simple price series
    price = 100 + np.cumsum(np.random.normal(0, 0.5, size=len(dates)))
    df = pd.DataFrame({
        'date': dates,
        'open': price + np.random.normal(0, 0.1, size=len(dates)),
        'high': price + np.random.normal(0.1, 0.2, size=len(dates)),
        'low': price - np.random.normal(0.1, 0.2, size=len(dates)),
        'close': price + np.random.normal(0, 0.1, size=len(dates)),
        'adj_close': price,
        'volume': np.random.randint(1_000_000, 5_000_000, size=len(dates)),
        'ticker': ticker,
    })
    p = RAW_DIR / f"{ticker}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return p


def test_build_features_full(tmp_path, features_tmp_dirs):
    ticker = "TEST"
    # create synthetic raw
    p = make_synthetic_raw(ticker)

    res = build_features_for_ticker(ticker, mode='full', lookback=90, write_csv=False)
    assert res.get('rows', None) is not None
    p_feat = FEATURES_DIR / f"{ticker}.parquet"
    assert p_feat.exists()

    df_feat = pd.read_parquet(p_feat)
    # check required columns
    required = [
        'date','ticker','ret_1d','log_ret_1d','rv_20d','rv_60d','sma_20','sma_50','sma_200',
        'ema_20','ema_50','ema_200','ma_ratio_20_50','ma_ratio_50_200','ma_ratio_20_200',
        'dist_from_50dma','dist_from_200dma','dow','month','as_of','data_version'
    ]
    for c in required:
        assert c in df_feat.columns, f"Missing column {c}"

    # enforce presence and dtype for canonical columns
    assert 'ret_1d' in df_feat.columns and 'rv_20d' in df_feat.columns
    assert str(df_feat['ret_1d'].dtype) == 'float32', f"ret_1d dtype expected float32, got {df_feat['ret_1d'].dtype}"
    assert str(df_feat['rv_20d'].dtype) == 'float32', f"rv_20d dtype expected float32, got {df_feat['rv_20d'].dtype}"

    # dates sorted
    assert df_feat['date'].is_monotonic_increasing

    # NaNs only in warm-up region for sma_200 (first ~200 rows may be NaN)
    # ensure that after index 200 there are no NaNs in sma_200
    if len(df_feat) > 210:
        assert not df_feat['sma_200'].iloc[200:].isna().any()

    # Numeric dtypes should be float32 for feature columns (exclude meta)
    numeric_cols = [
        'ret_1d','log_ret_1d','rv_20d','rv_60d','sma_20','sma_50','sma_200',
        'ema_20','ema_50','ema_200','ma_ratio_20_50','ma_ratio_50_200','ma_ratio_20_200',
        'dist_from_50dma','dist_from_200dma'
    ]
    for col in numeric_cols:
        if col in df_feat.columns:
            assert str(df_feat[col].dtype) == 'float32', f"Column {col} is not float32, got {df_feat[col].dtype}"

    # Clean up
    p.unlink(missing_ok=True)
    p_feat.unlink(missing_ok=True)


@pytest.fixture
def features_tmp_dirs(tmp_path):
    (tmp_path / "data" / "features").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_update_features_incremental(features_tmp_dirs):
    ticker = "TEST2"
    # create initial synthetic raw with 300 business days
    p = make_synthetic_raw(ticker, days=300)

    # full build
    res_full = build_features_for_ticker(ticker, mode='full', lookback=90, write_csv=False)
    assert res_full.get('rows', None) is not None
    p_feat = FEATURES_DIR / f"{ticker}.parquet"
    assert p_feat.exists()
    df_feat_before = pd.read_parquet(p_feat)
    rows_before = len(df_feat_before)

    # Append 5 new business days to raw
    raw_df = pd.read_parquet(RAW_DIR / f"{ticker}.parquet")
    last_date = pd.to_datetime(raw_df['date']).max()
    new_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=5)
    last_price = raw_df['adj_close'].iloc[-1]
    new_price = last_price + np.cumsum(np.random.normal(0, 0.5, size=len(new_dates)))
    new_rows = pd.DataFrame({
        'date': new_dates,
        'open': new_price + np.random.normal(0, 0.1, size=len(new_dates)),
        'high': new_price + np.random.normal(0.1, 0.2, size=len(new_dates)),
        'low': new_price - np.random.normal(0.1, 0.2, size=len(new_dates)),
        'close': new_price + np.random.normal(0, 0.1, size=len(new_dates)),
        'adj_close': new_price,
        'volume': np.random.randint(1_000_000, 5_000_000, size=len(new_dates)),
        'ticker': ticker,
    })
    appended = pd.concat([raw_df, new_rows], ignore_index=True).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    appended.to_parquet(RAW_DIR / f"{ticker}.parquet", index=False)

    # incremental update
    res_update = build_features_for_ticker(ticker, mode='update', lookback=90, write_csv=False)
    assert res_update.get('rows', None) is not None
    df_feat_after = pd.read_parquet(p_feat)
    rows_after = len(df_feat_after)

    # rows should increase by number of new dates
    assert rows_after == rows_before + len(new_rows)

    # No NaNs in ret_1d beyond warm-up (first row may be NaN)
    if rows_after > 10:
        assert not df_feat_after['ret_1d'].iloc[1:].isna().any()

    # re-run update (idempotent) - no new raw data
    res_update2 = build_features_for_ticker(ticker, mode='update', lookback=90, write_csv=False)
    df_feat_after2 = pd.read_parquet(p_feat)
    assert len(df_feat_after2) == rows_after

    # Cleanup
    (RAW_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    (FEATURES_DIR / f"{ticker}.parquet").unlink(missing_ok=True)


def test_schema_enforcement_missing_or_wrong_dtype(tmp_path, features_tmp_dirs):
    # Create a bogus features file missing rv_20d to ensure validator fails
    ticker = "BAD1"
    from mie_lib.features.build_features import _write_features, _validate_feature_df
    dates = pd.bdate_range("2021-01-01", periods=30)
    df = pd.DataFrame({
        'date': dates,
        'ticker': ticker,
        'ret_1d': pd.Series([0.0]*30, dtype='float32'),
        'log_ret_1d': pd.Series([0.0]*30, dtype='float32'),
        'rv_60d': pd.Series([0.0]*30, dtype='float32'),
        'sma_20': pd.Series([0.0]*30, dtype='float32'),
        'sma_50': pd.Series([0.0]*30, dtype='float32'),
        'sma_200': pd.Series([0.0]*30, dtype='float32'),
        'ema_20': pd.Series([0.0]*30, dtype='float32'),
        'ema_50': pd.Series([0.0]*30, dtype='float32'),
        'ema_200': pd.Series([0.0]*30, dtype='float32'),
        'ma_ratio_20_50': pd.Series([0.0]*30, dtype='float32'),
        'ma_ratio_50_200': pd.Series([0.0]*30, dtype='float32'),
        'ma_ratio_20_200': pd.Series([0.0]*30, dtype='float32'),
        'dist_from_50dma': pd.Series([0.0]*30, dtype='float32'),
        'dist_from_200dma': pd.Series([0.0]*30, dtype='float32'),
        'dow': dates.weekday,
        'month': dates.month,
        'as_of': ["2021-01-01T00:00:00+00:00"]*30,
        'data_version': ['features_v1.0.0']*30,
    })
    # Should fail validation due to missing rv_20d
    try:
        _validate_feature_df(df)
        assert False, "Validator should fail when rv_20d is missing"
    except ValueError as e:
        assert 'rv_20d' in str(e)

    # Wrong dtype
    df['rv_20d'] = pd.Series([0.0]*30, dtype='float64')
    try:
        _validate_feature_df(df)
        assert False, "Validator should fail when dtype is not float32"
    except TypeError as e:
        assert 'float32' in str(e)
