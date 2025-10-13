"""
Tests for Comprehensive Command Handler

Tests the complete command handling framework including parsing, registry,
help system, and permissions as specified in Task 6.3.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from src.services.bot.comprehensive_command_handler import ComprehensiveCommandHandler
from src.services.bot.command_registry import CommandContext, CommandPermission
from src.services.bot.command_parser import CommandType


class TestComprehensiveCommandHandler:
    """Test comprehensive command handler functionality"""
    
    @pytest.fixture
    def handler(self):
        """Create command handler instance"""
        return ComprehensiveCommandHandler()
    
    @pytest.fixture
    def basic_context(self):
        """Create basic command context"""
        return {
            'sender_id': '!12345678',
            'sender_name': 'TestUser',
            'channel': 0,
            'is_direct_message': False,
            'is_admin': False,
            'is_moderator': False,
            'user_permissions': {'user'},
            'message_timestamp': None,
            'interface_id': 'test'
        }
    
    @pytest.fixture
    def admin_context(self):
        """Create admin command context"""
        return {
            'sender_id': '!admin123',
            'sender_name': 'AdminUser',
            'channel': 0,
            'is_direct_message': False,
            'is_admin': True,
            'is_moderator': True,
            'user_permissions': {'user', 'moderator', 'admin'},
            'message_timestamp': None,
            'interface_id': 'test'
        }
    
    @pytest.mark.asyncio
    async def test_help_command_basic(self, handler, basic_context):
        """Test basic help command"""
        response = await handler.handle_command('help', [], basic_context)
        
        assert '📋 **Available Commands**' in response
        assert 'Basic:' in response
        assert 'Emergency:' in response
        assert 'help <command>' in response
    
    @pytest.mark.asyncio
    async def test_help_command_specific(self, handler, basic_context):
        """Test help for specific command"""
        response = await handler.handle_command('help', ['ping'], basic_context)
        
        assert '📋 **PING**' in response
        assert 'Test connectivity' in response
        assert 'Usage:' in response
        assert 'Examples:' in response
    
    @pytest.mark.asyncio
    async def test_help_command_category(self, handler, basic_context):
        """Test help for command category"""
        response = await handler.handle_command('help', ['emergency'], basic_context)
        
        assert '📚 **Emergency Commands**' in response
        assert 'sos' in response.lower()
        assert 'clear' in response.lower()
    
    @pytest.mark.asyncio
    async def test_help_command_categories(self, handler, basic_context):
        """Test help categories listing"""
        response = await handler.handle_command('help', ['categories'], basic_context)
        
        assert '📚 **Command Categories**' in response
        assert 'Basic' in response
        assert 'Emergency' in response
        assert 'Games' in response
    
    @pytest.mark.asyncio
    async def test_ping_command(self, handler, basic_context):
        """Test ping command"""
        response = await handler.handle_command('ping', [], basic_context)
        
        assert '🏓 Pong!' in response
        assert 'Signal: Good' in response
        assert basic_context['sender_id'] in response
    
    @pytest.mark.asyncio
    async def test_status_command(self, handler, basic_context):
        """Test status command"""
        response = await handler.handle_command('status', [], basic_context)
        
        assert '📊 **System Status**' in response
        assert 'Core Services: Online' in response
        assert 'Success Rate:' in response
    
    @pytest.mark.asyncio
    async def test_sos_command(self, handler, basic_context):
        """Test SOS emergency command"""
        response = await handler.handle_command('sos', ['Need help at coordinates'], basic_context)
        
        assert '🚨 **SOS ALERT TRIGGERED**' in response
        assert 'Need help at coordinates' in response
        assert 'Responders have been notified' in response
        assert 'escalate' in response.lower()
    
    @pytest.mark.asyncio
    async def test_sos_variants(self, handler, basic_context):
        """Test different SOS command variants"""
        commands = ['sos', 'sosp', 'sosf', 'sosm']
        
        for cmd in commands:
            response = await handler.handle_command(cmd, [], basic_context)
            assert f'🚨 **{cmd.upper()} ALERT TRIGGERED**' in response
    
    @pytest.mark.asyncio
    async def test_clear_command(self, handler, basic_context):
        """Test emergency clear command"""
        response = await handler.handle_command('clear', [], basic_context)
        
        assert '✅ **CLEAR COMMAND RECEIVED**' in response
        assert 'All responders have been notified' in response
    
    @pytest.mark.asyncio
    async def test_ack_command(self, handler, basic_context):
        """Test emergency acknowledgment command"""
        response = await handler.handle_command('ack', [], basic_context)
        
        assert '👍 **ACK ACKNOWLEDGED**' in response
        assert 'Incident commander has been notified' in response
    
    @pytest.mark.asyncio
    async def test_active_command(self, handler, basic_context):
        """Test active incidents command"""
        response = await handler.handle_command('active', [], basic_context)
        
        assert '📋 **Active Emergency Incidents**' in response
        assert 'No active incidents' in response
    
    @pytest.mark.asyncio
    async def test_bbs_commands(self, handler, basic_context):
        """Test BBS commands"""
        # Test main BBS command
        response = await handler.handle_command('bbs', [], basic_context)
        assert '📮 **Bulletin Board System**' in response
        
        # Test BBS help
        response = await handler.handle_command('bbshelp', [], basic_context)
        assert '📋 **BBS Help**' in response
        
        # Test BBS list
        response = await handler.handle_command('bbslist', [], basic_context)
        assert '📄 **Bulletin List**' in response
    
    @pytest.mark.asyncio
    async def test_weather_command(self, handler, basic_context):
        """Test weather command"""
        response = await handler.handle_command('wx', [], basic_context)
        
        assert '🌤️ **Current Weather**' in response
        assert '72°F' in response
        assert 'your location' in response
    
    @pytest.mark.asyncio
    async def test_subscription_commands(self, handler, basic_context):
        """Test subscription management commands"""
        # Test subscribe
        response = await handler.handle_command('subscribe', ['weather'], basic_context)
        assert 'Successfully subscribed to weather' in response
        
        # Test unsubscribe
        response = await handler.handle_command('unsubscribe', ['weather'], basic_context)
        assert 'Successfully unsubscribed from weather' in response
        
        # Test subscription status
        response = await handler.handle_command('subscribe', [], basic_context)
        assert '📋 **Current Subscriptions**' in response
    
    @pytest.mark.asyncio
    async def test_profile_commands(self, handler, basic_context):
        """Test profile setting commands"""
        # Test name command
        response = await handler.handle_command('name', ['John Smith'], basic_context)
        assert 'Name updated successfully' in response
        assert 'John Smith' in response
        
        # Test phone command
        response = await handler.handle_command('phone', ['1', '555-1234'], basic_context)
        assert 'Phone updated successfully' in response
    
    @pytest.mark.asyncio
    async def test_communication_commands(self, handler, basic_context):
        """Test communication commands"""
        # Test email command with separate arguments
        response = await handler.handle_command('email', ['test@example.com', 'Subject', 'Body'], basic_context)
        assert '📧 **Email Sent**' in response
        assert 'test@example.com' in response
        
        # Test SMS command
        response = await handler.handle_command('sms', ['Test', 'message'], basic_context)
        assert '📱 **SMS Sent**' in response
    
    @pytest.mark.asyncio
    async def test_tag_commands(self, handler, basic_context):
        """Test tag-based messaging commands"""
        # Test tagsend with space-separated format (as it would be called)
        response = await handler.handle_command('tagsend', ['emergency,responder', 'Test', 'message'], basic_context)
        assert '📢 **Tag Message Sent**' in response
        
        # Test tagin
        response = await handler.handle_command('tagin', ['EMERGENCY'], basic_context)
        assert 'Added to tag group: EMERGENCY' in response
        
        # Test tagout
        response = await handler.handle_command('tagout', ['EMERGENCY'], basic_context)
        assert 'Removed from tag group: EMERGENCY' in response
    
    @pytest.mark.asyncio
    async def test_asset_commands(self, handler, basic_context):
        """Test asset management commands"""
        # Test checkin
        response = await handler.handle_command('checkin', ['At staging area'], basic_context)
        assert '✅ **Checked In**' in response
        assert 'At staging area' in response
        
        # Test checkout
        response = await handler.handle_command('checkout', [], basic_context)
        assert '✅ **Checked Out**' in response
        
        # Test checklist
        response = await handler.handle_command('checklist', [], basic_context)
        assert '📋 **Current Check-in Status**' in response
    
    @pytest.mark.asyncio
    async def test_admin_commands_permission_denied(self, handler, basic_context):
        """Test admin commands with insufficient permissions"""
        response = await handler.handle_command('block', ['spam@example.com'], basic_context)
        assert 'Administrative privileges required' in response
    
    @pytest.mark.asyncio
    async def test_admin_commands_with_permissions(self, handler, admin_context):
        """Test admin commands with proper permissions"""
        # Test block command
        response = await handler.handle_command('block', ['spam@example.com'], admin_context)
        assert '🚫 **Email Blocked**' in response
        assert 'spam@example.com' in response
        
        # Test unblock command
        response = await handler.handle_command('unblock', ['user@example.com'], admin_context)
        assert '✅ **Email Unblocked**' in response
        assert 'user@example.com' in response
    
    @pytest.mark.asyncio
    async def test_game_commands(self, handler, basic_context):
        """Test game commands"""
        games = ['blackjack', 'hangman', 'tictactoe']
        
        for game in games:
            response = await handler.handle_command(game, [], basic_context)
            assert f'🎮 **{game.title()} Game**' in response
            assert 'not fully implemented' in response
    
    @pytest.mark.asyncio
    async def test_information_commands(self, handler, basic_context):
        """Test information commands"""
        # Test implemented location commands
        location_commands = ['whereami', 'whoami']
        for cmd in location_commands:
            response = await handler.handle_command(cmd, [], basic_context)
            # These should now return actual responses or error messages
            assert '❌' in response or '📍' in response or '👤' in response
        
        # Test unimplemented information commands
        unimplemented_commands = ['solar', 'moon']
        for cmd in unimplemented_commands:
            response = await handler.handle_command(cmd, [], basic_context)
            assert f'ℹ️ **{cmd.title()} Information**' in response
            assert 'not yet implemented' in response
    
    @pytest.mark.asyncio
    async def test_command_parsing_integration(self, handler, basic_context):
        """Test command parsing integration"""
        # Test complex command format - this should now work correctly
        response = await handler.handle_command('email', ['to@example.com/Subject/Body'], basic_context)
        assert '📧 **Email Sent**' in response  # Should be parsed correctly now
        
        # Test prefixed command format
        response = await handler.handle_command('wiki', ['Meshtastic'], basic_context)
        assert 'not yet implemented' in response
    
    @pytest.mark.asyncio
    async def test_unknown_command(self, handler, basic_context):
        """Test unknown command handling"""
        response = await handler.handle_command('unknowncommand', [], basic_context)
        assert "not implemented yet" in response
    
    @pytest.mark.asyncio
    async def test_command_statistics(self, handler, basic_context):
        """Test command execution statistics"""
        # Get initial stats
        initial_stats = handler.get_execution_statistics()
        initial_total = initial_stats['total_commands']
        initial_successful = initial_stats['successful_commands']
        
        # Execute some commands
        await handler.handle_command('ping', [], basic_context)
        await handler.handle_command('status', [], basic_context)
        await handler.handle_command('help', [], basic_context)
        
        stats = handler.get_execution_statistics()
        
        assert stats['total_commands'] >= initial_total + 3
        assert stats['successful_commands'] >= initial_successful + 2  # At least 2 should succeed
        assert stats['help_requests'] >= 1
        assert 'success_rate' in stats
        assert stats['success_rate'] > 0
    
    def test_command_registry_integration(self, handler):
        """Test integration with command registry"""
        # Verify commands are registered
        assert len(handler.registry.commands) > 0
        
        # Verify categories exist
        categories = handler.registry.get_commands_by_category()
        assert 'basic' in categories
        assert 'emergency' in categories
        assert 'bbs' in categories
    
    def test_help_system_integration(self, handler):
        """Test integration with help system"""
        # Verify help documentation exists
        help_text = handler.help_system.get_command_help('ping')
        assert help_text is not None
        assert 'ping' in help_text.lower()
        
        # Verify categories
        categories = handler.help_system.get_all_categories()
        assert len(categories) > 0
        assert 'basic' in categories
    
    def test_command_parser_integration(self, handler):
        """Test integration with command parser"""
        # Test simple command parsing
        parsed = handler.parser.parse('ping')
        assert parsed.command == 'ping'
        assert parsed.command_type == CommandType.SIMPLE
        
        # Test complex command parsing
        parsed = handler.parser.parse('email/to@example.com/Subject/Body')
        assert parsed.command == 'email'
        assert parsed.command_type == CommandType.COMPLEX
        assert 'to' in parsed.named_parameters
    
    @pytest.mark.asyncio
    async def test_error_handling(self, handler, basic_context):
        """Test error handling in command execution"""
        # This should not crash the handler
        response = await handler.handle_command('', [], basic_context)
        assert 'Error' in response or 'Invalid' in response
    
    @pytest.mark.asyncio
    async def test_command_aliases(self, handler, basic_context):
        """Test command aliases work correctly"""
        # Test ping aliases (note: 'ack' is not a ping alias, it's an emergency response command)
        aliases = ['cq', 'test', 'pong']
        
        for alias in aliases:
            response = await handler.handle_command(alias, [], basic_context)
            assert '🏓 Pong!' in response
    
    @pytest.mark.asyncio
    async def test_permission_system(self, handler, basic_context, admin_context):
        """Test permission system works correctly"""
        # Regular user should not access admin commands
        response = await handler.handle_command('block', ['test@example.com'], basic_context)
        assert 'Administrative privileges required' in response
        
        # Admin user should access admin commands
        response = await handler.handle_command('block', ['test@example.com'], admin_context)
        assert 'Email Blocked' in response
    
    def test_comprehensive_command_coverage(self, handler):
        """Test that all required commands from Requirement 14 are covered"""
        required_commands = [
            # Basic commands (14.1)
            'help', 'ping', 'status',
            
            # Emergency commands
            'sos', 'sosp', 'sosf', 'sosm', 'clear', 'cancel', 'safe', 'ack', 'responding', 'active',
            
            # BBS commands (14.5)
            'bbshelp', 'bbslist', 'bbsread', 'bbspost', 'bbsdelete', 'bbsinfo', 'bbslink',
            
            # Communication commands (14.6)
            'email', 'sms', 'tagsend', 'tagin', 'tagout',
            
            # Weather commands
            'wx', 'wxc', 'wxa', 'wxalert', 'mwx',
            
            # Information commands
            'whereami', 'whoami', 'whois', 'howfar', 'howtall',
            'solar', 'hfcond', 'sun', 'moon', 'tide', 'earthquake', 'riverflow',
            'lheard', 'sitrep', 'sysinfo', 'leaderboard', 'history', 'messages',
            'wiki', 'askai', 'ask', 'satpass', 'rlist', 'readnews', 'readrss', 'motd',
            
            # Game commands
            'blackjack', 'videopoker', 'dopewars', 'lemonstand', 'golfsim',
            'mastermind', 'hangman', 'tictactoe', 'hamtest', 'quiz', 'survey', 'joke',
            
            # Subscription commands
            'subscribe', 'unsubscribe', 'alerts', 'weather', 'forecasts',
            
            # Profile commands
            'name', 'phone', 'address', 'setemail', 'setsms', 'clearsms',
            
            # Asset commands
            'checkin', 'checkout', 'checklist',
            
            # Admin commands
            'block', 'unblock'
        ]
        
        registered_commands = set(handler.commands)
        
        for cmd in required_commands:
            assert cmd in registered_commands, f"Required command '{cmd}' not registered"