"""
Unit tests for Plugin Interfaces
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.core.plugin_interfaces import (
    PluginMessage, PluginEvent, PluginResponse, PluginMessageType, PluginEventType,
    MessageHandler, CommandHandler, PluginCommunicationBridge, PluginRegistry,
    BaseMessageHandler, BaseCommandHandler
)
from src.models.message import Message, MessageType


class TestPluginMessage:
    """Test plugin message structures"""
    
    def test_plugin_message_creation(self):
        """Test creating plugin messages"""
        message = PluginMessage(
            type=PluginMessageType.MESH_MESSAGE,
            source_plugin="test_plugin",
            target_plugin="target_plugin",
            data={"key": "value"}
        )
        
        assert message.type == PluginMessageType.MESH_MESSAGE
        assert message.source_plugin == "test_plugin"
        assert message.target_plugin == "target_plugin"
        assert message.data == {"key": "value"}
        assert message.id is not None
        assert isinstance(message.timestamp, datetime)
    
    def test_plugin_message_defaults(self):
        """Test plugin message default values"""
        message = PluginMessage()
        
        assert message.type == PluginMessageType.PLUGIN_COMMAND
        assert message.source_plugin == ""
        assert message.target_plugin is None
        assert message.data is None
        assert len(message.metadata) == 0
        assert message.reply_to is None
        assert message.correlation_id is None


class TestPluginEvent:
    """Test plugin event structures"""
    
    def test_plugin_event_creation(self):
        """Test creating plugin events"""
        event = PluginEvent(
            type=PluginEventType.PLUGIN_STARTED,
            source_plugin="test_plugin",
            data={"status": "started"}
        )
        
        assert event.type == PluginEventType.PLUGIN_STARTED
        assert event.source_plugin == "test_plugin"
        assert event.data == {"status": "started"}
        assert event.id is not None
        assert isinstance(event.timestamp, datetime)
    
    def test_plugin_event_defaults(self):
        """Test plugin event default values"""
        event = PluginEvent()
        
        assert event.type == PluginEventType.CUSTOM_EVENT
        assert event.source_plugin == ""
        assert event.data is None
        assert len(event.metadata) == 0


class TestPluginResponse:
    """Test plugin response structures"""
    
    def test_plugin_response_creation(self):
        """Test creating plugin responses"""
        response = PluginResponse(
            request_id="req123",
            success=True,
            data={"result": "success"}
        )
        
        assert response.request_id == "req123"
        assert response.success is True
        assert response.data == {"result": "success"}
        assert response.error is None
        assert response.id is not None
    
    def test_plugin_response_error(self):
        """Test plugin response with error"""
        response = PluginResponse(
            request_id="req123",
            success=False,
            error="Something went wrong"
        )
        
        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.data is None


class MockMessageHandler(BaseMessageHandler):
    """Mock message handler for testing"""
    
    def __init__(self, can_handle_result=True, handle_result="handled"):
        super().__init__(priority=50)
        self.can_handle_result = can_handle_result
        self.handle_result = handle_result
        self.handled_messages = []
    
    def can_handle(self, message: Message) -> bool:
        return self.can_handle_result
    
    async def handle_message(self, message: Message, context: dict) -> str:
        self.handled_messages.append(message)
        return self.handle_result


class MockCommandHandler(BaseCommandHandler):
    """Mock command handler for testing"""
    
    def __init__(self, commands=None):
        super().__init__(commands or ["test", "help"])
        self.handled_commands = []
        self.add_help("test", "Test command")
        self.add_help("help", "Show help")
    
    async def handle_command(self, command: str, args: list, context: dict) -> str:
        self.handled_commands.append((command, args))
        if command == "test":
            return f"Test executed with args: {args}"
        elif command == "help":
            return "Help text"
        return f"Unknown command: {command}"


class TestBaseMessageHandler:
    """Test base message handler"""
    
    @pytest.mark.asyncio
    async def test_message_handler_creation(self):
        """Test creating message handler"""
        handler = MockMessageHandler()
        
        assert handler.get_priority() == 50
        assert len(handler.handled_messages) == 0
    
    @pytest.mark.asyncio
    async def test_message_handler_can_handle(self):
        """Test message handler can_handle method"""
        handler = MockMessageHandler(can_handle_result=True)
        message = Message(content="test", sender_id="user1")
        
        assert handler.can_handle(message) is True
        
        handler.can_handle_result = False
        assert handler.can_handle(message) is False
    
    @pytest.mark.asyncio
    async def test_message_handler_handle_message(self):
        """Test message handler handle_message method"""
        handler = MockMessageHandler(handle_result="processed")
        message = Message(content="test message", sender_id="user1")
        context = {"key": "value"}
        
        result = await handler.handle_message(message, context)
        
        assert result == "processed"
        assert len(handler.handled_messages) == 1
        assert handler.handled_messages[0] == message


class TestBaseCommandHandler:
    """Test base command handler"""
    
    @pytest.mark.asyncio
    async def test_command_handler_creation(self):
        """Test creating command handler"""
        handler = MockCommandHandler(["cmd1", "cmd2"])
        
        commands = handler.get_commands()
        assert "cmd1" in commands
        assert "cmd2" in commands
        assert len(handler.handled_commands) == 0
    
    @pytest.mark.asyncio
    async def test_command_handler_help(self):
        """Test command handler help functionality"""
        handler = MockCommandHandler()
        
        help_text = handler.get_help("test")
        assert help_text == "Test command"
        
        help_text = handler.get_help("nonexistent")
        assert "No help available" in help_text
    
    @pytest.mark.asyncio
    async def test_command_handler_handle_command(self):
        """Test command handler handle_command method"""
        handler = MockCommandHandler()
        context = {"user": "test_user"}
        
        # Test known command
        result = await handler.handle_command("test", ["arg1", "arg2"], context)
        assert "Test executed with args: ['arg1', 'arg2']" in result
        
        # Test help command
        result = await handler.handle_command("help", [], context)
        assert result == "Help text"
        
        # Test unknown command
        result = await handler.handle_command("unknown", [], context)
        assert "Unknown command: unknown" in result
        
        assert len(handler.handled_commands) == 3


class TestPluginCommunicationBridge:
    """Test plugin communication bridge"""
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Create mock plugin manager"""
        manager = Mock()
        manager.send_message_to_plugin = AsyncMock(return_value="response")
        manager.get_running_plugins = Mock(return_value=["plugin1", "plugin2"])
        manager.handle_plugin_event = AsyncMock()
        manager.config_manager = Mock()
        manager.config_manager.get = Mock(return_value="config_value")
        manager.config_manager.set = Mock()
        return manager
    
    @pytest.fixture
    def mock_core_router(self):
        """Create mock core router"""
        router = Mock()
        router.handle_plugin_message = AsyncMock(return_value="router_response")
        router.send_message = AsyncMock(return_value=True)
        return router
    
    @pytest.fixture
    def communication_bridge(self, mock_plugin_manager, mock_core_router):
        """Create communication bridge"""
        return PluginCommunicationBridge(
            "test_plugin",
            mock_plugin_manager,
            mock_core_router
        )
    
    @pytest.mark.asyncio
    async def test_send_message_to_plugin(self, communication_bridge, mock_plugin_manager):
        """Test sending message to specific plugin"""
        message = PluginMessage(
            type=PluginMessageType.PLUGIN_COMMAND,
            target_plugin="target_plugin",
            data={"test": "data"}
        )
        
        result = await communication_bridge.send_message(message)
        
        assert result == "response"
        assert message.source_plugin == "test_plugin"
        mock_plugin_manager.send_message_to_plugin.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_to_core(self, communication_bridge, mock_core_router):
        """Test sending message to core router"""
        message = PluginMessage(
            type=PluginMessageType.SYSTEM_EVENT,
            data={"event": "test"}
        )
        
        result = await communication_bridge.send_message(message)
        
        assert result == "router_response"
        assert message.source_plugin == "test_plugin"
        mock_core_router.handle_plugin_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, communication_bridge, mock_plugin_manager):
        """Test broadcasting message to all plugins"""
        message = PluginMessage(
            type=PluginMessageType.BROADCAST,
            data={"broadcast": "data"}
        )
        
        responses = await communication_bridge.broadcast_message(message)
        
        assert len(responses) == 2  # Two plugins returned by mock
        assert message.source_plugin == "test_plugin"
        assert mock_plugin_manager.send_message_to_plugin.call_count == 2
    
    @pytest.mark.asyncio
    async def test_emit_event(self, communication_bridge, mock_plugin_manager):
        """Test emitting events"""
        event = PluginEvent(
            type=PluginEventType.PLUGIN_STARTED,
            data={"status": "started"}
        )
        
        await communication_bridge.emit_event(event)
        
        assert event.source_plugin == "test_plugin"
        mock_plugin_manager.handle_plugin_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_mesh_message(self, communication_bridge, mock_core_router):
        """Test sending mesh message"""
        message = Message(content="test mesh message", sender_id="user1")
        
        result = await communication_bridge.send_mesh_message(message, "interface1")
        
        assert result is True
        mock_core_router.send_message.assert_called_once_with(message, "interface1")
    
    def test_config_operations(self, communication_bridge, mock_plugin_manager):
        """Test configuration get/set operations"""
        # Test get config
        value = communication_bridge.get_config("test_key", "default")
        
        mock_plugin_manager.config_manager.get.assert_called_once_with(
            "plugins.test_plugin.test_key", "default"
        )
        
        # Test set config
        communication_bridge.set_config("test_key", "new_value")
        
        mock_plugin_manager.config_manager.set.assert_called_once_with(
            "plugins.test_plugin.test_key", "new_value"
        )
    
    @pytest.mark.asyncio
    async def test_event_subscription(self, communication_bridge):
        """Test event subscription"""
        handler_called = False
        
        async def test_handler(event):
            nonlocal handler_called
            handler_called = True
        
        # Subscribe to events
        await communication_bridge.subscribe_to_events(
            [PluginEventType.PLUGIN_STARTED],
            test_handler
        )
        
        # Handle an event
        event = PluginEvent(type=PluginEventType.PLUGIN_STARTED)
        await communication_bridge.handle_event(event)
        
        assert handler_called is True


class TestPluginRegistry:
    """Test plugin registry"""
    
    @pytest.fixture
    def registry(self):
        """Create plugin registry"""
        return PluginRegistry()
    
    def test_message_handler_registration(self, registry):
        """Test message handler registration"""
        handler1 = MockMessageHandler()
        handler2 = MockMessageHandler()
        
        # Register handlers
        registry.register_message_handler("plugin1", handler1)
        registry.register_message_handler("plugin1", handler2)
        registry.register_message_handler("plugin2", handler1)
        
        # Get handlers for specific plugin
        plugin1_handlers = registry.get_message_handlers("plugin1")
        assert len(plugin1_handlers) == 2
        assert handler1 in plugin1_handlers
        assert handler2 in plugin1_handlers
        
        # Get all handlers
        all_handlers = registry.get_message_handlers()
        assert len(all_handlers) == 3
    
    def test_message_handler_unregistration(self, registry):
        """Test message handler unregistration"""
        handler = MockMessageHandler()
        
        # Register and then unregister
        registry.register_message_handler("plugin1", handler)
        assert len(registry.get_message_handlers("plugin1")) == 1
        
        registry.unregister_message_handler("plugin1", handler)
        assert len(registry.get_message_handlers("plugin1")) == 0
    
    def test_command_handler_registration(self, registry):
        """Test command handler registration"""
        handler1 = MockCommandHandler(["cmd1", "cmd2"])
        handler2 = MockCommandHandler(["cmd3", "cmd4"])
        
        # Register handlers
        registry.register_command_handler("plugin1", handler1)
        registry.register_command_handler("plugin2", handler2)
        
        # Get handlers
        plugin1_handlers = registry.get_command_handlers("plugin1")
        assert len(plugin1_handlers) == 1
        assert handler1 in plugin1_handlers
        
        all_handlers = registry.get_command_handlers()
        assert len(all_handlers) == 2
    
    def test_available_commands(self, registry):
        """Test getting available commands"""
        handler1 = MockCommandHandler(["cmd1", "cmd2"])
        handler2 = MockCommandHandler(["cmd3", "cmd4"])
        
        registry.register_command_handler("plugin1", handler1)
        registry.register_command_handler("plugin2", handler2)
        
        commands = registry.get_available_commands()
        
        assert commands["cmd1"] == "plugin1"
        assert commands["cmd2"] == "plugin1"
        assert commands["cmd3"] == "plugin2"
        assert commands["cmd4"] == "plugin2"
    
    def test_plugin_capabilities(self, registry):
        """Test plugin capability registration"""
        # Register capabilities
        registry.register_plugin_capability(
            "plugin1", 
            "weather", 
            {"api": "openweather", "features": ["current", "forecast"]}
        )
        registry.register_plugin_capability(
            "plugin2",
            "weather",
            {"api": "noaa", "features": ["current", "alerts"]}
        )
        registry.register_plugin_capability(
            "plugin1",
            "email",
            {"smtp": True, "imap": True}
        )
        
        # Get capabilities for specific plugin
        plugin1_caps = registry.get_plugin_capabilities("plugin1")
        assert "weather" in plugin1_caps
        assert "email" in plugin1_caps
        
        # Find plugins with specific capability
        weather_plugins = registry.find_plugins_with_capability("weather")
        assert "plugin1" in weather_plugins
        assert "plugin2" in weather_plugins
        
        email_plugins = registry.find_plugins_with_capability("email")
        assert "plugin1" in email_plugins
        assert "plugin2" not in email_plugins


if __name__ == "__main__":
    pytest.main([__file__])