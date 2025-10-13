"""
Unit tests for Weather Service

Tests weather data fetching, caching, alert processing, and location-based filtering.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from src.services.weather.weather_service import WeatherService
from src.services.weather.models import (
    WeatherData, WeatherCondition, WeatherForecast, WeatherAlert,
    Location, AlertType, AlertSeverity, WeatherProvider, WeatherSubscription
)
from src.core.plugin_manager import PluginManager


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_plugin_manager():
    """Mock plugin manager"""
    manager = Mock(spec=PluginManager)
    manager.register_message_handler = AsyncMock()
    manager.register_command_handler = AsyncMock()
    return manager


@pytest.fixture
def weather_config(temp_dir):
    """Weather service configuration"""
    return {
        'cache_duration_minutes': 30,
        'update_interval_minutes': 15,
        'default_location': {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'name': 'New York',
            'country': 'US'
        },
        'default_alert_radius_km': 50.0,
        'noaa_api_key': 'test_key',
        'openmeteo_enabled': True,
        'earthquake_monitoring': True,
        'proximity_monitoring': True,
        'data_directory': str(temp_dir),
        'max_cache_size_mb': 10
    }


@pytest_asyncio.fixture
async def weather_service(weather_config, mock_plugin_manager):
    """Create weather service instance"""
    service = WeatherService("weather_service", weather_config, mock_plugin_manager)
    await service.initialize()
    await service.start()
    yield service
    await service.stop()
    await service.cleanup()


@pytest.fixture
def sample_location():
    """Sample location for testing"""
    return Location(
        latitude=40.7128,
        longitude=-74.0060,
        name="New York",
        country="US",
        state="NY",
        fips_code="36061",
        same_code="036061"
    )


@pytest.fixture
def sample_weather_data(sample_location):
    """Sample weather data for testing"""
    current = WeatherCondition(
        temperature=20.0,
        humidity=65.0,
        pressure=1013.25,
        wind_speed=15.0,
        wind_direction=180,
        visibility=10.0,
        cloud_cover=50,
        description="Partly cloudy"
    )
    
    forecasts = [
        WeatherForecast(
            timestamp=datetime.utcnow() + timedelta(days=1),
            temperature_min=15.0,
            temperature_max=25.0,
            humidity=60.0,
            precipitation_probability=20.0,
            description="Sunny"
        )
    ]
    
    return WeatherData(
        location=sample_location,
        current=current,
        forecasts=forecasts,
        provider=WeatherProvider.OPEN_METEO,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )


@pytest.fixture
def sample_weather_alert(sample_location):
    """Sample weather alert for testing"""
    return WeatherAlert(
        id="test_alert_001",
        alert_type=AlertType.WEATHER,
        severity=AlertSeverity.MODERATE,
        title="Thunderstorm Warning",
        description="Severe thunderstorms expected in the area",
        location=sample_location,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(hours=6),
        source="Test Weather Service",
        fips_codes=["36061"],
        same_codes=["036061"]
    )


class TestWeatherService:
    """Test weather service functionality"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, weather_service):
        """Test weather service initialization"""
        assert weather_service.is_running
        assert weather_service.cache_manager is not None
        assert weather_service.alert_aggregator is not None
        assert weather_service.environmental_monitor is not None
        assert weather_service.file_sensor_monitor is not None
        assert weather_service.location_filter is not None
    
    @pytest.mark.asyncio
    async def test_get_weather_data_cached(self, weather_service, sample_location, sample_weather_data):
        """Test getting cached weather data"""
        # Mock cache manager to return cached data
        weather_service.cache_manager.get = AsyncMock(return_value=sample_weather_data)
        
        result = await weather_service.get_weather_data(sample_location)
        
        assert result == sample_weather_data
        weather_service.cache_manager.get.assert_called_once_with(sample_location, "weather")
    
    @pytest.mark.asyncio
    async def test_get_weather_data_fetch_new(self, weather_service, sample_location, sample_weather_data):
        """Test fetching new weather data"""
        # Mock cache manager to return None (no cached data)
        weather_service.cache_manager.get = AsyncMock(return_value=None)
        weather_service.cache_manager.put = AsyncMock()
        
        # Mock API client to return weather data
        weather_service.openmeteo_client = Mock()
        weather_service.openmeteo_client.get_weather_data = AsyncMock(return_value=sample_weather_data)
        
        result = await weather_service.get_weather_data(sample_location)
        
        assert result == sample_weather_data
        weather_service.cache_manager.put.assert_called_once_with(sample_location, sample_weather_data, "weather")
    
    @pytest.mark.asyncio
    async def test_get_weather_data_offline_fallback(self, weather_service, sample_location, sample_weather_data):
        """Test offline fallback for weather data"""
        # Mock cache manager and API clients to fail
        weather_service.cache_manager.get = AsyncMock(return_value=None)
        weather_service.cache_manager.get_offline_data = AsyncMock(return_value=sample_weather_data)
        weather_service.openmeteo_client = Mock()
        weather_service.openmeteo_client.get_weather_data = AsyncMock(side_effect=Exception("API Error"))
        
        result = await weather_service.get_weather_data(sample_location)
        
        assert result == sample_weather_data
        weather_service.cache_manager.get_offline_data.assert_called_once_with(sample_location)
    
    @pytest.mark.asyncio
    async def test_weather_report_generation(self, weather_service, sample_weather_data):
        """Test weather report generation"""
        user_id = "test_user"
        
        # Create subscription with location
        subscription = WeatherSubscription(user_id=user_id, location=sample_weather_data.location)
        weather_service.subscriptions[user_id] = subscription
        
        # Mock get_weather_data
        weather_service.get_weather_data = AsyncMock(return_value=sample_weather_data)
        
        result = await weather_service.get_weather_report(user_id, detailed=False)
        
        assert "Weather for New York" in result
        assert "20.1°C" in result
        assert "65%" in result  # humidity
        assert "15.0 km/h" in result  # wind speed
    
    @pytest.mark.asyncio
    async def test_forecast_report_generation(self, weather_service, sample_weather_data):
        """Test forecast report generation"""
        user_id = "test_user"
        
        # Create subscription with location
        subscription = WeatherSubscription(user_id=user_id, location=sample_weather_data.location)
        weather_service.subscriptions[user_id] = subscription
        
        # Mock get_weather_data
        weather_service.get_weather_data = AsyncMock(return_value=sample_weather_data)
        
        result = await weather_service.get_forecast_report(user_id, days=3)
        
        assert "3-day forecast for New York" in result
        assert "15-25°C" in result  # temperature range
    
    @pytest.mark.asyncio
    async def test_user_subscription_management(self, weather_service):
        """Test user subscription management"""
        user_id = "test_user"
        
        # Test subscription
        result = await weather_service.subscribe_user(user_id, ['weather', 'alerts'])
        assert "Weather subscription updated" in result
        assert user_id in weather_service.subscriptions
        
        subscription = weather_service.subscriptions[user_id]
        assert subscription.weather_updates
        assert subscription.severe_weather_alerts
        
        # Test unsubscription
        result = await weather_service.unsubscribe_user(user_id)
        assert "Weather subscription removed" in result
        assert user_id not in weather_service.subscriptions
    
    @pytest.mark.asyncio
    async def test_location_management(self, weather_service):
        """Test user location management"""
        user_id = "test_user"
        
        # Mock location filter
        weather_service.location_filter = Mock()
        weather_service.location_filter.update_user_location = Mock(return_value=True)
        
        # Test setting location
        result = await weather_service.set_user_location(user_id, 40.7128, -74.0060, "New York")
        
        assert "Location set to" in result
        assert "40.7128, -74.0060 (New York)" in result
        
        # Verify subscription was created/updated
        assert user_id in weather_service.subscriptions
        subscription = weather_service.subscriptions[user_id]
        assert subscription.location is not None
        assert subscription.location.latitude == 40.7128
        assert subscription.location.longitude == -74.0060
        assert subscription.location.name == "New York"
    
    @pytest.mark.asyncio
    async def test_alert_broadcasting(self, weather_service, sample_weather_alert):
        """Test alert broadcasting to subscribed users"""
        user_id = "test_user"
        
        # Create subscription
        subscription = WeatherSubscription(
            user_id=user_id,
            location=sample_weather_alert.location,
            severe_weather_alerts=True,
            alert_types=[AlertType.WEATHER]
        )
        weather_service.subscriptions[user_id] = subscription
        
        # Mock communication interface
        weather_service.comm = Mock()
        weather_service.comm.send_mesh_message = AsyncMock()
        
        # Mock location filter
        weather_service.location_filter = Mock()
        weather_service.location_filter.filter_alerts_for_user = Mock(return_value=[sample_weather_alert])
        
        # Broadcast alert
        await weather_service._broadcast_alert(sample_weather_alert)
        
        # Verify message was sent
        weather_service.comm.send_mesh_message.assert_called_once()
        call_args = weather_service.comm.send_mesh_message.call_args[0][0]
        assert call_args.recipient_id == user_id
        assert "Thunderstorm Warning" in call_args.content
    
    @pytest.mark.asyncio
    async def test_proximity_alert_handling(self, weather_service):
        """Test proximity alert handling"""
        from src.services.weather.models import ProximityAlert
        
        # Create proximity alert
        alert = ProximityAlert(
            id="prox_001",
            node_id="node_123",
            node_name="Test Node",
            distance=5.0,
            altitude=1500.0,
            is_aircraft=True
        )
        
        # Mock communication interface
        weather_service.comm = Mock()
        weather_service.comm.send_mesh_message = AsyncMock()
        
        # Create user with proximity alerts enabled
        user_id = "test_user"
        subscription = WeatherSubscription(user_id=user_id, proximity_alerts=True)
        weather_service.subscriptions[user_id] = subscription
        
        # Handle environmental alert
        weather_service._handle_environmental_alert(alert)
        
        # Wait for async broadcast
        await asyncio.sleep(0.1)
        
        # Verify alert was stored
        assert alert.id in weather_service.proximity_alerts
    
    @pytest.mark.asyncio
    async def test_earthquake_info_retrieval(self, weather_service, sample_location):
        """Test earthquake information retrieval"""
        from src.services.weather.models import EarthquakeData
        
        user_id = "test_user"
        
        # Create subscription with location
        subscription = WeatherSubscription(user_id=user_id, location=sample_location)
        weather_service.subscriptions[user_id] = subscription
        
        # Mock earthquake data
        earthquake = EarthquakeData(
            id="eq_001",
            magnitude=5.2,
            location=Location(latitude=40.5, longitude=-74.2, name="Near New York"),
            depth=10.0,
            timestamp=datetime.utcnow(),
            title="M 5.2 - Near New York"
        )
        
        # Mock alert aggregator
        weather_service.alert_aggregator = Mock()
        weather_service.alert_aggregator.earthquake_client = Mock()
        weather_service.alert_aggregator.earthquake_client.get_earthquakes = AsyncMock(return_value=[earthquake])
        
        result = await weather_service.get_earthquake_info(user_id)
        
        assert "1 earthquake(s) in last 24 hours" in result
        assert "M5.2" in result
        assert "Near New York" in result
    
    @pytest.mark.asyncio
    async def test_command_handling(self, weather_service):
        """Test weather command handling"""
        from src.models.message import Message, MessageType
        
        # Create test message
        message = Message(
            id="msg_001",
            sender_id="test_user",
            recipient_id="weather_service",
            channel=0,
            content="wx",
            timestamp=datetime.utcnow(),
            message_type=MessageType.DIRECT_MESSAGE,
            interface_id="test"
        )
        
        # Mock weather data
        weather_service.get_weather_report = AsyncMock(return_value="Test weather report")
        
        result = await weather_service.handle_weather_command(message)
        
        assert result == "Test weather report"
        weather_service.get_weather_report.assert_called_once_with("test_user", detailed=False)
    
    @pytest.mark.asyncio
    async def test_alert_filtering_by_location(self, weather_service, sample_weather_alert):
        """Test alert filtering by user location"""
        user_id = "test_user"
        
        # Create subscription with different location
        different_location = Location(latitude=34.0522, longitude=-118.2437, name="Los Angeles")
        subscription = WeatherSubscription(
            user_id=user_id,
            location=different_location,
            severe_weather_alerts=True,
            alert_types=[AlertType.WEATHER],
            alert_radius_km=10.0  # Small radius
        )
        weather_service.subscriptions[user_id] = subscription
        
        # Mock location filter to return no alerts (too far)
        weather_service.location_filter = Mock()
        weather_service.location_filter.filter_alerts_for_user = Mock(return_value=[])
        
        # Mock communication interface
        weather_service.comm = Mock()
        weather_service.comm.send_mesh_message = AsyncMock()
        
        # Broadcast alert
        await weather_service._broadcast_alert(sample_weather_alert)
        
        # Verify no message was sent (user too far from alert)
        weather_service.comm.send_mesh_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_manager_integration(self, weather_service, sample_location, sample_weather_data):
        """Test cache manager integration"""
        # Test cache put operation
        await weather_service.cache_manager.put(sample_location, sample_weather_data, "weather")
        
        # Test cache get operation
        cached_data = await weather_service.cache_manager.get(sample_location, "weather")
        
        assert cached_data is not None
        assert cached_data.location.latitude == sample_location.latitude
        assert cached_data.location.longitude == sample_location.longitude
    
    def test_weather_report_formatting(self, weather_service, sample_weather_data):
        """Test weather report formatting"""
        # Test basic report
        report = weather_service._format_weather_report(sample_weather_data, detailed=False)
        
        assert "Weather for New York" in report
        assert "20.1°C" in report
        assert "65%" in report
        assert "15.0 km/h" in report
        
        # Test detailed report
        detailed_report = weather_service._format_weather_report(sample_weather_data, detailed=True)
        
        assert "Weather for New York" in detailed_report
        assert "1013.3 hPa" in detailed_report  # pressure
        assert "10.0 km" in detailed_report  # visibility
        assert "50%" in detailed_report  # cloud cover
    
    def test_forecast_report_formatting(self, weather_service, sample_weather_data):
        """Test forecast report formatting"""
        report = weather_service._format_forecast_report(sample_weather_data, days=1)
        
        assert "1-day forecast for New York" in report
        assert "15-25°C" in report
        assert "20%" in report  # precipitation probability
    
    def test_alert_formatting(self, weather_service, sample_weather_alert):
        """Test alert formatting"""
        alerts = [sample_weather_alert]
        report = weather_service._format_alerts(alerts)
        
        assert "1 active alert(s)" in report
        assert "🟠" in report  # moderate severity emoji
        assert "Thunderstorm Warning" in report
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, weather_config, mock_plugin_manager):
        """Test complete service lifecycle"""
        service = WeatherService("weather_service", weather_config, mock_plugin_manager)
        
        # Test initialization
        assert await service.initialize()
        assert not service.is_running
        
        # Test start
        assert await service.start()
        assert service.is_running
        
        # Test stop
        assert await service.stop()
        assert not service.is_running
        
        # Test cleanup
        assert await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, weather_service, sample_location):
        """Test error handling in weather service"""
        # Test with invalid location
        result = await weather_service.get_weather_report("nonexistent_user")
        assert "No location configured" in result
        
        # Test with API failure
        weather_service.cache_manager.get = AsyncMock(return_value=None)
        weather_service.cache_manager.get_offline_data = AsyncMock(return_value=None)
        weather_service.openmeteo_client = Mock()
        weather_service.openmeteo_client.get_weather_data = AsyncMock(side_effect=Exception("API Error"))
        weather_service.noaa_client = None
        
        result = await weather_service.get_weather_data(sample_location)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])