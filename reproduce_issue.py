
import json
import yaml
from pathlib import Path
import sys
import os

# Mock paths module behavior since we might not be able to import mie_lib easily 
# without setting PYTHONPATH, but I will try to set it.
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "src"))

from mie_lib.utils.paths import options_latest_json_path, ROOT as LIB_ROOT

print(f"ROOT: {ROOT}")
print(f"LIB_ROOT: {LIB_ROOT}")

def test_endpoint_logic():
    path = options_latest_json_path()
    print(f"Reading from: {path} (Exists: {path.exists()})")
    
    if not path.exists():
        print("File not found")
        return

    try:
        with open(path, "r") as f:
            data = json.load(f)
        
        print("JSON loaded successfully.")
        
        # Filter Logic Reproduction
        print("Testing Filter Logic...")
        scope_path = LIB_ROOT / "config" / "analysis_scope.yml"
        print(f"Scope Path: {scope_path} (Exists: {scope_path.exists()})")
        
        if scope_path.exists():
            with open(scope_path, "r") as f:
                scope_cfg = yaml.safe_load(f)
                
            allowed_tickers = scope_cfg.get("scope", {}).get("Expected_Moves_Reliability", [])
            print(f"Allowed tickers: {len(allowed_tickers)}")
            
            if allowed_tickers:
                # Filter existing tickers
                filtered_tickers = {k: v for k, v in data.get("tickers", {}).items() if k in allowed_tickers}
                data["tickers"] = filtered_tickers
                print(f"Filtered tickers count: {len(filtered_tickers)}")
                
        return data  
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_endpoint_logic()
