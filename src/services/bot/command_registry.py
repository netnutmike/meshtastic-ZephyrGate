"""
Command Registry and Dispatch System

Provides centralized command registration, dispatch, and management for the bot service.
Implements comprehensive command parser with help system, command registration for all
service modules, command documentation and usage help, and command permissions and access control.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Callable, Any, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from core.plugin_interfaces import CommandHandler, BaseCommandHandler


class CommandPermission(Enum):
    """Command permission levels"""
    PUBLIC = "public"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class CommandMetadata:
    """Metadata for registered commands"""
    name: str
    handler: CommandHandler
    plugin_name: str
    description: str
    usage: str = ""
    examples: List[str] = field(default_factory=list)
    permissions: List[CommandPermission] = field(default_factory=lambda: [CommandPermission.PUBLIC])
    aliases: List[str] = field(default_factory=list)
    category: str = "general"
    enabled: bool = True
    hidden: bool = False
    rate_limit: Optional[int] = None  # Commands per minute
    cooldown: Optional[int] = None    # Seconds between uses
    syntax: str = ""  # Command syntax specification
    parameters: List[str] = field(default_factory=list)  # Parameter descriptions
    returns: str = ""  # Return value description
    version: str = "1.0"  # Command version
    deprecated: bool = False  # Whether command is deprecated
    replacement: Optional[str] = None  # Replacement command if deprecated


@dataclass
class CommandContext:
    """Context information for command execution"""
    sender_id: str
    sender_name: str = ""
    channel: int = 0
    is_direct_message: bool = False
    is_admin: bool = False
    is_moderator: bool = False
    user_permissions: Set[str] = field(default_factory=set)
    message_timestamp: Optional[float] = None
    interface_id: str = ""
    additional_data: Dict[str, Any] = field(default_factory=dict)


class CommandRegistry:
    """
    Central registry for all bot commands with dispatch and management capabilities
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Command storage
        self.commands: Dict[str, CommandMetadata] = {}
        self.aliases: Dict[str, str] = {}
        self.categories: Dict[str, List[str]] = {}
        
        # Rate limiting and cooldowns
        self.rate_limits: Dict[str, Dict[str, List[float]]] = {}  # user_id -> command -> timestamps
        self.cooldowns: Dict[str, Dict[str, float]] = {}  # user_id -> command -> last_used
        
        # Permission system
        self.user_permissions: Dict[str, Set[CommandPermission]] = {}
        self.admin_users: Set[str] = set()
        self.moderator_users: Set[str] = set()
        
        # Command hooks
        self.pre_command_hooks: List[Callable] = []
        self.post_command_hooks: List[Callable] = []
        
        # Statistics
        self.command_stats: Dict[str, int] = {}
        self.error_stats: Dict[str, int] = {}
    
    def register_command(self, handler: CommandHandler, plugin_name: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Register commands from a command handler
        
        Args:
            handler: The command handler to register
            plugin_name: Name of the plugin registering the handler
            metadata: Optional metadata for the commands
            
        Returns:
            List of registered command names
        """
        registered_commands = []
        metadata = metadata or {}
        
        for command in handler.get_commands():
            # Create command metadata
            cmd_metadata = CommandMetadata(
                name=command,
                handler=handler,
                plugin_name=plugin_name,
                description=handler.get_help(command),
                usage=metadata.get('usage', {}).get(command, f"{command} [args]"),
                examples=metadata.get('examples', {}).get(command, []),
                permissions=metadata.get('permissions', {}).get(command, [CommandPermission.PUBLIC]),
                aliases=metadata.get('aliases', {}).get(command, []),
                category=metadata.get('category', {}).get(command, plugin_name),
                enabled=metadata.get('enabled', {}).get(command, True),
                hidden=metadata.get('hidden', {}).get(command, False),
                rate_limit=metadata.get('rate_limit', {}).get(command),
                cooldown=metadata.get('cooldown', {}).get(command)
            )
            
            # Register command
            self.commands[command] = cmd_metadata
            registered_commands.append(command)
            
            # Register aliases
            for alias in cmd_metadata.aliases:
                self.aliases[alias] = command
            
            # Add to category
            if cmd_metadata.category not in self.categories:
                self.categories[cmd_metadata.category] = []
            if command not in self.categories[cmd_metadata.category]:
                self.categories[cmd_metadata.category].append(command)
            
            # Initialize stats
            if command not in self.command_stats:
                self.command_stats[command] = 0
            
            self.logger.debug(f"Registered command '{command}' from plugin '{plugin_name}'")
        
        return registered_commands
    
    def unregister_command(self, command: str, plugin_name: str) -> bool:
        """
        Unregister a command
        
        Args:
            command: Command name to unregister
            plugin_name: Plugin name (for verification)
            
        Returns:
            True if command was unregistered
        """
        if command not in self.commands:
            return False
        
        cmd_metadata = self.commands[command]
        if cmd_metadata.plugin_name != plugin_name:
            self.logger.warning(f"Plugin '{plugin_name}' tried to unregister command '{command}' "
                              f"owned by '{cmd_metadata.plugin_name}'")
            return False
        
        # Remove from categories
        if cmd_metadata.category in self.categories:
            try:
                self.categories[cmd_metadata.category].remove(command)
                if not self.categories[cmd_metadata.category]:
                    del self.categories[cmd_metadata.category]
            except ValueError:
                pass
        
        # Remove aliases
        aliases_to_remove = [alias for alias, cmd in self.aliases.items() if cmd == command]
        for alias in aliases_to_remove:
            del self.aliases[alias]
        
        # Remove command
        del self.commands[command]
        
        self.logger.debug(f"Unregistered command '{command}' from plugin '{plugin_name}'")
        return True
    
    def unregister_plugin_commands(self, plugin_name: str) -> List[str]:
        """
        Unregister all commands from a plugin
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            List of unregistered command names
        """
        commands_to_remove = [
            cmd for cmd, metadata in self.commands.items() 
            if metadata.plugin_name == plugin_name
        ]
        
        for command in commands_to_remove:
            self.unregister_command(command, plugin_name)
        
        return commands_to_remove
    
    async def dispatch_command(self, command_text: str, context: CommandContext) -> str:
        """
        Dispatch a command for execution
        
        Args:
            command_text: The command text to parse and execute
            context: Command execution context
            
        Returns:
            Command response text
        """
        try:
            # Parse command
            parts = command_text.strip().split()
            if not parts:
                return "Empty command"
            
            command_name = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Resolve aliases
            if command_name in self.aliases:
                command_name = self.aliases[command_name]
            
            # Check if command exists
            if command_name not in self.commands:
                return f"Unknown command: {command_name}. Send 'help' for available commands."
            
            cmd_metadata = self.commands[command_name]
            
            # Check if command is enabled
            if not cmd_metadata.enabled:
                return f"Command '{command_name}' is currently disabled."
            
            # Check permissions
            if not await self._check_permissions(cmd_metadata, context):
                return f"You don't have permission to use the '{command_name}' command."
            
            # Check rate limits
            if not await self._check_rate_limit(cmd_metadata, context):
                return f"Rate limit exceeded for command '{command_name}'. Please wait before trying again."
            
            # Check cooldowns
            if not await self._check_cooldown(cmd_metadata, context):
                cooldown_time = cmd_metadata.cooldown
                return f"Command '{command_name}' is on cooldown. Wait {cooldown_time} seconds."
            
            # Execute pre-command hooks
            for hook in self.pre_command_hooks:
                try:
                    await hook(command_name, args, context)
                except Exception as e:
                    self.logger.error(f"Pre-command hook error: {e}")
            
            # Execute command
            handler_context = {
                'sender_id': context.sender_id,
                'sender_name': context.sender_name,
                'channel': context.channel,
                'is_direct_message': context.is_direct_message,
                'is_admin': context.is_admin,
                'is_moderator': context.is_moderator,
                'user_permissions': context.user_permissions,
                'message_timestamp': context.message_timestamp,
                'interface_id': context.interface_id,
                **context.additional_data
            }
            
            response = await cmd_metadata.handler.handle_command(command_name, args, handler_context)
            
            # Update statistics
            self.command_stats[command_name] += 1
            
            # Update rate limits and cooldowns
            await self._update_rate_limit(cmd_metadata, context)
            await self._update_cooldown(cmd_metadata, context)
            
            # Execute post-command hooks
            for hook in self.post_command_hooks:
                try:
                    await hook(command_name, args, context, response)
                except Exception as e:
                    self.logger.error(f"Post-command hook error: {e}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error dispatching command '{command_text}': {e}")
            
            # Update error statistics
            command_name = command_text.split()[0] if command_text.split() else "unknown"
            if command_name not in self.error_stats:
                self.error_stats[command_name] = 0
            self.error_stats[command_name] += 1
            
            return f"Error executing command. Please try again."
    
    def get_command_help(self, command: str, detailed: bool = False) -> Optional[str]:
        """Get help text for a command"""
        if command in self.aliases:
            command = self.aliases[command]
        
        if command not in self.commands:
            return None
        
        cmd_metadata = self.commands[command]
        
        if detailed:
            # Detailed help format
            help_text = f"📋 **{command.upper()}** - {cmd_metadata.description}\n\n"
            
            if cmd_metadata.syntax:
                help_text += f"**Syntax:** {cmd_metadata.syntax}\n"
            else:
                help_text += f"**Usage:** {cmd_metadata.usage}\n"
            
            if cmd_metadata.parameters:
                help_text += f"**Parameters:**\n"
                for param in cmd_metadata.parameters:
                    help_text += f"  • {param}\n"
            
            if cmd_metadata.aliases:
                help_text += f"**Aliases:** {', '.join(cmd_metadata.aliases)}\n"
            
            help_text += f"**Category:** {cmd_metadata.category}\n"
            help_text += f"**Plugin:** {cmd_metadata.plugin_name}\n"
            
            if cmd_metadata.permissions != [CommandPermission.PUBLIC]:
                perm_names = [p.value for p in cmd_metadata.permissions]
                help_text += f"**Permissions:** {', '.join(perm_names)}\n"
            
            if cmd_metadata.rate_limit:
                help_text += f"**Rate Limit:** {cmd_metadata.rate_limit} uses/minute\n"
            
            if cmd_metadata.cooldown:
                help_text += f"**Cooldown:** {cmd_metadata.cooldown} seconds\n"
            
            if cmd_metadata.deprecated:
                help_text += f"⚠️ **DEPRECATED**"
                if cmd_metadata.replacement:
                    help_text += f" - Use '{cmd_metadata.replacement}' instead"
                help_text += "\n"
            
            if cmd_metadata.examples:
                help_text += f"\n**Examples:**\n"
                for example in cmd_metadata.examples:
                    help_text += f"  {example}\n"
            
            if cmd_metadata.returns:
                help_text += f"\n**Returns:** {cmd_metadata.returns}\n"
            
        else:
            # Brief help format
            help_text = f"**{command}**: {cmd_metadata.description}"
            if cmd_metadata.usage:
                help_text += f" - Usage: {cmd_metadata.usage}"
            if cmd_metadata.deprecated:
                help_text += " ⚠️ DEPRECATED"
        
        return help_text.strip()
    
    def get_help_summary(self, context: CommandContext, category: Optional[str] = None) -> str:
        """Get a summary of available commands"""
        available_commands = self.get_available_commands(context, include_hidden=False)
        
        if category:
            # Filter by category
            category_commands = []
            for cmd in available_commands:
                if self.commands[cmd].category == category:
                    category_commands.append(cmd)
            available_commands = category_commands
        
        if not available_commands:
            return "No commands available."
        
        # Group by category
        categories = {}
        for cmd in available_commands:
            cmd_category = self.commands[cmd].category
            if cmd_category not in categories:
                categories[cmd_category] = []
            categories[cmd_category].append(cmd)
        
        help_text = "📋 **Available Commands**\n\n"
        
        for cat, commands in sorted(categories.items()):
            help_text += f"**{cat.title()}:**\n"
            for cmd in sorted(commands):
                cmd_meta = self.commands[cmd]
                help_text += f"  • `{cmd}` - {cmd_meta.description}"
                if cmd_meta.deprecated:
                    help_text += " ⚠️"
                help_text += "\n"
            help_text += "\n"
        
        help_text += "💡 Send `help <command>` for detailed information about a specific command.\n"
        help_text += "📚 Send `help categories` to see all available categories."
        
        return help_text.strip()
    
    def get_categories_help(self) -> str:
        """Get help text for all categories"""
        categories = {}
        for cmd, metadata in self.commands.items():
            if not metadata.hidden and metadata.enabled:
                if metadata.category not in categories:
                    categories[metadata.category] = []
                categories[metadata.category].append(cmd)
        
        help_text = "📚 **Command Categories**\n\n"
        
        for category, commands in sorted(categories.items()):
            help_text += f"**{category.title()}** ({len(commands)} commands)\n"
            help_text += f"  Send `help {category}` to see commands in this category\n\n"
        
        return help_text.strip()
    
    def get_commands_by_category(self, include_hidden: bool = False) -> Dict[str, List[str]]:
        """Get commands organized by category"""
        result = {}
        
        for category, commands in self.categories.items():
            visible_commands = []
            for command in commands:
                cmd_metadata = self.commands[command]
                if include_hidden or not cmd_metadata.hidden:
                    visible_commands.append(command)
            
            if visible_commands:
                result[category] = sorted(visible_commands)
        
        return result
    
    def get_available_commands(self, context: CommandContext, include_hidden: bool = False) -> List[str]:
        """Get commands available to a user based on their permissions"""
        available = []
        
        for command, cmd_metadata in self.commands.items():
            if not cmd_metadata.enabled:
                continue
            
            if not include_hidden and cmd_metadata.hidden:
                continue
            
            # Check permissions (simplified check)
            if CommandPermission.PUBLIC in cmd_metadata.permissions:
                available.append(command)
            elif context.is_admin and CommandPermission.ADMIN in cmd_metadata.permissions:
                available.append(command)
            elif context.is_moderator and CommandPermission.MODERATOR in cmd_metadata.permissions:
                available.append(command)
        
        return sorted(available)
    
    def get_command_statistics(self) -> Dict[str, Any]:
        """Get command usage statistics"""
        return {
            'total_commands': len(self.commands),
            'total_categories': len(self.categories),
            'command_usage': self.command_stats.copy(),
            'error_counts': self.error_stats.copy(),
            'most_used': sorted(self.command_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    def set_user_permissions(self, user_id: str, permissions: Set[CommandPermission]):
        """Set permissions for a user"""
        self.user_permissions[user_id] = permissions
        
        if CommandPermission.ADMIN in permissions:
            self.admin_users.add(user_id)
        else:
            self.admin_users.discard(user_id)
        
        if CommandPermission.MODERATOR in permissions:
            self.moderator_users.add(user_id)
        else:
            self.moderator_users.discard(user_id)
    
    def add_pre_command_hook(self, hook: Callable):
        """Add a pre-command execution hook"""
        self.pre_command_hooks.append(hook)
    
    def add_post_command_hook(self, hook: Callable):
        """Add a post-command execution hook"""
        self.post_command_hooks.append(hook)
    
    async def _check_permissions(self, cmd_metadata: CommandMetadata, context: CommandContext) -> bool:
        """Check if user has permission to execute command"""
        # Public commands are always allowed
        if CommandPermission.PUBLIC in cmd_metadata.permissions:
            return True
        
        # Check admin permissions
        if CommandPermission.ADMIN in cmd_metadata.permissions:
            return context.is_admin or context.sender_id in self.admin_users
        
        # Check moderator permissions
        if CommandPermission.MODERATOR in cmd_metadata.permissions:
            return (context.is_moderator or context.sender_id in self.moderator_users or
                   context.is_admin or context.sender_id in self.admin_users)
        
        # Check user permissions
        if CommandPermission.USER in cmd_metadata.permissions:
            user_perms = self.user_permissions.get(context.sender_id, set())
            return bool(user_perms.intersection(cmd_metadata.permissions))
        
        return False
    
    async def _check_rate_limit(self, cmd_metadata: CommandMetadata, context: CommandContext) -> bool:
        """Check if command is within rate limits"""
        if not cmd_metadata.rate_limit:
            return True
        
        user_id = context.sender_id
        command = cmd_metadata.name
        current_time = asyncio.get_event_loop().time()
        
        # Initialize rate limit tracking
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = {}
        if command not in self.rate_limits[user_id]:
            self.rate_limits[user_id][command] = []
        
        # Clean old timestamps (older than 1 minute)
        timestamps = self.rate_limits[user_id][command]
        timestamps[:] = [ts for ts in timestamps if current_time - ts < 60]
        
        # Check if under limit
        return len(timestamps) < cmd_metadata.rate_limit
    
    async def _check_cooldown(self, cmd_metadata: CommandMetadata, context: CommandContext) -> bool:
        """Check if command is off cooldown"""
        if not cmd_metadata.cooldown:
            return True
        
        user_id = context.sender_id
        command = cmd_metadata.name
        current_time = asyncio.get_event_loop().time()
        
        # Initialize cooldown tracking
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        
        last_used = self.cooldowns[user_id].get(command, 0)
        return current_time - last_used >= cmd_metadata.cooldown
    
    async def _update_rate_limit(self, cmd_metadata: CommandMetadata, context: CommandContext):
        """Update rate limit tracking"""
        if not cmd_metadata.rate_limit:
            return
        
        user_id = context.sender_id
        command = cmd_metadata.name
        current_time = asyncio.get_event_loop().time()
        
        self.rate_limits[user_id][command].append(current_time)
    
    async def _update_cooldown(self, cmd_metadata: CommandMetadata, context: CommandContext):
        """Update cooldown tracking"""
        if not cmd_metadata.cooldown:
            return
        
        user_id = context.sender_id
        command = cmd_metadata.name
        current_time = asyncio.get_event_loop().time()
        
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        
        self.cooldowns[user_id][command] = current_time