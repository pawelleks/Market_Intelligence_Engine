from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class RealizedOHLC(BaseModel):
    open: float
    high: float
    low: float
    close: float

class HistoricalEMRecord(BaseModel):
    """
    Schema for the Historical Expected Move Record.
    Used to serialize EOD calculations and reliability metrics before storage.
    """
    # Core Identification
    ticker: str
    expiry_type: str  # "ODTE", "WEEKLY", "MONTHLY"
    expiry_date: date # Added for clarity, though not explicitly in prompt list, it's implied by "expiry_type" context usually, but let's stick to prompt list + common sense. Prompt list: ticker, expiry_type... wait, prompt list didn't explicitly say expiry_date, but it's crucial. I will add it as it's in the spec 4.1 "history/{ticker}/{expiry_date}".
    
    # Calculation Data
    underlying_price: float
    expected_move_dollars: float
    upper_range: float
    lower_range: float
    
    # Volatility & Confidence
    vix1d_value: Optional[float] = None
    confidence_score_percent: int
    
    # Metadata
    timestamp: datetime
    
    # Realized Data (Phase 4.3) - Optional as they are filled post-expiration
    realized_ohlc: Optional[RealizedOHLC] = None
    realized_close: Optional[float] = None # Added for flat table display
    
    # Derived Reliability Metrics (Phase 4.3)
    closed_within_em: Optional[bool] = None
    
    high_breach_amount: Optional[float] = None
    high_breach_percent: Optional[float] = None
    
    low_breach_amount: Optional[float] = None
    low_breach_percent: Optional[float] = None
