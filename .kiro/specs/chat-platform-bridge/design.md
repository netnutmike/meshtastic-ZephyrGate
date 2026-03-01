# Chat Platform Bridge - Design Document

## Architecture Overview

The Chat Platform Bridge follows the established plugin architecture pattern used by the MQTT Gateway and other ZephyrGate plugins. It provides bidirectional message forwarding between Meshtastic mesh networks and Slack/Discord chat platforms.

```
┌─────────────────────────────────────────────────────────────┐
│                    ZephyrGate Core                          │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   Message    │◄───────►│   Plugin     │                 │
│  │   Router     │         │   Manager    │                 │
│  └──────────────┘         └──────────────┘                 │
└────────────┬────────────────────┬──────────────────────────┘
             │                    │
             │                    │
             ▼                    ▼
┌────────────────────────────────────────────────────────────┐
│          Chat Platform Bridge Plugin                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Bridge Manager (Coordinator)              │  │
│  │  - Plugin lifecycle management                      │  │
│  │  - Configuration loading                            │  │
│  │  - Health monitoring                                │  │
│  │  - Message routing coordination                     │  │
│  └────────┬──────────────────────────┬─────────────────┘  │
│           │                          │                     │
│           ▼                          ▼                     │
│  ┌─────────────────┐       ┌─────────────────┐           │
│  │  Slack Bridge   │       │ Discord Bridge  │           │
│  │  - Connection   │       │  - Connection   │           │
│  │  - Send/Receive │       │  - Send/Receive │           │
│  │  - Queue Mgmt   │       │  - Queue Mgmt   │           │
│  └────────┬────────┘       └────────┬────────┘           │
│           │                          │                     │
│           ▼                          ▼                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         Message Transformer & Filter                │  │
│  │  - Format conversion                                │  │
│  │  - Length truncation                                │  │
│  │  - Filtering rules                                  │  │
│  │  - Loop prevention                                  │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
             │                          │
             ▼                          ▼
    ┌────────────────┐        ┌────────────────┐
    │  Slack API     │        │  Discord API   │
    │  (WebSocket)   │        │  (Gateway)     │
    └────────────────┘        └────────────────┘
```

## Component Design

### 1. ChatPlatformBridgePlugin (Main Plugin Class)

The main plugin class that coordinates all bridge operations.

**Responsibilities:**
- Plugin lifecycle (initialize, start, stop, cleanup)
- Configuration loading and validation
- Instantiate and manage platform bridges
- Route messages between mesh and platforms
- Health status aggregation
- Web interface integration

**Key Methods:**
```python
class ChatPlatformBridgePlugin:
    async def initialize(self) -> bool
    async def start(self) -> bool
    async def stop(self) -> bool
    async def cleanup(self) -> bool
    
    async def _handle_mesh_message(self, message: Message, context: Dict) -> Optional[Any]
    async def _route_to_platforms(self, message: Message)
    async def _handle_platform_message(self, platform: str, message: PlatformMessage)
    
    async def get_health_status(self) -> Dict[str, Any]
    def get_metadata(self) -> PluginMetadata
```

### 2. BasePlatformBridge (Abstract Base Class)

Abstract base class for platform-specific implementations.

**Responsibilities:**
- Define common interface for all platforms
- Shared queue management logic
- Common filtering and transformation
- Loop prevention tracking
- Connection health monitoring

**Key Methods:**
```python
class BasePlatformBridge(ABC):
    @abstractmethod
    async def connect(self) -> bool
    
    @abstractmethod
    async def disconnect(self) -> bool
    
    @abstractmethod
    async def send_message(self, channel_id: str, content: str, metadata: Dict) -> bool
    
    @abstractmethod
    async def _listen_for_messages(self)
    
    async def queue_outbound_message(self, message: Message)
    async def _process_outbound_queue(self)
    async def _process_inbound_queue(self)
    
    def _should_forward_to_platform(self, message: Message) -> bool
    def _should_forward_to_mesh(self, platform_msg: PlatformMessage) -> bool
    def _transform_mesh_to_platform(self, message: Message) -> str
    def _transform_platform_to_mesh(self, platform_msg: PlatformMessage) -> str
    
    async def get_health_status(self) -> Dict[str, Any]
```

### 3. SlackBridge (Slack Implementation)

Slack-specific implementation using slack-sdk.

**Responsibilities:**
- Slack WebSocket connection (Socket Mode)
- Send messages to Slack channels
- Receive messages from Slack channels
- Handle Slack-specific formatting
- Manage Slack API rate limits

**Key Attributes:**
```python
class SlackBridge(BasePlatformBridge):
    bot_token: str
    app_token: str  # For Socket Mode
    use_socket_mode: bool
    client: WebClient
    socket_client: SocketModeClient
    channel_mappings: List[ChannelMapping]
    outbound_queue: asyncio.Queue
    inbound_queue: asyncio.Queue
    connected: bool
    last_error: Optional[str]
```

**Slack Message Format:**
```
📡 [NodeName] (ID: !abc123)
Message content here
---
Channel: LongFast | Hops: 3 | 14:23:45
```

### 4. DiscordBridge (Discord Implementation)

Discord-specific implementation using discord.py.

**Responsibilities:**
- Discord Gateway connection
- Send messages to Discord channels
- Receive messages from Discord channels
- Handle Discord-specific formatting
- Manage Discord API rate limits

**Key Attributes:**
```python
class DiscordBridge(BasePlatformBridge):
    bot_token: str
    client: discord.Client
    channel_mappings: List[ChannelMapping]
    outbound_queue: asyncio.Queue
    inbound_queue: asyncio.Queue
    connected: bool
    last_error: Optional[str]
```

**Discord Message Format:**
```
📡 **[NodeName]** (ID: !abc123)
Message content here
---
*Channel: LongFast | Hops: 3 | 14:23:45*
```

### 5. MessageTransformer

Handles message format conversion and filtering.

**Responsibilities:**
- Convert mesh messages to platform format
- Convert platform messages to mesh format
- Apply length limits and truncation
- Strip/convert formatting
- Add metadata and context

**Key Methods:**
```python
class MessageTransformer:
    @staticmethod
    def mesh_to_platform(message: Message, platform: str, config: Dict) -> str
    
    @staticmethod
    def platform_to_mesh(content: str, sender: str, platform: str, config: Dict) -> str
    
    @staticmethod
    def truncate_for_mesh(content: str, max_length: int = 237) -> str
    
    @staticmethod
    def format_metadata(message: Message, platform: str) -> str
    
    @staticmethod
    def strip_formatting(content: str) -> str
```

### 6. MessageFilter

Applies filtering rules to messages.

**Responsibilities:**
- Check message against filter rules
- Whitelist/blacklist checking
- Content filtering (keywords)
- Message type filtering
- Length validation

**Key Methods:**
```python
class MessageFilter:
    def __init__(self, config: Dict):
        self.mesh_to_platform_rules = config.get('mesh_to_platform', {})
        self.platform_to_mesh_rules = config.get('platform_to_mesh', {})
    
    def should_forward_to_platform(self, message: Message) -> bool
    def should_forward_to_mesh(self, platform_msg: PlatformMessage) -> bool
    
    def _check_node_filters(self, node_id: str, rules: Dict) -> bool
    def _check_content_filters(self, content: str, rules: Dict) -> bool
    def _check_length_filters(self, content: str, rules: Dict) -> bool
```

### 7. ChannelMapping

Represents a mapping between mesh and platform channels.

**Attributes:**
```python
@dataclass
class ChannelMapping:
    mesh_channel: str
    platform_channel_id: str
    bidirectional: bool = True
    mesh_to_platform: bool = True
    platform_to_mesh: bool = True
    priority: str = "normal"  # low, normal, high
    
    def allows_mesh_to_platform(self) -> bool
    def allows_platform_to_mesh(self) -> bool
```

### 8. PlatformMessage

Represents a message from a chat platform.

**Attributes:**
```python
@dataclass
class PlatformMessage:
    platform: str  # "slack" or "discord"
    channel_id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: datetime
    message_id: str
    is_bot: bool = False
    mentions: List[str] = field(default_factory=list)
```

### 9. LoopPrevention

Prevents message loops between platforms.

**Responsibilities:**
- Track recently forwarded messages
- Detect potential loops
- Prevent duplicate forwarding
- Time-based expiration

**Key Methods:**
```python
class LoopPrevention:
    def __init__(self, window_seconds: int = 60):
        self.seen_messages: Dict[str, datetime] = {}
        self.window = timedelta(seconds=window_seconds)
    
    def is_duplicate(self, message_id: str) -> bool
    def mark_seen(self, message_id: str)
    def cleanup_old_entries(self)
    
    @staticmethod
    def generate_message_hash(content: str, sender: str) -> str
```

### 10. RateLimiter

Manages rate limiting for both directions.

**Responsibilities:**
- Token bucket algorithm
- Per-platform rate limits
- Burst handling
- Queue backpressure

**Key Methods:**
```python
class RateLimiter:
    def __init__(self, max_per_minute: int, burst_multiplier: float = 2.0):
        self.max_per_minute = max_per_minute
        self.burst_multiplier = burst_multiplier
        self.tokens = max_per_minute * burst_multiplier
        self.last_update = datetime.now()
    
    async def acquire(self, tokens: int = 1) -> bool
    def _refill_tokens(self)
    def get_available_tokens(self) -> float
```

## Data Flow

### Mesh → Platform Flow

```
1. Mesh message received by ZephyrGate
   ↓
2. Message Router forwards to ChatPlatformBridgePlugin
   ↓
3. Plugin._handle_mesh_message() called
   ↓
4. Check if message should be forwarded (filters)
   ↓
5. Determine target platforms and channels (mappings)
   ↓
6. For each platform:
   a. Transform message to platform format
   b. Check loop prevention
   c. Add to outbound queue
   ↓
7. Platform bridge processes queue
   ↓
8. Rate limiter checks availability
   ↓
9. Send to platform API
   ↓
10. Update statistics and health status
```

### Platform → Mesh Flow

```
1. Platform message received via WebSocket/Gateway
   ↓
2. Platform bridge._listen_for_messages() receives it
   ↓
3. Create PlatformMessage object
   ↓
4. Check if message should be forwarded (filters)
   ↓
5. Check loop prevention (not our own bot)
   ↓
6. Transform message to mesh format
   ↓
7. Add to inbound queue
   ↓
8. Process inbound queue
   ↓
9. Rate limiter checks availability
   ↓
10. Send to mesh via plugin_manager.send_message()
   ↓
11. Update statistics and health status
```

## Configuration Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "enabled": {"type": "boolean"},
    "slack": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"},
        "bot_token": {"type": "string"},
        "app_token": {"type": "string"},
        "use_socket_mode": {"type": "boolean"},
        "channels": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "mesh_channel": {"type": "string"},
              "slack_channel_id": {"type": "string"},
              "bidirectional": {"type": "boolean"},
              "mesh_to_slack": {"type": "boolean"},
              "slack_to_mesh": {"type": "boolean"},
              "priority": {"enum": ["low", "normal", "high"]}
            },
            "required": ["mesh_channel", "slack_channel_id"]
          }
        }
      },
      "required": ["bot_token"]
    },
    "discord": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"},
        "bot_token": {"type": "string"},
        "channels": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "mesh_channel": {"type": "string"},
              "discord_channel_id": {"type": "string"},
              "bidirectional": {"type": "boolean"},
              "mesh_to_discord": {"type": "boolean"},
              "discord_to_mesh": {"type": "boolean"},
              "priority": {"enum": ["low", "normal", "high"]}
            },
            "required": ["mesh_channel", "discord_channel_id"]
          }
        }
      },
      "required": ["bot_token"]
    },
    "filtering": {
      "type": "object",
      "properties": {
        "mesh_to_platform": {
          "type": "object",
          "properties": {
            "message_types": {"type": "array", "items": {"type": "string"}},
            "exclude_nodes": {"type": "array", "items": {"type": "string"}},
            "include_nodes": {"type": "array", "items": {"type": "string"}},
            "min_length": {"type": "integer", "minimum": 0},
            "max_length": {"type": "integer", "minimum": 1}
          }
        },
        "platform_to_mesh": {
          "type": "object",
          "properties": {
            "require_prefix": {"type": "boolean"},
            "command_prefix": {"type": "string"},
            "exclude_users": {"type": "array", "items": {"type": "string"}},
            "include_users": {"type": "array", "items": {"type": "string"}},
            "min_length": {"type": "integer", "minimum": 0},
            "max_length": {"type": "integer", "minimum": 1},
            "truncate_long": {"type": "boolean"}
          }
        }
      }
    },
    "rate_limiting": {
      "type": "object",
      "properties": {
        "mesh_to_platform": {
          "type": "object",
          "properties": {
            "max_messages_per_minute": {"type": "integer", "minimum": 1},
            "burst_multiplier": {"type": "number", "minimum": 1.0}
          }
        },
        "platform_to_mesh": {
          "type": "object",
          "properties": {
            "max_messages_per_minute": {"type": "integer", "minimum": 1},
            "burst_multiplier": {"type": "number", "minimum": 1.0}
          }
        }
      }
    },
    "queue_settings": {
      "type": "object",
      "properties": {
        "outbound_max_size": {"type": "integer", "minimum": 10},
        "inbound_max_size": {"type": "integer", "minimum": 10},
        "persist_queues": {"type": "boolean"}
      }
    },
    "loop_prevention": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"},
        "window_seconds": {"type": "integer", "minimum": 10}
      }
    }
  },
  "required": ["enabled"]
}
```

## Error Handling

### Connection Errors
- Automatic reconnection with exponential backoff
- Max backoff: 5 minutes
- Log all connection attempts
- Update health status

### API Errors
- Retry transient errors (3 attempts)
- Log permanent errors
- Skip message on permanent failure
- Alert on repeated failures

### Queue Overflow
- Discard oldest messages
- Log overflow events
- Alert if overflow is frequent
- Consider increasing queue size

### Rate Limit Errors
- Respect platform rate limits
- Backoff when rate limited
- Queue messages for later
- Log rate limit events

## Security Considerations

### Token Management
- Store tokens in environment variables
- Never log tokens
- Validate tokens on startup
- Rotate tokens periodically

### Message Validation
- Validate all incoming messages
- Sanitize content for injection
- Check message length limits
- Verify sender authenticity

### Access Control
- Whitelist/blacklist users
- Channel-level permissions
- Admin-only configuration
- Audit logging

## Performance Optimization

### Async Operations
- All I/O operations are async
- Non-blocking queue processing
- Concurrent platform handling
- Efficient event loops

### Queue Management
- Bounded queues prevent memory issues
- FIFO processing ensures fairness
- Batch processing where possible
- Queue metrics for monitoring

### Connection Pooling
- Reuse WebSocket connections
- Connection health checks
- Graceful reconnection
- Minimal overhead

## Testing Strategy

### Unit Tests
- Test each component in isolation
- Mock platform APIs
- Test error conditions
- Test edge cases

### Integration Tests
- Test full message flow
- Test with real APIs (optional)
- Test reconnection logic
- Test queue overflow

### Property-Based Tests
- Message transformation properties
- Queue behavior properties
- Rate limiter properties
- Filter logic properties

## Monitoring & Observability

### Metrics
- Messages forwarded (per platform, per direction)
- Queue sizes (current, max)
- Connection uptime
- Error counts
- Rate limit hits
- Latency (queue to send)

### Health Checks
- Connection status
- Queue health
- Error rate
- Last successful message
- API availability

### Logging
- Connection events (connect, disconnect, reconnect)
- Message forwarding (debug level)
- Errors with full context
- Rate limit events
- Configuration changes

## Deployment Considerations

### Dependencies
```
slack-sdk>=3.19.0
discord.py>=2.3.0
aiohttp>=3.8.0
```

### Environment Variables
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
DISCORD_BOT_TOKEN=...
```

### Configuration File
```yaml
# config/config.yaml
plugins:
  chat_platform_bridge:
    enabled: true
    # ... rest of config
```

### Docker Support
- Add dependencies to requirements.txt
- Environment variables in docker-compose.yml
- Volume mount for persistent queues (optional)
- Health check endpoint

## Future Enhancements

### Phase 2
- File/image attachment support
- Markdown formatting conversion
- Thread support
- Reaction synchronization

### Phase 3
- Matrix protocol support
- Telegram integration
- Microsoft Teams integration
- Mattermost support

### Phase 4
- Voice channel integration
- Video call notifications
- Screen sharing alerts
- Presence synchronization
