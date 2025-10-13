"""
Unit tests for BBS channel service
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import initialize_database
from src.services.bbs.channel_service import ChannelService, get_channel_service
from src.services.bbs.models import ChannelType
from src.services.bbs.database import BBSDatabase


class TestChannelService:
    """Test channel service functionality"""
    
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
            import src.services.bbs.channel_service
            import src.services.bbs.database
            src.services.bbs.channel_service.channel_service = None
            src.services.bbs.database.bbs_db = None
            
            yield db_manager
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.fixture
    def channel_service(self, setup_fresh_db):
        """Create channel service with fresh database"""
        return ChannelService()
    
    def test_add_channel_success(self, channel_service):
        """Test successful channel addition"""
        success, message = channel_service.add_channel(
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
        
        assert success is True
        assert "added to directory successfully" in message
    
    def test_add_channel_invalid_name(self, channel_service):
        """Test adding channel with invalid name"""
        # Empty name
        success, message = channel_service.add_channel(
            name="",
            frequency="146.520",
            description="Valid description",
            added_by="!12345678"
        )
        
        assert success is False
        assert "Invalid channel name" in message
        
        # Too long name
        long_name = "A" * 51
        success, message = channel_service.add_channel(
            name=long_name,
            frequency="146.520",
            description="Valid description",
            added_by="!12345678"
        )
        
        assert success is False
        assert "Invalid channel name" in message
    
    def test_add_channel_invalid_frequency(self, channel_service):
        """Test adding channel with invalid frequency"""
        success, message = channel_service.add_channel(
            name="Test Channel",
            frequency="invalid_freq",
            description="Valid description",
            added_by="!12345678"
        )
        
        assert success is False
        assert "Invalid frequency format" in message
    
    def test_add_channel_empty_description(self, channel_service):
        """Test adding channel with empty description"""
        success, message = channel_service.add_channel(
            name="Test Channel",
            frequency="146.520",
            description="",
            added_by="!12345678"
        )
        
        assert success is False
        assert "Description cannot be empty" in message
    
    def test_add_channel_long_description(self, channel_service):
        """Test adding channel with too long description"""
        long_description = "A" * 501
        success, message = channel_service.add_channel(
            name="Test Channel",
            frequency="146.520",
            description=long_description,
            added_by="!12345678"
        )
        
        assert success is False
        assert "Description too long" in message
    
    def test_add_channel_duplicate_name(self, channel_service):
        """Test adding channel with duplicate name"""
        # Add first channel
        channel_service.add_channel(
            name="Test Repeater",
            frequency="146.520",
            description="First repeater",
            added_by="!12345678"
        )
        
        # Try to add duplicate
        success, message = channel_service.add_channel(
            name="Test Repeater",  # Same name
            frequency="146.940",
            description="Second repeater",
            added_by="!87654321"
        )
        
        assert success is False
        assert "already exists" in message
    
    def test_get_channel_success(self, channel_service):
        """Test successful channel retrieval"""
        # Add a channel
        channel_service.add_channel(
            name="Test Repeater",
            frequency="146.520",
            description="Test description",
            channel_type="repeater",
            location="Test City",
            added_by="!12345678"
        )
        
        # Get the channel (should be ID 1)
        success, formatted = channel_service.get_channel(1)
        
        assert success is True
        assert "Channel #1" in formatted
        assert "Test Repeater" in formatted
        assert "146.520" in formatted
        assert "Test description" in formatted
        assert "Test City" in formatted
    
    def test_get_channel_not_found(self, channel_service):
        """Test getting non-existent channel"""
        success, message = channel_service.get_channel(999)
        
        assert success is False
        assert "not found" in message
    
    def test_list_channels_empty(self, channel_service):
        """Test listing channels when directory is empty"""
        success, message = channel_service.list_channels()
        
        assert success is True
        assert "No channels found in directory" in message
    
    def test_list_channels_with_content(self, channel_service):
        """Test listing channels with content"""
        # Add some channels
        channel_service.add_channel("Repeater 1", "146.520", "First repeater", "repeater", "City A", added_by="!12345678")
        channel_service.add_channel("Simplex", "146.550", "Simplex frequency", "simplex", "City B", added_by="!87654321")
        
        success, formatted = channel_service.list_channels()
        
        assert success is True
        assert "Channel Directory" in formatted
        assert "Repeater 1" in formatted
        assert "Simplex" in formatted
        assert "Total: 2 channels" in formatted
    
    def test_search_channels_empty_term(self, channel_service):
        """Test searching with empty term"""
        success, message = channel_service.search_channels("")
        
        assert success is False
        assert "cannot be empty" in message
    
    def test_search_channels_no_results(self, channel_service):
        """Test searching with no results"""
        success, message = channel_service.search_channels("nonexistent")
        
        assert success is True
        assert "No channels found matching" in message
    
    def test_search_channels_with_results(self, channel_service):
        """Test searching with results"""
        # Add some channels
        channel_service.add_channel("Emergency Repeater", "146.520", "Emergency communications", "emergency", "Downtown", added_by="!12345678")
        channel_service.add_channel("Simplex", "146.550", "Simplex frequency", "simplex", "Uptown", added_by="!87654321")
        channel_service.add_channel("Digital", "70cm", "Digital mode", "digital", "Suburb", added_by="!12345678")
        
        # Search by name
        success, formatted = channel_service.search_channels("Emergency")
        
        assert success is True
        assert "Channel search results for 'Emergency'" in formatted
        assert "Emergency Repeater" in formatted
        assert "Simplex" not in formatted
        
        # Search by frequency
        success, formatted = channel_service.search_channels("146")
        
        assert success is True
        assert "Emergency Repeater" in formatted
        assert "Simplex" in formatted
        assert "Digital" not in formatted
    
    def test_update_channel_success(self, channel_service):
        """Test successful channel update"""
        # Add a channel
        channel_service.add_channel("Test Channel", "146.520", "Original description", added_by="!12345678")
        
        # Update the channel
        success, message = channel_service.update_channel(
            channel_id=1,
            user_id="!12345678",
            description="Updated description",
            location="New Location"
        )
        
        assert success is True
        assert "updated successfully" in message
    
    def test_update_channel_not_found(self, channel_service):
        """Test updating non-existent channel"""
        success, message = channel_service.update_channel(999, "!12345678", description="New desc")
        
        assert success is False
        assert "not found" in message
    
    def test_update_channel_not_owner(self, channel_service):
        """Test updating channel by non-owner"""
        # Add a channel
        channel_service.add_channel("Test Channel", "146.520", "Description", added_by="!12345678")
        
        # Try to update by different user
        success, message = channel_service.update_channel(1, "!87654321", description="New desc")
        
        assert success is False
        assert "only update channels you added" in message
    
    def test_delete_channel_success(self, channel_service):
        """Test successful channel deletion"""
        # Add a channel
        channel_service.add_channel("Test Channel", "146.520", "Description", added_by="!12345678")
        
        # Delete the channel
        success, message = channel_service.delete_channel(1, "!12345678")
        
        assert success is True
        assert "removed from directory" in message
    
    def test_delete_channel_not_found(self, channel_service):
        """Test deleting non-existent channel"""
        success, message = channel_service.delete_channel(999, "!12345678")
        
        assert success is False
        assert "not found" in message
    
    def test_delete_channel_not_owner(self, channel_service):
        """Test deleting channel by non-owner"""
        # Add a channel
        channel_service.add_channel("Test Channel", "146.520", "Description", added_by="!12345678")
        
        # Try to delete by different user
        success, message = channel_service.delete_channel(1, "!87654321")
        
        assert success is False
        assert "only delete channels you added" in message
    
    def test_verify_channel(self, channel_service):
        """Test channel verification"""
        # Add a channel
        channel_service.add_channel("Test Channel", "146.520", "Description", added_by="!12345678")
        
        # Verify the channel
        success, message = channel_service.verify_channel(1, "!87654321")
        
        assert success is True
        assert "marked as verified" in message
    
    def test_get_channels_by_type(self, channel_service):
        """Test getting channels by type"""
        # Add channels of different types
        channel_service.add_channel("Repeater 1", "146.520", "Repeater", "repeater", added_by="!12345678")
        channel_service.add_channel("Simplex 1", "146.550", "Simplex", "simplex", added_by="!87654321")
        channel_service.add_channel("Repeater 2", "146.940", "Another repeater", "repeater", added_by="!12345678")
        
        # Get repeater channels
        success, formatted = channel_service.get_channels_by_type("repeater")
        
        assert success is True
        assert "Repeater Channels" in formatted
        assert "Repeater 1" in formatted
        assert "Repeater 2" in formatted
        assert "Simplex 1" not in formatted
    
    def test_get_channels_by_type_invalid(self, channel_service):
        """Test getting channels by invalid type"""
        success, message = channel_service.get_channels_by_type("invalid_type")
        
        assert success is False
        assert "Invalid channel type" in message
    
    def test_get_channels_by_location(self, channel_service):
        """Test getting channels by location"""
        # Add channels in different locations
        channel_service.add_channel("Channel 1", "146.520", "Description", location="Downtown", added_by="!12345678")
        channel_service.add_channel("Channel 2", "146.550", "Description", location="Uptown", added_by="!87654321")
        channel_service.add_channel("Channel 3", "146.940", "Description", location="Downtown Area", added_by="!12345678")
        
        # Get downtown channels
        success, formatted = channel_service.get_channels_by_location("Downtown")
        
        assert success is True
        assert "Channels in 'Downtown'" in formatted
        assert "Channel 1" in formatted
        assert "Channel 3" in formatted  # Should match "Downtown Area"
        assert "Channel 2" not in formatted
    
    def test_get_channels_by_location_empty(self, channel_service):
        """Test getting channels by empty location"""
        success, message = channel_service.get_channels_by_location("")
        
        assert success is False
        assert "Location cannot be empty" in message
    
    def test_get_channel_stats(self, channel_service):
        """Test getting channel statistics"""
        # Initially no channels
        stats = channel_service.get_channel_stats()
        assert stats['total_channels'] == 0
        assert stats['active_channels'] == 0
        
        # Add some channels
        channel_service.add_channel("Repeater 1", "146.520", "Description", "repeater", added_by="!12345678")
        channel_service.add_channel("Simplex 1", "146.550", "Description", "simplex", added_by="!87654321")
        channel_service.add_channel("Repeater 2", "146.940", "Description", "repeater", added_by="!12345678")
        
        # Verify one channel
        channel_service.verify_channel(1, "!87654321")
        
        stats = channel_service.get_channel_stats()
        assert stats['total_channels'] == 3
        assert stats['active_channels'] == 3
        assert stats['verified_channels'] == 1
        assert stats['channels_by_type']['repeater'] == 2
        assert stats['channels_by_type']['simplex'] == 1
        assert stats['unique_contributors'] == 2
        assert stats['most_active_contributor']['user_id'] == "!12345678"
        assert stats['most_active_contributor']['channel_count'] == 2


def test_get_channel_service_singleton():
    """Test channel service singleton pattern"""
    service1 = get_channel_service()
    service2 = get_channel_service()
    
    assert service1 is service2
    assert isinstance(service1, ChannelService)