"""
Unit tests for EnhancedPlugin base class
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock

from src.core.enhanced_plugin import (
    EnhancedPlugin,
    EnhancedCommandHandler,
    EnhancedMessageHandler,
    ScheduledTask,
    PluginHTTPClient,
    PluginStorage
)
from src.core.plugin_manager import PluginManager, PluginMetadata, PluginPriority
from src.models.message import Message, MessageType


class TestPlugin(EnhancedPlugin):
    """Test plugin implementation"""
    
    def __init__(self, name: str, config: dict, plugin_manager):
        super().__init__(name, config, plugin_manager)
    
    async def initialize(self) -> bool:
        return True
    
    def get_metadata(self):
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test plugin",
            author="Test"
        )


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager"""
    manager = Mock(spec=PluginManager)
    # Don't set config_manager so get_config falls back to direct access
    return manager


@pytest.fixture
def test_plugin(mock_plugin_manager):
    """Create a test plugin instance"""
    config = {
        'enabled': True,
        'api_key': 'test_key',
        'nested': {
            'value': 42
        }
    }
    return TestPlugin("test_plugin", config, mock_plugin_manager)


class TestEnhancedCommandHandler:
    """Tests for EnhancedCommandHandler"""
    
    @pytest.mark.asyncio
    async def test_command_handler_creation(self):
        """Test creating a command handler"""
        async def handler(args, context):
            return "test response"
        
        cmd_handler = EnhancedCommandHandler(
            "test_plugin",
            "test",
            handler,
            "Test command",
            100
        )
        
        assert cmd_handler.plugin_name == "test_plugin"
        assert cmd_handler.command == "test"
        assert cmd_handler.get_commands() == ["test"]
        assert cmd_handler.get_priority() == 100
    
    @pytest.mark.asyncio
    async def test_command_handler_execution(self):
        """Test executing a command handler"""
        async def handler(args, context):
            return f"Hello {args[0]}"
        
        cmd_handler = EnhancedCommandHandler(
            "test_plugin",
            "hello",
            handler,
            "Say hello"
        )
        
        result = await cmd_handler.handle_command("hello", ["World"], {})
        assert result == "Hello World"
    
    @pytest.mark.asyncio
    async def test_command_handler_error(self):
        """Test command handler error handling"""
        async def handler(args, context):
            raise ValueError("Test error")
        
        cmd_handler = EnhancedCommandHandler(
            "test_plugin",
            "error",
            handler
        )
        
        result = await cmd_handler.handle_command("error", [], {})
        assert "Error executing command" in result


class TestEnhancedMessageHandler:
    """Tests for EnhancedMessageHandler"""
    
    @pytest.mark.asyncio
    async def test_message_handler_creation(self):
        """Test creating a message handler"""
        async def handler(message, context):
            return "processed"
        
        msg_handler = EnhancedMessageHandler("test_plugin", handler, 50)
        
        assert msg_handler.plugin_name == "test_plugin"
        assert msg_handler.get_priority() == 50
    
    @pytest.mark.asyncio
    async def test_message_handler_execution(self):
        """Test executing a message handler"""
        async def handler(message, context):
            return f"Processed: {message.content}"
        
        msg_handler = EnhancedMessageHandler("test_plugin", handler)
        
        message = Message(
            id="test",
            message_type=MessageType.TEXT,
            content="Hello",
            sender_id="user1",
            timestamp=datetime.utcnow()
        )
        
        result = await msg_handler.handle_message(message, {})
        assert result == "Processed: Hello"


class TestScheduledTask:
    """Tests for ScheduledTask"""
    
    @pytest.mark.asyncio
    async def test_scheduled_task_creation(self):
        """Test creating a scheduled task"""
        async def handler():
            pass
        
        task = ScheduledTask("test_task", 60, None, handler, "test_plugin")
        
        assert task.name == "test_task"
        assert task.interval == 60
        assert task.plugin_name == "test_plugin"
        assert task.enabled is True
        assert task.run_count == 0
    
    @pytest.mark.asyncio
    async def test_scheduled_task_execution(self):
        """Test scheduled task execution"""
        call_count = 0
        
        async def handler():
            nonlocal call_count
            call_count += 1
        
        task = ScheduledTask("test_task", 0.1, None, handler, "test_plugin")
        task.start()
        
        # Wait for a few executions
        await asyncio.sleep(0.3)
        task.stop()
        
        # Should have run at least twice
        assert call_count >= 2
    
    @pytest.mark.asyncio
    async def test_scheduled_task_error_handling(self):
        """Test scheduled task continues after errors"""
        call_count = 0
        
        async def handler():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error")
        
        task = ScheduledTask("test_task", 0.1, None, handler, "test_plugin")
        task.start()
        
        # Wait for executions
        await asyncio.sleep(0.3)
        task.stop()
        
        # Should have continued after error
        assert call_count >= 2
        assert task.error_count >= 1


class TestPluginStorage:
    """Tests for PluginStorage"""
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, mock_plugin_manager):
        """Test storing and retrieving data"""
        storage = PluginStorage("test_plugin", mock_plugin_manager)
        
        await storage.store_data("key1", "value1")
        result = await storage.retrieve_data("key1")
        
        assert result == "value1"
    
    @pytest.mark.asyncio
    async def test_retrieve_default(self, mock_plugin_manager):
        """Test retrieving with default value"""
        storage = PluginStorage("test_plugin", mock_plugin_manager)
        
        result = await storage.retrieve_data("nonexistent", "default")
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_store_with_ttl(self, mock_plugin_manager):
        """Test storing data with TTL"""
        storage = PluginStorage("test_plugin", mock_plugin_manager)
        
        await storage.store_data("key1", "value1", ttl=1)
        
        # Should exist immediately
        result = await storage.retrieve_data("key1")
        assert result == "value1"
        
        # Wait for expiry
        await asyncio.sleep(1.1)
        
        # Should be expired
        result = await storage.retrieve_data("key1", "expired")
        assert result == "expired"
    
    @pytest.mark.asyncio
    async def test_delete_data(self, mock_plugin_manager):
        """Test deleting data"""
        storage = PluginStorage("test_plugin", mock_plugin_manager)
        
        await storage.store_data("key1", "value1")
        deleted = await storage.delete_data("key1")
        
        assert deleted is True
        
        result = await storage.retrieve_data("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_keys(self, mock_plugin_manager):
        """Test listing keys"""
        storage = PluginStorage("test_plugin", mock_plugin_manager)
        
        await storage.store_data("prefix:key1", "value1")
        await storage.store_data("prefix:key2", "value2")
        await storage.store_data("other:key3", "value3")
        
        keys = await storage.list_keys("prefix:")
        
        assert len(keys) == 2
        assert "prefix:key1" in keys
        assert "prefix:key2" in keys
        assert "other:key3" not in keys
    
    @pytest.mark.asyncio
    async def test_plugin_isolation(self, mock_plugin_manager):
        """Test that plugins can't access each other's data"""
        storage1 = PluginStorage("plugin1", mock_plugin_manager)
        storage2 = PluginStorage("plugin2", mock_plugin_manager)
        
        await storage1.store_data("key", "value1")
        await storage2.store_data("key", "value2")
        
        result1 = await storage1.retrieve_data("key")
        result2 = await storage2.retrieve_data("key")
        
        assert result1 == "value1"
        assert result2 == "value2"


class TestEnhancedPlugin:
    """Tests for EnhancedPlugin"""
    
    def test_plugin_creation(self, test_plugin):
        """Test creating an enhanced plugin"""
        assert test_plugin.name == "test_plugin"
        assert test_plugin.config['enabled'] is True
        assert test_plugin._http_client is not None
        assert test_plugin._storage is not None
    
    def test_register_command(self, test_plugin):
        """Test registering a command"""
        async def handler(args, context):
            return "test"
        
        test_plugin.register_command("test", handler, "Test command")
        
        assert "test" in test_plugin._command_handlers
        assert test_plugin._command_handlers["test"].command == "test"
    
    def test_register_message_handler(self, test_plugin):
        """Test registering a message handler"""
        async def handler(message, context):
            return "processed"
        
        test_plugin.register_message_handler(handler)
        
        assert test_plugin._message_handler is not None
    
    def test_register_scheduled_task(self, test_plugin):
        """Test registering a scheduled task"""
        async def handler():
            pass
        
        test_plugin.register_scheduled_task("task1", 60, handler)
        
        assert "task1" in test_plugin._scheduled_tasks
        assert test_plugin._scheduled_tasks["task1"].interval == 60
    
    def test_register_menu_item(self, test_plugin):
        """Test registering a menu item"""
        async def handler(context):
            return "menu"
        
        test_plugin.register_menu_item("main", "Test Item", handler)
        
        assert len(test_plugin._menu_items) == 1
        assert test_plugin._menu_items[0]['label'] == "Test Item"
    
    def test_get_config(self, test_plugin):
        """Test getting configuration values"""
        assert test_plugin.get_config("enabled") is True
        assert test_plugin.get_config("api_key") == "test_key"
        assert test_plugin.get_config("nested.value") == 42
        assert test_plugin.get_config("nonexistent", "default") == "default"
    
    def test_set_config(self, test_plugin):
        """Test setting configuration values"""
        test_plugin.set_config("new_key", "new_value")
        assert test_plugin.get_config("new_key") == "new_value"
        
        test_plugin.set_config("nested.new_value", 100)
        assert test_plugin.get_config("nested.new_value") == 100
    
    @pytest.mark.asyncio
    async def test_send_message(self, test_plugin):
        """Test sending a message"""
        result = await test_plugin.send_message("Test message")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_data(self, test_plugin):
        """Test storing and retrieving data"""
        await test_plugin.store_data("test_key", {"data": "value"})
        result = await test_plugin.retrieve_data("test_key")
        
        assert result == {"data": "value"}
    
    @pytest.mark.asyncio
    async def test_start_stops_scheduled_tasks(self, test_plugin):
        """Test that start/stop manages scheduled tasks"""
        call_count = 0
        
        async def handler():
            nonlocal call_count
            call_count += 1
        
        test_plugin.register_scheduled_task("task1", 0.1, handler)
        
        # Start plugin
        await test_plugin.start()
        assert test_plugin.is_running is True
        
        # Wait for some executions
        await asyncio.sleep(0.3)
        
        # Stop plugin
        await test_plugin.stop()
        assert test_plugin.is_running is False
        
        # Should have executed
        assert call_count >= 2
    
    @pytest.mark.asyncio
    async def test_cleanup(self, test_plugin):
        """Test cleanup closes resources"""
        result = await test_plugin.cleanup()
        assert result is True
        assert test_plugin._http_client.session is None or test_plugin._http_client.session.closed
