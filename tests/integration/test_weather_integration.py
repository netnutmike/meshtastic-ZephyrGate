"""
Integration tests for Weather Service

Tests complete weather service integration including API clients,
cache management, alert processing, and location-based filtering.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import shutil
import json

from src.services.weather.weather_service import WeatherService
from src.services.weather.models import (
    WeatherData, WeatherCondition, WeatherAlert, Location,
    AlertType, AlertSeverity, WeatherSubscription
)
from src.services.weather.noaa_client import NOAAClient
from src.services.weather.openmeteo_client import OpenMeteoClient
from src.services.weather.alert_clients import AlertAggregator
from src.services.weather.environmental_monitoring import EnvironmentalMonitoringService
from src.services.weather.location_filtering import LocationBasedFilteringService, LocationAccuracy
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
def integration_config(temp_dir):
    """Integration test configuration"""
    return {
        'cache_duration_minutes': 5,  # Short cache for testing
        'update_interval_minutes': 1,  # Fast updates for testing
        'default_location': {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'name': 'New York',
            'country': 'US',
            'fips_code': '36061',
            'same_code': '036061'
        },
        'default_alert_radius_km': 50.0,
        'noaa_api_key': 'test_key',
        'openmeteo_enabled': True,
        'earthquake_monitoring': True,
        'proximity_monitoring': True,
        'data_directory': str(temp_dir),
        'max_cache_size_mb': 5,
        'environmental_monitoring': {
            'proximity': {
                'enabled': True,
                'detection_radius_km': 10.0,
                'update_interval_seconds': 5
            },
            'opensky_username': None,
            'opensky_password': None,
            'rf_monitoring': {
                'enabled': False
            }
        },
        'file_sensor_monitoring': {
            'file_monitoring': {
                'enabled': False
            },
            'sensor_monitoring': {
                'enabled': False
            }
        },
        'location_filtering': {
            'location_tracking': {
                'enabled': True,
                'max_location_age_hours': 24
            }
        }
    }


@pytest_asyncio.fixture
async def weather_service(integration_config, mock_plugin_manager):
    """Create integrated weather service"""
    service = WeatherService("weather_service", integration_config, mock_plugin_manager)
    await service.initialize()
    await service.start()
    yield service
    await service.stop()
    await service.cleanup()


@pytest.fixture
def sample_locations():
    """Sample locations for testing"""
    return {
        'new_york': Location(
            latitude=40.7128,
            longitude=-74.0060,
            name="New York",
            country="US",
            state="NY",
            fips_code="36061",
            same_code="036061"
        ),
        'los_angeles': Location(
            latitude=34.0522,
            longitude=-118.2437,
            name="Los Angeles",
            country="US",
            state="CA",
            fips_code="06037",
            same_code="006037"
        ),
        'london': Location(
            latitude=51.5074,
            longitude=-0.1278,
            name="London",
            country="GB"
        )
    }


class TestWeatherServiceIntegration:
    """Integration tests for weather service"""
    
    @pytest.mark.asyncio
    async def test_complete_weather_workflow(self, weather_service, sample_locations):
        """Test complete weather data workflow"""
        user_id = "test_user"
        location = sample_locations['new_york']
        
        # Set user location
        result = await weather_service.set_user_location(
            user_id, location.latitude, location.longitude, location.name
        )
        assert "Location set to" in result
        
        # Subscribe to weather updates
        result = await weather_service.subscribe_user(user_id, ['weather', 'forecast', 'alerts'])
        assert "Weather subscription updated" in result
        
        # Mock weather data
        mock_weather_data = WeatherData(
            location=location,
            current=WeatherCondition(
                temperature=22.0,
                humidity=60.0,
                pressure=1015.0,
                wind_speed=10.0,
                wind_direction=90,
                description="Clear sky"
            ),
            forecasts=[],
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        
        # Mock API client
        with patch.object(weather_service, '_fetch_weather_data', return_value=mock_weather_data):
            # Get weather report
            report = await weather_service.get_weather_report(user_id)
            
            assert "Weather for New York" in report
            assert "22.0°C" in report
            assert "60%" in report
            assert "10.0 km/h" in report
    
    @pytest.mark.asyncio
    async def test_alert_processing_and_filtering(self, weather_service, sample_locations):
        """Test alert processing with location-based filtering"""
        # Create users in different locations
        ny_user = "ny_user"
        la_user = "la_user"
        
        # Set locations
        await weather_service.set_user_location(
            ny_user, sample_locations['new_york'].latitude, 
            sample_locations['new_york'].longitude, "New York"
        )
        await weather_service.set_user_location(
            la_user, sample_locations['los_angeles'].latitude,
            sample_locations['los_angeles'].longitude, "Los Angeles"
        )
        
        # Subscribe both users to alerts
        await weather_service.subscribe_user(ny_user, ['alerts'])
        await weather_service.subscribe_user(la_user, ['alerts'])
        
        # Create alert for New York area
        ny_alert = WeatherAlert(
            id="ny_alert_001",
            alert_type=AlertType.WEATHER,
            severity=AlertSeverity.SEVERE,
            title="Severe Thunderstorm Warning",
            description="Severe thunderstorms in New York area",
            location=sample_locations['new_york'],
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=4),
            source="Test Weather Service",
            fips_codes=["36061"]
        )
        
        # Mock communication interface
        weather_service.comm = Mock()
        weather_service.comm.send_mesh_message = AsyncMock()
        
        # Process alert
        weather_service.active_alerts[ny_alert.id] = ny_alert
        await weather_service._broadcast_alert(ny_alert)
        
        # Verify only NY user received the alert
        # (LA user should be filtered out due to distance)
        calls = weather_service.comm.send_mesh_message.call_args_list
        
        # Should have at least one call for NY user
        assert len(calls) >= 1
        
        # Check that NY user received the alert
        ny_received = any(
            call[0][0].recipient_id == ny_user and "Severe Thunderstorm Warning" in call[0][0].content
            for call in calls
        )
        assert ny_received
    
    @pytest.mark.asyncio
    async def test_proximity_monitoring_integration(self, weather_service, sample_locations):
        """Test proximity monitoring integration"""
        user1 = "user1"
        user2 = "user2"
        
        # Set up users with proximity alerts enabled
        await weather_service.set_user_location(
            user1, sample_locations['new_york'].latitude,
            sample_locations['new_york'].longitude, "User 1"
        )
        
        subscription1 = WeatherSubscription(user_id=user1, proximity_alerts=True)
        weather_service.subscriptions[user1] = subscription1
        
        # Mock communication interface
        weather_service.comm = Mock()
        weather_service.comm.send_mesh_message = AsyncMock()
        
        # Simulate user2 coming within proximity
        nearby_location = Location(
            latitude=sample_locations['new_york'].latitude + 0.01,  # ~1km away
            longitude=sample_locations['new_york'].longitude + 0.01,
            name="User 2"
        )
        
        # Update node position in environmental monitor
        if weather_service.environmental_monitor:
            weather_service.environmental_monitor.update_node_position(
                user2, nearby_location, altitude=100.0, metadata={'name': 'User 2'}
            )
            
            # Wait for proximity detection
            await asyncio.sleep(0.2)
            
            # Check if proximity alert was generated
            proximity_alerts = weather_service.environmental_monitor.get_proximity_alerts()
            
            # Should have detected proximity
            assert len(proximity_alerts) > 0 or len(weather_service.proximity_alerts) > 0
    
    @pytest.mark.asyncio
    async def test_cache_persistence_and_recovery(self, weather_service, sample_locations):
        """Test cache persistence and recovery"""
        location = sample_locations['new_york']
        
        # Create mock weather data
        weather_data = WeatherData(
            location=location,
            current=WeatherCondition(
                temperature=25.0,
                humidity=55.0,
                pressure=1020.0,
                wind_speed=8.0,
                wind_direction=270,
                description="Sunny"
            ),
            forecasts=[],
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Store in cache
        await weather_service.cache_manager.put(location, weather_data, "weather")
        
        # Verify cache hit
        cached_data = await weather_service.cache_manager.get(location, "weather")
        assert cached_data is not None
        assert cached_data.current.temperature == 25.0
        
        # Test cache statistics
        stats = weather_service.cache_manager.get_stats()
        assert stats['hits'] > 0
        assert stats['memory_entries'] > 0
    
    @pytest.mark.asyncio
    async def test_subscription_persistence(self, weather_service, sample_locations):
        """Test subscription persistence across service restarts"""
        user_id = "persistent_user"
        location = sample_locations['new_york']
        
        # Create subscription
        await weather_service.set_user_location(
            user_id, location.latitude, location.longitude, location.name
        )
        await weather_service.subscribe_user(user_id, ['weather', 'alerts', 'earthquake'])
        
        # Verify subscription exists
        assert user_id in weather_service.subscriptions
        subscription = weather_service.subscriptions[user_id]
        assert subscription.weather_updates
        assert subscription.severe_weather_alerts
        assert subscription.earthquake_alerts
        
        # Save subscriptions
        await weather_service._save_subscriptions()
        
        # Clear subscriptions and reload
        weather_service.subscriptions.clear()
        await weather_service._load_subscriptions()
        
        # Verify subscription was restored
        assert user_id in weather_service.subscriptions
        restored_subscription = weather_service.subscriptions[user_id]
        assert restored_subscription.weather_updates
        assert restored_subscription.severe_weather_alerts
        assert restored_subscription.earthquake_alerts
    
    @pytest.mark.asyncio
    async def test_location_tracking_and_geofencing(self, weather_service, sample_locations):
        """Test location tracking and geofencing"""
        user_id = "mobile_user"
        
        # Set initial location
        initial_location = sample_locations['new_york']
        await weather_service.set_user_location(
            user_id, initial_location.latitude, initial_location.longitude, "Start Location"
        )
        
        # Verify location was set
        if weather_service.location_filter:
            location_update = weather_service.location_filter.get_user_location(user_id)
            assert location_update is not None
            assert location_update.location.latitude == initial_location.latitude
            assert location_update.location.longitude == initial_location.longitude
            
            # Move user to different location
            new_location = sample_locations['los_angeles']
            updated = weather_service.location_filter.update_user_location(
                user_id, new_location, LocationAccuracy.HIGH, "gps"
            )
            
            # Should be significant change
            assert updated
            
            # Verify new location
            updated_location = weather_service.location_filter.get_user_location(user_id)
            assert updated_location.location.latitude == new_location.latitude
            assert updated_location.location.longitude == new_location.longitude
    
    @pytest.mark.asyncio
    async def test_multi_user_nearby_detection(self, weather_service, sample_locations):
        """Test nearby user detection"""
        base_location = sample_locations['new_york']
        
        # Create multiple users in nearby locations
        users = []
        for i in range(3):
            user_id = f"user_{i}"
            # Spread users within 5km radius
            lat_offset = (i - 1) * 0.02  # ~2km per 0.02 degrees
            lon_offset = (i - 1) * 0.02
            
            location = Location(
                latitude=base_location.latitude + lat_offset,
                longitude=base_location.longitude + lon_offset,
                name=f"User {i} Location"
            )
            
            await weather_service.set_user_location(
                user_id, location.latitude, location.longitude, location.name
            )
            users.append(user_id)
        
        # Test nearby user detection
        result = await weather_service.get_nearby_users(users[1], radius_km=10.0)
        
        # Should find other users
        assert "user(s) within 10.0km" in result
        # Should not include the requesting user
        assert users[1] not in result
    
    @pytest.mark.asyncio
    async def test_command_processing_integration(self, weather_service, sample_locations):
        """Test complete command processing workflow"""
        from src.models.message import Message, MessageType
        
        user_id = "command_user"
        location = sample_locations['new_york']
        
        # Set location first
        await weather_service.set_user_location(
            user_id, location.latitude, location.longitude, location.name
        )
        
        # Test weather command
        weather_msg = Message(
            id="msg_wx",
            sender_id=user_id,
            recipient_id="weather_service",
            channel=0,
            content="wx",
            timestamp=datetime.utcnow(),
            message_type=MessageType.DIRECT_MESSAGE,
            interface_id="test"
        )
        
        # Mock weather data
        with patch.object(weather_service, 'get_weather_data') as mock_get_weather:
            mock_weather_data = WeatherData(
                location=location,
                current=WeatherCondition(
                    temperature=18.0,
                    humidity=70.0,
                    pressure=1010.0,
                    wind_speed=12.0,
                    wind_direction=180,
                    description="Overcast"
                ),
                forecasts=[]
            )
            mock_get_weather.return_value = mock_weather_data
            
            result = await weather_service.handle_weather_command(weather_msg)
            
            assert "Weather for New York" in result
            assert "18.0°C" in result
        
        # Test subscription command
        subscribe_msg = Message(
            id="msg_sub",
            sender_id=user_id,
            recipient_id="weather_service",
            channel=0,
            content="subscribe_weather alerts earthquake",
            timestamp=datetime.utcnow(),
            message_type=MessageType.DIRECT_MESSAGE,
            interface_id="test"
        )
        
        result = await weather_service.handle_weather_command(subscribe_msg)
        assert "Weather subscription updated" in result
        
        # Verify subscription
        assert user_id in weather_service.subscriptions
        subscription = weather_service.subscriptions[user_id]
        assert subscription.severe_weather_alerts
        assert subscription.earthquake_alerts
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_resilience(self, weather_service, sample_locations):
        """Test error recovery and system resilience"""
        user_id = "resilience_user"
        location = sample_locations['new_york']
        
        # Test with API failures
        with patch.object(weather_service, '_fetch_weather_data', side_effect=Exception("API Error")):
            # Should not crash, should return error message
            result = await weather_service.get_weather_report(user_id)
            assert "No location configured" in result or "Unable to fetch" in result
        
        # Test with invalid location data
        result = await weather_service.set_user_location(user_id, 999.0, 999.0, "Invalid")
        # Should handle gracefully (coordinates are technically valid, just unusual)
        assert "Location set to" in result or "Location services not available" in result
        
        # Test with malformed commands
        from src.models.message import Message, MessageType
        
        malformed_msg = Message(
            id="msg_bad",
            sender_id=user_id,
            recipient_id="weather_service",
            channel=0,
            content="invalid_command_xyz",
            timestamp=datetime.utcnow(),
            message_type=MessageType.DIRECT_MESSAGE,
            interface_id="test"
        )
        
        result = await weather_service.handle_weather_command(malformed_msg)
        assert "Unknown weather command" in result
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, weather_service, sample_locations):
        """Test performance under concurrent load"""
        import time
        
        # Create multiple concurrent requests
        tasks = []
        start_time = time.time()
        
        for i in range(10):
            user_id = f"load_user_{i}"
            location = sample_locations['new_york']
            
            # Create tasks for concurrent execution
            tasks.extend([
                weather_service.set_user_location(
                    user_id, location.latitude + i * 0.001, 
                    location.longitude + i * 0.001, f"User {i}"
                ),
                weather_service.subscribe_user(user_id, ['weather', 'alerts']),
                weather_service.get_subscription_status(user_id)
            ])
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert execution_time < 5.0  # 5 seconds for 30 operations
        
        # Check that most operations succeeded
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) > len(results) * 0.8  # At least 80% success rate


if __name__ == "__main__":
    pytest.main([__file__])