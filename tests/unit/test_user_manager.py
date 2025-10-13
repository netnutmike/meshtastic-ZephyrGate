"""
Unit tests for User Manager
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from src.services.web.user_manager import (
    UserManager, UserProfile, PermissionLevel, SubscriptionType, UserActivity
)
from src.models.message import Message, MessageType


class TestUserManager:
    """Test user manager functionality"""
    
    @pytest.fixture
    def user_manager(self):
        return UserManager()
    
    def test_init(self, user_manager):
        """Test user manager initialization"""
        assert user_manager.users == {}
        assert user_manager.activity_history_limit == 1000
        assert PermissionLevel.READ in user_manager.default_permissions
        assert SubscriptionType.EMERGENCY_ALERTS in user_manager.default_subscriptions
    
    def test_create_user(self, user_manager):
        """Test user creation"""
        user = user_manager.create_user("!12345678", "TestUser", "Test User Full Name")
        
        assert user.node_id == "!12345678"
        assert user.short_name == "TestUser"
        assert user.long_name == "Test User Full Name"
        assert PermissionLevel.READ in user.permissions
        assert SubscriptionType.EMERGENCY_ALERTS in user.subscriptions
        assert user.is_active is True
        assert user.message_count == 0
        
        # Check user is stored
        assert "!12345678" in user_manager.users
        assert user_manager.users["!12345678"] == user
    
    def test_create_duplicate_user(self, user_manager):
        """Test creating duplicate user returns existing user"""
        user1 = user_manager.create_user("!12345678", "TestUser1")
        user2 = user_manager.create_user("!12345678", "TestUser2")
        
        assert user1 == user2
        assert user1.short_name == "TestUser1"  # Original name preserved
    
    def test_get_user(self, user_manager):
        """Test getting user"""
        user_manager.create_user("!12345678", "TestUser")
        
        user = user_manager.get_user("!12345678")
        assert user is not None
        assert user.node_id == "!12345678"
        
        # Test non-existent user
        user = user_manager.get_user("!nonexistent")
        assert user is None
    
    def test_update_user(self, user_manager):
        """Test updating user profile"""
        user_manager.create_user("!12345678", "TestUser")
        
        # Update user
        success = user_manager.update_user(
            "!12345678",
            email="test@example.com",
            phone="123-456-7890",
            notes="Test notes"
        )
        
        assert success is True
        
        user = user_manager.get_user("!12345678")
        assert user.email == "test@example.com"
        assert user.phone == "123-456-7890"
        assert user.notes == "Test notes"
        
        # Test updating non-existent user
        success = user_manager.update_user("!nonexistent", email="test@example.com")
        assert success is False
    
    def test_delete_user(self, user_manager):
        """Test deleting user"""
        user_manager.create_user("!12345678", "TestUser")
        
        # Verify user exists
        assert user_manager.get_user("!12345678") is not None
        
        # Delete user
        success = user_manager.delete_user("!12345678")
        assert success is True
        
        # Verify user is gone
        assert user_manager.get_user("!12345678") is None
        
        # Test deleting non-existent user
        success = user_manager.delete_user("!nonexistent")
        assert success is False
    
    def test_update_permissions(self, user_manager):
        """Test updating user permissions"""
        user_manager.create_user("!12345678", "TestUser")
        
        new_permissions = {PermissionLevel.READ, PermissionLevel.WRITE, PermissionLevel.ADMIN}
        success = user_manager.update_permissions("!12345678", new_permissions)
        
        assert success is True
        
        user = user_manager.get_user("!12345678")
        assert user.permissions == new_permissions
        
        # Test updating non-existent user
        success = user_manager.update_permissions("!nonexistent", new_permissions)
        assert success is False
    
    def test_update_subscriptions(self, user_manager):
        """Test updating user subscriptions"""
        user_manager.create_user("!12345678", "TestUser")
        
        new_subscriptions = {SubscriptionType.WEATHER_ALERTS, SubscriptionType.BBS_NOTIFICATIONS}
        success = user_manager.update_subscriptions("!12345678", new_subscriptions)
        
        assert success is True
        
        user = user_manager.get_user("!12345678")
        assert user.subscriptions == new_subscriptions
        
        # Test updating non-existent user
        success = user_manager.update_subscriptions("!nonexistent", new_subscriptions)
        assert success is False
    
    def test_add_remove_tag(self, user_manager):
        """Test adding and removing tags"""
        user_manager.create_user("!12345678", "TestUser")
        
        # Add tag
        success = user_manager.add_tag("!12345678", "emergency_contact")
        assert success is True
        
        user = user_manager.get_user("!12345678")
        assert "emergency_contact" in user.tags
        
        # Add duplicate tag (should not duplicate)
        user_manager.add_tag("!12345678", "emergency_contact")
        assert len([t for t in user.tags if t == "emergency_contact"]) == 1
        
        # Remove tag
        success = user_manager.remove_tag("!12345678", "emergency_contact")
        assert success is True
        assert "emergency_contact" not in user.tags
        
        # Remove non-existent tag
        success = user_manager.remove_tag("!12345678", "nonexistent_tag")
        assert success is True  # Should not fail
        
        # Test with non-existent user
        success = user_manager.add_tag("!nonexistent", "tag")
        assert success is False
    
    def test_get_users_by_tag(self, user_manager):
        """Test getting users by tag"""
        user1 = user_manager.create_user("!11111111", "User1")
        user2 = user_manager.create_user("!22222222", "User2")
        user3 = user_manager.create_user("!33333333", "User3")
        
        # Add tags
        user_manager.add_tag("!11111111", "admin")
        user_manager.add_tag("!22222222", "admin")
        user_manager.add_tag("!33333333", "user")
        
        # Get users by tag
        admin_users = user_manager.get_users_by_tag("admin")
        assert len(admin_users) == 2
        assert all(user.node_id in ["!11111111", "!22222222"] for user in admin_users)
        
        user_users = user_manager.get_users_by_tag("user")
        assert len(user_users) == 1
        assert user_users[0].node_id == "!33333333"
        
        # Non-existent tag
        empty_users = user_manager.get_users_by_tag("nonexistent")
        assert len(empty_users) == 0
    
    def test_get_users_by_permission(self, user_manager):
        """Test getting users by permission"""
        user_manager.create_user("!11111111", "User1")
        user_manager.create_user("!22222222", "User2")
        
        # Update permissions
        user_manager.update_permissions("!11111111", {PermissionLevel.READ, PermissionLevel.ADMIN})
        user_manager.update_permissions("!22222222", {PermissionLevel.READ, PermissionLevel.WRITE})
        
        # Get users by permission
        admin_users = user_manager.get_users_by_permission(PermissionLevel.ADMIN)
        assert len(admin_users) == 1
        assert admin_users[0].node_id == "!11111111"
        
        read_users = user_manager.get_users_by_permission(PermissionLevel.READ)
        assert len(read_users) == 2
    
    def test_get_users_by_subscription(self, user_manager):
        """Test getting users by subscription"""
        user_manager.create_user("!11111111", "User1")
        user_manager.create_user("!22222222", "User2")
        
        # Update subscriptions
        user_manager.update_subscriptions("!11111111", {SubscriptionType.WEATHER_ALERTS})
        user_manager.update_subscriptions("!22222222", {SubscriptionType.EMERGENCY_ALERTS})
        
        # Get users by subscription
        weather_users = user_manager.get_users_by_subscription(SubscriptionType.WEATHER_ALERTS)
        assert len(weather_users) == 1
        assert weather_users[0].node_id == "!11111111"
        
        emergency_users = user_manager.get_users_by_subscription(SubscriptionType.EMERGENCY_ALERTS)
        assert len(emergency_users) == 1
        assert emergency_users[0].node_id == "!22222222"
    
    def test_update_user_activity(self, user_manager):
        """Test updating user activity from messages"""
        # Create test message
        message = Message(
            id="test_msg",
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Test message",
            timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            interface_id="serial0"
        )
        
        # Update activity (should auto-create user)
        user_manager.update_user_activity("!12345678", message)
        
        # Check user was created
        user = user_manager.get_user("!12345678")
        assert user is not None
        assert user.message_count == 1
        assert user.last_seen == message.timestamp
        assert user.last_message_time == message.timestamp
        assert 0 in user.favorite_channels
        
        # Update activity again
        message2 = Message(
            id="test_msg2",
            sender_id="!12345678",
            recipient_id=None,
            channel=1,
            content="Test message 2",
            timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            interface_id="serial0"
        )
        
        user_manager.update_user_activity("!12345678", message2)
        
        user = user_manager.get_user("!12345678")
        assert user.message_count == 2
        assert 1 in user.favorite_channels
    
    def test_search_users(self, user_manager):
        """Test searching users"""
        user_manager.create_user("!11111111", "Alice", "Alice Smith")
        user_manager.create_user("!22222222", "Bob", "Bob Johnson")
        user_manager.create_user("!33333333", "Charlie", "Charlie Brown")
        
        # Update one user with email
        user_manager.update_user("!11111111", email="alice@example.com")
        
        # Search by short name
        results = user_manager.search_users("alice")
        assert len(results) == 1
        assert results[0].node_id == "!11111111"
        
        # Search by long name
        results = user_manager.search_users("johnson")
        assert len(results) == 1
        assert results[0].node_id == "!22222222"
        
        # Search by email
        results = user_manager.search_users("alice@example.com")
        assert len(results) == 1
        assert results[0].node_id == "!11111111"
        
        # Search by node ID
        results = user_manager.search_users("!33333333")
        assert len(results) == 1
        assert results[0].node_id == "!33333333"
        
        # Search with no results
        results = user_manager.search_users("nonexistent")
        assert len(results) == 0
    
    def test_get_user_stats(self, user_manager):
        """Test getting user statistics"""
        # Create users
        user_manager.create_user("!11111111", "User1")
        user_manager.create_user("!22222222", "User2")
        user_manager.create_user("!33333333", "User3")
        
        # Deactivate one user
        user_manager.update_user("!33333333", is_active=False)
        
        # Add some message activity
        message = Message(
            id="msg1", sender_id="!11111111", recipient_id=None,
            channel=0, content="Test", timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT, interface_id="serial0"
        )
        user_manager.update_user_activity("!11111111", message)
        user_manager.update_user_activity("!11111111", message)  # 2 messages
        
        message2 = Message(
            id="msg2", sender_id="!22222222", recipient_id=None,
            channel=0, content="Test", timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT, interface_id="serial0"
        )
        user_manager.update_user_activity("!22222222", message2)  # 1 message
        
        stats = user_manager.get_user_stats()
        
        assert stats.total_users == 3
        assert stats.active_users == 2
        assert stats.total_messages == 3
        assert len(stats.top_users) >= 2
        
        # Check top user
        top_user = stats.top_users[0]
        assert top_user["node_id"] == "!11111111"
        assert top_user["message_count"] == 2
    
    def test_export_import_users(self, user_manager):
        """Test exporting and importing users"""
        # Create test users
        user1 = user_manager.create_user("!11111111", "User1", "First User")
        user2 = user_manager.create_user("!22222222", "User2", "Second User")
        
        # Add some data
        user_manager.update_user("!11111111", email="user1@example.com")
        user_manager.add_tag("!11111111", "admin")
        user_manager.update_permissions("!11111111", {PermissionLevel.READ, PermissionLevel.ADMIN})
        
        # Export users
        export_data = user_manager.export_users()
        
        assert "users" in export_data
        assert "export_timestamp" in export_data
        assert export_data["total_users"] == 2
        assert "!11111111" in export_data["users"]
        assert "!22222222" in export_data["users"]
        
        # Check exported user data
        exported_user1 = export_data["users"]["!11111111"]
        assert exported_user1["email"] == "user1@example.com"
        assert "admin" in exported_user1["tags"]
        assert "admin" in exported_user1["permissions"]
        
        # Clear users and import
        user_manager.users.clear()
        assert len(user_manager.users) == 0
        
        success = user_manager.import_users(export_data)
        assert success is True
        assert len(user_manager.users) == 2
        
        # Verify imported data
        imported_user1 = user_manager.get_user("!11111111")
        assert imported_user1 is not None
        assert imported_user1.email == "user1@example.com"
        assert "admin" in imported_user1.tags
        assert PermissionLevel.ADMIN in imported_user1.permissions


if __name__ == "__main__":
    pytest.main([__file__])