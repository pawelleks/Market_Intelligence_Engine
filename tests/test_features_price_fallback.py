import pandas as pd
from pathlib import Path

from mie_lib.features.build_features import _select_price_column, build_features_for_ticker


def test_select_price_column_prefers_adj_close(tmp_path, monkeypatch):
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10, freq='D'),
        'adj_close': [100 + i for i in range(10)],
        'close': [99 + i for i in range(10)],
    })
    col, series = _select_price_column(df)
    assert col == 'adj_close'
    assert series.iloc[0] == 100


def test_select_price_column_fallback_to_close(tmp_path, monkeypatch):
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10, freq='D'),
        'close': [50 + i for i in range(10)],
    })
    col, series = _select_price_column(df)
    assert col == 'close'


def test_build_features_uses_fallback_close(tmp_path, monkeypatch):
    # Redirect data directories to tmp
    monkeypatch.setattr('mie_lib.features.build_features.RAW_DIR', tmp_path/'raw')
    monkeypatch.setattr('mie_lib.features.build_features.FEATURES_DIR', tmp_path/'features')
    raw_dir = tmp_path/'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker = 'TSTX'
    df_raw = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=15, freq='D'),
        'close': [100 + i for i in range(15)],
        'volume': [1000]*15,
    })
    df_raw.to_parquet(raw_dir/f'{ticker}.parquet', index=False)
    res = build_features_for_ticker(ticker, mode='full', lookback=5, write_csv=False)
    assert res.get('parquet'), 'Features parquet path not returned'
    df_feat = pd.read_parquet(res['parquet'])
    assert 'ret_1d' in df_feat.columns
    # First non-NaN daily return should match pct change formula
    first_non_nan = df_feat['ret_1d'].dropna().iloc[0]
    assert first_non_nan == (101/100 - 1)

