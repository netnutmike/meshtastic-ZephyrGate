"""
Unit tests for Interactive Bot Service
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.services.bot.interactive_bot_service import InteractiveBotService, AutoResponseRule, BotCommandHandler, ResponseTracker
from src.services.bot.command_registry import CommandRegistry, CommandContext, CommandPermission
from src.services.bot.message_processor import MessageProcessor, ProcessingContext
from src.models.message import Message, MessageType, MessagePriority
from src.core.plugin_interfaces import BaseCommandHandler


class TestInteractiveBotService:
    """Test cases for InteractiveBotService"""
    
    @pytest.fixture
    def bot_service(self):
        """Create a bot service instance for testing"""
        config = {
            'auto_response': {
                'enabled': True,
                'emergency_keywords': ['help', 'emergency'],
                'greeting_enabled': True,
                'greeting_message': 'Welcome to the mesh!',
                'emergency_escalation_delay': 5,  # 5 seconds for testing
                'response_rate_limit': 10,
                'cooldown_seconds': 2  # 2 seconds for testing
            },
            'commands': {
                'enabled': True,
                'help_enabled': True
            },
            'ai': {
                'enabled': False
            }
        }
        return InteractiveBotService(config)
    
    @pytest.fixture
    def sample_message(self):
        """Create a sample message for testing"""
        return Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="test message",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, bot_service):
        """Test service initialization"""
        assert not bot_service._running
        assert bot_service.config['auto_response']['enabled']
        assert bot_service.greeting_enabled
        assert len(bot_service.auto_response_rules) == 0  # Not initialized until start()
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, bot_service):
        """Test service start and stop"""
        await bot_service.start()
        assert bot_service._running
        assert len(bot_service.auto_response_rules) > 0  # Should have default rules
        assert len(bot_service.command_handlers) > 0  # Should have default commands
        
        await bot_service.stop()
        assert not bot_service._running
    
    @pytest.mark.asyncio
    async def test_auto_response_rules(self, bot_service):
        """Test auto-response rule functionality"""
        await bot_service.start()
        
        # Test help response (use ? to avoid emergency keyword)
        help_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="?",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(help_message)
        assert response is not None
        assert "commands" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_ping_response(self, bot_service):
        """Test ping auto-response"""
        await bot_service.start()
        
        ping_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="ping",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(ping_message)
        assert response is not None
        assert "pong" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_command_handling(self, bot_service):
        """Test command handling"""
        await bot_service.start()
        
        # Test help command
        help_command = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="help",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(help_command)
        assert response is not None
        assert response.sender_id == "bot"
        assert response.recipient_id == "!12345678"
    
    @pytest.mark.asyncio
    async def test_new_node_greeting(self, bot_service):
        """Test new node greeting functionality"""
        # Mock communication interface
        mock_comm = AsyncMock()
        bot_service.set_communication_interface(mock_comm)
        
        # Mock database to avoid initialization errors
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.cursor.return_value = mock_cursor
            
            await bot_service.start()
            
            # First message from a new node should trigger greeting
            new_node_message = Message(
                sender_id="!87654321",
                recipient_id=None,
                channel=0,
                content="hello",
                message_type=MessageType.TEXT,
                priority=MessagePriority.NORMAL,
                timestamp=datetime.utcnow()
            )
            
            await bot_service.handle_message(new_node_message)
            
            # Check that greeting was sent
            assert "!87654321" in bot_service.new_node_greetings
            mock_comm.send_mesh_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_emergency_keyword_detection(self, bot_service):
        """Test emergency keyword detection"""
        # Mock communication interface
        mock_comm = AsyncMock()
        bot_service.set_communication_interface(mock_comm)
        
        await bot_service.start()
        
        emergency_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="emergency help needed",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(emergency_message)
        
        # Should get emergency response
        assert response is not None
        assert "emergency" in response.content.lower()
        
        # Should send plugin message to emergency service
        mock_comm.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_remove_auto_response_rules(self, bot_service):
        """Test adding and removing auto-response rules"""
        await bot_service.start()
        
        initial_count = len(bot_service.auto_response_rules)
        
        # Add custom rule with higher priority
        custom_rule = AutoResponseRule(
            keywords=['custom'],
            response='Test response',
            priority=1  # Higher priority than default rules
        )
        bot_service.add_auto_response_rule(custom_rule)
        
        assert len(bot_service.auto_response_rules) == initial_count + 1
        
        # Test the custom rule
        test_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="custom",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(test_message)
        assert response is not None
        assert response.content == 'Test response'
        
        # Remove rule
        bot_service.remove_auto_response_rule(['custom'])
        assert len(bot_service.auto_response_rules) == initial_count
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, bot_service):
        """Test rate limiting functionality"""
        # Mock database to avoid initialization errors
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.cursor.return_value = mock_cursor
            
            await bot_service.start()
            
            # Create a test rule with very short cooldown for testing
            test_rule = AutoResponseRule(
                keywords=['ratelimit'],
                response='Rate test response',
                priority=1,  # High priority
                cooldown_seconds=1,  # 1 second cooldown
                max_responses_per_hour=5
            )
            bot_service.add_auto_response_rule(test_rule)
            
            # Send multiple messages quickly
            test_message = Message(
                sender_id="!12345678",
                recipient_id=None,
                channel=0,
                content="ratelimit",
                message_type=MessageType.TEXT,
                priority=MessagePriority.NORMAL,
                timestamp=datetime.utcnow()
            )
            
            # First response should work
            response1 = await bot_service.handle_message(test_message)
            assert response1 is not None
            assert response1.content == 'Rate test response'
            
            # Second response should be rate limited (within cooldown)
            # The auto-response should be blocked, but it might still process as a command
            response2 = await bot_service.handle_message(test_message)
            # Should either be None (no response) or an "unknown command" message
            if response2 is not None:
                assert "Unknown command" in response2.content
            
            # Wait for cooldown to expire
            await asyncio.sleep(1.5)
            
            # Third response should work
            response3 = await bot_service.handle_message(test_message)
            assert response3 is not None
            assert response3.content == 'Rate test response'
    
    @pytest.mark.asyncio
    async def test_keyword_match_types(self, bot_service):
        """Test different keyword match types"""
        await bot_service.start()
        
        # Add rule with exact match
        exact_rule = AutoResponseRule(
            keywords=['exact'],
            response='Exact match',
            match_type='exact',
            priority=10
        )
        bot_service.add_auto_response_rule(exact_rule)
        
        # Test exact match
        assert bot_service._check_keyword_match("exact", exact_rule) == True
        assert bot_service._check_keyword_match("not exact", exact_rule) == False
        
        # Add rule with starts_with match
        starts_rule = AutoResponseRule(
            keywords=['start'],
            response='Starts with match',
            match_type='starts_with',
            priority=10
        )
        bot_service.add_auto_response_rule(starts_rule)
        
        # Test starts_with match
        assert bot_service._check_keyword_match("start here", starts_rule) == True
        assert bot_service._check_keyword_match("not start", starts_rule) == False
    
    @pytest.mark.asyncio
    async def test_emergency_escalation(self, bot_service):
        """Test emergency escalation functionality"""
        # Mock communication interface
        mock_comm = AsyncMock()
        bot_service.set_communication_interface(mock_comm)
        
        # Set short escalation delay for testing
        bot_service.config['auto_response']['emergency_escalation_delay'] = 1
        
        # Mock database to avoid initialization errors
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.cursor.return_value = mock_cursor
            
            await bot_service.start()
            
            emergency_message = Message(
                sender_id="!12345678",
                recipient_id=None,
                channel=0,
                content="urgent help needed",
                message_type=MessageType.TEXT,
                priority=MessagePriority.NORMAL,
                timestamp=datetime.utcnow()
            )
            
            response = await bot_service.handle_message(emergency_message)
            assert response is not None
            
            # Check that escalation task was created
            assert len(bot_service.emergency_escalation_tasks) > 0
            
            # Wait for escalation
            await asyncio.sleep(2)
            
            # Check that escalation message was sent
            assert mock_comm.send_mesh_message.call_count >= 2  # Initial greeting + escalation
    
    @pytest.mark.asyncio
    async def test_case_sensitivity(self, bot_service):
        """Test case sensitivity in keyword matching"""
        await bot_service.start()
        
        # Add case-sensitive rule
        case_rule = AutoResponseRule(
            keywords=['CaseSensitive'],
            response='Case sensitive match',
            case_sensitive=True,
            priority=10
        )
        bot_service.add_auto_response_rule(case_rule)
        
        # Test case sensitivity
        assert bot_service._check_keyword_match("CaseSensitive", case_rule) == True
        assert bot_service._check_keyword_match("casesensitive", case_rule) == False
        
        # Test case insensitive (default)
        case_rule.case_sensitive = False
        assert bot_service._check_keyword_match("casesensitive", case_rule) == True
    
    @pytest.mark.asyncio
    async def test_update_auto_response_rule(self, bot_service):
        """Test updating auto-response rules"""
        await bot_service.start()
        
        # Add rule to update
        test_rule = AutoResponseRule(
            keywords=['update_test'],
            response='Original response',
            priority=50
        )
        bot_service.add_auto_response_rule(test_rule)
        
        # Update the rule
        success = bot_service.update_auto_response_rule(
            ['update_test'],
            response='Updated response',
            priority=25
        )
        
        assert success == True
        
        # Find the updated rule
        updated_rule = None
        for rule in bot_service.auto_response_rules:
            if 'update_test' in rule.keywords:
                updated_rule = rule
                break
        
        assert updated_rule is not None
        assert updated_rule.response == 'Updated response'
        assert updated_rule.priority == 25
    
    @pytest.mark.asyncio
    async def test_response_statistics(self, bot_service):
        """Test response statistics collection"""
        await bot_service.start()
        
        # Generate some responses
        ping_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="ping",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        await bot_service.handle_message(ping_message)
        
        # Wait for cooldown
        await asyncio.sleep(2)
        
        help_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="?",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        await bot_service.handle_message(help_message)
        
        # Get statistics
        stats = bot_service.get_response_statistics()
        
        assert 'total_rules' in stats
        assert 'emergency_rules' in stats
        assert 'active_rules' in stats
        assert 'known_nodes' in stats
        assert stats['total_rules'] > 0
    
    @pytest.mark.asyncio
    async def test_emergency_escalation_cancellation(self, bot_service):
        """Test cancelling emergency escalation"""
        # Mock communication interface
        mock_comm = AsyncMock()
        bot_service.set_communication_interface(mock_comm)
        
        await bot_service.start()
        
        emergency_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="emergency help",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        # Trigger emergency
        await bot_service.handle_message(emergency_message)
        
        # Check escalation task exists
        assert len(bot_service.emergency_escalation_tasks) > 0
        
        # Cancel escalation
        bot_service.cancel_emergency_escalation(emergency_message.sender_id, "emergency help")
        
        # Check escalation task was cancelled
        await asyncio.sleep(0.1)  # Allow task cancellation to process
        assert len(bot_service.emergency_escalation_tasks) == 0


class TestCommandRegistry:
    """Test cases for CommandRegistry"""
    
    @pytest.fixture
    def registry(self):
        """Create a command registry for testing"""
        return CommandRegistry()
    
    @pytest.fixture
    def sample_handler(self):
        """Create a sample command handler"""
        class TestHandler(BaseCommandHandler):
            def __init__(self):
                super().__init__(['test', 'sample'])
                self.add_help('test', 'Test command')
                self.add_help('sample', 'Sample command')
            
            async def handle_command(self, command: str, args: list, context: dict) -> str:
                return f"Executed {command} with args: {args}"
        
        return TestHandler()
    
    def test_registry_initialization(self, registry):
        """Test registry initialization"""
        assert len(registry.commands) == 0
        assert len(registry.aliases) == 0
        assert len(registry.categories) == 0
    
    def test_register_command(self, registry, sample_handler):
        """Test command registration"""
        registered = registry.register_command(sample_handler, "test_plugin")
        
        assert len(registered) == 2
        assert 'test' in registered
        assert 'sample' in registered
        assert 'test' in registry.commands
        assert 'sample' in registry.commands
        assert registry.commands['test'].plugin_name == "test_plugin"
    
    def test_unregister_command(self, registry, sample_handler):
        """Test command unregistration"""
        registry.register_command(sample_handler, "test_plugin")
        
        success = registry.unregister_command('test', 'test_plugin')
        assert success
        assert 'test' not in registry.commands
        assert 'sample' in registry.commands  # Other command should remain
    
    @pytest.mark.asyncio
    async def test_command_dispatch(self, registry, sample_handler):
        """Test command dispatch"""
        registry.register_command(sample_handler, "test_plugin")
        
        context = CommandContext(
            sender_id="!12345678",
            is_admin=False,
            is_moderator=False
        )
        
        response = await registry.dispatch_command("test arg1 arg2", context)
        assert "Executed test with args: ['arg1', 'arg2']" in response
    
    @pytest.mark.asyncio
    async def test_unknown_command(self, registry):
        """Test unknown command handling"""
        context = CommandContext(
            sender_id="!12345678",
            is_admin=False,
            is_moderator=False
        )
        
        response = await registry.dispatch_command("unknown", context)
        assert "Unknown command" in response
    
    def test_command_help(self, registry, sample_handler):
        """Test command help functionality"""
        registry.register_command(sample_handler, "test_plugin")
        
        help_text = registry.get_command_help('test')
        assert help_text is not None
        assert 'Test command' in help_text
    
    def test_commands_by_category(self, registry, sample_handler):
        """Test getting commands by category"""
        registry.register_command(sample_handler, "test_plugin")
        
        categories = registry.get_commands_by_category()
        assert 'test_plugin' in categories
        assert 'test' in categories['test_plugin']
        assert 'sample' in categories['test_plugin']


class TestMessageProcessor:
    """Test cases for MessageProcessor"""
    
    @pytest.fixture
    def processor(self):
        """Create a message processor for testing"""
        return MessageProcessor()
    
    @pytest.fixture
    def sample_message(self):
        """Create a sample message for testing"""
        return Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="test message",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
    
    def test_processor_initialization(self, processor):
        """Test processor initialization"""
        assert len(processor.message_handlers) == 0
        assert len(processor.routes) == 0
        assert processor.processing_stats['total_processed'] == 0
    
    @pytest.mark.asyncio
    async def test_message_processing(self, processor, sample_message):
        """Test basic message processing"""
        # Create a mock handler
        mock_handler = Mock()
        mock_handler.can_handle.return_value = True
        mock_handler.get_priority.return_value = 100
        mock_handler.handle_message = AsyncMock(return_value="Test response")
        
        processor.register_handler(mock_handler)
        
        result, response = await processor.process_message(sample_message)
        
        assert result.value == "handled"
        assert response == "Test response"
        assert processor.processing_stats['handled'] == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_message_detection(self, processor, sample_message):
        """Test duplicate message detection"""
        # Create a mock handler
        mock_handler = Mock()
        mock_handler.can_handle.return_value = True
        mock_handler.get_priority.return_value = 100
        mock_handler.handle_message = AsyncMock(return_value="Test response")
        
        processor.register_handler(mock_handler)
        
        # Process same message twice
        result1, response1 = await processor.process_message(sample_message)
        result2, response2 = await processor.process_message(sample_message)
        
        assert result1.value == "handled"
        assert result2.value == "ignored"  # Should be ignored as duplicate
        assert processor.processing_stats['duplicates'] == 1
    
    def test_message_history(self, processor, sample_message):
        """Test message history functionality"""
        # Process message to add to history
        asyncio.run(processor._store_message_history(sample_message))
        
        history = processor.get_message_history(sample_message.sender_id)
        assert len(history) == 1
        assert history[0] == sample_message
    
    def test_processing_statistics(self, processor):
        """Test processing statistics"""
        processor.processing_stats['total_processed'] = 10
        processor.processing_stats['handled'] = 7
        processor.processing_stats['ignored'] = 3
        
        stats = processor.get_processing_statistics()
        
        assert stats['total_processed'] == 10
        assert stats['percentages']['handled'] == 70.0
        assert stats['percentages']['ignored'] == 30.0


if __name__ == '__main__':
    pytest.main([__file__])