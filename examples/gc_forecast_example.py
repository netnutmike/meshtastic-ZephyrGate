#!/usr/bin/env python3
"""
GC Forecast Example

This example demonstrates how to use the get_gc_forecast method
from the weather service plugin programmatically.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


async def example_basic_forecast():
    """Example: Basic forecast with default settings"""
    print("=" * 60)
    print("Example 1: Basic Forecast (5 hours, today)")
    print("=" * 60)
    
    # In a real application, you would get the plugin instance from the plugin manager
    # For this example, we'll show the expected output format
    
    print("\nCommand: gc_forecast")
    print("\nExpected Output:")
    print("#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#4pm,9,75,0.0#5pm,9,74,0.0#")
    print("\nFormat: [sep][current_temp][sep][hour,icon,temp,precip][sep]...")
    print()


async def example_custom_hours():
    """Example: Custom number of hours"""
    print("=" * 60)
    print("Example 2: 8-Hour Forecast for Tomorrow")
    print("=" * 60)
    
    print("\nCommand: gc_forecast 8 tomorrow")
    print("\nExpected Output:")
    print("#76#1am,9,72,0.0#2am,9,71,0.0#3am,9,70,0.0#4am,9,69,0.0#5am,9,68,0.0#6am,9,67,0.0#7am,9,68,0.0#8am,9,70,0.0#")
    print()


async def example_with_preamble():
    """Example: Forecast with preamble"""
    print("=" * 60)
    print("Example 3: Forecast with Preamble")
    print("=" * 60)
    
    print("\nCommand: gc_forecast --preamble 'WX:'")
    print("\nExpected Output:")
    print("WX:#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#4pm,9,75,0.0#5pm,9,74,0.0#")
    print("\nNote: Preamble replaces the initial separator")
    print()


async def example_custom_separators():
    """Example: Custom separators"""
    print("=" * 60)
    print("Example 4: Custom Separators")
    print("=" * 60)
    
    print("\nCommand: gc_forecast --entry-sep '|' --field-sep ':'")
    print("\nExpected Output:")
    print("|76|1pm:9:75:0.0|2pm:9:76:0.0|3pm:9:76:0.0|4pm:9:75:0.0|5pm:9:74:0.0|")
    print("\nNote: Pipe separates entries, colon separates fields")
    print()


async def example_custom_fields():
    """Example: Custom fields"""
    print("=" * 60)
    print("Example 5: Custom Fields")
    print("=" * 60)
    
    print("\nCommand: gc_forecast --fields hour,icon,temp,humidity,wind_speed")
    print("\nExpected Output:")
    print("#76#1pm,9,75,65,5.2#2pm,9,76,63,6.1#3pm,9,76,62,7.3#4pm,9,75,64,6.8#5pm,9,74,66,5.9#")
    print("\nFields: hour, icon, temp, humidity, wind_speed")
    print()


async def example_meshtastic_format():
    """Example: Optimized for Meshtastic (237-byte limit)"""
    print("=" * 60)
    print("Example 6: Meshtastic-Optimized Format")
    print("=" * 60)
    
    print("\nCommand: gc_forecast 5 --preamble 'WX:' --fields hour,icon,temp")
    print("\nExpected Output:")
    print("WX:#76#1pm,9,75#2pm,9,76#3pm,9,76#4pm,9,75#5pm,9,74#")
    print("\nSize: ~52 bytes (well under 237-byte Meshtastic limit)")
    print()


async def example_status_bar_format():
    """Example: Minimal format for status bars"""
    print("=" * 60)
    print("Example 7: Status Bar Format")
    print("=" * 60)
    
    print("\nCommand: gc_forecast 3 --entry-sep ' ' --field-sep ':' --fields icon,temp")
    print("\nExpected Output:")
    print("9:76 9:75 9:74")
    print("\nSize: ~14 bytes (ultra-compact)")
    print()


async def example_programmatic_usage():
    """Example: Programmatic usage from Python"""
    print("=" * 60)
    print("Example 8: Programmatic Usage")
    print("=" * 60)
    
    print("\nPython Code:")
    print("""
# Get plugin instance from plugin manager
weather_plugin = plugin_manager.get_plugin('weather_service')

# Basic usage
result = await weather_plugin.get_gc_forecast()

# Advanced usage with custom parameters
result = await weather_plugin.get_gc_forecast(
    user_id='user123',
    hours=8,
    day='tomorrow',
    entry_sep='|',
    field_sep=':',
    fields=['hour', 'icon', 'temp', 'humidity'],
    preamble='WEATHER:'
)

print(result)
""")
    print()


async def example_scheduled_broadcast():
    """Example: Scheduled broadcast configuration"""
    print("=" * 60)
    print("Example 9: Scheduled Broadcast Configuration")
    print("=" * 60)
    
    print("\nAdd to config.yaml:")
    print("""
scheduled_broadcasts:
  broadcasts:
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_gc_forecast"
      plugin_args:
        user_id: "system"
        hours: 8
        day: "today"
        preamble: "MORNING WX:"
        fields: ["hour", "icon", "temp", "precip"]
      schedule_type: "cron"
      cron_expression: "0 6 * * *"  # 6 AM daily
      channel: 0
      priority: "normal"
      enabled: true
""")
    print()


async def show_icon_reference():
    """Show icon code reference"""
    print("=" * 60)
    print("Icon Code Reference")
    print("=" * 60)
    
    icons = {
        '9': '☀️  Sunny/Clear',
        '4': '⛅ Partly Cloudy',
        '0': '☁️  Cloudy/Overcast',
        '7': '🌧️  Light/Moderate Rain',
        '6': '🌧️  Heavy Rain',
        '5': '⛈️  Thunderstorms',
        '8': '❄️  Snow',
        '3': '🌨️  Sleet/Mixed',
        '2': '🌨️  Light Snow Showers',
        '1': '🌫️  Fog/Mist',
        ';': '💨 Windy',
        '<': '🌪️  Tornado',
        '?': '❓ Unknown'
    }
    
    print("\nIcon Codes:")
    for code, description in icons.items():
        print(f"  {code} = {description}")
    print()


async def show_field_reference():
    """Show available fields reference"""
    print("=" * 60)
    print("Available Fields Reference")
    print("=" * 60)
    
    fields = {
        'hour': 'Hour in 12-hour format (e.g., 1pm, 2pm)',
        'icon': 'Weather condition icon code (0-9, ;, <, ?)',
        'temp': 'Temperature in Fahrenheit (integer)',
        'feels_like': 'Feels-like temperature (integer)',
        'precip': 'Precipitation amount in mm/hour (float)',
        'precip_probability': 'Precipitation probability 0-100% (float)',
        'humidity': 'Humidity percentage (integer)',
        'wind_speed': 'Wind speed in mph (float)',
        'wind_direction': 'Wind direction in degrees (integer)',
        'pressure': 'Atmospheric pressure in hPa (integer)',
        'uv_index': 'UV index (float)',
        'visibility': 'Visibility distance in meters (integer)',
        'dew_point': 'Dew point temperature (integer)'
    }
    
    print("\nAvailable Fields:")
    for field, description in fields.items():
        print(f"  {field:20} - {description}")
    print()


async def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "GC FORECAST EXAMPLES" + " " * 28 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Run all examples
    await example_basic_forecast()
    await example_custom_hours()
    await example_with_preamble()
    await example_custom_separators()
    await example_custom_fields()
    await example_meshtastic_format()
    await example_status_bar_format()
    await example_programmatic_usage()
    await example_scheduled_broadcast()
    await show_icon_reference()
    await show_field_reference()
    
    print("=" * 60)
    print("For more information, see:")
    print("  - docs/GC_FORECAST_GUIDE.md")
    print("  - docs/GC_FORECAST_QUICK_REFERENCE.md")
    print("  - GC_FORECAST_INTEGRATION.md")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
