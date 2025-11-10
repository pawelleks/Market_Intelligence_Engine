from datetime import date

from src.data_ingest.yfinance_loader import _detect_missing_weekdays

def test_detect_missing_weekdays_no_gap():
    last = date(2025, 11, 4)
    new_dates = [date(2025, 11, 5)]
    assert _detect_missing_weekdays(last, new_dates) == []

def test_detect_missing_weekdays_gap_two_weekdays():
    last = date(2025, 11, 4)
    new_dates = [date(2025, 11, 7)]  # missing 5th and 6th (Wed/Thu)
    missing = _detect_missing_weekdays(last, new_dates)
    assert len(missing) >= 1
    assert date(2025, 11, 5) in missing

def test_detect_missing_weekdays_handles_empty():
    assert _detect_missing_weekdays(None, []) == []

