# MQTT Gateway Plugin

## Overview

The MQTT Gateway plugin enables one-way message forwarding from your Meshtastic mesh network to MQTT brokers, following the official [Meshtastic MQTT protocol](https://meshtastic.org/docs/software/integrations/mqtt/). This allows you to integrate your mesh network with cloud services, monitoring systems, and other MQTT-based applications.

**Key Features:**
- ✅ Official Meshtastic MQTT protocol compliance
- ✅ Automatic reconnection with exponential backoff
- ✅ Message queuing when broker is unavailable
- ✅ Configurable rate limiting
- ✅ Support for both JSON and protobuf formats
- ✅ TLS/SSL encryption support
- ✅ Channel-based message filtering
- ✅ Optional and non-blocking (ZephyrGate works standalone without it)

## Quick Start

### 1. Enable the Plugin

Add the following to your `config.yaml`:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"
  region: "US"
```

### 2. Configure Channels

Specify which channels should forward messages to MQTT:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position", "nodeinfo", "telemetry"]
    
    - name: "0"  # Primary channel
      uplink_enabled: true
```

### 3. Restart ZephyrGate

The plugin will automatically connect to the MQTT broker and start forwarding messages.

## Configuration Reference

### Basic Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable or disable the MQTT gateway |
| `broker_address` | string | `"mqtt.meshtastic.org"` | MQTT broker hostname or IP |
| `broker_port` | integer | `1883` | MQTT broker port (1883 for plain, 8883 for TLS) |
| `username` | string | `""` | MQTT authentication username (optional) |
| `password` | string | `""` | MQTT authentication password (optional) |
| `format` | string | `"json"` | Message format: `"json"` or `"protobuf"` |
| `region` | string | `"US"` | Geographic region code (US, EU, etc.) |

### TLS/SSL Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tls_enabled` | boolean | `false` | Enable TLS/SSL encryption |
| `ca_cert` | string | `""` | Path to CA certificate file |
| `client_cert` | string | `""` | Path to client certificate file |
| `client_key` | string | `""` | Path to client private key file |

### Topic Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `root_topic` | string | `"msh/US"` | Root MQTT topic path |
| `encryption_enabled` | boolean | `false` | Forward encrypted payloads without decryption |

### Rate Limiting

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_messages_per_second` | integer | `10` | Maximum messages to publish per second |
| `burst_multiplier` | number | `2` | Burst capacity multiplier for token bucket |

### Message Queue

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `queue_max_size` | integer | `1000` | Maximum queued messages when broker unavailable |
| `queue_persist` | boolean | `false` | Persist queue to disk for crash recovery |

### Reconnection

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reconnect_enabled` | boolean | `true` | Enable automatic reconnection |
| `reconnect_initial_delay` | number | `1` | Initial delay (seconds) before reconnection |
| `reconnect_max_delay` | number | `60` | Maximum delay (seconds) between attempts |
| `reconnect_multiplier` | number | `2.0` | Exponential backoff multiplier |
| `max_reconnect_attempts` | integer | `-1` | Max reconnection attempts (-1 = infinite) |

### Logging

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_level` | string | `"INFO"` | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `log_published_messages` | boolean | `true` | Log details of each published message |

### Channel Configuration

Configure per-channel message forwarding:

```yaml
channels:
  - name: "LongFast"           # Channel name or number
    uplink_enabled: true        # Enable forwarding for this channel
    message_types:              # Filter by message type (optional)
      - "text"
      - "position"
      - "nodeinfo"
      - "telemetry"
```

**Supported Message Types:**
- `text` - Text messages
- `position` - GPS position updates
- `nodeinfo` - Node information
- `telemetry` - Device telemetry (battery, temperature, etc.)
- `routing` - Routing protocol messages
- `admin` - Administrative messages
- `traceroute` - Network traceroute
- `neighborinfo` - Neighbor information
- `detection_sensor` - Sensor detection events
- `reply` - Reply messages
- `ip_tunnel` - IP tunnel packets
- `paxcounter` - People counter data
- `serial` - Serial data
- `store_forward` - Store and forward messages
- `range_test` - Range test packets
- `private` - Private messages
- `atak` - ATAK integration messages

## MQTT Topic Structure

The plugin follows the official Meshtastic MQTT protocol topic structure:

### JSON Format (Unencrypted)

```
msh/{region}/2/json/{channel}/{nodeId}
```

**Example:**
```
msh/US/2/json/LongFast/!a1b2c3d4
```

### Protobuf Format (Encrypted)

```
msh/{region}/2/e/{channel}/{nodeId}
```

**Example:**
```
msh/US/2/e/LongFast/!a1b2c3d4
```

### Topic Components

- **region**: Geographic region (e.g., `US`, `EU`)
- **2**: Protocol version
- **json/e**: Format indicator (`json` for plaintext, `e` for encrypted)
- **channel**: Meshtastic channel name or number
- **nodeId**: Sender's node ID (e.g., `!a1b2c3d4`)

### Custom Root Topic

Override the default `msh/{region}` prefix:

```yaml
mqtt_gateway:
  root_topic: "custom/mesh/network"
```

This produces topics like:
```
custom/mesh/network/2/json/LongFast/!a1b2c3d4
```

## Configuration Examples

### Example 1: Public Meshtastic MQTT Server

Forward all messages to the public Meshtastic MQTT server:

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

### Example 2: Private MQTT Broker with TLS

Connect to a private broker with authentication and encryption:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  broker_port: 8883
  username: "meshtastic_user"
  password: "secure_password"
  tls_enabled: true
  ca_cert: "/path/to/ca.crt"
  format: "json"
  region: "US"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Example 3: Selective Message Forwarding

Forward only text messages and positions from specific channels:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  format: "json"
  region: "US"
  max_messages_per_second: 5
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position"]
    
    - name: "0"
      uplink_enabled: true
      message_types: ["text"]
    
    - name: "Admin"
      uplink_enabled: false  # Don't forward admin channel
```

### Example 4: High-Traffic Network

Optimize for high message volume:

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  format: "json"
  region: "US"
  max_messages_per_second: 50
  burst_multiplier: 3
  queue_max_size: 5000
  reconnect_max_delay: 30
  log_published_messages: false  # Reduce log volume
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Example 5: Encrypted Payloads

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

## Troubleshooting

### Connection Issues

**Problem:** Plugin fails to connect to MQTT broker

**Solutions:**
1. Verify broker address and port are correct
2. Check network connectivity: `ping mqtt.meshtastic.org`
3. Verify firewall allows outbound connections on MQTT port
4. Check broker logs for authentication errors
5. Enable debug logging:
   ```yaml
   mqtt_gateway:
     log_level: "DEBUG"
   ```

**Check logs for:**
```
ERROR: Failed to connect to MQTT broker: Connection refused
ERROR: Authentication failed for user 'username'
```

### TLS/SSL Errors

**Problem:** TLS connection fails with certificate errors

**Solutions:**
1. Verify CA certificate path is correct and readable
2. Check certificate expiration: `openssl x509 -in ca.crt -noout -dates`
3. Ensure certificate matches broker hostname
4. Try disabling TLS temporarily to isolate the issue

**Check logs for:**
```
ERROR: TLS handshake failed: certificate verify failed
ERROR: SSL certificate problem: unable to get local issuer certificate
```

### Messages Not Forwarding

**Problem:** Plugin connects but messages aren't published

**Solutions:**
1. Verify channel configuration matches your Meshtastic channels
2. Check that `uplink_enabled: true` for the channel
3. Verify message type filters aren't too restrictive
4. Check rate limiting isn't blocking messages
5. Monitor queue size in health status

**Check logs for:**
```
DEBUG: Message filtered: channel 'LongFast' uplink disabled
DEBUG: Message type 'telemetry' not in allowed types for channel
WARNING: Rate limit exceeded, queuing message
```

### Queue Overflow

**Problem:** Messages being dropped due to queue overflow

**Solutions:**
1. Increase `queue_max_size`:
   ```yaml
   mqtt_gateway:
     queue_max_size: 5000
   ```
2. Reduce `max_messages_per_second` if broker is rate limiting
3. Check broker connectivity and fix connection issues
4. Enable queue persistence:
   ```yaml
   mqtt_gateway:
     queue_persist: true
   ```

**Check logs for:**
```
WARNING: Message queue full (1000 messages), dropping oldest message
WARNING: Dropped 15 messages due to queue overflow
```

### High Latency

**Problem:** Significant delay between mesh receipt and MQTT publish

**Solutions:**
1. Reduce rate limiting if broker supports higher rates:
   ```yaml
   mqtt_gateway:
     max_messages_per_second: 50
   ```
2. Check network latency to broker: `ping mqtt.meshtastic.org`
3. Use a geographically closer broker
4. Disable message logging to reduce overhead:
   ```yaml
   mqtt_gateway:
     log_published_messages: false
   ```

### Reconnection Loops

**Problem:** Plugin continuously reconnects and disconnects

**Solutions:**
1. Increase reconnection delays:
   ```yaml
   mqtt_gateway:
     reconnect_initial_delay: 5
     reconnect_max_delay: 300
   ```
2. Check for broker-side rate limiting or connection limits
3. Verify credentials are correct
4. Check broker logs for disconnect reasons

**Check logs for:**
```
WARNING: MQTT connection lost, entering recovery mode
INFO: Reconnection attempt 5 failed: Connection refused
INFO: MQTT connection restored after 3 attempts
```

## Health Monitoring

Check plugin health status via ZephyrGate's health endpoint or logs:

```python
# Health status includes:
{
    'healthy': True,
    'connected': True,
    'queue_size': 0,
    'messages_published': 1234,
    'messages_dropped': 0,
    'last_publish': '2024-01-15T10:30:45Z',
    'errors': 0
}
```

**Key Metrics:**
- `connected`: MQTT broker connection status
- `queue_size`: Number of messages waiting to be published
- `messages_published`: Total messages successfully published
- `messages_dropped`: Messages lost due to queue overflow
- `errors`: Count of publish errors

## Performance Considerations

### Message Throughput

The plugin can handle high message volumes with proper configuration:

- **Low traffic** (< 10 msg/sec): Default settings work well
- **Medium traffic** (10-50 msg/sec): Increase rate limit and queue size
- **High traffic** (> 50 msg/sec): Consider multiple brokers or message filtering

### Memory Usage

Memory usage scales with queue size:
- Default queue (1000 messages): ~5-10 MB
- Large queue (10000 messages): ~50-100 MB
- Queue persistence: Additional disk I/O overhead

### CPU Usage

CPU usage is minimal:
- JSON serialization: ~0.1ms per message
- Protobuf serialization: ~0.05ms per message
- Rate limiting: Negligible overhead

## Security Best Practices

1. **Use TLS/SSL in production:**
   ```yaml
   mqtt_gateway:
     tls_enabled: true
     broker_port: 8883
   ```

2. **Store credentials securely:**
   - Use environment variables instead of config files
   - Restrict config file permissions: `chmod 600 config.yaml`

3. **Use strong passwords:**
   - Minimum 16 characters
   - Mix of letters, numbers, and symbols

4. **Limit message types:**
   - Only forward necessary message types
   - Disable admin messages on public brokers

5. **Use client certificates:**
   ```yaml
   mqtt_gateway:
     tls_enabled: true
     client_cert: "/path/to/client.crt"
     client_key: "/path/to/client.key"
   ```

## Protocol Compliance

This plugin strictly follows the [Meshtastic MQTT protocol specification](https://meshtastic.org/docs/software/integrations/mqtt/):

- ✅ ServiceEnvelope protobuf wrapping
- ✅ Standard topic structure
- ✅ JSON schema compliance
- ✅ Metadata preservation (sender, timestamp, SNR/RSSI)
- ✅ Encrypted payload pass-through

Messages published by this plugin are compatible with:
- Official Meshtastic MQTT clients
- Meshtastic web interface
- Third-party MQTT integrations
- Home Assistant Meshtastic integration

## Dependencies

The plugin requires the following Python packages (automatically installed):

- `paho-mqtt>=1.6.1` - MQTT client library
- `protobuf>=3.20.0` - Protobuf serialization
- `meshtastic>=2.0.0` - Meshtastic protobuf definitions

## Support

For issues, questions, or contributions:

- **Documentation:** See `docs/MQTT_GATEWAY_GUIDE.md` for detailed setup guide
- **GitHub Issues:** Report bugs and request features
- **Meshtastic Discord:** Join the community for help
- **Logs:** Enable debug logging for troubleshooting

## License

This plugin is part of ZephyrGate and is licensed under GPL-3.0.
