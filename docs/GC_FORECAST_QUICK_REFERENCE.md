# GC Forecast Quick Reference

## Command Syntax

```
gc_forecast [hours] [day] [options]
```

## Quick Examples

| Command | Output |
|---------|--------|
| `gc_forecast` | `#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#4pm,9,75,0.0#5pm,9,74,0.0#` |
| `gc_forecast 8` | 8-hour forecast for today |
| `gc_forecast 8 tomorrow` | 8-hour forecast for tomorrow |
| `gc_forecast --preamble "WX:"` | `WX:#76#1pm,9,75,0.0#2pm,9,76,0.0#...` |
| `gc_forecast --entry-sep "\|"` | `\|76\|1pm,9,75,0.0\|2pm,9,76,0.0\|...` |
| `gc_forecast --field-sep ":"` | `#76#1pm:9:75:0.0#2pm:9:76:0.0#...` |
| `gc_forecast --fields hour,icon,temp` | `#76#1pm,9,75#2pm,9,76#3pm,9,76#...` |

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `hours` | Number of forecast hours | 5 |
| `day` | `today` or `tomorrow` | today |
| `--entry-sep` | Entry separator | # |
| `--field-sep` | Field separator | , |
| `--fields` | Comma-separated field list | hour,icon,temp,precip |
| `--preamble` | Prefix string | (empty) |

## Available Fields

| Field | Description | Example |
|-------|-------------|---------|
| `hour` | 12-hour format | 1pm, 2pm |
| `icon` | Weather icon code | 9, 7, 5 |
| `temp` | Temperature (°F) | 75, 76 |
| `feels_like` | Feels-like temp (°F) | 73, 74 |
| `precip` | Precipitation (mm/h) | 0.0, 2.5 |
| `precip_probability` | Precip chance (%) | 10.0, 85.0 |
| `humidity` | Humidity (%) | 65, 70 |
| `wind_speed` | Wind speed (mph) | 5.2, 10.5 |
| `wind_direction` | Wind direction (°) | 180, 270 |
| `pressure` | Pressure (hPa) | 1013, 1015 |
| `uv_index` | UV index | 3.5, 7.2 |
| `visibility` | Visibility (m) | 10000 |
| `dew_point` | Dew point (°F) | 55, 60 |

## Icon Codes

| Code | Condition |
|------|-----------|
| 9 | ☀️ Sunny/Clear |
| 4 | ⛅ Partly Cloudy |
| 0 | ☁️ Cloudy/Overcast |
| 7 | 🌧️ Light/Moderate Rain |
| 6 | 🌧️ Heavy Rain |
| 5 | ⛈️ Thunderstorms |
| 8 | ❄️ Snow |
| 3 | 🌨️ Sleet/Mixed |
| 2 | 🌨️ Light Snow Showers |
| 1 | 🌫️ Fog/Mist |
| ; | 💨 Windy |
| < | 🌪️ Tornado |
| ? | ❓ Unknown |

## Output Format

```
[preamble][sep][current][sep][hour1][sep][hour2][sep]...[sep]
```

Where each hour entry is:
```
[field1][fsep][field2][fsep]...[fsep][fieldN]
```

## Scheduled Broadcast Example

```yaml
scheduled_broadcasts:
  broadcasts:
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_gc_forecast"
      plugin_args:
        hours: 8
        day: "today"
        preamble: "WX:"
        fields: ["hour", "icon", "temp", "precip"]
      schedule_type: "cron"
      cron_expression: "0 6 * * *"  # 6 AM daily
      channel: 0
      enabled: true
```

## Programmatic Usage

```python
# Basic
result = await weather_plugin.get_gc_forecast()

# Advanced
result = await weather_plugin.get_gc_forecast(
    user_id='user123',
    hours=8,
    day='tomorrow',
    entry_sep='|',
    field_sep=':',
    fields=['hour', 'icon', 'temp', 'humidity'],
    preamble='WEATHER:'
)
```

## Common Use Cases

### Meshtastic (237-byte limit)
```
gc_forecast 5 --preamble "WX:" --fields hour,icon,temp
```
Output: `WX:#76#1pm,9,75#2pm,9,76#3pm,9,76#4pm,9,75#5pm,9,74#` (52 bytes)

### Status Bar
```
gc_forecast 3 --entry-sep " " --field-sep ":" --fields icon,temp
```
Output: `9:76 9:75 9:74` (14 bytes)

### Detailed Forecast
```
gc_forecast 8 --fields hour,icon,temp,precip,humidity,wind_speed
```
Output: `#76#1pm,9,75,0.0,65,5.2#2pm,9,76,0.0,63,6.1#...`

### Tomorrow's Weather
```
gc_forecast 12 tomorrow --preamble "TOMORROW:"
```
Output: `TOMORROW:#76#1am,9,72,0.0#2am,9,71,0.0#...`

## Tips

1. **Keep it short for Meshtastic**: Use 3-5 fields max
2. **Use preamble for context**: Helps identify the message type
3. **Custom separators**: Use `|` or `:` for better readability
4. **Field selection**: Only include fields you need
5. **Tomorrow forecasts**: Great for planning next day activities

## See Also

- Full documentation: `docs/GC_FORECAST_GUIDE.md`
- Integration details: `GC_FORECAST_INTEGRATION.md`
- Weather service docs: `docs/FEATURES_OVERVIEW.md`
