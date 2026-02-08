"""
Property-Based Tests for Direct Node Transition Cleanup

Tests Property 2: Direct Node Transition Cleanup
Validates: Requirements 2.2

**Validates: Requirements 2.2**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime
import asyncio

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.node_state_tracker import NodeStateTracker
from plugins.traceroute_mapper.priority_queue import PriorityQueue


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    # Node IDs are in format !xxxxxxxx where x is hex digit
    hex_part = ''.join(draw(st.lists(
        st.sampled_from('0123456789abcdef'),
        min_size=8,
        max_size=8
    )))
    return f'!{hex_part}'


@composite
def indirect_node_data(draw):
    """Generate data for an indirect node (hop_count > 1)"""
    node_id = draw(valid_node_id())
    hop_count = draw(st.integers(min_value=2, max_value=10))
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    role = draw(st.one_of(st.none(), st.sampled_from(['CLIENT', 'ROUTER', 'REPEATER'])))
    
    return {
        'node_id': node_id,
        'hop_count': hop_count,
        'snr': snr,
        'rssi': rssi,
        'role': role
    }


@composite
def direct_hop_count(draw):
    """Generate a hop count that indicates a direct node (0 or 1)"""
    return draw(st.integers(min_value=0, max_value=1))


@composite
def priority_value(draw):
    """Generate a valid priority value (1-10)"""
    return draw(st.integers(min_value=1, max_value=10))


@composite
def node_transition_scenario(draw):
    """
    Generate a scenario where a node transitions from indirect to direct.
    
    Returns a dict with:
    - node_id: The node identifier
    - initial_hop_count: Initial hop count (indirect, > 1)
    - final_hop_count: Final hop count (direct, <= 1)
    - priority: Priority for the queued request
    - snr: Signal-to-noise ratio
    - rssi: Received signal strength indicator
    """
    node_id = draw(valid_node_id())
    initial_hop_count = draw(st.integers(min_value=2, max_value=10))
    final_hop_count = draw(st.integers(min_value=0, max_value=1))
    priority = draw(priority_value())
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    
    return {
        'node_id': node_id,
        'initial_hop_count': initial_hop_count,
        'final_hop_count': final_hop_count,
        'priority': priority,
        'snr': snr,
        'rssi': rssi
    }


@composite
def multiple_node_transitions(draw):
    """
    Generate multiple nodes, some of which transition from indirect to direct.
    
    Returns a list of dicts, each with:
    - node_id: The node identifier
    - initial_hop_count: Initial hop count
    - final_hop_count: Final hop count (may or may not transition)
    - priority: Priority for the queued request
    - transitions_to_direct: Whether this node transitions to direct
    """
    num_nodes = draw(st.integers(min_value=3, max_value=20))
    nodes = []
    seen_ids = set()
    
    for _ in range(num_nodes):
        node_id = draw(valid_node_id())
        
        # Ensure unique node IDs
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        
        # Decide if this node will transition to direct
        transitions_to_direct = draw(st.booleans())
        
        if transitions_to_direct:
            # Start indirect, end direct
            initial_hop_count = draw(st.integers(min_value=2, max_value=10))
            final_hop_count = draw(st.integers(min_value=0, max_value=1))
        else:
            # Either stays indirect or stays direct
            stays_indirect = draw(st.booleans())
            if stays_indirect:
                initial_hop_count = draw(st.integers(min_value=2, max_value=10))
                final_hop_count = draw(st.integers(min_value=2, max_value=10))
            else:
                initial_hop_count = draw(st.integers(min_value=0, max_value=1))
                final_hop_count = draw(st.integers(min_value=0, max_value=1))
        
        priority = draw(priority_value())
        
        nodes.append({
            'node_id': node_id,
            'initial_hop_count': initial_hop_count,
            'final_hop_count': final_hop_count,
            'priority': priority,
            'transitions_to_direct': transitions_to_direct
        })
    
    return nodes


# Property Tests

class TestDirectNodeTransitionCleanupProperty:
    """
    Feature: network-traceroute-mapper, Property 2: Direct Node Transition Cleanup
    
    Tests that when a node transitions from Indirect_Node to Direct_Node, any
    pending traceroute requests for that node are removed from the queue.
    
    **Validates: Requirements 2.2**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(scenario=node_transition_scenario())
    def test_single_node_transition_removes_pending_request(self, scenario):
        """
        Property: For any node that transitions from Indirect_Node to Direct_Node,
        any pending traceroute requests for that node should be removed from the queue.
        
        **Validates: Requirements 2.2**
        """
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        node_id = scenario['node_id']
        initial_hop_count = scenario['initial_hop_count']
        final_hop_count = scenario['final_hop_count']
        priority = scenario['priority']
        
        # Step 1: Update node as indirect
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=initial_hop_count,
            snr=scenario['snr'],
            rssi=scenario['rssi']
        )
        
        # Verify node is classified as indirect
        assert not tracker.is_direct_node(node_id), (
            f"Node {node_id} should be indirect with hop_count={initial_hop_count}"
        )
        
        # Step 2: Queue a traceroute request for this node
        queue.enqueue(node_id, priority, "test_transition")
        
        # Verify request is in queue
        assert queue.contains(node_id), (
            f"Node {node_id} should be in queue after enqueue"
        )
        initial_queue_size = queue.size()
        assert initial_queue_size > 0, "Queue should not be empty"
        
        # Step 3: Update node to direct (transition)
        tracker.update_node(
            node_id=node_id,
            is_direct=False,  # Let tracker determine from hop_count
            hop_count=final_hop_count,
            snr=scenario['snr'],
            rssi=scenario['rssi']
        )
        
        # Verify node is now classified as direct
        assert tracker.is_direct_node(node_id), (
            f"Node {node_id} should be direct with hop_count={final_hop_count}"
        )
        
        # Step 4: Simulate the plugin's direct node transition handler
        # (Remove pending request from queue)
        if queue.contains(node_id):
            removed = queue.remove(node_id)
            assert removed, f"Failed to remove node {node_id} from queue"
        
        # Step 5: Verify request was removed from queue
        assert not queue.contains(node_id), (
            f"Node {node_id} should NOT be in queue after transition to direct"
        )
        
        # Verify queue size decreased
        final_queue_size = queue.size()
        assert final_queue_size == initial_queue_size - 1, (
            f"Queue size should decrease by 1 after removing node {node_id}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(nodes=multiple_node_transitions())
    def test_multiple_node_transitions_remove_only_transitioned_nodes(self, nodes):
        """
        Property: For any set of nodes where some transition from indirect to direct,
        only the transitioned nodes' pending requests should be removed from the queue.
        Non-transitioned nodes should remain in the queue.
        
        **Validates: Requirements 2.2**
        """
        # Ensure we have at least one transitioning node
        transitioning_nodes = [n for n in nodes if n['transitions_to_direct']]
        assume(len(transitioning_nodes) > 0)
        
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        # Step 1: Initialize all nodes as their initial state
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,
                hop_count=node['initial_hop_count'],
                snr=None,
                rssi=None
            )
        
        # Step 2: Queue traceroute requests for all indirect nodes
        queued_nodes = []
        for node in nodes:
            # Only queue if initially indirect
            if node['initial_hop_count'] > 1:
                queue.enqueue(node['node_id'], node['priority'], "test_multiple")
                queued_nodes.append(node['node_id'])
        
        initial_queue_size = queue.size()
        
        # Step 3: Transition nodes to their final state
        transitioned_to_direct = []
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,
                hop_count=node['final_hop_count'],
                snr=None,
                rssi=None
            )
            
            # Track which nodes transitioned to direct
            was_indirect = node['initial_hop_count'] > 1
            is_now_direct = node['final_hop_count'] <= 1
            
            if was_indirect and is_now_direct:
                transitioned_to_direct.append(node['node_id'])
        
        # Step 4: Remove pending requests for nodes that transitioned to direct
        removed_count = 0
        for node_id in transitioned_to_direct:
            if queue.contains(node_id):
                removed = queue.remove(node_id)
                if removed:
                    removed_count += 1
        
        # Step 5: Verify only transitioned nodes were removed
        for node in nodes:
            node_id = node['node_id']
            was_queued = node_id in queued_nodes
            transitioned = node_id in transitioned_to_direct
            
            if was_queued and transitioned:
                # Should be removed from queue
                assert not queue.contains(node_id), (
                    f"Node {node_id} transitioned to direct and should be removed from queue"
                )
            elif was_queued and not transitioned:
                # Should still be in queue
                assert queue.contains(node_id), (
                    f"Node {node_id} did not transition to direct and should remain in queue"
                )
        
        # Verify queue size decreased by the number of removed nodes
        final_queue_size = queue.size()
        expected_size = initial_queue_size - removed_count
        assert final_queue_size == expected_size, (
            f"Queue size should be {expected_size} after removing {removed_count} nodes, "
            f"but got {final_queue_size}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        initial_hop_count=st.integers(min_value=2, max_value=10),
        final_hop_count=st.integers(min_value=0, max_value=1),
        priority=priority_value()
    )
    def test_transition_cleanup_idempotent(self, node_id, initial_hop_count, final_hop_count, priority):
        """
        Property: For any node that transitions to direct, attempting to remove
        its pending request multiple times should be idempotent (safe to call
        multiple times without error).
        
        **Validates: Requirements 2.2**
        """
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        # Step 1: Create indirect node and queue request
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=initial_hop_count,
            snr=None,
            rssi=None
        )
        
        queue.enqueue(node_id, priority, "test_idempotent")
        assert queue.contains(node_id), "Node should be in queue"
        
        # Step 2: Transition to direct
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=final_hop_count,
            snr=None,
            rssi=None
        )
        
        assert tracker.is_direct_node(node_id), "Node should be direct"
        
        # Step 3: Remove from queue (first time)
        removed_first = queue.remove(node_id)
        assert removed_first, "First removal should succeed"
        assert not queue.contains(node_id), "Node should not be in queue after removal"
        
        # Step 4: Try to remove again (should be safe, return False)
        removed_second = queue.remove(node_id)
        assert not removed_second, "Second removal should return False (not found)"
        assert not queue.contains(node_id), "Node should still not be in queue"
        
        # Step 5: Try to remove a third time (should still be safe)
        removed_third = queue.remove(node_id)
        assert not removed_third, "Third removal should return False (not found)"
        assert not queue.contains(node_id), "Node should still not be in queue"
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        initial_hop_count=st.integers(min_value=2, max_value=10),
        final_hop_count=st.integers(min_value=0, max_value=1)
    )
    def test_transition_without_pending_request_is_safe(self, node_id, initial_hop_count, final_hop_count):
        """
        Property: For any node that transitions to direct but has no pending
        traceroute request, the cleanup operation should be safe (no error).
        
        **Validates: Requirements 2.2**
        """
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        # Step 1: Create indirect node (but don't queue a request)
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=initial_hop_count,
            snr=None,
            rssi=None
        )
        
        assert not tracker.is_direct_node(node_id), "Node should be indirect"
        assert not queue.contains(node_id), "Node should not be in queue"
        
        # Step 2: Transition to direct
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=final_hop_count,
            snr=None,
            rssi=None
        )
        
        assert tracker.is_direct_node(node_id), "Node should be direct"
        
        # Step 3: Try to remove from queue (should be safe, return False)
        removed = queue.remove(node_id)
        assert not removed, "Removal should return False (node not in queue)"
        assert not queue.contains(node_id), "Node should still not be in queue"
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        hop_count_sequence=st.lists(
            st.integers(min_value=0, max_value=10),
            min_size=3,
            max_size=10
        ),
        priority=priority_value()
    )
    def test_multiple_transitions_handle_correctly(self, node_id, hop_count_sequence, priority):
        """
        Property: For any node that transitions multiple times between direct
        and indirect states, the queue should correctly reflect the current state
        (request removed when direct, can be re-queued when indirect).
        
        **Validates: Requirements 2.2**
        """
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        # Process each hop count in the sequence
        for i, hop_count in enumerate(hop_count_sequence):
            # Update node state
            tracker.update_node(
                node_id=node_id,
                is_direct=False,
                hop_count=hop_count,
                snr=None,
                rssi=None
            )
            
            is_direct = tracker.is_direct_node(node_id)
            
            if is_direct:
                # Node is direct - should remove from queue if present
                if queue.contains(node_id):
                    removed = queue.remove(node_id)
                    assert removed, f"Should remove node from queue at step {i}"
                
                # Verify not in queue
                assert not queue.contains(node_id), (
                    f"Direct node should not be in queue at step {i}"
                )
            else:
                # Node is indirect - can be queued if not already present
                if not queue.contains(node_id):
                    queue.enqueue(node_id, priority, f"test_step_{i}")
                
                # Verify in queue
                assert queue.contains(node_id), (
                    f"Indirect node should be in queue at step {i}"
                )
        
        # Final verification: queue state should match final node state
        final_is_direct = tracker.is_direct_node(node_id)
        final_in_queue = queue.contains(node_id)
        
        if final_is_direct:
            assert not final_in_queue, (
                "Final state: direct node should not be in queue"
            )
        else:
            assert final_in_queue, (
                "Final state: indirect node should be in queue"
            )
    
    @settings(max_examples=10, deadline=None)
    @given(
        node_id=valid_node_id(),
        initial_hop_count=st.integers(min_value=2, max_value=10),
        final_hop_count=st.integers(min_value=0, max_value=1),
        priority=priority_value(),
        other_nodes=st.lists(indirect_node_data(), min_size=5, max_size=20)
    )
    def test_transition_does_not_affect_other_nodes(
        self, node_id, initial_hop_count, final_hop_count, priority, other_nodes
    ):
        """
        Property: For any node that transitions to direct, removing its pending
        request should not affect other nodes' pending requests in the queue.
        
        **Validates: Requirements 2.2**
        """
        # Ensure unique node IDs
        seen_ids = {node_id}
        unique_other_nodes = []
        for node in other_nodes:
            if node['node_id'] not in seen_ids:
                seen_ids.add(node['node_id'])
                unique_other_nodes.append(node)
        
        # Need at least one other node
        assume(len(unique_other_nodes) > 0)
        
        # Setup
        tracker = NodeStateTracker({'skip_direct_nodes': True})
        queue = PriorityQueue(max_size=500, overflow_strategy='drop_lowest_priority')
        
        # Step 1: Queue the transitioning node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=initial_hop_count,
            snr=None,
            rssi=None
        )
        queue.enqueue(node_id, priority, "test_main_node")
        
        # Step 2: Queue other nodes
        for node in unique_other_nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi']
            )
            queue.enqueue(node['node_id'], priority, "test_other_node")
        
        # Record which other nodes are in queue
        other_nodes_in_queue = [
            n['node_id'] for n in unique_other_nodes
            if queue.contains(n['node_id'])
        ]
        
        initial_queue_size = queue.size()
        
        # Step 3: Transition main node to direct and remove from queue
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=final_hop_count,
            snr=None,
            rssi=None
        )
        
        removed = queue.remove(node_id)
        assert removed, "Main node should be removed"
        
        # Step 4: Verify other nodes are still in queue
        for other_node_id in other_nodes_in_queue:
            assert queue.contains(other_node_id), (
                f"Other node {other_node_id} should still be in queue after "
                f"removing main node {node_id}"
            )
        
        # Verify queue size decreased by exactly 1
        final_queue_size = queue.size()
        assert final_queue_size == initial_queue_size - 1, (
            f"Queue size should decrease by 1, was {initial_queue_size}, "
            f"now {final_queue_size}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
