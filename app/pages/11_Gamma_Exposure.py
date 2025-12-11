import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from mie_lib.analytics.gex.storage import load_gex_profile, GEX_DATA_DIR
from datetime import datetime

# Page Config
st.set_page_config(page_title="Gamma Exposure (GEX)", layout="wide")

def _load_available_tickers():
    if not GEX_DATA_DIR.exists():
        return []
    # Directories like {TICKER}_gex
    return sorted([
        p.name.replace("_gex", "") 
        for p in GEX_DATA_DIR.iterdir() 
        if p.is_dir() and p.name.endswith("_gex")
    ])

def main():
    st.title("Gamma Exposure (GEX) Analysis")
    
    # Sidebar
    tickers = _load_available_tickers()
    if not tickers:
        st.warning(f"No GEX data found in {GEX_DATA_DIR}. Please run 'build-gex-daily'.")
        # Fallback to configured tickers just in case we want to show empty state for them
        try: 
             from app.pages.Seasonality_Analysis import _load_tickers
             tickers = _load_tickers()
        except:
             pass
    
    if not tickers:
        st.stop()
        
    selected_ticker = st.sidebar.selectbox("Ticker", tickers, index=0)
    
    if st.sidebar.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

    # Load Data
    data = load_gex_profile(selected_ticker)
    
    if not data or "profile" not in data or not data["profile"]:
        st.error(f"No GEX profile found for {selected_ticker}")
        st.stop()
        
    profile = pd.DataFrame(data["profile"])
    meta = {k:v for k,v in data.items() if k != "profile"}
    
    # Display Metadata
    st.subheader(f"{selected_ticker} GEX Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Spot Price", f"${meta.get('spot_price', 0):,.2f}")
    net_gex = meta.get('net_gex', 0)
    col2.metric("Net GEX", f"${net_gex/1e9:.2f}B", delta_color="normal" if net_gex >= 0 else "inverse")
    col3.metric("Last Updated", meta.get('timestamp', 'Unknown'))
    
    # Charts
    st.subheader("GEX by Strike")
    
    # 1. Net GEX by Strike (Bar Chart)
    fig = go.Figure()
    
    # Colors: Call=Green, Put=Red (Negative). But here we simply show Net.
    # If Net > 0 -> Green, Net < 0 -> Red.
    colors = ["green" if v >= 0 else "red" for v in profile["total_net_gex"]]
    
    fig.add_trace(go.Bar(
        x=profile["strike"],
        y=profile["total_net_gex"],
        marker_color=colors,
        name="Net GEX"
    ))
    
    # Add Spot Line
    spot = meta.get('spot_price', 0)
    if spot > 0:
        fig.add_vline(x=spot, line_dash="dash", line_color="white", annotation_text="Spot")
        
    fig.update_layout(
        title=f"Total Net GEX by Strike ({selected_ticker})",
        xaxis_title="Strike Price",
        yaxis_title="Gamma Exposure ($)",
        template="plotly_dark",
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. Open Interest / Gamma Details (Optional - add tabs for granular view)
    tab1, tab2 = st.tabs(["Profile Data", "Expiry Details"])
    
    with tab1:
        st.dataframe(profile, use_container_width=True)
        
    with tab2:
        st.json(meta.get("group_dates", {}))


if __name__ == "__main__":
    main()
