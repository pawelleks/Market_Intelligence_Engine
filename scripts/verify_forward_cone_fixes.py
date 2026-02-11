import sys
import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# Mock LOG
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("test_forward_cone")

# Import the function from our job file
sys.path.insert(0, str(Path(os.getcwd())))
from jobs.process_implied_probabilities import calculate_forward_cone

def test_logic():
    spot_price = 500.0
    
    # Create mock density surfaces with highly oscillatory data to trigger CubicSpline overshooting
    density_surfaces = [
        {
            "dte": 10,
            "distribution": {
                "strikes": np.linspace(400, 600, 11).tolist(),
                "pdf": [0.001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.05, 0.01, 0.005, 0.001, 0.001]
            }
        },
        {
            "dte": 20,
            "distribution": {
                "strikes": np.linspace(400, 600, 11).tolist(),
                # Sharp spike to cause oscillation in spline
                "pdf": [0.001, 0.05, 0.001, 0.001, 0.001, 0.1, 0.001, 0.001, 0.001, 0.05, 0.001]
            }
        },
        {
            "dte": 30,
            "distribution": {
                "strikes": np.linspace(400, 600, 11).tolist(),
                "pdf": [0.001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.05, 0.01, 0.005, 0.001, 0.001]
            }
        },
        {
            "dte": 40,
            "distribution": {
                "strikes": np.linspace(400, 600, 11).tolist(),
                # Extreme spread to trigger Volatility Clamping
                "pdf": [0.1, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.1]
            }
        }
    ]
    
    LOG.info("Testing calculate_forward_cone with mock data...")
    # Mock dataframe for parametric logic
    df_mock = pd.DataFrame({
        'expiration': ['2026-02-27'] * 10,
        'strike': np.linspace(5000, 7000, 10),
        'mid_price': [10.0] * 10,
         'right': ['C'] * 10
    })
    
    results = calculate_forward_cone(df_mock, spot_price, "SPX", days_out=45)
    
    mu = 0.045
    for row in results:
        dte = row['dte']
        p50 = row['p50']
        T = dte / 365.25
        
        # Verify Forced Median (Anchor)
        expected_p50 = float(spot_price * np.exp(mu * T))
        if abs(p50 - expected_p50) > 0.01:
            LOG.error(f"FAIL: Forced Median failed at DTE {dte}, expected {expected_p50:.2f}, got {p50:.2f}")
        
        # Verify Monotonicity and No Crossing
        q_keys = ["p05", "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90", "p95"]
        q_values = [row[k] for k in q_keys]
        if q_values != sorted(q_values):
            LOG.error(f"FAIL: Monotonicity violated at DTE {dte}")
        
        # Verify non-crossing (specifically p50 vs bounds)
        if row['p50'] >= row['p95'] and dte > 0:
            LOG.error(f"FAIL: Median crossed Upper Bound at DTE {dte}")
        if row['p50'] <= row['p05'] and dte > 0:
            LOG.error(f"FAIL: Median crossed Lower Bound at DTE {dte}")

    LOG.info("Verification Complete.")

if __name__ == "__main__":
    test_logic()
