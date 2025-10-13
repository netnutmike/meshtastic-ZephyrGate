"""
Integration tests for BBS Synchronization
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.bbs.sync_service import BBSSyncService, SyncPeer, SyncMessage, SyncMessageType
from src.services.bbs.models import BBSBulletin, BBSChannel, ChannelType
from src.services.bbs.database import BBSDatabase
from src.models.message import Message, MessageType


class TestBBSSyncIntegration:
    """Integration tests for BBS synchronization"""
    
    @pytest.fixture
    def mock_interface_manager_a(self):
        """Mock interface manager for Node A"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_interface_manager_b(self):
        """Mock interface manager for Node B"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_db(self):
        """Mock BBS database"""
        with patch('src.services.bbs.sync_service.get_bbs_database') as mock:
            db = MagicMock()
            mock.return_value = db
            yield db
    
    @pytest.fixture
    def sync_service_a(self, mock_interface_manager_a, mock_db):
        """First sync service (Node A)"""
        return BBSSyncService(mock_interface_manager_a, "!AAAAAAAA")
    
    @pytest.fixture
    def sync_service_b(self, mock_interface_manager_b, mock_db):
        """Second sync service (Node B)"""
        return BBSSyncService(mock_interface_manager_b, "!BBBBBBBB")
    
    @pytest.mark.asyncio
    async def test_peer_discovery_flow(self, sync_service_a, sync_service_b):
        """Test complete peer discovery flow"""
        # Node A discovers peers
        await sync_service_a.discover_peers()
        
        # Get the discovery message that would be sent
        sent_calls = sync_service_a.interface_manager.send_message.call_args_list
        assert len(sent_calls) == 1
        
        discovery_msg = sent_calls[0][0][0]
        discovery_data = json.loads(discovery_msg.content)
        
        # Simulate Node B receiving the discovery message
        discovery_message = Message(
            sender_id="!AAAAAAAA",
            content=discovery_msg.content,
            message_type=MessageType.TEXT
        )
        
        # Node B handles discovery and responds
        result = await sync_service_b.handle_message(discovery_message)
        assert result is True
        
        # Node B should have sent an announce response
        sent_calls_b = sync_service_b.interface_manager.send_message.call_args_list
        assert len(sent_calls_b) == 1
        
        announce_msg = sent_calls_b[0][0][0]
        announce_data = json.loads(announce_msg.content)
        assert announce_data['sync_type'] == 'peer_announce'
        assert announce_data['recipient'] == '!AAAAAAAA'
        
        # Simulate Node A receiving the announce response
        announce_message = Message(
            sender_id="!BBBBBBBB",
            content=announce_msg.content,
            message_type=MessageType.TEXT
        )
        
        # Node A handles announce and auto-adds peer
        result = await sync_service_a.handle_message(announce_message)
        assert result is True
        
        # Node A should now have Node B as a peer
        peer_b = sync_service_a.get_peer("!BBBBBBBB")
        assert peer_b is not None
        assert peer_b.name == "BBS-BBBB"
    
    @pytest.mark.asyncio
    async def test_bulletin_sync_flow(self, sync_service_a, sync_service_b, mock_db):
        """Test complete bulletin synchronization flow"""
        # Add Node B as a peer to Node A
        peer_b = SyncPeer(node_id="!BBBBBBBB", name="NodeB")
        sync_service_a.add_peer(peer_b)
        
        # Mock database responses for Node A (requesting sync)
        mock_db.get_all_bulletins.return_value = []
        mock_db.get_all_channels.return_value = []
        
        # Node A initiates sync with Node B
        result = await sync_service_a.sync_with_peer("!BBBBBBBB")
        assert result is True
        
        # Get the sync request message
        sent_calls_a = sync_service_a.interface_manager.send_message.call_args_list
        assert len(sent_calls_a) == 1
        
        sync_request_msg = sent_calls_a[0][0][0]
        sync_request_data = json.loads(sync_request_msg.content)
        assert sync_request_data['sync_type'] == 'sync_request'
        
        # Add Node A as a peer to Node B
        peer_a = SyncPeer(node_id="!AAAAAAAA", name="NodeA")
        sync_service_b.add_peer(peer_a)
        
        # Mock database responses for Node B (responding to sync)
        test_bulletin = BBSBulletin(
            id=1,
            board="general",
            sender_id="!CCCCCCCC",
            sender_name="TestUser",
            subject="Test Bulletin",
            content="This is a test bulletin",
            timestamp=datetime.utcnow()
        )
        
        mock_db.get_all_bulletins.return_value = [test_bulletin]
        mock_db.get_all_channels.return_value = []
        
        # Simulate Node B receiving the sync request
        sync_request_message = Message(
            sender_id="!AAAAAAAA",
            content=sync_request_msg.content,
            message_type=MessageType.TEXT
        )
        
        # Node B handles sync request and responds with data
        result = await sync_service_b.handle_message(sync_request_message)
        assert result is True
        
        # Node B should have sent sync response
        sent_calls_b = sync_service_b.interface_manager.send_message.call_args_list
        assert len(sent_calls_b) == 1
        
        sync_response_msg = sent_calls_b[0][0][0]
        sync_response_data = json.loads(sync_response_msg.content)
        assert sync_response_data['sync_type'] == 'sync_response'
        assert 'bulletins' in sync_response_data['data']
        assert len(sync_response_data['data']['bulletins']) == 1
        
        # Mock database for Node A to handle incoming sync data
        mock_db.search_bulletins.return_value = []  # No existing bulletins
        mock_db.create_bulletin.return_value = MagicMock()
        
        # Simulate Node A receiving the sync response
        sync_response_message = Message(
            sender_id="!BBBBBBBB",
            content=sync_response_msg.content,
            message_type=MessageType.TEXT
        )
        
        # Node A handles sync response and creates bulletin
        result = await sync_service_a.handle_message(sync_response_message)
        assert result is True
        
        # Node A should have created the bulletin
        mock_db.create_bulletin.assert_called_once()
        create_args = mock_db.create_bulletin.call_args[0]
        assert create_args[0] == "general"  # board
        assert create_args[1] == "!CCCCCCCC"  # sender_id
        assert create_args[2] == "TestUser"  # sender_name
        assert create_args[3] == "Test Bulletin"  # subject
        assert create_args[4] == "This is a test bulletin"  # content
        
        # Node A should have sent acknowledgment
        sent_calls_a_ack = sync_service_a.interface_manager.send_message.call_args_list
        assert len(sent_calls_a_ack) == 2  # Original request + ack
        
        ack_msg = sent_calls_a_ack[1][0][0]
        ack_data = json.loads(ack_msg.content)
        assert ack_data['sync_type'] == 'sync_ack'
        assert ack_data['recipient'] == '!BBBBBBBB'
        
        # Peer should have updated sync timestamp
        assert peer_b.last_sync is not None
    
    @pytest.mark.asyncio
    async def test_channel_sync_flow(self, sync_service_a, sync_service_b, mock_db):
        """Test channel synchronization flow"""
        # Add peers
        peer_b = SyncPeer(node_id="!BBBBBBBB", name="NodeB")
        sync_service_a.add_peer(peer_b)
        
        peer_a = SyncPeer(node_id="!AAAAAAAA", name="NodeA")
        sync_service_b.add_peer(peer_a)
        
        # Create test channel for Node B
        test_channel = BBSChannel(
            id=1,
            name="Test Repeater",
            frequency="146.520",
            description="Test repeater channel",
            channel_type=ChannelType.REPEATER,
            location="Test City",
            coverage_area="Local",
            tone="100.0",
            offset="+0.6",
            added_by="!BBBBBBBB",
            added_at=datetime.utcnow()
        )
        
        # Mock database responses
        mock_db.get_all_bulletins.return_value = []
        mock_db.get_all_channels.return_value = [test_channel]
        mock_db.search_channels.return_value = []  # No existing channels
        mock_db.add_channel.return_value = MagicMock()
        
        # Node A initiates sync
        await sync_service_a.sync_with_peer("!BBBBBBBB")
        
        # Get sync request
        sync_request_msg = sync_service_a.interface_manager.send_message.call_args_list[0][0][0]
        
        # Node B handles request
        sync_request_message = Message(
            sender_id="!AAAAAAAA",
            content=sync_request_msg.content,
            message_type=MessageType.TEXT
        )
        
        await sync_service_b.handle_message(sync_request_message)
        
        # Get sync response
        sync_response_msg = sync_service_b.interface_manager.send_message.call_args_list[0][0][0]
        sync_response_data = json.loads(sync_response_msg.content)
        
        # Verify channel data in response
        assert 'channels' in sync_response_data['data']
        assert len(sync_response_data['data']['channels']) == 1
        channel_data = sync_response_data['data']['channels'][0]
        assert channel_data['name'] == "Test Repeater"
        assert channel_data['frequency'] == "146.520"
        
        # Node A handles response
        sync_response_message = Message(
            sender_id="!BBBBBBBB",
            content=sync_response_msg.content,
            message_type=MessageType.TEXT
        )
        
        await sync_service_a.handle_message(sync_response_message)
        
        # Node A should have added the channel
        mock_db.add_channel.assert_called_once()
        add_args = mock_db.add_channel.call_args[0]
        assert add_args[0] == "Test Repeater"  # name
        assert add_args[1] == "146.520"  # frequency
        assert add_args[2] == "Test repeater channel"  # description
    
    @pytest.mark.asyncio
    async def test_conflict_resolution(self, sync_service_a, sync_service_b, mock_db):
        """Test conflict resolution during sync"""
        # Add peers
        peer_b = SyncPeer(node_id="!BBBBBBBB", name="NodeB")
        sync_service_a.add_peer(peer_b)
        
        peer_a = SyncPeer(node_id="!AAAAAAAA", name="NodeA")
        sync_service_b.add_peer(peer_a)
        
        # Create conflicting channels (same name, different info)
        existing_channel = BBSChannel(
            id=1,
            name="Test Channel",
            frequency="146.520",
            description="Original description",
            added_at=datetime.utcnow() - timedelta(hours=1)  # Older
        )
        
        incoming_channel = BBSChannel(
            id=2,
            name="Test Channel",
            frequency="146.520",
            description="Updated description",
            added_at=datetime.utcnow()  # Newer
        )
        
        # Mock database responses
        mock_db.get_all_bulletins.return_value = []
        mock_db.get_all_channels.return_value = [incoming_channel]
        mock_db.search_channels.return_value = [existing_channel]  # Existing conflict
        mock_db.update_channel.return_value = True
        
        # Perform sync
        await sync_service_a.sync_with_peer("!BBBBBBBB")
        
        # Get and handle sync request
        sync_request_msg = sync_service_a.interface_manager.send_message.call_args_list[0][0][0]
        sync_request_message = Message(
            sender_id="!AAAAAAAA",
            content=sync_request_msg.content,
            message_type=MessageType.TEXT
        )
        await sync_service_b.handle_message(sync_request_message)
        
        # Get and handle sync response
        sync_response_msg = sync_service_b.interface_manager.send_message.call_args_list[0][0][0]
        sync_response_message = Message(
            sender_id="!BBBBBBBB",
            content=sync_response_msg.content,
            message_type=MessageType.TEXT
        )
        await sync_service_a.handle_message(sync_response_message)
        
        # Should have updated existing channel (newer timestamp wins)
        mock_db.update_channel.assert_called_once()
        update_args = mock_db.update_channel.call_args
        assert update_args[0][0] == 1  # existing channel ID
        assert 'description' in update_args[1]
        assert update_args[1]['description'] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_sync_status_tracking(self, sync_service_a):
        """Test sync status and history tracking"""
        # Add a peer
        peer = SyncPeer(node_id="!BBBBBBBB", name="TestPeer")
        sync_service_a.add_peer(peer)
        
        # Add some sync history
        sync_service_a.sync_history.append(("!BBBBBBBB", datetime.utcnow(), True))
        sync_service_a.sync_history.append(("!BBBBBBBB", datetime.utcnow(), False))
        
        # Get status
        status = sync_service_a.get_sync_status()
        
        assert status['enabled'] is True
        assert status['peers'] == 1
        assert status['pending_syncs'] == 0
        assert len(status['sync_history']) == 2
        assert status['sync_history'][0]['peer_id'] == "!BBBBBBBB"
        assert status['sync_history'][0]['success'] is True
        assert status['sync_history'][1]['success'] is False
    
    @pytest.mark.asyncio
    async def test_duplicate_prevention(self, sync_service_a, sync_service_b, mock_db):
        """Test that duplicate messages are prevented during sync"""
        # Add peers
        peer_b = SyncPeer(node_id="!BBBBBBBB", name="NodeB")
        sync_service_a.add_peer(peer_b)
        
        peer_a = SyncPeer(node_id="!AAAAAAAA", name="NodeA")
        sync_service_b.add_peer(peer_a)
        
        # Create bulletin with specific unique_id
        test_bulletin = BBSBulletin(
            id=1,
            board="general",
            sender_id="!CCCCCCCC",
            sender_name="TestUser",
            subject="Test Bulletin",
            content="This is a test bulletin",
            unique_id="test-unique-id-123"
        )
        
        # Mock Node B has the bulletin
        mock_db.get_all_bulletins.return_value = [test_bulletin]
        mock_db.get_all_channels.return_value = []
        
        # Mock Node A already has the same bulletin (duplicate)
        existing_bulletin = BBSBulletin(
            id=2,
            board="general",
            sender_id="!CCCCCCCC",
            sender_name="TestUser",
            subject="Test Bulletin",
            content="This is a test bulletin",
            unique_id="test-unique-id-123"  # Same unique_id
        )
        
        mock_db.search_bulletins.return_value = [existing_bulletin]
        
        # Perform sync
        await sync_service_a.sync_with_peer("!BBBBBBBB")
        
        # Handle sync request and response
        sync_request_msg = sync_service_a.interface_manager.send_message.call_args_list[0][0][0]
        sync_request_message = Message(
            sender_id="!AAAAAAAA",
            content=sync_request_msg.content,
            message_type=MessageType.TEXT
        )
        await sync_service_b.handle_message(sync_request_message)
        
        sync_response_msg = sync_service_b.interface_manager.send_message.call_args_list[0][0][0]
        sync_response_message = Message(
            sender_id="!BBBBBBBB",
            content=sync_response_msg.content,
            message_type=MessageType.TEXT
        )
        await sync_service_a.handle_message(sync_response_message)
        
        # Should NOT have created duplicate bulletin
        mock_db.create_bulletin.assert_not_called()