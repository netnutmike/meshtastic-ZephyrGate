"""
Unit tests for MQTT Gateway Message Queue

Tests queue operations, priority handling, and statistics tracking.

Requirements: 4.5, 4.6
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from models.message import Message, MessagePriority
from mqtt_gateway.message_queue import MessageQueue, QueuedMQTTMessage


@pytest.fixture
def queue():
    """Provide a message queue with default settings"""
    return MessageQueue(max_size=10)


@pytest.fixture
def large_queue():
    """Provide a larger message queue"""
    return MessageQueue(max_size=100)


@pytest.fixture
def sample_message():
    """Provide a sample message"""
    return Message(
        sender_id="!12345678",
        content="Test message",
        channel=0,
        priority=MessagePriority.NORMAL
    )


class TestMessageQueueInitialization:
    """Tests for message queue initialization"""
    
    def test_initialization_with_default_size(self):
        """Test queue initializes with default max size"""
        queue = MessageQueue()
        
        assert queue.max_size == 1000
        assert queue.size() == 0
        assert queue.is_empty()
        assert not queue.is_full()
    
    def test_initialization_with_custom_size(self):
        """Test queue initializes with custom max size"""
        queue = MessageQueue(max_size=50)
        
        assert queue.max_size == 50
        assert queue.size() == 0
    
    def test_initial_statistics(self):
        """Test queue starts with zero statistics"""
        queue = MessageQueue()
        stats = queue.get_statistics()
        
        assert stats['size'] == 0
        assert stats['enqueued'] == 0
        assert stats['dequeued'] == 0
        assert stats['dropped'] == 0
        assert stats['overflow_drops'] == 0


class TestEnqueueOperations:
    """Tests for enqueue operations"""
    
    @pytest.mark.asyncio
    async def test_enqueue_single_message(self, queue, sample_message):
        """Test enqueuing a single message"""
        result = await queue.enqueue(
            message=sample_message,
            topic="test/topic",
            payload=b"test payload",
            qos=0
        )
        
        assert result is True
        assert queue.size() == 1
        assert not queue.is_empty()
    
    @pytest.mark.asyncio
    async def test_enqueue_multiple_messages(self, queue):
        """Test enqueuing multiple messages"""
        for i in range(5):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            result = await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
            assert result is True
        
        assert queue.size() == 5
    
    @pytest.mark.asyncio
    async def test_enqueue_with_explicit_priority(self, queue, sample_message):
        """Test enqueuing with explicit priority override"""
        result = await queue.enqueue(
            message=sample_message,
            topic="test/topic",
            payload=b"payload",
            qos=0,
            priority=MessagePriority.HIGH.value
        )
        
        assert result is True
        
        # Dequeue and verify priority was set
        queued_msg = await queue.dequeue()
        assert queued_msg.priority == MessagePriority.HIGH.value
    
    @pytest.mark.asyncio
    async def test_enqueue_uses_message_priority_by_default(self, queue):
        """Test enqueue uses message's priority when not specified"""
        msg = Message(
            sender_id="!12345678",
            content="Test",
            priority=MessagePriority.EMERGENCY
        )
        
        await queue.enqueue(msg, "topic", b"payload", qos=0)
        
        queued_msg = await queue.dequeue()
        assert queued_msg.priority == MessagePriority.EMERGENCY.value
    
    @pytest.mark.asyncio
    async def test_enqueue_updates_statistics(self, queue, sample_message):
        """Test enqueue updates statistics correctly"""
        await queue.enqueue(sample_message, "topic", b"payload", qos=0)
        
        stats = queue.get_statistics()
        assert stats['enqueued'] == 1
        assert stats['size'] == 1


class TestDequeueOperations:
    """Tests for dequeue operations"""
    
    @pytest.mark.asyncio
    async def test_dequeue_from_empty_queue(self, queue):
        """Test dequeuing from empty queue returns None"""
        result = await queue.dequeue()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_dequeue_single_message(self, queue, sample_message):
        """Test dequeuing a single message"""
        await queue.enqueue(sample_message, "test/topic", b"payload", qos=0)
        
        queued_msg = await queue.dequeue()
        
        assert queued_msg is not None
        assert queued_msg.message.sender_id == sample_message.sender_id
        assert queued_msg.topic == "test/topic"
        assert queued_msg.payload == b"payload"
        assert queued_msg.qos == 0
    
    @pytest.mark.asyncio
    async def test_dequeue_fifo_order_same_priority(self, queue):
        """Test messages are dequeued in FIFO order for same priority"""
        # Add messages with same priority
        for i in range(5):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=MessagePriority.NORMAL
            )
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Dequeue and verify order
        for i in range(5):
            queued_msg = await queue.dequeue()
            assert queued_msg.message.sender_id == f"!{i:08x}"
    
    @pytest.mark.asyncio
    async def test_dequeue_updates_statistics(self, queue, sample_message):
        """Test dequeue updates statistics correctly"""
        await queue.enqueue(sample_message, "topic", b"payload", qos=0)
        await queue.dequeue()
        
        stats = queue.get_statistics()
        assert stats['dequeued'] == 1
        assert stats['size'] == 0
    
    @pytest.mark.asyncio
    async def test_dequeue_empties_queue(self, queue):
        """Test dequeuing all messages empties the queue"""
        # Add messages
        for i in range(3):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Dequeue all
        for _ in range(3):
            await queue.dequeue()
        
        assert queue.is_empty()
        assert queue.size() == 0


class TestPriorityOrdering:
    """Tests for priority-based ordering"""
    
    @pytest.mark.asyncio
    async def test_high_priority_before_low_priority(self, queue):
        """Test high priority messages are dequeued before low priority"""
        # Add low priority message first
        low_msg = Message(
            sender_id="!aaaaaaaa",
            content="Low priority",
            priority=MessagePriority.LOW
        )
        await queue.enqueue(low_msg, "topic/low", b"low", qos=0)
        
        # Add high priority message second
        high_msg = Message(
            sender_id="!bbbbbbbb",
            content="High priority",
            priority=MessagePriority.HIGH
        )
        await queue.enqueue(high_msg, "topic/high", b"high", qos=0)
        
        # High priority should be dequeued first
        first = await queue.dequeue()
        assert first.message.sender_id == "!bbbbbbbb"
        
        second = await queue.dequeue()
        assert second.message.sender_id == "!aaaaaaaa"
    
    @pytest.mark.asyncio
    async def test_emergency_priority_first(self, queue):
        """Test emergency priority messages are dequeued first"""
        priorities = [
            MessagePriority.LOW,
            MessagePriority.NORMAL,
            MessagePriority.HIGH,
            MessagePriority.EMERGENCY
        ]
        
        # Add messages in random order
        for i, priority in enumerate([priorities[1], priorities[3], priorities[0], priorities[2]]):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=priority
            )
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Should dequeue in priority order: EMERGENCY, HIGH, NORMAL, LOW
        first = await queue.dequeue()
        assert first.priority == MessagePriority.EMERGENCY.value
        
        second = await queue.dequeue()
        assert second.priority == MessagePriority.HIGH.value
        
        third = await queue.dequeue()
        assert third.priority == MessagePriority.NORMAL.value
        
        fourth = await queue.dequeue()
        assert fourth.priority == MessagePriority.LOW.value
    
    @pytest.mark.asyncio
    async def test_priority_breakdown_statistics(self, queue):
        """Test statistics show breakdown by priority"""
        # Add messages with different priorities
        await queue.enqueue(
            Message(sender_id="!11111111", priority=MessagePriority.HIGH),
            "topic1", b"payload", qos=0
        )
        await queue.enqueue(
            Message(sender_id="!22222222", priority=MessagePriority.HIGH),
            "topic2", b"payload", qos=0
        )
        await queue.enqueue(
            Message(sender_id="!33333333", priority=MessagePriority.LOW),
            "topic3", b"payload", qos=0
        )
        
        stats = queue.get_statistics()
        priority_breakdown = stats['priority_breakdown']
        
        assert priority_breakdown[MessagePriority.HIGH.value] == 2
        assert priority_breakdown[MessagePriority.LOW.value] == 1
        assert priority_breakdown[MessagePriority.NORMAL.value] == 0


class TestQueueSizeLimits:
    """Tests for queue size limits and overflow"""
    
    @pytest.mark.asyncio
    async def test_queue_full_detection(self, queue):
        """Test is_full() correctly detects full queue"""
        # Fill queue to capacity
        for i in range(10):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        assert queue.is_full()
        assert queue.size() == queue.max_size
    
    @pytest.mark.asyncio
    async def test_overflow_drops_oldest_message(self, queue):
        """Test overflow drops oldest message from lowest priority"""
        # Fill queue with low priority messages
        for i in range(10):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=MessagePriority.LOW
            )
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Add one more message (should drop oldest)
        new_msg = Message(
            sender_id="!99999999",
            content="New message",
            priority=MessagePriority.LOW
        )
        result = await queue.enqueue(new_msg, "topic/new", b"payload", qos=0)
        
        assert result is True
        assert queue.size() == 10  # Still at max
        
        # First dequeued message should NOT be the first one we added
        first = await queue.dequeue()
        assert first.message.sender_id != "!00000000"  # First message was dropped
    
    @pytest.mark.asyncio
    async def test_overflow_statistics(self, queue):
        """Test overflow events are tracked in statistics"""
        # Fill queue
        for i in range(10):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Add 3 more messages to trigger overflow
        for i in range(3):
            msg = Message(sender_id=f"!overflow{i:08x}", content=f"Overflow {i}")
            await queue.enqueue(msg, f"topic/overflow/{i}", b"payload", qos=0)
        
        stats = queue.get_statistics()
        assert stats['overflow_drops'] == 3
        assert stats['dropped'] == 3
    
    @pytest.mark.asyncio
    async def test_overflow_drops_from_lowest_priority(self, queue):
        """Test overflow drops from lowest priority queue first"""
        # Add high priority messages
        for i in range(5):
            msg = Message(
                sender_id=f"!high{i:08x}",
                content=f"High {i}",
                priority=MessagePriority.HIGH
            )
            await queue.enqueue(msg, f"topic/high/{i}", b"payload", qos=0)
        
        # Add low priority messages
        for i in range(5):
            msg = Message(
                sender_id=f"!low{i:08x}",
                content=f"Low {i}",
                priority=MessagePriority.LOW
            )
            await queue.enqueue(msg, f"topic/low/{i}", b"payload", qos=0)
        
        # Queue is now full (10 messages)
        # Add one more high priority message
        new_msg = Message(
            sender_id="!newhigh",
            content="New high",
            priority=MessagePriority.HIGH
        )
        await queue.enqueue(new_msg, "topic/newhigh", b"payload", qos=0)
        
        # Should have dropped a low priority message
        # Dequeue all and count priorities
        high_count = 0
        low_count = 0
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            if queued_msg.priority == MessagePriority.HIGH.value:
                high_count += 1
            elif queued_msg.priority == MessagePriority.LOW.value:
                low_count += 1
        
        # Should have 6 high priority (5 original + 1 new) and 4 low (1 dropped)
        assert high_count == 6
        assert low_count == 4


class TestQueueClear:
    """Tests for clearing the queue"""
    
    @pytest.mark.asyncio
    async def test_clear_empties_queue(self, queue):
        """Test clear removes all messages"""
        # Add messages
        for i in range(5):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        await queue.clear()
        
        assert queue.is_empty()
        assert queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_clear_all_priorities(self, queue):
        """Test clear removes messages from all priority queues"""
        # Add messages with different priorities
        for priority in MessagePriority:
            msg = Message(
                sender_id=f"!{priority.value:08x}",
                content=f"Priority {priority.name}",
                priority=priority
            )
            await queue.enqueue(msg, f"topic/{priority.name}", b"payload", qos=0)
        
        await queue.clear()
        
        stats = queue.get_statistics()
        for priority_value in stats['priority_breakdown'].values():
            assert priority_value == 0


class TestQueueStatistics:
    """Tests for queue statistics"""
    
    @pytest.mark.asyncio
    async def test_statistics_structure(self, queue):
        """Test statistics contain all required fields"""
        stats = queue.get_statistics()
        
        assert 'size' in stats
        assert 'max_size' in stats
        assert 'enqueued' in stats
        assert 'dequeued' in stats
        assert 'dropped' in stats
        assert 'overflow_drops' in stats
        assert 'priority_breakdown' in stats
    
    @pytest.mark.asyncio
    async def test_statistics_accuracy(self, queue):
        """Test statistics accurately reflect queue operations"""
        # Enqueue 5 messages
        for i in range(5):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Dequeue 2 messages
        await queue.dequeue()
        await queue.dequeue()
        
        stats = queue.get_statistics()
        
        assert stats['size'] == 3
        assert stats['enqueued'] == 5
        assert stats['dequeued'] == 2
        assert stats['max_size'] == 10


class TestQueueEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_queue_size_one(self):
        """Test queue with size limit of 1"""
        queue = MessageQueue(max_size=1)
        
        msg1 = Message(sender_id="!11111111", content="First")
        await queue.enqueue(msg1, "topic1", b"payload1", qos=0)
        
        assert queue.size() == 1
        assert queue.is_full()
        
        # Add another message (should drop first)
        msg2 = Message(sender_id="!22222222", content="Second")
        await queue.enqueue(msg2, "topic2", b"payload2", qos=0)
        
        assert queue.size() == 1
        
        # Dequeue should get second message
        queued = await queue.dequeue()
        assert queued.message.sender_id == "!22222222"
    
    @pytest.mark.asyncio
    async def test_empty_payload(self, queue):
        """Test enqueuing message with empty payload"""
        msg = Message(sender_id="!12345678", content="Test")
        result = await queue.enqueue(msg, "topic", b"", qos=0)
        
        assert result is True
        
        queued = await queue.dequeue()
        assert queued.payload == b""
    
    @pytest.mark.asyncio
    async def test_different_qos_levels(self, queue):
        """Test messages with different QoS levels"""
        for qos in [0, 1, 2]:
            msg = Message(sender_id=f"!{qos:08x}", content=f"QoS {qos}")
            await queue.enqueue(msg, f"topic/{qos}", b"payload", qos=qos)
        
        # Verify QoS is preserved
        for expected_qos in [0, 1, 2]:
            queued = await queue.dequeue()
            assert queued.qos == expected_qos
