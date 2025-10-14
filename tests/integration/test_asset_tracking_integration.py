"""
Integration tests for Asset Tracking and Scheduling System

Tests the complete asset tracking and scheduling functionality including
service integration, command handling, and database operations.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.asset import (
    AssetTrackingService, SchedulingService, TaskManager,
    TaskType, ScheduleType, AssetStatus, CheckInAction
)
from src.services.asset.command_handlers import AssetCommandHandler
from tests.base import BaseTestCase


class TestAssetTrackingIntegration(BaseTestCase):
    """Integration tests for asset tracking and scheduling system"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create services
        self.asset_config = {
            'auto_checkout_hours': 24,
            'cleanup_days': 30,
            'enable_auto_checkout': False
        }
        
        self.scheduling_config = {
            'check_interval': 1,
            'max_concurrent_tasks': 5,
            'cleanup_days': 7
        }
        
        self.asset_service = AssetTrackingService(self.asset_config)
        self.scheduling_service = SchedulingService(self.scheduling_config)
        self.task_manager = TaskManager(self.scheduling_service, {})
        
        # Create command handler
        self.command_handler = AssetCommandHandler(self.asset_service)
        
        # Mock service integrations
        self.mock_message_router = Mock()
        self.mock_weather_service = Mock()
        self.mock_bbs_service = Mock()
        
        self.task_manager.set_service_integrations(
            message_router=self.mock_message_router,
            weather_service=self.mock_weather_service,
            bbs_service=self.mock_bbs_service
        )
    
    async def test_complete_checkin_workflow(self):
        """Test complete check-in workflow"""
        # Create test users
        await self.create_test_user("!user1", "Alice", permissions={'user': True})
        await self.create_test_user("!user2", "Bob", permissions={'user': True})
        await self.create_test_user("!admin", "Admin", permissions={'admin': True})
        
        # Start services
        await self.asset_service.start()
        
        # Test check-in process
        success, response = await self.command_handler.handle_command(
            "checkin", ["Ready for duty"], "!user1", False
        )
        self.assertTrue(success)
        self.assertIn("Alice checked in", response)
        self.assertIn("Ready for duty", response)
        
        # Test another user check-in
        success, response = await self.command_handler.handle_command(
            "checkin", [], "!user2", False
        )
        self.assertTrue(success)
        self.assertIn("Bob checked in", response)
        
        # Test checklist view
        success, response = await self.command_handler.handle_command(
            "checklist", [], "!user1", False
        )
        self.assertTrue(success)
        self.assertIn("CHECKLIST STATUS", response)
        self.assertIn("Checked In: 2", response)
        
        # Test status query
        success, response = await self.command_handler.handle_command(
            "status", ["Alice"], "!user2", False
        )
        self.assertTrue(success)
        self.assertIn("STATUS: Alice", response)
        self.assertIn("Status: Checked In", response)
        
        # Test check-out
        success, response = await self.command_handler.handle_command(
            "checkout", ["Going off duty"], "!user1", False
        )
        self.assertTrue(success)
        self.assertIn("Alice checked out", response)
        
        # Verify updated checklist
        success, response = await self.command_handler.handle_command(
            "checklist", [], "!user2", False
        )
        self.assertTrue(success)
        self.assertIn("Checked In: 1", response)
        self.assertIn("Checked Out: 1", response)
        
        await self.asset_service.stop()
    
    async def test_bulk_operations_workflow(self):
        """Test bulk operations workflow"""
        # Create test users
        await self.create_test_user("!user1", "Alice")
        await self.create_test_user("!user2", "Bob")
        await self.create_test_user("!admin", "Admin", permissions={'admin': True})
        
        # Start service
        await self.asset_service.start()
        
        # Check in users individually
        await self.command_handler.handle_command("checkin", [], "!user1", False)
        await self.command_handler.handle_command("checkin", [], "!user2", False)
        
        # Test bulk checkout (admin only)
        success, response = await self.command_handler.handle_command(
            "bulkops", ["checkout_all", "End of shift"], "!admin", True
        )
        self.assertTrue(success)
        self.assertIn("Bulk check-out completed for 2 users", response)
        
        # Verify all users are checked out
        summary = await self.asset_service.get_checklist_summary()
        self.assertEqual(summary.checked_out_users, 2)
        self.assertEqual(summary.checked_in_users, 0)
        
        # Test bulk check-in
        success, response = await self.command_handler.handle_command(
            "bulkops", ["checkin_all", "Start of shift"], "!admin", True
        )
        self.assertTrue(success)
        self.assertIn("Bulk check-in completed for 2 users", response)
        
        # Verify all users are checked in
        summary = await self.asset_service.get_checklist_summary()
        self.assertEqual(summary.checked_in_users, 2)
        
        await self.asset_service.stop()
    
    async def test_asset_statistics_workflow(self):
        """Test asset statistics workflow"""
        # Create test users
        await self.create_test_user("!user1", "Alice")
        await self.create_test_user("!user2", "Bob")
        
        # Start service
        await self.asset_service.start()
        
        # Create some activity
        for i in range(3):
            await self.command_handler.handle_command("checkin", [f"Activity {i}"], "!user1", False)
            await asyncio.sleep(0.1)  # Small delay
            await self.command_handler.handle_command("checkout", [], "!user1", False)
            await asyncio.sleep(0.1)
        
        # Test statistics
        success, response = await self.command_handler.handle_command(
            "assetstats", ["1"], "!user1", False
        )
        self.assertTrue(success)
        self.assertIn("ASSET STATISTICS", response)
        self.assertIn("Total Check-ins: 3", response)
        self.assertIn("Total Check-outs: 3", response)
        self.assertIn("Most Active: Alice", response)
        
        await self.asset_service.stop()
    
    async def test_scheduling_integration(self):
        """Test scheduling service integration"""
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create a broadcast task
        task_id = self.task_manager.create_task_from_template(
            template_name='daily_checkin',
            name='Test Daily Checkin',
            schedule_type=ScheduleType.INTERVAL,
            schedule_value='60',  # 1 minute for testing
            created_by='test_admin'
        )
        
        self.assertIsNotNone(task_id)
        
        # Verify task was created
        task = self.scheduling_service.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.name, 'Test Daily Checkin')
        self.assertEqual(task.task_type, TaskType.BROADCAST)
        
        # Test task templates
        templates = self.task_manager.get_task_templates()
        self.assertIn('daily_checkin', templates)
        self.assertIn('weather_broadcast', templates)
        self.assertIn('bbs_sync', templates)
        
        await self.scheduling_service.stop()
    
    async def test_weather_update_task_execution(self):
        """Test weather update task execution"""
        # Mock weather service response
        self.mock_weather_service.get_current_weather = AsyncMock(return_value={
            'current': {
                'temperature': 72,
                'conditions': 'Partly Cloudy',
                'humidity': 65,
                'wind_speed': 8
            },
            'forecast': [{
                'summary': 'Sunny',
                'high': 78,
                'low': 62
            }],
            'alerts': []
        })
        
        self.mock_message_router.send_broadcast = AsyncMock(return_value=True)
        
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create weather update task
        task_id = self.task_manager.create_weather_broadcast_task(
            name='Test Weather Update',
            cron_expression='0 */6 * * *',
            location='test_location',
            created_by='test_admin'
        )
        
        self.assertIsNotNone(task_id)
        
        # Execute task manually
        success = await self.task_manager.execute_task_now(task_id)
        self.assertTrue(success)
        
        # Verify weather service was called
        self.mock_weather_service.get_current_weather.assert_called_once_with('test_location')
        
        # Verify broadcast was sent
        self.mock_message_router.send_broadcast.assert_called_once()
        
        await self.scheduling_service.stop()
    
    async def test_bbs_sync_task_execution(self):
        """Test BBS sync task execution"""
        # Mock BBS service response
        self.mock_bbs_service.sync_with_peers = AsyncMock(return_value={
            'synced_peers': ['peer1', 'peer2'],
            'failed_peers': []
        })
        
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create BBS sync task
        task_id = self.task_manager.create_bbs_sync_task(
            name='Test BBS Sync',
            cron_expression='0 */4 * * *',
            peer_nodes=['peer1', 'peer2'],
            created_by='test_admin'
        )
        
        self.assertIsNotNone(task_id)
        
        # Execute task manually
        success = await self.task_manager.execute_task_now(task_id)
        self.assertTrue(success)
        
        # Verify BBS service was called
        self.mock_bbs_service.sync_with_peers.assert_called_once()
        
        await self.scheduling_service.stop()
    
    async def test_maintenance_task_execution(self):
        """Test maintenance task execution"""
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create maintenance task
        task_id = self.task_manager.create_maintenance_task(
            name='Test Cleanup',
            cron_expression='0 2 * * *',
            maintenance_type='cleanup',
            created_by='test_admin'
        )
        
        self.assertIsNotNone(task_id)
        
        # Execute task manually
        success = await self.task_manager.execute_task_now(task_id)
        self.assertTrue(success)
        
        # Verify task execution was recorded
        executions = self.scheduling_service.get_task_executions(task_id)
        self.assertGreater(len(executions), 0)
        
        await self.scheduling_service.stop()
    
    async def test_task_failure_handling(self):
        """Test task failure handling and recovery"""
        # Mock failing weather service
        self.mock_weather_service.get_current_weather = AsyncMock(
            side_effect=Exception("Weather service unavailable")
        )
        
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create weather task
        task_id = self.task_manager.create_weather_broadcast_task(
            name='Failing Weather Task',
            cron_expression='0 */6 * * *',
            created_by='test_admin'
        )
        
        # Execute task (should fail)
        success = await self.task_manager.execute_task_now(task_id)
        self.assertTrue(success)  # Task execution completes, but with failure
        
        # Check task status
        task = self.scheduling_service.get_task(task_id)
        self.assertEqual(task.failure_count, 1)
        self.assertIn("Weather service unavailable", task.last_error)
        
        # Check execution history
        executions = self.scheduling_service.get_task_executions(task_id)
        self.assertGreater(len(executions), 0)
        self.assertEqual(executions[0].status.value, 'failed')
        
        await self.scheduling_service.stop()
    
    async def test_command_permissions(self):
        """Test command permission handling"""
        # Create users with different permissions
        await self.create_test_user("!user", "User")
        await self.create_test_user("!admin", "Admin", permissions={'admin': True})
        
        # Test regular user cannot use bulk operations
        success, response = await self.command_handler.handle_command(
            "bulkops", ["checkout_all"], "!user", False
        )
        self.assertFalse(success)
        self.assertIn("Admin permissions required", response)
        
        # Test admin can use bulk operations
        success, response = await self.command_handler.handle_command(
            "bulkops", ["checkout_all"], "!admin", True
        )
        self.assertTrue(success)
        
        # Test regular user cannot clear checklist
        success, response = await self.command_handler.handle_command(
            "clearlist", ["confirm"], "!user", False
        )
        self.assertFalse(success)
        self.assertIn("Admin permissions required", response)
    
    async def test_task_summary_and_monitoring(self):
        """Test task summary and monitoring functionality"""
        # Start scheduling service
        await self.scheduling_service.start()
        
        # Create various tasks
        task1_id = self.task_manager.create_task_from_template(
            'daily_checkin', 'Daily Checkin', ScheduleType.CRON, '0 8 * * *'
        )
        
        task2_id = self.task_manager.create_weather_broadcast_task(
            'Weather Updates', '0 */6 * * *'
        )
        
        task3_id = self.task_manager.create_maintenance_task(
            'Nightly Cleanup', '0 2 * * *'
        )
        
        # Get task summary
        summary = self.task_manager.get_active_tasks_summary()
        
        self.assertEqual(summary['total_active'], 3)
        self.assertIn('broadcast', summary['by_type'])
        self.assertIn('weather_update', summary['by_type'])
        self.assertIn('maintenance', summary['by_type'])
        
        await self.scheduling_service.stop()
    
    async def test_service_health_monitoring(self):
        """Test service health monitoring"""
        # Test asset service health
        asset_health = self.asset_service.get_health_status()
        self.assertEqual(asset_health['status'], 'healthy')
        self.assertEqual(asset_health['service'], 'asset_tracking')
        
        # Test scheduling service health
        scheduling_health = self.scheduling_service.get_health_status()
        self.assertEqual(scheduling_health['status'], 'healthy')
        self.assertEqual(scheduling_health['service'], 'scheduling')
    
    async def test_data_persistence(self):
        """Test data persistence across service restarts"""
        # Start services
        await self.asset_service.start()
        await self.scheduling_service.start()
        
        # Create test data
        await self.create_test_user("!user1", "Alice")
        await self.command_handler.handle_command("checkin", ["Test"], "!user1", False)
        
        task_id = self.task_manager.create_task_from_template(
            'daily_checkin', 'Persistent Task', ScheduleType.INTERVAL, '3600'
        )
        
        # Stop services
        await self.asset_service.stop()
        await self.scheduling_service.stop()
        
        # Restart services
        new_asset_service = AssetTrackingService(self.asset_config)
        new_scheduling_service = SchedulingService(self.scheduling_config)
        
        await new_asset_service.start()
        await new_scheduling_service.start()
        
        # Verify data persisted
        asset_info = await new_asset_service.get_asset_status("!user1")
        self.assertEqual(asset_info.status, AssetStatus.CHECKED_IN)
        
        task = new_scheduling_service.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.name, 'Persistent Task')
        
        await new_asset_service.stop()
        await new_scheduling_service.stop()


if __name__ == '__main__':
    pytest.main([__file__])