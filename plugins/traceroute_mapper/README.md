# Network Traceroute Mapper Plugin

Automatically discovers and maps mesh network topology by performing intelligent traceroutes to nodes.

## Overview

The Network Traceroute Mapper is a ZephyrGate plugin that automatically discovers and maps the mesh network topology by performing traceroutes to nodes and publishing the results to MQTT for visualization by online mapping tools. This feature is designed to be optional, disabled by default, and intelligently manages traceroute requests to avoid overwhelming the network.

## Features

- **Intelligent Prioritization**: Priority queue ensures important discoveries happen quickly while routine checks happen in the background
- **Network-Aware**: Rate limiting, quiet hours, and congestion detection protect network health
- **Direct Node Filtering**: Skips traceroutes to nodes directly heard by the radio (single-hop paths)
- **Periodic Rechecks**: Automatically re-traces nodes to detect topology changes over time
- **State Persistence**: Saves node discovery state across restarts
- **MQTT Integration**: Publishes traceroute messages to MQTT using standard Meshtastic protocol
- **Emergency Stop**: Automatically pauses operations when network health is critical

## Configuration

The plugin is configured in `config/config.yaml` under the `traceroute_mapper` section.

### Basic Configuration

```yaml
traceroute_mapper:
  enabled: false  # Disabled by default
  traceroutes_per_minute: 1  # Rate limit
  max_hops: 7  # Maximum hops for traceroutes
  skip_direct_nodes: true  # Skip single-hop nodes
```

### Advanced Configuration

See `config_schema.json` for complete configuration options including:
- Rate limiting and burst control
- Priority queue management
- Periodic recheck intervals
- Node filtering (blacklist, whitelist, role, SNR threshold)
- Quiet hours for reduced network activity
- Congestion detection and throttling
- Emergency stop mode
- State persistence settings

## Usage

### Enable the Plugin

1. Edit `config/config.yaml`
2. Set `traceroute_mapper.enabled: true`
3. Configure rate limits and other settings as needed
4. Restart ZephyrGate

### Monitor Status

The plugin provides health status through the plugin manager:

```python
status = await plugin_manager.get_plugin_health('traceroute_mapper')
print(f"Queue size: {status['queue_size']}")
print(f"Success rate: {status['success_rate']:.1%}")
```

### View Logs

The plugin logs all traceroute activity:

```
INFO: Traceroute queued for node !a1b2c3d4 (priority=1, reason=new_node)
INFO: Sending traceroute to !a1b2c3d4 (max_hops=7)
INFO: Traceroute response from !a1b2c3d4: 3 hops, 1.2s
```

## Network Health Protection

The plugin includes multiple layers of network health protection:

1. **Rate Limiting**: Enforces maximum traceroutes per minute
2. **Quiet Hours**: Pauses operations during configured time windows
3. **Congestion Detection**: Automatically reduces rate when success rate drops
4. **Emergency Stop**: Pauses all operations when network health is critical

## MQTT Integration

Traceroute messages are automatically forwarded to the MQTT Gateway (if enabled) for publishing to MQTT brokers. This allows mapping tools like Meshtastic Map to visualize the network topology.

## Recommended Settings

### Small Networks (<50 nodes)
```yaml
traceroutes_per_minute: 2
queue_max_size: 100
recheck_interval_hours: 12
max_hops: 5
initial_discovery_enabled: true
```

### Large Networks (>100 nodes)
```yaml
traceroutes_per_minute: 1
queue_max_size: 500
recheck_interval_hours: 24
max_hops: 7
initial_discovery_enabled: false
```

### High-Density Networks
```yaml
traceroutes_per_minute: 0.5  # 1 every 2 minutes
queue_max_size: 1000
recheck_interval_hours: 48
min_snr_threshold: -10  # Only trace nodes with decent signal
quiet_hours:
  enabled: true
  start_time: "20:00"
  end_time: "08:00"
```

## Requirements

- ZephyrGate 1.0.0 or later
- Python 3.8 or later
- No external dependencies (uses Python standard library only)
- Optional: MQTT Gateway plugin for MQTT publishing

## License

GPL-3.0

## Author

ZephyrGate Team
