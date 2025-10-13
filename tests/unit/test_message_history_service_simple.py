"""
Simplified unit tests for Message History Service

Tests core functionality of message history storage, retrieval, and store-and-forward.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json
import unittest

from src.services.bot.message_history_service import (
    MessageHistoryService, MessageFilter, StoredMessage, OfflineUser
)
from src.models.message import Message, MessageType, MessagePriority
from src.core.plugin_interfaces import PluginCommunicationInterface
from src.core.database import initialize_database


class TestMessageHistoryService(unittest.TestCase):
    """Test cases for MessageHistoryService"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Initialize test database
        self.db = initialize_database(":memory:")
        
        # Test configuration
        self.config = {
            'history_retention_days': 7,
            'max_offline_messages': 10,
            'offline_message_ttl_hours': 24,
            'max_message_chunk_size': 100,
            'store_forward_enabled': True,
            'chunk_responses': True,
            'offline_check_interval': 60,
            'cleanup_interval': 300,
            'max_history_results': 50,
            'enable_message_search': True,
            'enable_replay_system': True
        }
        
        # Create service instance
        self.service = MessageHistoryService(self.config)
        
        # Mock communication interface
        self.mock_communication = Mock(spec=PluginCommunicationInterface)
        self.mock_communication.send_mesh_message = AsyncMock()
        self.service.set_communication_interface(self.mock_communication)
        
        # Test messages
        self.test_message = Message(
            id="test_msg_1",
            sender_id="!12345678",
            recipient_id="!87654321",
            content="Test message content",
            timestamp=datetime.utcnow(),
            channel=0,
            interface_id="test_interface"
        )
    
    def test_service_initialization(self):
        """Test service initialization"""
        service = MessageHistoryService()
        
        # Check default configuration
        self.assertEqual(service.config['history_retention_days'], 30)
        self.assertEqual(service.config['max_offline_messages'], 50)
        self.assertTrue(service.config['store_forward_enabled'])
        self.assertFalse(service._running)
    
    @pytest.mark.asyncio
    async def test_start_stop_service(self):
        """Test service start and stop"""
        with patch.object(self.service, '_load_offline_users', new_callable=AsyncMock):
            with patch.object(self.service, '_load_pending_messages', new_callable=AsyncMock):
                await self.service.start()
                self.assertTrue(self.service._running)
                
                await self.service.stop()
                self.assertFalse(self.service._running)
    
    @pytest.mark.asyncio
    async def test_history_command_basic(self):
        """Test basic history command"""
        history_message = Message(
            sender_id="!12345678",
            content="history",
            timestamp=datetime.utcnow()
        )
        
        mock_messages = [
            {
                'timestamp': '2024-01-01T12:00:00',
                'sender_id': '!87654321',
                'content': 'Test message 1'
            }
        ]
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock, return_value=mock_messages):
            response = await self.service.handle_message(history_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Message History", response.content)
    
    @pytest.mark.asyncio
    async def test_pending_command_no_messages(self):
        """Test pending command with no pending messages"""
        pending_message = Message(
            sender_id="!12345678",
            content="pending",
            timestamp=datetime.utcnow()
        )
        
        response = await self.service.handle_message(pending_message)
        
        self.assertIsNotNone(response)
        self.assertIn("No pending messages", response.content)
    
    @pytest.mark.asyncio
    async def test_store_offline_message(self):
        """Test storing message for offline user"""
        message = Message(
            sender_id="!12345678",
            recipient_id="!87654321",
            content="Offline message",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(self.service.db, 'execute_update') as mock_execute:
            await self.service._store_offline_message(message)
            
            # Check message was stored
            self.assertIn(message.id, self.service.pending_messages)
            stored_msg = self.service.pending_messages[message.id]
            self.assertEqual(stored_msg.recipient_id, "!87654321")
            self.assertEqual(stored_msg.content, "Offline message")
            
            # Check user was added to offline tracking
            self.assertIn("!87654321", self.service.offline_users)
    
    def test_get_stats(self):
        """Test getting service statistics"""
        # Add some test data
        self.service.offline_users["!12345678"] = OfflineUser(
            node_id="!12345678",
            last_seen=datetime.utcnow() - timedelta(hours=1)
        )
        
        stored_msg = StoredMessage(
            id="pending_1",
            recipient_id="!87654321",
            sender_id="!12345678",
            content="Pending message",
            timestamp=datetime.utcnow(),
            priority=MessagePriority.NORMAL,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.service.pending_messages["pending_1"] = stored_msg
        
        stats = self.service.get_stats()
        
        self.assertEqual(stats['offline_users'], 1)
        self.assertEqual(stats['pending_messages'], 1)
        self.assertTrue(stats['store_forward_enabled'])
        self.assertEqual(stats['history_retention_days'], 7)


class TestMessageFilter(unittest.TestCase):
    """Test cases for MessageFilter"""
    
    def test_message_filter_defaults(self):
        """Test MessageFilter default values"""
        filter_criteria = MessageFilter()
        
        self.assertIsNone(filter_criteria.sender_id)
        self.assertIsNone(filter_criteria.recipient_id)
        self.assertIsNone(filter_criteria.channel)
        self.assertEqual(filter_criteria.limit, 50)
        self.assertEqual(filter_criteria.offset, 0)
    
    def test_message_filter_custom_values(self):
        """Test MessageFilter with custom values"""
        start_time = datetime.utcnow() - timedelta(hours=1)
        
        filter_criteria = MessageFilter(
            sender_id="!12345678",
            channel=0,
            content_pattern="test",
            start_time=start_time,
            limit=10
        )
        
        self.assertEqual(filter_criteria.sender_id, "!12345678")
        self.assertEqual(filter_criteria.channel, 0)
        self.assertEqual(filter_criteria.content_pattern, "test")
        self.assertEqual(filter_criteria.start_time, start_time)
        self.assertEqual(filter_criteria.limit, 10)


class TestStoredMessage(unittest.TestCase):
    """Test cases for StoredMessage"""
    
    def test_stored_message_creation(self):
        """Test StoredMessage creation"""
        timestamp = datetime.utcnow()
        expires_at = timestamp + timedelta(hours=24)
        
        stored_msg = StoredMessage(
            id="test_msg",
            recipient_id="!12345678",
            sender_id="!87654321",
            content="Test message",
            timestamp=timestamp,
            priority=MessagePriority.HIGH,
            expires_at=expires_at
        )
        
        self.assertEqual(stored_msg.id, "test_msg")
        self.assertEqual(stored_msg.recipient_id, "!12345678")
        self.assertEqual(stored_msg.sender_id, "!87654321")
        self.assertEqual(stored_msg.content, "Test message")
        self.assertEqual(stored_msg.priority, MessagePriority.HIGH)
        self.assertEqual(stored_msg.attempts, 0)
        self.assertEqual(stored_msg.max_attempts, 3)


class TestOfflineUser(unittest.TestCase):
    """Test cases for OfflineUser"""
    
    def test_offline_user_creation(self):
        """Test OfflineUser creation"""
        last_seen = datetime.utcnow() - timedelta(hours=1)
        
        offline_user = OfflineUser(
            node_id="!12345678",
            last_seen=last_seen
        )
        
        self.assertEqual(offline_user.node_id, "!12345678")
        self.assertEqual(offline_user.last_seen, last_seen)
        self.assertEqual(offline_user.pending_messages, [])
        self.assertFalse(offline_user.notification_sent)
        self.assertEqual(offline_user.max_offline_hours, 24)


if __name__ == '__main__':
    pytest.main([__file__])