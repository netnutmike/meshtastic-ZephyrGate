"""
Base test classes for ZephyrGate testing.
"""
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import sqlite3
import json

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from tests.mocks.meshtastic_mocks import MockMeshtasticInterface
from tests.mocks.external_service_mocks import (
    MockWeatherService, MockEmailService, MockAIService, 
    MockRedisService, MockHTTPClient
)


class BaseTestCase:
    """Base class for all test cases."""
    
    def setup_method(self):
        """Set up test method."""
        self.temp_files = []
        self.mock_patches = []
    
    def teardown_method(self):
        """Clean up after test method."""
        # Clean up temporary files
        for temp_file in self.temp_files:
            if temp_file.exists():
                temp_file.unlink()
        
        # Stop all mock patches
        for patch_obj in self.mock_patches:
            patch_obj.stop()
    
    def create_temp_file(self, content: str = "", suffix: str = ".tmp") -> Path:
        """Create a temporary file for testing."""
        temp_file = Path(tempfile.mktemp(suffix=suffix))
        temp_file.write_text(content)
        self.temp_files.append(temp_file)
        return temp_file
    
    def add_patch(self, target: str, **kwargs) -> Mock:
        """Add a mock patch that will be automatically cleaned up."""
        patch_obj = patch(target, **kwargs)
        mock_obj = patch_obj.start()
        self.mock_patches.append(patch_obj)
        return mock_obj


class AsyncTestCase(BaseTestCase):
    """Base class for async test cases."""
    
    def setup_async(self, event_loop=None):
        """Set up async test environment."""
        import asyncio
        self.loop = event_loop or asyncio.get_event_loop()
    
    # Add pytest fixture only if pytest is available
    if PYTEST_AVAILABLE:
        import pytest
        
        @pytest.fixture(autouse=True)
        def _setup_async_fixture(self, event_loop):
            """Set up async test environment (pytest fixture)."""
            self.setup_async(event_loop)
    
    async def wait_for_condition(self, condition_func, timeout: float = 1.0, 
                                interval: float = 0.1) -> bool:
        """Wait for a condition to become true."""
        start_time = self.loop.time()
        while self.loop.time() - start_time < timeout:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        return False


class DatabaseTestCase(BaseTestCase):
    """Base class for database-related tests."""
    
    def setup_method(self):
        """Set up database test environment."""
        super().setup_method()
        self.db_path = None
        self.db_connection = None
    
    def teardown_method(self):
        """Clean up database test environment."""
        if self.db_connection:
            self.db_connection.close()
        if self.db_path and Path(self.db_path).exists():
            Path(self.db_path).unlink()
        super().teardown_method()
    
    def create_test_database(self) -> str:
        """Create a test database with schema."""
        temp_db = tempfile.mktemp(suffix=".db")
        self.db_path = temp_db
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Create test schema (same as in conftest.py)
        schema_sql = [
            """CREATE TABLE users (
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
            )""",
            """CREATE TABLE sos_incidents (
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
            )""",
            """CREATE TABLE bulletins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                unique_id TEXT UNIQUE NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users (node_id)
            )""",
            """CREATE TABLE mail (
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
            )""",
            """CREATE TABLE channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                frequency TEXT,
                description TEXT,
                added_by TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (added_by) REFERENCES users (node_id)
            )""",
            """CREATE TABLE checklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                action TEXT NOT NULL,
                notes TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES users (node_id)
            )"""
        ]
        
        for sql in schema_sql:
            cursor.execute(sql)
        
        conn.commit()
        self.db_connection = conn
        return temp_db
    
    def insert_test_data(self, table: str, data: List[Dict[str, Any]]):
        """Insert test data into a table."""
        if not self.db_connection:
            raise RuntimeError("Database not initialized")
        
        cursor = self.db_connection.cursor()
        
        for row in data:
            columns = list(row.keys())
            placeholders = ["?" for _ in columns]
            values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
            
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
        
        self.db_connection.commit()


class MeshtasticTestCase(AsyncTestCase):
    """Base class for Meshtastic-related tests."""
    
    def setup_method(self):
        """Set up Meshtastic test environment."""
        super().setup_method()
        self.mock_interfaces = {}
        self.message_history = []
    
    def create_mock_interface(self, interface_id: str = "test_interface", 
                            interface_type: str = "serial", **kwargs) -> MockMeshtasticInterface:
        """Create a mock Meshtastic interface."""
        interface = MockMeshtasticInterface(interface_type, **kwargs)
        self.mock_interfaces[interface_id] = interface
        
        # Track messages for testing
        original_send = interface.send_message
        async def tracked_send(*args, **kwargs):
            result = await original_send(*args, **kwargs)
            self.message_history.append(("sent", args, kwargs))
            return result
        interface.send_message = tracked_send
        
        return interface
    
    async def simulate_message_received(self, interface_id: str, text: str, 
                                      sender: str = "!87654321", **kwargs):
        """Simulate receiving a message on an interface."""
        if interface_id not in self.mock_interfaces:
            raise ValueError(f"Interface {interface_id} not found")
        
        interface = self.mock_interfaces[interface_id]
        await interface.simulate_received_message(text, sender, **kwargs)
        self.message_history.append(("received", text, sender, kwargs))


class ServiceTestCase(AsyncTestCase):
    """Base class for service module tests."""
    
    def setup_method(self):
        """Set up service test environment."""
        super().setup_method()
        self.mock_services = {}
        self.service_config = {}
    
    def create_mock_service(self, service_name: str, service_class):
        """Create a mock service instance."""
        mock_service = service_class()
        self.mock_services[service_name] = mock_service
        return mock_service
    
    def get_mock_service(self, service_name: str):
        """Get a mock service by name."""
        return self.mock_services.get(service_name)


class IntegrationTestCase(BaseTestCase):
    """Base class for integration tests."""
    
    def setup_method(self):
        """Set up integration test environment."""
        super().setup_method()
        
        # Set up async environment
        import asyncio
        self.loop = asyncio.get_event_loop()
        
        # Set up database environment
        self.db_path = None
        self.db_connection = None
        
        # Set up Meshtastic environment
        self.mock_interfaces = {}
        self.message_history = []
        
        # Create external service mocks
        self.weather_service = MockWeatherService()
        self.email_service = MockEmailService()
        self.ai_service = MockAIService()
        self.redis_service = MockRedisService()
        self.http_client = MockHTTPClient()
    
    def teardown_method(self):
        """Clean up integration test environment."""
        # Clean up database
        if self.db_connection:
            self.db_connection.close()
        if self.db_path and Path(self.db_path).exists():
            Path(self.db_path).unlink()
        
        super().teardown_method()
    
    # Include methods from other test case classes
    async def wait_for_condition(self, condition_func, timeout: float = 1.0, 
                                interval: float = 0.1) -> bool:
        """Wait for a condition to become true."""
        start_time = self.loop.time()
        while self.loop.time() - start_time < timeout:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        return False
    
    def create_test_database(self) -> str:
        """Create a test database with schema."""
        temp_db = tempfile.mktemp(suffix=".db")
        self.db_path = temp_db
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Create test schema
        schema_sql = [
            """CREATE TABLE users (
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
            )""",
            """CREATE TABLE sos_incidents (
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
            )""",
            """CREATE TABLE bulletins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                unique_id TEXT UNIQUE NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users (node_id)
            )""",
            """CREATE TABLE mail (
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
            )""",
            """CREATE TABLE channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                frequency TEXT,
                description TEXT,
                added_by TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (added_by) REFERENCES users (node_id)
            )""",
            """CREATE TABLE checklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                action TEXT NOT NULL,
                notes TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES users (node_id)
            )"""
        ]
        
        for sql in schema_sql:
            cursor.execute(sql)
        
        conn.commit()
        self.db_connection = conn
        return temp_db
    
    def insert_test_data(self, table: str, data: List[Dict[str, Any]]):
        """Insert test data into a table."""
        if not self.db_connection:
            raise RuntimeError("Database not initialized")
        
        cursor = self.db_connection.cursor()
        
        for row in data:
            columns = list(row.keys())
            placeholders = ["?" for _ in columns]
            values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
            
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
        
        self.db_connection.commit()
    
    def create_mock_interface(self, interface_id: str = "test_interface", 
                            interface_type: str = "serial", **kwargs) -> MockMeshtasticInterface:
        """Create a mock Meshtastic interface."""
        interface = MockMeshtasticInterface(interface_type, **kwargs)
        self.mock_interfaces[interface_id] = interface
        
        # Track messages for testing
        original_send = interface.send_message
        async def tracked_send(*args, **kwargs):
            result = await original_send(*args, **kwargs)
            self.message_history.append(("sent", args, kwargs))
            return result
        interface.send_message = tracked_send
        
        return interface
    
    async def simulate_message_received(self, interface_id: str, text: str, 
                                      sender: str = "!87654321", **kwargs):
        """Simulate receiving a message on an interface."""
        if interface_id not in self.mock_interfaces:
            raise ValueError(f"Interface {interface_id} not found")
        
        interface = self.mock_interfaces[interface_id]
        await interface.simulate_received_message(text, sender, **kwargs)
        self.message_history.append(("received", text, sender, kwargs))


class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user(node_id: str = "!12345678", short_name: str = "TEST", **kwargs) -> Dict[str, Any]:
        """Create test user data."""
        return {
            "node_id": node_id,
            "short_name": short_name,
            "long_name": kwargs.get("long_name", f"Test User {short_name}"),
            "email": kwargs.get("email"),
            "phone": kwargs.get("phone"),
            "address": kwargs.get("address"),
            "tags": json.dumps(kwargs.get("tags", [])),
            "permissions": json.dumps(kwargs.get("permissions", {})),
            "subscriptions": json.dumps(kwargs.get("subscriptions", {})),
            "location_lat": kwargs.get("lat"),
            "location_lon": kwargs.get("lon")
        }
    
    @staticmethod
    def create_sos_incident(incident_id: str = "sos_001", sender_id: str = "!12345678", **kwargs) -> Dict[str, Any]:
        """Create test SOS incident data."""
        return {
            "id": incident_id,
            "incident_type": kwargs.get("incident_type", "SOS"),
            "sender_id": sender_id,
            "message": kwargs.get("message", "Need help"),
            "location_lat": kwargs.get("lat"),
            "location_lon": kwargs.get("lon"),
            "timestamp": kwargs.get("timestamp", "2024-01-01 12:00:00"),
            "status": kwargs.get("status", "active"),
            "responders": json.dumps(kwargs.get("responders", [])),
            "acknowledgers": json.dumps(kwargs.get("acknowledgers", [])),
            "escalated": kwargs.get("escalated", False)
        }
    
    @staticmethod
    def create_bulletin(board: str = "general", sender_id: str = "!12345678", **kwargs) -> Dict[str, Any]:
        """Create test bulletin data."""
        return {
            "board": board,
            "sender_id": sender_id,
            "sender_name": kwargs.get("sender_name", "TEST"),
            "subject": kwargs.get("subject", "Test Bulletin"),
            "content": kwargs.get("content", "This is a test bulletin"),
            "timestamp": kwargs.get("timestamp", "2024-01-01 12:00:00"),
            "unique_id": kwargs.get("unique_id", f"bull_{board}_{sender_id}_001")
        }