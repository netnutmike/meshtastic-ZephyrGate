"""
Unit tests for Asset Tracking Service

Tests check-in/check-out functionality, asset status tracking,
and accountability reporting.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from src.services.asset.asset_tracking_service import AssetTrackingService
from src.services.asset.models import (
    CheckInRecord, AssetInfo, AssetStatus, CheckInAction,
    ChecklistSummary, CheckInStats
)
from tests.base import DatabaseTestCase


@pytest.mark.asyncio
class TestAssetTrackingService(DatabaseTestCase):
    """Test cases for AssetTrackingService"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        
        # Create test database
        self.db_path = self.create_test_database()
        
        # Initialize database manager
        from src.core.database import initialize_database
        self.db = initialize_database(self.db_path)
        
        # Create service with test config
        self.config = {
            'auto_checkout_hours': 24,
            'cleanup_days': 30,
            'enable_auto_checkout': False
        }
        
        self.service = AssetTrackingService(self.config)
    
    async def create_test_user(self, node_id: str, short_name: str, long_name: str = None, 
                             permissions: Dict[str, bool] = None):
        """Create a test user"""
        user_data = {
            'node_id': node_id,
            'short_name': short_name,
            'long_name': long_name or short_name,
            'permissions': permissions or {},
            'subscriptions': {},
            'tags': []
        }
        self.db.upsert_user(user_data)
    
    async def test_service_initialization(self):
        """Test service initialization"""
        self.assertIsNotNone(self.service)
        self.assertEqual(self.service.auto_checkout_hours, 24)
        self.assertEqual(self.service.cleanup_days, 30)
        self.assertFalse(self.service.enable_auto_checkout)
    
    async def test_start_stop_service(self):
        """Test service start and stop"""
        await self.service.start()
        self.assertTrue(self.service.running)
        
        await self.service.stop()
        self.assertFalse(self.service.running)
    
    async def test_handle_checkin_command(self):
        """Test check-in command handling"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Test check-in without notes
        response = await self.service.handle_message("checkin", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("TestUser checked in", response)
        self.assertIn("Total checked in:", response)
        
        # Test check-in with notes
        response = await self.service.handle_message("checkin Ready for duty", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("Ready for duty", response)
    
    async def test_handle_checkout_command(self):
        """Test check-out command handling"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Check in first
        await self.service.handle_message("checkin", "!12345678")
        
        # Test check-out
        response = await self.service.handle_message("checkout Going off duty", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("TestUser checked out", response)
        self.assertIn("Going off duty", response)
    
    async def test_handle_checklist_command(self):
        """Test checklist view command"""
        # Create test users
        await self.create_test_user("!12345678", "User1")
        await self.create_test_user("!87654321", "User2")
        
        # Check in one user
        await self.service.handle_message("checkin", "!12345678")
        
        # Test checklist view
        response = await self.service.handle_message("checklist", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("CHECKLIST STATUS", response)
        self.assertIn("Total Users:", response)
        self.assertIn("Checked In:", response)
    
    async def test_handle_status_command(self):
        """Test status query command"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Check in user
        await self.service.handle_message("checkin Test notes", "!12345678")
        
        # Test own status
        response = await self.service.handle_message("status", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("STATUS: TestUser", response)
        self.assertIn("Status: Checked In", response)
        self.assertIn("Test notes", response)
    
    async def test_bulk_operations_admin_only(self):
        """Test bulk operations require admin permissions"""
        # Create regular user
        await self.create_test_user("!12345678", "RegularUser")
        
        # Test bulk operation without admin
        response = await self.service.handle_message("bulk checkout_all", "!12345678")
        self.assertIsNotNone(response)
        self.assertIn("Admin permissions required", response)
        
        # Create admin user
        await self.create_test_user("!87654321", "AdminUser", permissions={'admin': True})
        
        # Test bulk operation with admin
        response = await self.service.handle_message("bulk checkout_all Test bulk", "!87654321")
        self.assertIsNotNone(response)
        self.assertIn("Bulk check-out completed", response)
    
    async def test_get_asset_status(self):
        """Test asset status retrieval"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Initially no status
        asset_info = await self.service.get_asset_status("!12345678")
        self.assertIsNotNone(asset_info)
        self.assertEqual(asset_info.status, AssetStatus.UNKNOWN)
        
        # Check in user
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            notes="Test checkin",
            timestamp=datetime.now(timezone.utc)
        ))
        
        # Check status after checkin
        asset_info = await self.service.get_asset_status("!12345678")
        self.assertEqual(asset_info.status, AssetStatus.CHECKED_IN)
        self.assertEqual(asset_info.current_notes, "Test checkin")
        self.assertIsNotNone(asset_info.last_checkin)
    
    async def test_get_checklist_summary(self):
        """Test checklist summary generation"""
        # Create test users
        await self.create_test_user("!12345678", "User1")
        await self.create_test_user("!87654321", "User2")
        await self.create_test_user("!11111111", "User3")
        
        # Check in some users
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        ))
        
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!87654321",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        ))
        
        # Check out one user
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!87654321",
            action=CheckInAction.CHECKOUT,
            timestamp=datetime.now(timezone.utc)
        ))
        
        # Get summary
        summary = await self.service.get_checklist_summary()
        self.assertEqual(summary.total_users, 3)
        self.assertEqual(summary.checked_in_users, 1)
        self.assertEqual(summary.checked_out_users, 1)
        self.assertEqual(summary.unknown_status_users, 1)
    
    async def test_get_checkin_stats(self):
        """Test check-in statistics"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Create some check-in records
        now = datetime.now(timezone.utc)
        
        for i in range(3):
            await self.service._store_checkin_record(CheckInRecord(
                node_id="!12345678",
                action=CheckInAction.CHECKIN,
                timestamp=now - timedelta(hours=i)
            ))
        
        for i in range(2):
            await self.service._store_checkin_record(CheckInRecord(
                node_id="!12345678",
                action=CheckInAction.CHECKOUT,
                timestamp=now - timedelta(hours=i + 0.5)
            ))
        
        # Get stats
        stats = await self.service.get_checkin_stats(days=1)
        self.assertEqual(stats.total_checkins, 3)
        self.assertEqual(stats.total_checkouts, 2)
        self.assertEqual(stats.unique_users, 1)
        self.assertEqual(stats.most_active_user, "!12345678")
        self.assertEqual(stats.most_active_count, 5)
    
    async def test_bulk_checkout_all(self):
        """Test bulk checkout operation"""
        # Create test users
        await self.create_test_user("!12345678", "User1")
        await self.create_test_user("!87654321", "User2")
        
        # Check in users
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        ))
        
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!87654321",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        ))
        
        # Perform bulk checkout
        count = await self.service._bulk_checkout_all("Bulk checkout test")
        self.assertEqual(count, 2)
        
        # Verify users are checked out
        summary = await self.service.get_checklist_summary()
        self.assertEqual(summary.checked_out_users, 2)
        self.assertEqual(summary.checked_in_users, 0)
    
    async def test_bulk_checkin_all(self):
        """Test bulk checkin operation"""
        # Create test users
        await self.create_test_user("!12345678", "User1")
        await self.create_test_user("!87654321", "User2")
        
        # Perform bulk checkin
        count = await self.service._bulk_checkin_all("Bulk checkin test")
        self.assertEqual(count, 2)
        
        # Verify users are checked in
        summary = await self.service.get_checklist_summary()
        self.assertEqual(summary.checked_in_users, 2)
    
    async def test_clear_all_checkins(self):
        """Test clearing all check-in records"""
        # Create test user and records
        await self.create_test_user("!12345678", "TestUser")
        
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        ))
        
        await self.service._store_checkin_record(CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKOUT,
            timestamp=datetime.now(timezone.utc)
        ))
        
        # Clear all records
        count = await self.service._clear_all_checkins()
        self.assertGreaterEqual(count, 2)
        
        # Verify records are cleared
        records = self.db.execute_query("SELECT COUNT(*) as count FROM checklist")
        self.assertEqual(records[0]['count'], 0)
    
    async def test_find_user_by_name(self):
        """Test finding user by name"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser", long_name="Test User Long")
        
        # Find by short name
        node_id = await self.service._find_user_by_name("TestUser")
        self.assertEqual(node_id, "!12345678")
        
        # Find by long name
        node_id = await self.service._find_user_by_name("Test User Long")
        self.assertEqual(node_id, "!12345678")
        
        # Case insensitive
        node_id = await self.service._find_user_by_name("testuser")
        self.assertEqual(node_id, "!12345678")
        
        # Not found
        node_id = await self.service._find_user_by_name("NonExistent")
        self.assertIsNone(node_id)
    
    async def test_health_status(self):
        """Test service health status"""
        health = self.service.get_health_status()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertEqual(health['service'], 'asset_tracking')
        self.assertIn('running', health)
        self.assertIn('auto_checkout_enabled', health)
        self.assertIn('auto_checkout_hours', health)
        self.assertIn('cleanup_days', health)
    
    async def test_invalid_commands(self):
        """Test handling of invalid commands"""
        # Test unknown command
        response = await self.service.handle_message("unknown_command", "!12345678")
        self.assertIsNone(response)
        
        # Test empty message
        response = await self.service.handle_message("", "!12345678")
        self.assertIsNone(response)
    
    async def test_store_checkin_record(self):
        """Test storing check-in records"""
        # Create test user
        await self.create_test_user("!12345678", "TestUser")
        
        # Create and store record
        record = CheckInRecord(
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            notes="Test notes",
            timestamp=datetime.now(timezone.utc)
        )
        
        record_id = await self.service._store_checkin_record(record)
        self.assertIsNotNone(record_id)
        self.assertGreater(record_id, 0)
        
        # Verify record was stored
        records = self.db.execute_query(
            "SELECT * FROM checklist WHERE id = ?",
            (record_id,)
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['node_id'], "!12345678")
        self.assertEqual(records[0]['action'], "checkin")
        self.assertEqual(records[0]['notes'], "Test notes")


if __name__ == '__main__':
    pytest.main([__file__])