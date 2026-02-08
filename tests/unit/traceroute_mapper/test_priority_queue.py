"""
Unit Tests for Priority Queue

Tests the basic functionality of the PriorityQueue class including
enqueue, dequeue, duplicate detection, and overflow handling.
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.priority_queue import (
    PriorityQueue,
    TracerouteRequest,
    TraceroutePriority
)


class TestPriorityQueueBasics:
    """Test basic priority queue operations"""
    
    def test_enqueue_dequeue_single_request(self):
        """Test enqueueing and dequeueing a single request"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue a request
        result = queue.enqueue(
            node_id="!12345678",
            priority=TraceroutePriority.NEW_NODE,
            reason="new_node_discovered"
        )
        
        assert result is True
        assert queue.size() == 1
        assert queue.contains("!12345678")
        
        # Dequeue the request
        request = queue.dequeue()
        
        assert request is not None
        assert request.node_id == "!12345678"
        assert request.priority == TraceroutePriority.NEW_NODE
        assert request.reason == "new_node_discovered"
        assert queue.size() == 0
        assert not queue.contains("!12345678")
    
    def test_priority_ordering(self):
        """Test that requests are dequeued in priority order"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue requests with different priorities
        queue.enqueue("!node1", TraceroutePriority.LOW_PRIORITY, "low")
        queue.enqueue("!node2", TraceroutePriority.NEW_NODE, "high")
        queue.enqueue("!node3", TraceroutePriority.PERIODIC_RECHECK, "medium")
        
        assert queue.size() == 3
        
        # Dequeue and verify order (lowest priority number first)
        request1 = queue.dequeue()
        assert request1.node_id == "!node2"  # Priority 1 (NEW_NODE)
        
        request2 = queue.dequeue()
        assert request2.node_id == "!node3"  # Priority 8 (PERIODIC_RECHECK)
        
        request3 = queue.dequeue()
        assert request3.node_id == "!node1"  # Priority 10 (LOW_PRIORITY)
        
        assert queue.is_empty()
    
    def test_fifo_ordering_same_priority(self):
        """Test that requests with same priority are processed in FIFO order"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue multiple requests with same priority
        queue.enqueue("!node1", TraceroutePriority.PERIODIC_RECHECK, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        queue.enqueue("!node3", TraceroutePriority.PERIODIC_RECHECK, "third")
        
        # Dequeue and verify FIFO order
        request1 = queue.dequeue()
        assert request1.node_id == "!node1"
        
        request2 = queue.dequeue()
        assert request2.node_id == "!node2"
        
        request3 = queue.dequeue()
        assert request3.node_id == "!node3"
    
    def test_duplicate_detection(self):
        """Test that duplicate requests for the same node are rejected"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue first request
        result1 = queue.enqueue("!12345678", TraceroutePriority.NEW_NODE, "first")
        assert result1 is True
        assert queue.size() == 1
        
        # Try to enqueue duplicate
        result2 = queue.enqueue("!12345678", TraceroutePriority.PERIODIC_RECHECK, "duplicate")
        assert result2 is False
        assert queue.size() == 1  # Size should not change
    
    def test_duplicate_with_higher_priority_updates(self):
        """Test that duplicate with higher priority updates the existing request"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue with low priority
        queue.enqueue("!12345678", TraceroutePriority.PERIODIC_RECHECK, "low_priority")
        assert queue.size() == 1
        
        # Enqueue same node with higher priority (lower number)
        result = queue.enqueue("!12345678", TraceroutePriority.NEW_NODE, "high_priority")
        assert result is True
        assert queue.size() == 1  # Still only one request
        
        # Dequeue and verify it has the higher priority
        request = queue.dequeue()
        assert request.node_id == "!12345678"
        assert request.priority == TraceroutePriority.NEW_NODE
        assert request.reason == "high_priority"
    
    def test_remove_specific_node(self):
        """Test removing a specific node's request from the queue"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue multiple requests
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "third")
        
        assert queue.size() == 3
        assert queue.contains("!node2")
        
        # Remove node2
        result = queue.remove("!node2")
        assert result is True
        assert queue.size() == 2
        assert not queue.contains("!node2")
        
        # Verify other nodes are still there
        assert queue.contains("!node1")
        assert queue.contains("!node3")
    
    def test_clear_queue(self):
        """Test clearing all requests from the queue"""
        queue = PriorityQueue(max_size=10)
        
        # Enqueue multiple requests
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "third")
        
        assert queue.size() == 3
        
        # Clear queue
        queue.clear()
        
        assert queue.size() == 0
        assert queue.is_empty()
        assert not queue.contains("!node1")
        assert not queue.contains("!node2")
        assert not queue.contains("!node3")
    
    def test_is_full(self):
        """Test queue full detection"""
        queue = PriorityQueue(max_size=3)
        
        assert not queue.is_full()
        
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        assert not queue.is_full()
        
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        assert not queue.is_full()
        
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "third")
        assert queue.is_full()


class TestQueueOverflowStrategies:
    """Test queue overflow handling strategies"""
    
    def test_drop_lowest_priority_strategy(self):
        """Test drop_lowest_priority overflow strategy"""
        queue = PriorityQueue(max_size=3, overflow_strategy="drop_lowest_priority")
        
        # Fill queue
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "high")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "medium")
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "low")
        
        assert queue.is_full()
        
        # Try to add higher priority request (should drop lowest priority)
        result = queue.enqueue("!node4", TraceroutePriority.NODE_BACK_ONLINE, "new_high")
        
        assert result is True
        assert queue.size() == 3
        assert not queue.contains("!node3")  # Lowest priority should be dropped
        assert queue.contains("!node4")
    
    def test_drop_lowest_priority_rejects_lower_priority(self):
        """Test that drop_lowest_priority rejects new request if it has lower priority"""
        queue = PriorityQueue(max_size=3, overflow_strategy="drop_lowest_priority")
        
        # Fill queue with high priority requests
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "high1")
        queue.enqueue("!node2", TraceroutePriority.CRITICAL, "high2")
        queue.enqueue("!node3", TraceroutePriority.NODE_BACK_ONLINE, "high3")
        
        assert queue.is_full()
        
        # Try to add lower priority request (should be rejected)
        result = queue.enqueue("!node4", TraceroutePriority.LOW_PRIORITY, "low")
        
        assert result is False
        assert queue.size() == 3
        assert not queue.contains("!node4")
    
    def test_drop_oldest_strategy(self):
        """Test drop_oldest overflow strategy"""
        queue = PriorityQueue(max_size=3, overflow_strategy="drop_oldest")
        
        # Fill queue
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "third")
        
        assert queue.is_full()
        
        # Try to add new request (should drop oldest)
        result = queue.enqueue("!node4", TraceroutePriority.PERIODIC_RECHECK, "fourth")
        
        assert result is True
        assert queue.size() == 3
        assert not queue.contains("!node1")  # Oldest should be dropped
        assert queue.contains("!node4")
    
    def test_drop_new_strategy(self):
        """Test drop_new overflow strategy"""
        queue = PriorityQueue(max_size=3, overflow_strategy="drop_new")
        
        # Fill queue
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        queue.enqueue("!node3", TraceroutePriority.LOW_PRIORITY, "third")
        
        assert queue.is_full()
        
        # Try to add new request (should be rejected)
        result = queue.enqueue("!node4", TraceroutePriority.CRITICAL, "fourth")
        
        assert result is False
        assert queue.size() == 3
        assert not queue.contains("!node4")  # New request should be rejected
        
        # Verify original requests are still there
        assert queue.contains("!node1")
        assert queue.contains("!node2")
        assert queue.contains("!node3")


class TestQueueStatistics:
    """Test queue statistics tracking"""
    
    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly"""
        queue = PriorityQueue(max_size=5)
        
        # Initial statistics
        stats = queue.get_statistics()
        assert stats['current_size'] == 0
        assert stats['total_enqueued'] == 0
        assert stats['total_dequeued'] == 0
        assert stats['total_dropped'] == 0
        
        # Enqueue some requests
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "first")
        queue.enqueue("!node2", TraceroutePriority.PERIODIC_RECHECK, "second")
        
        stats = queue.get_statistics()
        assert stats['current_size'] == 2
        assert stats['total_enqueued'] == 2
        assert stats['total_dequeued'] == 0
        
        # Dequeue one
        queue.dequeue()
        
        stats = queue.get_statistics()
        assert stats['current_size'] == 1
        assert stats['total_enqueued'] == 2
        assert stats['total_dequeued'] == 1
    
    def test_dropped_count_tracking(self):
        """Test that dropped requests are counted"""
        queue = PriorityQueue(max_size=2, overflow_strategy="drop_lowest_priority")
        
        # Fill queue
        queue.enqueue("!node1", TraceroutePriority.NEW_NODE, "high")
        queue.enqueue("!node2", TraceroutePriority.LOW_PRIORITY, "low")
        
        # Try to add higher priority (should drop lowest)
        queue.enqueue("!node3", TraceroutePriority.CRITICAL, "critical")
        
        stats = queue.get_statistics()
        assert stats['total_dropped'] == 1


class TestTracerouteRequestDataclass:
    """Test TracerouteRequest dataclass"""
    
    def test_request_creation(self):
        """Test creating a TracerouteRequest"""
        now = datetime.now()
        request = TracerouteRequest(
            request_id="test_123",
            node_id="!12345678",
            priority=TraceroutePriority.NEW_NODE,
            reason="test_reason",
            queued_at=now,
            retry_count=0
        )
        
        assert request.request_id == "test_123"
        assert request.node_id == "!12345678"
        assert request.priority == TraceroutePriority.NEW_NODE
        assert request.reason == "test_reason"
        assert request.queued_at == now
        assert request.retry_count == 0
    
    def test_request_ordering_by_priority(self):
        """Test that requests are ordered by priority"""
        now = datetime.now()
        
        request1 = TracerouteRequest(
            request_id="1",
            node_id="!node1",
            priority=TraceroutePriority.LOW_PRIORITY,
            reason="low",
            queued_at=now
        )
        
        request2 = TracerouteRequest(
            request_id="2",
            node_id="!node2",
            priority=TraceroutePriority.NEW_NODE,
            reason="high",
            queued_at=now
        )
        
        # Lower priority number should be "less than"
        assert request2 < request1
    
    def test_request_ordering_by_timestamp_same_priority(self):
        """Test that requests with same priority are ordered by timestamp"""
        from datetime import timedelta
        
        now = datetime.now()
        later = now + timedelta(seconds=1)
        
        request1 = TracerouteRequest(
            request_id="1",
            node_id="!node1",
            priority=TraceroutePriority.PERIODIC_RECHECK,
            reason="first",
            queued_at=now
        )
        
        request2 = TracerouteRequest(
            request_id="2",
            node_id="!node2",
            priority=TraceroutePriority.PERIODIC_RECHECK,
            reason="second",
            queued_at=later
        )
        
        # Earlier timestamp should be "less than"
        assert request1 < request2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
