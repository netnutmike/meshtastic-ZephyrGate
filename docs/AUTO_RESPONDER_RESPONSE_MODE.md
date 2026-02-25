# Auto-Responder Response Mode Feature

## Overview

The `response_mode` parameter gives you explicit control over how auto-responses are sent - as direct messages (DMs) or as channel broadcasts.

## The Problem

Previously, auto-responses used channel-based logic:
- **Channel 0**: Responses sent as DMs to the sender
- **Channel > 0**: Responses broadcast to the entire channel

This caused issues when you wanted auto-responses on Channel 0 to broadcast to everyone, not just the sender.

## The Solution

Add `response_mode` to any auto-response rule to explicitly control the behavior.

## Configuration

### Response Mode Options

| Mode | Behavior |
|------|----------|
| `auto` | Default/legacy behavior: DM on channel 0, broadcast on other channels |
| `dm` | Always send as direct message to the sender |
| `broadcast` | Always broadcast to the channel (everyone sees it) |

### Example Configuration

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        # Text response that broadcasts to channel
        - keywords: ['test', 'testing']
          response: "✅ Test message received!"
          priority: 5
          cooldown_seconds: 30
          max_responses_per_hour: 10
          enabled: true
          response_mode: "broadcast"  # Everyone sees the response
        
        # Plugin calls that broadcast to channel
        - keywords: ['~#01#GC#AWAKE#']
          priority: 5
          cooldown_seconds: 300
          match_type: "contains"
          enabled: true
          response_mode: "broadcast"  # Everyone sees weather/events
          plugin_calls:
            - plugin_name: "weather_service"
              plugin_method: "get_gc_forecast"
              plugin_args:
                user_id: "system"
            
            - plugin_name: "villages_events_service"
              plugin_method: "get_events_report"
              plugin_args:
                format_type: "meshtastic"
                date_range: "today"
        
        # Private response (DM only)
        - keywords: ['private', 'secret']
          response: "This is a private message just for you"
          priority: 50
          enabled: true
          response_mode: "dm"  # Only sender sees the response
```

## Use Cases

### Broadcast Mode (Recommended for Most Cases)

Use `response_mode: "broadcast"` when:
- You want everyone to see the auto-response
- Golf cart startup messages should be visible to all
- Weather/events updates should go to the channel
- Status updates should be public

### DM Mode

Use `response_mode: "dm"` when:
- Responses contain personal information
- You want private conversations with the bot
- Sensitive commands or data

### Auto Mode (Legacy)

Use `response_mode: "auto"` (or omit it) when:
- You want the old behavior
- Channel 0 should be DMs, other channels broadcast
- Backward compatibility with existing configs

## Migration Guide

### Before (Old Behavior)

```yaml
- keywords: ['test']
  response: "Test received"
  enabled: true
  # On channel 0: Sent as DM
  # On channel 3: Broadcast to channel
```

### After (New Behavior)

```yaml
- keywords: ['test']
  response: "Test received"
  enabled: true
  response_mode: "broadcast"  # Always broadcast, regardless of channel
```

## Technical Details

### How It Works

1. **Text Responses**: The `_create_response_message()` method checks `response_mode` and sets the `recipient_id` accordingly:
   - `dm`: Sets `recipient_id` to sender's ID
   - `broadcast`: Sets `recipient_id` to `"^all"`
   - `auto`: Uses channel-based logic (legacy)

2. **Plugin Call Responses**: The `_execute_plugin_calls()` method applies the same logic when sending plugin-generated content.

### Backward Compatibility

- If `response_mode` is not specified, it defaults to `"auto"` (legacy behavior)
- Existing configurations continue to work without changes
- No breaking changes to the API

## Testing

After updating your config:

1. **Test on Channel 0**:
   ```
   Send: "test"
   Expected: Response broadcasts to channel (everyone sees it)
   ```

2. **Test on Channel 3**:
   ```
   Send: "test"
   Expected: Response broadcasts to channel (everyone sees it)
   ```

3. **Test DM Mode**:
   ```
   Add response_mode: "dm" to a rule
   Send trigger keyword
   Expected: Only you receive the response
   ```

## Related Documentation

- [AUTO_RESPONDER_PLUGIN_CALLS.md](AUTO_RESPONDER_PLUGIN_CALLS.md) - Plugin call configuration
- [AUTO_RESPONDER_QUICK_REFERENCE.md](AUTO_RESPONDER_QUICK_REFERENCE.md) - Quick reference guide
- [FEATURES_OVERVIEW.md](FEATURES_OVERVIEW.md) - All features overview

## Support

If you encounter issues:
1. Check that `response_mode` is set to `"broadcast"`, `"dm"`, or `"auto"`
2. Enable debug logging: `logging.services.bot: "DEBUG"`
3. Check logs for response mode in action: `grep "mode:" logs/zephyrgate.log`
4. Restart the service after config changes
