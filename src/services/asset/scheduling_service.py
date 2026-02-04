"""
Scheduling Service

Provides cron-like functionality for automated task scheduling, including
broadcasts, weather updates, BBS synchronization, and maintenance tasks.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json
from croniter import croniter

from core.database import get_database, DatabaseError
from core.plugin_interfaces import BaseMessageHandler


class TaskType(Enum):
    """Types of scheduled tasks"""
    BROADCAST = "broadcast"
    WEATHER_UPDATE = "weather_update"
    BBS_SYNC = "bbs_sync"
    MAINTENANCE = "maintenance"
    CUSTOM = "custom"


class TaskStatus(Enum):
    """Status of scheduled tasks"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(Enum):
    """Types of scheduling"""
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"


@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    id: str
    name: str
    task_type: TaskType
    schedule_type: ScheduleType
    
    # Scheduling parameters
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    
    # Task parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Execution tracking
    status: TaskStatus = TaskStatus.ACTIVE
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    last_error: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    max_failures: int = 3
    timeout_seconds: int = 300
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type.value,
            'schedule_type': self.schedule_type.value,
            'cron_expression': self.cron_expression,
            'interval_seconds': self.interval_seconds,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'parameters': json.dumps(self.parameters),
            'status': self.status.value,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'run_count': self.run_count,
            'failure_count': self.failure_count,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'max_failures': self.max_failures,
            'timeout_seconds': self.timeout_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledTask':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            name=data['name'],
            task_type=TaskType(data['task_type']),
            schedule_type=ScheduleType(data['schedule_type']),
            cron_expression=data.get('cron_expression'),
            interval_seconds=data.get('interval_seconds'),
            scheduled_time=datetime.fromisoformat(data['scheduled_time']) if data.get('scheduled_time') else None,
            parameters=json.loads(data.get('parameters', '{}')),
            status=TaskStatus(data.get('status', 'active')),
            last_run=datetime.fromisoformat(data['last_run']) if data.get('last_run') else None,
            next_run=datetime.fromisoformat(data['next_run']) if data.get('next_run') else None,
            run_count=data.get('run_count', 0),
            failure_count=data.get('failure_count', 0),
            last_error=data.get('last_error'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now(timezone.utc).isoformat())),
            created_by=data.get('created_by', ''),
            max_failures=data.get('max_failures', 3),
            timeout_seconds=data.get('timeout_seconds', 300)
        )


@dataclass
class TaskExecution:
    """Represents a task execution record"""
    id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.RUNNING
    result: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'duration_seconds': self.duration_seconds
        }


class SchedulingService(BaseMessageHandler):
    """
    Scheduling service for automated task execution with cron-like functionality
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(priority=60)  # Initialize base class
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        self.running = False
        
        # Task storage
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_handlers: Dict[TaskType, Callable] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.check_interval = config.get('check_interval', 30)  # Check every 30 seconds
        self.max_concurrent_tasks = config.get('max_concurrent_tasks', 10)
        self.cleanup_days = config.get('cleanup_days', 30)
        
        # Scheduler task
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Initialize database tables
        self._initialize_database()
        
        # Register default task handlers
        self._register_default_handlers()
        
        self.logger.info("Scheduling Service initialized")
    
    def _initialize_database(self):
        """Initialize database tables for scheduling"""
        try:
            with self.db.transaction() as conn:
                # Scheduled tasks table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_tasks (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        schedule_type TEXT NOT NULL,
                        cron_expression TEXT,
                        interval_seconds INTEGER,
                        scheduled_time TEXT,
                        parameters TEXT,
                        status TEXT DEFAULT 'active',
                        last_run TEXT,
                        next_run TEXT,
                        run_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT,
                        max_failures INTEGER DEFAULT 3,
                        timeout_seconds INTEGER DEFAULT 300
                    )
                """)
                
                # Task execution history
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS task_executions (
                        id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        status TEXT NOT NULL,
                        result TEXT,
                        error TEXT,
                        duration_seconds REAL,
                        FOREIGN KEY (task_id) REFERENCES scheduled_tasks (id)
                    )
                """)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks (next_run)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks (status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_task_executions_task_id ON task_executions (task_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_task_executions_started ON task_executions (started_at)")
            
            # Load existing tasks
            self._load_tasks()
            
        except Exception as e:
            self.logger.error(f"Error initializing scheduling database: {e}")
            raise
    
    def _load_tasks(self):
        """Load tasks from database"""
        try:
            rows = self.db.execute_query("SELECT * FROM scheduled_tasks WHERE status != 'cancelled'")
            
            for row in rows:
                task = ScheduledTask.from_dict(dict(row))
                self.tasks[task.id] = task
                
                # Calculate next run time if not set
                if not task.next_run and task.status == TaskStatus.ACTIVE:
                    task.next_run = self._calculate_next_run(task)
                    self._save_task(task)
            
            self.logger.info(f"Loaded {len(self.tasks)} scheduled tasks")
            
        except Exception as e:
            self.logger.error(f"Error loading tasks: {e}")
    
    def _register_default_handlers(self):
        """Register default task handlers"""
        self.task_handlers[TaskType.BROADCAST] = self._handle_broadcast_task
        self.task_handlers[TaskType.WEATHER_UPDATE] = self._handle_weather_update_task
        self.task_handlers[TaskType.BBS_SYNC] = self._handle_bbs_sync_task
        self.task_handlers[TaskType.MAINTENANCE] = self._handle_maintenance_task
        self.task_handlers[TaskType.CUSTOM] = self._handle_custom_task
    
    async def start(self) -> None:
        """Start the scheduling service"""
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("Scheduling Service started")
    
    async def stop(self) -> None:
        """Stop the scheduling service"""
        self.running = False
        
        # Cancel scheduler task
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running tasks
        for task in self.running_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        self.logger.info("Scheduling Service stopped")
    
    async def handle_message(self, message: str, sender_id: str, **kwargs) -> Optional[str]:
        """Handle scheduling-related commands"""
        message = message.strip().lower()
        
        # Check if user has admin permissions for scheduling commands
        user = self.db.get_user(sender_id)
        if not user or not user.get('permissions', {}).get('admin', False):
            return None
        
        if message.startswith('schedule'):
            return await self._handle_schedule_command(message, sender_id)
        elif message.startswith('tasks'):
            return await self._handle_tasks_command(message, sender_id)
        
        return None
    
    def can_handle(self, message) -> bool:
        """Check if this service can handle the message"""
        if hasattr(message, 'content'):
            content = message.content.strip().lower()
            return any(content.startswith(cmd) for cmd in ['schedule', 'tasks'])
        return False
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._check_scheduled_tasks()
                await self._cleanup_old_executions()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_scheduled_tasks(self):
        """Check for tasks that need to be executed"""
        now = datetime.now(timezone.utc)
        
        # Limit concurrent tasks
        if len(self.running_tasks) >= self.max_concurrent_tasks:
            return
        
        for task in list(self.tasks.values()):
            if (task.status == TaskStatus.ACTIVE and 
                task.next_run and 
                task.next_run <= now and
                task.id not in self.running_tasks):
                
                # Check failure threshold
                if task.failure_count >= task.max_failures:
                    task.status = TaskStatus.FAILED
                    self._save_task(task)
                    self.logger.warning(f"Task {task.name} disabled due to too many failures")
                    continue
                
                # Execute task
                execution_task = asyncio.create_task(self._execute_task(task))
                self.running_tasks[task.id] = execution_task
    
    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        execution_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        
        execution = TaskExecution(
            id=execution_id,
            task_id=task.id,
            started_at=started_at,
            status=TaskStatus.RUNNING
        )
        
        try:
            self.logger.info(f"Executing task: {task.name} ({task.task_type.value})")
            
            # Update task status
            task.status = TaskStatus.RUNNING
            task.last_run = started_at
            self._save_task(task)
            
            # Get task handler
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise Exception(f"No handler for task type: {task.task_type.value}")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(task),
                timeout=task.timeout_seconds
            )
            
            # Task completed successfully
            completed_at = datetime.now(timezone.utc)
            execution.completed_at = completed_at
            execution.status = TaskStatus.COMPLETED
            execution.result = str(result) if result else None
            execution.duration_seconds = (completed_at - started_at).total_seconds()
            
            # Update task
            task.status = TaskStatus.ACTIVE
            task.run_count += 1
            task.failure_count = 0  # Reset failure count on success
            task.last_error = None
            task.next_run = self._calculate_next_run(task)
            
            self.logger.info(f"Task {task.name} completed successfully")
            
        except asyncio.TimeoutError:
            error_msg = f"Task timed out after {task.timeout_seconds} seconds"
            self.logger.error(f"Task {task.name} timed out")
            
            execution.completed_at = datetime.now(timezone.utc)
            execution.status = TaskStatus.FAILED
            execution.error = error_msg
            execution.duration_seconds = task.timeout_seconds
            
            task.status = TaskStatus.ACTIVE
            task.failure_count += 1
            task.last_error = error_msg
            task.next_run = self._calculate_next_run(task)
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Task {task.name} failed: {error_msg}")
            
            execution.completed_at = datetime.now(timezone.utc)
            execution.status = TaskStatus.FAILED
            execution.error = error_msg
            execution.duration_seconds = (execution.completed_at - started_at).total_seconds()
            
            task.status = TaskStatus.ACTIVE
            task.failure_count += 1
            task.last_error = error_msg
            task.next_run = self._calculate_next_run(task)
        
        finally:
            # Save task and execution
            self._save_task(task)
            self._save_execution(execution)
            
            # Remove from running tasks
            if task.id in self.running_tasks:
                del self.running_tasks[task.id]
    
    def _calculate_next_run(self, task: ScheduledTask) -> Optional[datetime]:
        """Calculate next run time for a task"""
        now = datetime.now(timezone.utc)
        
        if task.schedule_type == ScheduleType.ONE_TIME:
            # One-time tasks don't repeat
            return None
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            if task.interval_seconds:
                return now + timedelta(seconds=task.interval_seconds)
        
        elif task.schedule_type == ScheduleType.CRON:
            if task.cron_expression:
                try:
                    cron = croniter(task.cron_expression, now)
                    return cron.get_next(datetime)
                except Exception as e:
                    self.logger.error(f"Invalid cron expression for task {task.name}: {e}")
        
        return None
    
    def _save_task(self, task: ScheduledTask):
        """Save task to database"""
        try:
            data = task.to_dict()
            
            # Convert datetime fields to ISO strings
            for field in ['scheduled_time', 'last_run', 'next_run', 'created_at']:
                if data[field]:
                    if isinstance(data[field], datetime):
                        data[field] = data[field].isoformat()
            
            query = """
                INSERT OR REPLACE INTO scheduled_tasks 
                (id, name, task_type, schedule_type, cron_expression, interval_seconds,
                 scheduled_time, parameters, status, last_run, next_run, run_count,
                 failure_count, last_error, created_at, created_by, max_failures, timeout_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.db.execute_update(query, (
                data['id'], data['name'], data['task_type'], data['schedule_type'],
                data['cron_expression'], data['interval_seconds'], data['scheduled_time'],
                data['parameters'], data['status'], data['last_run'], data['next_run'],
                data['run_count'], data['failure_count'], data['last_error'],
                data['created_at'], data['created_by'], data['max_failures'], data['timeout_seconds']
            ))
            
        except Exception as e:
            self.logger.error(f"Error saving task {task.id}: {e}")
    
    def _save_execution(self, execution: TaskExecution):
        """Save task execution to database"""
        try:
            data = execution.to_dict()
            
            query = """
                INSERT INTO task_executions 
                (id, task_id, started_at, completed_at, status, result, error, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.db.execute_update(query, (
                data['id'], data['task_id'], data['started_at'], data['completed_at'],
                data['status'], data['result'], data['error'], data['duration_seconds']
            ))
            
        except Exception as e:
            self.logger.error(f"Error saving execution {execution.id}: {e}")
    
    async def _cleanup_old_executions(self):
        """Clean up old task executions"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.cleanup_days)
            
            deleted = self.db.execute_update(
                "DELETE FROM task_executions WHERE started_at < ?",
                (cutoff_date.isoformat(),)
            )
            
            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} old task executions")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up executions: {e}")
    
    # Task Handlers
    async def _handle_broadcast_task(self, task: ScheduledTask) -> str:
        """Handle broadcast task"""
        # This would integrate with the message router to send broadcasts
        message = task.parameters.get('message', 'Scheduled broadcast')
        channel = task.parameters.get('channel')
        
        # TODO: Integrate with message router
        self.logger.info(f"Broadcasting message: {message}")
        return f"Broadcast sent: {message}"
    
    async def _handle_weather_update_task(self, task: ScheduledTask) -> str:
        """Handle weather update task"""
        # This would integrate with the weather service
        location = task.parameters.get('location', 'default')
        
        # TODO: Integrate with weather service
        self.logger.info(f"Updating weather for location: {location}")
        return f"Weather updated for {location}"
    
    async def _handle_bbs_sync_task(self, task: ScheduledTask) -> str:
        """Handle BBS synchronization task"""
        # This would integrate with the BBS service
        peer_nodes = task.parameters.get('peer_nodes', [])
        
        # TODO: Integrate with BBS service
        self.logger.info(f"Synchronizing BBS with peers: {peer_nodes}")
        return f"BBS sync completed with {len(peer_nodes)} peers"
    
    async def _handle_maintenance_task(self, task: ScheduledTask) -> str:
        """Handle maintenance task"""
        maintenance_type = task.parameters.get('type', 'cleanup')
        
        if maintenance_type == 'cleanup':
            # Database cleanup
            self.db.cleanup_expired_data()
            return "Database cleanup completed"
        
        elif maintenance_type == 'backup':
            # Database backup
            backup_path = self.db.backup_database()
            return f"Database backed up to {backup_path}"
        
        else:
            return f"Unknown maintenance type: {maintenance_type}"
    
    async def _handle_custom_task(self, task: ScheduledTask) -> str:
        """Handle custom task"""
        # Custom tasks would be handled by plugins or external handlers
        self.logger.info(f"Executing custom task: {task.name}")
        return f"Custom task {task.name} executed"
    
    # Public API methods
    def create_task(self, name: str, task_type: TaskType, schedule_type: ScheduleType,
                   cron_expression: Optional[str] = None, interval_seconds: Optional[int] = None,
                   scheduled_time: Optional[datetime] = None, parameters: Dict[str, Any] = None,
                   created_by: str = "", max_failures: int = 3, timeout_seconds: int = 300) -> str:
        """Create a new scheduled task"""
        try:
            task_id = str(uuid.uuid4())
            
            task = ScheduledTask(
                id=task_id,
                name=name,
                task_type=task_type,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                interval_seconds=interval_seconds,
                scheduled_time=scheduled_time,
                parameters=parameters or {},
                created_by=created_by,
                max_failures=max_failures,
                timeout_seconds=timeout_seconds
            )
            
            # Calculate next run time
            task.next_run = self._calculate_next_run(task)
            
            # Save task
            self.tasks[task_id] = task
            self._save_task(task)
            
            self.logger.info(f"Created scheduled task: {name}")
            return task_id
            
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            return ""
    
    def get_tasks(self, active_only: bool = False) -> List[ScheduledTask]:
        """Get all scheduled tasks"""
        tasks = list(self.tasks.values())
        if active_only:
            tasks = [t for t in tasks if t.status == TaskStatus.ACTIVE]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a specific task"""
        return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """Update a scheduled task"""
        try:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            allowed_fields = {
                'name', 'cron_expression', 'interval_seconds', 'scheduled_time',
                'parameters', 'status', 'max_failures', 'timeout_seconds'
            }
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(task, field, value)
            
            # Recalculate next run if schedule changed
            if any(field in kwargs for field in ['cron_expression', 'interval_seconds', 'scheduled_time']):
                task.next_run = self._calculate_next_run(task)
            
            self._save_task(task)
            self.logger.info(f"Updated task {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating task {task_id}: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a scheduled task"""
        try:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = TaskStatus.CANCELLED
                self._save_task(task)
                del self.tasks[task_id]
                
                # Cancel if currently running
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()
                
                self.logger.info(f"Deleted task: {task.name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting task {task_id}: {e}")
            return False
    
    def get_task_executions(self, task_id: str, limit: int = 50) -> List[TaskExecution]:
        """Get execution history for a task"""
        try:
            query = """
                SELECT * FROM task_executions 
                WHERE task_id = ? 
                ORDER BY started_at DESC 
                LIMIT ?
            """
            
            rows = self.db.execute_query(query, (task_id, limit))
            
            executions = []
            for row in rows:
                execution = TaskExecution(
                    id=row['id'],
                    task_id=row['task_id'],
                    started_at=datetime.fromisoformat(row['started_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    status=TaskStatus(row['status']),
                    result=row['result'],
                    error=row['error'],
                    duration_seconds=row['duration_seconds']
                )
                executions.append(execution)
            
            return executions
            
        except Exception as e:
            self.logger.error(f"Error getting executions for task {task_id}: {e}")
            return []
    
    async def _handle_schedule_command(self, message: str, sender_id: str) -> str:
        """Handle schedule command"""
        # Basic schedule command handling
        return "📅 Schedule commands: create, list, delete, status"
    
    async def _handle_tasks_command(self, message: str, sender_id: str) -> str:
        """Handle tasks command"""
        parts = message.split(' ', 1)
        
        if len(parts) == 1 or parts[1] == 'list':
            # List active tasks
            tasks = self.get_tasks(active_only=True)
            if not tasks:
                return "📅 No active scheduled tasks"
            
            response = "📅 **ACTIVE TASKS**\n"
            for task in tasks[:10]:  # Limit to 10
                next_run = task.next_run.strftime("%m/%d %H:%M") if task.next_run else "N/A"
                response += f"• {task.name} ({task.task_type.value}) - Next: {next_run}\n"
            
            if len(tasks) > 10:
                response += f"... and {len(tasks) - 10} more"
            
            return response
        
        return "📅 Tasks commands: list"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        try:
            active_tasks = len([t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE])
            running_tasks = len(self.running_tasks)
            
            return {
                'status': 'healthy',
                'service': 'scheduling',
                'running': self.running,
                'active_tasks': active_tasks,
                'running_tasks': running_tasks,
                'max_concurrent_tasks': self.max_concurrent_tasks,
                'check_interval': self.check_interval
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'service': 'scheduling',
                'error': str(e),
                'running': self.running
            }