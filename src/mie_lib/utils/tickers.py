from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

from mie_lib.utils.config import load_named_config
from mie_lib.data_ingest.ticker_metadata import ensure_ticker_metadata


@dataclass
class TickerMeta:
    ticker: str
    name: str | None = None
    sector: str | None = None
    groups: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()


def _normalize_symbol(symbol: str) -> str:
    sym = (symbol or "").strip()
    if not sym:
        return ""
    if sym.startswith("^"):
        return "^" + sym[1:].upper()
    return sym.upper()


@lru_cache(maxsize=1)
def _registry_cache() -> Dict[str, Dict]:
    cfg = load_named_config("tickers")
    registry: Dict[str, Dict] = {
        "groups": cfg.get("groups", {}) if isinstance(cfg, dict) else {},
        "defaults": cfg.get("defaults", {}) if isinstance(cfg, dict) else {},
        "tickers": {},
    }

    raw_tickers = None
    if isinstance(cfg, dict):
        raw_tickers = cfg.get("tickers")
    elif isinstance(cfg, list):
        raw_tickers = cfg

    if isinstance(raw_tickers, list):
        items = {str(t): {} for t in raw_tickers}
    elif isinstance(raw_tickers, dict):
        items = raw_tickers
    else:
        items = {}

    for symbol, meta in items.items():
        sym = str(symbol).strip()
        if not sym:
            continue
        normalized = _normalize_symbol(sym)
        data = meta or {}
        groups = data.get("groups") or []
        aliases = data.get("aliases") or []
        registry["tickers"][normalized] = {
            "symbol": sym,
            "name": data.get("name"),
            "sector": data.get("sector"),
            "groups": [str(g).strip().lower() for g in groups if str(g).strip()],
            "aliases": tuple(str(a).strip() for a in aliases if str(a).strip()),
        }

    # If config was a bare list without groups key, treat entries as tickers
    if not registry["tickers"] and isinstance(cfg, list):
        for sym in cfg:
            s = str(sym).strip()
            if not s:
                continue
            registry["tickers"][_normalize_symbol(s)] = {
                "symbol": s,
                "groups": [],
                "aliases": (),
            }

    return registry


def _load_registry(force_refresh: bool = False) -> Dict[str, Dict]:
    if force_refresh:
        _registry_cache.cache_clear()
    return _registry_cache()


def _fallback_groups() -> List[str]:
    reg = _load_registry()
    defaults = reg.get("defaults", {}) or {}
    return list(defaults.get("fallback_groups", [])) or ["single_stock"]


def _hydrate_meta(meta: TickerMeta) -> TickerMeta:
    needs_name = not meta.name
    needs_sector = not meta.sector
    if not (needs_name or needs_sector):
        return meta
    payload = ensure_ticker_metadata(meta.ticker)
    if not payload:
        return meta
    if needs_name:
        meta.name = payload.get("longName") or payload.get("shortName") or payload.get("symbol")
    if needs_sector:
        meta.sector = payload.get("sector")
    return meta


@lru_cache(maxsize=512)
def get_ticker_meta(ticker: str) -> TickerMeta | None:
    symbol = _normalize_symbol(ticker)
    reg = _load_registry()
    entry = reg.get("tickers", {}).get(symbol)
    if not entry:
        return None
    meta = TickerMeta(
        ticker=entry.get("symbol", ticker),
        name=entry.get("name"),
        sector=entry.get("sector"),
        groups=tuple(entry.get("groups", ())),
        aliases=tuple(entry.get("aliases", ())),
    )
    return _hydrate_meta(meta)


def get_all_tickers() -> List[str]:
    reg = _load_registry()
    tickers = [entry.get("symbol") for entry in reg.get("tickers", {}).values() if entry.get("symbol")]
    return sorted(set(tickers))


def get_ticker_groups(ticker: str) -> List[str]:
    meta = get_ticker_meta(ticker)
    return list(meta.groups) if meta else []


def _match_include(groups: set[str], include: List[str], require_all: bool) -> bool:
    include_clean = [g for g in include if g != "all"]
    if not include_clean:
        return True
    include_set = set(include_clean)
    if require_all:
        return include_set.issubset(groups)
    return bool(groups & include_set)


def _matches_filters(meta: TickerMeta, include: List[str], exclude: List[str], require_all: bool) -> bool:
    groups = set(meta.groups)
    include = [g.lower() for g in include]
    exclude = set(g.lower() for g in exclude if g and g.lower() != "all")
    if exclude and groups & exclude:
        return False
    return _match_include(groups, include, require_all)


def tickers_in_groups(
    include: Iterable[str],
    *,
    exclude: Iterable[str] = (),
    require_all: bool = False,
) -> List[str]:
    reg = _load_registry()
    include_list = [g.lower() for g in (include or ["all"])]
    exclude_list = [g.lower() for g in (exclude or [])]
    tickers: List[str] = []
    for entry in reg.get("tickers", {}).values():
        symbol = entry.get("symbol")
        if not symbol:
            continue
        meta = TickerMeta(
            ticker=symbol,
            name=entry.get("name"),
            sector=entry.get("sector"),
            groups=tuple(entry.get("groups", ())),
            aliases=tuple(entry.get("aliases", ())),
        )
        if _matches_filters(meta, include_list, exclude_list, require_all):
            tickers.append(symbol)
    return sorted(dict.fromkeys(tickers))


def tickers_not_in_groups(groups: Iterable[str]) -> List[str]:
    groups_list = [g.lower() for g in groups or []]
    if not groups_list:
        return get_all_tickers()
    reg = _load_registry()
    out: List[str] = []
    for entry in reg.get("tickers", {}).values():
        symbol = entry.get("symbol")
        if not symbol:
            continue
        entry_groups = set(entry.get("groups", ()))
        if not entry_groups.intersection(groups_list):
            out.append(symbol)
    return sorted(dict.fromkeys(out))


def resolve_tickers(
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
    require_all: bool = False,
    default_policy: str = "all",
) -> List[str]:
    include_list = list(include) if include else [default_policy]
    exclude_list = list(exclude) if exclude else []
    return tickers_in_groups(include_list, exclude=exclude_list, require_all=require_all)


def get_ticker_full_name(ticker: str) -> str | None:
    meta = get_ticker_meta(ticker)
    if not meta:
        return None
    return meta.name or meta.ticker


def get_ticker_sector(ticker: str) -> str | None:
    meta = get_ticker_meta(ticker)
    return meta.sector if meta else None


def clear_ticker_cache() -> None:
    """Helper for tests to reset cached registry/meta."""
    _registry_cache.cache_clear()
    get_ticker_meta.cache_clear()