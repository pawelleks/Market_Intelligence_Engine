import sys
from pathlib import Path
from importlib import import_module

PAGES = [
    "app.pages.01_Markov_Chain",
    "app.pages.02_Markov_OneStep",
    "app.pages.03_Markov_MultiStep",
    "app.pages.04_HMM_Price_Current",
    "app.pages.05_HMM_Probabilities_vs_Price",
    "app.pages.06_HMM_Price_FullHistory",
    "app.pages.07_HMM_Transition_Matrix",
    "app.pages.08_Markov_Predictive_Bands",
    "app.pages.09_Downtrend_Confirmation_Score",
    "app.pages.10_Key_Probability_Gauges",
]


def test_pages_exist_and_import(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    # Assert files exist
    for mod in PAGES:
        path = root / Path(mod.replace(".", "/") + ".py")
        assert path.exists(), f"Missing page file: {path}"
    # Import without running Streamlit
    for mod in PAGES:
        import_module(mod)

