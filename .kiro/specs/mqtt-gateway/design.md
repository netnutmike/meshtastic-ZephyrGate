# Design Document: MQTT Gateway Integration

## Overview

The MQTT Gateway is a plugin service for ZephyrGate that forwards Meshtastic mesh messages to MQTT brokers following the official Meshtastic MQTT protocol. This design implements a one-way (uplink only) gateway that publishes mesh messages to MQTT topics while maintaining ZephyrGate's ability to operate standalone without internet connectivity.

### Key Design Principles

1. **Optional and Non-Blocking**: The MQTT gateway operates as an optional plugin that doesn't interfere with core mesh functionality
2. **Async-First Architecture**: All MQTT operations use async/await patterns to prevent blocking the message router
3. **Resilient Connection Management**: Automatic reconnection with exponential backoff ensures reliable operation
4. **Protocol Compliance**: Strict adherence to Meshtastic MQTT protocol standards for interoperability
5. **Minimal Dependencies**: Uses standard Python MQTT libraries (paho-mqtt) with minimal additional dependencies

### Architecture Context

The MQTT Gateway integrates into ZephyrGate's existing plugin architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      ZephyrGate Core                        │
│                                                             │
│  ┌──────────────┐      ┌─────────────────┐                │
│  │  Meshtastic  │─────▶│ Message Router  │                │
│  │  Interface   │      │                 │                │
│  └──────────────┘      └────────┬────────┘                │
│                                  │                          │
│                                  ├──▶ Bot Service           │
│                                  ├──▶ Weather Service       │
│                                  ├──▶ BBS Service           │
│                                  │                          │
│                                  ├──▶ MQTT Gateway (NEW)    │
│                                  │     │                    │
│                                  │     ├─ Message Queue    │
│                                  │     ├─ Rate Limiter     │
│                                  │     └─ MQTT Client      │
│                                  │           │              │
└──────────────────────────────────┼───────────┼──────────────┘
                                   │           │
                                   │           ▼
                                   │    ┌──────────────┐
                                   │    │ MQTT Broker  │
                                   │    │ (External)   │
                                   │    └──────────────┘
                                   │
                                   ▼
                            Other Services
```

## Architecture

### Component Structure

The MQTT Gateway is implemented as a ZephyrGate plugin with the following components:

```
plugins/mqtt_gateway/
├── __init__.py
├── plugin.py              # Main plugin class (MQTTGatewayPlugin)
├── mqtt_client.py         # MQTT connection management
├── message_formatter.py   # Meshtastic protocol formatting
├── message_queue.py       # Message queuing and retry logic
├── rate_limiter.py        # Rate limiting implementation
├── config_schema.json     # Configuration validation schema
├── manifest.yaml          # Plugin metadata
└── requirements.txt       # paho-mqtt dependency
```

### Core Components

#### 1. MQTTGatewayPlugin

The main plugin class that implements the ZephyrGate plugin interface.

**Responsibilities:**
- Plugin lifecycle management (initialize, start, stop)
- Configuration loading and validation
- Registration with message router
- Coordination between sub-components

**Key Methods:**
```python
async def initialize(config: Dict[str, Any]) -> bool
async def start() -> bool
async def stop() -> bool
async def handle_message(message: Message) -> Optional[str]
async def get_health_status() -> Dict[str, Any]
```

#### 2. MQTTClient

Manages the MQTT broker connection using paho-mqtt library.

**Responsibilities:**
- Establish and maintain MQTT broker connection
- Handle TLS/SSL configuration
- Implement reconnection logic with exponential backoff
- Publish messages to MQTT topics
- Track connection state and statistics

**Key Methods:**
```python
async def connect() -> bool
async def disconnect() -> None
async def publish(topic: str, payload: bytes, qos: int = 0) -> bool
async def reconnect() -> bool
def is_connected() -> bool
```

**Connection State Machine:**
```
┌─────────────┐
│ DISCONNECTED│
└──────┬──────┘
       │ connect()
       ▼
┌─────────────┐
│ CONNECTING  │
└──────┬──────┘
       │ on_connect
       ▼
┌─────────────┐     connection_lost
│  CONNECTED  │◀────────────────────┐
└──────┬──────┘                     │
       │ disconnect()               │
       ▼                            │
┌─────────────┐     reconnect()    │
│DISCONNECTING│─────────────────────┘
└─────────────┘
```

#### 3. MessageFormatter

Formats Meshtastic messages according to the Meshtastic MQTT protocol.

**Responsibilities:**
- Convert Message objects to protobuf ServiceEnvelope
- Serialize messages to JSON format
- Generate appropriate MQTT topic paths
- Handle encryption/decryption based on configuration

**Key Methods:**
```python
def format_protobuf(message: Message) -> bytes
def format_json(message: Message) -> str
def get_topic_path(message: Message, encrypted: bool) -> str
def should_forward_message(message: Message) -> bool
```

**Topic Path Generation:**
```
Encrypted: msh/{region}/2/e/{channel}/{nodeId}
JSON:      msh/{region}/2/json/{channel}/{nodeId}

Where:
- region: Configured region (e.g., "US", "EU")
- channel: Meshtastic channel name or number
- nodeId: Sender's node ID (e.g., "!a1b2c3d4")
```

#### 4. MessageQueue

Implements a persistent queue for messages when MQTT broker is unavailable.

**Responsibilities:**
- Queue messages when broker is disconnected
- Implement FIFO ordering with priority support
- Enforce maximum queue size limits
- Persist queue to disk for crash recovery (optional)

**Key Methods:**
```python
async def enqueue(message: Message, priority: int = 0) -> bool
async def dequeue() -> Optional[Message]
def size() -> int
def is_full() -> bool
async def clear() -> None
```

**Queue Behavior:**
- Maximum size: 1000 messages (configurable)
- Overflow strategy: Drop oldest messages
- Priority levels: Emergency (3), High (2), Normal (1), Low (0)

#### 5. RateLimiter

Implements token bucket rate limiting to respect broker limits.

**Responsibilities:**
- Enforce configurable message rate limits
- Implement exponential backoff on rate limit errors
- Track rate limit statistics

**Key Methods:**
```python
async def acquire() -> bool
async def wait_if_needed() -> None
def get_wait_time() -> float
def reset() -> None
```

**Rate Limiting Algorithm:**
```
Token Bucket:
- Capacity: max_messages_per_second * burst_multiplier
- Refill rate: max_messages_per_second tokens/second
- Cost per message: 1 token

Exponential Backoff:
- Initial delay: 1 second
- Max delay: 60 seconds
- Multiplier: 2.0
```

## Components and Interfaces

### Plugin Interface

The MQTT Gateway implements the standard ZephyrGate plugin interface:

```python
class MQTTGatewayPlugin:
    """MQTT Gateway plugin for ZephyrGate"""
    
    def __init__(self):
        self.name = "mqtt_gateway"
        self.version = "1.0.0"
        self.config = {}
        self.mqtt_client = None
        self.message_queue = None
        self.rate_limiter = None
        self.formatter = None
        self.enabled = False
        self.logger = None
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize plugin with configuration"""
        pass
    
    async def start(self) -> bool:
        """Start the plugin"""
        pass
    
    async def stop(self) -> bool:
        """Stop the plugin"""
        pass
    
    async def handle_message(self, message: Message) -> Optional[str]:
        """Handle incoming message from mesh"""
        pass
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get plugin health status"""
        pass
```

### Message Router Integration

The plugin registers with the message router to receive all mesh messages:

```python
# In plugin.py
async def start(self) -> bool:
    # Register with message router
    if self.message_router:
        self.message_router.register_service("mqtt_gateway", self)
        self.logger.info("Registered with message router")
    
    # Start MQTT client
    await self.mqtt_client.connect()
    
    # Start background tasks
    asyncio.create_task(self._process_queue())
    
    return True
```

### MQTT Client Interface

The MQTT client wraps paho-mqtt with async support:

```python
class MQTTClient:
    """Async MQTT client wrapper"""
    
    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.client = mqtt.Client()
        self.connected = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
    async def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            # Configure TLS if enabled
            if self.config.get('tls_enabled', False):
                self.client.tls_set(
                    ca_certs=self.config.get('ca_cert'),
                    certfile=self.config.get('client_cert'),
                    keyfile=self.config.get('client_key')
                )
            
            # Set credentials
            if self.config.get('username'):
                self.client.username_pw_set(
                    self.config['username'],
                    self.config.get('password')
                )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # Connect
            self.client.connect_async(
                self.config['broker_address'],
                self.config.get('broker_port', 1883),
                keepalive=60
            )
            
            self.client.loop_start()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
```

## Data Models

### Configuration Schema

```yaml
mqtt_gateway:
  enabled: false  # Default: disabled
  
  # Broker connection
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  username: ""
  password: ""
  
  # TLS/SSL
  tls_enabled: false
  ca_cert: ""
  client_cert: ""
  client_key: ""
  
  # Topic configuration
  root_topic: "msh/US"  # Default: msh/{region}
  region: "US"
  
  # Message format
  format: "json"  # Options: "json", "protobuf"
  encryption_enabled: false
  
  # Channel configuration
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position", "nodeinfo", "telemetry"]
    
    - name: "0"  # Primary channel
      uplink_enabled: true
      message_types: ["text"]
  
  # Rate limiting
  max_messages_per_second: 10
  burst_multiplier: 2
  
  # Queue configuration
  queue_max_size: 1000
  queue_persist: false
  
  # Reconnection
  reconnect_enabled: true
  reconnect_initial_delay: 1
  reconnect_max_delay: 60
  reconnect_multiplier: 2.0
  max_reconnect_attempts: -1  # -1 = infinite
  
  # Logging
  log_level: "INFO"
  log_published_messages: true
```

### Internal Data Structures

```python
@dataclass
class QueuedMQTTMessage:
    """Message queued for MQTT publishing"""
    message: Message
    topic: str
    payload: bytes
    qos: int
    priority: int
    timestamp: datetime
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class MQTTStats:
    """MQTT gateway statistics"""
    messages_published: int = 0
    messages_queued: int = 0
    messages_dropped: int = 0
    publish_errors: int = 0
    connection_count: int = 0
    disconnection_count: int = 0
    last_publish_time: Optional[datetime] = None
    queue_size: int = 0
    connected: bool = False
```

## Correctness Properties


*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Topic Path Format for Encrypted Messages

*For any* Meshtastic message with encryption enabled, the generated MQTT topic path should match the format msh/{region}/2/e/{channel}/{nodeId} where region, channel, and nodeId are extracted from the message and configuration.

**Validates: Requirements 3.1, 6.3**

### Property 2: Topic Path Format for JSON Messages

*For any* Meshtastic message with JSON format enabled, the generated MQTT topic path should match the format msh/{region}/2/json/{channel}/{nodeId} where region, channel, and nodeId are extracted from the message and configuration.

**Validates: Requirements 3.2, 6.4**

### Property 3: Custom Root Topic Override

*For any* configured root topic value, all generated MQTT topic paths should start with the configured root topic instead of the default "msh/{region}".

**Validates: Requirements 3.5**

### Property 4: Protobuf ServiceEnvelope Wrapping

*For any* message formatted as protobuf, the output should be a valid ServiceEnvelope structure that can be deserialized using Meshtastic protobuf definitions.

**Validates: Requirements 3.3, 5.1**

### Property 5: JSON Schema Compliance

*For any* message formatted as JSON, the output should be valid JSON containing all required Meshtastic fields (sender, timestamp, channel, payload) according to the Meshtastic JSON schema.

**Validates: Requirements 3.4, 5.2**

### Property 6: Channel Uplink Filtering

*For any* message from a channel, the message should be forwarded to MQTT if and only if uplink is enabled for that channel in the configuration.

**Validates: Requirements 4.2, 4.3**

### Property 7: Message Metadata Preservation

*For any* message forwarded to MQTT, the serialized output should contain the original sender Node_ID, timestamp, and signal quality (SNR/RSSI) from the source message.

**Validates: Requirements 4.4**

### Property 8: Queue Overflow Behavior

*For any* message queue at maximum capacity, adding a new message should result in the oldest message being removed and the new message being added, maintaining the queue size at the maximum.

**Validates: Requirements 4.6, 7.4**

### Property 9: Message Queuing When Disconnected

*For any* message received when the MQTT broker connection is unavailable, the message should be added to the queue for later transmission.

**Validates: Requirements 4.5, 7.3**

### Property 10: Encrypted Payload Pass-Through

*For any* message with encryption enabled, the encrypted payload bytes should be forwarded to MQTT without modification or decryption attempts.

**Validates: Requirements 6.1**

### Property 11: Exponential Backoff Calculation

*For any* reconnection attempt number N, the backoff delay should be min(initial_delay * (multiplier ^ N), max_delay) where initial_delay, multiplier, and max_delay are configuration parameters.

**Validates: Requirements 2.5, 2.6, 7.2, 8.2**

### Property 12: Rate Limit Enforcement

*For any* sequence of message publish attempts, the number of messages published in any 1-second window should not exceed the configured max_messages_per_second limit.

**Validates: Requirements 7.1**

### Property 13: Configuration Validation

*For any* configuration object, all required parameters should either be present with valid values or have sensible defaults applied, and invalid configurations should be rejected with descriptive error messages.

**Validates: Requirements 9.2, 9.3**

### Property 14: Message Type Filtering

*For any* message with a specific message type, the message should be forwarded to MQTT if and only if either no message type filter is configured or the message type is included in the configured filter list.

**Validates: Requirements 12.1, 12.2, 12.3**

## Error Handling

### Connection Errors

**Broker Unreachable:**
- Log error with broker details
- Enter reconnection loop with exponential backoff
- Queue messages for later transmission
- Continue accepting messages from mesh

**Authentication Failure:**
- Log authentication error with username (not password)
- Disable MQTT gateway
- Alert operator via logs
- Continue mesh operations

**TLS/SSL Errors:**
- Log certificate validation errors
- Disable MQTT gateway if TLS is required
- Fall back to unencrypted if TLS is optional
- Alert operator via logs

### Message Processing Errors

**Serialization Failure:**
- Log error with message details
- Skip the problematic message
- Continue processing other messages
- Increment error counter in statistics

**Invalid Message Format:**
- Log warning with message type
- Skip unsupported message types
- Continue processing other messages
- Track skipped message types in statistics

**Queue Overflow:**
- Log warning with queue size
- Drop oldest message
- Add new message to queue
- Increment dropped message counter

### Rate Limiting Errors

**Broker Rate Limit Exceeded:**
- Detect rate limit error from broker
- Enter exponential backoff
- Queue messages during backoff
- Resume normal operation after backoff

**Local Rate Limit Exceeded:**
- Wait for token bucket to refill
- Queue message if wait time exceeds threshold
- Log rate limit events at debug level
- Track rate limit statistics

### Recovery Procedures

**Connection Recovery:**
```python
async def recover_connection():
    """Recover from connection loss"""
    # 1. Log disconnection
    logger.warning("MQTT connection lost, entering recovery mode")
    
    # 2. Start reconnection loop
    attempt = 0
    while not connected and attempt < max_attempts:
        delay = calculate_backoff(attempt)
        await asyncio.sleep(delay)
        
        try:
            await connect()
            logger.info("MQTT connection restored")
            break
        except Exception as e:
            logger.error(f"Reconnection attempt {attempt} failed: {e}")
            attempt += 1
    
    # 3. Process queued messages
    if connected:
        await process_queue()
```

**Queue Recovery:**
```python
async def recover_queue():
    """Process queued messages after reconnection"""
    logger.info(f"Processing {queue.size()} queued messages")
    
    processed = 0
    failed = 0
    
    while not queue.is_empty():
        message = await queue.dequeue()
        
        try:
            await publish_message(message)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to publish queued message: {e}")
            failed += 1
            
            # Re-queue if retries remain
            if message.retry_count < message.max_retries:
                message.retry_count += 1
                await queue.enqueue(message)
    
    logger.info(f"Queue recovery complete: {processed} published, {failed} failed")
```

## Testing Strategy

### Dual Testing Approach

The MQTT Gateway will be tested using both unit tests and property-based tests:

**Unit Tests:**
- Configuration parsing and validation
- Specific message type serialization (TEXT_MESSAGE_APP, TELEMETRY_APP, etc.)
- Error handling for invalid inputs
- Connection state transitions
- Queue operations (enqueue, dequeue, overflow)

**Property-Based Tests:**
- Topic path generation for all message combinations
- Message metadata preservation across serialization
- Queue overflow behavior with random message sequences
- Rate limiting with random message arrival patterns
- Backoff calculation for all attempt numbers
- Configuration validation with random parameter combinations

### Property-Based Testing Configuration

All property tests will use the Hypothesis library for Python with the following configuration:
- Minimum 100 iterations per test
- Each test tagged with: **Feature: mqtt-gateway, Property {number}: {property_text}**
- Custom generators for Message objects, configuration dictionaries, and MQTT topics

### Test Organization

```
tests/
├── unit/
│   └── mqtt_gateway/
│       ├── test_config.py
│       ├── test_formatter.py
│       ├── test_queue.py
│       ├── test_rate_limiter.py
│       └── test_mqtt_client.py
│
└── property/
    └── mqtt_gateway/
        ├── test_topic_generation.py
        ├── test_message_serialization.py
        ├── test_queue_behavior.py
        ├── test_rate_limiting.py
        └── test_configuration.py
```

### Example Property Test

```python
from hypothesis import given, strategies as st
import pytest

@given(
    message=message_strategy(),
    region=st.text(min_size=2, max_size=10),
    encrypted=st.booleans()
)
def test_topic_path_format(message, region, encrypted):
    """
    Feature: mqtt-gateway, Property 1: Topic Path Format for Encrypted Messages
    Feature: mqtt-gateway, Property 2: Topic Path Format for JSON Messages
    
    For any message, the generated topic path should match the expected format.
    """
    formatter = MessageFormatter(config={'region': region})
    topic = formatter.get_topic_path(message, encrypted=encrypted)
    
    # Verify topic structure
    parts = topic.split('/')
    assert len(parts) == 5
    assert parts[0] == 'msh'
    assert parts[1] == region
    assert parts[2] == '2'
    assert parts[3] in ['e', 'json']
    assert parts[4] == message.sender_id
    
    # Verify encryption flag matches topic type
    if encrypted:
        assert parts[3] == 'e'
    else:
        assert parts[3] == 'json'
```

### Integration Testing

Integration tests will verify:
- Message flow from Meshtastic interface through message router to MQTT gateway
- MQTT broker connectivity with real broker (using test broker)
- End-to-end message forwarding with verification
- Reconnection behavior with simulated network failures
- Queue persistence and recovery

### Performance Testing

Performance tests will measure:
- Message throughput (messages per second)
- Latency from mesh receipt to MQTT publish
- Memory usage under load
- Queue performance with large message volumes
- Rate limiter overhead

## Implementation Notes

### Dependencies

**Required Python Packages:**
- `paho-mqtt>=1.6.1` - MQTT client library
- `protobuf>=3.20.0` - Protobuf serialization
- `meshtastic>=2.0.0` - Meshtastic protobuf definitions

**Optional Dependencies:**
- `hypothesis>=6.0.0` - Property-based testing (dev only)

### Meshtastic Protocol References

**Official Documentation:**
- MQTT Module: https://meshtastic.org/docs/configuration/module/mqtt/
- MQTT Integration: https://meshtastic.org/docs/software/integrations/mqtt/
- Protobuf Definitions: https://github.com/meshtastic/protobufs

**Topic Structure:**
```
msh/{region}/2/{format}/{channel}/{nodeId}

Where:
- region: Geographic region (US, EU, etc.)
- 2: Protocol version
- format: "e" (encrypted) or "json" (plaintext JSON)
- channel: Channel name or number
- nodeId: Sender's node ID (e.g., "!a1b2c3d4")
```

**ServiceEnvelope Structure:**
```protobuf
message ServiceEnvelope {
  MeshPacket packet = 1;
  bytes channel_id = 2;
  bytes gateway_id = 3;
}
```

### Configuration Best Practices

**Recommended Settings:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"  # More compatible than protobuf
  encryption_enabled: false  # Easier debugging
  max_messages_per_second: 5  # Conservative rate limit
  queue_max_size: 500  # Balance memory vs reliability
  reconnect_max_delay: 60  # Don't wait too long
```

**Security Considerations:**
- Use TLS/SSL for production deployments
- Store credentials in environment variables, not config files
- Use strong passwords for MQTT authentication
- Consider using client certificates for authentication
- Limit message types forwarded to reduce data exposure

### Async/Await Patterns

All MQTT operations use async/await to prevent blocking:

```python
async def handle_message(self, message: Message) -> Optional[str]:
    """Handle incoming message from mesh (non-blocking)"""
    # Quick validation
    if not self.should_forward(message):
        return None
    
    # Format message (CPU-bound, but fast)
    topic, payload = self.formatter.format_message(message)
    
    # Publish asynchronously (I/O-bound)
    asyncio.create_task(self._publish_async(topic, payload))
    
    # Return immediately, don't wait for publish
    return None

async def _publish_async(self, topic: str, payload: bytes):
    """Publish message asynchronously"""
    try:
        # Wait for rate limiter
        await self.rate_limiter.acquire()
        
        # Publish to MQTT
        if self.mqtt_client.is_connected():
            await self.mqtt_client.publish(topic, payload)
        else:
            # Queue for later
            await self.message_queue.enqueue(topic, payload)
    except Exception as e:
        self.logger.error(f"Publish failed: {e}")
```

### Plugin Lifecycle

```python
# Initialization
plugin = MQTTGatewayPlugin()
await plugin.initialize(config)

# Startup
await plugin.start()
# - Connects to MQTT broker
# - Starts background tasks
# - Registers with message router

# Runtime
# - Receives messages via handle_message()
# - Publishes to MQTT asynchronously
# - Manages queue and rate limiting

# Shutdown
await plugin.stop()
# - Disconnects from MQTT broker
# - Stops background tasks
# - Flushes message queue
# - Cleans up resources
```

### Monitoring and Observability

**Health Check Endpoint:**
```python
async def get_health_status(self) -> Dict[str, Any]:
    """Get plugin health status"""
    return {
        'healthy': self.mqtt_client.is_connected(),
        'connected': self.mqtt_client.is_connected(),
        'queue_size': self.message_queue.size(),
        'messages_published': self.stats.messages_published,
        'messages_dropped': self.stats.messages_dropped,
        'last_publish': self.stats.last_publish_time,
        'errors': self.stats.publish_errors
    }
```

**Metrics to Track:**
- Messages published (counter)
- Messages queued (gauge)
- Messages dropped (counter)
- Publish errors (counter)
- Connection uptime (gauge)
- Publish latency (histogram)
- Queue depth (histogram)

### Future Enhancements

**Potential Future Features:**
- Downlink support (MQTT to mesh)
- Message filtering by content/sender
- Multiple MQTT broker support
- Message transformation/enrichment
- Persistent queue storage
- Metrics export (Prometheus)
- Web UI for monitoring
- Map reporting integration
