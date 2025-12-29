
import sys
import os
import pandas as pd

# Path hack to ensure we find mie_lib
sys.path.append(os.path.join(os.getcwd(), 'src'))

from mie_lib.analytics.volatility_term_structure import generate_term_structure_report

def main():
    print("Running Volatility Term Structure Analysis...")
    df = generate_term_structure_report()
    
    if df.empty:
        print("Error: No data generated.")
        return

    print("\n--- Volatility Term Structure (Tail 10) ---")
    # Show VIX, VIX3M, Ratio, Regime, VIX1D, Flash Premium
    cols = ['VIX', 'VIX3M', 'ratio', 'regime', 'VIX1D', 'flash_premium']
    print(df[cols].tail(10))
    
    print("\n--- Regime Counts (Last 2 Years) ---")
    print(df['regime'].value_counts())

    print("\n--- Recent 'Extreme Backwardation' Days ---")
    extreme = df[df['regime'] == "Extreme Backwardation"]
    if not extreme.empty:
        print(extreme[cols].tail(5))
    else:
        print("None found in lookback period.")

if __name__ == "__main__":
    main()
