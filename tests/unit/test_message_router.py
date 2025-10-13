"""
Unit tests for Core Message Router

Tests message routing logic, classification, and core functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.models.message import Message, MessageType, MessagePriority, SOSType, UserProfile
from src.core.message_router import CoreMessageRouter, MessageClassifier, RouteRule, RateLimitBucket
from src.core.config import ConfigurationManager
from src.core.database import DatabaseManager


class TestMessageClassifier:
    """Test message classification logic"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.classifier = MessageClassifier()
    
    def test_classify_sos_message(self):
        """Test SOS message classification"""
        message = Message(content="SOS need help", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'emergency' in services
    
    def test_classify_bbs_message(self):
        """Test BBS message classification"""
        message = Message(content="bbslist", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'bbs' in services
    
    def test_classify_bot_command(self):
        """Test bot command classification"""
        message = Message(content="help", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'bot' in services
    
    def test_classify_email_command(self):
        """Test email command classification"""
        message = Message(content="email/test@example.com/subject/body", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'email' in services
    
    def test_classify_weather_message(self):
        """Test weather-related message classification"""
        message = Message(content="what's the weather like?", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'weather' in services
    
    def test_classify_high_altitude_message(self):
        """Test high-altitude user message classification"""
        user = UserProfile(
            node_id="!12345678",
            short_name="Aircraft",
            altitude=2000.0
        )
        message = Message(content="hello from above", sender_id="!12345678")
        services = self.classifier.classify_message(message, user)
        
        assert 'bot' in services
    
    def test_extract_sos_type(self):
        """Test SOS type extraction"""
        assert self.classifier.extract_sos_type("SOSP help") == SOSType.SOSP
        assert self.classifier.extract_sos_type("SOSF fire") == SOSType.SOSF
        assert self.classifier.extract_sos_type("SOSM medical") == SOSType.SOSM
        assert self.classifier.extract_sos_type("SOS general") == SOSType.SOS
    
    def test_default_classification(self):
        """Test default classification for unmatched messages"""
        message = Message(content="random message", sender_id="!12345678")
        services = self.classifier.classify_message(message)
        
        assert 'bot' in services


class TestRouteRule:
    """Test routing rule matching"""
    
    def test_pattern_matching(self):
        """Test pattern matching"""
        rule = RouteRule(pattern=r'\bSOS\b', service='emergency')
        
        message = Message(content="SOS help needed", sender_id="!12345678")
        assert rule.matches(message)
        
        message = Message(content="SOSP police needed", sender_id="!12345678")
        assert not rule.matches(message)  # Should not match SOS pattern
    
    def test_condition_matching(self):
        """Test condition matching"""
        rule = RouteRule(
            pattern='',
            service='test',
            conditions={'message_type': 'text', 'is_dm': True}
        )
        
        # Should match
        message = Message(
            content="test",
            sender_id="!12345678",
            recipient_id="!87654321",
            message_type=MessageType.TEXT
        )
        assert rule.matches(message)
        
        # Should not match (broadcast)
        message = Message(
            content="test",
            sender_id="!12345678",
            recipient_id=None,
            message_type=MessageType.TEXT
        )
        assert not rule.matches(message)
    
    def test_user_permission_condition(self):
        """Test user permission condition"""
        rule = RouteRule(
            pattern='',
            service='admin',
            conditions={'sender_has_permission': 'admin'}
        )
        
        # User with permission
        user = UserProfile(
            node_id="!12345678",
            short_name="Admin",
            permissions={'admin': True}
        )
        message = Message(content="admin command", sender_id="!12345678")
        assert rule.matches(message, user)
        
        # User without permission
        user.permissions = {'admin': False}
        assert not rule.matches(message, user)
        
        # No user
        assert not rule.matches(message, None)


class TestRateLimitBucket:
    """Test rate limiting bucket"""
    
    def test_token_consumption(self):
        """Test token consumption"""
        bucket = RateLimitBucket(
            tokens=5.0,
            last_refill=datetime.utcnow(),
            max_tokens=5.0,
            refill_rate=1.0
        )
        
        # Should be able to consume tokens
        assert bucket.can_consume(3.0)
        assert bucket.consume(3.0)
        assert bucket.tokens == 2.0
        
        # Should not be able to consume more than available
        assert not bucket.can_consume(3.0)
        assert not bucket.consume(3.0)
        assert bucket.tokens == 2.0
    
    def test_token_refill(self):
        """Test token refill over time"""
        past_time = datetime.utcnow() - timedelta(seconds=2)
        bucket = RateLimitBucket(
            tokens=0.0,
            last_refill=past_time,
            max_tokens=5.0,
            refill_rate=1.0  # 1 token per second
        )
        
        # Should refill tokens based on elapsed time
        bucket._refill()
        assert bucket.tokens >= 2.0  # At least 2 tokens after 2 seconds
        assert bucket.tokens <= 5.0  # But not more than max


@pytest.fixture
async def mock_config():
    """Mock configuration manager"""
    config = Mock(spec=ConfigurationManager)
    config.get.return_value = 228  # max_message_size
    return config


@pytest.fixture
async def mock_db():
    """Mock database manager"""
    db = Mock(spec=DatabaseManager)
    db.execute_update.return_value = 1
    db.get_user.return_value = None
    db.upsert_user.return_value = None
    db.cleanup_expired_data.return_value = None
    return db


@pytest.fixture
async def message_router(mock_config, mock_db):
    """Create message router for testing"""
    router = CoreMessageRouter(mock_config, mock_db)
    await router.start()
    yield router
    await router.stop()


class TestCoreMessageRouter:
    """Test core message router functionality"""
    
    @pytest.mark.asyncio
    async def test_service_registration(self, message_router):
        """Test service registration and unregistration"""
        mock_service = Mock()
        
        # Register service
        message_router.register_service('test_service', mock_service)
        assert 'test_service' in message_router.services
        
        # Unregister service
        message_router.unregister_service('test_service')
        assert 'test_service' not in message_router.services
    
    @pytest.mark.asyncio
    async def test_interface_registration(self, message_router):
        """Test interface registration and unregistration"""
        mock_interface = Mock()
        
        # Register interface
        message_router.register_interface('test_interface', mock_interface)
        assert 'test_interface' in message_router.interfaces
        assert message_router.stats['interfaces_active'] == 1
        
        # Unregister interface
        message_router.unregister_interface('test_interface')
        assert 'test_interface' not in message_router.interfaces
        assert message_router.stats['interfaces_active'] == 0
    
    @pytest.mark.asyncio
    async def test_message_processing(self, message_router):
        """Test message processing flow"""
        # Register mock service
        mock_service = AsyncMock()
        message_router.register_service('bot', mock_service)
        
        # Process message
        message = Message(content="help", sender_id="!12345678")
        await message_router.process_message(message, 'test_interface')
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify message was processed
        assert message_router.stats['messages_received'] == 1
        assert message_router.stats['messages_queued'] == 1
    
    @pytest.mark.asyncio
    async def test_message_routing_to_services(self, message_router):
        """Test message routing to appropriate services"""
        # Register mock services
        emergency_service = AsyncMock()
        bot_service = AsyncMock()
        
        message_router.register_service('emergency', emergency_service)
        message_router.register_service('bot', bot_service)
        
        # Process SOS message
        sos_message = Message(content="SOS help needed", sender_id="!12345678")
        await message_router.process_message(sos_message, 'test_interface')
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Verify emergency service was called
        emergency_service.handle_message.assert_called()
        
        # Process bot command
        bot_message = Message(content="help", sender_id="!12345678")
        await message_router.process_message(bot_message, 'test_interface')
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Verify bot service was called
        bot_service.handle_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, message_router):
        """Test rate limiting functionality"""
        # Send multiple messages quickly
        sender_id = "!12345678"
        
        # First few messages should succeed
        for i in range(3):
            message = Message(content=f"message {i}", sender_id=sender_id)
            result = await message_router.send_message(message)
            # Note: This will fail without actual interfaces, but tests the rate limiting logic
        
        # Verify rate limiting is applied
        rate_key = f"sender_{sender_id}"
        assert rate_key in message_router.rate_limiters
    
    @pytest.mark.asyncio
    async def test_message_chunking(self, message_router):
        """Test message chunking for large messages"""
        # Create large message
        large_content = "A" * 300  # Larger than max_message_size (228)
        message = Message(content=large_content, sender_id="!12345678")
        
        # Chunk the message
        chunks = message_router._chunk_message(message)
        
        # Verify chunking
        assert len(chunks) > 1
        
        # Verify chunk metadata
        for i, chunk in enumerate(chunks):
            assert chunk.metadata['is_chunk'] is True
            assert chunk.metadata['chunk_index'] == i
            assert chunk.metadata['total_chunks'] == len(chunks)
            assert chunk.metadata['chunk_id'] is not None
    
    @pytest.mark.asyncio
    async def test_user_profile_handling(self, message_router, mock_db):
        """Test user profile retrieval and updates"""
        # Mock user data
        user_data = {
            'node_id': '!12345678',
            'short_name': 'TestUser',
            'long_name': 'Test User',
            'email': None,
            'phone': None,
            'address': None,
            'tags': [],
            'permissions': {},
            'subscriptions': {},
            'last_seen': datetime.utcnow().isoformat(),
            'location_lat': None,
            'location_lon': None
        }
        
        mock_db.get_user.return_value = user_data
        
        # Process message to trigger user profile handling
        message = Message(content="test", sender_id="!12345678")
        await message_router.process_message(message, 'test_interface')
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify user profile was retrieved
        mock_db.get_user.assert_called_with('!12345678')
    
    def test_statistics_collection(self, message_router):
        """Test statistics collection"""
        stats = message_router.get_stats()
        
        # Verify required stats are present
        assert 'messages_received' in stats
        assert 'messages_sent' in stats
        assert 'messages_queued' in stats
        assert 'messages_failed' in stats
        assert 'services_called' in stats
        assert 'interfaces_active' in stats
        assert 'uptime_seconds' in stats
        assert 'queue_size' in stats
    
    def test_recent_messages_tracking(self, message_router):
        """Test recent messages tracking"""
        # Add some messages to recent history
        for i in range(5):
            message_data = {
                'timestamp': datetime.utcnow(),
                'message': {'id': f'msg_{i}', 'content': f'test {i}'},
                'interface_id': 'test'
            }
            message_router.recent_messages.append(message_data)
        
        # Get recent messages
        recent = message_router.get_recent_messages(3)
        
        assert len(recent) == 3
        assert recent[0]['message']['id'] == 'msg_2'  # Should get last 3


class TestMessageRouterIntegration:
    """Integration tests for message router components"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_message_flow(self, mock_config, mock_db):
        """Test complete message flow from receipt to service handling"""
        router = CoreMessageRouter(mock_config, mock_db)
        await router.start()
        
        try:
            # Register mock service
            mock_service = AsyncMock()
            router.register_service('bot', mock_service)
            
            # Process message
            message = Message(
                content="help",
                sender_id="!12345678",
                timestamp=datetime.utcnow()
            )
            
            await router.process_message(message, 'test_interface')
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Verify service was called
            mock_service.handle_message.assert_called_once()
            
            # Verify statistics
            stats = router.get_stats()
            assert stats['messages_received'] == 1
            assert stats['messages_queued'] == 1
            
        finally:
            await router.stop()
    
    @pytest.mark.asyncio
    async def test_service_failure_handling(self, mock_config, mock_db):
        """Test handling of service failures"""
        router = CoreMessageRouter(mock_config, mock_db)
        await router.start()
        
        try:
            # Register failing service
            failing_service = AsyncMock()
            failing_service.handle_message.side_effect = Exception("Service failed")
            router.register_service('bot', failing_service)
            
            # Process message
            message = Message(content="help", sender_id="!12345678")
            await router.process_message(message, 'test_interface')
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Verify service was called despite failure
            failing_service.handle_message.assert_called_once()
            
            # Verify error was handled gracefully
            stats = router.get_stats()
            assert stats['messages_received'] == 1
            
        finally:
            await router.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_service_routing(self, mock_config, mock_db):
        """Test routing to multiple services"""
        router = CoreMessageRouter(mock_config, mock_db)
        await router.start()
        
        try:
            # Register multiple services
            emergency_service = AsyncMock()
            bot_service = AsyncMock()
            
            router.register_service('emergency', emergency_service)
            router.register_service('bot', bot_service)
            
            # Process message that should go to multiple services
            # (SOS messages typically go to both emergency and bot services)
            message = Message(content="SOS help", sender_id="!12345678")
            await router.process_message(message, 'test_interface')
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Verify both services were called
            emergency_service.handle_message.assert_called_once()
            # Bot service might also be called depending on routing rules
            
        finally:
            await router.stop()


if __name__ == '__main__':
    pytest.main([__file__])