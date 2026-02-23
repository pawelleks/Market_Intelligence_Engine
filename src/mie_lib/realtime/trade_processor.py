
import asyncio
from datetime import datetime
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Any, Set
import logging

# Configure Logger
logger = logging.getLogger(__name__)

# Constants
AGGREGATION_WINDOW_MS = 50
HISTORY_SIZE = 200

# Enum for Trade Tags
class TradeTag(Enum):
    SWEEP = "SWEEP"
    BLOCK = "BLOCK"
    SPLIT = "SPLIT"
    NORMAL = "NORMAL"

class TradeSide(Enum):
    ASK = "ASK"  # Green / Aggressive Buy
    BID = "BID"  # Red / Aggressive Sell
    MID = "MID"  # White / Neutral

class TradeProcessor:
    """
    Handles Real-Time Aggregation, Tagging, and Persistence of Options Trades.
    
    Usage:
        processor = TradeProcessor()
        
        # In WebSocket Loop:
        if msg.type == QUOTE:
            processor.on_quote(msg)
        elif msg.type == TRADE:
            clean_trade = await processor.on_trade(msg)
            if clean_trade:
                broadcast(clean_trade)
    """
    
    def __init__(self, on_clean_trade_callback):
        """
        Args:
            on_clean_trade_callback: Async function to call with clean trade object.
        """
        self.on_clean_trade = on_clean_trade_callback
        
        # State: {(root, exp, strike, right): {bid: float, ask: float}}
        self.quotes: Dict[tuple, Dict[str, float]] = {}
        
        # Aggregation Buffer: {(root, exp, strike, right): AggregationBucket}
        self.buffer: Dict[tuple, 'AggregationBucket'] = {}
        
        # Persistence
        self.history: deque = deque(maxlen=HISTORY_SIZE)
        
    def on_quote(self, msg: Any):
        """Updates NBBO state."""
        try:
            # Extract Key (Tuple)
            # Quote msg structure: msg.contract, msg.quote
            if not hasattr(msg, 'contract') or not hasattr(msg, 'quote'): return
            
            key = self._get_contract_key(msg.contract)
            if not key: return 
            
            # Fix A: use correct attribute names (bid_price / ask_price, not bid / ask)
            self.quotes[key] = {
                "bid": getattr(msg.quote, 'bid_price', 0.0),
                "ask": getattr(msg.quote, 'ask_price', 0.0)
            }
        except Exception as e:
            logger.error(f"Quote Error: {e}")

    async def on_trade(self, msg: Any):
        """
        Buffers trade. If flush occurs, invokes callback.
        """
        try:
            if not hasattr(msg, 'contract') or not hasattr(msg, 'trade'): return

            key = self._get_contract_key(msg.contract)
            if not key: return 
            
            now_ms = int(datetime.now().timestamp() * 1000)
            
            bucket = self.buffer.get(key)
            if bucket:
                if now_ms - bucket.start_time_ms <= AGGREGATION_WINDOW_MS:
                    bucket.add_trade(msg)
                else:
                    await self._finalize_bucket(bucket)
                    self.buffer[key] = AggregationBucket(msg, now_ms, key)
                    asyncio.create_task(self._delayed_flush(key, now_ms))
            else:
                self.buffer[key] = AggregationBucket(msg, now_ms, key)
                asyncio.create_task(self._delayed_flush(key, now_ms))
                
        except Exception as e:
            logger.error(f"Trade Process Error: {e}")

    async def _delayed_flush(self, key, bucket_id_time):
        await asyncio.sleep(AGGREGATION_WINDOW_MS / 1000.0)
        bucket = self.buffer.get(key)
        if bucket and bucket.start_time_ms == bucket_id_time:
            await self._finalize_bucket(bucket)

    async def _finalize_bucket(self, bucket: 'AggregationBucket'):
        # 1. Aggregate
        total_size = bucket.total_size
        if total_size == 0: return

        avg_price = bucket.total_premium / total_size
        
        # 2. Tagging
        tags = []
        # Fix C: code 95 = INTERMARKET_SWEEP (code 83 = MID_BID_ASK_PRICE — not a sweep)
        is_sweep = any(c in [95, 'INTERMARKET_SWEEP'] for c in bucket.conditions)
        if is_sweep: tags.append(TradeTag.SWEEP.value)
        
        if total_size >= 200 and not is_sweep:
            tags.append(TradeTag.BLOCK.value)
            
        if bucket.count > 1 and len(bucket.exchanges) == 1 and not is_sweep:
            tags.append(TradeTag.SPLIT.value)
            
        # 3. Side — Fix B: condition-code-first, NBBO tick-test fallback
        # Priority 1: OPRA aggressor condition codes (authoritative, when present)
        if 146 in bucket.conditions or 'ASK_AGGRESSOR' in bucket.conditions:
            side = TradeSide.ASK.value   # buyer-initiated
        elif 145 in bucket.conditions or 'BID_AGGRESSOR' in bucket.conditions:
            side = TradeSide.BID.value   # seller-initiated
        else:
            # Priority 2: NBBO tick-test (now works — bid_price/ask_price fixed in on_quote)
            quote = self.quotes.get(bucket.key)
            side = TradeSide.MID.value
            if quote:
                bid, ask = quote['bid'], quote['ask']
                if bid > 0 and ask > 0:
                    if avg_price >= ask:
                        side = TradeSide.ASK.value
                    elif avg_price <= bid:
                        side = TradeSide.BID.value
        
        # 4. Object
        root, exp, strike, right = bucket.key
        clean_obj = {
            "root": root,
            "exp": exp,
            "strike": strike,
            "right": right,
            "price": round(avg_price, 2),
            "size": total_size,
            "side": side,
            "tags": tags,
            "timestamp": bucket.start_time_ms,
            "conditions": list(bucket.conditions),
            "count": bucket.count,
            "type": "TRADE_CLEAN" 
        }
        
        # 5. Persist + debug logging (first 10 trades at startup for spot-check)
        self.history.append(clean_obj)
        if len(self.history) <= 10:
            quote = self.quotes.get(bucket.key, {})
            logger.info(
                f"[TRADE #{len(self.history)}] {root} {right} {strike} exp={exp} "
                f"price={avg_price:.2f} bid={quote.get('bid', 'n/a')} ask={quote.get('ask', 'n/a')} "
                f"conditions={list(bucket.conditions)} side={side} tags={tags}"
            )
        
        # Cleanup
        if bucket.key in self.buffer and self.buffer[bucket.key] == bucket:
             del self.buffer[bucket.key]
             
        # 6. Callback
        if self.on_clean_trade:
             if asyncio.iscoroutinefunction(self.on_clean_trade):
                 await self.on_clean_trade(clean_obj)
             else:
                 self.on_clean_trade(clean_obj)

    def _get_contract_key(self, contract):
        return (contract.root, str(contract.exp), contract.strike, contract.right)
        
class AggregationBucket:
    def __init__(self, first_msg, start_time, key):
        self.key = key
        self.start_time_ms = start_time
        self.total_size = 0
        self.total_premium = 0.0
        self.count = 0
        self.conditions = set()
        self.exchanges = set()
        
        self.add_trade(first_msg)
        
    def add_trade(self, msg):
        self.total_size += msg.trade.size
        self.total_premium += (msg.trade.price * msg.trade.size)
        self.count += 1
        
        # Condition Handling
        # Handling both int (Thetadata enum) and string
        cond = getattr(msg.trade, 'condition', None)
        if cond:
            # If enum
            if hasattr(cond, 'value'): self.conditions.add(cond.value)
            elif hasattr(cond, 'name'): self.conditions.add(cond.name)
            else: self.conditions.add(cond)
            
        # Exchange
        exc = getattr(msg.trade, 'exchange', None)
        if exc: self.exchanges.add(exc)
