"""
Scheduled Task Management

Provides integration between the scheduling service and other system services
for automated broadcasts, weather updates, BBS synchronization, and maintenance.
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from services.asset.scheduling_service import SchedulingService, TaskType, ScheduleType, ScheduledTask
from core.database import get_database


@dataclass
class TaskTemplate:
    """Template for creating scheduled tasks"""
    name: str
    task_type: TaskType
    description: str
    default_parameters: Dict[str, Any]
    schedule_examples: List[str]
    required_permissions: List[str] = None


class TaskManager:
    """
    Manages scheduled tasks and provides integration with other services
    """
    
    def __init__(self, scheduling_service: SchedulingService, config: Dict[str, Any]):
        self.scheduling_service = scheduling_service
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        
        # Service integrations (will be set by main application)
        self.message_router = None
        self.weather_service = None
        self.bbs_service = None
        
        # Task templates
        self.task_templates = self._create_task_templates()
        
        # Register custom task handlers
        self._register_task_handlers()
        
        self.logger.info("Task Manager initialized")
    
    def set_service_integrations(self, message_router=None, weather_service=None, bbs_service=None):
        """Set service integrations for task execution"""
        self.message_router = message_router
        self.weather_service = weather_service
        self.bbs_service = bbs_service
    
    def _create_task_templates(self) -> Dict[str, TaskTemplate]:
        """Create predefined task templates"""
        templates = {}
        
        # Broadcast templates
        templates['daily_checkin'] = TaskTemplate(
            name="Daily Check-in Reminder",
            task_type=TaskType.BROADCAST,
            description="Send daily check-in reminder to all users",
            default_parameters={
                'message': '📋 Daily check-in reminder: Please respond with your status and location.',
                'channel': None,
                'interface_id': None
            },
            schedule_examples=['0 8 * * *', '0 20 * * *'],  # 8 AM and 8 PM daily
            required_permissions=['broadcast']
        )
        
        templates['weather_broadcast'] = TaskTemplate(
            name="Weather Update Broadcast",
            task_type=TaskType.WEATHER_UPDATE,
            description="Broadcast weather updates to subscribed users",
            default_parameters={
                'location': 'default',
                'include_forecast': True,
                'include_alerts': True
            },
            schedule_examples=['0 6,18 * * *', '0 */6 * * *'],  # Every 6 hours
            required_permissions=['weather', 'broadcast']
        )
        
        templates['bbs_sync'] = TaskTemplate(
            name="BBS Synchronization",
            task_type=TaskType.BBS_SYNC,
            description="Synchronize BBS data with peer nodes",
            default_parameters={
                'peer_nodes': [],
                'sync_bulletins': True,
                'sync_mail': True,
                'sync_channels': True
            },
            schedule_examples=['0 */4 * * *', '0 2,14 * * *'],  # Every 4 hours
            required_permissions=['bbs', 'admin']
        )
        
        templates['maintenance_cleanup'] = TaskTemplate(
            name="Database Cleanup",
            task_type=TaskType.MAINTENANCE,
            description="Clean up old database records and optimize storage",
            default_parameters={
                'type': 'cleanup',
                'cleanup_days': 30,
                'vacuum_db': True
            },
            schedule_examples=['0 2 * * 0', '0 3 1 * *'],  # Weekly or monthly
            required_permissions=['admin']
        )
        
        templates['backup'] = TaskTemplate(
            name="Database Backup",
            task_type=TaskType.MAINTENANCE,
            description="Create database backup",
            default_parameters={
                'type': 'backup',
                'compress': True,
                'cleanup_old': True
            },
            schedule_examples=['0 1 * * *', '0 2 * * 0'],  # Daily or weekly
            required_permissions=['admin']
        )
        
        templates['network_test'] = TaskTemplate(
            name="Network Test Broadcast",
            task_type=TaskType.BROADCAST,
            description="Send network test message for connectivity verification",
            default_parameters={
                'message': '📡 Network test - Please acknowledge if you receive this message.',
                'channel': None,
                'interface_id': None
            },
            schedule_examples=['0 */12 * * *', '0 6,18 * * *'],  # Twice daily
            required_permissions=['broadcast']
        )
        
        templates['emergency_drill'] = TaskTemplate(
            name="Emergency Communication Drill",
            task_type=TaskType.BROADCAST,
            description="Conduct emergency communication drill",
            default_parameters={
                'message': '🚨 DRILL: Emergency communication test. Please respond with your status. This is only a drill.',
                'channel': None,
                'interface_id': None
            },
            schedule_examples=['0 10 1 * *', '0 14 15 * *'],  # Monthly
            required_permissions=['emergency', 'broadcast']
        )
        
        return templates
    
    def _register_task_handlers(self):
        """Register custom task handlers with the scheduling service"""
        # Override default handlers with integrated versions
        self.scheduling_service.task_handlers[TaskType.BROADCAST] = self._handle_integrated_broadcast
        self.scheduling_service.task_handlers[TaskType.WEATHER_UPDATE] = self._handle_integrated_weather_update
        self.scheduling_service.task_handlers[TaskType.BBS_SYNC] = self._handle_integrated_bbs_sync
        self.scheduling_service.task_handlers[TaskType.MAINTENANCE] = self._handle_integrated_maintenance
    
    async def _handle_integrated_broadcast(self, task: ScheduledTask) -> str:
        """Handle broadcast task with message router integration"""
        try:
            message = task.parameters.get('message', 'Scheduled broadcast')
            channel = task.parameters.get('channel')
            interface_id = task.parameters.get('interface_id')
            
            if self.message_router:
                # Send through message router
                success = await self.message_router.send_broadcast(
                    content=message,
                    channel=channel,
                    interface_id=interface_id
                )
                
                if success:
                    self.logger.info(f"Broadcast sent successfully: {message[:50]}...")
                    return f"Broadcast sent: {message[:100]}..."
                else:
                    raise Exception("Failed to send broadcast through message router")
            else:
                # Fallback: log the message
                self.logger.info(f"Would broadcast: {message}")
                return f"Broadcast logged: {message[:100]}..."
                
        except Exception as e:
            self.logger.error(f"Error in integrated broadcast: {e}")
            raise
    
    async def _handle_integrated_weather_update(self, task: ScheduledTask) -> str:
        """Handle weather update task with weather service integration"""
        try:
            location = task.parameters.get('location', 'default')
            include_forecast = task.parameters.get('include_forecast', True)
            include_alerts = task.parameters.get('include_alerts', True)
            
            if self.weather_service:
                # Get weather data from weather service
                weather_data = await self.weather_service.get_current_weather(location)
                
                if weather_data:
                    # Format weather message
                    message = self._format_weather_message(weather_data, include_forecast, include_alerts)
                    
                    # Send weather broadcast
                    if self.message_router:
                        success = await self.message_router.send_broadcast(
                            content=message,
                            channel=task.parameters.get('channel'),
                            interface_id=task.parameters.get('interface_id')
                        )
                        
                        if success:
                            return f"Weather update broadcast sent for {location}"
                        else:
                            raise Exception("Failed to send weather broadcast")
                    else:
                        self.logger.info(f"Weather update: {message}")
                        return f"Weather update logged for {location}"
                else:
                    raise Exception(f"No weather data available for {location}")
            else:
                # Fallback: basic weather message
                message = f"🌤️ Weather update for {location} - Service not available"
                self.logger.info(f"Weather service not available: {message}")
                return f"Weather service unavailable for {location}"
                
        except Exception as e:
            self.logger.error(f"Error in integrated weather update: {e}")
            raise
    
    async def _handle_integrated_bbs_sync(self, task: ScheduledTask) -> str:
        """Handle BBS sync task with BBS service integration"""
        try:
            peer_nodes = task.parameters.get('peer_nodes', [])
            sync_bulletins = task.parameters.get('sync_bulletins', True)
            sync_mail = task.parameters.get('sync_mail', True)
            sync_channels = task.parameters.get('sync_channels', True)
            
            if self.bbs_service:
                # Perform BBS synchronization
                sync_results = await self.bbs_service.sync_with_peers(
                    peer_nodes=peer_nodes,
                    sync_bulletins=sync_bulletins,
                    sync_mail=sync_mail,
                    sync_channels=sync_channels
                )
                
                synced_count = len(sync_results.get('synced_peers', []))
                failed_count = len(sync_results.get('failed_peers', []))
                
                result_msg = f"BBS sync completed: {synced_count} successful, {failed_count} failed"
                self.logger.info(result_msg)
                return result_msg
            else:
                # Fallback: log sync attempt
                self.logger.info(f"BBS sync requested for peers: {peer_nodes}")
                return f"BBS service not available - sync logged for {len(peer_nodes)} peers"
                
        except Exception as e:
            self.logger.error(f"Error in integrated BBS sync: {e}")
            raise
    
    async def _handle_integrated_maintenance(self, task: ScheduledTask) -> str:
        """Handle maintenance task with enhanced functionality"""
        try:
            maintenance_type = task.parameters.get('type', 'cleanup')
            
            if maintenance_type == 'cleanup':
                cleanup_days = task.parameters.get('cleanup_days', 30)
                vacuum_db = task.parameters.get('vacuum_db', False)
                
                # Perform database cleanup
                self.db.cleanup_expired_data()
                
                # Additional cleanup for asset tracking
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=cleanup_days)
                deleted_checkins = self.db.execute_update(
                    "DELETE FROM checklist WHERE timestamp < ?",
                    (cutoff_date.isoformat(),)
                )
                
                deleted_executions = self.db.execute_update(
                    "DELETE FROM task_executions WHERE started_at < ?",
                    (cutoff_date.isoformat(),)
                )
                
                result_msg = f"Cleanup completed: {deleted_checkins} checklist records, {deleted_executions} task executions"
                
                # Vacuum database if requested
                if vacuum_db:
                    with self.db.get_connection() as conn:
                        conn.execute("VACUUM")
                    result_msg += ", database vacuumed"
                
                self.logger.info(result_msg)
                return result_msg
                
            elif maintenance_type == 'backup':
                compress = task.parameters.get('compress', True)
                cleanup_old = task.parameters.get('cleanup_old', True)
                
                # Create database backup
                backup_path = self.db.backup_database()
                
                # TODO: Add compression and old backup cleanup if needed
                
                result_msg = f"Database backed up to {backup_path}"
                self.logger.info(result_msg)
                return result_msg
                
            else:
                raise Exception(f"Unknown maintenance type: {maintenance_type}")
                
        except Exception as e:
            self.logger.error(f"Error in integrated maintenance: {e}")
            raise
    
    def _format_weather_message(self, weather_data: Dict[str, Any], 
                               include_forecast: bool, include_alerts: bool) -> str:
        """Format weather data into a broadcast message"""
        try:
            message = "🌤️ **WEATHER UPDATE**\n"
            
            # Current conditions
            if 'current' in weather_data:
                current = weather_data['current']
                temp = current.get('temperature', 'N/A')
                conditions = current.get('conditions', 'N/A')
                humidity = current.get('humidity', 'N/A')
                wind = current.get('wind_speed', 'N/A')
                
                message += f"Current: {temp}°F, {conditions}\n"
                message += f"Humidity: {humidity}%, Wind: {wind} mph\n"
            
            # Forecast
            if include_forecast and 'forecast' in weather_data:
                forecast = weather_data['forecast']
                if forecast:
                    message += f"\nToday: {forecast[0].get('summary', 'N/A')}\n"
                    message += f"High: {forecast[0].get('high', 'N/A')}°F, Low: {forecast[0].get('low', 'N/A')}°F"
            
            # Alerts
            if include_alerts and 'alerts' in weather_data:
                alerts = weather_data['alerts']
                if alerts:
                    message += f"\n⚠️ ALERTS: {len(alerts)} active"
                    for alert in alerts[:2]:  # Limit to 2 alerts
                        message += f"\n• {alert.get('title', 'Alert')}"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting weather message: {e}")
            return "🌤️ Weather update - Error formatting data"
    
    # Public API methods
    def get_task_templates(self) -> Dict[str, TaskTemplate]:
        """Get available task templates"""
        return self.task_templates.copy()
    
    def create_task_from_template(self, template_name: str, name: str, 
                                 schedule_type: ScheduleType, schedule_value: str,
                                 parameters: Dict[str, Any] = None, 
                                 created_by: str = "") -> Optional[str]:
        """Create a task from a template"""
        try:
            template = self.task_templates.get(template_name)
            if not template:
                self.logger.error(f"Unknown template: {template_name}")
                return None
            
            # Merge parameters with template defaults
            task_parameters = template.default_parameters.copy()
            if parameters:
                task_parameters.update(parameters)
            
            # Determine schedule parameters
            cron_expression = None
            interval_seconds = None
            scheduled_time = None
            
            if schedule_type == ScheduleType.CRON:
                cron_expression = schedule_value
            elif schedule_type == ScheduleType.INTERVAL:
                interval_seconds = int(schedule_value)
            elif schedule_type == ScheduleType.ONE_TIME:
                scheduled_time = datetime.fromisoformat(schedule_value)
            
            # Create the task
            task_id = self.scheduling_service.create_task(
                name=name,
                task_type=template.task_type,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                interval_seconds=interval_seconds,
                scheduled_time=scheduled_time,
                parameters=task_parameters,
                created_by=created_by
            )
            
            if task_id:
                self.logger.info(f"Created task from template {template_name}: {name}")
            
            return task_id
            
        except Exception as e:
            self.logger.error(f"Error creating task from template: {e}")
            return None
    
    def create_weather_broadcast_task(self, name: str, cron_expression: str, 
                                    location: str = 'default', created_by: str = "") -> Optional[str]:
        """Create a weather broadcast task"""
        return self.create_task_from_template(
            template_name='weather_broadcast',
            name=name,
            schedule_type=ScheduleType.CRON,
            schedule_value=cron_expression,
            parameters={'location': location},
            created_by=created_by
        )
    
    def create_bbs_sync_task(self, name: str, cron_expression: str, 
                           peer_nodes: List[str], created_by: str = "") -> Optional[str]:
        """Create a BBS synchronization task"""
        return self.create_task_from_template(
            template_name='bbs_sync',
            name=name,
            schedule_type=ScheduleType.CRON,
            schedule_value=cron_expression,
            parameters={'peer_nodes': peer_nodes},
            created_by=created_by
        )
    
    def create_maintenance_task(self, name: str, cron_expression: str, 
                              maintenance_type: str = 'cleanup', created_by: str = "") -> Optional[str]:
        """Create a maintenance task"""
        return self.create_task_from_template(
            template_name='maintenance_cleanup' if maintenance_type == 'cleanup' else 'backup',
            name=name,
            schedule_type=ScheduleType.CRON,
            schedule_value=cron_expression,
            parameters={'type': maintenance_type},
            created_by=created_by
        )
    
    def get_active_tasks_summary(self) -> Dict[str, Any]:
        """Get summary of active tasks"""
        try:
            tasks = self.scheduling_service.get_tasks(active_only=True)
            
            summary = {
                'total_active': len(tasks),
                'by_type': {},
                'upcoming': [],
                'recent_failures': []
            }
            
            # Count by type
            for task in tasks:
                task_type = task.task_type.value
                summary['by_type'][task_type] = summary['by_type'].get(task_type, 0) + 1
            
            # Get upcoming tasks (next 24 hours)
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=24)
            
            for task in tasks:
                if task.next_run and now <= task.next_run <= cutoff:
                    summary['upcoming'].append({
                        'name': task.name,
                        'type': task.task_type.value,
                        'next_run': task.next_run.isoformat()
                    })
            
            # Get recent failures
            for task in tasks:
                if task.failure_count > 0:
                    summary['recent_failures'].append({
                        'name': task.name,
                        'failure_count': task.failure_count,
                        'last_error': task.last_error
                    })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting tasks summary: {e}")
            return {'error': str(e)}
    
    async def execute_task_now(self, task_id: str) -> bool:
        """Execute a task immediately (manual trigger)"""
        try:
            task = self.scheduling_service.get_task(task_id)
            if not task:
                return False
            
            # Execute the task
            await self.scheduling_service._execute_task(task)
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing task {task_id}: {e}")
            return False