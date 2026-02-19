"""
Theta Expected Moves Engine V2
-------------------------------
ThetaData-only backend provider for Expected Moves calculation.
Uses ThetaData REST API (port 25510) for reliable data access.
Dual-Logic: Static EOD Reference (Anchor) vs Live pricing.
Formula: Expected Move = Straddle Price * 0.85

Dependencies: httpx, logging, datetime, pytz
"""

import logging
import time
import httpx
from datetime import date, timedelta, datetime, time as dt_time
from typing import Dict, Any, Optional
import traceback
import pytz
import os
from pathlib import Path
import pandas as pd

# Setup Logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

# Index tickers that require /v2/hist/index/price instead of /v2/hist/stock/eod
INDEX_TICKERS = {"SPX", "VIX", "NDX", "RUT", "DJX"}
# Option root mapping (SPX options use SPXW for better liquidity)
OPTION_ROOT_MAP = {"SPX": "SPXW"}
SIGMA_FACTOR = 0.85


class ThetaExpectedMovesEngine:
    """
    Engine to calculate Expected Moves using ThetaData REST API (port 25510).
    Replaces the broken thetadata Python library with direct REST calls.
    Targets the previous trading day's close for Static EOD Anchors.
    """

    
    # Constants
    INDEX_TICKERS = {"SPX", "NDX", "RUT", "VIX", "DJI"}

    def __init__(self, host: str = "theta_terminal", port: int = 25510, use_mock: bool = False):
        self.theta_host = host
        self.theta_port = port
        self.base_url = f"http://{host}:{port}"
        self.et_tz = pytz.timezone('America/New_York')
        self.data_dir = Path("/app/data/expected_moves_v2")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        """No-op for compatibility with API endpoints."""
        pass

    def get_last_trading_day(self) -> date:
        """Get the most recent completed trading day."""
        from mie_lib.utils.trading_calendar import is_trading_day
        now_et = datetime.now(self.et_tz)

        # If before 4 PM on a weekday, last completed session is yesterday
        if now_et.time() < dt_time(16, 0) and now_et.weekday() < 5:
            target = now_et - timedelta(days=1)
        else:
            target = now_et

        # Walk backwards to find last weekday that's a trading day
        target_date = target.date()
        while target_date.weekday() >= 5 or not is_trading_day(target_date):
            target_date -= timedelta(days=1)

        return target_date

    def get_spot_price(self, client: httpx.Client, ticker: str) -> Optional[float]:
        """Fetch latest LIVE price (snapshot)"""
        try:
            # Determine URL based on asset type
            is_index = ticker.upper() in self.INDEX_TICKERS
            
            if is_index:
                # 2026-02-18: Snapshot endpoint for indices (SPX) is unreliable (472).
                # Use Historical Ticks instead (proven to work in theta_streamer).
                from datetime import date
                today_str = date.today().strftime("%Y%m%d")
                url = f"{self.base_url}/v2/hist/index/price"
                params = {
                    "root": ticker,
                    "start_date": today_str,
                    "end_date": today_str,
                    "ivl": "0" # 0 = tick level (every price change)
                }
            else:
                url = f"{self.base_url}/v2/snapshot/stock/quote"
                params = {"root": ticker}

            resp = client.get(url, params=params, timeout=5)
            
            if resp.status_code == 474:
                return None
            if resp.status_code != 200:
                LOG.warning(f"Snapshot Price API error {resp.status_code} for {ticker}")
                return None
            
            data = resp.json()
            if not data or "response" not in data:
                return None
            
            header = data.get("header", {}).get("format", [])
            items = data.get("response", [])
            
            if not items:
                return None
                
            # Parse Index Response (Hist Price)
            if is_index:
                last_item = items[-1]
                price = 0.0
                if "price" in header:
                    idx = header.index("price")
                    price = float(last_item[idx])
                elif "close" in header:
                    idx = header.index("close")
                    price = float(last_item[idx])
                elif len(last_item) >= 2:
                    price = float(last_item[1])
                
                LOG.info(f"Live {ticker} price (Tick): ${price}")
                return price

            # Parse Stock Response (Snapshot Quote)
            item = items[0] 
            tick = item
            
            bid = 0.0
            ask = 0.0
            
            if "bid" in header and "ask" in header:
                idx_bid = header.index("bid")
                idx_ask = header.index("ask")
                
                if isinstance(item, list):
                    bid = float(item[idx_bid]) if item[idx_bid] else 0.0
                    ask = float(item[idx_ask]) if item[idx_ask] else 0.0
                
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2.0
                LOG.info(f"Live {ticker} price (Mid): ${mid}")
                return mid
            
            return None

        except Exception as e:
            LOG.error(f"Error getting spot price for {ticker}: {e}")
            return None

    def get_atm_straddle(self, client: httpx.Client, option_root: str, exp_date: date, spot_price: float) -> Optional[Dict[str, Any]]:
        """
        Fetch ATM straddle from ThetaData bulk snapshot for a specific expiration.
        Uses /v2/bulk_snapshot/option/quote for all strikes at once.
        """
        exp_str = exp_date.strftime('%Y%m%d')
        url = f"{self.base_url}/v2/bulk_snapshot/option/quote"
        params = {"root": option_root, "exp": exp_str}

        LOG.info(f"Fetching ATM straddle for {option_root} exp={exp_date}...")
        try:
            response = client.get(url, params=params, timeout=15.0)
            if response.status_code != 200:
                LOG.warning(f"Snapshot API error {response.status_code} for {option_root} exp={exp_date}")
                return None

            data = response.json()
            header = data.get("header", {}).get("format", [])
            if not header:
                return None

            idx_bid = header.index("bid") if "bid" in header else None
            idx_ask = header.index("ask") if "ask" in header else None
            if idx_bid is None or idx_ask is None:
                LOG.warning(f"Missing bid/ask in header: {header}")
                return None

            # Parse contracts, find calls and puts near ATM
            calls = {}
            puts = {}

            for item in data.get("response", []):
                contract = item.get("contract", {})
                ticks = item.get("ticks", [])
                if not contract or not ticks:
                    continue

                strike_raw = contract.get("strike", 0)
                right = contract.get("right", "")
                strike = strike_raw / 1000.0

                tick = ticks[-1]
                bid = tick[idx_bid] if tick[idx_bid] else 0
                ask = tick[idx_ask] if tick[idx_ask] else 0
                mid = (bid + ask) / 2.0

                if right == "C":
                    calls[strike] = mid
                elif right == "P":
                    puts[strike] = mid

            if not calls and not puts:
                LOG.warning(f"No option data for {option_root} exp={exp_date}")
                return None

            # Find ATM strike
            all_strikes = sorted(set(calls.keys()) | set(puts.keys()))
            if not all_strikes:
                return None
            atm_strike = min(all_strikes, key=lambda s: abs(s - spot_price))

            call_price = calls.get(atm_strike, 0)
            put_price = puts.get(atm_strike, 0)
            data_quality = "good"

            # Bad Tick Filter
            if call_price <= 0.05 and put_price > 0.05:
                LOG.warning(f"BAD TICK: Call=${call_price:.2f} near-zero. Estimating Call ≈ Put (${put_price:.2f})")
                call_price = put_price
                data_quality = "estimated"
            elif put_price <= 0.05 and call_price > 0.05:
                LOG.warning(f"BAD TICK: Put=${put_price:.2f} near-zero. Estimating Put ≈ Call (${call_price:.2f})")
                put_price = call_price
                data_quality = "estimated"
            elif call_price <= 0.05 and put_price <= 0.05:
                LOG.error(f"BAD TICK: Both legs near-zero. Skipping {option_root} exp={exp_date}")
                return None

            straddle = call_price + put_price
            LOG.info(f"ATM {atm_strike}: C=${call_price:.2f} P=${put_price:.2f} Straddle=${straddle:.2f} [{data_quality}]")
            return {
                "strike": atm_strike,
                "call_price": round(call_price, 2),
                "put_price": round(put_price, 2),
                "straddle_price": round(straddle, 2),
                "data_quality": data_quality,
            }

        except Exception as e:
            LOG.error(f"Straddle fetch error for {option_root} exp={exp_date}: {e}")
            return None

    def get_expirations(self, as_of: date) -> Dict[str, date]:
        """Resolves 0DTE, Weekly, Monthly expirations."""
        from mie_lib.utils.trading_calendar import is_trading_day, get_next_trading_day, last_trading_day_of_month

        now_et = datetime.now(self.et_tz)
        market_still_open = (
            is_trading_day(as_of)
            and now_et.date() == as_of
            and now_et.time() < dt_time(16, 0)
        )

        # 0DTE: today if market open, else next trading day
        if market_still_open:
            odte = as_of
        else:
            odte = get_next_trading_day(as_of)

        # Weekly: next Friday (or nearest trading day after it)
        days_ahead = 4 - as_of.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        weekly = as_of + timedelta(days=days_ahead)

        # Monthly: last trading day of current month (EOM)
        monthly = last_trading_day_of_month(as_of.year, as_of.month)
        if monthly <= as_of:
            if as_of.month == 12:
                monthly = last_trading_day_of_month(as_of.year + 1, 1)
            else:
                monthly = last_trading_day_of_month(as_of.year, as_of.month + 1)

        return {
            "0DTE": odte,
            "WEEKLY": weekly,
            "MONTHLY": monthly,
        }

    def save_to_parquet(self, data: Dict[str, Any]):
        """Persist static EOD data to Parquet for Reliability Study sync."""
        try:
            ticker = data['ticker']
            data_date = data['data_date']

            rows = []
            for expiry_type in ['0dte', 'weekly', 'monthly']:
                range_key = f"{expiry_type}_range"
                rdata = data.get(range_key)
                if rdata:
                    debug = rdata.get('debug', {})
                    rows.append({
                        'calc_date': data_date,
                        'ticker': ticker,
                        'expiry_type': expiry_type.upper(),
                        'expiry_date': debug.get('expiry'),
                        'spot_price': data['current_price'],
                        'expected_move_dollars': rdata.get('plus_minus'),
                        'expected_move_high': rdata.get('high'),
                        'expected_move_low': rdata.get('low'),
                    })

            if not rows:
                LOG.warning("No range data to save to Parquet")
                return

            df_new = pd.DataFrame(rows)
            parquet_file = self.data_dir / f"{ticker}_expected_moves_v2.parquet"

            if parquet_file.exists():
                df_existing = pd.read_parquet(parquet_file)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['calc_date', 'expiry_type'], keep='last')
                df_combined.to_parquet(parquet_file, index=False)
            else:
                df_new.to_parquet(parquet_file, index=False)

            LOG.info(f"Saved EOD data to {parquet_file}")

        except Exception as e:
            LOG.error(f"Failed to save Parquet: {e}")

    def run(self, ticker: str) -> Dict[str, Any]:
        """
        Executes the full calculation and returns Static EOD Reference data.
        Uses ThetaData REST API (port 25510) for all data access.
        """
        try:
            LOG.info(f"=== Expected Moves V2 (ThetaData REST) for {ticker} ===")
            ticker = ticker.upper()

            with httpx.Client() as client:
                # 1. Get spot price
                spot_price = self.get_spot_price(client, ticker)
                if not spot_price or spot_price <= 0:
                    return {"error": "Failed to fetch spot price", "ticker": ticker}

                LOG.info(f"Spot Price: ${spot_price:.2f}")

                # 2. Get expiration dates
                last_trading_day = self.get_last_trading_day()
                today = date.today()
                exps = self.get_expirations(today)

                # 3. Determine option root (SPXW for SPX, ticker for others)
                option_root = OPTION_ROOT_MAP.get(ticker, ticker)

                output = {
                    "ticker": ticker,
                    "current_price": spot_price,
                    "market_status": "OPEN" if self._is_market_open() else "CLOSED",
                    "data_date": last_trading_day.isoformat(),
                    "data_source": "theta_rest_api",
                    "reference_type": "static_eod_anchor",
                }

                # 4. Calculate EM for each tenor
                for label, exp_date in exps.items():
                    key = label.lower() + "_range"
                    straddle = self.get_atm_straddle(client, option_root, exp_date, spot_price)

                    if straddle:
                        breakeven = straddle["straddle_price"]
                        sigma = round(breakeven * SIGMA_FACTOR, 2)
                        quality = straddle.get("data_quality", "good")
                        output[key] = {
                            # Backward-compatible fields (default to sigma)
                            "high": round(spot_price + sigma, 2),
                            "low": round(spot_price - sigma, 2),
                            "plus_minus": sigma,
                            # Dual-mode fields
                            "breakeven_move": round(breakeven, 2),
                            "sigma_move": sigma,
                            "upper_breakeven": round(spot_price + breakeven, 2),
                            "lower_breakeven": round(spot_price - breakeven, 2),
                            "upper_sigma": round(spot_price + sigma, 2),
                            "lower_sigma": round(spot_price - sigma, 2),
                            "data_quality": quality,
                            "debug": {
                                "expiry": exp_date.isoformat(),
                                "atm_strike": straddle["strike"],
                                "call_price": straddle["call_price"],
                                "put_price": straddle["put_price"],
                                "straddle_price": straddle["straddle_price"],
                            },
                        }
                    else:
                        output[key] = None

                # 5. Persist to Parquet
                self.save_to_parquet(output)

                LOG.info(f"=== Static EOD Reference Complete for {ticker} ===")
                return output

        except Exception as e:
            LOG.error(f"Run failed for {ticker}: {e}", exc_info=True)
            return {"error": str(e), "ticker": ticker}

    def _is_market_open(self) -> bool:
        """Simple check for market hours."""
        now_et = datetime.now(self.et_tz)
        if now_et.weekday() >= 5:
            return False
        return dt_time(9, 30) <= now_et.time() <= dt_time(16, 0)


if __name__ == "__main__":
    eng = ThetaExpectedMovesEngine()
    res = eng.run("SPY")
    print(res)
