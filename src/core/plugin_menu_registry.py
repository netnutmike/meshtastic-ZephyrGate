"""
Plugin Menu Registry for BBS Integration

Manages plugin menu items and integrates them with the BBS menu system.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class MenuType(Enum):
    """Menu types matching BBS menu system"""
    MAIN = "main"
    BBS = "bbs"
    MAIL = "mail"
    BULLETINS = "bulletins"
    CHANNELS = "channels"
    UTILITIES = "utilities"
    JS8CALL = "js8call"
    COMPOSE = "compose"
    READ = "read"


@dataclass
class PluginMenuItem:
    """Plugin menu item definition"""
    plugin: str
    menu: MenuType
    label: str
    command: str
    handler: Callable
    description: str = ""
    admin_only: bool = False
    enabled: bool = True
    order: int = 100  # Display order
    parent_command: Optional[str] = None  # For nested submenus


class PluginMenuRegistry:
    """Registry for plugin menu items"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.menu_items: Dict[MenuType, List[PluginMenuItem]] = {}
        self._command_to_item: Dict[str, PluginMenuItem] = {}
    
    def register_menu_item(
        self,
        plugin_name: str,
        menu: str,
        label: str,
        command: str,
        handler: Callable,
        description: str = "",
        admin_only: bool = False,
        order: int = 100,
        parent_command: Optional[str] = None
    ) -> bool:
        """
        Register a plugin menu item.
        
        Args:
            plugin_name: Name of the plugin registering the item
            menu: Menu type (e.g., "main", "utilities")
            label: Display label for the menu item
            command: Command to trigger this menu item
            handler: Async function to handle menu selection
            description: Description of the menu item
            admin_only: Whether item requires admin privileges
            order: Display order (lower = earlier)
            parent_command: Parent command for nested submenus
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Convert menu string to MenuType
            try:
                menu_type = MenuType(menu.lower())
            except ValueError:
                self.logger.error(f"Invalid menu type: {menu}")
                return False
            
            # Create menu item
            item = PluginMenuItem(
                plugin=plugin_name,
                menu=menu_type,
                label=label,
                command=command.lower(),
                handler=handler,
                description=description,
                admin_only=admin_only,
                order=order,
                parent_command=parent_command
            )
            
            # Check for duplicate commands
            if command.lower() in self._command_to_item:
                existing = self._command_to_item[command.lower()]
                self.logger.warning(
                    f"Command '{command}' already registered by plugin '{existing.plugin}'. "
                    f"Overriding with plugin '{plugin_name}'."
                )
            
            # Add to menu items
            if menu_type not in self.menu_items:
                self.menu_items[menu_type] = []
            
            self.menu_items[menu_type].append(item)
            self._command_to_item[command.lower()] = item
            
            # Sort by order
            self.menu_items[menu_type].sort(key=lambda x: x.order)
            
            self.logger.info(
                f"Registered menu item '{label}' (command: {command}) "
                f"for plugin '{plugin_name}' in menu '{menu}'"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering menu item: {e}")
            return False
    
    def unregister_menu_item(self, command: str) -> bool:
        """
        Unregister a menu item by command.
        
        Args:
            command: Command to unregister
            
        Returns:
            True if item was removed, False if not found
        """
        command = command.lower()
        
        if command not in self._command_to_item:
            return False
        
        item = self._command_to_item[command]
        
        # Remove from menu items list
        if item.menu in self.menu_items:
            self.menu_items[item.menu] = [
                i for i in self.menu_items[item.menu] if i.command != command
            ]
        
        # Remove from command mapping
        del self._command_to_item[command]
        
        self.logger.info(f"Unregistered menu item with command '{command}'")
        return True
    
    def unregister_plugin_menu_items(self, plugin_name: str) -> int:
        """
        Unregister all menu items for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Number of items removed
        """
        removed_count = 0
        commands_to_remove = []
        
        # Find all commands for this plugin
        for command, item in self._command_to_item.items():
            if item.plugin == plugin_name:
                commands_to_remove.append(command)
        
        # Remove each command
        for command in commands_to_remove:
            if self.unregister_menu_item(command):
                removed_count += 1
        
        self.logger.info(f"Unregistered {removed_count} menu items for plugin '{plugin_name}'")
        return removed_count
    
    def get_menu_items(self, menu: str, include_disabled: bool = False) -> List[PluginMenuItem]:
        """
        Get menu items for a specific menu.
        
        Args:
            menu: Menu type
            include_disabled: Whether to include disabled items
            
        Returns:
            List of menu items for the menu
        """
        try:
            menu_type = MenuType(menu.lower())
        except ValueError:
            return []
        
        items = self.menu_items.get(menu_type, [])
        
        if not include_disabled:
            items = [item for item in items if item.enabled]
        
        return items
    
    def get_menu_item_by_command(self, command: str) -> Optional[PluginMenuItem]:
        """
        Get menu item by command.
        
        Args:
            command: Command to look up
            
        Returns:
            Menu item if found, None otherwise
        """
        return self._command_to_item.get(command.lower())
    
    async def handle_menu_command(
        self,
        command: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Handle a menu command by routing to the appropriate handler.
        
        Args:
            command: Command to handle
            context: Context dictionary with user, session, etc.
            
        Returns:
            Handler response string, or None if command not found
        """
        item = self.get_menu_item_by_command(command)
        
        if not item:
            return None
        
        if not item.enabled:
            return "This menu item is currently disabled."
        
        # Check admin requirement
        if item.admin_only and not context.get('is_admin', False):
            return "This menu item requires administrator privileges."
        
        try:
            # Call the handler
            result = await item.handler(context)
            return result
        except Exception as e:
            self.logger.error(f"Error handling menu command '{command}': {e}")
            return f"Error executing menu command: {str(e)}"
    
    def get_submenu_items(self, parent_command: str) -> List[PluginMenuItem]:
        """
        Get submenu items for a parent command.
        
        Args:
            parent_command: Parent command
            
        Returns:
            List of submenu items
        """
        submenu_items = []
        
        for items in self.menu_items.values():
            for item in items:
                if item.parent_command == parent_command and item.enabled:
                    submenu_items.append(item)
        
        # Sort by order
        submenu_items.sort(key=lambda x: x.order)
        
        return submenu_items
    
    def format_menu_items(self, menu: str, include_plugin_items: bool = True) -> List[str]:
        """
        Format menu items for display.
        
        Args:
            menu: Menu type
            include_plugin_items: Whether to include plugin menu items
            
        Returns:
            List of formatted menu item strings
        """
        if not include_plugin_items:
            return []
        
        items = self.get_menu_items(menu)
        formatted = []
        
        for item in items:
            # Format: "command - description"
            formatted.append(f"{item.command:12} - {item.description or item.label}")
        
        return formatted
    
    def enable_menu_item(self, command: str) -> bool:
        """
        Enable a menu item.
        
        Args:
            command: Command to enable
            
        Returns:
            True if item was enabled, False if not found
        """
        item = self.get_menu_item_by_command(command)
        
        if item:
            item.enabled = True
            self.logger.info(f"Enabled menu item with command '{command}'")
            return True
        
        return False
    
    def disable_menu_item(self, command: str) -> bool:
        """
        Disable a menu item.
        
        Args:
            command: Command to disable
            
        Returns:
            True if item was disabled, False if not found
        """
        item = self.get_menu_item_by_command(command)
        
        if item:
            item.enabled = False
            self.logger.info(f"Disabled menu item with command '{command}'")
            return True
        
        return False
    
    def get_all_commands(self) -> List[str]:
        """
        Get all registered commands.
        
        Returns:
            List of all commands
        """
        return list(self._command_to_item.keys())
    
    def get_plugin_commands(self, plugin_name: str) -> List[str]:
        """
        Get all commands registered by a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            List of commands
        """
        commands = []
        
        for command, item in self._command_to_item.items():
            if item.plugin == plugin_name:
                commands.append(command)
        
        return commands
