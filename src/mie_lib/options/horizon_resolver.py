from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Sequence

from mie_lib.utils.trading_calendar import (
    is_trading_day,
    last_trading_day_of_month,
    last_trading_day_of_next_week,
    last_trading_day_of_previous_week,
    last_trading_day_of_week,
    next_trading_day,
)

HorizonName = str

PRIMARY_HORIZONS: Sequence[HorizonName] = (
    "Next Session",
    "Through Friday",
    "End of Next Week",
    "Month End",
)
WEEKLY_REFERENCE_HORIZON: HorizonName = "Prev Friday (Weekly Ref)"
EM_HORIZON_DISPLAY_ORDER: Sequence[HorizonName] = tuple(
    list(PRIMARY_HORIZONS) + [WEEKLY_REFERENCE_HORIZON]
)


@dataclass(frozen=True)
class HorizonResolution:
    """Represents the canonical metadata for an expected move horizon."""

    horizon: HorizonName
    as_of: date
    target_date: date
    target_days: int
    base_trading_day: date
    chosen_expiry: date | None

    def to_record(self) -> dict:
        return {
            "horizon": self.horizon,
            "as_of": self.as_of,
            "target_date": self.target_date,
            "target_days": self.target_days,
            "base_trading_day": self.base_trading_day,
            "chosen_expiry": self.chosen_expiry,
        }


def _count_trading_days(start: date, end: date) -> int:
    """Count trading days strictly between start and end inclusive of end."""

    if end <= start:
        return 0
    cursor = start
    count = 0
    while cursor < end:
        cursor += timedelta(days=1)
        if is_trading_day(cursor):
            count += 1
    return count


def _pick_expiry(target: date, expiries: Sequence[date]) -> date | None:
    for expiry in expiries:
        if expiry >= target:
            return expiry
    return expiries[-1] if expiries else None


def _normalize_expiries(expiries: Iterable[date]) -> List[date]:
    uniq = sorted({d for d in expiries if isinstance(d, date)})
    return uniq


def resolve_horizons(
    as_of: date,
    available_expiries: Iterable[date] | None = None,
    include_weekly_reference: bool = True,
) -> List[HorizonResolution]:
    """Resolve canonical horizons for *as_of* using available expiries."""

    expiries = _normalize_expiries(available_expiries or [])

    def _build(horizon: HorizonName, target_date: date) -> HorizonResolution:
        return HorizonResolution(
            horizon=horizon,
            as_of=as_of,
            target_date=target_date,
            target_days=_count_trading_days(as_of, target_date),
            base_trading_day=target_date,
            chosen_expiry=_pick_expiry(target_date, expiries),
        )

    resolved: List[HorizonResolution] = []
    resolved.append(_build("Next Session", next_trading_day(as_of)))
    resolved.append(_build("Through Friday", last_trading_day_of_week(as_of)))
    resolved.append(_build("End of Next Week", last_trading_day_of_next_week(as_of)))
    resolved.append(_build("Month End", last_trading_day_of_month(as_of)))

    if include_weekly_reference:
        resolved.append(
            _build(
                WEEKLY_REFERENCE_HORIZON,
                last_trading_day_of_previous_week(as_of),
            )
        )

    resolved.sort(key=lambda res: EM_HORIZON_DISPLAY_ORDER.index(res.horizon))
    return resolved


__all__ = [
    "HorizonName",
    "HorizonResolution",
    "PRIMARY_HORIZONS",
    "WEEKLY_REFERENCE_HORIZON",
    "EM_HORIZON_DISPLAY_ORDER",
    "resolve_horizons",
]
