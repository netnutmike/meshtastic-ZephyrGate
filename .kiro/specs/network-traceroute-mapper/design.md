# Design Document: Network Traceroute Mapper

## Overview

The Network Traceroute Mapper is a plugin service for ZephyrGate that automatically discovers and maps mesh network topology by performing intelligent traceroutes to nodes. This design implements an automated discovery system that prioritizes important network changes, respects network health constraints, and publishes results to MQTT for visualization by mapping tools.

### Key Design Principles

1. **Optional and Non-Intrusive**: The traceroute mapper operates as an optional plugin that doesn't interfere with normal mesh operations
2. **Intelligent Prioritization**: Priority queue ensures important discoveries happen quickly while routine checks happen in the background
3. **Network-Aware**: Rate limiting, quiet hours, and congestion detection protect network health
4. **Async-First Architecture**: All operations use async/await patterns to prevent blocking the message router
5. **Standard Protocol Compliance**: Uses Meshtastic traceroute protocol and forwards messages through existing MQTT Gateway

### Architecture Context

The Traceroute Mapper integrates into ZephyrGate's existing plugin architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                      ZephyrGate Core                            │
│                                                                 │
│  ┌──────────────┐      ┌─────────────────┐                    │
│  │  Meshtastic  │─────▶│ Message Router  │                    │
│  │  Interface   │      │                 │                    │
│  └──────────────┘      └────────┬────────┘                    │
│                                  │                              │
│                                  ├──▶ Bot Service               │
│                                  ├──▶ MQTT Gateway              │
│                                  │                              │
│                                  ├──▶ Traceroute Mapper (NEW)  │
│                                  │     │                        │
│                                  │     ├─ Node State Tracker   │
│                                  │     ├─ Priority Queue        │
│                                  │     ├─ Rate Limiter          │
│                                  │     ├─ Traceroute Manager   │
│                                  │     └─ State Persistence     │
│                                  │           │                  │
└──────────────────────────────────┼───────────┼──────────────────┘
                                   │           │
                                   │           ▼
                                   │    ┌──────────────┐
                                   │    │ Meshtastic   │
                                   │    │ Interface    │
                                   │    │ (Traceroute) │
                                   │    └──────────────┘
                                   │
                                   ▼
                            Other Services
```

## Architecture

### Component Structure

The Traceroute Mapper is implemented as a ZephyrGate plugin with the following components:

```
plugins/traceroute_mapper/
├── __init__.py
├── plugin.py                  # Main plugin class (TracerouteMapperPlugin)
├── node_state_tracker.py      # Track node state and direct/indirect status
├── priority_queue.py           # Priority queue for traceroute requests
├── rate_limiter.py             # Rate limiting implementation
├── traceroute_manager.py       # Traceroute request/response handling
├── state_persistence.py        # Save/load node state to disk
├── network_health_monitor.py  # Monitor network health and congestion
├── config_schema.json          # Configuration validation schema
├── manifest.yaml               # Plugin metadata
└── requirements.txt            # Dependencies (if any)
```

### Core Components

#### 1. TracerouteMapperPlugin

The main plugin class that implements the ZephyrGate plugin interface.

**Responsibilities:**
- Plugin lifecycle management (initialize, start, stop)
- Configuration loading and validation
- Registration with message router
- Coordination between sub-components
- Handle node discovery events
- Handle traceroute responses

**Key Methods:**
```python
async def initialize(config: Dict[str, Any]) -> bool
async def start() -> bool
async def stop() -> bool
async def handle_message(message: Message, context: Dict[str, Any]) -> Optional[Any]
async def get_health_status() -> Dict[str, Any]
```

#### 2. NodeStateTracker

Tracks the state of all known nodes on the mesh network.

**Responsibilities:**
- Maintain node state (last seen, last traced, direct/indirect)
- Determine if a node is directly heard or indirect
- Track node online/offline transitions
- Provide node filtering (blacklist, whitelist, role, SNR threshold)

**Key Methods:**
```python
def update_node(node_id: str, is_direct: bool, snr: Optional[float], rssi: Optional[float]) -> None
def get_node_state(node_id: str) -> Optional[NodeState]
def is_direct_node(node_id: str) -> bool
def should_trace_node(node_id: str) -> bool
def get_nodes_needing_trace() -> List[str]
def mark_node_traced(node_id: str, success: bool) -> None
```

**Node State Data:**
```python
@dataclass
class NodeState:
    node_id: str
    is_direct: bool
    last_seen: datetime
    last_traced: Optional[datetime]
    last_trace_success: bool
    trace_count: int
    failure_count: int
    snr: Optional[float]
    rssi: Optional[float]
    was_offline: bool  # Track if node came back online
```

**Direct Node Detection:**
- Node appears in neighbor list from Meshtastic interface
- Node has SNR/RSSI values indicating direct reception (hop_count == 0 or 1)
- Node is in the routing table with hop count of 1

#### 3. PriorityQueue

Implements a priority queue for traceroute requests with intelligent ordering.

**Responsibilities:**
- Queue traceroute requests with priority levels (1-10)
- Process requests in priority order (lowest number = highest priority)
- Enforce maximum queue size
- Handle queue overflow with configurable strategies
- Prevent duplicate requests for the same node

**Key Methods:**
```python
async def enqueue(node_id: str, priority: int, reason: str) -> bool
async def dequeue() -> Optional[TracerouteRequest]
def size() -> int
def is_full() -> bool
def contains(node_id: str) -> bool
async def remove(node_id: str) -> bool
async def clear() -> None
```

**Priority Levels:**
```python
class TraceroutePriority(Enum):
    NEW_NODE = 1          # New indirect node discovered
    CRITICAL = 2          # Manual request or critical path
    NODE_BACK_ONLINE = 4  # Node came back online
    TOPOLOGY_CHANGE = 6   # Detected topology change
    PERIODIC_RECHECK = 8  # Scheduled periodic recheck
    LOW_PRIORITY = 10     # Background discovery
```

**Queue Overflow Strategies:**
- `drop_lowest_priority`: Drop lowest priority request when full
- `drop_oldest`: Drop oldest request when full
- `drop_new`: Reject new request when full

#### 4. RateLimiter

Implements token bucket rate limiting for traceroute requests.

**Responsibilities:**
- Enforce configurable traceroute rate (traceroutes per minute)
- Implement token bucket algorithm
- Track rate limit statistics
- Coordinate with network health monitor for dynamic throttling

**Key Methods:**
```python
async def acquire() -> bool
async def wait_if_needed() -> None
def get_wait_time() -> float
def set_rate(traceroutes_per_minute: int) -> None
def reset() -> None
```

**Rate Limiting Algorithm:**
```
Token Bucket:
- Capacity: traceroutes_per_minute tokens
- Refill rate: traceroutes_per_minute / 60 tokens/second
- Cost per traceroute: 1 token
- Burst allowance: 2x capacity (configurable)
```

#### 5. TracerouteManager

Manages traceroute request sending and response handling.

**Responsibilities:**
- Send traceroute requests to Meshtastic interface
- Track pending traceroute requests
- Handle traceroute responses
- Implement retry logic with exponential backoff
- Timeout detection for failed traceroutes
- Forward traceroute messages to message router for MQTT publishing

**Key Methods:**
```python
async def send_traceroute(node_id: str, max_hops: int) -> str
async def handle_traceroute_response(message: Message) -> None
def is_pending(request_id: str) -> bool
def get_pending_count() -> int
async def cancel_traceroute(request_id: str) -> None
```

**Traceroute Request Tracking:**
```python
@dataclass
class PendingTraceroute:
    request_id: str
    node_id: str
    sent_at: datetime
    timeout_at: datetime
    retry_count: int
    max_retries: int
    priority: int
```

**Meshtastic Traceroute Protocol:**
```python
# Send traceroute request
message = Message(
    recipient_id=target_node_id,
    message_type=MessageType.ROUTING,  # TRACEROUTE_APP
    content="",  # Empty for traceroute
    hop_limit=max_hops,
    metadata={
        'want_response': True,
        'route_discovery': True
    }
)
```

#### 6. StatePersistence

Handles saving and loading node state to/from disk.

**Responsibilities:**
- Persist node state to JSON file
- Load node state at startup
- Handle file corruption gracefully
- Periodic auto-save
- Store traceroute history

**Key Methods:**
```python
async def save_state(node_states: Dict[str, NodeState]) -> bool
async def load_state() -> Dict[str, NodeState]
async def save_traceroute_history(node_id: str, result: TracerouteResult) -> None
async def get_traceroute_history(node_id: str, limit: int) -> List[TracerouteResult]
```

**Persistence Format:**
```json
{
  "version": "1.0",
  "last_saved": "2024-01-15T10:30:00Z",
  "nodes": {
    "!a1b2c3d4": {
      "node_id": "!a1b2c3d4",
      "is_direct": false,
      "last_seen": "2024-01-15T10:25:00Z",
      "last_traced": "2024-01-15T09:00:00Z",
      "last_trace_success": true,
      "trace_count": 5,
      "failure_count": 0,
      "snr": -5.2,
      "rssi": -95
    }
  },
  "traceroute_history": {
    "!a1b2c3d4": [
      {
        "timestamp": "2024-01-15T09:00:00Z",
        "success": true,
        "hop_count": 3,
        "route": ["!gateway", "!relay1", "!relay2", "!a1b2c3d4"],
        "snr_values": [10.5, 5.2, -2.1, -5.2],
        "rssi_values": [-75, -85, -92, -95]
      }
    ]
  }
}
```

#### 7. NetworkHealthMonitor

Monitors network health and adjusts traceroute behavior accordingly.

**Responsibilities:**
- Detect network congestion
- Track failure rates
- Implement quiet hours
- Trigger emergency stop when needed
- Dynamically adjust rate limits

**Key Methods:**
```python
def is_healthy() -> bool
def is_quiet_hours() -> bool
def should_throttle() -> bool
def get_recommended_rate() -> int
def record_success() -> None
def record_failure() -> None
def enter_emergency_stop() -> None
def exit_emergency_stop() -> None
```

**Health Metrics:**
```python
@dataclass
class NetworkHealthMetrics:
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeout_count: int
    success_rate: float
    avg_response_time: float
    is_congested: bool
    is_emergency_stop: bool
```

**Congestion Detection:**
- Success rate < 50% over last 10 traceroutes
- Average response time > 2x normal
- Timeout rate > 30%

**Emergency Stop Triggers:**
- Success rate < 20% over last 20 traceroutes
- 10 consecutive failures
- Manual trigger via configuration

## Components and Interfaces

### Plugin Interface

The Traceroute Mapper implements the standard ZephyrGate plugin interface:

```python
class TracerouteMapperPlugin(EnhancedPlugin):
    """Traceroute Mapper plugin for ZephyrGate"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.enabled = False
        self.initialized = False
        
        # Component references
        self.node_tracker = None
        self.priority_queue = None
        self.rate_limiter = None
        self.traceroute_manager = None
        self.state_persistence = None
        self.health_monitor = None
        
        # Configuration cache
        self._config_cache = {}
        
        # Statistics
        self.stats = {
            'nodes_discovered': 0,
            'traceroutes_sent': 0,
            'traceroutes_successful': 0,
            'traceroutes_failed': 0,
            'queue_size': 0,
            'direct_nodes_skipped': 0
        }
    
    async def initialize(self) -> bool:
        """Initialize plugin with configuration"""
        pass
    
    async def start(self) -> bool:
        """Start the plugin"""
        pass
    
    async def stop(self) -> bool:
        """Stop the plugin"""
        pass
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Handle incoming message from mesh"""
        pass
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get plugin health status"""
        pass
```

### Message Router Integration

The plugin registers with the message router to receive node discovery events and traceroute responses:

```python
# In plugin.py
async def start(self) -> bool:
    # Register message handler for all messages
    self.register_message_handler(self._handle_mesh_message, priority=50)
    
    # Start background tasks
    asyncio.create_task(self._process_queue_loop())
    asyncio.create_task(self._periodic_recheck_loop())
    asyncio.create_task(self._state_persistence_loop())
    
    # Load persisted state if enabled
    if self._config_cache.get('state_persistence_enabled', False):
        await self._load_persisted_state()
    
    # Run initial discovery scan if enabled
    if self._config_cache.get('initial_discovery_enabled', False):
        await self._run_initial_discovery()
    
    return True

async def _handle_mesh_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
    """Handle incoming mesh message"""
    # Update node state tracker
    await self._update_node_state(message)
    
    # Check if this is a traceroute response
    if self._is_traceroute_response(message):
        await self.traceroute_manager.handle_traceroute_response(message)
    
    # Check if this is a new node discovery
    if self._is_new_node(message):
        await self._handle_new_node_discovery(message)
    
    return None
```

### Traceroute Request Flow

```
1. Node Discovery Event
   ↓
2. NodeStateTracker.update_node()
   ↓
3. Check if node is direct → Skip if direct
   ↓
4. Check if node should be traced (filters)
   ↓
5. PriorityQueue.enqueue(node_id, priority)
   ↓
6. Background loop: PriorityQueue.dequeue()
   ↓
7. RateLimiter.acquire() → Wait if needed
   ↓
8. NetworkHealthMonitor.is_healthy() → Skip if unhealthy
   ↓
9. TracerouteManager.send_traceroute()
   ↓
10. Forward message to Message Router
    ↓
11. Message Router → Meshtastic Interface
    ↓
12. Message Router → MQTT Gateway (for publishing)
```

### Traceroute Response Flow

```
1. Meshtastic Interface receives traceroute response
   ↓
2. Message Router → TracerouteMapperPlugin
   ↓
3. TracerouteManager.handle_traceroute_response()
   ↓
4. Parse route array (node IDs, SNR, RSSI)
   ↓
5. NodeStateTracker.mark_node_traced()
   ↓
6. StatePersistence.save_traceroute_history()
   ↓
7. NetworkHealthMonitor.record_success()
   ↓
8. Schedule periodic recheck
   ↓
9. Forward message to Message Router
   ↓
10. Message Router → MQTT Gateway (for publishing)
```

## Data Models

### Configuration Schema

```yaml
traceroute_mapper:
  enabled: false  # Default: disabled
  
  # Rate limiting
  traceroutes_per_minute: 1  # Default: 1 per minute
  burst_multiplier: 2  # Allow short bursts
  
  # Priority queue
  queue_max_size: 500  # Maximum queued requests
  queue_overflow_strategy: "drop_lowest_priority"  # Options: drop_lowest_priority, drop_oldest, drop_new
  clear_queue_on_startup: false
  
  # Periodic rechecks
  recheck_interval_hours: 6  # Default: 6 hours
  recheck_enabled: true
  
  # Traceroute parameters
  max_hops: 7  # Default: 7 hops
  timeout_seconds: 60  # Default: 60 seconds
  max_retries: 3  # Default: 3 retries
  retry_backoff_multiplier: 2.0
  
  # Startup behavior
  initial_discovery_enabled: false  # Run discovery scan at startup
  startup_delay_seconds: 60  # Wait before first traceroute
  
  # Node filtering
  skip_direct_nodes: true  # Don't trace direct nodes
  blacklist: []  # List of node IDs to never trace
  whitelist: []  # If set, only trace these nodes
  exclude_roles: ["CLIENT"]  # Exclude nodes with these roles
  min_snr_threshold: null  # Minimum SNR to trace (null = no limit)
  
  # Network health protection
  quiet_hours:
    enabled: false
    start_time: "22:00"  # 10 PM
    end_time: "06:00"    # 6 AM
    timezone: "UTC"
  
  congestion_detection:
    enabled: true
    success_rate_threshold: 0.5  # Throttle if success rate < 50%
    throttle_multiplier: 0.5  # Reduce rate by 50% when congested
  
  emergency_stop:
    enabled: true
    failure_threshold: 0.2  # Stop if success rate < 20%
    consecutive_failures: 10  # Stop after 10 consecutive failures
    auto_recovery_minutes: 30  # Auto-resume after 30 minutes
  
  # State persistence
  state_persistence_enabled: true
  state_file_path: "data/traceroute_state.json"
  auto_save_interval_minutes: 5
  history_per_node: 10  # Keep last 10 traceroutes per node
  
  # MQTT integration (uses existing MQTT Gateway)
  forward_to_mqtt: true  # Forward traceroute messages to MQTT
  
  # Logging
  log_level: "INFO"
  log_traceroute_requests: true
  log_traceroute_responses: true
```

### Internal Data Structures

```python
@dataclass
class NodeState:
    """State of a node on the mesh"""
    node_id: str
    is_direct: bool
    last_seen: datetime
    last_traced: Optional[datetime] = None
    next_recheck: Optional[datetime] = None
    last_trace_success: bool = False
    trace_count: int = 0
    failure_count: int = 0
    snr: Optional[float] = None
    rssi: Optional[float] = None
    was_offline: bool = False
    role: Optional[str] = None

@dataclass
class TracerouteRequest:
    """Traceroute request in the queue"""
    request_id: str
    node_id: str
    priority: int
    reason: str
    queued_at: datetime
    retry_count: int = 0

@dataclass
class PendingTraceroute:
    """Pending traceroute awaiting response"""
    request_id: str
    node_id: str
    sent_at: datetime
    timeout_at: datetime
    retry_count: int
    max_retries: int
    priority: int

@dataclass
class TracerouteResult:
    """Result of a completed traceroute"""
    node_id: str
    timestamp: datetime
    success: bool
    hop_count: int
    route: List[str]  # List of node IDs in path
    snr_values: List[float]
    rssi_values: List[float]
    duration_ms: float
    error_message: Optional[str] = None

@dataclass
class TracerouteStats:
    """Traceroute mapper statistics"""
    nodes_discovered: int = 0
    traceroutes_sent: int = 0
    traceroutes_successful: int = 0
    traceroutes_failed: int = 0
    traceroutes_timeout: int = 0
    queue_size: int = 0
    direct_nodes_skipped: int = 0
    filtered_nodes_skipped: int = 0
    last_traceroute_time: Optional[datetime] = None
    avg_response_time_ms: float = 0.0
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Direct Node Exclusion

*For any* node that is classified as a Direct_Node (appears in neighbor list or has hop_count ≤ 1), the Traceroute_Mapper should not queue a traceroute request for that node.

**Validates: Requirements 2.1, 2.3**

### Property 2: Direct Node Transition Cleanup

*For any* node that transitions from Indirect_Node to Direct_Node, any pending traceroute requests for that node should be removed from the queue.

**Validates: Requirements 2.2**

### Property 3: Rate Limit Enforcement

*For any* sequence of traceroute requests sent over time, the number of traceroutes sent in any 60-second window should not exceed the configured traceroutes_per_minute limit.

**Validates: Requirements 3.1**

### Property 4: New Node Priority Assignment

*For any* newly discovered Indirect_Node, the queued traceroute request should have priority 1 (highest priority).

**Validates: Requirements 4.1**

### Property 5: Node Back Online Priority Assignment

*For any* node that was offline and comes back online, the queued traceroute request should have priority 4.

**Validates: Requirements 4.2**

### Property 6: Periodic Recheck Priority Assignment

*For any* periodic recheck that is scheduled, the queued traceroute request should have priority 8.

**Validates: Requirements 4.3**

### Property 7: Priority Queue Ordering

*For any* sequence of traceroute requests in the queue, when dequeuing, requests should be processed in priority order (lowest number first), and requests with the same priority should be processed in FIFO order.

**Validates: Requirements 4.4, 4.5**

### Property 8: Queue Overflow with Priority

*For any* full queue, when a new high-priority request arrives, the lowest priority request in the queue should be dropped to make room.

**Validates: Requirements 4.6**

### Property 9: Recheck Scheduling After Success

*For any* node that is successfully traced, a recheck should be scheduled at current_time + recheck_interval_hours.

**Validates: Requirements 5.1**

### Property 10: Recheck Timer Reset

*For any* node that is traced before its scheduled recheck time, the recheck timer should be reset to current_time + recheck_interval_hours.

**Validates: Requirements 5.4**

### Property 11: Max Hops Configuration

*For any* traceroute request sent, the hop_limit field should be set to the configured max_hops value.

**Validates: Requirements 6.1**

### Property 12: Traceroute Request Forwarding

*For any* traceroute request sent by the Traceroute_Mapper, the message should be forwarded to the Message_Router for normal message processing (including MQTT publishing).

**Validates: Requirements 7.1**

### Property 13: Traceroute Response Forwarding

*For any* traceroute response received from the mesh, the message should be forwarded to the Message_Router for normal message processing (including MQTT publishing).

**Validates: Requirements 7.2**

### Property 14: Meshtastic Message Format Compliance

*For any* traceroute message forwarded to the Message_Router, the message should be a valid Meshtastic Message object with all required fields (sender_id, recipient_id, message_type, content, metadata).

**Validates: Requirements 7.3**

### Property 15: Startup Delay Enforcement

*For any* configured startup_delay_seconds value, the first traceroute should not be sent until at least startup_delay_seconds have elapsed since plugin start.

**Validates: Requirements 8.3**

### Property 16: State Persistence Round Trip

*For any* set of NodeState objects, saving to disk and then loading should produce equivalent NodeState objects with all fields preserved.

**Validates: Requirements 8.5, 13.2**

### Property 17: Blacklist Filtering

*For any* node on the configured blacklist, the Traceroute_Mapper should not queue a traceroute request for that node.

**Validates: Requirements 9.1**

### Property 18: Whitelist Filtering

*For any* node when a whitelist is configured, the Traceroute_Mapper should only queue traceroute requests for nodes on the whitelist.

**Validates: Requirements 9.2**

### Property 19: Blacklist and Whitelist Precedence

*For any* configuration with both blacklist and whitelist, a node should be traced if and only if it is on the whitelist AND not on the blacklist.

**Validates: Requirements 9.3**

### Property 20: Role Filtering

*For any* node with a role in the configured exclude_roles list, the Traceroute_Mapper should not queue a traceroute request for that node.

**Validates: Requirements 9.4**

### Property 21: SNR Threshold Filtering

*For any* node when a min_snr_threshold is configured, the Traceroute_Mapper should only queue traceroute requests for nodes with SNR >= min_snr_threshold.

**Validates: Requirements 9.5**

### Property 22: Queue Size Limit

*For any* state of the priority queue, the queue size should never exceed the configured queue_max_size.

**Validates: Requirements 10.1**

### Property 23: Queue Overflow Strategy

*For any* full queue and configured overflow strategy, when a new request arrives, the system should follow the configured strategy: drop_lowest_priority (drop lowest priority request), drop_oldest (drop oldest request), or drop_new (reject new request).

**Validates: Requirements 10.4, 10.5**

### Property 24: Retry Attempts Limit

*For any* failed traceroute, the system should retry up to max_retries times before giving up.

**Validates: Requirements 11.1**

### Property 25: Exponential Backoff Calculation

*For any* retry attempt N (where N >= 1), the backoff delay should be initial_delay * (backoff_multiplier ^ (N-1)), capped at max_delay.

**Validates: Requirements 11.3**

### Property 26: Timeout Enforcement

*For any* traceroute request sent, if no response is received within timeout_seconds, the request should be marked as failed.

**Validates: Requirements 11.4**

### Property 27: Quiet Hours Enforcement

*For any* time during configured quiet hours, no traceroute requests should be sent.

**Validates: Requirements 12.1**

### Property 28: Congestion Throttling

*For any* detected network congestion (success_rate < success_rate_threshold), the traceroute rate should be reduced by the configured throttle_multiplier.

**Validates: Requirements 12.2**

### Property 29: Emergency Stop Trigger

*For any* situation where the success rate falls below failure_threshold OR consecutive_failures threshold is exceeded, the system should enter emergency stop mode and pause all traceroute operations.

**Validates: Requirements 12.3**

### Property 30: Automatic Recovery

*For any* emergency stop state, when network conditions improve (success rate rises above failure_threshold for a sustained period), the system should automatically resume normal operations.

**Validates: Requirements 12.5**

### Property 31: Periodic State Persistence

*For any* configured auto_save_interval_minutes, the node state should be saved to disk at least once per interval.

**Validates: Requirements 13.1**

### Property 32: State Completeness

*For any* saved node state, the persisted data should include node_id, is_direct, last_seen, last_traced, and direct/indirect status for each node.

**Validates: Requirements 13.3**

### Property 33: Traceroute History Limit

*For any* node with traceroute history, the system should store at most history_per_node successful traceroutes, keeping the most recent ones.

**Validates: Requirements 13.4**

### Property 34: All Traceroute Messages Forwarded

*For any* traceroute message (sent by us or received from other nodes), the message should be forwarded to the Message_Router for normal processing.

**Validates: Requirements 14.1, 14.5**

### Property 35: Traceroute Message Field Preservation

*For any* traceroute message forwarded, all Meshtastic protobuf fields should be preserved, including the route array with SNR/RSSI values for each hop.

**Validates: Requirements 14.4**

### Property 36: Statistics Accuracy

*For any* request for statistics, the reported values (traceroutes_sent, traceroutes_successful, traceroutes_failed, queue_size) should match the actual counts maintained by the system.

**Validates: Requirements 15.5**

### Property 37: Health Status Accuracy

*For any* request for health status, the reported operational status should accurately reflect the current state of the system (enabled, connected, emergency_stop, etc.).

**Validates: Requirements 15.6**

### Property 38: Traceroute Request Protocol Compliance

*For any* traceroute request sent, the message should use MessageType.ROUTING (TRACEROUTE_APP), set want_response=True in metadata, include the destination node_id as recipient_id, and set hop_limit to max_hops.

**Validates: Requirements 18.1, 18.2, 18.3**

### Property 39: Traceroute Response Route Parsing

*For any* traceroute response received, the system should correctly parse the route array to extract the list of node IDs in the path.

**Validates: Requirements 18.4**

### Property 40: Traceroute Response Signal Parsing

*For any* traceroute response received, the system should correctly extract SNR and RSSI values for each hop in the route.

**Validates: Requirements 18.5**

## Error Handling

### Traceroute Request Errors

**Node Not Reachable:**
- Log warning with node ID
- Mark traceroute as failed
- Schedule retry with exponential backoff
- Update failure count in node state

**Timeout:**
- Log timeout event with node ID and duration
- Mark traceroute as failed
- Schedule retry if retries remain
- Update timeout statistics

**Invalid Node ID:**
- Log error with invalid node ID
- Skip traceroute request
- Remove from queue
- Do not retry

### Traceroute Response Errors

**Malformed Response:**
- Log error with response details
- Mark traceroute as failed
- Do not retry (response was received, just invalid)
- Update error statistics

**Incomplete Route:**
- Log warning with partial route
- Store partial result
- Mark as partially successful
- Schedule recheck sooner than normal

**Missing SNR/RSSI Data:**
- Log warning
- Store route without signal data
- Mark as successful (route is valid)
- Continue normal operation

### Queue Management Errors

**Queue Overflow:**
- Log warning with queue size and dropped request details
- Apply configured overflow strategy
- Update dropped request statistics
- Continue operation

**Invalid Priority:**
- Log error with invalid priority value
- Use default priority (8)
- Queue request anyway
- Continue operation

**Duplicate Request:**
- Log debug message
- Update existing request priority if new priority is higher
- Do not add duplicate
- Continue operation

### State Persistence Errors

**File Write Error:**
- Log error with file path and error details
- Retry write after delay
- Continue operation (state in memory is still valid)
- Alert if multiple consecutive failures

**File Read Error:**
- Log error with file path and error details
- Start with empty state
- Continue operation
- Create new state file on next save

**Corrupted State File:**
- Log error with corruption details
- Backup corrupted file
- Start with empty state
- Continue operation

### Network Health Errors

**Emergency Stop Triggered:**
- Log alert with trigger reason and statistics
- Pause all traceroute operations
- Clear pending requests (optional, configurable)
- Wait for auto-recovery or manual intervention

**Congestion Detected:**
- Log warning with congestion metrics
- Reduce traceroute rate
- Continue operation at reduced rate
- Monitor for improvement

**Rate Limiter Failure:**
- Log error
- Fall back to conservative rate (1 per minute)
- Continue operation
- Attempt to reinitialize rate limiter

### Recovery Procedures

**Traceroute Retry:**
```python
async def retry_traceroute(request: TracerouteRequest):
    """Retry a failed traceroute with exponential backoff"""
    if request.retry_count >= max_retries:
        logger.error(f"Max retries exceeded for node {request.node_id}")
        node_tracker.mark_node_traced(request.node_id, success=False)
        return
    
    # Calculate backoff delay
    delay = initial_delay * (backoff_multiplier ** request.retry_count)
    delay = min(delay, max_delay)
    
    logger.info(f"Retrying traceroute to {request.node_id} after {delay}s (attempt {request.retry_count + 1}/{max_retries})")
    
    await asyncio.sleep(delay)
    
    # Re-queue with same priority
    request.retry_count += 1
    await priority_queue.enqueue(request.node_id, request.priority, f"retry_{request.retry_count}")
```

**Emergency Stop Recovery:**
```python
async def check_emergency_recovery():
    """Check if conditions have improved enough to exit emergency stop"""
    if not health_monitor.is_emergency_stop():
        return
    
    # Check if success rate has improved
    recent_success_rate = health_monitor.get_recent_success_rate(window_minutes=10)
    
    if recent_success_rate > failure_threshold * 1.5:  # 50% above threshold
        logger.info(f"Network conditions improved (success_rate={recent_success_rate:.2%}), exiting emergency stop")
        health_monitor.exit_emergency_stop()
        
        # Resume operations
        await resume_normal_operations()
    else:
        logger.debug(f"Still in emergency stop, success_rate={recent_success_rate:.2%}")
```

**State Persistence Recovery:**
```python
async def recover_state_persistence():
    """Recover from state persistence failure"""
    try:
        # Try to load state
        state = await state_persistence.load_state()
        logger.info(f"Loaded {len(state)} nodes from persisted state")
        return state
    except FileNotFoundError:
        logger.warning("No persisted state found, starting fresh")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted state file: {e}")
        
        # Backup corrupted file
        backup_path = state_file_path + f".corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(state_file_path, backup_path)
        logger.info(f"Backed up corrupted state to {backup_path}")
        
        # Start fresh
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading state: {e}", exc_info=True)
        return {}
```

## Testing Strategy

### Dual Testing Approach

The Traceroute Mapper will be tested using both unit tests and property-based tests:

**Unit Tests:**
- Configuration parsing and validation
- Node state tracking for specific scenarios
- Priority queue operations (enqueue, dequeue, overflow)
- Rate limiter token bucket mechanics
- State persistence file I/O
- Traceroute request/response handling for specific cases
- Error handling for edge cases

**Property-Based Tests:**
- Direct node filtering across all node types
- Priority queue ordering with random request sequences
- Rate limiting with random request timing
- Node filtering with random blacklists/whitelists
- Queue overflow behavior with random priorities
- Retry backoff calculation for all attempt numbers
- State persistence round-trip with random node states
- Statistics accuracy with random operation sequences
- Protocol compliance for all traceroute messages

### Property-Based Testing Configuration

All property tests will use the Hypothesis library for Python with the following configuration:
- Minimum 100 iterations per test
- Each test tagged with: **Feature: network-traceroute-mapper, Property {number}: {property_text}**
- Custom generators for NodeState, TracerouteRequest, Message objects, and configuration dictionaries

### Test Organization

```
tests/
├── unit/
│   └── traceroute_mapper/
│       ├── test_config.py
│       ├── test_node_state_tracker.py
│       ├── test_priority_queue.py
│       ├── test_rate_limiter.py
│       ├── test_traceroute_manager.py
│       ├── test_state_persistence.py
│       └── test_network_health_monitor.py
│
└── property/
    └── traceroute_mapper/
        ├── test_node_filtering.py
        ├── test_priority_queue_properties.py
        ├── test_rate_limiting.py
        ├── test_retry_logic.py
        ├── test_state_persistence_properties.py
        ├── test_protocol_compliance.py
        └── test_statistics_accuracy.py
```

### Example Property Test

```python
from hypothesis import given, strategies as st
import pytest

@given(
    nodes=st.lists(node_state_strategy(), min_size=1, max_size=50),
    blacklist=st.lists(st.text(min_size=9, max_size=9), max_size=10)
)
def test_blacklist_filtering(nodes, blacklist):
    """
    Feature: network-traceroute-mapper, Property 17: Blacklist Filtering
    
    For any node on the configured blacklist, the Traceroute_Mapper should not
    queue a traceroute request for that node.
    """
    config = {'blacklist': blacklist}
    tracker = NodeStateTracker(config)
    queue = PriorityQueue(max_size=100)
    
    # Add all nodes to tracker
    for node in nodes:
        tracker.update_node(node.node_id, node.is_direct, node.snr, node.rssi)
    
    # Try to queue traceroutes for all nodes
    for node in nodes:
        if tracker.should_trace_node(node.node_id):
            queue.enqueue(node.node_id, priority=8, reason="test")
    
    # Verify no blacklisted nodes are in queue
    queued_nodes = []
    while not queue.is_empty():
        request = queue.dequeue()
        queued_nodes.append(request.node_id)
    
    for node_id in queued_nodes:
        assert node_id not in blacklist, f"Blacklisted node {node_id} was queued"
```

### Integration Testing

Integration tests will verify:
- Message flow from Meshtastic interface through message router to traceroute mapper
- Traceroute request sending through Meshtastic interface
- Traceroute response handling and parsing
- MQTT message forwarding through MQTT Gateway
- State persistence across plugin restarts
- Priority queue behavior under load
- Rate limiting with real timing

### Performance Testing

Performance tests will measure:
- Queue operations throughput (enqueue/dequeue per second)
- Node state tracker lookup performance
- State persistence save/load time
- Memory usage with large node counts (1000+ nodes)
- Rate limiter overhead
- Traceroute response processing latency

## Implementation Notes

### Dependencies

**Required Python Packages:**
- Standard library only (asyncio, json, dataclasses, datetime, etc.)
- No external dependencies required

**Integration Dependencies:**
- Meshtastic interface (existing)
- Message Router (existing)
- MQTT Gateway plugin (existing, optional)

### Meshtastic Traceroute Protocol

**Traceroute Request Format:**
```python
# Create traceroute request message
message = Message(
    recipient_id=target_node_id,
    message_type=MessageType.ROUTING,  # TRACEROUTE_APP in Meshtastic
    content="",  # Empty content for traceroute
    hop_limit=max_hops,
    metadata={
        'want_response': True,
        'route_discovery': True,
        'request_id': str(uuid.uuid4())
    }
)
```

**Traceroute Response Format:**
```python
# Traceroute response contains route array in metadata
response_metadata = {
    'route': [
        {'node_id': '!gateway', 'snr': 10.5, 'rssi': -75},
        {'node_id': '!relay1', 'snr': 5.2, 'rssi': -85},
        {'node_id': '!relay2', 'snr': -2.1, 'rssi': -92},
        {'node_id': '!target', 'snr': -5.2, 'rssi': -95}
    ],
    'request_id': 'original-request-id'
}
```

### Configuration Best Practices

**Recommended Settings for Small Networks (<50 nodes):**
```yaml
traceroute_mapper:
  enabled: true
  traceroutes_per_minute: 2  # More aggressive
  queue_max_size: 100
  recheck_interval_hours: 12  # Less frequent
  max_hops: 5  # Smaller network
  initial_discovery_enabled: true
```

**Recommended Settings for Large Networks (>100 nodes):**
```yaml
traceroute_mapper:
  enabled: true
  traceroutes_per_minute: 1  # Conservative
  queue_max_size: 500
  recheck_interval_hours: 24  # Less frequent
  max_hops: 7
  initial_discovery_enabled: false  # Gradual discovery
  congestion_detection:
    enabled: true
    success_rate_threshold: 0.6
```

**Recommended Settings for High-Density Networks:**
```yaml
traceroute_mapper:
  enabled: true
  traceroutes_per_minute: 0.5  # Very conservative (1 every 2 minutes)
  queue_max_size: 1000
  recheck_interval_hours: 48  # Very infrequent
  skip_direct_nodes: true
  min_snr_threshold: -10  # Only trace nodes with decent signal
  quiet_hours:
    enabled: true
    start_time: "20:00"
    end_time: "08:00"
```

### Async/Await Patterns

All operations use async/await to prevent blocking:

```python
async def _process_queue_loop(self):
    """Background task to process traceroute queue"""
    while True:
        try:
            # Check if we should process (not in quiet hours, not emergency stop)
            if not self._should_process_queue():
                await asyncio.sleep(60)
                continue
            
            # Check if queue has requests
            if self.priority_queue.is_empty():
                await asyncio.sleep(10)
                continue
            
            # Dequeue next request
            request = await self.priority_queue.dequeue()
            if not request:
                continue
            
            # Wait for rate limiter
            await self.rate_limiter.acquire()
            
            # Send traceroute (non-blocking)
            asyncio.create_task(self._send_traceroute_async(request))
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            self.logger.error(f"Error in queue processing loop: {e}", exc_info=True)
            await asyncio.sleep(5)
```

### Plugin Lifecycle

```python
# Initialization
plugin = TracerouteMapperPlugin(name, config, plugin_manager)
await plugin.initialize()

# Startup
await plugin.start()
# - Loads persisted state (if enabled)
# - Starts background tasks (queue processing, periodic rechecks, state persistence)
# - Registers with message router
# - Runs initial discovery (if enabled)

# Runtime
# - Receives node discovery events via handle_message()
# - Receives traceroute responses via handle_message()
# - Processes queue in background
# - Sends traceroute requests
# - Forwards messages to MQTT Gateway
# - Persists state periodically

# Shutdown
await plugin.stop()
# - Stops background tasks
# - Saves final state to disk
# - Clears queue (optional)
# - Cleans up resources
```

### Monitoring and Observability

**Health Check Endpoint:**
```python
async def get_health_status(self) -> Dict[str, Any]:
    """Get plugin health status"""
    return {
        'healthy': self.enabled and self.initialized and not self.health_monitor.is_emergency_stop(),
        'enabled': self.enabled,
        'initialized': self.initialized,
        'emergency_stop': self.health_monitor.is_emergency_stop(),
        'queue_size': self.priority_queue.size(),
        'pending_traceroutes': self.traceroute_manager.get_pending_count(),
        'nodes_tracked': len(self.node_tracker.get_all_nodes()),
        'direct_nodes': len(self.node_tracker.get_direct_nodes()),
        'indirect_nodes': len(self.node_tracker.get_indirect_nodes()),
        'traceroutes_sent': self.stats['traceroutes_sent'],
        'traceroutes_successful': self.stats['traceroutes_successful'],
        'traceroutes_failed': self.stats['traceroutes_failed'],
        'success_rate': self.stats['traceroutes_successful'] / max(self.stats['traceroutes_sent'], 1),
        'last_traceroute_time': self.stats.get('last_traceroute_time'),
        'current_rate': self.rate_limiter.get_current_rate(),
        'is_throttled': self.health_monitor.should_throttle(),
        'is_quiet_hours': self.health_monitor.is_quiet_hours()
    }
```

**Metrics to Track:**
- Traceroutes sent (counter)
- Traceroutes successful (counter)
- Traceroutes failed (counter)
- Traceroutes timeout (counter)
- Queue size (gauge)
- Pending traceroutes (gauge)
- Nodes tracked (gauge)
- Direct nodes (gauge)
- Indirect nodes (gauge)
- Success rate (gauge)
- Average response time (histogram)
- Queue wait time (histogram)

### Future Enhancements

**Potential Future Features:**
- Topology change detection (compare routes over time)
- Path quality scoring (prefer routes with better SNR/RSSI)
- Automatic mesh optimization suggestions
- Integration with mapping visualization tools
- Export topology data in standard formats (GraphML, JSON)
- Historical topology analysis
- Anomaly detection (unusual route changes)
- Predictive maintenance (detect failing nodes)
- Multi-gateway coordination (avoid duplicate traceroutes)
- Advanced scheduling (trace critical paths more frequently)
