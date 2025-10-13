"""
Integration tests for Message History Service

Tests integration between message history service and other components,
including database operations, message routing, and store-and-forward functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from src.services.bot.message_history_service import MessageHistoryService
from src.services.bot.interactive_bot_service import InteractiveBotService
from src.models.message import Message, MessageType, MessagePriority
from src.core.database import get_database, initialize_database
from src.core.plugin_interfaces import PluginCommunicationInterface
from tests.base import BaseTestCase


class TestMessageHistoryIntegration(BaseTestCase):
    """Integration test cases for MessageHistoryService"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Initialize test database
        self.db = initialize_database(":memory:")
        
        # Test configuration
        self.config = {
            'message_history': {
                'history_retention_days': 7,
                'max_offline_messages': 5,
                'offline_message_ttl_hours': 24,
                'max_message_chunk_size': 100,
                'store_forward_enabled': True,
                'chunk_responses': True,
                'offline_check_interval': 1,  # Fast for testing
                'cleanup_interval': 1,  # Fast for testing
                'max_history_results': 20,
                'enable_message_search': True,
                'enable_replay_system': True
            }
        }
        
        # Create service instances
        self.history_service = MessageHistoryService(self.config['message_history'])
        self.bot_service = InteractiveBotService(self.config)
        
        # Mock communication interface
        self.mock_communication = Mock(spec=PluginCommunicationInterface)
        self.mock_communication.send_mesh_message = AsyncMock()
        
        self.history_service.set_communication_interface(self.mock_communication)
        self.bot_service.set_communication_interface(self.mock_communication)
        
        # Test users
        self.test_users = [
            {
                'node_id': '!12345678',
                'short_name': 'TEST1',
                'long_name': 'Test User 1',
                'last_seen': datetime.utcnow().isoformat(),
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            },
            {
                'node_id': '!87654321',
                'short_name': 'TEST2',
                'long_name': 'Test User 2',
                'last_seen': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            }
        ]
        
        # Insert test users
        for user in self.test_users:
            self.db.upsert_user(user)
    
    async def test_full_message_history_workflow(self):
        """Test complete message history workflow"""
        await self.history_service.start()
        
        try:
            # Send some test messages
            messages = [
                Message(
                    id="msg_1",
                    sender_id="!12345678",
                    content="First test message",
                    timestamp=datetime.utcnow() - timedelta(minutes=30),
                    channel=0
                ),
                Message(
                    id="msg_2",
                    sender_id="!87654321",
                    content="Second test message",
                    timestamp=datetime.utcnow() - timedelta(minutes=20),
                    channel=0
                ),
                Message(
                    id="msg_3",
                    sender_id="!12345678",
                    content="Third test message with keyword test",
                    timestamp=datetime.utcnow() - timedelta(minutes=10),
                    channel=1
                )
            ]
            
            # Process messages through history service
            for msg in messages:
                await self.history_service.handle_message(msg)
            
            # Test history command
            history_request = Message(
                sender_id="!12345678",
                content="history",
                timestamp=datetime.utcnow()
            )
            
            response = await self.history_service.handle_message(history_request)
            
            self.assertIsNotNone(response)
            self.assertIn("Message History", response.content)
            self.assertIn("First test message", response.content)
            self.assertIn("Second test message", response.content)
            
        finally:
            await self.history_service.stop()
    
    async def test_store_and_forward_integration(self):
        """Test store-and-forward integration with database"""
        await self.history_service.start()
        
        try:
            # Create direct message to offline user
            offline_message = Message(
                id="offline_msg_1",
                sender_id="!12345678",
                recipient_id="!87654321",  # This user is offline (last seen 2 hours ago)
                content="Message for offline user",
                timestamp=datetime.utcnow()
            )
            
            # Process message
            await self.history_service.handle_message(offline_message)
            
            # Verify message was stored for offline user
            self.assertIn("offline_msg_1", self.history_service.pending_messages)
            stored_msg = self.history_service.pending_messages["offline_msg_1"]
            self.assertEqual(stored_msg.recipient_id, "!87654321")
            self.assertEqual(stored_msg.content, "Message for offline user")
            
            # Verify offline user tracking
            self.assertIn("!87654321", self.history_service.offline_users)
            offline_user = self.history_service.offline_users["!87654321"]
            self.assertIn("offline_msg_1", offline_user.pending_messages)
            
            # Simulate user coming online by updating their last_seen
            self.db.execute_update(
                "UPDATE users SET last_seen = ? WHERE node_id = ?",
                (datetime.utcnow().isoformat(), "!87654321")
            )
            
            # Simulate user activity (should trigger message delivery)
            online_message = Message(
                sender_id="!87654321",
                content="I'm back online",
                timestamp=datetime.utcnow()
            )
            
            await self.history_service.handle_message(online_message)
            
            # Verify pending message was delivered
            self.mock_communication.send_mesh_message.assert_called()
            
            # Check that offline message was delivered
            calls = self.mock_communication.send_mesh_message.call_args_list
            delivery_call = None
            for call in calls:
                msg = call[0][0]
                if "Offline message from" in msg.content:
                    delivery_call = call
                    break
            
            self.assertIsNotNone(delivery_call)
            delivered_msg = delivery_call[0][0]
            self.assertEqual(delivered_msg.recipient_id, "!87654321")
            self.assertIn("Message for offline user", delivered_msg.content)
            
        finally:
            await self.history_service.stop()
    
    async def test_message_search_and_filtering(self):
        """Test message search and filtering functionality"""
        await self.history_service.start()
        
        try:
            # Insert test messages directly into database
            test_messages = [
                {
                    'message_id': 'search_msg_1',
                    'sender_id': '!12345678',
                    'recipient_id': None,
                    'channel': 0,
                    'content': 'This is a test message about weather',
                    'timestamp': (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                    'interface_id': 'test_interface',
                    'hop_count': 0,
                    'snr': None,
                    'rssi': None
                },
                {
                    'message_id': 'search_msg_2',
                    'sender_id': '!87654321',
                    'recipient_id': None,
                    'channel': 1,
                    'content': 'Another message about emergency procedures',
                    'timestamp': (datetime.utcnow() - timedelta(minutes=20)).isoformat(),
                    'interface_id': 'test_interface',
                    'hop_count': 1,
                    'snr': 5.0,
                    'rssi': -80.0
                },
                {
                    'message_id': 'search_msg_3',
                    'sender_id': '!12345678',
                    'recipient_id': '!87654321',
                    'channel': 0,
                    'content': 'Direct message with weather info',
                    'timestamp': (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                    'interface_id': 'test_interface',
                    'hop_count': 0,
                    'snr': None,
                    'rssi': None
                }
            ]
            
            for msg_data in test_messages:
                self.db.execute_update(
                    """
                    INSERT INTO message_history 
                    (message_id, sender_id, recipient_id, channel, content, timestamp, 
                     interface_id, hop_count, snr, rssi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(msg_data.values())
                )
            
            # Test search by content pattern
            search_request = Message(
                sender_id="!12345678",
                content="history search:weather",
                timestamp=datetime.utcnow()
            )
            
            response = await self.history_service.handle_message(search_request)
            
            self.assertIsNotNone(response)
            self.assertIn("Message History", response.content)
            self.assertIn("weather", response.content.lower())
            
            # Test search by sender
            sender_search = Message(
                sender_id="!12345678",
                content="history sender:!87654321",
                timestamp=datetime.utcnow()
            )
            
            response = await self.history_service.handle_message(sender_search)
            
            self.assertIsNotNone(response)
            self.assertIn("4321: Another message about emergency", response.content)
            
            # Test search by channel
            channel_search = Message(
                sender_id="!12345678",
                content="history channel:1",
                timestamp=datetime.utcnow()
            )
            
            response = await self.history_service.handle_message(channel_search)
            
            self.assertIsNotNone(response)
            self.assertIn("emergency procedures", response.content)
            
        finally:
            await self.history_service.stop()
    
    async def test_replay_system_with_chunking(self):
        """Test replay system with message chunking for large responses"""
        await self.history_service.start()
        
        try:
            # Insert many messages to trigger chunking
            for i in range(15):
                msg_data = {
                    'message_id': f'replay_msg_{i}',
                    'sender_id': f'!{i:08d}',
                    'recipient_id': None,
                    'channel': 0,
                    'content': f'This is replay test message number {i} with some additional content to make it longer',
                    'timestamp': (datetime.utcnow() - timedelta(minutes=60-i)).isoformat(),
                    'interface_id': 'test_interface',
                    'hop_count': 0,
                    'snr': None,
                    'rssi': None
                }
                
                self.db.execute_update(
                    """
                    INSERT INTO message_history 
                    (message_id, sender_id, recipient_id, channel, content, timestamp, 
                     interface_id, hop_count, snr, rssi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(msg_data.values())
                )
            
            # Test replay command that should trigger chunking
            replay_request = Message(
                sender_id="!12345678",
                content="replay 1",
                timestamp=datetime.utcnow()
            )
            
            response = await self.history_service.handle_message(replay_request)
            
            # Should return None when chunking is used
            self.assertIsNone(response)
            
            # Should have sent multiple chunked messages
            self.assertGreater(self.mock_communication.send_mesh_message.call_count, 1)
            
            # Verify chunk headers
            calls = self.mock_communication.send_mesh_message.call_args_list
            chunk_messages = [call[0][0] for call in calls]
            
            # Check for chunk indicators
            chunk_found = False
            for msg in chunk_messages:
                if "[1/" in msg.content and "]" in msg.content:
                    chunk_found = True
                    break
            
            self.assertTrue(chunk_found, "Should have found chunked messages")
            
        finally:
            await self.history_service.stop()
    
    async def test_pending_messages_persistence(self):
        """Test pending messages persistence across service restarts"""
        # Start service and create pending message
        await self.history_service.start()
        
        offline_message = Message(
            id="persistent_msg",
            sender_id="!12345678",
            recipient_id="!87654321",
            content="Persistent offline message",
            timestamp=datetime.utcnow()
        )
        
        await self.history_service.handle_message(offline_message)
        
        # Verify message was stored
        self.assertIn("persistent_msg", self.history_service.pending_messages)
        
        # Stop service
        await self.history_service.stop()
        
        # Create new service instance and start
        new_service = MessageHistoryService(self.config['message_history'])
        new_service.set_communication_interface(self.mock_communication)
        await new_service.start()
        
        try:
            # Verify pending message was loaded
            self.assertIn("persistent_msg", new_service.pending_messages)
            stored_msg = new_service.pending_messages["persistent_msg"]
            self.assertEqual(stored_msg.content, "Persistent offline message")
            self.assertEqual(stored_msg.recipient_id, "!87654321")
            
        finally:
            await new_service.stop()
    
    async def test_integration_with_bot_service(self):
        """Test integration with InteractiveBotService"""
        await self.bot_service.start()
        
        try:
            # Test that history commands are handled by message history service
            history_message = Message(
                sender_id="!12345678",
                content="history",
                timestamp=datetime.utcnow()
            )
            
            response = await self.bot_service.handle_message(history_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Message History", response.content)
            
            # Test messages command
            messages_message = Message(
                sender_id="!12345678",
                content="messages",
                timestamp=datetime.utcnow()
            )
            
            response = await self.bot_service.handle_message(messages_message)
            
            self.assertIsNotNone(response)
            self.assertIn("Recent Messages", response.content)
            
        finally:
            await self.bot_service.stop()
    
    async def test_offline_user_detection_and_cleanup(self):
        """Test offline user detection and cleanup processes"""
        await self.history_service.start()
        
        try:
            # Create messages for users with different activity levels
            recent_message = Message(
                sender_id="!12345678",  # This user is online
                content="Recent activity",
                timestamp=datetime.utcnow()
            )
            
            old_message = Message(
                sender_id="!87654321",  # This user is offline
                content="Old activity",
                timestamp=datetime.utcnow()
            )
            
            # Process messages
            await self.history_service.handle_message(recent_message)
            await self.history_service.handle_message(old_message)
            
            # Wait for offline check task to run
            await asyncio.sleep(0.1)
            
            # Verify offline user detection
            self.assertIn("!87654321", self.history_service.offline_users)
            self.assertNotIn("!12345678", self.history_service.offline_users)
            
            # Create expired pending message
            from src.services.bot.message_history_service import StoredMessage
            expired_msg = StoredMessage(
                id="expired_test",
                recipient_id="!87654321",
                sender_id="!12345678",
                content="Expired message",
                timestamp=datetime.utcnow() - timedelta(hours=25),
                priority=MessagePriority.NORMAL,
                expires_at=datetime.utcnow() - timedelta(hours=1)  # Already expired
            )
            
            self.history_service.pending_messages["expired_test"] = expired_msg
            self.history_service.offline_users["!87654321"].pending_messages.append("expired_test")
            
            # Wait for cleanup task to run
            await asyncio.sleep(0.1)
            
            # Verify expired message was cleaned up
            self.assertNotIn("expired_test", self.history_service.pending_messages)
            
        finally:
            await self.history_service.stop()
    
    async def test_message_history_database_operations(self):
        """Test database operations for message history"""
        await self.history_service.start()
        
        try:
            # Test message storage
            test_message = Message(
                id="db_test_msg",
                sender_id="!12345678",
                recipient_id="!87654321",
                content="Database test message",
                timestamp=datetime.utcnow(),
                channel=1,
                interface_id="test_interface",
                hop_count=2,
                snr=3.5,
                rssi=-75.0
            )
            
            await self.history_service.handle_message(test_message)
            
            # Verify message was stored in database
            rows = self.db.execute_query(
                "SELECT * FROM message_history WHERE message_id = ?",
                ("db_test_msg",)
            )
            
            self.assertEqual(len(rows), 1)
            stored_msg = rows[0]
            self.assertEqual(stored_msg['sender_id'], "!12345678")
            self.assertEqual(stored_msg['recipient_id'], "!87654321")
            self.assertEqual(stored_msg['content'], "Database test message")
            self.assertEqual(stored_msg['channel'], 1)
            self.assertEqual(stored_msg['hop_count'], 2)
            self.assertEqual(stored_msg['snr'], 3.5)
            self.assertEqual(stored_msg['rssi'], -75.0)
            
            # Test message retrieval with filters
            from src.services.bot.message_history_service import MessageFilter
            filter_criteria = MessageFilter(
                sender_id="!12345678",
                channel=1,
                limit=10
            )
            
            messages = await self.history_service._get_message_history(filter_criteria)
            
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]['message_id'], "db_test_msg")
            
        finally:
            await self.history_service.stop()
    
    async def test_service_statistics(self):
        """Test service statistics collection"""
        await self.history_service.start()
        
        try:
            # Add some test data
            offline_message = Message(
                id="stats_msg",
                sender_id="!12345678",
                recipient_id="!87654321",
                content="Message for stats",
                timestamp=datetime.utcnow()
            )
            
            await self.history_service.handle_message(offline_message)
            
            # Get statistics
            stats = self.history_service.get_stats()
            
            self.assertIn('offline_users', stats)
            self.assertIn('pending_messages', stats)
            self.assertIn('store_forward_enabled', stats)
            self.assertIn('history_retention_days', stats)
            
            self.assertGreaterEqual(stats['offline_users'], 1)
            self.assertGreaterEqual(stats['pending_messages'], 1)
            self.assertTrue(stats['store_forward_enabled'])
            self.assertEqual(stats['history_retention_days'], 7)
            
        finally:
            await self.history_service.stop()


if __name__ == '__main__':
    pytest.main([__file__])