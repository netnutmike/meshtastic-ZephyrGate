"""
Unit tests for BBS bulletin service
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import initialize_database
from src.services.bbs.bulletin_service import BulletinService, get_bulletin_service
from src.services.bbs.database import BBSDatabase


class TestBulletinService:
    """Test bulletin service functionality"""
    
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
                }
            ]
            
            for user in test_users:
                db_manager.upsert_user(user)
            
            # Reset global services
            import src.services.bbs.bulletin_service
            import src.services.bbs.database
            src.services.bbs.bulletin_service.bulletin_service = None
            src.services.bbs.database.bbs_db = None
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def bulletin_service(self, setup_fresh_db):
        """Create bulletin service with fresh database"""
        return BulletinService()
    
    def test_post_bulletin_success(self, bulletin_service):
        """Test successful bulletin posting"""
        success, message = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Test Bulletin",
            content="This is a test bulletin content."
        )
        
        assert success is True
        assert "posted to 'general' board successfully" in message
        assert "#" in message  # Should contain bulletin ID
    
    def test_post_bulletin_invalid_subject(self, bulletin_service):
        """Test posting bulletin with invalid subject"""
        # Empty subject
        success, message = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="",
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid subject" in message
        
        # Too long subject
        long_subject = "A" * 101
        success, message = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject=long_subject,
            content="Valid content"
        )
        
        assert success is False
        assert "Invalid subject" in message
    
    def test_post_bulletin_invalid_content(self, bulletin_service):
        """Test posting bulletin with invalid content"""
        # Empty content
        success, message = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Valid Subject",
            content=""
        )
        
        assert success is False
        assert "Invalid content" in message
        
        # Too long content
        long_content = "A" * 2001
        success, message = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Valid Subject",
            content=long_content
        )
        
        assert success is False
        assert "Invalid content" in message
    
    def test_post_bulletin_default_board(self, bulletin_service):
        """Test posting bulletin with empty board name defaults to general"""
        success, message = bulletin_service.post_bulletin(
            board="",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Test Subject",
            content="Test content"
        )
        
        assert success is True
        assert "'general' board" in message
    
    def test_get_bulletin_success(self, bulletin_service):
        """Test successful bulletin retrieval"""
        # First post a bulletin
        success, post_msg = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Test Bulletin",
            content="This is test content."
        )
        assert success is True
        
        # Extract bulletin ID from message
        import re
        match = re.search(r'#(\d+)', post_msg)
        assert match is not None
        bulletin_id = int(match.group(1))
        
        # Get the bulletin
        success, formatted = bulletin_service.get_bulletin(bulletin_id, "!87654321")
        
        assert success is True
        assert f"Bulletin #{bulletin_id}" in formatted
        assert "Test Bulletin" in formatted
        assert "This is test content." in formatted
        assert "TestUser1" in formatted
    
    def test_get_bulletin_not_found(self, bulletin_service):
        """Test getting non-existent bulletin"""
        success, message = bulletin_service.get_bulletin(999, "!12345678")
        
        assert success is False
        assert "not found" in message
    
    def test_list_bulletins_empty(self, bulletin_service):
        """Test listing bulletins when board is empty"""
        success, message = bulletin_service.list_bulletins("general", user_id="!12345678")
        
        assert success is True
        assert "No bulletins found on 'general' board" in message
    
    def test_list_bulletins_with_content(self, bulletin_service):
        """Test listing bulletins with content"""
        # Post some bulletins
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        bulletin_service.post_bulletin("general", "!87654321", "User2", "Subject2", "Content2")
        bulletin_service.post_bulletin("emergency", "!12345678", "User1", "Subject3", "Content3")
        
        # List general board
        success, formatted = bulletin_service.list_bulletins("general", user_id="!12345678")
        
        assert success is True
        assert "Bulletins on 'general' board" in formatted
        assert "Subject1" in formatted
        assert "Subject2" in formatted
        assert "Subject3" not in formatted  # Should not be in general board
        assert "Total: 2 bulletins" in formatted
    
    def test_list_all_bulletins(self, bulletin_service):
        """Test listing bulletins from all boards"""
        # Post bulletins to different boards
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        bulletin_service.post_bulletin("emergency", "!87654321", "User2", "Subject2", "Content2")
        
        success, formatted = bulletin_service.list_all_bulletins(user_id="!12345678")
        
        assert success is True
        assert "Recent bulletins from all boards" in formatted
        assert "Subject1" in formatted
        assert "Subject2" in formatted
        assert "general" in formatted
        assert "emergency" in formatted
    
    def test_delete_bulletin_success(self, bulletin_service):
        """Test successful bulletin deletion"""
        # Post a bulletin
        success, post_msg = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Test Subject",
            content="Test content"
        )
        assert success is True
        
        # Extract bulletin ID
        import re
        match = re.search(r'#(\d+)', post_msg)
        bulletin_id = int(match.group(1))
        
        # Delete the bulletin (by original poster)
        success, message = bulletin_service.delete_bulletin(bulletin_id, "!12345678")
        
        assert success is True
        assert "deleted successfully" in message
    
    def test_delete_bulletin_not_found(self, bulletin_service):
        """Test deleting non-existent bulletin"""
        success, message = bulletin_service.delete_bulletin(999, "!12345678")
        
        assert success is False
        assert "not found" in message
    
    def test_delete_bulletin_not_owner(self, bulletin_service):
        """Test deleting bulletin by non-owner"""
        # Post a bulletin
        success, post_msg = bulletin_service.post_bulletin(
            board="general",
            sender_id="!12345678",
            sender_name="TestUser1",
            subject="Test Subject",
            content="Test content"
        )
        assert success is True
        
        # Extract bulletin ID
        import re
        match = re.search(r'#(\d+)', post_msg)
        bulletin_id = int(match.group(1))
        
        # Try to delete by different user
        success, message = bulletin_service.delete_bulletin(bulletin_id, "!87654321")
        
        assert success is False
        assert "only delete your own bulletins" in message
    
    def test_search_bulletins_empty_term(self, bulletin_service):
        """Test searching with empty term"""
        success, message = bulletin_service.search_bulletins("", user_id="!12345678")
        
        assert success is False
        assert "cannot be empty" in message
    
    def test_search_bulletins_no_results(self, bulletin_service):
        """Test searching with no results"""
        success, message = bulletin_service.search_bulletins("nonexistent", user_id="!12345678")
        
        assert success is True
        assert "No bulletins found matching" in message
    
    def test_search_bulletins_with_results(self, bulletin_service):
        """Test searching with results"""
        # Post some bulletins
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Python Tutorial", "Learn Python programming")
        bulletin_service.post_bulletin("general", "!87654321", "User2", "Java Guide", "Java programming guide")
        bulletin_service.post_bulletin("tech", "!12345678", "User1", "Python Tips", "Advanced Python tips")
        
        # Search for Python
        success, formatted = bulletin_service.search_bulletins("Python", user_id="!12345678")
        
        assert success is True
        assert "Search results for 'Python'" in formatted
        assert "Python Tutorial" in formatted
        assert "Python Tips" in formatted
        assert "Java Guide" not in formatted
    
    def test_search_bulletins_specific_board(self, bulletin_service):
        """Test searching within specific board"""
        # Post bulletins to different boards
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Python Tutorial", "Learn Python")
        bulletin_service.post_bulletin("tech", "!12345678", "User1", "Python Tips", "Advanced Python")
        
        # Search only in general board
        success, formatted = bulletin_service.search_bulletins("Python", board="general", user_id="!12345678")
        
        assert success is True
        assert "on 'general' board" in formatted
        assert "Python Tutorial" in formatted
        assert "Python Tips" not in formatted  # Should not appear (different board)
    
    def test_get_bulletin_boards_empty(self, bulletin_service):
        """Test getting boards when none exist"""
        success, message = bulletin_service.get_bulletin_boards()
        
        assert success is True
        assert "No bulletin boards found" in message
    
    def test_get_bulletin_boards_with_content(self, bulletin_service):
        """Test getting boards with content"""
        # Post to different boards
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        bulletin_service.post_bulletin("emergency", "!87654321", "User2", "Subject2", "Content2")
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject3", "Content3")
        
        success, formatted = bulletin_service.get_bulletin_boards()
        
        assert success is True
        assert "Available bulletin boards" in formatted
        assert "general" in formatted
        assert "emergency" in formatted
        assert "(2 bulletins)" in formatted  # general should have 2
        assert "(1 bulletins)" in formatted  # emergency should have 1
    
    def test_get_bulletin_stats_global(self, bulletin_service):
        """Test getting global bulletin statistics"""
        # Post some bulletins
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        bulletin_service.post_bulletin("emergency", "!87654321", "User2", "Subject2", "Content2")
        
        stats = bulletin_service.get_bulletin_stats()
        
        assert stats['total_bulletins'] == 2
        assert stats['total_boards'] == 2
        assert stats['unique_posters'] == 2
        assert stats['oldest_bulletin'] is not None
        assert stats['newest_bulletin'] is not None
    
    def test_get_bulletin_stats_board_specific(self, bulletin_service):
        """Test getting board-specific statistics"""
        # Post bulletins to different boards
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Subject1", "Content1")
        bulletin_service.post_bulletin("general", "!87654321", "User2", "Subject2", "Content2")
        bulletin_service.post_bulletin("emergency", "!12345678", "User1", "Subject3", "Content3")
        
        stats = bulletin_service.get_bulletin_stats(board="general")
        
        assert stats['board'] == "general"
        assert stats['total_bulletins'] == 2
        assert stats['unique_posters'] == 2
        assert stats['oldest_bulletin'] is not None
        assert stats['newest_bulletin'] is not None
    
    def test_get_recent_activity_empty(self, bulletin_service):
        """Test getting recent activity when none exists"""
        success, message = bulletin_service.get_recent_activity(hours=24)
        
        assert success is True
        assert "No bulletin activity in the last 24 hours" in message
    
    def test_get_recent_activity_with_content(self, bulletin_service):
        """Test getting recent activity with content"""
        # Post some bulletins
        bulletin_service.post_bulletin("general", "!12345678", "User1", "Recent Post", "Recent content")
        bulletin_service.post_bulletin("tech", "!87654321", "User2", "Another Post", "More content")
        
        success, formatted = bulletin_service.get_recent_activity(hours=24)
        
        assert success is True
        assert "Bulletin activity in the last 24 hours" in formatted
        assert "Recent Post" in formatted
        assert "Another Post" in formatted
        assert "Total: 2 new bulletins" in formatted
    
    def test_get_recent_activity_board_specific(self, bulletin_service):
        """Test getting recent activity for specific board"""
        # Post to different boards
        bulletin_service.post_bulletin("general", "!12345678", "User1", "General Post", "General content")
        bulletin_service.post_bulletin("tech", "!87654321", "User2", "Tech Post", "Tech content")
        
        success, formatted = bulletin_service.get_recent_activity(board="general", hours=24)
        
        assert success is True
        assert "on 'general' board" in formatted
        assert "General Post" in formatted
        assert "Tech Post" not in formatted
        assert "Total: 1 new bulletins" in formatted
    
    def test_age_calculation(self, bulletin_service):
        """Test age calculation formatting"""
        # Test different age calculations
        now = datetime.utcnow()
        
        # Test seconds
        recent_time = now - timedelta(seconds=30)
        age = bulletin_service._calculate_age(recent_time)
        assert age == "now"
        
        # Test minutes
        minutes_ago = now - timedelta(minutes=5)
        age = bulletin_service._calculate_age(minutes_ago)
        assert age == "5m"
        
        # Test hours
        hours_ago = now - timedelta(hours=3)
        age = bulletin_service._calculate_age(hours_ago)
        assert age == "3h"
        
        # Test days
        days_ago = now - timedelta(days=5)
        age = bulletin_service._calculate_age(days_ago)
        assert age == "5d"
        
        # Test months
        months_ago = now - timedelta(days=60)
        age = bulletin_service._calculate_age(months_ago)
        assert age == "2mo"
        
        # Test years
        years_ago = now - timedelta(days=400)
        age = bulletin_service._calculate_age(years_ago)
        assert age == "1y"


def test_get_bulletin_service_singleton():
    """Test bulletin service singleton pattern"""
    service1 = get_bulletin_service()
    service2 = get_bulletin_service()
    
    assert service1 is service2
    assert isinstance(service1, BulletinService)