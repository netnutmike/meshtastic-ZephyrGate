"""
Unit tests for MQTT Gateway Plugin health status reporting

Tests health status reporting and statistics tracking for the MQTT Gateway plugin.

Requirements: 11.1
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.plugin import MQTTGatewayPlugin
from models.message import Message, MessageType, MessagePriority


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


class TestHealthStatusStructure:
    """Tests for health status structure and required fields"""
    
    @pytest.mark.asyncio
    async def test_health_status_contains_all_required_fields(self, mock_plugin_manager, valid_config):
        """Test health status includes all required fields"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Overall health fields
        assert 'healthy' in status
        assert 'enabled' in status
        assert 'initialized' in status
        assert 'connected' in status
        
        # Connection statistics
        assert 'connection_count' in status
        assert 'disconnection_count' in status
        assert 'reconnection_count' in status
        assert 'last_connect_time' in status
        assert 'last_disconnect_time' in status
        
        # Message counters
        assert 'messages_received' in status
        assert 'messages_published' in status
        assert 'messages_queued' in status
        assert 'messages_dropped' in status
        assert 'last_publish_time' in status
        
        # Error counts
        assert 'publish_errors' in status
        assert 'mqtt_publish_errors' in status
        
        # Queue statistics
        assert 'queue_size' in status
        assert 'queue_max_size' in status
        assert 'queue_utilization_percent' in status
        
        # Rate limiter statistics
        assert 'rate_limit' in status
        assert isinstance(status['rate_limit'], dict)
    
    @pytest.mark.asyncio
    async def test_health_status_rate_limit_contains_required_fields(self, mock_plugin_manager, valid_config):
        """Test health status rate_limit section contains all required fields"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        rate_limit = status['rate_limit']
        assert 'max_messages_per_second' in rate_limit
        assert 'burst_capacity' in rate_limit
        assert 'current_tokens' in rate_limit
        assert 'messages_allowed' in rate_limit
        assert 'messages_delayed' in rate_limit
        assert 'total_wait_time' in rate_limit
        assert 'max_wait_time' in rate_limit
        assert 'avg_wait_time' in rate_limit
    
    @pytest.mark.asyncio
    async def test_health_status_field_types(self, mock_plugin_manager, valid_config):
        """Test health status fields have correct types"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        # Boolean fields
        assert isinstance(status['healthy'], bool)
        assert isinstance(status['enabled'], bool)
        assert isinstance(status['initialized'], bool)
        assert isinstance(status['connected'], bool)
        
        # Integer fields
        assert isinstance(status['connection_count'], int)
        assert isinstance(status['disconnection_count'], int)
        assert isinstance(status['reconnection_count'], int)
        assert isinstance(status['messages_received'], int)
        assert isinstance(status['messages_published'], int)
        assert isinstance(status['messages_queued'], int)
        assert isinstance(status['messages_dropped'], int)
        assert isinstance(status['publish_errors'], int)
        assert isinstance(status['mqtt_publish_errors'], int)
        assert isinstance(status['queue_size'], int)
        assert isinstance(status['queue_max_size'], int)
        
        # Float fields
        assert isinstance(status['queue_utilization_percent'], (int, float))
        
        # Timestamp fields (can be None or string)
        assert status['last_connect_time'] is None or isinstance(status['last_connect_time'], str)
        assert status['last_disconnect_time'] is None or isinstance(status['last_disconnect_time'], str)
        assert status['last_publish_time'] is None or isinstance(status['last_publish_time'], str)


class TestHealthStatusBeforeInitialization:
    """Tests for health status before plugin initialization"""
    
    @pytest.mark.asyncio
    async def test_health_status_before_initialization(self, mock_plugin_manager, valid_config):
        """Test health status before initialization shows unhealthy state"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is False
        assert status['enabled'] is False
        assert status['initialized'] is False
        assert status['connected'] is False
    
    @pytest.mark.asyncio
    async def test_health_status_before_initialization_has_zero_counters(self, mock_plugin_manager, valid_config):
        """Test health status before initialization has zero counters"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['messages_received'] == 0
        assert status['messages_published'] == 0
        assert status['messages_queued'] == 0
        assert status['messages_dropped'] == 0
        assert status['publish_errors'] == 0
        assert status['connection_count'] == 0
        assert status['disconnection_count'] == 0
        assert status['reconnection_count'] == 0
    
    @pytest.mark.asyncio
    async def test_health_status_before_initialization_has_null_timestamps(self, mock_plugin_manager, valid_config):
        """Test health status before initialization has null timestamps"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['last_connect_time'] is None
        assert status['last_disconnect_time'] is None
        assert status['last_publish_time'] is None


class TestHealthStatusAfterInitialization:
    """Tests for health status after plugin initialization"""
    
    @pytest.mark.asyncio
    async def test_health_status_after_initialization(self, mock_plugin_manager, valid_config):
        """Test health status after initialization shows correct state"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        assert status['enabled'] is True
        assert status['initialized'] is True
        # Note: healthy depends on connection status, which may be False initially
        # Note: connected may be False if MQTT client hasn't connected yet
    
    @pytest.mark.asyncio
    async def test_health_status_after_initialization_has_queue_info(self, mock_plugin_manager, valid_config):
        """Test health status after initialization includes queue information"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        assert status['queue_size'] == 0  # Empty queue initially
        assert status['queue_max_size'] == 1000  # From config
        assert status['queue_utilization_percent'] == 0.0
    
    @pytest.mark.asyncio
    async def test_health_status_after_initialization_has_rate_limit_info(self, mock_plugin_manager, valid_config):
        """Test health status after initialization includes rate limiter information"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        rate_limit = status['rate_limit']
        assert rate_limit['max_messages_per_second'] == 10  # From config
        assert rate_limit['burst_capacity'] == 20  # 10 * 2
        assert rate_limit['messages_allowed'] == 0  # No messages processed yet
        assert rate_limit['messages_delayed'] == 0


class TestStatisticsTracking:
    """Tests for statistics tracking in health status"""
    
    @pytest.mark.asyncio
    async def test_message_received_counter_increments(self, mock_plugin_manager, valid_config):
        """Test messages_received counter increments when messages are received"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate receiving messages
        plugin.stats['messages_received'] = 5
        
        status = await plugin.get_health_status()
        
        assert status['messages_received'] == 5
    
    @pytest.mark.asyncio
    async def test_message_published_counter_increments(self, mock_plugin_manager, valid_config):
        """Test messages_published counter increments when messages are published"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate publishing messages
        plugin.stats['messages_published'] = 3
        
        status = await plugin.get_health_status()
        
        assert status['messages_published'] == 3
    
    @pytest.mark.asyncio
    async def test_message_queued_counter_increments(self, mock_plugin_manager, valid_config):
        """Test messages_queued counter increments when messages are queued"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate queuing messages
        plugin.stats['messages_queued'] = 7
        
        status = await plugin.get_health_status()
        
        assert status['messages_queued'] == 7
    
    @pytest.mark.asyncio
    async def test_message_dropped_counter_increments(self, mock_plugin_manager, valid_config):
        """Test messages_dropped counter increments when messages are dropped"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate dropping messages
        plugin.stats['messages_dropped'] = 2
        
        status = await plugin.get_health_status()
        
        assert status['messages_dropped'] == 2
    
    @pytest.mark.asyncio
    async def test_publish_errors_counter_increments(self, mock_plugin_manager, valid_config):
        """Test publish_errors counter increments when publish errors occur"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate publish errors
        plugin.stats['publish_errors'] = 1
        
        status = await plugin.get_health_status()
        
        assert status['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_last_publish_time_is_tracked(self, mock_plugin_manager, valid_config):
        """Test last_publish_time is tracked and formatted correctly"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate a publish
        now = datetime.now()
        plugin.stats['last_publish_time'] = now
        
        status = await plugin.get_health_status()
        
        assert status['last_publish_time'] is not None
        assert isinstance(status['last_publish_time'], str)
        # Verify it's a valid ISO format timestamp
        parsed_time = datetime.fromisoformat(status['last_publish_time'])
        assert abs((parsed_time - now).total_seconds()) < 1


class TestQueueStatistics:
    """Tests for queue statistics in health status"""
    
    @pytest.mark.asyncio
    async def test_queue_size_reflects_current_queue(self, mock_plugin_manager, valid_config):
        """Test queue_size reflects the current number of queued messages"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Add messages to queue
        for i in range(10):
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
        
        assert status['queue_size'] == 10
    
    @pytest.mark.asyncio
    async def test_queue_utilization_calculation(self, mock_plugin_manager, valid_config):
        """Test queue_utilization_percent is calculated correctly"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Add 250 messages to a queue with max_size 1000
        for i in range(250):
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
        
        assert status['queue_size'] == 250
        assert status['queue_max_size'] == 1000
        assert status['queue_utilization_percent'] == 25.0
    
    @pytest.mark.asyncio
    async def test_queue_utilization_at_full_capacity(self, mock_plugin_manager, valid_config):
        """Test queue_utilization_percent at 100% capacity"""
        # Use smaller queue for faster test
        config = valid_config.copy()
        config['queue_max_size'] = 10
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Fill the queue to capacity
        for i in range(10):
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
        
        assert status['queue_size'] == 10
        assert status['queue_max_size'] == 10
        assert status['queue_utilization_percent'] == 100.0
    
    @pytest.mark.asyncio
    async def test_queue_utilization_with_empty_queue(self, mock_plugin_manager, valid_config):
        """Test queue_utilization_percent with empty queue"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        status = await plugin.get_health_status()
        
        assert status['queue_size'] == 0
        assert status['queue_max_size'] == 1000
        assert status['queue_utilization_percent'] == 0.0


class TestConnectionStatistics:
    """Tests for connection statistics in health status"""
    
    @pytest.mark.asyncio
    async def test_connection_statistics_from_mqtt_client(self, mock_plugin_manager, valid_config):
        """Test connection statistics are retrieved from MQTT client"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Mock MQTT client stats
        mock_stats = {
            'connection_count': 3,
            'disconnection_count': 2,
            'reconnection_count': 1,
            'last_connect_time': datetime.now(),
            'last_disconnect_time': datetime.now() - timedelta(minutes=5),
            'publish_errors': 1
        }
        plugin.mqtt_client.get_stats = Mock(return_value=mock_stats)
        
        status = await plugin.get_health_status()
        
        assert status['connection_count'] == 3
        assert status['disconnection_count'] == 2
        assert status['reconnection_count'] == 1
        assert status['mqtt_publish_errors'] == 1
        assert status['last_connect_time'] is not None
        assert status['last_disconnect_time'] is not None
    
    @pytest.mark.asyncio
    async def test_connection_statistics_handles_missing_mqtt_client(self, mock_plugin_manager, valid_config):
        """Test connection statistics handle missing MQTT client gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        # Don't initialize - mqtt_client will be None
        
        status = await plugin.get_health_status()
        
        # Should not raise exception
        assert status['connection_count'] == 0
        assert status['disconnection_count'] == 0
        assert status['reconnection_count'] == 0
    
    @pytest.mark.asyncio
    async def test_connection_statistics_handles_mqtt_client_exception(self, mock_plugin_manager, valid_config):
        """Test connection statistics handle MQTT client exceptions gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Mock MQTT client to raise exception
        plugin.mqtt_client.get_stats = Mock(side_effect=Exception("Test error"))
        
        # Should not raise exception
        status = await plugin.get_health_status()
        
        assert status is not None
        assert 'connection_count' in status


class TestRateLimiterStatistics:
    """Tests for rate limiter statistics in health status"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_statistics_from_rate_limiter(self, mock_plugin_manager, valid_config):
        """Test rate limiter statistics are retrieved from rate limiter"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Mock rate limiter stats
        mock_stats = {
            'max_messages_per_second': 10,
            'burst_capacity': 20,
            'current_tokens': 15.5,
            'messages_allowed': 100,
            'messages_delayed': 5,
            'total_wait_time': 2.5,
            'max_wait_time': 1.0,
            'avg_wait_time': 0.5
        }
        plugin.rate_limiter.get_statistics = Mock(return_value=mock_stats)
        
        status = await plugin.get_health_status()
        
        rate_limit = status['rate_limit']
        assert rate_limit['max_messages_per_second'] == 10
        assert rate_limit['burst_capacity'] == 20
        assert rate_limit['current_tokens'] == 15.5
        assert rate_limit['messages_allowed'] == 100
        assert rate_limit['messages_delayed'] == 5
        assert rate_limit['total_wait_time'] == 2.5
        assert rate_limit['max_wait_time'] == 1.0
        assert rate_limit['avg_wait_time'] == 0.5
    
    @pytest.mark.asyncio
    async def test_rate_limiter_statistics_handles_missing_rate_limiter(self, mock_plugin_manager, valid_config):
        """Test rate limiter statistics handle missing rate limiter gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        # Don't initialize - rate_limiter will be None
        
        status = await plugin.get_health_status()
        
        # Should not raise exception
        assert 'rate_limit' in status
        assert isinstance(status['rate_limit'], dict)
    
    @pytest.mark.asyncio
    async def test_rate_limiter_statistics_handles_exception(self, mock_plugin_manager, valid_config):
        """Test rate limiter statistics handle exceptions gracefully"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Mock rate limiter to raise exception
        plugin.rate_limiter.get_statistics = Mock(side_effect=Exception("Test error"))
        
        # Should not raise exception
        status = await plugin.get_health_status()
        
        assert status is not None
        assert 'rate_limit' in status


class TestHealthyStatus:
    """Tests for overall healthy status determination"""
    
    @pytest.mark.asyncio
    async def test_healthy_when_enabled_initialized_and_connected(self, mock_plugin_manager, valid_config):
        """Test plugin is healthy when enabled, initialized, and connected"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Simulate connected state
        plugin.stats['connected'] = True
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is True
        assert status['enabled'] is True
        assert status['initialized'] is True
        assert status['connected'] is True
    
    @pytest.mark.asyncio
    async def test_unhealthy_when_not_connected(self, mock_plugin_manager, valid_config):
        """Test plugin is unhealthy when not connected"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Ensure not connected
        plugin.stats['connected'] = False
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is False
        assert status['enabled'] is True
        assert status['initialized'] is True
        assert status['connected'] is False
    
    @pytest.mark.asyncio
    async def test_unhealthy_when_not_initialized(self, mock_plugin_manager, valid_config):
        """Test plugin is unhealthy when not initialized"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        # Don't initialize
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is False
        assert status['initialized'] is False
    
    @pytest.mark.asyncio
    async def test_unhealthy_when_disabled(self, mock_plugin_manager):
        """Test plugin is unhealthy when disabled"""
        config = {'enabled': False}
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        status = await plugin.get_health_status()
        
        assert status['healthy'] is False
        assert status['enabled'] is False


class TestHealthStatusRounding:
    """Tests for numeric value rounding in health status"""
    
    @pytest.mark.asyncio
    async def test_queue_utilization_rounded_to_two_decimals(self, mock_plugin_manager, valid_config):
        """Test queue_utilization_percent is rounded to 2 decimal places"""
        # Use queue size that results in non-round percentage
        config = valid_config.copy()
        config['queue_max_size'] = 300
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Add 100 messages (100/300 = 33.333...%)
        for i in range(100):
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
        
        # Should be rounded to 2 decimal places
        assert status['queue_utilization_percent'] == 33.33
    
    @pytest.mark.asyncio
    async def test_rate_limit_values_rounded_appropriately(self, mock_plugin_manager, valid_config):
        """Test rate limit values are rounded to appropriate precision"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", valid_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Mock rate limiter with precise values
        mock_stats = {
            'max_messages_per_second': 10,
            'burst_capacity': 20,
            'current_tokens': 15.123456,
            'messages_allowed': 100,
            'messages_delayed': 5,
            'total_wait_time': 2.123456,
            'max_wait_time': 1.123456,
            'avg_wait_time': 0.123456
        }
        plugin.rate_limiter.get_statistics = Mock(return_value=mock_stats)
        
        status = await plugin.get_health_status()
        
        rate_limit = status['rate_limit']
        # current_tokens rounded to 2 decimals
        assert rate_limit['current_tokens'] == 15.12
        # Wait times rounded to 3 decimals
        assert rate_limit['total_wait_time'] == 2.123
        assert rate_limit['max_wait_time'] == 1.123
        assert rate_limit['avg_wait_time'] == 0.123
