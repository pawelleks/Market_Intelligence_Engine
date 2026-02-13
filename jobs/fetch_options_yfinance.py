"""
Fetch SPX option chain from yfinance for comparison with ThetaData.
Saves to parquet with same schema for processing through the probability pipeline.
"""
import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

OUTPUT_DIR = Path('/app/data/options_yfinance')
SYMBOL = '^SPX'  # Yahoo Finance uses ^SPX for S&P 500 Index

def fetch_spx_options():
    """Fetch SPX option chain from yfinance."""
    LOG.info(f"Fetching {SYMBOL} options from yfinance...")
    
    try:
        ticker = yf.Ticker(SYMBOL)
        
        # Get current price
        info = ticker.info
        spot = info.get('regularMarketPrice') or info.get('currentPrice')
        LOG.info(f"   > Spot price: ${spot:,.2f}")
        
        # Get all expiration dates
        expirations = ticker.options
        if not expirations:
            LOG.error("No option expirations available")
            return
        
        LOG.info(f"   > Found {len(expirations)} expirations")
        
        all_chains = []
        snapshot_time = datetime.now()
        
        for exp_date in expirations[:20]:  # Limit to first 20 expirations (~60 days)
            LOG.info(f"   > Fetching {exp_date}...")
            
            try:
                opt_chain = ticker.option_chain(exp_date)
                calls = opt_chain.calls
                
                # Convert to ThetaData-like format
                calls['expiry'] = exp_date
                calls['timestamp'] = snapshot_time
                calls['contractSymbol'] = calls['contractSymbol'].astype(str)
                
                # Rename columns to match ThetaData schema
                calls = calls.rename(columns={
                    'lastPrice': 'last',
                    'bid': 'bid',
                    'ask': 'ask',
                    'strike': 'strike',
                    'volume': 'volume',
                    'openInterest': 'open_interest',
                    'impliedVolatility': 'iv'
                })
                
                # Select relevant columns
                cols = ['timestamp', 'expiry', 'strike', 'bid', 'ask', 'last', 
                       'volume', 'open_interest', 'iv', 'contractSymbol']
                calls = calls[[c for c in cols if c in calls.columns]]
                
                all_chains.append(calls)
                
            except Exception as e:
                LOG.warning(f"   > Failed to fetch {exp_date}: {e}")
                continue
        
        if not all_chains:
            LOG.error("No option data retrieved")
            return
        
        # Combine all chains
        df = pd.concat(all_chains, ignore_index=True)
        
        # Filter out zero bids/asks
        df = df[(df['bid'] > 0) | (df['ask'] > 0)]
        
        # Sort
        df = df.sort_values(['expiry', 'strike']).reset_index(drop=True)
        
        # Save
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / 'SPX_options.parquet'
        df.to_parquet(output_path, index=False)
        
        LOG.info(f"✓ Saved {len(df)} option contracts to {output_path}")
        LOG.info(f"   > Expirations: {df['expiry'].nunique()}")
        LOG.info(f"   > Strike range: ${df['strike'].min():.0f} - ${df['strike'].max():.0f}")
        
        return df
        
    except Exception as e:
        LOG.error(f"Failed to fetch yfinance data: {e}", exc_info=True)
        return None


if __name__ == '__main__':
    fetch_spx_options()
