"""
Property-Based Tests for MQTT Gateway Configuration Validation

Tests Property 13: Configuration Validation
Validates: Requirements 9.2, 9.3

**Validates: Requirements 9.2, 9.3**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from unittest.mock import Mock

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.plugin import MQTTGatewayPlugin


# Strategy builders for generating test data

@composite
def valid_broker_address(draw):
    """Generate valid broker addresses"""
    # Valid hostnames or IP addresses
    return draw(st.one_of(
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters='.-'
        )).filter(lambda x: x and x.strip() and not x.startswith('.') and not x.endswith('.')),
        st.from_regex(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', fullmatch=True)
    ))


@composite
def valid_port(draw):
    """Generate valid port numbers"""
    return draw(st.integers(min_value=1, max_value=65535))


@composite
def valid_region(draw):
    """Generate valid region codes"""
    return draw(st.text(min_size=2, max_size=10, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd')
    )))


@composite
def valid_root_topic(draw):
    """Generate valid root topics (no MQTT wildcards)"""
    # Generate topic without + or # characters
    return draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'),
        whitelist_characters='/-_'
    )).filter(lambda x: x and x.strip() and '+' not in x and '#' not in x))


@composite
def valid_message_type(draw):
    """Generate valid message types"""
    valid_types = [
        'text', 'position', 'nodeinfo', 'telemetry', 'routing', 'admin',
        'traceroute', 'neighborinfo', 'detection_sensor', 'reply', 'ip_tunnel',
        'paxcounter', 'serial', 'store_forward', 'range_test', 'private', 'atak'
    ]
    return draw(st.sampled_from(valid_types))


@composite
def valid_channel_config(draw):
    """Generate valid channel configuration"""
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd')
    )))
    uplink_enabled = draw(st.booleans())
    message_types = draw(st.lists(valid_message_type(), max_size=5, unique=True))
    
    return {
        'name': name,
        'uplink_enabled': uplink_enabled,
        'message_types': message_types
    }


@composite
def valid_mqtt_config(draw):
    """Generate valid MQTT gateway configuration"""
    # For property tests, disable TLS to avoid file loading issues
    # TLS configuration validation is tested separately in unit tests
    return {
        'enabled': True,
        'broker_address': draw(valid_broker_address()),
        'broker_port': draw(valid_port()),
        'username': draw(st.text(max_size=50)),
        'password': draw(st.text(max_size=50)),
        'tls_enabled': False,  # Disable TLS to avoid certificate file loading
        'ca_cert': '',
        'client_cert': '',
        'client_key': '',
        'root_topic': draw(valid_root_topic()),
        'region': draw(valid_region()),
        'format': draw(st.sampled_from(['json', 'protobuf'])),
        'encryption_enabled': draw(st.booleans()),
        'max_messages_per_second': draw(st.integers(min_value=1, max_value=1000)),
        'burst_multiplier': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
        'queue_max_size': draw(st.integers(min_value=10, max_value=100000)),
        'queue_persist': draw(st.booleans()),
        'reconnect_enabled': draw(st.booleans()),
        'reconnect_initial_delay': draw(st.floats(min_value=0.1, max_value=60.0, allow_nan=False, allow_infinity=False)),
        'reconnect_max_delay': draw(st.floats(min_value=1.0, max_value=3600.0, allow_nan=False, allow_infinity=False)),
        'reconnect_multiplier': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
        'max_reconnect_attempts': draw(st.integers(min_value=-1, max_value=1000)),
        'log_level': draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])),
        'log_published_messages': draw(st.booleans()),
        'channels': draw(st.lists(valid_channel_config(), max_size=3))
    }


@composite
def minimal_valid_config(draw):
    """Generate minimal valid configuration (only required fields)"""
    return {
        'enabled': True,
        'broker_address': draw(valid_broker_address())
    }


# Property Tests

class TestConfigurationValidationProperty:
    """
    Feature: mqtt-gateway, Property 13: Configuration Validation
    
    Tests that configuration validation correctly accepts valid configurations
    and rejects invalid ones with descriptive error messages.
    
    **Validates: Requirements 9.2, 9.3**
    """
    
    @settings(max_examples=100, deadline=None)
    @given(config=valid_mqtt_config())
    @pytest.mark.asyncio
    async def test_valid_config_passes_validation(self, config):
        """
        Property: For any valid configuration with all parameters within valid ranges,
        validation should succeed and the plugin should initialize.
        
        **Validates: Requirements 9.2, 9.3**
        """
        # Ensure reconnect_max_delay >= reconnect_initial_delay
        if config['reconnect_max_delay'] < config['reconnect_initial_delay']:
            config['reconnect_max_delay'] = config['reconnect_initial_delay']
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with valid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should succeed
        result = await plugin.initialize()
        
        assert result is True, "Valid configuration should pass validation"
        assert plugin.initialized is True, "Plugin should be initialized"
        assert plugin.enabled is True, "Plugin should be enabled"
        
        # Verify all config values are cached correctly
        assert plugin._config_cache['broker_address'] == config['broker_address']
        assert plugin._config_cache['broker_port'] == config['broker_port']
        assert plugin._config_cache['format'] == config['format']
        assert plugin._config_cache['region'] == config['region']
    
    @settings(max_examples=100, deadline=None)
    @given(config=minimal_valid_config())
    @pytest.mark.asyncio
    async def test_minimal_config_applies_defaults(self, config):
        """
        Property: For any minimal valid configuration (only required fields),
        validation should succeed and sensible defaults should be applied.
        
        **Validates: Requirements 9.2, 9.3**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should succeed
        result = await plugin.initialize()
        
        assert result is True, "Minimal valid configuration should pass validation"
        assert plugin.initialized is True, "Plugin should be initialized"
        
        # Verify defaults are applied
        assert plugin._config_cache['broker_port'] == 1883, "Default port should be 1883"
        assert plugin._config_cache['format'] == 'json', "Default format should be json"
        assert plugin._config_cache['encryption_enabled'] is False, "Default encryption should be False"
        assert plugin._config_cache['max_messages_per_second'] == 10, "Default rate limit should be 10"
        assert plugin._config_cache['queue_max_size'] == 1000, "Default queue size should be 1000"
        assert plugin._config_cache['reconnect_enabled'] is True, "Default reconnect should be True"
        assert plugin._config_cache['channels'] == [], "Default channels should be empty list"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_port=st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=65536)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_port_fails_validation(self, base_config, invalid_port):
        """
        Property: For any configuration with an invalid port number (< 1 or > 65535),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['broker_port'] = invalid_port
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid port {invalid_port} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(base_config=valid_mqtt_config())
    @pytest.mark.asyncio
    async def test_empty_broker_address_fails_validation(self, base_config):
        """
        Property: For any configuration with an empty broker address,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['broker_address'] = ''
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, "Empty broker address should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_format=st.text(min_size=1, max_size=20).filter(lambda x: x not in ['json', 'protobuf'])
    )
    @pytest.mark.asyncio
    async def test_invalid_format_fails_validation(self, base_config, invalid_format):
        """
        Property: For any configuration with an invalid format (not 'json' or 'protobuf'),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['format'] = invalid_format
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid format '{invalid_format}' should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_rate=st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=1001)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_rate_limit_fails_validation(self, base_config, invalid_rate):
        """
        Property: For any configuration with an invalid rate limit (< 1 or > 1000),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['max_messages_per_second'] = invalid_rate
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid rate limit {invalid_rate} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_queue_size=st.one_of(
            st.integers(max_value=9),
            st.integers(min_value=100001)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_queue_size_fails_validation(self, base_config, invalid_queue_size):
        """
        Property: For any configuration with an invalid queue size (< 10 or > 100000),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['queue_max_size'] = invalid_queue_size
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid queue size {invalid_queue_size} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(base_config=valid_mqtt_config())
    @pytest.mark.asyncio
    async def test_root_topic_with_wildcards_fails_validation(self, base_config):
        """
        Property: For any configuration with a root topic containing MQTT wildcards (+ or #),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        # Test with + wildcard
        config = base_config.copy()
        config['root_topic'] = 'msh/+/test'
        
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False, "Root topic with + wildcard should fail validation"
        
        # Test with # wildcard
        config['root_topic'] = 'msh/#'
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        result = await plugin.initialize()
        
        assert result is False, "Root topic with # wildcard should fail validation"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_region=st.one_of(
            st.text(max_size=1),  # Too short
            st.text(min_size=11, max_size=20)  # Too long
        ).filter(lambda x: len(x.strip()) != 0)  # Not empty after strip
    )
    @pytest.mark.asyncio
    async def test_invalid_region_length_fails_validation(self, base_config, invalid_region):
        """
        Property: For any configuration with a region code that is too short (< 2 chars)
        or too long (> 10 chars), validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['region'] = invalid_region
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid region length '{invalid_region}' (len={len(invalid_region.strip())}) should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        initial_delay=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        max_delay=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False)
    )
    @pytest.mark.asyncio
    async def test_reconnect_max_less_than_initial_fails_validation(self, base_config, initial_delay, max_delay):
        """
        Property: For any configuration where reconnect_max_delay < reconnect_initial_delay,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        assume(max_delay < initial_delay)  # Ensure max is less than initial
        
        config = base_config.copy()
        config['reconnect_initial_delay'] = initial_delay
        config['reconnect_max_delay'] = max_delay
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"reconnect_max_delay ({max_delay}) < reconnect_initial_delay ({initial_delay}) should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_log_level=st.text(min_size=1, max_size=20).filter(
            lambda x: x.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_log_level_fails_validation(self, base_config, invalid_log_level):
        """
        Property: For any configuration with an invalid log level,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['log_level'] = invalid_log_level
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid log level '{invalid_log_level}' should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(base_config=valid_mqtt_config())
    @pytest.mark.asyncio
    async def test_channel_without_name_fails_validation(self, base_config):
        """
        Property: For any configuration with a channel missing the required 'name' field,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['channels'] = [
            {
                'uplink_enabled': True,
                'message_types': ['text']
                # Missing 'name' field
            }
        ]
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, "Channel without name should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        invalid_message_type=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in [
                'text', 'position', 'nodeinfo', 'telemetry', 'routing', 'admin',
                'traceroute', 'neighborinfo', 'detection_sensor', 'reply', 'ip_tunnel',
                'paxcounter', 'serial', 'store_forward', 'range_test', 'private', 'atak'
            ]
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_message_type_fails_validation(self, base_config, invalid_message_type):
        """
        Property: For any configuration with an invalid message type in channel config,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        config = base_config.copy()
        config['channels'] = [
            {
                'name': 'TestChannel',
                'uplink_enabled': True,
                'message_types': [invalid_message_type]
            }
        ]
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid message type '{invalid_message_type}' should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        wrong_type_value=st.one_of(
            st.integers(),
            st.lists(st.text()),
            st.dictionaries(st.text(), st.text())
        )
    )
    @pytest.mark.asyncio
    async def test_wrong_type_for_string_field_fails_validation(self, base_config, wrong_type_value):
        """
        Property: For any configuration with a wrong type for a string field,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        assume(not isinstance(wrong_type_value, str))  # Ensure it's not a string
        
        config = base_config.copy()
        config['broker_address'] = wrong_type_value
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Wrong type {type(wrong_type_value).__name__} for broker_address should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=100, deadline=None)
    @given(
        base_config=valid_mqtt_config(),
        wrong_type_value=st.one_of(
            st.text(),
            st.lists(st.text()),
            st.dictionaries(st.text(), st.text())
        )
    )
    @pytest.mark.asyncio
    async def test_wrong_type_for_boolean_field_fails_validation(self, base_config, wrong_type_value):
        """
        Property: For any configuration with a wrong type for a boolean field,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 9.2, 9.3**
        """
        assume(not isinstance(wrong_type_value, bool))  # Ensure it's not a boolean
        
        config = base_config.copy()
        config['tls_enabled'] = wrong_type_value
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Wrong type {type(wrong_type_value).__name__} for tls_enabled should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
