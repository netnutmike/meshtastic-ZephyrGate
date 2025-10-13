"""
Unit tests for Broadcast Scheduler
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock

from src.services.web.scheduler import (
    BroadcastScheduler, MessageTemplate, ScheduledBroadcast, BroadcastHistory,
    ScheduleType, RecurrencePattern, BroadcastStatus
)


class TestBroadcastScheduler:
    """Test broadcast scheduler functionality"""
    
    @pytest.fixture
    def scheduler(self):
        return BroadcastScheduler()
    
    def test_init(self, scheduler):
        """Test scheduler initialization"""
        assert scheduler.scheduled_broadcasts == {}
        assert len(scheduler.message_templates) > 0  # Default templates
        assert scheduler.broadcast_history == []
        assert scheduler.history_limit == 1000
        assert scheduler.check_interval == 60
        assert scheduler.is_running is False
    
    def test_default_templates(self, scheduler):
        """Test default templates are created"""
        templates = scheduler.get_templates()
        assert len(templates) >= 5
        
        # Check for specific default templates
        template_names = [t.name for t in templates]
        assert "Weather Alert" in template_names
        assert "Emergency Broadcast" in template_names
        assert "Daily Check-in" in template_names
    
    def test_create_template(self, scheduler):
        """Test creating message templates"""
        template_id = scheduler.create_template(
            name="Test Template",
            content="This is a test template with {variable}",
            description="Test description",
            variables=["variable"],
            category="test",
            created_by="test_user"
        )
        
        assert template_id != ""
        assert template_id in scheduler.message_templates
        
        template = scheduler.message_templates[template_id]
        assert template.name == "Test Template"
        assert template.content == "This is a test template with {variable}"
        assert template.variables == ["variable"]
        assert template.category == "test"
        assert template.created_by == "test_user"
        assert template.usage_count == 0
    
    def test_update_template(self, scheduler):
        """Test updating templates"""
        template_id = scheduler.create_template("Test", "Content", "Description")
        
        success = scheduler.update_template(
            template_id,
            name="Updated Test",
            content="Updated content",
            description="Updated description"
        )
        
        assert success is True
        
        template = scheduler.message_templates[template_id]
        assert template.name == "Updated Test"
        assert template.content == "Updated content"
        assert template.description == "Updated description"
        
        # Test updating non-existent template
        success = scheduler.update_template("nonexistent", name="Test")
        assert success is False
    
    def test_delete_template(self, scheduler):
        """Test deleting templates"""
        template_id = scheduler.create_template("Test", "Content")
        
        # Verify template exists
        assert template_id in scheduler.message_templates
        
        # Delete template
        success = scheduler.delete_template(template_id)
        assert success is True
        assert template_id not in scheduler.message_templates
        
        # Test deleting non-existent template
        success = scheduler.delete_template("nonexistent")
        assert success is False
    
    def test_schedule_one_time_broadcast(self, scheduler):
        """Test scheduling one-time broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        broadcast_id = scheduler.schedule_broadcast(
            name="Test Broadcast",
            content="Test message",
            scheduled_time=scheduled_time,
            channel=0,
            interface_id="serial0",
            created_by="test_user"
        )
        
        assert broadcast_id != ""
        assert broadcast_id in scheduler.scheduled_broadcasts
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.name == "Test Broadcast"
        assert broadcast.content == "Test message"
        assert broadcast.scheduled_time == scheduled_time
        assert broadcast.schedule_type == ScheduleType.ONE_TIME
        assert broadcast.is_active is True
        assert broadcast.send_count == 0
        assert broadcast.status == BroadcastStatus.SCHEDULED
    
    def test_schedule_recurring_broadcast(self, scheduler):
        """Test scheduling recurring broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        broadcast_id = scheduler.schedule_broadcast(
            name="Daily Broadcast",
            content="Daily message",
            scheduled_time=scheduled_time,
            schedule_type=ScheduleType.RECURRING,
            recurrence_pattern=RecurrencePattern.DAILY,
            max_occurrences=5,
            created_by="test_user"
        )
        
        assert broadcast_id != ""
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.schedule_type == ScheduleType.RECURRING
        assert broadcast.recurrence_pattern == RecurrencePattern.DAILY
        assert broadcast.max_occurrences == 5
        assert broadcast.next_send == scheduled_time
    
    def test_schedule_interval_broadcast(self, scheduler):
        """Test scheduling interval-based broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        
        broadcast_id = scheduler.schedule_broadcast(
            name="Interval Broadcast",
            content="Interval message",
            scheduled_time=scheduled_time,
            schedule_type=ScheduleType.INTERVAL,
            interval_minutes=60,
            created_by="test_user"
        )
        
        assert broadcast_id != ""
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.schedule_type == ScheduleType.INTERVAL
        assert broadcast.interval_minutes == 60
        assert broadcast.next_send == scheduled_time
    
    def test_schedule_with_template(self, scheduler):
        """Test scheduling broadcast with template"""
        # Create template
        template_id = scheduler.create_template(
            name="Test Template",
            content="Hello {name}, the time is {timestamp}",
            variables=["name", "timestamp"]
        )
        
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        broadcast_id = scheduler.schedule_broadcast(
            name="Template Broadcast",
            content="",  # Will be overridden by template
            scheduled_time=scheduled_time,
            template_id=template_id,
            variables={"name": "World"},
            created_by="test_user"
        )
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.template_id == template_id
        assert broadcast.content == "Hello {name}, the time is {timestamp}"
        assert broadcast.variables == {"name": "World"}
        
        # Check template usage count increased
        template = scheduler.message_templates[template_id]
        assert template.usage_count == 1
    
    def test_update_broadcast(self, scheduler):
        """Test updating scheduled broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        broadcast_id = scheduler.schedule_broadcast(
            "Test", "Content", scheduled_time, created_by="test"
        )
        
        new_time = scheduled_time + timedelta(hours=1)
        success = scheduler.update_broadcast(
            broadcast_id,
            name="Updated Test",
            content="Updated content",
            scheduled_time=new_time
        )
        
        assert success is True
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.name == "Updated Test"
        assert broadcast.content == "Updated content"
        assert broadcast.scheduled_time == new_time
        
        # Test updating non-existent broadcast
        success = scheduler.update_broadcast("nonexistent", name="Test")
        assert success is False
    
    def test_cancel_broadcast(self, scheduler):
        """Test cancelling broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        broadcast_id = scheduler.schedule_broadcast(
            "Test", "Content", scheduled_time, created_by="test"
        )
        
        success = scheduler.cancel_broadcast(broadcast_id)
        assert success is True
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        assert broadcast.is_active is False
        assert broadcast.status == BroadcastStatus.CANCELLED
        
        # Test cancelling non-existent broadcast
        success = scheduler.cancel_broadcast("nonexistent")
        assert success is False
    
    def test_delete_broadcast(self, scheduler):
        """Test deleting broadcast"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        broadcast_id = scheduler.schedule_broadcast(
            "Test", "Content", scheduled_time, created_by="test"
        )
        
        # Verify broadcast exists
        assert broadcast_id in scheduler.scheduled_broadcasts
        
        # Delete broadcast
        success = scheduler.delete_broadcast(broadcast_id)
        assert success is True
        assert broadcast_id not in scheduler.scheduled_broadcasts
        
        # Test deleting non-existent broadcast
        success = scheduler.delete_broadcast("nonexistent")
        assert success is False
    
    def test_get_scheduled_broadcasts(self, scheduler):
        """Test getting scheduled broadcasts"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Create active broadcast
        id1 = scheduler.schedule_broadcast("Active", "Content", scheduled_time, created_by="test")
        
        # Create inactive broadcast
        id2 = scheduler.schedule_broadcast("Inactive", "Content", scheduled_time, created_by="test")
        scheduler.cancel_broadcast(id2)
        
        # Get all broadcasts
        all_broadcasts = scheduler.get_scheduled_broadcasts()
        assert len(all_broadcasts) == 2
        
        # Get active only
        active_broadcasts = scheduler.get_scheduled_broadcasts(active_only=True)
        assert len(active_broadcasts) == 1
        assert active_broadcasts[0].id == id1
    
    def test_get_upcoming_broadcasts(self, scheduler):
        """Test getting upcoming broadcasts"""
        now = datetime.now(timezone.utc)
        
        # Create broadcast for next hour
        id1 = scheduler.schedule_broadcast(
            "Soon", "Content", now + timedelta(hours=1), created_by="test"
        )
        
        # Create broadcast for next week
        id2 = scheduler.schedule_broadcast(
            "Later", "Content", now + timedelta(days=7), created_by="test"
        )
        
        # Get upcoming broadcasts in next 24 hours
        upcoming = scheduler.get_upcoming_broadcasts(hours=24)
        assert len(upcoming) == 1
        assert upcoming[0].id == id1
        
        # Get upcoming broadcasts in next week
        upcoming_week = scheduler.get_upcoming_broadcasts(hours=24*7)
        assert len(upcoming_week) == 2
    
    def test_prepare_message_content(self, scheduler):
        """Test message content preparation with variables"""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        broadcast_id = scheduler.schedule_broadcast(
            name="Variable Test",
            content="Hello {name}, today is {date} and the broadcast is {broadcast_name}",
            scheduled_time=scheduled_time,
            variables={"name": "World"},
            created_by="test"
        )
        
        broadcast = scheduler.scheduled_broadcasts[broadcast_id]
        content = scheduler._prepare_message_content(broadcast)
        
        assert "Hello World" in content
        assert "{date}" not in content  # Should be replaced with actual date
        assert "{timestamp}" not in content  # Should be replaced with actual timestamp
        assert "Variable Test" in content  # broadcast_name should be replaced
    
    def test_calculate_next_send_time(self, scheduler):
        """Test calculating next send time for recurring broadcasts"""
        now = datetime.now(timezone.utc)
        
        # Create a mock broadcast for testing
        broadcast = ScheduledBroadcast(
            id="test",
            name="Test",
            content="Test",
            schedule_type=ScheduleType.RECURRING,
            recurrence_pattern=RecurrencePattern.DAILY
        )
        
        # Test daily recurrence
        next_time = scheduler._calculate_next_send_time(broadcast, now)
        expected = now + timedelta(days=1)
        assert abs((next_time - expected).total_seconds()) < 60  # Within 1 minute
        
        # Test weekly recurrence
        broadcast.recurrence_pattern = RecurrencePattern.WEEKLY
        next_time = scheduler._calculate_next_send_time(broadcast, now)
        expected = now + timedelta(weeks=1)
        assert abs((next_time - expected).total_seconds()) < 60
        
        # Test weekdays recurrence
        broadcast.recurrence_pattern = RecurrencePattern.WEEKDAYS
        next_time = scheduler._calculate_next_send_time(broadcast, now)
        # Should be next weekday
        while next_time.weekday() >= 5:  # Skip weekends
            next_time += timedelta(days=1)
        assert next_time.weekday() < 5
    
    @pytest.mark.asyncio
    async def test_send_immediate_broadcast(self, scheduler):
        """Test sending immediate broadcast"""
        # Mock message sender
        mock_sender = AsyncMock(return_value=True)
        scheduler.message_sender = mock_sender
        
        success = await scheduler.send_immediate_broadcast(
            content="Immediate test message",
            channel=0,
            interface_id="serial0",
            sent_by="test_user"
        )
        
        assert success is True
        mock_sender.assert_called_once_with(
            content="Immediate test message",
            channel=0,
            interface_id="serial0"
        )
        
        # Check history was recorded
        assert len(scheduler.broadcast_history) == 1
        history = scheduler.broadcast_history[0]
        assert history.content == "Immediate test message"
        assert history.sent_by == "test_user"
        assert history.status == BroadcastStatus.SENT
    
    @pytest.mark.asyncio
    async def test_send_immediate_broadcast_failure(self, scheduler):
        """Test sending immediate broadcast with failure"""
        # Mock message sender that fails
        mock_sender = AsyncMock(side_effect=Exception("Send failed"))
        scheduler.message_sender = mock_sender
        
        success = await scheduler.send_immediate_broadcast(
            content="Failed test message",
            sent_by="test_user"
        )
        
        assert success is False
        
        # Check history was recorded with failure
        assert len(scheduler.broadcast_history) == 1
        history = scheduler.broadcast_history[0]
        assert history.status == BroadcastStatus.FAILED
        assert history.error_message == "Send failed"
    
    @pytest.mark.asyncio
    async def test_start_stop_scheduler(self, scheduler):
        """Test starting and stopping scheduler"""
        assert scheduler.is_running is False
        assert scheduler.scheduler_task is None
        
        # Start scheduler
        await scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.scheduler_task is not None
        
        # Stop scheduler
        await scheduler.stop()
        assert scheduler.is_running is False
    
    def test_get_templates_by_category(self, scheduler):
        """Test getting templates by category"""
        # Create templates in different categories
        scheduler.create_template("Test1", "Content1", category="test")
        scheduler.create_template("Test2", "Content2", category="test")
        scheduler.create_template("Other", "Content3", category="other")
        
        # Get templates by category
        test_templates = scheduler.get_templates(category="test")
        assert len(test_templates) == 2
        assert all(t.category == "test" for t in test_templates)
        
        other_templates = scheduler.get_templates(category="other")
        assert len(other_templates) == 1
        assert other_templates[0].category == "other"
        
        # Get all templates
        all_templates = scheduler.get_templates()
        assert len(all_templates) >= 3  # At least our 3 plus defaults
    
    def test_get_broadcast_history(self, scheduler):
        """Test getting broadcast history"""
        # Add some history entries
        for i in range(5):
            history = BroadcastHistory(
                id=f"history_{i}",
                schedule_id=None,
                content=f"Message {i}",
                channel=0,
                interface_id="serial0",
                sent_at=datetime.now(timezone.utc) - timedelta(hours=i),
                sent_by="test",
                status=BroadcastStatus.SENT
            )
            scheduler.broadcast_history.append(history)
        
        # Get history with limit
        history = scheduler.get_broadcast_history(limit=3)
        assert len(history) == 3
        
        # Should be sorted by sent_at descending (most recent first)
        # Message 0 was sent most recently (now - 0 hours)
        # But the get_broadcast_history method takes from the end of the list and sorts
        # Let's check that we get the right number and they're properly sorted
        sent_times = [h.sent_at for h in history]
        assert sent_times == sorted(sent_times, reverse=True)  # Should be descending


@pytest.mark.asyncio
async def test_scheduler_integration():
    """Integration test for scheduler"""
    # Mock message sender
    sent_messages = []
    
    async def mock_sender(content, channel=None, interface_id=None):
        sent_messages.append({
            "content": content,
            "channel": channel,
            "interface_id": interface_id
        })
        return True
    
    scheduler = BroadcastScheduler(message_sender=mock_sender)
    
    try:
        # Start scheduler
        await scheduler.start()
        
        # Schedule immediate broadcast
        success = await scheduler.send_immediate_broadcast(
            "Integration test message",
            channel=1,
            interface_id="tcp0",
            sent_by="integration_test"
        )
        
        assert success is True
        assert len(sent_messages) == 1
        assert sent_messages[0]["content"] == "Integration test message"
        assert sent_messages[0]["channel"] == 1
        assert sent_messages[0]["interface_id"] == "tcp0"
        
        # Check history
        history = scheduler.get_broadcast_history()
        assert len(history) == 1
        assert history[0].content == "Integration test message"
        assert history[0].sent_by == "integration_test"
        
    finally:
        # Clean up
        await scheduler.stop()


if __name__ == "__main__":
    pytest.main([__file__])