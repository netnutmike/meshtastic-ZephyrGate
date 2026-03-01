# Chat Platform Bridge - Requirements

## Overview

Integrate Slack and Discord with ZephyrGate to enable bidirectional communication between Meshtastic mesh networks and popular chat platforms. This allows mesh users to communicate with team members on Slack/Discord and vice versa, extending the reach of the mesh network beyond radio range.

## Goals

1. Enable mesh messages to be forwarded to Slack/Discord channels
2. Allow Slack/Discord users to send messages to the mesh network
3. Support multiple channels per platform
4. Provide flexible filtering and routing rules
5. Maintain message context and user identification
6. Ensure reliable delivery with queue management
7. Support both platforms with a unified architecture

## Non-Goals

- File/image attachments (text only initially)
- Rich formatting (markdown conversion is optional)
- Thread support (flat message structure)
- Voice/video integration
- Bot commands on chat platforms (mesh commands only)

## Use Cases

### Emergency Coordination
- Emergency responders on mesh can coordinate with command center on Slack
- Incident updates broadcast to both mesh and Discord channels
- Remote team members can monitor mesh activity

### Community Networks
- Neighborhood mesh network bridged to community Discord server
- Local events announced on both platforms
- Questions from Discord users answered by mesh users

### Ham Radio Operations
- Field operators on mesh coordinate with net control on Slack
- Contest updates shared across platforms
- Emergency nets accessible to remote operators

### Remote Monitoring
- Monitor mesh network activity from anywhere via Slack/Discord
- Send commands to mesh devices remotely
- Receive alerts and notifications on mobile devices

## Functional Requirements

### FR1: Slack Integration

#### FR1.1: Slack Bot Setup
- Support Slack Bot Token authentication
- Connect to Slack workspace via WebSocket (Socket Mode) or Events API
- Automatic reconnection on connection loss
- Health monitoring and status reporting

#### FR1.2: Message Forwarding (Mesh → Slack)
- Forward mesh messages to configured Slack channels
- Include sender information (node name, ID)
- Include message metadata (timestamp, channel, hop count)
- Support emoji/icon indicators for message types
- Rate limiting to prevent spam

#### FR1.3: Message Receiving (Slack → Mesh)
- Monitor configured Slack channels for messages
- Forward messages to mesh network
- Prefix with sender name/username
- Filter bot messages (prevent loops)
- Support @mentions for direct messages

#### FR1.4: Channel Mapping
- Map mesh channels to Slack channels (1:1 or many:1)
- Support multiple Slack channels
- Configurable routing rules per channel
- Default channel for unmapped messages

### FR2: Discord Integration

#### FR2.1: Discord Bot Setup
- Support Discord Bot Token authentication
- Connect via Discord Gateway API
- Automatic reconnection on connection loss
- Health monitoring and status reporting

#### FR2.2: Message Forwarding (Mesh → Discord)
- Forward mesh messages to configured Discord channels
- Include sender information (node name, ID)
- Include message metadata (timestamp, channel, hop count)
- Support emoji/icon indicators for message types
- Rate limiting to prevent spam

#### FR2.3: Message Receiving (Discord → Mesh)
- Monitor configured Discord channels for messages
- Forward messages to mesh network
- Prefix with sender name/username
- Filter bot messages (prevent loops)
- Support @mentions for direct messages

#### FR2.4: Channel Mapping
- Map mesh channels to Discord channels (1:1 or many:1)
- Support multiple Discord channels
- Configurable routing rules per channel
- Default channel for unmapped messages

### FR3: Message Filtering & Routing

#### FR3.1: Mesh → Platform Filtering
- Filter by mesh channel name
- Filter by message type (text, position, telemetry, etc.)
- Filter by sender (whitelist/blacklist)
- Filter by content (keyword matching)
- Minimum/maximum message length

#### FR3.2: Platform → Mesh Filtering
- Filter by platform channel
- Filter by sender (whitelist/blacklist)
- Filter by content (keyword matching)
- Command prefix requirement (e.g., "!mesh")
- Minimum/maximum message length

#### FR3.3: Message Transformation
- Truncate long messages to mesh limits (237 chars)
- Strip mentions/formatting for mesh
- Add sender prefix for platform messages
- Optional emoji/icon translation
- Character encoding handling

### FR4: Queue Management

#### FR4.1: Outbound Queue (Mesh → Platform)
- Queue messages when platform unavailable
- Configurable queue size (default 1000)
- FIFO processing
- Discard oldest on overflow
- Persist queue across restarts (optional)

#### FR4.2: Inbound Queue (Platform → Mesh)
- Queue messages when mesh unavailable
- Configurable queue size (default 100)
- FIFO processing
- Discard oldest on overflow
- Rate limiting to protect mesh

### FR5: Reliability & Error Handling

#### FR5.1: Connection Management
- Automatic reconnection with exponential backoff
- Connection health monitoring
- Graceful degradation on failure
- Status reporting to web interface

#### FR5.2: Error Handling
- Log all errors with context
- Retry failed message sends (configurable)
- Alert on repeated failures
- Graceful handling of API rate limits

#### FR5.3: Loop Prevention
- Detect and prevent message loops
- Track message IDs to avoid duplicates
- Filter own bot messages
- Configurable loop detection window

### FR6: Configuration

#### FR6.1: Platform Configuration
```yaml
chat_platform_bridge:
  enabled: true
  
  slack:
    enabled: true
    bot_token: "xoxb-your-token"
    app_token: "xapp-your-token"  # For Socket Mode
    use_socket_mode: true  # or Events API
    
    channels:
      - mesh_channel: "LongFast"
        slack_channel_id: "C01234567"
        bidirectional: true
        mesh_to_slack: true
        slack_to_mesh: true
        
      - mesh_channel: "Emergency"
        slack_channel_id: "C98765432"
        bidirectional: true
        priority: high
  
  discord:
    enabled: true
    bot_token: "your-discord-token"
    
    channels:
      - mesh_channel: "LongFast"
        discord_channel_id: "123456789012345678"
        bidirectional: true
        mesh_to_discord: true
        discord_to_mesh: true
        
      - mesh_channel: "Emergency"
        discord_channel_id: "987654321098765432"
        bidirectional: true
        priority: high
```

#### FR6.2: Filtering Configuration
```yaml
  filtering:
    mesh_to_platform:
      message_types: ["TEXT_MESSAGE_APP"]
      exclude_nodes: []
      include_nodes: []  # Empty = all
      min_length: 1
      max_length: 1000
      
    platform_to_mesh:
      require_prefix: false
      command_prefix: "!mesh"
      exclude_users: []  # Bot IDs
      include_users: []  # Empty = all
      min_length: 1
      max_length: 237
      truncate_long: true
```

#### FR6.3: Rate Limiting
```yaml
  rate_limiting:
    mesh_to_platform:
      max_messages_per_minute: 30
      burst_multiplier: 2
      
    platform_to_mesh:
      max_messages_per_minute: 10
      burst_multiplier: 1.5
```

### FR7: Monitoring & Status

#### FR7.1: Health Status
- Connection status per platform
- Message queue sizes
- Messages forwarded (counters)
- Error counts and last error
- Uptime and reconnection count

#### FR7.2: Web Interface Integration
- Display connection status
- Show recent messages
- Configuration management
- Manual reconnect button
- Statistics dashboard

#### FR7.3: Logging
- Log all forwarded messages (configurable level)
- Log connection events
- Log errors with full context
- Separate log file for bridge activity

## Technical Requirements

### TR1: Dependencies
- `slack-sdk` (Python) for Slack integration
- `discord.py` for Discord integration
- Async/await support throughout
- JSON schema validation for config

### TR2: Performance
- Handle 100+ messages per minute
- Queue processing latency < 1 second
- Reconnection time < 30 seconds
- Memory usage < 100 MB per platform

### TR3: Security
- Secure token storage (environment variables)
- No token logging
- Validate all incoming messages
- Prevent injection attacks
- Rate limiting to prevent abuse

### TR4: Compatibility
- Python 3.8+
- Compatible with existing plugin architecture
- No breaking changes to core system
- Works with all mesh interface types

## Success Criteria

1. Messages successfully forwarded in both directions
2. Connection maintained with automatic recovery
3. No message loops or duplicates
4. Rate limiting prevents network abuse
5. Configuration is clear and well-documented
6. Web interface shows accurate status
7. Logs provide useful debugging information
8. Performance meets technical requirements

## Future Enhancements

- File/image attachment support
- Markdown formatting conversion
- Thread support (Discord threads, Slack threads)
- Slash commands on platforms
- User presence synchronization
- Reaction synchronization
- Voice channel integration
- Matrix protocol support
- Telegram integration
- Microsoft Teams integration

## Documentation Requirements

1. Setup guide for Slack bot creation
2. Setup guide for Discord bot creation
3. Configuration reference
4. Troubleshooting guide
5. Security best practices
6. Example configurations
7. API documentation
