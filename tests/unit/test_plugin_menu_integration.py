"""
Unit tests for plugin menu integration.

Tests the integration between PluginMenuRegistry, EnhancedPlugin, and BBS menu system.
"""

import pytest
from typing import Dict, Any

from src.core.plugin_menu_registry import PluginMenuRegistry, MenuType
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginManager


class TestPluginMenuIntegration:
    """Test plugin menu integration"""
    
    def test_menu_registry_creation(self):
        """Test creating a menu registry"""
        registry = PluginMenuRegistry()
        assert registry is not None
        assert len(registry.menu_items) == 0
    
    def test_register_single_menu_item(self):
        """Test registering a single menu item"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Test response"
        
        success = registry.register_menu_item(
            plugin_name="test_plugin",
            menu="utilities",
            label="Test Item",
            command="testcmd",
            handler=handler,
            description="Test menu item"
        )
        
        assert success
        
        # Verify item is registered
        items = registry.get_menu_items("utilities")
        assert len(items) == 1
        assert items[0].command == "testcmd"
        assert items[0].label == "Test Item"
    
    def test_register_multiple_menu_items(self):
        """Test registering multiple menu items"""
        registry = PluginMenuRegistry()
        
        async def handler1(context: Dict[str, Any]) -> str:
            return "Handler 1"
        
        async def handler2(context: Dict[str, Any]) -> str:
            return "Handler 2"
        
        registry.register_menu_item(
            plugin_name="plugin1",
            menu="utilities",
            label="Item 1",
            command="cmd1",
            handler=handler1
        )
        
        registry.register_menu_item(
            plugin_name="plugin2",
            menu="utilities",
            label="Item 2",
            command="cmd2",
            handler=handler2
        )
        
        items = registry.get_menu_items("utilities")
        assert len(items) == 2
        
        commands = [item.command for item in items]
        assert "cmd1" in commands
        assert "cmd2" in commands
    
    @pytest.mark.asyncio
    async def test_menu_command_routing(self):
        """Test routing menu commands to handlers"""
        registry = PluginMenuRegistry()
        
        result_value = None
        
        async def handler(context: Dict[str, Any]) -> str:
            nonlocal result_value
            result_value = context.get('test_key')
            return f"Received: {result_value}"
        
        registry.register_menu_item(
            plugin_name="test_plugin",
            menu="utilities",
            label="Test",
            command="test",
            handler=handler
        )
        
        context = {'test_key': 'test_value'}
        result = await registry.handle_menu_command("test", context)
        
        assert result == "Received: test_value"
        assert result_value == "test_value"
    
    def test_unregister_menu_item(self):
        """Test unregistering a menu item"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Test"
        
        registry.register_menu_item(
            plugin_name="test_plugin",
            menu="utilities",
            label="Test",
            command="test",
            handler=handler
        )
        
        # Verify registered
        items = registry.get_menu_items("utilities")
        assert len(items) == 1
        
        # Unregister
        success = registry.unregister_menu_item("test")
        assert success
        
        # Verify removed
        items = registry.get_menu_items("utilities")
        assert len(items) == 0
    
    def test_unregister_plugin_menu_items(self):
        """Test unregistering all menu items for a plugin"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Test"
        
        # Register multiple items for same plugin
        registry.register_menu_item(
            plugin_name="test_plugin",
            menu="utilities",
            label="Test 1",
            command="test1",
            handler=handler
        )
        
        registry.register_menu_item(
            plugin_name="test_plugin",
            menu="main",
            label="Test 2",
            command="test2",
            handler=handler
        )
        
        # Register item for different plugin
        registry.register_menu_item(
            plugin_name="other_plugin",
            menu="utilities",
            label="Other",
            command="other",
            handler=handler
        )
        
        # Verify all registered
        assert len(registry.get_all_commands()) == 3
        
        # Unregister all items for test_plugin
        removed = registry.unregister_plugin_menu_items("test_plugin")
        assert removed == 2
        
        # Verify only other_plugin item remains
        assert len(registry.get_all_commands()) == 1
        assert "other" in registry.get_all_commands()
    
    def test_menu_item_ordering(self):
        """Test menu items are ordered correctly"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Test"
        
        # Register items with different orders
        registry.register_menu_item(
            plugin_name="plugin",
            menu="utilities",
            label="Third",
            command="third",
            handler=handler,
            order=300
        )
        
        registry.register_menu_item(
            plugin_name="plugin",
            menu="utilities",
            label="First",
            command="first",
            handler=handler,
            order=100
        )
        
        registry.register_menu_item(
            plugin_name="plugin",
            menu="utilities",
            label="Second",
            command="second",
            handler=handler,
            order=200
        )
        
        items = registry.get_menu_items("utilities")
        assert len(items) == 3
        
        # Verify order
        assert items[0].command == "first"
        assert items[1].command == "second"
        assert items[2].command == "third"
    
    @pytest.mark.asyncio
    async def test_disabled_menu_item(self):
        """Test disabling and enabling menu items"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Success"
        
        registry.register_menu_item(
            plugin_name="plugin",
            menu="utilities",
            label="Test",
            command="test",
            handler=handler
        )
        
        # Verify enabled
        context = {}
        result = await registry.handle_menu_command("test", context)
        assert result == "Success"
        
        # Disable
        registry.disable_menu_item("test")
        
        # Verify disabled
        result = await registry.handle_menu_command("test", context)
        assert "disabled" in result.lower()
        
        # Re-enable
        registry.enable_menu_item("test")
        
        # Verify enabled again
        result = await registry.handle_menu_command("test", context)
        assert result == "Success"
    
    def test_get_plugin_commands(self):
        """Test getting all commands for a plugin"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Test"
        
        registry.register_menu_item(
            plugin_name="plugin1",
            menu="utilities",
            label="Test 1",
            command="test1",
            handler=handler
        )
        
        registry.register_menu_item(
            plugin_name="plugin1",
            menu="main",
            label="Test 2",
            command="test2",
            handler=handler
        )
        
        registry.register_menu_item(
            plugin_name="plugin2",
            menu="utilities",
            label="Other",
            command="other",
            handler=handler
        )
        
        # Get commands for plugin1
        commands = registry.get_plugin_commands("plugin1")
        assert len(commands) == 2
        assert "test1" in commands
        assert "test2" in commands
        assert "other" not in commands
    
    @pytest.mark.asyncio
    async def test_admin_only_menu_item(self):
        """Test admin-only menu items"""
        registry = PluginMenuRegistry()
        
        async def handler(context: Dict[str, Any]) -> str:
            return "Admin action"
        
        registry.register_menu_item(
            plugin_name="plugin",
            menu="utilities",
            label="Admin",
            command="admin",
            handler=handler,
            admin_only=True
        )
        
        # Try as non-admin
        context = {'is_admin': False}
        result = await registry.handle_menu_command("admin", context)
        assert "administrator" in result.lower() or "admin" in result.lower()
        
        # Try as admin
        context = {'is_admin': True}
        result = await registry.handle_menu_command("admin", context)
        assert result == "Admin action"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
