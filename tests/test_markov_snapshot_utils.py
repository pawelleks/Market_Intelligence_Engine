from datetime import date

from mie_lib.ui.markov_snapshots import compute_snapshot_staleness


def test_compute_snapshot_staleness_importable():
    assert callable(compute_snapshot_staleness)


def test_compute_snapshot_staleness_flags_stale_snapshot():
    result = compute_snapshot_staleness("2025-01-01", today="2025-01-10")
    assert result["last_date_iso"] == "2025-01-01"
    assert result["days_old"] == 9
    assert result["is_stale"] is True


def test_compute_snapshot_staleness_flags_fresh_snapshot():
    result = compute_snapshot_staleness("2025-01-10", today="2025-01-10")
    assert result["days_old"] == 0
    assert result["is_stale"] is False


def test_compute_snapshot_staleness_handles_none():
    result = compute_snapshot_staleness(None, today=date(2025, 1, 10))
    assert result["last_date"] is None
    assert result["last_date_iso"] is None
    assert result["days_old"] is None
    assert result["is_stale"] is False
