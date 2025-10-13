"""
Test utilities and helper functions for ZephyrGate testing.
"""
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, AsyncMock


class AsyncTestHelper:
    """Helper class for async testing operations."""
    
    @staticmethod
    async def wait_for_calls(mock_obj: Mock, expected_calls: int, timeout: float = 1.0) -> bool:
        """Wait for a mock object to be called a specific number of times."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if mock_obj.call_count >= expected_calls:
                return True
            await asyncio.sleep(0.01)
        return False
    
    @staticmethod
    async def wait_for_condition(condition: Callable[[], bool], timeout: float = 1.0) -> bool:
        """Wait for a condition to become true."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if condition():
                return True
            await asyncio.sleep(0.01)
        return False
    
    @staticmethod
    async def collect_async_results(async_generator, max_items: int = 10, timeout: float = 1.0) -> List[Any]:
        """Collect results from an async generator with timeout."""
        results = []
        start_time = asyncio.get_event_loop().time()
        
        async for item in async_generator:
            results.append(item)
            if len(results) >= max_items:
                break
            if asyncio.get_event_loop().time() - start_time > timeout:
                break
        
        return results


class MessageTestHelper:
    """Helper class for testing message-related functionality."""
    
    @staticmethod
    def create_test_message(content: str = "test message", sender: str = "!12345678", **kwargs) -> Dict[str, Any]:
        """Create a test message object."""
        return {
            "id": kwargs.get("id", f"msg_{hash(content) % 10000:04d}"),
            "sender_id": sender,
            "recipient_id": kwargs.get("recipient_id"),
            "channel": kwargs.get("channel", 0),
            "content": content,
            "timestamp": kwargs.get("timestamp", datetime.utcnow()),
            "message_type": kwargs.get("message_type", "text"),
            "interface_id": kwargs.get("interface_id", "test_interface"),
            "hop_count": kwargs.get("hop_count", 0),
            "snr": kwargs.get("snr"),
            "rssi": kwargs.get("rssi")
        }
    
    @staticmethod
    def create_sos_message(sos_type: str = "SOS", message: str = "Need help", **kwargs) -> Dict[str, Any]:
        """Create a test SOS message."""
        content = f"{sos_type} {message}" if message else sos_type
        return MessageTestHelper.create_test_message(content, **kwargs)
    
    @staticmethod
    def create_command_message(command: str, args: str = "", **kwargs) -> Dict[str, Any]:
        """Create a test command message."""
        content = f"{command} {args}".strip()
        return MessageTestHelper.create_test_message(content, **kwargs)
    
    @staticmethod
    def extract_commands_from_messages(messages: List[Dict[str, Any]]) -> List[str]:
        """Extract command strings from a list of messages."""
        commands = []
        for msg in messages:
            content = msg.get("content", "").strip()
            if content:
                commands.append(content.split()[0].upper())
        return commands


class DatabaseTestHelper:
    """Helper class for database testing operations."""
    
    @staticmethod
    def create_test_db_file() -> str:
        """Create a temporary database file."""
        return tempfile.mktemp(suffix=".db")
    
    @staticmethod
    def insert_test_users(db_path: str, users: List[Dict[str, Any]]):
        """Insert test users into database."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for user in users:
            # Convert dict/list fields to JSON
            user_data = user.copy()
            for field in ["tags", "permissions", "subscriptions"]:
                if field in user_data and isinstance(user_data[field], (dict, list)):
                    user_data[field] = json.dumps(user_data[field])
            
            columns = list(user_data.keys())
            placeholders = ["?" for _ in columns]
            values = list(user_data.values())
            
            sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def count_table_rows(db_path: str, table: str) -> int:
        """Count rows in a database table."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    @staticmethod
    def get_table_data(db_path: str, table: str, where_clause: str = None) -> List[Dict[str, Any]]:
        """Get data from a database table."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = f"SELECT * FROM {table}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        
        cursor.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows


class ConfigTestHelper:
    """Helper class for configuration testing."""
    
    @staticmethod
    def create_test_config(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a test configuration."""
        config = {
            "database": {
                "url": ":memory:",
                "pool_size": 1
            },
            "meshtastic": {
                "interfaces": {
                    "serial": {"enabled": False},
                    "tcp": {"enabled": False},
                    "ble": {"enabled": False}
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
                "level": "DEBUG"
            }
        }
        
        if overrides:
            config = ConfigTestHelper._deep_merge(config, overrides)
        
        return config
    
    @staticmethod
    def create_config_file(config: Dict[str, Any], file_format: str = "yaml") -> Path:
        """Create a temporary configuration file."""
        import yaml
        
        temp_file = Path(tempfile.mktemp(suffix=f".{file_format}"))
        
        if file_format == "yaml":
            with open(temp_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
        elif file_format == "json":
            with open(temp_file, "w") as f:
                json.dump(config, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {file_format}")
        
        return temp_file
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigTestHelper._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


class FileTestHelper:
    """Helper class for file system testing operations."""
    
    @staticmethod
    def create_temp_file(content: str = "", suffix: str = ".tmp") -> Path:
        """Create a temporary file with content."""
        temp_file = Path(tempfile.mktemp(suffix=suffix))
        temp_file.write_text(content)
        return temp_file
    
    @staticmethod
    def create_temp_dir() -> Path:
        """Create a temporary directory."""
        return Path(tempfile.mkdtemp())
    
    @staticmethod
    def create_file_structure(base_dir: Path, structure: Dict[str, Any]):
        """Create a file/directory structure from a dict."""
        for name, content in structure.items():
            path = base_dir / name
            
            if isinstance(content, dict):
                # It's a directory
                path.mkdir(parents=True, exist_ok=True)
                FileTestHelper.create_file_structure(path, content)
            else:
                # It's a file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content))


class AssertionHelper:
    """Helper class for custom assertions."""
    
    @staticmethod
    def assert_message_sent(mock_interface, expected_content: str, timeout: float = 1.0):
        """Assert that a message with specific content was sent."""
        sent_messages = [msg.text for msg in mock_interface.sent_messages]
        assert expected_content in sent_messages, f"Expected message '{expected_content}' not found in {sent_messages}"
    
    @staticmethod
    def assert_message_contains(mock_interface, partial_content: str):
        """Assert that a sent message contains specific text."""
        sent_messages = [msg.text for msg in mock_interface.sent_messages]
        found = any(partial_content in msg for msg in sent_messages)
        assert found, f"No message containing '{partial_content}' found in {sent_messages}"
    
    @staticmethod
    def assert_database_record_exists(db_path: str, table: str, conditions: Dict[str, Any]):
        """Assert that a database record exists with specific conditions."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        where_parts = []
        values = []
        for key, value in conditions.items():
            where_parts.append(f"{key} = ?")
            values.append(value)
        
        where_clause = " AND ".join(where_parts)
        sql = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
        
        cursor.execute(sql, values)
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count > 0, f"No record found in {table} with conditions {conditions}"
    
    @staticmethod
    def assert_config_value(config: Dict[str, Any], key_path: str, expected_value: Any):
        """Assert that a nested config value matches expected value."""
        keys = key_path.split(".")
        current = config
        
        for key in keys[:-1]:
            assert key in current, f"Config key '{key}' not found in path '{key_path}'"
            current = current[key]
        
        final_key = keys[-1]
        assert final_key in current, f"Config key '{final_key}' not found in path '{key_path}'"
        assert current[final_key] == expected_value, f"Config value at '{key_path}' is {current[final_key]}, expected {expected_value}"


# Pytest fixtures (only available when pytest is installed)
try:
    import pytest

    @pytest.fixture
    def async_helper():
        """Provide async test helper."""
        return AsyncTestHelper()

    @pytest.fixture
    def message_helper():
        """Provide message test helper."""
        return MessageTestHelper()

    @pytest.fixture
    def db_helper():
        """Provide database test helper."""
        return DatabaseTestHelper()

    @pytest.fixture
    def config_helper():
        """Provide config test helper."""
        return ConfigTestHelper()

    @pytest.fixture
    def file_helper():
        """Provide file test helper."""
        return FileTestHelper()

    @pytest.fixture
    def assert_helper():
        """Provide assertion helper."""
        return AssertionHelper()

except ImportError:
    # pytest not available, skip fixture definitions
    pass