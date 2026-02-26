import sqlite3
import os
import logging
import threading
from typing import List, Dict, Any, Optional

LOG = logging.getLogger(__name__)

# Follow existing convention from option_flow.db
DB_PATH = os.path.abspath(os.path.join(os.getcwd(), "data", "volume_regime_signals.db"))
_lock = threading.Lock()

def init_db():
    """Initializes the SQLite database and creates the volume_regime_signals table."""
    with _lock:
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            
            conn = sqlite3.connect(DB_PATH)
            # Enable Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS volume_regime_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    candle_time INTEGER NOT NULL,
                    recorded_at INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    ud_vol_ratio REAL,
                    price_change_20d REAL,
                    volume_vs_avg REAL,
                    current_price REAL,
                    UNIQUE(ticker, timeframe, candle_time)
                )
            """)
            
            # Add indexes for fast lookups and historical time series slicing
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vrs_ticker_tf ON volume_regime_signals(ticker, timeframe)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vrs_candle_time ON volume_regime_signals(candle_time)")
            
            conn.commit()
            conn.close()
            LOG.info(f"Volume Regime Signals DB initialized at {DB_PATH}")
        except Exception as e:
            LOG.error(f"Failed to initialize Volume Regime Signals DB: {e}")

def insert_signal(signal: Dict[str, Any]):
    """Inserts a single signal record safely using INSERT OR IGNORE to prevent duplicates."""
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO volume_regime_signals (
                    ticker, timeframe, candle_time, recorded_at, state, 
                    ud_vol_ratio, price_change_20d, volume_vs_avg, current_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal["ticker"],
                signal["timeframe"],
                signal["candle_time"],
                signal["recorded_at"],
                signal["state"],
                signal.get("ud_vol_ratio"),
                signal.get("price_change_20d"),
                signal.get("volume_vs_avg"),
                signal.get("current_price")
            ))
            conn.commit()
            conn.close()
    except Exception as e:
        LOG.error(f"Failed to insert volume regime signal into SQLite: {e}")

def bulk_insert(signals: List[Dict[str, Any]]):
    """Inserts multiple signal records efficiently using executemany."""
    if not signals:
        return
        
    try:
        data = [
            (
                s["ticker"], s["timeframe"], s["candle_time"], s["recorded_at"],
                s["state"], s.get("ud_vol_ratio"), s.get("price_change_20d"),
                s.get("volume_vs_avg"), s.get("current_price")
            )
            for s in signals
        ]
        
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR IGNORE INTO volume_regime_signals (
                    ticker, timeframe, candle_time, recorded_at, state, 
                    ud_vol_ratio, price_change_20d, volume_vs_avg, current_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()
            conn.close()
    except Exception as e:
        LOG.error(f"Failed to bulk insert volume regime signals into SQLite: {e}")

def get_signals(ticker: str, timeframe: str, start_time: Optional[int] = None, end_time: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
    """Query stored volume regime signals by ticker, timeframe, and optional date range."""
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM volume_regime_signals WHERE ticker = ? AND timeframe = ?"
            params = [ticker, timeframe]
            
            if start_time:
                query += " AND candle_time >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND candle_time <= ?"
                params.append(end_time)
                
            query += " ORDER BY candle_time ASC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        LOG.error(f"Failed to query volume regime signals from SQLite: {e}")
        return []

def get_latest_candle_time(ticker: str, timeframe: str) -> Optional[int]:
    """Returns the single most recent candle_time for the given ticker/timeframe to support backfill resume."""
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            query = "SELECT MAX(candle_time) FROM volume_regime_signals WHERE ticker = ? AND timeframe = ?"
            cursor.execute(query, (ticker, timeframe))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] is not None:
                return int(row[0])
            return None
    except Exception as e:
        LOG.error(f"Failed to query latest candle_time from SQLite: {e}")
        return None

def get_summary() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Returns a coverage summary grouped by ticker and timeframe.
    {
      "SPY": {
         "1d": {"count": 252, "from": "2024-01-02", "to": "2024-12-31"},
         ...
      }
    }
    """
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticker, timeframe, COUNT(*) as count, 
                       MIN(candle_time) as min_time, MAX(candle_time) as max_time
                FROM volume_regime_signals
                GROUP BY ticker, timeframe
            """)
            rows = cursor.fetchall()
            conn.close()
            
            from datetime import datetime
            import pytz
            et_tz = pytz.timezone("America/New_York")
            
            summary = {}
            for row in rows:
                ticker = row["ticker"]
                tf = row["timeframe"]
                
                if ticker not in summary:
                    summary[ticker] = {}
                    
                min_dt = datetime.fromtimestamp(row["min_time"], tz=et_tz).strftime("%Y-%m-%d") if row["min_time"] else None
                max_dt = datetime.fromtimestamp(row["max_time"], tz=et_tz).strftime("%Y-%m-%d") if row["max_time"] else None
                
                summary[ticker][tf] = {
                    "count": row["count"],
                    "from": min_dt,
                    "to": max_dt
                }
            return summary
    except Exception as e:
        LOG.error(f"Failed to get DB summary: {e}")
        return {}

def get_db_health_stats() -> Dict[str, Any]:
    """Returns high-level health stats for the database file."""
    try:
        size_mb = 0
        if os.path.exists(DB_PATH):
            size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
            
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), MIN(candle_time), MAX(candle_time) FROM volume_regime_signals")
            row = cursor.fetchone()
            conn.close()
            
            total_count = row[0] if row else 0
            min_time = row[1] if row and row[1] else None
            max_time = row[2] if row and row[2] else None
            
            from datetime import datetime
            import pytz
            et_tz = pytz.timezone("America/New_York")
            min_dt = datetime.fromtimestamp(min_time, tz=et_tz).isoformat() if min_time else None
            max_dt = datetime.fromtimestamp(max_time, tz=et_tz).isoformat() if max_time else None
            
            return {
                "file_size_mb": round(size_mb, 2),
                "total_signals": total_count,
                "oldest_signal": min_dt,
                "newest_signal": max_dt
            }
    except Exception:
        return {"file_size_mb": 0, "total_signals": 0, "oldest_signal": None, "newest_signal": None}
