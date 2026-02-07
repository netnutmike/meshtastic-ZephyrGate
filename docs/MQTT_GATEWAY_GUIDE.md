# MQTT Gateway User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Basic Setup](#basic-setup)
5. [Configuration](#configuration)
6. [Common Use Cases](#common-use-cases)
7. [Advanced Configuration](#advanced-configuration)
8. [Meshtastic MQTT Protocol](#meshtastic-mqtt-protocol)
9. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
10. [Security](#security)
11. [Performance Tuning](#performance-tuning)
12. [FAQ](#faq)

## Introduction

The MQTT Gateway plugin enables ZephyrGate to forward messages from your Meshtastic mesh network to MQTT brokers. This creates a bridge between your local mesh network and cloud-based services, monitoring systems, or other MQTT-enabled applications.

### What is MQTT?

MQTT (Message Queuing Telemetry Transport) is a lightweight messaging protocol designed for IoT devices and low-bandwidth networks. It uses a publish-subscribe model where:
- **Publishers** send messages to topics
- **Subscribers** receive messages from topics they're interested in
- **Brokers** route messages between publishers and subscribers

### Why Use MQTT Gateway?

- **Remote Monitoring:** View mesh activity from anywhere with internet access
- **Data Integration:** Feed mesh data into databases, dashboards, or analytics platforms
- **Automation:** Trigger actions based on mesh events using tools like Node-RED or Home Assistant
- **Backup:** Archive mesh messages for historical analysis
- **Multi-Site:** Connect multiple mesh networks via MQTT

### Key Features

- ✅ **One-way uplink:** Forwards messages from mesh to MQTT (downlink not supported)
- ✅ **Protocol compliant:** Follows official Meshtastic MQTT standards
- ✅ **Non-blocking:** Doesn't interfere with ZephyrGate's core mesh functionality
- ✅ **Resilient:** Automatic reconnection and message queuing
- ✅ **Flexible:** Support for JSON and protobuf formats
- ✅ **Secure:** TLS/SSL encryption and authentication support

## Prerequisites

### Required

- ZephyrGate 1.0.0 or later installed and configured
- Working Meshtastic mesh network connection
- MQTT broker access (public or private)
- Internet connectivity (for remote brokers)

### Optional

- TLS/SSL certificates (for encrypted connections)
- MQTT broker credentials (if authentication required)

### MQTT Broker Options

**Public Brokers:**
- `mqtt.meshtastic.org` - Official Meshtastic public broker (free, no auth required)
- `test.mosquitto.org` - Eclipse test broker (free, no auth required)
- `broker.hivemq.com` - HiveMQ public broker (free, no auth required)

**Private Brokers:**
- Self-hosted Mosquitto
- AWS IoT Core
- Azure IoT Hub
- Google Cloud IoT Core
- CloudMQTT
- HiveMQ Cloud

## Installation

The MQTT Gateway plugin is included with ZephyrGate. No additional installation is required.

### Verify Installation

Check that the plugin is available:

```bash
ls plugins/mqtt_gateway/
```

You should see:
```
__init__.py
config_schema.json
manifest.yaml
message_formatter.py
message_queue.py
mqtt_client.py
plugin.py
rate_limiter.py
README.md
requirements.txt
```

### Install Dependencies

Dependencies are automatically installed when ZephyrGate starts. To manually install:

```bash
pip install -r plugins/mqtt_gateway/requirements.txt
```

This installs:
- `paho-mqtt` - MQTT client library
- `protobuf` - Protocol buffer support
- `meshtastic` - Meshtastic protobuf definitions

## Basic Setup

### Step 1: Enable the Plugin

Edit your `config.yaml` file:

```yaml
mqtt_gateway:
  enabled: true
```

### Step 2: Configure Broker Connection

Add broker details:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"
  region: "US"
```

### Step 3: Configure Channels

Specify which channels to forward:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Step 4: Restart ZephyrGate

```bash
# If running as a service
sudo systemctl restart zephyrgate

# If running manually
python main.py
```

### Step 5: Verify Connection

Check the logs for successful connection:

```bash
tail -f logs/zephyrgate.log | grep mqtt_gateway
```

Look for:
```
INFO: MQTT Gateway plugin initialized
INFO: Connected to MQTT broker at mqtt.meshtastic.org:1883
INFO: Registered with message router
```

## Configuration

### Complete Configuration Example

```yaml
mqtt_gateway:
  # Enable/disable plugin
  enabled: true
  
  # Broker connection
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  username: ""
  password: ""
  
  # TLS/SSL (optional)
  tls_enabled: false
  ca_cert: ""
  client_cert: ""
  client_key: ""
  
  # Topic configuration
  root_topic: "msh/US"
  region: "US"
  
  # Message format
  format: "json"  # or "protobuf"
  encryption_enabled: false
  
  # Rate limiting
  max_messages_per_second: 10
  burst_multiplier: 2
  
  # Message queue
  queue_max_size: 1000
  queue_persist: false
  
  # Reconnection
  reconnect_enabled: true
  reconnect_initial_delay: 1
  reconnect_max_delay: 60
  reconnect_multiplier: 2.0
  max_reconnect_attempts: -1
  
  # Logging
  log_level: "INFO"
  log_published_messages: true
  
  # Channel configuration
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position", "nodeinfo", "telemetry"]
```

### Configuration Parameters Explained

#### Broker Connection

**broker_address** (required)
- MQTT broker hostname or IP address
- Examples: `"mqtt.meshtastic.org"`, `"192.168.1.100"`, `"mqtt.example.com"`

**broker_port** (default: 1883)
- MQTT broker port number
- Standard ports: 1883 (plain), 8883 (TLS), 8080 (WebSocket)

**username** (optional)
- MQTT authentication username
- Leave empty if broker doesn't require authentication

**password** (optional)
- MQTT authentication password
- Leave empty if broker doesn't require authentication

#### TLS/SSL Configuration

**tls_enabled** (default: false)
- Enable TLS/SSL encryption for MQTT connection
- Recommended for production deployments

**ca_cert** (optional)
- Path to CA certificate file for verifying broker certificate
- Example: `"/etc/ssl/certs/ca-certificates.crt"`

**client_cert** (optional)
- Path to client certificate file for mutual TLS authentication
- Example: `"/path/to/client.crt"`

**client_key** (optional)
- Path to client private key file for mutual TLS authentication
- Example: `"/path/to/client.key"`

#### Topic Configuration

**root_topic** (default: "msh/US")
- Root MQTT topic path for all published messages
- Override to use custom topic hierarchy
- Must not contain `#` or `+` wildcards

**region** (default: "US")
- Geographic region code for topic structure
- Common values: US, EU, AU, CN, JP, etc.
- Used in default root_topic: `msh/{region}`

#### Message Format

**format** (default: "json")
- Message serialization format
- Options:
  - `"json"` - Human-readable JSON format (recommended for debugging)
  - `"protobuf"` - Binary protobuf format (more efficient)

**encryption_enabled** (default: false)
- Forward encrypted payloads without decryption
- When true: publishes to `/e/` topics with encrypted data
- When false: publishes to `/json/` topics with decrypted data

#### Rate Limiting

**max_messages_per_second** (default: 10)
- Maximum messages to publish per second
- Prevents overwhelming the broker
- Adjust based on broker limits and network capacity

**burst_multiplier** (default: 2)
- Token bucket burst capacity multiplier
- Allows short bursts above the rate limit
- Example: With limit=10 and multiplier=2, can burst up to 20 msg/sec briefly

#### Message Queue

**queue_max_size** (default: 1000)
- Maximum messages to queue when broker is unavailable
- Prevents memory exhaustion during extended outages
- Oldest messages are dropped when queue is full

**queue_persist** (default: false)
- Persist message queue to disk for crash recovery
- Enables recovery of queued messages after restart
- Adds disk I/O overhead

#### Reconnection

**reconnect_enabled** (default: true)
- Enable automatic reconnection to broker
- Recommended to keep enabled for reliability

**reconnect_initial_delay** (default: 1)
- Initial delay in seconds before first reconnection attempt
- Lower values reconnect faster but may overwhelm broker

**reconnect_max_delay** (default: 60)
- Maximum delay in seconds between reconnection attempts
- Prevents excessive wait times during extended outages

**reconnect_multiplier** (default: 2.0)
- Exponential backoff multiplier for reconnection delays
- Each attempt waits: `initial_delay * (multiplier ^ attempt_number)`
- Example: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped at max_delay)

**max_reconnect_attempts** (default: -1)
- Maximum number of reconnection attempts
- -1 = infinite attempts (recommended)
- Positive number = give up after N attempts

#### Logging

**log_level** (default: "INFO")
- Logging verbosity level
- Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Use DEBUG for troubleshooting

**log_published_messages** (default: true)
- Log details of each published message
- Disable for high-traffic networks to reduce log volume

#### Channel Configuration

Configure per-channel message forwarding:

```yaml
channels:
  - name: "LongFast"           # Channel name or number (required)
    uplink_enabled: true        # Enable forwarding (default: true)
    message_types:              # Filter by type (optional, empty = all)
      - "text"
      - "position"
```

**name** (required)
- Meshtastic channel name or number
- Examples: `"LongFast"`, `"0"`, `"Admin"`
- Must match channel configured in Meshtastic device

**uplink_enabled** (default: true)
- Enable message forwarding for this channel
- Set to false to disable forwarding without removing config

**message_types** (optional)
- List of message types to forward
- Empty list = forward all message types
- See [Message Types](#message-types) for available types

## Common Use Cases

### Use Case 1: Monitor Mesh Activity Remotely

Forward all messages to public Meshtastic MQTT server for remote monitoring:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Subscribe to messages:**
```bash
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/#" -v
```

### Use Case 2: Private Broker with Authentication

Connect to a private MQTT broker with username/password:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  broker_port: 1883
  username: "meshtastic_gateway"
  password: "secure_password_here"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Use Case 3: Secure Connection with TLS

Use TLS/SSL encryption for secure communication:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  broker_port: 8883
  username: "meshtastic_gateway"
  password: "secure_password_here"
  tls_enabled: true
  ca_cert: "/etc/ssl/certs/ca-certificates.crt"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Use Case 4: Selective Message Forwarding

Forward only text messages and GPS positions:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types:
        - "text"
        - "position"
    
    - name: "Admin"
      uplink_enabled: false  # Don't forward admin channel
```

### Use Case 5: Home Assistant Integration

Forward mesh data to Home Assistant via MQTT:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "homeassistant.local"
  broker_port: 1883
  username: "mqtt_user"
  password: "mqtt_password"
  root_topic: "homeassistant/meshtastic"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types:
        - "text"
        - "position"
        - "telemetry"
```

**Home Assistant Configuration:**
```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Mesh Node Battery"
      state_topic: "homeassistant/meshtastic/2/json/LongFast/+/telemetry"
      value_template: "{{ value_json.battery_level }}"
      unit_of_measurement: "%"
```

### Use Case 6: Data Logging to Database

Forward messages to MQTT broker, then use a subscriber to log to database:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  format: "json"
  region: "US"
  log_published_messages: false  # Reduce log volume
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Python subscriber example:**
```python
import paho.mqtt.client as mqtt
import json
import sqlite3

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    # Insert into database
    conn = sqlite3.connect('mesh_messages.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (sender, text, timestamp) VALUES (?, ?, ?)",
        (data['sender'], data['text'], data['timestamp'])
    )
    conn.commit()
    conn.close()

client = mqtt.Client()
client.on_message = on_message
client.connect("mqtt.example.com", 1883)
client.subscribe("msh/US/2/json/#")
client.loop_forever()
```

### Use Case 7: Multi-Site Mesh Network

Connect multiple ZephyrGate instances to share messages across sites:

**Site A Configuration:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  root_topic: "mesh/site_a"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Site B Configuration:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  root_topic: "mesh/site_b"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Bridge script to forward between sites:**
```python
import paho.mqtt.client as mqtt

def on_message_site_a(client, userdata, msg):
    # Forward Site A messages to Site B topic
    client.publish(msg.topic.replace("site_a", "site_b"), msg.payload)

def on_message_site_b(client, userdata, msg):
    # Forward Site B messages to Site A topic
    client.publish(msg.topic.replace("site_b", "site_a"), msg.payload)

client = mqtt.Client()
client.message_callback_add("mesh/site_a/#", on_message_site_a)
client.message_callback_add("mesh/site_b/#", on_message_site_b)
client.connect("mqtt.example.com", 1883)
client.subscribe("mesh/#")
client.loop_forever()
```

## Advanced Configuration

### Custom Topic Hierarchy

Override the default Meshtastic topic structure:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  root_topic: "company/iot/mesh/production"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Resulting topics:**
```
company/iot/mesh/production/2/json/LongFast/!a1b2c3d4
```

### High-Traffic Network Optimization

Optimize for networks with high message volume:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  format: "json"
  region: "US"
  
  # Increase rate limit
  max_messages_per_second: 100
  burst_multiplier: 3
  
  # Larger queue for buffering
  queue_max_size: 10000
  queue_persist: true
  
  # Faster reconnection
  reconnect_initial_delay: 0.5
  reconnect_max_delay: 30
  
  # Reduce logging overhead
  log_level: "WARNING"
  log_published_messages: false
  
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Multiple Channel Configuration

Configure different settings for each channel:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  format: "json"
  region: "US"
  channels:
    # Public channel - forward everything
    - name: "LongFast"
      uplink_enabled: true
    
    # Emergency channel - text only
    - name: "Emergency"
      uplink_enabled: true
      message_types: ["text"]
    
    # Telemetry channel - sensors only
    - name: "Sensors"
      uplink_enabled: true
      message_types: ["telemetry", "position"]
    
    # Admin channel - disabled
    - name: "Admin"
      uplink_enabled: false
```

### Encrypted Payload Forwarding

Forward encrypted messages without decryption:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  format: "protobuf"
  encryption_enabled: true
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Use cases:**
- Privacy: Keep message content encrypted in transit
- Compliance: Meet data protection requirements
- Efficiency: Skip decryption overhead

**Note:** Encrypted messages use `/e/` topic path and require decryption keys on subscriber side.

### Message Type Filtering

Filter messages by type to reduce bandwidth and storage:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types:
        - "text"          # Text messages
        - "position"      # GPS positions
        - "nodeinfo"      # Node information
        - "telemetry"     # Device telemetry
```

### Message Types

Available message types for filtering:

| Type | Description | Common Use |
|------|-------------|------------|
| `text` | Text messages | Chat, alerts, notifications |
| `position` | GPS coordinates | Tracking, mapping |
| `nodeinfo` | Node information | Network discovery |
| `telemetry` | Device metrics | Battery, temperature, voltage |
| `routing` | Routing protocol | Network topology |
| `admin` | Admin commands | Configuration, management |
| `traceroute` | Network trace | Diagnostics |
| `neighborinfo` | Neighbor data | Network analysis |
| `detection_sensor` | Sensor events | Motion, presence detection |
| `reply` | Reply messages | Acknowledgments |
| `ip_tunnel` | IP packets | Internet tunneling |
| `paxcounter` | People counter | Crowd monitoring |
| `serial` | Serial data | Device communication |
| `store_forward` | Delayed messages | Offline delivery |
| `range_test` | Range testing | Coverage analysis |
| `private` | Private messages | Direct messaging |
| `atak` | ATAK integration | Military/tactical |

## Meshtastic MQTT Protocol

The plugin implements the official [Meshtastic MQTT protocol](https://meshtastic.org/docs/software/integrations/mqtt/) for full compatibility with the Meshtastic ecosystem.

### Topic Structure

**JSON Format (Unencrypted):**
```
msh/{region}/2/json/{channel}/{nodeId}
```

**Protobuf Format (Encrypted):**
```
msh/{region}/2/e/{channel}/{nodeId}
```

**Components:**
- `msh` - Meshtastic namespace (or custom root_topic)
- `{region}` - Geographic region (US, EU, etc.)
- `2` - Protocol version
- `json/e` - Format indicator (json=plaintext, e=encrypted)
- `{channel}` - Channel name or number
- `{nodeId}` - Sender's node ID (e.g., !a1b2c3d4)

### JSON Message Format

Example JSON message:

```json
{
  "sender": "!a1b2c3d4",
  "from": 2748779460,
  "to": 4294967295,
  "channel": 0,
  "type": "text",
  "payload": {
    "text": "Hello from the mesh!"
  },
  "timestamp": 1705334445,
  "rxTime": 1705334445,
  "rxSnr": 9.5,
  "rxRssi": -45,
  "hopLimit": 3
}
```

**Field Descriptions:**
- `sender` - Node ID in hex format
- `from` - Sender node ID (decimal)
- `to` - Destination node ID (decimal, 4294967295 = broadcast)
- `channel` - Channel index
- `type` - Message type (text, position, etc.)
- `payload` - Message-specific data
- `timestamp` - Unix timestamp when sent
- `rxTime` - Unix timestamp when received
- `rxSnr` - Signal-to-noise ratio (dB)
- `rxRssi` - Received signal strength (dBm)
- `hopLimit` - Remaining hops

### Protobuf Message Format

Protobuf messages use the ServiceEnvelope structure:

```protobuf
message ServiceEnvelope {
  MeshPacket packet = 1;
  bytes channel_id = 2;
  bytes gateway_id = 3;
}
```

**Advantages:**
- Smaller message size (50-70% reduction)
- Faster serialization/deserialization
- Type safety with schema validation

**Disadvantages:**
- Not human-readable
- Requires protobuf library to decode
- More complex to debug

### Protocol Compliance

The plugin ensures full compliance with Meshtastic MQTT standards:

✅ **ServiceEnvelope Wrapping** - Protobuf messages wrapped correctly  
✅ **Topic Structure** - Standard topic hierarchy  
✅ **JSON Schema** - All required fields included  
✅ **Metadata Preservation** - Sender, timestamp, SNR/RSSI maintained  
✅ **Encrypted Pass-Through** - Encrypted payloads forwarded without modification

### Subscribing to Messages

**Subscribe to all messages in a region:**
```bash
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/#" -v
```

**Subscribe to specific channel:**
```bash
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/LongFast/#" -v
```

**Subscribe to specific node:**
```bash
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/LongFast/!a1b2c3d4" -v
```

**Subscribe with authentication:**
```bash
mosquitto_sub -h mqtt.example.com -u username -P password -t "msh/US/2/json/#" -v
```

**Subscribe with TLS:**
```bash
mosquitto_sub -h mqtt.example.com -p 8883 \
  --cafile /path/to/ca.crt \
  -u username -P password \
  -t "msh/US/2/json/#" -v
```

## Monitoring and Troubleshooting

### Health Status

Check plugin health via ZephyrGate API or logs:

```python
# Health status structure
{
    'healthy': True,              # Overall health
    'connected': True,            # MQTT broker connection
    'queue_size': 0,              # Messages in queue
    'messages_published': 1234,   # Total published
    'messages_dropped': 0,        # Dropped due to overflow
    'last_publish': '2024-01-15T10:30:45Z',
    'errors': 0                   # Publish error count
}
```

### Log Monitoring

**View real-time logs:**
```bash
tail -f logs/zephyrgate.log | grep mqtt_gateway
```

**Key log messages:**

**Successful connection:**
```
INFO: MQTT Gateway plugin initialized
INFO: Connected to MQTT broker at mqtt.meshtastic.org:1883
INFO: Registered with message router
```

**Message forwarding:**
```
INFO: Published message to msh/US/2/json/LongFast/!a1b2c3d4
DEBUG: Message: {"sender": "!a1b2c3d4", "type": "text", ...}
```

**Connection issues:**
```
ERROR: Failed to connect to MQTT broker: Connection refused
WARNING: MQTT connection lost, entering recovery mode
INFO: Reconnection attempt 3 failed: Connection timeout
INFO: MQTT connection restored after 5 attempts
```

**Queue events:**
```
WARNING: Message queue size: 500/1000
WARNING: Message queue full, dropping oldest message
INFO: Processing 250 queued messages after reconnection
```

**Rate limiting:**
```
DEBUG: Rate limit reached, queuing message
DEBUG: Waiting 0.5s for rate limit token
```

### Common Issues and Solutions

#### Issue: Plugin Not Starting

**Symptoms:**
- No MQTT gateway logs
- Plugin not listed in active plugins

**Solutions:**
1. Verify `enabled: true` in config.yaml
2. Check for configuration syntax errors
3. Verify dependencies installed: `pip list | grep paho-mqtt`
4. Check ZephyrGate logs for initialization errors

#### Issue: Cannot Connect to Broker

**Symptoms:**
```
ERROR: Failed to connect to MQTT broker: Connection refused
```

**Solutions:**
1. Verify broker address and port:
   ```bash
   ping mqtt.meshtastic.org
   telnet mqtt.meshtastic.org 1883
   ```
2. Check firewall rules allow outbound MQTT traffic
3. Verify credentials if authentication required
4. Try different broker to isolate issue
5. Enable debug logging:
   ```yaml
   mqtt_gateway:
     log_level: "DEBUG"
   ```

#### Issue: TLS Connection Fails

**Symptoms:**
```
ERROR: TLS handshake failed: certificate verify failed
```

**Solutions:**
1. Verify CA certificate path is correct
2. Check certificate hasn't expired:
   ```bash
   openssl x509 -in /path/to/ca.crt -noout -dates
   ```
3. Verify certificate matches broker hostname
4. Update CA certificates:
   ```bash
   sudo update-ca-certificates
   ```
5. Test without TLS to isolate issue

#### Issue: Messages Not Forwarding

**Symptoms:**
- Plugin connected but no messages published
- Empty MQTT topics

**Solutions:**
1. Verify channel configuration matches Meshtastic channels
2. Check `uplink_enabled: true` for channel
3. Verify message type filters aren't too restrictive
4. Check rate limiting isn't blocking messages
5. Monitor queue size for backlog
6. Enable message logging:
   ```yaml
   mqtt_gateway:
     log_published_messages: true
     log_level: "DEBUG"
   ```

#### Issue: High Latency

**Symptoms:**
- Long delay between mesh receipt and MQTT publish
- Messages arrive out of order

**Solutions:**
1. Check network latency to broker:
   ```bash
   ping mqtt.meshtastic.org
   ```
2. Increase rate limit if broker supports it:
   ```yaml
   mqtt_gateway:
     max_messages_per_second: 50
   ```
3. Use geographically closer broker
4. Disable message logging to reduce overhead
5. Check queue size - large queue indicates backlog

#### Issue: Queue Overflow

**Symptoms:**
```
WARNING: Message queue full (1000 messages), dropping oldest message
WARNING: Dropped 15 messages due to queue overflow
```

**Solutions:**
1. Increase queue size:
   ```yaml
   mqtt_gateway:
     queue_max_size: 5000
   ```
2. Fix broker connection issues causing queue buildup
3. Reduce message volume with type filtering
4. Increase rate limit if broker supports it
5. Enable queue persistence:
   ```yaml
   mqtt_gateway:
     queue_persist: true
   ```

#### Issue: Reconnection Loops

**Symptoms:**
- Continuous connect/disconnect cycles
- Logs show repeated reconnection attempts

**Solutions:**
1. Increase reconnection delays:
   ```yaml
   mqtt_gateway:
     reconnect_initial_delay: 5
     reconnect_max_delay: 300
   ```
2. Check broker logs for disconnect reasons
3. Verify credentials are correct
4. Check for broker-side rate limiting or connection limits
5. Reduce message rate to avoid overwhelming broker

### Debugging Tips

**Enable Debug Logging:**
```yaml
mqtt_gateway:
  log_level: "DEBUG"
  log_published_messages: true
```

**Test MQTT Connection:**
```bash
# Test publish
mosquitto_pub -h mqtt.meshtastic.org -t "test/topic" -m "test message"

# Test subscribe
mosquitto_sub -h mqtt.meshtastic.org -t "test/topic" -v
```

**Monitor MQTT Traffic:**
```bash
# Subscribe to all topics
mosquitto_sub -h mqtt.meshtastic.org -t "#" -v

# Subscribe to specific region
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/#" -v
```

**Check Network Connectivity:**
```bash
# Test DNS resolution
nslookup mqtt.meshtastic.org

# Test TCP connection
telnet mqtt.meshtastic.org 1883

# Test TLS connection
openssl s_client -connect mqtt.meshtastic.org:8883
```

**Validate Configuration:**
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Validate against schema
python -c "import json; json.load(open('plugins/mqtt_gateway/config_schema.json'))"
```

## Security

### Best Practices

1. **Use TLS/SSL in Production**
   ```yaml
   mqtt_gateway:
     tls_enabled: true
     broker_port: 8883
   ```

2. **Strong Authentication**
   - Use strong passwords (16+ characters)
   - Rotate credentials regularly
   - Use client certificates when possible

3. **Secure Credential Storage**
   - Use environment variables:
     ```yaml
     mqtt_gateway:
       username: "${MQTT_USERNAME}"
       password: "${MQTT_PASSWORD}"
     ```
   - Restrict config file permissions:
     ```bash
     chmod 600 config.yaml
     ```

4. **Limit Message Exposure**
   - Filter sensitive message types
   - Use encryption for sensitive data
   - Disable admin channel forwarding:
     ```yaml
     channels:
       - name: "Admin"
         uplink_enabled: false
     ```

5. **Network Security**
   - Use VPN for remote broker access
   - Implement firewall rules
   - Use private broker instead of public

6. **Monitor Access**
   - Enable broker access logs
   - Monitor for unauthorized connections
   - Set up alerts for suspicious activity

### TLS/SSL Configuration

**Generate Self-Signed Certificates:**
```bash
# Generate CA key and certificate
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.crt

# Generate server key and certificate
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365

# Generate client key and certificate
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt -days 365
```

**Configure Mutual TLS:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  broker_port: 8883
  tls_enabled: true
  ca_cert: "/path/to/ca.crt"
  client_cert: "/path/to/client.crt"
  client_key: "/path/to/client.key"
```

### Access Control

**Broker-Side ACLs (Mosquitto Example):**
```
# /etc/mosquitto/acl
user meshtastic_gateway
topic write msh/US/2/json/#
topic write msh/US/2/e/#

user monitoring_user
topic read msh/US/2/json/#
```

**Topic-Based Isolation:**
```yaml
# Gateway 1 - Site A
mqtt_gateway:
  root_topic: "mesh/site_a"

# Gateway 2 - Site B
mqtt_gateway:
  root_topic: "mesh/site_b"
```

## Performance Tuning

### Optimizing Throughput

**For Low-Traffic Networks (< 10 msg/sec):**
```yaml
mqtt_gateway:
  max_messages_per_second: 10
  queue_max_size: 500
  log_published_messages: true
```

**For Medium-Traffic Networks (10-50 msg/sec):**
```yaml
mqtt_gateway:
  max_messages_per_second: 50
  burst_multiplier: 3
  queue_max_size: 2000
  log_published_messages: false
  log_level: "INFO"
```

**For High-Traffic Networks (> 50 msg/sec):**
```yaml
mqtt_gateway:
  max_messages_per_second: 100
  burst_multiplier: 5
  queue_max_size: 10000
  queue_persist: true
  log_published_messages: false
  log_level: "WARNING"
  format: "protobuf"  # More efficient than JSON
```

### Memory Optimization

**Reduce Memory Usage:**
```yaml
mqtt_gateway:
  queue_max_size: 500          # Smaller queue
  queue_persist: false         # No disk caching
  log_published_messages: false
```

**Memory Usage Estimates:**
- Queue (1000 messages): ~5-10 MB
- Queue (10000 messages): ~50-100 MB
- Per message overhead: ~5-10 KB

### Network Optimization

**Reduce Bandwidth:**
```yaml
mqtt_gateway:
  format: "protobuf"           # 50-70% smaller than JSON
  encryption_enabled: true     # Skip decryption overhead
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text"]  # Filter unnecessary types
```

**Bandwidth Estimates:**
- JSON message: ~500-1000 bytes
- Protobuf message: ~200-400 bytes
- 10 msg/sec JSON: ~5-10 KB/sec
- 10 msg/sec Protobuf: ~2-4 KB/sec

### CPU Optimization

**Reduce CPU Usage:**
```yaml
mqtt_gateway:
  format: "protobuf"           # Faster serialization
  log_level: "WARNING"         # Less logging overhead
  log_published_messages: false
```

**CPU Usage Estimates:**
- JSON serialization: ~0.1ms per message
- Protobuf serialization: ~0.05ms per message
- Rate limiting: Negligible
- Queue operations: Negligible

### Latency Optimization

**Minimize Latency:**
```yaml
mqtt_gateway:
  max_messages_per_second: 100  # Higher rate limit
  reconnect_initial_delay: 0.5  # Faster reconnection
  reconnect_max_delay: 30
```

**Latency Sources:**
- Serialization: < 1ms
- Network RTT: 10-100ms (depends on broker location)
- Rate limiting: 0-100ms (depends on rate)
- Queue processing: < 1ms

### Broker Selection

**Choose Broker Based on Requirements:**

| Requirement | Recommended Broker |
|-------------|-------------------|
| Low latency | Geographically close broker |
| High throughput | Dedicated broker with high limits |
| Reliability | Managed service (AWS IoT, Azure IoT) |
| Cost | Public broker (mqtt.meshtastic.org) |
| Security | Private broker with TLS |

## FAQ

### General Questions

**Q: Does MQTT Gateway support downlink (MQTT to mesh)?**  
A: No, the current version only supports uplink (mesh to MQTT). Downlink support may be added in future versions.

**Q: Can I use multiple MQTT brokers simultaneously?**  
A: No, the plugin currently supports one broker at a time. You can use MQTT bridge functionality to forward messages between brokers.

**Q: Does the plugin work without internet connectivity?**  
A: The plugin requires network connectivity to the MQTT broker. However, ZephyrGate continues to operate normally for mesh functionality even if MQTT is unavailable.

**Q: What happens to messages when the broker is down?**  
A: Messages are queued in memory (up to `queue_max_size`). When the queue is full, oldest messages are dropped. Enable `queue_persist` to save the queue to disk.

**Q: Can I forward messages from multiple Meshtastic devices?**  
A: Yes, ZephyrGate receives messages from all devices on the mesh network and forwards them to MQTT.

### Configuration Questions

**Q: How do I find my Meshtastic channel name?**  
A: Check your Meshtastic device configuration or use the Meshtastic app. Common names: "LongFast", "MediumSlow", or numeric like "0", "1".

**Q: What's the difference between JSON and protobuf format?**  
A: JSON is human-readable and easier to debug. Protobuf is binary, more efficient (50-70% smaller), but requires decoding tools.

**Q: Should I enable encryption?**  
A: Enable `encryption_enabled: true` if you want to forward encrypted payloads without decryption. This maintains privacy but makes messages unreadable without decryption keys.

**Q: What rate limit should I use?**  
A: Start with default (10 msg/sec) and increase if needed. Public brokers may have limits around 10-50 msg/sec. Private brokers can handle 100+ msg/sec.

**Q: How do I know if my configuration is valid?**  
A: Check ZephyrGate logs for validation errors. The plugin validates configuration against the schema on startup.

### Technical Questions

**Q: What MQTT QoS level is used?**  
A: The plugin uses QoS 0 (at most once) by default for best performance. QoS 1 (at least once) may be added in future versions.

**Q: Does the plugin support MQTT 5.0?**  
A: The plugin uses paho-mqtt which supports both MQTT 3.1.1 and 5.0. The protocol version is negotiated automatically.

**Q: Can I use WebSocket MQTT?**  
A: Not directly. Use a standard MQTT connection. If you need WebSocket, use an MQTT broker that bridges WebSocket to standard MQTT.

**Q: How does exponential backoff work?**  
A: Reconnection delay doubles each attempt: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped at `reconnect_max_delay`).

**Q: What happens if serialization fails?**  
A: The plugin logs the error and skips the message. Other messages continue to be processed normally.

**Q: Are messages published in order?**  
A: Yes, messages are published in the order received from the mesh network, subject to rate limiting and queuing.

### Troubleshooting Questions

**Q: Why aren't my messages appearing on MQTT?**  
A: Check: 1) Plugin enabled, 2) Broker connected, 3) Channel configured, 4) `uplink_enabled: true`, 5) Message type not filtered.

**Q: Why is the plugin constantly reconnecting?**  
A: Possible causes: 1) Invalid credentials, 2) Broker rate limiting, 3) Network instability, 4) Broker connection limits.

**Q: Why are messages being dropped?**  
A: Queue is full due to: 1) Broker disconnected, 2) Rate limit too low, 3) High message volume. Increase `queue_max_size` or fix connection.

**Q: How do I reduce log volume?**  
A: Set `log_level: "WARNING"` and `log_published_messages: false`.

**Q: Why is latency high?**  
A: Check: 1) Network latency to broker, 2) Rate limiting delays, 3) Queue backlog, 4) Broker processing time.

### Integration Questions

**Q: How do I integrate with Home Assistant?**  
A: Configure MQTT integration in Home Assistant, then create sensors/automations that subscribe to Meshtastic topics. See [Use Case 5](#use-case-5-home-assistant-integration).

**Q: Can I use this with Node-RED?**  
A: Yes, use Node-RED's MQTT input node to subscribe to Meshtastic topics and process messages.

**Q: How do I log messages to a database?**  
A: Create a subscriber script that receives MQTT messages and inserts them into your database. See [Use Case 6](#use-case-6-data-logging-to-database).

**Q: Can I forward messages to multiple systems?**  
A: Yes, multiple subscribers can connect to the same MQTT broker and receive all messages.

**Q: How do I bridge to another MQTT broker?**  
A: Use MQTT broker bridge functionality (Mosquitto) or create a custom bridge script that subscribes to one broker and publishes to another.

## Additional Resources

### Documentation

- **Plugin README:** `plugins/mqtt_gateway/README.md`
- **Configuration Schema:** `plugins/mqtt_gateway/config_schema.json`
- **ZephyrGate Documentation:** `docs/`

### External Resources

- **Meshtastic MQTT Protocol:** https://meshtastic.org/docs/software/integrations/mqtt/
- **MQTT Specification:** https://mqtt.org/mqtt-specification/
- **Paho MQTT Python:** https://www.eclipse.org/paho/index.php?page=clients/python/index.php
- **Mosquitto Broker:** https://mosquitto.org/
- **MQTT Explorer:** http://mqtt-explorer.com/

### Community

- **Meshtastic Discord:** https://discord.gg/meshtastic
- **Meshtastic Forum:** https://meshtastic.discourse.group/
- **GitHub Issues:** Report bugs and request features

### Example Configurations

See `examples/` directory for:
- Basic configuration examples
- Advanced use case configurations
- Integration examples (Home Assistant, Node-RED, etc.)
- Subscriber script examples

## Changelog

### Version 1.0.0 (Initial Release)

**Features:**
- One-way uplink (mesh to MQTT)
- JSON and protobuf message formats
- TLS/SSL encryption support
- Automatic reconnection with exponential backoff
- Message queuing when broker unavailable
- Configurable rate limiting
- Per-channel configuration
- Message type filtering
- Meshtastic MQTT protocol compliance

**Known Limitations:**
- No downlink support (MQTT to mesh)
- Single broker support only
- QoS 0 only
- No message persistence across restarts (unless `queue_persist` enabled)

**Future Enhancements:**
- Downlink support (MQTT to mesh)
- Multiple broker support
- QoS 1 and 2 support
- Message transformation/enrichment
- Metrics export (Prometheus)
- Web UI for monitoring

## Support

For help with MQTT Gateway:

1. **Check this guide** for configuration and troubleshooting
2. **Review logs** with debug logging enabled
3. **Test MQTT connection** independently using mosquitto_pub/sub
4. **Check broker status** and logs
5. **Report issues** on GitHub with logs and configuration (redact credentials)

## License

MQTT Gateway plugin is part of ZephyrGate and is licensed under GPL-3.0.

---

**Last Updated:** 2024-01-15  
**Plugin Version:** 1.0.0  
**ZephyrGate Version:** 1.0.0+
