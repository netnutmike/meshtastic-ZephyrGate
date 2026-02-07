# MQTT Gateway Integration Tests

## Overview

This document describes the integration tests for the MQTT Gateway plugin. These tests verify end-to-end functionality including message flow, connection management, and rate limiting.

## Test Structure

The integration tests are organized into four test classes:

### 1. TestMQTTGatewayMessageFlow

Tests message forwarding from mesh to MQTT broker with a real MQTT test broker.

**Tests:**
- `test_message_forwarding_to_real_broker` - Verifies messages are published to MQTT broker
- `test_topic_path_correctness` - Validates MQTT topic structure follows Meshtastic protocol
- `test_metadata_preservation` - Ensures SNR, RSSI, and timestamp are preserved

**Requirements Tested:** 4.1, 10.1, 10.2

**Note:** These tests require `paho-mqtt` library and connection to `test.mosquitto.org`. They will be skipped if the broker is unavailable.

### 2. TestMQTTGatewayReconnection

Tests connection loss and recovery behavior.

**Tests:**
- `test_message_queuing_when_disconnected` - Verifies messages are queued when broker unavailable
- `test_queue_processing_after_reconnection` - Validates queued messages are sent after reconnection
- `test_exponential_backoff_on_reconnection` - Confirms exponential backoff is used for reconnection

**Requirements Tested:** 8.2, 8.3

### 3. TestMQTTGatewayRateLimiting

Tests rate limiting under high message load.

**Tests:**
- `test_rate_limit_enforcement_under_load` - Verifies rate limits are enforced
- `test_rate_limiter_allows_burst` - Confirms initial burst is allowed
- `test_rate_limiter_backoff_behavior` - Validates backoff when limit exceeded

**Requirements Tested:** 7.1, 7.2

### 4. TestMQTTGatewayComponentIntegration

Tests component wiring and integration (no external dependencies).

**Tests:**
- `test_plugin_initialization_wires_components` - Verifies all components are initialized
- `test_message_filtering_with_uplink_disabled` - Tests channel filtering
- `test_message_filtering_with_uplink_enabled` - Tests message pass-through
- `test_health_status_includes_queue_size` - Validates health status reporting

## Running the Tests

### Run all integration tests (requires MQTT broker):
```bash
python -m pytest tests/integration/test_mqtt_gateway_integration.py -v
```

### Run tests without MQTT broker dependency:
```bash
python -m pytest tests/integration/test_mqtt_gateway_integration.py -v -k "not mqtt_subscriber"
```

### Run specific test class:
```bash
python -m pytest tests/integration/test_mqtt_gateway_integration.py::TestMQTTGatewayReconnection -v
```

## Test Configuration

The tests use a public MQTT test broker:
- **Broker:** test.mosquitto.org
- **Port:** 1883
- **Topic Prefix:** zephyrgate/test/{timestamp}

Each test run uses a unique topic prefix to avoid conflicts.

## Dependencies

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `paho-mqtt` - MQTT client (optional, tests will skip if not available)

## Known Issues

1. **Async Fixture Warning:** Tests using `mqtt_subscriber` fixture show a deprecation warning in pytest 9. This is expected and the tests work correctly.

2. **Broker Availability:** Tests requiring real MQTT broker will be skipped if `test.mosquitto.org` is unavailable.

3. **Timing Sensitivity:** Some tests (especially reconnection tests) may be sensitive to timing. If tests fail intermittently, increase wait times.

## Test Coverage

These integration tests cover:
- ✅ Message forwarding to MQTT broker
- ✅ Topic path generation (Meshtastic protocol compliance)
- ✅ Metadata preservation (SNR, RSSI, timestamp)
- ✅ Message queuing when disconnected
- ✅ Queue processing after reconnection
- ✅ Exponential backoff on reconnection
- ✅ Rate limit enforcement
- ✅ Burst handling
- ✅ Component initialization and wiring
- ✅ Channel filtering
- ✅ Health status reporting

## Future Enhancements

Potential improvements for integration tests:
- Add tests for TLS/SSL connections
- Test with multiple MQTT brokers
- Add performance benchmarks
- Test protobuf message format (currently only JSON)
- Add tests for message type filtering
- Test custom root topic configuration
