import json
from pathlib import Path

CONFIG_DIR = Path("frontend/src/data/tier2_configs")

REQUIRED_PAGES = [
    "interest_rates_config.json",
    "gdp_growth_config.json",
    "consumer_spending_config.json",
    "labor_market_config.json",
    "inflation_config.json",
    "business_confidence_config.json",
    "housing_market_config.json",
    "trade_balance_config.json"
]

def verify_configs():
    all_passed = True
    
    if not CONFIG_DIR.exists():
        print(f"FAILED: Directory {CONFIG_DIR} does not exist.")
        return False
        
    for filename in REQUIRED_PAGES:
        file_path = CONFIG_DIR / filename
        if not file_path.exists():
            print(f"FAILED: Config {filename} missing.")
            all_passed = False
            continue
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Schema Check
            if "page" not in data or "educational_content" not in data or "related_metrics" not in data:
                print(f"FAILED: {filename} missing top-level keys.")
                all_passed = False
                continue
                
            # Educational Content Check
            edu = data["educational_content"]
            if "title" not in edu or "overview" not in edu or "bullets" not in edu:
                 print(f"FAILED: {filename} educational_content schema error.")
                 all_passed = False
                 continue
                 
            # Related Metrics Check
            metrics = data["related_metrics"]
            if not isinstance(metrics, list):
                print(f"FAILED: {filename} related_metrics should be a list.")
                all_passed = False
                continue
                
            for m in metrics:
                if "series_id" not in m or "display_name" not in m or "unit" not in m:
                    print(f"FAILED: {filename} metric missing required fields: {m}")
                    all_passed = False
                    
            print(f"PASSED: {filename} ({len(metrics)} metrics)")
            
        except Exception as e:
            print(f"FAILED: {filename} error: {e}")
            all_passed = False
            
    return all_passed

if __name__ == "__main__":
    if verify_configs():
        print("\nAll Tier 2 configs verified successfully.")
    else:
        print("\nVerification FAILED.")
        exit(1)
