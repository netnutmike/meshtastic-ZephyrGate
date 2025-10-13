"""
Tests for Reference Service

Tests the reference data features including:
- Solar conditions
- HF band conditions  
- Earthquake data
- Astronomical data (sun, moon)
- Tide information
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.services.bot.reference_service import (
    ReferenceService, SolarData, EarthquakeData, LocationData
)


@pytest.fixture
def reference_service():
    """Create reference service for testing"""
    config = {
        'cache_duration_minutes': 30,
        'earthquake_min_magnitude': 4.0,
        'earthquake_max_results': 10,
        'default_latitude': 40.7128,
        'default_longitude': -74.0060,
        'default_timezone_offset': -5.0
    }
    
    service = ReferenceService(config)
    return service


class TestReferenceService:
    """Test reference service functionality"""
    
    def test_initialization(self, reference_service):
        """Test service initialization"""
        assert reference_service is not None
        assert reference_service.cache_duration_minutes == 30
        assert reference_service.earthquake_min_magnitude == 4.0
        assert reference_service.default_location.latitude == 40.7128
    
    @pytest.mark.asyncio
    async def test_solar_command_no_data(self, reference_service):
        """Test solar command when no data available"""
        # Mock failed API call
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response
            
            response = await reference_service.handle_solar_command([], {})
            
            assert "Unable to retrieve solar data" in response
    
    @pytest.mark.asyncio
    async def test_solar_command_with_data(self, reference_service):
        """Test solar command with mock data"""
        # Mock successful API call
        mock_solar_data = [
            {
                "observed_ssn": 150.5,
                "date": "2024-01-01"
            }
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_solar_data
            mock_get.return_value.__aenter__.return_value = mock_response
            
            response = await reference_service.handle_solar_command([], {})
            
            assert "Solar Conditions" in response
            assert "Solar Flux" in response or "Sunspot Number" in response
    
    @pytest.mark.asyncio
    async def test_hfcond_command(self, reference_service):
        """Test HF conditions command"""
        # Set up mock solar data
        reference_service.solar_data_cache = SolarData(
            solar_flux=150.0,
            sunspot_number=100,
            updated=datetime.now()
        )
        
        response = await reference_service.handle_hfcond_command([], {})
        
        assert "HF Band Conditions" in response
        assert "80m:" in response
        assert "40m:" in response
        assert "20m:" in response
        assert "Solar Flux: 150.0" in response
    
    @pytest.mark.asyncio
    async def test_earthquake_command_no_data(self, reference_service):
        """Test earthquake command with no data"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"features": []}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            response = await reference_service.handle_earthquake_command([], {})
            
            assert "No significant earthquakes" in response
    
    @pytest.mark.asyncio
    async def test_earthquake_command_with_data(self, reference_service):
        """Test earthquake command with mock data"""
        mock_earthquake_data = {
            "features": [
                {
                    "properties": {
                        "mag": 5.2,
                        "place": "Test Location",
                        "time": int(datetime.now().timestamp() * 1000),
                        "url": "http://example.com"
                    },
                    "geometry": {
                        "coordinates": [-120.0, 35.0, 10.0]
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_earthquake_data
            mock_get.return_value.__aenter__.return_value = mock_response
            
            response = await reference_service.handle_earthquake_command([], {})
            
            assert "Recent Significant Earthquakes" in response
            assert "M5.2" in response
            assert "Test Location" in response
    
    @pytest.mark.asyncio
    async def test_sun_command(self, reference_service):
        """Test sun information command"""
        context = {'sender_id': 'test_user'}
        
        response = await reference_service.handle_sun_command([], context)
        
        assert "Sun Information" in response
        assert "Sunrise:" in response
        assert "Sunset:" in response
        assert "Daylight:" in response
        assert "Current:" in response
    
    @pytest.mark.asyncio
    async def test_moon_command(self, reference_service):
        """Test moon phase command"""
        response = await reference_service.handle_moon_command([], {})
        
        assert "Moon Information" in response
        assert "Phase:" in response
        assert "Illumination:" in response
        assert "%" in response
    
    @pytest.mark.asyncio
    async def test_tide_command(self, reference_service):
        """Test tide information command"""
        response = await reference_service.handle_tide_command([], {})
        
        assert "Tide Information" in response
        assert "location-specific data" in response
        assert "NOAA" in response
    
    def test_calculate_band_condition(self, reference_service):
        """Test HF band condition calculation"""
        # Test high solar flux, daytime, high band
        condition = reference_service._calculate_band_condition(200, 15, True)
        assert condition in ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
        
        # Test low solar flux, nighttime, low band
        condition = reference_service._calculate_band_condition(80, 80, False)
        assert condition in ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
    
    def test_get_condition_emoji(self, reference_service):
        """Test condition emoji mapping"""
        assert reference_service._get_condition_emoji("Excellent") == "🟢"
        assert reference_service._get_condition_emoji("Good") == "🟢"
        assert reference_service._get_condition_emoji("Fair") == "🟡"
        assert reference_service._get_condition_emoji("Poor") == "🟠"
        assert reference_service._get_condition_emoji("Very Poor") == "🔴"
        assert reference_service._get_condition_emoji("Unknown") == "⚪"
    
    def test_calculate_sun_times(self, reference_service):
        """Test sunrise/sunset calculation"""
        location = LocationData(latitude=40.7128, longitude=-74.0060)  # NYC
        date = datetime(2024, 6, 21).date()  # Summer solstice
        
        sunrise, sunset = reference_service._calculate_sun_times(location, date)
        
        assert isinstance(sunrise, datetime)
        assert isinstance(sunset, datetime)
        assert sunrise < sunset
        assert sunrise.tzinfo == timezone.utc
        assert sunset.tzinfo == timezone.utc
    
    def test_calculate_moon_phase(self, reference_service):
        """Test moon phase calculation"""
        test_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        
        phase_info = reference_service._calculate_moon_phase(test_date)
        
        assert 'name' in phase_info
        assert 'emoji' in phase_info
        assert 'illumination' in phase_info
        assert 'cycle_position' in phase_info
        
        assert 0 <= phase_info['illumination'] <= 100
        assert 0 <= phase_info['cycle_position'] <= 1
        assert phase_info['name'] in [
            "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
            "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"
        ]
    
    def test_get_next_moon_phase(self, reference_service):
        """Test next moon phase calculation"""
        test_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        
        next_phase = reference_service._get_next_moon_phase(test_date)
        
        assert next_phase is not None
        assert 'name' in next_phase
        assert 'date' in next_phase
        assert next_phase['date'] > test_date
        assert next_phase['name'] in [
            "New Moon", "First Quarter", "Full Moon", "Last Quarter"
        ]
    
    @pytest.mark.asyncio
    async def test_get_user_location_from_db(self, reference_service):
        """Test getting user location from database"""
        with patch('src.core.database.get_database') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (35.0, -120.0)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            location = await reference_service._get_user_location('test_user')
            
            assert location.latitude == 35.0
            assert location.longitude == -120.0
    
    @pytest.mark.asyncio
    async def test_get_user_location_default(self, reference_service):
        """Test getting default location when user location not found"""
        with patch('src.core.database.get_database') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            location = await reference_service._get_user_location('test_user')
            
            assert location.latitude == 40.7128  # Default NYC
            assert location.longitude == -74.0060
    
    def test_cache_functionality(self, reference_service):
        """Test data caching"""
        # Initially no cache
        assert reference_service.solar_data_cache is None
        assert len(reference_service.cache_timestamps) == 0
        
        # Set cache data
        solar_data = SolarData(solar_flux=150.0, updated=datetime.now())
        reference_service.solar_data_cache = solar_data
        reference_service.cache_timestamps['solar_data'] = datetime.now()
        
        # Check cache status
        status = reference_service.get_cache_status()
        assert 'solar_data' in status
        assert 'last_updated' in status['solar_data']
        assert 'age_minutes' in status['solar_data']
        assert 'expired' in status['solar_data']
    
    def test_clear_cache(self, reference_service):
        """Test cache clearing"""
        # Set some cache data
        reference_service.solar_data_cache = SolarData(solar_flux=150.0)
        reference_service.earthquake_cache = [EarthquakeData(
            magnitude=5.0, location="Test", depth=10.0, 
            time=datetime.now(), latitude=35.0, longitude=-120.0
        )]
        reference_service.cache_timestamps['test'] = datetime.now()
        
        # Clear cache
        reference_service.clear_cache()
        
        # Verify cache is cleared
        assert reference_service.solar_data_cache is None
        assert len(reference_service.earthquake_cache) == 0
        assert len(reference_service.cache_timestamps) == 0


class TestDataStructures:
    """Test data structure classes"""
    
    def test_solar_data_creation(self):
        """Test SolarData creation"""
        data = SolarData(
            solar_flux=150.5,
            sunspot_number=100,
            a_index=15,
            k_index=3,
            x_ray_class="C1.2",
            geomagnetic_field="Quiet",
            updated=datetime.now()
        )
        
        assert data.solar_flux == 150.5
        assert data.sunspot_number == 100
        assert data.a_index == 15
        assert data.geomagnetic_field == "Quiet"
    
    def test_earthquake_data_creation(self):
        """Test EarthquakeData creation"""
        data = EarthquakeData(
            magnitude=5.2,
            location="Test Location",
            depth=10.5,
            time=datetime.now(timezone.utc),
            latitude=35.0,
            longitude=-120.0,
            url="http://example.com"
        )
        
        assert data.magnitude == 5.2
        assert data.location == "Test Location"
        assert data.depth == 10.5
        assert data.latitude == 35.0
        assert data.longitude == -120.0
        assert data.url == "http://example.com"
    
    def test_location_data_creation(self):
        """Test LocationData creation"""
        data = LocationData(
            latitude=40.7128,
            longitude=-74.0060,
            timezone_offset=-5.0,
            elevation=10.0
        )
        
        assert data.latitude == 40.7128
        assert data.longitude == -74.0060
        assert data.timezone_offset == -5.0
        assert data.elevation == 10.0