"""
Unit Tests for Plugin Scheduler

Tests basic functionality of the PluginScheduler class.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from src.core.plugin_scheduler import PluginScheduler, ScheduledTask, CronParser


class TestPluginScheduler:
    """Unit tests for PluginScheduler"""
    
    @pytest.mark.asyncio
    async def test_register_interval_task(self):
        """Test registering an interval-based task"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        task = scheduler.register_task("test_task", test_handler, interval=60)
        
        assert task.name == "test_task"
        assert task.plugin == "test_plugin"
        assert task.interval == 60
        assert task.cron is None
        assert task.enabled == True
        assert "test_task" in scheduler.tasks
    
    @pytest.mark.asyncio
    async def test_register_cron_task(self):
        """Test registering a cron-based task"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        task = scheduler.register_task("test_task", test_handler, cron="0 * * * *")
        
        assert task.name == "test_task"
        assert task.plugin == "test_plugin"
        assert task.interval is None
        assert task.cron == "0 * * * *"
        assert task.enabled == True
    
    @pytest.mark.asyncio
    async def test_register_task_requires_interval_or_cron(self):
        """Test that registering a task requires either interval or cron"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        with pytest.raises(ValueError, match="Either interval or cron must be provided"):
            scheduler.register_task("test_task", test_handler)
    
    @pytest.mark.asyncio
    async def test_register_task_cannot_have_both(self):
        """Test that a task cannot have both interval and cron"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        with pytest.raises(ValueError, match="Cannot specify both interval and cron"):
            scheduler.register_task("test_task", test_handler, interval=60, cron="0 * * * *")
    
    @pytest.mark.asyncio
    async def test_invalid_cron_expression(self):
        """Test that invalid cron expressions are rejected"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        with pytest.raises(ValueError, match="Invalid cron expression"):
            scheduler.register_task("test_task", test_handler, cron="invalid")
    
    @pytest.mark.asyncio
    async def test_task_executes(self):
        """Test that a task executes"""
        scheduler = PluginScheduler("test_plugin")
        execution_count = [0]
        
        async def test_handler():
            execution_count[0] += 1
        
        try:
            scheduler.register_task("test_task", test_handler, interval=1)
            await scheduler.start_task("test_task")
            
            # Wait for execution
            await asyncio.sleep(1.5)
            
            await scheduler.stop_task("test_task")
            
            assert execution_count[0] >= 1
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    async def test_task_stops(self):
        """Test that a task stops when requested"""
        scheduler = PluginScheduler("test_plugin")
        execution_count = [0]
        
        async def test_handler():
            execution_count[0] += 1
        
        try:
            scheduler.register_task("test_task", test_handler, interval=1)
            await scheduler.start_task("test_task")
            
            # Wait for execution
            await asyncio.sleep(0.5)
            count_before_stop = execution_count[0]
            
            # Stop the task
            await scheduler.stop_task("test_task")
            
            # Wait and verify no more executions
            await asyncio.sleep(2)
            
            assert execution_count[0] == count_before_stop
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test getting task status"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        try:
            scheduler.register_task("test_task", test_handler, interval=60)
            
            status = scheduler.get_task_status("test_task")
            
            assert status['name'] == "test_task"
            assert status['plugin'] == "test_plugin"
            assert status['interval'] == 60
            assert status['enabled'] == True
            assert status['run_count'] == 0
            assert status['error_count'] == 0
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    async def test_get_all_task_status(self):
        """Test getting status of all tasks"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        try:
            scheduler.register_task("task1", test_handler, interval=60)
            scheduler.register_task("task2", test_handler, interval=120)
            
            all_status = scheduler.get_all_task_status()
            
            assert len(all_status) == 2
            assert any(s['name'] == "task1" for s in all_status)
            assert any(s['name'] == "task2" for s in all_status)
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    async def test_unregister_task(self):
        """Test unregistering a task"""
        scheduler = PluginScheduler("test_plugin")
        
        async def test_handler():
            pass
        
        try:
            scheduler.register_task("test_task", test_handler, interval=60)
            assert "test_task" in scheduler.tasks
            
            scheduler.unregister_task("test_task")
            assert "test_task" not in scheduler.tasks
        finally:
            await scheduler.stop_all()


class TestCronParser:
    """Unit tests for CronParser"""
    
    def test_parse_valid_cron(self):
        """Test parsing valid cron expressions"""
        parsed = CronParser.parse("0 * * * *")
        
        assert parsed['minute'] == '0'
        assert parsed['hour'] == '*'
        assert parsed['day'] == '*'
        assert parsed['month'] == '*'
        assert parsed['weekday'] == '*'
    
    def test_parse_invalid_cron(self):
        """Test parsing invalid cron expressions"""
        with pytest.raises(ValueError):
            CronParser.parse("invalid")
        
        with pytest.raises(ValueError):
            CronParser.parse("0 * *")  # Too few fields
    
    def test_next_run_time_is_future(self):
        """Test that next run time is in the future"""
        now = datetime.utcnow()
        next_run = CronParser.next_run_time("0 * * * *", now)
        
        assert next_run > now
    
    def test_seconds_until_next_run(self):
        """Test calculating seconds until next run"""
        now = datetime.utcnow()
        seconds = CronParser.seconds_until_next_run("0 * * * *", now)
        
        assert seconds >= 1
        assert seconds <= 3600  # Should be within an hour
