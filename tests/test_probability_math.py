
import pytest
import numpy as np
from mie_lib.utils.probability_math import BreedenLitzenberger

@pytest.fixture
def bl():
    return BreedenLitzenberger()

def test_enforce_monotonicity_already_monotonic(bl):
    """Test that strictly decreasing array is unchanged."""
    # Create valid probability column (decreasing with strike)
    col = np.array([0.9, 0.8, 0.5, 0.1, 0.0])
    # Shape it into (5, 1) grid (5 strikes, 1 time slice)
    grid = col.reshape(-1, 1)
    
    result = bl.enforce_monotonicity(grid.copy())
    
    np.testing.assert_array_almost_equal(result, grid)

def test_enforce_monotonicity_fix_violation(bl):
    """Test that non-monotonic "hills" are flattened."""
    # Violation: 0.5 -> 0.6 (increase) -> 0.4
    col = np.array([0.9, 0.5, 0.6, 0.4, 0.1])
    grid = col.reshape(-1, 1)
    
    # Expected: 0.9, 0.5, 0.5 (capped at prev), 0.4, 0.1
    expected = np.array([0.9, 0.5, 0.5, 0.4, 0.1]).reshape(-1, 1)
    
    result = bl.enforce_monotonicity(grid)
    
    np.testing.assert_array_almost_equal(result, expected)

def test_enforce_monotonicity_multi_column(bl):
    """Test multiple time slices independently."""
    col1 = np.array([0.9, 0.6, 0.7, 0.2]) # Expect 0.9, 0.6, 0.6, 0.2
    col2 = np.array([1.0, 0.8, 0.9, 0.5]) # Expect 1.0, 0.8, 0.8, 0.5
    
    grid = np.column_stack((col1, col2))
    
    result = bl.enforce_monotonicity(grid)
    
    expected_col1 = np.array([0.9, 0.6, 0.6, 0.2])
    expected_col2 = np.array([1.0, 0.8, 0.8, 0.5])
    
    np.testing.assert_array_almost_equal(result[:, 0], expected_col1)
    np.testing.assert_array_almost_equal(result[:, 1], expected_col2)

def test_calculate_parametric_cone(bl):
    """Test that log-normal cone generation returns expected structure."""
    spot = 5000.0
    exp_sigmas = [(10, 0.20), (30, 0.20)]
    mu = 0.05
    
    results = bl.calculate_parametric_cone(spot, exp_sigmas, mu, days_out=5)
    
    assert len(results) == 6 # 0 to 5 inclusive
    assert results[0]['dte'] == 0
    assert results[0]['p50'] == spot
    
    # Check T=5
    res_5 = results[-1]
    assert res_5['dte'] == 5
    assert res_5['p50'] > spot # Positive drift
    
    # Check cone expansion
    assert res_5['p95'] > res_5['p50']
    assert res_5['p05'] < res_5['p50']
