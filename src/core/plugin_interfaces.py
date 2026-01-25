"""
Plugin Communication Interfaces for ZephyrGate

Defines interfaces and patterns for plugin communication with the core router
and other system components.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
import uuid

try:
    from ..models.message import Message, MessageType
except ImportError:
    from models.message import Message, MessageType


class PluginMessageType(Enum):
    """Types of messages that can be sent between plugins and core"""
    MESH_MESSAGE = "mesh_message"
    SYSTEM_EVENT = "system_event"
    CONFIG_UPDATE = "config_update"
    HEALTH_CHECK = "health_check"
    PLUGIN_COMMAND = "plugin_command"
    BROADCAST = "broadcast"
    DIRECT_MESSAGE = "direct_message"


class PluginEventType(Enum):
    """Types of events that plugins can emit"""
    PLUGIN_STARTED = "plugin_started"
    PLUGIN_STOPPED = "plugin_stopped"
    PLUGIN_ERROR = "plugin_error"
    MESSAGE_PROCESSED = "message_processed"
    USER_ACTION = "user_action"
    SYSTEM_ALERT = "system_alert"
    CUSTOM_EVENT = "custom_event"


@dataclass
class PluginMessage:
    """Message structure for plugin communication"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: PluginMessageType = PluginMessageType.PLUGIN_COMMAND
    source_plugin: str = ""
    target_plugin: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class PluginEvent:
    """Event structure for plugin events"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: PluginEventType = PluginEventType.CUSTOM_EVENT
    source_plugin: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResponse:
    """Response structure for plugin communication"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageHandler(ABC):
    """Abstract base class for message handlers"""
    
    @abstractmethod
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """
        Handle an incoming message.
        
        Args:
            message: The message to handle
            context: Additional context information
            
        Returns:
            Optional response data
        """
        pass
    
    @abstractmethod
    def can_handle(self, message: Message) -> bool:
        """
        Check if this handler can process the given message.
        
        Args:
            message: The message to check
            
        Returns:
            True if this handler can process the message
        """
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get the priority of this handler (lower number = higher priority).
        
        Returns:
            Priority value
        """
        pass


class CommandHandler(ABC):
    """Abstract base class for command handlers"""
    
    @abstractmethod
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle a command.
        
        Args:
            command: The command name
            args: Command arguments
            context: Additional context information
            
        Returns:
            Response message
        """
        pass
    
    @abstractmethod
    def get_commands(self) -> List[str]:
        """
        Get list of commands this handler supports.
        
        Returns:
            List of command names
        """
        pass
    
    @abstractmethod
    def get_help(self, command: str) -> str:
        """
        Get help text for a command.
        
        Args:
            command: The command name
            
        Returns:
            Help text
        """
        pass


class PluginCommunicationInterface(ABC):
    """Interface for plugin communication with the core system"""
    
    @abstractmethod
    async def send_message(self, message: PluginMessage) -> Optional[PluginResponse]:
        """
        Send a message to another plugin or the core system.
        
        Args:
            message: The message to send
            
        Returns:
            Optional response
        """
        pass
    
    @abstractmethod
    async def broadcast_message(self, message: PluginMessage) -> List[PluginResponse]:
        """
        Broadcast a message to all plugins.
        
        Args:
            message: The message to broadcast
            
        Returns:
            List of responses
        """
        pass
    
    @abstractmethod
    async def emit_event(self, event: PluginEvent):
        """
        Emit an event.
        
        Args:
            event: The event to emit
        """
        pass
    
    @abstractmethod
    async def subscribe_to_events(self, event_types: List[PluginEventType], handler: Callable):
        """
        Subscribe to specific event types.
        
        Args:
            event_types: List of event types to subscribe to
            handler: Event handler function
        """
        pass
    
    @abstractmethod
    async def send_mesh_message(self, message: Message, interface_id: Optional[str] = None) -> bool:
        """
        Send a message to the mesh network.
        
        Args:
            message: The message to send
            interface_id: Optional specific interface to use
            
        Returns:
            True if message was queued successfully
        """
        pass
    
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        pass
    
    @abstractmethod
    def set_config(self, key: str, value: Any):
        """
        Set configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            value: Value to set
        """
        pass


class CoreRouterInterface(ABC):
    """Interface for core router functionality"""
    
    @abstractmethod
    async def route_message(self, message: Message, source_interface: str):
        """
        Route a message to appropriate handlers.
        
        Args:
            message: The message to route
            source_interface: Interface the message came from
        """
        pass
    
    @abstractmethod
    async def register_message_handler(self, handler: MessageHandler, plugin_name: str):
        """
        Register a message handler.
        
        Args:
            handler: The message handler
            plugin_name: Name of the plugin registering the handler
        """
        pass
    
    @abstractmethod
    async def unregister_message_handler(self, handler: MessageHandler, plugin_name: str):
        """
        Unregister a message handler.
        
        Args:
            handler: The message handler to remove
            plugin_name: Name of the plugin unregistering the handler
        """
        pass
    
    @abstractmethod
    async def register_command_handler(self, handler: CommandHandler, plugin_name: str):
        """
        Register a command handler.
        
        Args:
            handler: The command handler
            plugin_name: Name of the plugin registering the handler
        """
        pass
    
    @abstractmethod
    async def unregister_command_handler(self, handler: CommandHandler, plugin_name: str):
        """
        Unregister a command handler.
        
        Args:
            handler: The command handler to remove
            plugin_name: Name of the plugin unregistering the handler
        """
        pass


class PluginConfigurationInterface(ABC):
    """Interface for plugin configuration management"""
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate plugin configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid
        """
        pass
    
    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get the configuration schema for this plugin.
        
        Returns:
            JSON schema for configuration
        """
        pass
    
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration values.
        
        Returns:
            Default configuration dictionary
        """
        pass
    
    @abstractmethod
    async def on_config_changed(self, key: str, old_value: Any, new_value: Any):
        """
        Handle configuration changes.
        
        Args:
            key: Configuration key that changed
            old_value: Previous value
            new_value: New value
        """
        pass


class PluginStorageInterface(ABC):
    """Interface for plugin data storage"""
    
    @abstractmethod
    async def store_data(self, key: str, data: Any, ttl: Optional[int] = None):
        """
        Store data with optional TTL.
        
        Args:
            key: Storage key
            data: Data to store
            ttl: Time to live in seconds (optional)
        """
        pass
    
    @abstractmethod
    async def retrieve_data(self, key: str, default: Any = None) -> Any:
        """
        Retrieve stored data.
        
        Args:
            key: Storage key
            default: Default value if key not found
            
        Returns:
            Stored data or default
        """
        pass
    
    @abstractmethod
    async def delete_data(self, key: str) -> bool:
        """
        Delete stored data.
        
        Args:
            key: Storage key
            
        Returns:
            True if data was deleted
        """
        pass
    
    @abstractmethod
    async def list_keys(self, prefix: str = "") -> List[str]:
        """
        List storage keys with optional prefix filter.
        
        Args:
            prefix: Key prefix filter
            
        Returns:
            List of matching keys
        """
        pass


class PluginCommunicationBridge:
    """
    Bridge class that implements PluginCommunicationInterface and provides
    communication between plugins and the core system.
    """
    
    def __init__(self, plugin_name: str, plugin_manager, core_router):
        self.plugin_name = plugin_name
        self.plugin_manager = plugin_manager
        self.core_router = core_router
        self.event_subscriptions: Dict[PluginEventType, List[Callable]] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    async def send_message(self, message: PluginMessage) -> Optional[PluginResponse]:
        """Send a message to another plugin or the core system"""
        message.source_plugin = self.plugin_name
        
        if message.target_plugin:
            # Send to specific plugin
            return await self.plugin_manager.send_message_to_plugin(
                message.target_plugin, 
                message.type.value, 
                message
            )
        else:
            # Send to core router
            return await self.core_router.handle_plugin_message(message)
    
    async def broadcast_message(self, message: PluginMessage) -> List[PluginResponse]:
        """Broadcast a message to all plugins"""
        message.source_plugin = self.plugin_name
        responses = []
        
        for plugin_name in self.plugin_manager.get_running_plugins():
            if plugin_name != self.plugin_name:
                response = await self.plugin_manager.send_message_to_plugin(
                    plugin_name,
                    message.type.value,
                    message
                )
                if response:
                    responses.append(response)
        
        return responses
    
    async def emit_event(self, event: PluginEvent):
        """Emit an event"""
        event.source_plugin = self.plugin_name
        await self.plugin_manager.handle_plugin_event(
            self.plugin_name,
            event.type.value,
            event
        )
    
    async def subscribe_to_events(self, event_types: List[PluginEventType], handler: Callable):
        """Subscribe to specific event types"""
        for event_type in event_types:
            if event_type not in self.event_subscriptions:
                self.event_subscriptions[event_type] = []
            self.event_subscriptions[event_type].append(handler)
    
    async def send_mesh_message(self, message: Message, interface_id: Optional[str] = None) -> bool:
        """Send a message to the mesh network"""
        return await self.core_router.send_message(message, interface_id)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        plugin_config_key = f"plugins.{self.plugin_name}.{key}"
        return self.plugin_manager.config_manager.get(plugin_config_key, default)
    
    def set_config(self, key: str, value: Any):
        """Set configuration value"""
        plugin_config_key = f"plugins.{self.plugin_name}.{key}"
        self.plugin_manager.config_manager.set(plugin_config_key, value)
    
    async def handle_event(self, event: PluginEvent):
        """Handle incoming events"""
        if event.type in self.event_subscriptions:
            for handler in self.event_subscriptions[event.type]:
                try:
                    await handler(event)
                except Exception as e:
                    # Log error but don't propagate
                    pass


class BaseMessageHandler(MessageHandler):
    """Base implementation of MessageHandler with common functionality"""
    
    def __init__(self, priority: int = 100):
        self.priority = priority
    
    def get_priority(self) -> int:
        """Get handler priority"""
        return self.priority
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Default message handling - override in subclasses"""
        return None
    
    def can_handle(self, message: Message) -> bool:
        """Default can_handle - override in subclasses"""
        return False


class BaseCommandHandler(CommandHandler):
    """Base implementation of CommandHandler with common functionality"""
    
    def __init__(self, commands: List[str]):
        self.commands = commands
        self.help_text: Dict[str, str] = {}
    
    def get_commands(self) -> List[str]:
        """Get supported commands"""
        return self.commands
    
    def get_help(self, command: str) -> str:
        """Get help text for command"""
        return self.help_text.get(command, f"No help available for {command}")
    
    def add_help(self, command: str, help_text: str):
        """Add help text for a command"""
        self.help_text[command] = help_text
    
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """Default command handling - override in subclasses"""
        return f"Command {command} not implemented"


class PluginRegistry:
    """Registry for tracking plugin capabilities and interfaces"""
    
    def __init__(self):
        self.message_handlers: Dict[str, List[MessageHandler]] = {}
        self.command_handlers: Dict[str, List[CommandHandler]] = {}
        self.plugin_capabilities: Dict[str, Dict[str, Any]] = {}
    
    def register_message_handler(self, plugin_name: str, handler: MessageHandler):
        """Register a message handler for a plugin"""
        if plugin_name not in self.message_handlers:
            self.message_handlers[plugin_name] = []
        self.message_handlers[plugin_name].append(handler)
    
    def unregister_message_handler(self, plugin_name: str, handler: MessageHandler):
        """Unregister a message handler"""
        if plugin_name in self.message_handlers:
            try:
                self.message_handlers[plugin_name].remove(handler)
            except ValueError:
                pass
    
    def register_command_handler(self, plugin_name: str, handler: CommandHandler):
        """Register a command handler for a plugin"""
        if plugin_name not in self.command_handlers:
            self.command_handlers[plugin_name] = []
        self.command_handlers[plugin_name].append(handler)
    
    def unregister_command_handler(self, plugin_name: str, handler: CommandHandler):
        """Unregister a command handler"""
        if plugin_name in self.command_handlers:
            try:
                self.command_handlers[plugin_name].remove(handler)
            except ValueError:
                pass
    
    def get_message_handlers(self, plugin_name: Optional[str] = None) -> List[MessageHandler]:
        """Get message handlers for a plugin or all plugins"""
        if plugin_name:
            return self.message_handlers.get(plugin_name, [])
        else:
            handlers = []
            for plugin_handlers in self.message_handlers.values():
                handlers.extend(plugin_handlers)
            return sorted(handlers, key=lambda h: h.get_priority())
    
    def get_command_handlers(self, plugin_name: Optional[str] = None) -> List[CommandHandler]:
        """Get command handlers for a plugin or all plugins"""
        if plugin_name:
            return self.command_handlers.get(plugin_name, [])
        else:
            handlers = []
            for plugin_handlers in self.command_handlers.values():
                handlers.extend(plugin_handlers)
            return handlers
    
    def get_available_commands(self) -> Dict[str, str]:
        """Get all available commands with their source plugins"""
        commands = {}
        for plugin_name, handlers in self.command_handlers.items():
            for handler in handlers:
                for command in handler.get_commands():
                    commands[command] = plugin_name
        return commands
    
    def register_plugin_capability(self, plugin_name: str, capability: str, details: Dict[str, Any]):
        """Register a plugin capability"""
        if plugin_name not in self.plugin_capabilities:
            self.plugin_capabilities[plugin_name] = {}
        self.plugin_capabilities[plugin_name][capability] = details
    
    def get_plugin_capabilities(self, plugin_name: str) -> Dict[str, Any]:
        """Get capabilities for a specific plugin"""
        return self.plugin_capabilities.get(plugin_name, {})
    
    def find_plugins_with_capability(self, capability: str) -> List[str]:
        """Find plugins that provide a specific capability"""
        plugins = []
        for plugin_name, capabilities in self.plugin_capabilities.items():
            if capability in capabilities:
                plugins.append(plugin_name)
        return plugins