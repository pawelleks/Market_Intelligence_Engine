from pathlib import Path
from importlib import import_module

PAGES = [
    "mie_lib.pages.m_chain",
    "mie_lib.pages.m_multistep",
    # Unified HMM page only
    "mie_lib.pages.hmm",
    "mie_lib.pages.m_predictive_bands",
    "mie_lib.pages.downtrend_score",
    "mie_lib.pages.prob_gauges",
]


def test_pages_exist_and_import():

    # Assert files exist under src/
    for mod in PAGES:
        path = Path("src") / (mod.replace(".", "/") + ".py")
        assert path.exists(), f"Missing page file: {path}"
    # Import without running Streamlit
    for mod in PAGES:
        import_module(mod)
