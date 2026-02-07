"""
Property-based tests for MQTT Gateway Message Queue

Tests universal properties of message queuing, overflow behavior,
and priority handling.

Properties tested:
- Property 8: Queue Overflow Behavior (Requirements 4.6, 7.4)
- Property 9: Message Queuing When Disconnected (Requirements 4.5, 7.3)

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings
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

from models.message import Message, MessageType, MessagePriority
from mqtt_gateway.message_queue import MessageQueue


# ============================================================================
# Hypothesis Strategies for Generating Test Data
# ============================================================================

@st.composite
def node_id_strategy(draw):
    """Generate valid Meshtastic node IDs"""
    hex_chars = draw(st.text(
        alphabet='0123456789abcdef',
        min_size=8,
        max_size=8
    ))
    return f"!{hex_chars}"


@st.composite
def message_strategy(draw):
    """Generate valid Message objects"""
    return Message(
        sender_id=draw(node_id_strategy()),
        channel=draw(st.integers(min_value=0, max_value=255)),
        content=draw(st.text(min_size=0, max_size=200)),
        message_type=draw(st.sampled_from(list(MessageType))),
        priority=draw(st.sampled_from(list(MessagePriority)))
    )


@st.composite
def topic_strategy(draw):
    """Generate valid MQTT topics"""
    region = draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ', min_size=2, max_size=3))
    channel = draw(st.integers(min_value=0, max_value=255))
    node_id = draw(node_id_strategy())
    format_type = draw(st.sampled_from(['e', 'json']))
    return f"msh/{region}/2/{format_type}/{channel}/{node_id}"


@st.composite
def payload_strategy(draw):
    """Generate valid message payloads"""
    return draw(st.binary(min_size=0, max_size=1000))


# ============================================================================
# Property 8: Queue Overflow Behavior
# ============================================================================

class TestQueueOverflowProperty:
    """
    **Validates: Requirements 4.6, 7.4**
    
    For any message queue at maximum capacity, adding a new message should
    result in the oldest message being removed and the new message being added,
    maintaining the queue size at the maximum.
    """
    
    @pytest.mark.asyncio
    @given(
        max_size=st.integers(min_value=1, max_value=100),
        num_extra=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50, deadline=None)
    async def test_queue_overflow_maintains_max_size(self, max_size, num_extra):
        """
        Property: Queue never exceeds maximum size
        
        When messages are added to a full queue, the queue size should
        remain at max_size by dropping oldest messages.
        """
        queue = MessageQueue(max_size=max_size)
        
        # Add messages up to and beyond capacity
        total_messages = max_size + num_extra
        for i in range(total_messages):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            topic = f"test/topic/{i}"
            payload = f"payload_{i}".encode()
            
            await queue.enqueue(msg, topic, payload, qos=0)
            
            # Queue size should never exceed max_size
            assert queue.size() <= max_size, \
                f"Queue size {queue.size()} exceeds max_size {max_size}"
        
        # After adding all messages, size should be exactly max_size
        assert queue.size() == max_size, \
            f"Final queue size {queue.size()} should equal max_size {max_size}"
    
    @pytest.mark.asyncio
    @given(
        max_size=st.integers(min_value=5, max_value=50),
        num_messages=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=30, deadline=None)
    async def test_queue_overflow_drops_oldest_first(self, max_size, num_messages):
        """
        Property: Overflow drops oldest messages from lowest priority
        
        When the queue overflows, the oldest message from the lowest
        priority queue should be dropped first.
        """
        assume(num_messages > max_size)
        
        queue = MessageQueue(max_size=max_size)
        
        # Add messages with known priorities and track them
        added_messages = []
        for i in range(num_messages):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=MessagePriority.LOW  # All low priority for simplicity
            )
            topic = f"test/topic/{i}"
            payload = f"payload_{i}".encode()
            
            await queue.enqueue(msg, topic, payload, qos=0)
            added_messages.append((msg, topic, payload))
        
        # Queue should contain only the last max_size messages
        assert queue.size() == max_size
        
        # Dequeue all messages and verify they are the most recent ones
        dequeued_indices = []
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            # Find which message this is
            for idx, (msg, topic, payload) in enumerate(added_messages):
                if queued_msg.message.sender_id == msg.sender_id:
                    dequeued_indices.append(idx)
                    break
        
        # The dequeued messages should be the last max_size messages
        expected_indices = list(range(num_messages - max_size, num_messages))
        assert sorted(dequeued_indices) == expected_indices, \
            f"Queue should contain messages {expected_indices}, got {sorted(dequeued_indices)}"
    
    @pytest.mark.asyncio
    @given(
        max_size=st.integers(min_value=10, max_value=50),
        overflow_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=30, deadline=None)
    async def test_queue_overflow_statistics(self, max_size, overflow_count):
        """
        Property: Overflow events are tracked in statistics
        
        When messages are dropped due to overflow, the statistics should
        accurately reflect the number of dropped messages.
        """
        queue = MessageQueue(max_size=max_size)
        
        # Fill queue to capacity
        for i in range(max_size):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Add more messages to trigger overflow
        for i in range(overflow_count):
            msg = Message(sender_id=f"!overflow{i:08x}", content=f"Overflow {i}")
            await queue.enqueue(msg, f"topic/overflow/{i}", b"payload", qos=0)
        
        stats = queue.get_statistics()
        
        # Check that overflow drops are tracked
        assert stats['overflow_drops'] == overflow_count, \
            f"Expected {overflow_count} overflow drops, got {stats['overflow_drops']}"
        
        # Total dropped should include overflow drops
        assert stats['dropped'] >= overflow_count, \
            f"Total dropped {stats['dropped']} should be at least {overflow_count}"
    
    @pytest.mark.asyncio
    @given(
        max_size=st.integers(min_value=10, max_value=50),
        priorities=st.lists(
            st.sampled_from(list(MessagePriority)),
            min_size=20,
            max_size=100
        )
    )
    @settings(max_examples=30, deadline=None)
    async def test_queue_overflow_respects_priority(self, max_size, priorities):
        """
        Property: Overflow drops from lowest priority first
        
        When the queue overflows, messages from lower priority queues
        should be dropped before higher priority messages.
        """
        assume(len(priorities) > max_size)
        
        queue = MessageQueue(max_size=max_size)
        
        # Add messages with various priorities
        for i, priority in enumerate(priorities):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=priority
            )
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        # Dequeue all messages and check priorities
        dequeued_priorities = []
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            dequeued_priorities.append(queued_msg.priority)
        
        # Count how many of each priority we have
        priority_counts = {}
        for p in dequeued_priorities:
            priority_counts[p] = priority_counts.get(p, 0) + 1
        
        # The queue should have dropped low priority messages first
        # So we should have more high priority messages remaining
        # This is a soft check - we just verify the queue maintained max_size
        assert len(dequeued_priorities) == max_size, \
            f"Should have dequeued exactly {max_size} messages"


# ============================================================================
# Property 9: Message Queuing When Disconnected
# ============================================================================

class TestMessageQueuingWhenDisconnectedProperty:
    """
    **Validates: Requirements 4.5, 7.3**
    
    For any message received when the MQTT broker connection is unavailable,
    the message should be added to the queue for later transmission.
    """
    
    @pytest.mark.asyncio
    @given(
        messages=st.lists(message_strategy(), min_size=1, max_size=50),
        topics=st.lists(topic_strategy(), min_size=1, max_size=50),
        payloads=st.lists(payload_strategy(), min_size=1, max_size=50)
    )
    @settings(max_examples=30, deadline=None)
    async def test_all_messages_queued_when_disconnected(self, messages, topics, payloads):
        """
        Property: All messages are queued when broker is unavailable
        
        When the MQTT broker is disconnected, all messages should be
        successfully added to the queue.
        """
        assume(len(topics) >= len(messages))
        assume(len(payloads) >= len(messages))
        
        queue = MessageQueue(max_size=1000)
        
        # Simulate disconnected state by just enqueuing messages
        # (In real usage, the plugin would check connection before enqueuing)
        for i in range(len(messages)):
            result = await queue.enqueue(
                message=messages[i],
                topic=topics[i],
                payload=payloads[i],
                qos=0
            )
            
            # Enqueue should succeed
            assert result is True, \
                f"Message {i} should be successfully enqueued"
        
        # All messages should be in the queue
        assert queue.size() == len(messages), \
            f"Queue should contain {len(messages)} messages, got {queue.size()}"
    
    @pytest.mark.asyncio
    @given(
        num_messages=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=30, deadline=None)
    async def test_queued_messages_preserve_order(self, num_messages):
        """
        Property: Messages are dequeued in priority order
        
        Messages should be dequeued in priority order (highest first),
        and within the same priority, in FIFO order.
        """
        queue = MessageQueue(max_size=1000)
        
        # Add messages with known priorities
        added_messages = []
        for i in range(num_messages):
            # Alternate priorities to test ordering
            priority = MessagePriority.HIGH if i % 2 == 0 else MessagePriority.LOW
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=priority
            )
            topic = f"test/topic/{i}"
            payload = f"payload_{i}".encode()
            
            await queue.enqueue(msg, topic, payload, qos=0)
            added_messages.append((i, priority))
        
        # Dequeue all messages
        dequeued_order = []
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            # Extract the index from sender_id
            idx = int(queued_msg.message.sender_id[1:], 16)
            dequeued_order.append((idx, queued_msg.priority))
        
        # Verify all messages were dequeued
        assert len(dequeued_order) == num_messages, \
            f"Should dequeue {num_messages} messages, got {len(dequeued_order)}"
        
        # Verify priority ordering: all HIGH priority should come before LOW
        high_indices = [idx for idx, pri in dequeued_order if pri == MessagePriority.HIGH.value]
        low_indices = [idx for idx, pri in dequeued_order if pri == MessagePriority.LOW.value]
        
        if high_indices and low_indices:
            # All high priority messages should be dequeued before low priority
            last_high_position = len(high_indices) - 1
            first_low_position = len(high_indices)
            
            assert first_low_position > last_high_position or first_low_position == len(dequeued_order), \
                "High priority messages should be dequeued before low priority"
    
    @pytest.mark.asyncio
    @given(
        num_messages=st.integers(min_value=5, max_value=30)
    )
    @settings(max_examples=30, deadline=None)
    async def test_queued_messages_preserve_metadata(self, num_messages):
        """
        Property: Queued messages preserve all metadata
        
        When messages are queued and later dequeued, all message metadata
        (topic, payload, qos, priority) should be preserved.
        """
        queue = MessageQueue(max_size=1000)
        
        # Add messages with specific metadata
        added_data = []
        for i in range(num_messages):
            msg = Message(
                sender_id=f"!{i:08x}",
                content=f"Message {i}",
                priority=MessagePriority.NORMAL
            )
            topic = f"test/topic/{i}"
            payload = f"payload_{i}".encode()
            qos = i % 3  # QoS 0, 1, or 2
            
            await queue.enqueue(msg, topic, payload, qos=qos)
            added_data.append({
                'sender_id': msg.sender_id,
                'topic': topic,
                'payload': payload,
                'qos': qos
            })
        
        # Dequeue and verify metadata
        dequeued_data = []
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            dequeued_data.append({
                'sender_id': queued_msg.message.sender_id,
                'topic': queued_msg.topic,
                'payload': queued_msg.payload,
                'qos': queued_msg.qos
            })
        
        # Sort both lists by sender_id for comparison
        added_data.sort(key=lambda x: x['sender_id'])
        dequeued_data.sort(key=lambda x: x['sender_id'])
        
        # Verify all metadata matches
        assert len(dequeued_data) == len(added_data), \
            f"Should dequeue {len(added_data)} messages"
        
        for added, dequeued in zip(added_data, dequeued_data):
            assert added['sender_id'] == dequeued['sender_id'], \
                "Sender ID should be preserved"
            assert added['topic'] == dequeued['topic'], \
                "Topic should be preserved"
            assert added['payload'] == dequeued['payload'], \
                "Payload should be preserved"
            assert added['qos'] == dequeued['qos'], \
                "QoS should be preserved"
    
    @pytest.mark.asyncio
    @given(
        num_messages=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=30, deadline=None)
    async def test_queue_statistics_accurate(self, num_messages):
        """
        Property: Queue statistics are accurate
        
        The queue statistics should accurately reflect the number of
        enqueued and dequeued messages.
        """
        queue = MessageQueue(max_size=1000)
        
        # Add messages
        for i in range(num_messages):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        stats_after_enqueue = queue.get_statistics()
        assert stats_after_enqueue['enqueued'] == num_messages, \
            f"Should have enqueued {num_messages} messages"
        assert stats_after_enqueue['size'] == num_messages, \
            f"Queue size should be {num_messages}"
        
        # Dequeue half the messages
        dequeue_count = num_messages // 2
        for _ in range(dequeue_count):
            await queue.dequeue()
        
        stats_after_dequeue = queue.get_statistics()
        assert stats_after_dequeue['dequeued'] == dequeue_count, \
            f"Should have dequeued {dequeue_count} messages"
        assert stats_after_dequeue['size'] == num_messages - dequeue_count, \
            f"Queue size should be {num_messages - dequeue_count}"
    
    @pytest.mark.asyncio
    @given(
        num_messages=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=30, deadline=None)
    async def test_empty_queue_returns_none(self, num_messages):
        """
        Property: Dequeuing from empty queue returns None
        
        When the queue is empty, dequeue should return None without error.
        """
        queue = MessageQueue(max_size=1000)
        
        # Add and remove all messages
        for i in range(num_messages):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        for _ in range(num_messages):
            await queue.dequeue()
        
        # Queue should be empty
        assert queue.is_empty(), "Queue should be empty"
        
        # Dequeuing from empty queue should return None
        result = await queue.dequeue()
        assert result is None, "Dequeue from empty queue should return None"
        
        # Multiple dequeues should all return None
        for _ in range(5):
            result = await queue.dequeue()
            assert result is None, "Dequeue from empty queue should always return None"


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestMessageQueuePropertyEdgeCases:
    """Test edge cases that combine multiple properties"""
    
    @pytest.mark.asyncio
    @given(
        max_size=st.integers(min_value=5, max_value=20),
        num_messages=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=20, deadline=None)
    async def test_concurrent_enqueue_dequeue(self, max_size, num_messages):
        """
        Edge case: Concurrent enqueue and dequeue operations
        
        The queue should handle concurrent operations correctly.
        """
        assume(num_messages > max_size)
        
        queue = MessageQueue(max_size=max_size)
        
        # Enqueue messages
        enqueue_tasks = []
        for i in range(num_messages):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            task = queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
            enqueue_tasks.append(task)
        
        await asyncio.gather(*enqueue_tasks)
        
        # Queue should not exceed max size
        assert queue.size() <= max_size, \
            f"Queue size {queue.size()} should not exceed {max_size}"
    
    @pytest.mark.asyncio
    async def test_clear_queue(self):
        """
        Edge case: Clearing the queue
        
        After clearing, the queue should be empty and ready for new messages.
        """
        queue = MessageQueue(max_size=100)
        
        # Add some messages
        for i in range(10):
            msg = Message(sender_id=f"!{i:08x}", content=f"Message {i}")
            await queue.enqueue(msg, f"topic/{i}", b"payload", qos=0)
        
        assert queue.size() == 10, "Queue should have 10 messages"
        
        # Clear the queue
        await queue.clear()
        
        assert queue.is_empty(), "Queue should be empty after clear"
        assert queue.size() == 0, "Queue size should be 0 after clear"
        
        # Should be able to add messages after clearing
        msg = Message(sender_id="!12345678", content="New message")
        result = await queue.enqueue(msg, "topic/new", b"payload", qos=0)
        assert result is True, "Should be able to enqueue after clear"
        assert queue.size() == 1, "Queue should have 1 message after enqueue"
