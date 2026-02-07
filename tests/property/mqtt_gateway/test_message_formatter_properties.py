"""
Property-based tests for MQTT Gateway Message Formatter

Tests universal properties of message formatting, topic path generation,
and message type filtering.

Properties tested:
- Property 1: Topic Path Format for Encrypted Messages (Requirements 3.1, 6.3)
- Property 2: Topic Path Format for JSON Messages (Requirements 3.2, 6.4)
- Property 3: Custom Root Topic Override (Requirements 3.5)
- Property 14: Message Type Filtering (Requirements 12.1, 12.2, 12.3)

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from pathlib import Path
import sys
import re

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from models.message import Message, MessageType
from mqtt_gateway.message_formatter import MessageFormatter

# Import Meshtastic protobuf definitions for testing
from meshtastic.protobuf import mqtt_pb2, mesh_pb2, portnums_pb2


# ============================================================================
# Hypothesis Strategies for Generating Test Data
# ============================================================================

@st.composite
def node_id_strategy(draw):
    """Generate valid Meshtastic node IDs"""
    # Node IDs are typically in format !xxxxxxxx (8 hex chars)
    hex_chars = draw(st.text(
        alphabet='0123456789abcdef',
        min_size=8,
        max_size=8
    ))
    return f"!{hex_chars}"


@st.composite
def region_strategy(draw):
    """Generate valid region codes"""
    # Common regions: US, EU, CN, JP, ANZ, KR, TW, RU, IN, NZ, TH, UA, etc.
    return draw(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        min_size=2,
        max_size=3
    ))


@st.composite
def root_topic_strategy(draw):
    """Generate valid custom root topics"""
    # Root topics can be paths like "msh/US", "custom/mesh", "my/custom/root"
    # Generate 1-4 path segments
    num_segments = draw(st.integers(min_value=1, max_value=4))
    segments = []
    for _ in range(num_segments):
        segment = draw(st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-',
            min_size=1,
            max_size=10
        ))
        segments.append(segment)
    return '/'.join(segments)


@st.composite
def message_strategy(draw):
    """Generate valid Message objects"""
    return Message(
        sender_id=draw(node_id_strategy()),
        channel=draw(st.integers(min_value=0, max_value=255)),
        content=draw(st.text(min_size=0, max_size=200)),
        message_type=draw(st.sampled_from(list(MessageType)))
    )


@st.composite
def message_with_signal_quality_strategy(draw):
    """Generate valid Message objects with signal quality data"""
    return Message(
        sender_id=draw(node_id_strategy()),
        channel=draw(st.integers(min_value=0, max_value=255)),
        content=draw(st.text(min_size=0, max_size=200)),
        message_type=draw(st.sampled_from(list(MessageType))),
        snr=draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False)),
        rssi=draw(st.floats(min_value=-120.0, max_value=-20.0, allow_nan=False, allow_infinity=False))
    )


@st.composite
def channel_config_strategy(draw):
    """Generate valid channel configuration"""
    # Generate a list of message types to allow (or empty for all)
    all_types = ['text', 'position', 'nodeinfo', 'telemetry', 'routing', 
                 'admin', 'range_test', 'detection_sensor', 'reply']
    
    # Randomly choose to have a filter or not
    has_filter = draw(st.booleans())
    
    if has_filter:
        # Choose a subset of message types
        num_types = draw(st.integers(min_value=0, max_value=len(all_types)))
        if num_types == 0:
            message_types = []
        else:
            message_types = draw(st.lists(
                st.sampled_from(all_types),
                min_size=num_types,
                max_size=num_types,
                unique=True
            ))
    else:
        message_types = []
    
    return {
        'name': str(draw(st.integers(min_value=0, max_value=255))),
        'uplink_enabled': draw(st.booleans()),
        'message_types': message_types
    }


# ============================================================================
# Property 1: Topic Path Format for Encrypted Messages
# ============================================================================

class TestEncryptedTopicPathProperty:
    """
    **Feature: mqtt-gateway, Property 1: Topic Path Format for Encrypted Messages**
    
    For any Meshtastic message with encryption enabled, the generated MQTT topic
    path should match the format msh/{region}/2/e/{channel}/{nodeId} where region,
    channel, and nodeId are extracted from the message and configuration.
    
    **Validates: Requirements 3.1, 6.3**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_encrypted_topic_path_format(self, message, region):
        """
        Property: Encrypted topic paths follow the correct format
        
        For any message and region, when encryption is enabled, the topic
        should be: msh/{region}/2/e/{channel}/{nodeId}
        """
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message, encrypted=True)
        
        # Parse the topic path
        parts = topic.split('/')
        
        # Verify structure: should have exactly 6 parts
        # Format is: msh/{region}/2/e/{channel}/{nodeId}
        assert len(parts) == 6, \
            f"Topic should have 6 parts, got {len(parts)}: {topic}"
        
        # Verify each part
        assert parts[0] == 'msh', \
            f"First part should be 'msh', got '{parts[0]}'"
        assert parts[1] == region, \
            f"Second part should be region '{region}', got '{parts[1]}'"
        assert parts[2] == '2', \
            f"Third part should be protocol version '2', got '{parts[2]}'"
        assert parts[3] == 'e', \
            f"Fourth part should be format 'e' (encrypted), got '{parts[3]}'"
        assert parts[4] == str(message.channel), \
            f"Fifth part should be channel '{message.channel}', got '{parts[4]}'"
        assert parts[5] == message.sender_id, \
            f"Sixth part should be sender_id '{message.sender_id}', got '{parts[5]}'"
        
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_encrypted_topic_path_complete_format(self, message, region):
        """
        Property: Encrypted topic paths include all required components
        
        The complete format should be: msh/{region}/2/e/{channel}/{nodeId}
        """
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message, encrypted=True)
        
        # Expected format: msh/{region}/2/e/{channel}/{nodeId}
        expected_pattern = f"^msh/{re.escape(region)}/2/e/{message.channel}/{re.escape(message.sender_id)}$"
        
        assert re.match(expected_pattern, topic), \
            f"Topic '{topic}' doesn't match expected pattern '{expected_pattern}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_encrypted_override_parameter(self, message, region):
        """
        Property: Encrypted parameter overrides config setting
        
        When encrypted=True is passed, the topic should use 'e' format
        regardless of config encryption_enabled setting.
        """
        # Config says encryption disabled
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # But we override with encrypted=True
        topic = formatter.get_topic_path(message, encrypted=True)
        
        # Should still use 'e' format
        parts = topic.split('/')
        assert parts[3] == 'e', \
            f"Topic should use 'e' format when encrypted=True, got '{parts[3]}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_encrypted_topic_uses_config_default(self, message, region):
        """
        Property: When no override, topic uses config encryption setting
        
        When encrypted parameter is None, the topic format should match
        the config encryption_enabled setting.
        """
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Don't pass encrypted parameter (uses config default)
        topic = formatter.get_topic_path(message)
        
        # Should use 'e' format from config
        parts = topic.split('/')
        assert parts[3] == 'e', \
            f"Topic should use 'e' format from config, got '{parts[3]}'"


# ============================================================================
# Property 2: Topic Path Format for JSON Messages
# ============================================================================

class TestJSONTopicPathProperty:
    """
    **Feature: mqtt-gateway, Property 2: Topic Path Format for JSON Messages**
    
    For any Meshtastic message with JSON format enabled, the generated MQTT topic
    path should match the format msh/{region}/2/json/{channel}/{nodeId} where
    region, channel, and nodeId are extracted from the message and configuration.
    
    **Validates: Requirements 3.2, 6.4**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_topic_path_format(self, message, region):
        """
        Property: JSON topic paths follow the correct format
        
        For any message and region, when encryption is disabled, the topic
        should be: msh/{region}/2/json/{channel}/{nodeId}
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message, encrypted=False)
        
        # Expected format: msh/{region}/2/json/{channel}/{nodeId}
        expected_pattern = f"^msh/{re.escape(region)}/2/json/{message.channel}/{re.escape(message.sender_id)}$"
        
        assert re.match(expected_pattern, topic), \
            f"Topic '{topic}' doesn't match expected pattern '{expected_pattern}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_topic_path_components(self, message, region):
        """
        Property: JSON topic paths contain all required components
        
        The topic should have all 6 components in the correct order.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message, encrypted=False)
        
        # Parse the topic path
        parts = topic.split('/')
        
        # Verify structure: should have exactly 6 parts
        assert len(parts) == 6, \
            f"Topic should have 6 parts, got {len(parts)}: {topic}"
        
        # Verify each part
        assert parts[0] == 'msh', \
            f"First part should be 'msh', got '{parts[0]}'"
        assert parts[1] == region, \
            f"Second part should be region '{region}', got '{parts[1]}'"
        assert parts[2] == '2', \
            f"Third part should be protocol version '2', got '{parts[2]}'"
        assert parts[3] == 'json', \
            f"Fourth part should be format 'json', got '{parts[3]}'"
        assert parts[4] == str(message.channel), \
            f"Fifth part should be channel '{message.channel}', got '{parts[4]}'"
        assert parts[5] == message.sender_id, \
            f"Sixth part should be sender_id '{message.sender_id}', got '{parts[5]}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_override_parameter(self, message, region):
        """
        Property: JSON format used when encrypted=False
        
        When encrypted=False is passed, the topic should use 'json' format
        regardless of config encryption_enabled setting.
        """
        # Config says encryption enabled
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # But we override with encrypted=False
        topic = formatter.get_topic_path(message, encrypted=False)
        
        # Should use 'json' format
        parts = topic.split('/')
        assert parts[3] == 'json', \
            f"Topic should use 'json' format when encrypted=False, got '{parts[3]}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_topic_uses_config_default(self, message, region):
        """
        Property: When no override, topic uses config encryption setting
        
        When encrypted parameter is None and config has encryption_enabled=False,
        the topic should use 'json' format.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Don't pass encrypted parameter (uses config default)
        topic = formatter.get_topic_path(message)
        
        # Should use 'json' format from config
        parts = topic.split('/')
        assert parts[3] == 'json', \
            f"Topic should use 'json' format from config, got '{parts[3]}'"


# ============================================================================
# Property 3: Custom Root Topic Override
# ============================================================================

class TestCustomRootTopicProperty:
    """
    **Feature: mqtt-gateway, Property 3: Custom Root Topic Override**
    
    For any configured root topic value, all generated MQTT topic paths should
    start with the configured root topic instead of the default "msh/{region}".
    
    **Validates: Requirements 3.5**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        root_topic=root_topic_strategy(),
        encrypted=st.booleans()
    )
    def test_custom_root_topic_overrides_default(self, message, region, root_topic, encrypted):
        """
        Property: Custom root topic replaces default msh/{region}
        
        When root_topic is configured, it should be used instead of the
        default "msh/{region}" prefix.
        """
        config = {
            'region': region,
            'root_topic': root_topic,
            'encryption_enabled': encrypted,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message)
        
        # Topic should start with custom root topic
        assert topic.startswith(root_topic), \
            f"Topic '{topic}' should start with custom root '{root_topic}'"
        
        # Topic should NOT start with default msh/{region}
        default_root = f"msh/{region}"
        assert not topic.startswith(default_root), \
            f"Topic '{topic}' should not start with default root '{default_root}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        root_topic=root_topic_strategy(),
        encrypted=st.booleans()
    )
    def test_custom_root_topic_complete_format(self, message, region, root_topic, encrypted):
        """
        Property: Custom root topic maintains correct overall format
        
        With custom root topic, the format should be:
        {root_topic}/2/{format}/{channel}/{nodeId}
        """
        config = {
            'region': region,
            'root_topic': root_topic,
            'encryption_enabled': encrypted,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message)
        
        # Determine expected format string
        format_str = 'e' if encrypted else 'json'
        
        # Expected pattern: {root_topic}/2/{format}/{channel}/{nodeId}
        expected_pattern = f"^{re.escape(root_topic)}/2/{format_str}/{message.channel}/{re.escape(message.sender_id)}$"
        
        assert re.match(expected_pattern, topic), \
            f"Topic '{topic}' doesn't match expected pattern '{expected_pattern}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_no_custom_root_uses_default(self, message, region):
        """
        Property: Without custom root topic, default msh/{region} is used
        
        When root_topic is not configured (None), the default "msh/{region}"
        should be used.
        """
        config = {
            'region': region,
            'root_topic': None,  # No custom root
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message)
        
        # Topic should start with default msh/{region}
        default_root = f"msh/{region}"
        assert topic.startswith(default_root), \
            f"Topic '{topic}' should start with default root '{default_root}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        root_topic=root_topic_strategy()
    )
    def test_custom_root_topic_with_both_formats(self, message, region, root_topic):
        """
        Property: Custom root topic works with both encrypted and JSON formats
        
        The custom root topic should work correctly with both 'e' and 'json' formats.
        """
        config = {
            'region': region,
            'root_topic': root_topic,
            'encryption_enabled': False,  # Default to JSON
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Test with encrypted format
        topic_encrypted = formatter.get_topic_path(message, encrypted=True)
        assert topic_encrypted.startswith(root_topic), \
            f"Encrypted topic should start with custom root"
        assert '/e/' in topic_encrypted, \
            f"Encrypted topic should contain '/e/'"
        
        # Test with JSON format
        topic_json = formatter.get_topic_path(message, encrypted=False)
        assert topic_json.startswith(root_topic), \
            f"JSON topic should start with custom root"
        assert '/json/' in topic_json, \
            f"JSON topic should contain '/json/'"


# ============================================================================
# Property 14: Message Type Filtering
# ============================================================================

class TestMessageTypeFilteringProperty:
    """
    **Feature: mqtt-gateway, Property 14: Message Type Filtering**
    
    For any message with a specific message type, the message should be forwarded
    to MQTT if and only if either no message type filter is configured or the
    message type is included in the configured filter list.
    
    **Validates: Requirements 12.1, 12.2, 12.3**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_no_filter_allows_all_messages(self, message, region):
        """
        Property: Without filter configuration, all messages are allowed
        
        When no channel configuration exists, all message types should be
        forwarded (should_forward_message returns True).
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []  # No channel configuration
        }
        formatter = MessageFormatter(config)
        
        result = formatter.should_forward_message(message)
        
        assert result is True, \
            f"Message type {message.message_type.value} should be allowed when no filter configured"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_empty_filter_allows_all_messages(self, message, region):
        """
        Property: Empty filter list allows all messages
        
        When a channel has an empty message_types list, all message types
        should be forwarded.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,
                    'message_types': []  # Empty filter
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        result = formatter.should_forward_message(message)
        
        assert result is True, \
            f"Message type {message.message_type.value} should be allowed with empty filter"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        allowed_types=st.lists(
            st.sampled_from(['text', 'position', 'nodeinfo', 'telemetry', 'routing']),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    def test_filter_allows_only_specified_types(self, message, region, allowed_types):
        """
        Property: Filter allows only specified message types
        
        When a channel has a message_types filter, only messages with types
        in that list should be forwarded.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,
                    'message_types': allowed_types
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        result = formatter.should_forward_message(message)
        
        # Check if message type is in allowed list (case-insensitive)
        message_type_lower = message.message_type.value.lower()
        should_be_allowed = message_type_lower in allowed_types
        
        assert result == should_be_allowed, \
            f"Message type {message.message_type.value} should be " \
            f"{'allowed' if should_be_allowed else 'blocked'} with filter {allowed_types}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_filter_is_case_insensitive(self, message, region):
        """
        Property: Message type filtering is case-insensitive
        
        The filter should match message types regardless of case.
        """
        # Use uppercase in filter
        message_type_upper = message.message_type.value.upper()
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,
                    'message_types': [message_type_upper]  # Uppercase
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        result = formatter.should_forward_message(message)
        
        # Should be allowed despite case difference
        assert result is True, \
            f"Message type {message.message_type.value} should match filter {message_type_upper} (case-insensitive)"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        channel_configs=st.lists(channel_config_strategy(), min_size=1, max_size=5)
    )
    def test_different_channels_different_filters(self, message, region, channel_configs):
        """
        Property: Different channels can have different filters
        
        Each channel's filter should be independent and only apply to
        messages on that channel.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': channel_configs
        }
        formatter = MessageFormatter(config)
        
        result = formatter.should_forward_message(message)
        
        # Find the LAST config for this message's channel (dict behavior)
        # The formatter builds a dict, so the last config wins
        channel_str = str(message.channel)
        matching_config = None
        for ch_config in channel_configs:
            if ch_config['name'] == channel_str:
                matching_config = ch_config  # Keep updating to get the last one
        
        if matching_config is None:
            # No config for this channel - should allow all
            assert result is True, \
                f"Message should be allowed when channel {message.channel} has no config"
        else:
            # Check against the channel's filter
            allowed_types = matching_config['message_types']
            if not allowed_types:
                # Empty filter - allow all
                assert result is True, \
                    f"Message should be allowed with empty filter"
            else:
                # Check if message type is in filter
                message_type_lower = message.message_type.value.lower()
                should_be_allowed = message_type_lower in allowed_types
                assert result == should_be_allowed, \
                    f"Message type {message.message_type.value} filtering incorrect for channel {message.channel}"
    
    @given(
        channel=st.integers(min_value=0, max_value=255),
        region=region_strategy(),
        message_type=st.sampled_from(list(MessageType))
    )
    def test_filter_consistency_across_messages(self, channel, region, message_type):
        """
        Property: Filter decision is consistent for same message type
        
        Multiple messages of the same type on the same channel should all
        get the same filtering decision.
        """
        # Create a filter that includes some types but not others
        allowed_types = ['text', 'position']
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(channel),
                    'uplink_enabled': True,
                    'message_types': allowed_types
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Create multiple messages with same type
        message1 = Message(
            sender_id='!aaaaaaaa',
            channel=channel,
            message_type=message_type
        )
        message2 = Message(
            sender_id='!bbbbbbbb',
            channel=channel,
            message_type=message_type
        )
        
        result1 = formatter.should_forward_message(message1)
        result2 = formatter.should_forward_message(message2)
        
        # Results should be identical
        assert result1 == result2, \
            f"Filtering decision should be consistent for message type {message_type.value}"


# ============================================================================
# Property 6: Channel Uplink Filtering
# ============================================================================

class TestChannelUplinkFilteringProperty:
    """
    **Feature: mqtt-gateway, Property 6: Channel Uplink Filtering**
    
    For any message from a channel, the message should be forwarded to MQTT
    if and only if uplink is enabled for that channel in the configuration.
    
    **Validates: Requirements 4.2, 4.3**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_uplink_disabled_blocks_messages(self, message, region):
        """
        Property: Messages from channels with uplink disabled are blocked
        
        When uplink_enabled is False for a channel, is_uplink_enabled should
        return False and messages should not be forwarded.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': False,  # Uplink disabled
                    'message_types': []
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Check uplink status
        uplink_enabled = formatter.is_uplink_enabled(message.channel)
        
        assert uplink_enabled is False, \
            f"Uplink should be disabled for channel {message.channel}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_uplink_enabled_allows_messages(self, message, region):
        """
        Property: Messages from channels with uplink enabled are allowed
        
        When uplink_enabled is True for a channel, is_uplink_enabled should
        return True (subject to message type filtering).
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,  # Uplink enabled
                    'message_types': []  # No type filtering
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Check uplink status
        uplink_enabled = formatter.is_uplink_enabled(message.channel)
        
        assert uplink_enabled is True, \
            f"Uplink should be enabled for channel {message.channel}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_no_channel_config_defaults_to_disabled(self, message, region):
        """
        Property: Channels without configuration default to uplink disabled
        
        When no configuration exists for a channel, uplink should be disabled
        by default for security/privacy.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []  # No channel configurations
        }
        formatter = MessageFormatter(config)
        
        # Check uplink status for unconfigured channel
        uplink_enabled = formatter.is_uplink_enabled(message.channel)
        
        assert uplink_enabled is False, \
            f"Uplink should be disabled by default for unconfigured channel {message.channel}"
    
    @given(
        channel=st.integers(min_value=0, max_value=255),
        region=region_strategy(),
        uplink_enabled=st.booleans()
    )
    def test_uplink_setting_is_consistent(self, channel, region, uplink_enabled):
        """
        Property: Uplink setting is consistent across multiple checks
        
        Multiple calls to is_uplink_enabled for the same channel should
        return the same result.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(channel),
                    'uplink_enabled': uplink_enabled,
                    'message_types': []
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Check multiple times
        result1 = formatter.is_uplink_enabled(channel)
        result2 = formatter.is_uplink_enabled(channel)
        result3 = formatter.is_uplink_enabled(channel)
        
        # All results should be identical
        assert result1 == result2 == result3 == uplink_enabled, \
            f"Uplink status should be consistent across multiple checks"
    
    @given(
        region=region_strategy(),
        channel_configs=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=255),  # channel number
                st.booleans()  # uplink_enabled
            ),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique channel numbers
        )
    )
    def test_different_channels_independent_uplink_settings(self, region, channel_configs):
        """
        Property: Different channels have independent uplink settings
        
        Each channel's uplink setting should be independent and not affect
        other channels.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(channel),
                    'uplink_enabled': uplink,
                    'message_types': []
                }
                for channel, uplink in channel_configs
            ]
        }
        formatter = MessageFormatter(config)
        
        # Check each channel has its configured uplink setting
        for channel, expected_uplink in channel_configs:
            actual_uplink = formatter.is_uplink_enabled(channel)
            assert actual_uplink == expected_uplink, \
                f"Channel {channel} should have uplink_enabled={expected_uplink}, got {actual_uplink}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_uplink_and_message_type_filtering_combined(self, message, region):
        """
        Property: Uplink and message type filtering work together
        
        Both uplink_enabled and message_types filter must pass for a message
        to be forwarded. If uplink is disabled, message type doesn't matter.
        """
        # Test 1: Uplink disabled, message type allowed
        config1 = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': False,  # Disabled
                    'message_types': [message.message_type.value.lower()]  # Type allowed
                }
            ]
        }
        formatter1 = MessageFormatter(config1)
        
        uplink1 = formatter1.is_uplink_enabled(message.channel)
        assert uplink1 is False, \
            f"Uplink should be disabled even if message type is allowed"
        
        # Test 2: Uplink enabled, message type allowed
        config2 = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,  # Enabled
                    'message_types': [message.message_type.value.lower()]  # Type allowed
                }
            ]
        }
        formatter2 = MessageFormatter(config2)
        
        uplink2 = formatter2.is_uplink_enabled(message.channel)
        type_allowed2 = formatter2.should_forward_message(message)
        assert uplink2 is True, \
            f"Uplink should be enabled"
        assert type_allowed2 is True, \
            f"Message type should be allowed"
        
        # Test 3: Uplink enabled, message type blocked
        config3 = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,  # Enabled
                    'message_types': ['nonexistent_type']  # Type blocked
                }
            ]
        }
        formatter3 = MessageFormatter(config3)
        
        uplink3 = formatter3.is_uplink_enabled(message.channel)
        type_allowed3 = formatter3.should_forward_message(message)
        assert uplink3 is True, \
            f"Uplink should be enabled"
        assert type_allowed3 is False, \
            f"Message type should be blocked"
    
    @given(
        channel=st.integers(min_value=0, max_value=255),
        region=region_strategy()
    )
    def test_channel_number_as_string_or_int(self, channel, region):
        """
        Property: Channel numbers work as both strings and integers
        
        The is_uplink_enabled method should work correctly whether the
        channel is passed as an integer or string.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(channel),  # Stored as string
                    'uplink_enabled': True,
                    'message_types': []
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Check with integer
        result_int = formatter.is_uplink_enabled(channel)
        
        # Check with string
        result_str = formatter.is_uplink_enabled(str(channel))
        
        # Both should return True
        assert result_int is True, \
            f"Should work with integer channel number"
        assert result_str is True, \
            f"Should work with string channel number"
        assert result_int == result_str, \
            f"Results should be identical for int and string channel numbers"


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestMessageFormatterPropertyEdgeCases:
    """Test edge cases that combine multiple properties"""
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        root_topic=root_topic_strategy()
    )
    def test_custom_root_with_filtering(self, message, region, root_topic):
        """
        Edge case: Custom root topic works with message filtering
        
        Custom root topic and message filtering should work together correctly.
        """
        config = {
            'region': region,
            'root_topic': root_topic,
            'encryption_enabled': False,
            'channels': [
                {
                    'name': str(message.channel),
                    'uplink_enabled': True,
                    'message_types': ['text', 'position']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Get topic (should use custom root)
        topic = formatter.get_topic_path(message)
        assert topic.startswith(root_topic), \
            f"Topic should use custom root even with filtering configured"
        
        # Check filtering (should work independently)
        should_forward = formatter.should_forward_message(message)
        message_type_lower = message.message_type.value.lower()
        expected = message_type_lower in ['text', 'position']
        assert should_forward == expected, \
            f"Filtering should work correctly with custom root topic"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_empty_sender_id_in_topic(self, message, region):
        """
        Edge case: Empty sender ID should still generate valid topic
        
        Even with empty sender_id, the topic structure should be maintained.
        """
        # Force empty sender_id
        message.sender_id = ''
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        topic = formatter.get_topic_path(message)
        
        # Should still have correct structure (ending with empty string)
        parts = topic.split('/')
        assert len(parts) == 6, \
            f"Topic should have 6 parts even with empty sender_id"
        assert parts[5] == '', \
            f"Last part should be empty string for empty sender_id"


# ============================================================================
# Property 4: Protobuf ServiceEnvelope Wrapping
# ============================================================================

class TestProtobufServiceEnvelopeProperty:
    """
    **Feature: mqtt-gateway, Property 4: Protobuf ServiceEnvelope Wrapping**
    
    For any message formatted as protobuf, the output should be a valid
    ServiceEnvelope structure that can be deserialized using Meshtastic
    protobuf definitions.
    
    **Validates: Requirements 3.3, 5.1**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_output_is_valid_service_envelope(self, message, region):
        """
        Property: Protobuf output can be deserialized as ServiceEnvelope
        
        For any message, the protobuf output should be valid ServiceEnvelope
        that can be deserialized without errors.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Should be bytes
        assert isinstance(protobuf_bytes, bytes), \
            f"Protobuf output should be bytes, got {type(protobuf_bytes)}"
        
        # Should be non-empty
        assert len(protobuf_bytes) > 0, \
            f"Protobuf output should not be empty"
        
        # Should deserialize as ServiceEnvelope
        envelope = mqtt_pb2.ServiceEnvelope()
        try:
            envelope.ParseFromString(protobuf_bytes)
        except Exception as e:
            pytest.fail(f"Failed to deserialize ServiceEnvelope: {e}")
        
        # Envelope should have a packet
        assert envelope.HasField('packet'), \
            f"ServiceEnvelope should have a packet field"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_contains_mesh_packet(self, message, region):
        """
        Property: ServiceEnvelope contains valid MeshPacket
        
        The ServiceEnvelope should contain a MeshPacket with routing information.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Check packet fields
        packet = envelope.packet
        
        # Should have from field (sender)
        # Note: 'from' is a Python keyword, so we use getattr
        from_node = getattr(packet, 'from')
        assert from_node != 0 or message.sender_id == '' or message.sender_id == '!00000000', \
            f"Packet should have from field set (unless sender_id is empty/zero)"
        
        # Should have channel
        assert packet.channel == message.channel, \
            f"Packet channel should match message channel"
        
        # Should have hop_limit
        assert packet.hop_limit > 0, \
            f"Packet should have positive hop_limit"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_preserves_sender_id(self, message, region):
        """
        Property: Protobuf preserves sender node ID
        
        The sender node ID should be preserved in the MeshPacket.
        """
        # Skip if sender_id is empty or invalid
        assume(message.sender_id and message.sender_id.startswith('!'))
        assume(len(message.sender_id) > 1)
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Convert sender_id to int for comparison
        expected_from = formatter._node_id_to_int(message.sender_id)
        
        # Note: 'from' is a Python keyword, so we use getattr
        from_node = getattr(packet, 'from')
        assert from_node == expected_from, \
            f"Packet from field should match sender_id: {from_node} != {expected_from}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_preserves_channel(self, message, region):
        """
        Property: Protobuf preserves channel number
        
        The channel number should be preserved in both the MeshPacket
        and the ServiceEnvelope.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Check packet channel
        assert envelope.packet.channel == message.channel, \
            f"Packet channel should match message channel"
        
        # Check envelope channel_id (it's a string field)
        assert envelope.channel_id == str(message.channel), \
            f"Envelope channel_id should match message channel"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_contains_payload(self, message, region):
        """
        Property: Protobuf contains message payload
        
        The MeshPacket should contain either encrypted or decoded payload.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have either encrypted or decoded field
        has_encrypted = packet.HasField('encrypted') or len(packet.encrypted) > 0
        has_decoded = packet.HasField('decoded')
        
        assert has_encrypted or has_decoded, \
            f"Packet should have either encrypted or decoded payload"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_unencrypted_has_decoded_data(self, message, region):
        """
        Property: Unencrypted messages have decoded Data field
        
        When encryption is disabled, the packet should have a decoded
        Data field with the message content.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have decoded field
        assert packet.HasField('decoded'), \
            f"Unencrypted packet should have decoded field"
        
        # Decoded should be Data protobuf
        data = packet.decoded
        
        # Should have portnum (may be 0 for UNKNOWN type)
        assert data.portnum >= 0, \
            f"Data should have valid portnum (>= 0)"
        
        # Should have payload
        assert len(data.payload) > 0 or message.content == '', \
            f"Data should have payload (unless message content is empty)"
    
    @given(
        message=message_with_signal_quality_strategy(),
        region=region_strategy()
    )
    def test_protobuf_preserves_signal_quality(self, message, region):
        """
        Property: Protobuf preserves signal quality (SNR/RSSI)
        
        If the message has SNR or RSSI, it should be preserved in the packet.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Check SNR if present
        if message.snr is not None:
            assert abs(packet.rx_snr - message.snr) < 0.01, \
                f"Packet rx_snr should match message SNR"
        
        # Check RSSI if present
        if message.rssi is not None:
            assert abs(packet.rx_rssi - int(message.rssi)) <= 1, \
                f"Packet rx_rssi should match message RSSI (within 1 due to int conversion)"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_protobuf_has_gateway_id(self, message, region):
        """
        Property: ServiceEnvelope has gateway_id
        
        The ServiceEnvelope should have a gateway_id field set.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Should have gateway_id
        assert len(envelope.gateway_id) > 0, \
            f"ServiceEnvelope should have gateway_id set"


# ============================================================================
# Property 10: Encrypted Payload Pass-Through
# ============================================================================

class TestEncryptedPayloadPassThroughProperty:
    """
    **Feature: mqtt-gateway, Property 10: Encrypted Payload Pass-Through**
    
    For any message with encryption enabled, the encrypted payload bytes should
    be forwarded to MQTT without modification or decryption attempts.
    
    **Validates: Requirements 6.1**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        encrypted_payload=st.binary(min_size=1, max_size=256)
    )
    def test_encrypted_payload_preserved(self, message, region, encrypted_payload):
        """
        Property: Encrypted payload is preserved without modification
        
        When a message has an encrypted payload in metadata and encryption
        is enabled, the payload should be passed through unchanged.
        """
        # Add encrypted payload to message metadata
        message.metadata['encrypted_payload'] = encrypted_payload
        
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have encrypted field
        assert packet.HasField('encrypted') or len(packet.encrypted) > 0, \
            f"Packet should have encrypted field when encryption enabled"
        
        # Encrypted payload should match original
        assert packet.encrypted == encrypted_payload, \
            f"Encrypted payload should be preserved unchanged"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        encrypted_payload=st.binary(min_size=1, max_size=256)
    )
    def test_encrypted_payload_not_decrypted(self, message, region, encrypted_payload):
        """
        Property: Encrypted payload is not decrypted
        
        When encryption is enabled and encrypted payload is present,
        the packet should NOT have a decoded field.
        """
        # Add encrypted payload to message metadata
        message.metadata['encrypted_payload'] = encrypted_payload
        
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have encrypted field
        assert len(packet.encrypted) > 0, \
            f"Packet should have encrypted payload"
        
        # Should NOT have decoded field (no decryption attempted)
        # Note: In protobuf3, HasField may not work for all field types
        # We check if decoded is empty/default instead
        if packet.HasField('decoded'):
            # If decoded exists, it should be empty/default
            assert len(packet.decoded.payload) == 0, \
                f"Packet should not have decoded payload when encrypted"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_encrypted_mode_without_payload_creates_empty_encrypted(self, message, region):
        """
        Property: Encryption mode without encrypted payload creates empty encrypted field
        
        When encryption is enabled but no encrypted payload is in metadata,
        an empty encrypted field should be created (indicating encryption
        is expected but data is not available).
        """
        # Ensure no encrypted payload in metadata
        if 'encrypted_payload' in message.metadata:
            del message.metadata['encrypted_payload']
        
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have encrypted field (even if empty)
        assert packet.encrypted == b'', \
            f"Packet should have empty encrypted field when no payload available"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        encrypted_payload=st.binary(min_size=1, max_size=256)
    )
    def test_encrypted_payload_byte_for_byte_identical(self, message, region, encrypted_payload):
        """
        Property: Encrypted payload is byte-for-byte identical
        
        The encrypted payload in the packet should be exactly the same
        as the input, with no transformations, encoding, or modifications.
        """
        # Add encrypted payload to message metadata
        message.metadata['encrypted_payload'] = encrypted_payload
        
        config = {
            'region': region,
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Byte-for-byte comparison
        assert packet.encrypted == encrypted_payload, \
            f"Encrypted payload must be byte-for-byte identical"
        
        # Length should match exactly
        assert len(packet.encrypted) == len(encrypted_payload), \
            f"Encrypted payload length must match exactly"
    
    @given(
        message=message_strategy(),
        region=region_strategy(),
        encrypted_payload=st.binary(min_size=1, max_size=256)
    )
    def test_unencrypted_mode_ignores_encrypted_payload(self, message, region, encrypted_payload):
        """
        Property: Unencrypted mode ignores encrypted payload in metadata
        
        When encryption is disabled, even if encrypted payload exists in
        metadata, it should be ignored and the message should be decoded.
        """
        # Add encrypted payload to message metadata
        message.metadata['encrypted_payload'] = encrypted_payload
        
        config = {
            'region': region,
            'encryption_enabled': False,  # Encryption disabled
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have decoded field (not encrypted)
        assert packet.HasField('decoded'), \
            f"Packet should have decoded field when encryption disabled"
        
        # Encrypted field should be empty or not set
        assert len(packet.encrypted) == 0, \
            f"Packet should not have encrypted payload when encryption disabled"


# ============================================================================
# Property 5: JSON Schema Compliance
# ============================================================================

class TestJSONSchemaComplianceProperty:
    """
    **Feature: mqtt-gateway, Property 5: JSON Schema Compliance**
    
    For any message formatted as JSON, the output should be valid JSON containing
    all required Meshtastic fields (sender, timestamp, channel, payload) according
    to the Meshtastic JSON schema.
    
    **Validates: Requirements 3.4, 5.2**
    """
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_output_is_valid_json(self, message, region):
        """
        Property: JSON output is valid JSON that can be parsed
        
        For any message, the JSON output should be valid JSON that can
        be parsed without errors.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Should be a string
        assert isinstance(json_str, str), \
            f"JSON output should be string, got {type(json_str)}"
        
        # Should be non-empty
        assert len(json_str) > 0, \
            f"JSON output should not be empty"
        
        # Should parse as valid JSON
        import json
        try:
            json_obj = json.loads(json_str)
        except json.JSONDecodeError as e:
            pytest.fail(f"Failed to parse JSON: {e}")
        
        # Should be a dictionary
        assert isinstance(json_obj, dict), \
            f"Parsed JSON should be a dictionary, got {type(json_obj)}"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_contains_required_fields(self, message, region):
        """
        Property: JSON contains all required Meshtastic fields
        
        The JSON output should contain: sender, timestamp, channel, type, payload
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Check required fields
        required_fields = ['sender', 'timestamp', 'channel', 'type', 'payload']
        
        for field in required_fields:
            assert field in json_obj, \
                f"JSON should contain required field '{field}'"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_sender_matches_message(self, message, region):
        """
        Property: JSON sender field matches message sender_id
        
        The sender field in JSON should match the message sender_id.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        assert json_obj['sender'] == message.sender_id, \
            f"JSON sender should match message sender_id"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_timestamp_is_unix_epoch(self, message, region):
        """
        Property: JSON timestamp is Unix epoch seconds
        
        The timestamp field should be an integer representing Unix epoch seconds.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Should be an integer
        assert isinstance(json_obj['timestamp'], int), \
            f"Timestamp should be integer, got {type(json_obj['timestamp'])}"
        
        # Should match message timestamp
        expected_timestamp = int(message.timestamp.timestamp())
        assert json_obj['timestamp'] == expected_timestamp, \
            f"Timestamp should match message timestamp"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_channel_matches_message(self, message, region):
        """
        Property: JSON channel field matches message channel
        
        The channel field in JSON should match the message channel number.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        assert json_obj['channel'] == message.channel, \
            f"JSON channel should match message channel"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_type_is_lowercase(self, message, region):
        """
        Property: JSON type field is lowercase message type
        
        The type field should be the lowercase version of the message type.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Should be lowercase
        assert json_obj['type'] == message.message_type.value.lower(), \
            f"JSON type should be lowercase message type"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_payload_matches_content(self, message, region):
        """
        Property: JSON payload field matches message content
        
        The payload field should contain the message content.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        assert json_obj['payload'] == message.content, \
            f"JSON payload should match message content"
    
    @given(
        message=message_with_signal_quality_strategy(),
        region=region_strategy()
    )
    def test_json_preserves_signal_quality(self, message, region):
        """
        Property: JSON preserves signal quality (SNR/RSSI)
        
        If the message has SNR or RSSI, it should be included in the JSON.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Check SNR if present
        if message.snr is not None:
            assert 'snr' in json_obj, \
                f"JSON should contain SNR field when message has SNR"
            assert abs(json_obj['snr'] - message.snr) < 0.01, \
                f"JSON SNR should match message SNR"
        
        # Check RSSI if present
        if message.rssi is not None:
            assert 'rssi' in json_obj, \
                f"JSON should contain RSSI field when message has RSSI"
            assert abs(json_obj['rssi'] - message.rssi) < 0.01, \
                f"JSON RSSI should match message RSSI"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_includes_recipient_if_not_broadcast(self, message, region):
        """
        Property: JSON includes recipient for direct messages
        
        If the message has a specific recipient (not broadcast), the JSON
        should include a 'to' field.
        """
        # Set a specific recipient (not broadcast)
        message.recipient_id = '!deadbeef'
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Should have 'to' field
        assert 'to' in json_obj, \
            f"JSON should contain 'to' field for direct messages"
        assert json_obj['to'] == message.recipient_id, \
            f"JSON 'to' field should match recipient_id"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_omits_recipient_for_broadcast(self, message, region):
        """
        Property: JSON omits recipient for broadcast messages
        
        If the message is broadcast (no recipient or ^all), the JSON
        should not include a 'to' field or it should be omitted.
        """
        # Set broadcast recipient
        message.recipient_id = None
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # 'to' field should not be present for broadcast
        # (or if present, should not be set to a specific node)
        if 'to' in json_obj:
            # If present, should be None or empty
            assert json_obj['to'] is None or json_obj['to'] == '', \
                f"JSON 'to' field should be None/empty for broadcast"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_json_schema_consistency(self, message, region):
        """
        Property: JSON schema is consistent across multiple calls
        
        Formatting the same message multiple times should produce
        identical JSON output.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Format twice
        json_str1 = formatter.format_json(message)
        json_str2 = formatter.format_json(message)
        
        # Should be identical
        assert json_str1 == json_str2, \
            f"JSON output should be consistent across multiple calls"


# ============================================================================
# Property 7: Message Metadata Preservation
# ============================================================================

class TestMessageMetadataPreservationProperty:
    """
    **Feature: mqtt-gateway, Property 7: Message Metadata Preservation**
    
    For any message forwarded to MQTT, the serialized output should contain
    the original sender Node_ID, timestamp, and signal quality (SNR/RSSI)
    from the source message.
    
    **Validates: Requirements 4.4**
    """
    
    @given(
        message=message_with_signal_quality_strategy(),
        region=region_strategy()
    )
    def test_json_preserves_all_metadata(self, message, region):
        """
        Property: JSON format preserves all message metadata
        
        For any message with metadata (sender, timestamp, SNR, RSSI),
        the JSON output should contain all of these fields.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Check sender is preserved
        assert 'sender' in json_obj, \
            f"JSON should preserve sender metadata"
        assert json_obj['sender'] == message.sender_id, \
            f"Sender should match original message"
        
        # Check timestamp is preserved
        assert 'timestamp' in json_obj, \
            f"JSON should preserve timestamp metadata"
        assert json_obj['timestamp'] == int(message.timestamp.timestamp()), \
            f"Timestamp should match original message"
        
        # Check SNR is preserved (if present)
        if message.snr is not None:
            assert 'snr' in json_obj, \
                f"JSON should preserve SNR metadata"
            assert abs(json_obj['snr'] - message.snr) < 0.01, \
                f"SNR should match original message"
        
        # Check RSSI is preserved (if present)
        if message.rssi is not None:
            assert 'rssi' in json_obj, \
                f"JSON should preserve RSSI metadata"
            assert abs(json_obj['rssi'] - message.rssi) < 0.01, \
                f"RSSI should match original message"
    
    @given(
        message=message_with_signal_quality_strategy(),
        region=region_strategy()
    )
    def test_protobuf_preserves_all_metadata(self, message, region):
        """
        Property: Protobuf format preserves all message metadata
        
        For any message with metadata (sender, timestamp, SNR, RSSI),
        the protobuf output should contain all of these fields.
        """
        # Skip if sender_id is empty or invalid
        assume(message.sender_id and message.sender_id.startswith('!'))
        assume(len(message.sender_id) > 1)
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Check sender is preserved
        expected_from = formatter._node_id_to_int(message.sender_id)
        from_node = getattr(packet, 'from')
        assert from_node == expected_from, \
            f"Protobuf should preserve sender metadata"
        
        # Check timestamp is preserved
        assert packet.rx_time == int(message.timestamp.timestamp()), \
            f"Protobuf should preserve timestamp metadata"
        
        # Check SNR is preserved
        if message.snr is not None:
            assert abs(packet.rx_snr - message.snr) < 0.01, \
                f"Protobuf should preserve SNR metadata"
        
        # Check RSSI is preserved
        if message.rssi is not None:
            assert abs(packet.rx_rssi - int(message.rssi)) <= 1, \
                f"Protobuf should preserve RSSI metadata"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_metadata_preserved_without_signal_quality(self, message, region):
        """
        Property: Metadata preserved even without signal quality
        
        Even if SNR/RSSI are not present, sender and timestamp should
        still be preserved.
        """
        # Ensure no signal quality
        message.snr = None
        message.rssi = None
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        json_str = formatter.format_json(message)
        
        import json
        json_obj = json.loads(json_str)
        
        # Check sender is preserved
        assert 'sender' in json_obj, \
            f"JSON should preserve sender even without signal quality"
        assert json_obj['sender'] == message.sender_id, \
            f"Sender should match original message"
        
        # Check timestamp is preserved
        assert 'timestamp' in json_obj, \
            f"JSON should preserve timestamp even without signal quality"
        assert json_obj['timestamp'] == int(message.timestamp.timestamp()), \
            f"Timestamp should match original message"
    
    @given(
        message=message_with_signal_quality_strategy(),
        region=region_strategy()
    )
    def test_metadata_preservation_across_formats(self, message, region):
        """
        Property: Metadata preserved consistently across JSON and protobuf
        
        Both JSON and protobuf formats should preserve the same metadata
        from the original message.
        """
        # Skip if sender_id is empty or invalid
        assume(message.sender_id and message.sender_id.startswith('!'))
        assume(len(message.sender_id) > 1)
        
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Format as JSON
        json_str = formatter.format_json(message)
        import json
        json_obj = json.loads(json_str)
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        packet = envelope.packet
        
        # Compare sender
        expected_from = formatter._node_id_to_int(message.sender_id)
        from_node = getattr(packet, 'from')
        assert json_obj['sender'] == message.sender_id, \
            f"JSON sender should match message"
        assert from_node == expected_from, \
            f"Protobuf sender should match message"
        
        # Compare timestamp
        expected_timestamp = int(message.timestamp.timestamp())
        assert json_obj['timestamp'] == expected_timestamp, \
            f"JSON timestamp should match message"
        assert packet.rx_time == expected_timestamp, \
            f"Protobuf timestamp should match message"
        
        # Compare SNR (if present)
        if message.snr is not None:
            assert 'snr' in json_obj, \
                f"JSON should have SNR"
            assert abs(json_obj['snr'] - message.snr) < 0.01, \
                f"JSON SNR should match message"
            assert abs(packet.rx_snr - message.snr) < 0.01, \
                f"Protobuf SNR should match message"
        
        # Compare RSSI (if present)
        if message.rssi is not None:
            assert 'rssi' in json_obj, \
                f"JSON should have RSSI"
            assert abs(json_obj['rssi'] - message.rssi) < 0.01, \
                f"JSON RSSI should match message"
            assert abs(packet.rx_rssi - int(message.rssi)) <= 1, \
                f"Protobuf RSSI should match message"
    
    @given(
        message=message_strategy(),
        region=region_strategy()
    )
    def test_metadata_not_modified_during_formatting(self, message, region):
        """
        Property: Metadata is not modified during formatting
        
        The formatting process should not alter the original message metadata.
        """
        config = {
            'region': region,
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Store original values
        original_sender = message.sender_id
        original_timestamp = message.timestamp
        original_snr = message.snr
        original_rssi = message.rssi
        
        # Format the message
        json_str = formatter.format_json(message)
        
        # Check original values are unchanged
        assert message.sender_id == original_sender, \
            f"Sender should not be modified during formatting"
        assert message.timestamp == original_timestamp, \
            f"Timestamp should not be modified during formatting"
        assert message.snr == original_snr, \
            f"SNR should not be modified during formatting"
        assert message.rssi == original_rssi, \
            f"RSSI should not be modified during formatting"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
