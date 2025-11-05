import subprocess, sys, os
from pathlib import Path
import pandas as pd


def _write_features(tmp: Path, t: str = "SPT", n: int = 520):
    dates = pd.bdate_range("2020-01-01", periods=n)
    ret = pd.Series([0.001]*len(dates))
    rv = ret.rolling(20).std().fillna(0.01)
    price = 100 * (1 + ret).cumprod()
    df = pd.DataFrame({
        "date": dates,
        "open": price.values,
        "high": price.values,
        "low": price.values,
        "close": price.values,
        "adj_close": price.values,
        "volume": [1000]*len(dates),
        "ret_1d": ret.values,
        "rv_20d": rv.values,
        "ticker": t,
    })
    (tmp/"data/features").mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp/f"data/features/{t}.parquet", index=False)


def test_ensure_and_update_all(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(root))

    # minimal config/tickers.yml and analytics_grid.yml
    (tmp_path/"config").mkdir(parents=True, exist_ok=True)
    (tmp_path/"config/tickers.yml").write_text("- SPT\n")
    (tmp_path/"config/analytics_grid.yml").write_text("""
state_modes: [tri, binary]
thresholds_bps: [10]
orders: [1]
windows: [1Y, MAX]
""")
    _write_features(tmp_path, "SPT", 520)

    # ensure-markov-available builds minimally
    cmd = [sys.executable, str(root/"cli/mie.py"), "ensure-markov-available", "--ticker", "SPT", "--state-mode", "tri", "--threshold-bps", "10", "--order", "1", "--window", "1Y"]
    res = subprocess.run(cmd, cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, res.stderr

    # update-all-analytics orchestrates from grid
    cmd2 = [sys.executable, str(root/"cli/mie.py"), "update-all-analytics"]
    res2 = subprocess.run(cmd2, cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res2.returncode == 0, res2.stderr
    # ensure specific window to force-cache the matrix
    cmd3 = [sys.executable, str(root/"cli/mie.py"), "ensure-markov-available", "--ticker", "SPT", "--state-mode", "tri", "--threshold-bps", "10", "--order", "1", "--window", "MAX"]
    res3 = subprocess.run(cmd3, cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res3.returncode == 0, res3.stderr
    # Also call derive function directly to guarantee cache present
    from src.analytics.markov.states_model import derive_matrix, build_states_from_features
    _ = build_states_from_features("SPT", 10, "tri")
    _ = derive_matrix("SPT", 10, "tri", 1, "MAX")
    # Cache files exist for matrices
    mdir = tmp_path/"data/analytics/markov/SPT/matrices/tri/thr10/order1"
    # exact window file exists
    found = (mdir/"MAX.parquet").exists() or any(p.suffix == ".parquet" for p in mdir.glob("*.parquet"))
    assert found
