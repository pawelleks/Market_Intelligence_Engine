import sqlite3
import json
import os
import logging
from datetime import datetime
import threading
import pytz

LOG = logging.getLogger(__name__)

# DB stored in persistent data directory
DB_PATH = os.path.abspath(os.path.join(os.getcwd(), "data", "option_flow.db"))
_lock = threading.Lock()

def init_db():
    """Initializes the SQLite database and creates the trades table if it doesn't exist."""
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            # Enable Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT,
                    timestamp TEXT,
                    received_at TEXT,
                    root TEXT,
                    expiry TEXT,
                    strike REAL,
                    right TEXT,
                    trade_size INTEGER,
                    price REAL,
                    value REAL,
                    exchange TEXT,
                    condition TEXT,
                    raw_json TEXT
                )
            """)
            # Add index for session_date to speed up intraday queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_date ON trades(session_date)")
            conn.commit()
            conn.close()
            LOG.info(f"Option Flow DB initialized at {DB_PATH}")
        except Exception as e:
            LOG.error(f"Failed to initialize Option Flow DB: {e}")

def insert_trade(trade_dict: dict):
    """Inserts a single trade record into the database."""
    try:
        # Prepare data for insertion
        raw_json = json.dumps(trade_dict)
        
        # Extract fields with safe defaults
        root = trade_dict.get("root", "")
        expiry = trade_dict.get("exp", "")
        strike = float(trade_dict.get("strike", 0.0))
        right = trade_dict.get("right", "")
        trade_size = int(trade_dict.get("size", trade_dict.get("trade_size", 0)))
        price = float(trade_dict.get("price", 0.0))
        value = float(trade_dict.get("value", trade_dict.get("val", 0.0)))
        exchange = trade_dict.get("exchange", "")
        
        # Store tags/condition as JSON list
        tags = trade_dict.get("tags", [])
        condition = json.dumps(tags)
        
        # Timestamps
        received_at = datetime.now(pytz.UTC).isoformat()
        
        # Use existing timestamp if available, otherwise use reception time
        timestamp = trade_dict.get("timestamp")
        if not timestamp:
            timestamp = received_at
            
        # Session Date (ET YYYY-MM-DD) for easy filtering
        et_tz = pytz.timezone("America/New_York")
        session_date = datetime.now(et_tz).strftime("%Y-%m-%d")

        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    session_date, timestamp, received_at, root, expiry, strike,
                    right, trade_size, price, value, exchange, condition, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date, timestamp, received_at, root, expiry, strike,
                right, trade_size, price, value, exchange, condition, raw_json
            ))
            conn.commit()
            conn.close()
    except Exception as e:
        # Log but don't crash the streamer
        LOG.error(f"Failed to insert trade into SQLite: {e}")

def get_trades_since_open(date_str: str = None):
    """
    Returns all trades from a specific date. 
    Defaults to today's current session date in ET.
    """
    if not date_str:
        et_tz = pytz.timezone("America/New_York")
        date_str = datetime.now(et_tz).strftime("%Y-%m-%d")
        
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM trades WHERE session_date = ? ORDER BY id ASC", (date_str,))
            rows = cursor.fetchall()
            conn.close()
            
            # Reconstruct original trade objects from raw_json
            trades = []
            for row in rows:
                try:
                    trades.append(json.loads(row["raw_json"]))
                except:
                    continue
            return trades
    except Exception as e:
        LOG.error(f"Failed to query trades from SQLite: {e}")
        return []

def get_available_dates():
    """Returns a list of distinct session dates present in the database."""
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT session_date FROM trades ORDER BY session_date DESC")
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]
    except Exception as e:
        LOG.error(f"Failed to query available dates from SQLite: {e}")
        return []

# Self-initialize on first import
init_db()
