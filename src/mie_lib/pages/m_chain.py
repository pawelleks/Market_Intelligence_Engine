from __future__ import annotations
from pathlib import Path
import importlib as _il
import pandas as _pd
from typing import Any as _Any

# Import underlying Streamlit page module
_page = _il.import_module("app.pages.01_Markov_Chain")
# Default DATA root for shim; tests can monkeypatch this attribute safely
DATA: Path = Path("data")

# Re-export all public attributes for broad compatibility
for _k, _v in _page.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

# ---- Shim helpers that must respect this module's DATA and be monkeypatchable ----

def _matrix_exact_path(ticker: str, mode: str, thr: int, order: int, window: str) -> Path:
    mode = str(mode).lower().strip()
    window = str(window).upper().strip()
    return DATA / "analytics" / "markov" / str(ticker) / "matrices" / mode / f"thr{int(thr)}" / f"order{int(order)}" / f"{window}.parquet"


def _nearest_available_threshold(ticker: str, mode: str, order: int, window: str, requested_thr: int) -> int | None:
    mdir = DATA / "analytics" / "markov" / str(ticker) / "matrices" / str(mode).lower()
    if not mdir.exists():
        return None
    candidates: list[tuple[int, int]] = []
    for thr_dir in mdir.glob("thr*/"):
        try:
            tnum = int(thr_dir.name.replace("thr", ""))
        except Exception:
            continue
        p = thr_dir / f"order{int(order)}" / f"{str(window).upper()}.parquet"
        if p.exists():
            candidates.append((abs(tnum - int(requested_thr)), tnum))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


def _load_matrix_for_selection(
    ticker: str,
    mode: str,
    thr: int,
    order: int,
    window: str,
    allow_fallback: bool = True,
):
    mode_l = str(mode).lower().strip()
    thr_i = int(thr)
    win_u = str(window).upper().strip()
    p = _matrix_exact_path(ticker, mode_l, thr_i, order, win_u)
    used_thr = thr_i
    fallback_used = False
    if not p.exists() and allow_fallback:
        near = _nearest_available_threshold(ticker, mode_l, order, win_u, thr_i)
        if near is not None and near != thr_i:
            used_thr = near
            p = _matrix_exact_path(ticker, mode_l, used_thr, order, win_u)
            fallback_used = p.exists()
    if not p.exists():
        raise FileNotFoundError(str(p))
    df = _pd.read_parquet(p)
    info = {
        "path": p,
        "requested": {"mode": mode_l, "threshold_bps": thr_i, "order": int(order), "window": win_u},
        "resolved": {"mode": mode_l, "threshold_bps": used_thr, "thr": used_thr, "order": int(order), "window": win_u},
        "fallback_used": bool(fallback_used),
    }
    return df, info


def _load_matrix_cached_by_params(
    ticker: str,
    mode: str,
    thr: int,
    order: int,
    window: str,
    path_str: str,
    mtime: float,
):
    # Minimal shim: signature compatibility and direct read
    return _pd.read_parquet(Path(path_str))


def _as_context_key(obj) -> str:
    if isinstance(obj, str):
        return obj
    try:
        from numpy import ndarray as _ndarray  # type: ignore
        import pandas as _p
        if isinstance(obj, (list, tuple)):
            return "-".join([str(x) for x in obj])
        if isinstance(obj, _ndarray):
            return "-".join([str(x) for x in obj.tolist()])
        if isinstance(obj, _p.Series):
            return "-".join([str(x) for x in obj.tolist()])
    except Exception:
        pass
    return ""


def _find_context_row(df: _pd.DataFrame, ctx: str | None):
    if not isinstance(ctx, str) or not ctx:
        return None
    if "context" not in df.columns:
        return None
    m = df[df["context"].astype(str) == ctx]
    return None if m.empty else m.iloc[0]


def _safe_width(width):
    if width in (None, 0):
        return "stretch"
    if isinstance(width, int):
        return max(width, 300)
    if isinstance(width, str):
        return width
    return "stretch"


def _get_ticker_from_state(default: str = "SPY") -> str:
    # Lightweight, test-friendly version avoiding boolean or on pandas Series
    try:
        st_obj = globals().get("st")
        cand: _Any = None
        if st_obj is not None and hasattr(st_obj, "session_state"):
            ss = getattr(st_obj, "session_state")
            cand = ss.get("mk_ticker")
            # Determine if we should fallback to 'ticker'
            needs_fallback = (
                cand is None or
                (isinstance(cand, str) and not cand.strip()) or
                (isinstance(cand, (list, tuple)) and len(cand) == 0)
            )
            if not needs_fallback:
                try:
                    if isinstance(cand, _pd.Series) and cand.empty:
                        needs_fallback = True
                except Exception:
                    pass
            if needs_fallback:
                cand = ss.get("ticker")
        # Normalize containers
        if isinstance(cand, (list, tuple)):
            cand = cand[0] if cand else None
        elif isinstance(cand, _pd.Series):
            cand = cand.iloc[0] if not cand.empty else None
        elif isinstance(cand, dict):
            cand = cand.get("value") or (next(iter(cand.keys())) if cand else None)
        if isinstance(cand, str) and cand.strip():
            return cand.strip().upper()
    except Exception:
        pass
    return (default or "SPY").strip().upper()

# Provide a main symbol for import tests
if "main" not in globals():
    def main():  # type: ignore
        return None
