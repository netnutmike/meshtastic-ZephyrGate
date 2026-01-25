"""
Broadcast Scheduling Module for Web Administration

Provides message scheduling, broadcast history, and template management.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

try:
    from ...models.message import Message, MessageType
except ImportError:
    from models.message import Message, MessageType


logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Types of scheduled broadcasts"""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    INTERVAL = "interval"


class RecurrencePattern(Enum):
    """Recurrence patterns for scheduled broadcasts"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"


class BroadcastStatus(Enum):
    """Status of broadcast messages"""
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MessageTemplate:
    """Message template for reusable broadcasts"""
    id: str
    name: str
    content: str
    description: str
    variables: List[str] = field(default_factory=list)
    category: str = "general"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    usage_count: int = 0


@dataclass
class ScheduledBroadcast:
    """Scheduled broadcast message"""
    id: str
    name: str
    content: str
    channel: Optional[int] = None
    interface_id: Optional[str] = None
    schedule_type: ScheduleType = ScheduleType.ONE_TIME
    scheduled_time: Optional[datetime] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    interval_minutes: Optional[int] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    is_active: bool = True
    template_id: Optional[str] = None
    variables: Dict[str, str] = field(default_factory=dict)
    
    # Execution tracking
    last_sent: Optional[datetime] = None
    next_send: Optional[datetime] = None
    send_count: int = 0
    status: BroadcastStatus = BroadcastStatus.SCHEDULED


@dataclass
class BroadcastHistory:
    """History record of sent broadcasts"""
    id: str
    schedule_id: Optional[str]
    content: str
    channel: Optional[int]
    interface_id: Optional[str]
    sent_at: datetime
    sent_by: str
    status: BroadcastStatus
    error_message: Optional[str] = None
    recipient_count: int = 0


class BroadcastScheduler:
    """
    Broadcast scheduling service for managing scheduled messages,
    templates, and broadcast history.
    """
    
    def __init__(self, message_sender: Optional[Callable] = None):
        self.message_sender = message_sender
        self.logger = logger
        
        # Storage
        self.scheduled_broadcasts: Dict[str, ScheduledBroadcast] = {}
        self.message_templates: Dict[str, MessageTemplate] = {}
        self.broadcast_history: List[BroadcastHistory] = []
        
        # Configuration
        self.history_limit = 1000
        self.check_interval = 60  # Check every minute
        
        # Scheduler task
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Default templates
        self._create_default_templates()
        
        self.logger.info("BroadcastScheduler initialized")
    
    def _create_default_templates(self):
        """Create default message templates"""
        default_templates = [
            {
                "name": "Weather Alert",
                "content": "⚠️ Weather Alert: {alert_type} - {message}",
                "description": "Template for weather alerts",
                "variables": ["alert_type", "message"],
                "category": "weather"
            },
            {
                "name": "System Maintenance",
                "content": "🔧 System Maintenance: {service} will be unavailable from {start_time} to {end_time}",
                "description": "Template for maintenance notifications",
                "variables": ["service", "start_time", "end_time"],
                "category": "system"
            },
            {
                "name": "Emergency Broadcast",
                "content": "🚨 EMERGENCY: {message} - Please respond if you receive this.",
                "description": "Template for emergency broadcasts",
                "variables": ["message"],
                "category": "emergency"
            },
            {
                "name": "Daily Check-in",
                "content": "📋 Daily check-in: Please respond with your status and location.",
                "description": "Template for daily status checks",
                "variables": [],
                "category": "routine"
            },
            {
                "name": "Network Test",
                "content": "📡 Network test message sent at {timestamp} - Please acknowledge receipt.",
                "description": "Template for network testing",
                "variables": ["timestamp"],
                "category": "testing"
            }
        ]
        
        for template_data in default_templates:
            template = MessageTemplate(
                id=str(uuid.uuid4()),
                name=template_data["name"],
                content=template_data["content"],
                description=template_data["description"],
                variables=template_data["variables"],
                category=template_data["category"],
                created_by="system"
            )
            self.message_templates[template.id] = template
    
    async def start(self):
        """Start the scheduler"""
        try:
            self.is_running = True
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            self.logger.info("Broadcast scheduler started")
            
        except Exception as e:
            self.logger.error(f"Failed to start broadcast scheduler: {e}")
            raise
    
    async def stop(self):
        """Stop the scheduler"""
        try:
            self.is_running = False
            
            if self.scheduler_task:
                self.scheduler_task.cancel()
                try:
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("Broadcast scheduler stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping broadcast scheduler: {e}")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                await self._check_scheduled_broadcasts()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_scheduled_broadcasts(self):
        """Check for broadcasts that need to be sent"""
        now = datetime.now(timezone.utc)
        
        for broadcast in list(self.scheduled_broadcasts.values()):
            if not broadcast.is_active:
                continue
            
            should_send = False
            
            # Check if it's time to send
            if broadcast.schedule_type == ScheduleType.ONE_TIME:
                if broadcast.scheduled_time and broadcast.scheduled_time <= now and broadcast.send_count == 0:
                    should_send = True
            
            elif broadcast.schedule_type == ScheduleType.RECURRING:
                if broadcast.next_send and broadcast.next_send <= now:
                    should_send = True
            
            elif broadcast.schedule_type == ScheduleType.INTERVAL:
                if broadcast.last_sent:
                    next_time = broadcast.last_sent + timedelta(minutes=broadcast.interval_minutes or 60)
                    if next_time <= now:
                        should_send = True
                elif broadcast.scheduled_time and broadcast.scheduled_time <= now:
                    should_send = True
            
            # Check limits
            if should_send:
                if broadcast.end_date and now > broadcast.end_date:
                    broadcast.is_active = False
                    continue
                
                if broadcast.max_occurrences and broadcast.send_count >= broadcast.max_occurrences:
                    broadcast.is_active = False
                    continue
                
                # Send the broadcast
                await self._send_scheduled_broadcast(broadcast)
    
    async def _send_scheduled_broadcast(self, broadcast: ScheduledBroadcast):
        """Send a scheduled broadcast"""
        try:
            # Prepare message content
            content = self._prepare_message_content(broadcast)
            
            # Send message
            success = False
            error_message = None
            
            if self.message_sender:
                try:
                    success = await self.message_sender(
                        content=content,
                        channel=broadcast.channel,
                        interface_id=broadcast.interface_id
                    )
                except Exception as e:
                    error_message = str(e)
                    self.logger.error(f"Error sending broadcast {broadcast.id}: {e}")
            else:
                # No message sender configured - just log
                self.logger.info(f"Would send broadcast: {content}")
                success = True
            
            # Update broadcast status
            now = datetime.now(timezone.utc)
            broadcast.last_sent = now
            broadcast.send_count += 1
            
            if success:
                broadcast.status = BroadcastStatus.SENT
            else:
                broadcast.status = BroadcastStatus.FAILED
            
            # Calculate next send time for recurring broadcasts
            if broadcast.schedule_type == ScheduleType.RECURRING and broadcast.recurrence_pattern:
                broadcast.next_send = self._calculate_next_send_time(broadcast, now)
            elif broadcast.schedule_type == ScheduleType.INTERVAL:
                broadcast.next_send = now + timedelta(minutes=broadcast.interval_minutes or 60)
            
            # Add to history
            history_entry = BroadcastHistory(
                id=str(uuid.uuid4()),
                schedule_id=broadcast.id,
                content=content,
                channel=broadcast.channel,
                interface_id=broadcast.interface_id,
                sent_at=now,
                sent_by=broadcast.created_by,
                status=BroadcastStatus.SENT if success else BroadcastStatus.FAILED,
                error_message=error_message,
                recipient_count=0  # Would be populated by actual message sender
            )
            
            self.broadcast_history.append(history_entry)
            
            # Limit history size
            if len(self.broadcast_history) > self.history_limit:
                self.broadcast_history.pop(0)
            
            self.logger.info(f"Sent scheduled broadcast {broadcast.id}: {broadcast.name}")
            
        except Exception as e:
            self.logger.error(f"Error sending scheduled broadcast {broadcast.id}: {e}")
            broadcast.status = BroadcastStatus.FAILED
    
    def _prepare_message_content(self, broadcast: ScheduledBroadcast) -> str:
        """Prepare message content with variable substitution"""
        content = broadcast.content
        
        # Substitute variables
        variables = broadcast.variables.copy()
        
        # Add automatic variables
        variables.update({
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "broadcast_name": broadcast.name
        })
        
        # Perform substitution
        for var_name, var_value in variables.items():
            placeholder = "{" + var_name + "}"
            content = content.replace(placeholder, str(var_value))
        
        return content
    
    def _calculate_next_send_time(self, broadcast: ScheduledBroadcast, current_time: datetime) -> datetime:
        """Calculate next send time for recurring broadcasts"""
        if not broadcast.recurrence_pattern:
            return current_time
        
        if broadcast.recurrence_pattern == RecurrencePattern.DAILY:
            return current_time + timedelta(days=1)
        
        elif broadcast.recurrence_pattern == RecurrencePattern.WEEKLY:
            return current_time + timedelta(weeks=1)
        
        elif broadcast.recurrence_pattern == RecurrencePattern.MONTHLY:
            # Add one month (approximate)
            if current_time.month == 12:
                return current_time.replace(year=current_time.year + 1, month=1)
            else:
                return current_time.replace(month=current_time.month + 1)
        
        elif broadcast.recurrence_pattern == RecurrencePattern.WEEKDAYS:
            # Next weekday
            next_time = current_time + timedelta(days=1)
            while next_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                next_time += timedelta(days=1)
            return next_time
        
        elif broadcast.recurrence_pattern == RecurrencePattern.WEEKENDS:
            # Next weekend day
            next_time = current_time + timedelta(days=1)
            while next_time.weekday() < 5:  # Monday = 0, Friday = 4
                next_time += timedelta(days=1)
            return next_time
        
        return current_time + timedelta(days=1)
    
    def create_template(self, name: str, content: str, description: str = "", 
                       variables: List[str] = None, category: str = "general", 
                       created_by: str = "") -> str:
        """Create a new message template"""
        try:
            template_id = str(uuid.uuid4())
            
            template = MessageTemplate(
                id=template_id,
                name=name,
                content=content,
                description=description,
                variables=variables or [],
                category=category,
                created_by=created_by
            )
            
            self.message_templates[template_id] = template
            self.logger.info(f"Created message template: {name}")
            
            return template_id
            
        except Exception as e:
            self.logger.error(f"Error creating template: {e}")
            return ""
    
    def update_template(self, template_id: str, **kwargs) -> bool:
        """Update a message template"""
        try:
            template = self.message_templates.get(template_id)
            if not template:
                return False
            
            allowed_fields = {'name', 'content', 'description', 'variables', 'category'}
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(template, field, value)
            
            self.logger.info(f"Updated template {template_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating template {template_id}: {e}")
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a message template"""
        try:
            if template_id in self.message_templates:
                template = self.message_templates[template_id]
                del self.message_templates[template_id]
                self.logger.info(f"Deleted template: {template.name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting template {template_id}: {e}")
            return False
    
    def schedule_broadcast(self, name: str, content: str, scheduled_time: datetime,
                          channel: Optional[int] = None, interface_id: Optional[str] = None,
                          schedule_type: ScheduleType = ScheduleType.ONE_TIME,
                          recurrence_pattern: Optional[RecurrencePattern] = None,
                          interval_minutes: Optional[int] = None,
                          end_date: Optional[datetime] = None,
                          max_occurrences: Optional[int] = None,
                          template_id: Optional[str] = None,
                          variables: Dict[str, str] = None,
                          created_by: str = "") -> str:
        """Schedule a new broadcast"""
        try:
            broadcast_id = str(uuid.uuid4())
            
            # If using template, get content from template
            if template_id and template_id in self.message_templates:
                template = self.message_templates[template_id]
                content = template.content
                template.usage_count += 1
            
            broadcast = ScheduledBroadcast(
                id=broadcast_id,
                name=name,
                content=content,
                channel=channel,
                interface_id=interface_id,
                schedule_type=schedule_type,
                scheduled_time=scheduled_time,
                recurrence_pattern=recurrence_pattern,
                interval_minutes=interval_minutes,
                end_date=end_date,
                max_occurrences=max_occurrences,
                created_by=created_by,
                template_id=template_id,
                variables=variables or {}
            )
            
            # Calculate next send time for recurring broadcasts
            if schedule_type == ScheduleType.RECURRING and recurrence_pattern:
                broadcast.next_send = scheduled_time
            elif schedule_type == ScheduleType.INTERVAL:
                broadcast.next_send = scheduled_time
            
            self.scheduled_broadcasts[broadcast_id] = broadcast
            self.logger.info(f"Scheduled broadcast: {name} at {scheduled_time}")
            
            return broadcast_id
            
        except Exception as e:
            self.logger.error(f"Error scheduling broadcast: {e}")
            return ""
    
    def update_broadcast(self, broadcast_id: str, **kwargs) -> bool:
        """Update a scheduled broadcast"""
        try:
            broadcast = self.scheduled_broadcasts.get(broadcast_id)
            if not broadcast:
                return False
            
            allowed_fields = {
                'name', 'content', 'channel', 'interface_id', 'scheduled_time',
                'recurrence_pattern', 'interval_minutes', 'end_date', 
                'max_occurrences', 'is_active', 'variables'
            }
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(broadcast, field, value)
            
            # Recalculate next send time if schedule changed
            if 'scheduled_time' in kwargs or 'recurrence_pattern' in kwargs:
                if broadcast.schedule_type == ScheduleType.RECURRING and broadcast.recurrence_pattern:
                    broadcast.next_send = broadcast.scheduled_time
                elif broadcast.schedule_type == ScheduleType.INTERVAL:
                    broadcast.next_send = broadcast.scheduled_time
            
            self.logger.info(f"Updated broadcast {broadcast_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating broadcast {broadcast_id}: {e}")
            return False
    
    def cancel_broadcast(self, broadcast_id: str) -> bool:
        """Cancel a scheduled broadcast"""
        try:
            broadcast = self.scheduled_broadcasts.get(broadcast_id)
            if not broadcast:
                return False
            
            broadcast.is_active = False
            broadcast.status = BroadcastStatus.CANCELLED
            
            self.logger.info(f"Cancelled broadcast {broadcast_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling broadcast {broadcast_id}: {e}")
            return False
    
    def delete_broadcast(self, broadcast_id: str) -> bool:
        """Delete a scheduled broadcast"""
        try:
            if broadcast_id in self.scheduled_broadcasts:
                broadcast = self.scheduled_broadcasts[broadcast_id]
                del self.scheduled_broadcasts[broadcast_id]
                self.logger.info(f"Deleted broadcast: {broadcast.name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting broadcast {broadcast_id}: {e}")
            return False
    
    def get_scheduled_broadcasts(self, active_only: bool = False) -> List[ScheduledBroadcast]:
        """Get all scheduled broadcasts"""
        broadcasts = list(self.scheduled_broadcasts.values())
        if active_only:
            broadcasts = [b for b in broadcasts if b.is_active]
        return sorted(broadcasts, key=lambda b: b.created_at, reverse=True)
    
    def get_broadcast(self, broadcast_id: str) -> Optional[ScheduledBroadcast]:
        """Get a specific broadcast"""
        return self.scheduled_broadcasts.get(broadcast_id)
    
    def get_templates(self, category: Optional[str] = None) -> List[MessageTemplate]:
        """Get message templates"""
        templates = list(self.message_templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return sorted(templates, key=lambda t: t.name)
    
    def get_template(self, template_id: str) -> Optional[MessageTemplate]:
        """Get a specific template"""
        return self.message_templates.get(template_id)
    
    def get_broadcast_history(self, limit: int = 100) -> List[BroadcastHistory]:
        """Get broadcast history"""
        return sorted(self.broadcast_history[-limit:], key=lambda h: h.sent_at, reverse=True)
    
    def get_upcoming_broadcasts(self, hours: int = 24) -> List[ScheduledBroadcast]:
        """Get broadcasts scheduled in the next N hours"""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        
        upcoming = []
        for broadcast in self.scheduled_broadcasts.values():
            if not broadcast.is_active:
                continue
            
            next_time = None
            if broadcast.schedule_type == ScheduleType.ONE_TIME and broadcast.scheduled_time:
                if broadcast.send_count == 0:
                    next_time = broadcast.scheduled_time
            elif broadcast.next_send:
                next_time = broadcast.next_send
            
            if next_time and now <= next_time <= cutoff:
                upcoming.append(broadcast)
        
        return sorted(upcoming, key=lambda b: b.next_send or b.scheduled_time)
    
    async def send_immediate_broadcast(self, content: str, channel: Optional[int] = None,
                                     interface_id: Optional[str] = None, sent_by: str = "") -> bool:
        """Send an immediate broadcast"""
        try:
            success = False
            error_message = None
            
            if self.message_sender:
                try:
                    success = await self.message_sender(
                        content=content,
                        channel=channel,
                        interface_id=interface_id
                    )
                except Exception as e:
                    error_message = str(e)
                    self.logger.error(f"Error sending immediate broadcast: {e}")
            else:
                self.logger.info(f"Would send immediate broadcast: {content}")
                success = True
            
            # Add to history
            history_entry = BroadcastHistory(
                id=str(uuid.uuid4()),
                schedule_id=None,
                content=content,
                channel=channel,
                interface_id=interface_id,
                sent_at=datetime.now(timezone.utc),
                sent_by=sent_by,
                status=BroadcastStatus.SENT if success else BroadcastStatus.FAILED,
                error_message=error_message,
                recipient_count=0
            )
            
            self.broadcast_history.append(history_entry)
            
            # Limit history size
            if len(self.broadcast_history) > self.history_limit:
                self.broadcast_history.pop(0)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending immediate broadcast: {e}")
            return False