# Implementation Plan: MQTT Gateway Integration

## Overview

This implementation plan breaks down the MQTT Gateway feature into discrete, incremental coding tasks. Each task builds on previous work and includes testing to validate functionality early. The implementation follows the plugin architecture established in ZephyrGate and integrates with the existing message router.

## Tasks

- [x] 1. Set up plugin structure and configuration schema
  - Create `plugins/mqtt_gateway/` directory structure
  - Create `__init__.py`, `manifest.yaml`, and `requirements.txt`
  - Define configuration schema in `config_schema.json`
  - Add paho-mqtt and meshtastic dependencies
  - _Requirements: 1.1, 1.3, 9.1, 9.2_

- [ ] 2. Implement core plugin class and lifecycle management
  - [x] 2.1 Create `MQTTGatewayPlugin` class in `plugin.py`
    - Implement `__init__`, `initialize`, `start`, `stop` methods
    - Add configuration loading and validation
    - Implement plugin registration with message router
    - _Requirements: 1.4, 10.1, 10.2_
  
  - [x] 2.2 Write unit tests for plugin lifecycle
    - Test initialization with valid/invalid configs
    - Test start/stop sequences
    - Test configuration validation
    - _Requirements: 1.1, 1.3, 9.4_

- [ ] 3. Implement MQTT client wrapper
  - [x] 3.1 Create `MQTTClient` class in `mqtt_client.py`
    - Implement async wrapper around paho-mqtt
    - Add connection management (connect, disconnect, reconnect)
    - Implement TLS/SSL configuration
    - Add connection state tracking
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [x] 3.2 Implement exponential backoff for reconnection
    - Add backoff calculation method
    - Implement reconnection loop with backoff
    - Add maximum retry limit handling
    - _Requirements: 2.5, 2.6_
  
  - [x] 3.3 Write property test for exponential backoff
    - **Property 11: Exponential Backoff Calculation**
    - **Validates: Requirements 2.5, 2.6**
  
  - [x] 3.4 Write unit tests for MQTT client
    - Test connection with valid/invalid credentials
    - Test TLS/SSL configuration
    - Test connection state transitions
    - _Requirements: 2.1, 2.4_

- [ ] 4. Implement message formatting and topic generation
  - [x] 4.1 Create `MessageFormatter` class in `message_formatter.py`
    - Implement topic path generation for encrypted messages
    - Implement topic path generation for JSON messages
    - Add custom root topic support
    - Implement message type filtering logic
    - _Requirements: 3.1, 3.2, 3.5, 12.1, 12.2, 12.3_
  
  - [x] 4.2 Write property test for encrypted topic paths
    - **Property 1: Topic Path Format for Encrypted Messages**
    - **Validates: Requirements 3.1, 6.3**
  
  - [x] 4.3 Write property test for JSON topic paths
    - **Property 2: Topic Path Format for JSON Messages**
    - **Validates: Requirements 3.2, 6.4**
  
  - [x] 4.4 Write property test for custom root topic
    - **Property 3: Custom Root Topic Override**
    - **Validates: Requirements 3.5**
  
  - [x] 4.5 Write property test for message type filtering
    - **Property 14: Message Type Filtering**
    - **Validates: Requirements 12.1, 12.2, 12.3**

- [ ] 5. Implement protobuf message serialization
  - [x] 5.1 Add protobuf formatting to `MessageFormatter`
    - Implement ServiceEnvelope wrapping
    - Add MeshPacket serialization
    - Handle encrypted payload pass-through
    - _Requirements: 3.3, 5.1, 6.1_
  
  - [x] 5.2 Write property test for protobuf ServiceEnvelope
    - **Property 4: Protobuf ServiceEnvelope Wrapping**
    - **Validates: Requirements 3.3, 5.1**
  
  - [x] 5.3 Write property test for encrypted payload pass-through
    - **Property 10: Encrypted Payload Pass-Through**
    - **Validates: Requirements 6.1**
  
  - [x] 5.4 Write unit tests for specific message types
    - Test TEXT_MESSAGE_APP serialization
    - Test TELEMETRY_APP serialization
    - Test NODEINFO_APP serialization
    - Test POSITION_APP serialization
    - _Requirements: 5.3, 5.4, 5.5, 5.6_

- [ ] 6. Implement JSON message serialization
  - [x] 6.1 Add JSON formatting to `MessageFormatter`
    - Implement JSON serialization for all message types
    - Add Meshtastic JSON schema compliance
    - Implement metadata preservation (sender, timestamp, SNR/RSSI)
    - _Requirements: 3.4, 5.2, 4.4_
  
  - [x] 6.2 Write property test for JSON schema compliance
    - **Property 5: JSON Schema Compliance**
    - **Validates: Requirements 3.4, 5.2**
  
  - [x] 6.3 Write property test for metadata preservation
    - **Property 7: Message Metadata Preservation**
    - **Validates: Requirements 4.4**
  
  - [x] 6.4 Write unit tests for unsupported message types
    - Test that unsupported types are skipped
    - Test warning logging for unsupported types
    - _Requirements: 5.7_

- [x] 7. Checkpoint - Ensure message formatting tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement message queue
  - [x] 8.1 Create `MessageQueue` class in `message_queue.py`
    - Implement FIFO queue with priority support
    - Add enqueue/dequeue methods
    - Implement maximum size enforcement
    - Add queue statistics tracking
    - _Requirements: 4.5, 4.6_
  
  - [x] 8.2 Write property test for queue overflow behavior
    - **Property 8: Queue Overflow Behavior**
    - **Validates: Requirements 4.6, 7.4**
  
  - [x] 8.3 Write property test for queuing when disconnected
    - **Property 9: Message Queuing When Disconnected**
    - **Validates: Requirements 4.5, 7.3**
  
  - [x] 8.4 Write unit tests for queue operations
    - Test enqueue/dequeue operations
    - Test priority ordering
    - Test queue size limits
    - _Requirements: 4.5, 4.6_

- [ ] 9. Implement rate limiter
  - [x] 9.1 Create `RateLimiter` class in `rate_limiter.py`
    - Implement token bucket algorithm
    - Add configurable rate limit enforcement
    - Implement wait/acquire methods
    - Add rate limit statistics
    - _Requirements: 7.1_
  
  - [x] 9.2 Write property test for rate limit enforcement
    - **Property 12: Rate Limit Enforcement**
    - **Validates: Requirements 7.1**
  
  - [x] 9.3 Write unit tests for rate limiter
    - Test token bucket refill
    - Test rate limit enforcement
    - Test burst handling
    - _Requirements: 7.1_

- [ ] 10. Integrate components in main plugin class
  - [x] 10.1 Wire MQTT client, formatter, queue, and rate limiter together
    - Connect components in `MQTTGatewayPlugin`
    - Implement `handle_message` method
    - Add background task for queue processing
    - Implement async message publishing
    - _Requirements: 10.2, 10.3_
  
  - [x] 10.2 Implement channel filtering logic
    - Add channel uplink enable/disable checking
    - Implement message filtering based on channel config
    - _Requirements: 4.2, 4.3_
  
  - [x] 10.3 Write property test for channel uplink filtering
    - **Property 6: Channel Uplink Filtering**
    - **Validates: Requirements 4.2, 4.3**

- [ ] 11. Implement error handling and logging
  - [x] 11.1 Add comprehensive error handling
    - Handle connection errors gracefully
    - Implement serialization error handling
    - Add queue overflow handling
    - Implement rate limit error handling
    - _Requirements: 2.4, 8.4, 8.5_
  
  - [x] 11.2 Add detailed logging throughout
    - Log connection events
    - Log message forwarding
    - Log errors with stack traces
    - Log queue and rate limit events
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 11.3 Write unit tests for error handling
    - Test connection error handling
    - Test serialization error handling
    - Test invalid message handling
    - Test decryption error handling
    - _Requirements: 2.4, 6.5_

- [ ] 12. Implement configuration validation and defaults
  - [x] 12.1 Add configuration validation logic
    - Validate required parameters
    - Apply default values for missing parameters
    - Validate parameter types and ranges
    - Generate descriptive error messages
    - _Requirements: 9.2, 9.3, 9.4_
  
  - [x] 12.2 Write property test for configuration validation
    - **Property 13: Configuration Validation**
    - **Validates: Requirements 9.2, 9.3**
  
  - [x] 12.3 Write unit tests for configuration edge cases
    - Test missing required parameters
    - Test invalid parameter values
    - Test default value application
    - _Requirements: 9.3, 9.4_

- [ ] 13. Implement health status reporting
  - [x] 13.1 Add `get_health_status` method
    - Report connection status
    - Report queue size and statistics
    - Report message counters
    - Report error counts
    - _Requirements: 11.1, 11.4_
  
  - [x] 13.2 Write unit tests for health status
    - Test health status reporting
    - Test statistics tracking
    - _Requirements: 11.1_

- [ ] 14. Add example configuration to config-example.yaml
  - [x] 14.1 Add mqtt_gateway section to config-example.yaml
    - Add all configuration parameters with comments
    - Provide example values
    - Document all options
    - _Requirements: 9.1_

- [x] 15. Checkpoint - Integration testing
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Create integration tests
  - [x] 16.1 Write integration test for message flow
    - Test message from mesh to MQTT
    - Test with real MQTT test broker
    - Verify topic and payload correctness
    - _Requirements: 4.1, 10.1, 10.2_
  
  - [x] 16.2 Write integration test for reconnection
    - Test connection loss and recovery
    - Test queue processing after reconnection
    - Verify no message loss
    - _Requirements: 8.2, 8.3_
  
  - [x] 16.3 Write integration test for rate limiting
    - Test rate limit enforcement under load
    - Test backoff behavior
    - _Requirements: 7.1, 7.2_

- [x] 17. Create documentation
  - [x] 17.1 Create README.md for plugin
    - Document plugin purpose and features
    - Add configuration examples
    - Document MQTT topic structure
    - Add troubleshooting guide
    - _Requirements: 9.1_
  
  - [x] 17.2 Add user guide to docs/
    - Create MQTT_GATEWAY_GUIDE.md
    - Document setup and configuration
    - Add examples for common use cases
    - Document Meshtastic MQTT protocol compliance
    - _Requirements: 9.1_

- [ ] 18. Final checkpoint - Complete testing and validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end functionality with real MQTT broker
