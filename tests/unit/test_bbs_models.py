"""
Unit tests for BBS data models and database operations
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import initialize_database
from src.services.bbs.models import (
    BBSBulletin, BBSMail, BBSChannel, JS8CallMessage, BBSSession,
    MailStatus, ChannelType, JS8CallPriority,
    generate_unique_id, validate_bulletin_subject, validate_bulletin_content,
    validate_mail_subject, validate_mail_content, validate_channel_name
)
from src.services.bbs.database import BBSDatabase


class TestBBSModels:
    """Test BBS data models"""
    
    def test_bbs_bulletin_creation(self):
        """Test BBSBulletin creation and methods"""
        bulletin = BBSBulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser",
            subject="Test Subject",
            content="Test content for bulletin"
        )
        
        assert bulletin.board == "general"
        assert bulletin.sender_id == "!12345678"
        assert bulletin.sender_name == "TestUser"
        assert bulletin.subject == "Test Subject"
        assert bulletin.content == "Test content for bulletin"
        assert isinstance(bulletin.read_by, set)
        assert len(bulletin.unique_id) > 0
    
    def test_bbs_bulletin_read_tracking(self):
        """Test bulletin read tracking"""
        bulletin = BBSBulletin(
            sender_id="!12345678",
            sender_name="TestUser",
            subject="Test",
            content="Test content"
        )
        
        user_id = "!87654321"
        assert not bulletin.is_read_by(user_id)
        
        bulletin.mark_read_by(user_id)
        assert bulletin.is_read_by(user_id)
        assert user_id in bulletin.read_by
    
    def test_bbs_bulletin_preview(self):
        """Test bulletin content preview"""
        long_content = "A" * 200
        bulletin = BBSBulletin(
            sender_id="!12345678",
            sender_name="TestUser",
            subject="Test",
            content=long_content
        )
        
        preview = bulletin.get_preview(50)
        assert len(preview) <= 53  # 50 + "..."
        assert preview.endswith("...")
        
        short_content = "Short content"
        bulletin.content = short_content
        preview = bulletin.get_preview(50)
        assert preview == short_content
    
    def test_bbs_mail_creation(self):
        """Test BBSMail creation and methods"""
        mail = BBSMail(
            sender_id="!12345678",
            sender_name="Sender",
            recipient_id="!87654321",
            subject="Test Mail",
            content="Mail content"
        )
        
        assert mail.sender_id == "!12345678"
        assert mail.recipient_id == "!87654321"
        assert mail.status == MailStatus.UNREAD
        assert mail.read_at is None
        assert mail.is_unread()
        assert not mail.is_read()
    
    def test_bbs_mail_read_status(self):
        """Test mail read status management"""
        mail = BBSMail(
            sender_id="!12345678",
            sender_name="Sender",
            recipient_id="!87654321",
            subject="Test Mail",
            content="Mail content"
        )
        
        # Initially unread
        assert mail.is_unread()
        assert not mail.is_read()
        assert mail.read_at is None
        
        # Mark as read
        mail.mark_read()
        assert mail.is_read()
        assert not mail.is_unread()
        assert mail.read_at is not None
        assert mail.status == MailStatus.READ
    
    def test_bbs_mail_age_string(self):
        """Test mail age string generation"""
        now = datetime.utcnow()
        
        # Recent mail
        mail = BBSMail(
            sender_id="!12345678",
            sender_name="Sender",
            recipient_id="!87654321",
            subject="Test",
            content="Content",
            timestamp=now - timedelta(seconds=30)
        )
        assert mail.get_age_string() == "Just now"
        
        # Minutes ago
        mail.timestamp = now - timedelta(minutes=5)
        assert "5m ago" in mail.get_age_string()
        
        # Hours ago
        mail.timestamp = now - timedelta(hours=2)
        assert "2h ago" in mail.get_age_string()
        
        # Days ago
        mail.timestamp = now - timedelta(days=3)
        assert "3d ago" in mail.get_age_string()
    
    def test_bbs_channel_creation(self):
        """Test BBSChannel creation and methods"""
        channel = BBSChannel(
            name="Test Repeater",
            frequency="146.520",
            description="Test repeater description",
            channel_type=ChannelType.REPEATER,
            location="Test City",
            tone="123.0"
        )
        
        assert channel.name == "Test Repeater"
        assert channel.frequency == "146.520"
        assert channel.channel_type == ChannelType.REPEATER
        assert channel.active is True
        assert channel.verified is False
    
    def test_bbs_channel_search(self):
        """Test channel search functionality"""
        channel = BBSChannel(
            name="Test Repeater",
            frequency="146.520",
            description="Emergency communications",
            location="Downtown",
            channel_type=ChannelType.REPEATER
        )
        
        # Should match name
        assert channel.matches_search("test")
        assert channel.matches_search("repeater")
        
        # Should match frequency
        assert channel.matches_search("146")
        assert channel.matches_search("520")
        
        # Should match description
        assert channel.matches_search("emergency")
        assert channel.matches_search("communications")
        
        # Should match location
        assert channel.matches_search("downtown")
        
        # Should match type
        assert channel.matches_search("repeater")
        
        # Should not match unrelated terms
        assert not channel.matches_search("xyz123")
    
    def test_js8call_message_creation(self):
        """Test JS8CallMessage creation and methods"""
        msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Test JS8Call message",
            frequency="14.078",
            priority=JS8CallPriority.URGENT
        )
        
        assert msg.callsign == "KD0ABC"
        assert msg.group == "MESH"
        assert msg.priority == JS8CallPriority.URGENT
        assert msg.is_urgent()
        assert not msg.is_emergency()
        assert msg.should_forward_to_mesh()
    
    def test_js8call_message_priorities(self):
        """Test JS8Call message priority handling"""
        # Normal priority
        normal_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Normal message",
            frequency="14.078",
            priority=JS8CallPriority.NORMAL
        )
        
        assert not normal_msg.is_urgent()
        assert not normal_msg.is_emergency()
        assert not normal_msg.should_forward_to_mesh()
        
        # Urgent priority
        urgent_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Urgent message",
            frequency="14.078",
            priority=JS8CallPriority.URGENT
        )
        
        assert urgent_msg.is_urgent()
        assert not urgent_msg.is_emergency()
        assert urgent_msg.should_forward_to_mesh()
        
        # Emergency priority
        emergency_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Emergency message",
            frequency="14.078",
            priority=JS8CallPriority.EMERGENCY
        )
        
        assert emergency_msg.is_urgent()
        assert emergency_msg.is_emergency()
        assert emergency_msg.should_forward_to_mesh()
    
    def test_js8call_mesh_message_generation(self):
        """Test JS8Call mesh message generation"""
        # Normal message
        normal_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Normal message",
            frequency="14.078",
            priority=JS8CallPriority.NORMAL
        )
        
        mesh_msg = normal_msg.generate_mesh_message()
        assert "📻 JS8Call:" in mesh_msg
        assert "KD0ABC" in mesh_msg
        assert "14.078" in mesh_msg
        assert "Normal message" in mesh_msg
        
        # Urgent message
        urgent_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Urgent message",
            frequency="14.078",
            priority=JS8CallPriority.URGENT
        )
        
        mesh_msg = urgent_msg.generate_mesh_message()
        assert "⚠️ URGENT JS8Call:" in mesh_msg
        
        # Emergency message
        emergency_msg = JS8CallMessage(
            callsign="KD0ABC",
            group="MESH",
            message="Emergency message",
            frequency="14.078",
            priority=JS8CallPriority.EMERGENCY
        )
        
        mesh_msg = emergency_msg.generate_mesh_message()
        assert "🚨 EMERGENCY JS8Call:" in mesh_msg
    
    def test_bbs_session_management(self):
        """Test BBS session state management"""
        session = BBSSession(user_id="!12345678")
        
        assert session.current_menu == "main"
        assert len(session.menu_stack) == 0
        
        # Push menu
        session.push_menu("bbs")
        assert session.current_menu == "bbs"
        assert "main" in session.menu_stack
        
        # Push another menu
        session.push_menu("mail")
        assert session.current_menu == "mail"
        assert len(session.menu_stack) == 2
        
        # Pop menu
        previous = session.pop_menu()
        assert previous == "bbs"
        assert session.current_menu == "bbs"
        
        # Pop to main
        previous = session.pop_menu()
        assert previous == "main"
        assert session.current_menu == "main"
        
        # Pop when empty stack
        previous = session.pop_menu()
        assert previous == "main"
        assert session.current_menu == "main"
    
    def test_bbs_session_context(self):
        """Test BBS session context management"""
        session = BBSSession(user_id="!12345678")
        
        # Set and get context
        session.set_context("compose_subject", "Test Subject")
        assert session.get_context("compose_subject") == "Test Subject"
        assert session.get_context("nonexistent", "default") == "default"
        
        # Clear context
        session.clear_context()
        assert session.get_context("compose_subject") is None
    
    def test_bbs_session_expiration(self):
        """Test BBS session expiration"""
        session = BBSSession(user_id="!12345678")
        
        # Fresh session should not be expired
        assert not session.is_expired(30)
        
        # Set old activity time
        session.last_activity = datetime.utcnow() - timedelta(minutes=45)
        assert session.is_expired(30)
        assert not session.is_expired(60)


class TestBBSValidation:
    """Test BBS validation functions"""
    
    def test_validate_bulletin_subject(self):
        """Test bulletin subject validation"""
        # Valid subjects
        assert validate_bulletin_subject("Valid Subject")
        assert validate_bulletin_subject("A" * 100)  # Max length
        
        # Invalid subjects
        assert not validate_bulletin_subject("")
        assert not validate_bulletin_subject("   ")
        assert not validate_bulletin_subject("A" * 101)  # Too long
        assert not validate_bulletin_subject(None)
    
    def test_validate_bulletin_content(self):
        """Test bulletin content validation"""
        # Valid content
        assert validate_bulletin_content("Valid content")
        assert validate_bulletin_content("A" * 2000)  # Max length
        
        # Invalid content
        assert not validate_bulletin_content("")
        assert not validate_bulletin_content("   ")
        assert not validate_bulletin_content("A" * 2001)  # Too long
        assert not validate_bulletin_content(None)
    
    def test_validate_mail_subject(self):
        """Test mail subject validation"""
        # Valid subjects
        assert validate_mail_subject("Valid Subject")
        assert validate_mail_subject("A" * 100)  # Max length
        
        # Invalid subjects
        assert not validate_mail_subject("")
        assert not validate_mail_subject("   ")
        assert not validate_mail_subject("A" * 101)  # Too long
        assert not validate_mail_subject(None)
    
    def test_validate_mail_content(self):
        """Test mail content validation"""
        # Valid content
        assert validate_mail_content("Valid content")
        assert validate_mail_content("A" * 1000)  # Max length
        
        # Invalid content
        assert not validate_mail_content("")
        assert not validate_mail_content("   ")
        assert not validate_mail_content("A" * 1001)  # Too long
        assert not validate_mail_content(None)
    
    def test_validate_channel_name(self):
        """Test channel name validation"""
        # Valid names
        assert validate_channel_name("Valid Channel")
        assert validate_channel_name("A" * 50)  # Max length
        
        # Invalid names
        assert not validate_channel_name("")
        assert not validate_channel_name("   ")
        assert not validate_channel_name("A" * 51)  # Too long
        assert not validate_channel_name(None)


class TestBBSDatabase:
    """Test BBS database operations"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        
        try:
            # Initialize database
            db_manager = initialize_database(db_path)
            bbs_db = BBSDatabase()
            
            # Create test users to satisfy foreign key constraints
            test_users = [
                {
                    'node_id': '!12345678',
                    'short_name': 'TestUser1',
                    'long_name': 'Test User One',
                    'tags': [],
                    'permissions': {},
                    'subscriptions': {}
                },
                {
                    'node_id': '!87654321',
                    'short_name': 'TestUser2',
                    'long_name': 'Test User Two',
                    'tags': [],
                    'permissions': {},
                    'subscriptions': {}
                },
                {
                    'node_id': '!11111111',
                    'short_name': 'TestUser3',
                    'long_name': 'Test User Three',
                    'tags': [],
                    'permissions': {},
                    'subscriptions': {}
                },
                {
                    'node_id': '!99999999',
                    'short_name': 'TestUser4',
                    'long_name': 'Test User Four',
                    'tags': [],
                    'permissions': {},
                    'subscriptions': {}
                }
            ]
            
            for user in test_users:
                db_manager.upsert_user(user)
            
            yield bbs_db
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_create_bulletin(self, temp_db):
        """Test bulletin creation"""
        bulletin = temp_db.create_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser",
            subject="Test Bulletin",
            content="This is a test bulletin content"
        )
        
        assert bulletin is not None
        assert bulletin.id > 0
        assert bulletin.board == "general"
        assert bulletin.sender_id == "!12345678"
        assert bulletin.subject == "Test Bulletin"
    
    def test_get_bulletin(self, temp_db):
        """Test bulletin retrieval"""
        # Create bulletin
        created = temp_db.create_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser",
            subject="Test Bulletin",
            content="Test content"
        )
        
        # Retrieve bulletin
        retrieved = temp_db.get_bulletin(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.subject == created.subject
        assert retrieved.content == created.content
    
    def test_get_bulletins_by_board(self, temp_db):
        """Test getting bulletins by board"""
        # Create bulletins on different boards
        temp_db.create_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        temp_db.create_bulletin("general", "!87654321", "User2", "Subject2", "Content2")
        temp_db.create_bulletin("emergency", "!12345678", "User1", "Subject3", "Content3")
        
        # Get bulletins for general board
        general_bulletins = temp_db.get_bulletins_by_board("general")
        assert len(general_bulletins) == 2
        
        # Get bulletins for emergency board
        emergency_bulletins = temp_db.get_bulletins_by_board("emergency")
        assert len(emergency_bulletins) == 1
        
        # Get bulletins for non-existent board
        empty_bulletins = temp_db.get_bulletins_by_board("nonexistent")
        assert len(empty_bulletins) == 0
    
    def test_send_mail(self, temp_db):
        """Test mail sending"""
        mail = temp_db.send_mail(
            sender_id="!12345678",
            sender_name="Sender",
            recipient_id="!87654321",
            subject="Test Mail",
            content="This is test mail content"
        )
        
        assert mail is not None
        assert mail.id > 0
        assert mail.sender_id == "!12345678"
        assert mail.recipient_id == "!87654321"
        assert mail.subject == "Test Mail"
    
    def test_get_user_mail(self, temp_db):
        """Test getting user mail"""
        recipient_id = "!87654321"
        
        # Send some mail
        temp_db.send_mail("!12345678", "Sender1", recipient_id, "Subject1", "Content1")
        temp_db.send_mail("!11111111", "Sender2", recipient_id, "Subject2", "Content2")
        temp_db.send_mail("!12345678", "Sender1", "!99999999", "Subject3", "Content3")  # Different recipient
        
        # Get mail for recipient
        user_mail = temp_db.get_user_mail(recipient_id)
        assert len(user_mail) == 2
        
        # Check unread count
        unread_count = temp_db.get_unread_mail_count(recipient_id)
        assert unread_count == 2
    
    def test_mark_mail_read(self, temp_db):
        """Test marking mail as read"""
        # Send mail
        mail = temp_db.send_mail(
            sender_id="!12345678",
            sender_name="Sender",
            recipient_id="!87654321",
            subject="Test Mail",
            content="Test content"
        )
        
        # Initially unread
        unread_count = temp_db.get_unread_mail_count("!87654321")
        assert unread_count == 1
        
        # Mark as read
        success = temp_db.mark_mail_read(mail.id, "!87654321")
        assert success
        
        # Check unread count
        unread_count = temp_db.get_unread_mail_count("!87654321")
        assert unread_count == 0
    
    def test_add_channel(self, temp_db):
        """Test adding channel to directory"""
        channel = temp_db.add_channel(
            name="Test Repeater",
            frequency="146.520",
            description="Test repeater description",
            channel_type="repeater",
            location="Test City",
            coverage_area="50 miles",
            tone="123.0",
            offset="-0.6",
            added_by="!12345678"
        )
        
        assert channel is not None
        assert channel.id > 0
        assert channel.name == "Test Repeater"
        assert channel.frequency == "146.520"
        assert channel.channel_type == ChannelType.REPEATER
    
    def test_search_channels(self, temp_db):
        """Test channel search"""
        # Add some channels
        temp_db.add_channel("Test Repeater", "146.520", "Emergency repeater", "repeater", "Downtown", "", "", "", "!12345678")
        temp_db.add_channel("Simplex", "146.550", "Simplex frequency", "simplex", "Uptown", "", "", "", "!12345678")
        temp_db.add_channel("Digital", "70cm", "Digital mode", "digital", "Suburb", "", "", "", "!12345678")
        
        # Search by name
        results = temp_db.search_channels("repeater")
        assert len(results) == 1
        assert results[0].name == "Test Repeater"
        
        # Search by frequency
        results = temp_db.search_channels("146")
        assert len(results) == 2
        
        # Search by description
        results = temp_db.search_channels("emergency")
        assert len(results) == 1
        
        # Search by location
        results = temp_db.search_channels("downtown")
        assert len(results) == 1
    
    def test_get_statistics(self, temp_db):
        """Test getting BBS statistics"""
        # Add some data
        temp_db.create_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        temp_db.create_bulletin("emergency", "!12345678", "User1", "Subject2", "Content2")
        temp_db.send_mail("!12345678", "Sender", "!87654321", "Subject", "Content")
        temp_db.add_channel("Test", "146.520", "Description", "repeater", "", "", "", "", "!12345678")
        
        stats = temp_db.get_statistics()
        
        assert stats['total_bulletins'] == 2
        assert stats['bulletin_boards'] == 2
        assert stats['total_mail'] == 1
        assert stats['unread_mail'] == 1
        assert stats['active_channels'] == 1


def test_generate_unique_id():
    """Test unique ID generation"""
    content = "Test content"
    sender_id = "!12345678"
    timestamp = datetime.utcnow()
    
    # Same inputs should generate same ID
    id1 = generate_unique_id(content, sender_id, timestamp)
    id2 = generate_unique_id(content, sender_id, timestamp)
    assert id1 == id2
    
    # Different inputs should generate different IDs
    id3 = generate_unique_id("Different content", sender_id, timestamp)
    assert id1 != id3
    
    # ID should be reasonable length
    assert len(id1) == 16
    assert isinstance(id1, str)