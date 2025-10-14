"""
Simple unit tests for Asset Tracking Service

Tests basic functionality without full database setup.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.services.asset.asset_tracking_service import AssetTrackingService
from src.services.asset.models import (
    CheckInRecord, AssetInfo, AssetStatus, CheckInAction,
    ChecklistSummary, CheckInStats
)


@pytest.mark.asyncio
class TestAssetTrackingServiceSimple:
    """Simple test cases for AssetTrackingService"""
    
    def setup_method(self):
        """Set up test environment"""
        # Mock database
        self.mock_db = Mock()
        self.mock_db.execute_query.return_value = []
        self.mock_db.execute_update.return_value = 1
        self.mock_db.get_user.return_value = None
        
        # Create service with test config
        self.config = {
            'auto_checkout_hours': 24,
            'cleanup_days': 30,
            'enable_auto_checkout': False
        }
        
        # Patch the database
        with patch('src.services.asset.asset_tracking_service.get_database', return_value=self.mock_db):
            self.service = AssetTrackingService(self.config)
    
    async def test_service_initialization(self):
        """Test service initialization"""
        assert self.service is not None
        assert self.service.auto_checkout_hours == 24
        assert self.service.cleanup_days == 30
        assert self.service.enable_auto_checkout is False
        assert self.service.running is False
    
    async def test_start_stop_service(self):
        """Test service start and stop"""
        await self.service.start()
        assert self.service.running is True
        
        await self.service.stop()
        assert self.service.running is False
    
    async def test_can_handle_messages(self):
        """Test message handling capability"""
        # Mock message object
        message = Mock()
        
        # Test checkin message
        message.content = "checkin Ready for duty"
        assert self.service.can_handle(message) is True
        
        # Test checkout message
        message.content = "checkout Going home"
        assert self.service.can_handle(message) is True
        
        # Test checklist message
        message.content = "checklist"
        assert self.service.can_handle(message) is True
        
        # Test status message
        message.content = "status"
        assert self.service.can_handle(message) is True
        
        # Test bulk message
        message.content = "bulk checkout_all"
        assert self.service.can_handle(message) is True
        
        # Test non-matching message
        message.content = "hello world"
        assert self.service.can_handle(message) is False
    
    async def test_handle_checkin_no_user(self):
        """Test check-in with no existing user"""
        # Mock no user found
        self.mock_db.get_user.return_value = None
        
        response = await self.service.handle_message("checkin", "!12345678")
        
        assert response is not None
        assert "checked in" in response.lower()
    
    async def test_handle_checkin_with_user(self):
        """Test check-in with existing user"""
        # Mock user found
        self.mock_db.get_user.return_value = {
            'node_id': '!12345678',
            'short_name': 'TestUser',
            'long_name': 'Test User',
            'permissions': {},
            'subscriptions': {},
            'tags': []
        }
        
        response = await self.service.handle_message("checkin Ready", "!12345678")
        
        assert response is not None
        assert "TestUser checked in" in response
        assert "Ready" in response
    
    async def test_handle_checkout(self):
        """Test check-out handling"""
        # Mock user found
        self.mock_db.get_user.return_value = {
            'node_id': '!12345678',
            'short_name': 'TestUser',
            'permissions': {},
            'subscriptions': {},
            'tags': []
        }
        
        response = await self.service.handle_message("checkout Done", "!12345678")
        
        assert response is not None
        assert "TestUser checked out" in response
        assert "Done" in response
    
    async def test_handle_checklist(self):
        """Test checklist handling"""
        # Mock checklist summary
        with patch.object(self.service, 'get_checklist_summary') as mock_summary:
            mock_summary.return_value = ChecklistSummary(
                total_users=5,
                checked_in_users=3,
                checked_out_users=2,
                unknown_status_users=0,
                assets=[]
            )
            
            response = await self.service.handle_message("checklist", "!12345678")
            
            assert response is not None
            assert "CHECKLIST STATUS" in response
            assert "Total Users: 5" in response
            assert "Checked In: 3" in response
            assert "Checked Out: 2" in response
    
    async def test_handle_status_own(self):
        """Test status query for own status"""
        # Mock asset status
        with patch.object(self.service, 'get_asset_status') as mock_status:
            mock_status.return_value = AssetInfo(
                node_id="!12345678",
                short_name="TestUser",
                status=AssetStatus.CHECKED_IN,
                last_checkin=datetime.now(timezone.utc),
                checkin_count=5
            )
            
            response = await self.service.handle_message("status", "!12345678")
            
            assert response is not None
            assert "STATUS: TestUser" in response
            assert "Status: Checked In" in response
    
    async def test_bulk_operations_no_admin(self):
        """Test bulk operations without admin permissions"""
        # Mock regular user
        self.mock_db.get_user.return_value = {
            'node_id': '!12345678',
            'short_name': 'RegularUser',
            'permissions': {}
        }
        
        response = await self.service.handle_message("bulk checkout_all", "!12345678")
        
        assert response is not None
        assert "Admin permissions required" in response
    
    async def test_bulk_operations_with_admin(self):
        """Test bulk operations with admin permissions"""
        # Mock admin user
        self.mock_db.get_user.return_value = {
            'node_id': '!admin',
            'short_name': 'AdminUser',
            'permissions': {'admin': True}
        }
        
        # Mock bulk operation
        with patch.object(self.service, '_bulk_checkout_all', return_value=3):
            response = await self.service.handle_message("bulk checkout_all Test", "!admin")
            
            assert response is not None
            assert "Bulk check-out completed for 3 users" in response
    
    async def test_store_checkin_record(self):
        """Test storing check-in records"""
        record = CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            notes="Test notes",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Mock database insert
        self.mock_db.execute_update.return_value = 1
        with patch.object(self.service.db, 'transaction') as mock_transaction:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.lastrowid = 123
            mock_conn.execute.return_value = mock_cursor
            mock_transaction.__enter__.return_value = mock_conn
            
            record_id = await self.service._store_checkin_record(record)
            
            assert record_id == 123
            mock_conn.execute.assert_called_once()
    
    async def test_get_asset_status_no_user(self):
        """Test getting asset status for non-existent user"""
        self.mock_db.get_user.return_value = None
        
        asset_info = await self.service.get_asset_status("!nonexistent")
        
        assert asset_info is None
    
    async def test_get_asset_status_no_records(self):
        """Test getting asset status with no check-in records"""
        # Mock user exists but no records
        self.mock_db.get_user.return_value = {
            'node_id': '!12345678',
            'short_name': 'TestUser',
            'long_name': 'Test User'
        }
        self.mock_db.execute_query.return_value = []
        
        asset_info = await self.service.get_asset_status("!12345678")
        
        assert asset_info is not None
        assert asset_info.node_id == "!12345678"
        assert asset_info.short_name == "TestUser"
        assert asset_info.status == AssetStatus.UNKNOWN
    
    async def test_get_asset_status_with_checkin(self):
        """Test getting asset status with check-in record"""
        # Mock user and records
        self.mock_db.get_user.return_value = {
            'node_id': '!12345678',
            'short_name': 'TestUser',
            'long_name': 'Test User'
        }
        
        now = datetime.now(timezone.utc)
        self.mock_db.execute_query.return_value = [
            {
                'action': 'checkin',
                'notes': 'Ready for duty',
                'timestamp': now.isoformat()
            }
        ]
        
        asset_info = await self.service.get_asset_status("!12345678")
        
        assert asset_info is not None
        assert asset_info.status == AssetStatus.CHECKED_IN
        assert asset_info.current_notes == 'Ready for duty'
        assert asset_info.last_checkin is not None
    
    async def test_get_checklist_summary(self):
        """Test getting checklist summary"""
        # Mock users
        self.mock_db.execute_query.return_value = [
            {'node_id': '!user1', 'short_name': 'User1', 'long_name': 'User One'},
            {'node_id': '!user2', 'short_name': 'User2', 'long_name': 'User Two'}
        ]
        
        # Mock asset status calls
        with patch.object(self.service, 'get_asset_status') as mock_status:
            mock_status.side_effect = [
                AssetInfo(node_id="!user1", short_name="User1", status=AssetStatus.CHECKED_IN),
                AssetInfo(node_id="!user2", short_name="User2", status=AssetStatus.CHECKED_OUT)
            ]
            
            summary = await self.service.get_checklist_summary()
            
            assert summary.total_users == 2
            assert summary.checked_in_users == 1
            assert summary.checked_out_users == 1
            assert summary.unknown_status_users == 0
            assert len(summary.assets) == 2
    
    async def test_get_checkin_stats(self):
        """Test getting check-in statistics"""
        now = datetime.now(timezone.utc)
        
        # Mock records
        self.mock_db.execute_query.return_value = [
            {
                'node_id': '!user1',
                'action': 'checkin',
                'notes': None,
                'timestamp': now.isoformat()
            },
            {
                'node_id': '!user1',
                'action': 'checkout',
                'notes': None,
                'timestamp': (now - timedelta(hours=1)).isoformat()
            },
            {
                'node_id': '!user2',
                'action': 'checkin',
                'notes': None,
                'timestamp': (now - timedelta(hours=2)).isoformat()
            }
        ]
        
        stats = await self.service.get_checkin_stats(days=1)
        
        assert stats.total_checkins == 2
        assert stats.total_checkouts == 1
        assert stats.unique_users == 2
        assert stats.most_active_user == "!user1"
        assert stats.most_active_count == 2
        assert len(stats.recent_activity) == 3
    
    async def test_health_status(self):
        """Test service health status"""
        health = self.service.get_health_status()
        
        assert health['status'] == 'healthy'
        assert health['service'] == 'asset_tracking'
        assert 'running' in health
        assert 'auto_checkout_enabled' in health
        assert 'auto_checkout_hours' in health
        assert 'cleanup_days' in health
    
    async def test_invalid_commands(self):
        """Test handling of invalid commands"""
        # Test unknown command
        response = await self.service.handle_message("unknown_command", "!12345678")
        assert response is None
        
        # Test empty message
        response = await self.service.handle_message("", "!12345678")
        assert response is None
    
    async def test_find_user_by_name(self):
        """Test finding user by name"""
        # Mock database query
        self.mock_db.execute_query.return_value = [{'node_id': '!12345678'}]
        
        node_id = await self.service._find_user_by_name("TestUser")
        assert node_id == "!12345678"
        
        # Test not found
        self.mock_db.execute_query.return_value = []
        node_id = await self.service._find_user_by_name("NonExistent")
        assert node_id is None


if __name__ == '__main__':
    pytest.main([__file__])