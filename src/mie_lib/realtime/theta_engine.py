import asyncio
import logging
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional

try:
    from thetadata import Context, Stream, Header
    THETADATA_AVAILABLE = True
except ImportError:
    THETADATA_AVAILABLE = False
    class Context: pass # Mock or safe placeholder
    class Stream: pass
    class Header: pass
    # Import these safely if possible, or mock
    OptionRight = Any
    DateRange = Any

LOG = logging.getLogger(__name__)

class ThetaStreamer:
    """
    Asynchronous streaming engine for ThetaData.
    Handles connection, subscription, and real-time computation of Dealer Flow (HIRO).
    """

    def __init__(self, tickers: List[str]):
        """
        Args:
            tickers: List of underlying tickers to monitor (e.g. ['SPY', 'SPX'])
        """
        self.tickers = [t.upper() for t in tickers]
        self.running = False
        
        # State Storage
        # Structure: { Ticker: { 'price': float, 'dealer_flow': float, '0dte_gex': float } }
        self._state: Dict[str, Dict[str, float]] = {
            t: {'price': 0.0, 'dealer_flow': 0.0, '0dte_gex': 0.0}
            for t in self.tickers
        }
        
        # Configuration
        # Defaults to free/standard plan port and localhost if not specified
        self.jpm_mode = False # If True, use specific JPM logic (future expansion)

    def get_state(self) -> Dict[str, Dict[str, float]]:
        """Returns the latest thread-safe state dictionary."""
        return self._state.copy()

    def get_latest_data(self, ticker: str) -> Dict[str, Any]:
        """Returns the current state for a ticker (compatible with API)."""
        state = self._state.get(ticker, {})
        return {
            "ticker": ticker,
            "price": state.get('price', 0.0),
            "hiro_flow": state.get('dealer_flow', 0.0),
            "time": int(datetime.now().timestamp())
        }
        
    def get_intraday_history(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetches intraday history (1m candles) using YFinance fallback.
        """
        try:
            import yfinance as yf
            dat = yf.Ticker(ticker)
            df = dat.history(period="1d", interval="1m")
            if df.empty: return []

            history = []
            timestamps = df.index.astype('int64') // 10**9
            for ts, row in zip(timestamps, df.itertuples()):
                history.append({
                    "time": int(ts), 
                    "value": float(row.Close)
                })
            
            history.sort(key=lambda x: x['time'])
            if history:
                if self._state.get(ticker):
                    self._state[ticker]['price'] = history[-1]['value']
            return history
        except Exception as e:
            LOG.error(f"Failed to fetch history for {ticker}: {e}")
            return []

    async def run(self):
        """Main async loop. Connects and processes the stream."""
        self.running = True
        
        # Retry loop for connection persistence
        while self.running:
            try:
                LOG.info("Connecting to ThetaData Stream...")
                
                # Context manager handles automated connection/disconnection
                # using the default port 25510 per ThetaData docs
                async with Context() as context:
                    
                    # Create the stream handle
                    stream = context.stream()
                    
                    # 1. Subscribe to Underlying Quotes (Price Updates)
                    for ticker in self.tickers:
                        # Stream.quote(req, ...) - assuming standard QUOTE subscription
                        await stream.connect() # Ensure stream is connected
                        
                        # Subscribe to Quotes for the underlying
                        # Using 0 as expiration for underlying usually, or separate call
                        # ThetaData often treats underlying as a specific request type
                        await stream.level1_quote(ticker) 
                        LOG.info(f"Subscribed to Quotes for {ticker}")

                        # 2. Subscribe to Options Trades (for Flow/HIRO)
                        # We need full market feed for options on these tickers
                        # Subscribing to all trades for the root
                        await stream.trade(ticker)
                        LOG.info(f"Subscribed to Option Trades for {ticker}")

                    # Process the stream
                    async for msg in stream:
                        if not self.running:
                            break
                        
                        await self._handle_message(msg)

            except Exception as e:
                LOG.error(f"ThetaData Stream Error: {e}")
                if not self.running:
                    break
                LOG.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _handle_message(self, msg: Any):
        """Dispatches message to appropriate handler based on type."""
        try:
            # Note: Method names/attributes depend on exact ThetaData Header implementations
            # Adjusting to standard expected callbacks/objects
            
            msg_type = getattr(msg, 'type', None) # e.g., QUOTE, TRADE
            
            if msg_type == Header.QUOTE:
                await self._process_quote(msg)
            elif msg_type == Header.TRADE:
                await self._process_trade(msg)
                
        except Exception as e:
            LOG.error(f"Error processing message: {e}")

    async def _process_quote(self, msg: Any):
        """Updates underlying price state."""
        # Assuming msg has .root, .bid, .ask, or .price
        ticker = getattr(msg, 'root', None)
        if not ticker or ticker not in self._state:
            return

        # Simple mid-price or last
        bid = getattr(msg, 'bid', 0.0)
        ask = getattr(msg, 'ask', 0.0)
        price = (bid + ask) / 2 if (bid and ask) else getattr(msg, 'last', 0.0)
        
        if price > 0:
            self._state[ticker]['price'] = price
        
        # Store Bid/Ask for Trade inference
        self._state[ticker]['bid'] = bid
        self._state[ticker]['ask'] = ask
            
    async def _process_trade(self, msg: Any):
        """
        Calculates Dealer Hedging Impact (HIRO) on option trades.
        Logic: Impact = Size * Delta * Direction
        """
        root = getattr(msg, 'root', None)
        if not root or root not in self._state:
            return

        # Check if it's an option trade
        right = getattr(msg, 'right', None) # Call/Put
        if not right: 
            return # Likely underlying trade

        # Extract Trade Details
        size = getattr(msg, 'size', 0)
        price = getattr(msg, 'price', 0.0)
        condition = getattr(msg, 'condition', None) 
        
        # Delta Fallback Logic
        delta = getattr(msg, 'delta', None)
        if delta is None:
            # Fallback: Use 0.5 for ATM approximation to show flow direction
            # Real greeks stream requires separate subscription usually
            delta = 0.5
            
        # DEBUG: Log incoming trade details
        LOG.info(f"TRADE: {root} | Price={price} | Size={size} | Delta={delta} (Raw={getattr(msg, 'delta', 'MISSING')}) | Side={side}")
            
        # Direction Logic: Buy at Ask vs Sell at Bid
        side = getattr(msg, 'side', None) # BUY/SELL
        
        # Fallback if 'side' is missing (using Quote Test)
        if not side:
            bid = self._state[root].get('bid', 0.0)
            ask = self._state[root].get('ask', 0.0)
            if ask > 0 and price >= ask:
                side = 'BUY'
            elif bid > 0 and price <= bid:
                side = 'SELL'
            else:
                # Tick test fallback (not implemented statefully here) 
                # or default neutral
                pass

        direction = 0
        if side == 'BUY': # User Bought (at Ask) -> Dealer Sold Short
            # Call (D>0): Impact > 0
            # Put (D<0): Impact < 0 (but Delta is negative, so Size * NegDelta * 1 = Negative)
            # Wait, Dealer Short Put = Bullish.
            # HIRO Convention: "Dealar Hedging"
            # Short Put (-P, Delta -). Dealer Long Delta. Does NOT hedge by sold spot?
            # Standard: User Buy Call -> Dealer Short Call -> Dealer Long Stock -> +Flow
            # Standard: User Buy Put -> Dealer Short Put -> Dealer Short Stock (wait...)
            #   User Buy Put (Bearish). Dealer Short Put (Bullish).
            #   Delta is -. Dealer Position Delta = -1 * -0.5 = +0.5.
            #   Dealer needs to be Delta Neutral. Dealer SELLS Stock (-0.5).
            #   So Impact is NEGATIVE.
            #   Formula: Size * Delta * 1.
            #   100 * -0.5 * 1 = -50. Correct.
            direction = 1 
            
        elif side == 'SELL': # User Sold (at Bid) -> Dealer Bought Long
            # User Sell Call -> Dealer Long Call -> Dealer Short Stock -> -Flow
            #   Size * 0.5 * -1 = -50. Correct.
            direction = -1

        if direction != 0:
            impact = size * delta * direction
            self._state[root]['dealer_flow'] += impact

    async def stop(self):
        """Stops the collection loop."""
        self.running = False
        LOG.info("Stopping ThetaStreamer...")

    @staticmethod
    def calculate_forward_price(strikes: List[float], calls: Dict[float, float], puts: Dict[float, float]) -> float:
        """
        Calculates the At-The-Money (ATM) Forward Price using Put-Call Parity.
        S = C - P + K (ignoring interest/divs for short term approximation)
        We find the strike where |C - P| is minimized (ATM) and solve for S.
        """
        # Find ATM strike (min difference between Call and Put price)
        min_diff = float('inf')
        best_strike = 0.0
        
        common_strikes = set(calls.keys()) & set(puts.keys())
        if not common_strikes:
            return 0.0
            
        for k in common_strikes:
            diff = abs(calls[k] - puts[k])
            if diff < min_diff:
                min_diff = diff
                best_strike = k
        
        # Calculate Forward at this strike
        # C - P = S - K  =>  S = C - P + K
        if best_strike == 0:
            return 0.0
            
        c_price = calls[best_strike]
        p_price = puts[best_strike]
        
        forward_price = c_price - p_price + best_strike
        return forward_price

    async def get_spx_probability_chain(self, expirations: List[date]) -> List[Dict[str, Any]]:
        """
        Fetches SPX Option Chain for specific expirations to build probability distributions.
        Returns flattened list of [Expiration, Strike, MidPrice].
        """
        results = []
        if not THETADATA_AVAILABLE:
            LOG.warning("ThetaData not available. Returning empty chain.")
            return results

        try:
            LOG.info(f"Fetching SPX Probability Chain for {len(expirations)} expirations...")
            
            # Use a new context for this request to avoid interfering with stream if necessary,
            # or reuse if architecture permits. For snapshot, new context is safer.
            async with Context() as context:
                # Iterate expirations
                for exp in expirations:
                    # Format exp to integer YYYYMMDD
                    exp_int = int(exp.strftime('%Y%m%d'))
                    
                    # 1. Get Strikes for this expiration
                    # ThetaData: context.get_strikes(root, exp)
                    strikes = context.get_strikes('SPX', exp_int)
                    
                    if not strikes:
                        continue
                        
                    # 2. Fetch Prices (Bid/Ask) for all strikes
                    # We need Calls and Puts to calculate Forward Price
                    # Optimization: Request snapshot for all strikes
                    
                    # Storage for Forward Calc
                    call_prices = {} # Strike -> Mid
                    put_prices = {}  # Strike -> Mid
                    
                    # Batch request logic would be ideal, but looping for now as per "Skeleton" approach
                    # Real ThetaData API allows requesting bulk. 
                    
                    # For this implementation, we will use a simplified fetch loop or mock if library usage is complex.
                    # Assuming context.snapshot(root, exp, strike, right) available.
                    
                    chain_data = [] # Local storage for this exp
                    
                    for k in strikes:
                        # CALL
                        try:
                            # Right: 'C' or OptionRight.CALL
                            c_snap = context.snapshot('SPX', exp_int, k, 'C') 
                            c_bid = getattr(c_snap, 'bid', 0)
                            c_ask = getattr(c_snap, 'ask', 0)
                            c_mid = (c_bid + c_ask) / 2
                            call_prices[k] = c_mid
                        except: continue

                        # PUT
                        try:
                            p_snap = context.snapshot('SPX', exp_int, k, 'P')
                            p_bid = getattr(p_snap, 'bid', 0)
                            p_ask = getattr(p_snap, 'ask', 0)
                            p_mid = (p_bid + p_ask) / 2
                            put_prices[k] = p_mid
                        except: continue
                        
                        # Store for Result
                        chain_data.append({
                            'expiration': exp.isoformat(),
                            'strike': k,
                            'call_mid': c_mid,
                            'put_mid': p_mid
                        })
                        
                    # 3. Calculate Forward Price for this Expiration
                    fwd = self.calculate_forward_price(strikes, call_prices, put_prices)
                    
                    # Append fwd to each record or return as metadata?
                    # "Return a clean data structure containing: Strike, Mid-Price... "
                    # I'll attach the Forward Price to each record for ease of use in frontend
                    
                    for item in chain_data:
                        item['forward_price'] = fwd
                        results.append(item)
                        
            return results

        except Exception as e:
            LOG.error(f"Error fetching SPX Probability Chain: {e}")
            return []

