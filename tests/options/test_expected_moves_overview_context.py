from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from mie_lib.options.em_core import MockOptionChainProvider
from mie_lib.options.expected_move import (
    ExpectedMovesConfig,
    build_expected_moves_history,
    load_expected_moves_manifest,
)
from mie_lib.options.horizon_resolver import PRIMARY_HORIZONS, WEEKLY_REFERENCE_HORIZON
from mie_lib.utils.paths import options_expected_moves_path, options_manifest_path


def _base_config(ticker: str = "SPY") -> ExpectedMovesConfig:
    return ExpectedMovesConfig(
        spot_ticker=ticker,
        provider="mock",
        max_api_calls_per_day=10,
        horizons=[],
        confidence_levels=[0.6827],
        weekly_reference={"enabled": False},
    )


def test_em_core_pipeline_populates_manifest_and_horizons(expected_moves_env):
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-02", "2024-02-05"]),
            "adj_close": [411.25, 412.75],
            "close": [411.25, 412.75],
        }
    )
    prices.to_parquet(expected_moves_env.raw_dir / "SPY.parquet", index=False)

    as_of = date(2024, 2, 5)
    provider = MockOptionChainProvider(spot_close=412.75)

    results = build_expected_moves_history(
        start=as_of,
        end=as_of,
        ticker="SPY",
        provider=provider,
        include_weekly_reference=False,
        use_em_core_pipeline=True,
        config=_base_config(),
    )

    assert results and "manifest" in results[0]["artifacts"]

    em_path = options_expected_moves_path("SPY")
    em_df = pd.read_parquet(em_path)
    assert set(em_df["horizon"]) == set(PRIMARY_HORIZONS)

    manifest_path = options_manifest_path()
    assert manifest_path.exists()
    manifest = load_expected_moves_manifest()
    assert manifest["as_of"] == as_of.isoformat()
    assert manifest["ticker"] == "SPY"
    assert manifest["spot_close"] == pytest.approx(412.75)

    statuses = {entry["horizon"]: entry["status"] for entry in manifest["horizon_status"]}
    for horizon in PRIMARY_HORIZONS:
        assert statuses[horizon] == "ok"
    assert statuses[WEEKLY_REFERENCE_HORIZON] == "not_requested"


def test_manifest_loader_handles_missing_file(expected_moves_env):
    manifest_path = options_manifest_path()
    if manifest_path.exists():
        manifest_path.unlink()
    assert load_expected_moves_manifest() == {}
