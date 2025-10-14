"""
Unit tests for Scheduling Service

Tests cron-like functionality, task scheduling, and automated execution.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.asset.scheduling_service import (
    SchedulingService, ScheduledTask, TaskExecution,
    TaskType, TaskStatus, ScheduleType
)
from tests.base import BaseTestCase


class TestSchedulingService(BaseTestCase):
    """Test cases for SchedulingService"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create service with test config
        self.config = {
            'check_interval': 1,  # 1 second for testing
            'max_concurrent_tasks': 5,
            'cleanup_days': 7
        }
        
        self.service = SchedulingService(self.config)
    
    async def test_service_initialization(self):
        """Test service initialization"""
        self.assertIsNotNone(self.service)
        self.assertEqual(self.service.check_interval, 1)
        self.assertEqual(self.service.max_concurrent_tasks, 5)
        self.assertEqual(self.service.cleanup_days, 7)
        self.assertFalse(self.service.running)
    
    async def test_start_stop_service(self):
        """Test service start and stop"""
        await self.service.start()
        self.assertTrue(self.service.running)
        self.assertIsNotNone(self.service.scheduler_task)
        
        await self.service.stop()
        self.assertFalse(self.service.running)
    
    async def test_create_one_time_task(self):
        """Test creating a one-time task"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        
        task_id = self.service.create_task(
            name="Test One-Time Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            scheduled_time=scheduled_time,
            parameters={'message': 'Test broadcast'},
            created_by="test_user"
        )
        
        self.assertIsNotNone(task_id)
        self.assertNotEqual(task_id, "")
        
        # Verify task was created
        task = self.service.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "Test One-Time Task")
        self.assertEqual(task.task_type, TaskType.BROADCAST)
        self.assertEqual(task.schedule_type, ScheduleType.ONE_TIME)
        self.assertEqual(task.status, TaskStatus.ACTIVE)
    
    async def test_create_interval_task(self):
        """Test creating an interval-based task"""
        task_id = self.service.create_task(
            name="Test Interval Task",
            task_type=TaskType.MAINTENANCE,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=300,  # 5 minutes
            parameters={'type': 'cleanup'},
            created_by="test_user"
        )
        
        self.assertIsNotNone(task_id)
        
        # Verify task was created
        task = self.service.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.interval_seconds, 300)
        self.assertIsNotNone(task.next_run)
    
    async def test_create_cron_task(self):
        """Test creating a cron-based task"""
        task_id = self.service.create_task(
            name="Test Cron Task",
            task_type=TaskType.WEATHER_UPDATE,
            schedule_type=ScheduleType.CRON,
            cron_expression="0 */6 * * *",  # Every 6 hours
            parameters={'location': 'test_location'},
            created_by="test_user"
        )
        
        self.assertIsNotNone(task_id)
        
        # Verify task was created
        task = self.service.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.cron_expression, "0 */6 * * *")
        self.assertIsNotNone(task.next_run)
    
    async def test_get_tasks(self):
        """Test retrieving tasks"""
        # Create test tasks
        task_id1 = self.service.create_task(
            name="Active Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            created_by="test_user"
        )
        
        task_id2 = self.service.create_task(
            name="Inactive Task",
            task_type=TaskType.MAINTENANCE,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            created_by="test_user"
        )
        
        # Deactivate one task
        self.service.update_task(task_id2, status=TaskStatus.INACTIVE)
        
        # Test get all tasks
        all_tasks = self.service.get_tasks()
        self.assertGreaterEqual(len(all_tasks), 2)
        
        # Test get active tasks only
        active_tasks = self.service.get_tasks(active_only=True)
        active_task_ids = [task.id for task in active_tasks]
        self.assertIn(task_id1, active_task_ids)
        self.assertNotIn(task_id2, active_task_ids)
    
    async def test_update_task(self):
        """Test updating task properties"""
        # Create test task
        task_id = self.service.create_task(
            name="Original Name",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            created_by="test_user"
        )
        
        # Update task
        success = self.service.update_task(
            task_id,
            name="Updated Name",
            interval_seconds=1800,
            parameters={'new_param': 'value'}
        )
        
        self.assertTrue(success)
        
        # Verify updates
        task = self.service.get_task(task_id)
        self.assertEqual(task.name, "Updated Name")
        self.assertEqual(task.interval_seconds, 1800)
        self.assertEqual(task.parameters['new_param'], 'value')
    
    async def test_delete_task(self):
        """Test deleting a task"""
        # Create test task
        task_id = self.service.create_task(
            name="Task to Delete",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            created_by="test_user"
        )
        
        # Verify task exists
        task = self.service.get_task(task_id)
        self.assertIsNotNone(task)
        
        # Delete task
        success = self.service.delete_task(task_id)
        self.assertTrue(success)
        
        # Verify task is gone
        task = self.service.get_task(task_id)
        self.assertIsNone(task)
    
    async def test_calculate_next_run_interval(self):
        """Test calculating next run time for interval tasks"""
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600
        )
        
        next_run = self.service._calculate_next_run(task)
        self.assertIsNotNone(next_run)
        
        # Should be approximately 1 hour from now
        now = datetime.now(timezone.utc)
        expected = now + timedelta(seconds=3600)
        self.assertAlmostEqual(
            next_run.timestamp(),
            expected.timestamp(),
            delta=5  # 5 second tolerance
        )
    
    async def test_calculate_next_run_cron(self):
        """Test calculating next run time for cron tasks"""
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.CRON,
            cron_expression="0 0 * * *"  # Daily at midnight
        )
        
        next_run = self.service._calculate_next_run(task)
        self.assertIsNotNone(next_run)
        
        # Should be next midnight
        self.assertEqual(next_run.hour, 0)
        self.assertEqual(next_run.minute, 0)
        self.assertEqual(next_run.second, 0)
    
    async def test_calculate_next_run_one_time(self):
        """Test calculating next run time for one-time tasks"""
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            scheduled_time=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        next_run = self.service._calculate_next_run(task)
        self.assertIsNone(next_run)  # One-time tasks don't repeat
    
    @patch('src.services.asset.scheduling_service.SchedulingService._handle_broadcast_task')
    async def test_execute_task_success(self, mock_handler):
        """Test successful task execution"""
        mock_handler.return_value = "Task completed successfully"
        
        # Create and execute task
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            parameters={'message': 'Test message'}
        )
        
        await self.service._execute_task(task)
        
        # Verify handler was called
        mock_handler.assert_called_once_with(task)
        
        # Verify task status updated
        self.assertEqual(task.status, TaskStatus.ACTIVE)
        self.assertEqual(task.run_count, 1)
        self.assertEqual(task.failure_count, 0)
        self.assertIsNone(task.last_error)
    
    @patch('src.services.asset.scheduling_service.SchedulingService._handle_broadcast_task')
    async def test_execute_task_failure(self, mock_handler):
        """Test task execution failure"""
        mock_handler.side_effect = Exception("Task failed")
        
        # Create and execute task
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            parameters={'message': 'Test message'}
        )
        
        await self.service._execute_task(task)
        
        # Verify task status updated for failure
        self.assertEqual(task.status, TaskStatus.ACTIVE)
        self.assertEqual(task.run_count, 0)
        self.assertEqual(task.failure_count, 1)
        self.assertEqual(task.last_error, "Task failed")
    
    @patch('src.services.asset.scheduling_service.SchedulingService._handle_broadcast_task')
    async def test_execute_task_timeout(self, mock_handler):
        """Test task execution timeout"""
        # Mock handler that takes too long
        async def slow_handler(task):
            await asyncio.sleep(10)
            return "Should not complete"
        
        mock_handler.side_effect = slow_handler
        
        # Create task with short timeout
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            timeout_seconds=1,
            parameters={'message': 'Test message'}
        )
        
        await self.service._execute_task(task)
        
        # Verify timeout handling
        self.assertEqual(task.status, TaskStatus.ACTIVE)
        self.assertEqual(task.failure_count, 1)
        self.assertIn("timed out", task.last_error)
    
    async def test_task_failure_threshold(self):
        """Test task deactivation after too many failures"""
        # Create task with low failure threshold
        task_id = self.service.create_task(
            name="Failing Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=1,
            max_failures=2,
            created_by="test_user"
        )
        
        task = self.service.get_task(task_id)
        
        # Simulate failures
        task.failure_count = 2
        task.next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.service._save_task(task)
        
        # Check scheduled tasks (should deactivate failing task)
        await self.service._check_scheduled_tasks()
        
        # Verify task was deactivated
        updated_task = self.service.get_task(task_id)
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
    
    async def test_get_task_executions(self):
        """Test retrieving task execution history"""
        # Create test task
        task_id = self.service.create_task(
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.ONE_TIME,
            created_by="test_user"
        )
        
        # Create test execution
        execution = TaskExecution(
            id="exec_id",
            task_id=task_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            status=TaskStatus.COMPLETED,
            result="Success",
            duration_seconds=1.5
        )
        
        self.service._save_execution(execution)
        
        # Retrieve executions
        executions = self.service.get_task_executions(task_id)
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].id, "exec_id")
        self.assertEqual(executions[0].status, TaskStatus.COMPLETED)
    
    async def test_cleanup_old_executions(self):
        """Test cleanup of old task executions"""
        # Create old execution
        old_execution = TaskExecution(
            id="old_exec",
            task_id="test_task",
            started_at=datetime.now(timezone.utc) - timedelta(days=10),
            status=TaskStatus.COMPLETED
        )
        
        self.service._save_execution(old_execution)
        
        # Create recent execution
        recent_execution = TaskExecution(
            id="recent_exec",
            task_id="test_task",
            started_at=datetime.now(timezone.utc),
            status=TaskStatus.COMPLETED
        )
        
        self.service._save_execution(recent_execution)
        
        # Run cleanup (with cleanup_days = 7)
        await self.service._cleanup_old_executions()
        
        # Verify old execution was removed
        executions = self.service.get_task_executions("test_task")
        execution_ids = [e.id for e in executions]
        self.assertNotIn("old_exec", execution_ids)
        self.assertIn("recent_exec", execution_ids)
    
    async def test_handle_schedule_command(self):
        """Test schedule command handling"""
        # Create admin user
        await self.create_test_user("!admin", "Admin", permissions={'admin': True})
        
        # Test schedule command
        response = await self.service.handle_message("schedule", "!admin")
        self.assertIsNotNone(response)
        self.assertIn("Schedule commands", response)
    
    async def test_handle_tasks_command(self):
        """Test tasks command handling"""
        # Create admin user
        await self.create_test_user("!admin", "Admin", permissions={'admin': True})
        
        # Create test task
        self.service.create_task(
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            created_by="!admin"
        )
        
        # Test tasks list command
        response = await self.service.handle_message("tasks list", "!admin")
        self.assertIsNotNone(response)
        self.assertIn("ACTIVE TASKS", response)
        self.assertIn("Test Task", response)
    
    async def test_non_admin_command_access(self):
        """Test that non-admin users cannot access scheduling commands"""
        # Create regular user
        await self.create_test_user("!user", "User")
        
        # Test schedule command
        response = await self.service.handle_message("schedule", "!user")
        self.assertIsNone(response)
        
        # Test tasks command
        response = await self.service.handle_message("tasks", "!user")
        self.assertIsNone(response)
    
    async def test_health_status(self):
        """Test service health status"""
        health = self.service.get_health_status()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertEqual(health['service'], 'scheduling')
        self.assertIn('running', health)
        self.assertIn('active_tasks', health)
        self.assertIn('running_tasks', health)
    
    async def test_task_serialization(self):
        """Test task serialization to/from dictionary"""
        # Create test task
        task = ScheduledTask(
            id="test_id",
            name="Test Task",
            task_type=TaskType.BROADCAST,
            schedule_type=ScheduleType.CRON,
            cron_expression="0 0 * * *",
            parameters={'message': 'test'},
            created_by="test_user"
        )
        
        # Serialize to dict
        task_dict = task.to_dict()
        self.assertIsInstance(task_dict, dict)
        self.assertEqual(task_dict['name'], "Test Task")
        self.assertEqual(task_dict['task_type'], "broadcast")
        
        # Deserialize from dict
        restored_task = ScheduledTask.from_dict(task_dict)
        self.assertEqual(restored_task.name, task.name)
        self.assertEqual(restored_task.task_type, task.task_type)
        self.assertEqual(restored_task.cron_expression, task.cron_expression)


if __name__ == '__main__':
    pytest.main([__file__])