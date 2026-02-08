"""
Unit tests for TracerouteMapperPlugin message handling.

Tests the _handle_mesh_message method and related functionality for:
- Node discovery events
- Traceroute responses
- Direct node transitions
- Node back online events

Validates: Requirements 2.1, 2.2, 4.1, 4.2, 16.2, 16.3, 16.4
"""

import pytest
import pytest_asyncio
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add src directory to path (same as plugin does)
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from models.message import Message, MessageType, MessagePriority


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager."""
    manager = Mock()
    manager.get_plugin = Mock(return_value=None)
    return manager


@pytest.fixture
def minimal_config():
    """Minimal valid configuration for the plugin."""
    return {
        'enabled': True,
        'traceroutes_per_minute': 1,
        'burst_multiplier': 2,
        'queue_max_size': 500,
        'queue_overflow_strategy': 'drop_lowest_priority',
        'clear_queue_on_startup': False,
        'recheck_interval_hours': 6,
        'recheck_enabled': True,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'retry_backoff_multiplier': 2.0,
        'initial_discovery_enabled': False,
        'startup_delay_seconds': 0,
        'skip_direct_nodes': True,
        'blacklist': [],
        'whitelist': [],
        'exclude_roles': ['CLIENT'],
        'min_snr_threshold': None,
        'state_persistence_enabled': False,
        'state_file_path': 'data/test_traceroute_state.json',
        'auto_save_interval_minutes': 5,
        'history_per_node': 10,
        'forward_to_mqtt': True,
        'log_level': 'INFO',
        'log_traceroute_requests': True,
        'log_traceroute_responses': True,
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
            'consecutive_failures': 10,
            'auto_recovery_minutes': 30
        }
    }


@pytest_asyncio.fixture
async def initialized_plugin(mock_plugin_manager, minimal_config):
    """Create and initialize a plugin instance."""
    plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
    await plugin.initialize()
    return plugin


class TestNodeStateUpdate:
    """Test node state updates from incoming messages."""
    
    @pytest.mark.asyncio
    async def test_update_node_state_from_message(self, initialized_plugin):
        """Test that incoming messages update node state."""
        plugin = initialized_plugin
        
        # Create a message from an indirect node
        message = Message(
            id='msg1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        
        # Handle the message
        await plugin._handle_mesh_message(message, {})
        
        # Verify node state was updated
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state is not None
        assert node_state.node_id == '!node123'
        assert node_state.is_direct == False  # hop_count=3 means indirect
        assert node_state.snr == -5.0
        assert node_state.rssi == -95
    
    @pytest.mark.asyncio
    async def test_update_direct_node_from_message(self, initialized_plugin):
        """Test that direct nodes are correctly identified."""
        plugin = initialized_plugin
        
        # Create a message from a direct node (hop_count=1)
        message = Message(
            id='msg1',
            sender_id='!direct1',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=1,
            snr=10.0,
            rssi=-75,
            metadata={}
        )
        
        # Handle the message
        await plugin._handle_mesh_message(message, {})
        
        # Verify node is marked as direct
        node_state = plugin.node_tracker.get_node_state('!direct1')
        assert node_state is not None
        assert node_state.is_direct == True


class TestNewIndirectNodeDiscovery:
    """Test handling of new indirect node discoveries."""
    
    @pytest.mark.asyncio
    async def test_new_indirect_node_queues_traceroute(self, initialized_plugin):
        """Test that discovering a new indirect node queues a traceroute with priority 1."""
        plugin = initialized_plugin
        
        # Create a message from a new indirect node
        message = Message(
            id='msg1',
            sender_id='!newnode',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        
        # Handle the message
        await plugin._handle_mesh_message(message, {})
        
        # Verify traceroute was queued with priority 1 (NEW_NODE)
        assert plugin.priority_queue.contains('!newnode')
        
        # Dequeue and check priority
        request = plugin.priority_queue.dequeue()
        assert request is not None
        assert request.node_id == '!newnode'
        assert request.priority == 1
        assert request.reason == 'new_indirect_node'
    
    @pytest.mark.asyncio
    async def test_direct_node_not_queued(self, initialized_plugin):
        """Test that direct nodes are not queued for traceroute."""
        plugin = initialized_plugin
        
        # Create a message from a direct node
        message = Message(
            id='msg1',
            sender_id='!direct1',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=1,
            snr=10.0,
            rssi=-75,
            metadata={}
        )
        
        # Handle the message
        await plugin._handle_mesh_message(message, {})
        
        # Verify traceroute was NOT queued
        assert not plugin.priority_queue.contains('!direct1')
        assert plugin.priority_queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_filtered_node_not_queued(self, initialized_plugin):
        """Test that filtered nodes are not queued for traceroute."""
        plugin = initialized_plugin
        
        # Add node to blacklist
        plugin.node_tracker._blacklist.add('!blacklisted')
        
        # Create a message from the blacklisted node
        message = Message(
            id='msg1',
            sender_id='!blacklisted',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        
        # Handle the message
        await plugin._handle_mesh_message(message, {})
        
        # Verify traceroute was NOT queued
        assert not plugin.priority_queue.contains('!blacklisted')
        assert plugin.stats['filtered_nodes_skipped'] == 1


class TestDirectNodeTransition:
    """Test handling of nodes transitioning from indirect to direct."""
    
    @pytest.mark.asyncio
    async def test_indirect_to_direct_removes_pending_traceroute(self, initialized_plugin):
        """Test that transitioning to direct removes pending traceroute requests."""
        plugin = initialized_plugin
        
        # First, discover node as indirect
        message1 = Message(
            id='msg1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        await plugin._handle_mesh_message(message1, {})
        
        # Verify traceroute was queued
        assert plugin.priority_queue.contains('!node123')
        initial_queue_size = plugin.priority_queue.size()
        
        # Now receive message showing node is direct
        message2 = Message(
            id='msg2',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello again',
            hop_count=1,
            snr=10.0,
            rssi=-75,
            metadata={}
        )
        await plugin._handle_mesh_message(message2, {})
        
        # Verify node is now direct
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state.is_direct == True
        
        # Verify pending traceroute was removed
        assert not plugin.priority_queue.contains('!node123')
        assert plugin.priority_queue.size() < initial_queue_size
        assert plugin.stats['direct_nodes_skipped'] == 1


class TestNodeBackOnline:
    """Test handling of nodes coming back online."""
    
    @pytest.mark.asyncio
    async def test_node_back_online_queues_with_priority_4(self, initialized_plugin):
        """Test that nodes coming back online are queued with priority 4."""
        plugin = initialized_plugin
        
        # First, discover node as indirect
        message1 = Message(
            id='msg1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        await plugin._handle_mesh_message(message1, {})
        
        # Clear the queue (simulate node was already traced)
        plugin.priority_queue.clear()
        
        # Mark node as offline
        plugin.node_tracker.mark_node_offline('!node123')
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state.was_offline == True
        
        # Now receive message showing node is back online
        message2 = Message(
            id='msg2',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Back online',
            hop_count=3,
            snr=-5.0,
            rssi=-95,
            metadata={}
        )
        await plugin._handle_mesh_message(message2, {})
        
        # Verify traceroute was queued with priority 4 (NODE_BACK_ONLINE)
        assert plugin.priority_queue.contains('!node123')
        
        # Dequeue and check priority
        request = plugin.priority_queue.dequeue()
        assert request is not None
        assert request.node_id == '!node123'
        assert request.priority == 4
        assert request.reason == 'node_back_online'
        
        # Verify was_offline flag was cleared
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state.was_offline == False


class TestTracerouteResponseHandling:
    """Test handling of traceroute response messages."""
    
    @pytest.mark.asyncio
    async def test_traceroute_response_updates_statistics(self, initialized_plugin):
        """Test that traceroute responses update statistics."""
        plugin = initialized_plugin
        
        # First, send a traceroute request
        request_id = await plugin.traceroute_manager.send_traceroute('!node123', priority=1)
        
        # Create a traceroute response
        response = Message(
            id='response1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.ROUTING,
            content='',
            hop_count=3,
            metadata={
                'traceroute': True,
                'request_id': request_id,
                'route': [
                    {'node_id': '!gateway', 'snr': 10.0, 'rssi': -75},
                    {'node_id': '!relay1', 'snr': 5.0, 'rssi': -85},
                    {'node_id': '!relay2', 'snr': -2.0, 'rssi': -92},
                    {'node_id': '!node123', 'snr': -5.0, 'rssi': -95}
                ]
            }
        )
        
        # Handle the response
        await plugin._handle_mesh_message(response, {})
        
        # Verify statistics were updated
        assert plugin.stats['traceroutes_successful'] == 1
        
        # Verify node was marked as traced
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state is not None
        assert node_state.last_trace_success == True
        assert node_state.trace_count == 1
    
    @pytest.mark.asyncio
    async def test_traceroute_response_not_our_request(self, initialized_plugin):
        """Test handling traceroute responses that aren't for our requests."""
        plugin = initialized_plugin
        
        # Create a traceroute response for an unknown request
        response = Message(
            id='response1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.ROUTING,
            content='',
            hop_count=3,
            metadata={
                'traceroute': True,
                'request_id': 'unknown-request-id',
                'route': [
                    {'node_id': '!gateway', 'snr': 10.0, 'rssi': -75},
                    {'node_id': '!node123', 'snr': -5.0, 'rssi': -95}
                ]
            }
        )
        
        # Handle the response (should not crash)
        await plugin._handle_mesh_message(response, {})
        
        # Statistics should not be updated
        assert plugin.stats['traceroutes_successful'] == 0


class TestMessageHandlingEdgeCases:
    """Test edge cases in message handling."""
    
    @pytest.mark.asyncio
    async def test_message_without_sender_id(self, initialized_plugin):
        """Test handling messages without sender_id."""
        plugin = initialized_plugin
        
        # Create a message without sender_id
        message = Message(
            id='msg1',
            sender_id=None,
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            metadata={}
        )
        
        # Should not crash
        result = await plugin._handle_mesh_message(message, {})
        assert result is None
    
    @pytest.mark.asyncio
    async def test_message_with_missing_signal_data(self, initialized_plugin):
        """Test handling messages with missing SNR/RSSI data."""
        plugin = initialized_plugin
        
        # Create a message without SNR/RSSI
        message = Message(
            id='msg1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            snr=None,
            rssi=None,
            metadata={}
        )
        
        # Should not crash
        await plugin._handle_mesh_message(message, {})
        
        # Node should still be tracked
        node_state = plugin.node_tracker.get_node_state('!node123')
        assert node_state is not None
        assert node_state.snr is None
        assert node_state.rssi is None
    
    @pytest.mark.asyncio
    async def test_disabled_plugin_ignores_messages(self, mock_plugin_manager, minimal_config):
        """Test that disabled plugin ignores messages."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        # Don't initialize - plugin is disabled
        
        message = Message(
            id='msg1',
            sender_id='!node123',
            recipient_id='!gateway',
            message_type=MessageType.TEXT,
            content='Hello',
            hop_count=3,
            metadata={}
        )
        
        # Should return None without processing
        result = await plugin._handle_mesh_message(message, {})
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
