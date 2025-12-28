#!/usr/bin/env python3
"""
Verify Skew/PCR pipeline data integrity.

Checks:
1. Massive flat file exists for target date
2. Hybrid storage outputs are created correctly
3. Data timestamps match expected date
"""

import sys
from pathlib import Path
from datetime import date
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def verify_skew_pipeline(target_date: str = None) -> bool:
    """
    Verify that the Skew pipeline ran correctly for the given date.
    
    Returns:
        True if all checks pass, False otherwise
    """
    if target_date is None:
        target_date = str(date.today())
    
    print(f"Verifying Skew Pipeline for: {target_date}")
    print("=" * 60)
    
    all_passed = True
    
    # ===== CHECK 1: Massive Flat File =====
    massive_path = Path(f"data/raw/massive/options/options_{target_date}.csv")
    if massive_path.exists():
        import pandas as pd
        df = pd.read_csv(massive_path, nrows=10)
        print(f"✅ Massive flat file exists: {massive_path}")
        print(f"   Columns: {list(df.columns)[:5]}...")
        print(f"   Sample rows: {len(df)}")
    else:
        print(f"⚠️  Massive flat file not found: {massive_path}")
        print("   (This is expected if today is a non-trading day)")
    
    # ===== CHECK 2: Hybrid Storage - By Date =====
    by_date_path = Path(f"data/analytics/skew/by_date/date={target_date}/data.parquet")
    if by_date_path.exists():
        import pandas as pd
        df = pd.read_parquet(by_date_path)
        print(f"✅ By-date snapshot exists: {len(df)} tickers")
        if len(df) > 0:
            sample = df.head(3)[["ticker", "pcr_volume", "skew_25d", "regime"]].to_dict("records")
            for row in sample:
                print(f"   {row['ticker']}: PCR={row['pcr_volume']}, Skew={row['skew_25d']}, Regime={row['regime']}")
    else:
        print(f"❌ By-date snapshot NOT FOUND: {by_date_path}")
        all_passed = False
    
    # ===== CHECK 3: Hybrid Storage - By Ticker =====
    by_ticker_dir = Path("data/analytics/skew/by_ticker")
    if by_ticker_dir.exists():
        parquet_files = list(by_ticker_dir.glob("*.parquet"))
        print(f"✅ By-ticker storage: {len(parquet_files)} ticker files")
        
        # Check a sample ticker
        for ticker in ["SPY", "QQQ", "AAPL"]:
            ticker_path = by_ticker_dir / f"{ticker}.parquet"
            if ticker_path.exists():
                import pandas as pd
                df = pd.read_parquet(ticker_path)
                print(f"   {ticker}: {len(df)} historical records")
                break
    else:
        print(f"❌ By-ticker directory NOT FOUND")
        all_passed = False
    
    # ===== CHECK 4: Latest Cache =====
    latest_path = Path("data/analytics/skew/latest.json")
    if latest_path.exists():
        with open(latest_path) as f:
            latest = json.load(f)
        
        as_of = latest.get("as_of")
        tickers = latest.get("tickers", {})
        
        if as_of == target_date:
            print(f"✅ Latest cache is current: {len(tickers)} tickers")
        else:
            print(f"⚠️  Latest cache date mismatch: {as_of} (expected {target_date})")
        
        # Show sample
        for ticker in ["SPY", "QQQ"]:
            if ticker in tickers:
                data = tickers[ticker]
                print(f"   {ticker}: PCR={data.get('pcr_volume')}, Regime={data.get('regime')}")
    else:
        print(f"❌ Latest cache NOT FOUND: {latest_path}")
        all_passed = False
    
    # ===== SUMMARY =====
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
    else:
        print("❌ SOME CHECKS FAILED")
    
    return all_passed


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    success = verify_skew_pipeline(target)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
