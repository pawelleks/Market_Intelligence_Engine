from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import json
import logging

import numpy as np
import pandas as pd

try:  # pragma: no cover - optional provider module
    from mie_lib.data_ingest.providers import polygon as polygon_provider
except ImportError:  # pragma: no cover
    polygon_provider = None
from mie_lib.utils.config import load_named_config
from mie_lib.utils.paths import (
    DATA_DIR,
    options_expected_moves_path,
    options_weekly_reference_path,
    options_manifest_path,
)
from mie_lib.utils.trading_calendar import (
    is_trading_day,
    last_trading_day_of_month,
    last_trading_day_of_next_week,
    last_trading_day_of_previous_week,
    last_trading_day_of_week,
    next_trading_day,
)
from mie_lib.options.horizon_resolver import (
    PRIMARY_HORIZONS,
    WEEKLY_REFERENCE_HORIZON,
    resolve_horizons,
    HorizonResolution,
)
from mie_lib.options.em_core import (
    OptionChainProvider,
    MockOptionChainProvider,
    compute_expected_moves_for_horizons,
    adapt_em_core_to_dashboard_schema,
    confidence_bands_from_vix1d,
    EM_DASHBOARD_BASE_COLUMNS,
)

LOG = logging.getLogger(__name__)

RAW_DIR = DATA_DIR / "raw"
RAW_OPTIONS_DIR = RAW_DIR / "options"

EM_DASHBOARD_COLUMNS = list(EM_DASHBOARD_BASE_COLUMNS)
EM_HORIZON_NAME_MAP = {
    "Next Session": "Next Session",
    "next_session": "Next Session",
    "Through Friday": "Through Friday",
    "through_friday": "Through Friday",
    "End of Next Week": "End of Next Week",
    "end_of_next_week": "End of Next Week",
    "Month End": "Month End",
    "month_end": "Month End",
    WEEKLY_REFERENCE_HORIZON: WEEKLY_REFERENCE_HORIZON,
    "prev_friday_ref": WEEKLY_REFERENCE_HORIZON,
}


def _confidence_bands_from_vix1d(
    vix1d_close: float | None,
    target_days: float | None,
    levels: Iterable[float] | None = None,
):
    return confidence_bands_from_vix1d(vix1d_close, target_days, tuple(levels) if levels else None)


def _ensure_em_dashboard_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "horizon" in df.columns:
        df["horizon"] = df["horizon"].apply(
            lambda h: EM_HORIZON_NAME_MAP.get(str(h), h) if not pd.isna(h) else h
        )
    if "horizon_label" not in df.columns and "horizon" in df.columns:
        df["horizon_label"] = df["horizon"]

    defaults_nan = {
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
    }

    for col in EM_DASHBOARD_COLUMNS:
        if col not in df.columns:
            if col in ("theta_note", "implied_prob_hit_em"):
                df[col] = None
            elif col == "confidence_band":
                df[col] = False
            elif col in defaults_nan:
                df[col] = np.nan
            else:
                df[col] = np.nan

    return df.reindex(columns=EM_DASHBOARD_COLUMNS)


def _load_raw_prices(ticker: str) -> pd.DataFrame:
    path = RAW_DIR / f"{ticker.upper()}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"]).sort_values("date")
    return df


def _load_local_chain_snapshot(ticker: str, as_of: date) -> pd.DataFrame:
    ticker_dir = RAW_OPTIONS_DIR / ticker.lower()
    path = ticker_dir / f"{as_of.isoformat()}_chain.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - file guard
        LOG.warning("Failed to load local chain %s: %s", path, exc)
        return pd.DataFrame()
    return df


def _spot_from_prices(prices: pd.DataFrame, as_of: date) -> Optional[float]:
    if prices.empty:
        return None
    row = prices[prices["date"] == as_of]
    if row.empty:
        row = prices[prices["date"] < as_of].tail(1)
    if row.empty:
        return None
    for col in ("adj_close", "close"):
        if col in row.columns:
            value = row[col].iloc[0]
            if pd.notna(value):
                return float(value)
    return None


def _iter_trading_days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        if is_trading_day(current):
            yield current
        current += timedelta(days=1)


def _provider_set_spot_override(provider: Optional[OptionChainProvider], spot: float) -> None:
    if provider is None:
        return
    setter = getattr(provider, "set_spot_price", None)
    if callable(setter):
        setter(spot)
        return
    if hasattr(provider, "spot_close"):
        provider.spot_close = spot


def _fetch_vix_from_provider(provider: Optional[OptionChainProvider]) -> Optional[float]:
    if provider is None:
        return None
    fetcher = getattr(provider, "fetch_vix1d_close", None)
    if not callable(fetcher):
        return None
    try:  # pragma: no cover - network guarded
        value = fetcher()
        if value is None or not np.isfinite(value):
            return None
        return float(value)
    except Exception as exc:  # pragma: no cover - provider guard
        LOG.warning("Failed to fetch vix1d close: %s", exc)
        return None


def _coerce_to_date(value: date | datetime | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise TypeError(f"Unsupported date value: {value!r}")


def _compute_em_from_chain(
    spot_close: float,
    chain: pd.DataFrame,
    target_days: float = 1.0,
) -> Optional[Dict[str, Any]]:
    if spot_close is None or not np.isfinite(spot_close) or spot_close <= 0:
        return None
    df = chain.copy()
    if df.empty:
        return None
    if "type" in df.columns and "option_type" not in df.columns:
        df = df.rename(columns={"type": "option_type"})
    if "mid" in df.columns and "prev_close_mid" not in df.columns:
        df = df.rename(columns={"mid": "prev_close_mid"})
    types = df.get("option_type")
    if types is None:
        return None
    types = types.astype(str).str.upper()
    calls = df.loc[types == "C", "prev_close_mid"].dropna()
    puts = df.loc[types == "P", "prev_close_mid"].dropna()
    if calls.empty or puts.empty:
        return None
    call_mid = float(calls.iloc[0])
    put_mid = float(puts.iloc[0])
    straddle = call_mid + put_mid
    em_pct = straddle / spot_close
    em_abs = spot_close * em_pct
    if "strike" in df.columns:
        strike_series = df["strike"].dropna()
        atm_strike = float(strike_series.iloc[0]) if not strike_series.empty else float(spot_close)
    else:
        atm_strike = float(spot_close)
    return {
        "target_days": float(target_days),
        "spot_close": float(spot_close),
        "atm_strike": atm_strike,
        "call_price": call_mid,
        "put_price": put_mid,
        "expected_move_pct": em_pct,
        "em_low": spot_close - em_abs,
        "em_high": spot_close + em_abs,
        "em_low_1_5": spot_close - em_abs * 1.5,
        "em_high_1_5": spot_close + em_abs * 1.5,
        "em_low_2": spot_close - em_abs * 2.0,
        "em_high_2": spot_close + em_abs * 2.0,
    }


class PolygonOptionChainProvider(OptionChainProvider):
    def __init__(self, config: Optional[Mapping[str, Any]] = None):
        super().__init__()
        self.config: Dict[str, Any] = dict(config or {})
        self.metrics: Dict[str, Any] = {
            "http_calls": 0,
            "max_http_calls": self.config.get("max_api_calls_per_day"),
        }
        self._spot_override: Optional[float] = None
        self._local_chain_cache: Dict[tuple[str, date], pd.DataFrame] = {}

    def set_spot_price(self, spot: Optional[float]) -> None:
        self._spot_override = float(spot) if spot is not None else None

    def fetch_available_expiries(self, ticker: str, as_of: date) -> List[date]:
        expiries = {
            next_trading_day(as_of),
            last_trading_day_of_week(as_of),
            last_trading_day_of_next_week(as_of),
            last_trading_day_of_month(as_of),
        }
        lookahead = int(self.config.get("expiries_lookahead_days", 45))
        current = as_of
        limit = as_of + timedelta(days=max(1, lookahead))
        while current <= limit:
            if current.weekday() == 4 and is_trading_day(current):
                expiries.add(current)
            current += timedelta(days=1)
        expiries = {d for d in expiries if d is not None and d > as_of}
        return sorted(expiries)

    def fetch_chain_snapshot(
        self,
        ticker: str,
        expiry: date,
        as_of: date,
        strike_band: Optional[int] = None,
    ) -> pd.DataFrame:
        strike_band = strike_band or int(self.config.get("strike_band", 10))
        spot_close = self._spot_override or self.fetch_spot_close(ticker, as_of)
        if spot_close is None:
            return pd.DataFrame()
        local_chain = self._load_local_chain(ticker, as_of)
        if not local_chain.empty and "expiration_date" in local_chain.columns:
            subset = local_chain[
                pd.to_datetime(local_chain["expiration_date"], errors="coerce").dt.date == expiry
            ]
            if not subset.empty:
                df = subset.copy()
                df["spot_close"] = df.get("spot_close").fillna(spot_close)
                df["as_of"] = as_of
                return df
        max_calls = self.metrics.get("max_http_calls")
        http_calls = int(self.metrics.get("http_calls", 0) or 0)
        if max_calls and http_calls >= max_calls:
            LOG.warning("Polygon HTTP call budget reached (%s)", max_calls)
            return pd.DataFrame()
        if polygon_provider is None:
            LOG.debug("Polygon provider module unavailable; skipping live chain fetch")
            return pd.DataFrame()
        try:  # pragma: no cover - network guarded
            self.metrics["http_calls"] = http_calls + 1
            df = polygon_provider.fetch_atm_option_chain(
                ticker=ticker,
                spot_price=float(spot_close),
                expiration_date=expiry.isoformat(),
                strike_spacing=strike_band,
                config=self.config,
                metrics=self.metrics,
            )
        except Exception as exc:  # pragma: no cover - provider guard
            LOG.warning("Polygon chain fetch failed: %s", exc)
            return pd.DataFrame()
        if df.empty:
            return df
        df = df.copy()
        df["spot_close"] = spot_close
        df["as_of"] = as_of
        df["expiration_date"] = expiry
        return df

    def _load_local_chain(self, ticker: str, as_of: date) -> pd.DataFrame:
        key = (ticker.lower(), as_of)
        if key in self._local_chain_cache:
            return self._local_chain_cache[key]
        df = _load_local_chain_snapshot(ticker, as_of)
        if not df.empty and "expiration_date" in df.columns:
            df = df.copy()
            df["expiration_date"] = (
                pd.to_datetime(df["expiration_date"], errors="coerce").dt.date
            )
        self._local_chain_cache[key] = df
        return df

    def fetch_spot_close(self, ticker: str, as_of: Optional[date] = None) -> Optional[float]:
        if self._spot_override is not None:
            return self._spot_override
        if polygon_provider is None:
            return None
        try:  # pragma: no cover - provider guard
            return polygon_provider.fetch_spot_close_polygon(
                ticker=ticker,
                config=self.config,
                metrics=self.metrics,
            )
        except Exception as exc:  # pragma: no cover
            LOG.warning("Polygon spot fetch failed: %s", exc)
            return None

    def fetch_vix1d_close(self) -> Optional[float]:
        if polygon_provider is None:
            return None
        try:  # pragma: no cover - provider guard
            return polygon_provider.fetch_vix1d(
                config=self.config,
                metrics=self.metrics,
            )
        except Exception as exc:
            LOG.warning("Polygon vix1d fetch failed: %s", exc)
            return None


def load_expected_moves_manifest() -> Dict[str, Any]:
    path = options_manifest_path()
    if not path.exists():
        return {}
    with path.open("r") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class ExpectedMoveHorizon:
    key: str
    label: str
    target_days: Any
    use_expiration: str


@dataclass
class ExpectedMovesConfig:
    spot_ticker: str
    provider: str
    max_api_calls_per_day: int
    horizons: List[ExpectedMoveHorizon]
    confidence_levels: List[float]
    weekly_reference: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_dir: str = "config") -> "ExpectedMovesConfig":
        raw = load_named_config("expected_moves", config_dir)
        horizons = []
        for key, payload in (raw.get("horizons") or {}).items():
            horizons.append(
                ExpectedMoveHorizon(
                    key=key,
                    label=payload.get("label", key),
                    target_days=payload.get("target_days"),
                    use_expiration=payload.get("use_expiration", "nearest"),
                )
            )
        return cls(
            spot_ticker=raw.get("spot_ticker", "SPY"),
            provider=raw.get("provider", "polygon"),
            max_api_calls_per_day=int(raw.get("max_api_calls_per_day", 0)),
            horizons=horizons,
            confidence_levels=list(raw.get("confidence_levels") or []),
            weekly_reference=raw.get("weekly_reference") or {},
        )


class ExpectedMovesCalculator:
    def __init__(self, config: ExpectedMovesConfig):
        self.config = config

    def _ensure_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def _load_existing(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=EM_DASHBOARD_COLUMNS)
        df = pd.read_parquet(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        return _ensure_em_dashboard_columns(df)

    def _write_parquet(self, path: Path, df: pd.DataFrame) -> Path:
        self._ensure_dir(path)
        df.to_parquet(path, index=False)
        return path

    def _merge_history(self, path: Path, todays: pd.DataFrame) -> pd.DataFrame:
        hist = self._load_existing(path)
        combined = pd.concat([hist, todays], ignore_index=True)
        combined["date_key"] = pd.to_datetime(combined["date"]).dt.date
        combined = combined.sort_values(["date_key", "horizon", "confidence_band"])
        combined = combined.drop_duplicates(
            subset=["date_key", "horizon", "confidence_band"], keep="last"
        )
        combined = combined.drop(columns=["date_key"])
        return combined

    def _get_available_expiries(
        self,
        provider: OptionChainProvider,
        ticker: str,
        as_of: date,
    ) -> List[date]:
        if hasattr(provider, "fetch_available_expiries"):
            try:
                return list(provider.fetch_available_expiries(ticker, as_of))
            except Exception as exc:  # pragma: no cover - provider guard
                LOG.warning("Failed to fetch expiries: %s", exc)
                return []
        return []

    def _canonicalize_rows(
        self,
        as_of: date,
        rows: pd.DataFrame,
        horizon_resolutions: List[HorizonResolution],
    ) -> pd.DataFrame:
        if rows is None or rows.empty:
            return pd.DataFrame(columns=EM_DASHBOARD_COLUMNS)
        rows = rows.copy()
        rows = rows[rows.get("confidence_band", False) == False]
        rows = rows.dropna(subset=["horizon"])
        rows["horizon"] = rows["horizon"].apply(
            lambda h: EM_HORIZON_NAME_MAP.get(str(h), h)
        )
        rows = rows[rows["horizon"].isin(PRIMARY_HORIZONS)]
        if rows.empty:
            return rows
        rows = rows.sort_values("horizon")
        rows = rows.drop_duplicates(subset=["horizon"], keep="first")
        meta = {res.horizon: res for res in horizon_resolutions}
        for idx, row in rows.iterrows():
            res = meta.get(row["horizon"])
            if not res:
                continue
            rows.at[idx, "date"] = as_of
            rows.at[idx, "horizon_label"] = row["horizon"]
            rows.at[idx, "target_date"] = res.target_date
            rows.at[idx, "target_days"] = float(res.target_days)
        rows = _ensure_em_dashboard_columns(rows)
        return rows

    def _build_manifest(
        self,
        as_of: date,
        ticker: str,
        horizon_resolutions: List[HorizonResolution],
        present_horizons: Iterable[str],
        metadata: Optional[Mapping[str, Any]] = None,
        spot_close: Optional[float] = None,
        vix1d_close: Optional[float] = None,
    ) -> Path:
        statuses: List[Dict[str, Any]] = []
        present = set(present_horizons)
        for res in horizon_resolutions:
            status = "ok" if res.horizon in present else "missing_data"
            if res.chosen_expiry is None:
                status = "missing_expiry"
            if res.horizon == WEEKLY_REFERENCE_HORIZON and res.horizon not in present:
                status = "not_requested"
            statuses.append(
                {
                    "horizon": res.horizon,
                    "status": status,
                    "target_date": res.target_date.isoformat(),
                }
            )
        payload = {
            "as_of": as_of.isoformat(),
            "ticker": ticker,
            "spot_close": spot_close,
            "vix1d_close": vix1d_close,
            "horizon_status": statuses,
        }
        if metadata:
            payload.update(metadata)
        path = options_manifest_path()
        self._ensure_dir(path)
        with path.open("w") as fh:
            json.dump(payload, fh, indent=2, default=str)
        return path

    def _build_weekly_reference(
        self,
        ticker: str,
        as_of: date,
    ) -> Optional[Path]:
        prices = _load_raw_prices(ticker)
        if prices.empty:
            return None
        target = last_trading_day_of_previous_week(as_of)
        ref = prices[prices["date"] == target]
        if ref.empty:
            return None
        out = ref.tail(1).copy()
        out["as_of"] = as_of
        path = options_weekly_reference_path(ticker)
        self._ensure_dir(path)
        out.to_parquet(path, index=False)
        return path

    def build_for_day(
        self,
        as_of: date,
        spot_close: float,
        chain: pd.DataFrame,
        vix1d_close: Optional[float] = None,
        weekly_ref: bool = False,
        provider: Optional[OptionChainProvider] = None,
        ticker: Optional[str] = None,
        use_em_core_pipeline: bool = False,
        manifest_metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Path]:
        ticker = ticker or self.config.spot_ticker
        outputs: Dict[str, Path] = {}

        if use_em_core_pipeline:
            provider = provider or MockOptionChainProvider(spot_close=spot_close)
            expiries = self._get_available_expiries(provider, ticker, as_of)
            horizon_resolutions = resolve_horizons(as_of, expiries)
            em_core_df, _ = compute_expected_moves_for_horizons(
                provider=provider,
                ticker=ticker,
                horizon_resolutions=horizon_resolutions,
            )
            dashboard = adapt_em_core_to_dashboard_schema(
                em_core_df, vix1d_close=vix1d_close
            )
            canonical = self._canonicalize_rows(as_of, dashboard, horizon_resolutions)
            if canonical.empty or len(canonical["horizon"].unique()) < len(
                PRIMARY_HORIZONS
            ):
                return outputs
            em_path = options_expected_moves_path(ticker)
            merged = self._merge_history(em_path, canonical)
            outputs["expected_moves"] = self._write_parquet(em_path, merged)
            manifest_path = self._build_manifest(
                as_of,
                ticker,
                horizon_resolutions,
                canonical["horizon"].unique(),
                metadata=manifest_metadata,
                spot_close=spot_close,
                vix1d_close=vix1d_close,
            )
            outputs["manifest"] = manifest_path
        else:
            em_row = _compute_em_from_chain(spot_close, chain)
            if not em_row:
                return outputs
            df = pd.DataFrame(
                [
                    {
                        "date": as_of,
                        "horizon": "Next Session",
                        "horizon_label": "Next Session",
                        "target_date": next_trading_day(as_of),
                        **em_row,
                        "vix1d_close": vix1d_close,
                        "confidence_band": False,
                    }
                ]
            )
            df = _ensure_em_dashboard_columns(df)
            em_path = options_expected_moves_path(ticker)
            merged = self._merge_history(em_path, df)
            outputs["expected_moves"] = self._write_parquet(em_path, merged)

        if weekly_ref:
            weekly_path = self._build_weekly_reference(ticker, as_of)
            if weekly_path:
                outputs["weekly_reference"] = weekly_path

        return outputs


def _default_expected_moves_provider(
    config: ExpectedMovesConfig,
    provider: Optional[OptionChainProvider] = None,
) -> OptionChainProvider:
    if provider is not None:
        return provider
    provider_name = (config.provider or "polygon").lower()
    if provider_name == "mock":
        return MockOptionChainProvider()
    return PolygonOptionChainProvider(
        {
            "max_api_calls_per_day": config.max_api_calls_per_day,
            "provider": provider_name,
        }
    )


def build_expected_moves_history(
    start: date | datetime | str,
    end: Optional[date | datetime | str] = None,
    ticker: Optional[str] = None,
    provider: Optional[OptionChainProvider] = None,
    include_weekly_reference: bool = True,
    use_em_core_pipeline: bool = True,
    config: Optional[ExpectedMovesConfig] = None,
) -> List[Dict[str, Any]]:
    cfg = config or ExpectedMovesConfig.load()
    ticker = (ticker or cfg.spot_ticker).upper()
    start_date = _coerce_to_date(start)
    end_date = _coerce_to_date(end) if end else start_date
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    provider = _default_expected_moves_provider(cfg, provider)
    calc = ExpectedMovesCalculator(cfg)
    prices = _load_raw_prices(ticker)
    outputs: List[Dict[str, Any]] = []
    for as_of in _iter_trading_days(start_date, end_date):
        spot_close = _spot_from_prices(prices, as_of)
        if spot_close is None:
            fetch_spot = getattr(provider, "fetch_spot_close", None)
            if callable(fetch_spot):
                spot_close = fetch_spot(ticker, as_of)
        if spot_close is None:
            LOG.warning("Skipping %s for %s: no spot close", ticker, as_of)
            continue
        _provider_set_spot_override(provider, spot_close)
        vix1d_close = _fetch_vix_from_provider(provider)
        chain = _load_local_chain_snapshot(ticker, as_of)
        artifacts = calc.build_for_day(
            as_of=as_of,
            spot_close=spot_close,
            chain=chain,
            vix1d_close=vix1d_close,
            weekly_ref=include_weekly_reference,
            provider=provider,
            ticker=ticker,
            use_em_core_pipeline=use_em_core_pipeline,
            manifest_metadata={"mode": "history"},
        )
        outputs.append({"date": as_of, "artifacts": artifacts})
    return outputs


def update_expected_moves(
    ticker: Optional[str] = None,
    lookback_days: int = 5,
    provider: Optional[OptionChainProvider] = None,
    end: Optional[date | datetime | str] = None,
    include_weekly_reference: bool = False,
    use_em_core_pipeline: bool = True,
    config: Optional[ExpectedMovesConfig] = None,
) -> List[Dict[str, Any]]:
    cfg = config or ExpectedMovesConfig.load()
    ticker = (ticker or cfg.spot_ticker).upper()
    end_date = _coerce_to_date(end) if end else date.today()
    lookback_days = max(1, int(lookback_days or 1))
    start_date = end_date - timedelta(days=lookback_days - 1)
    existing = options_expected_moves_path(ticker)
    if existing.exists():
        try:
            hist = pd.read_parquet(existing, columns=["date"])
        except Exception as exc:  # pragma: no cover - parquet guard
            LOG.warning("Failed to read existing expected moves %s: %s", existing, exc)
            hist = pd.DataFrame()
        if not hist.empty and "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"], errors="coerce").dt.date
            last_date = hist["date"].dropna().max()
            if isinstance(last_date, date):
                start_date = min(start_date, last_date)
    return build_expected_moves_history(
        start=start_date,
        end=end_date,
        ticker=ticker,
        provider=provider,
        include_weekly_reference=include_weekly_reference,
        use_em_core_pipeline=use_em_core_pipeline,
        config=cfg,
    )


__all__ = [
    "ExpectedMovesConfig",
    "ExpectedMovesCalculator",
    "PolygonOptionChainProvider",
    "EM_DASHBOARD_COLUMNS",
    "_compute_em_from_chain",
    "_confidence_bands_from_vix1d",
    "load_expected_moves_manifest",
    "build_expected_moves_history",
    "update_expected_moves",
]
