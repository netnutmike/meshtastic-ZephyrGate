# Auto-Responder Plugin Calls - Quick Reference

## Basic Format

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
          plugin_calls:
            - plugin_name: "plugin_name"
              plugin_method: "method_name"
              plugin_args:
                arg1: value1
              preamble: "Prefix:"
              channel: 0
              priority: "normal"
```

## Quick Examples

### Golf Cart Startup
```yaml
- keywords: ['test', 'testing']
  cooldown_seconds: 300
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      plugin_args: {days: 1}
      preamble: "🌤️"
    - plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args: {date_range: "today"}
      preamble: "📅"
```

### Single Plugin
```yaml
- keywords: ['weather']
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
```

### Text + Plugin
```yaml
- keywords: ['status']
  response: "Getting status..."
  plugin_calls:
    - plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
```

## Plugin Call Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `plugin_name` | Yes | - | Plugin to call |
| `plugin_method` | No | "generate_content" | Method to call |
| `plugin_args` | No | {} | Method arguments |
| `preamble` | No | "" | Text prefix |
| `channel` | No | 0 | Target channel |
| `priority` | No | "normal" | Message priority |

## Available Plugins

### Weather Service
```yaml
- plugin_name: "weather_service"
  plugin_method: "get_forecast_report"
  plugin_args:
    days: 3
```

Methods: `get_forecast_report`, `get_current_conditions`, `get_gc_forecast`, `get_alerts`

### Villages Events
```yaml
- plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    date_range: "today"
    format_type: "meshtastic"
```

Methods: `get_events_report`

### BBS Service
```yaml
- plugin_name: "bbs_service"
  plugin_method: "get_recent_bulletins"
  plugin_args:
    count: 5
```

Methods: `get_bulletin_count`, `get_recent_bulletins`, `get_unread_summary`

## Rate Limiting

```yaml
cooldown_seconds: 300      # 5 minutes between responses
max_responses_per_hour: 5  # Max 5 per hour per user
```

**Recommended Values:**
- Startup messages: 300s cooldown, 5/hour
- Frequent updates: 120s cooldown, 10/hour
- Rare updates: 600s cooldown, 3/hour

## Channel Targeting

```yaml
channel: 0  # Direct message to requester
channel: 1  # LongFast channel
channel: 2  # MediumSlow channel
channel: 3  # Custom channel
```

## Priority Levels

```yaml
priority: "low"     # Low priority
priority: "normal"  # Normal priority (default)
priority: "high"    # High priority
```

## Debugging

### Enable Debug Logging
```yaml
logging:
  services:
    bot: "DEBUG"
```

### Watch Logs
```bash
tail -f logs/zephyrgate.log | grep -E "(plugin_call|auto_response)"
```

## Common Patterns

### Multiple Plugins in Sequence
```yaml
plugin_calls:
  - plugin_name: "weather_service"
    plugin_method: "get_current_conditions"
  - plugin_name: "villages_events_service"
    plugin_method: "get_events_report"
  - plugin_name: "bbs_service"
    plugin_method: "get_unread_summary"
```

### Different Channels
```yaml
plugin_calls:
  - plugin_name: "weather_service"
    plugin_method: "get_forecast_report"
    channel: 2  # Broadcast to channel 2
  - plugin_name: "bbs_service"
    plugin_method: "get_unread_summary"
    channel: 0  # DM to requester
```

### With Preambles
```yaml
plugin_calls:
  - plugin_name: "weather_service"
    plugin_method: "get_forecast_report"
    preamble: "🌤️ Weather:"
  - plugin_name: "villages_events_service"
    plugin_method: "get_events_report"
    preamble: "📅 Events:"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No response | Check rate limits, verify plugin enabled |
| Plugin not found | Check plugin name spelling, verify loaded |
| Method not found | Check method name, verify plugin supports it |
| Empty response | Check plugin args, enable debug logging |
| Rate limited | Increase cooldown or max_responses |

## Testing Checklist

- [ ] YAML syntax valid
- [ ] Plugin names correct
- [ ] Method names correct
- [ ] Plugin args valid
- [ ] Rate limits appropriate
- [ ] Debug logging enabled
- [ ] Test message sent
- [ ] Response received
- [ ] Logs checked

## See Also

- [AUTO_RESPONDER_PLUGIN_CALLS.md](AUTO_RESPONDER_PLUGIN_CALLS.md) - Complete guide
- [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md) - Auto-responder basics
- [SCHEDULED_PLUGIN_CALLS_GUIDE.md](SCHEDULED_PLUGIN_CALLS_GUIDE.md) - Scheduled calls
- `examples/auto_response_examples.yaml` - More examples
