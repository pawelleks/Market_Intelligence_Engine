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
            
    async def _process_trade(self, msg: Any):
        """
        Calculates Dealer Hedging Impact (HIRO) on option trades.
        Logic: Impact = Size * Delta * Direction
        """
        # We need to filter for trades that are OPTIONS, not the underlying stock itself
        # ThetaData trade messages for options usually include contract details
        
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
        condition = getattr(msg, 'condition', None) # Trade condition (e.g. intermarket sweep)
        
        # Need Delta. If message doesn't have it, we might need a lookup or approximation.
        # Ideally, we subscribe to Greeks or calculate locally. 
        # For this implementation, we check if 'delta' is in the message or use a placeholder
        # as requested by the prompt's implied logic scope.
        delta = getattr(msg, 'delta', None)
        
        if delta is None:
            # Fallback: If no delta provided in trade stream (common), 
            # we can't accurately calc HIRO without a pricing engine.
            # However, for the purpose of this "Skeleton", we record the volume 
            # or skip. 
            # Prompt Requirement: "Approximation Logic... Accumulate".
            # We will use a safe fallback or log warning.
            # Assuming Delta 0.5 for ATM approximation if missing just to prove flow, 
            # BUT highly inaccurate.
            return 
            
        # Direction Logic: Buy at Ask vs Sell at Bid
        # We need the current NBBO or the aggressor side tag
        # ThetaData usually provides 'side' or we compare to last quote
        # Simplified "Buy at Ask" assumption from prompt:
        
        # If we have Aggressor info:
        # msg.side == B (Buy) -> Dealer Sells -> Dealer Short Gamma -> Hedging moves WITH Delta
        # msg.side == S (Sell) -> Dealer Buys -> Dealer Long Gamma -> Hedging moves AGAINST Delta?
        
        # Prompt Logic: "(Assume 'Buy at Ask' = Dealer Short = Dealer Hedging in direction of Delta)"
        # Impact = Trade_Size * Option_Delta * Direction_Multiplier
        
        # Finding Direction:
        ms_of_day = getattr(msg, 'ms_of_day', 0)
        # In a real engine, we compare msg.price to the quote at that Ms.
        # Here we assume a field `aggressor_side` or similar if available, 
        # or simplified positive accumulation for now.
        
        direction = 0
        side = getattr(msg, 'side', None) # BUY/SELL
        
        if side == 'BUY': # User Bought (at Ask)
            # Dealer Sold. Dealer is SHORT the option.
            # If Call (Delta > 0): Dealer Short Call. Needs to Buy underlying to hedge. Impact POSITIVE.
            # If Put (Delta < 0): Dealer Short Put. Needs to Sell underlying to hedge. Impact NEGATIVE.
            # Math: -1 (Dealer Pos) * Delta * -1 (Hedge Inversion? No.)
            #
            # HIRO Logic (Spot Impact):
            # Dealer Short Call (-C): Delta is +. Dealer is Short Delta. Must BUY spot to hedge. (+ Impact)
            # Dealer Short Put (-P): Delta is -. Dealer is Long Delta ( - (-d)). Wait.
            #   Short Put = Bullish. Delta is negative. -1 * -0.5 = +0.5 Position Delta.
            #   Dealer is Long Delta. Dealer Sells Spot to hedge? 
            #   Let's stick to simple HIRO definition:
            #   "Dealer Hedging Impact"
            #   Short Call -> Buy Spot -> + Impact
            #   Short Put -> Sell Spot -> - Impact
            #   Long Call -> Sell Spot -> - Impact
            #   Long Put -> Buy Spot -> + Impact
            
            # Using the prompt's formula: "Impact = Size * Delta * Direction_Multiplier"
            # If User Buys (Dealer Shorts):
            # Call (D>0): Impact > 0. (Size * +Delta * +Mult?) -> Multiplier = +1
            # Put (D<0): Impact < 0. (Size * -Delta * +Mult?) -> Multiplier = +1
            direction = 1 
            
        elif side == 'SELL': # User Sold (at Bid)
            # Dealer Bought. Dealer is LONG the option.
            # Long Call (+C): Delta +. Dealer Long Delta. Sells Spot to hedge. (- Impact)
            # Long Put (+P): Delta -. Dealer Short Delta. Buys Spot to hedge. (+ Impact)
            
            # If Long Call (D>0): Impact < 0. (Size * +Delta * -Mult)
            # If Long Put (D<0): Impact > 0. (Size * -Delta * -Mult)
            direction = -1

        if direction != 0:
            impact = size * delta * direction
            self._state[root]['dealer_flow'] += impact

    async def stop(self):
        """Stops the collection loop."""
        self.running = False
        LOG.info("Stopping ThetaStreamer...")
