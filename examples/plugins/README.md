# ZephyrGate Example Plugins

This directory contains example plugins that demonstrate various features of the ZephyrGate plugin system. Each plugin showcases different capabilities and best practices for plugin development.

## Available Examples

### 1. Hello World Plugin (`hello_world_plugin.py`)

**Purpose**: Minimal example demonstrating basic plugin functionality

**Features Demonstrated**:
- Command registration
- Message handling
- Configuration access
- Scheduled tasks
- Data storage
- Mesh messaging

**Commands**:
- `hello` - Say hello to the mesh network
- `greet <name>` - Greet a specific user

**Configuration**:
```yaml
plugins:
  hello_world:
    enabled: true
    greeting_message: "Greetings"
    greeting_interval: 3600
    periodic_greeting_enabled: false
```

**Use Case**: Starting point for new plugin developers

---

### 2. Weather Alert Plugin (`weather_alert_plugin.py`)

**Purpose**: Demonstrates HTTP requests and scheduled data fetching

**Features Demonstrated**:
- HTTP client usage (simulated)
- Scheduled task execution
- Data caching with TTL
- Configuration management
- Error handling for network requests
- Alert system

**Commands**:
- `weather <location>` - Get current weather
- `weatheralert [location]` - Check for weather alerts
- `weatherconfig` - Show configuration

**Configuration**:
```yaml
plugins:
  weather_alert:
    enabled: true
    default_location: "San Francisco"
    check_interval: 1800  # 30 minutes
    alerts_enabled: true
    temp_threshold: 35  # Celsius
    wind_threshold: 50  # km/h
    alert_types:
      - severe
      - warning
```

**Use Case**: Plugins that need to fetch external data periodically and send alerts

---

### 3. Menu Example Plugin (`menu_example_plugin.py`)

**Purpose**: Demonstrates BBS menu integration

**Features Demonstrated**:
- Menu item registration
- Multiple menu locations
- Admin-only menu items
- Menu handler context access
- Dynamic menu ordering

**Menu Items**:
- Utilities → Plugin Demo
- Utilities → Admin Demo (admin only)
- Main → Quick Demo

**Configuration**:
```yaml
plugins:
  menu_example:
    enabled: true
```

**Use Case**: Plugins that provide interactive BBS menu interfaces

---

### 4. Data Logger Plugin (`data_logger_plugin.py`)

**Purpose**: Demonstrates plugin storage capabilities

**Features Demonstrated**:
- Storing and retrieving data
- Data persistence across restarts
- TTL (Time To Live) for cached data
- Data querying and filtering
- Statistics tracking
- Export functionality
- Automatic message logging

**Commands**:
- `log <type> <message>` - Log a message (types: info, warning, error, event)
- `logquery [type] [limit]` - Query logged data
- `logstats` - Show logging statistics
- `logexport [type] [limit]` - Export logged data
- `logclear <type|all>` - Clear logged data

**Configuration**:
```yaml
plugins:
  data_logger:
    enabled: true
    auto_log_messages: true
    max_stored_entries: 1000
```

**Use Case**: Plugins that need to store and query historical data

---

### 5. Multi-Command Plugin (`multi_command_plugin.py`)

**Purpose**: Demonstrates multiple command handlers with different patterns

**Features Demonstrated**:
- Multiple command registration
- Different priority levels
- Argument parsing and validation
- Context usage
- Help system
- Command usage tracking

**Commands**:
- `echo <message>` - Echo back a message (high priority)
- `time [format]` - Show current time (formats: utc, local, unix)
- `calc <op> <n1> <n2>` - Simple calculator (operations: add, sub, mul, div)
- `reverse <text>` - Reverse a string
- `count <type> <text>` - Count words or characters (types: words, chars)
- `info` - Show message context information
- `help [command]` - Show help information
- `fallback` - Low priority fallback handler

**Configuration**:
```yaml
plugins:
  multi_command:
    enabled: true
```

**Use Case**: Plugins that provide multiple utility commands

---

### 6. Scheduled Task Example Plugin (`scheduled_task_example_plugin.py`)

**Purpose**: Demonstrates scheduled task system with multiple schedules

**Features Demonstrated**:
- Interval-based scheduling
- Cron-style scheduling
- Error handling in scheduled tasks
- Task status monitoring
- Multiple concurrent tasks

**Commands**:
- `taskstatus` - Show status of all scheduled tasks

**Scheduled Tasks**:
- `periodic_update` - Runs every 60 seconds
- `five_minute_report` - Runs every 5 minutes (cron: */5 * * * *)
- `error_demo` - Demonstrates error handling (runs every 120 seconds)

**Configuration**:
```yaml
plugins:
  scheduled_task_example:
    enabled: true
```

**Use Case**: Plugins that need to perform periodic background tasks

---

### 7. Core Services Example Plugin (`core_services_example_plugin.py`)

**Purpose**: Demonstrates core service access and inter-plugin messaging

**Features Demonstrated**:
- Message routing to mesh network
- System state queries
- Inter-plugin messaging
- Permission enforcement
- Broadcasting to all plugins

**Commands**:
- `status [node_id]` - Get system status information
- `ping <plugin_name>` - Ping another plugin
- `broadcast <message>` - Broadcast a message to all plugins
- `mesh <message> [destination] [channel]` - Send message to mesh network

**Required Permissions**:
- `send_messages`
- `system_state_read`
- `inter_plugin_messaging`

**Configuration**:
```yaml
plugins:
  core_services_example:
    enabled: true
```

**Use Case**: Plugins that need to interact with other plugins or access system state

---

## Quick Start

### Using an Example Plugin

1. **Copy the example plugin** to your plugins directory:
   ```bash
   cp examples/plugins/hello_world_plugin.py plugins/
   ```

2. **Add configuration** to your `config.yaml`:
   ```yaml
   plugins:
     hello_world:
       enabled: true
   ```

3. **Restart ZephyrGate** or enable the plugin dynamically through the admin interface

4. **Test the plugin** by sending a command:
   ```
   hello
   ```

### Creating Your Own Plugin

1. **Start with an example** that matches your use case
2. **Copy and rename** the example plugin
3. **Modify the class name** and functionality
4. **Update the configuration** section
5. **Test thoroughly** before deployment

## Plugin Development Resources

- **Plugin Development Guide**: `docs/PLUGIN_DEVELOPMENT.md`
- **Enhanced Plugin API**: `docs/ENHANCED_PLUGIN_API.md`
- **Plugin Template Generator**: `docs/PLUGIN_TEMPLATE_GENERATOR.md`
- **Plugin Menu Integration**: `docs/PLUGIN_MENU_INTEGRATION.md`

## Common Patterns

### Command Handler Pattern
```python
async def handle_command(self, args: List[str], context: Dict[str, Any]) -> str:
    if not args:
        return "Usage: command <arg>"
    
    # Process command
    result = process(args)
    
    return f"Result: {result}"
```

### Scheduled Task Pattern
```python
async def scheduled_task(self):
    try:
        # Perform task
        data = await fetch_data()
        await self.store_data("key", data)
    except Exception as e:
        self.logger.error(f"Task error: {e}")
```

### Storage Pattern
```python
# Store data
await self.store_data("key", value, ttl=3600)

# Retrieve data
value = await self.retrieve_data("key", default=None)

# Delete data
await self.delete_data("key")
```

### HTTP Request Pattern
```python
try:
    data = await self.http_get(url, params={'key': 'value'})
    # Process data
except Exception as e:
    self.logger.error(f"HTTP error: {e}")
```

### Menu Handler Pattern
```python
async def menu_handler(self, context: Dict[str, Any]) -> str:
    user_name = context.get('user_name', 'Unknown')
    
    response = [
        "=== Menu Title ===",
        f"Hello {user_name}!",
        "Menu content here..."
    ]
    
    return "\n".join(response)
```

## Testing Your Plugin

1. **Unit Tests**: Test individual methods
2. **Integration Tests**: Test with ZephyrGate core
3. **Manual Testing**: Test commands and functionality
4. **Error Testing**: Test error handling and edge cases

## Best Practices

1. **Error Handling**: Always wrap operations in try-except blocks
2. **Logging**: Use `self.logger` for all log messages
3. **Configuration**: Use `self.get_config()` for all settings
4. **Storage**: Use plugin storage for persistent data
5. **Documentation**: Include docstrings and usage examples
6. **Cleanup**: Properly clean up resources in `stop()` method

## Troubleshooting

### Plugin Not Loading
- Check plugin is in correct directory
- Verify configuration is correct
- Check logs for error messages
- Ensure all dependencies are installed

### Commands Not Working
- Verify command registration in `initialize()`
- Check command priority conflicts
- Review command handler implementation
- Test with simple echo command first

### Scheduled Tasks Not Running
- Verify task registration
- Check task interval/cron expression
- Review task handler for errors
- Check plugin is started successfully

## Contributing

When contributing example plugins:
1. Follow existing code style
2. Include comprehensive documentation
3. Add configuration examples
4. Test thoroughly
5. Update this README

## License

These examples are provided under the same license as ZephyrGate.
