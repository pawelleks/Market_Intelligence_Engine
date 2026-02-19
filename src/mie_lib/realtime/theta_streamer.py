import os
import asyncio
import logging
import json
import traceback
from datetime import datetime, date as dt_date
from typing import List, Optional, Dict
from collections import defaultdict, deque

# Official Library
try:
    from thetadata import ThetaClient, StreamMsg
except ImportError:
    # Critical dependency missing
    class ThetaClient: pass
    class StreamMsg: pass

# Enums (Handle strict import errors for partial versions)
try:
    from thetadata import StreamMsgType, OptionReqType, OptionRight, SecType
    # Fallback for older/newer versions of the library that use SecurityType
    try:
        from thetadata import SecurityType
    except ImportError:
        SecurityType = SecType
except ImportError:
    # Define dummy enums if missing or package is old
    class StreamMsgType:
        TRADE = "TRADE"
        QUOTE = "QUOTE"
        PING = "PING"
        STREAM_DEAD = "STREAM_DEAD"
    class OptionReqType:
        QUOTE = 101
        OHLC = 102
        TRADE = 103
    class OptionRight:
        CALL = "C"
        PUT = "P"
    class SecType:
        OPTION = "OPTION"
        STOCK = "STOCK"
        INDEX = "INDEX"
    SecurityType = SecType

LOG = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

from mie_lib.realtime.trade_processor import TradeProcessor

class ThetaStreamer:
    """
    Manages real-time data streaming from Theta Terminal using the OFFICIAL TCP Client.
    Replacing the custom WebSocket implementation to avoid protocol mismatch.
    """
    
    def __init__(self, tickers: List[str]):
        self.tickers = tickers
        self.active = False
        self._queue = asyncio.Queue()  # For internal processing if needed
        self.listeners = [] # List of queues to broadcast to
        self.state = {} # Aggregated State for Polling
        # Flow history: ticker -> deque of {time, price, flow}
        self.flow_history: Dict[str, deque] = {t: deque(maxlen=5000) for t in tickers}
        
        # Trade Processor (Aggregation & Tagging)
        self.processor = TradeProcessor(self._on_clean_trade)
        
        # NEW: Trade History and Day Stats for Option Flow Page
        self.recent_trades = deque(maxlen=1000)
        # ticker -> {call_vol, put_vol, call_prem, put_prem, net_flow}
        self.day_stats = defaultdict(lambda: {
            "call_vol": 0, "put_vol": 0, 
            "call_prem": 0.0, "put_prem": 0.0, 
            "net_flow": 0.0
        })
        
        # Determine Host (Docker vs Local)
        self.theta_host = os.getenv("THETA_HOST", "theta_terminal")
        self.theta_rest_port = int(os.getenv("THETA_REST_PORT", "25510"))
        self.theta_timeout = 60
        
        # TCP Client provided by thetadata library
        self.client: Optional[ThetaClient] = None
        self.streaming_thread = None
        self.loop = None

    async def _on_clean_trade(self, trade: Dict):
        """
        Callback from TradeProcessor when a trade is aggregated and tagged.
        """
        try:
            root = trade["root"]
            price = trade["price"]
            size = trade["size"]
            right = trade["right"]
            
            # 1. Update State (Net Flow)
            if root not in self.state:
                self.state[root] = {"price": 0.0, "net_flow": 0.0, "last_update_ms": 0}

            # Calculate Premium (Size * Price * 100)
            premium = price * size * 100
            
            # Update Flow & Day Stats
            if right == "C":
                self.state[root]["net_flow"] += premium
                self.day_stats[root]["call_vol"] += size
                self.day_stats[root]["call_prem"] += premium
            else:
                self.state[root]["net_flow"] -= premium
                self.day_stats[root]["put_vol"] += size
                self.day_stats[root]["put_prem"] += premium
                
            self.day_stats[root]["net_flow"] = self.state[root]["net_flow"]
            
            # Enrich Trade Object with latest Flow & Spot
            trade["val"] = premium
            trade["value"] = premium
            trade["hiro_flow"] = self.state[root]["net_flow"]
            trade["asset_type"] = "OPTION"
            
            # 2. History
            self.recent_trades.append(trade)
            if root in self.flow_history:
                self.flow_history[root].append({
                    "time": int(datetime.now().timestamp()), # Seconds for chart
                    "price": self.state[root].get("price", 0.0), # Use underlying price
                    "flow": self.state[root]["net_flow"]
                })
                
            # 3. Broadcast
            for q in self.listeners:
                if not q.full():
                    q.put_nowait(trade)
                    
            # Log significant trades
            if "SWEEP" in trade["tags"] or "BLOCK" in trade["tags"]:
                try:
                    LOG.info(f"BIG TRADE: {root} {trade['tags']} ${premium:,.0f}")
                except: pass
                
        except Exception as e:
            LOG.error(f"Broadcasting Error: {e}")

    async def start(self):
        """
        Initializes the TCP connection and starts streaming.
        """
        if self.active:
            LOG.warning("ThetaStreamer already active.")
            return

        self.loop = asyncio.get_running_loop()
        LOG.info(f"Starting Theta TCP Streamer (Target: {self.theta_host})...")
        self.active = True
        
        try:
            # Initialize Client (Connect Mode Only)
            
            # Retrieve and Sanitize Password
            env_user = os.getenv("THETADATA_USERNAME") or os.getenv("THETA_USER", "default")
            env_pass = os.getenv("THETADATA_PASSWORD") or os.getenv("THETA_PASS", "default")
            
            # Strip quotes if present (common .env issue)
            if env_pass and len(env_pass) > 2:
                if (env_pass.startswith("'") and env_pass.endswith("'")) or \
                   (env_pass.startswith('"') and env_pass.endswith('"')):
                    env_pass = env_pass[1:-1]

            self.client = ThetaClient(
                username=env_user,
                passwd=env_pass,
                launch=False, 
                host=self.theta_host,
                port=11000,           # TCP Command Port
                streaming_port=10000,  # Experiment: Try 10000 based on netstat
                timeout=10
            )

            # 1. Connect to Command Port (Blocking)
            LOG.info(f"Connecting to Theta Terminal Command Port (11000) at {self.theta_host}...")
            await self.loop.run_in_executor(None, self.client.connect)
            LOG.info("Connected to Command Port successfully.")
            
            # 2. Start the background stream thread (Non-blocking)
            LOG.info("Connecting to Theta Terminal Stream Port (11001)...")
            self.streaming_thread = self.client.connect_stream(self._on_stream_msg)
            LOG.info("Stream connection thread started.")
            
            # Wait a moment for connection stability
            await asyncio.sleep(2)
            
            # 3. Subscribe to all necessary streams
            LOG.info("Starting subscription phase...")
            await self._subscribe_all()
            LOG.info("Subscription phase complete.")

            # Keep alive loop
            asyncio.create_task(self._monitor_stream())
            # REST Polling Fallback for Stock/Index prices (options stream doesn't carry stock prices)
            asyncio.create_task(self._poll_price_loop())
            # REST-based Option Flow Poller (bypasses broken thetadata stream)
            asyncio.create_task(self._poll_option_flow_loop())

        except Exception as e:
            LOG.error(f"Failed to start Theta TCP Streamer: {e}")
            LOG.error(traceback.format_exc())
            self.active = False
            # Ensure we close if failed
            await self.stop()

    async def stop(self):
        """
        Stops the streamer.
        """
        LOG.info("Stopping Theta Streamer...")
        self.active = False
        if self.client:
            try:
                # This might block?
                self.client.close_stream()
            except:
                pass
        self.client = None

    def _on_stream_msg(self, msg: StreamMsg):
        """
        Callback from the Java Bridge Thread.
        WARNING: This runs in a separate thread.
        """
        try:
            m_type = str(msg.type)
            
            # Robust Type Detection
            is_trade = "TRADE" in m_type or (hasattr(msg.type, "name") and msg.type.name == "TRADE") or (isinstance(msg.type, int) and msg.type == 1)
            is_quote = "QUOTE" in m_type or (hasattr(msg.type, "name") and msg.type.name == "QUOTE") or (isinstance(msg.type, int) and msg.type == 0)

            if self.loop and self.active:
                if is_trade:
                    # Check Asset Type
                    strike_val = getattr(msg.contract, "strike", 0)
                    is_option = strike_val > 0
                    
                    if is_option:
                        # Pass Option Trades to Processor (Aggregation)
                        self.loop.call_soon_threadsafe(
                            lambda: self.loop.create_task(self.processor.on_trade(msg))
                        )
                    else:
                        # Update Stock Price directly (No aggregation needed for price line)
                        self.loop.call_soon_threadsafe(
                            self._update_stock_price, msg
                        )

                elif is_quote:
                    # Update Processor's NBBO State
                    self.loop.call_soon_threadsafe(
                        self.processor.on_quote, msg
                    )

        except Exception as e:
            # Avoid logging too heavily in high-freq callback
            pass

    def _update_stock_price(self, msg):
        """Helper to update internal state for Underlying Price."""
        try:
            root = msg.contract.root
            price = msg.trade.price
            
            if root not in self.state:
                self.state[root] = {"price": 0.0, "net_flow": 0.0, "last_update_ms": 0}
            
            # Simple outlier check (Session-aware)
            last = self.state[root]["price"]
            if last > 0:
                pct = abs(price - last) / last
                if pct > 0.05: return # Ignore >5% jumps
            
            now_ts = int(datetime.now().timestamp())
            self.state[root]["price"] = price
            self.state[root]["last_update_ms"] = now_ts * 1000
            
            # Broadcast Stock Update
            msg = {
                "type": "TRADE",
                "root": root,
                "price": price,
                "asset_type": "STOCK",
                "time": now_ts,
                "timestamp": datetime.now().isoformat(),
                "hiro_flow": self.state[root]["net_flow"]
            }
            for q in self.listeners:
                if not q.full(): q.put_nowait(msg)
        except:
            pass

    def _update_and_broadcast(self, msg, cond_name, is_option, is_stock):
        """
        Updates state and broadcasts formatted message.
        """
        # 1. Update State
        # Safer extraction
        is_call = getattr(msg.contract, 'isCall', False)
        right = "C" if is_call else "P"
        strike = getattr(msg.contract, 'strike', 0)
        exp = str(getattr(msg.contract, 'exp', ''))
        
        self._update_state(
             msg.contract.root, 
             msg.trade.price, 
             msg.trade.size, 
             right,
             "OPTION" if is_option else "STOCK"
        )
        
        # 2. Get Updated Flow
        updated_state = self.state.get(msg.contract.root, {})
        updated_flow = updated_state.get("net_flow", 0.0)
        spot_price = updated_state.get("price", 0.0)

        # 3. Format Message
        ts_now = datetime.now()
        data = {
            "type": "TRADE",
            "root": msg.contract.root,
            "strike": strike,
            "right": right,
            "exp": exp,
            "price": msg.trade.price,
            "size": msg.trade.size,
            "condition": cond_name,
            "ms_of_day": msg.trade.ms_of_day,
            "timestamp": ts_now.isoformat(),
            "time": int(ts_now.timestamp()), # Frontend expects Unix Int
            "asset_type": "OPTION" if is_option else "STOCK",
            "hiro_flow": updated_flow,
            "spot": spot_price
        }

        if is_option:
            premium = msg.trade.price * msg.trade.size * 100
            data["value"] = premium
            data["sweep"] = "SWEEP" in cond_name or "ISO" in cond_name # Check flags
            
            # Sentiment Logic:
            # We don't have 'side' explicitly from basic stream in all plans.
            # But thetadata usually provides it. Let's try to get it, or infer.
            # Assuming 'aggressor_side' or similar if available, or using tick test fallback.
            # For now, simple Bullish/Bearish based on Right + Delta (if we had it)
            # Actually, standard flow color:
            # Bid side (Sold) = Bearish for Calls, Bullish for Puts?
            # No, typically:
            # Green = Bought at Ask (Bullish if Call, Bearish if Put - wait, usually Green means 'Aggressive Buy')
            # Red = Sold at Bid (Aggressive Sell)
            
            # Let's try to use 'side' if available on the msg object
            # The library `StreamMsg` might not have it easily accessible without casting.
            # We will default to Neutral/White if unknown.
            data["sentiment"] = "NEUTRAL"
            
            # Update Day Stats
            stats = self.day_stats[msg.contract.root]
            if right == "C":
                stats["call_vol"] += msg.trade.size
                stats["call_prem"] += premium
            else:
                stats["put_vol"] += msg.trade.size
                stats["put_prem"] += premium
            
            # Store in History
            self.recent_trades.append(data)
        
        self.broadcast_sync(data)


    def broadcast_sync(self, msg: Dict):
        """
        Sync wrapper to schedule the async broadcast.
        """
        asyncio.create_task(self.broadcast(msg))

    async def broadcast(self, msg: Dict):
        """
        Pushes message to all listener queues.
        """
        for q in self.listeners:
            try:
                await q.put(msg)
            except Exception:
                pass

    def get_latest_data(self, ticker: str) -> Dict[str, float]:
        """
        Returns the current aggregated state for a ticker.
        Used by polling endpoints.
        """
        if ticker not in self.state:
            return {"price": 0.0, "hiro_flow": 0.0}
        return {
             "price": self.state[ticker]["price"],
             "hiro_flow": self.state[ticker]["net_flow"]
        }

    def _record_flow_snapshot(self, ticker: str):
        """Records a {time, price, flow} data point for intraday history."""
        if ticker not in self.state:
            return
        price = self.state[ticker].get("price", 0.0)
        flow = self.state[ticker].get("net_flow", 0.0)
        if price <= 0:
            return
        ts = int(datetime.now().timestamp())
        if ticker not in self.flow_history:
            self.flow_history[ticker] = deque(maxlen=5000)
        hist = self.flow_history[ticker]
        # Avoid duplicate timestamps
        if hist and hist[-1]["time"] == ts:
            return
        hist.append({"time": ts, "value": price, "flow": flow})

    def get_flow_history(self, ticker: str) -> list:
        """Returns stored intraday flow history for chart backfill."""
        if ticker not in self.flow_history:
            return []
        return list(self.flow_history[ticker])

    def _update_state(self, ticker: str, price: float, size: int, right: str, asset_type: str = "OPTION"):
        """
        Updates internal state (Price and Net Flow).
        Flow Metric: Net Premium (Call Volume - Put Volume).
        """
        if ticker not in self.state:
            self.state[ticker] = {"price": 0.0, "net_flow": 0.0, "last_update_ms": 0}

        # 1. Update Net Flow (Only for Options)
        if asset_type == "OPTION":
            premium = price * size * 100
            if right == "C":
                self.state[ticker]["net_flow"] += premium
            else:
                self.state[ticker]["net_flow"] -= premium

        # 2. Update Underlying Price (Only for Stock/Index)
        elif asset_type == "STOCK":
            self.state[ticker]["price"] = price
            self.state[ticker]["last_update_ms"] = int(datetime.now().timestamp() * 1000)


    # Index tickers that require /v2/hist/index/price instead of /v2/hist/stock/ohlc
    INDEX_TICKERS = {"SPX", "VIX", "NDX", "RUT", "DJX"}

    def get_intraday_history(self, ticker: str, resolution: str = "1m") -> list:
        """
        Fetches intraday or daily history via Theta Terminal REST API.
        Uses the REST endpoint directly (not the buggy thetadata v0.9.11 Python lib).
        Handles both stock (SPY, QQQ, IWM) and index (SPX) tickers with correct endpoints.
        Resolutions: 1m, 5m, 15m, 30m, 1h, 4h, 1d.
        """
        import httpx
        from datetime import date, timedelta
        import pytz

        is_index = ticker.upper() in self.INDEX_TICKERS

        # Resolution Mapping (interval_ms, lookback_days)
        res_map = {
            "1m": (60000, 5),
            "5m": (300000, 30),
            "15m": (900000, 60),
            "30m": (1800000, 120),
            "1h": (3600000, 180),
            "4h": (14400000, 365),
            "1d": (86400000, 730),
        }

        interval_ms, lookback_days = res_map.get(resolution, (60000, 1))
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        base_url = f"http://{self.theta_host}:{self.theta_rest_port}"

        try:
            if is_index:
                return self._fetch_index_history(
                    base_url, ticker, start_date, end_date, resolution, interval_ms
                )
            elif resolution == "1d":
                return self._fetch_stock_daily(
                    base_url, ticker, start_date, end_date
                )
            else:
                return self._fetch_stock_intraday(
                    base_url, ticker, start_date, end_date, interval_ms
                )
        except Exception as e:
            LOG.error(f"Failed to fetch history for {ticker} ({resolution}): {e}")
            LOG.error(traceback.format_exc())
            return []

    def _fetch_stock_daily(self, base_url: str, ticker: str, start_date, end_date) -> list:
        """Fetch daily stock OHLC via /v2/hist/stock/eod (purpose-built for daily data)."""
        import httpx

        url = f"{base_url}/v2/hist/stock/eod"
        params = {
            "root": ticker,
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
        }
        resp = httpx.get(url, params=params, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()

        header = data.get("header", {}).get("format", [])
        rows = data.get("response", [])
        if not rows:
            LOG.warning(f"No daily data for {ticker}")
            return []

        # Map column names to indices
        col_map = {name.lower(): i for i, name in enumerate(header)}
        date_i = col_map.get("date")
        open_i = col_map.get("open")
        high_i = col_map.get("high")
        low_i = col_map.get("low")
        close_i = col_map.get("close")
        vol_i = col_map.get("volume")

        if date_i is None or close_i is None:
            LOG.warning(f"Missing columns for {ticker} daily: {header}")
            return []

        result = []
        for r in rows:
            dt_str = str(r[date_i])
            if len(dt_str) != 8:
                continue
            day_str = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
            c = float(r[close_i]) if close_i is not None else 0
            if c <= 0:
                continue

            result.append({
                "time": day_str,
                "date": day_str,
                "open": float(r[open_i]) if open_i is not None else c,
                "high": float(r[high_i]) if high_i is not None else c,
                "low": float(r[low_i]) if low_i is not None else c,
                "close": c,
                "volume": int(r[vol_i]) if vol_i is not None else 0,
                "value": c,
            })

        # Outlier filter: reject bars where ANY OHLC field deviates >50% from its median
        if len(result) > 2:
            for field in ("open", "high", "low", "close"):
                vals = sorted([r[field] for r in result if r[field] > 0])
                if not vals:
                    continue
                median = vals[len(vals) // 2]
                if median > 0:
                    before = len(result)
                    result = [r for r in result if r[field] <= 0 or abs(r[field] - median) / median < 0.5]
                    if len(result) < before:
                        LOG.warning(f"Filtered {before - len(result)} outlier bars ({field}) for {ticker}")

        LOG.info(f"Fetched {len(result)} daily bars for {ticker} via /stock/eod")
        return result

    def _fetch_stock_intraday(self, base_url: str, ticker: str, start_date, end_date, interval_ms: int) -> list:
        """Fetch intraday stock OHLC via /v2/hist/stock/ohlc."""
        import httpx
        import pytz
        from datetime import date as dt_date

        url = f"{base_url}/v2/hist/stock/ohlc"
        params = {
            "root": ticker,
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
            "ivl": str(interval_ms),
        }
        resp = httpx.get(url, params=params, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("response", [])
        if not rows:
            LOG.warning(f"No intraday data for {ticker}")
            return []

        # Columns: [ms_of_day, open, high, low, close, volume, count, date]
        et_tz = pytz.timezone("America/New_York")
        result = []
        for r in rows:
            ms_of_day, o, h, l, c, vol, cnt, dt_int = r
            dt_str = str(dt_int)
            if len(dt_str) != 8:
                continue
            day = dt_date(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
            hours = ms_of_day // 3600000
            minutes = (ms_of_day % 3600000) // 60000
            seconds = (ms_of_day % 60000) // 1000
            naive_et = datetime(day.year, day.month, day.day, hours, minutes, seconds)
            aware_et = et_tz.localize(naive_et)
            ts = int(aware_et.timestamp())

            result.append({
                "time": ts,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "value": float(c),
            })

        # Outlier filter: reject bars where ANY OHLC field deviates >50% from its median
        if len(result) > 2:
            for field in ("open", "high", "low", "close"):
                vals = sorted([r[field] for r in result if r[field] > 0])
                if not vals:
                    continue
                median = vals[len(vals) // 2]
                if median > 0:
                    before = len(result)
                    result = [r for r in result if r[field] <= 0 or abs(r[field] - median) / median < 0.5]
                    if len(result) < before:
                        LOG.warning(f"Filtered {before - len(result)} outlier intraday bars ({field}) for {ticker}")

        LOG.info(f"Fetched {len(result)} intraday bars for {ticker} via /stock/ohlc")
        return result

    def _fetch_index_history(self, base_url: str, ticker: str, start_date, end_date, resolution: str, interval_ms: int) -> list:
        """
        Fetch history for index tickers (SPX, VIX) from /v2/hist/index/price.
        Always fetches at finest available granularity and resamples to target OHLC.
        This avoids flat candles (O=H=L=C=price) that appear as dots.
        """
        import httpx
        import pytz
        from datetime import date as dt_date
        from collections import OrderedDict

        # Always fetch at finer granularity, then resample to target resolution.
        # Index endpoint only returns single price per tick, so resampling gives real OHLC.
        fetch_ivl_map = {
            "1m": "0",         # 1m: fetch TICK data, resample to 1m OHLC (fixes flat candles)
            "5m": "0",         # 5m: fetch tick data, resample to 5m OHLC
            "15m": "60000",    # 15m: fetch 1m, resample to 15m (enough variation)
            "30m": "60000",    # 30m: fetch 1m, resample to 30m
            "1h": "300000",    # 1h: fetch 5m, resample to 1h
            "4h": "300000",    # 4h: fetch 5m, resample to 4h
            "1d": "300000",    # 1d: fetch 5m, resample to daily
        }
        fetch_ivl = fetch_ivl_map.get(resolution, "60000")

        url = f"{base_url}/v2/hist/index/price"
        params = {
            "root": ticker,
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
            "ivl": fetch_ivl,
        }
        resp = httpx.get(url, params=params, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()

        header = data.get("header", {}).get("format", [])
        rows = data.get("response", [])
        if not rows or not header:
            LOG.warning(f"No index data for {ticker}")
            return []

        # Map column names to indices
        col_map = {name.lower(): i for i, name in enumerate(header)}
        date_i = col_map.get("date")
        ms_i = col_map.get("ms_of_day")
        price_i = col_map.get("price")
        # Some intervals may return OHLC
        open_i = col_map.get("open")
        high_i = col_map.get("high")
        low_i = col_map.get("low")
        close_i = col_map.get("close")
        has_ohlc = all(x is not None for x in [open_i, high_i, low_i, close_i])

        et_tz = pytz.timezone("America/New_York")

        if resolution == "1d":
            # Resample to daily OHLC
            daily = OrderedDict()
            for r in rows:
                dt_int = r[date_i] if date_i is not None else 0
                dt_str = str(dt_int)
                if len(dt_str) != 8:
                    continue
                day_key = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}"

                if has_ohlc:
                    o_val = float(r[open_i])
                    h_val = float(r[high_i])
                    l_val = float(r[low_i])
                    c_val = float(r[close_i])
                elif price_i is not None:
                    p = float(r[price_i])
                    o_val = h_val = l_val = c_val = p
                else:
                    continue

                if c_val <= 0:
                    continue

                if day_key not in daily:
                    daily[day_key] = {"open": o_val, "high": h_val, "low": l_val, "close": c_val}
                else:
                    d = daily[day_key]
                    d["high"] = max(d["high"], h_val)
                    d["low"] = min(d["low"], l_val)
                    d["close"] = c_val  # Last value of the day

            result = []
            for day_key, ohlc in daily.items():
                result.append({
                    "time": day_key,
                    "date": day_key,
                    "open": round(ohlc["open"], 2),
                    "high": round(ohlc["high"], 2),
                    "low": round(ohlc["low"], 2),
                    "close": round(ohlc["close"], 2),
                    "volume": 0,
                    "value": round(ohlc["close"], 2),
                })

            # Outlier filter: reject bars where ANY OHLC field deviates >50% from its median
            if len(result) > 2:
                for field in ("open", "high", "low", "close"):
                    vals = sorted([r[field] for r in result if r[field] > 0])
                    if not vals:
                        continue
                    median = vals[len(vals) // 2]
                    if median > 0:
                        before = len(result)
                        result = [r for r in result if r[field] <= 0 or abs(r[field] - median) / median < 0.5]
                        if len(result) < before:
                            LOG.warning(f"Filtered {before - len(result)} outlier daily bars ({field}) for index {ticker}")

            LOG.info(f"Fetched {len(result)} daily bars for index {ticker} (resampled from 5-min)")
            return result

        else:
            # Intraday resolution: resample fine-grained ticks into target OHLC buckets
            bucket_seconds_map = {
                "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                "1h": 3600, "4h": 14400,
            }
            bucket_size = bucket_seconds_map.get(resolution, 60)

            buckets = OrderedDict()
            for r in rows:
                dt_int = r[date_i] if date_i is not None else 0
                ms_of_day = r[ms_i] if ms_i is not None else 0

                dt_str = str(dt_int)
                if len(dt_str) != 8:
                    continue

                day = dt_date(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
                hours = ms_of_day // 3600000
                minutes = (ms_of_day % 3600000) // 60000
                seconds = (ms_of_day % 60000) // 1000
                naive_et = datetime(day.year, day.month, day.day, hours, minutes, seconds)
                aware_et = et_tz.localize(naive_et)
                ts = int(aware_et.timestamp())

                if has_ohlc:
                    o_val = float(r[open_i])
                    h_val = float(r[high_i])
                    l_val = float(r[low_i])
                    c_val = float(r[close_i])
                elif price_i is not None:
                    p = float(r[price_i])
                    o_val = h_val = l_val = c_val = p
                else:
                    continue

                if c_val <= 0:
                    continue

                # Snap to bucket
                bucket_ts = (ts // bucket_size) * bucket_size
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {"open": o_val, "high": h_val, "low": l_val, "close": c_val}
                else:
                    b = buckets[bucket_ts]
                    b["high"] = max(b["high"], h_val)
                    b["low"] = min(b["low"], l_val)
                    b["close"] = c_val

            result = []
            for bucket_ts, ohlc in buckets.items():
                result.append({
                    "time": bucket_ts,
                    "open": round(ohlc["open"], 2),
                    "high": round(ohlc["high"], 2),
                    "low": round(ohlc["low"], 2),
                    "close": round(ohlc["close"], 2),
                    "value": round(ohlc["close"], 2),
                })

            # Outlier filter: reject bars where ANY OHLC field deviates >50% from its median
            if len(result) > 2:
                for field in ("open", "high", "low", "close"):
                    vals = sorted([r[field] for r in result if r[field] > 0])
                    if not vals:
                        continue
                    median = vals[len(vals) // 2]
                    if median > 0:
                        before = len(result)
                        result = [r for r in result if r[field] <= 0 or abs(r[field] - median) / median < 0.5]
                        if len(result) < before:
                            LOG.warning(f"Filtered {before - len(result)} outlier intraday bars ({field}) for index {ticker}")

            LOG.info(f"Fetched {len(result)} intraday bars for index {ticker} (resampled to {resolution})")
            return result



    async def _subscribe_all(self):
        """
        Sends subscription commands.
        """
        if not self.client:
            return
            
        # 1. Subscribe to ALL OPTION TRADES (market-wide)
        LOG.info("Subscribing to FULL OPTION TRADE STREAM...")
        try:
            req_id = await self.loop.run_in_executor(None, self.client.req_full_trade_stream_opt)
            LOG.info(f"Subscribed to FULL OPTION TRADE STREAM (id={req_id})")
        except Exception as e:
            LOG.error(f"Failed to subscribe to full option stream: {e}")
        
        # DEBUG: Subscribe to specific SPY Option to test stream (Exp: 2026-02-20 Fri, Strike: 685)
        try:
             # Strike in millis (685000 = 685.00)
             spy_opt_req = await self.loop.run_in_executor(
                 None,
                 lambda: self.client.req_trade_stream_opt(
                     root="SPY", 
                     exp=dt_date(2026, 2, 20), 
                     strike=685000, 
                     right=OptionRight.CALL
                 )
             )
             LOG.info(f"Subscribed to TEST SPY OPTION (id={spy_opt_req})")
             
             # DEBUG: Subscribe to QUOTES too
             spy_quote_req = await self.loop.run_in_executor(
                 None,
                 lambda: self.client.req_quote_stream_opt(
                     root="SPY", 
                     exp=dt_date(2026, 2, 20), 
                     strike=685000, 
                     right=OptionRight.CALL
                 )
             )
             LOG.info(f"Subscribed to TEST SPY QUOTE (id={spy_quote_req})")
        except Exception as e:
             LOG.error(f"Failed to subscribe to TEST SPY OPTION: {e}")
        
        # 2. Subscribe to specific stock roots ONLY for index prices
        for ticker in self.tickers:
            try:
                # Sub to Stock Trades (for price line)
                if ticker not in ("SPX", "VIX", "NDX", "RUT"):
                    LOG.info(f"Subscribing to STOCK root {ticker}...")
                    stock_req = await self.loop.run_in_executor(
                        None,
                        lambda t=ticker: self.client.req_trade_stream_opt(root=t, exp=dt_date(1, 1, 1), strike=0, right=OptionRight.CALL)
                    )
                    LOG.info(f"Subscribed to {ticker} STOCK trade stream (id={stock_req})")
            except Exception as e:
                LOG.error(f"Failed to subscribe to {ticker} stock: {e}")

    # DEPRECATED: Old manual TCP bypass method
    # def req_trade_stream_root_bypass(self, root: str):
    #     ... (kept for reference)


    async def _monitor_stream(self):
        """
        Keeps the connection alive and handles reconnects if needed.
        """
        while self.active:
            await asyncio.sleep(5)
            # Check connection status if exposed by library
            # client._stream_connected is boolean in client.py
            if self.client and not self.client._stream_connected:
                LOG.warning("TCP Stream reported disconnected. Reconnecting...")
                # Simple Restart logic
                await self.stop()
                await asyncio.sleep(2)
                await self.start()

    async def _poll_price_loop(self):
        """
        Polls Theta Terminal REST API (port 25510) for latest stock prices.
        Uses httpx directly — avoids thetadata library connection state issues.
        Runs every 2s. Provides stock/index prices during all sessions including pre-market.
        """
        import httpx

        LOG.info("Starting Price Poller (REST API)...")
        base_url = f"http://{self.theta_host}:{self.theta_rest_port}"

        # Wait for Theta Terminal to be ready
        await asyncio.sleep(5)

        while self.active:
            for ticker in self.tickers:
                try:
                    # Use snapshot/stock/quote for real-time bid/ask (works pre-market)
                    if ticker in ("SPX", "VIX"):
                        # Indices: use tick-level data from hist/index/price
                        # ivl=0 returns every price change (~1/sec for SPX)
                        # so each 2s poll gets the latest tick price, not a stale minute bar
                        from datetime import date
                        today = date.today()
                        url = f"{base_url}/v2/hist/index/price"
                        params = {
                            "root": ticker,
                            "start_date": today.strftime("%Y%m%d"),
                            "end_date": today.strftime("%Y%m%d"),
                            "ivl": "0",
                        }
                    else:
                        # Stocks (SPY, QQQ, IWM): prefer last trade, fallback to quote midpoint
                        url = f"{base_url}/v2/snapshot/stock/trade"
                        params = {"root": ticker}

                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(url, params=params, timeout=5.0)
                            
                        if resp.status_code == 472:
                            # 472 = No Data (Common on weekends/holidays for "Today")
                            # Just continue silently or debug log occasionally
                            continue
                            
                        if resp.status_code != 200:
                            # Log other errors as warning but don't crash loop
                            LOG.warning(f"Polling warning for {ticker}: HTTP {resp.status_code}")
                            continue

                    except httpx.ReadTimeout:
                        # Timeout means sidecar is busy/crashed. Don't spam error logs.
                        LOG.warning(f"Polling timeout for {ticker} (Theta Sidecar busy/down)")
                        continue
                    except Exception as e:
                        LOG.error(f"Polling failed for {ticker}: {e}")
                        continue

                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    response = data.get("response", [])
                    if not response:
                        continue

                    price = 0.0
                    if ticker in ("SPX", "VIX"):
                        # Index: use header-based column mapping for reliability
                        header = data.get("header", {}).get("format", [])
                        col_map = {name.lower(): i for i, name in enumerate(header)}
                        last = response[-1]
                        if "close" in col_map:
                            price = float(last[col_map["close"]])
                        elif "price" in col_map:
                            price = float(last[col_map["price"]])
                        else:
                            # Fallback: second column for simple [ms_of_day, price, date]
                            price = float(last[1]) if len(last) >= 2 else 0.0
                    else:
                        # Stocks: extract last trade price
                        header = data.get("header", {}).get("format", [])
                        raw_entry = response[-1]
                        # Handle both flat array and dict-wrapped responses
                        if isinstance(raw_entry, list):
                            tick = raw_entry
                        elif isinstance(raw_entry, dict):
                            sub_ticks = raw_entry.get("ticks", [])
                            tick = sub_ticks[-1] if sub_ticks else []
                        else:
                            tick = []

                        if tick and "price" in header:
                            raw_val = tick[header.index("price")]
                            price = float(raw_val) if raw_val else 0
                            LOG.info(f"TRADE PRICE {ticker}: ${price:.2f} (header={header})")
                        else:
                            LOG.warning(f"TRADE PARSE FAIL {ticker}: header={header}, entry_type={type(raw_entry).__name__}, tick={tick}")

                        # Fallback: quote midpoint if trade endpoint returned 0
                        if price <= 0:
                            LOG.warning(f"TRADE FALLBACK {ticker}: price={price}, using quote midpoint")
                            try:
                                async with httpx.AsyncClient() as client:
                                    quote_resp = await client.get(
                                        f"{base_url}/v2/snapshot/stock/quote",
                                        params={"root": ticker}, timeout=5.0
                                    )
                                if quote_resp.status_code == 200:
                                    q_data = quote_resp.json()
                                    q_response = q_data.get("response", [])
                                    q_header = q_data.get("header", {}).get("format", [])
                                    if q_response and "bid" in q_header and "ask" in q_header:
                                        q_entry = q_response[-1]
                                        q_tick = q_entry if isinstance(q_entry, list) else q_entry.get("ticks", [[]])[0]
                                        bid = float(q_tick[q_header.index("bid")]) if q_tick[q_header.index("bid")] else 0
                                        ask = float(q_tick[q_header.index("ask")]) if q_tick[q_header.index("ask")] else 0
                                        price = (bid + ask) / 2.0 if bid > 0 and ask > 0 else max(bid, ask)
                                        LOG.info(f"QUOTE MIDPOINT {ticker}: bid=${bid:.2f} ask=${ask:.2f} mid=${price:.2f}")
                            except Exception as e:
                                LOG.warning(f"QUOTE FALLBACK FAILED {ticker}: {e}")

                    if price > 0:
                        # Broadcast as a STOCK price update
                        ts_now = datetime.now()
                        msg = {
                            "type": "TRADE",
                            "root": ticker,
                            "strike": 0,
                            "right": "C",
                            "exp": "0",
                            "price": price,
                            "size": 0,
                            "condition": "POLLED",
                            "ms_of_day": int(ts_now.timestamp() * 1000) % 86400000,
                            "timestamp": ts_now.isoformat(),
                            "time": int(ts_now.timestamp()),
                            "asset_type": "STOCK",
                            "hiro_flow": self.state.get(ticker, {}).get("net_flow", 0.0),
                        }

                        # Update internal state directly
                        self._update_state(ticker, price, 0, "C", "STOCK")

                        # Record flow snapshot for intraday history
                        self._record_flow_snapshot(ticker)

                        # Broadcast to all WebSocket listeners
                        await self.broadcast(msg)
                        LOG.info(f"Polled {ticker}: ${price:.2f}")

                except Exception as e:
                    LOG.error(f"Polling failed for {ticker}: {e}")

            await asyncio.sleep(2)

    async def _get_next_expiration(self, root: str) -> Optional[str]:
        """Helper: Find nearest valid expiration date for root. Returns YYYYMMDD string."""
        import httpx
        from datetime import date
        
        base_url = f"http://{self.theta_host}:{self.theta_rest_port}"
        try:
             async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/v2/list/expirations",
                    params={"root": root},
                    timeout=5.0
                )
                if resp.status_code != 200:
                    return None
                
                data = resp.json()
                exps = data.get("response", [])
                if not exps:
                    return None
                
                # Filter for today or future
                today_int = int(date.today().strftime("%Y%m%d"))
                valid_exps = sorted([e for e in exps if e >= today_int])
                
                return str(valid_exps[0]) if valid_exps else None
        except Exception as e:
            LOG.warning(f"Failed to fetch expirations for {root}: {e}")
            return None

    async def _poll_option_flow_loop(self):
        """
        REST-based HIRO Flow Poller & Synthetic Trade Generator.
        Polls bulk_snapshot/option/ohlc every 10s for each ticker's nearest expiry.
        Tracks volume changes between polls and:
        1. Computes option net flow.
        2. Generates SYNTHETIC_POLL trades for the frontend.
        """
        import httpx
        from datetime import date as dt_date
        
        LOG.info("Starting Option Flow Poller & Synthetic Trade Generator (REST API)...")
        base_url = f"http://{self.theta_host}:{self.theta_rest_port}"

        # Wait for price data to arrive first
        await asyncio.sleep(15)

        # Track previous volumes: ticker -> {contract_key: volume}
        prev_volumes: Dict[str, Dict[str, Dict]] = {}

        while self.active:
            for ticker in self.tickers:
                if ticker == "VIX": continue # VIX options are special, skip for now
                
                # Dynamic Expiration (Fixes 474 Errors)
                exp_str = await self._get_next_expiration(ticker)
                if not exp_str:
                    continue
                
                option_root = "SPXW" if ticker == "SPX" else ticker

                try:
                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(
                                f"{base_url}/v2/bulk_snapshot/option/ohlc",
                                params={"root": option_root, "exp": exp_str},
                                timeout=10.0,
                            )
                        
                        if resp.status_code != 200:
                            if resp.status_code != 472: # 472 = No Data
                                LOG.warning(f"Flow Poll warning for {ticker} ({exp_str}): {resp.status_code}")
                            continue
                            
                    except Exception as e:
                        LOG.error(f"Option flow poll failed for {ticker}: {e}")
                        continue

                    data = resp.json()
                    header = data.get("header", {}).get("format", [])
                    if "close" not in header or "volume" not in header:
                        continue

                    idx_close = header.index("close")
                    idx_volume = header.index("volume")

                    # Build current volume snapshot
                    current: Dict[str, Dict] = {}
                    for item in data.get("response", []):
                        contract = item.get("contract", {})
                        ticks = item.get("ticks", [])
                        if not contract or not ticks:
                            continue

                        strike = contract.get("strike", 0) / 1000.0
                        right = contract.get("right", "")
                        tick = ticks[-1]
                        volume = int(tick[idx_volume])
                        close_price = float(tick[idx_close])

                        key = f"{strike}_{right}"
                        current[key] = {"volume": volume, "close": close_price, "right": right}

                    # Compute flow delta & Synthesize Trades
                    prev = prev_volumes.get(ticker, {})
                    if prev:
                        delta_flow = 0.0
                        trades_generated = 0
                        
                        for key, curr_data in current.items():
                            prev_data = prev.get(key)
                            if prev_data and curr_data["close"] > 0:
                                delta_vol = curr_data["volume"] - prev_data["volume"]
                                if delta_vol > 0:
                                    premium = curr_data["close"] * delta_vol * 100
                                    
                                    # Info for Trade
                                    is_call = (curr_data["right"] == "C")
                                    if is_call:
                                        delta_flow += premium
                                    else:
                                        delta_flow -= premium
                                        
                                    # SYNTHETIC TRADE GENERATION
                                    # Create a trade object consistent with stream 
                                    trade_data = {
                                        "type": "TRADE",
                                        "root": ticker,
                                        "strike": float(key.split('_')[0]),
                                        "right": curr_data["right"],
                                        "exp": f"{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:]}", 
                                        "price": curr_data["close"],
                                        "size": delta_vol,
                                        "condition": "SYNTHETIC_POLL",
                                        "ms_of_day": int(datetime.now().timestamp() * 1000) % 86400000,
                                        "timestamp": datetime.now().isoformat(),
                                        "time": int(datetime.now().timestamp()), # Unix Timestamp
                                        "asset_type": "OPTION",
                                        "value": premium,
                                        "sweep": False,
                                        "sentiment": "NEUTRAL",
                                        "spot": self.state.get(ticker, {}).get("price", 0.0),
                                        "hiro_flow": self.state.get(ticker, {}).get("net_flow", 0.0) # Will be stale until end of loop update
                                    }
                                    
                                    # Update stats directly? 
                                    # broadcast_sync will handle nothing but pushing to queue.
                                    # frontend stats update every 1s might pick this up if day_stats are updated?
                                    # Actually day_stats only updated in _update_and_broadcast which is called by stream.
                                    # We should probably update day_stats here too?
                                    
                                    # Update Day Stats
                                    stats = self.day_stats[ticker]
                                    if is_call:
                                        stats["call_vol"] += delta_vol
                                        stats["call_prem"] += premium
                                        stats["net_flow"] += premium
                                    else:
                                        stats["put_vol"] += delta_vol
                                        stats["put_prem"] += premium
                                        stats["net_flow"] -= premium
                                        
                                    # Store in History (Critical for Snapshot on new connection)
                                    self.recent_trades.append(trade_data)

                                    # Send to frontend
                                    self.broadcast_sync(trade_data)
                                    trades_generated += 1

                        # Update cumulative flow in state
                        if ticker not in self.state:
                            self.state[ticker] = {"price": 0.0, "net_flow": 0.0, "last_update_ms": 0}
                        self.state[ticker]["net_flow"] += delta_flow

                        if trades_generated > 0:
                             LOG.info(f"Synthesized {trades_generated} trades for {ticker} (Delta Flow: ${delta_flow:,.0f})")

                    prev_volumes[ticker] = current

                except Exception as e:
                    LOG.error(f"Option flow poll failed for {ticker}: {e}")

            await asyncio.sleep(10)

    def add_listener(self, queue: asyncio.Queue):
        self.listeners.append(queue)

    async def get_spx_probability_chain(self, expirations: list) -> list:
        """
        Fetches SPX option chain data for specified expirations.
        Returns a list of dicts with expiration, strike, call_mid, put_mid, forward_price.
        """
        if not self.client:
            LOG.warning("ThetaClient not initialized, cannot fetch SPX chain")
            return []
        
        results = []
        
        try:
            from datetime import date
            from thetadata.enums import OptionRight, OptionReqType
            
            with self.client.connect():
                # Limit to 8 expirations to save time
                limited_expirations = expirations[:8]
                
                for exp_date in limited_expirations:
                    # Ensure we have a date object
                    if isinstance(exp_date, str):
                        from datetime import datetime
                        try:
                            exp_date = datetime.strptime(exp_date, '%Y-%m-%d').date()
                        except ValueError:
                            LOG.warning(f"Invalid expiration date format: {exp_date}")
                            continue
                    
                    exp_str = exp_date.isoformat()
                    
                    # Try SPX first, then SPXW (Weekly) fallback
                    strikes_df = None
                    active_root = 'SPX'
                    
                    try:
                        LOG.debug(f"Trying SPX for {exp_str}...")
                        strikes_df = self.client.get_strikes(root='SPX', exp=exp_date)
                    except Exception:
                        pass
                        
                    if strikes_df is None or strikes_df.empty:
                        try:
                            LOG.debug(f"Falling back to SPXW for {exp_str}...")
                            strikes_df = self.client.get_strikes(root='SPXW', exp=exp_date)
                            active_root = 'SPXW'
                        except Exception as e:
                            LOG.warning(f"No strikes found for SPX or SPXW on {exp_str}: {e}")
                            continue
                    
                    if strikes_df is None or strikes_df.empty:
                        LOG.warning(f"Final: No strikes found for {exp_str}")
                        continue
                    
                    # Extract strikes list
                    all_strikes = strikes_df.tolist() if hasattr(strikes_df, 'tolist') else []
                    if not all_strikes:
                        continue
                    
                    # --- SMART FILTERING: Dynamic 3-Sigma Range ---
                    import math
                    from datetime import date
                    today = date.today()
                    dte_days = max((exp_date - today).days, 1)
                    
                    # Attempt to get actual spot price for centering
                    spot_price = float(all_strikes[len(all_strikes)//2]) # Fallback
                    try:
                        from thetadata.enums import StockReqType
                        # Try SPX last price directly first
                        spx_p = self.client.get_last_stock(req=StockReqType.QUOTE, root='SPX')
                        if not spx_p.empty and 'bid' in spx_p.columns:
                            spot_price = float(spx_p['bid'].iloc[0])
                        else:
                            # Fallback to SPY * 10
                            spy_p = self.client.get_last_stock(req=StockReqType.QUOTE, root='SPY')
                            if not spy_p.empty and 'bid' in spy_p.columns:
                                spot_price = float(spy_p['bid'].iloc[0]) * 10
                        LOG.debug(f"Centering {active_root} on spot: {spot_price}")
                    except Exception: pass
                    
                    # Limit = Spot * IV(20%) * sqrt(Days/365) * 3 Sigma
                    limit = spot_price * 0.20 * math.sqrt(dte_days / 365.0) * 3.0
                    lower_bound = spot_price - limit
                    upper_bound = spot_price + limit
                    
                    filtered_strikes = [s for s in all_strikes if lower_bound <= s <= upper_bound]
                    
                    # Smart Decimation: instead of hard cap, skip strikes to keep ~100
                    if len(filtered_strikes) > 100:
                        step = math.ceil(len(filtered_strikes) / 100)
                        strikes = filtered_strikes[::step]
                    else:
                        strikes = filtered_strikes
                    
                    if not strikes:
                        # Fallback to nearest strikes if bounds are empty
                        mid = len(all_strikes) // 2
                        strikes = all_strikes[max(0, mid-50) : min(len(all_strikes), mid+50)]
                        
                    LOG.info(f"Processing {len(strikes)} smart-filtered strikes for {active_root} {exp_str} (Range: +/-{limit:.1f}, Step: {len(filtered_strikes)//len(strikes) if len(strikes)>0 else 1})")
                    
                    # --- PARALLEL FETCHING: ThreadPoolExecutor ---
                    from concurrent.futures import ThreadPoolExecutor
                    
                    call_prices = {}
                    put_prices = {}
                    
                    def fetch_strike_quotes(strike):
                        strike_f = float(strike)
                        c_mid = 0.0
                        p_mid = 0.0
                        try:
                            # CALL
                            c_q = self.client.get_last_option(
                                req=OptionReqType.QUOTE,
                                root=active_root,
                                exp=exp_date,
                                strike=strike_f,
                                right=OptionRight.CALL
                            )
                            if not c_q.empty:
                                b = float(c_q['bid'].iloc[0]) if 'bid' in c_q.columns else 0.0
                                a = float(c_q['ask'].iloc[0]) if 'ask' in c_q.columns else 0.0
                                c_mid = (b + a) / 2
                        except: pass
                        
                        try:
                            # PUT
                            p_q = self.client.get_last_option(
                                req=OptionReqType.QUOTE,
                                root=active_root,
                                exp=exp_date,
                                strike=strike_f,
                                right=OptionRight.PUT
                            )
                            if not p_q.empty:
                                b = float(p_q['bid'].iloc[0]) if 'bid' in p_q.columns else 0.0
                                a = float(p_q['ask'].iloc[0]) if 'ask' in p_q.columns else 0.0
                                p_mid = (b + a) / 2
                        except: pass
                        
                        return strike, c_mid, p_mid

                    with ThreadPoolExecutor(max_workers=20) as executor:
                        all_results = list(executor.map(fetch_strike_quotes, strikes))
                    
                    for s, c, p in all_results:
                        call_prices[s] = c
                        put_prices[s] = p
                    
                    # Forward Price calculation
                    min_diff = float('inf')
                    forward_price = 0.0
                    
                    for strike in strikes:
                        cm = call_prices.get(strike, 0.0)
                        pm = put_prices.get(strike, 0.0)
                        if cm > 0 and pm > 0:
                            diff = abs(cm - pm)
                            if diff < min_diff:
                                min_diff = diff
                                forward_price = float(strike + (cm - pm))
                    
                    if forward_price == 0.0 and strikes:
                        forward_price = float((min(strikes) + max(strikes)) / 2)
                    
                    # Build Results
                    for strike in strikes:
                        results.append({
                            'expiration': exp_str,
                            'strike': float(strike),
                            'call_mid': float(call_prices.get(strike, 0.0)),
                            'put_mid': float(put_prices.get(strike, 0.0)),
                            'forward_price': float(forward_price)
                        })
            
            LOG.info(f"Fetched optimized SPX chain: {len(results)} records across {len(limited_expirations)} expirations")
            return results
            
        except Exception as e:
            LOG.error(f"Failed to fetch SPX probability chain: {e}")
            import traceback
            LOG.error(traceback.format_exc())
            return []

    def get_daily_history(self, ticker: str, days: int = 90) -> list:
        """
        Fetches daily OHLC history for the specified ticker.
        Used for historical price chart background.
        Returns list of {date: str, close: float}
        """
        if not self.client:
            LOG.warning("ThetaClient not initialized, cannot fetch daily history")
            return []
        
        try:
            from datetime import date
            from thetadata.enums import DateRange, StockReqType, DataType
            
            # Use DateRange to get last N days
            date_range = DateRange.from_days(days)
            
            with self.client.connect():
                # Fetch daily bars (86400000ms = 1 day)
                df = self.client.get_hist_stock(
                    req=StockReqType.OHLC,
                    root=ticker,
                    date_range=date_range,
                    interval_size=86400000,  # 86400000ms = 1 day
                    use_rth=True
                )
                
                if df is None or df.empty:
                    LOG.warning(f"No daily history for {ticker}")
                    return []
                
                # Convert to chart format
                result = []
                for idx, row in df.iterrows():
                    date_val = row[DataType.DATE]
                    close_val = row[DataType.CLOSE]
                    
                    result.append({
                        "date": str(date_val),
                        "close": float(close_val)
                    })
                
                LOG.info(f"Fetched {len(result)} daily bars for {ticker}")
                return result
                
        except Exception as e:
            LOG.error(f"Failed to fetch daily history for {ticker}: {e}")
            import traceback
            LOG.error(traceback.format_exc())
            return []
