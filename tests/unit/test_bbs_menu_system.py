"""
Unit tests for BBS menu system
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import initialize_database
from src.services.bbs.menu_system import BBSMenuSystem, MenuType
from src.services.bbs.models import BBSSession
from src.services.bbs.database import BBSDatabase


class TestBBSMenuSystem:
    """Test BBS menu system"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
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
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def menu_system(self, temp_db):
        """Create BBS menu system with temporary database"""
        return BBSMenuSystem()
    
    def test_session_creation(self, menu_system):
        """Test session creation and management"""
        user_id = "!12345678"
        
        # Get session (should create new one)
        session = menu_system.get_session(user_id)
        assert session.user_id == user_id
        assert session.current_menu == "main"
        assert len(session.menu_stack) == 0
        
        # Get same session again
        session2 = menu_system.get_session(user_id)
        assert session is session2
    
    def test_session_cleanup(self, menu_system):
        """Test expired session cleanup"""
        user_id = "!12345678"
        
        # Create session
        session = menu_system.get_session(user_id)
        assert user_id in menu_system.sessions
        
        # Make session expired
        session.last_activity = datetime.utcnow() - timedelta(minutes=45)
        
        # Get session again (should trigger cleanup)
        new_session = menu_system.get_session(user_id)
        assert new_session is not session  # Should be a new session
        assert new_session.user_id == user_id
    
    def test_main_menu_display(self, menu_system):
        """Test main menu display"""
        user_id = "!12345678"
        
        # Process empty command (should show menu)
        response = menu_system.process_command(user_id, "")
        
        assert "MAIN MENU" in response
        assert "bbs" in response.lower()
        assert "utilities" in response.lower()
        assert "help" in response.lower()
        assert "quit" in response.lower()
    
    def test_help_command(self, menu_system):
        """Test help command"""
        user_id = "!12345678"
        
        # General help
        response = menu_system.process_command(user_id, "help")
        assert "MAIN MENU" in response
        
        # Help for specific command
        response = menu_system.process_command(user_id, "help bbs")
        assert "bbs" in response.lower()
        assert "description" in response.lower()
    
    def test_navigation_to_bbs(self, menu_system):
        """Test navigation to BBS menu"""
        user_id = "!12345678"
        
        # Enter BBS
        response = menu_system.process_command(user_id, "bbs")
        
        assert "Welcome to the BBS system" in response
        assert "BBS MENU" in response
        assert "mail" in response.lower()
        assert "bulletins" in response.lower()
        assert "channels" in response.lower()
        
        # Check session state
        session = menu_system.get_session(user_id)
        assert session.current_menu == "bbs"
        assert "main" in session.menu_stack
    
    def test_navigation_back(self, menu_system):
        """Test back navigation"""
        user_id = "!12345678"
        
        # Enter BBS, then mail
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        
        session = menu_system.get_session(user_id)
        assert session.current_menu == "mail"
        
        # Go back
        response = menu_system.process_command(user_id, "back")
        
        assert "Returned to bbs menu" in response
        session = menu_system.get_session(user_id)
        assert session.current_menu == "bbs"
    
    def test_navigation_to_main(self, menu_system):
        """Test navigation to main menu"""
        user_id = "!12345678"
        
        # Navigate deep into menus
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        
        # Go to main
        response = menu_system.process_command(user_id, "main")
        
        assert "Returned to main menu" in response
        session = menu_system.get_session(user_id)
        assert session.current_menu == "main"
        assert len(session.menu_stack) == 0
    
    def test_quit_command(self, menu_system):
        """Test quit command"""
        user_id = "!12345678"
        
        # Create session
        menu_system.get_session(user_id)
        assert user_id in menu_system.sessions
        
        # Quit
        response = menu_system.process_command(user_id, "quit")
        
        assert "Thank you for using the BBS system" in response
        assert user_id not in menu_system.sessions
    
    def test_mail_menu(self, menu_system):
        """Test mail menu functionality"""
        user_id = "!12345678"
        
        # Navigate to mail
        menu_system.process_command(user_id, "bbs")
        response = menu_system.process_command(user_id, "mail")
        
        assert "Personal Mail System" in response
        assert "unread message" in response
        assert "MAIL MENU" in response
        assert "list" in response.lower()
        assert "read" in response.lower()
        assert "send" in response.lower()
    
    def test_mail_list_empty(self, menu_system):
        """Test listing mail when empty"""
        user_id = "!12345678"
        
        # Navigate to mail and list
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        response = menu_system.process_command(user_id, "list")
        
        assert "No mail messages found" in response
    
    def test_bulletin_menu(self, menu_system):
        """Test bulletin menu functionality"""
        user_id = "!12345678"
        
        # Navigate to bulletins
        menu_system.process_command(user_id, "bbs")
        response = menu_system.process_command(user_id, "bulletins")
        
        assert "Public Bulletin System" in response
        assert "Current board: general" in response
        assert "BULLETINS MENU" in response
        assert "list" in response.lower()
        assert "post" in response.lower()
        assert "boards" in response.lower()
    
    def test_bulletin_list_empty(self, menu_system):
        """Test listing bulletins when empty"""
        user_id = "!12345678"
        
        # Navigate to bulletins and list
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "bulletins")
        response = menu_system.process_command(user_id, "list")
        
        assert "No bulletins found on board 'general'" in response
    
    def test_bulletin_board_switching(self, menu_system):
        """Test switching bulletin boards"""
        user_id = "!12345678"
        
        # Navigate to bulletins
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "bulletins")
        
        # Switch board
        response = menu_system.process_command(user_id, "board emergency")
        assert "Switched to 'emergency' board" in response
        
        # Check session context
        session = menu_system.get_session(user_id)
        assert session.get_context("current_board") == "emergency"
    
    def test_channel_menu(self, menu_system):
        """Test channel menu functionality"""
        user_id = "!12345678"
        
        # Navigate to channels
        menu_system.process_command(user_id, "bbs")
        response = menu_system.process_command(user_id, "channels")
        
        assert "Channel Directory" in response
        assert "channels available" in response
        assert "CHANNELS MENU" in response
        assert "list" in response.lower()
        assert "add" in response.lower()
        assert "search" in response.lower()
    
    def test_channel_list_empty(self, menu_system):
        """Test listing channels when empty"""
        user_id = "!12345678"
        
        # Navigate to channels and list
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "channels")
        response = menu_system.process_command(user_id, "list")
        
        assert "No channels found in directory" in response
    
    def test_utilities_menu(self, menu_system):
        """Test utilities menu"""
        user_id = "!12345678"
        
        # Navigate to utilities
        response = menu_system.process_command(user_id, "utilities")
        
        assert "System Utilities" in response
        assert "UTILITIES MENU" in response
        assert "stats" in response.lower()
        assert "fortune" in response.lower()
        assert "time" in response.lower()
    
    def test_stats_command(self, menu_system):
        """Test stats command"""
        user_id = "!12345678"
        
        # Navigate to utilities and show stats
        menu_system.process_command(user_id, "utilities")
        response = menu_system.process_command(user_id, "stats")
        
        assert "BBS System Statistics" in response
        assert "Total Bulletins:" in response
        assert "Total Mail:" in response
        assert "Active Sessions:" in response
    
    def test_fortune_command(self, menu_system):
        """Test fortune command"""
        user_id = "!12345678"
        
        # Navigate to utilities and show fortune
        menu_system.process_command(user_id, "utilities")
        response = menu_system.process_command(user_id, "fortune")
        
        assert "Fortune:" in response
        assert len(response) > 10  # Should have some content
    
    def test_time_command(self, menu_system):
        """Test time command"""
        user_id = "!12345678"
        
        # Navigate to utilities and show time
        menu_system.process_command(user_id, "utilities")
        response = menu_system.process_command(user_id, "time")
        
        assert "Current UTC time:" in response
        assert datetime.utcnow().strftime("%Y") in response
    
    def test_invalid_command(self, menu_system):
        """Test invalid command handling"""
        user_id = "!12345678"
        
        response = menu_system.process_command(user_id, "invalid_command")
        
        assert "Unknown command 'invalid_command'" in response
        assert "Type 'help' for available commands" in response
    
    def test_command_requiring_args(self, menu_system):
        """Test commands that require arguments"""
        user_id = "!12345678"
        
        # Navigate to mail menu
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        
        # Try read command without arguments
        response = menu_system.process_command(user_id, "read")
        
        assert "requires arguments" in response
        assert "Type 'help' for usage" in response
    
    def test_mail_composition_start(self, menu_system):
        """Test starting mail composition"""
        user_id = "!12345678"
        
        # Navigate to mail and start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        response = menu_system.process_command(user_id, "send")
        
        assert "Compose New Mail" in response
        assert "Enter recipient node ID" in response
        
        # Check session state
        session = menu_system.get_session(user_id)
        assert session.current_menu == "compose"
        assert session.get_context("compose_type") == "mail"
        assert session.get_context("compose_step") == "recipient"
    
    def test_bulletin_composition_start(self, menu_system):
        """Test starting bulletin composition"""
        user_id = "!12345678"
        
        # Navigate to bulletins and start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "bulletins")
        response = menu_system.process_command(user_id, "post")
        
        assert "Compose New Bulletin" in response
        assert "Enter subject" in response
        
        # Check session state
        session = menu_system.get_session(user_id)
        assert session.current_menu == "compose"
        assert session.get_context("compose_type") == "bulletin"
        assert session.get_context("compose_step") == "subject"
    
    def test_channel_addition_start(self, menu_system):
        """Test starting channel addition"""
        user_id = "!12345678"
        
        # Navigate to channels and start addition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "channels")
        response = menu_system.process_command(user_id, "add")
        
        assert "Add New Channel" in response
        assert "Enter channel name" in response
        
        # Check session state
        session = menu_system.get_session(user_id)
        assert session.current_menu == "compose"
        assert session.get_context("compose_type") == "channel"
        assert session.get_context("compose_step") == "name"


class TestBBSComposition:
    """Test BBS composition workflows"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
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
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def menu_system(self, temp_db):
        """Create BBS menu system with temporary database"""
        return BBSMenuSystem()
    
    def test_mail_composition_cancel(self, menu_system):
        """Test cancelling mail composition"""
        user_id = "!12345678"
        
        # Start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        menu_system.process_command(user_id, "send")
        
        # Cancel
        response = menu_system.handle_compose_input(user_id, "cancel")
        
        assert "Composition cancelled" in response
        
        # Check session state
        session = menu_system.get_session(user_id)
        assert session.current_menu == "mail"  # Should return to mail menu
    
    def test_mail_composition_invalid_recipient(self, menu_system):
        """Test mail composition with invalid recipient"""
        user_id = "!12345678"
        
        # Start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        menu_system.process_command(user_id, "send")
        
        # Enter invalid recipient
        response = menu_system.handle_compose_input(user_id, "invalid")
        
        assert "Invalid node ID format" in response
        
        # Should still be in recipient step
        session = menu_system.get_session(user_id)
        assert session.get_context("compose_step") == "recipient"
    
    def test_mail_composition_valid_recipient(self, menu_system):
        """Test mail composition with valid recipient"""
        user_id = "!12345678"
        
        # Start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        menu_system.process_command(user_id, "send")
        
        # Enter valid recipient
        response = menu_system.handle_compose_input(user_id, "!87654321")
        
        assert "Enter subject" in response
        
        # Should move to subject step
        session = menu_system.get_session(user_id)
        assert session.get_context("compose_step") == "subject"
        assert session.get_context("compose_recipient") == "!87654321"
    
    def test_mail_composition_empty_subject(self, menu_system):
        """Test mail composition with empty subject"""
        user_id = "!12345678"
        
        # Start composition and enter recipient
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        menu_system.process_command(user_id, "send")
        menu_system.handle_compose_input(user_id, "!87654321")
        
        # Enter empty subject
        response = menu_system.handle_compose_input(user_id, "")
        
        assert "Subject cannot be empty" in response
        
        # Should still be in subject step
        session = menu_system.get_session(user_id)
        assert session.get_context("compose_step") == "subject"
    
    def test_mail_composition_complete(self, menu_system):
        """Test complete mail composition workflow"""
        user_id = "!12345678"
        user_name = "TestUser1"
        
        # Start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "mail")
        menu_system.process_command(user_id, "send")
        
        # Enter recipient
        menu_system.handle_compose_input(user_id, "!87654321", user_name)
        
        # Enter subject
        menu_system.handle_compose_input(user_id, "Test Subject", user_name)
        
        # Enter content
        menu_system.handle_compose_input(user_id, "This is test content", user_name)
        response = menu_system.handle_compose_input(user_id, ".", user_name)
        
        assert "Mail sent to !87654321" in response
        
        # Should return to mail menu
        session = menu_system.get_session(user_id)
        assert session.current_menu == "mail"
    
    def test_bulletin_composition_complete(self, menu_system):
        """Test complete bulletin composition workflow"""
        user_id = "!12345678"
        user_name = "TestUser1"
        
        # Start composition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "bulletins")
        menu_system.process_command(user_id, "post")
        
        # Enter subject
        menu_system.handle_compose_input(user_id, "Test Bulletin", user_name)
        
        # Enter content
        menu_system.handle_compose_input(user_id, "This is test bulletin content", user_name)
        response = menu_system.handle_compose_input(user_id, ".", user_name)
        
        assert "Bulletin posted to 'general' board" in response
        
        # Should return to bulletins menu
        session = menu_system.get_session(user_id)
        assert session.current_menu == "bulletins"
    
    def test_channel_addition_complete(self, menu_system):
        """Test complete channel addition workflow"""
        user_id = "!12345678"
        user_name = "TestUser1"
        
        # Start addition
        menu_system.process_command(user_id, "bbs")
        menu_system.process_command(user_id, "channels")
        menu_system.process_command(user_id, "add")
        
        # Enter name
        menu_system.handle_compose_input(user_id, "Test Repeater", user_name)
        
        # Enter frequency
        menu_system.handle_compose_input(user_id, "146.520", user_name)
        
        # Enter description
        response = menu_system.handle_compose_input(user_id, "Test repeater description", user_name)
        
        assert "Channel 'Test Repeater' added to directory" in response
        
        # Should return to channels menu
        session = menu_system.get_session(user_id)
        assert session.current_menu == "channels"