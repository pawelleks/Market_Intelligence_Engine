from __future__ import annotations

from datetime import date, timedelta

__all__ = [
    "is_trading_day",
    "next_trading_day",
    "last_trading_day_of_week",
    "last_trading_day_of_next_week",
    "last_trading_day_of_previous_week",
    "last_trading_day_of_month",
]


def is_trading_day(day: date) -> bool:
    """Basic trading day check assuming Monday-Friday calendar."""
    return day.weekday() < 5


def next_trading_day(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


def _start_of_week(day: date) -> date:
    return day - timedelta(days=day.weekday())


def last_trading_day_of_week(day: date) -> date:
    return _start_of_week(day) + timedelta(days=4)


def last_trading_day_of_next_week(day: date) -> date:
    return _start_of_week(day) + timedelta(days=11)


def last_trading_day_of_previous_week(day: date) -> date:
    return _start_of_week(day) - timedelta(days=3)


def last_trading_day_of_month(day: date) -> date:
    # Jump to first day of next month then step backward to last weekday
    if day.month == 12:
        next_month = date(day.year + 1, 1, 1)
    else:
        next_month = date(day.year, day.month + 1, 1)
    cursor = next_month - timedelta(days=1)
    while not is_trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor
