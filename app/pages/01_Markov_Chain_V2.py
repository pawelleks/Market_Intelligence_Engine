"""Streamlit Markov Chain V2 page that consumes Markov snapshot artifacts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

import pandas as pd
import streamlit as st

from app.utils.ticker_policy import get_page_tickers
from mie_lib.analytics.markov.states_model import multi_step
import mie_lib.ui.markov_snapshots as markov_snapshots_ui
from mie_lib.utils.tickers import get_ticker_full_name

st.set_page_config(page_title="Markov Chain V2", layout="wide")

DEFAULT_HORIZONS = [1, 2, 3, 4, 5, 10, 20, 60]
WINDOW_SORT_ORDER = ["1Y", "2Y", "5Y", "10Y", "20Y", "50Y", "MAX"]
STATE_ACRONYMS = {"Green": "G", "Neutral": "N", "Red": "R"}
STATE_NAME_TO_CHAR = {name.upper(): char for name, char in STATE_ACRONYMS.items()}
STATE_NAME_TO_CHAR.update({"UP": "G", "DOWN": "R", "NEUTRAL": "N"})
STATE_CHAR_NORMALIZE = {
    "U": "G",
    "G": "G",
    "N": "N",
    "D": "R",
    "R": "R",
}
DISPLAY_TO_RAW = {"G": "U", "N": "N", "R": "D"}


def _sort_windows(values: Iterable[str]) -> list[str]:
    order_map = {name.upper(): idx for idx, name in enumerate(WINDOW_SORT_ORDER)}
    unique = {str(v).upper() for v in values if str(v).strip()}
    return sorted(unique, key=lambda w: order_map.get(w, len(WINDOW_SORT_ORDER)))


def _available_windows(
    ticker: str,
    mode: str,
    threshold_bps: int,
    order: int,
) -> list[str]:
    windows = markov_snapshots_ui.available_windows_for_combo(ticker, mode, threshold_bps, order)
    if windows:
        return _sort_windows(windows)
    # Fallback to direct filesystem inspection if metadata missing
    matrix_dir = markov_snapshots_ui.matrix_path(ticker, mode, threshold_bps, order, "1Y").parent
    if matrix_dir.exists():
        files = [p.stem for p in matrix_dir.glob("*.parquet") if p.is_file()]
        if files:
            return _sort_windows(files)
    return WINDOW_SORT_ORDER.copy()


def _ticker_caption(ticker: str) -> str:
    friendly = get_ticker_full_name(ticker)
    if friendly and friendly.upper() != ticker.upper():
        return f"{ticker.upper()}: {friendly}"
    return ticker.upper()


def _state_columns_for_mode(mode: str) -> list[str]:
    ordered = ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"]
    if mode == "binary":
        return ["mc_prob_up", "mc_prob_down"]
    return ordered


def _compute_staleness(last_date, today=None):
    """Compute staleness metadata for a snapshot date."""
    if today is None:
        today = date.today()
    elif isinstance(today, datetime):
        today = today.date()
    elif isinstance(today, str):
        today = datetime.fromisoformat(today).date()
    
    if last_date is None:
        return {
            "last_date": None,
            "last_date_iso": None,
            "days_old": None,
            "is_stale": False,
        }
    
    if isinstance(last_date, datetime):
        last_date = last_date.date()
    elif isinstance(last_date, str):
        last_date = datetime.fromisoformat(last_date).date()
    
    days_old = (today - last_date).days
    return {
        "last_date": last_date,
        "last_date_iso": last_date.isoformat(),
        "days_old": days_old,
        "is_stale": days_old > 0,
    }


def _normalize_context(context: str) -> str:
    chars = [STATE_CHAR_NORMALIZE.get(ch.upper(), ch.upper()) for ch in str(context)]
    return "".join(chars)


def _context_short_label(context: str, order: int) -> str:
    if not context:
        return ""
    if order <= 1:
        return markov_snapshots_ui.format_state_name(context[-1])
    return _normalize_context(context)


def _context_hover_label(context: str) -> str:
    if not context:
        return ""
    return markov_snapshots_ui.format_context_label(context)


def _context_sequence_html(context: str) -> str:
    parts = []
    for ch in str(context):
        state = markov_snapshots_ui.format_state_name(ch)
        color = markov_snapshots_ui.state_color(state)
        parts.append(f'<span style="color:{color};font-weight:bold;">{state}</span>')
    return " &rarr; ".join(parts)


def _context_label_html(context: str, order: int) -> str:
    if not context:
        return ""
    compact = _normalize_context(context)
    sequence = _context_sequence_html(context)
    if order <= 1:
        return sequence or compact
    if compact and sequence:
        return f"{compact} ({sequence})"
    return sequence or compact


def _state_span(state: str) -> str:
    color = markov_snapshots_ui.state_color(state)
    return f'<span style="color:{color};font-weight:bold;">{state}</span>'


def _state_chars_from_value(value: object) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    token = text.upper()
    if token in {"U", "N", "D"}:
        display = STATE_CHAR_NORMALIZE.get(token, token)
        return display, token
    mapped = STATE_NAME_TO_CHAR.get(token)
    if mapped:
        display = STATE_CHAR_NORMALIZE.get(mapped, mapped)
        return display, DISPLAY_TO_RAW.get(display)
    base = token[0]
    display = STATE_CHAR_NORMALIZE.get(base, base)
    raw = DISPLAY_TO_RAW.get(display)
    if raw is None and base in {"U", "N", "D"}:
        raw = base
    return display, raw


def _recent_state_sequence(
    states_df: pd.DataFrame | None,
    start_date: str | None,
    end_date: str | None,
) -> list[tuple[str, str]]:
    if states_df is None or states_df.empty:
        return []
    df = states_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        try:
            start = datetime.fromisoformat(str(start_date)).date() if start_date else None
            end = datetime.fromisoformat(str(end_date)).date() if end_date else None
        except Exception:
            start = end = None
        if start and end:
            df = df[(df["date"] >= start) & (df["date"] <= end)]
    df = df.sort_values("date") if "date" in df.columns else df
    state_col = next((col for col in ("mc_state_today", "raw_state", "state", "mc_state") if col in df.columns), None)
    if state_col is None:
        return []
    seq: list[tuple[str, str]] = []
    for value in df[state_col].tolist():
        display, raw = _state_chars_from_value(value)
        if display and raw:
            seq.append((display, raw))
    return seq


def _fallback_context_from_matrix(matrix_df: pd.DataFrame | None) -> tuple[str, str]:
    if matrix_df is None or matrix_df.empty:
        return "", ""
    source = ""
    if "context" in matrix_df.columns and not matrix_df["context"].isna().all():
        source = str(matrix_df["context"].astype(str).iloc[-1]).strip().upper()
    elif isinstance(matrix_df.index, pd.Index) and len(matrix_df.index) > 0:
        idx_val = matrix_df.index[-1]
        if isinstance(idx_val, str):
            source = idx_val.strip().upper()
    if not source:
        return "", ""
    display = "".join(STATE_CHAR_NORMALIZE.get(ch, ch) for ch in source)
    return display, source


def _match_context_row(
    matrix_df: pd.DataFrame | None,
    display_code: str,
    raw_code: str,
) -> pd.Series | None:
    if matrix_df is None or matrix_df.empty:
        return None
    candidates: list[tuple[str, str]] = []
    if display_code:
        candidates.append(("context_display", display_code))
    if raw_code:
        candidates.append(("context", raw_code))
    for column, code in candidates:
        if column in matrix_df.columns:
            series = matrix_df[column].astype(str).str.upper()
            mask = series == code.upper()
            if mask.any():
                return matrix_df.loc[mask].iloc[0]
    for code in filter(None, [display_code, raw_code]):
        try:
            sel = matrix_df.loc[code]
            return sel.iloc[0] if isinstance(sel, pd.DataFrame) else sel
        except Exception:
            continue
    return None


def _select_active_context_row(
    mat_df: pd.DataFrame,
    states_df: pd.DataFrame | None,
    mode: str,
    order: int,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str | None, str | None, pd.Series | None, int]:
    if mat_df is None or mat_df.empty:
        return None, None, None, 0
    seq = _recent_state_sequence(states_df, start_date, end_date)
    if seq:
        display_seq = "".join(display for display, _ in seq)
        raw_seq = "".join(raw for _, raw in seq)
    else:
        display_seq, raw_seq = _fallback_context_from_matrix(mat_df)
    if not display_seq and not raw_seq:
        return None, None, None, 0
    if not raw_seq and display_seq:
        raw_seq = "".join(DISPLAY_TO_RAW.get(ch, ch) for ch in display_seq)
    if not display_seq and raw_seq:
        display_seq = "".join(STATE_CHAR_NORMALIZE.get(ch, ch) for ch in raw_seq)
    max_len = min(int(order), len(display_seq)) if display_seq else int(order)
    max_len = min(max_len, len(raw_seq)) if raw_seq else max_len
    for k in range(max_len, 0, -1):
        disp = display_seq[-k:] if display_seq else ""
        raw = raw_seq[-k:] if raw_seq else ""
        row = _match_context_row(mat_df, disp, raw)
        if row is not None:
            raw_val = str(row.get("context", raw)) if "context" in row else raw
            disp_val = str(row.get("context_display", disp)) if "context_display" in row else disp
            return raw_val or raw, disp_val or disp, row, k
    return None, None, None, 0


def _state_color_alias(name: str) -> str:
    alias = {
        "up": "G",
        "green": "G",
        "down": "R",
        "red": "R",
        "neutral": "N",
        "mid": "N",
    }
    token = alias.get(str(name).lower(), name)
    return markov_snapshots_ui.state_color(token)


def _state_text_with_short(state: str) -> str:
    if not state:
        return ""
    short = STATE_ACRONYMS.get(state, state[:1].upper())
    return f"{state} ({short})"


def _state_html_with_short(state: str) -> str:
    if not state:
        return ""
    short = STATE_ACRONYMS.get(state, state[:1].upper())
    return f"{_state_span(state)} ({short})"


def _context_descriptions(
    ctx_row: pd.Series | None,
    order: int,
    context_override: str | None = None,
) -> dict[str, str]:
    if context_override is not None:
        context_raw = str(context_override)
    else:
        context_raw = str(ctx_row.get("context", "")) if ctx_row is not None else ""
    last_code = context_raw[-1:] if context_raw else ""
    last_state = markov_snapshots_ui.format_state_name(last_code) if last_code else ""
    compact_code = _normalize_context(context_raw) if context_raw else ""
    sequence_plain = markov_snapshots_ui.format_context_label(context_raw) if context_raw else ""
    sequence_html = _context_sequence_html(context_raw) if context_raw else ""
    display_code = compact_code or context_raw
    combined_plain = (
        f"{display_code} ({sequence_plain})"
        if display_code and sequence_plain
        else display_code or sequence_plain
    )
    combined_html = (
        _context_label_html(context_raw, order)
        if context_raw
        else ""
    )
    return {
        "raw": context_raw,
        "compact": compact_code,
        "sequence_html": sequence_html,
        "sequence_plain": sequence_plain,
        "combined_plain": combined_plain,
        "combined_html": combined_html,
        "short": _context_short_label(context_raw, order) if context_raw else "",
        "last_state": last_state,
        "last_state_html": _state_html_with_short(last_state) if last_state else "",
        "last_state_text": _state_text_with_short(last_state) if last_state else "",
    }


def _collect_state_probabilities(ctx_row: pd.Series | None, mode: str) -> dict[str, float]:
    if ctx_row is None:
        return {}
    cols = [c for c in _state_columns_for_mode(mode) if c in ctx_row]
    result: dict[str, float] = {}
    for col in cols:
        value = ctx_row[col]
        if value is None or pd.isna(value):
            continue
        result[markov_snapshots_ui.STATE_COLUMN_LABELS.get(col, col)] = float(value)
    return result


def _continuation_info(ctx_row: pd.Series | None) -> tuple[float | None, str]:
    if ctx_row is None or "context" not in ctx_row:
        return None, ""
    last_code = str(ctx_row["context"])[-1:]
    column = {
        "G": "mc_prob_up",
        "U": "mc_prob_up",
        "N": "mc_prob_neutral",
        "D": "mc_prob_down",
        "R": "mc_prob_down",
    }.get(last_code)
    prob = ctx_row.get(column) if column else None
    label = markov_snapshots_ui.format_state_name(last_code) if last_code else ""
    return (float(prob) if prob is not None else None), label


def _prepare_states_dataframe(states_df: pd.DataFrame | None) -> pd.DataFrame | None:
    if states_df is None or states_df.empty:
        return states_df
    df = states_df.copy()
    if "mc_state_today" not in df.columns:
        for candidate in ("raw_state", "state", "mc_state", "mc_state_now"):
            if candidate in df.columns:
                df["mc_state_today"] = df[candidate]
                break
    if "mc_state_today" in df.columns:
        df["mc_state_today"] = df["mc_state_today"].astype(str).str.upper()
    return df


def _attach_context_display(matrix_df: pd.DataFrame | None, order: int) -> pd.DataFrame | None:
    if matrix_df is None or matrix_df.empty:
        return matrix_df
    if "context_display" in matrix_df.columns and not matrix_df["context_display"].isna().all():
        return matrix_df
    df = matrix_df.copy()
    mapping = {"U": "G", "G": "G", "N": "N", "D": "R", "R": "R"}
    if "context" in df.columns:
        df["context_display"] = df["context"].astype(str).apply(
            lambda ctx: "".join(mapping.get(ch.upper(), ch.upper()) for ch in ctx)
        )
    else:
        df["context_display"] = [
            _context_short_label(str(idx), order) for idx in df.index
        ]
    return df


def _transition_matrix_conclusion(ctx_row: pd.Series | None, order: int, mode: str) -> str:
    probs = _collect_state_probabilities(ctx_row, mode)
    context = _context_descriptions(ctx_row, order)
    if not probs or not context["combined_html"]:
        return ""
    best_state, best_prob = max(probs.items(), key=lambda item: item[1])
    continuation_prob, continuation_label = _continuation_info(ctx_row)
    continuation_html = (
        f" Continuation probability (stay {_state_html_with_short(continuation_label)}) = {markov_snapshots_ui.percent_str(continuation_prob)}."
        if continuation_prob is not None and continuation_label
        else ""
    )
    context_html = context["combined_html"] or context["sequence_html"] or context["short"]
    best_html = _state_html_with_short(best_state)
    return (
        f"<strong>Conclusion:</strong> Given previous context was {context_html}, "
        f"the next state is most likely {best_html} ({markov_snapshots_ui.percent_str(best_prob)})."
        f"{continuation_html}"
    )


def _format_follow_on_states(items: list[tuple[str, float]]) -> str:
    if not items:
        return ""
    parts = [f"{_state_html_with_short(label)} ({markov_snapshots_ui.percent_str(prob)})" for label, prob in items]
    if len(parts) == 1:
        return f"followed by {parts[0]}"
    if len(parts) == 2:
        return f"followed by {parts[0]} and {parts[1]}"
    return f"followed by {', '.join(parts[:-1])}, and {parts[-1]}"


def _one_step_conclusion(ctx_row: pd.Series | None, mode: str, order: int) -> str:
    probs = _collect_state_probabilities(ctx_row, mode)
    if not probs:
        return ""
    ranked = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    first_state, first_prob = ranked[0]
    follow_on = _format_follow_on_states(ranked[1:])
    continuation_prob, continuation_label = _continuation_info(ctx_row)
    context = _context_descriptions(ctx_row, order)
    context_html = context["combined_html"] or context["sequence_html"] or context["short"]
    first_html = _state_html_with_short(first_state)
    continuation_html = (
        f" Continuation probability (stay {_state_html_with_short(continuation_label)}) = {markov_snapshots_ui.percent_str(continuation_prob)}."
        if continuation_prob is not None and continuation_label
        else ""
    )
    narrative = (
        f"<strong>One-step outlook:</strong> Given previous context was {context_html}, "
        f"the most likely next state is {first_html} ({markov_snapshots_ui.percent_str(first_prob)})."
    )
    if follow_on:
        narrative += f" {follow_on}."
    return narrative + continuation_html


def _format_horizon_label(value) -> str:
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        return str(value)
    unit = "day" if abs(as_int) == 1 else "days"
    return f"{as_int} {unit}"


def _multi_horizon_conclusion(
    horizon_df: pd.DataFrame,
    context_info: dict[str, str] | None,
) -> str:
    if horizon_df.empty:
        return ""
    columns = [col for col in horizon_df.columns if col in STATE_ACRONYMS]
    if not columns:
        return ""
    avg_probs = horizon_df[columns].mean()
    if avg_probs.empty:
        return ""
    dominant_state = avg_probs.idxmax()
    first_horizon_label = _format_horizon_label(horizon_df.index[0])
    last_horizon_label = _format_horizon_label(horizon_df.index[-1])
    start_prob = horizon_df.iloc[0][dominant_state]
    end_prob = horizon_df.iloc[-1][dominant_state]
    bias_parts = []
    for col in columns:
        short = STATE_ACRONYMS.get(col, col[:1].upper())
        bias_parts.append(f"{col} ({short}) ≈ {markov_snapshots_ui.percent_str(avg_probs[col])}")
    context_html = ""
    context_plain = ""
    if context_info:
        context_html = context_info.get("combined_html") or context_info.get("sequence_html") or context_info.get("short", "")
        context_plain = context_info.get("combined_plain") or context_info.get("sequence_plain") or context_info.get("short", "")
    context_label = context_html or context_plain
    dominant_short = STATE_ACRONYMS.get(dominant_state, dominant_state[:1].upper())
    dominant_label = f"{dominant_state} ({dominant_short})"
    return (
        f"Start context: {context_label}. Overall bias: {', '.join(bias_parts)}. "
        f"{dominant_label} probability changes from {markov_snapshots_ui.percent_str(start_prob)} at {first_horizon_label} "
        f"to {markov_snapshots_ui.percent_str(end_prob)} at {last_horizon_label}."
    )


@st.cache_data(show_spinner=False)
def _cached_matrix(ticker: str, mode: str, threshold: int, order: int, window: str):
    df = markov_snapshots_ui.load_snapshot_matrix(ticker, mode, threshold, order, window)
    return df.copy() if df is not None else None


@st.cache_data(show_spinner=False)
def _cached_states(ticker: str, mode: str, threshold: int):
    df = markov_snapshots_ui.load_snapshot_states(ticker, mode, threshold)
    return df.copy() if df is not None else None


def _resolve_tickers() -> list[str]:
    configured = [t.upper() for t in (get_page_tickers("01_Markov_Chain_V2") or []) if t]
    snapshot_dirs = markov_snapshots_ui.list_snapshot_tickers()
    if configured:
        filtered = [t for t in configured if t in snapshot_dirs]
        if filtered:
            return filtered
    return snapshot_dirs or ["SPY"]


def _format_matrix_for_display(df: pd.DataFrame | None, *, order: int, mode: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cols = _state_columns_for_mode(mode)
    available_prob_cols = [col for col in cols if col in df.columns]
    extras = [col for col in ("row_sum", "counts") if col in df.columns]
    if not available_prob_cols and not extras:
        return pd.DataFrame()
    display = df.copy()
    display["ContextDisplay"] = display["context"].apply(lambda c: _context_short_label(c, order))
    display = display.set_index("ContextDisplay")
    rename_map = {
        "mc_prob_up": "Green",
        "mc_prob_neutral": "Neutral",
        "mc_prob_down": "Red",
        "row_sum": "Row Sum",
        "counts": "Counts",
    }
    ordered_cols = available_prob_cols + extras
    subset = display[ordered_cols].rename(columns={k: v for k, v in rename_map.items() if k in ordered_cols})
    percent_targets = [rename_map.get(col, col) for col in available_prob_cols + (["row_sum"] if "row_sum" in extras else [])]
    for col in percent_targets:
        if col in subset.columns:
            subset[col] = subset[col].apply(markov_snapshots_ui.percent_str)
    if "Counts" in subset.columns:
        subset["Counts"] = subset["Counts"].apply(lambda x: "" if pd.isna(x) else int(x))
    subset.index.name = "Context"
    return subset



def _render_diagnostics(
    *,
    ticker: str,
    state_mode: str,
    threshold_bps: int,
    order: int,
    window_key: str,
    matrix_df: pd.DataFrame | None,
    ctx_row: pd.Series | None,
    matrix_file: Path | str | None,
    window_meta: dict,
) -> None:
    with st.expander("Diagnostics / Debug"):
        st.write("Matrix snapshot", matrix_file)
        st.json(
            {
                "ticker": ticker,
                "state_mode": state_mode,
                "threshold_bps": threshold_bps,
                "order": order,
                "window": window_key,
                "matrix_rows": 0 if matrix_df is None else len(matrix_df),
                "context_active": ctx_row.get("context") if ctx_row is not None else None,
                "window_metadata": window_meta,
                "snapshot_root": str(markov_snapshots_ui.SNAPSHOT_ROOT),
            }
        )
        if matrix_df is not None:
            raw_cols = markov_snapshots_ui.raw_matrix_columns(matrix_df)
            if not raw_cols.empty:
                st.dataframe(raw_cols, use_container_width=True)
        st.caption("Use cli/mie.py build-markov-grid followed by build-markov-snapshots to refresh inputs.")


def _prepare_heatmap_frame(df: pd.DataFrame, *, mode: str, order: int) -> tuple[pd.DataFrame, list[str]]:
    cols = [col for col in _state_columns_for_mode(mode) if col in df.columns]
    if df.empty or not cols:
        return pd.DataFrame(), []
    frame = df[["context"] + cols].copy()
    frame["context_short"] = frame["context"].apply(lambda c: _context_short_label(c, order))
    frame["context_hover"] = frame["context"].apply(_context_hover_label)
    return frame, cols


def _build_multi_horizon_table(
    matrix_df: pd.DataFrame | None,
    horizons: list[int],
    mode: str,
) -> pd.DataFrame:
    """Return a numeric multi-horizon probability table indexed by horizon days."""

    if matrix_df is None or matrix_df.empty or not horizons:
        return pd.DataFrame()

    horizon_df = multi_step(matrix_df, horizons, mode)
    if horizon_df is None or horizon_df.empty:
        return pd.DataFrame()

    ordered_unique: list[int] = []
    seen: set[int] = set()
    for value in horizons:
        try:
            horizon_value = int(value)
        except (TypeError, ValueError):
            continue
        if horizon_value in horizon_df.index and horizon_value not in seen:
            ordered_unique.append(horizon_value)
            seen.add(horizon_value)
    if not ordered_unique:
        ordered_unique = list(horizon_df.index)

    ordered_df = horizon_df.loc[ordered_unique].copy()
    rename_map = {
        col: markov_snapshots_ui.STATE_COLUMN_LABELS.get(col, col)
        for col in ordered_df.columns
    }
    renamed = ordered_df.rename(columns=rename_map)
    renamed.index.name = "Horizon (days)"
    return renamed


def main():
    st.title("Markov Chain V2")
    tickers = _resolve_tickers()
    with st.sidebar:
        st.header("Markov Chain V2")
        ticker = st.selectbox("Ticker", tickers)
        state_mode = st.radio("State Mode", ["binary", "tri"], index=1, horizontal=True)
        threshold_bps = st.slider("Threshold (bps)", 0, 150, 10, 5)
        order = st.slider("Order (K)", 1, 4, 1)
        windows = _available_windows(ticker, state_mode, threshold_bps, order)
        preferred_index = windows.index("5Y") if "5Y" in windows else 0
        window_key = st.selectbox("Window", windows, index=preferred_index)
        horizon_start, horizon_end = st.slider("Horizons (days)", 1, 5, (1, 5))
        horizons = list(range(horizon_start, min(horizon_end, 5) + 1))
        if st.button("🔄 Clear snapshot cache & reload"):
            st.cache_data.clear()
            st.experimental_rerun()

    friendly_name = get_ticker_full_name(ticker)
    name_caption = ticker.upper()
    if friendly_name and friendly_name.upper() != ticker.upper():
        name_caption = f"{ticker.upper()} – {friendly_name}"
    horizons_label = f"{horizon_start}–{horizon_end}" if horizon_start != horizon_end else str(horizon_start)
    config_summary = (
        f"{name_caption} • Mode: {state_mode} • Threshold: {threshold_bps} bps • "
        f"Order: {order} • Window: {window_key} • Horizons: {horizons_label} days"
    )
    st.caption(config_summary)

    matrix_df = _cached_matrix(ticker, state_mode, threshold_bps, order, window_key)
    if matrix_df is not None:
        matrix_df = _attach_context_display(matrix_df, order)
    states_df = _prepare_states_dataframe(_cached_states(ticker, state_mode, threshold_bps))
    metadata = markov_snapshots_ui.load_matrix_metadata(ticker, state_mode, threshold_bps, order)
    window_meta = metadata.get(window_key.upper(), {})
    matrix_file = markov_snapshots_ui.matrix_path(ticker, state_mode, threshold_bps, order, window_key)

    if matrix_df is None or matrix_df.empty:
        st.warning(
            f"Snapshot matrix missing for {ticker} / mode={state_mode} / order={order} / window={window_key}."
        )
        st.code(f"python cli/mie.py build-markov-snapshots --tickers {ticker}")
        _render_diagnostics(
            ticker=ticker,
            state_mode=state_mode,
            threshold_bps=threshold_bps,
            order=order,
            window_key=window_key,
            matrix_df=matrix_df,
            ctx_row=None,
            matrix_file=matrix_file,
            window_meta=window_meta,
        )
        return

    if states_df is None or states_df.empty:
        st.warning(f"Snapshot states missing for {ticker} / mode={state_mode} / threshold={threshold_bps}.")
        st.code(f"python cli/mie.py build-markov-snapshots --tickers {ticker}")
        _render_diagnostics(
            ticker=ticker,
            state_mode=state_mode,
            threshold_bps=threshold_bps,
            order=order,
            window_key=window_key,
            matrix_df=matrix_df,
            ctx_row=None,
            matrix_file=matrix_file,
            window_meta=window_meta,
        )
        return

    states_last_date = None
    if "date" in states_df.columns:
        parsed_dates = pd.to_datetime(states_df["date"], errors="coerce").dropna()
        if not parsed_dates.empty:
            start_iso = parsed_dates.min().date().isoformat()
            end_iso = parsed_dates.max().date().isoformat()
            states_last_date = parsed_dates.max().to_pydatetime().date()
        else:
            start_iso = end_iso = "unknown"
    else:
        start_iso = end_iso = "unknown"

    meta_last_raw = window_meta.get("date_max")
    fallback_price_raw = window_meta.get("prices_last_date")
    last_data_candidate = meta_last_raw or states_last_date or fallback_price_raw

    staleness = _compute_staleness(last_data_candidate)
    
    if staleness["last_date_iso"]:
        st.caption(f"Data used through: {staleness['last_date_iso']} (last available market close).")
        if staleness["is_stale"] and staleness["days_old"] is not None:
            unit = "day" if staleness["days_old"] == 1 else "days"
            st.caption(
                f"⚠️ Snapshot is {staleness['days_old']} {unit} old (updated {staleness['last_date_iso']})."
            )
    else:
        st.caption("Data date: unknown")

    ctx_raw, ctx_compact, ctx_row, _ = _select_active_context_row(
        mat_df=matrix_df,
        states_df=states_df,
        mode=state_mode,
        order=int(order),
        start_date=start_iso,
        end_date=end_iso,
    )
    if ctx_row is None:
        missing_context_msg = (
            f"No active context row for {ticker} / mode={state_mode} / order={order} / window={window_key}."
        )
    else:
        missing_context_msg = None

    context_details: dict[str, str] | None = (
        _context_descriptions(ctx_row, order, context_override=ctx_raw if ctx_raw else None)
        if ctx_row is not None
        else None
    )

    if order == 1:
        order1_matrix_df = matrix_df
    else:
        order1_matrix_df = _cached_matrix(ticker, state_mode, threshold_bps, 1, window_key)
        if order1_matrix_df is not None:
            order1_matrix_df = _attach_context_display(order1_matrix_df, 1)

    st.subheader("Transition Matrix")
    pretty_matrix = _format_matrix_for_display(matrix_df, order=order, mode=state_mode)
    if pretty_matrix.empty:
        st.warning("Matrix does not contain probability columns for display.")
    else:
        column_config = {}
        for col in ("Green", "Neutral", "Red"):
            if col in pretty_matrix.columns:
                column_config[col] = st.column_config.Column(width="medium")
        if "Row Sum" in pretty_matrix.columns:
            column_config["Row Sum"] = st.column_config.Column(width="small")
        if "Counts" in pretty_matrix.columns:
            column_config["Counts"] = st.column_config.Column(width="small")
        st.dataframe(pretty_matrix, use_container_width=True, column_config=column_config or None)
        context_label_value = ctx_raw or ctx_compact
        if context_details:
            context_caption = (
                context_details.get("combined_html")
                or context_details.get("sequence_html")
                or context_details.get("short")
            )
            if context_caption:
                st.caption(f"Active context: {context_caption}", unsafe_allow_html=True)
            else:
                st.caption("Active context unavailable for this selection.")
        elif context_label_value:
            context_caption = _context_label_html(context_label_value, order)
            if context_caption:
                st.caption(f"Active context: {context_caption}", unsafe_allow_html=True)
            else:
                st.caption(f"Active context: {markov_snapshots_ui.format_context_label(context_label_value)}")
        else:
            st.caption("Active context unavailable for this selection.")
        if ctx_row is None:
            st.info(missing_context_msg or "Transition matrix conclusion unavailable for this context.")
        else:
            matrix_conclusion = _transition_matrix_conclusion(ctx_row, order, state_mode)
            if matrix_conclusion:
                st.markdown(matrix_conclusion, unsafe_allow_html=True)
            else:
                st.info("Transition matrix conclusion unavailable: missing probability columns for this mode.")

    st.subheader("Transition Probability Heatmap")
    heatmap_frame, heatmap_cols = _prepare_heatmap_frame(matrix_df, mode=state_mode, order=order)
    if heatmap_frame.empty:
        st.info("Heatmap unavailable: missing probability columns for this configuration.")
    else:
        try:
            import plotly.graph_objects as go

            matrix = (
                heatmap_frame.sort_values("context_short")
                .set_index("context_short")
                [heatmap_cols]
            )
            full_columns = [markov_snapshots_ui.STATE_COLUMN_LABELS.get(col, col) for col in heatmap_cols]
            contexts_hover = (
                heatmap_frame.drop_duplicates("context_short")
                .set_index("context_short")["context_hover"]
                .reindex(matrix.index)
                .fillna("")
            )
            customdata = [
                [
                    [contexts_hover.iloc[i], full_columns[j]]
                    for j in range(len(full_columns))
                ]
                for i in range(len(matrix.index))
            ]
            text = [[f"{val:.1%}" for val in row] for row in matrix.to_numpy()]
            colorscale = [
                [0.0, _state_color_alias("down")],
                [0.5, "white"],
                [1.0, _state_color_alias("up")],
            ]
            fig = go.Figure(
                data=
                go.Heatmap(
                    z=matrix.to_numpy(),
                    x=full_columns,
                    y=matrix.index.tolist(),
                    colorscale=colorscale,
                    customdata=customdata,
                    text=text,
                    hovertemplate="Context: %{customdata[0]}<br>Next state: %{customdata[1]}<br>Probability: %{z:.1%}<extra></extra>",
                    texttemplate="%{text}",
                )
            )
            fig.update_layout(
                xaxis_title="Next State",
                yaxis_title="Context",
                margin=dict(t=20, b=20, l=0, r=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.info("Plotly not available. Install plotly to view the heatmap.")

    st.subheader("One-Step Probabilities")
    if ctx_row is None:
        st.info("One-step probabilities unavailable: no matching context row.")
    else:
        prob_cols = [col for col in _state_columns_for_mode(state_mode) if col in ctx_row]
        if prob_cols:
            prob_series = pd.to_numeric(ctx_row[prob_cols], errors="coerce").fillna(0.0)
            ctx_probs_display = (
                prob_series.rename(index=markov_snapshots_ui.STATE_COLUMN_LABELS)
                .to_frame(name="Probability (%)")
            )
            ctx_probs_display.index.name = "State"
            ctx_probs_display["Probability (%)"] = ctx_probs_display["Probability (%)"].apply(markov_snapshots_ui.percent_str)
            st.dataframe(
                ctx_probs_display,
                use_container_width=True,
            )
            one_step_conclusion = _one_step_conclusion(ctx_row, state_mode, order)
            if one_step_conclusion:
                st.markdown(one_step_conclusion, unsafe_allow_html=True)
            else:
                st.info("One-step conclusion unavailable: missing probability columns for this mode.")
        else:
            st.info("Probability columns missing for the active context.")

    st.subheader("Multi-Horizon Probabilities")
    if ctx_row is None or context_details is None:
        st.info(
            "Multi-horizon view unavailable: unable to resolve a valid context (even after reducing order) "
            f"for {ticker} / mode={state_mode} / window={window_key}."
        )
    elif order1_matrix_df is None or order1_matrix_df.empty:
        st.info(
            "Multi-horizon view unavailable: order-1 transition matrix missing for this selection "
            f"({ticker} / mode={state_mode} / window={window_key})."
        )
    else:
        horizon_table = _build_multi_horizon_table(order1_matrix_df, horizons, state_mode)
        if horizon_table.empty:
            st.info("Not enough data to compute multi-horizon probabilities for this selection.")
        else:
            display_table = horizon_table.applymap(markov_snapshots_ui.percent_str).reset_index()
            st.dataframe(display_table, use_container_width=True)

            try:
                import plotly.graph_objects as go

                fig = go.Figure()
                color_order = ["Green", "Neutral", "Red"]
                color_map = {
                    "Green": _state_color_alias("up"),
                    "Neutral": _state_color_alias("neutral"),
                    "Red": _state_color_alias("down"),
                }
                x_vals = [str(h) for h in horizon_table.index]
                for state_label in color_order:
                    if state_label not in horizon_table.columns:
                        continue
                    fig.add_bar(
                        name=state_label,
                        x=x_vals,
                        y=horizon_table[state_label].tolist(),
                        marker_color=color_map.get(state_label, _state_color_alias(state_label)),
                        hovertemplate=(
                            f"Horizon %{{x}} days<br>{state_label}: %{{y:.1%}}<extra></extra>"
                        ),
                    )
                fig.update_layout(
                    barmode="group",
                    xaxis_title="Horizon (days)",
                    yaxis=dict(title="Probability (%)", tickformat=".0%"),
                    legend_title="State",
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Plotly not available. Install plotly to see the grouped chart.")

            multi_conclusion = _multi_horizon_conclusion(horizon_table, context_details)
            if multi_conclusion:
                st.markdown(multi_conclusion, unsafe_allow_html=True)
    _render_diagnostics(
        ticker=ticker,
        state_mode=state_mode,
        threshold_bps=threshold_bps,
        order=order,
        window_key=window_key,
        matrix_df=matrix_df,
        ctx_row=ctx_row,
        matrix_file=matrix_file,
        window_meta=window_meta,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        st.error(f"Markov Chain V2 failed: {exc}")
        with st.expander("Show Traceback"):
            import traceback

            st.code(traceback.format_exc())
