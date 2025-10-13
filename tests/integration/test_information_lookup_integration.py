"""
Integration tests for Information Lookup Service

Tests the integration between the information lookup service and the comprehensive command handler
to ensure all information lookup commands work properly end-to-end.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.services.bot.comprehensive_command_handler import ComprehensiveCommandHandler
from src.services.bot.interactive_bot_service import InteractiveBotService
from src.models.message import Message, MessageType


class TestInformationLookupIntegration:
    """Integration tests for information lookup service"""
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return {
            'default_location': (40.7128, -74.0060),  # NYC
            'weather': {
                'enabled': True,
                'api_key': 'test_key'
            },
            'auto_response': {
                'enabled': True,
                'emergency_keywords': ['help', 'emergency'],
                'greeting_enabled': True,
                'greeting_message': 'Welcome to the mesh network!',
                'greeting_delay_hours': 24,
                'emergency_escalation_delay': 300,
                'response_rate_limit': 10,
                'cooldown_seconds': 30
            },
            'commands': {
                'enabled': True,
                'help_enabled': True,
                'permissions_enabled': False
            }
        }
    
    @pytest.fixture
    def bot_service(self, config):
        """Create interactive bot service instance"""
        return InteractiveBotService(config)
    
    @pytest.fixture
    def command_handler(self, config):
        """Create comprehensive command handler instance"""
        return ComprehensiveCommandHandler(config)
    
    @pytest.fixture
    def test_message(self):
        """Create test message"""
        return Message(
            id="test_msg_001",
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="wx",
            timestamp=datetime.utcnow(),
            message_type=MessageType.TEXT,
            interface_id="test_interface"
        )
    
    @pytest.mark.asyncio
    async def test_weather_command_integration(self, command_handler, test_message):
        """Test weather command integration"""
        # Test basic weather command
        response = await command_handler.handle_command('wx', [], {
            'sender_id': '!12345678',
            'sender_name': 'TestUser',
            'channel': 0,
            'is_direct_message': False,
            'is_admin': False,
            'is_moderator': False,
            'user_permissions': {'user'},
            'message_timestamp': datetime.utcnow(),
            'interface_id': 'test_interface'
        })
        
        assert '🌤️ **Current Weather**' in response
        assert '72°F (22°C)' in response
        assert 'Partly Cloudy' in response
        
        # Test weather command with location
        response = await command_handler.handle_command('wx', ['Seattle'], {
            'sender_id': '!12345678',
            'sender_name': 'TestUser',
            'channel': 0,
            'is_direct_message': False,
            'is_admin': False,
            'is_moderator': False,
            'user_permissions': {'user'},
            'message_timestamp': datetime.utcnow(),
            'interface_id': 'test_interface'
        })
        
        assert '🌤️ **Current Weather**' in response
        assert 'Seattle' in response
    
    @pytest.mark.asyncio
    async def test_location_commands_integration(self, command_handler):
        """Test location-based commands integration"""
        context = {
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
        
        # Test whereami command
        response = await command_handler.handle_command('whereami', [], context)
        assert '❌ No location information available' in response or '📍' in response
        
        # Test howfar command without arguments
        response = await command_handler.handle_command('howfar', [], context)
        assert '❌ Usage: howfar <node_id>' in response
        
        # Test howfar command with arguments
        response = await command_handler.handle_command('howfar', ['!87654321'], context)
        assert '❌' in response or '📏' in response  # Either error or distance calculation
        
        # Test howtall command
        response = await command_handler.handle_command('howtall', ['!12345678'], context)
        assert '❌' in response or '⛰️' in response  # Either error or altitude info
    
    @pytest.mark.asyncio
    async def test_node_status_commands_integration(self, command_handler):
        """Test node status commands integration"""
        context = {
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
        
        # Test whoami command
        response = await command_handler.handle_command('whoami', [], context)
        assert '❌' in response or '👤' in response  # Either error or node info
        
        # Test whois command without arguments
        response = await command_handler.handle_command('whois', [], context)
        assert '❌ Usage: whois <node_id>' in response
        
        # Test status command
        response = await command_handler.handle_command('status', [], context)
        assert '📊 **System Status**' in response
        assert 'System Status' in response
        
        # Test lheard command
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                ('!12345678', 'TEST1', '2024-01-01T12:00:00', 10.5, -50, 1, 80),
                ('!87654321', 'TEST2', '2024-01-01T11:30:00', 8.2, -55, 2, 65)
            ]
            mock_db.return_value.cursor.return_value = mock_cursor
            
            response = await command_handler.handle_command('lheard', [], context)
            assert '📡 **Recently Heard Nodes**' in response
            assert 'TEST1' in response
    
    @pytest.mark.asyncio
    async def test_network_stats_commands_integration(self, command_handler):
        """Test network statistics commands integration"""
        context = {
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
        
        # Test sitrep command
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                (25,),  # total nodes
                (15,),  # nodes last day
                (8,),   # nodes last hour
                (8.5, -52.0),  # avg snr, rssi
                (4,)    # max hop count
            ]
            mock_db.return_value.cursor.return_value = mock_cursor
            
            response = await command_handler.handle_command('sitrep', [], context)
            assert '📊 **Network Situation Report**' in response
            assert 'Total Nodes: 25' in response
        
        # Test sysinfo command
        response = await command_handler.handle_command('sysinfo', [], context)
        assert '🖥️ **System Information**' in response
        assert 'ZephyrGate Gateway' in response
        
        # Test leaderboard command
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                ('NODE1', '!11111111', 95),
                ('NODE2', '!22222222', 87)
            ]
            mock_db.return_value.cursor.return_value = mock_cursor
            
            response = await command_handler.handle_command('leaderboard', ['battery'], context)
            assert '🔋 **Battery Leaderboard**' in response
            assert 'NODE1**: 95%' in response
    
    @pytest.mark.asyncio
    async def test_bot_service_integration(self, bot_service, test_message):
        """Test integration with interactive bot service"""
        await bot_service.start()
        
        try:
            # Test weather command through bot service
            test_message.content = "wx"
            response = await bot_service.handle_message(test_message)
            
            if response:
                assert '🌤️' in response.content
            
            # Test location command through bot service
            test_message.content = "whereami"
            response = await bot_service.handle_message(test_message)
            
            if response:
                assert '❌' in response.content or '📍' in response.content
            
            # Test status command through bot service
            test_message.content = "status"
            response = await bot_service.handle_message(test_message)
            
            if response:
                assert '📊' in response.content
                
        finally:
            await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, command_handler):
        """Test error handling in integration scenarios"""
        context = {
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
        
        # Test with database errors
        with patch('src.services.bot.information_lookup_service.get_database') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            response = await command_handler.handle_command('lheard', [], context)
            assert '❌ Error retrieving heard nodes' in response
        
        # Test with invalid node IDs
        response = await command_handler.handle_command('whois', ['invalid_node'], context)
        assert '❌' in response
        
        # Test with missing arguments
        response = await command_handler.handle_command('howfar', [], context)
        assert '❌ Usage: howfar <node_id>' in response
    
    @pytest.mark.asyncio
    async def test_command_help_integration(self, command_handler):
        """Test help system integration for information commands"""
        context = {
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
        
        # Test general help
        response = await command_handler.handle_command('help', [], context)
        assert 'Available Commands' in response
        assert 'Weather:' in response
        assert 'Information:' in response
        
        # Test specific command help
        response = await command_handler.handle_command('help', ['wx'], context)
        assert 'Weather' in response
        assert 'Usage:' in response
        
        response = await command_handler.handle_command('help', ['whereami'], context)
        assert 'location' in response.lower()
        assert 'Usage:' in response


if __name__ == '__main__':
    pytest.main([__file__])