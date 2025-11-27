# ZephyrGate Plugin Development Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Plugin Architecture](#plugin-architecture)
3. [API Reference](#api-reference)
4. [Advanced Topics](#advanced-topics)
5. [Testing Plugins](#testing-plugins)
6. [Packaging and Distribution](#packaging-and-distribution)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Overview

ZephyrGate's plugin system allows you to extend the gateway's functionality without modifying the core codebase. Plugins can:

- **Handle commands** from mesh messages
- **Process messages** with custom logic
- **Schedule tasks** to run periodically
- **Add BBS menu items** for interactive features
- **Store data** persistently
- **Make HTTP requests** to external APIs
- **Communicate** with other plugins
- **Access system state** and mesh network information

### Prerequisites

Before developing plugins, you should have:

- Python 3.8 or higher
- Basic understanding of async/await in Python
- Familiarity with the Meshtastic protocol (helpful but not required)
- ZephyrGate installed and running

### Quick Start Tutorial

Let's create a simple "Hello World" plugin in 5 minutes.

#### Step 1: Generate Plugin Structure

Use the plugin template generator:

```bash
python create_plugin.py hello_world --author "Your Name" --commands
```

This creates a `plugins/hello_world/` directory with all necessary files.

#### Step 2: Implement Your Plugin

Edit `plugins/hello_world/plugin.py`:


```python
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginMetadata

class HelloWorldPlugin(EnhancedPlugin):
    """A simple hello world plugin"""
    
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        # Register a command handler
        self.register_command(
            "hello",
            self.handle_hello,
            "Say hello to the mesh network"
        )
        return True
    
    async def handle_hello(self, args, context):
        """Handle the hello command"""
        sender = context.get('sender_id', 'unknown')
        if args:
            name = ' '.join(args)
            return f"Hello {name}! (from {sender})"
        return f"Hello mesh! (from {sender})"
    
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            name="hello_world",
            version="1.0.0",
            description="Simple hello world plugin",
            author="Your Name"
        )
```

#### Step 3: Configure the Plugin

Add to your `config.yaml`:

```yaml
plugins:
  hello_world:
    enabled: true
```

#### Step 4: Test Your Plugin

Restart ZephyrGate or enable the plugin dynamically, then send a message:

```
hello
hello Alice
```

You should receive responses like:
```
Hello mesh! (from !abc123)
Hello Alice! (from !abc123)
```

Congratulations! You've created your first plugin.

### What's Next?

- Explore [example plugins](../examples/plugins/) for more complex functionality
- Read the [API Reference](#api-reference) to learn about available methods
- Check out [Advanced Topics](#advanced-topics) for inter-plugin communication and more

---

## Plugin Architecture

### Plugin Lifecycle

Understanding the plugin lifecycle is crucial for proper resource management.

```
┌─────────────┐
│   Loaded    │  Plugin discovered and manifest validated
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Initialized │  initialize() called, commands/tasks registered
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Started   │  start() called, scheduled tasks begin
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Running   │  Handling commands, messages, tasks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Stopped   │  stop() called, tasks cancelled
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Unloaded   │  cleanup() called, resources released
└─────────────┘
```

### Lifecycle Methods

#### `initialize() -> bool`

Called when the plugin is first loaded. This is where you should:
- Register command handlers
- Register message handlers
- Register scheduled tasks
- Register BBS menu items
- Initialize data structures

**Returns:** `True` if initialization successful, `False` otherwise

**Example:**
```python
async def initialize(self) -> bool:
    self.register_command("mycommand", self.handle_command)
    self.register_scheduled_task("update", 300, self.update_task)
    return True
```

#### `start() -> bool`

Called when the plugin is started. Scheduled tasks automatically begin execution.

**Returns:** `True` if start successful, `False` otherwise

**Example:**
```python
async def start(self) -> bool:
    await super().start()
    self.logger.info("Plugin started successfully")
    return True
```


#### `stop() -> bool`

Called when the plugin is stopped. Scheduled tasks are automatically cancelled.

**Returns:** `True` if stop successful, `False` otherwise

**Example:**
```python
async def stop(self) -> bool:
    await super().stop()
    self.logger.info("Plugin stopped")
    return True
```

#### `cleanup() -> bool`

Called when the plugin is unloaded. Clean up any resources here.

**Returns:** `True` if cleanup successful, `False` otherwise

**Example:**
```python
async def cleanup(self) -> bool:
    await super().cleanup()
    # Close connections, save state, etc.
    return True
```

### Plugin Components

#### Command Handlers

Command handlers respond to text commands from mesh messages.

**Registration:**
```python
self.register_command(
    command="weather",           # Command name
    handler=self.get_weather,    # Handler function
    help_text="Get weather info", # Help text
    priority=100                 # Priority (lower = higher)
)
```

**Handler Signature:**
```python
async def get_weather(self, args: List[str], context: Dict[str, Any]) -> str:
    """
    Args:
        args: Command arguments (e.g., ["Seattle", "WA"])
        context: Context dictionary with sender_id, channel, timestamp, etc.
    
    Returns:
        Response string to send back to mesh
    """
    location = ' '.join(args) if args else "default"
    return f"Weather for {location}: Sunny, 75°F"
```

**Context Dictionary:**
- `sender_id`: Node ID of message sender
- `sender_profile`: User profile object (if available)
- `channel`: Channel number
- `is_dm`: True if direct message
- `timestamp`: Message timestamp
- `message`: Original message object

#### Message Handlers

Message handlers process all incoming messages, not just commands.

**Registration:**
```python
self.register_message_handler(
    handler=self.handle_message,
    priority=200  # Higher priority = later execution
)
```

**Handler Signature:**
```python
async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
    """
    Args:
        message: Message object
        context: Context dictionary
    
    Returns:
        None to allow other handlers to process
        Any other value to stop processing chain
    """
    if message.message_type == MessageType.TEXT:
        self.logger.info(f"Received: {message.content}")
    return None  # Allow other handlers
```

#### Scheduled Tasks

Scheduled tasks run periodically in the background.

**Registration:**
```python
# Interval-based (every 5 minutes)
self.register_scheduled_task(
    name="update",
    interval=300,  # seconds
    handler=self.update_task
)

# Cron-style (every hour at :00)
self.register_scheduled_task(
    name="hourly_report",
    interval=0,
    handler=self.hourly_report,
    cron="0 * * * *"
)
```

**Handler Signature:**
```python
async def update_task(self):
    """Scheduled task handler"""
    try:
        data = await self.fetch_data()
        await self.store_data("latest", data)
        await self.send_message(f"Update: {data}")
    except Exception as e:
        self.logger.error(f"Task error: {e}")
```

#### BBS Menu Items

Add interactive menu items to the BBS system.

**Registration:**
```python
self.register_menu_item(
    menu="utilities",              # Menu location
    label="My Feature",            # Display label
    handler=self.menu_handler,     # Handler function
    description="My plugin feature",
    admin_only=False,              # Admin requirement
    order=100                      # Display order
)
```

**Handler Signature:**
```python
async def menu_handler(self, context: Dict[str, Any]) -> str:
    """
    Args:
        context: Menu context with user_id, user_name, session, etc.
    
    Returns:
        Response text to display
    """
    user_name = context.get('user_name', 'Unknown')
    return f"Hello {user_name}!\n\nFeature content here..."
```

### Plugin Manifest

Every plugin must have a `manifest.yaml` file declaring its metadata and capabilities.

**Example manifest.yaml:**
```yaml
name: my_plugin
version: 1.0.0
description: "My awesome plugin"
author: "Your Name"
author_email: "you@example.com"
license: "MIT"
homepage: "https://github.com/you/my_plugin"

# ZephyrGate compatibility
zephyrgate:
  min_version: "1.0.0"
  max_version: "2.0.0"

# Dependencies
dependencies:
  plugins:
    - name: weather
      version: ">=1.0.0"
      optional: false
  python_packages:
    - requests>=2.28.0
    - aiohttp>=3.8.0

# Capabilities
capabilities:
  commands:
    - name: mycommand
      description: "My custom command"
      usage: "mycommand [args]"
  scheduled_tasks:
    - name: update
      interval: 300
  menu_items:
    - menu: utilities
      label: "My Plugin"

# Configuration
config:
  schema_file: "config_schema.json"
  defaults:
    enabled: true
    api_key: ""

# Permissions
permissions:
  - send_messages
  - database_access
  - http_requests
  - schedule_tasks
```


---

## API Reference

### EnhancedPlugin Base Class

All plugins should extend `EnhancedPlugin` which provides convenient helper methods.

```python
from src.core.enhanced_plugin import EnhancedPlugin
```

### Command Registration

#### `register_command(command, handler, help_text="", priority=100)`

Register a command handler.

**Parameters:**
- `command` (str): Command name (without prefix)
- `handler` (Callable): Async handler function
- `help_text` (str): Help text for the command
- `priority` (int): Handler priority (lower = higher priority)

**Example:**
```python
self.register_command("weather", self.get_weather, "Get weather info", priority=100)
```

### Message Handling

#### `register_message_handler(handler, priority=100)`

Register a handler for all incoming messages.

**Parameters:**
- `handler` (Callable): Async handler function
- `priority` (int): Handler priority

**Example:**
```python
self.register_message_handler(self.handle_all_messages, priority=200)
```

### Scheduled Tasks

#### `register_scheduled_task(name, interval, handler, cron=None)`

Register a task that runs on a schedule.

**Parameters:**
- `name` (str): Task name (unique within plugin)
- `interval` (int): Interval in seconds (0 for cron-only)
- `handler` (Callable): Async handler function
- `cron` (str, optional): Cron expression

**Example:**
```python
# Every 5 minutes
self.register_scheduled_task("update", 300, self.update_task)

# Every hour at :00
self.register_scheduled_task("hourly", 0, self.hourly_task, cron="0 * * * *")
```

### BBS Menu Integration

#### `register_menu_item(menu, label, handler, description="", admin_only=False, command=None, order=100)`

Register a BBS menu item.

**Parameters:**
- `menu` (str): Menu name (e.g., "utilities", "main")
- `label` (str): Display label
- `handler` (Callable): Async handler function
- `description` (str): Menu item description
- `admin_only` (bool): Restrict to admin users
- `command` (str): Command name (defaults to label)
- `order` (int): Display order

**Example:**
```python
self.register_menu_item(
    menu="utilities",
    label="My Feature",
    handler=self.menu_handler,
    description="Access my plugin features"
)
```

### Mesh Messaging

#### `send_message(content, destination=None, channel=None) -> bool`

Send a message to the mesh network.

**Parameters:**
- `content` (str): Message content
- `destination` (str, optional): Destination node ID (None for broadcast)
- `channel` (int, optional): Channel number (None for default)

**Returns:** `True` if message queued successfully

**Example:**
```python
# Broadcast
await self.send_message("Hello mesh!")

# Direct message
await self.send_message("Private message", destination="!abc123")

# Specific channel
await self.send_message("Channel message", channel=2)
```

### Configuration Management

#### `get_config(key, default=None) -> Any`

Get configuration value with dot notation support.

**Parameters:**
- `key` (str): Configuration key (supports "nested.key" notation)
- `default` (Any): Default value if key not found

**Returns:** Configuration value or default

**Example:**
```python
api_key = self.get_config("api_key", "")
interval = self.get_config("update_interval", 300)
nested = self.get_config("settings.timeout", 30)
```

#### `set_config(key, value)`

Set configuration value with dot notation support.

**Parameters:**
- `key` (str): Configuration key
- `value` (Any): Value to set

**Example:**
```python
self.set_config("last_update", datetime.utcnow().isoformat())
self.set_config("stats.count", 100)
```

### Data Storage

#### `store_data(key, value, ttl=None)`

Store plugin data with optional TTL.

**Parameters:**
- `key` (str): Storage key
- `value` (Any): Value to store (must be JSON serializable)
- `ttl` (int, optional): Time to live in seconds

**Example:**
```python
# Permanent storage
await self.store_data("user_prefs", {"theme": "dark"})

# Cached data with TTL
await self.store_data("cache:weather", weather_data, ttl=3600)
```

#### `retrieve_data(key, default=None) -> Any`

Retrieve stored plugin data.

**Parameters:**
- `key` (str): Storage key
- `default` (Any): Default value if key not found or expired

**Returns:** Stored value or default

**Example:**
```python
prefs = await self.retrieve_data("user_prefs", {})
cached = await self.retrieve_data("cache:weather")
```

#### `delete_data(key) -> bool`

Delete stored data.

**Parameters:**
- `key` (str): Storage key

**Returns:** `True` if data was deleted

**Example:**
```python
await self.delete_data("cache:weather")
```

### HTTP Requests

#### `http_get(url, params=None, timeout=30, headers=None) -> Dict`

Make HTTP GET request with rate limiting.

**Parameters:**
- `url` (str): URL to request
- `params` (Dict, optional): Query parameters
- `timeout` (int): Request timeout in seconds
- `headers` (Dict, optional): HTTP headers

**Returns:** Response data as dictionary

**Raises:** `Exception` if rate limit exceeded or request fails

**Example:**
```python
try:
    data = await self.http_get(
        "https://api.example.com/data",
        params={"key": api_key, "format": "json"},
        timeout=30
    )
    self.logger.info(f"Received: {data}")
except Exception as e:
    self.logger.error(f"Request failed: {e}")
```

#### `http_post(url, data=None, timeout=30, headers=None) -> Dict`

Make HTTP POST request with rate limiting.

**Parameters:**
- `url` (str): URL to request
- `data` (Dict, optional): Request body data
- `timeout` (int): Request timeout in seconds
- `headers` (Dict, optional): HTTP headers

**Returns:** Response data as dictionary

**Raises:** `Exception` if rate limit exceeded or request fails

**Example:**
```python
try:
    result = await self.http_post(
        "https://api.example.com/submit",
        data={"message": "Hello", "sender": self.name},
        timeout=30
    )
except Exception as e:
    self.logger.error(f"Submission failed: {e}")
```


### System State Queries

**Required Permission:** `system_state_read`

#### `get_node_info(node_id=None) -> Optional[Dict[str, Any]]`

Get information about a mesh node.

**Parameters:**
- `node_id` (str, optional): Node ID to query (None for local node)

**Returns:** Dictionary with node information or None

**Example:**
```python
try:
    node_info = self.get_node_info("!abc123")
    if node_info:
        self.logger.info(f"Node status: {node_info['status']}")
except PermissionDeniedError:
    self.logger.error("No permission to query system state")
```

#### `get_network_status() -> Dict[str, Any]`

Get current network status.

**Returns:** Dictionary with network status information

**Example:**
```python
status = self.get_network_status()
if status['connected']:
    self.logger.info(f"Network has {status['node_count']} nodes")
```

#### `get_plugin_list() -> List[str]`

Get list of running plugins.

**Returns:** List of plugin names

**Example:**
```python
plugins = self.get_plugin_list()
self.logger.info(f"Running plugins: {', '.join(plugins)}")
```

#### `get_plugin_status(plugin_name) -> Optional[Dict[str, Any]]`

Get status of another plugin.

**Parameters:**
- `plugin_name` (str): Name of the plugin to query

**Returns:** Dictionary with plugin status or None

**Example:**
```python
status = self.get_plugin_status("weather")
if status and status['is_running']:
    self.logger.info("Weather plugin is running")
```

### Inter-Plugin Messaging

**Required Permission:** `inter_plugin_messaging`

#### `send_to_plugin(target_plugin, message_type, data) -> Optional[PluginResponse]`

Send a message to another plugin.

**Parameters:**
- `target_plugin` (str): Name of the target plugin
- `message_type` (str): Type of message
- `data` (Any): Message data (must be JSON serializable)

**Returns:** `PluginResponse` object or None

**Example:**
```python
try:
    response = await self.send_to_plugin(
        "weather",
        "get_forecast",
        {"location": "Seattle"}
    )
    
    if response and response.success:
        forecast = response.data
        self.logger.info(f"Forecast: {forecast}")
except PermissionDeniedError:
    self.logger.error("No permission for inter-plugin messaging")
```

#### `broadcast_to_plugins(message_type, data) -> List[PluginResponse]`

Broadcast a message to all plugins.

**Parameters:**
- `message_type` (str): Type of message
- `data` (Any): Message data

**Returns:** List of `PluginResponse` objects

**Example:**
```python
responses = await self.broadcast_to_plugins(
    "system_alert",
    {"level": "warning", "message": "Low battery"}
)

for response in responses:
    if response.success:
        plugin = response.metadata.get('target_plugin')
        self.logger.info(f"{plugin} acknowledged alert")
```

#### `register_inter_plugin_handler(handler)`

Register a handler for incoming inter-plugin messages.

**Parameters:**
- `handler` (Callable): Async function to handle messages

**Example:**
```python
async def handle_plugin_message(self, message):
    message_type = message.metadata.get('message_type')
    
    if message_type == 'ping':
        return {'status': 'pong', 'plugin': self.name}
    elif message_type == 'get_data':
        return {'data': self.get_some_data()}
    
    return None

self.register_inter_plugin_handler(self.handle_plugin_message)
```

### Logging

Use the built-in logger for all log messages:

```python
self.logger.debug("Debug message")
self.logger.info("Info message")
self.logger.warning("Warning message")
self.logger.error("Error message")
self.logger.exception("Exception with traceback")
```

---

## Advanced Topics

### Inter-Plugin Communication

Plugins can communicate with each other through a structured messaging system.

#### Sending Messages

```python
# Send to specific plugin
response = await self.send_to_plugin(
    "weather",
    "get_forecast",
    {"location": "Seattle", "days": 3}
)

if response and response.success:
    forecast = response.data
    # Use forecast data
else:
    self.logger.error(f"Error: {response.error if response else 'No response'}")
```

#### Receiving Messages

```python
async def handle_plugin_message(self, message):
    """Handle inter-plugin messages"""
    msg_type = message.metadata.get('message_type')
    data = message.data
    
    if msg_type == 'get_forecast':
        location = data.get('location')
        days = data.get('days', 1)
        forecast = self.get_forecast(location, days)
        return {'forecast': forecast}
    
    elif msg_type == 'ping':
        return {'status': 'pong', 'timestamp': datetime.utcnow().isoformat()}
    
    return None  # Unknown message type

# Register the handler
self.register_inter_plugin_handler(self.handle_plugin_message)
```

#### Broadcasting

```python
# Broadcast to all plugins
responses = await self.broadcast_to_plugins(
    "system_event",
    {"event": "low_battery", "level": 15}
)

# Process responses
for response in responses:
    if response.success:
        plugin_name = response.metadata.get('target_plugin')
        self.logger.info(f"{plugin_name}: {response.data}")
```

### Database Access

Plugins have isolated database access through the storage interface.

#### Storing Complex Data

```python
# Store structured data
user_data = {
    "preferences": {"theme": "dark", "notifications": True},
    "stats": {"messages_sent": 42, "commands_used": 15},
    "last_seen": datetime.utcnow().isoformat()
}

await self.store_data("user:!abc123", user_data)
```

#### Querying Data

```python
# Retrieve and update
user_data = await self.retrieve_data("user:!abc123", {})
user_data['stats']['messages_sent'] += 1
await self.store_data("user:!abc123", user_data)
```

#### Caching with TTL

```python
# Cache API responses
cache_key = f"cache:weather:{location}"
cached = await self.retrieve_data(cache_key)

if cached:
    return cached

# Fetch fresh data
data = await self.http_get(api_url)

# Cache for 10 minutes
await self.store_data(cache_key, data, ttl=600)
return data
```

### Permission System

Plugins must declare required permissions in their manifest.

#### Available Permissions

- `send_messages`: Send messages to mesh network
- `system_state_read`: Query system state and node information
- `inter_plugin_messaging`: Communicate with other plugins
- `database_access`: Access database storage
- `http_requests`: Make HTTP requests
- `schedule_tasks`: Register scheduled tasks

#### Declaring Permissions

In `manifest.yaml`:
```yaml
permissions:
  - send_messages
  - http_requests
  - database_access
```

#### Handling Permission Errors

```python
from src.core.plugin_core_services import PermissionDeniedError

try:
    await self.send_message("Hello mesh!")
except PermissionDeniedError as e:
    self.logger.error(f"Permission denied: {e}")
    return "Feature not available (missing permission)"
```


### Error Handling Best Practices

#### Always Wrap External Operations

```python
async def fetch_data(self):
    """Fetch data with proper error handling"""
    try:
        data = await self.http_get(api_url, timeout=30)
        return data
    except Exception as e:
        self.logger.error(f"Failed to fetch data: {e}")
        return None
```

#### Handle Command Errors Gracefully

```python
async def handle_command(self, args, context):
    """Command handler with error handling"""
    try:
        if not args:
            return "Usage: command <arg>"
        
        result = await self.process(args)
        return f"Success: {result}"
        
    except ValueError as e:
        return f"Invalid input: {e}"
    except Exception as e:
        self.logger.exception("Command error")
        return "An error occurred. Please try again."
```

#### Scheduled Task Error Handling

```python
async def scheduled_task(self):
    """Scheduled task with error handling"""
    try:
        # Perform task
        data = await self.fetch_data()
        if data:
            await self.process_data(data)
    except Exception as e:
        self.logger.exception("Task error")
        # Task will continue on next schedule
```

#### Resource Cleanup

```python
async def cleanup(self):
    """Clean up resources"""
    try:
        await super().cleanup()
        
        # Close connections
        if hasattr(self, 'connection'):
            await self.connection.close()
        
        # Save state
        await self.store_data("state", self.get_state())
        
        return True
    except Exception as e:
        self.logger.exception("Cleanup error")
        return False
```

### Performance Considerations

#### Rate Limiting

The HTTP client automatically enforces rate limits (default: 100 requests/minute).

```python
# This is automatically rate-limited
for i in range(200):
    try:
        data = await self.http_get(url)
    except Exception as e:
        if "rate limit" in str(e).lower():
            self.logger.warning("Rate limit hit, waiting...")
            await asyncio.sleep(60)
```

#### Caching

Use TTL-based caching to reduce external API calls:

```python
async def get_data(self, key):
    """Get data with caching"""
    cache_key = f"cache:{key}"
    
    # Check cache first
    cached = await self.retrieve_data(cache_key)
    if cached:
        return cached
    
    # Fetch fresh data
    data = await self.fetch_data(key)
    
    # Cache for 5 minutes
    await self.store_data(cache_key, data, ttl=300)
    
    return data
```

#### Async Best Practices

```python
# Good: Use asyncio.gather for concurrent operations
results = await asyncio.gather(
    self.fetch_data_1(),
    self.fetch_data_2(),
    self.fetch_data_3(),
    return_exceptions=True
)

# Bad: Sequential operations
result1 = await self.fetch_data_1()
result2 = await self.fetch_data_2()
result3 = await self.fetch_data_3()
```

#### Memory Management

```python
# Limit stored data size
MAX_ENTRIES = 1000

async def add_entry(self, entry):
    """Add entry with size limit"""
    entries = await self.retrieve_data("entries", [])
    entries.append(entry)
    
    # Keep only recent entries
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    
    await self.store_data("entries", entries)
```

---

## Testing Plugins

### Unit Testing

Create unit tests in `tests/test_plugin.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from plugins.my_plugin.plugin import MyPlugin

@pytest.fixture
async def plugin():
    """Create plugin instance for testing"""
    plugin = MyPlugin()
    plugin.logger = MagicMock()
    plugin.config = {"enabled": True, "api_key": "test_key"}
    await plugin.initialize()
    return plugin

@pytest.mark.asyncio
async def test_command_handler(plugin):
    """Test command handler"""
    context = {
        'sender_id': '!test123',
        'channel': 0,
        'timestamp': '2024-01-01T00:00:00Z'
    }
    
    result = await plugin.handle_command(['arg1', 'arg2'], context)
    
    assert result is not None
    assert 'expected' in result.lower()

@pytest.mark.asyncio
async def test_scheduled_task(plugin):
    """Test scheduled task"""
    # Mock external dependencies
    plugin.http_get = AsyncMock(return_value={'data': 'test'})
    plugin.send_message = AsyncMock(return_value=True)
    
    await plugin.scheduled_task()
    
    # Verify calls
    plugin.http_get.assert_called_once()
    plugin.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_error_handling(plugin):
    """Test error handling"""
    # Simulate error
    plugin.http_get = AsyncMock(side_effect=Exception("Network error"))
    
    result = await plugin.handle_command(['test'], {})
    
    # Should handle error gracefully
    assert 'error' in result.lower()
```

### Mocking ZephyrGate Interfaces

```python
from unittest.mock import AsyncMock, MagicMock

# Mock storage
plugin.store_data = AsyncMock()
plugin.retrieve_data = AsyncMock(return_value={'key': 'value'})

# Mock HTTP client
plugin.http_get = AsyncMock(return_value={'data': 'test'})
plugin.http_post = AsyncMock(return_value={'status': 'ok'})

# Mock messaging
plugin.send_message = AsyncMock(return_value=True)
plugin.send_to_plugin = AsyncMock(return_value=MagicMock(
    success=True,
    data={'response': 'data'}
))

# Mock configuration
plugin.get_config = MagicMock(side_effect=lambda k, d: {
    'api_key': 'test_key',
    'interval': 300
}.get(k, d))
```

### Integration Testing

Test your plugin with a running ZephyrGate instance:

```python
import pytest
from src.core.plugin_manager import PluginManager

@pytest.mark.integration
@pytest.mark.asyncio
async def test_plugin_integration():
    """Test plugin in real environment"""
    # Load plugin manager
    manager = PluginManager()
    
    # Load plugin
    plugin = await manager.load_plugin("my_plugin")
    assert plugin is not None
    
    # Start plugin
    success = await plugin.start()
    assert success
    
    # Test command
    result = await plugin.handle_command(['test'], {
        'sender_id': '!test123'
    })
    assert result is not None
    
    # Stop plugin
    await plugin.stop()
```

### Debugging Techniques

#### Enable Debug Logging

```python
import logging

# In your plugin
self.logger.setLevel(logging.DEBUG)
self.logger.debug("Detailed debug information")
```

#### Use Breakpoints

```python
async def handle_command(self, args, context):
    import pdb; pdb.set_trace()  # Debugger breakpoint
    # Your code here
```

#### Log Context Information

```python
async def handle_command(self, args, context):
    self.logger.info(f"Command called with args={args}, context={context}")
    # Your code here
```

#### Test with Mock Data

```python
# Create test data
test_context = {
    'sender_id': '!test123',
    'sender_profile': {'display_name': 'Test User'},
    'channel': 0,
    'is_dm': False,
    'timestamp': datetime.utcnow()
}

# Test command
result = await plugin.handle_command(['arg1'], test_context)
print(f"Result: {result}")
```


---

## Packaging and Distribution

### Directory Structure

Organize your plugin with this recommended structure:

```
my_plugin/
├── __init__.py              # Package initialization
├── plugin.py                # Main plugin class
├── manifest.yaml            # Plugin metadata
├── config_schema.json       # Configuration schema
├── README.md                # Plugin documentation
├── requirements.txt         # Python dependencies
├── LICENSE                  # License file
├── handlers/                # Command and message handlers
│   ├── __init__.py
│   ├── commands.py
│   └── messages.py
├── tasks/                   # Scheduled tasks
│   ├── __init__.py
│   └── scheduled.py
├── utils/                   # Utility functions
│   ├── __init__.py
│   └── helpers.py
└── tests/                   # Plugin tests
    ├── __init__.py
    ├── test_plugin.py
    ├── test_commands.py
    └── test_tasks.py
```

### Manifest Requirements

Your `manifest.yaml` must include:

**Required Fields:**
- `name`: Plugin name (lowercase, alphanumeric, underscores)
- `version`: Semantic version (e.g., "1.0.0")
- `description`: Brief description
- `author`: Author name

**Recommended Fields:**
- `author_email`: Contact email
- `license`: License type (e.g., "MIT", "Apache-2.0")
- `homepage`: Project URL
- `zephyrgate.min_version`: Minimum ZephyrGate version
- `permissions`: Required permissions
- `dependencies`: Plugin and Python package dependencies

**Example:**
```yaml
name: my_plugin
version: 1.0.0
description: "My awesome plugin for ZephyrGate"
author: "Your Name"
author_email: "you@example.com"
license: "MIT"
homepage: "https://github.com/you/my_plugin"

zephyrgate:
  min_version: "1.0.0"

permissions:
  - send_messages
  - http_requests

dependencies:
  python_packages:
    - requests>=2.28.0
```

### Configuration Schema

Define your configuration schema in `config_schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "enabled": {
      "type": "boolean",
      "description": "Enable or disable the plugin",
      "default": true
    },
    "api_key": {
      "type": "string",
      "description": "API key for external service",
      "default": ""
    },
    "update_interval": {
      "type": "integer",
      "description": "Update interval in seconds",
      "default": 300,
      "minimum": 60
    },
    "features": {
      "type": "object",
      "properties": {
        "alerts": {
          "type": "boolean",
          "default": true
        },
        "notifications": {
          "type": "boolean",
          "default": false
        }
      }
    }
  },
  "required": ["enabled"]
}
```

### Dependency Management

#### Python Dependencies

List Python packages in `requirements.txt`:

```
requests>=2.28.0
aiohttp>=3.8.0
python-dateutil>=2.8.0
```

#### Plugin Dependencies

Declare plugin dependencies in `manifest.yaml`:

```yaml
dependencies:
  plugins:
    - name: weather
      version: ">=1.0.0"
      optional: false
    - name: bbs
      version: ">=1.0.0"
      optional: true
```

### Versioning Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version: Incompatible API changes
- **MINOR** version: New functionality (backward compatible)
- **PATCH** version: Bug fixes (backward compatible)

**Examples:**
- `1.0.0` → `1.0.1`: Bug fix
- `1.0.1` → `1.1.0`: New feature
- `1.1.0` → `2.0.0`: Breaking change

### README Template

Include a comprehensive README.md:

```markdown
# My Plugin

Brief description of what your plugin does.

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

1. Copy plugin to ZephyrGate plugins directory:
   ```bash
   cp -r my_plugin /path/to/zephyrgate/plugins/
   ```

2. Install dependencies:
   ```bash
   pip install -r my_plugin/requirements.txt
   ```

3. Configure in `config.yaml`:
   ```yaml
   plugins:
     my_plugin:
       enabled: true
       api_key: "your_api_key"
   ```

4. Restart ZephyrGate

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable plugin |
| `api_key` | string | `""` | API key for service |
| `update_interval` | integer | `300` | Update interval (seconds) |

## Commands

- `mycommand [args]` - Description of command
- `another <required>` - Description of another command

## Usage Examples

### Example 1
```
mycommand arg1 arg2
```
Response: `Result: ...`

### Example 2
```
another value
```
Response: `Success: ...`

## Development

### Running Tests
```bash
pytest tests/
```

### Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file

## Support

- Issues: https://github.com/you/my_plugin/issues
- Email: you@example.com
```

### Distribution Methods

#### Method 1: Git Repository

Host your plugin on GitHub/GitLab:

```bash
# Users can clone directly
git clone https://github.com/you/my_plugin.git plugins/my_plugin
```

#### Method 2: Archive File

Create a distributable archive:

```bash
# Create archive
tar -czf my_plugin-1.0.0.tar.gz my_plugin/

# Users extract to plugins directory
tar -xzf my_plugin-1.0.0.tar.gz -C /path/to/zephyrgate/plugins/
```

#### Method 3: Python Package

Package as a Python package (advanced):

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="zephyrgate-my-plugin",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
    ],
)
```

### Installation Instructions

Provide clear installation instructions:

```markdown
## Installation

### Prerequisites
- ZephyrGate 1.0.0 or higher
- Python 3.8 or higher

### Steps

1. **Download the plugin:**
   ```bash
   cd /path/to/zephyrgate/plugins
   git clone https://github.com/you/my_plugin.git
   ```

2. **Install dependencies:**
   ```bash
   pip install -r my_plugin/requirements.txt
   ```

3. **Configure the plugin:**
   
   Edit `config.yaml` and add:
   ```yaml
   plugins:
     my_plugin:
       enabled: true
       api_key: "your_api_key_here"
   ```

4. **Restart ZephyrGate:**
   ```bash
   systemctl restart zephyrgate
   ```

5. **Verify installation:**
   
   Send a test command:
   ```
   mycommand test
   ```
```

---

## Troubleshooting

### Common Issues and Solutions

#### Plugin Not Loading

**Symptom:** Plugin doesn't appear in plugin list

**Possible Causes:**
1. Plugin directory not in configured paths
2. Missing `__init__.py` or `manifest.yaml`
3. Invalid manifest format
4. Unmet dependencies

**Solutions:**
```bash
# Check plugin paths in config.yaml
plugins:
  paths:
    - "plugins"
    - "/opt/zephyrgate/plugins"

# Verify manifest is valid YAML
python -c "import yaml; yaml.safe_load(open('manifest.yaml'))"

# Check logs for errors
tail -f logs/zephyrgate.log | grep my_plugin
```

#### Plugin Fails to Initialize

**Symptom:** Plugin loads but `initialize()` returns False

**Possible Causes:**
1. Configuration validation failed
2. Missing required configuration
3. Exception in `initialize()` method
4. Dependency not available

**Solutions:**
```python
# Add debug logging
async def initialize(self) -> bool:
    try:
        self.logger.info("Initializing plugin...")
        
        # Check configuration
        api_key = self.get_config("api_key")
        if not api_key:
            self.logger.error("Missing api_key in configuration")
            return False
        
        # Register handlers
        self.register_command("test", self.test_handler)
        
        self.logger.info("Plugin initialized successfully")
        return True
    except Exception as e:
        self.logger.exception("Initialization failed")
        return False
```


#### Commands Not Working

**Symptom:** Commands registered but not responding

**Possible Causes:**
1. Command not registered in `initialize()`
2. Handler signature incorrect
3. Handler raising unhandled exception
4. Command priority conflict

**Solutions:**
```python
# Verify registration
async def initialize(self) -> bool:
    self.logger.info("Registering commands...")
    self.register_command("test", self.test_handler, "Test command")
    self.logger.info("Commands registered")
    return True

# Check handler signature
async def test_handler(self, args: List[str], context: Dict[str, Any]) -> str:
    try:
        self.logger.info(f"Handler called: args={args}, context={context}")
        return "Test response"
    except Exception as e:
        self.logger.exception("Handler error")
        return f"Error: {e}"

# Test with higher priority
self.register_command("test", self.test_handler, priority=10)
```

#### Scheduled Tasks Not Running

**Symptom:** Tasks registered but not executing

**Possible Causes:**
1. Plugin not started (only loaded)
2. Task interval too long
3. Task handler raising exception
4. Task registration failed

**Solutions:**
```python
# Verify task registration
async def initialize(self) -> bool:
    self.logger.info("Registering scheduled tasks...")
    self.register_scheduled_task(
        "test_task",
        60,  # Run every minute for testing
        self.test_task
    )
    self.logger.info("Tasks registered")
    return True

# Add logging to task
async def test_task(self):
    self.logger.info("Task executing...")
    try:
        # Task logic
        self.logger.info("Task completed")
    except Exception as e:
        self.logger.exception("Task error")

# Verify plugin is started
# Check logs for "Plugin started" message
```

#### HTTP Requests Failing

**Symptom:** HTTP requests timeout or fail

**Possible Causes:**
1. Rate limit exceeded
2. Network connectivity issues
3. Invalid URL or parameters
4. Missing `http_requests` permission

**Solutions:**
```python
# Add retry logic
async def fetch_with_retry(self, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            data = await self.http_get(url, timeout=30)
            return data
        except Exception as e:
            self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

# Check rate limiting
try:
    data = await self.http_get(url)
except Exception as e:
    if "rate limit" in str(e).lower():
        self.logger.error("Rate limit exceeded, waiting...")
        await asyncio.sleep(60)
```

#### Permission Denied Errors

**Symptom:** `PermissionDeniedError` when using features

**Possible Causes:**
1. Missing permission in manifest
2. Permission not granted in configuration

**Solutions:**
```yaml
# Add to manifest.yaml
permissions:
  - send_messages
  - http_requests
  - database_access
  - system_state_read
  - inter_plugin_messaging
  - schedule_tasks
```

```python
# Handle permission errors gracefully
from src.core.plugin_core_services import PermissionDeniedError

try:
    await self.send_message("Hello")
except PermissionDeniedError:
    self.logger.error("Missing send_messages permission")
    return "Feature not available"
```

#### Data Storage Issues

**Symptom:** Data not persisting or retrieval fails

**Possible Causes:**
1. Database connection issues
2. Invalid data format (not JSON serializable)
3. Key conflicts
4. TTL expired

**Solutions:**
```python
# Ensure data is JSON serializable
import json

async def store_safe(self, key, value):
    try:
        # Test serialization
        json.dumps(value)
        await self.store_data(key, value)
        self.logger.info(f"Stored {key}")
    except TypeError as e:
        self.logger.error(f"Data not JSON serializable: {e}")

# Handle missing data
async def retrieve_safe(self, key, default=None):
    try:
        data = await self.retrieve_data(key, default)
        if data is None:
            self.logger.warning(f"No data for key: {key}")
        return data
    except Exception as e:
        self.logger.exception(f"Retrieval error for {key}")
        return default
```

### Debugging Tools

#### Enable Verbose Logging

```python
import logging

# In plugin initialization
self.logger.setLevel(logging.DEBUG)

# Log everything
self.logger.debug("Detailed debug info")
self.logger.info("General information")
self.logger.warning("Warning message")
self.logger.error("Error message")
self.logger.exception("Exception with traceback")
```

#### Use Python Debugger

```python
# Add breakpoint
async def handle_command(self, args, context):
    import pdb; pdb.set_trace()
    # Execution will pause here
    result = self.process(args)
    return result
```

#### Inspect Plugin State

```python
async def debug_command(self, args, context):
    """Debug command to inspect plugin state"""
    info = {
        "name": self.name,
        "version": self.version,
        "config": self.config,
        "is_running": self.is_running,
        "registered_commands": list(self.command_handler.command_handlers.keys()),
        "scheduled_tasks": list(self.scheduler.tasks.keys())
    }
    return json.dumps(info, indent=2)

# Register debug command
self.register_command("debug", self.debug_command)
```

### Log Analysis

#### Finding Plugin Logs

```bash
# Filter logs by plugin name
grep "my_plugin" logs/zephyrgate.log

# Watch logs in real-time
tail -f logs/zephyrgate.log | grep my_plugin

# Find errors
grep "ERROR.*my_plugin" logs/zephyrgate.log

# Find exceptions
grep -A 10 "Exception.*my_plugin" logs/zephyrgate.log
```

#### Common Log Patterns

```
# Plugin loaded successfully
INFO: Plugin my_plugin loaded successfully

# Plugin initialization
INFO: my_plugin: Initializing plugin...
INFO: my_plugin: Plugin initialized successfully

# Command execution
INFO: my_plugin: Command 'test' called with args=['arg1']
INFO: my_plugin: Command completed successfully

# Scheduled task execution
INFO: my_plugin: Task 'update' executing...
INFO: my_plugin: Task completed

# Errors
ERROR: my_plugin: Failed to fetch data: Connection timeout
ERROR: my_plugin: Command handler error: ValueError: Invalid input
```

### Performance Profiling

#### Measure Command Execution Time

```python
import time

async def handle_command(self, args, context):
    start_time = time.time()
    
    try:
        result = await self.process(args)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Command completed in {elapsed:.2f}s")
        
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        self.logger.error(f"Command failed after {elapsed:.2f}s: {e}")
        raise
```

#### Track Resource Usage

```python
import psutil
import os

async def get_resource_usage(self):
    """Get current resource usage"""
    process = psutil.Process(os.getpid())
    
    return {
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "cpu_percent": process.cpu_percent(interval=1),
        "threads": process.num_threads()
    }

# Log periodically
async def monitor_task(self):
    usage = await self.get_resource_usage()
    self.logger.info(f"Resource usage: {usage}")
```

### Getting Help

#### Documentation Resources

- **Plugin Development Guide**: This document
- **Enhanced Plugin API**: `docs/ENHANCED_PLUGIN_API.md`
- **Plugin Menu Integration**: `docs/PLUGIN_MENU_INTEGRATION.md`
- **Plugin Template Generator**: `docs/PLUGIN_TEMPLATE_GENERATOR.md`
- **Example Plugins**: `examples/plugins/`

#### Community Support

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share plugins
- **Discord/Slack**: Real-time community support

#### Reporting Issues

When reporting issues, include:

1. **Plugin Information**:
   - Plugin name and version
   - ZephyrGate version
   - Python version

2. **Problem Description**:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce

3. **Logs**:
   - Relevant log excerpts
   - Error messages and stack traces

4. **Configuration**:
   - Plugin configuration (sanitize sensitive data)
   - Manifest file

**Example Issue Report:**

```markdown
## Plugin Not Loading

**Environment:**
- Plugin: my_plugin v1.0.0
- ZephyrGate: v1.2.0
- Python: 3.9.7

**Description:**
Plugin fails to load with "Invalid manifest" error.

**Steps to Reproduce:**
1. Copy plugin to plugins/ directory
2. Add configuration to config.yaml
3. Restart ZephyrGate

**Logs:**
```
ERROR: Failed to load plugin my_plugin: Invalid manifest format
ERROR: Missing required field: version
```

**Manifest:**
```yaml
name: my_plugin
description: "My plugin"
author: "Me"
```

**Expected:**
Plugin should load successfully.
```

---

## Best Practices Summary

### Development

1. **Start Simple**: Begin with basic functionality, add features incrementally
2. **Use Templates**: Generate plugins with `create_plugin.py`
3. **Follow Examples**: Study example plugins for patterns
4. **Test Thoroughly**: Write unit tests and integration tests
5. **Handle Errors**: Wrap operations in try-except blocks
6. **Log Appropriately**: Use appropriate log levels
7. **Document Code**: Add docstrings and comments

### Configuration

1. **Provide Defaults**: Always provide sensible default values
2. **Validate Input**: Use JSON schema for configuration validation
3. **Document Options**: Explain all configuration options
4. **Secure Credentials**: Never log or expose API keys

### Performance

1. **Cache Data**: Use TTL-based caching for external data
2. **Rate Limit**: Respect API rate limits
3. **Async Operations**: Use asyncio.gather for concurrent operations
4. **Limit Storage**: Don't store unlimited data

### Security

1. **Validate Input**: Always validate user input
2. **Handle Permissions**: Check and handle permission errors
3. **Sanitize Output**: Don't expose sensitive information
4. **Update Dependencies**: Keep dependencies up to date

### Distribution

1. **Version Properly**: Follow semantic versioning
2. **Document Well**: Provide comprehensive README
3. **Test Installation**: Test installation process
4. **Support Users**: Respond to issues and questions

---

## Additional Resources

### Example Plugins

Explore these example plugins for reference:

- **hello_world_plugin.py**: Basic command handling
- **weather_alert_plugin.py**: HTTP requests and scheduling
- **menu_example_plugin.py**: BBS menu integration
- **data_logger_plugin.py**: Data storage and querying
- **multi_command_plugin.py**: Multiple command handlers
- **scheduled_task_example_plugin.py**: Advanced scheduling
- **core_services_example_plugin.py**: Inter-plugin messaging

### Related Documentation

- [Enhanced Plugin API Reference](ENHANCED_PLUGIN_API.md)
- [Plugin Menu Integration Guide](PLUGIN_MENU_INTEGRATION.md)
- [Plugin Template Generator Guide](PLUGIN_TEMPLATE_GENERATOR.md)
- [ZephyrGate User Manual](USER_MANUAL.md)
- [ZephyrGate Developer Guide](DEVELOPER_GUIDE.md)

### External Resources

- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [Meshtastic Documentation](https://meshtastic.org/docs/)
- [JSON Schema Documentation](https://json-schema.org/)
- [Semantic Versioning](https://semver.org/)

---

## Conclusion

You now have everything you need to develop powerful plugins for ZephyrGate! Start with the Quick Start tutorial, explore the example plugins, and refer to the API Reference as you build.

Remember:
- Start simple and iterate
- Test thoroughly
- Handle errors gracefully
- Document your work
- Share with the community

Happy plugin development! 🚀

---

**Document Version:** 1.0.0  
**Last Updated:** 2024-01-15  
**ZephyrGate Version:** 1.0.0+
