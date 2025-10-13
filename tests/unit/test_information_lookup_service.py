"""
Unit tests for Information Lookup Service

Tests the information lookup service functionality including:
- Weather command integration
- Node status and signal reporting commands
- Network statistics and mesh information commands
- Location-based information services
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.bot.information_lookup_service import (
    InformationLookupService, NodeInfo, NetworkStats
)


class TestInformationLookupService:
    """Test cases for InformationLookupService"""
    
    @pytest.fixture
    def service(self):
        """Create information lookup service instance"""
        config = {
            'default_location': (40.7128, -74.0060),  # NYC
            'weather': {
                'enabled': True,
                'api_key': 'test_key'
            }
        }
        return InformationLookupService(config)
    
    @pytest.fixture
    def mock_context(self):
        """Create mock command context"""
        return {
            'sender_id': '!12345678',
            'sender_name': 'TestUser',
            'channel': 0,
            'is_direct_message': False,
            'is_admin': False,
            'is_moderator': False,
            'user_permissions': {'user'},
            'message_timestamp': datetime.utcnow(),
            'interface_id': 'test_interface'
        }
    
    @pytest.fixture
    def sample_node_info(self):
        """Create sample node info"""
        return NodeInfo(
            node_id='!12345678',
            short_name='TEST',
            long_name='Test Node',
            last_seen=datetime.utcnow(),
            location=(40.7128, -74.0060),
            altitude=100.0,
            battery_level=85,
            voltage=4.2,
            snr=12.5,
            rssi=-45,
            hop_count=2,
            hardware_model='TBEAM',
            firmware_version='2.3.2',
            role='CLIENT'
        )
    
    def test_service_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.default_location == (40.7128, -74.0060)
        assert service.EARTH_RADIUS_KM == 6371.0
        assert service.cache_duration.total_seconds() == 300  # 5 minutes
    
    def test_set_communication_interface(self, service):
        """Test setting communication interface"""
        mock_comm = Mock()
        service.set_communication_interface(mock_comm)
        assert service.communication == mock_comm
    
    @pytest.mark.asyncio
    async def test_handle_weather_command_basic(self, service, mock_context):
        """Test basic weather command handling"""
        with patch.object(service, '_request_weather_data') as mock_request:
            mock_request.return_value = {
                'location': 'Test Location',
                'temperature': 72,
                'temperature_c': 22,
                'conditions': 'Sunny',
                'wind_speed': 5,
                'wind_direction': 'NW',
                'humidity': 60,
                'pressure': 30.15,
                'visibility': 10,
                'forecast': []
            }
            
            result = await service.handle_weather_command('wx', [], mock_context)
            
            assert '🌤️ **Current Weather**' in result
            assert 'Test Location' in result
            assert '72°F (22°C)' in result
            assert 'Sunny' in result
    
    @pytest.mark.asyncio
    async def test_handle_weather_command_with_location(self, service, mock_context):
        """Test weather command with location argument"""
        with patch.object(service, '_request_weather_data') as mock_request:
            mock_request.return_value = {
                'location': 'Seattle',
                'temperature': 65,
                'temperature_c': 18,
                'conditions': 'Cloudy',
                'wind_speed': 8,
                'wind_direction': 'W',
                'humidity': 75,
                'pressure': 29.95,
                'visibility': 8,
                'forecast': []
            }
            
            result = await service.handle_weather_command('wx', ['Seattle'], mock_context)
            
            assert 'Seattle' in result
            assert '65°F (18°C)' in result
    
    @pytest.mark.asyncio
    async def test_handle_weather_command_forecast(self, service, mock_context):
        """Test weather forecast command"""
        with patch.object(service, '_request_weather_data') as mock_request:
            mock_request.return_value = {
                'location': 'Test Location',
                'forecast': [
                    {'day': 'Today', 'high': 75, 'low': 60, 'conditions': 'Sunny'},
                    {'day': 'Tomorrow', 'high': 78, 'low': 62, 'conditions': 'Partly Cloudy'}
                ]
            }
            
            result = await service.handle_weather_command('wxc', [], mock_context)
            
            assert '📅 **Weather Forecast**' in result
            assert 'Today' in result
            assert '75°/60°' in result
    
    @pytest.mark.asyncio
    async def test_handle_whoami_command(self, service, mock_context, sample_node_info):
        """Test whoami command"""
        with patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_node.return_value = sample_node_info
            
            result = await service.handle_node_status_command('whoami', [], mock_context)
            
            assert '👤 **Your Node Information**' in result
            assert '!12345678' in result
            assert 'TEST' in result
            assert 'Test Node' in result
            assert '85%' in result  # Battery level
            assert 'TBEAM' in result  # Hardware
    
    @pytest.mark.asyncio
    async def test_handle_whois_command(self, service, mock_context, sample_node_info):
        """Test whois command"""
        with patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_node.return_value = sample_node_info
            
            result = await service.handle_node_status_command('whois', ['!87654321'], mock_context)
            
            assert '👤 **Node Information: !87654321**' in result
    
    @pytest.mark.asyncio
    async def test_handle_whois_command_no_args(self, service, mock_context):
        """Test whois command without arguments"""
        result = await service.handle_node_status_command('whois', [], mock_context)
        
        assert '❌ Usage: whois <node_id>' in result
    
    @pytest.mark.asyncio
    async def test_handle_lheard_command(self, service, mock_context):
        """Test lheard command"""
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                ('!12345678', 'TEST1', '2024-01-01T12:00:00Z', 10.5, -50, 1, 80),
                ('!87654321', 'TEST2', '2024-01-01T11:30:00Z', 8.2, -55, 2, 65)
            ]
            mock_db.return_value.cursor.return_value = mock_cursor
            
            result = await service.handle_node_status_command('lheard', [], mock_context)
            
            assert '📡 **Recently Heard Nodes**' in result
            assert 'TEST1' in result
            assert 'TEST2' in result
            assert 'SNR 10.5dB' in result
    
    @pytest.mark.asyncio
    async def test_handle_sitrep_command(self, service, mock_context):
        """Test sitrep command"""
        mock_stats = NetworkStats(
            total_nodes=25,
            active_nodes=15,
            nodes_last_hour=8,
            nodes_last_day=15,
            total_messages=1250,
            messages_last_hour=45,
            messages_last_day=320,
            average_snr=8.5,
            average_rssi=-52.0,
            network_diameter=4
        )
        
        with patch.object(service, '_get_network_stats') as mock_get_stats:
            mock_get_stats.return_value = mock_stats
            
            result = await service.handle_network_stats_command('sitrep', [], mock_context)
            
            assert '📊 **Network Situation Report**' in result
            assert 'Total Nodes: 25' in result
            assert 'Active Nodes: 15' in result
            assert 'Messages (1h): 45' in result
            assert 'Avg SNR: 8.5dB' in result
    
    @pytest.mark.asyncio
    async def test_handle_status_command(self, service, mock_context, sample_node_info):
        """Test status command"""
        mock_stats = NetworkStats(
            total_nodes=20,
            active_nodes=12,
            nodes_last_hour=6,
            nodes_last_day=12,
            total_messages=800,
            messages_last_hour=25,
            messages_last_day=200
        )
        
        with patch.object(service, '_get_network_stats') as mock_get_stats, \
             patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_stats.return_value = mock_stats
            mock_get_node.return_value = sample_node_info
            
            result = await service.handle_node_status_command('status', [], mock_context)
            
            assert '📊 **System Status**' in result
            assert '12 active nodes' in result
            assert '25 msgs/hour' in result
            assert 'TEST' in result  # User's node name
    
    @pytest.mark.asyncio
    async def test_handle_whereami_command(self, service, mock_context, sample_node_info):
        """Test whereami command"""
        with patch.object(service, '_get_user_location') as mock_get_location, \
             patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_location.return_value = (40.7128, -74.0060)
            mock_get_node.return_value = sample_node_info
            
            result = await service.handle_location_command('whereami', [], mock_context)
            
            assert '📍 **Your Location**' in result
            assert '40.712800, -74.006000' in result
            assert 'Altitude: 100m' in result
    
    @pytest.mark.asyncio
    async def test_handle_whereami_command_no_location(self, service, mock_context):
        """Test whereami command when no location available"""
        with patch.object(service, '_get_user_location') as mock_get_location:
            mock_get_location.return_value = None
            
            result = await service.handle_location_command('whereami', [], mock_context)
            
            assert '❌ No location information available' in result
    
    @pytest.mark.asyncio
    async def test_handle_howfar_command(self, service, mock_context):
        """Test howfar command"""
        with patch.object(service, '_get_user_location') as mock_get_location, \
             patch.object(service, '_get_node_info') as mock_get_node:
            # User location (NYC)
            mock_get_location.side_effect = [
                (40.7128, -74.0060),  # User location
                (34.0522, -118.2437)  # Target location (LA)
            ]
            
            # Target node info
            target_node = NodeInfo(
                node_id='!87654321',
                short_name='LA_NODE',
                long_name='Los Angeles Node',
                last_seen=datetime.utcnow(),
                location=(34.0522, -118.2437)
            )
            mock_get_node.return_value = target_node
            
            result = await service.handle_location_command('howfar', ['!87654321'], mock_context)
            
            assert '📏 **Distance Calculation**' in result
            assert 'LA_NODE' in result
            assert 'Distance:' in result
            assert 'km' in result
            assert 'Bearing:' in result
    
    @pytest.mark.asyncio
    async def test_handle_howfar_command_no_args(self, service, mock_context):
        """Test howfar command without arguments"""
        result = await service.handle_location_command('howfar', [], mock_context)
        
        assert '❌ Usage: howfar <node_id>' in result
    
    @pytest.mark.asyncio
    async def test_handle_howtall_command(self, service, mock_context, sample_node_info):
        """Test howtall command"""
        with patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_node.return_value = sample_node_info
            
            result = await service.handle_location_command('howtall', ['!12345678'], mock_context)
            
            assert '⛰️ **Altitude Information**' in result
            assert 'TEST' in result
            assert '100m (328ft)' in result
            assert 'Low elevation (ground level)' in result
    
    @pytest.mark.asyncio
    async def test_handle_leaderboard_battery(self, service, mock_context):
        """Test battery leaderboard command"""
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                ('NODE1', '!11111111', 95),
                ('NODE2', '!22222222', 87),
                ('NODE3', '!33333333', 72)
            ]
            mock_db.return_value.cursor.return_value = mock_cursor
            
            result = await service.handle_network_stats_command('leaderboard', ['battery'], mock_context)
            
            assert '🔋 **Battery Leaderboard**' in result
            assert 'NODE1**: 95%' in result
            assert 'NODE2**: 87%' in result
    
    def test_calculate_distance(self, service):
        """Test distance calculation"""
        # NYC to LA
        nyc = (40.7128, -74.0060)
        la = (34.0522, -118.2437)
        
        distance = service._calculate_distance(nyc, la)
        
        # Should be approximately 3944 km
        assert 3900 < distance < 4000
    
    def test_calculate_bearing(self, service):
        """Test bearing calculation"""
        # NYC to LA (should be roughly west/southwest)
        nyc = (40.7128, -74.0060)
        la = (34.0522, -118.2437)
        
        bearing = service._calculate_bearing(nyc, la)
        
        # Should be roughly 274 degrees (west-northwest)
        assert 270 < bearing < 280
    
    def test_bearing_to_compass(self, service):
        """Test bearing to compass conversion"""
        assert service._bearing_to_compass(0) == "N"
        assert service._bearing_to_compass(90) == "E"
        assert service._bearing_to_compass(180) == "S"
        assert service._bearing_to_compass(270) == "W"
        assert service._bearing_to_compass(45) == "NE"
        assert service._bearing_to_compass(315) == "NW"
    
    def test_format_time_ago(self, service):
        """Test time ago formatting"""
        now = datetime.utcnow()
        
        # Just now
        assert service._format_time_ago(now) == "Just now"
        
        # Minutes ago
        minutes_ago = now - timedelta(minutes=5)
        assert service._format_time_ago(minutes_ago) == "5m ago"
        
        # Hours ago
        hours_ago = now - timedelta(hours=2)
        assert service._format_time_ago(hours_ago) == "2h ago"
        
        # Days ago
        days_ago = now - timedelta(days=3)
        assert service._format_time_ago(days_ago) == "3d ago"
    
    @pytest.mark.asyncio
    async def test_error_handling_weather_command(self, service, mock_context):
        """Test error handling in weather command"""
        with patch.object(service, '_request_weather_data') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            result = await service.handle_weather_command('wx', [], mock_context)
            
            assert '❌ Error retrieving weather information' in result
    
    @pytest.mark.asyncio
    async def test_error_handling_node_command(self, service, mock_context):
        """Test error handling in node status command"""
        with patch.object(service, '_get_node_info') as mock_get_node:
            mock_get_node.side_effect = Exception("Database Error")
            
            result = await service.handle_node_status_command('whoami', [], mock_context)
            
            assert '❌ Error retrieving node status' in result
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, service, sample_node_info):
        """Test node info caching"""
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (
                '!12345678', 'TEST', 'Test Node', '2024-01-01T12:00:00Z',
                40.7128, -74.0060, 100.0, 85, 4.2, 12.5, -45, 2,
                'TBEAM', '2.3.2', 'CLIENT'
            )
            mock_db.return_value.cursor.return_value = mock_cursor
            
            # First call should hit database
            result1 = await service._get_node_info('!12345678')
            assert result1 is not None
            assert mock_cursor.fetchone.call_count == 1
            
            # Second call should use cache
            result2 = await service._get_node_info('!12345678')
            assert result2 is not None
            assert mock_cursor.fetchone.call_count == 1  # No additional call
            
            # Results should be the same
            assert result1.node_id == result2.node_id
            assert result1.short_name == result2.short_name


if __name__ == '__main__':
    pytest.main([__file__])