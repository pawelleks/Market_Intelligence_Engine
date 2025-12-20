import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from typing import Dict, Optional, Tuple, Any
import numpy as np
from datetime import datetime

import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

VTS_OUTPUT_PATH = Path("data/analytics/volatility_term_structure.json")

class VolatilityTermStructure:
    """
    Analyzes the volatility term structure using VIX1D (Daily), VIX (Monthly), and VIX3M (3-Month).
    """
    
    TICKERS = {
        "VIX1D": "^VIX1D",
        "VIX": "^VIX",
        "VIX3M": "^VIX3M",
        "SPY": "SPY"
    }

    def __init__(self, lookback_days: int = 730):
        self.lookback_days = lookback_days

    def _fetch_data(self) -> pd.DataFrame:
        """Fetching aligned VIX data."""
        end_date = date.today()
        start_date = end_date - timedelta(days=self.lookback_days)
        
        data_frames = {}
        
        # Reuse efficient fetching pattern verified in audit
        for name, ticker in self.TICKERS.items():
            try:
                # yf.download call mirroring known good logic
                df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
                
                if df is None or df.empty:
                    print(f"Warning: No data for {name}")
                    continue
                    
                # Normalize columns
                if isinstance(df.columns, pd.MultiIndex):
                     df.columns = [str(col[0]) if isinstance(col, tuple) else str(col) for col in df.columns]
                
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                
                # Extract Price
                price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
                
                if price_col not in df.columns:
                     continue
                     
                df = df.reset_index()
                # Rename 'date'/'Date'
                if 'date' in df.columns:
                    df = df.rename(columns={'date': 'Date'})
                
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
                df = df.set_index('Date').sort_index()
                
                data_frames[name] = df[[price_col]].rename(columns={price_col: name})
                
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")

        # Align Data
        if "VIX" not in data_frames:
            return pd.DataFrame()
            
        aligned = data_frames["VIX"]
        for name, df in data_frames.items():
            if name == "VIX": continue
            aligned = aligned.merge(df, left_index=True, right_index=True, how='outer')
            
        # Clean Sort
        aligned = aligned.sort_index()
        
        # Drop rows where VIX or VIX3M is missing (cant calc ratio)
        # VIX1D might be missing historically, that's fine?
        # User said "Return a clean DataFrame".
        # If VIX1D is missing, flash_premium is NaN.
        # Ideally we forward fill gaps slightly? Or drop?
        # Let's just drop completely empty rows or rows without base VIX.
        aligned = aligned.dropna(subset=['VIX', 'VIX3M'])
        
        return aligned

    def analyze(self) -> pd.DataFrame:
        """
        Runs the full analysis:
        1. Fetch & Align
        2. Calc Ratio (VIX / VIX3M)
        3. Define Regimes
        4. Calc Flash Premium (VIX1D - VIX)
        """
        df = self._fetch_data()
        
        if df.empty:
            return df
            
        # 1. Structure Ratio
        # "ratio = ^VIX / ^VIX3M"
        # Safe division
        df['ratio'] = df['VIX'] / df['VIX3M'].replace(0, np.nan)
        df['ratio'] = df['ratio'].replace([np.inf, -np.inf], np.nan)
        
        # 2. Market Regimes
        # Contango: ratio < 1.0
        # Backwardation: ratio >= 1.0
        # Extreme Backwardation: ratio > 1.15
        
        def get_regime(row):
            r = row['ratio']
            if pd.isna(r): return None
            if r > 1.15: return "Extreme Backwardation"
            if r >= 1.0: return "Backwardation"
            return "Contango"
            
        df['regime'] = df.apply(get_regime, axis=1)
        
        # 3. Flash Crash Premium
        # "flash_premium = VIX1D - ^VIX"
        if 'VIX1D' in df.columns:
            df['flash_premium'] = df['VIX1D'] - df['VIX']
        else:
            df['flash_premium'] = np.nan
        return df

    def save_report(self):
        """Runs analysis and saves to JSON."""
        df = self.analyze()
        if df.empty:
            print("No data to save.")
            return
        
        # Prepare for JSON
        df_reset = df.reset_index()
        # Convert Timestamps to string
        if 'Date' in df_reset.columns:
            df_reset['Date'] = df_reset['Date'].dt.strftime('%Y-%m-%d')
            
        data = df_reset.replace({np.nan: None}).to_dict(orient='records')
        output = {
            "last_updated": datetime.now().isoformat(),
            "data_as_of": df_reset['Date'].iloc[-1] if 'Date' in df_reset.columns and not df_reset.empty else None,
            "data": data,
            "latest": data[-1] if data else None
        }
        
        VTS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(VTS_OUTPUT_PATH, 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"Volatility Term Structure saved to {VTS_OUTPUT_PATH}")

    @staticmethod
    def load_report() -> Dict:
        """Loads the pre-computed report."""
        if not VTS_OUTPUT_PATH.exists():
            return {}
            
        with open(VTS_OUTPUT_PATH, 'r') as f:
            return json.load(f)

def generate_term_structure_report():
    """Returns the loaded report or generates if missing."""
    if VTS_OUTPUT_PATH.exists():
         return VolatilityTermStructure.load_report()
    
    # Fallback to generation (and save)
    vts = VolatilityTermStructure()
    vts.save_report()
    return VolatilityTermStructure.load_report()


def display_dashboard(df: pd.DataFrame):
    """
    Visualizes the Volatility Term Structure and prints the human-readable report.
    """
    if df.empty:
        print("No data available to plot.")
        return

    # --- 1. Get Latest State ---
    latest = df.iloc[-1]
    current_ratio = latest['ratio']
    current_regime = latest['regime']
    current_date = df.index[-1].strftime('%Y-%m-%d')
    
    # --- 2. Generate Dynamic Insight ---
    print("\\n" + "="*60) 
    print(f"VOLATILITY STRUCTURE REPORT | {current_date}") 
    print("="*60)

    # Status Badge
    if current_regime == "Contango": 
        status_icon = "🟢" 
        action = "Carry strategies favored (Short Vol)." 
        meaning = "Normal market structure. Investors expect volatility to rise over time." 
    elif current_regime == "Backwardation": 
        status_icon = "⚠️" # Using warning icon instead of Rx which might be weird
        action = "Caution. Hedges are expensive." 
        meaning = "High stress. Immediate fear is higher than future expectations." 
    else: 
        # Extreme Backwardation 
        status_icon = "🔴 WARNING" 
        action = "Contrarian Buy Signal (if extreme)." 
        meaning = "Panic selling. Market often bottoms when this spike reverses."

    print(f"STATUS: {status_icon} {current_regime.upper()} (Ratio: {current_ratio:.2f})")
    print(f"MEANING: {meaning}")
    print(f"IMPLICATION: {action}")
    print("-" * 60 + "\\n")
    
    # --- 3. Plotting ---
    plt.figure(figsize=(12, 8))
    
    # Subplot 1: The Ratio (The Signal)
    ax1 = plt.subplot(2, 1, 1)

    # Color code the line based on regime (Visual trick: fill under curve)
    ax1.plot(df.index, df['ratio'], color='black', linewidth=1.5, label='VIX / VIX3M Ratio')

    # Add Threshold Line
    ax1.axhline(y=1.0, color='red', linestyle='--', alpha=0.7, label='Panic Threshold (1.0)')

    # Shade the "Panic" zones
    ax1.fill_between(df.index, df['ratio'], 1.0, where=(df['ratio'] >= 1.0), facecolor='red', alpha=0.3, interpolate=True, label='Backwardation (Fear)') 
    ax1.fill_between(df.index, df['ratio'], 1.0, where=(df['ratio'] < 1.0), facecolor='green', alpha=0.1, interpolate=True, label='Contango (Normal)')

    ax1.set_title(f"Volatility Term Structure (VIX / VIX3M) | Data as of: {current_date}", fontsize=12, fontweight='bold')
    ax1.set_ylabel("Ratio (>1.0 = Fear)")
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Subplot 2: The Raw Data (Context)
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.plot(df.index, df['VIX'], label='Spot VIX', color='blue', alpha=0.8, linewidth=1)
    ax2.plot(df.index, df['VIX3M'], label='VIX 3-Month', color='orange', alpha=0.8, linewidth=1)
    
    # Optional: Plot VIX1D if available and recent enough
    if 'VIX1D' in df.columns and not df['VIX1D'].iloc[-10:].isna().all(): 
        ax2.plot(df.index, df['VIX1D'], label='VIX 1-Day (Flash)', color='purple', linestyle=':', alpha=0.6)

    ax2.set_title("Underlying Volatility Indices", fontsize=10)
    ax2.set_ylabel("Price")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Formatting dates
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m')) 
    plt.xticks(rotation=45)

    plt.tight_layout() 
    plt.show()

if __name__ == "__main__":
    vts = VolatilityTermStructure()
    vts.save_report()
    df_analyzed = vts.analyze()
    display_dashboard(df_analyzed)


