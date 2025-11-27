from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np
import pandas as pd

from mie_lib.options.horizon_resolver import HorizonResolution

EM_DASHBOARD_BASE_COLUMNS: Sequence[str] = (
    "date",
    "horizon",
    "horizon_label",
    "target_days",
    "target_date",
    "spot_close",
    "atm_strike",
    "call_price",
    "put_price",
    "expected_move_pct",
    "em_low",
    "em_high",
    "em_low_1_5",
    "em_high_1_5",
    "em_low_2",
    "em_high_2",
    "vix1d_close",
    "confidence_level",
    "range_low",
    "range_high",
    "implied_prob_hit_em",
    "theta_note",
    "confidence_band",
)

DEFAULT_CONFIDENCE_LEVELS: Sequence[float] = (
    0.6827,
    0.75,
    0.8,
    0.85,
    0.9,
    0.95,
    0.975,
    0.983,
    0.9973,
)


class OptionChainProvider:
    """Minimal interface for option chain providers consumed by EM core."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Any] = {}

    def fetch_chain_snapshot(
        self,
        ticker: str,
        expiry: date,
        as_of: date,
        strike_band_pct: float = 0.03,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def fetch_available_expiries(self, ticker: str, as_of: date) -> List[date]:
        return []


class MockOptionChainProvider(OptionChainProvider):
    """Toy provider used in tests to generate deterministic chains."""

    def __init__(self, spot_close: float = 500.0) -> None:
        super().__init__()
        self.spot_close = float(spot_close)

    def fetch_chain_snapshot(
        self,
        ticker: str,
        expiry: date,
        as_of: date,
        strike_band_pct: float = 0.03,
    ) -> pd.DataFrame:
        tenor_days = max((expiry - as_of).days, 1)
        vol_scale = np.sqrt(tenor_days / 252.0)
        straddle_val = self.spot_close * 0.04 * vol_scale
        call_mid = straddle_val / 2.0
        put_mid = straddle_val / 2.0 * 0.95
        rows = [
            {
                "as_of": as_of,
                "ticker": ticker,
                "expiry": expiry,
                "option_type": "C",
                "strike": self.spot_close,
                "prev_close_mid": call_mid,
                "spot_close": self.spot_close,
            },
            {
                "as_of": as_of,
                "ticker": ticker,
                "expiry": expiry,
                "option_type": "P",
                "strike": self.spot_close,
                "prev_close_mid": put_mid,
                "spot_close": self.spot_close,
            },
        ]
        return pd.DataFrame(rows)

    def fetch_available_expiries(self, ticker: str, as_of: date) -> List[date]:
        return [as_of + timedelta(days=d) for d in (1, 4, 9, 20)]


def _ensure_chain_schema(chain: pd.DataFrame) -> pd.DataFrame:
    if chain.empty:
        return chain
    df = chain.copy()
    rename_map = {}
    if "type" in df.columns and "option_type" not in df.columns:
        rename_map["type"] = "option_type"
    if "mid" in df.columns and "prev_close_mid" not in df.columns:
        rename_map["mid"] = "prev_close_mid"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _extract_call_put(df: pd.DataFrame) -> tuple[float | None, float | None]:
    call_mid = None
    put_mid = None
    if df.empty or "option_type" not in df.columns:
        return call_mid, put_mid
    types = df["option_type"].astype(str).str.upper()
    calls = df.loc[types == "C"]
    puts = df.loc[types == "P"]
    if not calls.empty:
        val = calls["prev_close_mid"].dropna()
        if not val.empty:
            call_mid = float(val.iloc[0])
    if not puts.empty:
        val = puts["prev_close_mid"].dropna()
        if not val.empty:
            put_mid = float(val.iloc[0])
    return call_mid, put_mid


def _chain_spot(df: pd.DataFrame) -> float | None:
    for col in ("spot_close", "underlying_price"):
        if col in df.columns:
            series = df[col].dropna()
            if not series.empty:
                return float(series.iloc[0])
    spot = df["strike"].dropna().mean() if "strike" in df.columns else np.nan
    return float(spot) if np.isfinite(spot) else None


def _as_resolution(record: HorizonResolution | Mapping[str, Any]) -> HorizonResolution:
    if isinstance(record, HorizonResolution):
        return record
    return HorizonResolution(
        horizon=record["horizon"],
        as_of=record["as_of"],
        target_date=record.get("target_date") or record["base_trading_day"],
        target_days=int(record.get("target_days", 0)),
        base_trading_day=record.get("base_trading_day") or record["target_date"],
        chosen_expiry=record.get("chosen_expiry"),
    )


def compute_expected_moves_for_horizons(
    provider: OptionChainProvider,
    ticker: str,
    horizon_resolutions: Iterable[HorizonResolution | Mapping[str, Any]],
    strike_band_pct: float = 0.03,
    debug: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Fetch ATM chains per expiry and compute EM stats per horizon."""

    resolutions = [_as_resolution(rec) for rec in horizon_resolutions]
    if not resolutions:
        return pd.DataFrame(), []

    unique_expiries: Dict[date, pd.DataFrame] = {}
    skips: list[dict[str, Any]] = []

    for res in resolutions:
        expiry = res.chosen_expiry
        if expiry is None:
            skips.append({"horizon": res.horizon, "reason": "missing_expiry"})
            continue
        if expiry in unique_expiries:
            continue
        chain = provider.fetch_chain_snapshot(
            ticker=ticker,
            expiry=expiry,
            as_of=res.as_of,
            strike_band_pct=strike_band_pct,
        )
        unique_expiries[expiry] = _ensure_chain_schema(chain)

    rows: list[dict[str, Any]] = []
    for res in resolutions:
        expiry = res.chosen_expiry
        if expiry is None:
            continue
        chain = unique_expiries.get(expiry)
        if chain is None or chain.empty:
            skips.append({"horizon": res.horizon, "reason": "empty_chain"})
            continue
        call_mid, put_mid = _extract_call_put(chain)
        spot_close = _chain_spot(chain)
        if spot_close is None or call_mid is None or put_mid is None:
            skips.append({"horizon": res.horizon, "reason": "missing_prices"})
            continue
        straddle = call_mid + put_mid
        em_pct = straddle / spot_close if spot_close else np.nan
        em_abs = spot_close * em_pct if np.isfinite(em_pct) else np.nan
        if not np.isfinite(em_pct):
            skips.append({"horizon": res.horizon, "reason": "bad_calc"})
            continue
        base_row = {
            "as_of": res.as_of,
            "horizon": res.horizon,
            "expiry": expiry,
            "target_date": res.target_date,
            "target_days": float(res.target_days),
            "spot_close": float(spot_close),
            "atm_strike": float(chain["strike"].dropna().iloc[0])
            if "strike" in chain.columns and not chain["strike"].dropna().empty
            else float(spot_close),
            "atm_call_mid": float(call_mid),
            "atm_put_mid": float(put_mid),
            "straddle_value": float(straddle),
            "em_pct": float(em_pct),
            "em_abs": float(em_abs),
            "lower_bound": float(spot_close - em_abs),
            "upper_bound": float(spot_close + em_abs),
            "em_low_1_5": float(spot_close - em_abs * 1.5),
            "em_high_1_5": float(spot_close + em_abs * 1.5),
            "em_low_2": float(spot_close - em_abs * 2.0),
            "em_high_2": float(spot_close + em_abs * 2.0),
        }
        rows.append(base_row)

    return pd.DataFrame(rows), skips


def confidence_bands_from_vix1d(
    vix1d_close: float | None,
    target_days: float | None,
    levels: Sequence[float] | None = None,
) -> list[dict[str, float]]:
    if vix1d_close is None:
        return []
    if target_days is None or target_days <= 0:
        return []
    try:
        sigma = float(vix1d_close) / 100.0
    except (TypeError, ValueError):
        return []
    if not np.isfinite(sigma):
        return []
    horizon_scale = np.sqrt(float(target_days))
    dist = NormalDist()
    out = []
    for level in levels or DEFAULT_CONFIDENCE_LEVELS:
        try:
            lvl = float(level)
        except (TypeError, ValueError):
            continue
        if not 0 < lvl < 1:
            continue
        z = dist.inv_cdf((1.0 + lvl) / 2.0)
        pct_move = sigma * z * horizon_scale
        out.append({"confidence_level": lvl, "pct_move": pct_move})
    return out


def adapt_em_core_to_dashboard_schema(
    em_core_df: pd.DataFrame,
    vix1d_close: float | None = None,
    levels: Sequence[float] | None = None,
) -> pd.DataFrame:
    if em_core_df is None or em_core_df.empty:
        return pd.DataFrame(columns=EM_DASHBOARD_BASE_COLUMNS)

    df = em_core_df.copy()
    df["date"] = pd.to_datetime(df["as_of"], errors="coerce").dt.date
    df["horizon_label"] = df["horizon"]
    df["call_price"] = df["atm_call_mid"]
    df["put_price"] = df["atm_put_mid"]
    df["expected_move_pct"] = df["em_pct"]
    df["em_low"] = df["lower_bound"]
    df["em_high"] = df["upper_bound"]
    df["vix1d_close"] = vix1d_close if vix1d_close is not None else np.nan
    df["confidence_level"] = np.nan
    df["range_low"] = np.nan
    df["range_high"] = np.nan
    df["implied_prob_hit_em"] = None
    df["theta_note"] = None
    df["confidence_band"] = False

    base_cols = list(EM_DASHBOARD_BASE_COLUMNS)
    df = df.reindex(columns=base_cols)

    if vix1d_close is None:
        return df

    band_rows: List[dict[str, Any]] = []
    for _, row in df.iterrows():
        bands = confidence_bands_from_vix1d(
            vix1d_close=vix1d_close,
            target_days=row.get("target_days"),
            levels=levels,
        )
        for band in bands:
            pct_move = band["pct_move"]
            spot_close = row.get("spot_close")
            if spot_close is None or not np.isfinite(spot_close):
                continue
            band_rows.append(
                {
                    "date": row["date"],
                    "horizon": row["horizon"],
                    "horizon_label": row["horizon_label"],
                    "target_days": row["target_days"],
                    "target_date": row["target_date"],
                    "spot_close": spot_close,
                    "atm_strike": row["atm_strike"],
                    "call_price": row["call_price"],
                    "put_price": row["put_price"],
                    "expected_move_pct": pct_move,
                    "em_low": spot_close * (1.0 - pct_move),
                    "em_high": spot_close * (1.0 + pct_move),
                    "em_low_1_5": row["em_low_1_5"],
                    "em_high_1_5": row["em_high_1_5"],
                    "em_low_2": row["em_low_2"],
                    "em_high_2": row["em_high_2"],
                    "vix1d_close": vix1d_close,
                    "confidence_level": band["confidence_level"],
                    "range_low": spot_close * (1.0 - pct_move),
                    "range_high": spot_close * (1.0 + pct_move),
                    "implied_prob_hit_em": None,
                    "theta_note": None,
                    "confidence_band": True,
                }
            )

    if band_rows:
        df = pd.concat([df, pd.DataFrame(band_rows)], ignore_index=True)
        df = df.reindex(columns=base_cols)

    return df


__all__ = [
    "OptionChainProvider",
    "MockOptionChainProvider",
    "compute_expected_moves_for_horizons",
    "adapt_em_core_to_dashboard_schema",
    "confidence_bands_from_vix1d",
    "EM_DASHBOARD_BASE_COLUMNS",
]
