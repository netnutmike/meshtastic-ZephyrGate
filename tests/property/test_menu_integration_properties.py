"""
Property-based tests for plugin menu integration.

Tests universal properties that should hold for all plugin menu operations.
"""

import pytest
from hypothesis import given, settings, strategies as st
from typing import Dict, Any

from src.core.plugin_menu_registry import PluginMenuRegistry, MenuType


# Strategies for generating test data

@st.composite
def menu_type_strategy(draw):
    """Generate valid menu types"""
    return draw(st.sampled_from([m.value for m in MenuType]))


@st.composite
def plugin_name_strategy(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65),
        min_size=1,
        max_size=20
    ))


@st.composite
def command_strategy(draw):
    """Generate valid command names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), min_codepoint=97),
        min_size=1,
        max_size=15
    ).filter(lambda x: x and x[0].isalpha()))


@st.composite
def label_strategy(draw):
    """Generate valid labels"""
    return draw(st.text(min_size=1, max_size=50))


@st.composite
def description_strategy(draw):
    """Generate valid descriptions"""
    return draw(st.text(min_size=0, max_size=100))


async def dummy_handler(context: Dict[str, Any]) -> str:
    """Dummy handler for testing"""
    return "Handler executed"


# Feature: third-party-plugin-system, Property 4: Menu item registration
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    label=label_strategy(),
    command=command_strategy(),
    description=description_strategy(),
    admin_only=st.booleans(),
    order=st.integers(min_value=0, max_value=1000)
)
def test_menu_item_registration_property(
    plugin_name: str,
    menu: str,
    label: str,
    command: str,
    description: str,
    admin_only: bool,
    order: int
):
    """
    Property 4: Menu item registration
    
    For any menu item registered by a plugin, querying that menu should return
    the item in the results with correct label, command, and handler reference.
    
    Validates: Requirements 2.1
    """
    # Create registry
    registry = PluginMenuRegistry()
    
    # Register menu item
    success = registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label=label,
        command=command,
        handler=dummy_handler,
        description=description,
        admin_only=admin_only,
        order=order
    )
    
    # Property: Registration should succeed
    assert success, f"Failed to register menu item for plugin '{plugin_name}'"
    
    # Property: Querying the menu should return the item
    menu_items = registry.get_menu_items(menu)
    
    # Find our item
    our_item = None
    for item in menu_items:
        if item.command == command.lower():
            our_item = item
            break
    
    # Property: Item should be found
    assert our_item is not None, f"Menu item with command '{command}' not found in menu '{menu}'"
    
    # Property: Item should have correct attributes
    assert our_item.plugin == plugin_name, "Plugin name mismatch"
    assert our_item.label == label, "Label mismatch"
    assert our_item.command == command.lower(), "Command mismatch"
    assert our_item.handler == dummy_handler, "Handler mismatch"
    assert our_item.description == description, "Description mismatch"
    assert our_item.admin_only == admin_only, "Admin_only mismatch"
    assert our_item.order == order, "Order mismatch"
    assert our_item.enabled, "Item should be enabled by default"
    
    # Property: Item should be retrievable by command
    retrieved_item = registry.get_menu_item_by_command(command)
    assert retrieved_item is not None, "Item not retrievable by command"
    assert retrieved_item.command == command.lower(), "Retrieved item command mismatch"


# Feature: third-party-plugin-system, Property 4: Menu item registration (completeness)
@settings(max_examples=100)
@given(
    items=st.lists(
        st.tuples(
            plugin_name_strategy(),
            menu_type_strategy(),
            label_strategy(),
            command_strategy()
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[3]  # Unique by command
    )
)
def test_menu_registration_completeness_property(items):
    """
    Property 4: Menu item registration completeness
    
    For any set of menu items registered, all items should be retrievable
    and appear in their respective menus.
    
    Validates: Requirements 2.1
    """
    registry = PluginMenuRegistry()
    
    # Register all items
    registered_commands = []
    for plugin_name, menu, label, command in items:
        success = registry.register_menu_item(
            plugin_name=plugin_name,
            menu=menu,
            label=label,
            command=command,
            handler=dummy_handler
        )
        if success:
            registered_commands.append((command.lower(), menu))
    
    # Property: All registered commands should be retrievable
    all_commands = registry.get_all_commands()
    for command, _ in registered_commands:
        assert command in all_commands, f"Command '{command}' not in all commands list"
    
    # Property: Each command should appear in its menu
    for command, menu in registered_commands:
        menu_items = registry.get_menu_items(menu)
        command_found = any(item.command == command for item in menu_items)
        assert command_found, f"Command '{command}' not found in menu '{menu}'"


# Feature: third-party-plugin-system, Property 4: Menu item registration (ordering)
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    items=st.lists(
        st.tuples(
            label_strategy(),
            command_strategy(),
            st.integers(min_value=0, max_value=1000)  # order
        ),
        min_size=2,
        max_size=10,
        unique_by=lambda x: x[1]  # Unique by command
    )
)
def test_menu_item_ordering_property(plugin_name: str, menu: str, items):
    """
    Property 4: Menu item ordering
    
    For any set of menu items with different order values, items should
    appear in ascending order by their order value.
    
    Validates: Requirements 2.1
    """
    registry = PluginMenuRegistry()
    
    # Register all items
    for label, command, order in items:
        registry.register_menu_item(
            plugin_name=plugin_name,
            menu=menu,
            label=label,
            command=command,
            handler=dummy_handler,
            order=order
        )
    
    # Get menu items
    menu_items = registry.get_menu_items(menu)
    
    # Property: Items should be ordered by order value
    orders = [item.order for item in menu_items]
    assert orders == sorted(orders), f"Menu items not properly ordered: {orders}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



# Feature: third-party-plugin-system, Property 5: Menu handler routing
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    label=label_strategy(),
    command=command_strategy(),
    user_id=st.text(min_size=1, max_size=20),
    user_name=st.text(min_size=1, max_size=30)
)
@pytest.mark.asyncio
async def test_menu_handler_routing_property(
    plugin_name: str,
    menu: str,
    label: str,
    command: str,
    user_id: str,
    user_name: str
):
    """
    Property 5: Menu handler routing
    
    For any registered menu item, when a user selects that item, the system
    should invoke the plugin's menu handler with user and session context.
    
    Validates: Requirements 2.2, 2.4
    """
    # Track if handler was called and with what context
    handler_called = False
    received_context = None
    
    async def test_handler(context: Dict[str, Any]) -> str:
        nonlocal handler_called, received_context
        handler_called = True
        received_context = context
        return "Handler executed successfully"
    
    # Create registry and register menu item
    registry = PluginMenuRegistry()
    registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label=label,
        command=command,
        handler=test_handler
    )
    
    # Create context with user and session information
    context = {
        'user_id': user_id,
        'user_name': user_name,
        'session': {'test': 'data'},
        'is_admin': False
    }
    
    # Handle the menu command
    result = await registry.handle_menu_command(command, context)
    
    # Property: Handler should be called
    assert handler_called, f"Handler for command '{command}' was not called"
    
    # Property: Result should be returned
    assert result is not None, "Handler should return a result"
    assert result == "Handler executed successfully", "Handler result mismatch"
    
    # Property: Context should be passed to handler
    assert received_context is not None, "Context not passed to handler"
    assert received_context['user_id'] == user_id, "User ID not in context"
    assert received_context['user_name'] == user_name, "User name not in context"


# Feature: third-party-plugin-system, Property 5: Menu handler routing (context completeness)
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    command=command_strategy(),
    context_keys=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), min_codepoint=65),
            min_size=1,
            max_size=15
        ),
        min_size=1,
        max_size=10,
        unique=True
    )
)
@pytest.mark.asyncio
async def test_menu_handler_context_completeness_property(
    plugin_name: str,
    menu: str,
    command: str,
    context_keys: list
):
    """
    Property 5: Menu handler context completeness
    
    For any context provided to a menu command, all context keys should be
    accessible in the handler.
    
    Validates: Requirements 2.4
    """
    received_context = None
    
    async def test_handler(context: Dict[str, Any]) -> str:
        nonlocal received_context
        received_context = context
        return "OK"
    
    # Create registry and register menu item
    registry = PluginMenuRegistry()
    registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label="Test",
        command=command,
        handler=test_handler
    )
    
    # Create context with all keys
    context = {key: f"value_{key}" for key in context_keys}
    
    # Handle the menu command
    await registry.handle_menu_command(command, context)
    
    # Property: All context keys should be present in received context
    assert received_context is not None, "Context not received"
    for key in context_keys:
        assert key in received_context, f"Context key '{key}' not passed to handler"
        assert received_context[key] == f"value_{key}", f"Context value for '{key}' mismatch"


# Feature: third-party-plugin-system, Property 5: Menu handler routing (error handling)
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    command=command_strategy()
)
@pytest.mark.asyncio
async def test_menu_handler_error_handling_property(
    plugin_name: str,
    menu: str,
    command: str
):
    """
    Property 5: Menu handler error handling
    
    For any menu handler that raises an exception, the system should catch
    the error and return an error message rather than crashing.
    
    Validates: Requirements 2.2
    """
    async def failing_handler(context: Dict[str, Any]) -> str:
        raise ValueError("Test error")
    
    # Create registry and register menu item
    registry = PluginMenuRegistry()
    registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label="Test",
        command=command,
        handler=failing_handler
    )
    
    # Handle the menu command
    context = {'user_id': 'test'}
    result = await registry.handle_menu_command(command, context)
    
    # Property: Should return error message, not raise exception
    assert result is not None, "Should return error message"
    assert "error" in result.lower(), "Result should indicate an error"



# Feature: third-party-plugin-system, Property 6: Menu item lifecycle
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    label=label_strategy(),
    command=command_strategy()
)
def test_menu_item_lifecycle_removal_property(
    plugin_name: str,
    menu: str,
    label: str,
    command: str
):
    """
    Property 6: Menu item lifecycle
    
    For any registered menu item, calling the removal method should result
    in the item no longer appearing in subsequent menu queries.
    
    Validates: Requirements 2.5
    """
    # Create registry and register menu item
    registry = PluginMenuRegistry()
    registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label=label,
        command=command,
        handler=dummy_handler
    )
    
    # Verify item is registered
    menu_items_before = registry.get_menu_items(menu)
    command_found_before = any(item.command == command.lower() for item in menu_items_before)
    assert command_found_before, f"Command '{command}' not found after registration"
    
    # Unregister the menu item
    success = registry.unregister_menu_item(command)
    
    # Property: Unregistration should succeed
    assert success, f"Failed to unregister menu item with command '{command}'"
    
    # Property: Item should no longer appear in menu queries
    menu_items_after = registry.get_menu_items(menu)
    command_found_after = any(item.command == command.lower() for item in menu_items_after)
    assert not command_found_after, f"Command '{command}' still found after unregistration"
    
    # Property: Item should not be retrievable by command
    retrieved_item = registry.get_menu_item_by_command(command)
    assert retrieved_item is None, f"Item still retrievable by command after unregistration"


# Feature: third-party-plugin-system, Property 6: Menu item lifecycle (plugin cleanup)
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    items=st.lists(
        st.tuples(label_strategy(), command_strategy()),
        min_size=1,
        max_size=5,
        unique_by=lambda x: x[1]  # Unique by command
    )
)
def test_menu_item_lifecycle_plugin_cleanup_property(
    plugin_name: str,
    menu: str,
    items: list
):
    """
    Property 6: Menu item lifecycle (plugin cleanup)
    
    For any plugin with multiple registered menu items, unregistering all
    items for that plugin should remove all items from menus.
    
    Validates: Requirements 2.5
    """
    # Create registry and register all items for the plugin
    registry = PluginMenuRegistry()
    
    for label, command in items:
        registry.register_menu_item(
            plugin_name=plugin_name,
            menu=menu,
            label=label,
            command=command,
            handler=dummy_handler
        )
    
    # Verify all items are registered
    plugin_commands_before = registry.get_plugin_commands(plugin_name)
    assert len(plugin_commands_before) == len(items), "Not all items registered"
    
    # Unregister all items for the plugin
    removed_count = registry.unregister_plugin_menu_items(plugin_name)
    
    # Property: Should remove all items
    assert removed_count == len(items), f"Expected to remove {len(items)} items, removed {removed_count}"
    
    # Property: No items should remain for the plugin
    plugin_commands_after = registry.get_plugin_commands(plugin_name)
    assert len(plugin_commands_after) == 0, f"Plugin still has {len(plugin_commands_after)} commands"
    
    # Property: Menu should not contain any of the plugin's items
    menu_items = registry.get_menu_items(menu)
    for label, command in items:
        command_found = any(item.command == command.lower() for item in menu_items)
        assert not command_found, f"Command '{command}' still in menu after plugin cleanup"


# Feature: third-party-plugin-system, Property 6: Menu item lifecycle (enable/disable)
@settings(max_examples=100)
@given(
    plugin_name=plugin_name_strategy(),
    menu=menu_type_strategy(),
    command=command_strategy()
)
@pytest.mark.asyncio
async def test_menu_item_lifecycle_enable_disable_property(
    plugin_name: str,
    menu: str,
    command: str
):
    """
    Property 6: Menu item lifecycle (enable/disable)
    
    For any registered menu item, disabling it should prevent it from being
    executed, and enabling it should restore functionality.
    
    Validates: Requirements 2.5
    """
    handler_called = False
    
    async def test_handler(context: Dict[str, Any]) -> str:
        nonlocal handler_called
        handler_called = True
        return "OK"
    
    # Create registry and register menu item
    registry = PluginMenuRegistry()
    registry.register_menu_item(
        plugin_name=plugin_name,
        menu=menu,
        label="Test",
        command=command,
        handler=test_handler
    )
    
    # Verify item is enabled and works
    context = {'user_id': 'test'}
    result = await registry.handle_menu_command(command, context)
    assert handler_called, "Handler should be called when enabled"
    assert result == "OK", "Handler should return OK"
    
    # Disable the menu item
    success = registry.disable_menu_item(command)
    assert success, "Failed to disable menu item"
    
    # Property: Disabled item should not appear in menu queries (by default)
    menu_items = registry.get_menu_items(menu, include_disabled=False)
    command_found = any(item.command == command.lower() for item in menu_items)
    assert not command_found, "Disabled item should not appear in menu"
    
    # Property: Disabled item should still be retrievable
    item = registry.get_menu_item_by_command(command)
    assert item is not None, "Disabled item should still be retrievable"
    assert not item.enabled, "Item should be marked as disabled"
    
    # Property: Handling disabled item should return disabled message
    handler_called = False
    result = await registry.handle_menu_command(command, context)
    assert not handler_called, "Handler should not be called when disabled"
    assert "disabled" in result.lower(), "Should indicate item is disabled"
    
    # Re-enable the menu item
    success = registry.enable_menu_item(command)
    assert success, "Failed to enable menu item"
    
    # Property: Enabled item should work again
    handler_called = False
    result = await registry.handle_menu_command(command, context)
    assert handler_called, "Handler should be called after re-enabling"
    assert result == "OK", "Handler should return OK after re-enabling"
