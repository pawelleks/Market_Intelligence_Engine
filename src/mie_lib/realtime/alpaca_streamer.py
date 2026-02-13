"""
Alpaca Markets WebSocket Streamer for Real-Time IEX Quotes

Mode: REAL-TIME
Data Source: Alpaca Markets IEX feed (free tier)
Tickers: SPY, QQQ, IWM (ETFs)
Response Time: <100ms (WebSocket push)

This module provides real-time stock quotes using Alpaca Markets' free IEX feed.
It follows the same pattern as ThetaStreamer for consistency.
"""

import os
import asyncio
import logging
import json
import traceback
from datetime import datetime
from typing import List, Optional, Dict
from collections import defaultdict

try:
    import websockets
except ImportError:
    websockets = None

LOG = logging.getLogger(__name__)


class AlpacaStreamer:
    """
    Manages real-time stock quote streaming from Alpaca Markets IEX feed.
    
    **Free Tier Limits**:
    - 200 quotes/second
    - IEX exchange only (not consolidated)
    - Stocks and ETFs only (no options, no indices)
    
    **Supported Tickers**: SPY, QQQ, IWM (ETFs with high liquidity)
    """
    
    def __init__(self, tickers: List[str]):
        self.tickers = [t.upper() for t in tickers]
        self.active = False
        self.listeners = []  # List of queues to broadcast to
        self.state = {}  # Aggregated State: ticker -> {price, last_update_ms, source}
        
        # Alpaca Configuration
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.api_secret = os.getenv("ALPACA_API_SECRET", "")
        self.use_paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        
        # WebSocket URLs
        if self.use_paper:
            self.ws_url = "wss://stream.data.alpaca.markets/v2/iex"
        else:
            self.ws_url = "wss://stream.data.alpaca.markets/v2/iex"  # Same for live
        
        # Connection state
        self.websocket = None
        self.loop = None
        self._reconnect_delay = 1  # Exponential backoff starting value

    async def start(self):
        """
        Initializes the WebSocket connection and starts streaming.
        """
        if self.active:
            LOG.warning("AlpacaStreamer already active.")
            return

        if not self.api_key or not self.api_secret:
            LOG.error("Alpaca API credentials not found in environment. Skipping AlpacaStreamer.")
            return

        self.loop = asyncio.get_running_loop()
        LOG.info(f"Starting Alpaca IEX Streamer (Tickers: {', '.join(self.tickers)})...")
        self.active = True
        
        # Start connection task
        asyncio.create_task(self._connect_and_stream())

    async def stop(self):
        """
        Stops the streamer and closes WebSocket connection.
        """
        LOG.info("Stopping Alpaca Streamer...")
        self.active = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                LOG.warning(f"Error closing Alpaca WebSocket: {e}")
        self.websocket = None

    async def _connect_and_stream(self):
        """
        Establishes WebSocket connection with auto-reconnect logic.
        """
        while self.active:
            try:
                LOG.info(f"Connecting to Alpaca IEX WebSocket: {self.ws_url}")
                
                async with websockets.connect(self.ws_url) as ws:
                    self.websocket = ws
                    self._reconnect_delay = 1  # Reset backoff on successful connection
                    
                    # Step 1: Authenticate
                    await self._authenticate(ws)
                    
                    # Step 2: Subscribe to trades
                    await self._subscribe(ws)
                    
                    # Step 3: Listen for messages
                    await self._listen(ws)
                    
            except Exception as e:
                LOG.error(f"Alpaca WebSocket error: {e}")
                LOG.error(traceback.format_exc())
                
                if not self.active:
                    break
                
                # Exponential backoff (max 60 seconds)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
                LOG.info(f"Reconnecting in {self._reconnect_delay} seconds...")
                await asyncio.sleep(self._reconnect_delay)

    async def _authenticate(self, ws):
        """
        Sends authentication message to Alpaca WebSocket.
        
        Auth format:
        {
            "action": "auth",
            "key": "YOUR_API_KEY",
            "secret": "YOUR_API_SECRET"
        }
        """
        auth_msg = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.api_secret
        }
        
        LOG.info("Sending Alpaca authentication...")
        await ws.send(json.dumps(auth_msg))
        
        # Wait for auth response
        # Alpaca sends TWO messages: first "connected", then "authenticated"
        authenticated = False
        for _ in range(3):  # Try up to 3 messages
            response = await ws.recv()
            data = json.loads(response)
            
            if isinstance(data, list):
                for msg in data:
                    msg_type = msg.get("T")
                    msg_text = msg.get("msg", "")
                    
                    # Accept either "connected" or "authenticated" as success
                    if msg_type == "success" and msg_text in ("connected", "authenticated"):
                        LOG.info(f"✅ Alpaca {msg_text}")
                        authenticated = True
                    elif msg_type == "error":
                        raise Exception(f"Alpaca auth failed: {msg_text}")
            
            if authenticated:
                return
        
        raise Exception(f"Unexpected auth response: {data}")

    async def _subscribe(self, ws):
        """
        Subscribes to trade updates for configured tickers.
        
        Subscribe format:
        {
            "action": "subscribe",
            "trades": ["SPY", "QQQ", "IWM"]
        }
        """
        sub_msg = {
            "action": "subscribe",
            "trades": self.tickers
        }
        
        LOG.info(f"Subscribing to Alpaca IEX trades: {', '.join(self.tickers)}")
        await ws.send(json.dumps(sub_msg))
        
        # Wait for subscription confirmation
        response = await ws.recv()
        data = json.loads(response)
        
        if isinstance(data, list):
            for msg in data:
                if msg.get("T") == "subscription":
                    LOG.info(f"✅ Subscribed to: {msg.get('trades', [])}")

    async def _listen(self, ws):
        """
        Listens for incoming trade messages and updates state.
        
        Trade message format:
        {
            "T": "t",           # Message type (t = trade)
            "S": "SPY",         # Symbol
            "i": 12345,         # Trade ID
            "x": "V",           # Exchange (V = IEX)
            "p": 475.23,        # Price
            "s": 100,           # Size
            "t": "2024-02-12T14:30:00.123Z",  # Timestamp
            "c": ["@"],         # Conditions
            "z": "C"            # Tape
        }
        """
        LOG.info("Listening for Alpaca IEX trade messages...")
        
        async for message in ws:
            try:
                data = json.loads(message)
                
                if not isinstance(data, list):
                    continue
                
                for msg in data:
                    msg_type = msg.get("T")
                    
                    # Handle trade messages
                    if msg_type == "t":
                        await self._process_trade(msg)
                    
                    # Handle subscription confirmations
                    elif msg_type == "subscription":
                        LOG.debug(f"Subscription update: {msg}")
                    
                    # Handle errors
                    elif msg_type == "error":
                        LOG.error(f"Alpaca error: {msg.get('msg')}")
                    
            except Exception as e:
                LOG.error(f"Error processing Alpaca message: {e}")
                LOG.debug(f"Raw message: {message}")

    async def _process_trade(self, msg: Dict):
        """
        Processes a trade message and updates internal state.
        
        Args:
            msg: Trade message from Alpaca IEX feed
        """
        ticker = msg.get("S")
        price = msg.get("p")
        size = msg.get("s", 0)
        timestamp_str = msg.get("t")
        exchange = msg.get("x", "IEX")
        
        if not ticker or not price:
            return
        
        # Filter: Only process our subscribed tickers
        if ticker not in self.tickers:
            return
        
        # Parse timestamp
        try:
            # Alpaca timestamp format: "2024-02-12T14:30:00.123456789Z"
            timestamp_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            timestamp_ms = int(timestamp_dt.timestamp() * 1000)
        except Exception:
            timestamp_ms = int(datetime.now().timestamp() * 1000)
        
        # Update state
        self._update_state(ticker, price, timestamp_ms)
        
        # Broadcast to listeners
        trade_data = {
            "type": "TRADE",
            "root": ticker,
            "price": price,
            "size": size,
            "exchange": exchange,
            "timestamp": timestamp_str,
            "timestamp_ms": timestamp_ms,
            "asset_type": "STOCK",
            "source": "alpaca_iex"
        }
        
        await self.broadcast(trade_data)
        
        # Log periodically (every 10th trade to avoid spam)
        if not hasattr(self, '_trade_counter'):
            self._trade_counter = {}
        self._trade_counter[ticker] = self._trade_counter.get(ticker, 0) + 1
        
        if self._trade_counter[ticker] % 10 == 0:
            LOG.debug(f"Alpaca IEX: {ticker} @ ${price:.2f} (trades: {self._trade_counter[ticker]})")

    def _update_state(self, ticker: str, price: float, timestamp_ms: int):
        """
        Updates internal state with latest price.
        
        Args:
            ticker: Stock symbol
            price: Latest trade price
            timestamp_ms: Timestamp in milliseconds
        """
        if ticker not in self.state:
            self.state[ticker] = {}
        
        self.state[ticker]["price"] = price
        self.state[ticker]["last_update_ms"] = timestamp_ms
        self.state[ticker]["source"] = "alpaca_iex"

    async def broadcast(self, msg: Dict):
        """
        Pushes message to all listener queues.
        
        Args:
            msg: Message dict to broadcast
        """
        for q in self.listeners:
            try:
                await q.put(msg)
            except Exception as e:
                LOG.debug(f"Failed to broadcast to listener: {e}")

    def get_latest_data(self, ticker: str) -> Dict[str, any]:
        """
        Returns the current aggregated state for a ticker.
        Used by polling endpoints.
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Dict with price, last_update_ms, and source
        """
        ticker = ticker.upper()
        if ticker not in self.state:
            return {"price": 0.0, "last_update_ms": 0, "source": "alpaca_iex"}
        return self.state[ticker]
