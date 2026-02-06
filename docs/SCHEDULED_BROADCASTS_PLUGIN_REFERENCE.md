# Scheduled Broadcasts - Plugin Method Reference

## Overview

Scheduled broadcasts can call plugin methods and broadcast their results. This allows you to automatically send weather updates, system status, or any other plugin-generated content on a schedule.

## Configuration Format

```yaml
scheduled_broadcasts:
  enabled: true
  broadcasts:
    - name: "Broadcast Name"
      plugin_name: "plugin_service_name"
      plugin_method: "method_name"
      plugin_args:
        arg1: value1
        arg2: value2
      schedule_type: "cron"  # or "interval" or "one_time"
      cron_expression: "0 7 * * *"
      channel: 0
      priority: "normal"
      enabled: true
```

## Available Plugins and Methods

### Weather Service Plugin

**Plugin Name:** `weather_service`

#### Method: `get_forecast_report`
Get weather forecast for multiple days.

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts
- `days` (optional): Number of days to forecast (default: 3, max: 7)

**Example:**
```yaml
- name: "Daily Weather Forecast"
  plugin_name: "weather_service"
  plugin_method: "get_forecast_report"
  plugin_args:
    user_id: "system"
    days: 3
  schedule_type: "cron"
  cron_expression: "0 7 * * *"  # 7:00 AM daily
  channel: 0
  priority: "normal"
  enabled: true
```

**Output Example:**
```
🌤️ 3-Day Forecast for The Villages, FL:

📅 Thu Feb 6
🌡️ High: 72°F / Low: 54°F
💨 Wind: 12 mph SW
☁️ Partly Cloudy

📅 Fri Feb 7
🌡️ High: 75°F / Low: 56°F
💨 Wind: 8 mph S
☀️ Sunny
...
```

---

#### Method: `get_weather_report`
Get current weather conditions with optional detailed information.

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts
- `detailed` (optional): Include detailed information (default: False)

**Example:**
```yaml
- name: "Current Weather"
  plugin_name: "weather_service"
  plugin_method: "get_weather_report"
  plugin_args:
    user_id: "system"
    detailed: false
  schedule_type: "interval"
  interval_seconds: 3600  # Every hour
  channel: 0
  priority: "normal"
  enabled: true
```

**Output Example (brief):**
```
🌤️ Weather for The Villages, FL:
🌡️ 68°F | Feels like 66°F
💨 Wind: 10 mph SW
💧 Humidity: 65%
☁️ Partly Cloudy
```

**Output Example (detailed):**
```
🌤️ Weather for The Villages, FL:
🌡️ Temperature: 68°F (Feels like 66°F)
💨 Wind: 10 mph SW (Gusts: 15 mph)
💧 Humidity: 65%
🌡️ Pressure: 30.12 inHg
👁️ Visibility: 10 mi
☁️ Cloud Cover: 40%
🌅 Sunrise: 7:15 AM | Sunset: 6:30 PM
☁️ Partly Cloudy
```

---

#### Method: `get_current_conditions`
Get brief current weather conditions only.

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts

**Example:**
```yaml
- name: "Quick Weather Check"
  plugin_name: "weather_service"
  plugin_method: "get_current_conditions"
  plugin_args:
    user_id: "system"
  schedule_type: "interval"
  interval_seconds: 1800  # Every 30 minutes
  channel: 0
  priority: "normal"
  enabled: true
```

**Output Example:**
```
🌤️ Current: 68°F, Partly Cloudy
💨 Wind: 10 mph SW | 💧 Humidity: 65%
```

---

#### Method: `get_weather_alerts`
Get active weather alerts for the area.

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts

**Example:**
```yaml
- name: "Weather Alerts Check"
  plugin_name: "weather_service"
  plugin_method: "get_weather_alerts"
  plugin_args:
    user_id: "system"
  schedule_type: "interval"
  interval_seconds: 900  # Every 15 minutes
  channel: 0
  priority: "high"
  enabled: true
```

**Output Example (with alerts):**
```
⚠️ Active Weather Alerts:

🔴 Severe Thunderstorm Warning
Valid until: 8:30 PM EST
Areas: Lake County, Sumter County
Damaging winds and large hail possible.

🟡 Flash Flood Watch
Valid until: 11:00 PM EST
Areas: Central Florida
Heavy rainfall may cause flooding.
```

**Output Example (no alerts):**
```
✅ No active weather alerts for your area.
```

---

#### Method: `get_all_alerts`
Get all types of alerts (weather, earthquake, etc.).

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts

**Example:**
```yaml
- name: "All Alerts Check"
  plugin_name: "weather_service"
  plugin_method: "get_all_alerts"
  plugin_args:
    user_id: "system"
  schedule_type: "interval"
  interval_seconds: 600  # Every 10 minutes
  channel: 0
  priority: "high"
  enabled: true
```

---

#### Method: `get_earthquake_info`
Get recent earthquake information for the area.

**Parameters:**
- `user_id` (required): User ID or "system" for scheduled broadcasts

**Example:**
```yaml
- name: "Earthquake Report"
  plugin_name: "weather_service"
  plugin_method: "get_earthquake_info"
  plugin_args:
    user_id: "system"
  schedule_type: "cron"
  cron_expression: "0 */6 * * *"  # Every 6 hours
  channel: 0
  priority: "normal"
  enabled: true
```

**Output Example:**
```
🌍 2 earthquake(s) in last 24 hours:
• M4.2 - Central California (450km) at 14:23 UTC
• M3.8 - Southern Nevada (520km) at 09:15 UTC
```

---

### BBS Service Plugin

**Plugin Name:** `bbs_service`

#### Method: `get_bulletin_boards`
Get list of available bulletin boards.

**Parameters:** None

**Example:**
```yaml
- name: "BBS Boards List"
  plugin_name: "bbs_service"
  plugin_method: "get_bulletin_boards"
  plugin_args: {}
  schedule_type: "cron"
  cron_expression: "0 8 * * *"  # 8:00 AM daily
  channel: 0
  priority: "normal"
  enabled: true
```

---

### Bot Service Plugin

**Plugin Name:** `bot_service`

#### Method: `get_response_statistics`
Get bot response statistics.

**Parameters:** None

**Example:**
```yaml
- name: "Bot Stats"
  plugin_name: "bot_service"
  plugin_method: "get_response_statistics"
  plugin_args: {}
  schedule_type: "cron"
  cron_expression: "0 0 * * *"  # Midnight daily
  channel: 0
  priority: "low"
  enabled: true
```

---

## Schedule Types

### Cron Expression
Use standard cron syntax for recurring schedules.

**Format:** `minute hour day month day_of_week`

**Examples:**
- `"0 7 * * *"` - Every day at 7:00 AM
- `"*/5 * * * *"` - Every 5 minutes
- `"0 */6 * * *"` - Every 6 hours
- `"0 8 * * 1"` - Every Monday at 8:00 AM
- `"0 0 1 * *"` - First day of every month at midnight

**Tool:** Use https://crontab.guru/ to validate cron expressions

### Interval
Run at fixed intervals in seconds.

**Example:**
```yaml
schedule_type: "interval"
interval_seconds: 3600  # Every hour
```

### One-Time
Run once at a specific time.

**Example:**
```yaml
schedule_type: "one_time"
scheduled_time: "2026-02-06T15:30:00-05:00"  # Include timezone!
```

**Important:** Always include timezone offset (e.g., `-05:00` for EST)

---

## Channel Configuration

- `channel: 0` - Direct messages (default)
- `channel: 1` - Primary channel (LongFast)
- `channel: 2` - Secondary channel
- `channel: 3+` - Additional channels

---

## Priority Levels

- `priority: "low"` - Low priority messages
- `priority: "normal"` - Normal priority (default)
- `priority: "high"` - High priority messages

---

## Complete Example Configuration

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning weather forecast
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      plugin_args:
        user_id: "system"
        days: 3
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7:00 AM daily
      channel: 0
      priority: "normal"
      enabled: true
    
    # Hourly weather updates
    - name: "Hourly Weather"
      plugin_name: "weather_service"
      plugin_method: "get_current_conditions"
      plugin_args:
        user_id: "system"
      schedule_type: "interval"
      interval_seconds: 3600  # Every hour
      channel: 0
      priority: "normal"
      enabled: true
    
    # Weather alerts check (every 15 minutes)
    - name: "Weather Alerts"
      plugin_name: "weather_service"
      plugin_method: "get_weather_alerts"
      plugin_args:
        user_id: "system"
      schedule_type: "interval"
      interval_seconds: 900  # Every 15 minutes
      channel: 0
      priority: "high"
      enabled: true
    
    # Special event announcement
    - name: "Event Reminder"
      plugin_name: "weather_service"
      plugin_method: "get_weather_report"
      plugin_args:
        user_id: "system"
        detailed: false
      schedule_type: "one_time"
      scheduled_time: "2026-02-06T18:00:00-05:00"  # 6:00 PM EST
      channel: 0
      priority: "high"
      enabled: true
```

---

## Troubleshooting

### Plugin method not found
**Error:** `Plugin 'X' does not have method 'Y'`

**Solution:** Check the method name spelling and refer to this document for correct method names.

### Missing required parameter
**Error:** `TypeError: method() missing required positional argument`

**Solution:** Ensure all required parameters are provided in `plugin_args`. Most weather methods require `user_id: "system"`.

### Broadcast not sending
**Check:**
1. Is `enabled: true` set for the broadcast?
2. Is `scheduled_broadcasts.enabled: true` in the config?
3. Check logs for errors or timing information
4. For one-time broadcasts, ensure the time hasn't passed and includes timezone

### Wrong timezone
**Issue:** One-time broadcasts not sending at expected time

**Solution:** Always include timezone offset in ISO format:
- EST: `-05:00`
- CST: `-06:00`
- MST: `-07:00`
- PST: `-08:00`
- UTC: `+00:00` or `Z`

Example: `"2026-02-06T15:30:00-05:00"`

---

## Tips

1. **Test with short intervals first:** Use `*/5 * * * *` (every 5 minutes) to test, then change to your desired schedule
2. **Use appropriate channels:** Weather alerts on high-priority channels, routine updates on normal channels
3. **Monitor logs:** Check `logs/zephyrgate_dev.log` for broadcast execution and errors
4. **Disable when not needed:** Set `enabled: false` to temporarily disable a broadcast without deleting it
5. **Use descriptive names:** Make broadcast names clear so you can identify them in logs
