# Enhanced Plugin API Reference

## Overview

The `EnhancedPlugin` base class provides a developer-friendly API for creating third-party plugins for ZephyrGate. It extends the base `BasePlugin` class with convenient helper methods for common plugin operations.

## Quick Start

```python
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginMetadata, PluginPriority

class MyPlugin(EnhancedPlugin):
    async def initialize(self) -> bool:
        # Register your commands, handlers, and tasks here
        self.register_command("mycommand", self.handle_command, "My command help")
        return True
    
    async def handle_command(self, args, context):
        return "Command executed!"
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            description="My awesome plugin",
            author="Your Name"
        )
```

## API Reference

### Command Registration

#### `register_command(command, handler, help_text="", priority=100)`

Register a command handler that responds to text commands from the mesh network.

**Parameters:**
- `command` (str): Command name (without prefix)
- `handler` (Callable): Async function with signature `async def handler(args: List[str], context: Dict) -> str`
- `help_text` (str): Help text for the command
- `priority` (int): Handler priority (lower = higher priority)

**Example:**
```python
async def my_command(args, context):
    sender = context.get('sender_id', 'unknown')
    return f"Hello {sender}! Args: {args}"

self.register_command("hello", my_command, "Say hello", priority=100)
```

### Message Handling

#### `register_message_handler(handler, priority=100)`

Register a handler for all incoming messages (not just commands).

**Parameters:**
- `handler` (Callable): Async function with signature `async def handler(message: Message, context: Dict) -> Optional[Any]`
- `priority` (int): Handler priority (lower = higher priority)

**Example:**
```python
async def handle_message(message, context):
    if message.message_type == MessageType.TEXT:
        # Process text message
        self.logger.info(f"Received: {message.content}")
    return None  # Allow other handlers to process

self.register_message_handler(handle_message, priority=200)
```

### Scheduled Tasks

#### `register_scheduled_task(name, interval, handler)`

Register a task that runs at regular intervals.

**Parameters:**
- `name` (str): Task name (unique within plugin)
- `interval` (int): Interval in seconds
- `handler` (Callable): Async function with signature `async def handler() -> None`

**Example:**
```python
async def hourly_update():
    data = await self.http_get("https://api.example.com/data")
    await self.send_message(f"Update: {data}")

self.register_scheduled_task("hourly_update", 3600, hourly_update)
```

### BBS Menu Integration

#### `register_menu_item(menu, label, handler, description="", admin_only=False)`

Register a menu item in the BBS system.

**Parameters:**
- `menu` (str): Menu name (e.g., "main", "utilities")
- `label` (str): Menu item label
- `handler` (Callable): Async function with signature `async def handler(context: Dict) -> str`
- `description` (str): Menu item description
- `admin_only` (bool): Whether item is admin-only

**Example:**
```python
async def my_menu_handler(context):
    user = context.get('user_id', 'unknown')
    return f"Menu selected by {user}"

self.register_menu_item("utilities", "My Plugin", my_menu_handler, 
                       description="Access my plugin features")
```

### Mesh Messaging

#### `send_message(content, destination=None, channel=None) -> bool`

Send a message to the mesh network.

**Parameters:**
- `content` (str): Message content
- `destination` (str, optional): Destination node ID (None for broadcast)
- `channel` (int, optional): Channel number (None for default)

**Returns:**
- `bool`: True if message was queued successfully

**Example:**
```python
# Broadcast message
await self.send_message("Hello mesh!")

# Direct message
await self.send_message("Private message", destination="!abc123")

# Message on specific channel
await self.send_message("Channel message", channel=2)
```

### Configuration Management

#### `get_config(key, default=None) -> Any`

Get configuration value with dot notation support.

**Parameters:**
- `key` (str): Configuration key (supports dot notation for nested values)
- `default` (Any): Default value if key not found

**Returns:**
- Configuration value or default

**Example:**
```python
api_key = self.get_config("api_key", "")
interval = self.get_config("update_interval", 300)
nested = self.get_config("nested.value", 42)
```

#### `set_config(key, value)`

Set configuration value with dot notation support.

**Parameters:**
- `key` (str): Configuration key (supports dot notation)
- `value` (Any): Value to set

**Example:**
```python
self.set_config("last_update", datetime.utcnow().isoformat())
self.set_config("stats.message_count", 100)
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
# Store without expiry
await self.store_data("user_preferences", {"theme": "dark"})

# Store with TTL (cache)
await self.store_data("cache:weather", weather_data, ttl=3600)
```

#### `retrieve_data(key, default=None) -> Any`

Retrieve stored plugin data.

**Parameters:**
- `key` (str): Storage key
- `default` (Any): Default value if key not found

**Returns:**
- Stored value or default

**Example:**
```python
preferences = await self.retrieve_data("user_preferences", {})
cached_data = await self.retrieve_data("cache:weather")
```

### HTTP Requests

#### `http_get(url, params=None, timeout=30, headers=None) -> Dict`

Make HTTP GET request with rate limiting and error handling.

**Parameters:**
- `url` (str): URL to request
- `params` (Dict, optional): Query parameters
- `timeout` (int): Request timeout in seconds
- `headers` (Dict, optional): HTTP headers

**Returns:**
- Response data as dictionary

**Raises:**
- `Exception`: If rate limit exceeded or request fails

**Example:**
```python
try:
    data = await self.http_get(
        "https://api.example.com/data",
        params={"key": api_key, "format": "json"}
    )
    self.logger.info(f"Received: {data}")
except Exception as e:
    self.logger.error(f"Request failed: {e}")
```

#### `http_post(url, data=None, timeout=30, headers=None) -> Dict`

Make HTTP POST request with rate limiting and error handling.

**Parameters:**
- `url` (str): URL to request
- `data` (Dict, optional): Request body data
- `timeout` (int): Request timeout in seconds
- `headers` (Dict, optional): HTTP headers

**Returns:**
- Response data as dictionary

**Raises:**
- `Exception`: If rate limit exceeded or request fails

**Example:**
```python
try:
    result = await self.http_post(
        "https://api.example.com/submit",
        data={"message": "Hello", "sender": self.name}
    )
    self.logger.info(f"Submitted: {result}")
except Exception as e:
    self.logger.error(f"Submission failed: {e}")
```

## Lifecycle Methods

### `initialize() -> bool`

Called when the plugin is loaded. Register commands, handlers, and tasks here.

**Returns:**
- `bool`: True if initialization successful

### `start() -> bool`

Called when the plugin is started. Scheduled tasks are automatically started.

**Returns:**
- `bool`: True if start successful

### `stop() -> bool`

Called when the plugin is stopped. Scheduled tasks are automatically stopped.

**Returns:**
- `bool`: True if stop successful

### `cleanup() -> bool`

Called when the plugin is unloaded. HTTP client is automatically closed.

**Returns:**
- `bool`: True if cleanup successful

## Complete Example

```python
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginMetadata, PluginPriority

class WeatherAlertPlugin(EnhancedPlugin):
    """Plugin that fetches weather data and sends alerts"""
    
    async def initialize(self) -> bool:
        # Register commands
        self.register_command("weather", self.get_weather, 
                            "Get current weather")
        self.register_command("forecast", self.get_forecast,
                            "Get weather forecast")
        
        # Register scheduled task
        check_interval = self.get_config("check_interval", 1800)
        self.register_scheduled_task("check_weather", 
                                     check_interval,
                                     self.check_for_alerts)
        
        # Register menu item
        self.register_menu_item("utilities", "Weather", 
                               self.weather_menu,
                               "View weather information")
        
        return True
    
    async def get_weather(self, args, context):
        """Get current weather"""
        api_key = self.get_config("api_key", "")
        location = self.get_config("location", "")
        
        if not api_key:
            return "Weather API key not configured"
        
        try:
            # Check cache first
            cached = await self.retrieve_data("cache:current")
            if cached:
                return f"Weather: {cached['temp']}°F, {cached['conditions']}"
            
            # Fetch from API
            data = await self.http_get(
                "https://api.weather.com/current",
                params={"key": api_key, "location": location}
            )
            
            # Cache for 10 minutes
            await self.store_data("cache:current", data, ttl=600)
            
            return f"Weather: {data['temp']}°F, {data['conditions']}"
            
        except Exception as e:
            return f"Failed to get weather: {e}"
    
    async def get_forecast(self, args, context):
        """Get weather forecast"""
        # Similar implementation
        return "Forecast: Sunny, 75°F"
    
    async def check_for_alerts(self):
        """Check for weather alerts"""
        api_key = self.get_config("api_key", "")
        
        try:
            alerts = await self.http_get(
                "https://api.weather.com/alerts",
                params={"key": api_key}
            )
            
            if alerts:
                for alert in alerts:
                    await self.send_message(
                        f"⚠️ Weather Alert: {alert['title']}"
                    )
                    
        except Exception as e:
            self.logger.error(f"Failed to check alerts: {e}")
    
    async def weather_menu(self, context):
        """BBS menu handler"""
        weather = await self.get_weather([], context)
        return f"Current Weather\n{weather}"
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="weather_alert",
            version="1.0.0",
            description="Weather alerts and information",
            author="Your Name",
            priority=PluginPriority.NORMAL
        )
```

## Configuration Example

```yaml
plugins:
  weather_alert:
    enabled: true
    api_key: "your_api_key_here"
    location: "New York, NY"
    check_interval: 1800  # 30 minutes
```

## Best Practices

1. **Error Handling**: Always wrap external API calls in try-except blocks
2. **Rate Limiting**: The HTTP client enforces rate limits automatically
3. **Caching**: Use `store_data` with TTL for caching API responses
4. **Logging**: Use `self.logger` for all logging operations
5. **Configuration**: Use `get_config` with sensible defaults
6. **Cleanup**: Override `cleanup()` if you allocate resources that need cleanup
7. **Testing**: Write unit tests for your command handlers and scheduled tasks

## Troubleshooting

### Plugin Not Loading
- Check that `initialize()` returns `True`
- Verify plugin metadata is correct
- Check logs for initialization errors

### Commands Not Working
- Ensure commands are registered in `initialize()`
- Check command handler signature matches expected format
- Verify command handler returns a string

### HTTP Requests Failing
- Check rate limit (default 100 requests per minute)
- Verify API endpoint and credentials
- Check network connectivity
- Review error logs for details

### Scheduled Tasks Not Running
- Verify task is registered in `initialize()`
- Check that plugin is started (not just loaded)
- Ensure task handler doesn't raise unhandled exceptions
- Check logs for task execution errors


## Core Service Access

The Enhanced Plugin API provides controlled access to core ZephyrGate services through a permission-based system. All core service access requires appropriate permissions to be declared in the plugin manifest.

### Permission System

Plugins must declare required permissions in their `manifest.yaml` file:

```yaml
permissions:
  - send_messages           # Send messages to mesh network
  - system_state_read       # Query system state
  - inter_plugin_messaging  # Communicate with other plugins
  - database_access         # Access database
  - http_requests          # Make HTTP requests
  - schedule_tasks         # Register scheduled tasks
```

If a plugin attempts to use a capability without the required permission, a `PermissionDeniedError` will be raised.

### System State Queries

Query read-only system state information.

**Required Permission:** `system_state_read`

#### `get_node_info(node_id=None) -> Optional[Dict[str, Any]]`

Get information about a mesh node.

**Parameters:**
- `node_id` (str, optional): Node ID to query (None for local node)

**Returns:**
- Dictionary with node information or None if not found

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

**Returns:**
- Dictionary with network status information

**Example:**
```python
status = self.get_network_status()
if status['connected']:
    self.logger.info(f"Network has {status['node_count']} nodes")
```

#### `get_plugin_list() -> List[str]`

Get list of running plugins.

**Returns:**
- List of plugin names

**Example:**
```python
plugins = self.get_plugin_list()
self.logger.info(f"Running plugins: {', '.join(plugins)}")
```

#### `get_plugin_status(plugin_name) -> Optional[Dict[str, Any]]`

Get status of another plugin.

**Parameters:**
- `plugin_name` (str): Name of the plugin to query

**Returns:**
- Dictionary with plugin status or None if not found

**Example:**
```python
status = self.get_plugin_status("weather")
if status and status['is_running']:
    self.logger.info("Weather plugin is running")
```

### Message Routing to Mesh

Send messages to the mesh network with permission enforcement.

**Required Permission:** `send_messages`

#### `send_message(content, destination=None, channel=None) -> bool`

Send a message to the mesh network. This method is enhanced with permission checking.

**Parameters:**
- `content` (str): Message content
- `destination` (str, optional): Destination node ID (None for broadcast)
- `channel` (int, optional): Channel number (None for default)

**Returns:**
- True if message was queued successfully

**Raises:**
- `PermissionDeniedError`: If plugin doesn't have send_messages permission

**Example:**
```python
try:
    # Send broadcast message
    await self.send_message("Hello mesh!")
    
    # Send to specific node
    await self.send_message("Private message", destination="!abc123")
    
    # Send on specific channel
    await self.send_message("Channel message", channel=2)
except PermissionDeniedError:
    self.logger.error("No permission to send messages")
```

### Inter-Plugin Messaging

Communicate with other plugins through a structured messaging system.

**Required Permission:** `inter_plugin_messaging`

#### `send_to_plugin(target_plugin, message_type, data) -> Optional[PluginResponse]`

Send a message to another plugin.

**Parameters:**
- `target_plugin` (str): Name of the target plugin
- `message_type` (str): Type of message
- `data` (Any): Message data (must be JSON serializable)

**Returns:**
- `PluginResponse` object with success status and data, or None if no handler

**Raises:**
- `PermissionDeniedError`: If plugin doesn't have inter_plugin_messaging permission

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
    elif response:
        self.logger.error(f"Error: {response.error}")
except PermissionDeniedError:
    self.logger.error("No permission for inter-plugin messaging")
```

#### `broadcast_to_plugins(message_type, data) -> List[PluginResponse]`

Broadcast a message to all plugins.

**Parameters:**
- `message_type` (str): Type of message
- `data` (Any): Message data (must be JSON serializable)

**Returns:**
- List of `PluginResponse` objects from all plugins

**Raises:**
- `PermissionDeniedError`: If plugin doesn't have inter_plugin_messaging permission

**Example:**
```python
try:
    responses = await self.broadcast_to_plugins(
        "system_alert",
        {"level": "warning", "message": "Low battery"}
    )
    
    for response in responses:
        if response.success:
            plugin = response.metadata.get('target_plugin')
            self.logger.info(f"{plugin} acknowledged alert")
except PermissionDeniedError:
    self.logger.error("No permission for inter-plugin messaging")
```

#### `register_inter_plugin_handler(handler)`

Register a handler for incoming inter-plugin messages.

**Parameters:**
- `handler` (Callable): Async function with signature `async def handler(message: PluginMessage) -> Any`

**Example:**
```python
async def handle_plugin_message(message):
    message_type = message.metadata.get('message_type')
    
    if message_type == 'ping':
        return {'status': 'pong', 'plugin': self.name}
    elif message_type == 'get_data':
        return {'data': self.get_some_data()}
    
    return None  # Unknown message type

self.register_inter_plugin_handler(handle_plugin_message)
```

## Error Handling

### PermissionDeniedError

Raised when a plugin attempts to use a capability without the required permission.

**Example:**
```python
from src.core.plugin_core_services import PermissionDeniedError

try:
    await self.send_message("Hello")
except PermissionDeniedError as e:
    self.logger.error(f"Permission denied: {e}")
    # Handle gracefully - maybe notify user or disable feature
```

## Complete Example

Here's a complete example demonstrating core service access:

```python
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_interfaces import PluginMessage
from src.core.plugin_core_services import PermissionDeniedError

class MyPlugin(EnhancedPlugin):
    async def start(self) -> bool:
        await super().start()
        
        # Register commands
        self.register_command("status", self.handle_status)
        self.register_command("ping", self.handle_ping)
        
        # Register inter-plugin handler
        self.register_inter_plugin_handler(self.handle_plugin_message)
        
        return True
    
    async def handle_status(self, args, context):
        """Get system status"""
        try:
            status = self.get_network_status()
            plugins = self.get_plugin_list()
            
            response = f"Network: {status['connected']}\n"
            response += f"Plugins: {len(plugins)}"
            return response
        except PermissionDeniedError:
            return "Permission denied"
    
    async def handle_ping(self, args, context):
        """Ping another plugin"""
        if not args:
            return "Usage: ping <plugin_name>"
        
        try:
            response = await self.send_to_plugin(
                args[0], "ping", {"sender": self.name}
            )
            
            if response and response.success:
                return f"Pong: {response.data}"
            return "No response"
        except PermissionDeniedError:
            return "Permission denied"
    
    async def handle_plugin_message(self, message: PluginMessage):
        """Handle inter-plugin messages"""
        msg_type = message.metadata.get('message_type')
        
        if msg_type == 'ping':
            return {'status': 'pong', 'plugin': self.name}
        
        return None
```

**Manifest (manifest.yaml):**
```yaml
name: my_plugin
version: 1.0.0
description: "Example plugin with core service access"
author: "Your Name"

permissions:
  - send_messages
  - system_state_read
  - inter_plugin_messaging

capabilities:
  commands:
    - name: status
      description: "Get system status"
    - name: ping
      description: "Ping another plugin"
```

## Best Practices

1. **Always handle PermissionDeniedError**: Wrap core service calls in try-except blocks to handle permission errors gracefully.

2. **Request minimal permissions**: Only request permissions your plugin actually needs.

3. **Document required permissions**: Clearly document in your plugin's README what permissions are required and why.

4. **Validate inter-plugin messages**: Always validate data received from other plugins before using it.

5. **Use appropriate message types**: Use descriptive message types for inter-plugin communication to make debugging easier.

6. **Handle missing responses**: When sending inter-plugin messages, always handle the case where no response is received.

7. **Log permission errors**: Log permission errors to help users understand why features aren't working.

## See Also

- [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)
- [Plugin Manifest Format](PLUGIN_MANIFEST.md)
- [Example Plugins](../examples/plugins/)
