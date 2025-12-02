import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fastapi import FastAPI
    from mie_lib.utils.paths import markov_matrix_path_flat
    from mie_lib.analytics.markov.markov_engine import MarkovConfig

    TICKER = "SPY"
    matrix_path = markov_matrix_path_flat(TICKER, order=1)
    default_bps = MarkovConfig.threshold_bps

    print("✅ API imports successful.")
    print(f"   Ticker: {TICKER}")
    print(f"   Default Threshold: {default_bps} bps")
    print(f"   Canonical Path Test: {matrix_path}")

except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ AN UNEXPECTED ERROR OCCURRED: {e}")
    sys.exit(1)
