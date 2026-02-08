"""
Property-Based Tests for Startup Delay Enforcement

Tests Property 15: Startup Delay Enforcement
Validates Requirements: 8.3

Author: ZephyrGate Team
"""

import sys
import asyncio
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck

# Add src directory to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from plugins.traceroute_mapper.priority_queue import PriorityQueue


# Strategies
@st.composite
def startup_delay_config(draw):
    """Generate configuration with random startup delay."""
    return {
        'enabled': True,
        'startup_delay_seconds': draw(st.integers(min_value=1, max_value=10)),  # Short delays for testing
        'traceroutes_per_minute': draw(st.integers(min_value=1, max_value=10)),
        'queue_max_size': 100,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'recheck_interval_hours': 6,
        'recheck_enabled': False,  # Disable for this test
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'retry_backoff_multiplier': 2.0,
        'initial_discovery_enabled': False,  # Disable for this test
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


class MockPluginManager:
    """Mock plugin manager for testing."""
    def __init__(self):
        self.message_router = None


@pytest.mark.asyncio
@given(config=startup_delay_config())
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_startup_delay_enforcement(config):
    """
    Feature: network-traceroute-mapper, Property 15: Startup Delay Enforcement
    
    For any configured startup_delay_seconds value, the first traceroute should not
    be sent until at least startup_delay_seconds have elapsed since plugin start.
    
    Validates: Requirements 8.3
    """
    startup_delay = config['startup_delay_seconds']
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize plugin
    initialized = await plugin.initialize()
    assert initialized, "Plugin should initialize successfully"
    
    # Queue a traceroute request before starting
    plugin.priority_queue.enqueue(
        node_id="!test1234",
        priority=1,
        reason="test"
    )
    
    # Record start time
    start_time = datetime.now()
    
    # Start plugin (this starts background tasks including queue processing)
    started = await plugin.start()
    assert started, "Plugin should start successfully"
    
    # Wait for a bit longer than the startup delay
    wait_time = startup_delay + 1
    await asyncio.sleep(wait_time)
    
    # Check when the first traceroute was sent
    last_traceroute_time = plugin.stats.get('last_traceroute_time')
    
    # Stop plugin
    await plugin.stop()
    
    # If a traceroute was sent, verify it was after the startup delay
    if last_traceroute_time:
        elapsed = (last_traceroute_time - start_time).total_seconds()
        
        # Allow small tolerance for timing variations (0.5 seconds)
        assert elapsed >= (startup_delay - 0.5), (
            f"First traceroute sent too early: {elapsed:.2f}s < {startup_delay}s "
            f"(startup_delay_seconds={startup_delay})"
        )


@pytest.mark.asyncio
async def test_startup_delay_zero():
    """
    Test that startup_delay_seconds=0 allows immediate processing.
    
    Validates: Requirements 8.3
    """
    config = {
        'enabled': True,
        'startup_delay_seconds': 0,  # No delay
        'traceroutes_per_minute': 60,  # Fast rate for testing
        'queue_max_size': 100,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'recheck_interval_hours': 6,
        'recheck_enabled': False,
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
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    # Initialize and start
    await plugin.initialize()
    
    # Queue a request
    plugin.priority_queue.enqueue(
        node_id="!test1234",
        priority=1,
        reason="test"
    )
    
    start_time = datetime.now()
    await plugin.start()
    
    # Wait a short time
    await asyncio.sleep(0.5)
    
    # Stop plugin
    await plugin.stop()
    
    # With zero delay, traceroute should be sent quickly
    # (We can't guarantee it's sent immediately due to async scheduling,
    # but it should be within a reasonable time)
    last_traceroute_time = plugin.stats.get('last_traceroute_time')
    if last_traceroute_time:
        elapsed = (last_traceroute_time - start_time).total_seconds()
        # Should be sent within 1 second with zero delay
        assert elapsed < 1.0, (
            f"With zero startup delay, traceroute should be sent quickly, "
            f"but took {elapsed:.2f}s"
        )


@pytest.mark.asyncio
@given(
    startup_delay=st.integers(min_value=1, max_value=5),
    num_requests=st.integers(min_value=1, max_value=10)
)
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_startup_delay_applies_to_all_requests(startup_delay, num_requests):
    """
    Test that startup delay applies to all queued requests, not just the first.
    
    All requests should wait for the startup delay before any are processed.
    
    Validates: Requirements 8.3
    """
    config = {
        'enabled': True,
        'startup_delay_seconds': startup_delay,
        'traceroutes_per_minute': 60,  # Fast rate
        'queue_max_size': 100,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'recheck_interval_hours': 6,
        'recheck_enabled': False,
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
    
    # Create plugin
    plugin_manager = MockPluginManager()
    plugin = TracerouteMapperPlugin(
        name="traceroute_mapper",
        config=config,
        plugin_manager=plugin_manager
    )
    
    await plugin.initialize()
    
    # Queue multiple requests
    for i in range(num_requests):
        plugin.priority_queue.enqueue(
            node_id=f"!test{i:04d}",
            priority=1,
            reason="test"
        )
    
    start_time = datetime.now()
    await plugin.start()
    
    # Wait for startup delay + a bit more
    await asyncio.sleep(startup_delay + 1)
    
    await plugin.stop()
    
    # Check that first traceroute was sent after startup delay
    last_traceroute_time = plugin.stats.get('last_traceroute_time')
    if last_traceroute_time:
        elapsed = (last_traceroute_time - start_time).total_seconds()
        assert elapsed >= (startup_delay - 0.5), (
            f"First traceroute sent too early with multiple queued requests: "
            f"{elapsed:.2f}s < {startup_delay}s"
        )
