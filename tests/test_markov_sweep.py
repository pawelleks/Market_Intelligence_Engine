import pandas as pd
import numpy as np
from pathlib import Path

from mie_lib.features.build_features import RAW_DIR, FEATURES_DIR, build_features_for_ticker
from mie_lib.analytics.markov.markov_engine import build_markov_order_sweep, ANALYTICS_DIR


def _make_features_for_test(ticker: str = "MKSW", days: int = 280):
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    price = 100 + np.cumsum(np.random.normal(0, 0.5, size=len(dates)))
    raw = pd.DataFrame(
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
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(RAW_DIR / f"{ticker}.parquet", index=False)
    build_features_for_ticker(ticker, mode="full", lookback=90, write_csv=False)


def test_markov_order_sweep_csv_and_probs():
    ticker = "MKSW"
    _make_features_for_test(ticker, days=280)

    path = build_markov_order_sweep(ticker, orders=[1, 2], state_mode="tri", threshold_bps=10, min_samples_per_state=5)
    out_csv = Path(path)
    assert out_csv.exists()

    df = pd.read_csv(out_csv)
    # exactly one row per K
    assert set(df["order"].tolist()) == {1, 2}
    assert df.shape[0] == 2
    # required columns
    assert "latest_date" in df.columns and "coverage_pct" in df.columns
    # coverage in [0,1]
    assert (df["coverage_pct"] >= 0).all() and (df["coverage_pct"] <= 1).all()

    # For tri mode, three prob columns and row sums approx 1
    prob_cols = ["mc_prob_up_next", "mc_prob_neutral_next", "mc_prob_down_next"]
    for col in prob_cols:
        assert col in df.columns
    s = df[prob_cols].sum(axis=1)
    assert np.all((np.abs(s - 1.0) <= 0.01) | df[prob_cols].isna().all(axis=1))
    assert (df[prob_cols] >= 0).all().all()

    # Idempotency
    path2 = build_markov_order_sweep(ticker, orders=[1, 2], state_mode="tri", threshold_bps=10, min_samples_per_state=5)
    assert Path(path).read_text() == Path(path2).read_text()

    # Cleanup
    (RAW_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    (FEATURES_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    out_dir = ANALYTICS_DIR / ticker
    for fn in ["order_sweep.csv"]:
        (out_dir / fn).unlink(missing_ok=True)
    try:
        out_dir.rmdir()
    except OSError:
        pass

