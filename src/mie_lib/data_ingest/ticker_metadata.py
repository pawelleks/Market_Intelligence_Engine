from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from mie_lib.utils.logging import get_logger

LOG = get_logger("ticker-metadata")

METADATA_DIR = Path("data/meta/ticker_metadata")
METADATA_DIR.mkdir(parents=True, exist_ok=True)

_CACHE_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _filename_for(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace(" ", "_")
    return METADATA_DIR / f"{safe}.json"


def fetch_metadata_from_yf(ticker: str) -> Dict[str, Any] | None:
    """Fetch ticker metadata from yfinance. Returns dict or None on failure."""
    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover - optional dependency
        LOG.warning("yfinance unavailable for metadata fetch: %s", exc)
        return None

    try:
        ticker_obj = yf.Ticker(ticker)
        payload = ticker_obj.info or {}
        if not payload:
            # Some ETFs expose metadata via fast_info
            payload = getattr(ticker_obj, "fast_info", {}) or {}
    except Exception as exc:  # pragma: no cover - network errors
        LOG.warning("yfinance metadata fetch failed for %s: %s", ticker, exc)
        return None

    if not payload:
        LOG.warning("yfinance returned empty metadata for %s", ticker)
        return None

    return {
        "ticker": ticker,
        "fetched_at": _now().isoformat(),
        "data": payload,
    }


def save_metadata_cache(ticker: str, payload: Dict[str, Any]) -> None:
    path = _filename_for(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def load_metadata_cache(ticker: str) -> Dict[str, Any] | None:
    path = _filename_for(ticker)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        LOG.exception("Failed to read metadata cache for %s", ticker)
        return None


def _is_stale(entry: Dict[str, Any]) -> bool:
    ts = entry.get("fetched_at")
    if not ts:
        return True
    try:
        fetched = datetime.fromisoformat(ts)
    except Exception:
        return True
    return (_now() - fetched) > _CACHE_TTL


def ensure_ticker_metadata(ticker: str, *, force_refresh: bool = False) -> Dict[str, Any] | None:
    """Return cached metadata dict (yfinance payload). Refresh if stale or forced."""
    cached = load_metadata_cache(ticker)
    if cached and not force_refresh and not _is_stale(cached):
        return cached.get("data") or {}

    fresh = fetch_metadata_from_yf(ticker)
    if fresh:
        save_metadata_cache(ticker, fresh)
        return fresh.get("data") or {}

    # fall back to previously cached data even if stale
    if cached:
        return cached.get("data") or {}
    return None