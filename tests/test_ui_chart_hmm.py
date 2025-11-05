import pandas as pd
import numpy as np
from pathlib import Path
from importlib import import_module

from app.ui.theme import get_tokens

DATA_DIR = Path("data")


def _write_minimal_hmm(ticker: str = "SPY"):
    # minimal features with adj_close
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=50)
    price = 100 + np.linspace(0, 5, len(dates))
    feat = pd.DataFrame({"date": dates, "adj_close": price})
    (DATA_DIR / "features").mkdir(parents=True, exist_ok=True)
    feat.to_parquet(DATA_DIR / "features" / f"{ticker}.parquet", index=False)

    # states alternating
    states = pd.DataFrame({
        "date": dates,
        "hmm_state": np.tile([0, 1], len(dates) // 2 + 1)[: len(dates)],
        "hmm_state_name": ["Bull" if i % 2 == 0 else "Bear" for i in range(len(dates))],
    })
    hmm_dir = DATA_DIR / "analytics" / "hmm" / ticker
    hmm_dir.mkdir(parents=True, exist_ok=True)
    states.to_parquet(hmm_dir / "hmm_states.parquet", index=False)

    # probs with simple pattern
    probs = pd.DataFrame({
        "date": dates,
        "hmm_prob_bull": np.clip(np.linspace(0.2, 0.8, len(dates)), 0, 1),
        "hmm_prob_bear": np.clip(1 - np.linspace(0.2, 0.8, len(dates)), 0, 1),
    })
    probs.to_parquet(hmm_dir / "hmm_probs.parquet", index=False)


def test_hmm_helpers_and_chart_smoke():
    _write_minimal_hmm("SPY")

    mod = import_module("app.pages.01_Market_Regime_Dashboard")
    load_price_and_hmm = getattr(mod, "load_price_and_hmm")
    draw_hmm_regimes_chart = getattr(mod, "draw_hmm_regimes_chart")

    merged, probs = load_price_and_hmm("SPY")
    assert merged is not None and "price" in merged.columns and "hmm_state_name" in merged.columns

    tokens = get_tokens()
    fig = draw_hmm_regimes_chart(
        merged,
        tokens,
        width=tokens["theme"]["chart"]["default_width"],
        height=tokens["theme"]["chart"]["default_height"],
    )
    assert hasattr(fig, "savefig")
