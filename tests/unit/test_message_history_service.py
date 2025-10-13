"""
Unit tests for Message History Service

Tests message history storage, retrieval, store-and-forward functionality,
message replay system, and message chunking for large responses.
"""

import asyncio
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
from tests.base import BaseTestCase


class TestMessageHistoryService(BaseTestCase):
    """Test cases for MessageHistoryService"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
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
        
        self.broadcast_message = Message(
            id="broadcast_msg_1",
            sender_id="!12345678",
            content="Broadcast message",
            timestamp=datetime.utcnow(),
            channel=0
        )
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
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
    async def test_store_message_in_history(self):
        """Test storing message in history database"""
        with patch.object(self.service, '_store_message_in_history', new_callable=AsyncMock) as mock_store:
            await self.service.handle_message(self.test_message)
            mock_store.assert_called_once_with(self.test_message)
    
    @pytest.mark.asyncio
    async def test_update_user_activity(self):
        """Test updating user activity"""
        user_id = "!12345678"
        
        with patch.object(self.service, '_update_user_activity', new_callable=AsyncMock) as mock_update:
            await self.service.handle_message(self.test_message)
            mock_update.assert_called_once_with(user_id)
    
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
            },
            {
                'timestamp': '2024-01-01T12:01:00',
                'sender_id': '!11111111',
                'content': 'Test message 2'
            }
        ]
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock, return_value=mock_messages):
            response = await self.service.handle_message(history_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Message History", response.content)
            self.assertIn("4321: Test message 1", response.content)
            self.assertIn("1111: Test message 2", response.content)
    
    async def test_history_command_with_filters(self):
        """Test history command with filters"""
        history_message = Message(
            sender_id="!12345678",
            content="history sender:!87654321 hours:2 limit:5",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            await self.service.handle_message(history_message)
            
            # Verify filter criteria
            call_args = mock_get.call_args[0][0]
            self.assertEqual(call_args.sender_id, "!87654321")
            self.assertEqual(call_args.limit, 5)
            self.assertIsNotNone(call_args.start_time)
    
    async def test_messages_command(self):
        """Test messages command"""
        messages_message = Message(
            sender_id="!12345678",
            content="messages 3",
            timestamp=datetime.utcnow()
        )
        
        mock_messages = [
            {
                'timestamp': '2024-01-01T12:00:00',
                'sender_id': '!87654321',
                'content': 'Recent message 1'
            }
        ]
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock, return_value=mock_messages):
            response = await self.service.handle_message(messages_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Recent Messages", response.content)
            self.assertIn("4321: Recent message 1", response.content)
    
    async def test_replay_command(self):
        """Test replay command"""
        replay_message = Message(
            sender_id="!12345678",
            content="replay 1 sender:!87654321",
            timestamp=datetime.utcnow()
        )
        
        mock_messages = [
            {
                'timestamp': '2024-01-01T12:00:00',
                'sender_id': '!87654321',
                'channel': 0,
                'content': 'Replayed message'
            }
        ]
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock, return_value=mock_messages):
            response = await self.service.handle_message(replay_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Message Replay", response.content)
            self.assertIn("4321 : Replayed message", response.content)
    
    async def test_replay_command_invalid_hours(self):
        """Test replay command with invalid hours"""
        replay_message = Message(
            sender_id="!12345678",
            content="replay invalid",
            timestamp=datetime.utcnow()
        )
        
        response = await self.service.handle_message(replay_message)
        
        self.assertIsNotNone(response)
        self.assertIn("Invalid hours parameter", response.content)
    
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
    
    async def test_pending_command_with_messages(self):
        """Test pending command with pending messages"""
        user_id = "!12345678"
        
        # Add pending message
        stored_msg = StoredMessage(
            id="pending_1",
            recipient_id=user_id,
            sender_id="!87654321",
            content="Pending message content",
            timestamp=datetime.utcnow(),
            priority=MessagePriority.NORMAL,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.service.pending_messages["pending_1"] = stored_msg
        
        pending_message = Message(
            sender_id=user_id,
            content="pending",
            timestamp=datetime.utcnow()
        )
        
        response = await self.service.handle_message(pending_message)
        
        self.assertIsNotNone(response)
        self.assertIn("You have 1 pending messages", response.content)
        self.assertIn("4321: Pending message content", response.content)
    
    async def test_store_and_forward_offline_user(self):
        """Test store-and-forward for offline user"""
        direct_message = Message(
            sender_id="!12345678",
            recipient_id="!87654321",
            content="Message for offline user",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(self.service, '_is_user_online', new_callable=AsyncMock, return_value=False):
            with patch.object(self.service, '_store_offline_message', new_callable=AsyncMock) as mock_store:
                await self.service.handle_message(direct_message)
                mock_store.assert_called_once_with(direct_message)
    
    async def test_store_and_forward_online_user(self):
        """Test store-and-forward for online user (should not store)"""
        direct_message = Message(
            sender_id="!12345678",
            recipient_id="!87654321",
            content="Message for online user",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(self.service, '_is_user_online', new_callable=AsyncMock, return_value=True):
            with patch.object(self.service, '_store_offline_message', new_callable=AsyncMock) as mock_store:
                await self.service.handle_message(direct_message)
                mock_store.assert_not_called()
    
    async def test_is_user_online_recent_activity(self):
        """Test user online check with recent activity"""
        user_id = "!12345678"
        recent_time = datetime.utcnow() - timedelta(minutes=5)
        
        mock_rows = [{'last_seen': recent_time.isoformat()}]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            is_online = await self.service._is_user_online(user_id)
            self.assertTrue(is_online)
    
    async def test_is_user_online_old_activity(self):
        """Test user online check with old activity"""
        user_id = "!12345678"
        old_time = datetime.utcnow() - timedelta(hours=1)
        
        mock_rows = [{'last_seen': old_time.isoformat()}]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            is_online = await self.service._is_user_online(user_id)
            self.assertFalse(is_online)
    
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
            
            # Check database was updated
            mock_execute.assert_called_once()
    
    async def test_store_offline_message_max_limit(self):
        """Test storing offline message when user has max pending messages"""
        recipient_id = "!87654321"
        
        # Fill up pending messages for user
        for i in range(self.config['max_offline_messages']):
            stored_msg = StoredMessage(
                id=f"msg_{i}",
                recipient_id=recipient_id,
                sender_id="!12345678",
                content=f"Message {i}",
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                priority=MessagePriority.NORMAL,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            self.service.pending_messages[f"msg_{i}"] = stored_msg
        
        # Add offline user
        self.service.offline_users[recipient_id] = OfflineUser(
            node_id=recipient_id,
            last_seen=datetime.utcnow() - timedelta(hours=1),
            pending_messages=[f"msg_{i}" for i in range(self.config['max_offline_messages'])]
        )
        
        # Try to store another message
        new_message = Message(
            sender_id="!12345678",
            recipient_id=recipient_id,
            content="New message",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(self.service.db, 'execute_update'):
            await self.service._store_offline_message(new_message)
            
            # Should still have max messages (oldest removed)
            user_messages = [msg for msg in self.service.pending_messages.values() 
                           if msg.recipient_id == recipient_id]
            self.assertEqual(len(user_messages), self.config['max_offline_messages'])
            
            # New message should be stored
            self.assertIn(new_message.id, self.service.pending_messages)
    
    async def test_deliver_pending_messages(self):
        """Test delivering pending messages to online user"""
        user_id = "!12345678"
        
        # Add pending messages
        for i in range(3):
            stored_msg = StoredMessage(
                id=f"pending_{i}",
                recipient_id=user_id,
                sender_id="!87654321",
                content=f"Pending message {i}",
                timestamp=datetime.utcnow(),
                priority=MessagePriority.NORMAL,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            self.service.pending_messages[f"pending_{i}"] = stored_msg
        
        # Add offline user
        self.service.offline_users[user_id] = OfflineUser(
            node_id=user_id,
            last_seen=datetime.utcnow() - timedelta(hours=1),
            pending_messages=[f"pending_{i}" for i in range(3)]
        )
        
        with patch.object(self.service.db, 'execute_update'):
            await self.service._deliver_pending_messages(user_id)
            
            # Check messages were sent
            self.assertEqual(self.mock_communication.send_mesh_message.call_count, 4)  # 3 messages + 1 summary
            
            # Check pending messages were cleared
            user_messages = [msg for msg in self.service.pending_messages.values() 
                           if msg.recipient_id == user_id]
            self.assertEqual(len(user_messages), 0)
    
    async def test_deliver_pending_messages_expired(self):
        """Test delivering pending messages with expired messages"""
        user_id = "!12345678"
        
        # Add expired pending message
        expired_msg = StoredMessage(
            id="expired_msg",
            recipient_id=user_id,
            sender_id="!87654321",
            content="Expired message",
            timestamp=datetime.utcnow() - timedelta(hours=25),
            priority=MessagePriority.NORMAL,
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        self.service.pending_messages["expired_msg"] = expired_msg
        
        # Add offline user
        self.service.offline_users[user_id] = OfflineUser(
            node_id=user_id,
            last_seen=datetime.utcnow() - timedelta(hours=1),
            pending_messages=["expired_msg"]
        )
        
        with patch.object(self.service.db, 'execute_update'):
            await self.service._deliver_pending_messages(user_id)
            
            # Expired message should not be delivered
            self.mock_communication.send_mesh_message.assert_not_called()
            
            # Expired message should be removed
            self.assertNotIn("expired_msg", self.service.pending_messages)
    
    async def test_get_message_history_with_filters(self):
        """Test getting message history with various filters"""
        filter_criteria = MessageFilter(
            sender_id="!12345678",
            channel=0,
            content_pattern="test",
            start_time=datetime.utcnow() - timedelta(hours=1),
            limit=10
        )
        
        mock_rows = [
            {
                'message_id': 'msg_1',
                'sender_id': '!12345678',
                'content': 'Test message',
                'timestamp': '2024-01-01T12:00:00',
                'channel': 0
            }
        ]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            messages = await self.service._get_message_history(filter_criteria)
            
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]['content'], 'Test message')
    
    async def test_chunked_response_large_replay(self):
        """Test chunked response for large replay results"""
        replay_message = Message(
            sender_id="!12345678",
            content="replay 1",
            timestamp=datetime.utcnow()
        )
        
        # Create large message list that will exceed chunk size
        large_messages = []
        for i in range(20):
            large_messages.append({
                'timestamp': '2024-01-01T12:00:00',
                'sender_id': f'!{i:08d}',
                'channel': 0,
                'content': f'This is a long message content that will help exceed the chunk size limit {i}'
            })
        
        with patch.object(self.service, '_get_message_history', new_callable=AsyncMock, return_value=large_messages):
            with patch.object(self.service, '_send_chunked_response', new_callable=AsyncMock) as mock_chunked:
                response = await self.service.handle_message(replay_message)
                
                # Should use chunked response for large results
                mock_chunked.assert_called_once()
                self.assertIsNone(response)  # No direct response when chunked
    
    async def test_send_chunked_response(self):
        """Test sending chunked response"""
        response_parts = ["Part 1 content", "Part 2 content", "Part 3 content"]
        original_message = Message(
            sender_id="!12345678",
            content="test",
            timestamp=datetime.utcnow()
        )
        
        await self.service._send_chunked_response(response_parts, original_message)
        
        # Should send 3 chunks
        self.assertEqual(self.mock_communication.send_mesh_message.call_count, 3)
        
        # Check chunk headers
        calls = self.mock_communication.send_mesh_message.call_args_list
        self.assertIn("[1/3]", calls[0][0][0].content)
        self.assertIn("[2/3]", calls[1][0][0].content)
        self.assertIn("[3/3]", calls[2][0][0].content)
    
    async def test_load_offline_users(self):
        """Test loading offline users from database"""
        mock_rows = [
            {
                'node_id': '!12345678',
                'last_seen': (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                'node_id': '!87654321',
                'last_seen': (datetime.utcnow() - timedelta(minutes=5)).isoformat()
            }
        ]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            await self.service._load_offline_users()
            
            # Should load offline users (those not seen in last 10 minutes)
            self.assertIn('!12345678', self.service.offline_users)
            self.assertNotIn('!87654321', self.service.offline_users)  # Too recent
    
    async def test_load_pending_messages(self):
        """Test loading pending messages from database"""
        mock_rows = [
            {
                'key': 'pending_message_msg_1',
                'value': json.dumps({
                    'recipient_id': '!12345678',
                    'sender_id': '!87654321',
                    'content': 'Pending message',
                    'timestamp': datetime.utcnow().isoformat(),
                    'priority': MessagePriority.NORMAL.value,
                    'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                    'metadata': {}
                })
            }
        ]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            await self.service._load_pending_messages()
            
            # Should load pending message
            self.assertIn('msg_1', self.service.pending_messages)
            stored_msg = self.service.pending_messages['msg_1']
            self.assertEqual(stored_msg.recipient_id, '!12345678')
            self.assertEqual(stored_msg.content, 'Pending message')
    
    async def test_load_pending_messages_expired(self):
        """Test loading pending messages with expired message"""
        mock_rows = [
            {
                'key': 'pending_message_expired_msg',
                'value': json.dumps({
                    'recipient_id': '!12345678',
                    'sender_id': '!87654321',
                    'content': 'Expired message',
                    'timestamp': (datetime.utcnow() - timedelta(hours=25)).isoformat(),
                    'priority': MessagePriority.NORMAL.value,
                    'expires_at': (datetime.utcnow() - timedelta(hours=1)).isoformat(),  # Expired
                    'metadata': {}
                })
            }
        ]
        
        with patch.object(self.service.db, 'execute_query', return_value=mock_rows):
            with patch.object(self.service.db, 'execute_update') as mock_delete:
                await self.service._load_pending_messages()
                
                # Expired message should not be loaded
                self.assertNotIn('expired_msg', self.service.pending_messages)
                
                # Should delete expired message from database
                mock_delete.assert_called_once()
    
    async def test_cleanup_expired_messages(self):
        """Test cleanup of expired pending messages"""
        # Add expired message
        expired_msg = StoredMessage(
            id="expired_msg",
            recipient_id="!12345678",
            sender_id="!87654321",
            content="Expired message",
            timestamp=datetime.utcnow() - timedelta(hours=25),
            priority=MessagePriority.NORMAL,
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        self.service.pending_messages["expired_msg"] = expired_msg
        
        # Add offline user with expired message
        self.service.offline_users["!12345678"] = OfflineUser(
            node_id="!12345678",
            last_seen=datetime.utcnow() - timedelta(hours=1),
            pending_messages=["expired_msg"]
        )
        
        with patch.object(self.service.db, 'execute_update'):
            await self.service._cleanup_task()
            
            # Expired message should be removed
            self.assertNotIn("expired_msg", self.service.pending_messages)
            
            # Should be removed from offline user tracking
            self.assertNotIn("expired_msg", self.service.offline_users["!12345678"].pending_messages)
    
    async def test_cleanup_old_history(self):
        """Test cleanup of old message history"""
        with patch.object(self.service.db, 'execute_update', return_value=5) as mock_execute:
            await self.service._cleanup_old_history()
            
            # Should delete old messages
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0]
            self.assertIn("DELETE FROM message_history", call_args[0])
    
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


class TestMessageFilter(BaseTestCase):
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


class TestStoredMessage(BaseTestCase):
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


class TestOfflineUser(BaseTestCase):
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