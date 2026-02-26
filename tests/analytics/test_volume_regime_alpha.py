import pandas as pd
import numpy as np
import pytest
from src.mie_lib.analysis.volume_regime import compute_volume_metrics, classify_market_state

def test_compute_volume_metrics():
    # Create sample dataframe with 25 rows
    data = []
    base_price = 100
    for i in range(25):
        # alternate green and red days
        if i % 2 == 0:
            base_price += 1  # UP day
            vol = 2000
        else:
            base_price -= 0.5  # DOWN day
            vol = 1000
            
        data.append({"close": base_price, "volume": vol})
        
    df = pd.DataFrame(data)
    res = compute_volume_metrics(df)
    
    assert len(res) == 25
    assert "ud_vol_ratio" in res.columns
    assert "sma20" in res.columns
    assert "vol_mean_20d" in res.columns
    
    # The last row should have sma20 calculated
    last_row = res.iloc[-1]
    assert not pd.isna(last_row["sma20"])

def test_classify_market_state_insufficient_data():
    row = pd.Series({
        "close": 100,
        "volume": 1000,
        "sma20": np.nan
    })
    assert classify_market_state(row) == "Insufficient Data"

def test_classify_market_state_capitulation():
    row = pd.Series({
        "close": 90,
        "volume": 5000,
        "vol_mean_20d": 1000,
        "price_change_20d": -0.15,
        "ud_vol_ratio": 0.5,
        "sma20": 100,
        "high_20d": 110,
        "low_20d": 85
    })
    assert classify_market_state(row) == "Capitulation"

def test_classify_market_state_distribution():
    row = pd.Series({
        "close": 105,
        "volume": 1000,
        "vol_mean_20d": 1000,
        "price_change_20d": 0.05,
        "ud_vol_ratio": 0.8,
        "sma20": 100,
        "high_20d": 110,
        "low_20d": 90
    })
    assert classify_market_state(row) == "Distribution"

def test_classify_market_state_accumulation():
    row = pd.Series({
        "close": 95,
        "volume": 1000,
        "vol_mean_20d": 1000,
        "price_change_20d": -0.05,
        "ud_vol_ratio": 1.5,
        "sma20": 100,
        "high_20d": 110,
        "low_20d": 85
    })
    assert classify_market_state(row) == "Accumulation"

def test_classify_market_state_consolidation():
    row = pd.Series({
        "close": 100,
        "volume": 500,
        "vol_mean_20d": 1000,
        "price_change_20d": 0.01,
        "ud_vol_ratio": 1.0,
        "sma20": 101,
        "high_20d": 102,
        "low_20d": 99
    })
    assert classify_market_state(row) == "Consolidation"

def test_classify_market_state_neutral():
    row = pd.Series({
        "close": 100,
        "volume": 1000,
        "vol_mean_20d": 1000,
        "price_change_20d": 0.01,
        "ud_vol_ratio": 1.0,
        "sma20": 98,
        "high_20d": 110,
        "low_20d": 90
    })
    assert classify_market_state(row) == "Neutral"
