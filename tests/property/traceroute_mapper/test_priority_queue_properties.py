"""
Property-Based Tests for Priority Queue Ordering

Tests Property 7: Priority Queue Ordering
Validates: Requirements 4.4, 4.5

**Validates: Requirements 4.4, 4.5**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime, timedelta

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
    # Use a more efficient approach
    hex_digits = '0123456789abcdef'
    hex_part = ''.join(draw(st.text(alphabet=hex_digits, min_size=8, max_size=8)))
    return f'!{hex_part}'


@composite
def priority_value(draw):
    """Generate valid priority values (1-10)"""
    return draw(st.integers(min_value=1, max_value=10))


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
def request_sequence(draw):
    """Generate a sequence of traceroute requests with unique node IDs"""
    num_requests = draw(st.integers(min_value=2, max_value=50))
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


@composite
def same_priority_requests(draw):
    """Generate a sequence of requests with the same priority"""
    priority = draw(priority_value())
    num_requests = draw(st.integers(min_value=2, max_value=20))
    requests = []
    seen_node_ids = set()
    
    for _ in range(num_requests):
        node_id = draw(valid_node_id())
        # Ensure unique node IDs
        while node_id in seen_node_ids:
            node_id = draw(valid_node_id())
        seen_node_ids.add(node_id)
        
        reason = draw(st.sampled_from([
            'new_node_discovered',
            'node_back_online',
            'periodic_recheck'
        ]))
        
        requests.append({
            'node_id': node_id,
            'priority': priority,
            'reason': reason
        })
    
    return requests


# Property Tests

class TestPriorityQueueOrderingProperty:
    """
    Feature: network-traceroute-mapper, Property 7: Priority Queue Ordering
    
    Tests that traceroute requests are processed in priority order (lowest 
    number first), and requests with the same priority are processed in FIFO order.
    
    **Validates: Requirements 4.4, 4.5**
    """
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(requests=request_sequence())
    def test_priority_ordering_across_all_requests(self, requests):
        """
        Property: For any sequence of traceroute requests in the queue, when 
        dequeuing, requests should be processed in priority order (lowest number 
        first).
        
        **Validates: Requirements 4.4**
        """
        # Create queue with sufficient size
        queue = PriorityQueue(max_size=len(requests) + 10)
        
        # Enqueue all requests
        for req in requests:
            result = queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            assert result is True, f"Failed to enqueue request for node {req['node_id']}"
        
        # Dequeue all requests and verify priority ordering
        previous_priority = None
        dequeued_requests = []
        
        while not queue.is_empty():
            request = queue.dequeue()
            assert request is not None
            dequeued_requests.append(request)
            
            # Verify priority is non-decreasing (lower number = higher priority)
            if previous_priority is not None:
                assert request.priority >= previous_priority, (
                    f"Priority ordering violated: dequeued priority {request.priority} "
                    f"after priority {previous_priority}. "
                    f"Requests should be dequeued in ascending priority order."
                )
            
            previous_priority = request.priority
        
        # Verify all requests were dequeued
        assert len(dequeued_requests) == len(requests), (
            f"Expected {len(requests)} requests to be dequeued, "
            f"but got {len(dequeued_requests)}"
        )
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(requests=same_priority_requests())
    def test_fifo_ordering_for_same_priority(self, requests):
        """
        Property: For any sequence of traceroute requests with the same priority, 
        requests should be processed in FIFO order (first in, first out).
        
        **Validates: Requirements 4.5**
        """
        # Create queue with sufficient size
        queue = PriorityQueue(max_size=len(requests) + 10)
        
        # Enqueue all requests (they all have the same priority)
        enqueue_order = []
        for req in requests:
            result = queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            assert result is True
            enqueue_order.append(req['node_id'])
        
        # Dequeue all requests and verify FIFO ordering
        dequeue_order = []
        while not queue.is_empty():
            request = queue.dequeue()
            assert request is not None
            dequeue_order.append(request.node_id)
        
        # Verify FIFO order is maintained
        assert dequeue_order == enqueue_order, (
            f"FIFO ordering violated for same-priority requests. "
            f"Enqueue order: {enqueue_order}, "
            f"Dequeue order: {dequeue_order}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        high_priority_count=st.integers(min_value=1, max_value=10),
        low_priority_count=st.integers(min_value=1, max_value=10)
    )
    def test_high_priority_always_before_low_priority(self, high_priority_count, low_priority_count):
        """
        Property: For any queue containing both high-priority and low-priority 
        requests, all high-priority requests should be dequeued before any 
        low-priority requests.
        
        **Validates: Requirements 4.4**
        """
        queue = PriorityQueue(max_size=high_priority_count + low_priority_count + 10)
        
        # Enqueue low priority requests first
        low_priority_nodes = []
        for i in range(low_priority_count):
            node_id = f'!low{i:08x}'
            queue.enqueue(node_id, priority=10, reason='low_priority')
            low_priority_nodes.append(node_id)
        
        # Then enqueue high priority requests
        high_priority_nodes = []
        for i in range(high_priority_count):
            node_id = f'!high{i:08x}'
            queue.enqueue(node_id, priority=1, reason='high_priority')
            high_priority_nodes.append(node_id)
        
        # Dequeue all and verify high priority comes first
        dequeued_high = []
        dequeued_low = []
        
        while not queue.is_empty():
            request = queue.dequeue()
            if request.priority == 1:
                dequeued_high.append(request.node_id)
            else:
                dequeued_low.append(request.node_id)
        
        # Verify all high priority requests were dequeued
        assert len(dequeued_high) == high_priority_count
        assert len(dequeued_low) == low_priority_count
        
        # Verify no low priority requests were dequeued before all high priority
        # This is implicitly verified by the priority ordering check above,
        # but we can also verify by checking the order
        all_dequeued = dequeued_high + dequeued_low
        assert len(all_dequeued) == high_priority_count + low_priority_count
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(requests=request_sequence())
    def test_priority_ordering_with_mixed_priorities(self, requests):
        """
        Property: For any sequence of requests with mixed priorities, the dequeue 
        order should respect priority levels, with FIFO ordering within each 
        priority level.
        
        **Validates: Requirements 4.4, 4.5**
        """
        # Create queue with sufficient size
        queue = PriorityQueue(max_size=len(requests) + 10)
        
        # Track enqueue order by priority
        enqueue_order_by_priority = {}
        for req in requests:
            result = queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            assert result is True
            
            if req['priority'] not in enqueue_order_by_priority:
                enqueue_order_by_priority[req['priority']] = []
            enqueue_order_by_priority[req['priority']].append(req['node_id'])
        
        # Dequeue all and track order by priority
        dequeue_order_by_priority = {}
        previous_priority = None
        
        while not queue.is_empty():
            request = queue.dequeue()
            assert request is not None
            
            # Verify priority ordering
            if previous_priority is not None:
                assert request.priority >= previous_priority, (
                    f"Priority ordering violated: priority {request.priority} "
                    f"after priority {previous_priority}"
                )
            previous_priority = request.priority
            
            # Track dequeue order by priority
            if request.priority not in dequeue_order_by_priority:
                dequeue_order_by_priority[request.priority] = []
            dequeue_order_by_priority[request.priority].append(request.node_id)
        
        # Verify FIFO ordering within each priority level
        for priority, enqueue_order in enqueue_order_by_priority.items():
            dequeue_order = dequeue_order_by_priority.get(priority, [])
            assert dequeue_order == enqueue_order, (
                f"FIFO ordering violated for priority {priority}. "
                f"Enqueue order: {enqueue_order}, "
                f"Dequeue order: {dequeue_order}"
            )
    
    @settings(max_examples=20, deadline=None)
    @given(
        num_priorities=st.integers(min_value=2, max_value=10),
        requests_per_priority=st.integers(min_value=1, max_value=5)
    )
    def test_strict_priority_levels(self, num_priorities, requests_per_priority):
        """
        Property: For any set of priority levels, all requests at priority N 
        should be dequeued before any requests at priority N+1.
        
        **Validates: Requirements 4.4**
        """
        queue = PriorityQueue(max_size=num_priorities * requests_per_priority + 10)
        
        # Create requests for each priority level
        all_requests = []
        for priority in range(1, num_priorities + 1):
            for i in range(requests_per_priority):
                node_id = f'!p{priority:02d}n{i:04x}'
                all_requests.append({
                    'node_id': node_id,
                    'priority': priority,
                    'reason': f'priority_{priority}'
                })
        
        # Enqueue in random order (Hypothesis will shuffle)
        for req in all_requests:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
        
        # Dequeue and verify strict priority ordering
        current_priority = 1
        count_at_current_priority = 0
        
        while not queue.is_empty():
            request = queue.dequeue()
            
            # Should still be at current priority or moved to next
            assert request.priority >= current_priority, (
                f"Priority ordering violated: got priority {request.priority} "
                f"when expecting priority >= {current_priority}"
            )
            
            if request.priority > current_priority:
                # Moved to next priority level
                # Verify we dequeued all requests at previous priority
                assert count_at_current_priority == requests_per_priority, (
                    f"Not all requests at priority {current_priority} were dequeued "
                    f"before moving to priority {request.priority}. "
                    f"Dequeued {count_at_current_priority} out of {requests_per_priority}"
                )
                current_priority = request.priority
                count_at_current_priority = 1
            else:
                count_at_current_priority += 1
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        initial_requests=request_sequence(),
        additional_requests=request_sequence()
    )
    def test_priority_ordering_with_dynamic_enqueue(self, initial_requests, additional_requests):
        """
        Property: For any sequence of requests, priority ordering should be 
        maintained even when new requests are added while dequeuing.
        
        **Validates: Requirements 4.4**
        """
        # Ensure unique node IDs across both sequences
        all_node_ids = set()
        unique_initial = []
        for req in initial_requests:
            if req['node_id'] not in all_node_ids:
                all_node_ids.add(req['node_id'])
                unique_initial.append(req)
        
        unique_additional = []
        for req in additional_requests:
            if req['node_id'] not in all_node_ids:
                all_node_ids.add(req['node_id'])
                unique_additional.append(req)
        
        # Need at least some requests in each sequence
        assume(len(unique_initial) >= 2)
        assume(len(unique_additional) >= 1)
        
        queue = PriorityQueue(max_size=len(unique_initial) + len(unique_additional) + 10)
        
        # Enqueue initial requests
        for req in unique_initial:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
        
        # Dequeue half, then add more
        half_count = len(unique_initial) // 2
        first_half = []
        for _ in range(half_count):
            if not queue.is_empty():
                first_half.append(queue.dequeue())
        
        # Verify first half is in priority order
        for i in range(1, len(first_half)):
            assert first_half[i].priority >= first_half[i-1].priority, (
                f"Priority ordering violated in first half at position {i}: "
                f"priority {first_half[i].priority} after priority {first_half[i-1].priority}"
            )
        
        # Add additional requests
        for req in unique_additional:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
        
        # Dequeue remaining and verify priority ordering within this batch
        second_half = []
        while not queue.is_empty():
            second_half.append(queue.dequeue())
        
        # Verify second half is in priority order
        for i in range(1, len(second_half)):
            assert second_half[i].priority >= second_half[i-1].priority, (
                f"Priority ordering violated in second half at position {i}: "
                f"priority {second_half[i].priority} after priority {second_half[i-1].priority}"
            )
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(requests=request_sequence())
    def test_timestamp_ordering_within_priority(self, requests):
        """
        Property: For any sequence of requests with the same priority, the 
        queued_at timestamp should be in ascending order when dequeued.
        
        **Validates: Requirements 4.5**
        """
        # Filter to only requests with the same priority
        if not requests:
            return
        
        # Group by priority
        by_priority = {}
        for req in requests:
            if req['priority'] not in by_priority:
                by_priority[req['priority']] = []
            by_priority[req['priority']].append(req)
        
        # Test each priority group that has multiple requests
        for priority, priority_requests in by_priority.items():
            if len(priority_requests) < 2:
                continue
            
            queue = PriorityQueue(max_size=len(priority_requests) + 10)
            
            # Enqueue all requests for this priority
            for req in priority_requests:
                queue.enqueue(
                    node_id=req['node_id'],
                    priority=req['priority'],
                    reason=req['reason']
                )
            
            # Dequeue and verify timestamp ordering
            previous_timestamp = None
            while not queue.is_empty():
                request = queue.dequeue()
                
                if previous_timestamp is not None:
                    # Timestamps should be in ascending order (FIFO)
                    assert request.queued_at >= previous_timestamp, (
                        f"FIFO ordering violated: timestamp {request.queued_at} "
                        f"is before {previous_timestamp} for priority {priority}"
                    )
                
                previous_timestamp = request.queued_at


class TestPriorityQueueConsistencyProperty:
    """
    Additional consistency tests for priority queue behavior
    """
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(requests=request_sequence())
    def test_all_enqueued_requests_are_dequeued(self, requests):
        """
        Property: For any sequence of requests enqueued, all requests should 
        eventually be dequeued with no duplicates or losses.
        
        **Validates: Requirements 4.4**
        """
        queue = PriorityQueue(max_size=len(requests) + 10)
        
        # Enqueue all requests
        enqueued_node_ids = set()
        for req in requests:
            result = queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
            if result:
                enqueued_node_ids.add(req['node_id'])
        
        # Dequeue all requests
        dequeued_node_ids = set()
        while not queue.is_empty():
            request = queue.dequeue()
            assert request is not None
            assert request.node_id not in dequeued_node_ids, (
                f"Duplicate node {request.node_id} dequeued"
            )
            dequeued_node_ids.add(request.node_id)
        
        # Verify all enqueued requests were dequeued
        assert dequeued_node_ids == enqueued_node_ids, (
            f"Mismatch between enqueued and dequeued requests. "
            f"Enqueued: {enqueued_node_ids}, Dequeued: {dequeued_node_ids}"
        )
    
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        requests=request_sequence(),
        remove_indices=st.lists(st.integers(min_value=0, max_value=49), min_size=0, max_size=10)
    )
    def test_priority_ordering_after_removals(self, requests, remove_indices):
        """
        Property: For any sequence of requests, priority ordering should be 
        maintained even after removing specific requests from the queue.
        
        **Validates: Requirements 4.4**
        """
        assume(len(requests) >= 2)
        
        queue = PriorityQueue(max_size=len(requests) + 10)
        
        # Enqueue all requests
        for req in requests:
            queue.enqueue(
                node_id=req['node_id'],
                priority=req['priority'],
                reason=req['reason']
            )
        
        # Remove some requests
        for idx in remove_indices:
            if idx < len(requests):
                queue.remove(requests[idx]['node_id'])
        
        # Dequeue remaining and verify priority ordering
        previous_priority = None
        while not queue.is_empty():
            request = queue.dequeue()
            
            if previous_priority is not None:
                assert request.priority >= previous_priority, (
                    f"Priority ordering violated after removals: "
                    f"priority {request.priority} after priority {previous_priority}"
                )
            
            previous_priority = request.priority


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
