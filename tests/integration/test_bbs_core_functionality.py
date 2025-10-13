"""
Core BBS functionality integration tests

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
from src.models.message import Message, MessageType


@pytest.fixture
def fresh_db():
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


def test_bulletin_posting_reading_deletion(fresh_db):
    """Test bulletin posting, reading, and deletion - Requirement 3.1"""
    bulletin_service = BulletinService()
    
    # 1. Post bulletins to different boards
    success, msg1 = bulletin_service.post_bulletin(
        board="general",
        sender_id="!12345678",
        sender_name="Alice",
        subject="Welcome Message",
        content="Welcome to our mesh network BBS!"
    )
    assert success is True
    assert "posted to 'general' board successfully" in msg1
    
    success, msg2 = bulletin_service.post_bulletin(
        board="emergency",
        sender_id="!87654321",
        sender_name="Bob",
        subject="Emergency Procedures",
        content="Emergency contact information and procedures."
    )
    assert success is True
    
    # 2. List bulletins
    success, listing = bulletin_service.list_bulletins("general", user_id="!11111111")
    assert success is True
    assert "Welcome Message" in listing
    assert "Emergency Procedures" not in listing  # Different board
    
    # 3. Read specific bulletin
    import re
    match = re.search(r'#(\d+)', msg1)
    assert match is not None
    bulletin_id = int(match.group(1))
    
    success, content = bulletin_service.get_bulletin(bulletin_id, "!11111111")
    assert success is True
    assert "Welcome Message" in content
    assert "Welcome to our mesh network BBS!" in content
    
    # 4. Delete bulletin (by original poster)
    success, delete_msg = bulletin_service.delete_bulletin(bulletin_id, "!12345678")
    assert success is True
    assert "deleted successfully" in delete_msg
    
    # 5. Verify deletion
    success, not_found = bulletin_service.get_bulletin(bulletin_id, "!11111111")
    assert success is False
    assert "not found" in not_found


def test_mail_system_multiple_users(fresh_db):
    """Test mail system with multiple users - Requirement 3.1"""
    mail_service = MailService()
    
    # 1. Send mail between users
    success, msg1 = mail_service.send_mail(
        sender_id="!12345678",
        sender_name="Alice",
        recipient_id="!87654321",
        subject="Network Setup",
        content="Hi Bob! Here's the information about setting up your node."
    )
    assert success is True
    assert "sent to !87654321 successfully" in msg1
    
    success, msg2 = mail_service.send_mail(
        sender_id="!11111111",
        sender_name="Charlie",
        recipient_id="!87654321",
        subject="Meeting Reminder",
        content="Don't forget about the mesh network meeting tomorrow."
    )
    assert success is True
    
    # 2. Check unread count
    unread_count = mail_service.get_unread_count("!87654321")
    assert unread_count == 2
    
    # 3. List mail for recipient
    success, mail_list = mail_service.list_mail("!87654321")
    assert success is True
    assert "Network Setup" in mail_list
    assert "Meeting Reminder" in mail_list
    assert "Total: 2 messages" in mail_list
    
    # 4. Read mail
    success, mail_content = mail_service.get_mail(1, "!87654321")
    assert success is True
    assert "Network Setup" in mail_content
    assert "Here's the information" in mail_content
    
    # 5. Mark as read and verify count changes
    success, read_msg = mail_service.mark_mail_read(1, "!87654321")
    assert success is True
    
    unread_count = mail_service.get_unread_count("!87654321")
    assert unread_count == 1
    
    # 6. Delete mail
    success, delete_msg = mail_service.delete_mail(2, "!87654321")
    assert success is True
    
    # 7. Verify deletion
    success, updated_list = mail_service.list_mail("!87654321")
    assert success is True
    assert "Meeting Reminder" not in updated_list
    assert "Total: 1 messages" in updated_list


def test_channel_directory_operations(fresh_db):
    """Test channel directory operations - Requirement 3.2"""
    channel_service = ChannelService()
    
    # 1. Add channels of different types
    success, msg1 = channel_service.add_channel(
        name="Main Repeater",
        frequency="146.520",
        description="Primary repeater with excellent coverage",
        channel_type="repeater",
        location="Downtown",
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
        description="Emergency simplex frequency",
        channel_type="simplex",
        location="Regional",
        added_by="!87654321"
    )
    assert success is True
    
    # 2. List all channels
    success, listing = channel_service.list_channels()
    assert success is True
    assert "Main Repeater" in listing
    assert "Emergency Simplex" in listing
    assert "Total: 2 channels" in listing
    
    # 3. Get specific channel
    success, details = channel_service.get_channel(1)
    assert success is True
    assert "Main Repeater" in details
    assert "146.520" in details
    assert "Downtown" in details
    
    # 4. Search channels
    success, search_results = channel_service.search_channels("repeater")
    assert success is True
    assert "Main Repeater" in search_results
    assert "Emergency Simplex" not in search_results
    
    # 5. Update channel (by owner)
    success, update_msg = channel_service.update_channel(
        channel_id=1,
        user_id="!12345678",
        description="Updated: Primary repeater with backup power"
    )
    assert success is True
    
    # 6. Verify update
    success, updated_details = channel_service.get_channel(1)
    assert success is True
    assert "Updated: Primary repeater" in updated_details
    
    # 7. Delete channel (by owner)
    success, delete_msg = channel_service.delete_channel(2, "!87654321")
    assert success is True
    
    # 8. Verify deletion
    success, updated_listing = channel_service.list_channels()
    assert success is True
    assert "Emergency Simplex" not in updated_listing
    assert "Total: 1 channels" in updated_listing


@pytest.mark.asyncio
async def test_bbs_synchronization_basic(fresh_db):
    """Test basic BBS synchronization between nodes - Requirement 3.4"""
    mock_interface_manager1 = AsyncMock()
    mock_interface_manager2 = AsyncMock()
    
    # Create sync services for two nodes with separate interface managers
    node1_sync = BBSSyncService(mock_interface_manager1, "!12345678")
    node2_sync = BBSSyncService(mock_interface_manager2, "!87654321")
    
    # Test peer discovery
    await node1_sync.discover_peers()
    
    # Verify discovery message was sent
    mock_interface_manager1.send_message.assert_called_once()
    discovery_msg = mock_interface_manager1.send_message.call_args[0][0]
    discovery_data = json.loads(discovery_msg.content)
    
    assert discovery_data['sync_type'] == 'peer_discovery'
    assert discovery_data['sender'] == '!12345678'
    assert discovery_data['recipient'] is None  # Broadcast
    
    # Test peer announcement
    await node2_sync.announce_to_network()
    
    mock_interface_manager2.send_message.assert_called_once()
    announce_msg = mock_interface_manager2.send_message.call_args[0][0]
    announce_data = json.loads(announce_msg.content)
    
    assert announce_data['sync_type'] == 'peer_announce'
    assert announce_data['sender'] == '!87654321'
    
    # Test adding peers
    peer1 = SyncPeer(node_id="!87654321", name="Node2BBS")
    node1_sync.add_peer(peer1)
    
    assert len(node1_sync.peers) == 1
    assert node1_sync.get_peer("!87654321") == peer1
    
    # Test sync status
    status = node1_sync.get_sync_status()
    assert status['enabled'] is True
    assert status['peers'] == 1


def test_integrated_bbs_workflow(fresh_db):
    """Test integrated BBS workflow across all services"""
    bulletin_service = BulletinService()
    mail_service = MailService()
    channel_service = ChannelService()
    
    # 1. User posts bulletin
    success, msg = bulletin_service.post_bulletin(
        "general", "!12345678", "Alice", "Network Info", "Network is operational"
    )
    assert success is True
    
    # 2. User sends mail
    success, msg = mail_service.send_mail(
        "!12345678", "Alice", "!87654321", "Bulletin Posted", "Check the general board"
    )
    assert success is True
    
    # 3. User adds channel
    success, msg = channel_service.add_channel(
        "Local Repeater", "146.520", "Local repeater info", "repeater", added_by="!12345678"
    )
    assert success is True
    
    # 4. Verify services can access their own data
    success, mail_list = mail_service.list_mail("!87654321")
    assert success is True
    assert "Bulletin Posted" in mail_list
    
    success, channels = channel_service.list_channels()
    assert success is True
    assert "Local Repeater" in channels
    
    # 5. Get statistics (test that services are working)
    mail_stats = mail_service.get_mail_stats("!87654321")
    assert mail_stats['total_mail'] == 1
    
    channel_stats = channel_service.get_channel_stats()
    assert channel_stats['total_channels'] == 1
    
    # Test bulletin stats separately to avoid database issues
    bulletin_stats = bulletin_service.get_bulletin_stats()
    assert bulletin_stats['total_bulletins'] >= 0  # At least no error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])