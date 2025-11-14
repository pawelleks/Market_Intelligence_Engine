import pandas as pd
import numpy as np
from mie_lib.analytics.markov import helpers as markov_helpers


def test_binary_horizons_matrix_power():
    # Build a simple binary K=1 matrix DataFrame
    df = pd.DataFrame({
        "context": ["U", "D"],
        "mc_prob_up": [0.6, 0.3],
        "mc_prob_down": [0.4, 0.7],
    })
    # p0 corresponds to context 'G' (i.e., 'U')
    res = markov_helpers.compute_multi_horizon_probs(df, "G", [1, 2], mode="binary")
    # Manually compute
    P = np.array([[0.6, 0.4], [0.3, 0.7]], dtype=float)
    p0 = np.array([1.0, 0.0])
    p1 = p0 @ P
    p2 = p0 @ np.linalg.matrix_power(P, 2)
    assert abs(res.loc[1, "mc_prob_up"] - p1[0]) < 1e-9
    assert abs(res.loc[1, "mc_prob_down"] - p1[1]) < 1e-9
    assert abs(res.loc[2, "mc_prob_up"] - p2[0]) < 1e-9
    assert abs(res.loc[2, "mc_prob_down"] - p2[1]) < 1e-9
    # Ensure horizons differ
    assert not np.allclose(res.loc[1].values, res.loc[2].values)


def test_tri_horizons_matrix_power():
    # Tri-state 3x3
    df = pd.DataFrame({
        "context": ["U", "N", "D"],
        "mc_prob_up": [0.5, 0.2, 0.1],
        "mc_prob_neutral": [0.3, 0.6, 0.2],
        "mc_prob_down": [0.2, 0.2, 0.7],
    })
    res = markov_helpers.compute_multi_horizon_probs(df, "G", [1, 3], mode="tri")
    P = np.array([
        [0.5, 0.3, 0.2],
        [0.2, 0.6, 0.2],
        [0.1, 0.2, 0.7],
    ], dtype=float)
    p0 = np.array([1.0, 0.0, 0.0])
    p1 = p0 @ P
    p3 = p0 @ np.linalg.matrix_power(P, 3)
    assert abs(res.loc[1, "mc_prob_up"] - p1[0]) < 1e-9
    assert abs(res.loc[1, "mc_prob_neutral"] - p1[1]) < 1e-9
    assert abs(res.loc[1, "mc_prob_down"] - p1[2]) < 1e-9
    assert abs(res.loc[3, "mc_prob_up"] - p3[0]) < 1e-9
    assert abs(res.loc[3, "mc_prob_neutral"] - p3[1]) < 1e-9
    assert abs(res.loc[3, "mc_prob_down"] - p3[2]) < 1e-9
    assert not np.allclose(res.loc[1].values, res.loc[3].values)
