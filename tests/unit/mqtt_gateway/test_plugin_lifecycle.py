"""
Unit tests for MQTT Gateway Plugin lifecycle management

Tests initialization, start/stop sequences, and configuration validation
for the MQTT Gateway plugin.

Requirements: 1.1, 1.3, 9.4
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.plugin import MQTTGatewayPlugin
from models.message import Message, MessageType


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager"""
    manager = Mock()
    manager.config_manager = None  # Force plugin to use direct config access
    manager.send_message = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def valid_config():
    """Provide valid MQTT gateway configuration"""
    return {
        'enabled': True,
        'broker_address': 'mqtt.example.com',
        'broker_port': 1883,
        'username': 'test_user',
        'password': 'test_pass',
        'tls_enabled': False,
        'root_topic': 'msh/US',
        'region': 'US',
        'format': 'json',
        'encryption_enabled': False,
        'max_messages_per_second': 10,
        'burst_multiplier': 2,
        'queue_max_size': 1000,
        'queue_persist': False,
        'reconnect_enabled': True,
        'reconnect_initial_delay': 1,
        'reconnect_max_delay': 60,
        'reconnect_multiplier': 2.0,
        'max_reconnect_attempts': -1,
        'log_level': 'INFO',
        'log_published_messages': True,
        'channels': [
            {
                'name': 'LongFast',
                'uplink_enabled': True,
                'message_types': ['text', 'position']
            }
        ]
    }


@pytest.fixture
def disabled_config():
    """Provide configuration with MQTT gateway disabled"""
    return {
        'enabled': False
    }


@pytest.fixture
def minimal_config():
    """Provide minimal valid configuration (relies on defaults)"""
    return {
        'enabled': True,
        'broker_address': 'mqtt.example.com'
    }


class TestPluginInitialization:
    """Tests for plugin initialization"""
    
    @pytest.mark.asyncio
    async def test_initialization_with_valid_config(self, mock_plugin_manager, valid_config):
        """Test plugin initializes successfully with valid configuration"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is True
        assert plugin.initialized is True
        assert plugin.enabled is True
        assert plugin._config_cache['broker_address'] == 'mqtt.example.com'
        assert plugin._config_cache['broker_port'] == 1883
        assert plugin._config_cache['format'] == 'json'
    
    @pytest.mark.asyncio
    async def test_initialization_with_disabled_config(self, mock_plugin_manager, disabled_config):
        """Test plugin initialization when disabled in config"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", disabled_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        # Should return False when disabled, but not error
        assert result is False
        assert plugin.enabled is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_with_minimal_config(self, mock_plugin_manager, minimal_config):
        """Test plugin initializes with minimal config using defaults"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", minimal_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is True
        assert plugin.initialized is True
        assert plugin._config_cache['broker_address'] == 'mqtt.example.com'
        # Check defaults are applied
        assert plugin._config_cache['broker_port'] == 1883
        assert plugin._config_cache['format'] == 'json'
        assert plugin._config_cache['max_messages_per_second'] == 10
        assert plugin._config_cache['queue_max_size'] == 1000
    
    @pytest.mark.asyncio
    async def test_initialization_with_missing_broker_address(self, mock_plugin_manager):
        """Test initialization fails when broker_address is missing or empty"""
        config = {
            'enabled': True,
            'broker_address': ''  # Empty broker address
        }
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_with_invalid_format(self, mock_plugin_manager, valid_config):
        """Test initialization fails with invalid message format"""
        config = valid_config.copy()
        config['format'] = 'invalid_format'
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_with_invalid_rate_limit(self, mock_plugin_manager, valid_config):
        """Test initialization fails with invalid rate limit"""
        config = valid_config.copy()
        config['max_messages_per_second'] = 0  # Invalid: must be >= 1
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_with_invalid_queue_size(self, mock_plugin_manager, valid_config):
        """Test initialization fails with invalid queue size"""
        config = valid_config.copy()
        config['queue_max_size'] = 5  # Invalid: must be >= 10
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_with_invalid_channels_config(self, mock_plugin_manager, valid_config):
        """Test initialization fails when channels is not a list"""
        config = valid_config.copy()
        config['channels'] = "not_a_list"
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_exception_handling(self, mock_plugin_manager, valid_config):
        """Test initialization handles exceptions gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        # Mock get_config to raise an exception
        with patch.object(plugin, 'get_config', side_effect=Exception("Test error")):
            result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False


class TestPluginStartStop:
    """Tests for plugin start/stop sequences"""
    
    @pytest.mark.asyncio
    async def test_start_without_initialization(self, mock_plugin_manager, valid_config):
        """Test start fails when plugin is not initialized"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        # Don't call initialize()
        result = await plugin.start()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_after_initialization(self, mock_plugin_manager, valid_config):
        """Test start succeeds after successful initialization"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        await plugin.initialize()
        result = await plugin.start()
        
        # Should succeed (even though components aren't implemented yet)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_stop_cleans_up_resources(self, mock_plugin_manager, valid_config):
        """Test stop cleans up resources properly"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        await plugin.initialize()
        await plugin.start()
        
        # Add a real background task
        async def dummy_task():
            await asyncio.sleep(10)
        
        task = asyncio.create_task(dummy_task())
        plugin._background_tasks.append(task)
        
        result = await plugin.stop()
        
        assert result is True
        assert plugin.stats['connected'] is False
        assert len(plugin._background_tasks) == 0
        # Task should be cancelled
        assert task.cancelled() or task.done()
    
    @pytest.mark.asyncio
    async def test_stop_handles_cancelled_tasks(self, mock_plugin_manager, valid_config):
        """Test stop handles cancelled tasks gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        await plugin.initialize()
        await plugin.start()
        
        # Create a task that raises CancelledError
        async def cancellable_task():
            raise asyncio.CancelledError()
        
        task = asyncio.create_task(cancellable_task())
        plugin._background_tasks.append(task)
        
        # Should not raise exception
        result = await plugin.stop()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_start_stop_sequence(self, mock_plugin_manager, valid_config):
        """Test complete start/stop sequence"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        # Initialize
        init_result = await plugin.initialize()
        assert init_result is True
        assert plugin.initialized is True
        
        # Start
        start_result = await plugin.start()
        assert start_result is True
        
        # Stop
        stop_result = await plugin.stop()
        assert stop_result is True
        assert plugin.stats['connected'] is False
    
    @pytest.mark.asyncio
    async def test_multiple_stop_calls(self, mock_plugin_manager, valid_config):
        """Test multiple stop calls don't cause errors"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        await plugin.initialize()
        await plugin.start()
        
        # Stop multiple times
        result1 = await plugin.stop()
        result2 = await plugin.stop()
        
        assert result1 is True
        assert result2 is True
    
    @pytest.mark.asyncio
    async def test_stop_exception_handling(self, mock_plugin_manager, valid_config):
        """Test stop handles exceptions gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        await plugin.initialize()
        await plugin.start()
        
        # Create a task that will be cancelled normally
        async def normal_task():
            await asyncio.sleep(10)
        
        task = asyncio.create_task(normal_task())
        plugin._background_tasks.append(task)
        
        # Mock the task's cancel to raise an exception
        original_cancel = task.cancel
        def cancel_with_error():
            original_cancel()
            raise RuntimeError("Cancel error")
        task.cancel = cancel_with_error
        
        # The stop should catch the exception and return False
        result = await plugin.stop()
        
        # The stop returns False when an exception occurs
        assert result is False


class TestConfigurationValidation:
    """Tests for configuration validation"""
    
    @pytest.mark.asyncio
    async def test_valid_tls_configuration(self, mock_plugin_manager, valid_config):
        """Test TLS configuration is validated correctly"""
        config = valid_config.copy()
        config['tls_enabled'] = True
        config['ca_cert'] = '/path/to/ca.crt'
        config['client_cert'] = '/path/to/client.crt'
        config['client_key'] = '/path/to/client.key'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['tls_enabled'] is True
        assert plugin._config_cache['ca_cert'] == '/path/to/ca.crt'
    
    @pytest.mark.asyncio
    async def test_reconnection_parameters_validation(self, mock_plugin_manager, valid_config):
        """Test reconnection parameters are validated"""
        config = valid_config.copy()
        config['reconnect_initial_delay'] = 2
        config['reconnect_max_delay'] = 120
        config['reconnect_multiplier'] = 3.0
        config['max_reconnect_attempts'] = 10
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_initial_delay'] == 2
        assert plugin._config_cache['reconnect_max_delay'] == 120
        assert plugin._config_cache['reconnect_multiplier'] == 3.0
        assert plugin._config_cache['max_reconnect_attempts'] == 10
    
    @pytest.mark.asyncio
    async def test_channel_configuration_validation(self, mock_plugin_manager, valid_config):
        """Test channel configuration is validated"""
        config = valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'uplink_enabled': True,
                'message_types': ['text', 'position', 'telemetry']
            },
            {
                'name': '0',
                'uplink_enabled': False,
                'message_types': []
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert len(plugin._config_cache['channels']) == 2
        assert plugin._config_cache['channels'][0]['name'] == 'LongFast'
        assert plugin._config_cache['channels'][1]['uplink_enabled'] is False
    
    @pytest.mark.asyncio
    async def test_empty_channels_list(self, mock_plugin_manager, valid_config):
        """Test empty channels list is valid"""
        config = valid_config.copy()
        config['channels'] = []
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['channels'] == []
    
    @pytest.mark.asyncio
    async def test_default_values_applied(self, mock_plugin_manager):
        """Test default values are applied for missing optional parameters"""
        config = {
            'enabled': True,
            'broker_address': 'mqtt.example.com'
            # All other parameters missing
        }
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        # Check defaults
        assert plugin._config_cache['broker_port'] == 1883
        assert plugin._config_cache['username'] == ''
        assert plugin._config_cache['password'] == ''
        assert plugin._config_cache['tls_enabled'] is False
        assert plugin._config_cache['root_topic'] == 'msh/US'
        assert plugin._config_cache['region'] == 'US'
        assert plugin._config_cache['format'] == 'json'
        assert plugin._config_cache['encryption_enabled'] is False
        assert plugin._config_cache['max_messages_per_second'] == 10
        assert plugin._config_cache['burst_multiplier'] == 2
        assert plugin._config_cache['queue_max_size'] == 1000
        assert plugin._config_cache['queue_persist'] is False
        assert plugin._config_cache['reconnect_enabled'] is True
        assert plugin._config_cache['reconnect_initial_delay'] == 1
        assert plugin._config_cache['reconnect_max_delay'] == 60
        assert plugin._config_cache['reconnect_multiplier'] == 2.0
        assert plugin._config_cache['max_reconnect_attempts'] == -1
        assert plugin._config_cache['log_level'] == 'INFO'
        assert plugin._config_cache['log_published_messages'] is True
        assert plugin._config_cache['channels'] == []
    
    @pytest.mark.asyncio
    async def test_protobuf_format_validation(self, mock_plugin_manager, valid_config):
        """Test protobuf format is accepted"""
        config = valid_config.copy()
        config['format'] = 'protobuf'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['format'] == 'protobuf'
    
    @pytest.mark.asyncio
    async def test_encryption_enabled_validation(self, mock_plugin_manager, valid_config):
        """Test encryption_enabled flag is validated"""
        config = valid_config.copy()
        config['encryption_enabled'] = True
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['encryption_enabled'] is True


class TestPluginHealthStatus:
    """Tests for plugin health status reporting"""
    
    @pytest.mark.asyncio
    async def test_health_status_before_initialization(self, mock_plugin_manager, valid_config):
        """Test health status before initialization"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is False
        assert status['enabled'] is False
        assert status['initialized'] is False
        assert status['connected'] is False
    
    @pytest.mark.asyncio
    async def test_health_status_after_initialization(self, mock_plugin_manager, valid_config):
        """Test health status after initialization"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        assert status['enabled'] is True
        assert status['initialized'] is True
        assert status['messages_received'] == 0
        assert status['messages_published'] == 0
        assert status['messages_queued'] == 0
        assert status['messages_dropped'] == 0
        assert status['publish_errors'] == 0
    
    @pytest.mark.asyncio
    async def test_health_status_includes_statistics(self, mock_plugin_manager, valid_config):
        """Test health status includes all statistics"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate some activity
        plugin.stats['messages_received'] = 10
        plugin.stats['messages_published'] = 8
        plugin.stats['messages_queued'] = 2
        plugin.stats['publish_errors'] = 1
        
        status = await plugin.get_health_status()
        
        assert status['messages_received'] == 10
        assert status['messages_published'] == 8
        assert status['messages_queued'] == 2
        assert status['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_health_status_includes_connection_statistics(self, mock_plugin_manager, valid_config):
        """Test health status includes connection statistics from MQTT client"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Verify connection statistics are present
        assert 'connection_count' in status
        assert 'disconnection_count' in status
        assert 'reconnection_count' in status
        assert 'last_connect_time' in status
        assert 'last_disconnect_time' in status
        assert status['connection_count'] == 0  # No connections yet
        assert status['disconnection_count'] == 0
        assert status['reconnection_count'] == 0
    
    @pytest.mark.asyncio
    async def test_health_status_includes_queue_statistics(self, mock_plugin_manager, valid_config):
        """Test health status includes queue statistics"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Verify queue statistics are present
        assert 'queue_size' in status
        assert 'queue_max_size' in status
        assert 'queue_utilization_percent' in status
        assert status['queue_size'] == 0  # Empty queue
        assert status['queue_max_size'] == 1000  # From config
        assert status['queue_utilization_percent'] == 0.0
    
    @pytest.mark.asyncio
    async def test_health_status_includes_rate_limiter_statistics(self, mock_plugin_manager, valid_config):
        """Test health status includes rate limiter statistics"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Verify rate limiter statistics are present
        assert 'rate_limit' in status
        assert 'max_messages_per_second' in status['rate_limit']
        assert 'burst_capacity' in status['rate_limit']
        assert 'current_tokens' in status['rate_limit']
        assert 'messages_allowed' in status['rate_limit']
        assert 'messages_delayed' in status['rate_limit']
        assert 'total_wait_time' in status['rate_limit']
        assert 'max_wait_time' in status['rate_limit']
        assert 'avg_wait_time' in status['rate_limit']
        
        # Verify initial values
        assert status['rate_limit']['max_messages_per_second'] == 10  # From config
        assert status['rate_limit']['burst_capacity'] == 20  # 10 * 2
        assert status['rate_limit']['messages_allowed'] == 0
        assert status['rate_limit']['messages_delayed'] == 0
    
    @pytest.mark.asyncio
    async def test_health_status_queue_utilization_calculation(self, mock_plugin_manager, valid_config):
        """Test health status calculates queue utilization correctly"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Add messages to the queue to simulate 500 out of 1000
        from models.message import Message, MessageType, MessagePriority
        for i in range(500):
            test_message = Message(
                id=f"test_{i}",
                sender_id="!test1234",
                message_type=MessageType.TEXT,
                channel=0,
                priority=MessagePriority.NORMAL,
                content=f"Test message {i}"
            )
            await plugin.message_queue.enqueue(
                test_message,
                topic=f"msh/US/2/json/LongFast/!test1234",
                payload=b"test payload",
                qos=0
            )
        
        status = await plugin.get_health_status()
        
        assert status['queue_size'] == 500
        assert status['queue_max_size'] == 1000
        assert status['queue_utilization_percent'] == 50.0
    
    @pytest.mark.asyncio
    async def test_health_status_handles_missing_components(self, mock_plugin_manager, valid_config):
        """Test health status handles missing components gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        # Don't initialize - components will be None
        
        status = await plugin.get_health_status()
        
        # Should not raise exception
        assert status['healthy'] is False
        assert status['queue_size'] == 0  # Default when queue is None
        assert 'rate_limit' in status
        assert 'connection_count' in status


class TestPluginMetadata:
    """Tests for plugin metadata"""
    
    def test_get_metadata(self, mock_plugin_manager, valid_config):
        """Test plugin metadata is correct"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        metadata = plugin.get_metadata()
        
        assert metadata.name == "mqtt_gateway"
        assert metadata.version == "1.0.0"
        assert "MQTT Gateway" in metadata.description
        assert metadata.author == "ZephyrGate Team"


class TestPluginCleanup:
    """Tests for plugin cleanup"""
    
    @pytest.mark.asyncio
    async def test_cleanup_calls_stop(self, mock_plugin_manager, valid_config):
        """Test cleanup calls stop method"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        result = await plugin.cleanup()
        
        assert result is True
        assert plugin.stats['connected'] is False
