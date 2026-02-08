# Requirements Document: Network Traceroute Mapper

## Introduction

This document specifies the requirements for adding automated network traceroute functionality to ZephyrGate. The Network Traceroute Mapper will automatically discover and map the mesh network topology by performing traceroutes to nodes and publishing the results to MQTT for visualization by online mapping tools. This feature is designed to be optional, disabled by default, and will intelligently manage traceroute requests to avoid overwhelming the network.

## Glossary

- **Traceroute_Mapper**: The plugin service responsible for performing traceroutes and publishing results
- **Traceroute**: A network diagnostic operation that discovers the path packets take through the mesh network
- **Direct_Node**: A node that is directly heard by the ZephyrGate radio (one hop away)
- **Indirect_Node**: A node that requires multiple hops to reach from the ZephyrGate
- **Priority_Queue**: A queue that orders traceroute requests by priority level (1-10 scale)
- **Node_State**: The tracked state of a node including last seen time, last traced time, and direct/indirect status
- **Hop**: A single step in the path from source to destination node
- **Max_Hops**: The maximum number of hops to trace before stopping
- **Rate_Limiter**: Component that enforces maximum traceroute frequency
- **MQTT_Gateway**: The existing ZephyrGate plugin that publishes messages to MQTT brokers
- **Message_Router**: The existing ZephyrGate component that routes messages to service modules
- **Node_Discovery_Event**: An event triggered when a new node is detected on the mesh network

## Requirements

### Requirement 1: Optional Feature Configuration

**User Story:** As a ZephyrGate operator, I want the traceroute mapper to be optional and disabled by default, so that ZephyrGate can operate normally without automatic traceroute traffic.

#### Acceptance Criteria

1. WHEN ZephyrGate starts with default configuration THEN the Traceroute_Mapper SHALL remain disabled
2. WHEN the Traceroute_Mapper is disabled THEN the Message_Router SHALL function normally without traceroute operations
3. WHEN the Traceroute_Mapper configuration is missing THEN ZephyrGate SHALL start successfully without errors
4. WHEN the Traceroute_Mapper is enabled in configuration THEN the Traceroute_Mapper SHALL initialize and begin monitoring node discovery events
5. WHEN the Traceroute_Mapper initialization fails THEN ZephyrGate SHALL continue operating with normal mesh functionality

### Requirement 2: Direct Node Filtering

**User Story:** As a network operator, I want to skip traceroutes to nodes directly heard by my radio, so that I don't waste network resources on single-hop paths that are already known.

#### Acceptance Criteria

1. WHEN a node is detected as a Direct_Node THEN the Traceroute_Mapper SHALL not queue a traceroute request for that node
2. WHEN a node transitions from Indirect_Node to Direct_Node THEN the Traceroute_Mapper SHALL remove any pending traceroute requests for that node
3. WHEN determining if a node is direct THEN the Traceroute_Mapper SHALL check if the node appears in the neighbor list or has SNR/RSSI values indicating direct reception
4. WHEN a Direct_Node is detected THEN the Traceroute_Mapper SHALL log the skip event at debug level

### Requirement 3: Rate Limiting

**User Story:** As a network operator, I want to configure how frequently traceroutes are sent, so that I can balance network discovery speed with network load.

#### Acceptance Criteria

1. WHEN the Traceroute_Mapper sends traceroutes THEN the System SHALL enforce a configurable maximum traceroutes per minute rate limit
2. WHEN the rate limit is reached THEN the Traceroute_Mapper SHALL wait before sending the next traceroute
3. WHEN no rate limit is configured THEN the Traceroute_Mapper SHALL use a default of 1 traceroute per minute
4. WHEN the rate limit is set to zero THEN the Traceroute_Mapper SHALL disable all traceroute operations
5. WHEN the rate limit configuration is invalid THEN the Traceroute_Mapper SHALL log an error and use the default rate

### Requirement 4: Priority Queue System

**User Story:** As a network operator, I want traceroute requests to be prioritized intelligently, so that important network changes are discovered quickly while routine checks happen in the background.

#### Acceptance Criteria

1. WHEN a new Indirect_Node is discovered THEN the Traceroute_Mapper SHALL queue a traceroute request with priority 1 (highest)
2. WHEN a node that was offline comes back online THEN the Traceroute_Mapper SHALL queue a traceroute request with priority 4
3. WHEN a periodic recheck is scheduled THEN the Traceroute_Mapper SHALL queue a traceroute request with priority 8
4. WHEN multiple traceroute requests are queued THEN the Traceroute_Mapper SHALL process requests in priority order (lowest number first)
5. WHEN two requests have the same priority THEN the Traceroute_Mapper SHALL process them in FIFO order
6. WHEN the queue is full THEN the Traceroute_Mapper SHALL drop the lowest priority request to make room for higher priority requests

### Requirement 5: Periodic Rechecks

**User Story:** As a network operator, I want nodes to be re-traced periodically, so that I can detect changes in network topology over time.

#### Acceptance Criteria

1. WHEN a node has been successfully traced THEN the Traceroute_Mapper SHALL schedule a recheck after the configured recheck interval
2. WHEN no recheck interval is configured THEN the Traceroute_Mapper SHALL use a default of 6 hours
3. WHEN a recheck is due THEN the Traceroute_Mapper SHALL queue a traceroute request with priority 8
4. WHEN a node is traced before its scheduled recheck THEN the Traceroute_Mapper SHALL reset the recheck timer
5. WHEN the recheck interval is set to zero THEN the Traceroute_Mapper SHALL disable periodic rechecks

### Requirement 6: Max Hops Configuration

**User Story:** As a network operator, I want to configure the maximum number of hops for traceroutes, so that I can limit the scope of network discovery based on my network size.

#### Acceptance Criteria

1. WHEN sending a traceroute request THEN the Traceroute_Mapper SHALL set the max hops parameter to the configured value
2. WHEN no max hops is configured THEN the Traceroute_Mapper SHALL use a default of 7 hops
3. WHEN the max hops configuration is invalid THEN the Traceroute_Mapper SHALL log an error and use the default value
4. WHEN a traceroute reaches max hops without finding the destination THEN the Traceroute_Mapper SHALL log the incomplete trace and mark it as failed

### Requirement 7: MQTT Integration

**User Story:** As a network operator, I want traceroute messages published to MQTT in standard Meshtastic format, so that Meshtastic mapping tools can decode and visualize the network topology.

#### Acceptance Criteria

1. WHEN a traceroute request is sent by the Traceroute_Mapper THEN the System SHALL forward the message to the MQTT_Gateway for publishing
2. WHEN a traceroute response is received from the mesh THEN the System SHALL forward the message to the MQTT_Gateway for publishing
3. WHEN forwarding traceroute messages THEN the Traceroute_Mapper SHALL use the standard Meshtastic message format (protobuf or JSON)
4. WHEN the MQTT_Gateway is enabled THEN traceroute messages SHALL be published to MQTT following the Meshtastic MQTT protocol
5. WHEN the MQTT_Gateway is disabled THEN the Traceroute_Mapper SHALL continue operations without MQTT publishing
6. WHEN the MQTT_Gateway is unavailable THEN the Traceroute_Mapper SHALL log a warning and continue operations

### Requirement 8: Startup Behavior Configuration

**User Story:** As a network operator, I want to control how the traceroute mapper behaves at startup, so that I can choose between immediate discovery or gradual background mapping.

#### Acceptance Criteria

1. WHEN initial discovery scan is enabled THEN the Traceroute_Mapper SHALL queue traceroutes for all known Indirect_Nodes at startup
2. WHEN initial discovery scan is disabled THEN the Traceroute_Mapper SHALL only trace nodes discovered after startup
3. WHEN a startup delay is configured THEN the Traceroute_Mapper SHALL wait the specified duration before sending the first traceroute
4. WHEN no startup delay is configured THEN the Traceroute_Mapper SHALL use a default delay of 60 seconds
5. WHEN state persistence is enabled THEN the Traceroute_Mapper SHALL load previous Node_State from disk at startup

### Requirement 9: Node Filtering

**User Story:** As a network operator, I want to filter which nodes are traced, so that I can exclude specific nodes or node types from automatic discovery.

#### Acceptance Criteria

1. WHEN a node blacklist is configured THEN the Traceroute_Mapper SHALL not trace nodes on the blacklist
2. WHEN a node whitelist is configured THEN the Traceroute_Mapper SHALL only trace nodes on the whitelist
3. WHEN both blacklist and whitelist are configured THEN the Traceroute_Mapper SHALL apply the whitelist first, then exclude blacklisted nodes
4. WHEN node role filtering is enabled THEN the Traceroute_Mapper SHALL exclude nodes with specified roles (e.g., CLIENT)
5. WHEN a minimum SNR threshold is configured THEN the Traceroute_Mapper SHALL only trace nodes with SNR above the threshold
6. WHEN a filtered node is encountered THEN the Traceroute_Mapper SHALL log the filter reason at debug level

### Requirement 10: Queue Management

**User Story:** As a network operator, I want the traceroute queue to be managed intelligently, so that memory usage is controlled and the system remains stable.

#### Acceptance Criteria

1. WHEN the queue size is configured THEN the Traceroute_Mapper SHALL enforce the maximum queue size limit
2. WHEN no queue size is configured THEN the Traceroute_Mapper SHALL use a default maximum of 500 requests
3. WHEN the queue is full and a new high-priority request arrives THEN the Traceroute_Mapper SHALL drop the lowest priority request
4. WHEN the queue is full and a new low-priority request arrives THEN the Traceroute_Mapper SHALL drop the new request
5. WHEN queue overflow behavior is configured THEN the Traceroute_Mapper SHALL follow the configured strategy (drop_lowest_priority, drop_oldest, drop_new)
6. WHEN clear queue on startup is enabled THEN the Traceroute_Mapper SHALL empty the queue at initialization

### Requirement 11: Retry Logic

**User Story:** As a network operator, I want failed traceroutes to be retried intelligently, so that temporary network issues don't prevent topology discovery.

#### Acceptance Criteria

1. WHEN a traceroute fails THEN the Traceroute_Mapper SHALL retry up to the configured maximum retry attempts
2. WHEN no retry count is configured THEN the Traceroute_Mapper SHALL use a default of 3 retry attempts
3. WHEN retrying a failed traceroute THEN the Traceroute_Mapper SHALL apply exponential backoff between attempts
4. WHEN a traceroute times out THEN the Traceroute_Mapper SHALL wait for the configured timeout duration before marking it as failed
5. WHEN no timeout is configured THEN the Traceroute_Mapper SHALL use a default timeout of 60 seconds
6. WHEN max retries are exceeded THEN the Traceroute_Mapper SHALL log the failure and remove the request from the queue

### Requirement 12: Network Health Protection

**User Story:** As a network operator, I want the traceroute mapper to protect network health, so that automatic discovery doesn't degrade network performance.

#### Acceptance Criteria

1. WHEN quiet hours are configured THEN the Traceroute_Mapper SHALL pause all traceroute operations during those time windows
2. WHEN network congestion is detected THEN the Traceroute_Mapper SHALL automatically reduce the traceroute rate
3. WHEN the failure rate exceeds a threshold THEN the Traceroute_Mapper SHALL enter emergency stop mode and pause operations
4. WHEN in emergency stop mode THEN the Traceroute_Mapper SHALL log an alert and wait for manual intervention or automatic recovery
5. WHEN network conditions improve THEN the Traceroute_Mapper SHALL automatically resume normal operations

### Requirement 13: Data Persistence

**User Story:** As a network operator, I want node discovery state to be persisted, so that the system doesn't lose topology knowledge across restarts.

#### Acceptance Criteria

1. WHEN state persistence is enabled THEN the Traceroute_Mapper SHALL save Node_State to disk periodically
2. WHEN state persistence is enabled THEN the Traceroute_Mapper SHALL load Node_State from disk at startup
3. WHEN saving state THEN the Traceroute_Mapper SHALL include node ID, last seen time, last traced time, and direct/indirect status
4. WHEN saving traceroute history THEN the Traceroute_Mapper SHALL store the last N successful traceroutes per node
5. WHEN the state file is corrupted THEN the Traceroute_Mapper SHALL log an error and start with empty state

### Requirement 14: Traceroute Message Forwarding

**User Story:** As a mapping tool developer, I want all traceroute messages forwarded to MQTT in standard Meshtastic format, so that I can use existing Meshtastic tools to visualize network topology.

#### Acceptance Criteria

1. WHEN a traceroute message is sent or received THEN the Traceroute_Mapper SHALL forward it to the Message_Router for normal message processing
2. WHEN the MQTT_Gateway receives a traceroute message THEN the MQTT_Gateway SHALL publish it using the standard Meshtastic MQTT protocol
3. WHEN traceroute messages are published THEN the System SHALL use the same topic structure as other Meshtastic messages (msh/{region}/2/{format}/{channel}/{nodeId})
4. WHEN traceroute messages are published THEN the System SHALL preserve all Meshtastic protobuf fields including route array with SNR/RSSI values
5. WHEN other nodes on the mesh send traceroutes THEN the System SHALL forward those messages to MQTT as well

### Requirement 15: Monitoring and Logging

**User Story:** As a network operator, I want detailed logging and statistics, so that I can monitor traceroute mapper activity and troubleshoot issues.

#### Acceptance Criteria

1. WHEN the Traceroute_Mapper starts THEN the System SHALL log initialization status with configuration details
2. WHEN a traceroute is sent THEN the System SHALL log the target node ID, priority, and queue size
3. WHEN a traceroute completes THEN the System SHALL log the result with hop count and duration
4. WHEN a traceroute fails THEN the System SHALL log the failure reason and retry count
5. WHEN statistics are requested THEN the Traceroute_Mapper SHALL report traceroutes sent, successful, failed, and queue depth
6. WHEN health status is requested THEN the Traceroute_Mapper SHALL report operational status and error counts
7. WHEN debug mode is enabled THEN the Traceroute_Mapper SHALL log detailed information about queue operations and node state changes

### Requirement 16: Integration with Message Router

**User Story:** As a ZephyrGate developer, I want the traceroute mapper to integrate with the existing message router, so that it receives node discovery events and traceroute responses without blocking core functionality.

#### Acceptance Criteria

1. WHEN the Traceroute_Mapper is initialized THEN the System SHALL register it with the Message_Router
2. WHEN the Message_Router receives a node discovery event THEN the Traceroute_Mapper SHALL receive the event asynchronously
3. WHEN the Message_Router receives a traceroute response THEN the Traceroute_Mapper SHALL receive the response asynchronously
4. WHEN the Traceroute_Mapper processes an event THEN the Message_Router SHALL not be blocked
5. WHEN the Traceroute_Mapper is disabled THEN the Message_Router SHALL continue routing messages to other services

### Requirement 17: Coordination with Other Plugins

**User Story:** As a network operator, I want the traceroute mapper to coordinate with other plugins, so that network resources are shared fairly and congestion is avoided.

#### Acceptance Criteria

1. WHEN the MQTT_Gateway is rate limiting THEN the Traceroute_Mapper SHALL respect the shared rate limit
2. WHEN other plugins are sending high-priority messages THEN the Traceroute_Mapper SHALL reduce its traceroute rate
3. WHEN the Traceroute_Mapper detects high network activity THEN the System SHALL automatically throttle traceroute operations
4. WHEN network activity returns to normal THEN the Traceroute_Mapper SHALL resume normal operation

### Requirement 18: Meshtastic Traceroute Protocol Compliance

**User Story:** As a Meshtastic network operator, I want the traceroute mapper to follow the Meshtastic traceroute protocol, so that traceroutes work correctly with all Meshtastic devices.

#### Acceptance Criteria

1. WHEN sending a traceroute request THEN the Traceroute_Mapper SHALL use the Meshtastic TRACEROUTE_APP message type
2. WHEN sending a traceroute request THEN the Traceroute_Mapper SHALL set the want_response flag to true
3. WHEN sending a traceroute request THEN the Traceroute_Mapper SHALL include the destination node ID and max hops
4. WHEN receiving a traceroute response THEN the Traceroute_Mapper SHALL parse the route array containing node IDs
5. WHEN receiving a traceroute response THEN the Traceroute_Mapper SHALL extract SNR and RSSI values from the route entries
