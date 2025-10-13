"""
Integration tests for BBS functionality

Tests bulletin posting, reading, and deletion; mail system with multiple users;
channel directory operations; and BBS synchronization between nodes.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

import asyncio
import json
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.database import initialize_database
from src.services.bbs.bulletin_service import BulletinService
from src.services.bbs.mail_service import MailService
from src.services.bbs.channel_service import ChannelService
from src.services.bbs.sync_service import BBSSyncService, SyncPeer
from src.services.bbs.menu_system import BBSMenuSystem
from src.services.bbs.database import BBSDatabase
from src.models.message import Message, MessageType


class TestBBSIntegration:
    """Integration tests for complete BBS functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_fresh_db(self):
        """Set up fresh database for each test"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        
        try:
            # Initialize database
            db_manager = initialize_database(db_path)
            
            # Create test users
            test_users = [
                {
                    'node_id': '!12345678',
                    'short_name': 'Alice',
                    'long_name': 'Alice Smith',
                    'tags': ['admin'],
                    'permissions': {'bbs_admin': True},
                    'subscriptions': {'bbs': True}
                },
                {
                    'node_id': '!87654321',
                    'short_name': 'Bob',
                    'long_name': 'Bob Jones',
                    'tags': ['user'],
                    'permissions': {},
                    'subscriptions': {'bbs': True}
                },
                {
                    'node_id': '!11111111',
                    'short_name': 'Charlie',
                    'long_name': 'Charlie Brown',
                    'tags': ['user'],
                    'permissions': {},
                    'subscriptions': {'bbs': True}
                },
                {
                    'node_id': '!22222222',
                    'short_name': 'Diana',
                    'long_name': 'Diana Prince',
                    'tags': ['moderator'],
                    'permissions': {'bbs_moderate': True},
                    'subscriptions': {'bbs': True}
                }
            ]
            
            for user in test_users:
                db_manager.upsert_user(user)
            
            # Reset global services
            import src.services.bbs.bulletin_service
            import src.services.bbs.mail_service
            import src.services.bbs.channel_service
            import src.services.bbs.database
            src.services.bbs.bulletin_service.bulletin_service = None
            src.services.bbs.mail_service.mail_service = None
            src.services.bbs.channel_service.channel_service = None
            src.services.bbs.database.bbs_db = None
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def bbs_services(self, setup_fresh_db):
        """Create all BBS services with fresh database"""
        bulletin_service = BulletinService()
        mail_service = MailService()
        channel_service = ChannelService()
        menu_system = BBSMenuSystem()
        
        return {
            'bulletin': bulletin_service,
            'mail': mail_service,
            'channel': channel_service,
            'menu': menu_system
        }
    
    @pytest.fixture
    def mock_interface_manager(self):
        """Mock interface manager for sync testing"""
        return AsyncMock()


class TestBulletinBoardIntegration(TestBBSIntegration):
    """Test bulletin board posting, reading, and deletion"""
    
    def test_bulletin_workflow_complete(self, bbs_services):
        """Test complete bulletin workflow: post, list, read, delete"""
        bulletin_service = bbs_services['bulletin']
        
        # 1. Post bulletins to different boards
        success, msg1 = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="Alice",
            subject="Welcome to the Network",
            content="This is our first bulletin on the general board. Welcome everyone!"
        )
        assert success is True
        assert "posted to 'general' board successfully" in msg1
        
        success, msg2 = bulletin_service.post_bulletin(
            board="emergency",
            sender_id="!87654321",
            sender_name="Bob",
            subject="Emergency Procedures",
            content="In case of emergency, follow these procedures: 1. Stay calm 2. Contact emergency services"
        )
        assert success is True
        assert "posted to 'emergency' board successfully" in msg2
        
        success, msg3 = bulletin_service.post_bulletin(
            board="general",
            sender_id="!11111111",
            sender_name="Charlie",
            subject="Network Status Update",
            content="All nodes are operating normally. Signal strength is good across the mesh."
        )
        assert success is True
        
        # 2. List bulletins on general board
        success, listing = bulletin_service.list_bulletins("general", user_id="!22222222")
        assert success is True
        assert "Bulletins on 'general' board" in listing
        assert "Welcome to the Network" in listing
        assert "Network Status Update" in listing
        assert "Emergency Procedures" not in listing  # Different board
        assert "Total: 2 bulletins" in listing
        
        # 3. List all bulletins
        success, all_listing = bulletin_service.list_all_bulletins(user_id="!22222222")
        assert success is True
        assert "Recent bulletins from all boards" in all_listing
        assert "Welcome to the Network" in all_listing
        assert "Emergency Procedures" in all_listing
        assert "Network Status Update" in all_listing
        
        # 4. Read specific bulletin
        # Extract bulletin ID from first post message
        import re
        match = re.search(r'#(\d+)', msg1)
        assert match is not None
        bulletin_id = int(match.group(1))
        
        success, bulletin_content = bulletin_service.get_bulletin(bulletin_id, "!22222222")
        assert success is True
        assert f"Bulletin #{bulletin_id}" in bulletin_content
        assert "Welcome to the Network" in bulletin_content
        assert "This is our first bulletin" in bulletin_content
        assert "Alice" in bulletin_content
        
        # 5. Search bulletins
        success, search_results = bulletin_service.search_bulletins("network", user_id="!22222222")
        assert success is True
        assert "Search results for 'network'" in search_results
        assert "Welcome to the Network" in search_results
        assert "Network Status Update" in search_results
        assert "Emergency Procedures" not in search_results
        
        # 6. Delete bulletin (by original poster)
        success, delete_msg = bulletin_service.delete_bulletin(bulletin_id, "!12345678")
        assert success is True
        assert "deleted successfully" in delete_msg
        
        # 7. Verify deletion
        success, not_found = bulletin_service.get_bulletin(bulletin_id, "!22222222")
        assert success is False
        assert "not found" in not_found
        
        # 8. List bulletins again to confirm deletion
        success, updated_listing = bulletin_service.list_bulletins("general", user_id="!22222222")
        assert success is True
        assert "Network Status Update" in updated_listing
        assert "Welcome to the Network" not in updated_listing
        assert "Total: 1 bulletins" in updated_listing
    
    def test_bulletin_board_statistics(self, bbs_services):
        """Test bulletin board statistics and activity tracking"""
        bulletin_service = bbs_services['bulletin']
        
        # Post bulletins from different users
        bulletin_service.post_bulletin("general", "!12345678", "Alice", "Post 1", "Content 1")
        bulletin_service.post_bulletin("general", "!87654321", "Bob", "Post 2", "Content 2")
        bulletin_service.post_bulletin("tech", "!12345678", "Alice", "Post 3", "Content 3")
        bulletin_service.post_bulletin("emergency", "!11111111", "Charlie", "Post 4", "Content 4")
        
        # Get global statistics
        stats = bulletin_service.get_bulletin_stats()
        assert stats['total_bulletins'] == 4
        assert stats['total_boards'] == 3
        assert stats['unique_posters'] == 3
        assert stats['oldest_bulletin'] is not None
        assert stats['newest_bulletin'] is not None
        
        # Get board-specific statistics
        general_stats = bulletin_service.get_bulletin_stats(board="general")
        assert general_stats['board'] == "general"
        assert general_stats['total_bulletins'] == 2
        assert general_stats['unique_posters'] == 2
        
        # Get recent activity
        success, activity = bulletin_service.get_recent_activity(hours=24)
        assert success is True
        assert "Bulletin activity in the last 24 hours" in activity
        assert "Total: 4 new bulletins" in activity
        
        # Get board list
        success, boards = bulletin_service.get_bulletin_boards()
        assert success is True
        assert "Available bulletin boards" in boards
        assert "general" in boards
        assert "tech" in boards
        assert "emergency" in boards

class TestMailSystemIntegration(TestBBSIntegration):
    """Test mail system with multiple users"""
    
    def test_mail_workflow_multiple_users(self, bbs_services):
        """Test complete mail workflow with multiple users"""
        mail_service = bbs_services['mail']
        
        # 1. Send mail between users
        success, msg1 = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="Alice",
            recipient_id="!87654321",
            subject="Welcome to the mesh",
            content="Hi Bob! Welcome to our mesh network. Let me know if you need any help getting started."
        )
        assert success is True
        assert "sent to !87654321 successfully" in msg1
        
        success, msg2 = mail_service.send_mail(
            sender_id="!11111111",
            sender_name="Charlie",
            recipient_id="!87654321",
            subject="Network meeting",
            content="Don't forget about the network planning meeting this Saturday at 2 PM."
        )
        assert success is True
        
        success, msg3 = mail_service.send_mail(
            sender_id="!87654321",
            sender_name="Bob",
            recipient_id="!12345678",
            subject="Re: Welcome to the mesh",
            content="Thanks Alice! The network is working great. I appreciate the warm welcome."
        )
        assert success is True
        
        # 2. Check unread count for Bob
        unread_count = mail_service.get_unread_count("!87654321")
        assert unread_count == 2  # Two messages for Bob
        
        # 3. List mail for Bob
        success, bob_mail = mail_service.list_mail("!87654321")
        assert success is True
        assert "Your Mail Messages" in bob_mail
        assert "Welcome to the mesh" in bob_mail
        assert "Network meeting" in bob_mail
        assert "Total: 2 messages" in bob_mail
        
        # 4. List unread mail for Bob
        success, unread_mail = mail_service.list_unread_mail("!87654321")
        assert success is True
        assert "Your Unread Mail Messages" in unread_mail
        assert "Welcome to the mesh" in unread_mail
        assert "Network meeting" in unread_mail
        
        # 5. Read first mail (ID 1)
        success, mail_content = mail_service.get_mail(1, "!87654321")
        assert success is True
        assert "Mail #1" in mail_content
        assert "Welcome to the mesh" in mail_content
        assert "Hi Bob! Welcome to our mesh network" in mail_content
        assert "Alice" in mail_content
        
        # 6. Mark mail as read
        success, read_msg = mail_service.mark_mail_read(1, "!87654321")
        assert success is True
        assert "marked as read" in read_msg
        
        # 7. Check unread count again
        unread_count = mail_service.get_unread_count("!87654321")
        assert unread_count == 1  # One less unread
        
        # 8. List mail for Alice
        success, alice_mail = mail_service.list_mail("!12345678")
        assert success is True
        assert "Re: Welcome to the mesh" in alice_mail
        assert "Total: 1 messages" in alice_mail
        
        # 9. Get conversation between Alice and Bob
        success, conversation = mail_service.get_conversation("!12345678", "!87654321")
        assert success is True
        assert "Conversation with !87654321" in conversation
        assert "Re: Welcome to the mesh" in conversation
        
        # 10. Search mail
        success, search_results = mail_service.search_mail("!87654321", "meeting")
        assert success is True
        assert "Mail search results for 'meeting'" in search_results
        assert "Network meeting" in search_results
        assert "Welcome to the mesh" not in search_results
        
        # 11. Delete mail
        success, delete_msg = mail_service.delete_mail(2, "!87654321")
        assert success is True
        assert "deleted successfully" in delete_msg
        
        # 12. Verify deletion
        success, updated_mail = mail_service.list_mail("!87654321")
        assert success is True
        assert "Network meeting" not in updated_mail
        assert "Total: 1 messages" in updated_mail
    
    def test_mail_statistics_and_activity(self, bbs_services):
        """Test mail statistics and activity tracking"""
        mail_service = bbs_services['mail']
        
        # Send various mails
        mail_service.send_mail("!12345678", "Alice", "!87654321", "Subject 1", "Content 1")
        mail_service.send_mail("!11111111", "Charlie", "!87654321", "Subject 2", "Content 2")
        mail_service.send_mail("!12345678", "Alice", "!87654321", "Subject 3", "Content 3")
        mail_service.send_mail("!87654321", "Bob", "!22222222", "Subject 4", "Content 4")
        
        # Mark some as read
        mail_service.mark_mail_read(1, "!87654321")
        
        # Get mail statistics for Bob
        stats = mail_service.get_mail_stats("!87654321")
        assert stats['total_mail'] == 3
        assert stats['unread_mail'] == 2
        assert stats['read_mail'] == 1
        assert stats['unique_senders'] == 2
        assert stats['most_active_sender']['sender_id'] == "!12345678"
        assert stats['most_active_sender']['message_count'] == 2
        
        # Get recent activity
        success, activity = mail_service.get_recent_activity("!87654321", hours=24)
        assert success is True
        assert "Mail activity in the last 24 hours" in activity
        assert "Total: 3 new messages" in activity


class TestChannelDirectoryIntegration(TestBBSIntegration):
    """Test channel directory operations"""
    
    def test_channel_directory_workflow(self, bbs_services):
        """Test complete channel directory workflow"""
        channel_service = bbs_services['channel']
        
        # 1. Add channels of different types
        success, msg1 = channel_service.add_channel(
            name="Main Repeater",
            frequency="146.520",
            description="Primary repeater for the area with excellent coverage",
            channel_type="repeater",
            location="Downtown Tower",
            coverage_area="50 miles",
            tone="123.0",
            offset="+0.6",
            added_by="!12345678"
        )
        assert success is True
        assert "added to directory successfully" in msg1
        
        success, msg2 = channel_service.add_channel(
            name="Emergency Simplex",
            frequency="146.550",
            description="Emergency simplex frequency for direct communications",
            channel_type="simplex",
            location="Regional",
            coverage_area="Line of sight",
            added_by="!87654321"
        )
        assert success is True
        
        success, msg3 = channel_service.add_channel(
            name="Digital Link",
            frequency="440.125",
            description="Digital mode repeater for data communications",
            channel_type="digital",
            location="North Tower",
            coverage_area="30 miles",
            tone="DCS 023",
            offset="-5.0",
            added_by="!11111111"
        )
        assert success is True
        
        # 2. List all channels
        success, listing = channel_service.list_channels()
        assert success is True
        assert "Channel Directory" in listing
        assert "Main Repeater" in listing
        assert "Emergency Simplex" in listing
        assert "Digital Link" in listing
        assert "Total: 3 channels" in listing
        
        # 3. Get specific channel details
        success, channel_details = channel_service.get_channel(1)
        assert success is True
        assert "Channel #1" in channel_details
        assert "Main Repeater" in channel_details
        assert "146.520" in channel_details
        assert "Downtown Tower" in channel_details
        assert "123.0" in channel_details
        
        # 4. Search channels
        success, search_results = channel_service.search_channels("repeater")
        assert success is True
        assert "Channel search results for 'repeater'" in search_results
        assert "Main Repeater" in search_results
        assert "Digital Link" in search_results  # Description contains "repeater"
        assert "Emergency Simplex" not in search_results
        
        # 5. Get channels by type
        success, repeater_channels = channel_service.get_channels_by_type("repeater")
        assert success is True
        assert "Repeater Channels" in repeater_channels
        assert "Main Repeater" in repeater_channels
        assert "Emergency Simplex" not in repeater_channels
        
        # 6. Get channels by location
        success, downtown_channels = channel_service.get_channels_by_location("Downtown")
        assert success is True
        assert "Channels in 'Downtown'" in downtown_channels
        assert "Main Repeater" in downtown_channels
        assert "Digital Link" not in downtown_channels
        
        # 7. Update channel (by owner)
        success, update_msg = channel_service.update_channel(
            channel_id=1,
            user_id="!12345678",
            description="Updated: Primary repeater with enhanced coverage and backup power",
            coverage_area="60 miles"
        )
        assert success is True
        assert "updated successfully" in update_msg
        
        # 8. Verify update
        success, updated_details = channel_service.get_channel(1)
        assert success is True
        assert "Updated: Primary repeater" in updated_details
        assert "60 miles" in updated_details
        
        # 9. Verify channel (by different user)
        success, verify_msg = channel_service.verify_channel(1, "!87654321")
        assert success is True
        assert "marked as verified" in verify_msg
        
        # 10. Delete channel (by owner)
        success, delete_msg = channel_service.delete_channel(3, "!11111111")
        assert success is True
        assert "removed from directory" in delete_msg
        
        # 11. Verify deletion
        success, updated_listing = channel_service.list_channels()
        assert success is True
        assert "Digital Link" not in updated_listing
        assert "Total: 2 channels" in updated_listing
    
    def test_channel_statistics(self, bbs_services):
        """Test channel directory statistics"""
        channel_service = bbs_services['channel']
        
        # Add channels
        channel_service.add_channel("Repeater 1", "146.520", "Description", "repeater", added_by="!12345678")
        channel_service.add_channel("Simplex 1", "146.550", "Description", "simplex", added_by="!87654321")
        channel_service.add_channel("Repeater 2", "146.940", "Description", "repeater", added_by="!12345678")
        channel_service.add_channel("Digital 1", "70cm", "Description", "digital", added_by="!11111111")
        
        # Verify some channels
        channel_service.verify_channel(1, "!87654321")
        channel_service.verify_channel(2, "!11111111")
        
        # Get statistics
        stats = channel_service.get_channel_stats()
        assert stats['total_channels'] == 4
        assert stats['active_channels'] == 4
        assert stats['verified_channels'] == 2
        assert stats['channels_by_type']['repeater'] == 2
        assert stats['channels_by_type']['simplex'] == 1
        assert stats['channels_by_type']['digital'] == 1
        assert stats['unique_contributors'] == 3
        assert stats['most_active_contributor']['user_id'] == "!12345678"
        assert stats['most_active_contributor']['channel_count'] == 2


class TestBBSSynchronizationIntegration(TestBBSIntegration):
    """Test BBS synchronization between nodes"""
    
    @pytest.fixture
    def sync_services(self, mock_interface_manager):
        """Create sync services for two nodes"""
        node1_sync = BBSSyncService(mock_interface_manager, "!12345678")
        node2_sync = BBSSyncService(mock_interface_manager, "!87654321")
        
        return {
            'node1': node1_sync,
            'node2': node2_sync
        }
    
    @pytest.mark.asyncio
    async def test_peer_discovery_and_announcement(self, sync_services):
        """Test peer discovery and announcement process"""
        node1_sync = sync_services['node1']
        node2_sync = sync_services['node2']
        
        # Node 1 discovers peers
        await node1_sync.discover_peers()
        
        # Verify discovery message was sent
        node1_sync.interface_manager.send_message.assert_called_once()
        discovery_msg = node1_sync.interface_manager.send_message.call_args[0][0]
        discovery_data = json.loads(discovery_msg.content)
        
        assert discovery_data['sync_type'] == 'peer_discovery'
        assert discovery_data['sender'] == '!12345678'
        assert discovery_data['recipient'] is None  # Broadcast
        
        # Node 2 receives discovery and responds
        discovery_message = Message(
            sender_id="!12345678",
            content=discovery_msg.content,
            message_type=MessageType.TEXT
        )
        
        result = await node2_sync.handle_message(discovery_message)
        assert result is True
        
        # Node 2 should have sent announcement
        node2_sync.interface_manager.send_message.assert_called_once()
        announce_msg = node2_sync.interface_manager.send_message.call_args[0][0]
        announce_data = json.loads(announce_msg.content)
        
        assert announce_data['sync_type'] == 'peer_announce'
        assert announce_data['sender'] == '!87654321'
        assert announce_data['recipient'] == '!12345678'
        
        # Node 1 receives announcement
        announce_message = Message(
            sender_id="!87654321",
            content=announce_msg.content,
            message_type=MessageType.TEXT
        )
        
        result = await node1_sync.handle_message(announce_message)
        assert result is True
        
        # Node 1 should have auto-added the peer
        assert len(node1_sync.peers) == 1
        peer = node1_sync.get_peer("!87654321")
        assert peer is not None
        assert peer.name == "ZephyrGate-87654321"  # Default name
    
    @pytest.mark.asyncio
    async def test_bulletin_synchronization(self, sync_services, bbs_services):
        """Test bulletin synchronization between nodes"""
        node1_sync = sync_services['node1']
        node2_sync = sync_services['node2']
        bulletin_service = bbs_services['bulletin']
        
        # Add peers to each other
        peer1 = SyncPeer(node_id="!87654321", name="Node2BBS")
        peer2 = SyncPeer(node_id="!12345678", name="Node1BBS")
        node1_sync.add_peer(peer1)
        node2_sync.add_peer(peer2)
        
        # Node 1 has some bulletins
        bulletin_service.post_bulletin("general", "!12345678", "Alice", "Test Bulletin 1", "Content 1")
        bulletin_service.post_bulletin("emergency", "!11111111", "Charlie", "Emergency Alert", "Important info")
        
        # Mock database for node 2 sync service
        with patch('src.services.bbs.sync_service.get_bbs_database') as mock_db:
            mock_db.return_value.get_all_bulletins.return_value = []
            mock_db.return_value.search_bulletins.return_value = []
            mock_db.return_value.create_bulletin.return_value = MagicMock()
            mock_db.return_value.get_all_channels.return_value = []
            mock_db.return_value.search_channels.return_value = []
            mock_db.return_value.add_channel.return_value = MagicMock()
            
            # Node 1 initiates sync with Node 2
            result = await node1_sync.sync_with_peer("!87654321")
            assert result is True
            
            # Verify sync request was sent
            node1_sync.interface_manager.send_message.assert_called()
            sync_msg = node1_sync.interface_manager.send_message.call_args[0][0]
            sync_data = json.loads(sync_msg.content)
            
            assert sync_data['sync_type'] == 'sync_request'
            assert sync_data['sender'] == '!12345678'
            assert sync_data['recipient'] == '!87654321'
            assert sync_data['data']['sync_bulletins'] is True
            assert sync_data['data']['sync_channels'] is True
    
    @pytest.mark.asyncio
    async def test_sync_conflict_resolution(self, sync_services):
        """Test conflict resolution during synchronization"""
        node1_sync = sync_services['node1']
        node2_sync = sync_services['node2']
        
        # Add peers
        peer1 = SyncPeer(node_id="!87654321", name="Node2BBS")
        node1_sync.add_peer(peer1)
        
        # Mock conflicting data scenario
        with patch('src.services.bbs.sync_service.get_bbs_database') as mock_db:
            # Mock existing bulletin with same unique_id but different content
            existing_bulletin = MagicMock()
            existing_bulletin.unique_id = "test-unique-id"
            existing_bulletin.timestamp = datetime.utcnow() - timedelta(hours=1)  # Older
            
            mock_db.return_value.search_bulletins.return_value = [existing_bulletin]
            mock_db.return_value.create_bulletin.return_value = MagicMock()
            mock_db.return_value.update_bulletin.return_value = MagicMock()
            mock_db.return_value.get_all_channels.return_value = []
            mock_db.return_value.search_channels.return_value = []
            
            # Create sync response with newer bulletin
            sync_response_data = {
                'type': 'bbs_sync',
                'sync_type': 'sync_response',
                'sender': '!87654321',
                'recipient': '!12345678',
                'data': {
                    'bulletins': [{
                        'id': 1,
                        'board': 'general',
                        'sender_id': '!87654321',
                        'sender_name': 'Bob',
                        'subject': 'Updated Subject',
                        'content': 'Updated content',
                        'timestamp': datetime.utcnow().isoformat(),  # Newer
                        'unique_id': 'test-unique-id'
                    }],
                    'channels': []
                },
                'timestamp': datetime.utcnow().isoformat(),
                'sync_id': 'test123'
            }
            
            message = Message(
                sender_id="!87654321",
                content=json.dumps(sync_response_data),
                message_type=MessageType.TEXT
            )
            
            # Handle sync response
            result = await node1_sync.handle_message(message)
            assert result is True
            
            # Should have updated the bulletin (newer timestamp wins)
            mock_db.return_value.update_bulletin.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_status_and_history(self, sync_services):
        """Test sync status reporting and history tracking"""
        node1_sync = sync_services['node1']
        
        # Add a peer
        peer = SyncPeer(node_id="!87654321", name="TestPeer")
        node1_sync.add_peer(peer)
        
        # Add some sync history
        node1_sync.sync_history.append(("!87654321", datetime.utcnow(), True))
        node1_sync.sync_history.append(("!87654321", datetime.utcnow() - timedelta(hours=1), False))
        
        # Get sync status
        status = node1_sync.get_sync_status()
        
        assert status['enabled'] is True
        assert status['peers'] == 1
        assert status['pending_syncs'] == 0
        assert 'last_sync_check' in status
        assert len(status['sync_history']) == 2
        assert status['sync_history'][0]['peer_id'] == "!87654321"
        assert status['sync_history'][0]['success'] is True
        assert status['sync_history'][1]['success'] is False
    
    @pytest.mark.asyncio
    async def test_sync_all_peers(self, sync_services):
        """Test syncing with multiple peers"""
        node1_sync = sync_services['node1']
        
        # Add multiple peers
        peer1 = SyncPeer(node_id="!11111111", name="Peer1")
        peer2 = SyncPeer(node_id="!22222222", name="Peer2")
        peer3 = SyncPeer(node_id="!33333333", name="Peer3", sync_enabled=False)
        
        node1_sync.add_peer(peer1)
        node1_sync.add_peer(peer2)
        node1_sync.add_peer(peer3)
        
        # Sync with all peers
        success_count = await node1_sync.sync_all_peers()
        assert success_count == 2  # Only enabled peers
        
        # Should have sent sync requests to enabled peers only
        assert node1_sync.interface_manager.send_message.call_count == 2


class TestBBSMenuSystemIntegration(TestBBSIntegration):
    """Test BBS menu system integration with all services"""
    
    def test_menu_navigation_workflow(self, bbs_services):
        """Test complete menu navigation workflow"""
        menu_system = bbs_services['menu']
        
        # Start at main menu
        response = menu_system.process_command("!12345678", "")
        assert "MAIN MENU" in response
        assert "bbs" in response
        assert "utilities" in response
        
        # Navigate to BBS
        response = menu_system.process_command("!12345678", "bbs")
        assert "BBS MENU" in response
        assert "bulletins" in response
        assert "mail" in response
        assert "channels" in response
        
        # Navigate to bulletins
        response = menu_system.process_command("!12345678", "bulletins")
        assert "BULLETINS MENU" in response
        assert "list" in response
        assert "post" in response
        
        # Navigate to mail (need to go back to BBS first)
        response = menu_system.process_command("!12345678", "bbs")
        response = menu_system.process_command("!12345678", "mail")
        assert "MAIL MENU" in response
        assert "list" in response
        assert "send" in response
        
        # Navigate to channel directory (need to go back to BBS first)
        response = menu_system.process_command("!12345678", "bbs")
        response = menu_system.process_command("!12345678", "channels")
        assert "CHANNELS MENU" in response
        assert "list" in response
        assert "add" in response
    
    def test_integrated_bbs_operations(self, bbs_services):
        """Test integrated BBS operations through menu system"""
        menu_system = bbs_services['menu']
        bulletin_service = bbs_services['bulletin']
        mail_service = bbs_services['mail']
        
        # Post a bulletin through menu system
        menu_system.process_command("!12345678", "bbs")  # Go to BBS
        menu_system.process_command("!12345678", "bulletins")  # Go to bulletins
        response = menu_system.process_command("!12345678", "post")  # Post bulletin
        assert "Compose New Bulletin" in response
        
        # Send mail through menu system
        menu_system.process_command("!12345678", "main")  # Back to main
        menu_system.process_command("!12345678", "bbs")  # Go to BBS
        menu_system.process_command("!12345678", "mail")  # Go to mail
        response = menu_system.process_command("!12345678", "send")  # Send mail
        assert "Compose New Mail" in response
        
        # Verify services are working together
        bulletin_service.post_bulletin("general", "!12345678", "Alice", "Test", "Content")
        mail_service.send_mail("!12345678", "Alice", "!87654321", "Test", "Content")
        
        # Check that data is accessible through menu
        menu_system.process_command("!12345678", "bbs")  # BBS
        menu_system.process_command("!12345678", "bulletins")  # Bulletins
        response = menu_system.process_command("!12345678", "list")  # List bulletins
        assert "Test" in response
        
        menu_system.process_command("!87654321", "bbs")  # BBS
        menu_system.process_command("!87654321", "mail")  # Mail
        response = menu_system.process_command("!87654321", "list")  # List mail for Bob
        assert "Test" in response


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])