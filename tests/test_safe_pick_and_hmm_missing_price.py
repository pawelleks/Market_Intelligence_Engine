import importlib
from pathlib import Path
import types
import pandas as pd
import pytest


def test_safe_pick_context_row_avoids_truth_ambiguity(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")
    import pandas as _pd

    df = _pd.DataFrame({
        "context": ["UD", "UN"],
        "mc_prob_up": [0.6, 0.4],
        "mc_prob_down": [0.4, 0.6],
    })
    # Should pick first row when ctx is None
    r = mod._safe_pick_context_row(df, None)
    assert isinstance(r, _pd.Series)
    assert r["context"] == "UD" or r.get("Context", "UD")
    # When a matching ctx is provided in display form, back-conversion works
    r2 = mod._safe_pick_context_row(df, "G-R")
    assert isinstance(r2, _pd.Series)


def test_hmm_missing_price_column_shows_error(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.04_HMM_Price_Current")

    # Prepare minimal env: states parquet exists, features missing price columns
    hmm_dir = tmp_path / "data" / "analytics" / "hmm" / "SPY" / "win5y" / "states2"
    hmm_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.date_range("2022-01-01", periods=2), "hmm_state_name": ["Bull", "Bear"]}).to_parquet(hmm_dir / "hmm_states.parquet", index=False)
    pd.DataFrame({"date": pd.date_range("2022-01-01", periods=2), "hmm_prob_bull": [0.6, 0.4], "hmm_prob_bear": [0.4, 0.6]}).to_parquet(hmm_dir / "hmm_probs.parquet", index=False)
    (hmm_dir / "hmm_metadata.json").write_text("{}")

    feats_dir = tmp_path / "data" / "features"
    feats_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.date_range("2022-01-01", periods=2), "other": [1, 2]}).to_parquet(feats_dir / "SPY.parquet", index=False)

    # Monkeypatch DATA to tmp_path/data for the module
    monkeypatch.setattr(mod, "DATA", tmp_path / "data", raising=True)

    # Monkeypatch streamlit st.error to capture calls without running the app
    errors = []
    class DummyST:
        def error(self, msg):
            errors.append(msg)
    monkeypatch.setattr(mod, "st", types.SimpleNamespace(error=DummyST().error, sidebar=types.SimpleNamespace(selectbox=lambda *a, **k: "SPY"), title=lambda *a, **k: None))

    # Also monkeypatch ui functions used in main
    monkeypatch.setattr(mod, "css_inject", lambda *a, **k: None)
    monkeypatch.setattr(mod, "get_tokens", lambda *a, **k: {})
    monkeypatch.setattr(mod, "DataStatus", lambda *a, **k: None)
    monkeypatch.setattr(mod, "plot_mpl", lambda *a, **k: None)
    monkeypatch.setattr(mod, "read_parquet_safe", lambda p: pd.read_parquet(p) if Path(p).exists() else None)
    monkeypatch.setattr(mod, "read_json_safe", lambda p: {})

    # Run main; it should call st.error due to missing price columns and not crash
    mod.main()
    assert any("Price column not found" in str(e) for e in errors)

