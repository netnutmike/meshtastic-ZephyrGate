"""
Message Formatter for MQTT Gateway

Formats Meshtastic messages according to the Meshtastic MQTT protocol.
Handles topic path generation and message type filtering.

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from models.message import Message, MessageType

# Import Meshtastic protobuf definitions
from meshtastic.protobuf import mqtt_pb2, mesh_pb2, portnums_pb2


class MessageFormatter:
    """
    Formats Meshtastic messages for MQTT publishing.
    
    Responsibilities:
    - Generate MQTT topic paths according to Meshtastic protocol
    - Support both encrypted and JSON topic formats
    - Handle custom root topic configuration
    - Filter messages by type
    
    Topic Path Formats:
    - Encrypted: msh/{region}/2/e/{channel}/{nodeId}
    - JSON:      msh/{region}/2/json/{channel}/{nodeId}
    - Custom:    {root_topic}/2/{format}/{channel}/{nodeId}
    
    Requirements: 3.1, 3.2, 3.5, 12.1, 12.2, 12.3
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """
        Initialize the message formatter.
        
        Args:
            config: Configuration dictionary containing:
                - region: Geographic region (e.g., "US", "EU")
                - root_topic: Custom root topic (optional, overrides default msh/{region})
                - encryption_enabled: Whether to use encrypted topic paths
                - channels: List of channel configurations with message_types filters
            logger: Logger instance (optional)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Extract configuration
        self.region = config.get('region', 'US')
        self.root_topic = config.get('root_topic', None)
        self.encryption_enabled = config.get('encryption_enabled', False)
        self.channels = config.get('channels', [])
        
        # Build channel filter map for quick lookups
        self._channel_filters = self._build_channel_filters()
        
        self.logger.info(f"MessageFormatter initialized: region={self.region}, "
                        f"root_topic={self.root_topic}, encryption={self.encryption_enabled}")
    
    def _build_channel_filters(self) -> Dict[str, List[str]]:
        """
        Build a map of channel names/numbers to allowed message types.
        
        Returns:
            Dictionary mapping channel identifiers to list of allowed message types
        """
        filters = {}
        
        for channel_config in self.channels:
            channel_name = str(channel_config.get('name', '0'))
            message_types = channel_config.get('message_types', [])
            
            # Convert message types to lowercase for case-insensitive matching
            filters[channel_name] = [mt.lower() for mt in message_types]
        
        return filters
    
    def get_topic_path(self, message: Message, encrypted: Optional[bool] = None) -> str:
        """
        Generate MQTT topic path for a message.
        
        Topic format:
        - Encrypted: {root}/2/e/{channel}/{nodeId}
        - JSON:      {root}/2/json/{channel}/{nodeId}
        
        Where root is either custom root_topic or default msh/{region}.
        
        Args:
            message: The message to generate topic for
            encrypted: Override encryption setting (None = use config default)
            
        Returns:
            MQTT topic path string
            
        Requirements: 3.1, 3.2, 3.5
        """
        # Determine encryption setting
        use_encryption = encrypted if encrypted is not None else self.encryption_enabled
        
        # Determine root topic
        if self.root_topic:
            # Custom root topic overrides default
            root = self.root_topic
        else:
            # Default: msh/{region}
            root = f"msh/{self.region}"
        
        # Protocol version (always 2 for current Meshtastic MQTT protocol)
        version = "2"
        
        # Format: "e" for encrypted, "json" for plaintext JSON
        format_str = "e" if use_encryption else "json"
        
        # Channel: use channel number from message
        channel = str(message.channel)
        
        # Node ID: sender's node ID
        node_id = message.sender_id
        
        # Construct topic path
        topic = f"{root}/{version}/{format_str}/{channel}/{node_id}"
        
        return topic
    
    def should_forward_message(self, message: Message) -> bool:
        """
        Determine if a message should be forwarded to MQTT based on type filtering.
        
        Checks if the message type is allowed for the message's channel according
        to the channel configuration. If no filter is configured for the channel,
        all message types are allowed.
        
        Args:
            message: The message to check
            
        Returns:
            True if message should be forwarded, False otherwise
            
        Requirements: 12.1, 12.2, 12.3
        """
        channel_name = str(message.channel)
        
        # Check if we have a filter for this channel
        if channel_name not in self._channel_filters:
            # No filter configured for this channel - allow all messages
            return True
        
        # Get allowed message types for this channel
        allowed_types = self._channel_filters[channel_name]
        
        # If filter list is empty, allow all messages
        if not allowed_types:
            return True
        
        # Check if message type is in allowed list
        message_type_str = message.message_type.value.lower()
        
        return message_type_str in allowed_types
    
    def get_channel_config(self, channel: int) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific channel.
        
        Args:
            channel: Channel number
            
        Returns:
            Channel configuration dictionary or None if not found
        """
        channel_str = str(channel)
        
        for channel_config in self.channels:
            if str(channel_config.get('name', '0')) == channel_str:
                return channel_config
        
        return None
    
    def is_uplink_enabled(self, channel: int) -> bool:
        """
        Check if uplink is enabled for a specific channel.
        
        Args:
            channel: Channel number
            
        Returns:
            True if uplink is enabled, False otherwise
        """
        channel_config = self.get_channel_config(channel)
        
        if channel_config is None:
            # No configuration for this channel - default to disabled
            return False
        
        return channel_config.get('uplink_enabled', False)
    
    def format_protobuf(self, message: Message) -> bytes:
        """
        Format message as protobuf ServiceEnvelope.
        
        Wraps the message in a ServiceEnvelope structure according to the
        Meshtastic MQTT protocol. The ServiceEnvelope contains:
        - packet: The MeshPacket with routing and payload information
        - channel_id: The channel identifier (as bytes)
        - gateway_id: The gateway node ID (as bytes)
        
        For encrypted messages, the payload is passed through without decryption.
        For unencrypted messages, the payload is serialized as Data protobuf.
        
        Handles serialization errors gracefully:
        - Invalid message data
        - Missing required fields
        - Protobuf serialization failures
        
        Args:
            message: The message to format
            
        Returns:
            Serialized protobuf bytes
            
        Raises:
            ValueError: If message cannot be serialized
            
        Requirements: 3.3, 5.1, 6.1, 8.4
        """
        try:
            # Validate message
            if not message:
                raise ValueError("Message cannot be None")
            
            if not message.sender_id:
                raise ValueError("Message must have a sender_id")
            
            # Create ServiceEnvelope
            envelope = mqtt_pb2.ServiceEnvelope()
            
            # Create MeshPacket
            packet = mesh_pb2.MeshPacket()
            
            # Set sender (from field in MeshPacket)
            # Node IDs in Meshtastic are typically in format !xxxxxxxx
            # We need to convert to integer for the protobuf
            # Note: 'from' is a Python keyword, so we use setattr
            try:
                sender_int = self._node_id_to_int(message.sender_id)
                setattr(packet, 'from', sender_int)
            except Exception as e:
                raise ValueError(f"Invalid sender_id '{message.sender_id}': {e}")
            
            # Set recipient (to field in MeshPacket)
            try:
                if message.recipient_id and message.recipient_id != "^all":
                    packet.to = self._node_id_to_int(message.recipient_id)
                else:
                    # Broadcast address
                    packet.to = 0xFFFFFFFF
            except Exception as e:
                self.logger.warning(f"Invalid recipient_id '{message.recipient_id}', using broadcast: {e}")
                packet.to = 0xFFFFFFFF
            
            # Set channel
            try:
                packet.channel = int(message.channel)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid channel '{message.channel}': {e}")
            
            # Set hop limit and hop count
            if message.hop_limit is not None:
                try:
                    packet.hop_limit = int(message.hop_limit)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid hop_limit '{message.hop_limit}', using default: {e}")
                    packet.hop_limit = 3
            else:
                packet.hop_limit = 3  # Default hop limit
            
            packet.hop_start = packet.hop_limit  # Initial hop count
            
            # Set packet ID (use message ID or generate)
            # Meshtastic uses 32-bit packet IDs
            try:
                packet.id = hash(message.id) & 0xFFFFFFFF
            except Exception as e:
                self.logger.warning(f"Error hashing message ID, using random: {e}")
                import random
                packet.id = random.randint(0, 0xFFFFFFFF)
            
            # Set RX time (timestamp)
            try:
                packet.rx_time = int(message.timestamp.timestamp())
            except (AttributeError, ValueError, TypeError) as e:
                self.logger.warning(f"Invalid timestamp, using current time: {e}")
                from datetime import datetime
                packet.rx_time = int(datetime.now(datetime.UTC).timestamp() if hasattr(datetime, 'UTC') else datetime.utcnow().timestamp())
            
            # Set signal quality if available
            if message.snr is not None:
                try:
                    packet.rx_snr = float(message.snr)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid SNR value '{message.snr}': {e}")
            
            if message.rssi is not None:
                try:
                    packet.rx_rssi = int(message.rssi)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid RSSI value '{message.rssi}': {e}")
            
            # Handle payload based on encryption setting
            if self.encryption_enabled:
                # Encrypted payload pass-through
                # If message has encrypted payload in metadata, use it
                if 'encrypted_payload' in message.metadata:
                    encrypted_data = message.metadata['encrypted_payload']
                    if isinstance(encrypted_data, bytes):
                        packet.encrypted = encrypted_data
                    else:
                        self.logger.warning(f"encrypted_payload is not bytes, using empty")
                        packet.encrypted = b''
                else:
                    # No encrypted payload available - create empty encrypted field
                    # This indicates the message should be encrypted but we don't have the data
                    packet.encrypted = b''
            else:
                # Unencrypted payload - serialize as Data protobuf
                try:
                    data = mesh_pb2.Data()
                    
                    # Set portnum based on message type
                    data.portnum = self._get_portnum_for_message_type(message.message_type)
                    
                    # Set payload (message content as bytes)
                    if message.content:
                        if isinstance(message.content, str):
                            data.payload = message.content.encode('utf-8')
                        elif isinstance(message.content, bytes):
                            data.payload = message.content
                        else:
                            data.payload = str(message.content).encode('utf-8')
                    else:
                        data.payload = b''
                    
                    # Serialize Data and set as decoded field
                    packet.decoded.CopyFrom(data)
                except Exception as e:
                    raise ValueError(f"Failed to serialize message payload: {e}")
            
            # Set the packet in the envelope
            try:
                envelope.packet.CopyFrom(packet)
            except Exception as e:
                raise ValueError(f"Failed to copy packet to envelope: {e}")
            
            # Set channel_id (as string)
            try:
                envelope.channel_id = str(message.channel)
            except Exception as e:
                raise ValueError(f"Failed to set channel_id: {e}")
            
            # Set gateway_id (as string)
            if 'gateway_id' in message.metadata:
                try:
                    envelope.gateway_id = str(message.metadata['gateway_id'])
                except Exception as e:
                    self.logger.warning(f"Invalid gateway_id in metadata, using default: {e}")
                    envelope.gateway_id = 'zephyrgate'
            else:
                # Use a default gateway ID
                envelope.gateway_id = 'zephyrgate'
            
            # Serialize the envelope
            try:
                return envelope.SerializeToString()
            except Exception as e:
                raise ValueError(f"Failed to serialize ServiceEnvelope: {e}")
                
        except ValueError:
            # Re-raise ValueError with original message
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            raise ValueError(f"Unexpected error formatting protobuf message: {e}")
    
    def _node_id_to_int(self, node_id: str) -> int:
        """
        Convert Meshtastic node ID string to integer.
        
        Node IDs are typically in format !xxxxxxxx where x is hex digit.
        
        Args:
            node_id: Node ID string (e.g., "!a1b2c3d4")
            
        Returns:
            Integer representation of node ID
        """
        if not node_id:
            return 0
        
        # Remove leading ! if present
        if node_id.startswith('!'):
            node_id = node_id[1:]
        
        # Convert hex string to integer
        try:
            return int(node_id, 16)
        except ValueError:
            # If conversion fails, return 0
            return 0
    
    def _get_portnum_for_message_type(self, message_type: MessageType) -> int:
        """
        Get Meshtastic portnum for a message type.
        
        Args:
            message_type: The message type
            
        Returns:
            Meshtastic portnum value
        """
        # Map message types to Meshtastic portnums
        type_to_portnum = {
            MessageType.TEXT: portnums_pb2.PortNum.TEXT_MESSAGE_APP,
            MessageType.POSITION: portnums_pb2.PortNum.POSITION_APP,
            MessageType.NODEINFO: portnums_pb2.PortNum.NODEINFO_APP,
            MessageType.ROUTING: portnums_pb2.PortNum.ROUTING_APP,
            MessageType.ADMIN: portnums_pb2.PortNum.ADMIN_APP,
            MessageType.TELEMETRY: portnums_pb2.PortNum.TELEMETRY_APP,
            MessageType.RANGE_TEST: portnums_pb2.PortNum.RANGE_TEST_APP,
            MessageType.DETECTION_SENSOR: portnums_pb2.PortNum.DETECTION_SENSOR_APP,
            MessageType.REPLY: portnums_pb2.PortNum.REPLY_APP,
            MessageType.IP_TUNNEL: portnums_pb2.PortNum.IP_TUNNEL_APP,
            MessageType.SERIAL: portnums_pb2.PortNum.SERIAL_APP,
            MessageType.STORE_FORWARD: portnums_pb2.PortNum.STORE_FORWARD_APP,
            MessageType.UNKNOWN: portnums_pb2.PortNum.UNKNOWN_APP,
        }
        
        return type_to_portnum.get(message_type, portnums_pb2.PortNum.UNKNOWN_APP)
    
    def format_json(self, message: Message) -> str:
        """
        Format message as JSON string according to Meshtastic JSON schema.
        
        Creates a JSON object containing all required Meshtastic fields:
        - sender: Node ID of the sender
        - timestamp: Message timestamp (Unix epoch)
        - channel: Channel number
        - type: Message type (text, position, nodeinfo, telemetry, etc.)
        - payload: Message content (varies by type)
        - snr: Signal-to-noise ratio (if available)
        - rssi: Received signal strength indicator (if available)
        
        Handles serialization errors gracefully:
        - Invalid message data
        - Missing required fields
        - JSON serialization failures
        
        Args:
            message: The message to format
            
        Returns:
            JSON string compliant with Meshtastic JSON schema
            
        Raises:
            ValueError: If message cannot be serialized to JSON
            
        Requirements: 3.4, 5.2, 4.4, 8.4
        """
        import json
        
        try:
            # Validate message
            if not message:
                raise ValueError("Message cannot be None")
            
            if not message.sender_id:
                raise ValueError("Message must have a sender_id")
            
            # Build JSON object with required Meshtastic fields
            json_obj = {}
            
            # Sender node ID (from field) - required
            try:
                json_obj["sender"] = str(message.sender_id)
            except Exception as e:
                raise ValueError(f"Invalid sender_id: {e}")
            
            # Timestamp (Unix epoch seconds) - required
            try:
                json_obj["timestamp"] = int(message.timestamp.timestamp())
            except (AttributeError, ValueError, TypeError) as e:
                self.logger.warning(f"Invalid timestamp, using current time: {e}")
                from datetime import datetime
                json_obj["timestamp"] = int(datetime.now(datetime.UTC).timestamp() if hasattr(datetime, 'UTC') else datetime.utcnow().timestamp())
            
            # Channel number - required
            try:
                json_obj["channel"] = int(message.channel)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid channel '{message.channel}': {e}")
            
            # Message type (lowercase) - required
            try:
                json_obj["type"] = message.message_type.value.lower()
            except (AttributeError, ValueError) as e:
                raise ValueError(f"Invalid message_type: {e}")
            
            # Payload (message content) - required
            try:
                if message.content is None:
                    json_obj["payload"] = ""
                elif isinstance(message.content, str):
                    json_obj["payload"] = message.content
                elif isinstance(message.content, bytes):
                    json_obj["payload"] = message.content.decode('utf-8', errors='replace')
                else:
                    json_obj["payload"] = str(message.content)
            except Exception as e:
                self.logger.warning(f"Error converting payload, using empty string: {e}")
                json_obj["payload"] = ""
            
            # Add optional fields if available
            
            # Signal quality - SNR (Signal-to-Noise Ratio)
            if message.snr is not None:
                try:
                    json_obj["snr"] = float(message.snr)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid SNR value '{message.snr}': {e}")
            
            # Signal quality - RSSI (Received Signal Strength Indicator)
            if message.rssi is not None:
                try:
                    json_obj["rssi"] = int(message.rssi)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid RSSI value '{message.rssi}': {e}")
            
            # Recipient (if not broadcast)
            if message.recipient_id and message.recipient_id != "^all":
                try:
                    json_obj["to"] = str(message.recipient_id)
                except Exception as e:
                    self.logger.warning(f"Invalid recipient_id: {e}")
            
            # Hop limit (if available)
            if message.hop_limit is not None:
                try:
                    json_obj["hop_limit"] = int(message.hop_limit)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid hop_limit '{message.hop_limit}': {e}")
            
            # Add any additional metadata that should be preserved
            if message.metadata:
                # Gateway ID (if available)
                if 'gateway_id' in message.metadata:
                    try:
                        json_obj["gateway_id"] = str(message.metadata['gateway_id'])
                    except Exception as e:
                        self.logger.warning(f"Invalid gateway_id in metadata: {e}")
                
                # Hop count (if available)
                if 'hop_count' in message.metadata:
                    try:
                        json_obj["hop_count"] = int(message.metadata['hop_count'])
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Invalid hop_count in metadata: {e}")
            
            # Serialize to JSON string
            try:
                return json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Failed to serialize JSON: {e}")
                
        except ValueError:
            # Re-raise ValueError with original message
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            raise ValueError(f"Unexpected error formatting JSON message: {e}")
