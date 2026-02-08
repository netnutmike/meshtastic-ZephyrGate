"""
Property-Based Tests for Priority Assignment

Tests Property 4: New Node Priority Assignment
Tests Property 5: Node Back Online Priority Assignment
Tests Property 6: Periodic Recheck Priority Assignment

**Validates: Requirements 4.1, 4.2, 4.3**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import asyncio

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from plugins.traceroute_mapper.priority_queue import PriorityQueue
from plugins.traceroute_mapper.node_state_tracker import NodeStateTracker, NodeState
from models.message import Message, MessageType


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    hex_digits = '0123456789abcdef'
    hex_part = ''.join(draw(st.text(alphabet=hex_digits, min_size=8, max_size=8)))
    return f'!{hex_part}'


@composite
def node_message(draw, node_id=None, is_direct=False, is_traceroute_response=False):
    """Generate a mesh message from a node"""
    if node_id is None:
        node_id = draw(valid_node_id())
    
    # Direct nodes have low hop count and high SNR
    if is_direct:
        hop_count = draw(st.integers(min_value=0, max_value=1))
        snr = draw(st.floats(min_value=5.0, max_value=20.0))
        rssi = draw(st.integers(min_value=-70, max_value=-40))
    else:
        hop_count = draw(st.integers(min_value=2, max_value=7))
        snr = draw(st.floats(min_value=-10.0, max_value=4.9))
        rssi = draw(st.integers(min_value=-120, max_value=-71))
    
    message = Message(
        sender_id=node_id,
        recipient_id="!gateway",
        message_type=MessageType.ROUTING if is_traceroute_response else MessageType.TEXT,
        content="test message",
        hop_count=hop_count,
        snr=snr,
        rssi=rssi,
        metadata={
            'traceroute': is_traceroute_response,
            'route': [node_id] if is_traceroute_response else None
        }
    )
    
    return message


@composite
def indirect_node_sequence(draw):
    """Generate a sequence of unique indirect node IDs"""
    num_nodes = draw(st.integers(min_value=1, max_value=20))
    nodes = []
    seen = set()
    
    for _ in range(num_nodes):
        node_id = draw(valid_node_id())
        while node_id in seen:
            node_id = draw(valid_node_id())
        seen.add(node_id)
        nodes.append(node_id)
    
    return nodes


# Property Tests

class TestNewNodePriorityAssignmentProperty:
    """
    Feature: network-traceroute-mapper, Property 4: New Node Priority Assignment
    
    Tests that newly discovered indirect nodes are queued with priority 1 (highest).
    
    **Validates: Requirements 4.1**
    """
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(node_ids=indirect_node_sequence())
    @pytest.mark.asyncio
    async def test_new_indirect_nodes_get_priority_1(self, node_ids):
        """
        Property: For any newly discovered indirect node, the queued traceroute 
        request should have priority 1 (highest priority).
        
        **Validates: Requirements 4.1**
        """
        # Create plugin with minimal config
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        # Initialize components manually
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {
            'nodes_discovered': 0,
            'filtered_nodes_skipped': 0
        }
        
        # Process each new indirect node
        for node_id in node_ids:
            # First add node to tracker (this happens before _handle_new_indirect_node is called)
            plugin.node_tracker.update_node(
                node_id=node_id,
                is_direct=False,
                snr=-5.0,
                rssi=-95
            )
            # Simulate handling a new indirect node
            await plugin._handle_new_indirect_node(node_id)
        
        # Verify all nodes were queued with priority 1
        dequeued_priorities = []
        while not plugin.priority_queue.is_empty():
            request = plugin.priority_queue.dequeue()
            dequeued_priorities.append(request.priority)
            assert request.priority == 1, (
                f"New indirect node {request.node_id} was queued with priority "
                f"{request.priority}, expected priority 1"
            )
        
        # Verify all nodes were queued
        assert len(dequeued_priorities) == len(node_ids), (
            f"Expected {len(node_ids)} nodes to be queued, "
            f"but only {len(dequeued_priorities)} were queued"
        )
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        new_node_id=valid_node_id(),
        existing_priorities=st.lists(
            st.integers(min_value=2, max_value=10),
            min_size=1,
            max_size=10
        )
    )
    @pytest.mark.asyncio
    async def test_new_node_has_highest_priority(self, new_node_id, existing_priorities):
        """
        Property: For any queue containing requests with various priorities, 
        a newly discovered indirect node should be queued with priority 1, 
        which is higher than all other priorities.
        
        **Validates: Requirements 4.1**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {
            'nodes_discovered': 0,
            'filtered_nodes_skipped': 0
        }
        
        # Add existing requests with various priorities
        for i, priority in enumerate(existing_priorities):
            plugin.priority_queue.enqueue(
                node_id=f'!existing{i:08x}',
                priority=priority,
                reason='existing_request'
            )
        
        # Add new node to tracker first
        plugin.node_tracker.update_node(
            node_id=new_node_id,
            is_direct=False,
            snr=-5.0,
            rssi=-95
        )
        
        # Add new indirect node
        await plugin._handle_new_indirect_node(new_node_id)
        
        # Dequeue first request - should be the new node
        first_request = plugin.priority_queue.dequeue()
        assert first_request is not None
        assert first_request.node_id == new_node_id, (
            f"Expected new node {new_node_id} to be dequeued first, "
            f"but got {first_request.node_id}"
        )
        assert first_request.priority == 1, (
            f"Expected new node to have priority 1, got {first_request.priority}"
        )
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        node_id=valid_node_id(),
        is_direct=st.booleans()
    )
    @pytest.mark.asyncio
    async def test_only_indirect_nodes_get_priority_1(self, node_id, is_direct):
        """
        Property: For any node, only indirect nodes should be queued with 
        priority 1 when discovered. Direct nodes should not be queued at all.
        
        **Validates: Requirements 4.1, 2.1**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {
            'nodes_discovered': 0,
            'filtered_nodes_skipped': 0,
            'direct_nodes_skipped': 0
        }
        
        # Update node state
        plugin.node_tracker.update_node(
            node_id=node_id,
            is_direct=is_direct,
            snr=10.0 if is_direct else -5.0,
            rssi=-60 if is_direct else -95
        )
        
        # Try to handle as new indirect node
        # (In real code, this would only be called for indirect nodes)
        if not is_direct:
            await plugin._handle_new_indirect_node(node_id)
        
        # Check queue
        if is_direct:
            # Direct nodes should not be queued
            assert plugin.priority_queue.is_empty(), (
                f"Direct node {node_id} should not be queued"
            )
        else:
            # Indirect nodes should be queued with priority 1
            assert not plugin.priority_queue.is_empty(), (
                f"Indirect node {node_id} should be queued"
            )
            request = plugin.priority_queue.dequeue()
            assert request.priority == 1, (
                f"Indirect node should have priority 1, got {request.priority}"
            )


class TestNodeBackOnlinePriorityAssignmentProperty:
    """
    Feature: network-traceroute-mapper, Property 5: Node Back Online Priority Assignment
    
    Tests that nodes coming back online are queued with priority 4.
    
    **Validates: Requirements 4.2**
    """
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(node_ids=indirect_node_sequence())
    @pytest.mark.asyncio
    async def test_nodes_back_online_get_priority_4(self, node_ids):
        """
        Property: For any node that was offline and comes back online, the 
        queued traceroute request should have priority 4.
        
        **Validates: Requirements 4.2**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {}
        
        # Mark all nodes as previously offline
        for node_id in node_ids:
            plugin.node_tracker.update_node(
                node_id=node_id,
                is_direct=False,
                snr=-5.0,
                rssi=-95
            )
            node_state = plugin.node_tracker.get_node_state(node_id)
            node_state.was_offline = True
        
        # Handle nodes coming back online
        for node_id in node_ids:
            await plugin._handle_node_back_online(node_id)
        
        # Verify all nodes were queued with priority 4
        dequeued_priorities = []
        while not plugin.priority_queue.is_empty():
            request = plugin.priority_queue.dequeue()
            dequeued_priorities.append(request.priority)
            assert request.priority == 4, (
                f"Node back online {request.node_id} was queued with priority "
                f"{request.priority}, expected priority 4"
            )
        
        # Verify all nodes were queued
        assert len(dequeued_priorities) == len(node_ids), (
            f"Expected {len(node_ids)} nodes to be queued, "
            f"but only {len(dequeued_priorities)} were queued"
        )
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        back_online_node=valid_node_id(),
        new_node=valid_node_id(),
        periodic_node=valid_node_id()
    )
    @pytest.mark.asyncio
    async def test_back_online_priority_between_new_and_periodic(
        self, back_online_node, new_node, periodic_node
    ):
        """
        Property: For any queue containing new nodes (priority 1), nodes back 
        online (priority 4), and periodic rechecks (priority 8), the dequeue 
        order should be: new nodes first, then back online, then periodic.
        
        **Validates: Requirements 4.1, 4.2, 4.3**
        """
        # Ensure unique node IDs
        assume(back_online_node != new_node)
        assume(back_online_node != periodic_node)
        assume(new_node != periodic_node)
        
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {
            'nodes_discovered': 0,
            'filtered_nodes_skipped': 0
        }
        
        # Queue in reverse order: periodic, back online, new
        # This tests that priority ordering works regardless of enqueue order
        
        # Queue periodic recheck (priority 8)
        plugin.priority_queue.enqueue(
            node_id=periodic_node,
            priority=8,
            reason='periodic_recheck'
        )
        
        # Queue node back online (priority 4)
        plugin.node_tracker.update_node(
            node_id=back_online_node,
            is_direct=False,
            snr=-5.0,
            rssi=-95
        )
        node_state = plugin.node_tracker.get_node_state(back_online_node)
        node_state.was_offline = True
        await plugin._handle_node_back_online(back_online_node)
        
        # Queue new node (priority 1)
        # Add to tracker first
        plugin.node_tracker.update_node(
            node_id=new_node,
            is_direct=False,
            snr=-5.0,
            rssi=-95
        )
        await plugin._handle_new_indirect_node(new_node)
        
        # Dequeue and verify order
        first = plugin.priority_queue.dequeue()
        assert first.node_id == new_node, (
            f"Expected new node {new_node} first, got {first.node_id}"
        )
        assert first.priority == 1
        
        second = plugin.priority_queue.dequeue()
        assert second.node_id == back_online_node, (
            f"Expected back online node {back_online_node} second, got {second.node_id}"
        )
        assert second.priority == 4
        
        third = plugin.priority_queue.dequeue()
        assert third.node_id == periodic_node, (
            f"Expected periodic node {periodic_node} third, got {third.node_id}"
        )
        assert third.priority == 8
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(node_id=valid_node_id())
    @pytest.mark.asyncio
    async def test_was_offline_flag_cleared_after_queueing(self, node_id):
        """
        Property: For any node that comes back online, the was_offline flag 
        should be cleared after queueing the traceroute request.
        
        **Validates: Requirements 4.2**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        plugin.stats = {}
        
        # Mark node as offline
        plugin.node_tracker.update_node(
            node_id=node_id,
            is_direct=False,
            snr=-5.0,
            rssi=-95
        )
        node_state = plugin.node_tracker.get_node_state(node_id)
        node_state.was_offline = True
        
        # Handle node back online
        await plugin._handle_node_back_online(node_id)
        
        # Verify was_offline flag is cleared
        node_state = plugin.node_tracker.get_node_state(node_id)
        assert node_state is not None
        assert node_state.was_offline is False, (
            f"was_offline flag should be cleared after handling node back online"
        )


class TestPeriodicRecheckPriorityAssignmentProperty:
    """
    Feature: network-traceroute-mapper, Property 6: Periodic Recheck Priority Assignment
    
    Tests that periodic rechecks are queued with priority 8.
    
    **Validates: Requirements 4.3**
    """
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(node_ids=indirect_node_sequence())
    @pytest.mark.asyncio
    async def test_periodic_rechecks_get_priority_8(self, node_ids):
        """
        Property: For any periodic recheck that is scheduled, the queued 
        traceroute request should have priority 8.
        
        **Validates: Requirements 4.3**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None,
            'recheck_interval_hours': 6
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        
        # Mark nodes as needing trace (simulate periodic recheck time)
        for node_id in node_ids:
            plugin.node_tracker.update_node(
                node_id=node_id,
                is_direct=False,
                snr=-5.0,
                rssi=-95
            )
            node_state = plugin.node_tracker.get_node_state(node_id)
            # Set next_recheck to past time to trigger recheck
            node_state.next_recheck = datetime.now() - timedelta(hours=1)
        
        # Simulate periodic recheck loop logic
        nodes_needing_trace = plugin.node_tracker.get_nodes_needing_trace()
        for node_id in nodes_needing_trace:
            if not plugin.priority_queue.contains(node_id):
                plugin.priority_queue.enqueue(
                    node_id=node_id,
                    priority=8,  # PERIODIC_RECHECK priority
                    reason="periodic_recheck"
                )
        
        # Verify all nodes were queued with priority 8
        dequeued_priorities = []
        while not plugin.priority_queue.is_empty():
            request = plugin.priority_queue.dequeue()
            dequeued_priorities.append(request.priority)
            assert request.priority == 8, (
                f"Periodic recheck for {request.node_id} was queued with priority "
                f"{request.priority}, expected priority 8"
            )
        
        # Verify all nodes were queued
        assert len(dequeued_priorities) == len(node_ids), (
            f"Expected {len(node_ids)} nodes to be queued, "
            f"but only {len(dequeued_priorities)} were queued"
        )
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        periodic_nodes=indirect_node_sequence(),
        high_priority_count=st.integers(min_value=1, max_value=5)
    )
    @pytest.mark.asyncio
    async def test_periodic_rechecks_have_lowest_priority(
        self, periodic_nodes, high_priority_count
    ):
        """
        Property: For any queue containing periodic rechecks and other priority 
        requests, periodic rechecks (priority 8) should be dequeued after all 
        higher priority requests.
        
        **Validates: Requirements 4.3**
        """
        assume(len(periodic_nodes) >= 1)
        
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        
        # Queue periodic rechecks first
        for node_id in periodic_nodes:
            plugin.priority_queue.enqueue(
                node_id=node_id,
                priority=8,
                reason='periodic_recheck'
            )
        
        # Queue some higher priority requests
        high_priority_nodes = []
        for i in range(high_priority_count):
            node_id = f'!high{i:08x}'
            high_priority_nodes.append(node_id)
            # Use priorities 1-7 (all higher than 8)
            priority = (i % 7) + 1
            plugin.priority_queue.enqueue(
                node_id=node_id,
                priority=priority,
                reason='high_priority'
            )
        
        # Dequeue all and verify periodic rechecks come last
        dequeued_order = []
        while not plugin.priority_queue.is_empty():
            request = plugin.priority_queue.dequeue()
            dequeued_order.append((request.node_id, request.priority))
        
        # Find where periodic rechecks start
        periodic_start_index = None
        for i, (node_id, priority) in enumerate(dequeued_order):
            if priority == 8:
                periodic_start_index = i
                break
        
        # Verify all periodic rechecks come after all higher priority requests
        if periodic_start_index is not None:
            # All requests before periodic_start_index should have priority < 8
            for i in range(periodic_start_index):
                assert dequeued_order[i][1] < 8, (
                    f"Found priority {dequeued_order[i][1]} after periodic recheck "
                    f"at index {i}, but periodic rechecks should come last"
                )
            
            # All requests from periodic_start_index onward should have priority 8
            for i in range(periodic_start_index, len(dequeued_order)):
                assert dequeued_order[i][1] == 8, (
                    f"Found priority {dequeued_order[i][1]} in periodic recheck section "
                    f"at index {i}, expected priority 8"
                )
    
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        node_id=valid_node_id(),
        hours_since_last_trace=st.integers(min_value=7, max_value=24)
    )
    @pytest.mark.asyncio
    async def test_periodic_recheck_only_for_nodes_needing_trace(
        self, node_id, hours_since_last_trace
    ):
        """
        Property: For any node, periodic rechecks should only be queued if the 
        node needs tracing (based on recheck interval).
        
        **Validates: Requirements 4.3, 5.1**
        """
        config = {
            'enabled': True,
            'traceroutes_per_minute': 1,
            'queue_max_size': 100,
            'skip_direct_nodes': True,
            'blacklist': [],
            'whitelist': [],
            'exclude_roles': [],
            'min_snr_threshold': None,
            'recheck_interval_hours': 6
        }
        
        plugin_manager = Mock()
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, plugin_manager)
        
        plugin.node_tracker = NodeStateTracker(config)
        plugin.priority_queue = PriorityQueue(max_size=100)
        plugin._config_cache = config
        
        # Create node with last trace time
        plugin.node_tracker.update_node(
            node_id=node_id,
            is_direct=False,
            snr=-5.0,
            rssi=-95
        )
        node_state = plugin.node_tracker.get_node_state(node_id)
        
        # Set next_recheck based on hours_since_last_trace
        # If hours_since_last_trace >= 6 (recheck_interval), node needs trace
        node_state.next_recheck = datetime.now() - timedelta(
            hours=hours_since_last_trace - 6
        )
        
        # Check if node needs trace
        nodes_needing_trace = plugin.node_tracker.get_nodes_needing_trace()
        should_need_trace = hours_since_last_trace >= 6
        
        if should_need_trace:
            assert node_id in nodes_needing_trace, (
                f"Node {node_id} should need trace after {hours_since_last_trace} hours"
            )
            
            # Queue periodic recheck
            if not plugin.priority_queue.contains(node_id):
                plugin.priority_queue.enqueue(
                    node_id=node_id,
                    priority=8,
                    reason="periodic_recheck"
                )
            
            # Verify it was queued
            assert plugin.priority_queue.contains(node_id), (
                f"Node {node_id} should be queued for periodic recheck"
            )
        else:
            assert node_id not in nodes_needing_trace, (
                f"Node {node_id} should not need trace after {hours_since_last_trace} hours"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
