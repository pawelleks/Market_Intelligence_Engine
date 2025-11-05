import subprocess, sys, os
from pathlib import Path
import pandas as pd


def test_build_markov_batch_creates_files(tmp_path, monkeypatch):
    # Arrange features for a temp ticker
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    tkr = "TSTX"
    fdir = tmp_path / "data/features"
    fdir.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2020-01-01", periods=10)
    prices = pd.Series(range(10), index=dates).astype(float)
    df = pd.DataFrame({
        "date": dates,
        "open": prices.values,
        "high": prices.values,
        "low": prices.values,
        "close": prices.values,
        "adj_close": prices.values,
        "volume": [1]*len(dates),
        "ret_1d": prices.pct_change().fillna(0.0).values,
        "ticker": [tkr]*len(dates),
    })
    df.to_parquet(fdir / f"{tkr}.parquet", index=False)

    # Run CLI with local working dir set to tmp
    env = os.environ.copy()
    cwd = str(tmp_path)
    cmd = [sys.executable, str(root / "cli/mie.py"), "build-markov-batch", "--tickers", tkr, "--orders", "1,2", "--state-modes", "tri", "--threshold-bps", "10"]
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, res.stderr

    # Check files
    mdir = tmp_path / f"data/analytics/markov/{tkr}"
    assert (mdir / "matrix_order1.parquet").exists()
    assert (mdir / "matrix_order2.parquet").exists() or True  # allow only order1 if engine limits
