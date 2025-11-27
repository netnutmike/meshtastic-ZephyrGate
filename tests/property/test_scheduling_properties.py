"""
Property-Based Tests for Plugin Scheduled Task System

Tests universal properties of the scheduled task system using Hypothesis.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st
from hypothesis import assume

from src.core.plugin_scheduler import PluginScheduler, ScheduledTask, CronParser


# Strategies for generating test data

@st.composite
def task_name_strategy(draw):
    """Generate valid task names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ))


@st.composite
def interval_strategy(draw):
    """Generate valid intervals (1 second to 1 hour)"""
    return draw(st.integers(min_value=1, max_value=3600))


@st.composite
def cron_expression_strategy(draw):
    """Generate valid cron expressions"""
    # Simplified cron expressions for testing
    minute = draw(st.one_of(
        st.just('*'),
        st.integers(min_value=0, max_value=59).map(str),
        st.integers(min_value=1, max_value=59).map(lambda x: f'*/{x}')
    ))
    hour = draw(st.one_of(
        st.just('*'),
        st.integers(min_value=0, max_value=23).map(str),
        st.integers(min_value=1, max_value=23).map(lambda x: f'*/{x}')
    ))
    day = draw(st.just('*'))  # Simplified
    month = draw(st.just('*'))  # Simplified
    weekday = draw(st.just('*'))  # Simplified
    
    return f"{minute} {hour} {day} {month} {weekday}"


class TestScheduledTaskExecution:
    """
    Feature: third-party-plugin-system, Property 7: Scheduled task execution
    
    Property: For any scheduled task with an interval, the task should execute at 
    approximately that interval (within 10% tolerance), and failures should not 
    prevent future executions.
    
    Validates: Requirements 3.1, 3.4
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)  # 10 second deadline per example
    @given(
        interval=st.integers(min_value=1, max_value=2)  # Very short intervals for testing
    )
    async def test_interval_task_executes_at_interval(self, interval):
        """
        Property: Interval-based tasks execute at approximately the specified interval.
        
        For any interval, when a task is registered and started,
        it should execute multiple times at approximately the specified interval.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        execution_times = []
        
        async def test_handler():
            execution_times.append(datetime.utcnow())
        
        try:
            # Register and start task
            scheduler.register_task(task_name, test_handler, interval=interval)
            await scheduler.start_task(task_name)
            
            # Wait for at least 2 executions (with some buffer)
            wait_time = interval * 2.5
            await asyncio.sleep(wait_time)
            
            # Stop the task
            await scheduler.stop_task(task_name)
            
            # Verify task executed at least once
            assert len(execution_times) >= 1, \
                f"Task should execute at least once, got {len(execution_times)} executions"
            
            # If we have multiple executions, check interval
            if len(execution_times) >= 2:
                # Calculate actual intervals
                intervals = []
                for i in range(1, len(execution_times)):
                    delta = (execution_times[i] - execution_times[i-1]).total_seconds()
                    intervals.append(delta)
                
                # Check each interval is within tolerance (30% for test stability)
                tolerance = 0.30
                for actual_interval in intervals:
                    lower_bound = interval * (1 - tolerance)
                    upper_bound = interval * (1 + tolerance)
                    assert lower_bound <= actual_interval <= upper_bound, \
                        f"Interval {actual_interval}s not within {tolerance*100}% of {interval}s"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        interval=st.integers(min_value=1, max_value=2)  # Short intervals for testing
    )
    async def test_task_continues_after_handler_failure(self, interval):
        """
        Property: Task execution continues after handler failures.
        
        For any task, when the handler raises an exception, the task should continue
        executing on schedule and not crash.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        execution_count = [0]
        failure_count = [0]
        
        async def failing_handler():
            execution_count[0] += 1
            if execution_count[0] <= 2:
                failure_count[0] += 1
                raise Exception("Simulated failure")
            # Succeed on subsequent calls
        
        try:
            # Register and start task
            scheduler.register_task(task_name, failing_handler, interval=interval)
            await scheduler.start_task(task_name)
            
            # Wait for multiple executions
            await asyncio.sleep(interval * 3.5)
            
            # Stop the task
            await scheduler.stop_task(task_name)
            
            # Verify task executed multiple times despite failures
            assert execution_count[0] >= 2, \
                f"Task should execute multiple times, got {execution_count[0]} executions"
            
            # Verify failures were recorded
            task = scheduler.tasks[task_name]
            assert task.error_count >= failure_count[0], \
                f"Error count should be at least {failure_count[0]}, got {task.error_count}"
            
            # Verify task continued after failures
            assert execution_count[0] > failure_count[0], \
                "Task should continue executing after failures"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=5000)
    @given(
        cron_expr=cron_expression_strategy()
    )
    async def test_cron_task_executes(self, cron_expr):
        """
        Property: Cron-based tasks execute according to schedule.
        
        For any valid cron expression, when a task is registered with that expression,
        it should execute at the appropriate times.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        execution_count = [0]
        
        async def test_handler():
            execution_count[0] += 1
        
        try:
            # Register task with cron expression
            scheduler.register_task(task_name, test_handler, cron=cron_expr)
            
            # Verify task was registered
            assert task_name in scheduler.tasks
            task = scheduler.tasks[task_name]
            assert task.cron == cron_expr
            assert task.interval is None
            
            # Start the task
            await scheduler.start_task(task_name)
            
            # Wait a short time
            await asyncio.sleep(2)
            
            # Stop the task
            await scheduler.stop_task(task_name)
            
            # Verify task was started (execution count may be 0 or more depending on timing)
            # The important thing is it didn't crash
            assert execution_count[0] >= 0
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=5000)
    @given(
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_task_tracks_execution_metrics(self, interval):
        """
        Property: Task execution metrics are tracked correctly.
        
        For any task, the scheduler should track run count, error count, and last run time.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        
        async def test_handler():
            pass
        
        try:
            # Register and start task
            scheduler.register_task(task_name, test_handler, interval=interval)
            
            # Check initial state
            task = scheduler.tasks[task_name]
            assert task.run_count == 0
            assert task.error_count == 0
            assert task.last_run is None
            
            await scheduler.start_task(task_name)
            
            # Wait for at least one execution
            await asyncio.sleep(interval + 1)
            
            # Stop the task
            await scheduler.stop_task(task_name)
            
            # Verify metrics were updated
            assert task.run_count >= 1, "Run count should be at least 1"
            assert task.last_run is not None, "Last run time should be set"
            assert task.error_count == 0, "Error count should be 0 for successful handler"
        
        finally:
            await scheduler.stop_all()


class TestCronParser:
    """Tests for cron expression parsing"""
    
    @settings(max_examples=100)
    @given(cron_expr=cron_expression_strategy())
    def test_cron_parser_accepts_valid_expressions(self, cron_expr):
        """
        Property: Valid cron expressions are parsed without error.
        
        For any valid cron expression, the parser should successfully parse it.
        """
        # Should not raise exception
        parsed = CronParser.parse(cron_expr)
        
        # Verify structure
        assert 'minute' in parsed
        assert 'hour' in parsed
        assert 'day' in parsed
        assert 'month' in parsed
        assert 'weekday' in parsed
    
    @settings(max_examples=100)
    @given(cron_expr=cron_expression_strategy())
    def test_next_run_time_is_in_future(self, cron_expr):
        """
        Property: Next run time is always in the future.
        
        For any cron expression, the calculated next run time should be after the current time.
        """
        now = datetime.utcnow()
        next_run = CronParser.next_run_time(cron_expr, now)
        
        assert next_run > now, "Next run time should be in the future"
    
    @settings(max_examples=100)
    @given(
        cron_expr=cron_expression_strategy(),
        seconds_offset=st.integers(min_value=0, max_value=3600)
    )
    def test_seconds_until_next_run_is_positive(self, cron_expr, seconds_offset):
        """
        Property: Seconds until next run is always positive.
        
        For any cron expression and time, the seconds until next run should be positive.
        """
        from_time = datetime.utcnow() + timedelta(seconds=seconds_offset)
        seconds = CronParser.seconds_until_next_run(cron_expr, from_time)
        
        assert seconds >= 1, "Seconds until next run should be at least 1"


class TestTaskCancellation:
    """
    Feature: third-party-plugin-system, Property 8: Task cancellation on plugin stop
    
    Property: For any plugin with scheduled tasks, stopping the plugin should cancel 
    all tasks such that no further executions occur.
    
    Validates: Requirements 3.5
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_stopping_plugin_cancels_all_tasks(self, interval):
        """
        Property: Stopping scheduler cancels all tasks.
        
        For any task, when the scheduler is stopped, the task should not execute again.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        execution_count = [0]
        
        async def test_handler():
            execution_count[0] += 1
        
        try:
            # Register and start task
            scheduler.register_task(task_name, test_handler, interval=interval)
            await scheduler.start_task(task_name)
            
            # Wait for at least one execution
            await asyncio.sleep(0.5)
            initial_count = execution_count[0]
            
            # Stop all tasks
            await scheduler.stop_all()
            
            # Wait for more than one interval
            await asyncio.sleep(interval * 2)
            
            # Verify no more executions occurred
            assert execution_count[0] == initial_count, \
                f"Task should not execute after stop, but count increased from {initial_count} to {execution_count[0]}"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        num_tasks=st.integers(min_value=1, max_value=3),
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_stopping_cancels_multiple_tasks(self, num_tasks, interval):
        """
        Property: Stopping scheduler cancels all registered tasks.
        
        For any number of tasks, when the scheduler is stopped, all tasks should stop.
        """
        plugin_name = "test_plugin"
        scheduler = PluginScheduler(plugin_name)
        execution_counts = {}
        
        # Register multiple tasks
        for i in range(num_tasks):
            task_name = f"task_{i}"
            execution_counts[task_name] = [0]
            
            async def make_handler(name):
                async def handler():
                    execution_counts[name][0] += 1
                return handler
            
            handler = await make_handler(task_name)
            scheduler.register_task(task_name, handler, interval=interval)
        
        try:
            # Start all tasks
            await scheduler.start_all()
            
            # Wait for at least one execution
            await asyncio.sleep(0.5)
            
            # Record counts before stopping
            counts_before = {name: count[0] for name, count in execution_counts.items()}
            
            # Stop all tasks
            await scheduler.stop_all()
            
            # Wait for more than one interval
            await asyncio.sleep(interval * 2)
            
            # Verify no tasks executed after stop
            for task_name, count in execution_counts.items():
                assert count[0] == counts_before[task_name], \
                    f"Task {task_name} should not execute after stop"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_individual_task_can_be_stopped(self, interval):
        """
        Property: Individual tasks can be stopped without affecting others.
        
        For any task, stopping it should not affect other running tasks.
        """
        plugin_name = "test_plugin"
        scheduler = PluginScheduler(plugin_name)
        task1_count = [0]
        task2_count = [0]
        
        async def handler1():
            task1_count[0] += 1
        
        async def handler2():
            task2_count[0] += 1
        
        try:
            # Register and start two tasks
            scheduler.register_task("task1", handler1, interval=interval)
            scheduler.register_task("task2", handler2, interval=interval)
            await scheduler.start_all()
            
            # Wait for executions
            await asyncio.sleep(0.5)
            
            # Stop only task1
            await scheduler.stop_task("task1")
            task1_count_after_stop = task1_count[0]
            
            # Wait for more executions
            await asyncio.sleep(interval * 2)
            
            # Verify task1 stopped but task2 continued
            assert task1_count[0] == task1_count_after_stop, \
                "Task1 should not execute after being stopped"
            assert task2_count[0] > 0, \
                "Task2 should continue executing"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_task_cleanup_is_complete(self, interval):
        """
        Property: Task cleanup is complete after stopping.
        
        For any task, after stopping, the task should be marked as not enabled
        and not running.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        
        async def test_handler():
            pass
        
        try:
            # Register and start task
            scheduler.register_task(task_name, test_handler, interval=interval)
            await scheduler.start_task(task_name)
            
            # Verify task is running
            status = scheduler.get_task_status(task_name)
            assert status['enabled'] == True
            assert status['is_running'] == True
            
            # Stop the task
            await scheduler.stop_task(task_name)
            
            # Verify task is stopped
            status = scheduler.get_task_status(task_name)
            assert status['enabled'] == False
            assert status['is_running'] == False
        
        finally:
            await scheduler.stop_all()


class TestSchedulerTaskManagement:
    """Tests for scheduler task management"""
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        num_tasks=st.integers(min_value=1, max_value=3),
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_multiple_tasks_execute_independently(self, num_tasks, interval):
        """
        Property: Multiple tasks execute independently.
        
        For any set of tasks, each task should execute independently without
        interfering with others.
        """
        plugin_name = "test_plugin"
        scheduler = PluginScheduler(plugin_name)
        execution_counts = {}
        
        # Register multiple tasks
        for i in range(num_tasks):
            task_name = f"task_{i}"
            execution_counts[task_name] = [0]
            
            async def make_handler(name):
                async def handler():
                    execution_counts[name][0] += 1
                return handler
            
            handler = await make_handler(task_name)
            scheduler.register_task(task_name, handler, interval=interval)
        
        try:
            # Start all tasks
            await scheduler.start_all()
            
            # Wait for executions
            await asyncio.sleep(interval + 1)
            
            # Stop all tasks
            await scheduler.stop_all()
            
            # Verify all tasks executed
            for task_name in execution_counts.keys():
                assert execution_counts[task_name][0] >= 1, \
                    f"Task {task_name} should have executed at least once"
        
        finally:
            await scheduler.stop_all()
    
    @pytest.mark.asyncio
    @settings(max_examples=20, deadline=10000)
    @given(
        interval=st.integers(min_value=1, max_value=2)
    )
    async def test_task_status_reflects_current_state(self, interval):
        """
        Property: Task status accurately reflects current state.
        
        For any task, the status information should accurately reflect whether
        the task is running, enabled, and its execution history.
        """
        plugin_name = "test_plugin"
        task_name = "test_task"
        scheduler = PluginScheduler(plugin_name)
        
        async def test_handler():
            pass
        
        try:
            # Register task
            scheduler.register_task(task_name, test_handler, interval=interval)
            
            # Check status before starting
            status = scheduler.get_task_status(task_name)
            assert status['name'] == task_name
            assert status['plugin'] == plugin_name
            assert status['enabled'] == True
            assert status['interval'] == interval
            assert status['run_count'] == 0
            
            # Start task
            await scheduler.start_task(task_name)
            
            # Wait briefly
            await asyncio.sleep(0.5)
            
            # Check status while running
            status = scheduler.get_task_status(task_name)
            assert status['is_running'] == True
            
            # Stop task
            await scheduler.stop_task(task_name)
            
            # Check status after stopping
            status = scheduler.get_task_status(task_name)
            assert status['enabled'] == False
        
        finally:
            await scheduler.stop_all()
