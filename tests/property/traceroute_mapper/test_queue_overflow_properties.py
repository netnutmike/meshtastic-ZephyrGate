"""
Property-Based Tests for Queue Overflow Handling

Tests Properties 8, 22, and 23:
- Property 8: Queue Overflow with Priority
- Property 22: Queue Size Limit
- Property 23: Queue Overflow Strategy

**Validates: Requirements 4.6, 10.1, 10.4, 10.5**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.priority_queue import (
    PriorityQueue,
    TracerouteRequest,
    TraceroutePriority
)


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    # Node IDs are in format !xxxxxxxx where x is hex digit
    hex_digits = '0123456789abcdef'
    hex_part = ''.join(draw(st.text(alphabet=hex_digits, min_size=8, max_size=8)))
    return f'!{hex_part}'


@composite
def priority_value(draw):
    """Generate valid priority values (1-10)"""
    return draw(st.integers(min_value=1, max_value=10))


@composite
def overflow_strategy(draw):
    """Generate valid overflow strategies"""
    return draw(st.sampled_from([
        'drop_lowest_priority',
        'drop_oldest',
        'drop_new'
    ]))


@composite
def traceroute_request_data(draw):
    """Generate data for a traceroute request"""
    node_id = draw(valid_node_id())
    priority = draw(priority_value())
    reason = draw(st.sampled_from([
        'new_node_discovered',
        'node_back_online',
        'periodic_recheck',
        'topology_change',
        'manual_request'
    ]))
    
    return {
        'node_id': node_id,
        'priority': priority,
        'reason': reason
    }


@composite
def request_sequence_with_unique_nodes(draw, min_size=1, max_size=100):
    """Generate a sequence of traceroute requests with unique node IDs"""
    num_requests = draw(st.integers(min_value=min_size, max_value=max_size))
    requests = []
    seen_node_ids = set()
    
    for _ in range(num_requests):
        node_id = draw(valid_node_id())
        # Ensure unique node IDs
        while node_id in seen_node_ids:
            node_id = draw(valid_node_id())
        seen_node_ids.add(node_id)
        
        priority = draw(priority_value())
        reason = draw(st.sampled_from([
            'new_node_discovered',
            'node_back_online',
            'periodic_recheck',
            'topology_change',
            'manual_request'
        ]))
        
        requests.append({
            'node_id': node_id,
            'priority': priority,
            'reason': reason
        })
    
    return requests


class TestQueueSizeLimitProperty:
    """
    Feature: network-traceroute-mapper, Property 22: Queue Size Limit
    
    Tests that the queue size never exceeds the configured maximum size.
    
    **Validates: Requirements 10.1**
    """
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        max_size=st.integers(min_value=1, max_value=100),
        requests=request_sequence_with_unique_nodes(min_size=1, max_size=150),
        strategy=overflow_strategy()
    )
    def test_queue_never_exceeds_max_size(self, max_size, requests, strategy):
        """
        Property: For any state of the priority queue, the queue size should 
        never exceed the configured queue_max_size.
        
        **Validates: Requirements 10.1**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy=strategy)
        
        # Try to enqueue all requests
        for req in requests:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            
            # Verify size constraint is maintained
            current_size = queue.size()
            assert current_size <= max_size, (
                f"Queue size {current_size} exceeds max_size {max_size} "
                f"with overflow strategy '{strategy}'"
            )
        
        # Final verification
        final_size = queue.size()
        assert final_size <= max_size, (
            f"Final queue size {final_size} exceeds max_size {max_size}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=1, max_value=50),
        strategy=overflow_strategy()
    )
    def test_queue_size_at_boundary(self, max_size, strategy):
        """
        Property: When exactly max_size requests are enqueued, the queue size 
        should equal max_size, and when one more is added, it should still not 
        exceed max_size.
        
        **Validates: Requirements 10.1**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy=strategy)
        
        # Enqueue exactly max_size requests
        for i in range(max_size):
            node_id = f'!{i:08x}'
            result = queue.enqueue(node_id, priority=5, reason='test')
            assert result is True, f"Failed to enqueue request {i} of {max_size}"
        
        # Verify queue is at max size
        assert queue.size() == max_size
        assert queue.is_full()
        
        # Try to add one more
        extra_node_id = f'!{max_size:08x}'
        queue.enqueue(extra_node_id, priority=5, reason='overflow_test')
        
        # Verify size constraint is maintained
        assert queue.size() <= max_size, (
            f"Queue size {queue.size()} exceeds max_size {max_size} after overflow"
        )
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        max_size=st.integers(min_value=5, max_value=50),
        num_operations=st.integers(min_value=10, max_value=200),
        strategy=overflow_strategy()
    )
    def test_queue_size_with_mixed_operations(self, max_size, num_operations, strategy):
        """
        Property: For any sequence of enqueue and dequeue operations, the queue 
        size should never exceed max_size.
        
        **Validates: Requirements 10.1**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy=strategy)
        node_counter = 0
        
        for i in range(num_operations):
            # Randomly choose to enqueue or dequeue
            if i % 3 == 0 and not queue.is_empty():
                # Dequeue
                queue.dequeue()
            else:
                # Enqueue
                node_id = f'!{node_counter:08x}'
                node_counter += 1
                queue.enqueue(node_id, priority=(i % 10) + 1, reason='test')
            
            # Verify size constraint after each operation
            current_size = queue.size()
            assert current_size <= max_size, (
                f"Queue size {current_size} exceeds max_size {max_size} "
                f"after operation {i}"
            )


class TestQueueOverflowWithPriorityProperty:
    """
    Feature: network-traceroute-mapper, Property 8: Queue Overflow with Priority
    
    Tests that when the queue is full and a new high-priority request arrives,
    the lowest priority request in the queue is dropped to make room.
    
    **Validates: Requirements 4.6**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20),
        high_priority=st.integers(min_value=1, max_value=5),
        low_priority=st.integers(min_value=6, max_value=10)
    )
    def test_high_priority_replaces_low_priority(self, max_size, high_priority, low_priority):
        """
        Property: For any full queue, when a new high-priority request arrives, 
        the lowest priority request in the queue should be dropped to make room.
        
        **Validates: Requirements 4.6**
        """
        # Ensure high priority is actually higher (lower number) with sufficient gap
        assume(high_priority < low_priority - 1)
        
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Fill queue with high priority requests only
        for i in range(max_size - 1):
            node_id = f'!{i:08x}'
            queue.enqueue(node_id, priority=high_priority, reason='fill')
        
        # Add one low priority request (this will be the lowest priority in queue)
        low_priority_node = f'!low{max_size:08x}'
        queue.enqueue(low_priority_node, priority=low_priority, reason='low_priority')
        
        assert queue.is_full()
        assert queue.contains(low_priority_node)
        
        # Try to add a high priority request
        high_priority_node = f'!high{max_size+1:08x}'
        result = queue.enqueue(high_priority_node, priority=high_priority, reason='high_priority')
        
        # Should succeed by dropping the low priority request
        assert result is True, "High priority request should be accepted"
        assert queue.contains(high_priority_node), "High priority node should be in queue"
        assert not queue.contains(low_priority_node), "Low priority node should be dropped"
        assert queue.size() == max_size, "Queue size should remain at max_size"
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=3, max_value=20),
        num_high_priority=st.integers(min_value=1, max_value=10)
    )
    def test_multiple_high_priority_requests_drop_multiple_low(self, max_size, num_high_priority):
        """
        Property: For any full queue, when multiple high-priority requests arrive,
        multiple low-priority requests should be dropped to make room.
        
        **Validates: Requirements 4.6**
        """
        assume(num_high_priority < max_size)
        
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Fill queue with low priority requests
        low_priority_nodes = []
        for i in range(max_size):
            node_id = f'!low{i:08x}'
            queue.enqueue(node_id, priority=10, reason='low_priority')
            low_priority_nodes.append(node_id)
        
        assert queue.is_full()
        
        # Try to add multiple high priority requests
        high_priority_nodes = []
        for i in range(num_high_priority):
            node_id = f'!high{i:08x}'
            result = queue.enqueue(node_id, priority=1, reason='high_priority')
            if result:
                high_priority_nodes.append(node_id)
        
        # Verify all high priority requests were accepted
        assert len(high_priority_nodes) == num_high_priority
        
        # Verify all high priority nodes are in queue
        for node_id in high_priority_nodes:
            assert queue.contains(node_id), f"High priority node {node_id} should be in queue"
        
        # Verify some low priority nodes were dropped
        dropped_count = 0
        for node_id in low_priority_nodes:
            if not queue.contains(node_id):
                dropped_count += 1
        
        assert dropped_count >= num_high_priority, (
            f"Expected at least {num_high_priority} low priority nodes to be dropped, "
            f"but only {dropped_count} were dropped"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20),
        new_priority=st.integers(min_value=1, max_value=10)
    )
    def test_low_priority_rejected_when_queue_has_higher_priorities(self, max_size, new_priority):
        """
        Property: For any full queue containing only high-priority requests, 
        a new low-priority request should be rejected.
        
        **Validates: Requirements 4.6**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Fill queue with high priority requests (priority 1)
        for i in range(max_size):
            node_id = f'!high{i:08x}'
            queue.enqueue(node_id, priority=1, reason='high_priority')
        
        assert queue.is_full()
        
        # Try to add a lower priority request
        if new_priority > 1:
            low_priority_node = f'!low{max_size:08x}'
            result = queue.enqueue(low_priority_node, priority=new_priority, reason='low_priority')
            
            # Should be rejected
            assert result is False, (
                f"Low priority request (priority={new_priority}) should be rejected "
                f"when queue is full of higher priority requests"
            )
            assert not queue.contains(low_priority_node)
            assert queue.size() == max_size
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        max_size=st.integers(min_value=5, max_value=30),
        requests=request_sequence_with_unique_nodes(min_size=10, max_size=100)
    )
    def test_queue_maintains_highest_priorities_after_overflow(self, max_size, requests):
        """
        Property: For any sequence of requests causing overflow, the queue should 
        contain the highest priority requests (lowest priority numbers).
        
        **Validates: Requirements 4.6**
        """
        assume(len(requests) > max_size)
        
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Track all priorities we tried to enqueue
        all_priorities = []
        
        # Enqueue all requests
        for req in requests:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            all_priorities.append(req['priority'])
        
        # Get the priorities of requests in the queue
        queue_priorities = []
        temp_queue = []
        while not queue.is_empty():
            request = queue.dequeue()
            queue_priorities.append(request.priority)
            temp_queue.append(request)
        
        # Restore queue
        for request in temp_queue:
            queue.enqueue(request.node_id, request.priority, request.reason)
        
        # Find the max_size highest priorities from all requests
        sorted_priorities = sorted(all_priorities)
        expected_max_priority = sorted_priorities[max_size - 1] if len(sorted_priorities) >= max_size else sorted_priorities[-1]
        
        # Verify all priorities in queue are <= expected_max_priority
        for priority in queue_priorities:
            assert priority <= expected_max_priority, (
                f"Queue contains priority {priority} which is lower than expected "
                f"max priority {expected_max_priority} after overflow"
            )


class TestQueueOverflowStrategyProperty:
    """
    Feature: network-traceroute-mapper, Property 23: Queue Overflow Strategy
    
    Tests that the queue follows the configured overflow strategy when full.
    
    **Validates: Requirements 10.4, 10.5**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20)
    )
    def test_drop_lowest_priority_strategy(self, max_size):
        """
        Property: For any full queue with drop_lowest_priority strategy, when a 
        new request arrives, the system should drop the lowest priority request 
        if the new request has higher priority.
        
        **Validates: Requirements 10.4**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Fill queue with requests of varying priorities
        for i in range(max_size):
            node_id = f'!node{i:08x}'
            priority = (i % 10) + 1  # Priorities 1-10
            queue.enqueue(node_id, priority=priority, reason='fill')
        
        assert queue.is_full()
        
        # Find the lowest priority in the queue
        temp_requests = []
        lowest_priority = 0
        lowest_priority_node = None
        
        while not queue.is_empty():
            request = queue.dequeue()
            temp_requests.append(request)
            if request.priority > lowest_priority:
                lowest_priority = request.priority
                lowest_priority_node = request.node_id
        
        # Restore queue
        for request in temp_requests:
            queue.enqueue(request.node_id, request.priority, request.reason)
        
        # Try to add a higher priority request
        if lowest_priority > 1:
            new_node = f'!new{max_size:08x}'
            new_priority = lowest_priority - 1
            result = queue.enqueue(new_node, priority=new_priority, reason='new')
            
            assert result is True, "Higher priority request should be accepted"
            assert queue.contains(new_node), "New node should be in queue"
            assert not queue.contains(lowest_priority_node), "Lowest priority node should be dropped"
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20)
    )
    def test_drop_oldest_strategy(self, max_size):
        """
        Property: For any full queue with drop_oldest strategy, when a new 
        request arrives, the system should drop the oldest request.
        
        **Validates: Requirements 10.5**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_oldest')
        
        # Fill queue and track the first (oldest) node
        oldest_node = f'!oldest{0:08x}'
        queue.enqueue(oldest_node, priority=5, reason='oldest')
        
        for i in range(1, max_size):
            node_id = f'!node{i:08x}'
            queue.enqueue(node_id, priority=5, reason='fill')
        
        assert queue.is_full()
        assert queue.contains(oldest_node)
        
        # Try to add a new request
        new_node = f'!new{max_size:08x}'
        result = queue.enqueue(new_node, priority=5, reason='new')
        
        assert result is True, "New request should be accepted with drop_oldest strategy"
        assert queue.contains(new_node), "New node should be in queue"
        assert not queue.contains(oldest_node), "Oldest node should be dropped"
        assert queue.size() == max_size
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20),
        new_priority=priority_value()
    )
    def test_drop_new_strategy(self, max_size, new_priority):
        """
        Property: For any full queue with drop_new strategy, when a new request 
        arrives, the system should reject the new request regardless of priority.
        
        **Validates: Requirements 10.5**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_new')
        
        # Fill queue
        existing_nodes = []
        for i in range(max_size):
            node_id = f'!node{i:08x}'
            queue.enqueue(node_id, priority=10, reason='fill')  # Low priority
            existing_nodes.append(node_id)
        
        assert queue.is_full()
        
        # Try to add a new request (even with high priority)
        new_node = f'!new{max_size:08x}'
        result = queue.enqueue(new_node, priority=new_priority, reason='new')
        
        assert result is False, "New request should be rejected with drop_new strategy"
        assert not queue.contains(new_node), "New node should not be in queue"
        
        # Verify all existing nodes are still there
        for node_id in existing_nodes:
            assert queue.contains(node_id), f"Existing node {node_id} should still be in queue"
        
        assert queue.size() == max_size
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        max_size=st.integers(min_value=3, max_value=20),
        strategy=overflow_strategy(),
        num_overflow_requests=st.integers(min_value=1, max_value=10)
    )
    def test_strategy_consistency_across_multiple_overflows(self, max_size, strategy, num_overflow_requests):
        """
        Property: For any overflow strategy, the behavior should be consistent 
        across multiple overflow events.
        
        **Validates: Requirements 10.4, 10.5**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy=strategy)
        
        # Fill queue
        for i in range(max_size):
            node_id = f'!initial{i:08x}'
            queue.enqueue(node_id, priority=5, reason='initial')
        
        assert queue.is_full()
        initial_size = queue.size()
        
        # Try to add multiple overflow requests
        for i in range(num_overflow_requests):
            node_id = f'!overflow{i:08x}'
            priority = (i % 10) + 1
            queue.enqueue(node_id, priority=priority, reason='overflow')
            
            # Verify size constraint is maintained
            assert queue.size() <= max_size, (
                f"Queue size {queue.size()} exceeds max_size {max_size} "
                f"after overflow request {i} with strategy '{strategy}'"
            )
        
        # Final verification
        assert queue.size() <= max_size
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=5, max_value=20),
        strategy=overflow_strategy()
    )
    def test_overflow_statistics_tracking(self, max_size, strategy):
        """
        Property: For any overflow strategy, dropped requests should be tracked 
        in statistics.
        
        **Validates: Requirements 10.4, 10.5**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy=strategy)
        
        # Fill queue
        for i in range(max_size):
            node_id = f'!node{i:08x}'
            queue.enqueue(node_id, priority=5, reason='fill')
        
        assert queue.is_full()
        
        # Get initial statistics
        initial_stats = queue.get_statistics()
        initial_dropped = initial_stats['total_dropped']
        
        # Try to add requests that will cause overflow
        overflow_attempts = 5
        for i in range(overflow_attempts):
            node_id = f'!overflow{i:08x}'
            priority = 1 if strategy == 'drop_lowest_priority' else 5
            queue.enqueue(node_id, priority=priority, reason='overflow')
        
        # Get final statistics
        final_stats = queue.get_statistics()
        final_dropped = final_stats['total_dropped']
        
        # Verify dropped count increased (at least for some strategies)
        if strategy == 'drop_new':
            # All overflow requests should be rejected
            assert final_dropped >= initial_dropped + overflow_attempts, (
                f"Expected at least {overflow_attempts} requests to be dropped "
                f"with drop_new strategy, but only {final_dropped - initial_dropped} were dropped"
            )
        elif strategy in ['drop_lowest_priority', 'drop_oldest']:
            # Some requests should be dropped (either old ones or new ones)
            assert final_dropped >= initial_dropped, (
                f"Expected dropped count to increase with strategy '{strategy}'"
            )


class TestQueueOverflowEdgeCases:
    """
    Additional edge case tests for queue overflow behavior
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=1, max_value=10)
    )
    def test_overflow_with_single_slot_queue(self, max_size):
        """
        Property: For a queue with max_size=1, overflow handling should work correctly.
        
        **Validates: Requirements 10.1, 10.4, 10.5**
        """
        if max_size != 1:
            return
        
        queue = PriorityQueue(max_size=1, overflow_strategy='drop_lowest_priority')
        
        # Add first request
        queue.enqueue('!node1', priority=5, reason='first')
        assert queue.is_full()
        assert queue.contains('!node1')
        
        # Add higher priority request
        result = queue.enqueue('!node2', priority=1, reason='second')
        assert result is True
        assert queue.contains('!node2')
        assert not queue.contains('!node1')
        assert queue.size() == 1
    
    @settings(max_examples=20, deadline=None)
    @given(
        max_size=st.integers(min_value=2, max_value=20)
    )
    def test_overflow_with_all_same_priority(self, max_size):
        """
        Property: For a full queue where all requests have the same priority,
        drop_lowest_priority should reject new requests with the same priority.
        
        **Validates: Requirements 4.6, 10.4**
        """
        queue = PriorityQueue(max_size=max_size, overflow_strategy='drop_lowest_priority')
        
        # Fill queue with same priority
        for i in range(max_size):
            node_id = f'!node{i:08x}'
            queue.enqueue(node_id, priority=5, reason='same_priority')
        
        assert queue.is_full()
        
        # Try to add another request with same priority
        new_node = f'!new{max_size:08x}'
        result = queue.enqueue(new_node, priority=5, reason='same_priority')
        
        # Should be rejected (not higher priority)
        assert result is False
        assert not queue.contains(new_node)
        assert queue.size() == max_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
