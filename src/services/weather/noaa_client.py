"""
NOAA Weather API Client

Provides weather data fetching from NOAA/National Weather Service APIs
for US locations with comprehensive error handling and caching.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlencode

from .models import (
    WeatherData, WeatherCondition, WeatherForecast, WeatherAlert,
    Location, AlertType, AlertSeverity, WeatherProvider
)


class NOAAAPIError(Exception):
    """NOAA API specific error"""
    pass


class NOAAClient:
    """
    NOAA/National Weather Service API client
    
    Provides access to weather data, forecasts, and alerts for US locations.
    """
    
    def __init__(self, api_key: Optional[str] = None, user_agent: str = "ZephyrGate/1.0"):
        self.api_key = api_key
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # API endpoints
        self.base_url = "https://api.weather.gov"
        self.points_url = f"{self.base_url}/points"
        self.alerts_url = f"{self.base_url}/alerts"
        
        # Session for connection pooling
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 1.0  # seconds between requests
        
        # Cache for grid points to avoid repeated lookups
        self.grid_cache: Dict[str, Dict[str, Any]] = {}
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'application/json'
            }
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and error handling
        
        Args:
            url: Request URL
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            NOAAAPIError: If request fails
        """
        if not self.session:
            await self.start()
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        try:
            query_string = f"?{urlencode(params)}" if params else ""
            full_url = f"{url}{query_string}"
            
            self.logger.debug(f"Making NOAA API request: {full_url}")
            
            async with self.session.get(url, params=params) as response:
                self.last_request_time = asyncio.get_event_loop().time()
                
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 404:
                    raise NOAAAPIError(f"Resource not found: {url}")
                elif response.status == 429:
                    raise NOAAAPIError("Rate limit exceeded")
                else:
                    error_text = await response.text()
                    raise NOAAAPIError(f"HTTP {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NOAAAPIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise NOAAAPIError(f"Invalid JSON response: {e}")
    
    async def get_weather_data(self, location: Location) -> Optional[WeatherData]:
        """
        Get comprehensive weather data for a US location
        
        Args:
            location: Location to get weather for
            
        Returns:
            Weather data or None if unavailable
        """
        try:
            # Get grid point information
            grid_info = await self._get_grid_point(location)
            if not grid_info:
                return None
            
            # Get current conditions and forecast
            current_task = self._get_current_conditions(grid_info)
            forecast_task = self._get_forecast(grid_info)
            
            current, forecasts = await asyncio.gather(
                current_task, forecast_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(current, Exception):
                self.logger.warning(f"Failed to get current conditions: {current}")
                current = None
            
            if isinstance(forecasts, Exception):
                self.logger.warning(f"Failed to get forecast: {forecasts}")
                forecasts = []
            
            if not current:
                return None
            
            # Create weather data
            weather_data = WeatherData(
                location=location,
                current=current,
                forecasts=forecasts or [],
                provider=WeatherProvider.NOAA,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Failed to get NOAA weather data: {e}")
            return None
    
    async def _get_grid_point(self, location: Location) -> Optional[Dict[str, Any]]:
        """
        Get NOAA grid point information for a location
        
        Args:
            location: Location to get grid point for
            
        Returns:
            Grid point information or None
        """
        cache_key = f"{location.latitude:.4f},{location.longitude:.4f}"
        
        # Check cache first
        if cache_key in self.grid_cache:
            return self.grid_cache[cache_key]
        
        try:
            url = f"{self.points_url}/{location.latitude:.4f},{location.longitude:.4f}"
            data = await self._make_request(url)
            
            properties = data.get('properties', {})
            grid_info = {
                'gridId': properties.get('gridId'),
                'gridX': properties.get('gridX'),
                'gridY': properties.get('gridY'),
                'forecast': properties.get('forecast'),
                'forecastHourly': properties.get('forecastHourly'),
                'observationStations': properties.get('observationStations')
            }
            
            # Cache the result
            self.grid_cache[cache_key] = grid_info
            
            return grid_info
            
        except NOAAAPIError as e:
            self.logger.warning(f"Failed to get grid point: {e}")
            return None
    
    async def _get_current_conditions(self, grid_info: Dict[str, Any]) -> Optional[WeatherCondition]:
        """
        Get current weather conditions from observation stations
        
        Args:
            grid_info: Grid point information
            
        Returns:
            Current weather conditions or None
        """
        stations_url = grid_info.get('observationStations')
        if not stations_url:
            return None
        
        try:
            # Get list of observation stations
            stations_data = await self._make_request(stations_url)
            stations = stations_data.get('features', [])
            
            if not stations:
                return None
            
            # Try to get observations from the first few stations
            for station in stations[:3]:
                station_id = station.get('properties', {}).get('stationIdentifier')
                if not station_id:
                    continue
                
                try:
                    obs_url = f"{self.base_url}/stations/{station_id}/observations/latest"
                    obs_data = await self._make_request(obs_url)
                    
                    properties = obs_data.get('properties', {})
                    
                    # Extract weather data
                    temp_data = properties.get('temperature', {})
                    humidity_data = properties.get('relativeHumidity', {})
                    pressure_data = properties.get('barometricPressure', {})
                    wind_speed_data = properties.get('windSpeed', {})
                    wind_dir_data = properties.get('windDirection', {})
                    visibility_data = properties.get('visibility', {})
                    
                    # Convert units and create condition
                    temperature = self._convert_temperature(temp_data.get('value'), temp_data.get('unitCode'))
                    humidity = humidity_data.get('value', 0.0) or 0.0
                    pressure = self._convert_pressure(pressure_data.get('value'), pressure_data.get('unitCode'))
                    wind_speed = self._convert_wind_speed(wind_speed_data.get('value'), wind_speed_data.get('unitCode'))
                    wind_direction = wind_dir_data.get('value', 0) or 0
                    visibility = self._convert_distance(visibility_data.get('value'), visibility_data.get('unitCode'))
                    
                    description = properties.get('textDescription', '')
                    
                    condition = WeatherCondition(
                        temperature=temperature,
                        humidity=humidity,
                        pressure=pressure,
                        wind_speed=wind_speed,
                        wind_direction=int(wind_direction),
                        visibility=visibility,
                        description=description
                    )
                    
                    return condition
                    
                except NOAAAPIError:
                    continue  # Try next station
            
            return None
            
        except NOAAAPIError as e:
            self.logger.warning(f"Failed to get current conditions: {e}")
            return None
    
    async def _get_forecast(self, grid_info: Dict[str, Any]) -> List[WeatherForecast]:
        """
        Get weather forecast
        
        Args:
            grid_info: Grid point information
            
        Returns:
            List of forecast periods
        """
        forecast_url = grid_info.get('forecast')
        if not forecast_url:
            return []
        
        try:
            data = await self._make_request(forecast_url)
            periods = data.get('properties', {}).get('periods', [])
            
            forecasts = []
            for period in periods[:7]:  # Limit to 7 days
                try:
                    # Parse period data
                    name = period.get('name', '')
                    temperature = period.get('temperature', 0)
                    temp_unit = period.get('temperatureUnit', 'F')
                    
                    # Convert temperature to Celsius
                    if temp_unit == 'F':
                        temp_celsius = (temperature - 32) * 5/9
                    else:
                        temp_celsius = temperature
                    
                    # Parse start time
                    start_time_str = period.get('startTime', '')
                    try:
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    except:
                        start_time = datetime.utcnow()
                    
                    # Determine if this is a day or night period
                    is_daytime = period.get('isDaytime', True)
                    
                    forecast = WeatherForecast(
                        timestamp=start_time,
                        temperature_min=temp_celsius if not is_daytime else temp_celsius - 5,
                        temperature_max=temp_celsius if is_daytime else temp_celsius + 5,
                        humidity=50.0,  # NOAA doesn't provide humidity in basic forecast
                        precipitation_probability=0.0,  # Would need detailed forecast
                        description=period.get('shortForecast', ''),
                        icon=period.get('icon', '')
                    )
                    
                    forecasts.append(forecast)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse forecast period: {e}")
                    continue
            
            return forecasts
            
        except NOAAAPIError as e:
            self.logger.warning(f"Failed to get forecast: {e}")
            return []
    
    async def get_weather_alerts(self, location: Location, radius_km: float = 50.0) -> List[WeatherAlert]:
        """
        Get weather alerts for a location
        
        Args:
            location: Location to get alerts for
            radius_km: Search radius in kilometers
            
        Returns:
            List of active weather alerts
        """
        try:
            # Convert radius to miles for NOAA API
            radius_miles = radius_km * 0.621371
            
            params = {
                'point': f"{location.latitude},{location.longitude}",
                'status': 'actual',
                'message_type': 'alert'
            }
            
            data = await self._make_request(self.alerts_url, params)
            features = data.get('features', [])
            
            alerts = []
            for feature in features:
                try:
                    properties = feature.get('properties', {})
                    
                    # Parse alert data
                    alert_id = properties.get('id', str(datetime.utcnow().timestamp()))
                    event = properties.get('event', 'Weather Alert')
                    headline = properties.get('headline', '')
                    description = properties.get('description', '')
                    severity = properties.get('severity', 'Moderate').lower()
                    
                    # Parse times
                    onset_str = properties.get('onset', '')
                    expires_str = properties.get('expires', '')
                    
                    try:
                        start_time = datetime.fromisoformat(onset_str.replace('Z', '+00:00')) if onset_str else datetime.utcnow()
                    except:
                        start_time = datetime.utcnow()
                    
                    try:
                        end_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00')) if expires_str else None
                    except:
                        end_time = None
                    
                    # Map severity
                    severity_map = {
                        'minor': AlertSeverity.MINOR,
                        'moderate': AlertSeverity.MODERATE,
                        'severe': AlertSeverity.SEVERE,
                        'extreme': AlertSeverity.EXTREME
                    }
                    alert_severity = severity_map.get(severity, AlertSeverity.MODERATE)
                    
                    # Get affected areas
                    affected_areas = properties.get('areaDesc', '').split(';')
                    affected_areas = [area.strip() for area in affected_areas if area.strip()]
                    
                    # Get FIPS and SAME codes
                    geocode = properties.get('geocode', {})
                    fips_codes = geocode.get('FIPS6', [])
                    same_codes = geocode.get('SAME', [])
                    
                    alert = WeatherAlert(
                        id=alert_id,
                        alert_type=AlertType.WEATHER,
                        severity=alert_severity,
                        title=event,
                        description=headline or description,
                        location=location,
                        affected_areas=affected_areas,
                        start_time=start_time,
                        end_time=end_time,
                        issued_time=datetime.utcnow(),
                        source="NOAA/NWS",
                        fips_codes=fips_codes,
                        same_codes=same_codes,
                        metadata={
                            'urgency': properties.get('urgency'),
                            'certainty': properties.get('certainty'),
                            'category': properties.get('category'),
                            'response': properties.get('response')
                        }
                    )
                    
                    alerts.append(alert)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse alert: {e}")
                    continue
            
            return alerts
            
        except NOAAAPIError as e:
            self.logger.warning(f"Failed to get weather alerts: {e}")
            return []
    
    # Unit conversion utilities
    def _convert_temperature(self, value: Optional[float], unit_code: Optional[str]) -> float:
        """Convert temperature to Celsius"""
        if value is None:
            return 0.0
        
        if unit_code == 'wmoUnit:degF':
            return (value - 32) * 5/9
        elif unit_code == 'wmoUnit:K':
            return value - 273.15
        else:  # Assume Celsius
            return value
    
    def _convert_pressure(self, value: Optional[float], unit_code: Optional[str]) -> float:
        """Convert pressure to hPa"""
        if value is None:
            return 1013.25  # Standard atmospheric pressure
        
        if unit_code == 'wmoUnit:Pa':
            return value / 100.0
        elif unit_code == 'wmoUnit:inHg':
            return value * 33.8639
        else:  # Assume hPa
            return value
    
    def _convert_wind_speed(self, value: Optional[float], unit_code: Optional[str]) -> float:
        """Convert wind speed to km/h"""
        if value is None:
            return 0.0
        
        if unit_code == 'wmoUnit:m_s-1':
            return value * 3.6
        elif unit_code == 'wmoUnit:mi_h-1':
            return value * 1.60934
        elif unit_code == 'wmoUnit:kt':
            return value * 1.852
        else:  # Assume km/h
            return value
    
    def _convert_distance(self, value: Optional[float], unit_code: Optional[str]) -> Optional[float]:
        """Convert distance to kilometers"""
        if value is None:
            return None
        
        if unit_code == 'wmoUnit:m':
            return value / 1000.0
        elif unit_code == 'wmoUnit:mi':
            return value * 1.60934
        elif unit_code == 'wmoUnit:ft':
            return value * 0.0003048
        else:  # Assume km
            return value