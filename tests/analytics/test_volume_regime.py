
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from mie_lib.analytics.volume_regime import calculate_volume_regime, generate_volume_conclusion

# --- Fixtures ---

@pytest.fixture
def mock_ohlcv_data():
    """Generates 30 days of mock OHLCV data."""
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(30)]
    
    # Create a DataFrame where price generally rises
    # Close = 100 + i (rising)
    # Volume = 1M + random noise
    data = {
        "date": dates,
        "open": [100 + i for i in range(30)],
        "high": [105 + i for i in range(30)],
        "low": [95 + i for i in range(30)],
        "close": [101 + i for i in range(30)], # Increasing close
        "adj_close": [101 + i for i in range(30)], 
        "volume": [1000000 + (i * 1000) for i in range(30)]
    }
    return pd.DataFrame(data)

@pytest.fixture
def mock_ohlcv_down_data():
    """Generates 30 days of downtrend data."""
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(30)]
    data = {
        "date": dates,
        "close": [200 - i for i in range(30)], # Decreasing
        "adj_close": [200 - i for i in range(30)],
        "volume": [1000000 for _ in range(30)]
    }
    return pd.DataFrame(data)

# --- Tests ---

def test_calculate_volume_regime_insufficient_data():
    """Test that it handles insufficient data gracefully."""
    empty_df = pd.DataFrame()
    result = calculate_volume_regime("TEST", empty_df)
    assert result["market_state"] == "Insufficient Data"
    assert result["ticker"] == "TEST"

def test_calculate_volume_regime_success(mock_ohlcv_data):
    """Test standard calculation with sufficient data."""
    result = calculate_volume_regime("TEST", mock_ohlcv_data)
    
    assert result["ticker"] == "TEST"
    assert result["market_state"] in ["Distribution", "Accumulation", "Consolidation", "Neutral", "Capitulation"]
    assert isinstance(result["current_ratio"], float)
    assert isinstance(result["price_change_20d"], float)
    assert "current_price" in result

def test_volume_regime_logic_distribution():
    """
    Test Distribution logic: 
    Constraint: Price Rising (> SMA20) AND Ratio < 1.0
    """
    # Create data where Price Rising strategy holds
    # But Volume on UP days is 0, Volume on DOWN days is High => Ratio = 0 ( < 1.0)
    
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(30)]
    df = pd.DataFrame({
        "date": dates,
        "adj_close": [100 + (i*2) for i in range(30)], # Strong Uptrend
        "volume": [1000 if i % 2 == 0 else 10000 for i in range(30)] # Just alternating
    })
    
    # We need to force "ratio < 1.0". 
    # Ratio = UpVol / DownVol.
    # We need DownVol > UpVol.
    # DownVol happens when Price < PrevClose.
    # In our data above, Price is always rising (Prev 100, curr 102). So Price Change always > 0.
    # So UpVol is everything. DownVol is 0. Ratio is usually capped at 100.
    
    # Let's create a scenario: General trend up, but heavy volume on the few down days.
    
    # 25 days of slow grind up (Low Volume)
    # 5 days of sharp drop (High Volume)
    # But net result is still above SMA20?
    
    prices = []
    vols = []
    
    curr = 100
    for i in range(25):
        curr += 1 # Up
        prices.append(curr)
        vols.append(100) # Low vol on up
        
    # Introduce a down day with huge volume
    curr -= 0.5 # Small dip
    prices.append(curr)
    vols.append(5000) # Huge vol on down
    
    # Continue up
    for i in range(4):
        curr += 1
        prices.append(curr)
        vols.append(100)
        
    df = pd.DataFrame({"date": dates, "adj_close": prices, "volume": vols})
    
    result = calculate_volume_regime("DIST", df)
    # SMA20 check:
    # SMA20 is roughly avg of last 20 prices. Since price rising, SMA < Current.
    # Current Ratio: DownVol will be dominated by that 5000. UpVol will be ~25*100 = 2500.
    # Ratio ~ 0.5 (< 1.0).
    
    assert result["market_state"] == "Distribution", f"Expected Distribution, got {result['market_state']} (Ratio: {result['current_ratio']})"

def test_generate_volume_conclusion():
    """Test text generation."""
    metrics = {
        "ticker": "ABC",
        "market_state": "Accumulation",
        "current_ratio": 2.5
    }
    text = generate_volume_conclusion(metrics)
    assert "✅ Bullish" in text
    assert "Accumulation" in text
    assert "2.5" in text

    metrics_dist = {
        "ticker": "XYZ",
        "market_state": "Distribution",
        "current_ratio": 0.5
    }
    text_dist = generate_volume_conclusion(metrics_dist)
    assert "⚠️ Warning" in text_dist
    assert "Distribution" in text_dist
