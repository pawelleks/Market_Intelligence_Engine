import asyncio
import logging
import time
import pandas as pd
from datetime import datetime

from mie_lib.analysis.volume_regime import compute_volume_metrics, classify_market_state
from mie_lib.api.routers.volume_regime_router import fetch_thetadata_ohlc, is_market_open_now, TIMEFRAMES
from mie_lib.db.volume_regime_db import insert_signal

LOG = logging.getLogger(__name__)

TRACKED_TICKERS = ["SPY", "QQQ", "IWM", "AAPL", "TSLA"]

# We redefine the intervals in seconds for the asyncio sleep loop
POLL_INTERVALS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 3600,  # hourly polling for the daily candle
}

class VolumeRegimeRecorder:
    def __init__(self):
        self._running = False
        self._task = None

    async def start(self):
        if self._running:
            return
            
        self._running = True
        LOG.info("Starting Volume Regime Recorder background task...")
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        if not self._running:
            return
            
        LOG.info("Stopping Volume Regime Recorder...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        """
        Main loop schedules tasks for each timeframe and ticker based on their unique polling intervals.
        """
        # Dictionary tracking the last time we polled a specific timeframe
        last_poll_time = {tf: 0 for tf in POLL_INTERVALS.keys()}
        
        while self._running:
            try:
                if not is_market_open_now():
                    # Sleep lightly and wait for market open
                    await asyncio.sleep(60)
                    continue

                now = time.time()
                tasks = []
                
                for tf, interval_sec in POLL_INTERVALS.items():
                    # Check if it's time to poll this timeframe
                    if now - last_poll_time[tf] >= interval_sec:
                        last_poll_time[tf] = now
                        ivl = TIMEFRAMES[tf]
                        # 15 days is plenty for 25 candles on intraday; 75 for daily
                        days_back = 75 if tf == "1d" else 15 
                        
                        for idx, ticker in enumerate(TRACKED_TICKERS):
                            tasks.append(self._poll_ticker_tf(ticker, tf, ivl, days_back, idx))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check schedule every 10 seconds
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOG.error(f"Error in Volume Regime Recorder loop: {e}")
                await asyncio.sleep(60)

    async def _poll_ticker_tf(self, ticker: str, tf: str, ivl: int, days_back: int, stagger_idx: int):
        """Polls a single ticker+timeframe, computes metrics, and inserts signal if new."""
        # Optional stagger to spread out Thetadata requests
        if stagger_idx > 0:
            await asyncio.sleep(stagger_idx * 0.2)
            
        try:
            df = await fetch_thetadata_ohlc(ticker, ivl, days_back=days_back)
            if df.empty or len(df) < 20:
                return

            # Keep only the tail to optimize computation (25 candles is enough to get the 20d moving averages)
            # Actually, compute_volume_metrics needs at least 20 historical points. 
            # We fetch 15 days which guarantees we have plenty. We can just process it all and take the last row.
            df = compute_volume_metrics(df)
            
            last_row = df.iloc[-1]
            if pd.isna(last_row.get("vol_mean_20d")) or pd.isna(last_row.get("ud_vol_ratio")):
                return  # Data not seasoned enough

            state = classify_market_state(last_row)
            candle_time = int(last_row.get("time", 0))
            
            # Skip invalid timestamps
            if candle_time <= 0:
                return
                
            vol_mean = last_row.get("vol_mean_20d", 1)
            if vol_mean == 0:
                vol_mean = 1
                
            ud_vol_ratio = float(last_row.get("ud_vol_ratio", 1.0))
            price_change_20d = float(last_row.get("price_change_20d", 0))
            volume_vs_avg = float(last_row.get("volume", 0) / vol_mean)
            current_price = float(last_row.get("close", 0))

            signal = {
                "ticker": ticker,
                "timeframe": tf,
                "candle_time": candle_time,
                "recorded_at": int(time.time()),
                "state": state,
                "ud_vol_ratio": ud_vol_ratio,
                "price_change_20d": price_change_20d,
                "volume_vs_avg": volume_vs_avg,
                "current_price": current_price
            }
            
            # Will safely IGNORE if this candle_time was already recorded for this ticker/tf
            insert_signal(signal)
            LOG.debug(f"Signal recorded: {ticker} {tf} {state} ratio={ud_vol_ratio:.2f}")
            
        except Exception as e:
            LOG.error(f"Volume Regime Recorder failed for {ticker} {tf}: {e}")
