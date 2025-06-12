#!/usr/bin/env python3
"""
Database Connection Manager

Centralized database connection handling to avoid locking issues
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional

class DatabaseManager:
    """Thread-safe database connection manager"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialized = False
        
    def initialize_database(self):
        """Initialize database with proper settings"""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                conn = sqlite3.connect(self.db_path, timeout=60.0)
                # Enable WAL mode and other performance settings
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL") 
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=memory")
                conn.execute("PRAGMA mmap_size=268435456")  # 256MB
                conn.commit()
                conn.close()
                    
                self._initialized = True
                print("✅ Database initialized with optimized settings")
                
            except sqlite3.Error as e:
                print(f"❌ Database initialization failed: {e}")
                raise
    
    @contextmanager
    def get_connection(self, retry_count: int = 3):
        """Get a database connection with retry logic"""
        if not self._initialized:
            self.initialize_database()
            
        for attempt in range(retry_count):
            conn = None
            try:
                conn = sqlite3.connect(self.db_path, timeout=60.0)
                conn.row_factory = sqlite3.Row
                
                # Apply connection-specific settings
                conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
                
                yield conn
                break  # Success, exit retry loop
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < retry_count - 1:
                    print(f"   ⏳ Database locked, retrying in {attempt + 1}s... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(attempt + 1)  # Exponential backoff
                    continue
                else:
                    raise
            except Exception as e:
                raise
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass

# Global database manager instance
_db_manager: Optional[DatabaseManager] = None

def get_db_manager(db_path: str = None) -> DatabaseManager:
    """Get the global database manager instance"""
    global _db_manager
    
    if _db_manager is None:
        if db_path is None:
            db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
        _db_manager = DatabaseManager(db_path)
        
    return _db_manager 