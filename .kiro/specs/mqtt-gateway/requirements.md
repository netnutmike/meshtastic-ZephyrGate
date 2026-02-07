# Requirements Document: MQTT Gateway Integration

## Introduction

This document specifies the requirements for adding MQTT gateway functionality to ZephyrGate. The MQTT gateway will enable one-way message forwarding from the Meshtastic mesh network to MQTT brokers following the official Meshtastic MQTT protocol standards. This feature is designed to be optional and will not interfere with ZephyrGate's ability to operate standalone without internet connectivity.

## Glossary

- **MQTT_Gateway**: The service module responsible for forwarding messages from Meshtastic to MQTT
- **MQTT_Broker**: The external MQTT server that receives and distributes messages
- **Meshtastic_MQTT_Protocol**: The official protocol specification for MQTT integration with Meshtastic networks
- **ServiceEnvelope**: The protobuf wrapper structure used for encapsulating MeshPackets in MQTT messages
- **MeshPacket**: The core Meshtastic message structure containing routing and payload information
- **Uplink**: Message flow from mesh network to MQTT broker
- **Root_Topic**: The base MQTT topic path (default: msh/REGION)
- **Channel_Name**: The Meshtastic channel identifier used in topic structure
- **Node_ID**: The unique identifier for a Meshtastic node
- **Message_Router**: The existing ZephyrGate component that routes messages to service modules

## Requirements

### Requirement 1: Optional Feature Configuration

**User Story:** As a ZephyrGate operator, I want the MQTT gateway to be optional and disabled by default, so that ZephyrGate can operate standalone without requiring internet connectivity.

#### Acceptance Criteria

1. WHEN ZephyrGate starts with default configuration THEN the MQTT_Gateway SHALL remain disabled
2. WHEN the MQTT_Gateway is disabled THEN the Message_Router SHALL function normally without MQTT integration
3. WHEN the MQTT_Gateway configuration is missing THEN ZephyrGate SHALL start successfully without errors
4. WHEN the MQTT_Gateway is enabled in configuration THEN the MQTT_Gateway SHALL initialize and connect to the configured MQTT_Broker
5. WHEN the MQTT_Broker connection fails THEN ZephyrGate SHALL continue operating with mesh-only functionality

### Requirement 2: MQTT Broker Connection Management

**User Story:** As a ZephyrGate operator, I want to configure MQTT broker connection parameters, so that I can connect to my preferred MQTT server with appropriate security settings.

#### Acceptance Criteria

1. WHEN configuring the MQTT_Gateway THEN the System SHALL accept broker address, port, username, and password parameters
2. WHEN TLS/SSL is enabled in configuration THEN the MQTT_Gateway SHALL establish encrypted connections to the MQTT_Broker
3. WHEN TLS/SSL is disabled in configuration THEN the MQTT_Gateway SHALL establish unencrypted connections to the MQTT_Broker
4. WHEN connection parameters are invalid THEN the MQTT_Gateway SHALL log descriptive error messages
5. WHEN the MQTT_Broker becomes unavailable THEN the MQTT_Gateway SHALL attempt reconnection using exponential backoff
6. WHEN reconnection attempts exceed the configured maximum THEN the MQTT_Gateway SHALL log failure and continue attempting with maximum backoff interval

### Requirement 3: Meshtastic MQTT Protocol Compliance

**User Story:** As a Meshtastic network operator, I want the MQTT gateway to follow official Meshtastic MQTT standards, so that messages are compatible with other Meshtastic MQTT integrations.

#### Acceptance Criteria

1. WHEN forwarding encrypted messages THEN the MQTT_Gateway SHALL publish to topic structure msh/{region}/2/e/{channel}/{nodeId}
2. WHEN forwarding JSON messages THEN the MQTT_Gateway SHALL publish to topic structure msh/{region}/2/json/{channel}/{nodeId}
3. WHEN publishing protobuf messages THEN the MQTT_Gateway SHALL wrap MeshPacket in ServiceEnvelope structure
4. WHEN publishing JSON messages THEN the MQTT_Gateway SHALL serialize message fields according to Meshtastic JSON schema
5. WHEN the Root_Topic is configured THEN the MQTT_Gateway SHALL use the configured value instead of default msh/REGION

### Requirement 4: Uplink Message Forwarding

**User Story:** As a Meshtastic network operator, I want messages received from the mesh to be forwarded to MQTT, so that remote systems can monitor mesh activity.

#### Acceptance Criteria

1. WHEN the Message_Router receives a message from Meshtastic THEN the MQTT_Gateway SHALL receive the message for processing
2. WHEN uplink is enabled for a channel THEN the MQTT_Gateway SHALL forward messages from that channel to MQTT_Broker
3. WHEN uplink is disabled for a channel THEN the MQTT_Gateway SHALL not forward messages from that channel to MQTT_Broker
4. WHEN forwarding a message THEN the MQTT_Gateway SHALL preserve message metadata including sender Node_ID, timestamp, and signal quality
5. WHEN the MQTT_Broker is unavailable THEN the MQTT_Gateway SHALL queue messages for later transmission
6. WHEN the message queue exceeds maximum size THEN the MQTT_Gateway SHALL discard oldest messages and log warnings

### Requirement 5: Message Format Support

**User Story:** As a Meshtastic network operator, I want to support both protobuf and JSON message formats, so that I can integrate with different MQTT clients and tools.

#### Acceptance Criteria

1. WHEN protobuf mode is enabled THEN the MQTT_Gateway SHALL encode messages using Meshtastic protobuf definitions
2. WHEN JSON mode is enabled THEN the MQTT_Gateway SHALL serialize messages to JSON format
3. WHEN JSON mode is enabled THEN the MQTT_Gateway SHALL support TEXT_MESSAGE_APP message type
4. WHEN JSON mode is enabled THEN the MQTT_Gateway SHALL support TELEMETRY_APP message type
5. WHEN JSON mode is enabled THEN the MQTT_Gateway SHALL support NODEINFO_APP message type
6. WHEN JSON mode is enabled THEN the MQTT_Gateway SHALL support POSITION_APP message type
7. WHEN an unsupported message type is encountered THEN the MQTT_Gateway SHALL log a warning and skip the message

### Requirement 6: Encryption Configuration

**User Story:** As a Meshtastic network operator, I want to control whether MQTT payloads are encrypted, so that I can balance security with interoperability requirements.

#### Acceptance Criteria

1. WHEN encryption is enabled in configuration THEN the MQTT_Gateway SHALL forward encrypted message payloads without decryption
2. WHEN encryption is disabled in configuration THEN the MQTT_Gateway SHALL forward decrypted message payloads
3. WHEN encryption is enabled THEN the MQTT_Gateway SHALL publish to encrypted topic paths (msh/{region}/2/e/{channel}/{nodeId})
4. WHEN encryption is disabled THEN the MQTT_Gateway SHALL publish to JSON topic paths (msh/{region}/2/json/{channel}/{nodeId})
5. WHEN a message cannot be decrypted THEN the MQTT_Gateway SHALL log the error and forward the encrypted payload

### Requirement 7: Rate Limiting and Backoff

**User Story:** As a Meshtastic network operator, I want the MQTT gateway to respect broker rate limits, so that I don't overwhelm the MQTT server or get disconnected.

#### Acceptance Criteria

1. WHEN the MQTT_Gateway publishes messages THEN the System SHALL enforce a configurable maximum messages per second rate limit
2. WHEN the MQTT_Broker returns rate limit errors THEN the MQTT_Gateway SHALL implement exponential backoff
3. WHEN backoff is active THEN the MQTT_Gateway SHALL queue messages for later transmission
4. WHEN the message queue is full THEN the MQTT_Gateway SHALL discard oldest messages and log warnings
5. WHEN the MQTT_Broker connection is restored THEN the MQTT_Gateway SHALL resume normal message forwarding

### Requirement 8: Error Handling and Reconnection

**User Story:** As a ZephyrGate operator, I want the MQTT gateway to handle connection failures gracefully, so that temporary network issues don't disrupt mesh operations.

#### Acceptance Criteria

1. WHEN the MQTT_Broker connection is lost THEN the MQTT_Gateway SHALL log the disconnection event
2. WHEN disconnected from MQTT_Broker THEN the MQTT_Gateway SHALL attempt reconnection using exponential backoff
3. WHEN reconnection succeeds THEN the MQTT_Gateway SHALL resume forwarding queued messages
4. WHEN the MQTT_Gateway encounters a protocol error THEN the System SHALL log detailed error information for debugging
5. WHEN the MQTT_Gateway is disabled THEN the System SHALL gracefully disconnect from MQTT_Broker and clean up resources

### Requirement 9: Configuration Schema

**User Story:** As a ZephyrGate operator, I want MQTT gateway configuration to follow the existing YAML format, so that it integrates seamlessly with other ZephyrGate settings.

#### Acceptance Criteria

1. WHEN configuring the MQTT_Gateway THEN the System SHALL accept configuration in YAML format
2. WHEN the configuration file is loaded THEN the System SHALL validate all MQTT_Gateway parameters
3. WHEN required parameters are missing THEN the System SHALL use sensible default values
4. WHEN invalid parameters are provided THEN the System SHALL log validation errors and disable the MQTT_Gateway
5. WHEN configuration is reloaded THEN the MQTT_Gateway SHALL apply new settings without requiring a restart

### Requirement 10: Integration with Message Router

**User Story:** As a ZephyrGate developer, I want the MQTT gateway to integrate with the existing message router, so that it receives messages without blocking core routing functionality.

#### Acceptance Criteria

1. WHEN the MQTT_Gateway is initialized THEN the System SHALL register it with the Message_Router
2. WHEN the Message_Router processes a message THEN the MQTT_Gateway SHALL receive the message asynchronously
3. WHEN the MQTT_Gateway processes a message THEN the Message_Router SHALL not be blocked
4. WHEN the MQTT_Gateway is disabled THEN the Message_Router SHALL continue routing messages to other services

### Requirement 11: Logging and Monitoring

**User Story:** As a ZephyrGate operator, I want detailed logging of MQTT gateway activity, so that I can monitor message flow and troubleshoot issues.

#### Acceptance Criteria

1. WHEN the MQTT_Gateway connects to MQTT_Broker THEN the System SHALL log connection status with broker details
2. WHEN the MQTT_Gateway forwards an uplink message THEN the System SHALL log the message ID, sender, and topic
3. WHEN the MQTT_Gateway encounters an error THEN the System SHALL log detailed error information including stack traces
4. WHEN the MQTT_Gateway queues messages THEN the System SHALL log queue size and status
5. WHEN the MQTT_Gateway applies rate limiting THEN the System SHALL log rate limit events

### Requirement 12: Message Type Filtering

**User Story:** As a ZephyrGate operator, I want to filter which message types are forwarded to MQTT, so that I can reduce bandwidth and focus on relevant data.

#### Acceptance Criteria

1. WHEN message type filtering is configured THEN the MQTT_Gateway SHALL only forward messages matching the configured types
2. WHEN no message type filter is configured THEN the MQTT_Gateway SHALL forward all message types
3. WHEN a message type is excluded by filter THEN the MQTT_Gateway SHALL not forward that message to MQTT_Broker
4. WHEN a filtered message is skipped THEN the MQTT_Gateway SHALL log the skip event at debug level
