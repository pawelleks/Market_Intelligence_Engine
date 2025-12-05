from mie_lib.analytics.gex.gex_engine import GEXEngine
import json

def verify():
    print("Initializing GEX Engine...")
    engine = GEXEngine()
    
    ticker = "SPY"
    print(f"Fetching GEX for {ticker}...")
    data = engine.fetch_and_calculate_gex(ticker)
    
    if not data:
        print("FAILED: No data returned.")
        return

    print(f"SUCCESS: Data fetched for {ticker}")
    print(f"Spot Price: {data.get('spot_price')}")
    print(f"Net GEX: ${data.get('net_gex'):,.2f}")
    
    profile = data.get('profile', [])
    print(f"Profile Length: {len(profile)} strikes")
    
    if profile:
        print("Sample Strike Data (ATM):")
        # Find strike closest to spot
        spot = data.get('spot_price')
        closest = min(profile, key=lambda x: abs(x['strike'] - spot))
        print(json.dumps(closest, indent=2))

if __name__ == "__main__":
    verify()
