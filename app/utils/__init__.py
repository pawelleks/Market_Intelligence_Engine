def _render_section_header(title: str):
    """
    Render a section header with a consistent style.
    """
    import streamlit as st
    st.markdown(f"## {title}")

def _display_table(df, caption: str = None):
    """
    Display a DataFrame as a table with an optional caption.
    """
    import streamlit as st
    st.dataframe(df)
    if caption:
        st.caption(caption)

def _format_metric(value, metric_type: str):
    """
    Format a metric value based on its type (e.g., %, bp, z-score).
    """
    if metric_type == "%":
        return f"{value:.2f}%"
    elif metric_type == "bp":
        return f"{value:.0f} bp"
    elif metric_type == "z-score":
        return f"{value:.2f} z"
    return str(value)

def _get_ticker_colors():
    """
    Return a dictionary of ticker-specific colors for consistent chart styling.
    """
    return {
        "SPY": "blue",
        "QQQ": "green",
        "DIA": "red",
        "IWM": "purple",
    }
