"""
Weather Service Data Models

Defines data structures for weather information, alerts, and environmental monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import uuid


class WeatherProvider(Enum):
    """Weather data providers"""
    NOAA = "noaa"
    OPEN_METEO = "open_meteo"
    CACHED = "cached"


class AlertSeverity(Enum):
    """Alert severity levels"""
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class AlertType(Enum):
    """Types of alerts"""
    WEATHER = "weather"
    EARTHQUAKE = "earthquake"
    VOLCANO = "volcano"
    FLOOD = "flood"
    FIRE = "fire"
    EMERGENCY = "emergency"
    PROXIMITY = "proximity"
    AIRCRAFT = "aircraft"
    ENVIRONMENTAL = "environmental"


@dataclass(frozen=True)
class Location:
    """Geographic location information"""
    latitude: float
    longitude: float
    name: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    fips_code: Optional[str] = None
    same_code: Optional[str] = None
    
    def distance_to(self, other: 'Location') -> float:
        """
        Calculate distance to another location in kilometers
        
        Args:
            other: Other location
            
        Returns:
            Distance in kilometers
        """
        import math
        
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(self.latitude)
        lat2_rad = math.radians(other.latitude)
        delta_lat = math.radians(other.latitude - self.latitude)
        delta_lon = math.radians(other.longitude - self.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


@dataclass
class WeatherCondition:
    """Current weather conditions"""
    temperature: float  # Celsius
    humidity: float  # Percentage
    pressure: float  # hPa
    wind_speed: float  # km/h
    wind_direction: int  # Degrees
    visibility: Optional[float] = None  # km
    cloud_cover: Optional[int] = None  # Percentage
    precipitation: Optional[float] = None  # mm
    uv_index: Optional[float] = None
    description: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class WeatherForecast:
    """Weather forecast for a specific time"""
    timestamp: datetime
    temperature_min: float  # Celsius
    temperature_max: float  # Celsius
    humidity: float  # Percentage
    precipitation_probability: float  # Percentage
    precipitation_amount: Optional[float] = None  # mm
    wind_speed: float = 0.0  # km/h
    wind_direction: int = 0  # Degrees
    description: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class WeatherData:
    """Complete weather information for a location"""
    location: Location
    current: WeatherCondition
    forecasts: List[WeatherForecast] = field(default_factory=list)
    provider: WeatherProvider = WeatherProvider.CACHED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if weather data has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class WeatherAlert:
    """Weather alert information"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: AlertType = AlertType.WEATHER
    severity: AlertSeverity = AlertSeverity.MODERATE
    title: str = ""
    description: str = ""
    location: Optional[Location] = None
    affected_areas: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    issued_time: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    source_url: Optional[str] = None
    fips_codes: List[str] = field(default_factory=list)
    same_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if alert is currently active"""
        # Get current time in UTC with timezone awareness
        now = datetime.now(timezone.utc)
        
        # Make start_time timezone-aware if it's naive
        start_time = self.start_time
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        
        # Check if alert has started
        if now < start_time:
            return False
        
        # Check if alert has ended
        if self.end_time:
            end_time = self.end_time
            # Make end_time timezone-aware if it's naive
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            if now > end_time:
                return False
        
        return True
    
    def affects_location(self, location: Location, radius_km: float = 50.0) -> bool:
        """
        Check if alert affects a specific location
        
        Args:
            location: Location to check
            radius_km: Radius in kilometers for proximity check
            
        Returns:
            True if location is affected
        """
        # Check FIPS codes
        if location.fips_code and location.fips_code in self.fips_codes:
            return True
        
        # Check SAME codes
        if location.same_code and location.same_code in self.same_codes:
            return True
        
        # Check geographic proximity
        if self.location:
            distance = location.distance_to(self.location)
            return distance <= radius_km
        
        return False


@dataclass
class EarthquakeData:
    """Earthquake information"""
    id: str
    magnitude: float
    location: Location
    depth: float  # km
    timestamp: datetime
    title: str
    url: Optional[str] = None
    significance: Optional[int] = None
    
    def get_alert_radius(self) -> float:
        """
        Get alert radius based on magnitude
        
        Returns:
            Alert radius in kilometers
        """
        if self.magnitude >= 7.0:
            return 500.0
        elif self.magnitude >= 6.0:
            return 200.0
        elif self.magnitude >= 5.0:
            return 100.0
        elif self.magnitude >= 4.0:
            return 50.0
        else:
            return 25.0


@dataclass
class ProximityAlert:
    """Proximity detection alert"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    node_name: str = ""
    location: Optional[Location] = None
    distance: float = 0.0  # km
    altitude: Optional[float] = None  # meters
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_aircraft: bool = False
    aircraft_data: Optional[Dict[str, Any]] = None
    
    def is_high_altitude(self, threshold_meters: float = 1000.0) -> bool:
        """Check if node is at high altitude"""
        return self.altitude is not None and self.altitude > threshold_meters


@dataclass
class EnvironmentalReading:
    """Environmental sensor reading"""
    sensor_id: str
    sensor_type: str
    location: Optional[Location] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    readings: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_reading(self, parameter: str, default: float = 0.0) -> float:
        """Get a specific reading value"""
        return self.readings.get(parameter, default)
    
    def is_threshold_exceeded(self, parameter: str, threshold: float, 
                            comparison: str = "greater") -> bool:
        """
        Check if a reading exceeds a threshold
        
        Args:
            parameter: Parameter name
            threshold: Threshold value
            comparison: "greater", "less", "equal"
            
        Returns:
            True if threshold is exceeded
        """
        value = self.get_reading(parameter)
        
        if comparison == "greater":
            return value > threshold
        elif comparison == "less":
            return value < threshold
        elif comparison == "equal":
            return abs(value - threshold) < 0.001
        
        return False


@dataclass
class WeatherSubscription:
    """User weather subscription preferences"""
    user_id: str
    location: Optional[Location] = None
    weather_updates: bool = True
    forecast_updates: bool = True
    severe_weather_alerts: bool = True
    earthquake_alerts: bool = True
    proximity_alerts: bool = False
    aircraft_alerts: bool = False
    alert_radius_km: float = 50.0
    update_interval_minutes: int = 60
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None  # Hour (0-23)
    alert_types: List[AlertType] = field(default_factory=lambda: [
        AlertType.WEATHER, AlertType.EARTHQUAKE
    ])
    
    def is_quiet_time(self) -> bool:
        """Check if current time is within quiet hours"""
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False
        
        current_hour = datetime.now().hour
        
        if self.quiet_hours_start <= self.quiet_hours_end:
            # Same day quiet hours (e.g., 22:00 to 06:00 next day)
            return self.quiet_hours_start <= current_hour <= self.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 to 06:00 next day)
            return current_hour >= self.quiet_hours_start or current_hour <= self.quiet_hours_end
    
    def should_receive_alert(self, alert: WeatherAlert) -> bool:
        """
        Check if user should receive a specific alert
        
        Args:
            alert: Alert to check
            
        Returns:
            True if user should receive the alert
        """
        # Check if alert type is subscribed
        if alert.alert_type not in self.alert_types:
            return False
        
        # Check quiet hours for non-severe alerts
        if alert.severity != AlertSeverity.EXTREME and self.is_quiet_time():
            return False
        
        # Check location proximity
        if self.location and alert.location:
            distance = self.location.distance_to(alert.location)
            if distance > self.alert_radius_km:
                return False
        
        return True


@dataclass
class WeatherCache:
    """Weather data cache entry"""
    key: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def access(self):
        """Record cache access"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()