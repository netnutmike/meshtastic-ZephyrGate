"""
Unit Tests for Startup Behavior

Tests startup behavior including:
- Initial discovery enabled vs disabled
- State loading at startup
- Queue clearing on startup

Validates Requirements: 8.1, 8.2, 10.6

Author: ZephyrGate Team
"""

import sys
import asyncio
import pytest
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from plugins.traceroute_mapper.node_state_tracker import NodeState


class MockPluginManager:
    """Mock plugin manager for testing."""
    def __init__(self):
        self.message_router = None


def get_base_config():
    """Get base configuration for testing."""
    return {
        'enabled': True,
        'startup_delay_seconds': 0,  # No delay for faster tests
        'traceroutes_per_minute': 60,
        'burst_multiplier': 2,
        'queue_max_size': 100,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'clear_queue_on_startup': False,
        'recheck_interval_hours': 6,
        'recheck_enabled': False,  # Disable for these tests
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'retry_backoff_multiplier': 2.0,
        'initial_discovery_enabled': False,
        'skip_direct_nodes': True,
        'blacklist': [],
        'whitelist': [],
        'exclude_roles': [],
        'min_snr_threshold': None,
        'state_persistence_enabled': False,
        'state_file_path': 'data/test_traceroute_state.json',
        'auto_save_interval_minutes': 5,
        'history_per_node': 10,
        'forward_to_mqtt': False,
        'log_level': 'ERROR',
        'log_traceroute_requests': False,
        'log_traceroute_responses': False,
        'quiet_hours': {
            'enabled': False,
            'start_time': '22:00',
            'end_time': '06:00',
            'timezone': 'UTC'
        },
        'congestion_detection': {
            'enabled': False,
            'success_rate_threshold': 0.5,
            'throttle_multiplier': 0.5
        },
        'emergency_stop': {
            'enabled': False,
            'failure_threshold': 0.2,
            'consecutive_failures': 10,
            'auto_recovery_minutes': 30
        }
    }


@pytest.mark.asyncio
async def test_initial_discovery_enabled():
    """
    Test that initial discovery scan queues traceroutes for all indirect nodes.
    
    Validates: Requirements 8.1, 8.2
    """
    config = get_base_config()
    config['initial_discovery_enabled'] = True
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add some indirect nodes to the tracker before starting
    plugin.node_tracker.update_node("!node0001", is_direct=False, snr=-5.0, rssi=-90)
    plugin.node_tracker.update_node("!node0002", is_direct=False, snr=-8.0, rssi=-95)
    plugin.node_tracker.update_node("!node0003", is_direct=True, snr=10.0, rssi=-70)  # Direct node
    plugin.node_tracker.update_node("!node0004", is_direct=False, snr=-3.0, rssi=-85)
    
    # Start plugin (this should trigger initial discovery)
    await plugin.start()
    
    # Wait a moment for initial discovery to complete
    await asyncio.sleep(0.1)
    
    # Check that indirect nodes were queued
    queue_size = plugin.priority_queue.size()
    
    # Stop plugin
    await plugin.stop()
    
    # Should have queued 3 indirect nodes (not the direct one)
    assert queue_size == 3, f"Expected 3 nodes queued, got {queue_size}"


@pytest.mark.asyncio
async def test_initial_discovery_disabled():
    """
    Test that initial discovery scan does not queue nodes when disabled.
    
    Validates: Requirements 8.1, 8.2
    """
    config = get_base_config()
    config['initial_discovery_enabled'] = False
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add some indirect nodes to the tracker before starting
    plugin.node_tracker.update_node("!node0001", is_direct=False, snr=-5.0, rssi=-90)
    plugin.node_tracker.update_node("!node0002", is_direct=False, snr=-8.0, rssi=-95)
    plugin.node_tracker.update_node("!node0003", is_direct=False, snr=-3.0, rssi=-85)
    
    # Start plugin (should NOT trigger initial discovery)
    await plugin.start()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Check that no nodes were queued
    queue_size = plugin.priority_queue.size()
    
    # Stop plugin
    await plugin.stop()
    
    # Should have queued 0 nodes
    assert queue_size == 0, f"Expected 0 nodes queued, got {queue_size}"


@pytest.mark.asyncio
async def test_state_loading_at_startup():
    """
    Test that persisted state is loaded at startup when enabled.
    
    Validates: Requirements 8.5
    """
    config = get_base_config()
    config['state_persistence_enabled'] = True
    config['state_file_path'] = 'data/test_startup_state.json'
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Create some test state data
    test_nodes = {
        '!node0001': NodeState(
            node_id='!node0001',
            is_direct=False,
            last_seen=datetime.now(),
            last_traced=datetime.now(),
            last_trace_success=True,
            trace_count=5,
            failure_count=0,
            snr=-5.0,
            rssi=-90,
            was_offline=False,
            role='ROUTER'
        ),
        '!node0002': NodeState(
            node_id='!node0002',
            is_direct=False,
            last_seen=datetime.now(),
            last_traced=None,
            last_trace_success=False,
            trace_count=0,
            failure_count=0,
            snr=-8.0,
            rssi=-95,
            was_offline=False,
            role='ROUTER'
        )
    }
    
    # Save test state
    await plugin.state_persistence.save_state(test_nodes)
    
    # Start plugin (should load state)
    await plugin.start()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Check that state was loaded
    loaded_state = plugin.node_tracker.get_node_state('!node0001')
    
    # Stop plugin
    await plugin.stop()
    
    # Verify state was loaded
    assert loaded_state is not None, "State should be loaded"
    assert loaded_state.node_id == '!node0001'
    assert loaded_state.trace_count == 5
    assert loaded_state.last_trace_success is True
    
    # Check second node
    loaded_state2 = plugin.node_tracker.get_node_state('!node0002')
    assert loaded_state2 is not None
    assert loaded_state2.trace_count == 0


@pytest.mark.asyncio
async def test_state_loading_disabled():
    """
    Test that state is not loaded when persistence is disabled.
    
    Validates: Requirements 8.5
    """
    config = get_base_config()
    config['state_persistence_enabled'] = False
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Start plugin (should NOT load state)
    await plugin.start()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Check that no state was loaded
    all_nodes = plugin.node_tracker.get_all_nodes()
    
    # Stop plugin
    await plugin.stop()
    
    # Should have no nodes
    assert len(all_nodes) == 0, f"Expected 0 nodes, got {len(all_nodes)}"


@pytest.mark.asyncio
async def test_queue_clearing_on_startup():
    """
    Test that queue is cleared on startup when configured.
    
    Validates: Requirements 10.6
    """
    config = get_base_config()
    config['clear_queue_on_startup'] = True
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add some requests to the queue before starting
    plugin.priority_queue.enqueue("!node0001", priority=1, reason="test")
    plugin.priority_queue.enqueue("!node0002", priority=2, reason="test")
    plugin.priority_queue.enqueue("!node0003", priority=3, reason="test")
    
    # Verify queue has items
    assert plugin.priority_queue.size() == 3
    
    # Start plugin (should clear queue)
    await plugin.start()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Check that queue was cleared
    queue_size = plugin.priority_queue.size()
    
    # Stop plugin
    await plugin.stop()
    
    # Queue should be empty
    assert queue_size == 0, f"Expected queue to be cleared, but has {queue_size} items"


@pytest.mark.asyncio
async def test_queue_not_cleared_on_startup():
    """
    Test that queue is NOT cleared on startup when not configured.
    
    Validates: Requirements 10.6
    """
    config = get_base_config()
    config['clear_queue_on_startup'] = False
    config['startup_delay_seconds'] = 10  # Long delay to prevent queue processing
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add some requests to the queue before starting
    plugin.priority_queue.enqueue("!node0001", priority=1, reason="test")
    plugin.priority_queue.enqueue("!node0002", priority=2, reason="test")
    plugin.priority_queue.enqueue("!node0003", priority=3, reason="test")
    
    # Verify queue has items
    assert plugin.priority_queue.size() == 3
    
    # Start plugin (should NOT clear queue)
    await plugin.start()
    
    # Wait a moment (but less than startup delay)
    await asyncio.sleep(0.1)
    
    # Check that queue still has items (should not be processed yet due to startup delay)
    queue_size = plugin.priority_queue.size()
    
    # Stop plugin
    await plugin.stop()
    
    # Queue should still have all items (not cleared, and not processed due to startup delay)
    assert queue_size == 3, f"Expected queue to have 3 items, but has {queue_size}"


@pytest.mark.asyncio
async def test_initial_discovery_with_filters():
    """
    Test that initial discovery respects node filters (blacklist, whitelist, etc.).
    
    Validates: Requirements 8.1, 8.2, 9.1, 9.2
    """
    config = get_base_config()
    config['initial_discovery_enabled'] = True
    config['blacklist'] = ['!node0002']  # Blacklist one node
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add some indirect nodes to the tracker before starting
    plugin.node_tracker.update_node("!node0001", is_direct=False, snr=-5.0, rssi=-90)
    plugin.node_tracker.update_node("!node0002", is_direct=False, snr=-8.0, rssi=-95)  # Blacklisted
    plugin.node_tracker.update_node("!node0003", is_direct=False, snr=-3.0, rssi=-85)
    
    # Start plugin (this should trigger initial discovery)
    await plugin.start()
    
    # Wait a moment for initial discovery to complete
    await asyncio.sleep(0.1)
    
    # Check that only non-blacklisted nodes were queued
    queue_size = plugin.priority_queue.size()
    
    # Stop plugin
    await plugin.stop()
    
    # Should have queued 2 nodes (not the blacklisted one)
    assert queue_size == 2, f"Expected 2 nodes queued (excluding blacklisted), got {queue_size}"


@pytest.mark.asyncio
async def test_initial_discovery_priority():
    """
    Test that initial discovery uses priority 1 (NEW_NODE priority).
    
    Validates: Requirements 8.1, 8.2, 4.1
    """
    config = get_base_config()
    config['initial_discovery_enabled'] = True
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize
    await plugin.initialize()
    
    # Add an indirect node
    plugin.node_tracker.update_node("!node0001", is_direct=False, snr=-5.0, rssi=-90)
    
    # Start plugin
    await plugin.start()
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Dequeue the request and check priority
    request = plugin.priority_queue.dequeue()
    
    # Stop plugin
    await plugin.stop()
    
    # Verify priority is 1 (NEW_NODE)
    assert request is not None, "Should have queued a request"
    assert request.priority == 1, f"Expected priority 1 (NEW_NODE), got {request.priority}"
    assert request.reason == "initial_discovery"
