
import logging
import sys
from datetime import date

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add src to path
sys.path.append("src")

from mie_lib.analytics.skew.skew_pipeline import run_skew_pipeline_parallel

def verify_skew_hybrid():
    print("Running Skew Pipeline for SPY (Hybrid Verification)...")
    
    # Run for TODAY (or recent date). If Massive file exists (26th), it will load it, find no Greeks, and fallback.
    # If file doesn't exist (28th), it will warn "No massive data" and proceed with empty map, forcing fallback.
    
    # Let's try 2025-12-26 first (Massive exists but no Greeks)
    target_date = "2025-12-26"
    
    results = run_skew_pipeline_parallel(["SPY"], target_date=target_date, max_workers=1)
    
    print("\n--- RESULTS ---")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    
    if results['details']:
        det = results['details'][0]
        print(f"Ticker: {det['ticker']}")
        print(f"Status: {det['status']}")
        print(f"Source: {det.get('source', 'N/A')}")
        print(f"PCR: {det.get('pcr')}")
        
        if det['status'] == 'ok' and det.get('source') == 'hybrid_yfinance':
            print("\nVERIFICATION PASSED: Hybrid Fallback Success.")
        elif det['status'] == 'ok' and det.get('source') == 'massive':
            print("\nVERIFICATION WARNING: Used Massive source. Does it have Greeks?")
        else:
            print(f"\nVERIFICATION FAILED: {det.get('error')}")
    else:
        print("No details found.")

if __name__ == "__main__":
    verify_skew_hybrid()
