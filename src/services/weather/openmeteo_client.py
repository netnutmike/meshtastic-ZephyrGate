"""
Open-Meteo Weather API Client

Provides weather data fetching from Open-Meteo API for international locations
with comprehensive error handling and caching.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlencode

from .models import (
    WeatherData, WeatherCondition, WeatherForecast,
    Location, WeatherProvider
)


class OpenMeteoAPIError(Exception):
    """Open-Meteo API specific error"""
    pass


class OpenMeteoClient:
    """
    Open-Meteo API client for international weather data
    
    Provides free access to weather data and forecasts worldwide.
    """
    
    def __init__(self, user_agent: str = "ZephyrGate/1.0"):
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # API endpoints
        self.base_url = "https://api.open-meteo.com/v1"
        self.forecast_url = f"{self.base_url}/forecast"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        
        # Session for connection pooling
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting (Open-Meteo is quite generous)
        self.last_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms between requests
        
        # Location cache for geocoding
        self.location_cache: Dict[str, Dict[str, Any]] = {}
    
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
            OpenMeteoAPIError: If request fails
        """
        if not self.session:
            await self.start()
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        try:
            query_string = f"?{urlencode(params, doseq=True)}" if params else ""
            full_url = f"{url}{query_string}"
            
            self.logger.debug(f"Making Open-Meteo API request: {full_url}")
            
            async with self.session.get(url, params=params) as response:
                self.last_request_time = asyncio.get_event_loop().time()
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for API errors in response
                    if 'error' in data and data['error']:
                        raise OpenMeteoAPIError(f"API error: {data.get('reason', 'Unknown error')}")
                    
                    return data
                elif response.status == 400:
                    error_text = await response.text()
                    raise OpenMeteoAPIError(f"Bad request: {error_text}")
                elif response.status == 429:
                    raise OpenMeteoAPIError("Rate limit exceeded")
                else:
                    error_text = await response.text()
                    raise OpenMeteoAPIError(f"HTTP {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise OpenMeteoAPIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise OpenMeteoAPIError(f"Invalid JSON response: {e}")
    
    async def get_weather_data(self, location: Location) -> Optional[WeatherData]:
        """
        Get comprehensive weather data for any location worldwide
        
        Args:
            location: Location to get weather for
            
        Returns:
            Weather data or None if unavailable
        """
        try:
            # Log the location being queried
            self.logger.info(f"Fetching weather data from OpenMeteo for {location.name} at coordinates ({location.latitude}, {location.longitude})")
            
            # Prepare API parameters
            params = {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'current': [
                    'temperature_2m',
                    'relative_humidity_2m',
                    'apparent_temperature',
                    'is_day',
                    'precipitation',
                    'rain',
                    'showers',
                    'snowfall',
                    'weather_code',
                    'cloud_cover',
                    'pressure_msl',
                    'surface_pressure',
                    'wind_speed_10m',
                    'wind_direction_10m',
                    'wind_gusts_10m'
                ],
                'daily': [
                    'weather_code',
                    'temperature_2m_max',
                    'temperature_2m_min',
                    'apparent_temperature_max',
                    'apparent_temperature_min',
                    'sunrise',
                    'sunset',
                    'uv_index_max',
                    'precipitation_sum',
                    'rain_sum',
                    'showers_sum',
                    'snowfall_sum',
                    'precipitation_hours',
                    'precipitation_probability_max',
                    'wind_speed_10m_max',
                    'wind_gusts_10m_max',
                    'wind_direction_10m_dominant'
                ],
                'timezone': 'auto',
                'forecast_days': 7
            }
            
            # Make API request
            data = await self._make_request(self.forecast_url, params)
            
            # Log the raw API response for debugging
            self.logger.info(f"OpenMeteo API response for {location.name}: current temp={data.get('current', {}).get('temperature_2m')}°C, humidity={data.get('current', {}).get('relative_humidity_2m')}%, wind={data.get('current', {}).get('wind_speed_10m')}km/h, weather_code={data.get('current', {}).get('weather_code')}")
            
            # Parse current conditions
            current_data = data.get('current', {})
            current = self._parse_current_conditions(current_data)
            
            if not current:
                return None
            
            # Parse forecast
            daily_data = data.get('daily', {})
            forecasts = self._parse_daily_forecast(daily_data)
            
            # Create weather data
            weather_data = WeatherData(
                location=location,
                current=current,
                forecasts=forecasts,
                provider=WeatherProvider.OPEN_METEO,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Failed to get Open-Meteo weather data: {e}")
            return None
    
    def _parse_current_conditions(self, current_data: Dict[str, Any]) -> Optional[WeatherCondition]:
        """
        Parse current weather conditions from API response
        
        Args:
            current_data: Current weather data from API
            
        Returns:
            Weather condition or None
        """
        try:
            # Extract values with defaults
            temperature = current_data.get('temperature_2m', 0.0)
            humidity = current_data.get('relative_humidity_2m', 0.0)
            pressure = current_data.get('pressure_msl', 1013.25)
            wind_speed = current_data.get('wind_speed_10m', 0.0)
            wind_direction = current_data.get('wind_direction_10m', 0)
            cloud_cover = current_data.get('cloud_cover', 0)
            precipitation = current_data.get('precipitation', 0.0)
            weather_code = current_data.get('weather_code', 0)
            
            # Convert weather code to description
            description = self._weather_code_to_description(weather_code)
            
            condition = WeatherCondition(
                temperature=float(temperature),
                humidity=float(humidity),
                pressure=float(pressure),
                wind_speed=float(wind_speed),
                wind_direction=int(wind_direction or 0),
                cloud_cover=int(cloud_cover or 0),
                precipitation=float(precipitation),
                description=description
            )
            
            return condition
            
        except Exception as e:
            self.logger.warning(f"Failed to parse current conditions: {e}")
            return None
    
    def _parse_daily_forecast(self, daily_data: Dict[str, Any]) -> List[WeatherForecast]:
        """
        Parse daily forecast from API response
        
        Args:
            daily_data: Daily forecast data from API
            
        Returns:
            List of forecast periods
        """
        forecasts = []
        
        try:
            times = daily_data.get('time', [])
            temp_max = daily_data.get('temperature_2m_max', [])
            temp_min = daily_data.get('temperature_2m_min', [])
            weather_codes = daily_data.get('weather_code', [])
            precipitation_prob = daily_data.get('precipitation_probability_max', [])
            precipitation_sum = daily_data.get('precipitation_sum', [])
            wind_speeds = daily_data.get('wind_speed_10m_max', [])
            wind_directions = daily_data.get('wind_direction_10m_dominant', [])
            
            for i, time_str in enumerate(times):
                try:
                    # Parse date
                    forecast_date = datetime.fromisoformat(time_str)
                    
                    # Get values with bounds checking
                    t_max = temp_max[i] if i < len(temp_max) else 20.0
                    t_min = temp_min[i] if i < len(temp_min) else 10.0
                    weather_code = weather_codes[i] if i < len(weather_codes) else 0
                    precip_prob = precipitation_prob[i] if i < len(precipitation_prob) else 0.0
                    precip_sum = precipitation_sum[i] if i < len(precipitation_sum) else 0.0
                    wind_speed = wind_speeds[i] if i < len(wind_speeds) else 0.0
                    wind_dir = wind_directions[i] if i < len(wind_directions) else 0
                    
                    # Convert weather code to description
                    description = self._weather_code_to_description(weather_code)
                    
                    forecast = WeatherForecast(
                        timestamp=forecast_date,
                        temperature_min=float(t_min),
                        temperature_max=float(t_max),
                        humidity=50.0,  # Not provided in daily data
                        precipitation_probability=float(precip_prob or 0.0),
                        precipitation_amount=float(precip_sum or 0.0),
                        wind_speed=float(wind_speed or 0.0),
                        wind_direction=int(wind_dir or 0),
                        description=description
                    )
                    
                    forecasts.append(forecast)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse forecast day {i}: {e}")
                    continue
            
        except Exception as e:
            self.logger.warning(f"Failed to parse daily forecast: {e}")
        
        return forecasts
    
    def _weather_code_to_description(self, code: int) -> str:
        """
        Convert WMO weather code to description
        
        Args:
            code: WMO weather code
            
        Returns:
            Weather description
        """
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        
        return weather_codes.get(code, f"Unknown weather (code {code})")
    
    async def geocode_location(self, query: str, count: int = 1) -> List[Location]:
        """
        Geocode a location name to coordinates
        
        Args:
            query: Location name to search for
            count: Maximum number of results
            
        Returns:
            List of matching locations
        """
        cache_key = f"{query.lower()}_{count}"
        
        # Check cache first
        if cache_key in self.location_cache:
            cached_data = self.location_cache[cache_key]
            return self._parse_geocoding_results(cached_data)
        
        try:
            params = {
                'name': query,
                'count': count,
                'language': 'en',
                'format': 'json'
            }
            
            data = await self._make_request(self.geocoding_url, params)
            
            # Cache the result
            self.location_cache[cache_key] = data
            
            return self._parse_geocoding_results(data)
            
        except OpenMeteoAPIError as e:
            self.logger.warning(f"Failed to geocode location '{query}': {e}")
            return []
    
    def _parse_geocoding_results(self, data: Dict[str, Any]) -> List[Location]:
        """
        Parse geocoding results
        
        Args:
            data: Geocoding API response
            
        Returns:
            List of locations
        """
        locations = []
        results = data.get('results', [])
        
        for result in results:
            try:
                location = Location(
                    latitude=result.get('latitude', 0.0),
                    longitude=result.get('longitude', 0.0),
                    name=result.get('name', ''),
                    country=result.get('country', ''),
                    state=result.get('admin1', ''),  # State/province
                )
                
                locations.append(location)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse geocoding result: {e}")
                continue
        
        return locations
    
    async def get_air_quality(self, location: Location) -> Optional[Dict[str, Any]]:
        """
        Get air quality data for a location
        
        Args:
            location: Location to get air quality for
            
        Returns:
            Air quality data or None
        """
        try:
            air_quality_url = f"{self.base_url}/air-quality"
            
            params = {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'current': [
                    'us_aqi',
                    'pm10',
                    'pm2_5',
                    'carbon_monoxide',
                    'nitrogen_dioxide',
                    'sulphur_dioxide',
                    'ozone'
                ]
            }
            
            data = await self._make_request(air_quality_url, params)
            current = data.get('current', {})
            
            return {
                'aqi': current.get('us_aqi'),
                'pm10': current.get('pm10'),
                'pm2_5': current.get('pm2_5'),
                'co': current.get('carbon_monoxide'),
                'no2': current.get('nitrogen_dioxide'),
                'so2': current.get('sulphur_dioxide'),
                'o3': current.get('ozone'),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to get air quality data: {e}")
            return None
    
    async def get_marine_weather(self, location: Location) -> Optional[Dict[str, Any]]:
        """
        Get marine weather data for coastal locations
        
        Args:
            location: Coastal location
            
        Returns:
            Marine weather data or None
        """
        try:
            marine_url = f"{self.base_url}/marine"
            
            params = {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'current': [
                    'wave_height',
                    'wave_direction',
                    'wave_period',
                    'wind_wave_height',
                    'wind_wave_direction',
                    'wind_wave_period',
                    'swell_wave_height',
                    'swell_wave_direction',
                    'swell_wave_period'
                ]
            }
            
            data = await self._make_request(marine_url, params)
            current = data.get('current', {})
            
            return {
                'wave_height': current.get('wave_height'),
                'wave_direction': current.get('wave_direction'),
                'wave_period': current.get('wave_period'),
                'wind_wave_height': current.get('wind_wave_height'),
                'wind_wave_direction': current.get('wind_wave_direction'),
                'wind_wave_period': current.get('wind_wave_period'),
                'swell_wave_height': current.get('swell_wave_height'),
                'swell_wave_direction': current.get('swell_wave_direction'),
                'swell_wave_period': current.get('swell_wave_period'),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to get marine weather data: {e}")
            return None