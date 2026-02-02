import asyncio
import logging
import json
import os
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
import websockets

LOG = logging.getLogger(__name__)

class ThetaStreamer:
    """
    Real-Time Dealer Flow Engine using Direct WebSockets to Theta Terminal.
    Bypasses 'thetadata' python library dependency.
    """

    def __init__(self, port: int = 25520):
        self.port = port
        self.host = os.getenv("THETA_HOST", "localhost")
        self.tickers: List[str] = []
        self.running = False
        
        # State
        self.cumulative_hiro: Dict[str, float] = {}   # {Ticker: Float}
        self.latest_price: Dict[str, float] = {}      # {Ticker: Float}
        self.latest_quotes: Dict[str, Dict] = {}      # {Ticker: {bid: float, ask: float}}
        
        # WebSocket URL (Theta Terminal usually listens on /v1/events for streams)
        self.ws_url = f"ws://{self.host}:{self.port}/v1/events"

    def get_latest_data(self, ticker: str) -> Dict[str, Any]:
        """Returns the current state for a ticker."""
        return {
            "ticker": ticker,
            "price": self.latest_price.get(ticker, 0.0),
            "hiro_flow": self.cumulative_hiro.get(ticker, 0.0),
            "time": int(datetime.now().timestamp())
        }
        
    def get_intraday_history(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetches intraday history (1m candles) using YFinance fallback.
        (Theta REST API handling could be added here later).
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
                self.latest_price[ticker] = history[-1]['value']
            return history
        except Exception as e:
            LOG.error(f"Failed to fetch history for {ticker}: {e}")
            return []

    async def start_stream(self, tickers: List[str] = ["SPY", "SPX"]):
        """Main loop: Connects, Subscribes, Listens."""
        self.tickers = [t.upper() for t in tickers]
        self.running = True
        
        # Initialize State
        for t in self.tickers:
            if t not in self.cumulative_hiro:
                self.cumulative_hiro[t] = 0.0
                self.latest_price[t] = 0.0
                self.latest_quotes[t] = {'bid': 0.0, 'ask': 0.0}

        LOG.info(f"Connecting to Theta Terminal WebSocket at {self.ws_url}...")

        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    LOG.info("WebSocket Connected!")
                    
                    # 1. Subscribe
                    for ticker in self.tickers:
                        # Subscribe to TRADES (Options)
                        sub_trade = {
                            "msg_type": "STREAM", 
                            "sec_type": "OPTION", 
                            "req_type": "TRADE", 
                            "root": ticker
                        }
                        await ws.send(json.dumps(sub_trade))
                        
                        # Subscribe to QUOTES (Underlying/Option? usually Underlying quote is different)
                        # We need Underlying Price. 
                        # Requesting ROOT quote might give underlying? 
                        # Or explicit "sec_type": "STOCK"? (SPY is stock, SPX is Index).
                        # Trying generic subscription for now based on user prompt.
                        sub_quote = {
                             "msg_type": "STREAM",
                             "sec_type": "STOCK", # Assuming ROOT is stock/index
                             "req_type": "QUOTE",
                             "root": ticker
                        }
                        await ws.send(json.dumps(sub_quote))
                        
                        LOG.info(f"Subscribed to {ticker}")

                    # 2. Heartbeat Task
                    heartbeat_task = asyncio.create_task(self._heartbeat(ws))
                    
                    # 3. Listen
                    try:
                        async for message in ws:
                            if not self.running: break
                            await self._handle_message(message)
                    finally:
                        heartbeat_task.cancel()
                        
            except Exception as e:
                LOG.error(f"WebSocket Error: {e}")
                LOG.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _heartbeat(self, ws):
        """Sends Keep-Alive ping every 5 seconds."""
        while True:
            try:
                # Some APIs expect specific text ping, others specific JSON.
                # Standard WS Ping frame is usually handled by lib, but App-Level ping might be needed.
                # User asked for "Keep-Alive" ping.
                await ws.ping()
                await asyncio.sleep(5)
            except Exception:
                break

    async def _handle_message(self, raw_msg: str):
        try:
            data = json.loads(raw_msg)
            
            # Identify message type via parsing keys (Theta JSON structure varies)
            # Typically has "type", "ms_of_day", "root", etc.
            
            # Check for Quote (Underlying Price)
            # Quote usually has "bid", "ask"
            if "bid" in data and "ask" in data:
                await self._on_quote_msg(data)
                return

            # Check for Trade
            if "size" in data and "price" in data:
                await self._on_trade_msg(data)
                return
                
        except Exception as e:
            # LOG.debug(f"Parse Error ({raw_msg}): {e}")
            pass

    async def _on_quote_msg(self, data: Dict):
        root = data.get("root")
        if not root or root not in self.tickers: return
        
        bid = float(data.get("bid", 0))
        ask = float(data.get("ask", 0))
        
        if bid > 0 and ask > 0:
            self.latest_quotes[root] = {'bid': bid, 'ask': ask}
            self.latest_price[root] = (bid + ask) / 2
        
        # Fallback 'last'
        last = float(data.get("last", 0))
        if last > 0:
             self.latest_price[root] = last

    async def _on_trade_msg(self, data: Dict):
        """Calculates HIRO from Option Trade."""
        # Ensure it's an Option Trade (has 'right' or 'expiry' usually, or from specific sub)
        # Assuming we only get Option trades from our OPTION sub.
        
        root = data.get("root")
        if not root or root not in self.tickers: return

        # Parse
        price = float(data.get("price", 0))
        size = int(data.get("size", 0))
        # Theta usually provides 'delta' in the stream if configured? 
        # Or we need to calculate it?
        # User prompt implicitly assumed 'delta' exists.
        # If 'delta' is missing, HIRO = 0.
        delta = float(data.get("delta", 0)) 
        
        # Condition codes (for unusual flow later)
        condition = data.get("condition")
        
        # Determine Agitator (Side)
        quotes = self.latest_quotes.get(root, {'bid': 0.0, 'ask': 0.0})
        bid = quotes['bid']
        ask = quotes['ask']
        
        agitator_side = 0
        if ask > 0 and price >= ask: agitator_side = 1 # BUY
        elif bid > 0 and price <= bid: agitator_side = -1 # SELL
        
        # Calculate Flow
        # Flow = Size * Delta * Agitator
        flow = size * delta * agitator_side * 1000 # Scaling factor?
        
        self.cumulative_hiro[root] = self.cumulative_hiro.get(root, 0.0) + flow

    async def stop(self):
        self.running = False
