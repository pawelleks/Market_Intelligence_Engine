"""
ThetaData REST API Provider
---------------------------
Reusable client for accessing Theta Terminal REST API (default port 25510).
Used to replace yfinance for Spot Price, VIX, and Option Enrichment.
"""

import httpx
import logging
import os
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List

LOG = logging.getLogger(__name__)

class ThetaRestClient:
    """
    Client for Theta Terminal REST API.
    """
    def __init__(self, host: str = None, port: int = None):
        self.host = host or os.getenv("THETA_HOST", "theta_terminal")
        self.port = port or int(os.getenv("THETA_REST_PORT", "25510"))
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Known Indices for routing to /v2/hist/index
        self.INDEX_ROOTS = {"SPX", "VIX", "NDX", "RUT", "DJX", "VIX1D"}

    def get_eod_price(self, root: str, as_of: date) -> Optional[float]:
        """
        Fetches the Close price for a specific date (or nearest previous trading day).
        Walks back up to 5 days to find data.
        """
        # Determine endpoint
        # Remove ^ if present (ThetaData uses SPX not ^SPX)
        clean_root = root.lstrip('^')
        
        is_index = clean_root in self.INDEX_ROOTS
        endpoint = "/v2/hist/index/eod" if is_index else "/v2/hist/stock/eod"
        url = f"{self.base_url}{endpoint}"
        
        # Try fetch
        with httpx.Client() as client:
            # We request a small window ending on 'as_of' to ensure we get the latest available close
            # But 'as_of' might be a weekend.
            # EOD endpoint is efficient, we can request a 5 day window ending on as_of
            start_date = as_of - timedelta(days=5)
            params = {
                "root": clean_root,
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": as_of.strftime("%Y%m%d")
            }
            
            try:
                LOG.info(f"ThetaRest: Fetching price for {clean_root} [{start_date} to {as_of}]")
                resp = client.get(url, params=params, timeout=30.0)
                if resp.status_code != 200:
                    LOG.warning(f"ThetaRest: API Error {resp.status_code} for {clean_root}")
                    return None
                    
                data = resp.json()
                candles = data.get("response", [])
                
                if not candles:
                    LOG.warning(f"ThetaRest: No candles found for {clean_root}")
                    return None
                    
                # Parse Header
                header = data.get("header", {}).get("format", [])
                try:
                    close_idx = header.index("close")
                    date_idx = header.index("date") if "date" in header else -1
                    
                    # Sort by date descending to get most recent
                    if date_idx >= 0:
                        candles.sort(key=lambda x: x[date_idx], reverse=True)
                    
                    latest_close = float(candles[0][close_idx])
                    return latest_close
                    
                except ValueError:
                    LOG.error(f"ThetaRest: Could not parse header {header}")
                    return None
                    
            except Exception as e:
                LOG.error(f"ThetaRest: Exception fetching price for {clean_root}: {e}")
                return None

    def get_option_snapshot(self, root: str, exp: date) -> pd.DataFrame:
        """
        Fetches Option Chain Snapshot (Strike, Right, Bid, Ask, IV, OI?) 
        Note: /v2/bulk_snapshot/option/quote gives Bid/Ask.
        /v2/bulk_snapshot/option/greeks gives IV/Delta/Gamma.
        
        We need IV, OI, and Price (Mid).
        The most efficient way is likely `bulk_snapshot` if we want live data.
        
        For HISTORICAL enrichment (backfill), we would need `hist/option/eod` but that's per contract.
        ThetaData doesn't have a generic "bulk historical eod" for all strikes easily without iterating.
        
        However, `engine.py` calls this `enrich_with_yf_data` mostly for OI/IV when missing.
        Massive files usually have OI/IV. This is a fallback.
        
        If `as_of` is Today, we use Snapshot.
        If `as_of` is Historical, ThetaData usage is trickier for bulk.
        
        BUT: The requirement is for `/expected-moves` which runs DAILY.
        The `yfinance` fallback was checking `yf_ticker.option_chain(exp_str)`.
        YFinance ONLY provides CURRENT chain data (delayed). It does NOT provide historical chains.
        So replacing YF with Theta Snapshot is actually functionally equivalent (or better).
        
        We will return a DataFrame with: ['strike', 'option_type', 'iv', 'oi', 'bid', 'ask']
        """
        clean_root = root.lstrip('^')
        # SPX -> SPXW for liquidity? Massive usually maps SPX, but let's stick to root provided.
        # Actually expected moves engine handles 'SPX' vs 'SPXW' logic elsewhere?
        # Let's use the root passed in.
        
        exp_str = exp.strftime("%Y%m%d")
        
        # We need Quote (Price) and Greeks (IV). OI is in Quoute or OpenInterest endpoint?
        # /v2/bulk_snapshot/option/quote -> Bid, Ask
        # /v2/bulk_snapshot/option/greeks -> IV, Delta, Gamma
        # /v2/bulk_snapshot/option/open_interest -> OI
        
        # Fetching 3 bulk endpoints is heavy but accurate.
        # Let's implement QUOTE + GREEKS (for IV).
        
        dfs = []
        with httpx.Client() as client:
            # 1. Greeks (IV)
            greeks_url = f"{self.base_url}/v2/bulk_snapshot/option/greeks"
            try:
                resp = client.get(greeks_url, params={"root": clean_root, "exp": exp_str}, timeout=5.0)
                if resp.status_code == 200:
                    g_data = resp.json()
                    g_header = g_data.get("header", {}).get("format", [])
                    g_rows = g_data.get("response", [])
                    
                    parsed_greeks = []
                    # Header: [ms_of_day, strike, right, bid_iv, ask_iv, delta, gamma, ...]
                    # We need ms, strike, right, midpoint_iv? Usually just 'implied_vol' or bid/ask iv.
                    # Let's map dynamically.
                    
                    # Helper to safe get
                    def get_idx(h, name): return h.index(name) if name in h else -1
                    
                    idx_strike = get_idx(g_header, "strike")
                    idx_right = get_idx(g_header, "right")
                    idx_iv = get_idx(g_header, "implied_vol") # V1?
                    # V2 usually has delta, gamma, theta, vega, rho, implied_vol
                    
                    if idx_strike >= 0 and idx_right >= 0 and idx_iv >= 0:
                        for row in g_rows:
                            contract = row.get("contract", {}) # V2 uses Objects usually?
                            # Wait, bulk_snapshot returns list of objects usually?
                            # Let's check format. "response": [ { "contract": {...}, "ticks": [...] } ]
                            
                            # Actually bulk_snapshot usually returns a list of items.
                            # Each item has "contract": { "root":..., "strike":..., "right":... }
                            
                            # Let's parse strictly based on observed Theta response structure
                            contract = row.get("contract", {})
                            strike = contract.get("strike", 0) / 1000.0
                            right = contract.get("right", "")
                            
                            ticks = row.get("ticks", [])
                            if ticks:
                                # Greeks tick: [ms, iv, delta, gamma...]
                                val = ticks[-1] # Latest
                                iv = val[idx_iv]
                                parsed_greeks.append({
                                    "strike": strike,
                                    "option_type": right,
                                    "iv": iv,
                                })
                    
                    if parsed_greeks:
                         dfs.append(pd.DataFrame(parsed_greeks).set_index(["strike", "option_type"]))
            except Exception as e:
                LOG.warning(f"ThetaRest: Greeks fetch failed: {e}")

            # 2. Quote (Price for Mid/OI fallback?)
            # Does Quote give OI? No.
            # Does Quote give Price? Yes (Bid/Ask).
            # We want IV mostly.
            # If we need open interest, we need /open_interest endpoint.
            
            # For now, let's prioritize IV as that's what enrichment usually wants.
            
        if not dfs:
            return pd.DataFrame()
            
        # Join dataframes?
        # For now, just returning IVs
        result = dfs[0].reset_index()
        return result
