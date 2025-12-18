import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from mie_lib.analytics.hmm.hmm_engine import build_hmm_standardized_for_ticker, _load_features_for_hmm
from mie_lib.utils.paths import HMM_DIR, RAW_DIR
# --- NEW IMPORT ---
from mie_lib.utils.io import atomic_write_parquet
# --- END NEW IMPORT ---

# Configure Logging
logger = logging.getLogger(__name__)

class HMMBacktester:
    def __init__(self, ticker: str):
        self.ticker = ticker
        # Define Grid
        self.grid = []
        for n_states in [2, 3]:
            for window in [1, 5, 10, 15, 20, 25, 50, 'Max']:
                self.grid.append({"n_states": n_states, "train_window_years": window})
        self.results = []
        self.curves = {} # Key: "{n_states}_{window}"
        
    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculates Maximum Drawdown of an equity curve."""
        peak = equity_curve.cummax()
        drawdown = (equity_curve - peak) / peak
        return drawdown.min()
        
    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """Annualized Sharpe Ratio (assuming 252 days)."""
        if returns.std() == 0:
            return 0.0
        return (returns.mean() * 252) / (returns.std() * np.sqrt(252))

    def evaluate_strategy(self, states_df: pd.DataFrame, price_df: pd.DataFrame, n_states: int, window: Any) -> Dict[str, Any]:
        """
        Simulates:
        - Long if Bull
        - Cash if Bear/Neutral (0% return for simplicity, or Risk Free Rate)
        
        Also generates and saves the Signals Parquet.
        """
        # Merge on Date
        # Ensure dates are localized/delocalized consistently
        if states_df['date'].dt.tz is not None:
            states_df['date'] = states_df['date'].dt.tz_localize(None)
        if price_df['date'].dt.tz is not None:
            price_df['date'] = price_df['date'].dt.tz_localize(None)
            
        merged = pd.merge(price_df, states_df, on='date', how='inner').sort_values('date')
        
        if merged.empty:
            return {}
            
        # Strategy Logic
        # If 'hmm_state_name' == 'Bull', we are invested for the NEXT day.
        # So we shift the signal by 1.
        merged['signal'] = (merged['hmm_state_name'] == 'Bull').astype(int)
        
        # Strategy Return = Signal(t-1) * Return(t)
        # Shift signal to align: Signal calculated at Close T applies to Return T+1
        merged['strategy_ret'] = merged['signal'].shift(1) * merged['ret_1d']
        merged['bh_ret'] = merged['ret_1d']
        
        # Filter NaNs from shift
        valid = merged.dropna()
        
        if valid.empty:
            return {}

        # Metrics
        strat_sharpe = self._calculate_sharpe(valid['strategy_ret'])
        bh_sharpe = self._calculate_sharpe(valid['bh_ret'])
        
        strat_cum = (1 + valid['strategy_ret']).cumprod()
        bh_cum = (1 + valid['bh_ret']).cumprod()
        
        strat_dd = self._calculate_max_drawdown(strat_cum)
        bh_dd = self._calculate_max_drawdown(bh_cum)
        
        strat_total_ret = strat_cum.iloc[-1] - 1
        bh_total_ret = bh_cum.iloc[-1] - 1
        
        # Prepare Equity Curve Data (Normalized to 1.0 start)
        # We need dates as strings for JSON
        curve_data = []
        # Downsample if too large? 10 years * 252 = 2500 points. Fine for modern browser.
        for dt, s_val, b_val in zip(valid['date'], strat_cum, bh_cum):
            curve_data.append({
                "date": dt.strftime('%Y-%m-%d'),
                "strategy": float(s_val),
                "benchmark": float(b_val)
            })
            
        # --- NEW: Signals Generation & Saving ---
        # A signal is defined as a CHANGE in the 'signal' column (allocation).
        # We want to capture the Date, the Type (Buy/Sell), and the Price.
        
        # 'signal' column is 1 (Long) or 0 (Cash).
        # Shift back to align with the Decision Day (Close). 
        # The 'signal' above was shifted(1) for returns. Let's look at the raw allocation decision.
        # Allocation[t] corresponds to state at time t.
        merged['allocation'] = (merged['hmm_state_name'] == 'Bull').astype(int)
        merged['prev_alloc'] = merged['allocation'].shift(1)
        
        # Fill NaNs for first row
        merged['prev_alloc'] = merged['prev_alloc'].fillna(merged['allocation'])
        
        # Identify changes
        signal_changes = merged[merged['allocation'] != merged['prev_alloc']].copy()
        
        # Construct Signals DataFrame
        signals_list = []
        
        if not merged.empty:
             first_row = merged.iloc[0]
             if first_row['allocation'] == 1:
                 # Initial Buy
                 signals_list.append({
                     "date": first_row['date'],
                     "signal_type": "BUY",
                     "price": first_row['close'],
                     "hmm_state": first_row['hmm_state_name'],
                     "description": "Initial Entry"
                 })

        for idx, row in signal_changes.iterrows():
            sig_type = "BUY" if row['allocation'] == 1 else "SELL"
            signals_list.append({
                "date": row['date'],
                "signal_type": sig_type,
                "price": row['close'],
                "hmm_state": row['hmm_state_name'],
                "description": f"Regime changed to {row['hmm_state_name']}"
            })
            
        signals_df = pd.DataFrame(signals_list)
        
        # Save to Parquet
        signals_dir = HMM_DIR / self.ticker / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)
        signals_path = signals_dir / f"signals_{n_states}_{window}.parquet"
        
        if not signals_df.empty:
             atomic_write_parquet(signals_df, signals_path)
             
        # Determine Latest Signal for Summary
        latest_signal = {}
        if not signals_df.empty:
            last = signals_df.iloc[-1]
            latest_signal = {
                "last_signal_date": last['date'].strftime('%Y-%m-%d'),
                "last_signal_type": last['signal_type'],
                "last_signal_price": float(last['price'])
            }
        else:
             if not merged.empty:
                 curr = merged.iloc[-1]
                 latest_signal = {
                     "last_signal_date": curr['date'].strftime('%Y-%m-%d'),
                     "last_signal_type": "BUY" if curr['allocation'] == 1 else "SELL",
                     "last_signal_price": float(curr['close'])
                 }
        
        return {
            "scalar": {
                "strat_sharpe": strat_sharpe,
                "bh_sharpe": bh_sharpe,
                "strat_dd": strat_dd,
                "bh_dd": bh_dd,
                "strat_total_ret": strat_total_ret,
                "bh_total_ret": bh_total_ret,
                "outperformance_sharpe": strat_sharpe - bh_sharpe,
                "dd_savings": strat_dd - bh_dd,
                **latest_signal
            },
            "curves": curve_data
        }

    def run_grid_search(self):
        logger.info(f"Starting HMM Grid Search for {self.ticker}...")
        
        # Load raw price data once
        price_df = _load_features_for_hmm(self.ticker)
        
        if "close" in price_df.columns:
            # Normalize column names just in case
            price_df = price_df.rename(columns=lambda x: x.lower())
        
        # Merge actual 'close' price from RAW_DIR if available AND missing
        # (Features often lack the 'close' column, having only returns)
        raw_path = RAW_DIR / f"{self.ticker}.parquet"
        if raw_path.exists() and "close" not in price_df.columns:
             try:
                 df_raw = pd.read_parquet(raw_path)
                 df_raw = df_raw.rename(columns=lambda x: x.lower())
                 
                 if "date" in df_raw.columns:
                     df_raw["date"] = pd.to_datetime(df_raw["date"]).dt.tz_localize(None)
                 if "close" in df_raw.columns:
                     # Merge left to keep features alignment
                     price_df = pd.merge(price_df, df_raw[["date", "close"]], on="date", how="left")
             except Exception as e:
                 logger.warning(f"Failed to load raw close price: {e}")
        
        results = []
        
        for params in self.grid:
            n_states = params['n_states']
            window = params['train_window_years']
            
            logger.info(f"Testing Config: States={n_states}, Window={window}")
            
            try:
                # Build Model (this saves parquets to disk)
                output_paths = build_hmm_standardized_for_ticker(
                    ticker=self.ticker,
                    n_states=n_states,
                    train_window_years=window
                )
                
                if output_paths.get('skipped'):
                    logger.info("Skipped (Cached). Loading existing...")
                
                # Load Results
                states_path = output_paths['states']
                states_df = pd.read_parquet(states_path)
                
                # Evaluate
                metrics = self.evaluate_strategy(states_df, price_df, n_states, window)
                
                if not metrics:
                    logger.warning("No metrics calcualted (empty merge?)")
                    continue
                    
                row = {
                    **params,
                    **metrics['scalar']
                }
                
                # Store curve with a decent key
                curve_key = f"{n_states}_{window}"
                self.curves[curve_key] = metrics['curves']
                
                results.append(row)
                
            except Exception as e:
                logger.error(f"Failed config {params}: {e}")
                
        self.results = pd.DataFrame(results)
        self.save_results()
        
        if self.results.empty:
            return pd.DataFrame() # Return empty DF instead of crashing
            
        return self.results.sort_values('strat_sharpe', ascending=False)

    def save_results(self):
        """Saves backtest results to JSON for API consumption."""
        import json
        from mie_lib.utils.paths import DATA_DIR
        
        out_file = DATA_DIR / "analytics" / "hmm" / f"backtest_results_{self.ticker}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        payload = {
            "ticker": self.ticker,
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "summary": self.results.to_dict(orient="records"),
            "curves": self.curves
        }
        
        with open(out_file, "w") as f:
            json.dump(payload, f, indent=2)
            
        logger.info(f"Saved HMM backtest results to {out_file}")

    def print_leaderboard(self):
        if self.results.empty:
            print("No results generated.")
            return

        print(f"\n=== HMM Optimization Leaderboard ({self.ticker}) ===")
        print(f"{'States':<8} {'Window':<8} | {'Sharpe':<8} {'BH Sharpe':<10} | {'MaxDD':<8} {'BH DD':<8} | {'TotRet':<8}")
        print("-" * 80)
        
        df = self.results.sort_values('strat_sharpe', ascending=False)
        
        for _, row in df.iterrows():
            win = str(row['train_window_years'])
            print(f"{row['n_states']:<8} {win:<8} | {row['strat_sharpe']:<8.2f} {row['bh_sharpe']:<10.2f} | {row['strat_dd']:<8.1%} {row['bh_dd']:<8.1%} | {row['strat_total_ret']:<8.1%}")
            
        print("====================================================")
        
        best = df.iloc[0]
        print(f"\nWinner: {best['n_states']} States, {best['train_window_years']} Years")
        print(f"Improvement: +{best['outperformance_sharpe']:.2f} Sharpe, {best['dd_savings']*100:+.1f}% Drawdown Savings")
