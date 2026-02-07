"""
Database Infrastructure for ZephyrGate

Provides SQLite database management, connection pooling, migrations,
and transaction management for all ZephyrGate services.
"""

import sqlite3
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class Migration:
    """Database migration definition"""
    version: int
    name: str
    sql: str
    rollback_sql: Optional[str] = None


class DatabaseError(Exception):
    """Database-related errors"""
    pass


class ConnectionPool:
    """Simple SQLite connection pool"""
    
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = database_path
        self.max_connections = max_connections
        self.connections = []
        self.in_use = set()
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool"""
        with self.lock:
            # Try to reuse an existing connection
            for conn in self.connections:
                if conn not in self.in_use:
                    self.in_use.add(conn)
                    return conn
            
            # Create new connection if under limit
            if len(self.connections) < self.max_connections:
                conn = sqlite3.connect(
                    self.database_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                self.connections.append(conn)
                self.in_use.add(conn)
                return conn
            
            # Wait for a connection to become available
            raise DatabaseError("Connection pool exhausted")
    
    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool"""
        with self.lock:
            if conn in self.in_use:
                self.in_use.remove(conn)
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            for conn in self.connections:
                try:
                    conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing connection: {e}")
            self.connections.clear()
            self.in_use.clear()


class DatabaseManager:
    """
    Manages SQLite database operations, migrations, and connection pooling
    """
    
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = Path(database_path)
        self.pool = ConnectionPool(str(self.database_path), max_connections)
        self.logger = logging.getLogger(__name__)
        self.migrations = self._get_migrations()
        
        # Ensure database directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._initialize_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.return_connection(conn)
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
    
    def _initialize_database(self):
        """Initialize database with schema and migrations"""
        self.logger.info(f"Initializing database at {self.database_path}")
        
        # Create migrations table if it doesn't exist
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        
        # Run migrations
        self._run_migrations()
    
    def _get_migrations(self) -> List[Migration]:
        """Get all database migrations"""
        return [
            Migration(
                version=1,
                name="initial_schema",
                sql="""
                -- User profiles and permissions
                CREATE TABLE users (
                    node_id TEXT PRIMARY KEY,
                    short_name TEXT NOT NULL,
                    long_name TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    tags TEXT, -- JSON array
                    permissions TEXT, -- JSON object
                    subscriptions TEXT, -- JSON object
                    last_seen DATETIME,
                    location_lat REAL,
                    location_lon REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- SOS incidents and emergency response
                CREATE TABLE sos_incidents (
                    id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    message TEXT,
                    location_lat REAL,
                    location_lon REAL,
                    timestamp DATETIME NOT NULL,
                    status TEXT NOT NULL,
                    responders TEXT, -- JSON array
                    acknowledgers TEXT, -- JSON array
                    escalated BOOLEAN DEFAULT FALSE,
                    cleared_by TEXT,
                    cleared_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (node_id)
                );
                
                -- BBS bulletins
                CREATE TABLE bulletins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    unique_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (node_id)
                );
                
                -- BBS mail
                CREATE TABLE mail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    read_at DATETIME,
                    unique_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (node_id),
                    FOREIGN KEY (recipient_id) REFERENCES users (node_id)
                );
                
                -- Channel directory
                CREATE TABLE channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    frequency TEXT,
                    description TEXT,
                    added_by TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (added_by) REFERENCES users (node_id)
                );
                
                -- Check-in/check-out tracking
                CREATE TABLE checklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL, -- 'checkin' or 'checkout'
                    notes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (node_id) REFERENCES users (node_id)
                );
                
                -- Message history
                CREATE TABLE message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT,
                    sender_id TEXT NOT NULL,
                    recipient_id TEXT,
                    channel INTEGER,
                    content TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    interface_id TEXT,
                    hop_count INTEGER DEFAULT 0,
                    snr REAL,
                    rssi REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (node_id)
                );
                
                -- System configuration
                CREATE TABLE system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes for better performance
                CREATE INDEX idx_users_last_seen ON users (last_seen);
                CREATE INDEX idx_sos_incidents_status ON sos_incidents (status);
                CREATE INDEX idx_sos_incidents_timestamp ON sos_incidents (timestamp);
                CREATE INDEX idx_bulletins_board ON bulletins (board);
                CREATE INDEX idx_bulletins_timestamp ON bulletins (timestamp);
                CREATE INDEX idx_mail_recipient ON mail (recipient_id);
                CREATE INDEX idx_mail_read_at ON mail (read_at);
                CREATE INDEX idx_message_history_timestamp ON message_history (timestamp);
                CREATE INDEX idx_message_history_sender ON message_history (sender_id);
                """
            ),
            Migration(
                version=2,
                name="add_game_sessions",
                sql="""
                -- Game sessions for interactive games
                CREATE TABLE game_sessions (
                    id TEXT PRIMARY KEY,
                    game_type TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    state TEXT NOT NULL, -- JSON game state
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    FOREIGN KEY (player_id) REFERENCES users (node_id)
                );
                
                CREATE INDEX idx_game_sessions_player ON game_sessions (player_id);
                CREATE INDEX idx_game_sessions_expires ON game_sessions (expires_at);
                """
            ),
            Migration(
                version=3,
                name="add_weather_cache",
                sql="""
                -- Weather data cache
                CREATE TABLE weather_cache (
                    location_key TEXT PRIMARY KEY,
                    data TEXT NOT NULL, -- JSON weather data
                    cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL
                );
                
                -- Alert history
                CREATE TABLE alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    location_lat REAL,
                    location_lon REAL,
                    severity TEXT,
                    issued_at DATETIME NOT NULL,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX idx_weather_cache_expires ON weather_cache (expires_at);
                CREATE INDEX idx_alert_history_issued ON alert_history (issued_at);
                CREATE INDEX idx_alert_history_type ON alert_history (alert_type);
                """
            ),
            Migration(
                version=4,
                name="enhance_bbs_schema",
                sql="""
                -- Add additional fields to channels table
                ALTER TABLE channels ADD COLUMN channel_type TEXT DEFAULT 'other';
                ALTER TABLE channels ADD COLUMN location TEXT DEFAULT '';
                ALTER TABLE channels ADD COLUMN coverage_area TEXT DEFAULT '';
                ALTER TABLE channels ADD COLUMN tone TEXT DEFAULT '';
                ALTER TABLE channels ADD COLUMN offset TEXT DEFAULT '';
                ALTER TABLE channels ADD COLUMN verified BOOLEAN DEFAULT FALSE;
                ALTER TABLE channels ADD COLUMN active BOOLEAN DEFAULT TRUE;
                
                -- JS8Call messages table
                CREATE TABLE js8call_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    priority TEXT DEFAULT 'normal',
                    forwarded_to_mesh BOOLEAN DEFAULT FALSE,
                    unique_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- BBS sessions for menu state management
                CREATE TABLE bbs_sessions (
                    user_id TEXT PRIMARY KEY,
                    current_menu TEXT DEFAULT 'main',
                    menu_stack TEXT DEFAULT '[]', -- JSON array
                    context TEXT DEFAULT '{}', -- JSON object
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (node_id)
                );
                
                -- BBS synchronization tracking
                CREATE TABLE bbs_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_node TEXT NOT NULL,
                    sync_type TEXT NOT NULL, -- 'bulletin', 'mail', 'channel'
                    message_id TEXT NOT NULL,
                    unique_id TEXT NOT NULL,
                    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'success'
                );
                
                -- Create indexes for better performance
                CREATE INDEX idx_js8call_timestamp ON js8call_messages (timestamp);
                CREATE INDEX idx_js8call_priority ON js8call_messages (priority);
                CREATE INDEX idx_js8call_forwarded ON js8call_messages (forwarded_to_mesh);
                CREATE INDEX idx_bbs_sessions_activity ON bbs_sessions (last_activity);
                CREATE INDEX idx_bbs_sync_peer ON bbs_sync_log (peer_node);
                CREATE INDEX idx_bbs_sync_type ON bbs_sync_log (sync_type);
                """
            ),
            
            Migration(
                version=6,
                name="add_node_hardware_tracking",
                sql="""
                -- Node hardware information for statistics and wall of shame
                CREATE TABLE node_hardware (
                    node_id TEXT PRIMARY KEY,
                    hardware_model TEXT,
                    firmware_version TEXT,
                    battery_level INTEGER, -- 0-100 percentage
                    voltage REAL,
                    channel_utilization REAL,
                    air_util_tx REAL,
                    uptime_seconds INTEGER,
                    role TEXT, -- CLIENT, CLIENT_MUTE, ROUTER, ROUTER_CLIENT, REPEATER, TRACKER, SENSOR, TAK, CLIENT_HIDDEN, LOST_AND_FOUND, TAK_TRACKER
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (node_id) REFERENCES users (node_id)
                );
                
                -- Fortune messages for the fortune system
                CREATE TABLE fortunes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    added_by TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1
                );
                
                -- Create indexes for better performance
                CREATE INDEX idx_node_hardware_battery ON node_hardware (battery_level);
                CREATE INDEX idx_node_hardware_role ON node_hardware (role);
                CREATE INDEX idx_node_hardware_updated ON node_hardware (last_updated);
                CREATE INDEX idx_fortunes_active ON fortunes (active);
                CREATE INDEX idx_fortunes_category ON fortunes (category);
                """
            ),
            Migration(
                version=7,
                name="add_plugin_storage",
                sql="""
                -- Plugin key-value storage with TTL support
                CREATE TABLE plugin_storage (
                    plugin_name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (plugin_name, key)
                );
                
                -- Create indexes for better performance
                CREATE INDEX idx_plugin_storage_expires ON plugin_storage (expires_at);
                CREATE INDEX idx_plugin_storage_plugin ON plugin_storage (plugin_name);
                """
            ),
            Migration(
                version=8,
                name="add_node_tracking_fields",
                sql="""
                -- Add node tracking fields to users table
                ALTER TABLE users ADD COLUMN altitude REAL;
                ALTER TABLE users ADD COLUMN battery_level INTEGER;
                ALTER TABLE users ADD COLUMN voltage REAL;
                ALTER TABLE users ADD COLUMN snr REAL;
                ALTER TABLE users ADD COLUMN rssi REAL;
                ALTER TABLE users ADD COLUMN hop_count INTEGER;
                ALTER TABLE users ADD COLUMN hardware_model TEXT;
                ALTER TABLE users ADD COLUMN firmware_version TEXT;
                ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'CLIENT';
                
                -- Create index for last_seen to improve stats queries
                CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users (last_seen);
                """
            )
        ]
    
    def _run_migrations(self):
        """Run pending database migrations"""
        with self.get_connection() as conn:
            # Get current migration version
            cursor = conn.execute("SELECT MAX(version) FROM migrations")
            result = cursor.fetchone()
            current_version = result[0] if result[0] is not None else 0
            
            # Run pending migrations
            for migration in self.migrations:
                if migration.version > current_version:
                    self.logger.info(f"Running migration {migration.version}: {migration.name}")
                    
                    try:
                        # Execute migration SQL
                        conn.executescript(migration.sql)
                        
                        # Record migration
                        conn.execute(
                            "INSERT INTO migrations (version, name) VALUES (?, ?)",
                            (migration.version, migration.name)
                        )
                        
                        conn.commit()
                        self.logger.info(f"Migration {migration.version} completed successfully")
                        
                    except Exception as e:
                        conn.rollback()
                        self.logger.error(f"Migration {migration.version} failed: {e}")
                        raise DatabaseError(f"Migration failed: {e}")
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """Create a backup of the database"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.database_path}.backup_{timestamp}"
        
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self.get_connection() as conn:
            with sqlite3.connect(str(backup_path)) as backup_conn:
                conn.backup(backup_conn)
        
        self.logger.info(f"Database backed up to {backup_path}")
        return str(backup_path)
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute a query with multiple parameter sets"""
        with self.transaction() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
    
    def get_user(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get user by node ID"""
        rows = self.execute_query(
            "SELECT * FROM users WHERE node_id = ?",
            (node_id,)
        )
        if rows:
            row = rows[0]
            user = dict(row)
            # Parse JSON fields
            user['tags'] = json.loads(user['tags']) if user['tags'] else []
            user['permissions'] = json.loads(user['permissions']) if user['permissions'] else {}
            user['subscriptions'] = json.loads(user['subscriptions']) if user['subscriptions'] else {}
            return user
        return None
    
    def upsert_user(self, user_data: Dict[str, Any]) -> None:
        """Insert or update user data"""
        # Convert JSON fields to strings
        user_data = user_data.copy()
        if 'tags' in user_data:
            user_data['tags'] = json.dumps(user_data['tags'])
        if 'permissions' in user_data:
            user_data['permissions'] = json.dumps(user_data['permissions'])
        if 'subscriptions' in user_data:
            user_data['subscriptions'] = json.dumps(user_data['subscriptions'])
        
        # Add updated_at timestamp
        user_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Build upsert query
        columns = list(user_data.keys())
        placeholders = ', '.join(['?' for _ in columns])
        update_clause = ', '.join([f"{col} = excluded.{col}" for col in columns if col != 'node_id'])
        
        query = f"""
            INSERT INTO users ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(node_id) DO UPDATE SET {update_clause}
        """
        
        self.execute_update(query, tuple(user_data.values()))
    
    def cleanup_expired_data(self) -> None:
        """Clean up expired data from the database"""
        current_time = datetime.utcnow().isoformat()
        
        with self.transaction() as conn:
            # Clean up expired game sessions
            conn.execute(
                "DELETE FROM game_sessions WHERE expires_at < ?",
                (current_time,)
            )
            
            # Clean up expired weather cache
            conn.execute(
                "DELETE FROM weather_cache WHERE expires_at < ?",
                (current_time,)
            )
            
            # Clean up old message history (keep last 30 days)
            from datetime import timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            conn.execute(
                "DELETE FROM message_history WHERE created_at < ?",
                (cutoff_date,)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}
        
        tables = [
            'users', 'sos_incidents', 'bulletins', 'mail', 'channels',
            'checklist', 'message_history', 'game_sessions', 'weather_cache',
            'alert_history'
        ]
        
        for table in tables:
            try:
                rows = self.execute_query(f"SELECT COUNT(*) FROM {table}")
                stats[table] = rows[0][0] if rows else 0
            except Exception:
                stats[table] = 0
        
        # Database file size
        if self.database_path.exists():
            stats['database_size_bytes'] = self.database_path.stat().st_size
        else:
            stats['database_size_bytes'] = 0
        
        return stats
    
    def close(self):
        """Close all database connections"""
        self.pool.close_all()


# Global database manager instance (will be initialized by the application)
db_manager: Optional[DatabaseManager] = None


def initialize_database(database_path: str, max_connections: int = 10) -> DatabaseManager:
    """Initialize the global database manager"""
    global db_manager
    db_manager = DatabaseManager(database_path, max_connections)
    return db_manager


def get_database() -> DatabaseManager:
    """Get the global database manager instance"""
    if db_manager is None:
        raise DatabaseError("Database not initialized. Call initialize_database() first.")
    return db_manager