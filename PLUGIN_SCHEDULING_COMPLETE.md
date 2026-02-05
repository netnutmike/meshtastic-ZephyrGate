# Plugin Scheduling & Shell Commands - Complete! ✅

## New Features Implemented

### 1. ✅ Scheduled Plugin Calls

Call any plugin method on a schedule to generate dynamic content:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning weather from weather plugin
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
        format: "brief"
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7:00 AM daily
      channel: 0
      priority: "normal"
      enabled: true
```

**Features:**
- Call any plugin method
- Pass custom arguments
- Schedule with cron, interval, or one-time
- Flexible and extensible
- All in YAML!

### 2. ✅ Scheduled Shell Commands

Execute shell commands and broadcast results:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # System uptime
    - name: "System Status"
      command: "uptime"
      prefix: "📊 Status:"
      timeout: 10
      max_output_length: 200
      schedule_type: "cron"
      cron_expression: "0 12 * * *"  # Noon daily
      channel: 0
      priority: "low"
      enabled: true
```

**Features:**
- Execute any shell command
- Configurable timeout
- Output length limiting
- Optional prefix
- All in YAML!

---

## Three Types of Scheduled Tasks

### 1. Static Broadcasts
Predefined messages:
```yaml
- name: "Morning Greeting"
  message: "☀️ Good morning!"
  schedule_type: "cron"
  cron_expression: "0 8 * * *"
  channel: 0
  enabled: true
```

### 2. Plugin Calls
Dynamic content from plugins:
```yaml
- name: "Weather Forecast"
  plugin_name: "weather_service"
  plugin_method: "get_forecast_summary"
  plugin_args: {}
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  enabled: true
```

### 3. Shell Commands
Command output:
```yaml
- name: "System Uptime"
  command: "uptime"
  prefix: "📊 Status:"
  timeout: 10
  schedule_type: "cron"
  cron_expression: "0 12 * * *"
  channel: 0
  enabled: true
```

---

## Complete Example Configuration

```yaml
# config/config.yaml

scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning routine
    - name: "Morning Greeting"
      message: "☀️ Good morning! Network is active."
      schedule_type: "cron"
      cron_expression: "0 6 * * *"
      channel: 0
      enabled: true
    
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
        format: "brief"
      schedule_type: "cron"
      cron_expression: "0 7 * * *"
      channel: 0
      enabled: true
    
    # Midday status
    - name: "System Status"
      command: "uptime"
      prefix: "📊 Noon Status:"
      timeout: 10
      max_output_length: 200
      schedule_type: "cron"
      cron_expression: "0 12 * * *"
      channel: 0
      priority: "low"
      enabled: true
    
    # Evening weather
    - name: "Evening Weather"
      plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      plugin_args: {}
      schedule_type: "cron"
      cron_expression: "0 18 * * *"
      channel: 0
      enabled: true
    
    # Hourly beacon
    - name: "Hourly Beacon"
      message: "📡 Network active"
      schedule_type: "interval"
      interval_seconds: 3600
      channel: 0
      priority: "low"
      enabled: true
```

---

## Weather Plugin Example

Your specific use case - morning weather forecast:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Morning Weather Forecast"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"  # Uses your configured location
        format: "brief"      # Concise format
        days: 1              # Today's forecast
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7:00 AM every day
      channel: 0
      priority: "normal"
      enabled: true
```

---

## Creating Custom Plugin Methods

### Step 1: Add Method to Plugin

```python
# In your plugin

async def get_custom_data(self, format='brief'):
    """Generate custom content for scheduled broadcasts"""
    try:
        # Your logic here
        data = await self.fetch_data()
        content = self.format_data(data, format)
        
        return {
            'content': content,
            'success': True
        }
    except Exception as e:
        return {
            'content': f"Error: {e}",
            'success': False
        }
```

### Step 2: Handle Scheduled Requests

```python
# In plugin's message handler

async def handle_plugin_message(self, message):
    if message.data.get('request_type') == 'scheduled_content':
        method_name = message.data.get('method')
        args = message.data.get('args', {})
        
        method = getattr(self, method_name, None)
        if method:
            result = await method(**args)
            return PluginMessage(
                type=PluginMessageType.RESPONSE,
                data=result
            )
```

### Step 3: Configure in YAML

```yaml
- name: "My Custom Broadcast"
  plugin_name: "my_plugin"
  plugin_method: "get_custom_data"
  plugin_args:
    format: "brief"
  schedule_type: "cron"
  cron_expression: "0 8 * * *"
  channel: 0
  enabled: true
```

---

## Files Created/Modified

### New Files
1. `docs/SCHEDULED_PLUGIN_CALLS_GUIDE.md` - Complete guide
2. `PLUGIN_SCHEDULING_COMPLETE.md` - This file

### Modified Files
1. `src/services/asset/scheduling_service.py` - Added plugin call and shell command handlers
2. `src/core/config_loader.py` - Load plugin calls and shell commands from config
3. `config/config.yaml` - Added examples for plugin calls and shell commands
4. `config/auto_response_examples.yaml` - Added examples 25-27

---

## Quick Start

### 1. Configure Weather Broadcast

Edit `config/config.yaml`:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
      schedule_type: "cron"
      cron_expression: "0 7 * * *"
      channel: 0
      enabled: true
```

### 2. Restart Service

```bash
./stop.sh && ./start.sh
```

### 3. Check Logs

```bash
tail -f logs/zephyrgate.log | grep -E "(plugin|scheduled|weather)"
```

Look for:
- `"Loaded scheduled plugin_call from config: Morning Weather"`
- `"Calling plugin: weather_service.get_forecast_summary"`
- `"Plugin content broadcast:"`

### 4. Wait for Scheduled Time

The weather forecast will be broadcast at 7:00 AM daily.

---

## Testing

### Test with Short Interval

```yaml
- name: "Test Weather"
  plugin_name: "weather_service"
  plugin_method: "get_current_conditions"
  plugin_args: {}
  schedule_type: "interval"
  interval_seconds: 300  # 5 minutes for testing
  channel: 0
  enabled: true
```

### Monitor Execution

```bash
# Watch for plugin calls
tail -f logs/zephyrgate.log | grep "Calling plugin"

# Watch for broadcasts
tail -f logs/zephyrgate.log | grep "broadcast"

# Watch for errors
tail -f logs/zephyrgate.log | grep -i error
```

---

## Common Use Cases

### 1. Daily Weather Forecast

```yaml
- name: "Morning Weather"
  plugin_name: "weather_service"
  plugin_method: "get_forecast_summary"
  plugin_args: {}
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  enabled: true
```

### 2. Hourly Weather Updates

```yaml
- name: "Weather Update"
  plugin_name: "weather_service"
  plugin_method: "get_current_conditions"
  plugin_args: {}
  schedule_type: "interval"
  interval_seconds: 3600
  channel: 0
  enabled: true
```

### 3. System Status

```yaml
- name: "System Status"
  command: "uptime"
  prefix: "📊 Status:"
  timeout: 10
  schedule_type: "cron"
  cron_expression: "0 12 * * *"
  channel: 0
  enabled: true
```

### 4. Custom Script

```yaml
- name: "Custom Report"
  command: "/path/to/your/script.sh"
  prefix: "📋 Report:"
  timeout: 30
  max_output_length: 500
  schedule_type: "cron"
  cron_expression: "0 8 * * *"
  channel: 0
  enabled: true
```

---

## Future Plugins

When you create new plugins, just add methods that return content:

```python
async def generate_report(self, report_type='summary'):
    """Generate report for scheduled broadcast"""
    report = await self.create_report(report_type)
    return {
        'content': f"📊 Report\n{report}",
        'success': True
    }
```

Then configure in YAML:

```yaml
- name: "Daily Report"
  plugin_name: "my_new_plugin"
  plugin_method: "generate_report"
  plugin_args:
    report_type: "summary"
  schedule_type: "cron"
  cron_expression: "0 9 * * *"
  channel: 0
  enabled: true
```

---

## Documentation

- **[SCHEDULED_PLUGIN_CALLS_GUIDE.md](docs/SCHEDULED_PLUGIN_CALLS_GUIDE.md)** - Complete guide
- **[YAML_CONFIGURATION_GUIDE.md](docs/YAML_CONFIGURATION_GUIDE.md)** - YAML configuration
- **[auto_response_examples.yaml](config/auto_response_examples.yaml)** - Examples 25-27

---

## Summary

You can now:

1. ✅ **Call weather plugin** for morning forecast
2. ✅ **Call any plugin** on a schedule
3. ✅ **Run shell commands** and broadcast results
4. ✅ **Create custom plugin methods** for future use
5. ✅ **Configure everything in YAML** - no Python needed!

**Your specific request is fully implemented:**
- Morning weather forecast from weather plugin ✅
- Flexible for future plugins ✅
- Shell command support for future use ✅
- All configurable in YAML ✅

Enjoy your automated weather forecasts and plugin scheduling! 🌤️
