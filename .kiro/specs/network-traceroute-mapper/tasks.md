# Implementation Plan: Network Traceroute Mapper

## Overview

This implementation plan breaks down the Network Traceroute Mapper feature into discrete, incremental coding tasks. The approach follows a bottom-up strategy: build core components first (node tracking, priority queue, rate limiting), then integrate them into the main plugin, and finally add advanced features (persistence, health monitoring). Each task builds on previous work and includes testing to validate functionality early.

## Tasks

- [x] 1. Set up plugin structure and configuration
  - Create plugin directory structure: `plugins/traceroute_mapper/`
  - Create `__init__.py`, `plugin.py`, `manifest.yaml`, `config_schema.json`
  - Define configuration schema with all settings (rate limits, queue size, filters, etc.)
  - Implement configuration validation in plugin initialization
  - _Requirements: 1.1, 1.3, 1.4, 3.3, 6.2, 10.2, 11.2, 11.5_

- [x] 1.1 Write property test for configuration validation
  - **Property 13: Configuration validation with random parameters**
  - **Validates: Requirements 1.3, 3.5, 6.3**

- [x] 2. Implement NodeStateTracker component
  - [x] 2.1 Create `node_state_tracker.py` with NodeState dataclass
    - Define NodeState with all fields (node_id, is_direct, last_seen, last_traced, etc.)
    - Implement `update_node()` to track node state changes
    - Implement `get_node_state()` and `is_direct_node()` methods
    - Implement direct node detection logic (neighbor list, hop_count, SNR/RSSI)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Write property test for direct node detection
    - **Property 1: Direct Node Exclusion**
    - **Property 3: Direct node classification**
    - **Validates: Requirements 2.1, 2.3**

  - [x] 2.3 Implement node filtering logic
    - Implement `should_trace_node()` with blacklist/whitelist/role/SNR filtering
    - Implement filter precedence (whitelist first, then blacklist)
    - Add methods: `get_nodes_needing_trace()`, `mark_node_traced()`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 2.4 Write property tests for node filtering
    - **Property 17: Blacklist Filtering**
    - **Property 18: Whitelist Filtering**
    - **Property 19: Blacklist and Whitelist Precedence**
    - **Property 20: Role Filtering**
    - **Property 21: SNR Threshold Filtering**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

- [x] 3. Implement PriorityQueue component
  - [x] 3.1 Create `priority_queue.py` with TracerouteRequest dataclass
    - Define TracerouteRequest with priority, node_id, reason, timestamps
    - Implement priority queue using heapq or custom data structure
    - Implement `enqueue()` with priority ordering
    - Implement `dequeue()` with priority + FIFO ordering
    - Implement duplicate detection (don't queue same node twice)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.2 Write property test for priority queue ordering
    - **Property 7: Priority Queue Ordering**
    - **Validates: Requirements 4.4, 4.5**

  - [x] 3.3 Implement queue size limits and overflow handling
    - Implement `is_full()` and size limit enforcement
    - Implement overflow strategies: drop_lowest_priority, drop_oldest, drop_new
    - Implement `remove()` for removing specific node requests
    - Add `clear()` and `contains()` methods
    - _Requirements: 10.1, 10.4, 10.5, 10.6_

  - [x] 3.4 Write property tests for queue overflow
    - **Property 8: Queue Overflow with Priority**
    - **Property 22: Queue Size Limit**
    - **Property 23: Queue Overflow Strategy**
    - **Validates: Requirements 4.6, 10.1, 10.4, 10.5**

- [x] 4. Implement RateLimiter component
  - [x] 4.1 Create `rate_limiter.py` with token bucket algorithm
    - Implement token bucket with configurable rate (traceroutes per minute)
    - Implement `acquire()` method that waits for available token
    - Implement `wait_if_needed()` and `get_wait_time()` methods
    - Implement `set_rate()` for dynamic rate adjustment
    - Track statistics: tokens available, messages allowed, messages delayed
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.2 Write property test for rate limit enforcement
    - **Property 3: Rate Limit Enforcement**
    - **Validates: Requirements 3.1**

  - [x] 4.3 Write unit tests for rate limiter edge cases
    - Test zero rate (should disable operations)
    - Test burst allowance
    - Test rate changes during operation
    - _Requirements: 3.4_

- [x] 5. Checkpoint - Core components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement TracerouteManager component
  - [x] 6.1 Create `traceroute_manager.py` with PendingTraceroute dataclass
    - Define PendingTraceroute to track pending requests
    - Implement `send_traceroute()` to create and send traceroute messages
    - Create Meshtastic-compliant traceroute request (MessageType.ROUTING, hop_limit, metadata)
    - Track pending requests with timeout tracking
    - _Requirements: 6.1, 18.1, 18.2, 18.3_

  - [x] 6.2 Write property test for traceroute request protocol compliance
    - **Property 11: Max Hops Configuration**
    - **Property 38: Traceroute Request Protocol Compliance**
    - **Validates: Requirements 6.1, 18.1, 18.2, 18.3**

  - [x] 6.3 Implement traceroute response handling
    - Implement `handle_traceroute_response()` to process responses
    - Parse route array from response metadata
    - Extract node IDs, SNR, RSSI values from route
    - Match responses to pending requests
    - Calculate response time and update statistics
    - _Requirements: 18.4, 18.5_

  - [x] 6.4 Write property tests for response parsing
    - **Property 39: Traceroute Response Route Parsing**
    - **Property 40: Traceroute Response Signal Parsing**
    - **Validates: Requirements 18.4, 18.5**

  - [x] 6.5 Implement timeout and retry logic
    - Implement timeout detection for pending requests
    - Implement retry scheduling with exponential backoff
    - Implement `cancel_traceroute()` for cleanup
    - Track retry counts and enforce max retries
    - _Requirements: 11.1, 11.3, 11.4, 11.6_

  - [x] 6.6 Write property tests for retry logic
    - **Property 24: Retry Attempts Limit**
    - **Property 25: Exponential Backoff Calculation**
    - **Property 26: Timeout Enforcement**
    - **Validates: Requirements 11.1, 11.3, 11.4**

- [x] 7. Implement StatePersistence component
  - [x] 7.1 Create `state_persistence.py` with JSON serialization
    - Implement `save_state()` to write node states to JSON file
    - Implement `load_state()` to read node states from JSON file
    - Handle file I/O errors gracefully (missing file, corrupted data)
    - Implement state file format with version, timestamp, nodes dict
    - _Requirements: 13.1, 13.2, 13.3, 13.5_

  - [x] 7.2 Write property test for state persistence round trip
    - **Property 16: State Persistence Round Trip**
    - **Property 32: State Completeness**
    - **Validates: Requirements 8.5, 13.2, 13.3**

  - [x] 7.3 Implement traceroute history storage
    - Implement `save_traceroute_history()` to store successful traces
    - Implement `get_traceroute_history()` to retrieve history
    - Enforce history limit per node (keep last N traces)
    - Store TracerouteResult with route, SNR/RSSI, timestamp
    - _Requirements: 13.4_

  - [x] 7.4 Write property test for history limit enforcement
    - **Property 33: Traceroute History Limit**
    - **Validates: Requirements 13.4**

- [x] 8. Implement NetworkHealthMonitor component
  - [x] 8.1 Create `network_health_monitor.py` with health metrics tracking
    - Track success/failure counts and calculate success rate
    - Implement `is_healthy()` based on success rate threshold
    - Implement `record_success()` and `record_failure()` methods
    - Track consecutive failures for emergency stop trigger
    - _Requirements: 12.2, 12.3_

  - [x] 8.2 Implement quiet hours functionality
    - Implement `is_quiet_hours()` with time window checking
    - Parse start_time and end_time from configuration
    - Handle timezone conversion
    - _Requirements: 12.1_

  - [x] 8.3 Write property test for quiet hours enforcement
    - **Property 27: Quiet Hours Enforcement**
    - **Validates: Requirements 12.1**

  - [x] 8.4 Implement congestion detection and throttling
    - Implement `should_throttle()` based on success rate
    - Implement `get_recommended_rate()` for dynamic rate adjustment
    - Track average response time for congestion detection
    - _Requirements: 12.2_

  - [x] 8.5 Write property tests for network health protection
    - **Property 28: Congestion Throttling**
    - **Property 29: Emergency Stop Trigger**
    - **Property 30: Automatic Recovery**
    - **Validates: Requirements 12.2, 12.3, 12.5**

  - [x] 8.6 Implement emergency stop mode
    - Implement `enter_emergency_stop()` and `exit_emergency_stop()`
    - Implement auto-recovery timer
    - Track emergency stop state and reason
    - _Requirements: 12.3, 12.4, 12.5_

- [x] 9. Checkpoint - All components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement main TracerouteMapperPlugin class
  - [x] 10.1 Create plugin initialization and lifecycle
    - Implement `__init__()` with component initialization
    - Implement `initialize()` to load config and create components
    - Implement `start()` to begin operations and start background tasks
    - Implement `stop()` to cleanup and save state
    - Register with message router
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 16.1_

  - [x] 10.2 Implement message handling
    - Implement `_handle_mesh_message()` to receive messages from router
    - Detect node discovery events and update NodeStateTracker
    - Detect traceroute responses and forward to TracerouteManager
    - Detect new indirect nodes and queue traceroute requests
    - Detect nodes coming back online and queue with appropriate priority
    - _Requirements: 2.1, 4.1, 4.2, 16.2, 16.3, 16.4_

  - [x] 10.3 Write property tests for priority assignment
    - **Property 4: New Node Priority Assignment**
    - **Property 5: Node Back Online Priority Assignment**
    - **Property 6: Periodic Recheck Priority Assignment**
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [x] 10.4 Implement direct node transition handling
    - Detect when indirect node becomes direct
    - Remove pending traceroute requests for newly direct nodes
    - Update statistics for skipped direct nodes
    - _Requirements: 2.2_

  - [x] 10.5 Write property test for direct node transition cleanup
    - **Property 2: Direct Node Transition Cleanup**
    - **Validates: Requirements 2.2**

- [x] 11. Implement background task loops
  - [x] 11.1 Implement queue processing loop
    - Create `_process_queue_loop()` background task
    - Dequeue requests in priority order
    - Check rate limiter before sending
    - Check network health before sending
    - Send traceroute via TracerouteManager
    - Handle errors and continue operation
    - _Requirements: 3.1, 4.4, 12.1, 12.2, 12.3_

  - [x] 11.2 Implement periodic recheck loop
    - Create `_periodic_recheck_loop()` background task
    - Check for nodes needing recheck based on recheck_interval
    - Queue recheck requests with priority 8
    - Schedule next recheck after successful trace
    - Reset recheck timer when node is traced early
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

  - [x] 11.3 Write property tests for recheck scheduling
    - **Property 9: Recheck Scheduling After Success**
    - **Property 10: Recheck Timer Reset**
    - **Validates: Requirements 5.1, 5.4**

  - [x] 11.3 Implement state persistence loop
    - Create `_state_persistence_loop()` background task
    - Save state periodically based on auto_save_interval
    - Handle save errors gracefully
    - Track last save time
    - _Requirements: 13.1_

  - [x] 11.4 Write property test for periodic state persistence
    - **Property 31: Periodic State Persistence**
    - **Validates: Requirements 13.1**

- [x] 12. Implement MQTT message forwarding
  - [x] 12.1 Forward traceroute requests to message router
    - When sending traceroute, forward message to message router
    - Message router will route to MQTT Gateway (if enabled)
    - Use standard Meshtastic message format
    - _Requirements: 7.1, 7.3, 14.1_

  - [x] 12.2 Write property test for request forwarding
    - **Property 12: Traceroute Request Forwarding**
    - **Property 14: Meshtastic Message Format Compliance**
    - **Validates: Requirements 7.1, 7.3**

  - [x] 12.3 Forward traceroute responses to message router
    - When receiving traceroute response, forward to message router
    - Forward responses from other nodes as well (not just our requests)
    - Preserve all message fields including route array
    - _Requirements: 7.2, 14.4, 14.5_

  - [x] 12.4 Write property tests for response forwarding
    - **Property 13: Traceroute Response Forwarding**
    - **Property 34: All Traceroute Messages Forwarded**
    - **Property 35: Traceroute Message Field Preservation**
    - **Validates: Requirements 7.2, 14.1, 14.4, 14.5**

- [x] 13. Implement startup behavior
  - [x] 13.1 Implement startup delay
    - Wait for configured startup_delay_seconds before first traceroute
    - Use asyncio.sleep() in background task
    - _Requirements: 8.3, 8.4_

  - [x] 13.2 Write property test for startup delay enforcement
    - **Property 15: Startup Delay Enforcement**
    - **Validates: Requirements 8.3**

  - [x] 13.2 Implement initial discovery scan
    - Load persisted state if enabled
    - Queue traceroutes for all known indirect nodes if initial_discovery_enabled
    - Use appropriate priorities for initial scan
    - _Requirements: 8.1, 8.2, 8.5_

  - [x] 13.3 Write unit tests for startup behavior
    - Test initial discovery enabled vs disabled
    - Test state loading at startup
    - Test queue clearing on startup
    - _Requirements: 8.1, 8.2, 10.6_

- [x] 14. Implement health status and statistics
  - [x] 14.1 Implement `get_health_status()` method
    - Return comprehensive health status dict
    - Include enabled, initialized, emergency_stop, queue_size, etc.
    - Include statistics: traceroutes sent/successful/failed
    - Include network health metrics
    - _Requirements: 15.5, 15.6_

  - [x] 14.2 Write property tests for statistics and health status
    - **Property 36: Statistics Accuracy**
    - **Property 37: Health Status Accuracy**
    - **Validates: Requirements 15.5, 15.6**

  - [x] 14.3 Implement logging throughout plugin
    - Log initialization with configuration details
    - Log traceroute requests and responses
    - Log errors with stack traces
    - Log queue operations at debug level
    - Log health events (emergency stop, congestion, etc.)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.7_

- [x] 15. Integration and wiring
  - [x] 15.1 Wire all components together in plugin
    - Connect NodeStateTracker to message handler
    - Connect PriorityQueue to queue processing loop
    - Connect RateLimiter to queue processing loop
    - Connect TracerouteManager to send/receive methods
    - Connect StatePersistence to startup/shutdown
    - Connect NetworkHealthMonitor to queue processing
    - _Requirements: All integration requirements_

  - [x] 15.2 Write integration tests
    - Test end-to-end flow: node discovery → queue → send → response → MQTT
    - Test state persistence across plugin restarts
    - Test emergency stop and recovery
    - Test quiet hours enforcement
    - Test rate limiting under load

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- The implementation follows a bottom-up approach: build components first, then integrate
- All components are designed to be testable in isolation
- Background tasks use asyncio for non-blocking operation
- Error handling is built into each component
- Configuration validation happens early in initialization
- State persistence enables recovery across restarts
- Network health protection prevents overwhelming the mesh
- MQTT integration uses existing MQTT Gateway plugin
