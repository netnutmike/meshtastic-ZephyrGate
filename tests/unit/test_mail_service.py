"""
Unit tests for BBS mail service
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import initialize_database
from src.services.bbs.mail_service import MailService, get_mail_service
from src.services.bbs.database import BBSDatabase


class TestMailService:
    """Test mail service functionality"""
    
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
                }
            ]
            
            for user in test_users:
                db_manager.upsert_user(user)
            
            # Reset global services
            import src.services.bbs.mail_service
            import src.services.bbs.database
            src.services.bbs.mail_service.mail_service = None
            src.services.bbs.database.bbs_db = None
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def mail_service(self, setup_fresh_db):
        """Create mail service with fresh database"""
        return MailService()
    
    def test_send_mail_success(self, mail_service):
        """Test successful mail sending"""
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject="Test Mail",
            content="This is a test mail message."
        )
        
        assert success is True
        assert "sent to !87654321 successfully" in message
    
    def test_send_mail_invalid_subject(self, mail_service):
        """Test sending mail with invalid subject"""
        # Empty subject
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject="",
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid subject" in message
        
        # Too long subject
        long_subject = "A" * 101
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject=long_subject,
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid subject" in message
    
    def test_send_mail_invalid_content(self, mail_service):
        """Test sending mail with invalid content"""
        # Empty content
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject="Valid Subject",
            content=""
        )
        
        assert success is False
        assert "Invalid content" in message
        
        # Too long content
        long_content = "A" * 1001
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject="Valid Subject",
            content=long_content
        )
        
        assert success is False
        assert "Invalid content" in message
    
    def test_send_mail_invalid_recipient(self, mail_service):
        """Test sending mail with invalid recipient"""
        # Invalid format
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="invalid",
            subject="Valid Subject",
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid recipient node ID format" in message
        
        # Wrong length
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!123",
            subject="Valid Subject",
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid recipient node ID format" in message
    
    def test_send_mail_to_self(self, mail_service):
        """Test sending mail to self"""
        success, message = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!12345678",
            subject="Valid Subject",
            content="Valid content"
        )
        
        assert success is False
        assert "cannot send mail to yourself" in message
    
    def test_get_mail_success(self, mail_service):
        """Test successful mail retrieval"""
        # First send a mail
        success, send_msg = mail_service.send_mail(
            sender_id="!12345678",
            sender_name="TestUser1",
            recipient_id="!87654321",
            subject="Test Mail",
            content="This is test content."
        )
        assert success is True
        
        # Get the mail ID from database (we know it will be 1 for first mail)
        mail_id = 1
        
        # Get the mail
        success, formatted = mail_service.get_mail(mail_id, "!87654321")
        
        assert success is True
        assert f"Mail #{mail_id}" in formatted
        assert "Test Mail" in formatted
        assert "This is test content." in formatted
        assert "TestUser1" in formatted
    
    def test_get_mail_not_found(self, mail_service):
        """Test getting non-existent mail"""
        success, message = mail_service.get_mail(999, "!12345678")
        
        assert success is False
        assert "not found" in message
    
    def test_get_mail_not_owner(self, mail_service):
        """Test getting mail by non-recipient"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Try to read by different user
        success, message = mail_service.get_mail(1, "!11111111")
        
        assert success is False
        assert "only read your own mail" in message
    
    def test_list_mail_empty(self, mail_service):
        """Test listing mail when empty"""
        success, message = mail_service.list_mail("!12345678")
        
        assert success is True
        assert "No mail messages found" in message
    
    def test_list_mail_with_content(self, mail_service):
        """Test listing mail with content"""
        # Send some mail
        mail_service.send_mail("!12345678", "User1", "!87654321", "Subject1", "Content1")
        mail_service.send_mail("!11111111", "User3", "!87654321", "Subject2", "Content2")
        mail_service.send_mail("!12345678", "User1", "!11111111", "Subject3", "Content3")  # Different recipient
        
        # List mail for recipient
        success, formatted = mail_service.list_mail("!87654321")
        
        assert success is True
        assert "Your Mail Messages" in formatted
        assert "Subject1" in formatted
        assert "Subject2" in formatted
        assert "Subject3" not in formatted  # Should not appear (different recipient)
        assert "Total: 2 messages" in formatted
    
    def test_list_unread_mail(self, mail_service):
        """Test listing only unread mail"""
        # Send mail
        mail_service.send_mail("!12345678", "User1", "!87654321", "Subject1", "Content1")
        mail_service.send_mail("!11111111", "User3", "!87654321", "Subject2", "Content2")
        
        # Mark one as read
        mail_service.mark_mail_read(1, "!87654321")
        
        # List unread mail
        success, formatted = mail_service.list_unread_mail("!87654321")
        
        assert success is True
        assert "Your Unread Mail Messages" in formatted
        assert "Subject2" in formatted
        assert "Subject1" not in formatted  # Should not appear (marked as read)
    
    def test_delete_mail_success(self, mail_service):
        """Test successful mail deletion"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Delete the mail (by recipient)
        success, message = mail_service.delete_mail(1, "!87654321")
        
        assert success is True
        assert "deleted successfully" in message
    
    def test_delete_mail_not_found(self, mail_service):
        """Test deleting non-existent mail"""
        success, message = mail_service.delete_mail(999, "!12345678")
        
        assert success is False
        assert "not found" in message
    
    def test_delete_mail_not_owner(self, mail_service):
        """Test deleting mail by non-recipient"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Try to delete by different user
        success, message = mail_service.delete_mail(1, "!11111111")
        
        assert success is False
        assert "only delete your own mail" in message
    
    def test_get_unread_count(self, mail_service):
        """Test getting unread mail count"""
        user_id = "!87654321"
        
        # Initially no mail
        count = mail_service.get_unread_count(user_id)
        assert count == 0
        
        # Send some mail
        mail_service.send_mail("!12345678", "User1", user_id, "Subject1", "Content1")
        mail_service.send_mail("!11111111", "User3", user_id, "Subject2", "Content2")
        
        # Should have 2 unread
        count = mail_service.get_unread_count(user_id)
        assert count == 2
        
        # Mark one as read
        mail_service.mark_mail_read(1, user_id)
        
        # Should have 1 unread
        count = mail_service.get_unread_count(user_id)
        assert count == 1
    
    def test_mark_mail_read_success(self, mail_service):
        """Test marking mail as read"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Mark as read
        success, message = mail_service.mark_mail_read(1, "!87654321")
        
        assert success is True
        assert "marked as read" in message
    
    def test_mark_mail_read_already_read(self, mail_service):
        """Test marking already read mail"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Mark as read twice
        mail_service.mark_mail_read(1, "!87654321")
        success, message = mail_service.mark_mail_read(1, "!87654321")
        
        assert success is True
        assert "already marked as read" in message
    
    def test_mark_mail_read_not_owner(self, mail_service):
        """Test marking mail as read by non-recipient"""
        # Send mail
        mail_service.send_mail("!12345678", "TestUser1", "!87654321", "Subject", "Content")
        
        # Try to mark as read by different user
        success, message = mail_service.mark_mail_read(1, "!11111111")
        
        assert success is False
        assert "only mark your own mail" in message
    
    def test_get_mail_stats(self, mail_service):
        """Test getting mail statistics"""
        user_id = "!87654321"
        
        # Initially no mail
        stats = mail_service.get_mail_stats(user_id)
        assert stats['total_mail'] == 0
        assert stats['unread_mail'] == 0
        assert stats['unique_senders'] == 0
        
        # Send some mail
        mail_service.send_mail("!12345678", "User1", user_id, "Subject1", "Content1")
        mail_service.send_mail("!11111111", "User3", user_id, "Subject2", "Content2")
        mail_service.send_mail("!12345678", "User1", user_id, "Subject3", "Content3")
        
        # Mark one as read
        mail_service.mark_mail_read(1, user_id)
        
        stats = mail_service.get_mail_stats(user_id)
        assert stats['total_mail'] == 3
        assert stats['unread_mail'] == 2
        assert stats['read_mail'] == 1
        assert stats['unique_senders'] == 2
        assert stats['most_active_sender']['sender_id'] == "!12345678"
        assert stats['most_active_sender']['message_count'] == 2
    
    def test_search_mail_empty_term(self, mail_service):
        """Test searching with empty term"""
        success, message = mail_service.search_mail("!12345678", "")
        
        assert success is False
        assert "cannot be empty" in message
    
    def test_search_mail_no_results(self, mail_service):
        """Test searching with no results"""
        success, message = mail_service.search_mail("!12345678", "nonexistent")
        
        assert success is True
        assert "No mail found matching" in message
    
    def test_search_mail_with_results(self, mail_service):
        """Test searching with results"""
        user_id = "!87654321"
        
        # Send some mail
        mail_service.send_mail("!12345678", "User1", user_id, "Python Tutorial", "Learn Python programming")
        mail_service.send_mail("!11111111", "User3", user_id, "Java Guide", "Java programming guide")
        mail_service.send_mail("!12345678", "User1", user_id, "Meeting Notes", "Python discussion notes")
        
        # Search for Python
        success, formatted = mail_service.search_mail(user_id, "Python")
        
        assert success is True
        assert "Mail search results for 'Python'" in formatted
        assert "Python Tutorial" in formatted
        assert "Meeting Notes" in formatted  # Should match content
        assert "Java Guide" not in formatted
    
    def test_get_conversation(self, mail_service):
        """Test getting conversation thread"""
        user_id = "!87654321"
        other_user = "!12345678"
        
        # Send mail from different users
        mail_service.send_mail(other_user, "User1", user_id, "First message", "Hello there")
        mail_service.send_mail("!11111111", "User3", user_id, "Different user", "From someone else")
        mail_service.send_mail(other_user, "User1", user_id, "Second message", "Follow up")
        
        # Get conversation
        success, formatted = mail_service.get_conversation(user_id, other_user)
        
        assert success is True
        assert f"Conversation with {other_user}" in formatted
        assert "First message" in formatted
        assert "Second message" in formatted
        assert "Different user" not in formatted  # Should not appear (different sender)
    
    def test_get_conversation_empty(self, mail_service):
        """Test getting conversation when none exists"""
        success, message = mail_service.get_conversation("!87654321", "!12345678")
        
        assert success is True
        assert "No conversation found" in message
    
    def test_get_recent_activity_empty(self, mail_service):
        """Test getting recent activity when none exists"""
        success, message = mail_service.get_recent_activity("!12345678", hours=24)
        
        assert success is True
        assert "No mail activity in the last 24 hours" in message
    
    def test_get_recent_activity_with_content(self, mail_service):
        """Test getting recent activity with content"""
        user_id = "!87654321"
        
        # Send some mail
        mail_service.send_mail("!12345678", "User1", user_id, "Recent Mail", "Recent content")
        mail_service.send_mail("!11111111", "User3", user_id, "Another Mail", "More content")
        
        success, formatted = mail_service.get_recent_activity(user_id, hours=24)
        
        assert success is True
        assert "Mail activity in the last 24 hours" in formatted
        assert "Recent Mail" in formatted
        assert "Another Mail" in formatted
        assert "Total: 2 new messages" in formatted
    
    def test_age_calculation(self, mail_service):
        """Test age calculation formatting"""
        # Test different age calculations
        now = datetime.utcnow()
        
        # Test seconds
        recent_time = now - timedelta(seconds=30)
        age = mail_service._calculate_age(recent_time)
        assert age == "now"
        
        # Test minutes
        minutes_ago = now - timedelta(minutes=5)
        age = mail_service._calculate_age(minutes_ago)
        assert age == "5m"
        
        # Test hours
        hours_ago = now - timedelta(hours=3)
        age = mail_service._calculate_age(hours_ago)
        assert age == "3h"
        
        # Test days
        days_ago = now - timedelta(days=5)
        age = mail_service._calculate_age(days_ago)
        assert age == "5d"
        
        # Test months
        months_ago = now - timedelta(days=60)
        age = mail_service._calculate_age(months_ago)
        assert age == "2mo"
        
        # Test years
        years_ago = now - timedelta(days=400)
        age = mail_service._calculate_age(years_ago)
        assert age == "1y"


def test_get_mail_service_singleton():
    """Test mail service singleton pattern"""
    service1 = get_mail_service()
    service2 = get_mail_service()
    
    assert service1 is service2
    assert isinstance(service1, MailService)