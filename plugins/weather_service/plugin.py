"""
Weather Service Plugin

Wraps the Weather service as a plugin for the ZephyrGate plugin system.
This allows the weather service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import from src modules
from core.enhanced_plugin import EnhancedPlugin
from models.message import Message

# Import from local weather modules
from .weather.weather_service import WeatherService


class WeatherServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Weather Service.
    
    Provides:
    - Current weather conditions
    - Weather forecasts
    - Weather alerts
    - Location-based weather
    - Proximity monitoring
    """
    
    async def initialize(self) -> bool:
        """Initialize the weather service plugin"""
        self.logger.info("Initializing Weather Service Plugin")
        
        try:
            # The config passed to the plugin is already the weather-specific config
            # from services.weather (main.py handles the config path resolution)
            weather_config = self.config
            
            self.logger.info(f"Weather service config keys: {list(weather_config.keys())}")
            self.logger.info(f"Default location config: {weather_config.get('default_location')}")
            
            # Create the weather service instance with proper arguments
            self.weather_service = WeatherService(
                name=self.name,
                config=weather_config,
                plugin_manager=self.plugin_manager
            )
            
            # Initialize the weather service (sets up clients, geocoding, location)
            init_success = await self.weather_service.initialize()
            if not init_success:
                self.logger.error("Failed to initialize weather service")
                return False
            
            # Start the weather service (starts background tasks)
            start_success = await self.weather_service.start()
            if not start_success:
                self.logger.error("Failed to start weather service")
                return False
            
            # Register weather commands
            await self._register_weather_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            self.logger.info("Weather Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize weather service: {e}", exc_info=True)
            return False
    
    async def _register_weather_commands(self):
        """Register weather commands with the plugin system"""
        # Current weather command
        self.register_command(
            "wx",
            self._handle_wx_command,
            "Get current weather conditions",
            priority=50
        )
        
        # Detailed weather command
        self.register_command(
            "weather",
            self._handle_weather_command,
            "Get detailed weather information",
            priority=50
        )
        
        # Forecast command
        self.register_command(
            "forecast",
            self._handle_forecast_command,
            "Get weather forecast",
            priority=50
        )
        
        # Alerts command
        self.register_command(
            "alerts",
            self._handle_alerts_command,
            "Get active weather alerts",
            priority=50
        )
        
        # GC Forecast command (compact format)
        self.register_command(
            "gc_forecast",
            self._handle_gc_forecast_command,
            "Get compact weather forecast (GC format)",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for weather service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is a weather-related message
            content = message.content.lower().strip()
            
            # Let weather commands be handled by command handlers
            if content.startswith(('wx', 'weather', 'forecast', 'alerts')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in weather service: {e}", exc_info=True)
            return False
    
    async def _handle_wx_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle wx (current weather) command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported by get_weather_report
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, detailed=False)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in wx command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_weather_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle weather (detailed) command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported by get_weather_report
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get detailed weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, detailed=True)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in weather command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_forecast_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle forecast command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Parse days from args
            days = 3
            
            if args:
                if args[0].isdigit():
                    days = int(args[0])
                    # Note: Additional location args are currently not supported
                    # TODO: Add support for custom location parameter
            
            # Get forecast report
            if hasattr(self.weather_service, 'get_forecast_report'):
                return await self.weather_service.get_forecast_report(sender_id, days)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in forecast command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_alerts_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle alerts command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get weather alerts
            if hasattr(self.weather_service, 'get_weather_alerts'):
                return await self.weather_service.get_weather_alerts(sender_id)
            else:
                return "Weather alerts not available"
            
        except Exception as e:
            self.logger.error(f"Error in alerts command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_gc_forecast_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle gc_forecast (compact format) command
        
        Usage: gc_forecast [hours] [day] [--entry-sep SEP] [--field-sep SEP] [--fields FIELDS] [--preamble TEXT] [--units UNITS]
        
        Examples:
            gc_forecast                          # Default: 5 hours, today, imperial
            gc_forecast 8                        # 8 hours, today, imperial
            gc_forecast 8 tomorrow               # 8 hours, tomorrow, imperial
            gc_forecast 5 today --preamble WX:   # With preamble
            gc_forecast --fields hour,icon,temp  # Custom fields
            gc_forecast --units metric           # Use metric units (°C, km/h)
        """
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Parse arguments
            hours = 5
            day = 'today'
            entry_sep = '#'
            field_sep = ','
            fields = None
            preamble = ''
            units = 'imperial'
            
            i = 0
            while i < len(args):
                arg = args[i]
                
                # Check for numeric hours
                if arg.isdigit() and i == 0:
                    hours = int(arg)
                    i += 1
                    continue
                
                # Check for day
                if arg.lower() in ['today', 'tomorrow'] and i <= 1:
                    day = arg.lower()
                    i += 1
                    continue
                
                # Check for flags
                if arg == '--entry-sep' and i + 1 < len(args):
                    entry_sep = args[i + 1]
                    i += 2
                    continue
                
                if arg == '--field-sep' and i + 1 < len(args):
                    field_sep = args[i + 1]
                    i += 2
                    continue
                
                if arg == '--fields' and i + 1 < len(args):
                    fields = [f.strip() for f in args[i + 1].split(',')]
                    i += 2
                    continue
                
                if arg == '--preamble' and i + 1 < len(args):
                    preamble = args[i + 1]
                    i += 2
                    continue
                
                if arg == '--units' and i + 1 < len(args):
                    units = args[i + 1].lower()
                    if units not in ['imperial', 'metric']:
                        return f"Error: Invalid units '{units}'. Use 'imperial' or 'metric'."
                    i += 2
                    continue
                
                # Unknown argument
                i += 1
            
            # Get GC forecast
            return await self.get_gc_forecast(
                user_id=sender_id,
                hours=hours,
                day=day,
                entry_sep=entry_sep,
                field_sep=field_sep,
                fields=fields,
                preamble=preamble,
                units=units
            )
            
        except Exception as e:
            self.logger.error(f"Error in gc_forecast command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up weather service resources"""
        self.logger.info("Cleaning up Weather Service Plugin")
        
        try:
            if hasattr(self, 'weather_service') and self.weather_service:
                await self.weather_service.stop()
            
            self.logger.info("Weather Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up weather service: {e}", exc_info=True)
    
    async def get_forecast_report(self, user_id: str = 'system', days: int = 3) -> str:
        """
        Get a weather forecast report (exposed for scheduled broadcasts)
        
        Args:
            user_id: User ID for location lookup
            days: Number of days to forecast
            
        Returns:
            Formatted forecast report string
        """
        if hasattr(self, 'weather_service') and self.weather_service:
            return await self.weather_service.get_forecast_report(user_id, days)
        else:
            return "Weather service not available"
    
    async def get_weather_report(self, user_id: str = 'system', detailed: bool = False) -> str:
        """
        Get a current weather report (exposed for scheduled broadcasts)
        
        Args:
            user_id: User ID for location lookup
            detailed: Whether to include detailed information
            
        Returns:
            Formatted weather report string
        """
        if hasattr(self, 'weather_service') and self.weather_service:
            return await self.weather_service.get_weather_report(user_id, detailed)
        else:
            return "Weather service not available"
    
    async def get_weather_alerts(self, user_id: str = 'system') -> str:
        """
        Get weather alerts (exposed for scheduled broadcasts)
        
        Args:
            user_id: User ID for location lookup
            
        Returns:
            Formatted alerts string
        """
        if hasattr(self, 'weather_service') and self.weather_service:
            return await self.weather_service.get_weather_alerts(user_id)
        else:
            return "Weather alerts not available"
    
    async def get_forecast_report(self, user_id: str = 'system', days: int = 3) -> str:
        """
        Get forecast report - exposed for scheduled broadcasts and plugin calls
        
        Args:
            user_id: User ID for location lookup (defaults to 'system')
            days: Number of days to forecast (defaults to 3)
        
        Returns:
            Formatted forecast report string
        """
        try:
            if hasattr(self, 'weather_service') and self.weather_service:
                return await self.weather_service.get_forecast_report(user_id, days)
            else:
                return "Weather service not available"
        except Exception as e:
            self.logger.error(f"Error getting forecast report: {e}", exc_info=True)
            return f"Error getting forecast: {str(e)}"
    
    async def get_weather_report(self, user_id: str = 'system', detailed: bool = False) -> str:
        """
        Get current weather report - exposed for scheduled broadcasts and plugin calls
        
        Args:
            user_id: User ID for location lookup (defaults to 'system')
            detailed: Whether to include detailed information
        
        Returns:
            Formatted weather report string
        """
        try:
            if hasattr(self, 'weather_service') and self.weather_service:
                return await self.weather_service.get_weather_report(user_id, detailed)
            else:
                return "Weather service not available"
        except Exception as e:
            self.logger.error(f"Error getting weather report: {e}", exc_info=True)
            return f"Error getting weather: {str(e)}"
    
    async def get_weather_alerts(self, user_id: str = 'system') -> str:
        """
        Get weather alerts - exposed for scheduled broadcasts and plugin calls
        
        Args:
            user_id: User ID for location lookup (defaults to 'system')
        
        Returns:
            Formatted weather alerts string
        """
        try:
            if hasattr(self, 'weather_service') and self.weather_service:
                return await self.weather_service.get_weather_alerts(user_id)
            else:
                return "Weather service not available"
        except Exception as e:
            self.logger.error(f"Error getting weather alerts: {e}", exc_info=True)
            return f"Error getting alerts: {str(e)}"
    
    async def get_gc_forecast(
        self,
        user_id: str = 'system',
        hours: int = 5,
        day: str = 'today',
        entry_sep: str = '#',
        field_sep: str = ',',
        fields: Optional[List[str]] = None,
        preamble: str = '',
        icon_mappings: Optional[Dict[str, str]] = None,
        units: str = 'imperial'
    ) -> str:
        """
        Get weather forecast in GC (compact) format - compatible with python-weather-grab-summary-meshtastic
        
        This method provides weather data in a highly configurable, condensed format
        suitable for Meshtastic and other bandwidth-constrained applications.
        
        Args:
            user_id: User ID for location lookup (defaults to 'system')
            hours: Number of forecast hours to retrieve (default: 5)
            day: Forecast day - 'today' or 'tomorrow' (default: 'today')
            entry_sep: Entry separator character(s) (default: '#')
            field_sep: Field separator character(s) (default: ',')
            fields: List of fields to output (default: ['hour', 'icon', 'temp', 'precip'])
                   Available fields: hour, icon, temp, feels_like, precip, precip_probability,
                   humidity, wind_speed, wind_direction, pressure, uv_index, visibility, dew_point
            preamble: Optional prefix string for output (default: '')
            icon_mappings: Custom weather condition to icon code mappings (default: standard mappings)
            units: Unit system - 'imperial' (°F, mph) or 'metric' (°C, km/h) (default: 'imperial')
        
        Returns:
            Formatted weather string in GC format
            Example: "#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#"
            With preamble: "WEATHER:#76#1pm,9,75,0.0#2pm,9,76,0.0#"
        
        Format:
            [preamble][entry_sep][current_temp][entry_sep][forecast_1][entry_sep]...[entry_sep]
            Each forecast entry: [field_1][field_sep][field_2][field_sep]...[field_n]
        """
        try:
            if not hasattr(self, 'weather_service') or not self.weather_service:
                return "Weather service not available"
            
            # Set default fields if not provided
            if fields is None:
                fields = ['hour', 'icon', 'temp', 'precip']
            
            # Set default icon mappings if not provided
            if icon_mappings is None:
                icon_mappings = self._get_default_icon_mappings()
            
            # Get user location
            location = await self._get_user_location(user_id)
            if not location:
                return "Error: Location not configured"
            
            # Get current weather and forecast from weather service
            try:
                # Create a Location object
                from .weather.models import Location
                loc = Location(
                    latitude=location['latitude'],
                    longitude=location['longitude'],
                    name=location.get('name', 'Location')
                )
                
                # Get weather data (includes current and forecast)
                weather_data = await self.weather_service.get_weather_data(loc)
                if not weather_data:
                    return "Error: Unable to fetch weather data"
                
                # Get current temperature
                if weather_data.current:
                    current_temp = weather_data.current.temperature
                    # Convert to imperial if needed (weather service returns Celsius)
                    if units.lower() == 'imperial':
                        current_temp = self._celsius_to_fahrenheit(current_temp)
                    current_temp = int(current_temp)
                else:
                    return "Error: No current weather data available"
                
                # Get hourly forecast from daily forecasts
                # Since we don't have hourly data, we'll use daily forecasts
                # and create hourly-like entries
                forecast_data = self._convert_daily_to_hourly(
                    weather_data.forecasts,
                    hours,
                    day,
                    units
                )
                
                if not forecast_data:
                    return "Error: Unable to fetch forecast"
                
            except Exception as e:
                self.logger.error(f"Error fetching weather data: {e}", exc_info=True)
                return f"Error fetching weather: {str(e)}"
            
            # Format output
            output_parts = []
            
            # Add preamble or initial separator
            if preamble:
                output_parts.append(preamble)
            
            # Add entry separator before current temp
            output_parts.append(entry_sep)
            
            # Add current temperature
            output_parts.append(str(current_temp))
            output_parts.append(entry_sep)
            
            # Add each forecast entry
            for weather in forecast_data:
                entry = self._format_gc_entry(weather, fields, field_sep, icon_mappings)
                output_parts.append(entry)
                output_parts.append(entry_sep)
            
            return "".join(output_parts)
            
        except Exception as e:
            self.logger.error(f"Error getting GC forecast: {e}", exc_info=True)
            return f"Error getting GC forecast: {str(e)}"
    
    async def _get_user_location(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user location from weather service"""
        try:
            # Try to get user-specific location first
            if hasattr(self.weather_service, 'location_service') and self.weather_service.location_service:
                try:
                    user_location = await self.weather_service.location_service.get_user_location(user_id)
                    if user_location:
                        self.logger.debug(f"Using user location for {user_id}: {user_location.name}")
                        return {
                            'latitude': user_location.latitude,
                            'longitude': user_location.longitude,
                            'name': user_location.name
                        }
                except Exception as e:
                    self.logger.debug(f"Could not get user location: {e}")
            
            # Fall back to default location
            if hasattr(self.weather_service, 'default_location') and self.weather_service.default_location:
                default_loc = self.weather_service.default_location
                self.logger.debug(f"Using default location: {default_loc.name} ({default_loc.latitude}, {default_loc.longitude})")
                return {
                    'latitude': default_loc.latitude,
                    'longitude': default_loc.longitude,
                    'name': default_loc.name
                }
            
            # Check if default_location_config exists but wasn't parsed yet
            if hasattr(self.weather_service, 'default_location_config') and self.weather_service.default_location_config:
                self.logger.warning("Default location config exists but location not initialized")
                # Try to parse it now
                if hasattr(self.weather_service, 'geocoding_service') and self.weather_service.geocoding_service:
                    try:
                        location = await self.weather_service.geocoding_service.parse_location_config(
                            self.weather_service.default_location_config
                        )
                        if location:
                            self.weather_service.default_location = location
                            self.logger.info(f"Initialized default location: {location.name}")
                            return {
                                'latitude': location.latitude,
                                'longitude': location.longitude,
                                'name': location.name
                            }
                    except Exception as e:
                        self.logger.error(f"Failed to parse default location config: {e}")
            
            self.logger.error("No location available: no user location, no default location, and no location config")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting user location: {e}", exc_info=True)
            return None
    
    def _format_gc_entry(
        self,
        weather: Any,
        fields: List[str],
        field_sep: str,
        icon_mappings: Dict[str, str]
    ) -> str:
        """Format a single forecast entry in GC format"""
        field_values = []
        
        for field in fields:
            value = self._get_gc_field_value(weather, field, icon_mappings)
            if value is not None:
                field_values.append(value)
        
        return field_sep.join(field_values)
    
    def _get_gc_field_value(
        self,
        weather: Any,
        field: str,
        icon_mappings: Dict[str, str]
    ) -> Optional[str]:
        """Extract field value from weather data for GC format"""
        try:
            if field == "hour":
                # Convert timestamp to 12-hour format
                if hasattr(weather, 'timestamp'):
                    dt = weather.timestamp
                elif hasattr(weather, 'dt'):
                    dt = datetime.fromtimestamp(weather.dt)
                else:
                    return None
                return dt.strftime("%-I%p").lower()
            
            elif field == "icon":
                # Map weather condition to icon code
                condition = getattr(weather, 'condition', '').lower().strip()
                return icon_mappings.get(condition, icon_mappings.get('default', '?'))
            
            elif field == "temp":
                temp = getattr(weather, 'temp', None)
                return str(int(temp)) if temp is not None else None
            
            elif field == "feels_like":
                feels_like = getattr(weather, 'feels_like', None)
                return str(int(feels_like)) if feels_like is not None else None
            
            elif field == "precip":
                precip = getattr(weather, 'precip', 0.0)
                return f"{precip:.1f}"
            
            elif field == "precip_probability":
                precip_prob = getattr(weather, 'precip_probability', None)
                return f"{precip_prob:.1f}" if precip_prob is not None else "N/A"
            
            elif field == "humidity":
                humidity = getattr(weather, 'humidity', None)
                return str(humidity) if humidity is not None else None
            
            elif field == "wind_speed":
                wind_speed = getattr(weather, 'wind_speed', None)
                return f"{wind_speed:.1f}" if wind_speed is not None else None
            
            elif field == "wind_direction":
                wind_dir = getattr(weather, 'wind_direction', None)
                return str(wind_dir) if wind_dir is not None else None
            
            elif field == "pressure":
                pressure = getattr(weather, 'pressure', None)
                return str(pressure) if pressure is not None else None
            
            elif field == "uv_index":
                uv = getattr(weather, 'uv_index', None)
                return f"{uv:.1f}" if uv is not None else "N/A"
            
            elif field == "visibility":
                visibility = getattr(weather, 'visibility', None)
                return str(visibility) if visibility is not None else "N/A"
            
            elif field == "dew_point":
                dew_point = getattr(weather, 'dew_point', None)
                return str(int(dew_point)) if dew_point is not None else "N/A"
            
            else:
                # Try to get custom field from raw data
                if hasattr(weather, 'raw_data'):
                    try:
                        value = weather.raw_data
                        for key in field.split('.'):
                            value = value[key]
                        return str(value)
                    except (KeyError, TypeError):
                        return None
                return None
        
        except Exception as e:
            self.logger.error(f"Error getting field {field}: {e}")
            return None
    
    def _get_default_icon_mappings(self) -> Dict[str, str]:
        """Get default icon mappings for GC format (compatible with python-weather-grab-summary-meshtastic)"""
        return {
            # Clear conditions
            "clear sky": "9",
            "clear": "9",
            "sunny": "9",
            "mainly clear": "9",
            
            # Cloudy conditions
            "few clouds": "4",
            "scattered clouds": "4",
            "partly cloudy": "4",
            "broken clouds": "0",
            "overcast clouds": "0",
            "overcast": "0",
            "cloudy": "0",
            
            # Rain conditions
            "light rain": "7",
            "light intensity rain": "7",
            "drizzle": "7",
            "light drizzle": "7",
            "light intensity drizzle": "7",
            "moderate drizzle": "7",
            "moderate rain": "7",
            "slight rain": "7",
            "heavy intensity rain": "6",
            "heavy rain": "6",
            "very heavy rain": "6",
            "extreme rain": "6",
            "rain": "7",
            
            # Partially sunny with rain
            "light intensity shower rain": "7",
            "shower rain": "7",
            "light rain showers": "7",
            "moderate rain showers": "7",
            "slight rain showers": "7",
            
            # Thunderstorm conditions
            "thunderstorm": "5",
            "thunderstorm with light rain": "5",
            "thunderstorm with rain": "5",
            "thunderstorm with heavy rain": "5",
            "light thunderstorm": "5",
            "heavy thunderstorm": "5",
            "ragged thunderstorm": "5",
            "thunderstorm with slight hail": "5",
            "thunderstorm with heavy hail": "5",
            
            # Snow conditions
            "snow": "8",
            "light snow": "8",
            "heavy snow": "8",
            "slight snow fall": "8",
            "moderate snow fall": "8",
            "heavy snow fall": "8",
            "snow grains": "8",
            "sleet": "3",
            "light shower sleet": "3",
            "shower sleet": "3",
            "light rain and snow": "3",
            "rain and snow": "3",
            "light shower snow": "2",
            "shower snow": "2",
            "heavy shower snow": "8",
            "slight snow showers": "2",
            "heavy snow showers": "8",
            
            # Fog/Mist conditions
            "mist": "1",
            "fog": "1",
            "haze": "1",
            "smoke": "1",
            "dust": "1",
            "sand": "1",
            "depositing rime fog": "1",
            
            # Windy conditions
            "windy": ";",
            "squalls": ";",
            "tornado": "<",
            "violent rain showers": "<",
            
            # Default for unknown conditions
            "default": "?"
        }
    
    def _convert_daily_to_hourly(self, daily_forecasts: List[Any], hours: int, day: str, units: str = 'imperial') -> List[Any]:
        """Convert daily forecasts to hourly-like entries for GC format
        
        Since the weather service provides daily forecasts, we'll create
        hourly entries by interpolating the daily data across the day.
        
        Args:
            daily_forecasts: List of daily forecast objects
            hours: Number of hours to generate
            day: 'today' or 'tomorrow'
            units: 'imperial' or 'metric' for temperature/wind conversion
        """
        from datetime import datetime, timedelta
        
        hourly_data = []
        
        if not daily_forecasts:
            return hourly_data
        
        # Determine which day to use
        now = datetime.now()
        if day.lower() == 'tomorrow':
            target_date = (now + timedelta(days=1)).date()
        else:
            target_date = now.date()
        
        # Find the forecast for the target date
        target_forecast = None
        for forecast in daily_forecasts:
            if forecast.timestamp.date() == target_date:
                target_forecast = forecast
                break
        
        if not target_forecast:
            # Use the first available forecast
            target_forecast = daily_forecasts[0]
        
        # Create hourly entries by interpolating the daily forecast
        # Start from current hour or beginning of day
        if day.lower() == 'today':
            start_hour = now.hour
        else:
            start_hour = 0
        
        for i in range(hours):
            hour_offset = start_hour + i
            if hour_offset >= 24:
                # Move to next day if needed
                hour_offset = hour_offset % 24
                # Try to get next day's forecast
                next_date = target_date + timedelta(days=1)
                next_forecast = None
                for forecast in daily_forecasts:
                    if forecast.timestamp.date() == next_date:
                        next_forecast = forecast
                        break
                if next_forecast:
                    target_forecast = next_forecast
            
            # Create a pseudo-hourly entry
            hour_time = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour_offset)
            
            # Interpolate temperature between min and max
            # Assume min temp at 6am, max temp at 3pm
            hour_of_day = hour_offset
            temp_min = target_forecast.temperature_min
            temp_max = target_forecast.temperature_max
            
            # Convert to imperial if needed (weather service returns Celsius)
            if units.lower() == 'imperial':
                temp_min = self._celsius_to_fahrenheit(temp_min)
                temp_max = self._celsius_to_fahrenheit(temp_max)
            
            if hour_of_day < 6:
                temp = temp_min
            elif hour_of_day < 15:
                # Warming up
                progress = (hour_of_day - 6) / 9.0
                temp = temp_min + (temp_max - temp_min) * progress
            elif hour_of_day < 21:
                # Cooling down
                progress = (hour_of_day - 15) / 6.0
                temp = temp_max - (temp_max - temp_min) * progress * 0.5
            else:
                # Night
                temp = temp_min + (temp_max - temp_min) * 0.2
            
            # Convert wind speed if needed (weather service returns km/h)
            wind_speed = target_forecast.wind_speed
            if units.lower() == 'imperial':
                wind_speed = self._kmh_to_mph(wind_speed)
            
            # Create hourly entry object
            class HourlyEntry:
                def __init__(self, timestamp, temp, forecast, wind_speed):
                    self.timestamp = timestamp
                    self.temp = temp
                    self.feels_like = temp - 2  # Rough estimate
                    self.condition = forecast.description.lower()
                    self.precip = forecast.precipitation_amount / 24.0  # Distribute daily precip
                    self.precip_probability = forecast.precipitation_probability
                    self.humidity = forecast.humidity
                    self.wind_speed = wind_speed
                    self.wind_direction = forecast.wind_direction
                    self.pressure = 1013  # Standard pressure
                    self.uv_index = None
                    self.visibility = None
                    self.dew_point = None
                    self.raw_data = {}
            
            entry = HourlyEntry(hour_time, temp, target_forecast, wind_speed)
            hourly_data.append(entry)
        
        return hourly_data
    
    def _celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return (celsius * 9/5) + 32
    
    def _kmh_to_mph(self, kmh: float) -> float:
        """Convert km/h to mph"""
        return kmh * 0.621371
    
    def get_status(self) -> Dict[str, Any]:
        """Get weather service status"""
        status = {
            'service': 'weather',
            'running': hasattr(self, 'weather_service') and self.weather_service is not None,
            'features': {
                'current_conditions': True,
                'forecasts': True,
                'alerts': True,
                'location_based': True
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="weather_service",
            version="1.0.0",
            description="Weather service with current conditions, forecasts, and alerts",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
