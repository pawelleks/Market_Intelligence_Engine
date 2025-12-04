import os
import logging
import requests
import pandas as pd
from datetime import date
from typing import Optional, Dict, Any

LOG = logging.getLogger(__name__)

class MassiveOptionChainProvider:
    """
    Provider for fetching option chains from Massive.com.
    Requires MASSIVE_API_KEY environment variable.
    """
    BASE_URL = "https://api.massive.com/v1" # Hypothetical URL, adjust if known

    def __init__(self):
        self.api_key = os.environ.get("MASSIVE_API_KEY")
        if not self.api_key:
            LOG.warning("MASSIVE_API_KEY not found in environment variables.")

    def fetch_chain(self, ticker: str, expiry: date) -> pd.DataFrame:
        """
        Fetches option chain for a given ticker and expiry.
        """
        if not self.api_key:
            return pd.DataFrame()

        try:
            # Endpoint based on user example and previous context
            # The user used client.list_snapshot_options_chain which likely maps to:
            # GET /v3/snapshot/options/{ticker}
            base_url = f"https://api.massive.com/v3/snapshot/options/{ticker}"
            params = {
                "expiration_date": expiry.isoformat(), # User example uses 'expiration_date'
                "order": "asc",
                "limit": 250,
                "sort": "ticker",
                "apiKey": self.api_key
            }
            
            all_results = []
            while True:
                response = requests.get(base_url, params=params, timeout=10)
                if not response.ok:
                    LOG.error(f"Massive Chain Error {response.status_code}: {response.text}")
                    break
                    
                data = response.json()
                results = data.get('results', [])
                all_results.extend(results)
                
                # Log sample of first result to verify structure
                if len(all_results) > 0 and len(all_results) <= 250:
                     LOG.info(f"Sample Option Result: {all_results[0]}")

                # Pagination Logic
                next_url = data.get('next_url')
                if next_url:
                    base_url = next_url
                    params = {"apiKey": self.api_key}
                else:
                    break
                    
                if len(all_results) > 5000: 
                    LOG.warning(f"Massive chain fetch exceeded 5000 contracts for {ticker}")
                    break

            if not all_results:
                LOG.warning(f"No options found for {ticker} on {expiry}")
                return pd.DataFrame()

            records = []
            for opt in all_results:
                # Parse based on User's JSON example
                details = opt.get('details', {})
                strike = details.get('strike_price')
                contract_type = details.get('contract_type') # 'call' or 'put'
                
                # Price: Prefer midpoint from last_quote
                last_quote = opt.get('last_quote', {})
                mid = last_quote.get('midpoint')
                
                # Fallback to bid/ask calculation if midpoint missing
                if mid is None:
                    bid = last_quote.get('bid', 0)
                    ask = last_quote.get('ask', 0)
                    if bid or ask:
                        mid = (bid + ask) / 2
                    else:
                        # Fallback to last trade price if no quote
                        mid = opt.get('last_trade', {}).get('price', 0)
                
                # IV
                iv = opt.get('implied_volatility')
                
                if strike and contract_type:
                    records.append({
                        'strike': float(strike),
                        'option_type': 'C' if 'call' in contract_type.lower() else 'P',
                        'prev_close_mid': float(mid) if mid else 0.0,
                        'iv': float(iv) if iv else 0.0
                    })
            
            LOG.info(f"Parsed {len(records)} records for {ticker} {expiry}")
            return pd.DataFrame(records)

        except Exception as e:
            LOG.error(f"Massive API error for {ticker} {expiry}: {e}")
            return pd.DataFrame()

    def fetch_contract_price(self, contract_ticker: str) -> Optional[float]:
        """
        Fetches the previous close price for a specific option contract.
        Used as a workaround for blocked Snapshot API.
        """
        if not self.api_key:
            return None
        try:
            # Endpoint: /v2/aggs/ticker/{contract_ticker}/prev
            url = f"https://api.massive.com/v2/aggs/ticker/{contract_ticker}/prev"
            params = {"apiKey": self.api_key}
            
            response = requests.get(url, params=params, timeout=5)
            if not response.ok:
                LOG.warning(f"Massive Contract Error {response.status_code} for {contract_ticker}: {response.text}")
                return None
            
            data = response.json()
            results = data.get('results', [])
            if results and isinstance(results, list):
                return float(results[0].get('c'))
            return None
        except Exception as e:
            LOG.error(f"Massive Contract Fetch Error for {contract_ticker}: {e}")
            return None

    def fetch_spot(self, ticker: str) -> Optional[float]:
        if not self.api_key:
            return None
        try:
            # User has delayed/EOD data. Snapshot (Real-time) is blocked (403).
            # Try "Previous Close" endpoint which is usually available for EOD.
            # Endpoint: /v2/aggs/ticker/{ticker}/prev
            url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/prev"
            params = {"apiKey": self.api_key}
            
            response = requests.get(url, params=params, timeout=5)
            if not response.ok:
                LOG.error(f"Massive Spot Error {response.status_code}: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Expected Response for /prev:
            # { "results": [ { "c": 450.1, "o": 448.0, ... } ], "status": "OK" }
            
            results = data.get('results', [])
            if results and isinstance(results, list):
                # Use closing price of previous day
                return float(results[0].get('c'))
                
            return None
            
        except Exception as e:
            LOG.error(f"Massive API spot price error for {ticker}: {e}")
            return None
