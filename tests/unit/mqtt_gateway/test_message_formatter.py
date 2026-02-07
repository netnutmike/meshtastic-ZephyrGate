"""
Unit tests for MessageFormatter class

Tests topic path generation, message type filtering, and channel configuration.

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add src directory to path
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


class TestMessageFormatterTopicGeneration:
    """Test topic path generation for different configurations"""
    
    def test_encrypted_topic_path_default_root(self):
        """Test encrypted topic path with default root (msh/{region})"""
        config = {
            'region': 'US',
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        topic = formatter.get_topic_path(message)
        
        assert topic == 'msh/US/2/e/0/!a1b2c3d4'
    
    def test_json_topic_path_default_root(self):
        """Test JSON topic path with default root (msh/{region})"""
        config = {
            'region': 'EU',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!deadbeef',
            channel=1,
            content='test',
            message_type=MessageType.POSITION
        )
        
        topic = formatter.get_topic_path(message)
        
        assert topic == 'msh/EU/2/json/1/!deadbeef'
    
    def test_custom_root_topic_encrypted(self):
        """Test custom root topic overrides default"""
        config = {
            'region': 'US',
            'root_topic': 'custom/mesh',
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!12345678',
            channel=2,
            content='test',
            message_type=MessageType.TELEMETRY
        )
        
        topic = formatter.get_topic_path(message)
        
        assert topic == 'custom/mesh/2/e/2/!12345678'
    
    def test_custom_root_topic_json(self):
        """Test custom root topic with JSON format"""
        config = {
            'region': 'US',
            'root_topic': 'my/custom/root',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!abcdef01',
            channel=0,
            content='test',
            message_type=MessageType.NODEINFO
        )
        
        topic = formatter.get_topic_path(message)
        
        assert topic == 'my/custom/root/2/json/0/!abcdef01'
    
    def test_encryption_override_parameter(self):
        """Test that encrypted parameter overrides config setting"""
        config = {
            'region': 'US',
            'encryption_enabled': False,  # Config says JSON
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        # Override to encrypted
        topic = formatter.get_topic_path(message, encrypted=True)
        assert topic == 'msh/US/2/e/0/!test1234'
        
        # Override to JSON
        topic = formatter.get_topic_path(message, encrypted=False)
        assert topic == 'msh/US/2/json/0/!test1234'
    
    def test_different_channels(self):
        """Test topic generation for different channel numbers"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        for channel_num in [0, 1, 5, 10, 255]:
            message = Message(
                sender_id='!test1234',
                channel=channel_num,
                content='test',
                message_type=MessageType.TEXT
            )
            
            topic = formatter.get_topic_path(message)
            assert topic == f'msh/US/2/json/{channel_num}/!test1234'
    
    def test_different_node_ids(self):
        """Test topic generation for different node IDs"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        node_ids = ['!a1b2c3d4', '!deadbeef', '!12345678', '!ffffffff']
        
        for node_id in node_ids:
            message = Message(
                sender_id=node_id,
                channel=0,
                content='test',
                message_type=MessageType.TEXT
            )
            
            topic = formatter.get_topic_path(message)
            assert topic == f'msh/US/2/json/0/{node_id}'


class TestMessageFormatterTypeFiltering:
    """Test message type filtering logic"""
    
    def test_no_filter_allows_all_messages(self):
        """Test that messages are allowed when no filter is configured"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []  # No channel configuration
        }
        formatter = MessageFormatter(config)
        
        # Test various message types
        for msg_type in [MessageType.TEXT, MessageType.POSITION, MessageType.TELEMETRY, MessageType.NODEINFO]:
            message = Message(
                sender_id='!test1234',
                channel=0,
                content='test',
                message_type=msg_type
            )
            
            assert formatter.should_forward_message(message) is True
    
    def test_empty_filter_list_allows_all_messages(self):
        """Test that empty message_types list allows all messages"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': []  # Empty filter
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        for msg_type in [MessageType.TEXT, MessageType.POSITION, MessageType.TELEMETRY]:
            message = Message(
                sender_id='!test1234',
                channel=0,
                content='test',
                message_type=msg_type
            )
            
            assert formatter.should_forward_message(message) is True
    
    def test_filter_allows_specified_types(self):
        """Test that filter allows only specified message types"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['text', 'position']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Allowed types
        text_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.TEXT)
        position_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.POSITION)
        
        assert formatter.should_forward_message(text_msg) is True
        assert formatter.should_forward_message(position_msg) is True
        
        # Disallowed types
        telemetry_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.TELEMETRY)
        nodeinfo_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.NODEINFO)
        
        assert formatter.should_forward_message(telemetry_msg) is False
        assert formatter.should_forward_message(nodeinfo_msg) is False
    
    def test_filter_case_insensitive(self):
        """Test that message type filtering is case-insensitive"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['TEXT', 'Position', 'TELEMETRY']  # Mixed case
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        text_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.TEXT)
        position_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.POSITION)
        telemetry_msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.TELEMETRY)
        
        assert formatter.should_forward_message(text_msg) is True
        assert formatter.should_forward_message(position_msg) is True
        assert formatter.should_forward_message(telemetry_msg) is True
    
    def test_different_channels_different_filters(self):
        """Test that different channels can have different filters"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['text']
                },
                {
                    'name': '1',
                    'uplink_enabled': True,
                    'message_types': ['position', 'telemetry']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Channel 0 - only text allowed
        text_ch0 = Message(sender_id='!test1234', channel=0, message_type=MessageType.TEXT)
        position_ch0 = Message(sender_id='!test1234', channel=0, message_type=MessageType.POSITION)
        
        assert formatter.should_forward_message(text_ch0) is True
        assert formatter.should_forward_message(position_ch0) is False
        
        # Channel 1 - position and telemetry allowed
        text_ch1 = Message(sender_id='!test1234', channel=1, message_type=MessageType.TEXT)
        position_ch1 = Message(sender_id='!test1234', channel=1, message_type=MessageType.POSITION)
        telemetry_ch1 = Message(sender_id='!test1234', channel=1, message_type=MessageType.TELEMETRY)
        
        assert formatter.should_forward_message(text_ch1) is False
        assert formatter.should_forward_message(position_ch1) is True
        assert formatter.should_forward_message(telemetry_ch1) is True


class TestMessageFormatterChannelConfig:
    """Test channel configuration methods"""
    
    def test_get_channel_config_exists(self):
        """Test getting configuration for existing channel"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['text']
                },
                {
                    'name': '1',
                    'uplink_enabled': False,
                    'message_types': ['position']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        ch0_config = formatter.get_channel_config(0)
        assert ch0_config is not None
        assert ch0_config['name'] == '0'
        assert ch0_config['uplink_enabled'] is True
        
        ch1_config = formatter.get_channel_config(1)
        assert ch1_config is not None
        assert ch1_config['name'] == '1'
        assert ch1_config['uplink_enabled'] is False
    
    def test_get_channel_config_not_exists(self):
        """Test getting configuration for non-existent channel"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['text']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        ch5_config = formatter.get_channel_config(5)
        assert ch5_config is None
    
    def test_is_uplink_enabled_true(self):
        """Test uplink enabled check returns True"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': True,
                    'message_types': ['text']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        assert formatter.is_uplink_enabled(0) is True
    
    def test_is_uplink_enabled_false(self):
        """Test uplink enabled check returns False"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': '0',
                    'uplink_enabled': False,
                    'message_types': ['text']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        assert formatter.is_uplink_enabled(0) is False
    
    def test_is_uplink_enabled_no_config(self):
        """Test uplink enabled defaults to False for unconfigured channel"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        assert formatter.is_uplink_enabled(0) is False
        assert formatter.is_uplink_enabled(5) is False
    
    def test_channel_name_as_string(self):
        """Test that channel names can be strings (like 'LongFast')"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': [
                {
                    'name': 'LongFast',
                    'uplink_enabled': True,
                    'message_types': ['text', 'position']
                }
            ]
        }
        formatter = MessageFormatter(config)
        
        # Note: Message.channel is an int, but config can have string names
        # The formatter should handle this by converting to string for comparison
        ch_config = formatter.get_channel_config(0)
        # This will return None because 'LongFast' != '0'
        assert ch_config is None
        
        # But if we search by the actual name in the config
        # Channel names are stored as-is in the filter map
        assert 'LongFast' in formatter._channel_filters
        # Message types are lowercased
        assert formatter._channel_filters['LongFast'] == ['text', 'position']


class TestMessageFormatterEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_config(self):
        """Test formatter with minimal/empty config"""
        config = {}
        formatter = MessageFormatter(config)
        
        # Should use defaults
        assert formatter.region == 'US'
        assert formatter.root_topic is None
        assert formatter.encryption_enabled is False
        assert formatter.channels == []
    
    def test_message_with_empty_sender_id(self):
        """Test topic generation with empty sender ID"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='',
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        topic = formatter.get_topic_path(message)
        assert topic == 'msh/US/2/json/0/'


class TestMessageFormatterProtobufSerialization:
    """
    Test protobuf serialization for specific message types.
    
    **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
    """
    
    def test_text_message_app_serialization(self):
        """
        Test TEXT_MESSAGE_APP protobuf serialization
        
        **Validates: Requirement 5.3**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='Hello, mesh!',
            message_type=MessageType.TEXT
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        assert envelope.HasField('packet')
        packet = envelope.packet
        
        # Check portnum is TEXT_MESSAGE_APP
        assert packet.HasField('decoded')
        data = packet.decoded
        assert data.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP
        
        # Check payload
        assert data.payload == b'Hello, mesh!'
    
    def test_telemetry_app_serialization(self):
        """
        Test TELEMETRY_APP protobuf serialization
        
        **Validates: Requirement 5.4**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!deadbeef',
            channel=0,
            content='{"battery": 3.7, "voltage": 4.2}',
            message_type=MessageType.TELEMETRY
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        assert packet.HasField('decoded')
        data = packet.decoded
        
        # Check portnum is TELEMETRY_APP
        assert data.portnum == portnums_pb2.PortNum.TELEMETRY_APP
        
        # Check payload contains telemetry data
        assert b'battery' in data.payload or b'voltage' in data.payload
    
    def test_nodeinfo_app_serialization(self):
        """
        Test NODEINFO_APP protobuf serialization
        
        **Validates: Requirement 5.5**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!12345678',
            channel=0,
            content='Node: TestNode',
            message_type=MessageType.NODEINFO
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        assert packet.HasField('decoded')
        data = packet.decoded
        
        # Check portnum is NODEINFO_APP
        assert data.portnum == portnums_pb2.PortNum.NODEINFO_APP
        
        # Check payload
        assert len(data.payload) > 0
    
    def test_position_app_serialization(self):
        """
        Test POSITION_APP protobuf serialization
        
        **Validates: Requirement 5.6**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!abcdef01',
            channel=0,
            content='{"lat": 47.6062, "lon": -122.3321}',
            message_type=MessageType.POSITION
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        assert packet.HasField('decoded')
        data = packet.decoded
        
        # Check portnum is POSITION_APP
        assert data.portnum == portnums_pb2.PortNum.POSITION_APP
        
        # Check payload contains position data
        assert len(data.payload) > 0
    
    def test_all_message_types_have_valid_portnums(self):
        """
        Test that all message types map to valid portnums
        
        **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Test all message types
        for msg_type in MessageType:
            message = Message(
                sender_id='!test1234',
                channel=0,
                content='test',
                message_type=msg_type
            )
            
            # Format as protobuf
            protobuf_bytes = formatter.format_protobuf(message)
            
            # Deserialize and verify
            envelope = mqtt_pb2.ServiceEnvelope()
            envelope.ParseFromString(protobuf_bytes)
            
            packet = envelope.packet
            assert packet.HasField('decoded'), \
                f"Message type {msg_type.value} should have decoded field"
            
            data = packet.decoded
            # Portnum should be >= 0 (0 is UNKNOWN_APP)
            assert data.portnum >= 0, \
                f"Message type {msg_type.value} should have valid portnum"
    
    def test_encrypted_message_serialization(self):
        """
        Test encrypted message serialization
        
        **Validates: Requirement 6.1**
        """
        config = {
            'region': 'US',
            'encryption_enabled': True,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        encrypted_payload = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='This should be encrypted',
            message_type=MessageType.TEXT,
            metadata={'encrypted_payload': encrypted_payload}
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Should have encrypted field
        assert len(packet.encrypted) > 0, \
            "Encrypted message should have encrypted field"
        
        # Encrypted payload should match
        assert packet.encrypted == encrypted_payload, \
            "Encrypted payload should be preserved"
        
        # Should NOT have decoded field
        if packet.HasField('decoded'):
            assert len(packet.decoded.payload) == 0, \
                "Encrypted message should not have decoded payload"
    
    def test_message_with_signal_quality(self):
        """
        Test message serialization with signal quality (SNR/RSSI)
        
        **Validates: Requirement 4.4**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='test',
            message_type=MessageType.TEXT,
            snr=5.5,
            rssi=-85.0
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Check SNR
        assert abs(packet.rx_snr - 5.5) < 0.01, \
            "SNR should be preserved"
        
        # Check RSSI (converted to int)
        assert packet.rx_rssi == -85, \
            "RSSI should be preserved"
    
    def test_message_with_recipient(self):
        """
        Test message serialization with specific recipient (not broadcast)
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            recipient_id='!deadbeef',
            channel=0,
            content='Direct message',
            message_type=MessageType.TEXT
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Check recipient
        expected_to = formatter._node_id_to_int('!deadbeef')
        assert packet.to == expected_to, \
            "Recipient should be set correctly"
        
        # Should not be broadcast address
        assert packet.to != 0xFFFFFFFF, \
            "Direct message should not use broadcast address"
    
    def test_broadcast_message(self):
        """
        Test broadcast message serialization
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            recipient_id=None,  # Broadcast
            channel=0,
            content='Broadcast message',
            message_type=MessageType.TEXT
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize and verify
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        
        # Check recipient is broadcast address
        assert packet.to == 0xFFFFFFFF, \
            "Broadcast message should use broadcast address"


class TestMessageFormatterJSONSerialization:
    """
    Test JSON serialization for various message types.
    
    **Validates: Requirements 3.4, 5.2, 4.4**
    """
    
    def test_json_text_message_serialization(self):
        """
        Test JSON serialization for TEXT message type
        
        **Validates: Requirement 5.3**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='Hello, mesh!',
            message_type=MessageType.TEXT
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify required fields
        assert json_obj['sender'] == '!a1b2c3d4'
        assert json_obj['type'] == 'text'
        assert json_obj['payload'] == 'Hello, mesh!'
        assert json_obj['channel'] == 0
        assert 'timestamp' in json_obj
    
    def test_json_position_message_serialization(self):
        """
        Test JSON serialization for POSITION message type
        
        **Validates: Requirement 5.6**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!deadbeef',
            channel=0,
            content='{"lat": 47.6062, "lon": -122.3321}',
            message_type=MessageType.POSITION
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify required fields
        assert json_obj['sender'] == '!deadbeef'
        assert json_obj['type'] == 'position'
        assert 'lat' in json_obj['payload'] or 'payload' in json_obj
        assert json_obj['channel'] == 0
    
    def test_json_telemetry_message_serialization(self):
        """
        Test JSON serialization for TELEMETRY message type
        
        **Validates: Requirement 5.4**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!12345678',
            channel=0,
            content='{"battery": 3.7, "voltage": 4.2}',
            message_type=MessageType.TELEMETRY
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify required fields
        assert json_obj['sender'] == '!12345678'
        assert json_obj['type'] == 'telemetry'
        assert json_obj['channel'] == 0
    
    def test_json_nodeinfo_message_serialization(self):
        """
        Test JSON serialization for NODEINFO message type
        
        **Validates: Requirement 5.5**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!abcdef01',
            channel=0,
            content='Node: TestNode',
            message_type=MessageType.NODEINFO
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify required fields
        assert json_obj['sender'] == '!abcdef01'
        assert json_obj['type'] == 'nodeinfo'
        assert json_obj['channel'] == 0
    
    def test_json_with_signal_quality(self):
        """
        Test JSON serialization includes signal quality (SNR/RSSI)
        
        **Validates: Requirement 4.4**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            channel=0,
            content='test',
            message_type=MessageType.TEXT,
            snr=5.5,
            rssi=-85.0
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify signal quality fields
        assert 'snr' in json_obj
        assert abs(json_obj['snr'] - 5.5) < 0.01
        assert 'rssi' in json_obj
        assert abs(json_obj['rssi'] - (-85.0)) < 0.01
    
    def test_json_with_recipient(self):
        """
        Test JSON serialization includes recipient for direct messages
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!a1b2c3d4',
            recipient_id='!deadbeef',
            channel=0,
            content='Direct message',
            message_type=MessageType.TEXT
        )
        
        # Format as JSON
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Verify recipient field
        assert 'to' in json_obj
        assert json_obj['to'] == '!deadbeef'


class TestMessageFormatterUnsupportedTypes:
    """
    Test handling of unsupported message types.
    
    **Validates: Requirement 5.7**
    """
    
    def test_unsupported_message_type_in_json(self):
        """
        Test that unsupported message types can still be serialized to JSON
        
        Even if a message type is not explicitly supported, it should still
        be serializable to JSON format with the type field set correctly.
        
        **Validates: Requirement 5.7**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Use a less common message type
        message = Message(
            sender_id='!test1234',
            channel=0,
            content='test content',
            message_type=MessageType.ROUTING  # Less common type
        )
        
        # Should not raise an error
        json_str = formatter.format_json(message)
        
        # Parse JSON
        import json
        json_obj = json.loads(json_str)
        
        # Should have all required fields
        assert json_obj['sender'] == '!test1234'
        assert json_obj['type'] == 'routing'
        assert json_obj['payload'] == 'test content'
    
    def test_all_message_types_serializable_to_json(self):
        """
        Test that all message types can be serialized to JSON
        
        Every message type in the MessageType enum should be serializable
        to JSON format without errors.
        
        **Validates: Requirement 5.7**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Test all message types
        for msg_type in MessageType:
            message = Message(
                sender_id='!test1234',
                channel=0,
                content='test',
                message_type=msg_type
            )
            
            # Should not raise an error
            json_str = formatter.format_json(message)
            
            # Parse JSON
            import json
            json_obj = json.loads(json_str)
            
            # Should have correct type
            assert json_obj['type'] == msg_type.value.lower(), \
                f"Message type {msg_type.value} should be serializable to JSON"
    
    def test_all_message_types_serializable_to_protobuf(self):
        """
        Test that all message types can be serialized to protobuf
        
        Every message type in the MessageType enum should be serializable
        to protobuf format without errors.
        
        **Validates: Requirement 5.7**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Test all message types
        for msg_type in MessageType:
            message = Message(
                sender_id='!test1234',
                channel=0,
                content='test',
                message_type=msg_type
            )
            
            # Should not raise an error
            protobuf_bytes = formatter.format_protobuf(message)
            
            # Should be valid protobuf
            envelope = mqtt_pb2.ServiceEnvelope()
            envelope.ParseFromString(protobuf_bytes)
            
            # Should have packet
            assert envelope.HasField('packet'), \
                f"Message type {msg_type.value} should be serializable to protobuf"
    
    def test_unknown_message_type_has_valid_portnum(self):
        """
        Test that UNKNOWN message type maps to UNKNOWN_APP portnum
        
        **Validates: Requirement 5.7**
        """
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel=0,
            content='test',
            message_type=MessageType.UNKNOWN
        )
        
        # Format as protobuf
        protobuf_bytes = formatter.format_protobuf(message)
        
        # Deserialize
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        packet = envelope.packet
        assert packet.HasField('decoded')
        
        # Should have UNKNOWN_APP portnum
        data = packet.decoded
        assert data.portnum == portnums_pb2.PortNum.UNKNOWN_APP, \
            f"UNKNOWN message type should map to UNKNOWN_APP portnum"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
