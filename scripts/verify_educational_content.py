import json
import os
import sys

# Define config directory path relative to project root
# Assuming script is run from project root, so 'frontend/src/data/tier2_configs'
CONFIG_DIR = "frontend/src/data/tier2_configs"

# List of expected page keys (from file names or index keys)
# Config names are typically {page}_config.json
pages = [
    "interest_rates",
    "gdp_growth", 
    "consumer_spending",
    "labor_market",
    "inflation",
    "business_confidence",
    "housing_market",
    "trade_balance"
]

def verify_configs():
    all_passed = True
    print(f"Verifying configs in: {CONFIG_DIR}")
    
    if not os.path.exists(CONFIG_DIR):
        print(f"❌ Error: Directory not found: {CONFIG_DIR}")
        return False

    for page in pages:
        config_filename = f"{page}_config.json"
        config_path = os.path.join(CONFIG_DIR, config_filename)
        
        if not os.path.exists(config_path):
            print(f"❌ MISSING FILE: {config_filename}")
            all_passed = False
            continue
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ JSON ERROR: {config_filename} - {str(e)}")
            all_passed = False
            continue
        
        # Check educational_content presence
        if 'educational_content' not in config:
            print(f"❌ INVALID: {page} - Missing 'educational_content' object")
            all_passed = False
            continue
        
        edu = config['educational_content']
        
        # Check integrity of educational_content
        missing_fields = []
        if 'title' not in edu: missing_fields.append('title')
        if 'overview' not in edu: missing_fields.append('overview')
        if 'bullets' not in edu: missing_fields.append('bullets')
        
        if missing_fields:
            print(f"❌ INVALID: {page} - Missing fields in educational_content: {missing_fields}")
            all_passed = False
            continue
            
        # Check bullets array
        if not isinstance(edu['bullets'], list):
            print(f"❌ INVALID: {page} - 'bullets' is not a list")
            all_passed = False
            continue
            
        if len(edu['bullets']) != 3:
            print(f"⚠️ WARNING: {page} - 'bullets' count is {len(edu['bullets'])}, expected 3. (Not critical but check consistency)")
        
        for idx, bullet in enumerate(edu['bullets']):
            if 'label' not in bullet or 'text' not in bullet:
                print(f"❌ INVALID: {page} - Bullet {idx+1} missing 'label' or 'text'")
                all_passed = False
        
        print(f"✅ PASSED: {page}")

    if all_passed:
        print("\n🎉 Verification Complete: All educational content checks passed.")
        return True
    else:
        print("\nsc Verification Failed: Fix errors above.")
        return False

if __name__ == "__main__":
    success = verify_configs()
    sys.exit(0 if success else 1)
