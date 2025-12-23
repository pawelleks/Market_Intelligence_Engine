import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import math

# Setup Logging
logger = logging.getLogger(__name__)

class BlackScholes:
    """
    Black-Scholes Calculator for Option Greeks (specifically Gamma).
    """
    
    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate d1 component of Black-Scholes.
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate Gamma for an option (same for Call and Put).
        Formula: N'(d1) / (S * sigma * sqrt(T))
        """
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0.0
            
        d1_val = BlackScholes.d1(S, K, T, r, sigma)
        # N'(x) is the PDF of standard normal distribution
        n_prime_d1 = norm.pdf(d1_val)
        
        gamma_val = n_prime_d1 / (S * sigma * np.sqrt(T))
        return gamma_val

    @staticmethod
    def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate Black-Scholes Call Price."""
        if T <= 0: return max(0.0, S - K)
        if sigma <= 0: return max(0.0, S - K) # Intrinsic
        
        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = d1 - sigma * np.sqrt(T)
        
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

    @staticmethod
    def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate Black-Scholes Put Price."""
        if T <= 0: return max(0.0, K - S)
        if sigma <= 0: return max(0.0, K - S) # Intrinsic
        
        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = d1 - sigma * np.sqrt(T)
        
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

class GEXEngine:
    """
    Engine to calculate Gamma Exposure (GEX) for a ticker.
    """
    
    def __init__(self, risk_free_rate: float = 0.046):
        self.r = risk_free_rate # Approx 4.6% (e.g. 10Y Treasury)

    def _get_time_to_expiration(self, expiry_str: str) -> float:
        """
        Calculate years to expiration from a date string (YYYY-MM-DD).
        """
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            today = date.today()
            delta = (expiry_date - today).days
            
            # Explicitly handle expired options
            if delta < 0:
                return -1.0 # Expired
                
            # If expiration is today, use a small fraction (0DTE)
            if delta == 0:
                return 1.0 / 365.0 / 2.0 # Half a day
                
            return delta / 365.0
        except Exception:
            return 0.0

    def fetch_and_calculate_gex(self, ticker: str, spot_override: Optional[float] = None) -> Dict:
        """
        Fetches option chain from yfinance and calculates GEX profile.
        Uses consistent Horizon logic (EOW, EOM, EOQ).
        """
        try:
            yf_ticker = yf.Ticker(ticker)
            
            # 1. Get Spot Price
            spot = spot_override
            
            if spot is None:
                # Try fast info first, then history
                try:
                    spot = yf_ticker.fast_info['last_price']
                except:
                    hist = yf_ticker.history(period="1d")
                    if not hist.empty:
                        spot = hist['Close'].iloc[-1]
                    else:
                        logger.error(f"Could not fetch spot price for {ticker}")
                        return {}

            if spot is None or np.isnan(spot):
                 logger.error(f"Invalid spot price for {ticker}")
                 return {}

            # 2. Get Expirations
            expirations = yf_ticker.options
            if not expirations:
                logger.warning(f"No options found for {ticker}")
                return {}

            # Determine Horizons
            today = date.today()
            horizons = self._get_horizon_targets(today)
            
            all_gex_data = []

            # 3. Iterate Expirations and Calculate GEX
            for expiry in expirations:
                T = self._get_time_to_expiration(expiry)
                
                # Skip expired options
                if T < 0:
                    continue
                    
                # Determine Matched Horizons
                try:
                    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                except ValueError:
                    continue

                matched_horizons = ["total"]
                for h_key, h_date in horizons.items():
                    if exp_date <= h_date:
                        matched_horizons.append(h_key)

                try:
                    chain = yf_ticker.option_chain(expiry)
                    calls = chain.calls
                    puts = chain.puts
                except Exception as e:
                    logger.warning(f"Failed to fetch chain for {ticker} {expiry}: {e}")
                    continue

                # Process Calls
                if not calls.empty:
                    for _, row in calls.iterrows():
                        strike = row['strike']
                        iv = row['impliedVolatility']
                        oi = row['openInterest']
                        
                        if pd.isna(iv) or iv <= 0 or pd.isna(oi) or oi <= 0:
                            continue
                            
                        gamma = BlackScholes.gamma(spot, strike, T, self.r, iv)
                        
                        # GEX Formula: Gamma * OI * Spot^2 * 0.01 * 100
                        gex = gamma * oi * (spot ** 2) * 0.01 * 100
                        
                        all_gex_data.append({
                            "strike": strike,
                            "gex": gex,
                            "type": "call",
                            "horizons": matched_horizons,
                            "expiry": expiry
                        })

                # Process Puts
                if not puts.empty:
                    for _, row in puts.iterrows():
                        strike = row['strike']
                        iv = row['impliedVolatility']
                        oi = row['openInterest']
                        
                        if pd.isna(iv) or iv <= 0 or pd.isna(oi) or oi <= 0:
                            continue
                        
                        gamma = BlackScholes.gamma(spot, strike, T, self.r, iv)
                        
                        # GEX Formula (Negative for Puts)
                        gex = -1 * (gamma * oi * (spot ** 2) * 0.01 * 100)
                        
                        all_gex_data.append({
                            "strike": strike,
                            "gex": gex,
                            "type": "put",
                            "horizons": matched_horizons,
                            "expiry": expiry
                        })

            if not all_gex_data:
                return {}

            # 4. Aggregation by Strike
            profile_map = {}
            horizon_keys = list(horizons.keys()) + ["total"]
            
            def init_row(s):
                row = {"strike": s, "total_net_gex": 0.0}
                for h in horizon_keys:
                    row[f"{h}_call_gex"] = 0.0
                    row[f"{h}_put_gex"] = 0.0
                    row[f"{h}_net_gex"] = 0.0
                return row

            for d in all_gex_data:
                s = d['strike']
                gex = d['gex']
                otype = d['type']
                
                if s not in profile_map:
                    profile_map[s] = init_row(s)
                
                for h in d['horizons']:
                    if otype == 'call':
                        profile_map[s][f"{h}_call_gex"] += gex
                    else:
                        profile_map[s][f"{h}_put_gex"] += gex
                    profile_map[s][f"{h}_net_gex"] += gex

            sorted_strikes = sorted(profile_map.keys())
            profile = [profile_map[s] for s in sorted_strikes]

            # 5. Metadata
            group_dates = {k: v.strftime("%Y-%m-%d") for k, v in horizons.items()}
            
            return {
                "ticker": ticker,
                "spot_price": spot,
                "net_gex": sum(d['gex'] for d in all_gex_data),
                "profile": profile,
                "group_dates": group_dates,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating GEX for {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _get_horizon_targets(self, as_of: date) -> Dict[str, date]:
        """Calculates target dates for the requested horizons."""
        # 1. EOW (Friday of current week)
        # weekday: Mon=0, Sun=6. Friday=4.
        days_to_fri = (4 - as_of.weekday() + 7) % 7
        if days_to_fri == 0:
            days_to_fri = 7
        eow = as_of + timedelta(days=days_to_fri)

        # 2. EOM (Last day of month)
        next_month = as_of.replace(day=28) + timedelta(days=4)
        eom = next_month - timedelta(days=next_month.day)

        # 3. EOQ (End of current quarter: Mar, Jun, Sep, Dec)
        quarter_months = [3, 6, 9, 12]
        curr_month = as_of.month
        try:
            q_month = next(m for m in quarter_months if m >= curr_month)
        except StopIteration:
             q_month = 3 # fallback
        
        if q_month == 12:
            eoq = date(as_of.year, 12, 31)
        else:
            tgt = date(as_of.year, q_month, 1) + timedelta(days=32)
            eoq = tgt.replace(day=1) - timedelta(days=1)
        
        # 4. Next 5
        next5 = as_of + timedelta(days=5)

        # 5. Next 30
        next30 = as_of + timedelta(days=30)
        
        return {
            "eow": eow,
            "eom": eom,
            "eoq": eoq,
            "next5": next5,
            "next30": next30
        }

    def calculate_gex_from_frame(self, ticker: str, df: pd.DataFrame, spot_price: float, as_of: Optional[date] = None) -> Dict:
        """
        Calculates GEX using a pre-loaded DataFrame (from Massive Flat File).
        
        Args:
            ticker: Underlying Symbol
            df: DataFrame with columns [strike, type, expiration, oi, gamma, iv]
            spot_price: Current spot price of underlying
            as_of: Optional "Today" date for horizon calculations. Defaults to actual today.
            
        Returns:
             Dict structure with multi-horizon profiles.
        """
        try:
            if df.empty:
                return {}
            
            # Determine Horizons
            today = as_of if as_of else date.today()
            horizons = self._get_horizon_targets(today)
            
            all_gex_data = []
            
            for _, row in df.iterrows():
                expiry_str = str(row['expiration']).strip() # YYYY-MM-DD
                
                # Validate date string before parsing
                if not expiry_str or expiry_str.lower() in ('none', 'nan', 'nat', ''):
                    continue
                    
                try:
                    exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                except ValueError:
                    # Log debug if needed, but skipping is safer for pipeline resilience
                    continue
                
                # Calculate T (for Gamma if needed)
                # We need T for BlackScholes if gamma is missing
                # Duplicating logic from _get_time_to_expiration but using date obj
                delta = (exp_date - today).days
                if delta < 0:
                    # Expired
                    continue
                if delta == 0:
                    # 0DTE
                    T = 1.0 / 365.0 / 2.0
                else:
                    T = delta / 365.0
                
                # Assign to Horizons (One expiry can match multiple)
                matched_horizons = []
                # Always 'total'
                matched_horizons.append("total")
                
                for h_key, h_date in horizons.items():
                    if exp_date <= h_date:
                        matched_horizons.append(h_key)
                
                strike = row['strike']
                oi = row['oi']
                otype = row['type'].lower() # 'call' or 'put'
                
                # Use provided Gamma if available, else calc (if IV present)
                if 'gamma' in row and not pd.isna(row['gamma']) and row['gamma'] != 0:
                    gamma_val = row['gamma']
                elif 'iv' in row and row['iv'] > 0:
                     gamma_val = BlackScholes.gamma(spot_price, strike, T, self.r, row['iv'])
                else:
                    continue # Cannot calc GEX without Gamma
                    
                raw_gex = gamma_val * oi * (spot_price ** 2) * 0.01 * 100
                
                if otype == 'put':
                    raw_gex *= -1 # Puts are negative GEX usually implies Dealer Short Gamma
                    
                all_gex_data.append({
                    "strike": strike,
                    "gex": raw_gex,
                    "type": otype,
                    "horizons": matched_horizons,
                    "expiry": expiry_str
                })
                
            if not all_gex_data:
                return {}
                
            # Aggregation by Strike
            profile_map = {} 
            horizon_keys = list(horizons.keys()) + ["total"]
            
            def init_row(s):
                row = {"strike": s, "total_net_gex": 0.0}
                for h in horizon_keys:
                    row[f"{h}_call_gex"] = 0.0
                    row[f"{h}_put_gex"] = 0.0
                    row[f"{h}_net_gex"] = 0.0
                return row

            for d in all_gex_data:
                s = d['strike']
                gex = d['gex']
                otype = d['type']
                
                if s not in profile_map:
                    profile_map[s] = init_row(s)
                
                for h in d['horizons']:
                    if otype == 'call':
                        profile_map[s][f"{h}_call_gex"] += gex
                    else:
                        profile_map[s][f"{h}_put_gex"] += gex
                    profile_map[s][f"{h}_net_gex"] += gex

            sorted_strikes = sorted(profile_map.keys())
            profile = [profile_map[s] for s in sorted_strikes]

            group_dates = {k: v.strftime("%Y-%m-%d") for k, v in horizons.items()}
            
            return {
                "ticker": ticker,
                "spot_price": spot_price,
                "net_gex": sum(d['gex'] for d in all_gex_data), # Total Net
                "profile": profile,
                "group_dates": group_dates,
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Error in calculate_gex_from_frame: {e}")
            return {}
