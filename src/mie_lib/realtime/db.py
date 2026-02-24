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
            # Add indexes for fast intraday queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_date ON trades(session_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_value ON trades(session_date, value)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_root ON trades(session_date, root)")
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

def get_trades_since_open(date_str: str = None, min_value: float = 0,
                          tickers: list = None, limit: int = 2000):
    """
    Returns trades from a specific date, filtered at the SQL level.
    Defaults to today's current session date in ET.

    Args:
        date_str: Session date (YYYY-MM-DD). Defaults to today ET.
        min_value: Minimum trade premium ($). Filters at SQL level.
        tickers: List of root symbols to include. None = all.
        limit: Max rows returned (most recent first, reversed to ASC).
    """
    if not date_str:
        et_tz = pytz.timezone("America/New_York")
        date_str = datetime.now(et_tz).strftime("%Y-%m-%d")

    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT id, raw_json FROM trades WHERE session_date = ?"
            params = [date_str]

            if min_value > 0:
                query += " AND value >= ?"
                params.append(min_value)

            if tickers:
                placeholders = ",".join("?" * len(tickers))
                query += f" AND root IN ({placeholders})"
                params.extend(tickers)

            # Get most recent N rows, then reverse to chronological order
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Reconstruct and reverse to chronological (oldest first)
            trades = []
            for row in reversed(rows):
                try:
                    trade = json.loads(row["raw_json"])
                    trade["_db_id"] = row["id"]
                    trades.append(trade)
                except:
                    continue
            return trades
    except Exception as e:
        LOG.error(f"Failed to query trades from SQLite: {e}")
        return []

def get_trades_page(before_id: int, min_value: float = 0,
                    ticker: str = None, limit: int = 100):
    """
    Cursor-based pagination: returns trades with id < before_id.
    Returns trades in reverse chronological order (newest first).
    """
    et_tz = pytz.timezone("America/New_York")
    date_str = datetime.now(et_tz).strftime("%Y-%m-%d")

    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT id, raw_json FROM trades WHERE session_date = ? AND id < ?"
            params = [date_str, before_id]

            if min_value > 0:
                query += " AND value >= ?"
                params.append(min_value)

            if ticker:
                query += " AND root = ?"
                params.append(ticker)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            trades = []
            for row in rows:
                try:
                    trade = json.loads(row["raw_json"])
                    trade["_db_id"] = row["id"]
                    trades.append(trade)
                except:
                    continue
            return trades
    except Exception as e:
        LOG.error(f"Failed to query trades page from SQLite: {e}")
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
