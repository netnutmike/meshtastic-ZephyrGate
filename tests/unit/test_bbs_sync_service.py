"""
Unit tests for BBS Synchronization Service
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.bbs.sync_service import (
    BBSSyncService, SyncPeer, SyncMessage, SyncMessageType, ConflictResolution
)
from src.services.bbs.models import BBSBulletin, BBSMail, BBSChannel, ChannelType
from src.models.message import Message, MessageType


class TestSyncPeer:
    """Test SyncPeer class"""
    
    def test_sync_peer_creation(self):
        """Test creating a sync peer"""
        peer = SyncPeer(
            node_id="!12345678",
            name="TestBBS",
            sync_enabled=True,
            priority=2
        )
        
        assert peer.node_id == "!12345678"
        assert peer.name == "TestBBS"
        assert peer.sync_enabled is True
        assert peer.priority == 2
        assert peer.sync_bulletins is True
        assert peer.sync_mail is True
        assert peer.sync_channels is True
        assert peer.max_sync_age_days == 30
    
    def test_should_sync_with(self):
        """Test sync age checking"""
        peer = SyncPeer(
            node_id="!12345678",
            name="TestBBS",
            max_sync_age_days=7
        )
        
        # Recent message should sync
        recent_age = timedelta(days=3)
        assert peer.should_sync_with(recent_age) is True
        
        # Old message should not sync
        old_age = timedelta(days=10)
        assert peer.should_sync_with(old_age) is False


class TestSyncMessage:
    """Test SyncMessage class"""
    
    def test_sync_message_creation(self):
        """Test creating a sync message"""
        msg = SyncMessage(
            message_type=SyncMessageType.SYNC_REQUEST,
            sender_id="!12345678",
            recipient_id="!87654321",
            data={"test": "data"}
        )
        
        assert msg.message_type == SyncMessageType.SYNC_REQUEST
        assert msg.sender_id == "!12345678"
        assert msg.recipient_id == "!87654321"
        assert msg.data == {"test": "data"}
        assert len(msg.sync_id) == 16
    
    def test_to_mesh_message(self):
        """Test converting to mesh message format"""
        msg = SyncMessage(
            message_type=SyncMessageType.PEER_ANNOUNCE,
            sender_id="!12345678",
            recipient_id=None,
            data={"name": "TestBBS"}
        )
        
        mesh_msg = msg.to_mesh_message()
        data = json.loads(mesh_msg)
        
        assert data['type'] == 'bbs_sync'
        assert data['sync_type'] == 'peer_announce'
        assert data['sender'] == '!12345678'
        assert data['recipient'] is None
        assert data['data'] == {"name": "TestBBS"}
        assert 'timestamp' in data
        assert 'sync_id' in data
    
    def test_from_mesh_message(self):
        """Test creating from mesh message"""
        mesh_data = {
            'type': 'bbs_sync',
            'sync_type': 'sync_request',
            'sender': '!12345678',
            'recipient': '!87654321',
            'data': {'test': 'data'},
            'timestamp': '2024-01-01T12:00:00',
            'sync_id': 'test123'
        }
        
        mesh_msg = json.dumps(mesh_data)
        sync_msg = SyncMessage.from_mesh_message(mesh_msg)
        
        assert sync_msg is not None
        assert sync_msg.message_type == SyncMessageType.SYNC_REQUEST
        assert sync_msg.sender_id == '!12345678'
        assert sync_msg.recipient_id == '!87654321'
        assert sync_msg.data == {'test': 'data'}
        assert sync_msg.sync_id == 'test123'
    
    def test_from_invalid_mesh_message(self):
        """Test handling invalid mesh message"""
        # Invalid JSON
        assert SyncMessage.from_mesh_message("invalid json") is None
        
        # Wrong type
        wrong_type = json.dumps({'type': 'other', 'sync_type': 'test'})
        assert SyncMessage.from_mesh_message(wrong_type) is None
        
        # Missing fields
        incomplete = json.dumps({'type': 'bbs_sync'})
        assert SyncMessage.from_mesh_message(incomplete) is None


class TestBBSSyncService:
    """Test BBSSyncService class"""
    
    @pytest.fixture
    def mock_interface_manager(self):
        """Mock interface manager"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_db(self):
        """Mock BBS database"""
        with patch('src.services.bbs.sync_service.get_bbs_database') as mock:
            db = MagicMock()
            mock.return_value = db
            yield db
    
    @pytest.fixture
    def sync_service(self, mock_interface_manager, mock_db):
        """Create sync service for testing"""
        service = BBSSyncService(mock_interface_manager, "!12345678")
        return service
    
    def test_sync_service_creation(self, sync_service):
        """Test creating sync service"""
        assert sync_service.node_id == "!12345678"
        assert sync_service.sync_enabled is True
        assert sync_service.sync_interval_minutes == 30
        assert sync_service.max_sync_batch_size == 10
        assert sync_service.conflict_resolution == ConflictResolution.TIMESTAMP_WINS
        assert len(sync_service.peers) == 0
    
    def test_add_remove_peer(self, sync_service):
        """Test adding and removing peers"""
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        
        # Add peer
        sync_service.add_peer(peer)
        assert len(sync_service.peers) == 1
        assert sync_service.get_peer("!87654321") == peer
        
        # Remove peer
        sync_service.remove_peer("!87654321")
        assert len(sync_service.peers) == 0
        assert sync_service.get_peer("!87654321") is None
    
    @pytest.mark.asyncio
    async def test_start_stop(self, sync_service):
        """Test starting and stopping sync service"""
        # Start service
        await sync_service.start()
        assert sync_service._sync_task is not None
        assert not sync_service._sync_task.done()
        
        # Stop service
        await sync_service.stop()
        assert sync_service._sync_task.done()
    
    @pytest.mark.asyncio
    async def test_handle_peer_discovery(self, sync_service):
        """Test handling peer discovery"""
        # Create discovery message
        discovery_data = {
            'type': 'bbs_sync',
            'sync_type': 'peer_discovery',
            'sender': '!87654321',
            'recipient': None,
            'data': {'requesting_node': '!87654321'},
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!87654321",
            content=json.dumps(discovery_data),
            message_type=MessageType.TEXT
        )
        
        # Handle message
        result = await sync_service.handle_message(message)
        assert result is True
        
        # Should have sent a peer announce response
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'peer_announce'
        assert sent_data['recipient'] == '!87654321'
    
    @pytest.mark.asyncio
    async def test_handle_peer_announce(self, sync_service):
        """Test handling peer announcement"""
        # Create announce message
        announce_data = {
            'type': 'bbs_sync',
            'sync_type': 'peer_announce',
            'sender': '!87654321',
            'recipient': None,
            'data': {
                'name': 'RemoteBBS',
                'capabilities': {'bulletins': True, 'mail': True}
            },
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!87654321",
            content=json.dumps(announce_data),
            message_type=MessageType.TEXT
        )
        
        # Handle message
        result = await sync_service.handle_message(message)
        assert result is True
        
        # Should have auto-added the peer
        assert len(sync_service.peers) == 1
        peer = sync_service.get_peer("!87654321")
        assert peer is not None
        assert peer.name == "RemoteBBS"
    
    @pytest.mark.asyncio
    async def test_sync_with_peer(self, sync_service, mock_db):
        """Test syncing with a peer"""
        # Add a peer
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        sync_service.add_peer(peer)
        
        # Sync with peer
        result = await sync_service.sync_with_peer("!87654321")
        assert result is True
        
        # Should have sent sync request
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'sync_request'
        assert sent_data['recipient'] == '!87654321'
    
    @pytest.mark.asyncio
    async def test_sync_with_disabled_peer(self, sync_service):
        """Test syncing with disabled peer"""
        # Add disabled peer
        peer = SyncPeer(node_id="!87654321", name="TestPeer", sync_enabled=False)
        sync_service.add_peer(peer)
        
        # Try to sync
        result = await sync_service.sync_with_peer("!87654321")
        assert result is False
        
        # Should not have sent any messages
        sync_service.interface_manager.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_sync_all_peers(self, sync_service):
        """Test syncing with all peers"""
        # Add multiple peers
        peer1 = SyncPeer(node_id="!11111111", name="Peer1")
        peer2 = SyncPeer(node_id="!22222222", name="Peer2")
        peer3 = SyncPeer(node_id="!33333333", name="Peer3", sync_enabled=False)
        
        sync_service.add_peer(peer1)
        sync_service.add_peer(peer2)
        sync_service.add_peer(peer3)
        
        # Sync all
        success_count = await sync_service.sync_all_peers()
        assert success_count == 2  # Only enabled peers
        
        # Should have sent 2 sync requests
        assert sync_service.interface_manager.send_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_announce_to_network(self, sync_service):
        """Test announcing to network"""
        await sync_service.announce_to_network()
        
        # Should have sent broadcast announce
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'peer_announce'
        assert sent_data['recipient'] is None  # Broadcast
    
    @pytest.mark.asyncio
    async def test_discover_peers(self, sync_service):
        """Test peer discovery"""
        await sync_service.discover_peers()
        
        # Should have sent broadcast discovery
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'peer_discovery'
        assert sent_data['recipient'] is None  # Broadcast
    
    @pytest.mark.asyncio
    async def test_handle_sync_request(self, sync_service, mock_db):
        """Test handling sync request"""
        # Add peer
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        sync_service.add_peer(peer)
        
        # Mock database responses
        mock_db.get_all_bulletins.return_value = []
        mock_db.get_all_channels.return_value = []
        
        # Create sync request
        request_data = {
            'type': 'bbs_sync',
            'sync_type': 'sync_request',
            'sender': '!87654321',
            'recipient': '!12345678',
            'data': {
                'last_sync': None,
                'sync_bulletins': True,
                'sync_mail': True,
                'sync_channels': True,
                'max_age_days': 30
            },
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!87654321",
            content=json.dumps(request_data),
            message_type=MessageType.TEXT
        )
        
        # Handle request
        result = await sync_service.handle_message(message)
        assert result is True
        
        # Should have sent sync response
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'sync_response'
        assert sent_data['recipient'] == '!87654321'
        assert 'bulletins' in sent_data['data']
        assert 'channels' in sent_data['data']
    
    @pytest.mark.asyncio
    async def test_handle_sync_response(self, sync_service, mock_db):
        """Test handling sync response"""
        # Add peer
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        sync_service.add_peer(peer)
        
        # Mock database methods
        mock_db.search_bulletins.return_value = []
        mock_db.create_bulletin.return_value = MagicMock()
        mock_db.search_channels.return_value = []
        mock_db.add_channel.return_value = MagicMock()
        
        # Create sync response with test data
        response_data = {
            'type': 'bbs_sync',
            'sync_type': 'sync_response',
            'sender': '!87654321',
            'recipient': '!12345678',
            'data': {
                'bulletins': [{
                    'id': 1,
                    'board': 'general',
                    'sender_id': '!87654321',
                    'sender_name': 'TestUser',
                    'subject': 'Test Bulletin',
                    'content': 'Test content',
                    'timestamp': datetime.utcnow().isoformat(),
                    'unique_id': 'test-unique-id'
                }],
                'channels': [{
                    'id': 1,
                    'name': 'Test Channel',
                    'frequency': '146.520',
                    'description': 'Test channel',
                    'channel_type': 'repeater',
                    'location': 'Test Location',
                    'coverage_area': 'Local',
                    'tone': '100.0',
                    'offset': '+0.6',
                    'added_by': '!87654321',
                    'added_at': datetime.utcnow().isoformat(),
                    'verified': False,
                    'active': True
                }]
            },
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!87654321",
            content=json.dumps(response_data),
            message_type=MessageType.TEXT
        )
        
        # Handle response
        result = await sync_service.handle_message(message)
        assert result is True
        
        # Should have created bulletin and channel
        mock_db.create_bulletin.assert_called_once()
        mock_db.add_channel.assert_called_once()
        
        # Should have sent acknowledgment
        sync_service.interface_manager.send_message.assert_called_once()
        sent_msg = sync_service.interface_manager.send_message.call_args[0][0]
        sent_data = json.loads(sent_msg.content)
        assert sent_data['sync_type'] == 'sync_ack'
        assert sent_data['recipient'] == '!87654321'
        
        # Peer should have updated sync timestamp
        assert peer.last_sync is not None
    
    def test_get_sync_status(self, sync_service):
        """Test getting sync status"""
        # Add some test data
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        sync_service.add_peer(peer)
        sync_service.sync_history.append(("!87654321", datetime.utcnow(), True))
        
        status = sync_service.get_sync_status()
        
        assert status['enabled'] is True
        assert status['peers'] == 1
        assert status['pending_syncs'] == 0
        assert 'last_sync_check' in status
        assert len(status['sync_history']) == 1
        assert status['sync_history'][0]['peer_id'] == "!87654321"
        assert status['sync_history'][0]['success'] is True
    
    @pytest.mark.asyncio
    async def test_ignore_own_messages(self, sync_service):
        """Test ignoring our own sync messages"""
        # Create discovery message from ourselves
        discovery_data = {
            'type': 'bbs_sync',
            'sync_type': 'peer_discovery',
            'sender': '!12345678',  # Our own node ID
            'recipient': None,
            'data': {'requesting_node': '!12345678'},
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!12345678",
            content=json.dumps(discovery_data),
            message_type=MessageType.TEXT
        )
        
        # Handle message
        result = await sync_service.handle_message(message)
        assert result is True
        
        # Should not have sent any response
        sync_service.interface_manager.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_non_sync_message(self, sync_service):
        """Test handling non-sync messages"""
        message = Message(
            sender_id="!87654321",
            content="Regular message",
            message_type=MessageType.TEXT
        )
        
        result = await sync_service.handle_message(message)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_message_for_other_recipient(self, sync_service):
        """Test handling sync message for different recipient"""
        sync_data = {
            'type': 'bbs_sync',
            'sync_type': 'sync_request',
            'sender': '!87654321',
            'recipient': '!99999999',  # Different recipient
            'data': {},
            'timestamp': datetime.utcnow().isoformat(),
            'sync_id': 'test123'
        }
        
        message = Message(
            sender_id="!87654321",
            content=json.dumps(sync_data),
            message_type=MessageType.TEXT
        )
        
        result = await sync_service.handle_message(message)
        assert result is False