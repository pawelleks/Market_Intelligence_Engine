from pathlib import Path
import pandas as pd
import numpy as np
import importlib

# Import the page module (import-safe, does not execute main())
markov_page = importlib.import_module("mie_lib.pages.01_Markov_Chain")
from mie_lib.analytics.markov.states_model import classify_tri_state, classify_binary_state


def _make_features(tmp_path: Path, ticker: str, rets: list[float]):
    dates = pd.bdate_range("2024-01-01", periods=len(rets))
    price = 100 * (1 + pd.Series(rets)).cumprod()
    df = pd.DataFrame({
        "date": dates,
        "open": price.values,
        "high": price.values,
        "low": price.values,
        "close": price.values,
        "adj_close": price.values,
        "volume": np.random.randint(1000, 5000, size=len(rets)),
        "ret_1d": rets,
        "ticker": ticker,
    })
    feat_dir = tmp_path / "data" / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(feat_dir / f"{ticker}.parquet", index=False)
    return df


def test_classify_tri_state_boundaries():
    # threshold 10 bps -> T=0.001
    assert classify_tri_state(0.0010, 10) == "U"  # inclusive upper bound
    assert classify_tri_state(-0.0010, 10) == "D"  # inclusive lower bound
    assert classify_tri_state(0.000999, 10) == "N"
    assert classify_tri_state(-0.000999, 10) == "N"
    # higher threshold -> classify neutral
    assert classify_tri_state(0.0010, 15) == "N"


def test_previous_state_anchor_updates_with_threshold(tmp_path, monkeypatch):
    # Prepare synthetic features with last return exactly +0.001
    ticker = "TST"
    df = _make_features(tmp_path, ticker, rets=[0.0002, -0.0003, 0.0010])
    # Monkeypatch DATA root used inside page helper to point to tmp sandbox
    monkeypatch.chdir(tmp_path)
    # Provide window ISO bounds
    w_start = df["date"].min().date().isoformat()
    w_end = df["date"].max().date().isoformat()
    # threshold 10 bps -> expect Green ('U','G')
    raw_10, disp_10 = markov_page._select_previous_state_anchor(
        ticker=ticker,
        threshold_bps=10,
        window_key="1Y",
        window_start_iso=w_start,
        window_end_iso=w_end,
        state_mode="tri",
    )
    assert raw_10 == "U" and disp_10 == "G"
    # threshold 15 bps -> expect Neutral ('N','N')
    raw_15, disp_15 = markov_page._select_previous_state_anchor(
        ticker=ticker,
        threshold_bps=15,
        window_key="1Y",
        window_start_iso=w_start,
        window_end_iso=w_end,
        state_mode="tri",
    )
    assert raw_15 == "N" and disp_15 == "N"
    # negative boundary test for Red
    df2 = _make_features(tmp_path, ticker, rets=[0.0002, -0.0010])
    w_start2 = df2["date"].min().date().isoformat()
    w_end2 = df2["date"].max().date().isoformat()
    raw_red, disp_red = markov_page._select_previous_state_anchor(
        ticker=ticker,
        threshold_bps=10,
        window_key="1Y",
        window_start_iso=w_start2,
        window_end_iso=w_end2,
        state_mode="tri",
    )
    assert raw_red == "D" and disp_red == "R"
