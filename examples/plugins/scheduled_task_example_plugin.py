"""
Example Plugin: Scheduled Task Demonstration

This plugin demonstrates how to use the scheduled task system with both
interval-based and cron-style scheduling.
"""

import asyncio
from datetime import datetime
from src.core import EnhancedPlugin


class ScheduledTaskExamplePlugin(EnhancedPlugin):
    """
    Example plugin demonstrating scheduled task functionality.
    
    This plugin registers multiple scheduled tasks:
    - An interval-based task that runs every 60 seconds
    - A cron-based task that runs at specific times
    - A task that demonstrates error handling
    """
    
    async def initialize(self) -> bool:
        """Initialize the plugin and register scheduled tasks"""
        self.logger.info("Initializing Scheduled Task Example Plugin")
        
        # Register an interval-based task (runs every 60 seconds)
        self.register_scheduled_task(
            name="periodic_update",
            handler=self.periodic_update_handler,
            interval=60
        )
        
        # Register a cron-based task (runs every 5 minutes)
        self.register_scheduled_task(
            name="five_minute_report",
            handler=self.five_minute_report_handler,
            cron="*/5 * * * *"
        )
        
        # Register a task that demonstrates error handling
        self.register_scheduled_task(
            name="error_demo",
            handler=self.error_demo_handler,
            interval=120
        )
        
        # Register a command to check task status
        self.register_command(
            command="taskstatus",
            handler=self.task_status_command,
            help_text="Show status of all scheduled tasks"
        )
        
        return True
    
    async def periodic_update_handler(self):
        """
        Handler for periodic update task.
        
        This runs every 60 seconds and demonstrates basic scheduled task functionality.
        """
        self.logger.info("Periodic update task executing")
        
        # Get current time
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Store the last update time
        await self.store_data("last_update", current_time)
        
        # Send a message to the mesh (optional)
        # await self.send_message(f"Periodic update at {current_time}")
        
        self.logger.info(f"Periodic update completed at {current_time}")
    
    async def five_minute_report_handler(self):
        """
        Handler for five-minute report task.
        
        This runs every 5 minutes (cron: */5 * * * *) and demonstrates cron-based scheduling.
        """
        self.logger.info("Five-minute report task executing")
        
        # Get the scheduler to check task statistics
        scheduler = self.get_scheduler()
        all_status = scheduler.get_all_task_status()
        
        # Count total executions
        total_runs = sum(task['run_count'] for task in all_status)
        total_errors = sum(task['error_count'] for task in all_status)
        
        self.logger.info(f"Report: {len(all_status)} tasks, {total_runs} total runs, {total_errors} errors")
        
        # Store report data
        await self.store_data("last_report", {
            "time": datetime.utcnow().isoformat(),
            "total_runs": total_runs,
            "total_errors": total_errors
        })
    
    async def error_demo_handler(self):
        """
        Handler that demonstrates error handling in scheduled tasks.
        
        This task intentionally fails sometimes to show that the scheduler
        continues executing tasks even after errors.
        """
        self.logger.info("Error demo task executing")
        
        # Get error count from storage
        error_count = await self.retrieve_data("error_demo_count", 0)
        
        # Fail every 3rd execution to demonstrate error handling
        if error_count % 3 == 2:
            self.logger.warning("Error demo: Simulating an error")
            await self.store_data("error_demo_count", error_count + 1)
            raise Exception("Simulated error for demonstration")
        
        # Normal execution
        await self.store_data("error_demo_count", error_count + 1)
        self.logger.info(f"Error demo task completed successfully (count: {error_count + 1})")
    
    async def task_status_command(self, args, context):
        """
        Command handler to show status of all scheduled tasks.
        
        Usage: taskstatus
        """
        scheduler = self.get_scheduler()
        all_status = scheduler.get_all_task_status()
        
        if not all_status:
            return "No scheduled tasks registered"
        
        # Build status message
        lines = ["Scheduled Task Status:"]
        lines.append("-" * 40)
        
        for task in all_status:
            status_line = f"Task: {task['name']}"
            lines.append(status_line)
            lines.append(f"  Enabled: {task['enabled']}")
            lines.append(f"  Running: {task['is_running']}")
            
            if task['interval']:
                lines.append(f"  Interval: {task['interval']}s")
            elif task['cron']:
                lines.append(f"  Cron: {task['cron']}")
            
            lines.append(f"  Runs: {task['run_count']}")
            lines.append(f"  Errors: {task['error_count']}")
            
            if task['last_run']:
                lines.append(f"  Last Run: {task['last_run']}")
            if task['next_run']:
                lines.append(f"  Next Run: {task['next_run']}")
            
            if task['last_error']:
                lines.append(f"  Last Error: {task['last_error']}")
            
            lines.append("")
        
        return "\n".join(lines)


# Plugin factory function
def create_plugin(name: str, config: dict, plugin_manager):
    """Create and return plugin instance"""
    return ScheduledTaskExamplePlugin(name, config, plugin_manager)
