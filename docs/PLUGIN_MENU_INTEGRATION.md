# Plugin Menu Integration

## Overview

The Plugin Menu Integration system allows third-party plugins to add custom menu items to the ZephyrGate BBS menu system. This enables plugins to provide interactive features accessible through the BBS interface.

## Features

- **Menu Item Registration**: Plugins can register menu items in any BBS menu (main, utilities, BBS, etc.)
- **Handler Routing**: Menu selections are automatically routed to plugin handlers with full context
- **Dynamic Lifecycle**: Menu items can be added, removed, enabled, and disabled at runtime
- **Ordering Control**: Plugins can specify the display order of their menu items
- **Admin Support**: Menu items can be restricted to admin users only
- **Nested Submenus**: Support for hierarchical menu structures

## Architecture

### Components

1. **PluginMenuRegistry**: Central registry for all plugin menu items
2. **BBSMenuSystem**: Enhanced to support plugin menu items
3. **EnhancedPlugin**: Base class with menu registration methods

### Data Flow

```
User Input → BBS Menu System → Plugin Menu Registry → Plugin Handler → Response
```

## Usage

### Registering a Menu Item

```python
from src.core.enhanced_plugin import EnhancedPlugin

class MyPlugin(EnhancedPlugin):
    async def initialize(self) -> bool:
        # Register a menu item
        self.register_menu_item(
            menu="utilities",           # Menu to add item to
            label="My Feature",         # Display label
            handler=self.my_handler,    # Handler function
            description="My plugin feature",
            command="myfeature",        # Command to trigger
            order=100,                  # Display order
            admin_only=False            # Admin requirement
        )
        return True
    
    async def my_handler(self, context: dict) -> str:
        """Handle menu item selection"""
        user_name = context.get('user_name', 'Unknown')
        return f"Hello {user_name}! Feature executed."
```

### Handler Context

Menu handlers receive a context dictionary with:

- `user_id`: User's node ID
- `user_name`: User's display name
- `session`: BBS session object
- `args`: Command arguments (if any)
- `menu`: Current menu name
- `is_admin`: Admin status
- `timestamp`: Current timestamp

### Menu Types

Available menu types:
- `main`: Main menu
- `bbs`: BBS menu
- `utilities`: Utilities menu
- `mail`: Mail menu
- `bulletins`: Bulletins menu
- `channels`: Channels menu
- `js8call`: JS8Call menu

## API Reference

### PluginMenuRegistry

#### `register_menu_item(plugin_name, menu, label, command, handler, ...)`

Register a new menu item.

**Parameters:**
- `plugin_name` (str): Name of the plugin
- `menu` (str): Menu type
- `label` (str): Display label
- `command` (str): Command to trigger
- `handler` (Callable): Async handler function
- `description` (str): Optional description
- `admin_only` (bool): Admin requirement
- `order` (int): Display order
- `parent_command` (str): Parent for submenus

**Returns:** `bool` - Success status

#### `unregister_menu_item(command)`

Remove a menu item by command.

**Parameters:**
- `command` (str): Command to remove

**Returns:** `bool` - Success status

#### `unregister_plugin_menu_items(plugin_name)`

Remove all menu items for a plugin.

**Parameters:**
- `plugin_name` (str): Plugin name

**Returns:** `int` - Number of items removed

#### `get_menu_items(menu, include_disabled=False)`

Get all menu items for a menu.

**Parameters:**
- `menu` (str): Menu type
- `include_disabled` (bool): Include disabled items

**Returns:** `List[PluginMenuItem]` - Menu items

#### `handle_menu_command(command, context)`

Route a menu command to its handler.

**Parameters:**
- `command` (str): Command to handle
- `context` (dict): Context dictionary

**Returns:** `Optional[str]` - Handler response

### EnhancedPlugin

#### `register_menu_item(menu, label, handler, ...)`

Register a menu item for this plugin.

**Parameters:**
- `menu` (str): Menu type
- `label` (str): Display label
- `handler` (Callable): Handler function
- `description` (str): Optional description
- `admin_only` (bool): Admin requirement
- `command` (str): Optional command (defaults to label)
- `order` (int): Display order

## Examples

### Basic Menu Item

```python
async def simple_handler(self, context: dict) -> str:
    return "Simple menu item executed!"

self.register_menu_item(
    menu="utilities",
    label="Simple Item",
    handler=simple_handler
)
```

### Admin-Only Menu Item

```python
async def admin_handler(self, context: dict) -> str:
    return "Admin feature executed!"

self.register_menu_item(
    menu="utilities",
    label="Admin Feature",
    handler=admin_handler,
    admin_only=True
)
```

### Menu Item with Context

```python
async def context_handler(self, context: dict) -> str:
    user_name = context.get('user_name', 'Unknown')
    user_id = context.get('user_id', 'Unknown')
    
    response = []
    response.append(f"User: {user_name}")
    response.append(f"ID: {user_id}")
    response.append(f"Menu: {context.get('menu')}")
    
    return "\n".join(response)

self.register_menu_item(
    menu="utilities",
    label="Show Context",
    handler=context_handler
)
```

### Multiple Menu Items

```python
async def initialize(self) -> bool:
    # Register multiple items
    self.register_menu_item(
        menu="utilities",
        label="Feature 1",
        handler=self.feature1_handler,
        order=100
    )
    
    self.register_menu_item(
        menu="utilities",
        label="Feature 2",
        handler=self.feature2_handler,
        order=101
    )
    
    self.register_menu_item(
        menu="main",
        label="Quick Access",
        handler=self.quick_handler,
        order=200
    )
    
    return True
```

## Testing

### Property-Based Tests

The menu integration system includes comprehensive property-based tests:

1. **Menu Item Registration**: Verifies all registered items are retrievable
2. **Handler Routing**: Ensures handlers are called with correct context
3. **Lifecycle Management**: Tests item removal and cleanup

Run tests:
```bash
pytest tests/property/test_menu_integration_properties.py -v
```

### Unit Tests

Unit tests verify integration functionality:

```bash
pytest tests/unit/test_plugin_menu_integration.py -v
```

## Best Practices

1. **Clear Labels**: Use descriptive labels for menu items
2. **Helpful Descriptions**: Provide clear descriptions of functionality
3. **Error Handling**: Handle errors gracefully in handlers
4. **Context Usage**: Use context to personalize responses
5. **Cleanup**: Menu items are automatically removed when plugin stops
6. **Ordering**: Use order values to control menu item placement
7. **Admin Items**: Restrict sensitive features to admin users

## Troubleshooting

### Menu Item Not Appearing

- Verify menu type is correct
- Check if item is enabled
- Ensure plugin is running
- Check logs for registration errors

### Handler Not Called

- Verify command matches registration
- Check if item is disabled
- Ensure handler is async
- Check for exceptions in handler

### Context Missing Data

- Verify BBS system is passing context
- Check context keys in handler
- Use `.get()` with defaults for safety

## Future Enhancements

- Submenu support with parent/child relationships
- Menu item icons/emojis
- Dynamic menu item updates
- Menu item permissions beyond admin
- Menu item help text
- Menu item shortcuts

## See Also

- [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)
- [Enhanced Plugin API](ENHANCED_PLUGIN_API.md)
- [BBS System Documentation](USER_MANUAL.md#bbs-system)
