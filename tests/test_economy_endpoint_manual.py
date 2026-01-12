import sys
from pathlib import Path
from fastapi.testclient import TestClient
import pandas as pd

# Setup paths
REPO_ROOT = Path(".").resolve()
sys.path.append(str(REPO_ROOT / "src"))

# Mock auth dependency before importing router
# We need to install the mock before importing the router or rely on dependency_overrides
from unittest.mock import MagicMock
from fastapi import APIRouter
from mie_lib.api.routers.economy import router

# Create a minimal app for testing the router
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)

# Override the auth dependency
from mie_lib.api.dependencies import get_current_user
app.dependency_overrides[get_current_user] = lambda: {"username": "test_user"}

def verify_endpoint():
    client = TestClient(app)
    response = client.get("/economy/lei-coi")
    
    if response.status_code != 200:
        print(f"FAILED: Status Code {response.status_code}")
        print(response.json())
        return

    data = response.json()
    if not isinstance(data, list):
        print("FAILED: Response is not a list")
        return
        
    if not data:
        print("WARNING: Response list is empty (check if data file exists and is populated)")
        return
        
    first_row = data[0]
    expected_keys = {"date", "lei", "coi", "status_label"}
    if not expected_keys.issubset(first_row.keys()):
        print(f"FAILED: Missing keys. Found {first_row.keys()}")
        return
        
    print(f"SUCCESS: Endpoint returned {len(data)} records.")
    print("Last Record:")
    print(data[-1])
    
    # Check if verification log warning would trigger
    last_rec = data[-1]
    last_lei = last_rec['lei']
    last_coi = last_rec['coi']
    
    print(f"\nChecking Validation Logic (LEI~0.30, COI~0.21)...")
    lei_diff = abs(last_lei - 0.30)
    coi_diff = abs(last_coi - 0.21)
    
    if lei_diff > 0.05:
        print(f" > LEI deviation {lei_diff:.3f}: API should have logged a warning.")
    else:
        print(f" > LEI deviation {lei_diff:.3f}: Within range.")
        
    if coi_diff > 0.05:
        print(f" > COI deviation {coi_diff:.3f}: API should have logged a warning.")
    else:
        print(f" > COI deviation {coi_diff:.3f}: Within range.")

if __name__ == "__main__":
    verify_endpoint()
