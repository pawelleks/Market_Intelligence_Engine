from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from mie_lib.options.expected_move import (
    ExpectedMovesConfig,
    build_expected_moves_history,
    update_expected_moves,
)
from mie_lib.utils.paths import (
    options_expected_moves_path,
    options_weekly_reference_path,
)


def _write_chain(chain_dir, day: date, call_mid: float, put_mid: float, strike: float = 100.0) -> None:
    df = pd.DataFrame(
        [
            {"option_type": "C", "prev_close_mid": call_mid, "strike": strike},
            {"option_type": "P", "prev_close_mid": put_mid, "strike": strike},
        ]
    )
    chain_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(chain_dir / f"{day.isoformat()}_chain.parquet", index=False)


def _base_config(ticker: str = "SPY") -> ExpectedMovesConfig:
    return ExpectedMovesConfig(
        spot_ticker=ticker,
        provider="mock",
        max_api_calls_per_day=0,
        horizons=[],
        confidence_levels=[],
        weekly_reference={"enabled": True},
    )


def test_build_expected_moves_history_writes_artifacts(expected_moves_env):
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-12-29", "2024-01-02", "2024-01-03"]),
            "adj_close": [99.0, 100.0, 103.0],
            "close": [99.0, 100.0, 103.0],
        }
    )
    prices.to_parquet(expected_moves_env.raw_dir / "SPY.parquet", index=False)

    chain_dir = expected_moves_env.raw_options_dir / "spy"
    _write_chain(chain_dir, date(2024, 1, 2), call_mid=2.0, put_mid=1.5)
    _write_chain(chain_dir, date(2024, 1, 3), call_mid=2.2, put_mid=1.6)

    results = build_expected_moves_history(
        start=date(2024, 1, 2),
        end=date(2024, 1, 3),
        ticker="SPY",
        include_weekly_reference=True,
        use_em_core_pipeline=False,
        config=_base_config(),
    )

    assert len(results) == 2
    assert all("expected_moves" in day["artifacts"] for day in results)

    em_path = options_expected_moves_path("SPY")
    assert em_path.exists()
    em_df = pd.read_parquet(em_path)
    em_df["date"] = pd.to_datetime(em_df["date"]).dt.date
    assert list(em_df["horizon"].unique()) == ["Next Session"]
    assert {date(2024, 1, 2), date(2024, 1, 3)} <= set(em_df["date"])

    first_pct = em_df.loc[em_df["date"] == date(2024, 1, 2), "expected_move_pct"].iloc[0]
    second_pct = em_df.loc[em_df["date"] == date(2024, 1, 3), "expected_move_pct"].iloc[0]
    assert first_pct == pytest.approx((2.0 + 1.5) / 100.0)
    assert second_pct == pytest.approx((2.2 + 1.6) / 103.0)

    weekly_path = options_weekly_reference_path("SPY")
    assert weekly_path.exists()
    weekly_df = pd.read_parquet(weekly_path)
    assert "as_of" in weekly_df.columns
    assert pd.to_datetime(weekly_df["as_of"]).dt.date.iloc[-1] == date(2024, 1, 3)


def test_update_expected_moves_extends_history(expected_moves_env):
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-12-29", "2024-01-02", "2024-01-03", "2024-01-04"]),
            "adj_close": [99.0, 100.0, 103.0, 104.5],
            "close": [99.0, 100.0, 103.0, 104.5],
        }
    )
    prices.to_parquet(expected_moves_env.raw_dir / "SPY.parquet", index=False)

    chain_dir = expected_moves_env.raw_options_dir / "spy"
    _write_chain(chain_dir, date(2024, 1, 2), call_mid=2.0, put_mid=1.5)
    _write_chain(chain_dir, date(2024, 1, 3), call_mid=2.2, put_mid=1.6)
    _write_chain(chain_dir, date(2024, 1, 4), call_mid=2.4, put_mid=1.7)

    build_expected_moves_history(
        start=date(2024, 1, 2),
        end=date(2024, 1, 3),
        ticker="SPY",
        include_weekly_reference=False,
        use_em_core_pipeline=False,
        config=_base_config(),
    )

    updates = update_expected_moves(
        ticker="SPY",
        lookback_days=2,
        end=date(2024, 1, 4),
        include_weekly_reference=False,
        use_em_core_pipeline=False,
        config=_base_config(),
    )

    assert updates, "Expected at least one incremental build"
    em_path = options_expected_moves_path("SPY")
    em_df = pd.read_parquet(em_path)
    em_df["date"] = pd.to_datetime(em_df["date"]).dt.date
    assert {date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)} <= set(em_df["date"])
