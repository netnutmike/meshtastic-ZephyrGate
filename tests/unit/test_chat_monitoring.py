"""
Unit tests for Chat Monitoring functionality in Web Admin Service
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from src.services.web.web_admin_service import WebAdminService
from src.models.message import Message, MessageType


class TestChatMonitoring:
    """Test chat monitoring functionality"""
    
    @pytest.fixture
    def mock_plugin_manager(self):
        manager = Mock()
        manager.config_manager = Mock()
        manager.config_manager.get = Mock(return_value=None)
        return manager
    
    @pytest.fixture
    def config(self):
        return {
            "host": "127.0.0.1",
            "port": 8080,
            "secret_key": "test-secret-key",
            "debug": True
        }
    
    @pytest.fixture
    def web_service(self, config, mock_plugin_manager):
        return WebAdminService(config, mock_plugin_manager)
    
    def test_message_to_response(self, web_service):
        """Test converting Message to API response"""
        # Create a test user
        web_service.user_manager.create_user("!12345678", "TestUser", "Test User")
        
        # Create test message
        message = Message(
            id="test_msg",
            sender_id="!12345678",
            recipient_id="!87654321",
            channel=0,
            content="Test message",
            timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            interface_id="serial0",
            hop_count=2,
            snr=5.5,
            rssi=-85
        )
        
        response = web_service._message_to_response(message)
        
        assert response.id == "test_msg"
        assert response.sender_id == "!12345678"
        assert response.sender_name == "TestUser"
        assert response.recipient_id == "!87654321"
        assert response.channel == 0
        assert response.content == "Test message"
        assert response.message_type == "text"
        assert response.interface_id == "serial0"
        assert response.hop_count == 2
        assert response.snr == 5.5
        assert response.rssi == -85
    
    def test_filter_messages_by_query(self, web_service):
        """Test filtering messages by text query"""
        # Add test messages
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Hello world", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!22222222", recipient_id=None,
                channel=0, content="Goodbye world", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!33333333", recipient_id=None,
                channel=0, content="Test message", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Filter by query
        filtered = web_service._filter_messages(query="world")
        assert len(filtered) == 2
        assert all("world" in msg.content.lower() for msg in filtered)
        
        filtered = web_service._filter_messages(query="test")
        assert len(filtered) == 1
        assert filtered[0].content == "Test message"
        
        filtered = web_service._filter_messages(query="nonexistent")
        assert len(filtered) == 0
    
    def test_filter_messages_by_sender(self, web_service):
        """Test filtering messages by sender"""
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Message 1", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!22222222", recipient_id=None,
                channel=0, content="Message 2", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!11111111", recipient_id=None,
                channel=0, content="Message 3", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Filter by sender
        filtered = web_service._filter_messages(sender_id="!11111111")
        assert len(filtered) == 2
        assert all(msg.sender_id == "!11111111" for msg in filtered)
        
        filtered = web_service._filter_messages(sender_id="!22222222")
        assert len(filtered) == 1
        assert filtered[0].sender_id == "!22222222"
        
        filtered = web_service._filter_messages(sender_id="!nonexistent")
        assert len(filtered) == 0
    
    def test_filter_messages_by_channel(self, web_service):
        """Test filtering messages by channel"""
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Channel 0", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!22222222", recipient_id=None,
                channel=1, content="Channel 1", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!33333333", recipient_id=None,
                channel=0, content="Another Channel 0", timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Filter by channel
        filtered = web_service._filter_messages(channel=0)
        assert len(filtered) == 2
        assert all(msg.channel == 0 for msg in filtered)
        
        filtered = web_service._filter_messages(channel=1)
        assert len(filtered) == 1
        assert filtered[0].channel == 1
        
        filtered = web_service._filter_messages(channel=99)
        assert len(filtered) == 0
    
    def test_filter_messages_by_date_range(self, web_service):
        """Test filtering messages by date range"""
        now = datetime.now(timezone.utc)
        
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Old message", timestamp=now - timedelta(days=2),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!22222222", recipient_id=None,
                channel=0, content="Recent message", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!33333333", recipient_id=None,
                channel=0, content="Future message", timestamp=now + timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Filter by start date
        start_date = now - timedelta(days=1)
        filtered = web_service._filter_messages(start_date=start_date)
        assert len(filtered) == 2  # Recent and future messages
        
        # Filter by end date
        end_date = now
        filtered = web_service._filter_messages(end_date=end_date)
        assert len(filtered) == 2  # Old and recent messages
        
        # Filter by date range
        filtered = web_service._filter_messages(
            start_date=now - timedelta(hours=2),
            end_date=now + timedelta(minutes=30)
        )
        assert len(filtered) == 1  # Only recent message
        assert filtered[0].content == "Recent message"
    
    def test_filter_messages_multiple_criteria(self, web_service):
        """Test filtering messages with multiple criteria"""
        now = datetime.now(timezone.utc)
        
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Hello from channel 0", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!11111111", recipient_id=None,
                channel=1, content="Hello from channel 1", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!22222222", recipient_id=None,
                channel=0, content="Goodbye from channel 0", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Filter by sender and channel
        filtered = web_service._filter_messages(sender_id="!11111111", channel=0)
        assert len(filtered) == 1
        assert filtered[0].content == "Hello from channel 0"
        
        # Filter by query and channel
        filtered = web_service._filter_messages(query="hello", channel=1)
        assert len(filtered) == 1
        assert filtered[0].content == "Hello from channel 1"
        
        # Filter with no matches
        filtered = web_service._filter_messages(sender_id="!11111111", query="goodbye")
        assert len(filtered) == 0
    
    @pytest.mark.asyncio
    async def test_send_direct_message(self, web_service):
        """Test sending direct message"""
        initial_count = len(web_service.messages_cache)
        
        success = await web_service._send_direct_message(
            recipient_id="!12345678",
            content="Test direct message",
            interface_id="web_admin",
            sender="test_user"
        )
        
        assert success is True
        assert len(web_service.messages_cache) == initial_count + 1
        
        # Check the message was added
        new_message = web_service.messages_cache[-1]
        assert new_message.recipient_id == "!12345678"
        assert new_message.content == "Test direct message"
        assert new_message.interface_id == "web_admin"
        assert new_message.sender_id == "admin_test_user"
    
    @pytest.mark.asyncio
    async def test_get_chat_stats(self, web_service):
        """Test getting chat statistics"""
        now = datetime.now(timezone.utc)
        
        # Add test messages
        messages = [
            Message(
                id="msg1", sender_id="!11111111", recipient_id=None,
                channel=0, content="Message 1", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg2", sender_id="!11111111", recipient_id=None,
                channel=1, content="Message 2", timestamp=now - timedelta(hours=1),
                message_type=MessageType.TEXT, interface_id="serial0"
            ),
            Message(
                id="msg3", sender_id="!22222222", recipient_id=None,
                channel=0, content="Message 3", timestamp=now - timedelta(days=1),
                message_type=MessageType.POSITION, interface_id="serial0"
            )
        ]
        
        web_service.messages_cache = messages
        
        # Create users for sender names
        web_service.user_manager.create_user("!11111111", "User1")
        web_service.user_manager.create_user("!22222222", "User2")
        
        stats = await web_service._get_chat_stats()
        
        assert stats.total_messages == 3
        assert stats.messages_today == 2  # Messages from today
        assert set(stats.active_channels) == {0, 1}
        
        # Check top senders
        assert len(stats.top_senders) == 2
        top_sender = stats.top_senders[0]
        assert top_sender["sender_id"] == "!11111111"
        assert top_sender["sender_name"] == "User1"
        assert top_sender["message_count"] == 2
        
        # Check message types
        assert stats.message_types["text"] == 2
        assert stats.message_types["position"] == 1
        
        # Check hourly activity
        assert len(stats.hourly_activity) == 24
        assert all("hour" in activity and "message_count" in activity for activity in stats.hourly_activity)


if __name__ == "__main__":
    pytest.main([__file__])