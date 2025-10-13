"""
Weather Service Module

Provides comprehensive weather data fetching, multi-source emergency alerting,
proximity monitoring, and location-based filtering for ZephyrGate.
"""

from .weather_service import WeatherService
from .models import (
    WeatherData, WeatherAlert, WeatherSubscription, Location,
    AlertType, AlertSeverity, WeatherProvider, ProximityAlert,
    EarthquakeData, EnvironmentalReading
)

__all__ = [
    'WeatherService',
    'WeatherData',
    'WeatherAlert', 
    'WeatherSubscription',
    'Location',
    'AlertType',
    'AlertSeverity',
    'WeatherProvider',
    'ProximityAlert',
    'EarthquakeData',
    'EnvironmentalReading'
]