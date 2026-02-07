# GC Forecast Guide

## Overview

The `gc_forecast` command provides weather data in a highly configurable, condensed format that is compatible with the `python-weather-grab-summary-meshtastic` project. This format is ideal for bandwidth-constrained applications like Meshtastic messaging systems.

## Command Usage

### Basic Usage

```
gc_forecast
```

Gets a 5-hour forecast for today with default formatting.

**Example Output:**
```
#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#4pm,9,75,0.0#5pm,9,74,0.0#
```

### Specify Hours and Day

```
gc_forecast [hours] [day]
```

- `hours`: Number of forecast hours (default: 5)
- `day`: Either `today` or `tomorrow` (default: today)

**Examples:**
```
gc_forecast 8                # 8 hours, today
gc_forecast 8 tomorrow       # 8 hours, tomorrow
gc_forecast 12 today         # 12 hours, today
```

### Custom Separators

```
gc_forecast --entry-sep "|" --field-sep ":"
```

**Example Output:**
```
|76|1pm:9:75:0.0|2pm:9:76:0.0|3pm:9:76:0.0|
```

### Custom Fields

```
gc_forecast --fields hour,icon,temp,humidity,wind_speed
```

**Available Fields:**
- `hour` - Hour in 12-hour format (e.g., "1pm", "2pm")
- `icon` - Weather condition icon code (0-9, ;, <, ?)
- `temp` - Temperature (integer)
- `feels_like` - Feels-like temperature (integer)
- `precip` - Precipitation amount (mm/hour)
- `precip_probability` - Precipitation probability (0-100%)
- `humidity` - Humidity percentage
- `wind_speed` - Wind speed
- `wind_direction` - Wind direction in degrees
- `pressure` - Atmospheric pressure
- `uv_index` - UV index
- `visibility` - Visibility distance
- `dew_point` - Dew point temperature

**Example Output:**
```
#76#1pm,9,75,65,5.2#2pm,9,76,63,6.1#3pm,9,76,62,7.3#
```

### Add Preamble

```
gc_forecast --preamble "WEATHER:"
```

**Example Output:**
```
WEATHER:#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#
```

### Combined Options

```
gc_forecast 8 tomorrow --preamble "WX:" --entry-sep "|" --fields hour,icon,temp
```

**Example Output:**
```
WX:|76|1pm,9,75|2pm,9,76|3pm,9,76|4pm,9,75|5pm,9,74|6pm,9,73|7pm,9,72|8pm,9,71|
```

## Output Format

The output follows this structure:

```
[preamble][entry_sep][current_temp][entry_sep][forecast_1][entry_sep][forecast_2]...[entry_sep]
```

Each forecast entry contains the configured fields separated by the field separator:

```
[field_1][field_sep][field_2][field_sep]...[field_n]
```

## Weather Icon Codes

The default icon mappings are:

- `0` - Cloudy/overcast
- `1` - Foggy/misty
- `2` - Light shower snow
- `3` - Sleet/mixed precipitation
- `4` - Partly cloudy
- `5` - Thunderstorms
- `6` - Heavy rain
- `7` - Light/moderate rain
- `8` - Snow
- `9` - Sunny/clear
- `;` - Windy
- `<` - Tornado
- `?` - Unknown/default

## Programmatic Usage

The `get_gc_forecast` method can be called directly from other plugins or scheduled broadcasts:

```python
# Get default format
result = await weather_plugin.get_gc_forecast(user_id='system')

# Custom parameters
result = await weather_plugin.get_gc_forecast(
    user_id='user123',
    hours=8,
    day='tomorrow',
    entry_sep='|',
    field_sep=':',
    fields=['hour', 'icon', 'temp', 'humidity'],
    preamble='WEATHER:',
    icon_mappings=custom_mappings  # Optional custom icon mappings
)
```

### Method Parameters

```python
async def get_gc_forecast(
    user_id: str = 'system',
    hours: int = 5,
    day: str = 'today',
    entry_sep: str = '#',
    field_sep: str = ',',
    fields: Optional[List[str]] = None,
    preamble: str = '',
    icon_mappings: Optional[Dict[str, str]] = None
) -> str
```

## Use Cases

### Meshtastic Integration

The compact format is perfect for Meshtastic's 237-byte message limit:

```
gc_forecast 5 --preamble "WX:" --fields hour,icon,temp
```

### Scheduled Broadcasts

Configure in `config.yaml`:

```yaml
scheduled_broadcasts:
  - name: "Morning Weather"
    schedule: "0 7 * * *"  # 7 AM daily
    plugin: "weather_service"
    method: "get_gc_forecast"
    params:
      hours: 8
      day: "today"
      preamble: "MORNING WX:"
      fields: ["hour", "icon", "temp", "precip"]
```

### Status Bar Integration

Use the compact format for status displays:

```
gc_forecast 3 --entry-sep " " --field-sep ":" --fields icon,temp
```

**Output:** `9:76 9:75 9:74`

## Compatibility

This implementation is fully compatible with the `python-weather-grab-summary-meshtastic` project's output format and command-line options. The same icon mappings and field formats are used to ensure consistency across systems.

## Notes

- The forecast uses the user's configured location or the system default location
- Hours are counted from the start of the specified day (today or tomorrow)
- The forecast will continue across midnight if needed
- All temperatures are in Fahrenheit
- Precipitation is in mm/hour
- Wind speed is in mph
