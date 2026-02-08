# Network Traceroute Mapper - Developer Guide

## Quick Reference

### Component Overview

```
TracerouteMapperPlugin (Main)
├── NodeStateTracker      - Track node states and filtering
├── PriorityQueue         - Priority-based request queue
├── RateLimiter          - Token bucket rate limiting
├── TracerouteManager    - Request/response handling
├── StatePersistence     - Save/load state to disk
└── NetworkHealthMonitor - Health protection and monitoring
```

### Key Files

```
plugins/traceroute_mapper/
├── plugin.py                    # Main plugin (972 lines)
├── node_state_tracker.py        # Node state management
├── priority_queue.py            # Priority queue implementation
├── rate_limiter.py             # Rate limiting
├── traceroute_manager.py       # Traceroute handling
├── state_persistence.py        # State persistence
├── network_health_monitor.py   # Health monitoring
└── config_schema.json          # Configuration schema

tests/
├── unit/traceroute_mapper/     # 189 unit tests
└── property/traceroute_mapper/ # 56 property tests
```

## Component APIs

### NodeStateTracker

```python
# Update node state
tracker.update_node(
    node_id="!abc123",
    is_direct=False,
    snr=-5.0,
    rssi=-95
)

# Check if should trace
if tracker.should_trace_node(node_id):
    # Apply filters: blacklist, whitelist, role, SNR
    pass

# Get node state
state = tracker.get_node_state(node_id)
# Returns: NodeState(node_id, is_direct, last_seen, ...)

# Mark as traced
tracker.mark_node_traced(node_id, success=True)
```

### PriorityQueue

```python
# Enqueue request
queue.enqueue(
    node_id="!abc123",
    priority=1,  # 1=highest, 10=lowest
    reason="new_node"
)

# Dequeue next request
request = queue.dequeue()
# Returns: TracerouteRequest(node_id, priority, reason, ...)

# Check if contains
if queue.contains(node_id):
    queue.remove(node_id)
```

### RateLimiter

```python
# Wait for token
await rate_limiter.acquire()

# Check wait time
wait_time = rate_limiter.get_wait_time()

# Dynamic rate adjustment
rate_limiter.set_rate(new_rate)
```

### TracerouteManager

```python
# Send traceroute
request_id = await manager.send_traceroute(
    node_id="!abc123",
    priority=1
)

# Handle response
await manager.handle_traceroute_response(message)

# Check timeouts
timed_out = manager.check_timeouts()
for pending in timed_out:
    # Handle timeout
    pass
```

### StatePersistence

```python
# Save state
node_states = tracker.get_all_nodes()
await persistence.save_state(node_states)

# Load state
node_states = await persistence.load_state()
tracker.load_state(node_states)

# Save history
await persistence.save_traceroute_history(node_id, result)

# Get history
history = await persistence.get_traceroute_history(node_id, limit=10)
```

### NetworkHealthMonitor

```python
# Record results
monitor.record_success(response_time=1.5)
monitor.record_failure(is_timeout=True)

# Check health
if monitor.is_healthy():
    # Safe to send traceroutes
    pass

# Get recommended rate
current_rate = monitor.get_recommended_rate(base_rate)

# Emergency stop
if monitor.is_emergency_stop:
    # Halt operations
    pass
```

## Message Flow

### Incoming Message Processing

```python
async def _handle_mesh_message(message, context):
    # 1. Extract node info
    sender_id = message.sender_id
    is_direct = _is_direct_node(message)
    
    # 2. Update node state
    node_tracker.update_node(sender_id, is_direct, snr, rssi)
    
    # 3. Check message type
    if _is_traceroute_response(message):
        await _handle_traceroute_response(message)
    elif is_new_indirect_node:
        await _handle_new_indirect_node(sender_id)
    elif node_back_online:
        await _handle_node_back_online(sender_id)
    elif became_direct:
        await _handle_direct_node_transition(sender_id)
```

### Traceroute Request Flow

```python
# Background loop
while True:
    # 1. Check if should process
    if not _should_process_queue():
        await asyncio.sleep(60)
        continue
    
    # 2. Dequeue request
    request = priority_queue.dequeue()
    
    # 3. Wait for rate limiter
    await rate_limiter.acquire()
    
    # 4. Send traceroute
    await _send_traceroute_request(request)
```

## Priority Levels

```python
PRIORITIES = {
    1: "NEW_NODE",           # New indirect node discovered
    2: "CRITICAL",           # Manual request or critical path
    4: "NODE_BACK_ONLINE",   # Node came back online
    6: "TOPOLOGY_CHANGE",    # Detected topology change
    8: "PERIODIC_RECHECK",   # Scheduled periodic recheck
    10: "LOW_PRIORITY"       # Background discovery
}
```

## Configuration

### Essential Settings

```yaml
traceroute_mapper:
  enabled: true
  traceroutes_per_minute: 1    # Rate limit
  queue_max_size: 500           # Max queue size
  max_hops: 7                   # Traceroute hop limit
  skip_direct_nodes: true       # Skip single-hop nodes
```

### Advanced Settings

```yaml
  # Periodic rechecks
  recheck_enabled: true
  recheck_interval_hours: 6
  
  # Retry logic
  max_retries: 3
  timeout_seconds: 60
  retry_backoff_multiplier: 2.0
  
  # Node filtering
  blacklist: ["!node1", "!node2"]
  whitelist: []  # Empty = all nodes
  exclude_roles: ["CLIENT"]
  min_snr_threshold: -10.0
  
  # State persistence
  state_persistence_enabled: true
  state_file_path: "data/traceroute_state.json"
  auto_save_interval_minutes: 5
  history_per_node: 10
```

### Network Health Protection

```yaml
  # Quiet hours
  quiet_hours:
    enabled: true
    start_time: "22:00"
    end_time: "06:00"
    timezone: "UTC"
  
  # Congestion detection
  congestion_detection:
    enabled: true
    success_rate_threshold: 0.5
    throttle_multiplier: 0.5
  
  # Emergency stop
  emergency_stop:
    enabled: true
    failure_threshold: 0.2
    consecutive_failures: 10
    auto_recovery_minutes: 30
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/traceroute_mapper/ -v

# Unit tests only
pytest tests/unit/traceroute_mapper/ -v

# Property tests only
pytest tests/property/traceroute_mapper/ -v

# Specific component
pytest tests/unit/traceroute_mapper/test_priority_queue.py -v

# With coverage
pytest tests/traceroute_mapper/ --cov=plugins/traceroute_mapper --cov-report=html
```

### Writing Tests

```python
# Unit test example
@pytest.mark.asyncio
async def test_enqueue_dequeue():
    queue = PriorityQueue(max_size=10)
    
    # Enqueue
    result = queue.enqueue("!node1", priority=5, reason="test")
    assert result is True
    
    # Dequeue
    request = queue.dequeue()
    assert request.node_id == "!node1"
    assert request.priority == 5

# Property test example
@given(
    node_id=valid_node_id(),
    priority=st.integers(min_value=1, max_value=10)
)
def test_priority_ordering(node_id, priority):
    queue = PriorityQueue(max_size=100)
    queue.enqueue(node_id, priority, "test")
    # Property: Lower priority number = higher priority
    assert queue.peek().priority <= priority
```

## Debugging

### Enable Debug Logging

```yaml
traceroute_mapper:
  log_level: "DEBUG"
  log_traceroute_requests: true
  log_traceroute_responses: true
```

### Check Health Status

```python
status = await plugin.get_health_status()

print(f"Healthy: {status['healthy']}")
print(f"Enabled: {status['enabled']}")
print(f"Emergency Stop: {status['emergency_stop']}")
print(f"Queue Size: {status['queue_size']}")
print(f"Pending: {status['pending_traceroutes']}")
print(f"Success Rate: {status['success_rate']:.2%}")
print(f"Throttled: {status['is_throttled']}")
print(f"Quiet Hours: {status['is_quiet_hours']}")
```

### Common Issues

**Queue not processing:**
- Check `is_healthy()` - may be in quiet hours or emergency stop
- Check rate limit - may be waiting for token
- Check queue size - may be empty

**High failure rate:**
- Check network connectivity
- Verify max_hops is sufficient
- Check timeout_seconds is adequate
- Review node filtering settings

**Emergency stop triggered:**
- Check `emergency_stop_reason` in health status
- Review recent failure patterns
- Wait for auto-recovery or manually exit
- Adjust failure_threshold if too sensitive

## Performance Tuning

### High-Volume Networks (>100 nodes)

```yaml
traceroutes_per_minute: 5      # Increase rate
queue_max_size: 1000           # Larger queue
recheck_interval_hours: 12     # Less frequent rechecks
```

### Low-Bandwidth Networks

```yaml
traceroutes_per_minute: 0.5    # Slower rate
max_hops: 5                    # Fewer hops
timeout_seconds: 120           # Longer timeout
```

### Battery-Powered Gateways

```yaml
traceroutes_per_minute: 0.25   # Very slow rate
quiet_hours:
  enabled: true
  start_time: "20:00"
  end_time: "08:00"            # Long quiet period
```

## Extension Points

### Custom Priority Logic

```python
def calculate_priority(node_state, reason):
    if reason == "critical_path":
        return 1
    elif node_state.failure_count > 5:
        return 2  # Retry problematic nodes sooner
    elif node_state.snr < -10:
        return 9  # Deprioritize weak signals
    else:
        return 5  # Default
```

### Custom Filtering

```python
def should_trace_node(node_id, node_state):
    # Custom logic
    if node_id.startswith("!aircraft"):
        return False  # Skip aircraft
    if node_state.altitude > 10000:
        return False  # Skip high altitude
    return True
```

### Custom Health Checks

```python
def is_healthy():
    # Add custom checks
    if battery_level < 20:
        return False
    if cpu_usage > 80:
        return False
    return base_is_healthy()
```

## Best Practices

### Configuration
- Start with conservative settings (low rate)
- Enable quiet hours for nighttime
- Use blacklist for known problematic nodes
- Enable state persistence for reliability

### Monitoring
- Check health status regularly
- Monitor success rate trends
- Watch for emergency stop triggers
- Review queue size patterns

### Troubleshooting
- Enable debug logging temporarily
- Check component statistics
- Review recent traceroute history
- Verify network connectivity

### Production Deployment
- Test in staging first
- Start with plugin disabled
- Gradually increase rate
- Monitor for 24 hours before full deployment

## API Reference

### Plugin Methods

```python
# Lifecycle
await plugin.initialize()
await plugin.start()
await plugin.stop()

# Health
status = await plugin.get_health_status()
metadata = plugin.get_metadata()

# Message handling (automatic)
# Registered with message router
```

### Component Methods

See individual component sections above for detailed APIs.

## Support

### Documentation
- Requirements: `.kiro/specs/network-traceroute-mapper/requirements.md`
- Design: `.kiro/specs/network-traceroute-mapper/design.md`
- Tasks: `.kiro/specs/network-traceroute-mapper/tasks.md`
- Status: `.kiro/specs/network-traceroute-mapper/IMPLEMENTATION_STATUS.md`

### Testing
- Unit tests: `tests/unit/traceroute_mapper/`
- Property tests: `tests/property/traceroute_mapper/`
- Coverage: Run with `--cov` flag

### Issues
- Check logs for error messages
- Review health status for diagnostics
- Verify configuration is valid
- Test components individually

---

**Last Updated:** February 7, 2026  
**Version:** 1.0.0  
**Status:** Production Ready (Core Features)
