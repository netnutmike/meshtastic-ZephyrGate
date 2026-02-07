# Scheduled Plugin Calls and Shell Commands Guide

## Overview

The scheduling system supports three types of automated tasks:
1. **Static Broadcasts** - Send predefined messages
2. **Plugin Calls** - Call plugins to generate dynamic content
3. **Shell Commands** - Execute commands and broadcast results

**All configured in YAML - no Python code changes needed!**

---

## Table of Contents

1. [Plugin Calls](#plugin-calls)
2. [Shell Commands](#shell-commands)
3. [Configuration Examples](#configuration-examples)
4. [Creating Custom Plugin Methods](#creating-custom-plugin-methods)
5. [Weather Plugin Example](#weather-plugin-example)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Plugin Calls

### Basic Configuration

Call a plugin to generate content and broadcast it:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
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

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Descriptive name |
| `plugin_name` | string | Yes | Name of the plugin to call |
| `plugin_method` | string | No | Method to call (default: "generate_content") |
| `plugin_args` | dict | No | Arguments to pass to method |
| `schedule_type` | string | Yes | "cron", "interval", or "one_time" |
| `cron_expression` | string | For cron | Cron schedule |
| `interval_seconds` | integer | For interval | Seconds between calls |
| `scheduled_time` | string | For one_time | ISO timestamp |
| `channel` | integer | No | Channel to broadcast on (default: 0) |
| `priority` | string | No | "low", "normal", "high" (default: "normal") |
| `enabled` | boolean | No | Enable/disable (default: true) |

### How It Works

1. Scheduler triggers at specified time
2. Sends message to plugin requesting content
3. Plugin generates content and returns it
4. Content is broadcast on specified channel
5. Process repeats based on schedule

---

## Shell Commands

### Basic Configuration

Execute a shell command and broadcast the result:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "System Uptime"
      command: "uptime"
      prefix: "📊 System Status:"
      timeout: 10
      max_output_length: 200
      schedule_type: "cron"
      cron_expression: "0 12 * * *"  # Noon daily
      channel: 0
      priority: "low"
      enabled: true
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Descriptive name |
| `command` | string | Yes | Shell command to execute |
| `prefix` | string | No | Text to prepend to output |
| `timeout` | integer | No | Max execution time in seconds (default: 30) |
| `max_output_length` | integer | No | Max characters to broadcast (default: 500) |
| `schedule_type` | string | Yes | "cron", "interval", or "one_time" |
| `cron_expression` | string | For cron | Cron schedule |
| `interval_seconds` | integer | For interval | Seconds between executions |
| `scheduled_time` | string | For one_time | ISO timestamp |
| `channel` | integer | No | Channel to broadcast on (default: 0) |
| `priority` | string | No | "low", "normal", "high" (default: "normal") |
| `enabled` | boolean | No | Enable/disable (default: true) |

### Security Considerations

- Commands run with service permissions
- Use absolute paths for scripts
- Test commands manually first
- Set appropriate timeouts
- Limit output length
- Be careful with sensitive data

---

## Configuration Examples

### Example 1: Morning Weather from Plugin

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Morning Weather Forecast"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
        format: "brief"
        days: 1
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7:00 AM daily
      channel: 0
      priority: "normal"
      enabled: true
```

### Example 2: Hourly System Status

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "System Status"
      command: "uptime"
      prefix: "📊 Status:"
      timeout: 10
      max_output_length: 200
      schedule_type: "interval"
      interval_seconds: 3600  # Every hour
      channel: 0
      priority: "low"
      enabled: true
```

### Example 3: Multiple Plugin Calls

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning weather
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args: {}
      schedule_type: "cron"
      cron_expression: "0 7 * * *"
      channel: 0
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
    
    # BBS summary every 6 hours
    - name: "BBS Summary"
      plugin_name: "bbs_service"
      plugin_method: "get_unread_summary"
      plugin_args: {}
      schedule_type: "interval"
      interval_seconds: 21600
      channel: 0
      enabled: true
```

### Example 4: Complete Daily Routine

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # 6 AM - Morning greeting
    - name: "Morning Greeting"
      message: "☀️ Good morning! Network is active."
      schedule_type: "cron"
      cron_expression: "0 6 * * *"
      channel: 0
      enabled: true
    
    # 7 AM - Weather forecast
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
      schedule_type: "cron"
      cron_expression: "0 7 * * *"
      channel: 0
      enabled: true
    
    # Noon - System status
    - name: "Noon Status"
      command: "uptime"
      prefix: "📊 Noon Status:"
      timeout: 10
      schedule_type: "cron"
      cron_expression: "0 12 * * *"
      channel: 0
      enabled: true
    
    # 6 PM - Evening weather
    - name: "Evening Weather"
      plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      plugin_args: {}
      schedule_type: "cron"
      cron_expression: "0 18 * * *"
      channel: 0
      enabled: true
    
    # 8 PM - Evening announcement
    - name: "Evening Announcement"
      message: "🌙 Good evening! Network operational."
      schedule_type: "cron"
      cron_expression: "0 20 * * *"
      channel: 0
      enabled: true
```

---

## Creating Custom Plugin Methods

### Step 1: Add Method to Your Plugin

```python
# In your plugin (e.g., plugins/my_plugin/plugin.py)

async def get_custom_summary(self, format='brief', include_details=False):
    """
    Generate custom summary for scheduled broadcasts
    
    Args:
        format: 'brief' or 'detailed'
        include_details: Include additional details
        
    Returns:
        dict with 'content' and 'success' keys
    """
    try:
        # Generate your content
        summary = await self._generate_summary(format, include_details)
        
        # Format for broadcast
        content = f"📋 Custom Summary\n{summary}"
        
        # Return in expected format
        return {
            'content': content,
            'success': True
        }
    except Exception as e:
        self.logger.error(f"Error generating summary: {e}")
        return {
            'content': f"Error generating summary: {e}",
            'success': False
        }
```

### Step 2: Handle Scheduled Content Requests

```python
# In your plugin's message handler

async def handle_plugin_message(self, message):
    """Handle incoming plugin messages"""
    
    # Check if this is a scheduled content request
    if message.data.get('request_type') == 'scheduled_content':
        method_name = message.data.get('method', 'generate_content')
        args = message.data.get('args', {})
        
        # Get the method
        method = getattr(self, method_name, None)
        
        if method and callable(method):
            try:
                # Call the method
                result = await method(**args)
                
                # Return response
                return PluginMessage(
                    type=PluginMessageType.RESPONSE,
                    data=result
                )
            except Exception as e:
                self.logger.error(f"Error calling {method_name}: {e}")
                return PluginMessage(
                    type=PluginMessageType.RESPONSE,
                    data={
                        'content': f"Error: {e}",
                        'success': False
                    }
                )
        else:
            return PluginMessage(
                type=PluginMessageType.RESPONSE,
                data={
                    'content': f"Method {method_name} not found",
                    'success': False
                }
            )
```

### Step 3: Configure in YAML

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "My Custom Broadcast"
      plugin_name: "my_plugin"
      plugin_method: "get_custom_summary"
      plugin_args:
        format: "brief"
        include_details: true
      schedule_type: "cron"
      cron_expression: "0 8 * * *"
      channel: 0
      enabled: true
```

---

## Weather Plugin Example

### Available Methods

The weather service plugin supports these methods:

#### 1. get_forecast_summary

Get weather forecast summary:

```yaml
- name: "Weather Forecast"
  plugin_name: "weather_service"
  plugin_method: "get_forecast_summary"
  plugin_args:
    location: "default"  # or specific location
    format: "brief"      # or "detailed"
    days: 1              # number of days
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  enabled: true
```

#### 2. get_current_conditions

Get current weather conditions:

```yaml
- name: "Current Weather"
  plugin_name: "weather_service"
  plugin_method: "get_current_conditions"
  plugin_args:
    location: "default"
  schedule_type: "interval"
  interval_seconds: 10800  # Every 3 hours
  channel: 0
  enabled: true
```

#### 3. get_alerts

Get weather alerts:

```yaml
- name: "Weather Alerts"
  plugin_name: "weather_service"
  plugin_method: "get_alerts"
  plugin_args:
    location: "default"
    severity: "moderate"  # or "severe", "extreme"
  schedule_type: "interval"
  interval_seconds: 1800  # Every 30 minutes
  channel: 0
  priority: "high"
  enabled: true
```

### Complete Weather Schedule

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning forecast
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_summary"
      plugin_args:
        location: "default"
        format: "brief"
        days: 1
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7 AM
      channel: 0
      priority: "normal"
      enabled: true
    
    # Current conditions every 3 hours
    - name: "Weather Update"
      plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      plugin_args:
        location: "default"
      schedule_type: "interval"
      interval_seconds: 10800  # 3 hours
      channel: 0
      priority: "normal"
      enabled: true
    
    # Alert monitoring every 30 minutes
    - name: "Weather Alerts"
      plugin_name: "weather_service"
      plugin_method: "get_alerts"
      plugin_args:
        location: "default"
      schedule_type: "interval"
      interval_seconds: 1800  # 30 minutes
      channel: 0
      priority: "high"
      enabled: true
```

---

## Best Practices

### Plugin Calls

1. **Implement Error Handling**
   ```python
   try:
       content = await self.generate_content()
       return {'content': content, 'success': True}
   except Exception as e:
       return {'content': f"Error: {e}", 'success': False}
   ```

2. **Keep Content Concise**
   - Aim for < 500 characters
   - Use brief format for frequent updates
   - Detailed format for less frequent updates

3. **Cache Data**
   - Cache expensive operations
   - Reduce API calls
   - Improve performance

4. **Test Methods First**
   - Test manually before scheduling
   - Verify output format
   - Check error handling

5. **Use Appropriate Schedules**
   - Weather: Every 3-6 hours
   - Status: Hourly or daily
   - Alerts: Every 15-30 minutes

### Shell Commands

1. **Use Absolute Paths**
   ```yaml
   command: "/usr/bin/uptime"  # Good
   command: "uptime"            # May fail
   ```

2. **Set Timeouts**
   ```yaml
   timeout: 10  # Prevent hanging
   ```

3. **Limit Output**
   ```yaml
   max_output_length: 200  # Keep broadcasts short
   ```

4. **Test Manually**
   ```bash
   # Test command first
   uptime
   df -h
   /path/to/script.sh
   ```

5. **Use Prefixes**
   ```yaml
   prefix: "📊 Status:"  # Add context
   ```

### General

1. **Start with Long Intervals**
   - Test with hours or days
   - Adjust based on results

2. **Monitor Logs**
   ```bash
   tail -f logs/zephyrgate.log | grep -E "(plugin|command|broadcast)"
   ```

3. **Use Appropriate Priorities**
   - Weather: normal
   - Status: low
   - Alerts: high

4. **Consider Network Traffic**
   - Don't broadcast too frequently
   - Use low priority for frequent updates

5. **Document Custom Methods**
   - Add docstrings
   - Document parameters
   - Provide examples

---

## Troubleshooting

### Plugin Not Found

**Error:** `No response from plugin weather_service`

**Solutions:**
1. Check plugin name is correct
2. Verify plugin is enabled in config
3. Check plugin is loaded: `tail -f logs/zephyrgate.log | grep weather_service`

### Method Not Found

**Error:** `Method get_forecast_summary not found`

**Solutions:**
1. Verify method exists in plugin
2. Check method name spelling
3. Ensure method is async
4. Check method signature matches args

### Command Failed

**Error:** `Command timed out after 30 seconds`

**Solutions:**
1. Increase timeout value
2. Test command manually
3. Check command path
4. Verify command completes quickly

### No Content Returned

**Error:** `Plugin returned no content`

**Solutions:**
1. Check plugin method returns dict with 'content' key
2. Verify method doesn't return None
3. Check for errors in plugin logs
4. Test method manually

### Content Too Long

**Issue:** Broadcast is truncated

**Solutions:**
1. Reduce max_output_length
2. Make plugin method more concise
3. Use brief format
4. Filter unnecessary information

---

## Testing

### Test Plugin Method

```bash
# Enable debug logging
# In config.yaml:
logging:
  services:
    asset: "DEBUG"

# Restart and watch logs
./stop.sh && ./start.sh
tail -f logs/zephyrgate.log | grep -E "(plugin|scheduled)"
```

### Test Shell Command

```bash
# Test command manually
uptime
df -h
/path/to/script.sh

# Check output length
uptime | wc -c

# Test with timeout
timeout 10 your-command
```

### Test Schedule

```yaml
# Use short interval for testing
- name: "Test Broadcast"
  plugin_name: "weather_service"
  plugin_method: "get_current_conditions"
  plugin_args: {}
  schedule_type: "interval"
  interval_seconds: 300  # 5 minutes for testing
  channel: 0
  enabled: true
```

---

## Related Documentation

- [YAML_CONFIGURATION_GUIDE.md](YAML_CONFIGURATION_GUIDE.md) - Complete YAML guide
- [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md) - Auto-responder system
- [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) - Creating plugins
- [auto_response_examples.yaml](../config/auto_response_examples.yaml) - Examples 25-27

---

## Support

For issues:
1. Check this guide
2. Review example configurations
3. Enable debug logging
4. Check logs for errors
5. Test methods/commands manually
