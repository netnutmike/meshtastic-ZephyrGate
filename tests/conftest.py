"""
Global pytest configuration and fixtures for ZephyrGate testing.
"""
import asyncio
import os
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock, MagicMock
import sqlite3
import json

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "database": {
            "url": ":memory:",
            "pool_size": 1,
            "echo": False
        },
        "meshtastic": {
            "interfaces": {
                "serial": {
                    "enabled": False,
                    "port": "/dev/ttyUSB0"
                },
                "tcp": {
                    "enabled": False,
                    "host": "localhost",
                    "port": 4403
                },
                "ble": {
                    "enabled": False,
                    "address": None
                }
            },
            "node_id": "!12345678",
            "channel": 0
        },
        "services": {
            "bbs": {"enabled": True},
            "emergency": {"enabled": True},
            "bot": {"enabled": True},
            "weather": {"enabled": False},
            "email": {"enabled": False},
            "web": {"enabled": False}
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }


@pytest.fixture
async def test_database(temp_dir):
    """Create a test SQLite database."""
    db_path = temp_dir / "test.db"
    
    # Create test database schema
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE users (
            node_id TEXT PRIMARY KEY,
            short_name TEXT NOT NULL,
            long_name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            tags TEXT,
            permissions TEXT,
            subscriptions TEXT,
            last_seen DATETIME,
            location_lat REAL,
            location_lon REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # SOS incidents table
    cursor.execute("""
        CREATE TABLE sos_incidents (
            id TEXT PRIMARY KEY,
            incident_type TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            message TEXT,
            location_lat REAL,
            location_lon REAL,
            timestamp DATETIME NOT NULL,
            status TEXT NOT NULL,
            responders TEXT,
            acknowledgers TEXT,
            escalated BOOLEAN DEFAULT FALSE,
            cleared_by TEXT,
            cleared_at DATETIME,
            FOREIGN KEY (sender_id) REFERENCES users (node_id)
        )
    """)
    
    # BBS bulletins table
    cursor.execute("""
        CREATE TABLE bulletins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            unique_id TEXT UNIQUE NOT NULL,
            FOREIGN KEY (sender_id) REFERENCES users (node_id)
        )
    """)
    
    # BBS mail table
    cursor.execute("""
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
            FOREIGN KEY (sender_id) REFERENCES users (node_id),
            FOREIGN KEY (recipient_id) REFERENCES users (node_id)
        )
    """)
    
    # Channel directory table
    cursor.execute("""
        CREATE TABLE channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            frequency TEXT,
            description TEXT,
            added_by TEXT,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (added_by) REFERENCES users (node_id)
        )
    """)
    
    # Checklist table
    cursor.execute("""
        CREATE TABLE checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            action TEXT NOT NULL,
            notes TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES users (node_id)
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield str(db_path)


@pytest.fixture
def sample_users():
    """Provide sample user data for testing."""
    return [
        {
            "node_id": "!12345678",
            "short_name": "TEST1",
            "long_name": "Test User One",
            "email": "test1@example.com",
            "tags": ["responder", "admin"],
            "permissions": {"admin": True, "responder": True},
            "subscriptions": {"weather": True, "alerts": True}
        },
        {
            "node_id": "!87654321",
            "short_name": "TEST2",
            "long_name": "Test User Two",
            "email": "test2@example.com",
            "tags": ["user"],
            "permissions": {"admin": False, "responder": False},
            "subscriptions": {"weather": False, "alerts": True}
        }
    ]


@pytest.fixture
def sample_messages():
    """Provide sample message data for testing."""
    return [
        {
            "id": "msg_001",
            "sender_id": "!12345678",
            "recipient_id": None,
            "channel": 0,
            "content": "Hello mesh network!",
            "timestamp": datetime.utcnow(),
            "message_type": "text",
            "interface_id": "serial_0"
        },
        {
            "id": "msg_002",
            "sender_id": "!87654321",
            "recipient_id": "!12345678",
            "channel": 0,
            "content": "SOS Need help at coordinates 40.7128,-74.0060",
            "timestamp": datetime.utcnow(),
            "message_type": "text",
            "interface_id": "tcp_0"
        }
    ]