"""
Unit tests for TracerouteMapperPlugin lifecycle management.

Tests plugin initialization, start, stop, and component integration.

Validates: Requirements 1.1, 1.2, 1.4, 1.5, 16.1
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Import the plugin
from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin


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
        'startup_delay_seconds': 0,  # No delay for tests
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


@pytest.fixture
def disabled_config():
    """Configuration with plugin disabled."""
    return {
        'enabled': False
    }


class TestPluginInitialization:
    """Test plugin initialization."""
    
    def test_init_creates_plugin_instance(self, mock_plugin_manager, minimal_config):
        """Test that __init__ creates a plugin instance with correct initial state."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        assert plugin.name == 'traceroute_mapper'
        assert plugin.enabled == False  # Not enabled until initialize() is called
        assert plugin.initialized == False
        assert plugin.node_tracker is None
        assert plugin.priority_queue is None
        assert plugin.rate_limiter is None
        assert plugin.traceroute_manager is None
        assert plugin.state_persistence is None
        assert plugin.health_monitor is None
        assert len(plugin._background_tasks) == 0
    
    @pytest.mark.asyncio
    async def test_initialize_with_disabled_config(self, mock_plugin_manager, disabled_config):
        """Test that initialize() returns False when plugin is disabled."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', disabled_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result == False
        assert plugin.enabled == False
        assert plugin.initialized == False
    
    @pytest.mark.asyncio
    async def test_initialize_with_valid_config(self, mock_plugin_manager, minimal_config):
        """Test that initialize() succeeds with valid configuration."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result == True
        assert plugin.enabled == True
        assert plugin.initialized == True
        
        # Check that all components are initialized
        assert plugin.node_tracker is not None
        assert plugin.priority_queue is not None
        assert plugin.rate_limiter is not None
        assert plugin.traceroute_manager is not None
        assert plugin.state_persistence is not None
        assert plugin.health_monitor is not None
    
    @pytest.mark.asyncio
    async def test_initialize_creates_node_tracker(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates NodeStateTracker with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.node_tracker is not None
        # Verify configuration was passed
        assert plugin.node_tracker._skip_direct_nodes == True
        assert plugin.node_tracker._exclude_roles == {'CLIENT'}
    
    @pytest.mark.asyncio
    async def test_initialize_creates_priority_queue(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates PriorityQueue with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.priority_queue is not None
        assert plugin.priority_queue.max_size == 500
        assert plugin.priority_queue.overflow_strategy == 'drop_lowest_priority'
    
    @pytest.mark.asyncio
    async def test_initialize_creates_rate_limiter(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates RateLimiter with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.rate_limiter is not None
        assert plugin.rate_limiter.traceroutes_per_minute == 1
        assert plugin.rate_limiter.burst_multiplier == 2
    
    @pytest.mark.asyncio
    async def test_initialize_creates_traceroute_manager(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates TracerouteManager with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.traceroute_manager is not None
        assert plugin.traceroute_manager.max_hops == 7
        assert plugin.traceroute_manager.timeout_seconds == 60
        assert plugin.traceroute_manager.max_retries == 3
    
    @pytest.mark.asyncio
    async def test_initialize_creates_state_persistence(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates StatePersistence with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.state_persistence is not None
        assert plugin.state_persistence.history_per_node == 10
    
    @pytest.mark.asyncio
    async def test_initialize_creates_health_monitor(self, mock_plugin_manager, minimal_config):
        """Test that initialize() creates NetworkHealthMonitor with correct config."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        await plugin.initialize()
        
        assert plugin.health_monitor is not None
        assert plugin.health_monitor.success_rate_threshold == 0.5
        assert plugin.health_monitor.failure_threshold == 0.2
        assert plugin.health_monitor.consecutive_failures_threshold == 10


class TestPluginStart:
    """Test plugin start functionality."""
    
    @pytest.mark.asyncio
    async def test_start_fails_if_not_initialized(self, mock_plugin_manager, minimal_config):
        """Test that start() fails if plugin is not initialized."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        result = await plugin.start()
        
        assert result == False
    
    @pytest.mark.asyncio
    async def test_start_succeeds_after_initialization(self, mock_plugin_manager, minimal_config):
        """Test that start() succeeds after initialization."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        result = await plugin.start()
        
        assert result == True
        # Background tasks should be started
        assert len(plugin._background_tasks) > 0
    
    @pytest.mark.asyncio
    async def test_start_creates_background_tasks(self, mock_plugin_manager, minimal_config):
        """Test that start() creates background tasks."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        await plugin.start()
        
        # Should have at least queue processing and timeout check tasks
        assert len(plugin._background_tasks) >= 2
    
    @pytest.mark.asyncio
    async def test_start_with_recheck_enabled(self, mock_plugin_manager, minimal_config):
        """Test that start() creates recheck task when enabled."""
        minimal_config['recheck_enabled'] = True
        minimal_config['recheck_interval_hours'] = 6
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        await plugin.start()
        
        # Should have queue, timeout, and recheck tasks
        assert len(plugin._background_tasks) >= 3
    
    @pytest.mark.asyncio
    async def test_start_with_persistence_enabled(self, mock_plugin_manager, minimal_config, tmp_path):
        """Test that start() creates persistence task when enabled."""
        state_file = tmp_path / "test_state.json"
        minimal_config['state_persistence_enabled'] = True
        minimal_config['state_file_path'] = str(state_file)
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        await plugin.start()
        
        # Should have queue, timeout, and persistence tasks
        assert len(plugin._background_tasks) >= 3
    
    @pytest.mark.asyncio
    async def test_start_loads_persisted_state(self, mock_plugin_manager, minimal_config, tmp_path):
        """Test that start() loads persisted state if available."""
        state_file = tmp_path / "test_state.json"
        
        # Create a state file
        state_data = {
            'version': '1.0',
            'last_saved': datetime.now().isoformat(),
            'nodes': {
                '!test123': {
                    'node_id': '!test123',
                    'is_direct': False,
                    'last_seen': datetime.now().isoformat(),
                    'last_traced': None,
                    'next_recheck': None,
                    'last_trace_success': False,
                    'trace_count': 0,
                    'failure_count': 0,
                    'snr': None,
                    'rssi': None,
                    'was_offline': False,
                    'role': None
                }
            }
        }
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        minimal_config['state_persistence_enabled'] = True
        minimal_config['state_file_path'] = str(state_file)
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        await plugin.start()
        
        # Check that state was loaded
        node_state = plugin.node_tracker.get_node_state('!test123')
        assert node_state is not None
        assert node_state.node_id == '!test123'
    
    @pytest.mark.asyncio
    async def test_start_clears_queue_if_configured(self, mock_plugin_manager, minimal_config):
        """Test that start() clears queue if clear_queue_on_startup is True."""
        minimal_config['clear_queue_on_startup'] = True
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Add some items to queue
        plugin.priority_queue.enqueue('!node1', 5, 'test')
        plugin.priority_queue.enqueue('!node2', 5, 'test')
        assert plugin.priority_queue.size() == 2
        
        await plugin.start()
        
        # Queue should be cleared
        assert plugin.priority_queue.size() == 0


class TestPluginStop:
    """Test plugin stop functionality."""
    
    @pytest.mark.asyncio
    async def test_stop_cancels_background_tasks(self, mock_plugin_manager, minimal_config):
        """Test that stop() cancels all background tasks."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        initial_task_count = len(plugin._background_tasks)
        assert initial_task_count > 0
        
        await plugin.stop()
        
        # All tasks should be cancelled
        assert len(plugin._background_tasks) == 0
    
    @pytest.mark.asyncio
    async def test_stop_saves_state_if_enabled(self, mock_plugin_manager, minimal_config, tmp_path):
        """Test that stop() saves state if persistence is enabled."""
        state_file = tmp_path / "test_state.json"
        minimal_config['state_persistence_enabled'] = True
        minimal_config['state_file_path'] = str(state_file)
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        # Add a node to tracker
        plugin.node_tracker.update_node('!test123', is_direct=False, snr=-5.0, rssi=-95)
        
        await plugin.stop()
        
        # Check that state file was created
        assert state_file.exists()
        
        # Verify state content
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        assert '!test123' in state_data['nodes']
    
    @pytest.mark.asyncio
    async def test_stop_succeeds_even_if_save_fails(self, mock_plugin_manager, minimal_config):
        """Test that stop() succeeds even if state save fails."""
        minimal_config['state_persistence_enabled'] = True
        minimal_config['state_file_path'] = '/invalid/path/state.json'
        
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        # Should not raise exception
        result = await plugin.stop()
        assert result == True


class TestPluginHealthStatus:
    """Test plugin health status reporting."""
    
    @pytest.mark.asyncio
    async def test_get_health_status_before_initialization(self, mock_plugin_manager, minimal_config):
        """Test health status before initialization."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] == False
        assert status['enabled'] == False
        assert status['initialized'] == False
    
    @pytest.mark.asyncio
    async def test_get_health_status_after_initialization(self, mock_plugin_manager, minimal_config):
        """Test health status after initialization."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] == True
        assert status['enabled'] == True
        assert status['initialized'] == True
        assert status['emergency_stop'] == False
        assert status['queue_size'] == 0
        assert status['pending_traceroutes'] == 0
    
    @pytest.mark.asyncio
    async def test_get_health_status_includes_statistics(self, mock_plugin_manager, minimal_config):
        """Test that health status includes all required statistics."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Check required fields
        assert 'traceroutes_sent' in status
        assert 'traceroutes_successful' in status
        assert 'traceroutes_failed' in status
        assert 'success_rate' in status
        assert 'nodes_tracked' in status
        assert 'direct_nodes' in status
        assert 'indirect_nodes' in status
        assert 'is_throttled' in status
        assert 'is_quiet_hours' in status


class TestPluginMetadata:
    """Test plugin metadata."""
    
    def test_get_metadata(self, mock_plugin_manager, minimal_config):
        """Test that get_metadata returns correct information."""
        plugin = TracerouteMapperPlugin('traceroute_mapper', minimal_config, mock_plugin_manager)
        
        metadata = plugin.get_metadata()
        
        assert metadata.name == 'traceroute_mapper'
        assert metadata.version == '1.0.0'
        assert 'Network Traceroute Mapper' in metadata.description
        assert metadata.author == 'ZephyrGate Team'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
