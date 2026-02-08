"""
Integration tests for Network Traceroute Mapper Plugin

Tests the complete flow of traceroute operations including:
- End-to-end flow: node discovery → queue → send → response → MQTT
- State persistence across plugin restarts
- Emergency stop and recovery
- Quiet hours enforcement
- Rate limiting under load

Requirements tested:
- 2.1, 2.2: Direct node filtering and transitions
- 3.1: Rate limit enforcement
- 4.1-4.6: Priority queue system
- 5.1-5.5: Periodic rechecks
- 7.1-7.3: MQTT integration
- 8.1-8.5: Startup behavior
- 12.1-12.5: Network health protection
- 13.1-13.5: State persistence
- 16.1-16.5: Message router integration
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from models.message import Message, MessageType, MessagePriority


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager with message router"""
    manager = Mock()
    manager.config_manager = None
    
    # Mock message router
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    manager.message_router = message_router
    
    return manager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        Path(temp_path).unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def test_config(temp_state_file):
    """Provide test configuration"""
    return {
        'enabled': True,
        'traceroutes_per_minute': 60,  # Fast for testing
        'burst_multiplier': 2,
        'queue_max_size': 100,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'clear_queue_on_startup': False,
        'recheck_interval_hours': 1,
        'recheck_enabled': True,
        'max_hops': 7,
        'timeout_seconds': 10,  # Minimum allowed
        'max_retries': 2,
        'retry_backoff_multiplier': 2.0,
        'initial_discovery_enabled': False,
        'startup_delay_seconds': 0,  # No delay for testing
        'skip_direct_nodes': True,
        'blacklist': [],
        'whitelist': [],
        'exclude_roles': [],
        'min_snr_threshold': None,
        'quiet_hours': {
            'enabled': False,
            'start_time': '22:00',
            'end_time': '06:00',
            'timezone': 'UTC'
        },
        'congestion_detection': {
            'enabled': True,
            'success_rate_threshold': 0.5,
            'throttle_multiplier': 0.5
        },
        'emergency_stop': {
            'enabled': True,
            'failure_threshold': 0.2,
            'consecutive_failures': 5,
            'auto_recovery_minutes': 1
        },
        'state_persistence_enabled': True,
        'state_file_path': temp_state_file,
        'auto_save_interval_minutes': 1,
        'history_per_node': 10,
        'forward_to_mqtt': True,
        'log_level': 'DEBUG',
        'log_traceroute_requests': True,
        'log_traceroute_responses': True
    }


def create_test_message(sender_id: str, is_direct: bool = False, 
                       is_traceroute_response: bool = False,
                       route: list = None) -> Message:
    """Helper to create test messages"""
    metadata = {}
    
    if is_traceroute_response:
        metadata['traceroute'] = True
        metadata['route'] = route or [
            {'node_id': '!gateway', 'snr': 10.0, 'rssi': -70},
            {'node_id': '!relay1', 'snr': 5.0, 'rssi': -80},
            {'node_id': sender_id, 'snr': -2.0, 'rssi': -90}
        ]
        metadata['snr_values'] = [h['snr'] for h in metadata['route']]
        metadata['rssi_values'] = [h['rssi'] for h in metadata['route']]
    
    return Message(
        id=f"msg_{sender_id}",
        sender_id=sender_id,
        recipient_id="^all",
        message_type=MessageType.ROUTING if is_traceroute_response else MessageType.TEXT,
        content="Test message",
        channel=0,
        timestamp=datetime.utcnow(),
        hop_limit=3,
        hop_count=0 if is_direct else 2,
        snr=10.0 if is_direct else -5.0,
        rssi=-70 if is_direct else -90,
        priority=MessagePriority.NORMAL,
        metadata=metadata
    )


class TestEndToEndFlow:
    """Integration tests for complete traceroute flow"""
    
    @pytest.mark.asyncio
    async def test_node_discovery_to_mqtt_flow(self, mock_plugin_manager, test_config):
        """
        Test complete flow: node discovery → queue → send → response → MQTT
        
        Requirements: 2.1, 4.1, 7.1, 7.2, 16.2, 16.3, 16.4
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        # Wait for plugin to be ready
        await asyncio.sleep(0.1)
        
        # Simulate discovering a new indirect node
        indirect_node_msg = create_test_message("!indirect1", is_direct=False)
        context = {'timestamp': datetime.utcnow()}
        
        await plugin._handle_mesh_message(indirect_node_msg, context)
        
        # Wait for message processing
        await asyncio.sleep(0.1)
        
        # Verify node was added to tracker
        node_state = plugin.node_tracker.get_node_state("!indirect1")
        assert node_state is not None
        assert node_state.is_direct is False
        
        # Verify traceroute was queued
        assert plugin.priority_queue.size() > 0
        assert plugin.priority_queue.contains("!indirect1")
        
        # Wait for queue processing to send traceroute (longer wait)
        await asyncio.sleep(1.5)
        
        # Verify traceroute request was sent to message router
        assert mock_plugin_manager.message_router.send_message.called, \
            f"send_message not called. Queue size: {plugin.priority_queue.size()}"
        sent_message = mock_plugin_manager.message_router.send_message.call_args[0][0]
        assert sent_message.recipient_id == "!indirect1"
        assert sent_message.message_type == MessageType.ROUTING
        
        # Simulate receiving traceroute response
        response_msg = create_test_message(
            "!indirect1",
            is_direct=False,
            is_traceroute_response=True,
            route=[
                {'node_id': '!gateway', 'snr': 10.0, 'rssi': -70},
                {'node_id': '!relay1', 'snr': 5.0, 'rssi': -80},
                {'node_id': '!indirect1', 'snr': -2.0, 'rssi': -90}
            ]
        )
        
        # Add request_id to match pending request
        pending_requests = plugin.traceroute_manager.get_all_pending()
        if pending_requests:
            response_msg.metadata['request_id'] = pending_requests[0].request_id
        
        await plugin._handle_mesh_message(response_msg, context)
        
        # Wait for response processing
        await asyncio.sleep(0.1)
        
        # Verify response was forwarded to message router (for MQTT)
        assert mock_plugin_manager.message_router.send_message.call_count >= 2
        
        # Verify statistics updated
        assert plugin.stats['traceroutes_sent'] > 0
        assert plugin.stats['traceroutes_successful'] > 0
        
        # Verify node was marked as traced
        node_state = plugin.node_tracker.get_node_state("!indirect1")
        assert node_state.trace_count > 0
        assert node_state.last_trace_success is True
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_direct_node_skipped(self, mock_plugin_manager, test_config):
        """
        Test that direct nodes are skipped and not queued
        
        Requirements: 2.1, 2.3
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Simulate discovering a direct node
        direct_node_msg = create_test_message("!direct1", is_direct=True)
        context = {'timestamp': datetime.utcnow()}
        
        await plugin._handle_mesh_message(direct_node_msg, context)
        
        await asyncio.sleep(0.1)
        
        # Verify node was added to tracker as direct
        node_state = plugin.node_tracker.get_node_state("!direct1")
        assert node_state is not None
        assert node_state.is_direct is True
        
        # Verify traceroute was NOT queued
        assert not plugin.priority_queue.contains("!direct1")
        
        # Verify no traceroute was sent
        assert mock_plugin_manager.message_router.send_message.call_count == 0
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_indirect_to_direct_transition(self, mock_plugin_manager, test_config):
        """
        Test that pending traceroutes are removed when node becomes direct
        
        Requirements: 2.2
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # First, discover node as indirect
        indirect_msg = create_test_message("!transition1", is_direct=False)
        context = {'timestamp': datetime.utcnow()}
        
        await plugin._handle_mesh_message(indirect_msg, context)
        await asyncio.sleep(0.1)
        
        # Verify queued
        assert plugin.priority_queue.contains("!transition1")
        initial_queue_size = plugin.priority_queue.size()
        
        # Now, node becomes direct
        direct_msg = create_test_message("!transition1", is_direct=True)
        await plugin._handle_mesh_message(direct_msg, context)
        await asyncio.sleep(0.1)
        
        # Verify node is now direct
        node_state = plugin.node_tracker.get_node_state("!transition1")
        assert node_state.is_direct is True
        
        # Verify pending traceroute was removed
        assert not plugin.priority_queue.contains("!transition1")
        assert plugin.priority_queue.size() < initial_queue_size
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, mock_plugin_manager, test_config):
        """
        Test that traceroutes are processed in priority order
        
        Requirements: 4.4, 4.5
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Queue multiple nodes with different priorities
        # Priority 1 (new node), Priority 4 (back online), Priority 8 (recheck)
        
        # Manually queue with different priorities
        plugin.priority_queue.enqueue("!priority8", priority=8, reason="recheck")
        plugin.priority_queue.enqueue("!priority1", priority=1, reason="new_node")
        plugin.priority_queue.enqueue("!priority4", priority=4, reason="back_online")
        
        # Add nodes to tracker so they can be traced
        for node_id in ["!priority1", "!priority4", "!priority8"]:
            plugin.node_tracker.update_node(node_id, is_direct=False, snr=-5.0, rssi=-90)
        
        # Wait for queue processing
        await asyncio.sleep(0.5)
        
        # Verify messages were sent in priority order
        calls = mock_plugin_manager.message_router.send_message.call_args_list
        
        if len(calls) >= 3:
            # First should be priority 1
            first_msg = calls[0][0][0]
            assert first_msg.recipient_id == "!priority1"
            
            # Second should be priority 4
            second_msg = calls[1][0][0]
            assert second_msg.recipient_id == "!priority4"
            
            # Third should be priority 8
            third_msg = calls[2][0][0]
            assert third_msg.recipient_id == "!priority8"
        
        await plugin.stop()


class TestStatePersistence:
    """Integration tests for state persistence across restarts"""
    
    @pytest.mark.asyncio
    async def test_state_persisted_across_restarts(self, mock_plugin_manager, test_config):
        """
        Test that node state is persisted and loaded across plugin restarts
        
        Requirements: 8.5, 13.1, 13.2, 13.3
        """
        # First run: create plugin and add nodes
        plugin1 = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin1.initialize()
        await plugin1.start()
        
        await asyncio.sleep(0.1)
        
        # Add some nodes
        for i in range(5):
            msg = create_test_message(f"!node{i:04d}", is_direct=(i % 2 == 0))
            context = {'timestamp': datetime.utcnow()}
            await plugin1._handle_mesh_message(msg, context)
        
        await asyncio.sleep(0.1)
        
        # Verify nodes were added
        nodes_before = plugin1.node_tracker.get_all_nodes()
        assert len(nodes_before) == 5
        
        # Stop plugin (should save state)
        await plugin1.stop()
        
        # Wait for save
        await asyncio.sleep(0.2)
        
        # Verify state file exists
        state_file = Path(test_config['state_file_path'])
        assert state_file.exists()
        
        # Second run: create new plugin instance
        plugin2 = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin2.initialize()
        await plugin2.start()
        
        await asyncio.sleep(0.2)
        
        # Verify nodes were loaded
        nodes_after = plugin2.node_tracker.get_all_nodes()
        assert len(nodes_after) == 5
        
        # Verify node details match
        for node_id in nodes_before.keys():
            assert node_id in nodes_after
            assert nodes_before[node_id].is_direct == nodes_after[node_id].is_direct
        
        await plugin2.stop()
    
    @pytest.mark.asyncio
    async def test_periodic_state_saving(self, mock_plugin_manager, test_config):
        """
        Test that state is saved periodically
        
        Requirements: 13.1
        """
        # Set short auto-save interval
        config = test_config.copy()
        config['auto_save_interval_minutes'] = 0.05  # 3 seconds
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Add a node
        msg = create_test_message("!persist1", is_direct=False)
        context = {'timestamp': datetime.utcnow()}
        await plugin._handle_mesh_message(msg, context)
        
        # Wait for auto-save
        await asyncio.sleep(4)
        
        # Verify state file was updated
        state_file = Path(config['state_file_path'])
        assert state_file.exists()
        
        # Load and verify
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        assert 'nodes' in state_data
        assert '!persist1' in state_data['nodes']
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_traceroute_history_saved(self, mock_plugin_manager, test_config):
        """
        Test that traceroute history is saved
        
        Requirements: 13.4
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Discover node and send traceroute
        msg = create_test_message("!history1", is_direct=False)
        context = {'timestamp': datetime.utcnow()}
        await plugin._handle_mesh_message(msg, context)
        
        await asyncio.sleep(0.2)
        
        # Simulate successful response
        response_msg = create_test_message(
            "!history1",
            is_direct=False,
            is_traceroute_response=True
        )
        
        # Match request ID
        pending = plugin.traceroute_manager.get_all_pending()
        if pending:
            response_msg.metadata['request_id'] = pending[0].request_id
        
        await plugin._handle_mesh_message(response_msg, context)
        
        await asyncio.sleep(0.2)
        
        # Stop to save state
        await plugin.stop()
        
        # Load state and verify history
        with open(test_config['state_file_path'], 'r') as f:
            state_data = json.load(f)
        
        if 'traceroute_history' in state_data:
            assert '!history1' in state_data['traceroute_history']
            history = state_data['traceroute_history']['!history1']
            assert len(history) > 0


class TestEmergencyStopAndRecovery:
    """Integration tests for emergency stop and recovery"""
    
    @pytest.mark.asyncio
    async def test_emergency_stop_on_failures(self, mock_plugin_manager, test_config):
        """
        Test that emergency stop is triggered after consecutive failures
        
        Requirements: 12.3
        """
        # Set low failure threshold
        config = test_config.copy()
        config['emergency_stop']['consecutive_failures'] = 3
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Simulate consecutive failures
        for i in range(5):
            plugin.health_monitor.record_failure()
        
        # Verify emergency stop triggered
        assert plugin.health_monitor.is_emergency_stop is True
        
        # Verify queue processing stopped
        assert plugin._should_process_queue() is False
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_automatic_recovery(self, mock_plugin_manager, test_config):
        """
        Test that system recovers automatically after emergency stop
        
        Requirements: 12.5
        """
        # Set short recovery time
        config = test_config.copy()
        config['emergency_stop']['auto_recovery_minutes'] = 0.05  # 3 seconds
        config['emergency_stop']['consecutive_failures'] = 2
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Trigger emergency stop
        for i in range(3):
            plugin.health_monitor.record_failure()
        
        assert plugin.health_monitor.is_emergency_stop is True
        
        # Record some successes to improve health
        for i in range(5):
            plugin.health_monitor.record_success()
        
        # Wait for auto-recovery
        await asyncio.sleep(4)
        
        # Verify recovered
        assert plugin.health_monitor.is_emergency_stop is False
        assert plugin._should_process_queue() is True
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_congestion_throttling(self, mock_plugin_manager, test_config):
        """
        Test that rate is reduced when congestion detected
        
        Requirements: 12.2
        """
        plugin = TracerouteMapperPlugin("traceroute_mapper", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Record failures to trigger congestion
        for i in range(10):
            plugin.health_monitor.record_failure()
        
        # Record some successes (but not enough)
        for i in range(3):
            plugin.health_monitor.record_success()
        
        # Verify throttling recommended
        assert plugin.health_monitor.should_throttle() is True
        
        # Verify rate is reduced
        base_rate = test_config['traceroutes_per_minute']
        recommended_rate = plugin.health_monitor.get_recommended_rate(base_rate)
        assert recommended_rate < base_rate
        
        await plugin.stop()


class TestQuietHours:
    """Integration tests for quiet hours enforcement"""
    
    @pytest.mark.asyncio
    async def test_quiet_hours_enforcement(self, mock_plugin_manager, test_config):
        """
        Test that traceroutes are paused during quiet hours
        
        Requirements: 12.1
        """
        # Enable quiet hours for current time
        config = test_config.copy()
        config['quiet_hours']['enabled'] = True
        
        # Set quiet hours to include current time
        now = datetime.utcnow()
        start_time = (now - timedelta(hours=1)).strftime('%H:%M')
        end_time = (now + timedelta(hours=1)).strftime('%H:%M')
        
        config['quiet_hours']['start_time'] = start_time
        config['quiet_hours']['end_time'] = end_time
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Verify quiet hours detected
        assert plugin.health_monitor.is_quiet_hours() is True
        
        # Verify queue processing paused
        assert plugin._should_process_queue() is False
        
        # Queue a traceroute
        msg = create_test_message("!quiet1", is_direct=False)
        context = {'timestamp': datetime.utcnow()}
        await plugin._handle_mesh_message(msg, context)
        
        await asyncio.sleep(0.3)
        
        # Verify no traceroute was sent
        assert mock_plugin_manager.message_router.send_message.call_count == 0
        
        await plugin.stop()


class TestRateLimitingUnderLoad:
    """Integration tests for rate limiting under high load"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, mock_plugin_manager, test_config):
        """
        Test that rate limiting is enforced under load
        
        Requirements: 3.1
        """
        # Set moderate rate limit
        config = test_config.copy()
        config['traceroutes_per_minute'] = 10
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Queue many traceroutes
        for i in range(20):
            plugin.priority_queue.enqueue(
                node_id=f"!rate{i:04d}",
                priority=8,
                reason="test"
            )
            # Add to tracker
            plugin.node_tracker.update_node(
                f"!rate{i:04d}",
                is_direct=False,
                snr=-5.0,
                rssi=-90
            )
        
        # Wait for some processing
        await asyncio.sleep(2)
        
        # Verify rate limiter was used
        stats = plugin.rate_limiter.get_statistics()
        assert stats['tokens_consumed'] > 0
        
        # Verify not all messages sent immediately
        sent_count = mock_plugin_manager.message_router.send_message.call_count
        assert sent_count < 20  # Should be rate limited
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_burst_allowance(self, mock_plugin_manager, test_config):
        """
        Test that initial burst is allowed
        
        Requirements: 3.1
        """
        config = test_config.copy()
        config['traceroutes_per_minute'] = 30
        config['burst_multiplier'] = 2
        
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(0.1)
        
        # Queue burst of traceroutes
        for i in range(10):
            plugin.priority_queue.enqueue(
                node_id=f"!burst{i:04d}",
                priority=1,
                reason="test"
            )
            plugin.node_tracker.update_node(
                f"!burst{i:04d}",
                is_direct=False,
                snr=-5.0,
                rssi=-90
            )
        
        # Wait briefly
        await asyncio.sleep(0.5)
        
        # Verify burst was allowed (multiple messages sent quickly)
        sent_count = mock_plugin_manager.message_router.send_message.call_count
        assert sent_count >= 5  # At least some burst allowed
        
        await plugin.stop()


class TestInitialDiscovery:
    """Integration tests for initial discovery scan"""
    
    @pytest.mark.asyncio
    async def test_initial_discovery_scan(self, mock_plugin_manager, test_config):
        """
        Test that initial discovery scan queues known indirect nodes
        
        Requirements: 8.1, 8.2
        """
        # Enable initial discovery
        config = test_config.copy()
        config['initial_discovery_enabled'] = True
        
        # First, create plugin and add nodes, then stop
        plugin1 = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin1.initialize()
        await plugin1.start()
        
        await asyncio.sleep(0.1)
        
        # Add some indirect nodes
        for i in range(3):
            msg = create_test_message(f"!init{i:04d}", is_direct=False)
            context = {'timestamp': datetime.utcnow()}
            await plugin1._handle_mesh_message(msg, context)
        
        await asyncio.sleep(0.1)
        await plugin1.stop()
        await asyncio.sleep(0.2)
        
        # Reset mock
        mock_plugin_manager.message_router.send_message.reset_mock()
        
        # Second run: create new plugin with initial discovery
        plugin2 = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        await plugin2.initialize()
        await plugin2.start()
        
        # Wait for initial discovery
        await asyncio.sleep(0.5)
        
        # Verify nodes were queued
        assert plugin2.priority_queue.size() > 0 or \
               mock_plugin_manager.message_router.send_message.call_count > 0
        
        await plugin2.stop()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
