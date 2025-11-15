from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List

from mie_lib.utils.config import load_named_config
from mie_lib.utils.tickers import resolve_tickers


@lru_cache(maxsize=1)
def _load_policies() -> dict:
    try:
        data = load_named_config("page_ticker_policies")
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return data or {}


def get_page_tickers(
    page_id: str,
    extra_include: Iterable[str] | None = None,
    extra_exclude: Iterable[str] | None = None,
    *,
    require_all: bool = False,
) -> List[str]:
    policies = _load_policies()
    policy = policies.get(page_id) or policies.get("default") or {
        "include_groups": ["all"],
        "exclude_groups": [],
    }

    include = list(policy.get("include_groups", []))
    exclude = list(policy.get("exclude_groups", []))
    if extra_include:
        include.extend(extra_include)
    if extra_exclude:
        exclude.extend(extra_exclude)
    include = include or ["all"]

    return resolve_tickers(include=include, exclude=exclude, require_all=require_all)
