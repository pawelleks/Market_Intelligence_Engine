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
            # If expiration is today, use a small fraction to avoid div by zero (e.g. 0.5/365)
            if delta <= 0:
                return 1.0 / 365.0 / 2.0 # Half a day
            return delta / 365.0
        except Exception:
            return 0.0

    def fetch_and_calculate_gex(self, ticker: str, spot_override: Optional[float] = None) -> Dict:
        """
        Fetches option chain from yfinance and calculates GEX profile.
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

            all_gex_data = []

            # 3. Iterate Expirations and Calculate GEX
            for expiry in expirations:
                T = self._get_time_to_expiration(expiry)
                days_to_expiry = T * 365.0
                
                # Determine Group (Weekly vs Monthly)
                # Weekly: < 15 days
                # Monthly: 15 <= DTE < 45
                # Other: >= 45 (Included in Net, but maybe separate group)
                if days_to_expiry < 15:
                    group = "Weekly"
                elif 15 <= days_to_expiry < 45:
                    group = "Monthly"
                else:
                    group = "LongTerm"

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
                        
                        # GEX Formula: Gamma * OI * Spot^2 * 0.01 * 100 (Multiplier)
                        # Call GEX is Positive
                        gex = gamma * oi * (spot ** 2) * 0.01 * 100
                        
                        if strike == 680 or strike == 683:
                             print(f"DEBUG: type=call strike={strike} iv={iv} gamma={gamma} oi={oi} gex={gex}")
                        
                        all_gex_data.append({
                            "strike": strike,
                            "gex": gex,
                            "type": "call",
                            "group": group,
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
                        
                        # GEX Formula: Gamma * OI * Spot^2 * 0.01 * 100 (Multiplier)
                        # Put GEX is Negative
                        gex = -1 * (gamma * oi * (spot ** 2) * 0.01 * 100)
                        
                        all_gex_data.append({
                            "strike": strike,
                            "gex": gex,
                            "type": "put",
                            "group": group,
                            "expiry": expiry
                        })

            if not all_gex_data:
                return {}

            # 4. Aggregation
            df = pd.DataFrame(all_gex_data)
            
            # Net GEX (Total Sum)
            net_gex = df['gex'].sum()
            
            # Profile per Strike (Grouped by Weekly/Monthly)
            # We want: Strike | Weekly Call GEX | Weekly Put GEX | Monthly Call GEX | Monthly Put GEX | Total Net GEX
            
            # Pivot to get GEX per strike and group/type
            # We aggregate by Strike first
            
            strikes = sorted(df['strike'].unique())
            profile = []
            
            for strike in strikes:
                strike_df = df[df['strike'] == strike]
                
                # Weekly
                weekly_calls = strike_df[(strike_df['group'] == 'Weekly') & (strike_df['type'] == 'call')]['gex'].sum()
                weekly_puts = strike_df[(strike_df['group'] == 'Weekly') & (strike_df['type'] == 'put')]['gex'].sum()
                
                # Monthly
                monthly_calls = strike_df[(strike_df['group'] == 'Monthly') & (strike_df['type'] == 'call')]['gex'].sum()
                monthly_puts = strike_df[(strike_df['group'] == 'Monthly') & (strike_df['type'] == 'put')]['gex'].sum()
                
                # Quarterly / LongTerm
                quarterly_calls = strike_df[(strike_df['group'] == 'LongTerm') & (strike_df['type'] == 'call')]['gex'].sum()
                quarterly_puts = strike_df[(strike_df['group'] == 'LongTerm') & (strike_df['type'] == 'put')]['gex'].sum()

                # Total (including LongTerm)
                total_gex = strike_df['gex'].sum()
                
                profile.append({
                    "strike": strike,
                    "weekly_call_gex": weekly_calls,
                    "weekly_put_gex": weekly_puts,
                    "weekly_net_gex": weekly_calls + weekly_puts,
                    "monthly_call_gex": monthly_calls,
                    "monthly_put_gex": monthly_puts,
                    "monthly_net_gex": monthly_calls + monthly_puts,
                    "quarterly_call_gex": quarterly_calls,
                    "quarterly_put_gex": quarterly_puts,
                    "quarterly_net_gex": quarterly_calls + quarterly_puts,
                    "total_net_gex": total_gex
                })

            # 5. Metadata (Max Expiry per Group)
            group_max_dates = {
                "Weekly": None,
                "Monthly": None,
                "LongTerm": None
            }
            
            for row in all_gex_data:
                g = row['group']
                e_str = str(row['expiry'])
                if group_max_dates[g] is None or e_str > group_max_dates[g]:
                    group_max_dates[g] = e_str

            return {
                "ticker": ticker,
                "spot_price": spot,
                "net_gex": net_gex,
                "profile": profile,
                "group_dates": group_max_dates,
                "timestamp": datetime.now().isoformat()
            }

            return {
                "ticker": ticker,
                "spot_price": spot,
                "net_gex": net_gex,
                "profile": profile,
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
        if as_of.weekday() > 4: # Sat/Sun -> Next Friday
             # Actually "End of Week" usually implies "This trading week". 
             # If it's Saturday, the week is over. Let's aim for finding the *next* valid weekly expiry friday.
             # But simplistic: Just take next Friday if weekend.
             days_to_fri = (4 - as_of.weekday() + 7) % 7
        eow = as_of + timedelta(days=days_to_fri)

        # 2. EOM (Last day of month)
        # The first day of next month - 1 day
        next_month = as_of.replace(day=28) + timedelta(days=4)
        eom = next_month - timedelta(days=next_month.day)

        # 3. EOQ (End of current quarter: Mar, Jun, Sep, Dec)
        quarter_months = [3, 6, 9, 12]
        curr_month = as_of.month
        # Find next quarter end month
        q_month = next(m for m in quarter_months if m >= curr_month)
        # If we are in Dec, it returns 12. 
        # But if we are effectively AT the end of Dec?
        # Let's calculate last day of that month.
        # Logic: Get 1st of next month after q_month, minus 1 day.
        if q_month == 12:
            eoq = date(as_of.year, 12, 31)
        else:
            # First day of month avg+1
            tgt = date(as_of.year, q_month, 1) + timedelta(days=32)
            eoq = tgt.replace(day=1) - timedelta(days=1)
        
        # 4. Next 5
        next5 = as_of + timedelta(days=5)

        # 5. Next 30
        next30 = as_of + timedelta(days=30)
        
        # 6. Next 0 (0DTE - distinct logic? No, covered by others usually)

        return {
            "eow": eow,
            "eom": eom,
            "eoq": eoq,
            "next5": next5,
            "next30": next30
        }

    def calculate_gex_from_frame(self, ticker: str, df: pd.DataFrame, spot_price: float) -> Dict:
        """
        Calculates GEX using a pre-loaded DataFrame (from Massive Flat File).
        
        Args:
            ticker: Underlying Symbol
            df: DataFrame with columns [strike, type, expiration, oi, gamma, iv]
            spot_price: Current spot price of underlying
            
        Returns:
             Dict structure with multi-horizon profiles.
        """
        try:
            if df.empty:
                return {}
            
            # Determine Horizons
            today = date.today()
            horizons = self._get_horizon_targets(today)
            
            all_gex_data = []
            
            for _, row in df.iterrows():
                expiry_str = str(row['expiration']) # YYYY-MM-DD
                exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                
                T = self._get_time_to_expiration(expiry_str)
                
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
            # We want columns: strike, [h]_call, [h]_put, [h]_net for each h in horizons
            
            # 1. Initialize Profile Map
            # Use dictionary for O(1) access to strikes
            profile_map = {} 
            # Define keys we want
            horizon_keys = list(horizons.keys()) + ["total"]
            
            # Helper to init strike row
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
                
                # Add to all matched horizons
                for h in d['horizons']:
                    if otype == 'call':
                        profile_map[s][f"{h}_call_gex"] += gex
                    else:
                        profile_map[s][f"{h}_put_gex"] += gex
                    profile_map[s][f"{h}_net_gex"] += gex

            # Sort by strike
            sorted_strikes = sorted(profile_map.keys())
            profile = [profile_map[s] for s in sorted_strikes]

            # Metadata (Max Expiry per Group is just the target date essentially, 
            # except 'total' which is max of all data)
            group_dates = {k: v.strftime("%Y-%m-%d") for k, v in horizons.items()}
            
            # Find max overall for total? Or just leave it.
            # UI uses group_dates["Weekly"] etc. We will now return group_dates["eow"], etc.
            
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
