# ZephyrGate Plugin Examples - Feature Matrix

This document provides a quick reference showing which features each example plugin demonstrates.

## Feature Coverage Matrix

| Feature | hello_world | weather_alert | menu_example | data_logger | multi_command | scheduled_task | core_services |
|---------|-------------|---------------|--------------|-------------|---------------|----------------|---------------|
| **Command Registration** | ✓ | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| **Multiple Commands** | ✓ | ✓ | - | ✓ | ✓✓✓ | ✓ | ✓ |
| **Command Priority** | ✓ | ✓ | - | ✓ | ✓✓✓ | ✓ | ✓ |
| **Message Handlers** | ✓ | - | - | ✓ | - | - | ✓ |
| **Scheduled Tasks** | ✓ | ✓✓ | - | ✓ | - | ✓✓✓ | - |
| **Interval Scheduling** | ✓ | ✓ | - | ✓ | - | ✓ | - |
| **Cron Scheduling** | - | - | - | - | - | ✓ | - |
| **BBS Menu Integration** | - | - | ✓✓✓ | - | - | - | - |
| **Data Storage** | ✓ | ✓✓ | - | ✓✓✓ | ✓ | - | - |
| **Storage with TTL** | - | ✓ | - | ✓ | - | - | - |
| **HTTP Requests** | - | ✓✓✓ | - | - | - | - | - |
| **Configuration Access** | ✓ | ✓✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Mesh Messaging** | ✓ | ✓ | - | - | - | - | ✓✓ |
| **Inter-Plugin Messaging** | - | - | - | - | - | - | ✓✓✓ |
| **System State Queries** | - | - | - | - | - | - | ✓✓ |
| **Error Handling** | ✓ | ✓✓ | ✓ | ✓✓ | ✓ | ✓✓ | ✓✓ |
| **Context Usage** | ✓ | ✓ | ✓✓ | ✓ | ✓✓✓ | ✓ | ✓✓ |
| **Help System** | - | - | - | - | ✓✓ | - | - |
| **Statistics Tracking** | ✓ | - | - | ✓✓✓ | ✓ | ✓ | - |
| **Data Export** | - | - | - | ✓✓ | - | - | - |
| **Permission Enforcement** | - | - | - | - | - | - | ✓✓ |

**Legend:**
- ✓ = Feature demonstrated
- ✓✓ = Feature heavily used
- ✓✓✓ = Primary focus of example
- `-` = Feature not demonstrated

## Learning Path

### Beginner Path

1. **Start with `hello_world_plugin.py`**
   - Learn basic plugin structure
   - Understand command registration
   - See simple message handling
   - Introduction to configuration

2. **Move to `multi_command_plugin.py`**
   - Learn multiple command patterns
   - Understand command priorities
   - See argument parsing
   - Learn help system implementation

3. **Try `data_logger_plugin.py`**
   - Learn data storage
   - Understand data persistence
   - See query patterns
   - Learn statistics tracking

### Intermediate Path

4. **Explore `menu_example_plugin.py`**
   - Learn BBS menu integration
   - Understand menu handlers
   - See admin-only features
   - Learn menu context usage

5. **Study `scheduled_task_example_plugin.py`**
   - Learn interval scheduling
   - Understand cron expressions
   - See error handling in tasks
   - Learn task monitoring

6. **Review `weather_alert_plugin.py`**
   - Learn HTTP client usage
   - Understand data caching
   - See alert systems
   - Learn periodic data fetching

### Advanced Path

7. **Master `core_services_example_plugin.py`**
   - Learn inter-plugin messaging
   - Understand system state queries
   - See permission enforcement
   - Learn broadcasting patterns

## Use Case to Example Mapping

### "I want to create a plugin that..."

#### ...responds to commands
→ Start with `hello_world_plugin.py` or `multi_command_plugin.py`

#### ...fetches data from the internet
→ Use `weather_alert_plugin.py` as template

#### ...stores and queries data
→ Use `data_logger_plugin.py` as template

#### ...adds menu items to the BBS
→ Use `menu_example_plugin.py` as template

#### ...runs tasks on a schedule
→ Use `scheduled_task_example_plugin.py` as template

#### ...communicates with other plugins
→ Use `core_services_example_plugin.py` as template

#### ...provides multiple utility commands
→ Use `multi_command_plugin.py` as template

## Code Snippets by Feature

### Command Registration
```python
# From hello_world_plugin.py
self.register_command(
    "hello",
    self.handle_hello_command,
    "Say hello to the mesh network",
    priority=100
)
```

### Scheduled Task Registration
```python
# From weather_alert_plugin.py
self.register_scheduled_task(
    "weather_check",
    check_interval,
    self.check_weather_task
)
```

### Menu Item Registration
```python
# From menu_example_plugin.py
self.register_menu_item(
    menu="utilities",
    label="Plugin Demo",
    handler=self.demo_handler,
    description="Demonstration of plugin menu integration",
    command="plugindemo",
    order=150
)
```

### Data Storage
```python
# From data_logger_plugin.py
# Store with TTL
await self.store_data("key", value, ttl=3600)

# Retrieve
value = await self.retrieve_data("key", default=None)
```

### HTTP Request
```python
# From weather_alert_plugin.py (simulated)
data = await self.http_get(api_url, params={'location': location})
```

### Inter-Plugin Messaging
```python
# From core_services_example_plugin.py
response = await self.send_to_plugin(
    target_plugin,
    "ping",
    {"timestamp": datetime.utcnow().isoformat()}
)
```

### Message Handler
```python
# From hello_world_plugin.py
self.register_message_handler(self.handle_message, priority=200)

async def handle_message(self, message, context):
    # Process message
    return None  # Allow other handlers to process
```

## Testing Examples

Each example can be tested by:

1. **Copying to plugins directory**
   ```bash
   cp examples/plugins/hello_world_plugin.py plugins/
   ```

2. **Adding configuration**
   ```yaml
   plugins:
     hello_world:
       enabled: true
   ```

3. **Restarting ZephyrGate or enabling dynamically**

4. **Testing commands**
   ```
   hello
   greet Alice
   ```

## Common Patterns Demonstrated

### Error Handling Pattern
All examples demonstrate proper error handling:
```python
try:
    # Operation
    result = await operation()
    return f"Success: {result}"
except Exception as e:
    self.logger.error(f"Error: {e}")
    return f"Error: {str(e)}"
```

### Configuration Pattern
All examples show configuration access:
```python
value = self.get_config("key", default_value)
```

### Logging Pattern
All examples use proper logging:
```python
self.logger.info("Operation completed")
self.logger.warning("Warning message")
self.logger.error(f"Error: {e}")
```

### Context Usage Pattern
Command handlers receive context:
```python
async def handle_command(self, args, context):
    sender_id = context.get('sender_id', 'unknown')
    channel = context.get('channel', 'unknown')
    # Use context information
```

## Additional Resources

- **Plugin Development Guide**: `docs/PLUGIN_DEVELOPMENT.md`
- **Enhanced Plugin API**: `docs/ENHANCED_PLUGIN_API.md`
- **Plugin Template Generator**: Use `create_plugin.py` to generate new plugins
- **Example Plugins README**: `examples/plugins/README.md`

## Contributing New Examples

When adding new example plugins:

1. **Focus on a specific feature or use case**
2. **Include comprehensive docstrings**
3. **Add configuration examples**
4. **Create a manifest file**
5. **Update this overview document**
6. **Update the README.md**
7. **Test thoroughly**

## Questions?

If you have questions about any example:
1. Read the plugin's docstrings
2. Check the README.md
3. Review the Plugin Development Guide
4. Ask in the ZephyrGate community
