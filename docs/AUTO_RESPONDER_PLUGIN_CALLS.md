# Auto-Responder Plugin Calls Guide

## Overview

The auto-responder system can now trigger plugin calls in addition to sending text responses. This allows you to automatically execute plugin methods when specific keywords are detected in incoming messages.

**Perfect for:**
- Golf cart computers that send startup messages
- Automated status requests
- Dynamic content delivery based on keywords
- Multi-step automated responses

---

## Quick Example

When your golf cart computer sends "test" or "testing" on startup, automatically send weather and events:

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        - keywords: ['test', 'testing']
          priority: 5
          cooldown_seconds: 300  # 5 minutes
          enabled: true
          plugin_calls:
            # Send weather forecast
            - plugin_name: "weather_service"
              plugin_method: "get_forecast_report"
              plugin_args:
                user_id: "system"
                days: 1
              preamble: "🌤️ Weather:"
              channel: 0
              priority: "normal"
            
            # Send today's events
            - plugin_name: "villages_events_service"
              plugin_method: "get_events_report"
              plugin_args:
                format_type: "meshtastic"
                date_range: "today"
              preamble: "📅 Events:"
              channel: 0
              priority: "normal"
```

---

## Configuration Format

### Basic Structure

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        - keywords: ['keyword1', 'keyword2']
          priority: 50
          cooldown_seconds: 60
          max_responses_per_hour: 10
          enabled: true
          
          # Optional: Text response (sent before plugin calls)
          response: "Processing your request..."
          
          # Plugin calls to execute
          plugin_calls:
            - plugin_name: "plugin_name"
              plugin_method: "method_name"
              plugin_args:
                arg1: value1
                arg2: value2
              preamble: "Optional prefix:"
              channel: 0
              priority: "normal"
```

### Plugin Call Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `plugin_name` | string | Yes | Name of the plugin to call |
| `plugin_method` | string | No | Method to call (default: "generate_content") |
| `plugin_args` | dict | No | Arguments to pass to the method |
| `preamble` | string | No | Text to prepend to plugin output |
| `channel` | integer | No | Channel to send on (default: same as trigger) |
| `priority` | string | No | Message priority: "low", "normal", "high" |

---

## Multiple Plugin Calls

You can trigger multiple plugins in sequence. They execute in the order listed:

```yaml
- keywords: ['startup', 'wake']
  plugin_calls:
    # First: Weather
    - plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      preamble: "🌤️"
    
    # Second: Events
    - plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        date_range: "today"
      preamble: "📅"
    
    # Third: BBS summary
    - plugin_name: "bbs_service"
      plugin_method: "get_unread_summary"
      preamble: "📬"
```

---

## Text Response + Plugin Calls

You can combine a text response with plugin calls:

```yaml
- keywords: ['status', 'sitrep']
  response: "📊 Gathering status information..."
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
    - plugin_name: "bbs_service"
      plugin_method: "get_bulletin_count"
```

The text response is sent immediately, then plugin calls execute.

---

## Common Use Cases

### 1. Golf Cart Startup

Send weather and events when cart wakes up:

```yaml
- keywords: ['test', 'testing', 'startup']
  priority: 5
  cooldown_seconds: 300  # Don't spam if cart restarts
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      plugin_args:
        days: 1
      preamble: "🌤️ Today:"
    
    - plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        date_range: "today"
      preamble: "📅 Events:"
```

### 2. Morning Briefing

Comprehensive morning update on keyword:

```yaml
- keywords: ['morning', 'briefing', 'update']
  cooldown_seconds: 3600  # Once per hour max
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      plugin_args:
        days: 3
    
    - plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        date_range: "today"
    
    - plugin_name: "bbs_service"
      plugin_method: "get_recent_bulletins"
      plugin_args:
        count: 5
```

### 3. Location-Based Info

Send info when someone asks about a location:

```yaml
- keywords: ['brownwood', 'spanish springs', 'lake sumter']
  plugin_calls:
    - plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        date_range: "today"
        location: "{{keyword}}"  # Use matched keyword
```

### 4. Emergency + Weather

For emergency situations, send weather conditions:

```yaml
- keywords: ['emergency', 'help']
  emergency: true
  response: "🚨 Emergency detected! Sending weather conditions..."
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      priority: "high"
```

---

## Rate Limiting

Plugin calls respect the same rate limiting as text responses:

```yaml
- keywords: ['weather']
  cooldown_seconds: 120  # 2 minutes between responses
  max_responses_per_hour: 5  # Max 5 per hour per user
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
```

This prevents spam if someone repeatedly sends the keyword.

---

## Channel Targeting

Send plugin responses to specific channels:

```yaml
- keywords: ['broadcast-weather']
  plugin_calls:
    # Send to channel 2 (public)
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      channel: 2
      priority: "normal"
```

Or send to the requester (channel 0 = DM):

```yaml
- keywords: ['my-weather']
  plugin_calls:
    # Send directly to requester
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      channel: 0  # Direct message
```

---

## Available Plugins

### Weather Service

**Methods:**
- `get_forecast_report` - Multi-day forecast
- `get_current_conditions` - Current weather
- `get_gc_forecast` - Compact golf cart format
- `get_alerts` - Weather alerts

**Example:**
```yaml
plugin_calls:
  - plugin_name: "weather_service"
    plugin_method: "get_forecast_report"
    plugin_args:
      user_id: "system"
      days: 3
```

### Villages Events Service

**Methods:**
- `get_events_report` - Events listing

**Example:**
```yaml
plugin_calls:
  - plugin_name: "villages_events_service"
    plugin_method: "get_events_report"
    plugin_args:
      format_type: "meshtastic"
      date_range: "today"
      category: "entertainment"
```

### BBS Service

**Methods:**
- `get_bulletin_count` - Count of bulletins
- `get_recent_bulletins` - Recent bulletin list
- `get_unread_summary` - Unread message summary

**Example:**
```yaml
plugin_calls:
  - plugin_name: "bbs_service"
    plugin_method: "get_recent_bulletins"
    plugin_args:
      count: 5
```

---

## Debugging

### Enable Debug Logging

```yaml
logging:
  services:
    bot: "DEBUG"
```

### Check Logs

```bash
tail -f logs/zephyrgate.log | grep -E "(plugin_call|auto_response)"
```

### Test Manually

Send a test message with your keyword and watch the logs to see:
1. Keyword match detection
2. Rate limit checks
3. Plugin call execution
4. Response sending

---

## Best Practices

### 1. Use Appropriate Cooldowns

```yaml
# Frequent updates (weather)
cooldown_seconds: 120  # 2 minutes

# Infrequent updates (events)
cooldown_seconds: 300  # 5 minutes

# Rare updates (startup)
cooldown_seconds: 600  # 10 minutes
```

### 2. Set Rate Limits

```yaml
# Prevent abuse
max_responses_per_hour: 5  # Conservative
max_responses_per_hour: 10  # Moderate
max_responses_per_hour: 20  # Permissive
```

### 3. Use Preambles

Add context to plugin output:

```yaml
preamble: "🌤️ Weather:"  # Clear what the data is
preamble: "📅 Events:"    # Helps users understand
preamble: "📬 Messages:"  # Especially on small screens
```

### 4. Priority Matters

Lower priority numbers execute first:

```yaml
# High priority (executes first)
- keywords: ['emergency']
  priority: 1
  
# Normal priority
- keywords: ['weather']
  priority: 50
  
# Low priority (executes last)
- keywords: ['info']
  priority: 100
```

### 5. Test Before Deploying

Test with short intervals first:

```yaml
# Testing
cooldown_seconds: 10
max_responses_per_hour: 100

# Production
cooldown_seconds: 300
max_responses_per_hour: 5
```

---

## Troubleshooting

### Plugin Not Found

**Error:** `Cannot execute plugin calls: plugin not found`

**Solutions:**
1. Check plugin name spelling
2. Verify plugin is enabled in config
3. Check logs: `grep "plugin_name" logs/zephyrgate.log`

### Method Not Found

**Error:** `Plugin call failed: method not found`

**Solutions:**
1. Verify method name spelling
2. Check plugin documentation for available methods
3. Ensure method accepts the arguments you're passing

### No Response

**Possible causes:**
1. Rate limiting triggered (check cooldown/max_responses)
2. Plugin returned empty content
3. Plugin method failed (check logs)
4. Keyword didn't match (check match_type)

### Rate Limited

If responses aren't sending:
1. Check `cooldown_seconds` - may be too long
2. Check `max_responses_per_hour` - may be too low
3. Wait for cooldown period to expire
4. Check logs for rate limit messages

---

## Related Documentation

- [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md) - Complete auto-responder guide
- [SCHEDULED_PLUGIN_CALLS_GUIDE.md](SCHEDULED_PLUGIN_CALLS_GUIDE.md) - Scheduled plugin calls
- [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) - Creating custom plugins
- [YAML_CONFIGURATION_GUIDE.md](YAML_CONFIGURATION_GUIDE.md) - YAML configuration

---

## Support

For issues:
1. Check this guide
2. Enable debug logging
3. Check logs for errors
4. Test with simple configuration first
5. Verify plugins are loaded and working

