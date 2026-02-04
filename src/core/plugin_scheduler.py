"""
Plugin Scheduler System

Provides interval-based and cron-style scheduling for plugin tasks.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import re


@dataclass
class ScheduledTask:
    """Scheduled task definition"""
    name: str
    plugin: str
    interval: Optional[int] = None  # seconds
    cron: Optional[str] = None  # cron expression
    handler: Callable = None
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    _task: Optional[asyncio.Task] = field(default=None, init=False, repr=False)


class CronParser:
    """Simple cron expression parser"""
    
    @staticmethod
    def parse(cron_expr: str) -> Dict[str, Any]:
        """
        Parse cron expression.
        
        Supports simplified cron format: minute hour day month weekday
        Examples:
            "0 * * * *" - Every hour at minute 0
            "*/5 * * * *" - Every 5 minutes
            "0 0 * * *" - Daily at midnight
            "0 12 * * 1" - Every Monday at noon
        
        Args:
            cron_expr: Cron expression string
            
        Returns:
            Dictionary with parsed fields
            
        Raises:
            ValueError: If cron expression is invalid
        """
        parts = cron_expr.strip().split()
        
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}. Expected 5 fields.")
        
        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'weekday': parts[4]
        }
    
    @staticmethod
    def next_run_time(cron_expr: str, from_time: Optional[datetime] = None) -> datetime:
        """
        Calculate next run time from cron expression.
        
        Args:
            cron_expr: Cron expression
            from_time: Calculate from this time (defaults to now)
            
        Returns:
            Next scheduled run time
        """
        if from_time is None:
            from_time = datetime.utcnow()
        
        parsed = CronParser.parse(cron_expr)
        
        # For simplicity, handle common patterns
        # Full cron implementation would be more complex
        
        minute = parsed['minute']
        hour = parsed['hour']
        
        # Start from next minute
        next_time = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Handle */N patterns for minutes
        if minute.startswith('*/'):
            interval = int(minute[2:])
            # Round up to next interval
            minutes_since_hour = next_time.minute
            next_interval = ((minutes_since_hour // interval) + 1) * interval
            if next_interval >= 60:
                next_time = next_time.replace(minute=0) + timedelta(hours=1)
            else:
                next_time = next_time.replace(minute=next_interval)
        elif minute == '*':
            # Every minute - already set
            pass
        else:
            # Specific minute
            target_minute = int(minute)
            if next_time.minute > target_minute:
                # Move to next hour
                next_time = next_time.replace(minute=target_minute) + timedelta(hours=1)
            else:
                next_time = next_time.replace(minute=target_minute)
        
        # Handle hour
        if hour.startswith('*/'):
            interval = int(hour[2:])
            hours_since_day = next_time.hour
            next_interval = ((hours_since_day // interval) + 1) * interval
            if next_interval >= 24:
                next_time = next_time.replace(hour=0) + timedelta(days=1)
            else:
                next_time = next_time.replace(hour=next_interval)
        elif hour != '*':
            target_hour = int(hour)
            if next_time.hour > target_hour:
                # Move to next day
                next_time = next_time.replace(hour=target_hour) + timedelta(days=1)
            elif next_time.hour < target_hour:
                next_time = next_time.replace(hour=target_hour)
        
        return next_time
    
    @staticmethod
    def seconds_until_next_run(cron_expr: str, from_time: Optional[datetime] = None) -> int:
        """
        Calculate seconds until next run.
        
        Args:
            cron_expr: Cron expression
            from_time: Calculate from this time (defaults to now)
            
        Returns:
            Seconds until next run
        """
        if from_time is None:
            from_time = datetime.utcnow()
        
        next_run = CronParser.next_run_time(cron_expr, from_time)
        delta = next_run - from_time
        return max(1, int(delta.total_seconds()))


class PluginScheduler:
    """
    Scheduler for plugin tasks.
    
    Supports both interval-based and cron-style scheduling.
    """
    
    def __init__(self, plugin_name: str, mesh_interface: Optional[Any] = None):
        """
        Initialize scheduler.
        
        Args:
            plugin_name: Name of the plugin
            mesh_interface: Mesh interface for sending messages (optional)
        """
        self.plugin_name = plugin_name
        self.mesh_interface = mesh_interface
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running_tasks: Set[asyncio.Task] = set()
        self.logger = logging.getLogger(f"PluginScheduler.{plugin_name}")
        self._shutdown = False
    
    def register_task(self, name: str, handler: Callable,
                     interval: Optional[int] = None,
                     cron: Optional[str] = None) -> ScheduledTask:
        """
        Register a scheduled task.
        
        Args:
            name: Task name (unique within plugin)
            handler: Async function to execute
            interval: Interval in seconds (for interval-based scheduling)
            cron: Cron expression (for cron-style scheduling)
            
        Returns:
            Created ScheduledTask
            
        Raises:
            ValueError: If neither interval nor cron is provided, or both are provided
            
        Example:
            # Interval-based
            scheduler.register_task("hourly", my_handler, interval=3600)
            
            # Cron-style
            scheduler.register_task("daily", my_handler, cron="0 0 * * *")
        """
        if interval is None and cron is None:
            raise ValueError("Either interval or cron must be provided")
        
        if interval is not None and cron is not None:
            raise ValueError("Cannot specify both interval and cron")
        
        # Validate and convert interval to int if needed
        if interval is not None:
            if isinstance(interval, str):
                try:
                    interval = int(interval)
                except ValueError:
                    raise ValueError(f"Invalid interval value: {interval}. Must be an integer or numeric string.")
            elif not isinstance(interval, int):
                raise ValueError(f"Invalid interval type: {type(interval).__name__}. Must be an integer.")
            
            if interval <= 0:
                raise ValueError(f"Interval must be positive, got: {interval}")
        
        # Validate cron expression if provided
        if cron:
            try:
                CronParser.parse(cron)
            except ValueError as e:
                raise ValueError(f"Invalid cron expression: {e}")
        
        task = ScheduledTask(
            name=name,
            plugin=self.plugin_name,
            interval=interval,
            cron=cron,
            handler=handler,
            enabled=True
        )
        
        self.tasks[name] = task
        self.logger.info(f"Registered task '{name}' with " +
                        (f"interval={interval}s" if interval else f"cron='{cron}'"))
        
        return task
    
    async def start_all(self):
        """Start all registered tasks."""
        for task in self.tasks.values():
            if task.enabled:
                await self.start_task(task.name)
    
    async def start_task(self, name: str):
        """
        Start a specific task.
        
        Args:
            name: Task name
            
        Raises:
            KeyError: If task not found
        """
        if name not in self.tasks:
            raise KeyError(f"Task '{name}' not found")
        
        task = self.tasks[name]
        
        # Don't start if already running
        if task._task and not task._task.done():
            self.logger.warning(f"Task '{name}' is already running")
            return
        
        # Create and start the task
        task._task = asyncio.create_task(self._run_task(task))
        self.running_tasks.add(task._task)
        
        # Clean up when done
        task._task.add_done_callback(self.running_tasks.discard)
        
        self.logger.info(f"Started task '{name}'")
    
    async def _run_task(self, task: ScheduledTask):
        """
        Run a scheduled task loop.
        
        Args:
            task: Task to run
        """
        self.logger.debug(f"Task loop started for '{task.name}'")
        
        while task.enabled and not self._shutdown:
            try:
                # Execute the handler
                self.logger.debug(f"Executing task '{task.name}'")
                task.last_run = datetime.utcnow()
                
                try:
                    # Call the handler
                    result = task.handler()
                    if asyncio.iscoroutine(result):
                        await result
                    
                    task.run_count += 1
                    task.last_error = None
                    self.logger.debug(f"Task '{task.name}' completed successfully " +
                                    f"(run #{task.run_count})")
                    
                except Exception as e:
                    # Log error but continue running
                    task.error_count += 1
                    task.last_error = str(e)
                    self.logger.error(f"Error in task '{task.name}': {e}", exc_info=True)
                
                # Calculate wait time for next execution
                if task.interval:
                    # Interval-based scheduling
                    wait_time = task.interval
                    task.next_run = datetime.utcnow() + timedelta(seconds=wait_time)
                else:
                    # Cron-based scheduling
                    wait_time = CronParser.seconds_until_next_run(task.cron)
                    task.next_run = datetime.utcnow() + timedelta(seconds=wait_time)
                
                # Wait until next execution
                self.logger.debug(f"Task '{task.name}' waiting {wait_time}s until next run")
                await asyncio.sleep(wait_time)
                
            except asyncio.CancelledError:
                self.logger.info(f"Task '{task.name}' cancelled")
                break
            except Exception as e:
                # Unexpected error in task loop
                self.logger.error(f"Unexpected error in task loop for '{task.name}': {e}",
                                exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(60)
        
        self.logger.debug(f"Task loop ended for '{task.name}'")
    
    async def stop_task(self, name: str):
        """
        Stop a specific task.
        
        Args:
            name: Task name
            
        Raises:
            KeyError: If task not found
        """
        if name not in self.tasks:
            raise KeyError(f"Task '{name}' not found")
        
        task = self.tasks[name]
        task.enabled = False
        
        if task._task and not task._task.done():
            task._task.cancel()
            try:
                await task._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info(f"Stopped task '{name}'")
    
    async def stop_all(self):
        """Stop all tasks."""
        self._shutdown = True
        
        # Stop all tasks
        for name in list(self.tasks.keys()):
            await self.stop_task(name)
        
        # Wait for all running tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        self.logger.info("All tasks stopped")
    
    def get_task_status(self, name: str) -> Dict[str, Any]:
        """
        Get status of a specific task.
        
        Args:
            name: Task name
            
        Returns:
            Dictionary with task status information
            
        Raises:
            KeyError: If task not found
        """
        if name not in self.tasks:
            raise KeyError(f"Task '{name}' not found")
        
        task = self.tasks[name]
        
        return {
            'name': task.name,
            'plugin': task.plugin,
            'enabled': task.enabled,
            'interval': task.interval,
            'cron': task.cron,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'next_run': task.next_run.isoformat() if task.next_run else None,
            'run_count': task.run_count,
            'error_count': task.error_count,
            'last_error': task.last_error,
            'is_running': task._task is not None and not task._task.done()
        }
    
    def get_all_task_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all tasks.
        
        Returns:
            List of task status dictionaries
        """
        return [self.get_task_status(name) for name in self.tasks.keys()]
    
    def unregister_task(self, name: str):
        """
        Unregister a task.
        
        Args:
            name: Task name
            
        Raises:
            KeyError: If task not found
        """
        if name not in self.tasks:
            raise KeyError(f"Task '{name}' not found")
        
        # Stop the task first
        asyncio.create_task(self.stop_task(name))
        
        # Remove from registry
        del self.tasks[name]
        self.logger.info(f"Unregistered task '{name}'")
