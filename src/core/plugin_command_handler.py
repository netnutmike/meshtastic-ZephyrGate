"""
Plugin Command Handler System

Provides command registration, routing, and execution for third-party plugins.
Supports priority-based handler execution and context building.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

try:
    from ..models.message import Message, MessageType
except ImportError:
    from models.message import Message, MessageType
from .plugin_interfaces import BaseCommandHandler
from .logging import get_logger


@dataclass
class CommandContext:
    """Context provided to command handlers"""
    message: Message
    sender_id: str
    sender_name: Optional[str] = None
    channel: int = 0
    is_dm: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    interface_id: Optional[str] = None
    user_profile: Optional[Any] = None
    session_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            'message': self.message,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'channel': self.channel,
            'is_dm': self.is_dm,
            'timestamp': self.timestamp,
            'interface_id': self.interface_id,
            'user_profile': self.user_profile,
            'session_data': self.session_data
        }


@dataclass
class RegisteredCommand:
    """Represents a registered command with its handler"""
    command: str
    plugin_name: str
    handler: Callable
    help_text: str
    priority: int
    handler_instance: BaseCommandHandler
    
    def __lt__(self, other):
        """Compare by priority for sorting (lower priority value = higher precedence)"""
        return self.priority < other.priority


class PluginCommandHandler:
    """
    Central command handler system for plugins.
    
    Manages command registration, routing, and execution with priority support.
    """
    
    def __init__(self):
        self.logger = get_logger('plugin_command_handler')
        
        # Command registry: command_name -> List[RegisteredCommand]
        self._commands: Dict[str, List[RegisteredCommand]] = {}
        
        # Plugin registry: plugin_name -> List[command_names]
        self._plugin_commands: Dict[str, List[str]] = {}
        
        # Statistics
        self.stats = {
            'commands_registered': 0,
            'commands_executed': 0,
            'commands_failed': 0,
            'total_plugins': 0
        }
        
        self.logger.info("Plugin command handler initialized")
    
    def register_command(self, plugin_name: str, command: str, handler: Callable,
                        help_text: str = "", priority: int = 100,
                        handler_instance: Optional[BaseCommandHandler] = None) -> bool:
        """
        Register a command handler for a plugin.
        
        Args:
            plugin_name: Name of the plugin registering the command
            command: Command name (without prefix)
            handler: Async function that takes (args: List[str], context: Dict) -> str
            help_text: Help text for the command
            priority: Handler priority (lower = higher priority, default 100)
            handler_instance: Optional BaseCommandHandler instance
            
        Returns:
            True if registration successful
            
        Example:
            async def my_command(args, context):
                return f"Hello {context['sender_id']}"
            
            handler.register_command("my_plugin", "hello", my_command, "Say hello", priority=50)
        """
        try:
            command_lower = command.lower()
            
            # Create registered command entry
            registered_cmd = RegisteredCommand(
                command=command_lower,
                plugin_name=plugin_name,
                handler=handler,
                help_text=help_text,
                priority=priority,
                handler_instance=handler_instance
            )
            
            # Add to command registry
            if command_lower not in self._commands:
                self._commands[command_lower] = []
            
            self._commands[command_lower].append(registered_cmd)
            
            # Sort by priority (lower priority value = higher precedence)
            self._commands[command_lower].sort()
            
            # Track plugin commands
            if plugin_name not in self._plugin_commands:
                self._plugin_commands[plugin_name] = []
                self.stats['total_plugins'] += 1
            
            if command_lower not in self._plugin_commands[plugin_name]:
                self._plugin_commands[plugin_name].append(command_lower)
            
            self.stats['commands_registered'] += 1
            
            self.logger.info(
                f"Registered command '{command_lower}' for plugin '{plugin_name}' "
                f"with priority {priority}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register command '{command}' for plugin '{plugin_name}': {e}")
            return False
    
    def unregister_command(self, plugin_name: str, command: str) -> bool:
        """
        Unregister a command handler for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            command: Command name
            
        Returns:
            True if unregistration successful
        """
        try:
            command_lower = command.lower()
            
            if command_lower not in self._commands:
                return False
            
            # Remove command from registry
            original_count = len(self._commands[command_lower])
            self._commands[command_lower] = [
                cmd for cmd in self._commands[command_lower]
                if cmd.plugin_name != plugin_name
            ]
            
            # Remove empty command entries
            if not self._commands[command_lower]:
                del self._commands[command_lower]
            
            # Update plugin commands
            if plugin_name in self._plugin_commands:
                if command_lower in self._plugin_commands[plugin_name]:
                    self._plugin_commands[plugin_name].remove(command_lower)
                
                # Remove plugin entry if no commands left
                if not self._plugin_commands[plugin_name]:
                    del self._plugin_commands[plugin_name]
                    self.stats['total_plugins'] -= 1
            
            removed_count = original_count - len(self._commands.get(command_lower, []))
            if removed_count > 0:
                self.stats['commands_registered'] -= removed_count
                self.logger.info(f"Unregistered command '{command_lower}' for plugin '{plugin_name}'")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to unregister command '{command}' for plugin '{plugin_name}': {e}")
            return False
    
    def unregister_plugin_commands(self, plugin_name: str) -> int:
        """
        Unregister all commands for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Number of commands unregistered
        """
        if plugin_name not in self._plugin_commands:
            return 0
        
        commands = list(self._plugin_commands[plugin_name])
        count = 0
        
        for command in commands:
            if self.unregister_command(plugin_name, command):
                count += 1
        
        self.logger.info(f"Unregistered {count} commands for plugin '{plugin_name}'")
        return count
    
    async def route_command(self, message: Message, user_profile: Optional[Any] = None) -> Optional[str]:
        """
        Route a message to appropriate command handlers.
        
        Args:
            message: The message containing the command
            user_profile: Optional user profile for context
            
        Returns:
            Response string from the handler, or None if no handler found
        """
        try:
            content = message.content.strip()
            
            # Parse command and arguments
            parts = content.split(maxsplit=1)
            if not parts:
                return None
            
            command = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []
            
            # Check if command is registered
            if command not in self._commands:
                return None
            
            # Build context
            context = self._build_context(message, user_profile)
            
            # Execute handlers in priority order
            handlers = self._commands[command]
            
            for registered_cmd in handlers:
                try:
                    self.logger.debug(
                        f"Executing command '{command}' via plugin '{registered_cmd.plugin_name}' "
                        f"(priority {registered_cmd.priority})"
                    )
                    
                    # Execute handler
                    response = await registered_cmd.handler(args, context.to_dict())
                    
                    self.stats['commands_executed'] += 1
                    
                    # Return first successful response
                    if response:
                        return response
                    
                except Exception as e:
                    self.logger.error(
                        f"Error executing command '{command}' in plugin '{registered_cmd.plugin_name}': {e}"
                    )
                    self.stats['commands_failed'] += 1
                    
                    # Continue to next handler
                    continue
            
            # No handler produced a response
            return None
            
        except Exception as e:
            self.logger.error(f"Error routing command: {e}")
            self.stats['commands_failed'] += 1
            return None
    
    def _build_context(self, message: Message, user_profile: Optional[Any] = None) -> CommandContext:
        """
        Build command context from message and user profile.
        
        Args:
            message: The message
            user_profile: Optional user profile
            
        Returns:
            CommandContext object
        """
        sender_name = None
        if user_profile:
            sender_name = getattr(user_profile, 'short_name', None) or \
                         getattr(user_profile, 'long_name', None)
        
        return CommandContext(
            message=message,
            sender_id=message.sender_id,
            sender_name=sender_name,
            channel=message.channel,
            is_dm=message.is_direct_message(),
            timestamp=message.timestamp,
            interface_id=getattr(message, 'interface_id', None),
            user_profile=user_profile,
            session_data={}
        )
    
    def get_command_info(self, command: str) -> List[Dict[str, Any]]:
        """
        Get information about a command and its handlers.
        
        Args:
            command: Command name
            
        Returns:
            List of handler information dictionaries
        """
        command_lower = command.lower()
        
        if command_lower not in self._commands:
            return []
        
        return [
            {
                'command': cmd.command,
                'plugin': cmd.plugin_name,
                'help': cmd.help_text,
                'priority': cmd.priority
            }
            for cmd in self._commands[command_lower]
        ]
    
    def get_plugin_commands(self, plugin_name: str) -> List[str]:
        """
        Get all commands registered by a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            List of command names
        """
        return self._plugin_commands.get(plugin_name, [])
    
    def get_all_commands(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all registered commands with their handlers.
        
        Returns:
            Dictionary mapping command names to handler info lists
        """
        result = {}
        
        for command, handlers in self._commands.items():
            result[command] = [
                {
                    'plugin': cmd.plugin_name,
                    'help': cmd.help_text,
                    'priority': cmd.priority
                }
                for cmd in handlers
            ]
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get command handler statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            'unique_commands': len(self._commands),
            'total_handlers': sum(len(handlers) for handlers in self._commands.values())
        }
    
    def has_command(self, command: str) -> bool:
        """
        Check if a command is registered.
        
        Args:
            command: Command name
            
        Returns:
            True if command is registered
        """
        return command.lower() in self._commands
    
    def get_command_help(self, command: str) -> List[str]:
        """
        Get help text for a command from all registered handlers.
        
        Args:
            command: Command name
            
        Returns:
            List of help text strings
        """
        command_lower = command.lower()
        
        if command_lower not in self._commands:
            return []
        
        return [
            f"{cmd.plugin_name}: {cmd.help_text}" if cmd.help_text else f"{cmd.plugin_name}: No help available"
            for cmd in self._commands[command_lower]
        ]
