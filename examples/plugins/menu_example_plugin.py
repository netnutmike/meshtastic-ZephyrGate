"""
Example plugin demonstrating BBS menu integration.

This plugin shows how to add custom menu items to the BBS system.
"""

from typing import Dict, Any
from src.core.enhanced_plugin import EnhancedPlugin


class MenuExamplePlugin(EnhancedPlugin):
    """Example plugin with BBS menu integration"""
    
    async def initialize(self) -> bool:
        """Initialize the plugin and register menu items"""
        self.logger.info("Initializing Menu Example Plugin")
        
        # Register a menu item in the utilities menu
        self.register_menu_item(
            menu="utilities",
            label="Plugin Demo",
            handler=self.demo_handler,
            description="Demonstration of plugin menu integration",
            command="plugindemo",
            order=150
        )
        
        # Register another menu item with admin requirement
        self.register_menu_item(
            menu="utilities",
            label="Admin Demo",
            handler=self.admin_handler,
            description="Admin-only demonstration",
            command="admindemo",
            admin_only=True,
            order=151
        )
        
        # Register a menu item in the main menu
        self.register_menu_item(
            menu="main",
            label="Quick Demo",
            handler=self.quick_handler,
            description="Quick demo from main menu",
            command="quickdemo",
            order=200
        )
        
        return True
    
    async def demo_handler(self, context: Dict[str, Any]) -> str:
        """
        Handle the demo menu item selection.
        
        Args:
            context: Context dictionary with user info, session, etc.
            
        Returns:
            Response string to display to user
        """
        user_name = context.get('user_name', 'Unknown')
        user_id = context.get('user_id', 'Unknown')
        
        response = []
        response.append("=== Plugin Demo ===")
        response.append("")
        response.append(f"Hello {user_name} ({user_id})!")
        response.append("")
        response.append("This is a demonstration of plugin menu integration.")
        response.append("Plugins can add custom menu items to any BBS menu.")
        response.append("")
        response.append("Features:")
        response.append("- Custom menu items in any menu")
        response.append("- Access to user context and session")
        response.append("- Admin-only menu items")
        response.append("- Dynamic menu item ordering")
        response.append("")
        response.append("Type 'back' to return to the previous menu.")
        
        return "\n".join(response)
    
    async def admin_handler(self, context: Dict[str, Any]) -> str:
        """
        Handle the admin-only menu item.
        
        This handler will only be called if the user has admin privileges.
        """
        response = []
        response.append("=== Admin Demo ===")
        response.append("")
        response.append("This is an admin-only menu item.")
        response.append("Only users with admin privileges can access this.")
        response.append("")
        response.append("Admin features could include:")
        response.append("- Plugin configuration")
        response.append("- System management")
        response.append("- User administration")
        response.append("")
        
        return "\n".join(response)
    
    async def quick_handler(self, context: Dict[str, Any]) -> str:
        """
        Handle the quick demo from main menu.
        """
        return "Quick Demo: This menu item is accessible from the main menu!"


# Plugin metadata for discovery
PLUGIN_NAME = "menu_example"
PLUGIN_CLASS = MenuExamplePlugin
PLUGIN_DESCRIPTION = "Example plugin demonstrating BBS menu integration"
PLUGIN_VERSION = "1.0.0"
