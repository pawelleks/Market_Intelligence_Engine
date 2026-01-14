import requests
import json
import os
import sys

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
USERS_URL = "http://localhost:8000/api/users"
# Assumes dev server is running on localhost:8000
# For script execution, we mock the auth flow or need a valid token.
# Since we implemented a Mock Bypass in dependencies.py (MOCK_AUTH_USER env var), we can use that!

MOCK_EMAIL = "test_verifier@blindmonkey.io"
os.environ["MOCK_AUTH_USER"] = MOCK_EMAIL

def print_step(msg):
    print(f"\n[STEP] {msg}")

def run_test():
    print("=== Terms System Verification Script ===")
    
    # 1. Reset Terms (Requires Admin)
    # The mock user is Admin by default in dependencies.py (id=9999, is_admin=True)
    # But we need a token to pass 'Depends' check even if mocked?
    # dependencies.py: get_current_user checks token first, then MOCK_AUTH_USER.
    # So if we request without token, it should use MOCK_AUTH_USER.
    
    print_step("Checking prerequisites...")
    try:
        # Check backend alive
        r = requests.get(f"{BASE_URL}/health") # assuming health endpoint exists, or just try terms
    except Exception:
        print("⚠️ Backend might not be running at localhost:8000. Proceeding anyway...")

    print_step("Resetting terms for mock user...")
    r = requests.post(f"{USERS_URL}/dev/reset-terms", headers={})
    if r.status_code == 200:
        print("✅ Terms reset successfully.")
    else:
        print(f"❌ Failed to reset terms: {r.status_code} {r.text}")
        # If 401, mock auth might not be enabled or requires restart with env var.
        # We assume user is running backend with MOCK_AUTH_USER set or we can't test auto.
        return

    # 2. Check User Info (Should need terms)
    print_step("Verifying initial status (Should need terms)...")
    r = requests.get(f"{USERS_URL}/me")
    data = r.json()
    if data.get("needsTermsUpdate") is True and data.get("termsAccepted") is False:
        print("✅ User correctly flagged as needing terms update.")
    else:
        print(f"❌ Unexpected status: {data}")

    # 3. Get Current Terms
    print_step("Fetching current terms...")
    r = requests.get(f"{USERS_URL}/terms/current")
    terms_data = r.json()
    version = terms_data.get("version")
    if version == "1.0" and terms_data.get("content"):
        print(f"✅ Terms fetched: v{version}")
    else:
        print(f"❌ Failed to fetch terms: {terms_data}")

    # 4. Accept Terms
    print_step("Accepting terms...")
    r = requests.post(f"{USERS_URL}/accept-terms", json={"terms_version": version})
    if r.status_code == 200:
        print("✅ Terms accepted successfully.")
    else:
        print(f"❌ Failed to accept terms: {r.status_code} {r.text}")

    # 5. Verify Status Again
    print_step("Verifying final status (Should NOT need terms)...")
    r = requests.get(f"{USERS_URL}/me")
    data = r.json()
    if data.get("needsTermsUpdate") is False and data.get("termsAccepted") is True:
        print("✅ User correctly flagged as terms accepted.")
        print(f"   Accepted At: {data.get('termsAcceptedAt')}")
        print(f"   Version: {data.get('termsVersion')}")
    else:
        print(f"❌ Unexpected status: {data}")

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    run_test()
