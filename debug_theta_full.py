
import httpx
import asyncio
import os
import json

async def main():
    host = os.getenv("THETA_HOST", "theta_terminal")
    base_url = f"http://{host}:25510/v2"
    
    print(f"Testing full flow against {base_url}...")
    
    async with httpx.AsyncClient() as client:
        # 1. Get Expirations
        try:
            resp = await client.get(f"{base_url}/list/expirations?root=SPX")
            data = resp.json()
            exps = data.get('response', [])
            print(f"Found {len(exps)} expirations.")
            if not exps:
                print("No expirations found!")
                return
            
            # Pick the last one (assuming sorted, usually most recent or furthest out)
            target_exp = exps[-1]
            print(f"Targeting Expiration: {target_exp}")
            
        except Exception as e:
            print(f"Exps Failed: {e}")
            return

        # 2. Get Strikes
        try:
            resp = await client.get(f"{base_url}/list/strikes", params={"root": "SPX", "exp": target_exp})
            strikes = resp.json().get('response', [])
            print(f"Found {len(strikes)} strikes for {target_exp}.")
            if strikes:
                print(f"Sample Strikes: {strikes[:5]}")
            else:
                print("No strikes found.")
        except Exception as e:
            print(f"Strikes Failed: {e}")

        # 3. Get Bulk Quotes (The crucial part)
        try:
            resp = await client.get(f"{base_url}/bulk_snapshot/option/quote", params={"root": "SPX", "exp": target_exp})
            print(f"Bulk Quote Status: {resp.status_code}")
            if resp.status_code == 200:
                quotes = resp.json().get('response', [])
                print(f"Found {len(quotes)} quotes.")
                if quotes:
                    print(f"Sample Quote: {quotes[0]}")
            else:
                print(f"Bulk Quote Failed Body: {resp.text[:500]}")
        except Exception as e:
            print(f"Bulk Quote Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
