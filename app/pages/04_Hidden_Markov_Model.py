"""Hidden Markov Model (HMM) regime page with interactive controls and analytics."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yaml

try:  # pragma: no cover - import guard for optional dependency
    from hmmlearn.hmm import GaussianHMM
except ImportError:  # pragma: no cover
    GaussianHMM = None  # type: ignore

from app.version import get_version
from app.ui.theme import (
    HMM_HEATMAP_COLORSCALE,
    HMM_PRICE_LINE_COLOR,
    HMM_STATE_COLORS,
)
from mie_lib.utils.paths import features_parquet_path


STATE_DISPLAY_ORDER = ["Bull", "Neutral", "Bear"]
STATE_COLORS = HMM_STATE_COLORS
PRICE_COLOR = HMM_PRICE_LINE_COLOR
HEATMAP_COLORSCALE = HMM_HEATMAP_COLORSCALE
MIN_TRAIN_ROWS = 400
DEFAULT_RANDOM_SEED = 42
STACKGROUP_NAME = "probabilities"


@dataclass
class HMMRunResult:
    analysis_df: pd.DataFrame
    transition_df: pd.DataFrame
    expected_duration: Dict[str, float]
    state_name_map: Dict[int, str]
    feature_columns: List[str]
    training_rows: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp


@lru_cache(maxsize=1)
def _available_tickers() -> List[str]:
    cfg_path = Path("config/tickers.yml")
    if not cfg_path.exists():
        return ["SPY"]
    try:
        data = yaml.safe_load(cfg_path.read_text())
        if isinstance(data, dict):
            tickers = data.get("tickers", [])
        elif isinstance(data, list):
            tickers = data
        else:
            tickers = []
        cleaned = sorted({str(t).upper() for t in tickers})
        return cleaned or ["SPY"]
    except Exception:
        return ["SPY"]


def _state_sort_key(state: str) -> int:
    try:
        return STATE_DISPLAY_ORDER.index(state)
    except ValueError:
        return len(STATE_DISPLAY_ORDER)


def _ensure_hmm_dependency() -> None:
    if GaussianHMM is None:
        raise RuntimeError(
            "hmmlearn is not installed. Install it via `pip install hmmlearn` to use this page."
        )


@st.cache_data(show_spinner=False)
def _load_feature_history(ticker: str) -> pd.DataFrame:
    path = features_parquet_path(ticker)
    if not path.exists():
        raise FileNotFoundError(
            f"Features parquet for {ticker} not found at {path}. Run the feature pipeline first."
        )

    df = pd.read_parquet(path)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")

    if "close" not in df.columns:
        if "adj_close" in df.columns:
            df["close"] = df["adj_close"]
        else:
            raise ValueError("`close` column missing from features file.")

    for col in ["close", "ret_1d", "rv_20d"]:
        if col not in df.columns:
            raise ValueError(f"Required column `{col}` missing from features file.")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["close"] = df["close"].ffill()
    df["ret_1d"] = df["ret_1d"].fillna(0.0)
    df["rv_20d"] = df["rv_20d"].fillna(df["rv_20d"].median())

    return df[["date", "close", "ret_1d", "rv_20d"]].reset_index(drop=True)


def _map_state_names(model, feature_columns: List[str]) -> Dict[int, str]:
    ret_idx = feature_columns.index("ret_1d") if "ret_1d" in feature_columns else 0
    mean_returns = model.means_[:, ret_idx]
    order = np.argsort(mean_returns)  # ascending: bear -> neutral -> bull
    mapping: Dict[int, str] = {}
    mapping[int(order[0])] = "Bear"
    if len(order) == 3:
        mapping[int(order[1])] = "Neutral"
    mapping[int(order[-1])] = "Bull"
    return mapping


def _build_transition_df(transmat: np.ndarray, state_name_map: Dict[int, str]) -> pd.DataFrame:
    labels = [state for state in STATE_DISPLAY_ORDER if state in state_name_map.values()]
    df = pd.DataFrame(0.0, index=labels, columns=labels)
    for row_idx, row_name in state_name_map.items():
        for col_idx, col_name in state_name_map.items():
            if row_name in df.index and col_name in df.columns:
                df.loc[row_name, col_name] = float(transmat[row_idx, col_idx])
    return df


def _expected_durations(transmat: np.ndarray, state_name_map: Dict[int, str]) -> Dict[str, float]:
    durations: Dict[str, float] = {}
    for idx, name in state_name_map.items():
        stay_prob = float(transmat[idx, idx])
        if stay_prob >= 0.9999:
            durations[name] = float("inf")
        else:
            durations[name] = 1.0 / max(1e-6, 1.0 - stay_prob)
    return durations


def _filter_years(df: pd.DataFrame, years: int) -> pd.DataFrame:
    if df.empty or years <= 0:
        return df
    cutoff = df["date"].max() - pd.DateOffset(years=years)
    return df[df["date"] >= cutoff]


def _calc_max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _regime_segments(df: pd.DataFrame) -> List[Tuple[str, pd.Timestamp, pd.Timestamp]]:
    segments: List[Tuple[str, pd.Timestamp, pd.Timestamp]] = []
    current_state: str | None = None
    start: pd.Timestamp | None = None
    prev_date: pd.Timestamp | None = None

    for row in df.itertuples():
        state = getattr(row, "hmm_state_name", None)
        if state not in STATE_COLORS:
            state = None
        if state != current_state:
            if current_state is not None and start is not None and prev_date is not None:
                segments.append((current_state, start, prev_date))
            current_state = state
            start = row.date
        prev_date = row.date

    if current_state is not None and start is not None and prev_date is not None:
        segments.append((current_state, start, prev_date))

    return segments


@st.cache_data(show_spinner=True)
def _train_and_score_hmm(
    ticker: str,
    n_states: int,
    include_rv20: bool,
    train_window_years: int,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> HMMRunResult:
    _ensure_hmm_dependency()
    df = _load_feature_history(ticker)
    feature_columns = ["ret_1d"] + (["rv_20d"] if include_rv20 else [])

    feature_matrix = df[feature_columns].to_numpy(dtype=float)
    feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=0.0, neginf=0.0)

    cutoff = df["date"].max() - pd.DateOffset(years=train_window_years)
    train_mask = df["date"] >= cutoff
    X_train = feature_matrix[train_mask.to_numpy()]

    if X_train.shape[0] < MIN_TRAIN_ROWS:
        raise ValueError(
            f"Only {X_train.shape[0]} samples available for training ({train_window_years}y window)."
        )

    model = GaussianHMM(
        n_components=int(n_states),
        covariance_type="diag",
        random_state=int(random_seed),
        n_iter=200,
        min_covar=1e-6,
    )
    model.fit(X_train)

    posteriors = model.predict_proba(feature_matrix)
    inferred_states = posteriors.argmax(axis=1)

    state_name_map = _map_state_names(model, feature_columns)
    named_states = np.array([state_name_map[int(idx)] for idx in inferred_states])

    probs_df = pd.DataFrame({"date": df["date"].values})
    for label in STATE_DISPLAY_ORDER:
        column = f"hmm_prob_{label.lower()}"
        if label in state_name_map.values():
            idx = [i for i, name in state_name_map.items() if name == label][0]
            probs_df[column] = posteriors[:, idx]
        else:
            probs_df[column] = 0.0

    states_df = pd.DataFrame(
        {
            "date": df["date"].values,
            "hmm_state": inferred_states,
            "hmm_state_name": named_states,
        }
    )

    analysis_df = (
        df.merge(states_df, on="date", how="left")
        .merge(probs_df, on="date", how="left")
        .sort_values("date")
        .reset_index(drop=True)
    )

    for col in ["hmm_prob_bull", "hmm_prob_bear", "hmm_prob_neutral"]:
        if col not in analysis_df.columns:
            analysis_df[col] = 0.0

    transition_df = _build_transition_df(model.transmat_, state_name_map)
    expected_duration = _expected_durations(model.transmat_, state_name_map)

    train_start = df.loc[train_mask, "date"].min()
    train_end = df.loc[train_mask, "date"].max()

    return HMMRunResult(
        analysis_df=analysis_df,
        transition_df=transition_df,
        expected_duration=expected_duration,
        state_name_map=state_name_map,
        feature_columns=feature_columns,
        training_rows=int(train_mask.sum()),
        train_start=train_start,
        train_end=train_end,
    )


def _build_regime_stats_table(df: pd.DataFrame, expected_duration: Dict[str, float]) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    total = len(df)
    if total == 0:
        return pd.DataFrame()

    for state in sorted(df["hmm_state_name"].dropna().unique(), key=_state_sort_key):
        mask = df["hmm_state_name"] == state
        if not mask.any():
            continue
        returns = df.loc[mask, "ret_1d"].dropna()
        if returns.empty:
            continue
        mean_daily = returns.mean()
        std_daily = returns.std(ddof=0)
        ann_vol = std_daily * np.sqrt(252) if std_daily > 0 else 0.0
        sharpe = (mean_daily / std_daily) * np.sqrt(252) if std_daily > 0 else np.nan
        max_dd = _calc_max_drawdown(returns)
        rows.append(
            {
                "Regime": state,
                "Avg Daily Return": mean_daily,
                "Annual Volatility": ann_vol,
                "Sharpe": sharpe,
                "Max Drawdown": max_dd,
                "% Time": mask.mean() * 100,
                "Expected Duration (days)": expected_duration.get(state, np.nan),
            }
        )

    return pd.DataFrame(rows)


def _compute_strategy_returns(
    df: pd.DataFrame, bull_threshold: float, bear_threshold: float
) -> Dict[str, pd.Series]:
    bull_signal = df["hmm_prob_bull"] >= bull_threshold
    bear_signal = df["hmm_prob_bear"] >= bear_threshold
    state_bull = df["hmm_state_name"] == "Bull"
    state_bear = df["hmm_state_name"] == "Bear"

    strategies = {
        "Long Only SPY": df["ret_1d"],
        "Bull Prob Long": df["ret_1d"].where(bull_signal, 0.0),
        "Bear Prob Short": (-df["ret_1d"]).where(bear_signal, 0.0),
        "Bull Regime Only": df["ret_1d"].where(state_bull, 0.0),
        "Bull Regime 1.5x": (1.5 * df["ret_1d"]).where(state_bull & bull_signal, 0.0),
        "Bull vs Bear Overlay": df["ret_1d"].where(bull_signal, 0.0)
        - df["ret_1d"].where(bear_signal, 0.0),
    }

    return {name: series.fillna(0.0) for name, series in strategies.items()}


def _summarize_strategies(
    returns_map: Dict[str, pd.Series], dates: pd.Series
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metrics: List[Dict[str, float]] = []
    equity = pd.DataFrame({"date": dates})
    duration_years = max((dates.iloc[-1] - dates.iloc[0]).days / 365.25, 1 / 252)

    for name, series in returns_map.items():
        series = series.fillna(0.0)
        equity_curve = (1.0 + series).cumprod()
        equity[name] = equity_curve
        total_return = equity_curve.iloc[-1] - 1.0
        mean_daily = series.mean()
        std_daily = series.std(ddof=0)
        ann_vol = std_daily * np.sqrt(252) if std_daily > 0 else 0.0
        sharpe = (mean_daily / std_daily) * np.sqrt(252) if std_daily > 0 else np.nan
        cagr = (1.0 + total_return) ** (1.0 / duration_years) - 1.0 if duration_years > 0 else np.nan
        max_dd = _calc_max_drawdown(series)

        metrics.append(
            {
                "Strategy": name,
                "Total Return": float(total_return),
                "CAGR": float(cagr),
                "Volatility": float(ann_vol),
                "Sharpe": float(sharpe) if not np.isnan(sharpe) else np.nan,
                "Max Drawdown": float(max_dd),
            }
        )

    metrics_df = pd.DataFrame(metrics)
    return metrics_df, equity


def _render_price_chart(df: pd.DataFrame, subtitle: str) -> None:
    if df.empty:
        st.info("No price data available for plotting.")
        return

    fig = go.Figure()
    for state, start, end in _regime_segments(df):
        if state is None:
            continue
        fig.add_vrect(
            x0=start,
            x1=end,
            fillcolor=STATE_COLORS[state],
            opacity=0.12,
            line_width=0,
            layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close"],
            name="SPY Close",
            mode="lines",
            line=dict(color=PRICE_COLOR, width=1.6),
        )
    )

    for state, color in STATE_COLORS.items():
        if (df["hmm_state_name"] == state).any():
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="lines",
                    line=dict(color=color, width=6),
                    name=f"{state} Regime",
                )
            )

    fig.update_layout(
        title=f"SPY Price with HMM-Detected Regimes<br><sup>{subtitle}</sup>",
        height=520,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        margin=dict(t=90, l=20, r=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_probability_chart(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No probability data available.")
        return

    recent = _filter_years(df, 5)
    if recent.empty:
        recent = df

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for state in STATE_DISPLAY_ORDER:
        col = f"hmm_prob_{state.lower()}"
        if col in recent.columns and recent[col].sum() > 0:
            fig.add_trace(
                go.Scatter(
                    x=recent["date"],
                    y=recent[col],
                    name=f"{state} Probability",
                    mode="lines",
                    line=dict(color=STATE_COLORS[state], width=0.6),
                    stackgroup=STACKGROUP_NAME,
                ),
                secondary_y=False,
            )

    fig.add_trace(
        go.Scatter(
            x=recent["date"],
            y=recent["close"],
            name="SPY Close",
            line=dict(color=PRICE_COLOR, width=1.2),
            mode="lines",
        ),
        secondary_y=True,
    )

    fig.update_yaxes(title_text="Probability", range=[0, 1], secondary_y=False)
    fig.update_yaxes(title_text="Price", secondary_y=True)
    fig.update_layout(
        title="HMM Regime Probabilities vs SPY Price",
        height=460,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        margin=dict(t=80, l=20, r=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_transition_matrix(transition_df: pd.DataFrame, expected_duration: Dict[str, float]) -> None:
    if transition_df.empty:
        st.info("Transition matrix unavailable for this configuration.")
        return

    fig = go.Figure(
        data=go.Heatmap(
            z=transition_df.values,
            x=transition_df.columns,
            y=transition_df.index,
            colorscale=HEATMAP_COLORSCALE,
            text=np.vectorize(lambda v: f"{v * 100:.2f}%")(transition_df.values),
            texttemplate="%{text}",
            hovertemplate="From %{y} → %{x}: %{z:.2%}<extra></extra>",
        )
    )
    fig.update_layout(
        title="HMM Transition Matrix — Daily Probabilities",
        height=420,
        template="plotly_dark",
        margin=dict(t=80, l=40, r=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    bull_days = expected_duration.get("Bull")
    bear_days = expected_duration.get("Bear")
    if bull_days or bear_days:
        pieces = []
        if bull_days:
            pieces.append(f"~{bull_days:.1f} days in Bull regime")
        if bear_days:
            pieces.append(f"~{bear_days:.1f} days in Bear regime")
        st.caption("The model implies " + " and ".join(pieces) + " on average before switching.")


def _render_regime_stats(df: pd.DataFrame, expected_duration: Dict[str, float]) -> None:
    st.subheader("HMM Regime Statistics")
    stats_df = _build_regime_stats_table(df, expected_duration)
    if stats_df.empty:
        st.info("Not enough observations to compute regime statistics.")
        return

    fmt = {
        "Avg Daily Return": "{:.2%}",
        "Annual Volatility": "{:.2%}",
        "Sharpe": "{:.2f}",
        "Max Drawdown": "{:.1%}",
        "% Time": "{:.1f}%",
        "Expected Duration (days)": "{:.1f}",
    }
    st.dataframe(stats_df.style.format(fmt), use_container_width=True)


def _render_strategy_backtests(
    df: pd.DataFrame,
    evaluation_years: int,
    bull_threshold: float,
    bear_threshold: float,
) -> None:
    st.subheader("Strategy Backtests (Regime Filters)")
    eval_df = _filter_years(df, evaluation_years)
    if eval_df.empty:
        st.info("Not enough price history for the selected evaluation window.")
        return

    strategy_returns = _compute_strategy_returns(eval_df, bull_threshold, bear_threshold)
    metrics_df, equity_df = _summarize_strategies(strategy_returns, eval_df["date"])

    fmt = {
        "Total Return": "{:.1%}",
        "CAGR": "{:.1%}",
        "Volatility": "{:.1%}",
        "Sharpe": "{:.2f}",
        "Max Drawdown": "{:.1%}",
    }
    st.caption(
        f"Evaluation window: last {evaluation_years} years ({eval_df.shape[0]} trading days)."
    )
    st.dataframe(metrics_df.style.format(fmt), use_container_width=True)

    fig = go.Figure()
    for column in equity_df.columns:
        if column == "date":
            continue
        fig.add_trace(
            go.Scatter(
                x=equity_df["date"],
                y=equity_df[column],
                name=column,
                mode="lines",
            )
        )
    fig.update_layout(
        title="Strategy Equity Curves",
        yaxis_title="Growth of $1",
        template="plotly_dark",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Hidden Markov Model (Regimes)", layout="wide")
    st.title("Hidden Markov Model (Regimes)")

    tickers = _available_tickers()
    with st.sidebar:
        st.header("Configuration")
        ticker = st.selectbox("Ticker", options=tickers, index=tickers.index("SPY") if "SPY" in tickers else 0)
        n_states = st.selectbox("Hidden states", options=[2, 3], index=1)
        include_rv20 = st.checkbox("Include RV20 feature", value=True)
        train_window_years = st.select_slider(
            "Training window (years)", options=[5, 10, 15, 20, 25], value=15
        )
        bull_threshold = st.slider(
            "Bull signal threshold", min_value=0.50, max_value=0.95, value=0.60, step=0.01
        )
        bear_threshold = st.slider(
            "Bear signal threshold", min_value=0.50, max_value=0.95, value=0.60, step=0.01
        )
        evaluation_window_label = st.selectbox(
            "Backtest evaluation window", options=["5y", "10y", "15y", "20y"], index=0
        )

    evaluation_years = int(evaluation_window_label.rstrip("y"))

    try:
        with st.spinner("Training HMM and loading artifacts..."):
            hmm_result = _train_and_score_hmm(
                ticker=ticker,
                n_states=n_states,
                include_rv20=include_rv20,
                train_window_years=train_window_years,
            )
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.code(f"python cli/mie.py rebuild-features --tickers {ticker}")
        st.stop()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()

    df = hmm_result.analysis_df.copy()
    df["bull_signal"] = df["hmm_prob_bull"] >= bull_threshold
    df["bear_signal"] = df["hmm_prob_bear"] >= bear_threshold
    df["date"] = pd.to_datetime(df["date"])  # ensures tz-naive

    subtitle = (
        f"States={n_states}, Window={train_window_years}y, RV20={'On' if include_rv20 else 'Off'}, "
        f"Bull≥{bull_threshold:.2f}, Bear≥{bear_threshold:.2f}"
    )

    version = get_version()
    coverage = f"{df['date'].min():%Y-%m-%d} – {df['date'].max():%Y-%m-%d}"
    st.caption(
        f"Release: {version} • Last updated: {pd.Timestamp.utcnow():%Y-%m-%d %H:%M} UTC • Data coverage: {ticker} ({coverage})"
    )

    _render_price_chart(df, subtitle)
    _render_probability_chart(df)
    _render_transition_matrix(hmm_result.transition_df, hmm_result.expected_duration)
    _render_regime_stats(df, hmm_result.expected_duration)
    _render_strategy_backtests(df, evaluation_years, bull_threshold, bear_threshold)


if __name__ == "__main__":
    main()
