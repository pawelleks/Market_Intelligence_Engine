
import requests
import sys

def verify_api():
    base_url = "http://localhost:8000/api/v1/analytics/psar"
    ticker = "SPY"
    url = f"{base_url}/{ticker}"
    
    print(f"Testing API: {url}")
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print("Status: 200 OK")
            print(f"Keys: {list(data.keys())}")
            if "latest" in data:
                print("Latest:", data["latest"])
            if "history" in data:
                print(f"History Rows: {len(data['history'])}")
                if len(data['history']) > 0:
                    print("Sample History:", data['history'][0])
        else:
            print(f"Error: {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    verify_api()
