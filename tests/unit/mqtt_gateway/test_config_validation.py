"""
Unit tests for MQTT Gateway configuration validation

Tests comprehensive parameter validation including:
- Type validation for all parameters
- Range validation for numeric parameters
- Required parameter validation
- Default value application
- Descriptive error messages

Requirements: 9.2, 9.3, 9.4
"""

import pytest
from unittest.mock import Mock, patch
from plugins.mqtt_gateway.plugin import MQTTGatewayPlugin


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager"""
    manager = Mock()
    manager.config_manager = None  # Force plugin to use direct config access
    manager.message_router = None
    return manager


@pytest.fixture
def minimal_valid_config():
    """Minimal valid configuration with only required fields"""
    return {
        'enabled': True,
        'broker_address': 'mqtt.example.com'
    }


@pytest.fixture
def full_valid_config():
    """Full valid configuration with all fields"""
    return {
        'enabled': True,
        'broker_address': 'mqtt.example.com',
        'broker_port': 1883,
        'username': 'testuser',
        'password': 'testpass',
        'tls_enabled': False,
        'ca_cert': '',
        'client_cert': '',
        'client_key': '',
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
        'channels': []
    }


class TestBrokerAddressValidation:
    """Tests for broker_address parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_broker_address(self, mock_plugin_manager, minimal_valid_config):
        """Test valid broker address is accepted"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", minimal_valid_config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_address'] == 'mqtt.example.com'
    
    @pytest.mark.asyncio
    async def test_broker_address_with_whitespace_is_trimmed(self, mock_plugin_manager, minimal_valid_config):
        """Test broker address with whitespace is trimmed"""
        config = minimal_valid_config.copy()
        config['broker_address'] = '  mqtt.example.com  '
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_address'] == 'mqtt.example.com'
    
    @pytest.mark.asyncio
    async def test_empty_broker_address_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test empty broker address fails validation"""
        config = minimal_valid_config.copy()
        config['broker_address'] = ''
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_whitespace_only_broker_address_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test whitespace-only broker address fails validation"""
        config = minimal_valid_config.copy()
        config['broker_address'] = '   '
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False
    
    @pytest.mark.asyncio
    async def test_non_string_broker_address_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test non-string broker address fails validation"""
        config = minimal_valid_config.copy()
        config['broker_address'] = 12345
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
        assert plugin.initialized is False


class TestBrokerPortValidation:
    """Tests for broker_port parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_broker_port(self, mock_plugin_manager, minimal_valid_config):
        """Test valid broker port is accepted"""
        config = minimal_valid_config.copy()
        config['broker_port'] = 8883
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_port'] == 8883
    
    @pytest.mark.asyncio
    async def test_default_broker_port(self, mock_plugin_manager, minimal_valid_config):
        """Test default broker port is applied"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", minimal_valid_config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_port'] == 1883
    
    @pytest.mark.asyncio
    async def test_broker_port_below_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test broker port below valid range fails"""
        config = minimal_valid_config.copy()
        config['broker_port'] = 0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_broker_port_above_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test broker port above valid range fails"""
        config = minimal_valid_config.copy()
        config['broker_port'] = 65536
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_non_integer_broker_port_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test non-integer broker port fails validation"""
        config = minimal_valid_config.copy()
        config['broker_port'] = "1883"
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestRootTopicValidation:
    """Tests for root_topic parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_root_topic(self, mock_plugin_manager, minimal_valid_config):
        """Test valid root topic is accepted"""
        config = minimal_valid_config.copy()
        config['root_topic'] = 'custom/topic/path'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['root_topic'] == 'custom/topic/path'
    
    @pytest.mark.asyncio
    async def test_root_topic_with_wildcard_plus_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test root topic with + wildcard fails"""
        config = minimal_valid_config.copy()
        config['root_topic'] = 'msh/+/topic'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_root_topic_with_wildcard_hash_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test root topic with # wildcard fails"""
        config = minimal_valid_config.copy()
        config['root_topic'] = 'msh/#'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_empty_root_topic_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test empty root topic fails validation"""
        config = minimal_valid_config.copy()
        config['root_topic'] = ''
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestRegionValidation:
    """Tests for region parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_region(self, mock_plugin_manager, minimal_valid_config):
        """Test valid region is accepted"""
        config = minimal_valid_config.copy()
        config['region'] = 'EU'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['region'] == 'EU'
    
    @pytest.mark.asyncio
    async def test_region_too_short_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test region shorter than 2 characters fails"""
        config = minimal_valid_config.copy()
        config['region'] = 'U'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_region_too_long_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test region longer than 10 characters fails"""
        config = minimal_valid_config.copy()
        config['region'] = 'VERYLONGREGION'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestRateLimitValidation:
    """Tests for rate limiting parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_max_messages_per_second(self, mock_plugin_manager, minimal_valid_config):
        """Test valid max_messages_per_second is accepted"""
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = 50
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_messages_per_second'] == 50
    
    @pytest.mark.asyncio
    async def test_max_messages_per_second_below_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test max_messages_per_second below 1 fails"""
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = 0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_max_messages_per_second_above_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test max_messages_per_second above 1000 fails"""
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = 1001
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_valid_range(self, mock_plugin_manager, minimal_valid_config):
        """Test valid burst_multiplier is accepted"""
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = 5.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['burst_multiplier'] == 5.0
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_below_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test burst_multiplier below 1 fails"""
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = 0.5
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_above_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test burst_multiplier above 10 fails"""
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = 11
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestReconnectionValidation:
    """Tests for reconnection parameter validation"""
    
    @pytest.mark.asyncio
    async def test_reconnect_initial_delay_valid_range(self, mock_plugin_manager, minimal_valid_config):
        """Test valid reconnect_initial_delay is accepted"""
        config = minimal_valid_config.copy()
        config['reconnect_initial_delay'] = 5.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_initial_delay'] == 5.0
    
    @pytest.mark.asyncio
    async def test_reconnect_initial_delay_below_range_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test reconnect_initial_delay below 0.1 fails"""
        config = minimal_valid_config.copy()
        config['reconnect_initial_delay'] = 0.05
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_reconnect_max_delay_valid_range(self, mock_plugin_manager, minimal_valid_config):
        """Test valid reconnect_max_delay is accepted"""
        config = minimal_valid_config.copy()
        config['reconnect_max_delay'] = 120
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_max_delay'] == 120.0
    
    @pytest.mark.asyncio
    async def test_reconnect_max_delay_less_than_initial_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test reconnect_max_delay < reconnect_initial_delay fails"""
        config = minimal_valid_config.copy()
        config['reconnect_initial_delay'] = 10
        config['reconnect_max_delay'] = 5
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_reconnect_multiplier_valid_range(self, mock_plugin_manager, minimal_valid_config):
        """Test valid reconnect_multiplier is accepted"""
        config = minimal_valid_config.copy()
        config['reconnect_multiplier'] = 3.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_multiplier'] == 3.0
    
    @pytest.mark.asyncio
    async def test_max_reconnect_attempts_negative_one_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test max_reconnect_attempts = -1 (infinite) is valid"""
        config = minimal_valid_config.copy()
        config['max_reconnect_attempts'] = -1
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_reconnect_attempts'] == -1
    
    @pytest.mark.asyncio
    async def test_max_reconnect_attempts_below_negative_one_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test max_reconnect_attempts < -1 fails"""
        config = minimal_valid_config.copy()
        config['max_reconnect_attempts'] = -2
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestLogLevelValidation:
    """Tests for log_level parameter validation"""
    
    @pytest.mark.asyncio
    async def test_valid_log_levels(self, mock_plugin_manager, minimal_valid_config):
        """Test all valid log levels are accepted"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for level in valid_levels:
            config = minimal_valid_config.copy()
            config['log_level'] = level
            
            plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
            result = await plugin.initialize()
            
            assert result is True
            assert plugin._config_cache['log_level'] == level
    
    @pytest.mark.asyncio
    async def test_lowercase_log_level_converted_to_uppercase(self, mock_plugin_manager, minimal_valid_config):
        """Test lowercase log level is converted to uppercase"""
        config = minimal_valid_config.copy()
        config['log_level'] = 'debug'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['log_level'] == 'DEBUG'
    
    @pytest.mark.asyncio
    async def test_invalid_log_level_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test invalid log level fails validation"""
        config = minimal_valid_config.copy()
        config['log_level'] = 'INVALID'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False



class TestChannelConfigurationValidation:
    """Tests for channel configuration validation"""
    
    @pytest.mark.asyncio
    async def test_valid_channel_configuration(self, mock_plugin_manager, minimal_valid_config):
        """Test valid channel configuration is accepted"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'uplink_enabled': True,
                'message_types': ['text', 'position']
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert len(plugin._config_cache['channels']) == 1
    
    @pytest.mark.asyncio
    async def test_channel_without_name_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel without name field fails"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'uplink_enabled': True
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channel_with_empty_name_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with empty name fails"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': '',
                'uplink_enabled': True
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channel_with_invalid_message_type_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with invalid message type fails"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'message_types': ['text', 'invalid_type']
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channels_not_list_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channels that is not a list fails"""
        config = minimal_valid_config.copy()
        config['channels'] = "not_a_list"
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channel_not_dict_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel that is not a dict fails"""
        config = minimal_valid_config.copy()
        config['channels'] = ["not_a_dict"]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channel_message_types_not_list_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with message_types not a list fails"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'message_types': 'text'
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_channel_uplink_enabled_not_bool_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with uplink_enabled not a bool fails"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'uplink_enabled': 'true'
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False


class TestDefaultValueApplication:
    """Tests for default value application (Requirement 9.3)"""
    
    @pytest.mark.asyncio
    async def test_all_defaults_applied(self, mock_plugin_manager, minimal_valid_config):
        """Test all default values are applied when parameters are missing"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", minimal_valid_config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        # Verify all defaults
        assert plugin._config_cache['broker_port'] == 1883
        assert plugin._config_cache['username'] == ''
        assert plugin._config_cache['password'] == ''
        assert plugin._config_cache['tls_enabled'] is False
        assert plugin._config_cache['ca_cert'] == ''
        assert plugin._config_cache['client_cert'] == ''
        assert plugin._config_cache['client_key'] == ''
        assert plugin._config_cache['root_topic'] == 'msh/US'
        assert plugin._config_cache['region'] == 'US'
        assert plugin._config_cache['format'] == 'json'
        assert plugin._config_cache['encryption_enabled'] is False
        assert plugin._config_cache['max_messages_per_second'] == 10
        assert plugin._config_cache['burst_multiplier'] == 2.0
        assert plugin._config_cache['queue_max_size'] == 1000
        assert plugin._config_cache['queue_persist'] is False
        assert plugin._config_cache['reconnect_enabled'] is True
        assert plugin._config_cache['reconnect_initial_delay'] == 1.0
        assert plugin._config_cache['reconnect_max_delay'] == 60.0
        assert plugin._config_cache['reconnect_multiplier'] == 2.0
        assert plugin._config_cache['max_reconnect_attempts'] == -1
        assert plugin._config_cache['log_level'] == 'INFO'
        assert plugin._config_cache['log_published_messages'] is True
        assert plugin._config_cache['channels'] == []


class TestTypeValidation:
    """Tests for parameter type validation (Requirement 9.2)"""
    
    @pytest.mark.asyncio
    async def test_username_wrong_type_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test username with wrong type fails"""
        config = minimal_valid_config.copy()
        config['username'] = 12345
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_tls_enabled_wrong_type_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test tls_enabled with wrong type fails"""
        config = minimal_valid_config.copy()
        config['tls_enabled'] = 'true'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_format_wrong_type_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test format with wrong type fails"""
        config = minimal_valid_config.copy()
        config['format'] = 123
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_queue_max_size_wrong_type_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test queue_max_size with wrong type fails"""
        config = minimal_valid_config.copy()
        config['queue_max_size'] = "1000"
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False



class TestConfigurationEdgeCases:
    """
    Additional edge case tests for configuration validation
    Task 12.3: Test missing required parameters, invalid parameter values, and default value application
    Requirements: 9.3, 9.4
    """
    
    @pytest.mark.asyncio
    async def test_missing_broker_address_uses_default(self, mock_plugin_manager):
        """Test missing broker_address uses default value"""
        config = {'enabled': True}
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_address'] == 'mqtt.meshtastic.org'
    
    @pytest.mark.asyncio
    async def test_disabled_plugin_skips_validation(self, mock_plugin_manager):
        """Test disabled plugin skips validation and returns False"""
        config = {'enabled': False}
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        # Plugin should return False when disabled (not an error, just disabled)
        assert result is False
        assert plugin.enabled is False
    
    @pytest.mark.asyncio
    async def test_queue_max_size_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test queue_max_size at boundary values"""
        # Test minimum valid value
        config = minimal_valid_config.copy()
        config['queue_max_size'] = 10
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['queue_max_size'] == 10
        
        # Test maximum valid value
        config['queue_max_size'] = 100000
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['queue_max_size'] == 100000
    
    @pytest.mark.asyncio
    async def test_broker_port_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test broker_port at boundary values"""
        # Test minimum valid value
        config = minimal_valid_config.copy()
        config['broker_port'] = 1
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_port'] == 1
        
        # Test maximum valid value
        config['broker_port'] = 65535
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['broker_port'] == 65535
    
    @pytest.mark.asyncio
    async def test_max_messages_per_second_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test max_messages_per_second at boundary values"""
        # Test minimum valid value
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = 1
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_messages_per_second'] == 1
        
        # Test maximum valid value
        config['max_messages_per_second'] = 1000
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_messages_per_second'] == 1000
    
    @pytest.mark.asyncio
    async def test_region_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test region at boundary values"""
        # Test minimum valid length (2 chars)
        config = minimal_valid_config.copy()
        config['region'] = 'US'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['region'] == 'US'
        
        # Test maximum valid length (10 chars)
        config['region'] = 'ABCDEFGHIJ'
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['region'] == 'ABCDEFGHIJ'
    
    @pytest.mark.asyncio
    async def test_reconnect_delay_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test reconnect delay parameters at boundary values"""
        config = minimal_valid_config.copy()
        
        # Test minimum initial delay
        config['reconnect_initial_delay'] = 0.1
        config['reconnect_max_delay'] = 1.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_initial_delay'] == 0.1
        
        # Test maximum delays
        config['reconnect_initial_delay'] = 60
        config['reconnect_max_delay'] = 3600
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_initial_delay'] == 60.0
        assert plugin._config_cache['reconnect_max_delay'] == 3600.0
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test burst_multiplier at boundary values"""
        # Test minimum valid value
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = 1.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['burst_multiplier'] == 1.0
        
        # Test maximum valid value
        config['burst_multiplier'] = 10.0
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['burst_multiplier'] == 10.0
    
    @pytest.mark.asyncio
    async def test_reconnect_multiplier_boundary_values(self, mock_plugin_manager, minimal_valid_config):
        """Test reconnect_multiplier at boundary values"""
        # Test minimum valid value
        config = minimal_valid_config.copy()
        config['reconnect_multiplier'] = 1.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_multiplier'] == 1.0
        
        # Test maximum valid value
        config['reconnect_multiplier'] = 10.0
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_multiplier'] == 10.0
    
    @pytest.mark.asyncio
    async def test_format_case_sensitivity(self, mock_plugin_manager, minimal_valid_config):
        """Test format parameter is case-sensitive"""
        # Valid lowercase
        config = minimal_valid_config.copy()
        config['format'] = 'json'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['format'] == 'json'
        
        # Invalid uppercase should fail
        config['format'] = 'JSON'
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_empty_channels_list_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test empty channels list is valid (default)"""
        config = minimal_valid_config.copy()
        config['channels'] = []
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['channels'] == []
    
    @pytest.mark.asyncio
    async def test_channel_with_minimal_fields(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with only required name field"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {'name': 'TestChannel'}
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert len(plugin._config_cache['channels']) == 1
        assert plugin._config_cache['channels'][0]['name'] == 'TestChannel'
    
    @pytest.mark.asyncio
    async def test_channel_with_empty_message_types_list(self, mock_plugin_manager, minimal_valid_config):
        """Test channel with empty message_types list is valid"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'TestChannel',
                'message_types': []
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['channels'][0]['message_types'] == []
    
    @pytest.mark.asyncio
    async def test_multiple_channels_configuration(self, mock_plugin_manager, minimal_valid_config):
        """Test configuration with multiple channels"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'LongFast',
                'uplink_enabled': True,
                'message_types': ['text', 'position']
            },
            {
                'name': 'ShortFast',
                'uplink_enabled': False,
                'message_types': ['telemetry']
            },
            {
                'name': 'Channel0',
                'uplink_enabled': True,
                'message_types': []
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert len(plugin._config_cache['channels']) == 3
    
    @pytest.mark.asyncio
    async def test_all_valid_message_types(self, mock_plugin_manager, minimal_valid_config):
        """Test all valid message types are accepted"""
        valid_types = [
            'text', 'position', 'nodeinfo', 'telemetry', 'routing', 'admin',
            'traceroute', 'neighborinfo', 'detection_sensor', 'reply', 'ip_tunnel',
            'paxcounter', 'serial', 'store_forward', 'range_test', 'private', 'atak'
        ]
        
        config = minimal_valid_config.copy()
        config['channels'] = [
            {
                'name': 'AllTypes',
                'message_types': valid_types
            }
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['channels'][0]['message_types'] == valid_types
    
    @pytest.mark.asyncio
    async def test_numeric_string_channel_name(self, mock_plugin_manager, minimal_valid_config):
        """Test channel name can be numeric string (e.g., '0' for primary channel)"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {'name': '0'}
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['channels'][0]['name'] == '0'
    
    @pytest.mark.asyncio
    async def test_special_characters_in_root_topic(self, mock_plugin_manager, minimal_valid_config):
        """Test root topic with valid special characters"""
        config = minimal_valid_config.copy()
        config['root_topic'] = 'msh/US-west/region_1'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['root_topic'] == 'msh/US-west/region_1'
    
    @pytest.mark.asyncio
    async def test_empty_username_and_password_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test empty username and password are valid (no auth)"""
        config = minimal_valid_config.copy()
        config['username'] = ''
        config['password'] = ''
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['username'] == ''
        assert plugin._config_cache['password'] == ''
    
    @pytest.mark.asyncio
    async def test_tls_disabled_with_empty_cert_paths(self, mock_plugin_manager, minimal_valid_config):
        """Test TLS disabled with empty certificate paths is valid"""
        config = minimal_valid_config.copy()
        config['tls_enabled'] = False
        config['ca_cert'] = ''
        config['client_cert'] = ''
        config['client_key'] = ''
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['tls_enabled'] is False
    
    @pytest.mark.asyncio
    async def test_queue_persist_false_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test queue_persist=False is valid (default)"""
        config = minimal_valid_config.copy()
        config['queue_persist'] = False
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['queue_persist'] is False
    
    @pytest.mark.asyncio
    async def test_reconnect_disabled_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test reconnect_enabled=False is valid"""
        config = minimal_valid_config.copy()
        config['reconnect_enabled'] = False
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['reconnect_enabled'] is False
    
    @pytest.mark.asyncio
    async def test_log_published_messages_false_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test log_published_messages=False is valid"""
        config = minimal_valid_config.copy()
        config['log_published_messages'] = False
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['log_published_messages'] is False
    
    @pytest.mark.asyncio
    async def test_encryption_enabled_with_json_format(self, mock_plugin_manager, minimal_valid_config):
        """Test encryption_enabled=True with json format is valid (edge case)"""
        config = minimal_valid_config.copy()
        config['encryption_enabled'] = True
        config['format'] = 'json'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['encryption_enabled'] is True
        assert plugin._config_cache['format'] == 'json'
    
    @pytest.mark.asyncio
    async def test_protobuf_format_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test protobuf format is valid"""
        config = minimal_valid_config.copy()
        config['format'] = 'protobuf'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['format'] == 'protobuf'
    
    @pytest.mark.asyncio
    async def test_max_reconnect_attempts_zero_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test max_reconnect_attempts=0 is valid (no retries)"""
        config = minimal_valid_config.copy()
        config['max_reconnect_attempts'] = 0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_reconnect_attempts'] == 0
    
    @pytest.mark.asyncio
    async def test_max_reconnect_attempts_positive_is_valid(self, mock_plugin_manager, minimal_valid_config):
        """Test max_reconnect_attempts with positive value is valid"""
        config = minimal_valid_config.copy()
        config['max_reconnect_attempts'] = 100
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_reconnect_attempts'] == 100
    
    @pytest.mark.asyncio
    async def test_float_values_converted_to_appropriate_types(self, mock_plugin_manager, minimal_valid_config):
        """Test float values are properly converted"""
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = 10.5  # Should be converted to int
        config['burst_multiplier'] = 2  # Should be converted to float
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['max_messages_per_second'] == 10  # Converted to int
        assert plugin._config_cache['burst_multiplier'] == 2.0  # Converted to float
    
    @pytest.mark.asyncio
    async def test_region_with_whitespace_is_trimmed(self, mock_plugin_manager, minimal_valid_config):
        """Test region with whitespace is trimmed"""
        config = minimal_valid_config.copy()
        config['region'] = '  EU  '
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['region'] == 'EU'
    
    @pytest.mark.asyncio
    async def test_root_topic_with_whitespace_is_trimmed(self, mock_plugin_manager, minimal_valid_config):
        """Test root_topic with whitespace is trimmed"""
        config = minimal_valid_config.copy()
        config['root_topic'] = '  msh/US  '
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is True
        assert plugin._config_cache['root_topic'] == 'msh/US'
    
    @pytest.mark.asyncio
    async def test_channel_name_with_whitespace_not_trimmed(self, mock_plugin_manager, minimal_valid_config):
        """Test channel name preserves whitespace (not trimmed)"""
        config = minimal_valid_config.copy()
        config['channels'] = [
            {'name': '  LongFast  '}
        ]
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        # Channel names are not trimmed - they're used as-is
        assert result is True
        assert plugin._config_cache['channels'][0]['name'] == '  LongFast  '
    
    @pytest.mark.asyncio
    async def test_none_values_for_optional_string_fields(self, mock_plugin_manager, minimal_valid_config):
        """Test None values for optional string fields fail validation"""
        config = minimal_valid_config.copy()
        config['username'] = None
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        # None should fail type validation (expecting string)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_negative_broker_port_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test negative broker port fails validation"""
        config = minimal_valid_config.copy()
        config['broker_port'] = -1
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_negative_queue_size_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test negative queue size fails validation"""
        config = minimal_valid_config.copy()
        config['queue_max_size'] = -100
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_negative_max_messages_per_second_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test negative max_messages_per_second fails validation"""
        config = minimal_valid_config.copy()
        config['max_messages_per_second'] = -5
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_zero_burst_multiplier_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test zero burst_multiplier fails validation"""
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = 0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_zero_reconnect_multiplier_fails(self, mock_plugin_manager, minimal_valid_config):
        """Test zero reconnect_multiplier fails validation"""
        config = minimal_valid_config.copy()
        config['reconnect_multiplier'] = 0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_nan_float_values_fail(self, mock_plugin_manager, minimal_valid_config):
        """Test NaN float values fail validation"""
        config = minimal_valid_config.copy()
        config['burst_multiplier'] = float('nan')
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        # NaN should fail validation (not in valid range)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_infinity_float_values_fail(self, mock_plugin_manager, minimal_valid_config):
        """Test infinity float values fail validation"""
        config = minimal_valid_config.copy()
        config['reconnect_max_delay'] = float('inf')
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        # Infinity should fail validation (exceeds max)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
