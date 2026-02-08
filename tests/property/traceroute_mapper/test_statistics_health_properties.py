"""
Property-Based Tests for Network Traceroute Mapper Statistics and Health Status

Tests Property 36: Statistics Accuracy
Tests Property 37: Health Status Accuracy
Validates: Requirements 15.5, 15.6

**Validates: Requirements 15.5, 15.6**
"""

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite
from pathlib import Path
import sys
from unittest.mock import Mock, AsyncMock, MagicMock
import asyncio
from datetime import datetime

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin


# Strategy builders for generating test data

@composite
def operation_sequence(draw):
    """Generate a sequence of operations (sent, successful, failed, timeout)"""
    num_operations = draw(st.integers(min_value=1, max_value=100))
    operations = []
    for _ in range(num_operations):
        op_type = draw(st.sampled_from(['sent', 'successful', 'failed', 'timeout']))
        operations.append(op_type)
    return operations


@composite
def node_counts(draw):
    """Generate node count statistics"""
    total = draw(st.integers(min_value=0, max_value=1000))
    direct = draw(st.integers(min_value=0, max_value=total))
    indirect = total - direct
    return {
        'total_nodes': total,
        'direct_nodes': direct,
        'indirect_nodes': indirect
    }


@composite
def health_state(draw):
    """Generate health state parameters"""
    return {
        'enabled': draw(st.booleans()),
        'initialized': draw(st.booleans()),
        'emergency_stop': draw(st.booleans()),
        'is_throttled': draw(st.booleans()),
        'is_quiet_hours': draw(st.booleans())
    }


# Property Tests

class TestStatisticsAccuracyProperty:
    """
    Feature: network-traceroute-mapper, Property 36: Statistics Accuracy
    
    Tests that statistics reported by the plugin accurately reflect the actual
    operations performed.
    
    **Validates: Requirements 15.5**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(operations=operation_sequence())
    @pytest.mark.asyncio
    async def test_statistics_match_actual_operations(self, operations):
        """
        Property: For any sequence of traceroute operations, the reported statistics
        should exactly match the actual counts of sent, successful, failed, and timeout operations.
        
        **Validates: Requirements 15.5**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Count expected values
        expected_sent = operations.count('sent')
        expected_successful = operations.count('successful')
        expected_failed = operations.count('failed')
        expected_timeout = operations.count('timeout')
        
        # Simulate operations by directly updating stats
        for op in operations:
            if op == 'sent':
                plugin.stats['traceroutes_sent'] += 1
            elif op == 'successful':
                plugin.stats['traceroutes_successful'] += 1
            elif op == 'failed':
                plugin.stats['traceroutes_failed'] += 1
            elif op == 'timeout':
                plugin.stats['traceroutes_timeout'] += 1
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify statistics match
        assert health_status['traceroutes_sent'] == expected_sent, \
            f"Expected {expected_sent} sent, got {health_status['traceroutes_sent']}"
        assert health_status['traceroutes_successful'] == expected_successful, \
            f"Expected {expected_successful} successful, got {health_status['traceroutes_successful']}"
        assert health_status['traceroutes_failed'] == expected_failed, \
            f"Expected {expected_failed} failed, got {health_status['traceroutes_failed']}"
        assert health_status['traceroutes_timeout'] == expected_timeout, \
            f"Expected {expected_timeout} timeout, got {health_status['traceroutes_timeout']}"
    
    @settings(max_examples=20, deadline=None)
    @given(operations=operation_sequence())
    @pytest.mark.asyncio
    async def test_success_rate_calculation_accuracy(self, operations):
        """
        Property: For any sequence of operations, the success rate should be
        calculated as successful / sent, or 0.0 if no operations were sent.
        
        **Validates: Requirements 15.5**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Count operations
        sent_count = operations.count('sent')
        successful_count = operations.count('successful')
        
        # Simulate operations
        plugin.stats['traceroutes_sent'] = sent_count
        plugin.stats['traceroutes_successful'] = successful_count
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Calculate expected success rate
        if sent_count > 0:
            expected_rate = successful_count / sent_count
        else:
            expected_rate = 0.0
        
        # Verify success rate
        assert abs(health_status['success_rate'] - expected_rate) < 0.0001, \
            f"Expected success rate {expected_rate}, got {health_status['success_rate']}"
    
    @settings(max_examples=20, deadline=None)
    @given(
        direct_skipped=st.integers(min_value=0, max_value=1000),
        filtered_skipped=st.integers(min_value=0, max_value=1000)
    )
    @pytest.mark.asyncio
    async def test_skip_statistics_accuracy(self, direct_skipped, filtered_skipped):
        """
        Property: For any number of skipped nodes (direct or filtered),
        the statistics should accurately reflect the counts.
        
        **Validates: Requirements 15.5**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Set skip counts
        plugin.stats['direct_nodes_skipped'] = direct_skipped
        plugin.stats['filtered_nodes_skipped'] = filtered_skipped
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify skip statistics
        assert health_status['direct_nodes_skipped'] == direct_skipped, \
            f"Expected {direct_skipped} direct nodes skipped, got {health_status['direct_nodes_skipped']}"
        assert health_status['filtered_nodes_skipped'] == filtered_skipped, \
            f"Expected {filtered_skipped} filtered nodes skipped, got {health_status['filtered_nodes_skipped']}"


class TestHealthStatusAccuracyProperty:
    """
    Feature: network-traceroute-mapper, Property 37: Health Status Accuracy
    
    Tests that health status reported by the plugin accurately reflects the
    current operational state of the system.
    
    **Validates: Requirements 15.6**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(state=health_state())
    @pytest.mark.asyncio
    async def test_health_status_reflects_plugin_state(self, state):
        """
        Property: For any plugin state (enabled, initialized, emergency_stop),
        the health status should accurately reflect that state.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Set plugin state
        plugin.enabled = state['enabled']
        plugin.initialized = state['initialized']
        
        # Mock health monitor
        if plugin.health_monitor:
            plugin.health_monitor.is_emergency_stop = state['emergency_stop']
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify state fields
        assert health_status['enabled'] == state['enabled'], \
            f"Expected enabled={state['enabled']}, got {health_status['enabled']}"
        assert health_status['initialized'] == state['initialized'], \
            f"Expected initialized={state['initialized']}, got {health_status['initialized']}"
        
        # Verify healthy flag (should be True only if enabled, initialized, and not in emergency stop)
        expected_healthy = state['enabled'] and state['initialized'] and not state['emergency_stop']
        assert health_status['healthy'] == expected_healthy, \
            f"Expected healthy={expected_healthy}, got {health_status['healthy']}"
    
    @settings(max_examples=20, deadline=None)
    @given(
        queue_size=st.integers(min_value=0, max_value=10000),
        pending_traceroutes=st.integers(min_value=0, max_value=1000)
    )
    @pytest.mark.asyncio
    async def test_health_status_reflects_queue_metrics(self, queue_size, pending_traceroutes):
        """
        Property: For any queue size and pending traceroute count,
        the health status should accurately report these metrics.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Mock queue size
        if plugin.priority_queue:
            plugin.priority_queue.size = Mock(return_value=queue_size)
        
        # Mock pending traceroutes
        if plugin.traceroute_manager:
            plugin.traceroute_manager.get_pending_count = Mock(return_value=pending_traceroutes)
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify queue metrics
        assert health_status['queue_size'] == queue_size, \
            f"Expected queue_size={queue_size}, got {health_status['queue_size']}"
        assert health_status['pending_traceroutes'] == pending_traceroutes, \
            f"Expected pending_traceroutes={pending_traceroutes}, got {health_status['pending_traceroutes']}"
    
    @settings(max_examples=20, deadline=None)
    @given(node_stats=node_counts())
    @pytest.mark.asyncio
    async def test_health_status_reflects_node_metrics(self, node_stats):
        """
        Property: For any node count statistics (total, direct, indirect),
        the health status should accurately report these metrics.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Mock node statistics
        if plugin.node_tracker:
            plugin.node_tracker.get_statistics = Mock(return_value=node_stats)
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify node metrics
        assert health_status['nodes_tracked'] == node_stats['total_nodes'], \
            f"Expected nodes_tracked={node_stats['total_nodes']}, got {health_status['nodes_tracked']}"
        assert health_status['direct_nodes'] == node_stats['direct_nodes'], \
            f"Expected direct_nodes={node_stats['direct_nodes']}, got {health_status['direct_nodes']}"
        assert health_status['indirect_nodes'] == node_stats['indirect_nodes'], \
            f"Expected indirect_nodes={node_stats['indirect_nodes']}, got {health_status['indirect_nodes']}"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_rate=st.floats(min_value=0.1, max_value=60, allow_nan=False, allow_infinity=False),
        throttle_multiplier=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
        is_throttled=st.booleans()
    )
    @pytest.mark.asyncio
    async def test_health_status_reflects_rate_limiting(self, base_rate, throttle_multiplier, is_throttled):
        """
        Property: For any rate limiting configuration and throttle state,
        the health status should accurately report the current and base rates.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with config
        config = {
            'enabled': True,
            'traceroutes_per_minute': base_rate
        }
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Mock health monitor throttling
        if plugin.health_monitor:
            plugin.health_monitor.should_throttle = Mock(return_value=is_throttled)
            if is_throttled:
                current_rate = base_rate * throttle_multiplier
            else:
                current_rate = base_rate
            plugin.health_monitor.get_recommended_rate = Mock(return_value=current_rate)
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify rate fields
        assert abs(health_status['base_rate'] - base_rate) < 0.01, \
            f"Expected base_rate={base_rate}, got {health_status['base_rate']}"
        assert health_status['is_throttled'] == is_throttled, \
            f"Expected is_throttled={is_throttled}, got {health_status['is_throttled']}"
        
        # Verify current rate matches expected
        if is_throttled:
            expected_current = base_rate * throttle_multiplier
        else:
            expected_current = base_rate
        assert abs(health_status['current_rate'] - expected_current) < 0.01, \
            f"Expected current_rate={expected_current}, got {health_status['current_rate']}"
    
    @settings(max_examples=20, deadline=None)
    @given(is_quiet_hours=st.booleans())
    @pytest.mark.asyncio
    async def test_health_status_reflects_quiet_hours(self, is_quiet_hours):
        """
        Property: For any quiet hours state, the health status should
        accurately report whether the system is in quiet hours.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Mock quiet hours state
        if plugin.health_monitor:
            plugin.health_monitor.is_quiet_hours = Mock(return_value=is_quiet_hours)
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify quiet hours field
        assert health_status['is_quiet_hours'] == is_quiet_hours, \
            f"Expected is_quiet_hours={is_quiet_hours}, got {health_status['is_quiet_hours']}"
    
    @settings(max_examples=20, deadline=None)
    @given(emergency_stop=st.booleans())
    @pytest.mark.asyncio
    async def test_health_status_reflects_emergency_stop(self, emergency_stop):
        """
        Property: For any emergency stop state, the health status should
        accurately report the emergency stop flag and affect the healthy flag.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Set plugin to enabled and initialized
        plugin.enabled = True
        plugin.initialized = True
        
        # Mock emergency stop state
        if plugin.health_monitor:
            plugin.health_monitor.is_emergency_stop = emergency_stop
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify emergency stop field
        assert health_status['emergency_stop'] == emergency_stop, \
            f"Expected emergency_stop={emergency_stop}, got {health_status['emergency_stop']}"
        
        # Verify healthy flag (should be False if emergency stop is True)
        expected_healthy = not emergency_stop
        assert health_status['healthy'] == expected_healthy, \
            f"Expected healthy={expected_healthy}, got {health_status['healthy']}"
    
    @settings(max_examples=20, deadline=None)
    @given(operations=operation_sequence())
    @pytest.mark.asyncio
    async def test_health_status_includes_all_required_fields(self, operations):
        """
        Property: For any plugin state, the health status should include all
        required fields as specified in the design document.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Simulate some operations
        for op in operations[:10]:  # Limit to first 10 for performance
            if op == 'sent':
                plugin.stats['traceroutes_sent'] += 1
            elif op == 'successful':
                plugin.stats['traceroutes_successful'] += 1
        
        # Get health status
        health_status = await plugin.get_health_status()
        
        # Verify all required fields are present
        required_fields = [
            'healthy', 'enabled', 'initialized', 'emergency_stop',
            'queue_size', 'pending_traceroutes',
            'nodes_tracked', 'direct_nodes', 'indirect_nodes',
            'traceroutes_sent', 'traceroutes_successful', 'traceroutes_failed', 'traceroutes_timeout',
            'success_rate', 'last_traceroute_time',
            'current_rate', 'base_rate', 'is_throttled', 'is_quiet_hours',
            'direct_nodes_skipped', 'filtered_nodes_skipped'
        ]
        
        for field in required_fields:
            assert field in health_status, f"Required field '{field}' missing from health status"
    
    @settings(max_examples=20, deadline=None)
    @given(
        sent=st.integers(min_value=0, max_value=1000),
        successful=st.integers(min_value=0, max_value=1000),
        failed=st.integers(min_value=0, max_value=1000)
    )
    @pytest.mark.asyncio
    async def test_health_status_error_handling(self, sent, successful, failed):
        """
        Property: For any plugin state, if an error occurs during health status
        retrieval, the method should return a dict with healthy=False and error message.
        
        **Validates: Requirements 15.6**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        config = {'enabled': True}
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Set statistics
        plugin.stats['traceroutes_sent'] = sent
        plugin.stats['traceroutes_successful'] = successful
        plugin.stats['traceroutes_failed'] = failed
        
        # Mock priority_queue to raise an exception
        if plugin.priority_queue:
            plugin.priority_queue.size = Mock(side_effect=Exception("Test error"))
        
        # Get health status (should handle error gracefully)
        health_status = await plugin.get_health_status()
        
        # Verify error handling
        assert 'healthy' in health_status, "Health status should include 'healthy' field"
        assert health_status['healthy'] is False, "Health status should be False on error"
        assert 'error' in health_status, "Health status should include 'error' field on error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
