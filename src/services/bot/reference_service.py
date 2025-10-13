"""
Reference Data Service

Provides reference information commands:
- Solar conditions and space weather
- HF band conditions
- Earthquake data
- Sunrise/sunset times
- Moon phases
- Tide information

Requirements: 4.2.4, 4.2.5, 4.2.6
"""

import asyncio
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import aiohttp


@dataclass
class SolarData:
    """Solar conditions data"""
    solar_flux: Optional[float] = None
    sunspot_number: Optional[int] = None
    a_index: Optional[int] = None
    k_index: Optional[int] = None
    x_ray_class: Optional[str] = None
    geomagnetic_field: Optional[str] = None
    updated: Optional[datetime] = None


@dataclass
class EarthquakeData:
    """Earthquake data"""
    magnitude: float
    location: str
    depth: float
    time: datetime
    latitude: float
    longitude: float
    url: Optional[str] = None


@dataclass
class LocationData:
    """Location information"""
    latitude: float
    longitude: float
    timezone_offset: float = 0.0
    elevation: float = 0.0


class ReferenceService:
    """
    Reference data service for space weather, earthquakes, and astronomical data
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Cache for reference data
        self.solar_data_cache: Optional[SolarData] = None
        self.earthquake_cache: List[EarthquakeData] = []
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # Configuration
        self.cache_duration_minutes = self.config.get('cache_duration_minutes', 30)
        self.earthquake_min_magnitude = self.config.get('earthquake_min_magnitude', 4.0)
        self.earthquake_max_results = self.config.get('earthquake_max_results', 10)
        
        # API endpoints
        self.solar_api_url = "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json"
        self.earthquake_api_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson"
        
        # Default location (can be overridden by user location)
        self.default_location = LocationData(
            latitude=self.config.get('default_latitude', 40.7128),  # NYC
            longitude=self.config.get('default_longitude', -74.0060),
            timezone_offset=self.config.get('default_timezone_offset', -5.0)
        )
    
    async def handle_solar_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle solar conditions command"""
        try:
            solar_data = await self._get_solar_data()
            
            if not solar_data:
                return "❌ Unable to retrieve solar data at this time"
            
            response = "☀️ **Solar Conditions**\n\n"
            
            if solar_data.solar_flux:
                response += f"📡 Solar Flux: {solar_data.solar_flux:.1f} sfu\n"
                # Interpret solar flux
                if solar_data.solar_flux > 200:
                    response += "   📈 Very High - Excellent HF conditions\n"
                elif solar_data.solar_flux > 150:
                    response += "   📈 High - Good HF conditions\n"
                elif solar_data.solar_flux > 100:
                    response += "   📊 Moderate - Fair HF conditions\n"
                else:
                    response += "   📉 Low - Poor HF conditions\n"
            
            if solar_data.sunspot_number is not None:
                response += f"🌑 Sunspot Number: {solar_data.sunspot_number}\n"
            
            if solar_data.a_index is not None:
                response += f"🌍 A-Index: {solar_data.a_index}\n"
                # Interpret A-index
                if solar_data.a_index >= 50:
                    response += "   ⚠️ Severe geomagnetic storm\n"
                elif solar_data.a_index >= 30:
                    response += "   🟡 Strong geomagnetic storm\n"
                elif solar_data.a_index >= 15:
                    response += "   🟠 Minor geomagnetic storm\n"
                else:
                    response += "   🟢 Quiet geomagnetic conditions\n"
            
            if solar_data.k_index is not None:
                response += f"📊 K-Index: {solar_data.k_index}\n"
            
            if solar_data.geomagnetic_field:
                response += f"🧭 Geomagnetic Field: {solar_data.geomagnetic_field}\n"
            
            if solar_data.updated:
                response += f"\n🕐 Updated: {solar_data.updated.strftime('%Y-%m-%d %H:%M UTC')}"
            
            response += f"\n\n💡 Send `hfcond` for HF band conditions"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting solar data: {e}")
            return "❌ Error retrieving solar conditions"
    
    async def handle_hfcond_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle HF band conditions command"""
        try:
            solar_data = await self._get_solar_data()
            
            response = "📻 **HF Band Conditions**\n\n"
            
            if solar_data and solar_data.solar_flux:
                flux = solar_data.solar_flux
                
                # Calculate band conditions based on solar flux and time of day
                current_hour = datetime.utcnow().hour
                is_daytime = 6 <= current_hour <= 18  # Rough daytime estimate
                
                bands = {
                    "80m": self._calculate_band_condition(flux, 80, is_daytime),
                    "40m": self._calculate_band_condition(flux, 40, is_daytime),
                    "20m": self._calculate_band_condition(flux, 20, is_daytime),
                    "17m": self._calculate_band_condition(flux, 17, is_daytime),
                    "15m": self._calculate_band_condition(flux, 15, is_daytime),
                    "12m": self._calculate_band_condition(flux, 12, is_daytime),
                    "10m": self._calculate_band_condition(flux, 10, is_daytime)
                }
                
                for band, condition in bands.items():
                    emoji = self._get_condition_emoji(condition)
                    response += f"{emoji} {band}: {condition}\n"
                
                response += f"\n📡 Solar Flux: {flux:.1f} sfu\n"
                response += f"🕐 Time: {'Day' if is_daytime else 'Night'} (UTC)\n"
                
            else:
                response += "❌ Solar data unavailable\n"
                response += "📻 General HF conditions:\n"
                response += "🟡 80m: Fair (night)\n"
                response += "🟡 40m: Fair\n"
                response += "🟢 20m: Good\n"
                response += "🟡 17m: Fair\n"
                response += "🟡 15m: Fair\n"
                response += "🟡 12m: Fair\n"
                response += "🔴 10m: Poor\n"
            
            response += f"\n💡 Conditions vary by location and time"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting HF conditions: {e}")
            return "❌ Error retrieving HF band conditions"
    
    async def handle_earthquake_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle earthquake data command"""
        try:
            earthquakes = await self._get_earthquake_data()
            
            if not earthquakes:
                return "🌍 No significant earthquakes in the past 24 hours"
            
            response = "🌍 **Recent Significant Earthquakes**\n\n"
            
            for i, eq in enumerate(earthquakes[:self.earthquake_max_results], 1):
                response += f"**{i}. M{eq.magnitude:.1f}** - {eq.location}\n"
                response += f"   📅 {eq.time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                response += f"   📍 Depth: {eq.depth:.1f} km\n"
                if eq.url:
                    response += f"   🔗 Details: {eq.url}\n"
                response += "\n"
            
            response += f"💡 Showing earthquakes M{self.earthquake_min_magnitude}+ from past 24 hours"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting earthquake data: {e}")
            return "❌ Error retrieving earthquake information"
    
    async def handle_sun_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle sunrise/sunset command"""
        try:
            # Use user location if available, otherwise default
            location = await self._get_user_location(context.get('sender_id', ''))
            
            # Calculate sunrise/sunset
            today = datetime.now(timezone.utc).date()
            sunrise, sunset = self._calculate_sun_times(location, today)
            
            response = "🌅 **Sun Information**\n\n"
            response += f"📍 Location: {location.latitude:.2f}°, {location.longitude:.2f}°\n"
            response += f"🌅 Sunrise: {sunrise.strftime('%H:%M UTC')}\n"
            response += f"🌇 Sunset: {sunset.strftime('%H:%M UTC')}\n"
            
            # Calculate daylight duration
            daylight_duration = sunset - sunrise
            hours = int(daylight_duration.total_seconds() // 3600)
            minutes = int((daylight_duration.total_seconds() % 3600) // 60)
            response += f"☀️ Daylight: {hours}h {minutes}m\n"
            
            # Current sun status
            now = datetime.now(timezone.utc)
            if sunrise <= now <= sunset:
                response += f"🌞 Current: Daytime\n"
            else:
                response += f"🌙 Current: Nighttime\n"
            
            response += f"\n📅 Date: {today.strftime('%Y-%m-%d')}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error calculating sun times: {e}")
            return "❌ Error calculating sunrise/sunset times"
    
    async def handle_moon_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle moon phase command"""
        try:
            today = datetime.now(timezone.utc)
            
            # Calculate moon phase
            phase_info = self._calculate_moon_phase(today)
            
            response = "🌙 **Moon Information**\n\n"
            response += f"🌙 Phase: {phase_info['name']} {phase_info['emoji']}\n"
            response += f"💡 Illumination: {phase_info['illumination']:.1f}%\n"
            response += f"📅 Date: {today.strftime('%Y-%m-%d')}\n"
            
            # Next major phase
            next_phase = self._get_next_moon_phase(today)
            if next_phase:
                response += f"\n🔮 Next: {next_phase['name']} on {next_phase['date'].strftime('%Y-%m-%d')}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error calculating moon phase: {e}")
            return "❌ Error calculating moon phase"
    
    async def handle_tide_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle tide information command"""
        # Note: This is a simplified implementation
        # A full implementation would require access to tide prediction APIs
        
        response = "🌊 **Tide Information**\n\n"
        response += "ℹ️ Tide predictions require location-specific data\n"
        response += "and access to NOAA tide prediction services.\n\n"
        response += "📍 For accurate tide information:\n"
        response += "• Visit: https://tidesandcurrents.noaa.gov/\n"
        response += "• Use local marine weather services\n"
        response += "• Check local harbor/marina information\n\n"
        response += "💡 This feature will be enhanced with API integration"
        
        return response
    
    async def _get_solar_data(self) -> Optional[SolarData]:
        """Get solar conditions data with caching"""
        cache_key = 'solar_data'
        
        # Check cache
        if (cache_key in self.cache_timestamps and 
            self.solar_data_cache and
            (datetime.now() - self.cache_timestamps[cache_key]).total_seconds() < (self.cache_duration_minutes * 60)):
            return self.solar_data_cache
        
        try:
            # Fetch fresh data
            async with aiohttp.ClientSession() as session:
                async with session.get(self.solar_api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Parse the most recent data
                        if data and len(data) > 0:
                            latest = data[-1]  # Most recent entry
                            
                            solar_data = SolarData(
                                solar_flux=latest.get('observed_ssn'),  # Simplified mapping
                                sunspot_number=latest.get('observed_ssn'),
                                updated=datetime.now()
                            )
                            
                            # Cache the data
                            self.solar_data_cache = solar_data
                            self.cache_timestamps[cache_key] = datetime.now()
                            
                            return solar_data
            
            # If API fails, return cached data or None
            return self.solar_data_cache
            
        except Exception as e:
            self.logger.error(f"Error fetching solar data: {e}")
            # Return cached data if available
            return self.solar_data_cache
    
    async def _get_earthquake_data(self) -> List[EarthquakeData]:
        """Get earthquake data with caching"""
        cache_key = 'earthquake_data'
        
        # Check cache
        if (cache_key in self.cache_timestamps and 
            self.earthquake_cache and
            (datetime.now() - self.cache_timestamps[cache_key]).total_seconds() < (self.cache_duration_minutes * 60)):
            return self.earthquake_cache
        
        try:
            # Fetch fresh data
            async with aiohttp.ClientSession() as session:
                async with session.get(self.earthquake_api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        earthquakes = []
                        for feature in data.get('features', []):
                            props = feature.get('properties', {})
                            coords = feature.get('geometry', {}).get('coordinates', [])
                            
                            if len(coords) >= 3:
                                magnitude = props.get('mag', 0)
                                if magnitude >= self.earthquake_min_magnitude:
                                    eq = EarthquakeData(
                                        magnitude=magnitude,
                                        location=props.get('place', 'Unknown'),
                                        depth=coords[2],
                                        time=datetime.fromtimestamp(props.get('time', 0) / 1000, tz=timezone.utc),
                                        latitude=coords[1],
                                        longitude=coords[0],
                                        url=props.get('url')
                                    )
                                    earthquakes.append(eq)
                        
                        # Sort by magnitude (descending)
                        earthquakes.sort(key=lambda x: x.magnitude, reverse=True)
                        
                        # Cache the data
                        self.earthquake_cache = earthquakes
                        self.cache_timestamps[cache_key] = datetime.now()
                        
                        return earthquakes
            
            # If API fails, return cached data
            return self.earthquake_cache
            
        except Exception as e:
            self.logger.error(f"Error fetching earthquake data: {e}")
            return self.earthquake_cache
    
    async def _get_user_location(self, user_id: str) -> LocationData:
        """Get user location from database or use default"""
        try:
            from src.core.database import get_database
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                SELECT location_lat, location_lon FROM users WHERE node_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            
            if result and result[0] is not None and result[1] is not None:
                return LocationData(latitude=result[0], longitude=result[1])
            
        except Exception as e:
            self.logger.error(f"Error getting user location: {e}")
        
        return self.default_location
    
    def _calculate_band_condition(self, solar_flux: float, band_meters: int, is_daytime: bool) -> str:
        """Calculate HF band condition based on solar flux and band"""
        # Simplified band condition calculation
        # Real implementation would use more sophisticated propagation models
        
        base_score = 0
        
        # Solar flux contribution
        if solar_flux > 200:
            base_score += 3
        elif solar_flux > 150:
            base_score += 2
        elif solar_flux > 100:
            base_score += 1
        
        # Band-specific adjustments
        if band_meters >= 40:  # Lower bands (80m, 40m)
            if not is_daytime:
                base_score += 2  # Better at night
        elif band_meters <= 15:  # Higher bands (15m, 12m, 10m)
            if is_daytime:
                base_score += 2  # Better during day
            if solar_flux < 100:
                base_score -= 2  # Poor when solar flux is low
        
        # Convert score to condition
        if base_score >= 4:
            return "Excellent"
        elif base_score >= 3:
            return "Good"
        elif base_score >= 2:
            return "Fair"
        elif base_score >= 1:
            return "Poor"
        else:
            return "Very Poor"
    
    def _get_condition_emoji(self, condition: str) -> str:
        """Get emoji for condition"""
        emoji_map = {
            "Excellent": "🟢",
            "Good": "🟢",
            "Fair": "🟡",
            "Poor": "🟠",
            "Very Poor": "🔴"
        }
        return emoji_map.get(condition, "⚪")
    
    def _calculate_sun_times(self, location: LocationData, date: datetime.date) -> Tuple[datetime, datetime]:
        """Calculate sunrise and sunset times for given location and date"""
        # Simplified sunrise/sunset calculation
        # Real implementation would use more accurate astronomical algorithms
        
        lat_rad = math.radians(location.latitude)
        
        # Day of year
        day_of_year = date.timetuple().tm_yday
        
        # Solar declination (simplified)
        declination = math.radians(23.45) * math.sin(math.radians(360 * (284 + day_of_year) / 365))
        
        # Hour angle
        try:
            hour_angle = math.acos(-math.tan(lat_rad) * math.tan(declination))
        except ValueError:
            # Polar day/night
            hour_angle = math.pi if location.latitude > 0 else 0
        
        # Convert to hours
        sunrise_hour = 12 - (hour_angle * 12 / math.pi)
        sunset_hour = 12 + (hour_angle * 12 / math.pi)
        
        # Create datetime objects
        sunrise = datetime.combine(date, datetime.min.time().replace(
            hour=int(sunrise_hour), 
            minute=int((sunrise_hour % 1) * 60)
        )).replace(tzinfo=timezone.utc)
        
        sunset = datetime.combine(date, datetime.min.time().replace(
            hour=int(sunset_hour), 
            minute=int((sunset_hour % 1) * 60)
        )).replace(tzinfo=timezone.utc)
        
        return sunrise, sunset
    
    def _calculate_moon_phase(self, date: datetime) -> Dict[str, Any]:
        """Calculate moon phase for given date"""
        # Simplified moon phase calculation
        # Based on the synodic month (29.53 days)
        
        # Known new moon date (2000-01-06 18:14 UTC)
        known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
        
        # Days since known new moon
        days_since = (date - known_new_moon).total_seconds() / (24 * 3600)
        
        # Moon cycle position (0-1)
        cycle_position = (days_since % 29.53) / 29.53
        
        # Calculate illumination percentage
        illumination = 50 * (1 - math.cos(2 * math.pi * cycle_position))
        
        # Determine phase name
        if cycle_position < 0.03 or cycle_position > 0.97:
            phase_name = "New Moon"
            emoji = "🌑"
        elif cycle_position < 0.22:
            phase_name = "Waxing Crescent"
            emoji = "🌒"
        elif cycle_position < 0.28:
            phase_name = "First Quarter"
            emoji = "🌓"
        elif cycle_position < 0.47:
            phase_name = "Waxing Gibbous"
            emoji = "🌔"
        elif cycle_position < 0.53:
            phase_name = "Full Moon"
            emoji = "🌕"
        elif cycle_position < 0.72:
            phase_name = "Waning Gibbous"
            emoji = "🌖"
        elif cycle_position < 0.78:
            phase_name = "Last Quarter"
            emoji = "🌗"
        else:
            phase_name = "Waning Crescent"
            emoji = "🌘"
        
        return {
            'name': phase_name,
            'emoji': emoji,
            'illumination': illumination,
            'cycle_position': cycle_position
        }
    
    def _get_next_moon_phase(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Get next major moon phase"""
        # Calculate next new moon, first quarter, full moon, or last quarter
        current_phase = self._calculate_moon_phase(date)
        current_position = current_phase['cycle_position']
        
        # Major phase positions
        phases = [
            (0.0, "New Moon"),
            (0.25, "First Quarter"),
            (0.5, "Full Moon"),
            (0.75, "Last Quarter")
        ]
        
        # Find next phase
        for position, name in phases:
            if position > current_position:
                days_to_phase = (position - current_position) * 29.53
                next_date = date + timedelta(days=days_to_phase)
                return {'name': name, 'date': next_date}
        
        # If no phase found, next is new moon of next cycle
        days_to_new_moon = (1.0 - current_position) * 29.53
        next_date = date + timedelta(days=days_to_new_moon)
        return {'name': "New Moon", 'date': next_date}
    
    def clear_cache(self):
        """Clear all cached data"""
        self.solar_data_cache = None
        self.earthquake_cache = []
        self.cache_timestamps.clear()
        self.logger.info("Reference data cache cleared")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information"""
        status = {}
        current_time = datetime.now()
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age_minutes = (current_time - timestamp).total_seconds() / 60
            status[cache_key] = {
                'last_updated': timestamp.isoformat(),
                'age_minutes': age_minutes,
                'expired': age_minutes > self.cache_duration_minutes
            }
        
        return status