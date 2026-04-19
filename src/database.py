"""
Database Module
SQLite database for storing trading history, signals, and metrics
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for trading bot"""
    
    def __init__(self, db_path: str = "data/trading.db"):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def connect(self):
        """Establish database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_database(self):
        """Create database tables if they don't exist"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                size REAL NOT NULL,
                leverage INTEGER NOT NULL,
                pnl REAL,
                pnl_percent REAL,
                status TEXT NOT NULL,
                entry_time REAL,
                exit_time REAL,
                stop_loss REAL,
                take_profit REAL,
                exit_reason TEXT,
                signal_data TEXT
            )
        """)
        
        # Signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence REAL,
                metrics TEXT,
                executed BOOLEAN DEFAULT 0
            )
        """)
        
        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                account_value REAL NOT NULL,
                total_pnl REAL NOT NULL,
                daily_pnl REAL,
                open_positions INTEGER,
                total_trades INTEGER,
                win_rate REAL,
                sharpe_ratio REAL
            )
        """)
        
        # Market data cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                volume_24h REAL,
                social_volume REAL,
                interactions REAL,
                sentiment REAL,
                galaxy_score REAL,
                alt_rank INTEGER
            )
        """)
        
        self.conn.commit()
        logger.info("Database initialized")
    
    def log_trade(self, trade_data: Dict) -> int:
        """
        Log a new trade
        
        Args:
            trade_data: Trade information dictionary
            
        Returns:
            Trade ID
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (
                timestamp, symbol, strategy, side, entry_price, exit_price,
                size, leverage, pnl, pnl_percent, status, entry_time, exit_time,
                stop_loss, take_profit, exit_reason, signal_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get("timestamp", datetime.now().timestamp()),
            trade_data.get("symbol"),
            trade_data.get("strategy"),
            trade_data.get("side"),
            trade_data.get("entry_price"),
            trade_data.get("exit_price"),
            trade_data.get("size"),
            trade_data.get("leverage"),
            trade_data.get("pnl"),
            trade_data.get("pnl_percent"),
            trade_data.get("status", "OPEN"),
            trade_data.get("entry_time"),
            trade_data.get("exit_time"),
            trade_data.get("stop_loss"),
            trade_data.get("take_profit"),
            trade_data.get("exit_reason"),
            json.dumps(trade_data.get("signal_data", {}))
        ))
        
        self.conn.commit()
        trade_id = cursor.lastrowid
        logger.info(f"Logged trade #{trade_id}: {trade_data.get('symbol')} {trade_data.get('side')}")
        return trade_id
    
    def update_trade(self, trade_id: int, updates: Dict):
        """
        Update an existing trade
        
        Args:
            trade_id: Trade ID
            updates: Dictionary of fields to update
        """
        self.connect()
        cursor = self.conn.cursor()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [trade_id]
        
        cursor.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        logger.debug(f"Updated trade #{trade_id}")
    
    def get_open_trades(self) -> List[Dict]:
        """
        Get all open trades
        
        Returns:
            List of open trade dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_time DESC")
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_all_trades(self) -> List[Dict]:
        """
        Get all trades
        
        Returns:
            List of all trade dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_trade_by_id(self, trade_id: int) -> Optional[Dict]:
        """
        Get a trade by ID
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Trade dictionary or None
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        
        return dict(row) if row else None
    
    def log_signal(self, signal_data: Dict) -> int:
        """
        Log a trading signal
        
        Args:
            signal_data: Signal information dictionary
            
        Returns:
            Signal ID
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO signals (
                timestamp, symbol, strategy, signal_type, confidence, metrics, executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_data.get("timestamp", datetime.now().timestamp()),
            signal_data.get("symbol"),
            signal_data.get("strategy"),
            signal_data.get("signal_type"),
            signal_data.get("confidence"),
            json.dumps(signal_data.get("metrics", {})),
            signal_data.get("executed", False)
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def mark_signal_executed(self, signal_id: int):
        """Mark a signal as executed"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("UPDATE signals SET executed = 1 WHERE id = ?", (signal_id,))
        self.conn.commit()
    
    def log_performance(self, perf_data: Dict):
        """
        Log performance metrics
        
        Args:
            perf_data: Performance data dictionary
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO performance (
                timestamp, account_value, total_pnl, daily_pnl, open_positions,
                total_trades, win_rate, sharpe_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perf_data.get("timestamp", datetime.now().timestamp()),
            perf_data.get("account_value"),
            perf_data.get("total_pnl"),
            perf_data.get("daily_pnl"),
            perf_data.get("open_positions"),
            perf_data.get("total_trades"),
            perf_data.get("win_rate"),
            perf_data.get("sharpe_ratio")
        ))
        
        self.conn.commit()
    
    def log_market_data(self, market_data: Dict):
        """
        Log market data snapshot
        
        Args:
            market_data: Market data dictionary
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO market_data (
                timestamp, symbol, price, volume_24h, social_volume,
                interactions, sentiment, galaxy_score, alt_rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_data.get("timestamp", datetime.now().timestamp()),
            market_data.get("symbol"),
            market_data.get("price"),
            market_data.get("volume_24h"),
            market_data.get("social_volume"),
            market_data.get("interactions"),
            market_data.get("sentiment"),
            market_data.get("galaxy_score"),
            market_data.get("alt_rank")
        ))
        
        self.conn.commit()
    
    def get_statistics(self) -> Dict:
        """
        Get trading statistics
        
        Returns:
            Statistics dictionary
        """
        self.connect()
        cursor = self.conn.cursor()
        
        # Total trades
        cursor.execute("SELECT COUNT(*) as total FROM trades")
        total_trades = cursor.fetchone()["total"]
        
        # Closed trades
        cursor.execute("SELECT COUNT(*) as closed FROM trades WHERE status = 'closed'")
        closed_trades = cursor.fetchone()["closed"]
        
        # Winning trades
        cursor.execute("SELECT COUNT(*) as wins FROM trades WHERE status = 'closed' AND pnl > 0")
        winning_trades = cursor.fetchone()["wins"]
        
        # Total PnL
        cursor.execute("SELECT SUM(pnl) as total_pnl FROM trades WHERE status = 'closed'")
        total_pnl = cursor.fetchone()["total_pnl"] or 0
        
        # Win rate
        win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
        
        # Best and worst trade
        cursor.execute("SELECT MAX(pnl) as best, MIN(pnl) as worst FROM trades WHERE status = 'closed'")
        row = cursor.fetchone()
        best_trade = row["best"] or 0
        worst_trade = row["worst"] or 0
        
        return {
            "total_trades": total_trades,
            "closed_trades": closed_trades,
            "open_trades": total_trades - closed_trades,
            "winning_trades": winning_trades,
            "losing_trades": closed_trades - winning_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "best_trade": best_trade,
            "worst_trade": worst_trade
        }
    
    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """
        Get recent trades
        
        Args:
            limit: Number of trades to return
            
        Returns:
            List of trade dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute(f"SELECT * FROM trades ORDER BY timestamp DESC LIMIT {limit}")
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


if __name__ == "__main__":
    # Test the database
    logging.basicConfig(level=logging.INFO)
    
    db = TradingDatabase()
    stats = db.get_statistics()
    print(f"Database statistics: {stats}")
    print("Database module loaded successfully")
