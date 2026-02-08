"""
Property-Based Tests for Network Traceroute Mapper Configuration Validation

Tests Property 13: Configuration Validation with Random Parameters
Validates: Requirements 1.3, 3.5, 6.3

**Validates: Requirements 1.3, 3.5, 6.3**
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

from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    # Node IDs are in format !xxxxxxxx where x is hex digit
    hex_part = ''.join(draw(st.lists(
        st.sampled_from('0123456789abcdef'),
        min_size=8,
        max_size=8
    )))
    return f'!{hex_part}'


@composite
def valid_time_string(draw):
    """Generate valid time strings in HH:MM format"""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f'{hour:02d}:{minute:02d}'


@composite
def valid_timezone(draw):
    """Generate valid timezone strings"""
    return draw(st.sampled_from([
        'UTC', 'America/New_York', 'America/Los_Angeles', 'America/Chicago',
        'Europe/London', 'Europe/Paris', 'Asia/Tokyo', 'Australia/Sydney'
    ]))


@composite
def valid_role(draw):
    """Generate valid Meshtastic node roles"""
    return draw(st.sampled_from([
        'CLIENT', 'CLIENT_MUTE', 'ROUTER', 'ROUTER_CLIENT', 'REPEATER',
        'TRACKER', 'SENSOR', 'TAK', 'CLIENT_HIDDEN', 'LOST_AND_FOUND', 'TAK_TRACKER'
    ]))


@composite
def valid_quiet_hours_config(draw):
    """Generate valid quiet hours configuration"""
    return {
        'enabled': draw(st.booleans()),
        'start_time': draw(valid_time_string()),
        'end_time': draw(valid_time_string()),
        'timezone': draw(valid_timezone())
    }


@composite
def valid_congestion_config(draw):
    """Generate valid congestion detection configuration"""
    return {
        'enabled': draw(st.booleans()),
        'success_rate_threshold': draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        'throttle_multiplier': draw(st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False))
    }


@composite
def valid_emergency_stop_config(draw):
    """Generate valid emergency stop configuration"""
    return {
        'enabled': draw(st.booleans()),
        'failure_threshold': draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        'consecutive_failures': draw(st.integers(min_value=1, max_value=100)),
        'auto_recovery_minutes': draw(st.floats(min_value=1.0, max_value=1440.0, allow_nan=False, allow_infinity=False))
    }


@composite
def valid_traceroute_mapper_config(draw):
    """Generate valid traceroute mapper configuration"""
    return {
        'enabled': True,
        'traceroutes_per_minute': draw(st.floats(min_value=0, max_value=60, allow_nan=False, allow_infinity=False)),
        'burst_multiplier': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
        'queue_max_size': draw(st.integers(min_value=10, max_value=10000)),
        'queue_overflow_strategy': draw(st.sampled_from(['drop_lowest_priority', 'drop_oldest', 'drop_new'])),
        'clear_queue_on_startup': draw(st.booleans()),
        'recheck_interval_hours': draw(st.floats(min_value=0, max_value=168, allow_nan=False, allow_infinity=False)),
        'recheck_enabled': draw(st.booleans()),
        'max_hops': draw(st.integers(min_value=1, max_value=15)),
        'timeout_seconds': draw(st.floats(min_value=10, max_value=300, allow_nan=False, allow_infinity=False)),
        'max_retries': draw(st.integers(min_value=0, max_value=10)),
        'retry_backoff_multiplier': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
        'initial_discovery_enabled': draw(st.booleans()),
        'startup_delay_seconds': draw(st.floats(min_value=0, max_value=600, allow_nan=False, allow_infinity=False)),
        'skip_direct_nodes': draw(st.booleans()),
        'blacklist': draw(st.lists(valid_node_id(), max_size=10, unique=True)),
        'whitelist': draw(st.lists(valid_node_id(), max_size=10, unique=True)),
        'exclude_roles': draw(st.lists(valid_role(), max_size=5, unique=True)),
        'min_snr_threshold': draw(st.one_of(
            st.none(),
            st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)
        )),
        'quiet_hours': draw(valid_quiet_hours_config()),
        'congestion_detection': draw(valid_congestion_config()),
        'emergency_stop': draw(valid_emergency_stop_config()),
        'state_persistence_enabled': draw(st.booleans()),
        'state_file_path': draw(st.text(min_size=1, max_size=100)),
        'auto_save_interval_minutes': draw(st.floats(min_value=1, max_value=60, allow_nan=False, allow_infinity=False)),
        'history_per_node': draw(st.integers(min_value=1, max_value=100)),
        'forward_to_mqtt': draw(st.booleans()),
        'log_level': draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])),
        'log_traceroute_requests': draw(st.booleans()),
        'log_traceroute_responses': draw(st.booleans())
    }


@composite
def minimal_valid_config(draw):
    """Generate minimal valid configuration (only required fields)"""
    return {
        'enabled': True
    }


# Property Tests

class TestConfigurationValidationProperty:
    """
    Feature: network-traceroute-mapper, Property 13: Configuration Validation
    
    Tests that configuration validation correctly accepts valid configurations
    and rejects invalid ones with descriptive error messages.
    
    **Validates: Requirements 1.3, 3.5, 6.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(config=valid_traceroute_mapper_config())
    @pytest.mark.asyncio
    async def test_valid_config_passes_validation(self, config):
        """
        Property: For any valid configuration with all parameters within valid ranges,
        validation should succeed and the plugin should initialize.
        
        **Validates: Requirements 1.3**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with valid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should succeed
        result = await plugin.initialize()
        
        assert result is True, "Valid configuration should pass validation"
        assert plugin.initialized is True, "Plugin should be initialized"
        assert plugin.enabled is True, "Plugin should be enabled"
        
        # Verify all config values are cached correctly
        assert plugin._config_cache['traceroutes_per_minute'] == config['traceroutes_per_minute']
        assert plugin._config_cache['max_hops'] == config['max_hops']
        assert plugin._config_cache['queue_max_size'] == config['queue_max_size']
        assert plugin._config_cache['timeout_seconds'] == config['timeout_seconds']
    
    @settings(max_examples=20, deadline=None)
    @given(config=minimal_valid_config())
    @pytest.mark.asyncio
    async def test_minimal_config_applies_defaults(self, config):
        """
        Property: For any minimal valid configuration (only required fields),
        validation should succeed and sensible defaults should be applied.
        
        **Validates: Requirements 1.3, 3.3, 6.2, 10.2, 11.2**
        """
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with minimal config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should succeed
        result = await plugin.initialize()
        
        assert result is True, "Minimal valid configuration should pass validation"
        assert plugin.initialized is True, "Plugin should be initialized"
        
        # Verify defaults are applied (Requirements 3.3, 6.2, 10.2, 11.2, 11.5)
        assert plugin._config_cache['traceroutes_per_minute'] == 1, "Default rate should be 1 per minute"
        assert plugin._config_cache['max_hops'] == 7, "Default max hops should be 7"
        assert plugin._config_cache['queue_max_size'] == 500, "Default queue size should be 500"
        assert plugin._config_cache['timeout_seconds'] == 60, "Default timeout should be 60 seconds"
        assert plugin._config_cache['max_retries'] == 3, "Default max retries should be 3"
        assert plugin._config_cache['recheck_interval_hours'] == 6, "Default recheck interval should be 6 hours"
        assert plugin._config_cache['skip_direct_nodes'] is True, "Default skip_direct_nodes should be True"
        assert plugin._config_cache['blacklist'] == [], "Default blacklist should be empty"
        assert plugin._config_cache['whitelist'] == [], "Default whitelist should be empty"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_rate=st.one_of(
            st.floats(min_value=-100, max_value=-0.1, allow_nan=False, allow_infinity=False),
            st.floats(min_value=60.1, max_value=1000, allow_nan=False, allow_infinity=False)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_rate_limit_fails_validation(self, base_config, invalid_rate):
        """
        Property: For any configuration with an invalid rate limit (< 0 or > 60),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 3.5**
        """
        config = base_config.copy()
        config['traceroutes_per_minute'] = invalid_rate
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid rate limit {invalid_rate} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_hops=st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=16)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_max_hops_fails_validation(self, base_config, invalid_hops):
        """
        Property: For any configuration with invalid max_hops (< 1 or > 15),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 6.3**
        """
        config = base_config.copy()
        config['max_hops'] = invalid_hops
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid max_hops {invalid_hops} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_queue_size=st.one_of(
            st.integers(max_value=9),
            st.integers(min_value=10001)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_queue_size_fails_validation(self, base_config, invalid_queue_size):
        """
        Property: For any configuration with invalid queue_max_size (< 10 or > 10000),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 10.2**
        """
        config = base_config.copy()
        config['queue_max_size'] = invalid_queue_size
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid queue size {invalid_queue_size} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_timeout=st.one_of(
            st.floats(min_value=0.1, max_value=9.9, allow_nan=False, allow_infinity=False),
            st.floats(min_value=300.1, max_value=1000, allow_nan=False, allow_infinity=False)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_timeout_fails_validation(self, base_config, invalid_timeout):
        """
        Property: For any configuration with invalid timeout_seconds (< 10 or > 300),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 11.5**
        """
        config = base_config.copy()
        config['timeout_seconds'] = invalid_timeout
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid timeout {invalid_timeout} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_retries=st.one_of(
            st.integers(max_value=-1),
            st.integers(min_value=11)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_max_retries_fails_validation(self, base_config, invalid_retries):
        """
        Property: For any configuration with invalid max_retries (< 0 or > 10),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 11.2**
        """
        config = base_config.copy()
        config['max_retries'] = invalid_retries
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid max_retries {invalid_retries} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_strategy=st.text(min_size=1, max_size=30).filter(
            lambda x: x not in ['drop_lowest_priority', 'drop_oldest', 'drop_new']
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_overflow_strategy_fails_validation(self, base_config, invalid_strategy):
        """
        Property: For any configuration with invalid queue_overflow_strategy,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 10.5**
        """
        config = base_config.copy()
        config['queue_overflow_strategy'] = invalid_strategy
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid overflow strategy '{invalid_strategy}' should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_log_level=st.text(min_size=1, max_size=20).filter(
            lambda x: x.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_log_level_fails_validation(self, base_config, invalid_log_level):
        """
        Property: For any configuration with an invalid log level,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 1.3**
        """
        config = base_config.copy()
        config['log_level'] = invalid_log_level
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid log level '{invalid_log_level}' should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_threshold=st.one_of(
            st.floats(min_value=-1.0, max_value=-0.01, allow_nan=False, allow_infinity=False),
            st.floats(min_value=1.01, max_value=10.0, allow_nan=False, allow_infinity=False)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_success_rate_threshold_fails_validation(self, base_config, invalid_threshold):
        """
        Property: For any configuration with invalid success_rate_threshold (< 0.0 or > 1.0),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 12.2**
        """
        config = base_config.copy()
        config['congestion_detection'] = {
            'enabled': True,
            'success_rate_threshold': invalid_threshold,
            'throttle_multiplier': 0.5
        }
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid success_rate_threshold {invalid_threshold} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        invalid_multiplier=st.one_of(
            st.floats(min_value=0.01, max_value=0.09, allow_nan=False, allow_infinity=False),
            st.floats(min_value=1.01, max_value=10.0, allow_nan=False, allow_infinity=False)
        )
    )
    @pytest.mark.asyncio
    async def test_invalid_throttle_multiplier_fails_validation(self, base_config, invalid_multiplier):
        """
        Property: For any configuration with invalid throttle_multiplier (< 0.1 or > 1.0),
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 12.2**
        """
        config = base_config.copy()
        config['congestion_detection'] = {
            'enabled': True,
            'success_rate_threshold': 0.5,
            'throttle_multiplier': invalid_multiplier
        }
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Invalid throttle_multiplier {invalid_multiplier} should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        wrong_type_value=st.one_of(
            st.integers(),
            st.lists(st.text()),
            st.dictionaries(st.text(), st.text())
        )
    )
    @pytest.mark.asyncio
    async def test_wrong_type_for_boolean_field_fails_validation(self, base_config, wrong_type_value):
        """
        Property: For any configuration with a wrong type for a boolean field,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 1.3**
        """
        assume(not isinstance(wrong_type_value, bool))  # Ensure it's not a boolean
        
        config = base_config.copy()
        config['skip_direct_nodes'] = wrong_type_value
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Wrong type {type(wrong_type_value).__name__} for skip_direct_nodes should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(
        base_config=valid_traceroute_mapper_config(),
        wrong_type_value=st.one_of(
            st.text(),
            st.booleans(),
            st.dictionaries(st.text(), st.text())
        )
    )
    @pytest.mark.asyncio
    async def test_wrong_type_for_list_field_fails_validation(self, base_config, wrong_type_value):
        """
        Property: For any configuration with a wrong type for a list field,
        validation should fail with a descriptive error message.
        
        **Validates: Requirements 1.3**
        """
        assume(not isinstance(wrong_type_value, list))  # Ensure it's not a list
        
        config = base_config.copy()
        config['blacklist'] = wrong_type_value
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with invalid config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should fail
        result = await plugin.initialize()
        
        assert result is False, f"Wrong type {type(wrong_type_value).__name__} for blacklist should fail validation"
        assert plugin.initialized is False, "Plugin should not be initialized"
    
    @settings(max_examples=20, deadline=None)
    @given(base_config=valid_traceroute_mapper_config())
    @pytest.mark.asyncio
    async def test_rate_limit_zero_logs_warning(self, base_config):
        """
        Property: For any configuration with traceroutes_per_minute = 0,
        validation should succeed but log a warning that operations are disabled.
        
        **Validates: Requirements 3.4**
        """
        config = base_config.copy()
        config['traceroutes_per_minute'] = 0
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should succeed (rate of 0 is valid, just disables operations)
        result = await plugin.initialize()
        
        assert result is True, "Rate limit of 0 should pass validation (disables operations)"
        assert plugin._config_cache['traceroutes_per_minute'] == 0
    
    @settings(max_examples=20, deadline=None)
    @given(base_config=valid_traceroute_mapper_config())
    @pytest.mark.asyncio
    async def test_recheck_interval_zero_disables_rechecks(self, base_config):
        """
        Property: For any configuration with recheck_interval_hours = 0,
        validation should succeed and periodic rechecks should be disabled.
        
        **Validates: Requirements 5.5**
        """
        config = base_config.copy()
        config['recheck_interval_hours'] = 0
        
        # Create mock plugin manager
        mock_plugin_manager = Mock()
        mock_plugin_manager.config_manager = None
        
        # Create plugin with config
        plugin = TracerouteMapperPlugin("traceroute_mapper", config, mock_plugin_manager)
        
        # Initialize should succeed
        result = await plugin.initialize()
        
        assert result is True, "Recheck interval of 0 should pass validation (disables rechecks)"
        assert plugin._config_cache['recheck_interval_hours'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
