# ZephyrGate Features Overview

> Transform your Meshtastic network into a powerful communication platform with emergency response, automation, and intelligence.

---

## At a Glance

**ZephyrGate** is the most comprehensive gateway solution for Meshtastic mesh networks. Whether you're coordinating emergency response, building a community network, or integrating with existing systems, ZephyrGate provides the tools you need.

### Why ZephyrGate?

- **🤖 Intelligent Automation** - Smart auto-responses, scheduled broadcasts, and AI integration
- **📡 Network Intelligence** - Automatic topology mapping and health monitoring
- **🌐 Works Anywhere** - Full functionality with or without internet connectivity
- **🔌 Plug & Play** - Docker deployment, web interface, and extensive documentation
- **🎯 Battle-Tested** - Property-based testing ensures reliability under all conditions
- **🚨 Emergency Ready** - Built-in SOS handling, responder coordination, and automatic escalation

---

## Key Highlights

### 🤖 Intelligent Auto-Response
Never miss a message with keyword-based auto-responses, emergency detection, and customizable rules. Greet new users automatically and provide instant information.

### 📅 Scheduled Broadcasts & Automation
Automate weather updates, status announcements, and system reports. Schedule messages by time or interval, and call plugin functions for dynamic content.

### 🗺️ Network Topology Mapping
Automatically discover and map your mesh network with intelligent traceroutes. Visualize network structure and identify connectivity issues.

### � MQTT Gateway
Forward mesh messages to MQTT brokers for cloud integration and visualization. Compatible with Meshtastic mapping tools and monitoring systems.

### 💬 Bulletin Board System (BBS)
Classic BBS experience with message boards, private mail, and JS8Call integration. Synchronize across multiple nodes for network-wide communication.

### 📊 Web Administration
Monitor and manage your gateway through a modern web interface. Real-time dashboards, user management, and configuration tools at your fingertips.

### 🌤️ Weather & Alert Services
Integrate NOAA, Open-Meteo, earthquake alerts, and emergency broadcast systems. Keep your network informed with automatic weather updates and severe weather warnings.

### � Email Gateway
Bridge your mesh network to the internet with bidirectional email. Send and receive emails, manage group messaging, and enable remote communication.

### 🎮 Interactive Games & Education
Engage your community with card games, strategy games, and ham radio exam practice. Build camaraderie and provide entertainment during downtime.

### � Flexible Deployment
Deploy with internet for full features, or run completely offline. Two configuration templates make setup simple for any environment.

### 🔧 Asset Tracking
Track equipment, personnel, and resources with check-in/check-out workflows. Perfect for emergency response, events, and operational accountability.

### 🚨 Emergency Response System
Coordinate life-saving operations with automatic SOS detection, responder tracking, and escalation workflows. Handle multiple simultaneous incidents with complete audit trails.

---

## Core Architecture

### Unified Gateway Design

ZephyrGate consolidates multiple mesh network services into a single, cohesive application. The modular architecture allows you to enable only the features you need, reducing complexity and resource usage.

**Key Benefits:**
- **Single Application**: No need to manage multiple services
- **Modular Design**: Enable/disable features independently
- **Offline Capable**: Full functionality without internet
- **Docker Ready**: One-command deployment with Docker Compose
- **Web Management**: Configure everything through your browser

### Multi-Interface Support

Connect to your Meshtastic devices however you prefer:

- **Serial/USB**: Direct connection via USB cable (most reliable)
- **TCP/IP**: Network connection to WiFi-enabled devices
- **Bluetooth LE**: Wireless connection to compatible radios
- **Multiple Simultaneous**: Connect to multiple radios at once

Each interface type supports automatic reconnection, health monitoring, and failover capabilities.

---

## Emergency Response System

### Comprehensive SOS Management

The emergency response system is designed for real-world incident coordination:

**Alert Types:**
- `SOS` - General emergency
- `SOSP` - Police emergency
- `SOSF` - Fire emergency
- `SOSM` - Medical emergency

**Features:**
- **Automatic Logging**: Every alert logged with timestamp, location, and details
- **Responder Coordination**: Track who's responding to each incident
- **Multiple Incidents**: Handle several emergencies simultaneously
- **Escalation System**: Automatic escalation for unacknowledged alerts
- **Check-in System**: Periodic check-ins with SOS users
- **Resolution Tracking**: Complete audit trail from alert to resolution

### Incident Workflow

1. **Alert Detection**: User sends SOS message
2. **Automatic Logging**: System creates incident record
3. **Responder Notification**: Designated responders are alerted
4. **Coordination**: Responders acknowledge and coordinate
5. **Check-ins**: System checks in with SOS user periodically
6. **Resolution**: Incident marked resolved with notes

### Emergency Commands

```
SOS [message]           # Trigger general emergency alert
SOSP [message]          # Police emergency
SOSF [message]          # Fire emergency
SOSM [message]          # Medical emergency
ACK [incident#]         # Acknowledge alert (responders)
RESPONDING [incident#]  # Indicate you're responding
CLEAR                   # Clear your active alert
SAFE                    # Indicate you're safe
CANCEL                  # Cancel false alarm
```

---

## Intelligent Auto-Response System

### Smart Keyword Detection

The auto-response system monitors all messages for keywords and responds automatically:

**Emergency Keywords**: Automatically detect distress signals
- `help`, `emergency`, `urgent`, `mayday`, `sos`, `distress`
- Triggers emergency escalation workflow
- Notifies responders if no acknowledgment

**Custom Rules**: Define your own keyword-based responses
- Priority-based execution (1 = highest priority)
- Rate limiting to prevent spam
- Cooldown periods between responses
- Per-user response limits

**New Node Greeting**: Welcome new users automatically
- Customizable greeting message
- Configurable delay to prevent spam
- One-time or periodic greetings

### Advanced Features

**Hop Limit Control**: Ensure responses reach the sender
- `add_one` mode: Add 1 hop to incoming message count
- `fixed` mode: Use a specific hop limit
- `default` mode: Use Meshtastic default

**Plugin Integration**: Call plugin functions in responses
- Weather forecasts on demand
- Network statistics
- Custom plugin methods

**AI Integration**: Optional AI-powered responses
- Local LLM support (Ollama, etc.)
- Aircraft detection (high-altitude nodes)
- Contextual understanding
- Graceful fallback when unavailable

### Example Auto-Response Rules

```yaml
custom_rules:
  # High priority: Emergency detection
  - keywords: ['help', 'emergency']
    response: "🚨 Emergency detected! Help is on the way."
    priority: 1
    cooldown_seconds: 60
    enabled: true
  
  # Medium priority: Network info
  - keywords: ['info', 'status']
    response: "📡 Network online | Send 'help' for commands"
    priority: 40
    cooldown_seconds: 120
    enabled: true
  
  # Test responses
  - keywords: ['test', 'ping']
    response: "✅ System operational"
    priority: 50
    hop_limit_mode: "add_one"  # Ensure response reaches sender
    enabled: true
```

---

## Scheduled Broadcasts & Automation

### Flexible Scheduling

Automate messages and tasks with powerful scheduling options:

**Schedule Types:**
- **Cron**: Time-based scheduling (daily, weekly, specific times)
- **Interval**: Repeat every N seconds/minutes/hours
- **One-Time**: Schedule a single future message

**Message Types:**
- **Text Messages**: Simple announcements and updates
- **Plugin Calls**: Dynamic content from plugins (weather, events, etc.)
- **Shell Commands**: Execute local commands and broadcast results

### Plugin-Powered Broadcasts

Call any plugin function to generate dynamic content:

**Weather Forecasts:**
```yaml
- name: "Morning Weather"
  plugin_name: "weather_service"
  plugin_method: "get_forecast_report"
  plugin_args:
    user_id: "system"
    days: 3
  schedule_type: "cron"
  cron_expression: "0 7 * * *"  # 7 AM daily
  hop_limit: 3
```

**Compact Weather (GC Format):**
```yaml
- name: "Compact Weather"
  plugin_name: "weather_service"
  plugin_method: "get_gc_forecast"
  plugin_args:
    hours: 8
    fields: ["hour", "icon", "temp", "precip"]
  schedule_type: "cron"
  cron_expression: "0 6,12,18 * * *"  # 3x daily
```

**Community Events:**
```yaml
- name: "Daily Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    format_type: "meshtastic"
    date_range: "today"
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
```

### Hop Limit Control

Control how far your broadcasts travel:
- **1 hop**: Only direct neighbors
- **3 hops**: Standard range (default)
- **7 hops**: Maximum range (entire network)

Configure per-broadcast for optimal network usage.

---

## Weather & Alert Services

### Multi-Source Weather Data

Access weather information from multiple providers:

**NOAA (US):**
- National Weather Service data
- Highly accurate for US locations
- Severe weather alerts
- Marine forecasts

**Open-Meteo (Worldwide):**
- Free, no API key required
- Global coverage
- Hourly and daily forecasts
- Historical data

**Features:**
- Location-based forecasts (ZIP, GPS, city name)
- Automatic updates (configurable interval)
- Offline caching for reliability
- Imperial or metric units

### Emergency Alert Integration

Stay informed with real-time emergency alerts:

**FEMA iPAWS/EAS:**
- Emergency Alert System integration
- Presidential alerts
- State and local emergencies
- AMBER alerts

**NOAA Weather Alerts:**
- Severe thunderstorm warnings
- Tornado warnings
- Flash flood warnings
- Winter storm warnings
- Configurable severity threshold

**USGS Earthquake Alerts:**
- Real-time earthquake detection
- Configurable magnitude threshold
- Radius-based filtering
- Automatic notifications

**USGS Volcano Alerts:**
- Volcanic activity monitoring
- Eruption warnings
- Ash fall alerts

### Weather Commands

```
wx                      # Current weather
forecast [days]         # Multi-day forecast
alerts                  # Active weather alerts
wxset [location]        # Set your location
```

---

## Email Gateway Integration

### Bidirectional Email Bridge

Connect your mesh network to the internet with full email integration:

**Mesh to Email:**
- Send emails from mesh devices
- Standard SMTP support
- Attachment support (text)
- Queue management with retry

**Email to Mesh:**
- Receive emails on mesh
- IMAP/POP3 support
- Automatic polling
- Spam filtering

### Group Messaging

Organize users with tag-based groups:

**Features:**
- Join/leave groups dynamically
- Send to entire groups
- Multiple group membership
- Group management commands

**Commands:**
```
email/to@domain.com/Subject/Message    # Send email
tagin/GROUPNAME                        # Join group
tagout                                 # Leave group
tagsend/TAG/message                    # Message group
```

### Security & Control

**Authorized Senders:**
- Whitelist email addresses
- Prevent unauthorized broadcasts
- Per-user permissions

**Blocklist:**
- Block spam senders
- Automatic filtering
- User-managed blocklist

---

## Bulletin Board System (BBS)

### Classic BBS Experience

Bring the nostalgia of bulletin board systems to your mesh network:

**Features:**
- Menu-driven interface
- Public message boards
- Private mail system
- Channel directory
- Multi-node synchronization

### Message Boards

**Fixed Boards:**
- General - Community discussion
- Emergency - Emergency communications
- Trading - Buy/sell/trade
- Events - Community events
- Technical - Technical discussions

**Features:**
- Threaded discussions
- Read/unread tracking
- Search capability
- Moderation tools

### Private Mail

**Personal Messaging:**
- Send/receive private messages
- Inbox management
- Read receipts
- Cross-node delivery

### JS8Call Integration

Bridge your mesh network to HF radio:

**Features:**
- TCP API connection to JS8Call
- Monitor specific groups
- Message bridging
- Urgent message handling

**Use Cases:**
- Long-distance communication
- Emergency backup
- Ham radio integration
- Multi-band coordination

---

## Interactive Games & Education

### Card Games

**BlackJack:**
- Classic casino game
- Betting system
- Multiple hands
- Statistics tracking

**Video Poker:**
- Jacks or Better
- Betting and payouts
- Hand rankings
- Win tracking

### Strategy Games

**Mastermind:**
- Code-breaking puzzle
- Multiple difficulty levels
- Hint system
- Leaderboards

**Tic-Tac-Toe:**
- Classic strategy game
- Player vs player
- Quick gameplay

### Simulation Games

**DopeWars:**
- Economic simulation
- Buy low, sell high
- Random events
- High score tracking

**Lemonade Stand:**
- Business simulation
- Weather affects sales
- Resource management
- Profit tracking

**Golf Simulator:**
- 18-hole golf game
- Club selection
- Wind and terrain
- Score tracking

### Word Games

**Hangman:**
- Classic word guessing
- Multiple categories
- Difficulty levels
- Hint system

### Educational Features

**Ham Radio Exam Practice:**
- FCC Technician questions
- FCC General questions
- FCC Extra questions
- Instant feedback
- Score tracking

**Quizzes:**
- General knowledge
- Technical topics
- Custom quizzes
- Leaderboards

---

## Web Administration Interface

### Real-Time Dashboard

Monitor your gateway through a modern web interface:

**System Status:**
- CPU and memory usage
- Network connectivity
- Service health
- Active connections

**Node Information:**
- Real-time node list
- Signal strength (SNR/RSSI)
- Last seen timestamps
- Location data

**Active Alerts:**
- Emergency incidents
- Weather warnings
- System alerts
- User notifications

**Message Monitoring:**
- Live message feed
- Filter by channel/user
- Search history
- Export capabilities

### User Management

**User Profiles:**
- View user information
- Edit user details
- Subscription management
- Activity history

**Permission Management:**
- Role-based access control
- Admin privileges
- Service access
- Command permissions

### Configuration Management

**Web-Based Configuration:**
- Edit settings through browser
- Syntax validation
- Live preview
- Backup/restore

**Service Control:**
- Start/stop services
- Restart components
- View logs
- Health checks

### Monitoring & Analytics

**Performance Metrics:**
- Message throughput
- Response times
- Error rates
- Resource usage

**Usage Statistics:**
- Command usage
- Popular features
- User activity
- Network statistics

**Alert History:**
- Historical incidents
- Response times
- Resolution data
- Trend analysis

---

## Network Topology Mapping

### Automatic Network Discovery

The traceroute mapper automatically discovers and maps your mesh network topology:

**Intelligent Tracerouting:**
- Priority-based queue (new nodes first)
- Skip direct nodes (1-hop neighbors)
- Periodic rechecks for topology changes
- Retry logic with exponential backoff

**Network Health Protection:**
- Rate limiting (configurable traceroutes/minute)
- Quiet hours (pause during specific times)
- Congestion detection (auto-throttle)
- Emergency stop (pause if network unhealthy)

**Node Filtering:**
- Blacklist specific nodes
- Whitelist only certain nodes
- Filter by role (skip CLIENT nodes)
- SNR threshold filtering

### Topology Visualization

**MQTT Integration:**
- Forward traceroutes to MQTT brokers
- Compatible with Meshtastic mapping tools
- Standard Meshtastic MQTT protocol
- JSON or Protobuf format

**State Persistence:**
- Save node discovery state
- Traceroute history per node
- Survive restarts
- Periodic auto-save

### Configuration Options

```yaml
traceroute_mapper:
  enabled: false  # Disabled by default
  traceroutes_per_minute: 1  # Rate limit
  max_hops: 7  # Maximum trace depth
  recheck_interval_hours: 6  # Periodic updates
  skip_direct_nodes: true  # Skip 1-hop neighbors
  forward_to_mqtt: true  # Send to MQTT
```

---

## MQTT Gateway

### Cloud Integration

Forward mesh messages to MQTT brokers for cloud integration and visualization:

**Features:**
- One-way uplink (mesh to MQTT)
- Standard Meshtastic MQTT protocol
- JSON or Protobuf format
- TLS/SSL encryption support

**Message Filtering:**
- Filter by channel
- Filter by message type
- Selective forwarding
- Rate limiting

**Reliability:**
- Message queue (1000 messages)
- Automatic reconnection
- Exponential backoff
- Connection health monitoring

### MQTT Configuration

```yaml
mqtt_gateway:
  enabled: false
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"  # or "protobuf"
  tls_enabled: false
  
  # Channel filtering
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: []  # All types
  
  # Rate limiting
  max_messages_per_second: 10
  burst_multiplier: 2
```

### Use Cases

**Network Visualization:**
- Meshtastic mapping tools
- Custom dashboards
- Real-time monitoring

**Data Analysis:**
- Message analytics
- Network performance
- Usage patterns

**Integration:**
- Home automation
- IoT platforms
- Custom applications

---

## Asset Tracking & Management

### Check-In/Check-Out System

Track personnel, equipment, and resources:

**Features:**
- Check-in with notes
- Check-out with notes
- Current status view
- Historical tracking
- Integration with emergency system

**Commands:**
```
checkin [notes]         # Check in
checkout [notes]        # Check out
checklist              # View status
```

**Use Cases:**
- Emergency response accountability
- Event staff management
- Equipment tracking
- Operational coordination

### Asset Categories

Organize assets by type:
- Personnel
- Equipment
- Vehicles
- Supplies

**Auto-Checkout:**
- Configurable timeout (default 24 hours)
- Automatic status updates
- Notification system

---

## Data Management & Persistence

### Database Systems

**SQLite Primary Storage:**
- ACID compliance
- Automatic backups
- Corruption detection
- Schema migrations

**File Storage:**
- Configuration files
- Cache management
- State persistence
- Log files

### Backup & Recovery

**Automated Backups:**
- Scheduled database backups
- Configuration backups
- Incremental backups
- Retention policies

**Export/Import:**
- Data portability
- System migration
- Disaster recovery
- Configuration templates

---

## Security & Privacy

### Permission System

**Role-Based Access Control:**
- Admin privileges
- Trusted nodes
- Service access
- Command permissions

**Node Authentication:**
- Optional authentication
- Trusted node list
- Permission inheritance
- Access logging

### Rate Limiting

**Network Protection:**
- Per-node rate limits
- Burst allowance
- Automatic throttling
- Abuse prevention

**Service Limits:**
- Command rate limits
- API rate limits
- Resource quotas
- Fair usage policies

### Privacy Controls

**Data Protection:**
- Encrypted storage
- Secure transmission
- Privacy settings
- Data retention policies

**Audit Logging:**
- Complete activity logs
- Security events
- Access tracking
- Compliance reporting

---

## Deployment Options

### Docker Deployment

**One-Command Setup:**
```bash
docker-compose up -d
```

**Features:**
- Pre-built images
- Multi-architecture (ARM/x86)
- Health checks
- Auto-restart
- Volume management

### Configuration Templates

**With Internet:**
- Full feature set
- Weather services
- Email gateway
- MQTT integration
- AI services

**Without Internet:**
- Core features only
- BBS and emergency
- Games and bot
- Asset tracking
- Web interface (local)

### System Requirements

**Minimum:**
- 1 CPU core
- 512 MB RAM
- 1 GB storage
- Linux/macOS/Windows

**Recommended:**
- 2 CPU cores
- 1 GB RAM
- 5 GB storage
- Docker support

---

## Integration Capabilities

### External Services

**Weather APIs:**
- NOAA
- Open-Meteo
- Custom providers

**Email Services:**
- SMTP/IMAP
- Gmail
- Custom servers

**AI Services:**
- Ollama (local)
- OpenAI
- Anthropic
- Custom LLMs

**Ham Radio:**
- JS8Call
- Hamlib
- APRS (planned)

### Plugin Architecture

**Modular Design:**
- Enable/disable features
- Plugin discovery
- Dependency management
- Health monitoring

**Extensibility:**
- Custom plugins
- Event system
- API integration
- Command framework

---

## Use Cases

### Emergency Services

**Search & Rescue:**
- Coordinate SAR operations
- Track responders
- Share location data
- Emergency communications

**Disaster Response:**
- Communication during outages
- Resource coordination
- Status updates
- Evacuation management

**Public Safety:**
- Law enforcement coordination
- Fire department operations
- Medical response
- Multi-agency coordination

### Community Networks

**Neighborhood Networks:**
- Local communication
- Community announcements
- Event coordination
- Information sharing

**Event Management:**
- Large event coordination
- Staff communication
- Attendee information
- Emergency procedures

### Ham Radio Operations

**Emergency Communications:**
- ARES/RACES support
- Emergency nets
- Traffic handling
- Resource coordination

**Contest Operations:**
- Multi-operator coordination
- Logging integration
- Real-time updates
- Score tracking

### Commercial Applications

**Asset Tracking:**
- Equipment management
- Personnel tracking
- Inventory control
- Operational accountability

**Remote Operations:**
- Field team coordination
- Status reporting
- Resource management
- Communication backup

---

## Getting Started

### Quick Start

1. **Install Docker** (if not already installed)
2. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/zephyrgate.git
   cd zephyrgate
   ```
3. **Choose Configuration**
   - With internet: `cp config/config-example.yaml config/config.yaml`
   - Without internet: `cp config/config-example-no-internet.yaml config/config.yaml`
4. **Edit Configuration**
   - Set your Meshtastic interface
   - Configure desired features
   - Set admin password
5. **Start ZephyrGate**
   ```bash
   docker-compose up -d
   ```
6. **Access Web Interface**
   - Open http://localhost:8080
   - Login with admin/changeme
   - Change password immediately

### Documentation

- **Quick Start Guide**: `docs/QUICK_START.md`
- **User Manual**: `docs/USER_MANUAL.md`
- **Admin Guide**: `docs/ADMIN_GUIDE.md`
- **API Documentation**: `docs/API.md`
- **Plugin Development**: `docs/PLUGIN_DEVELOPMENT.md`

### Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Comprehensive guides and references
- **Examples**: Sample configurations and use cases
- **Community**: Join discussions and share experiences

---

## Why Choose ZephyrGate?

### Comprehensive Feature Set

ZephyrGate isn't just a gateway - it's a complete communication platform. From emergency response to entertainment, from automation to integration, ZephyrGate provides everything you need to build a powerful mesh network.

### Battle-Tested Reliability

With property-based testing covering all critical components, ZephyrGate is designed to work reliably under all conditions. Automatic error recovery, health monitoring, and graceful degradation ensure your network stays operational.

### Flexible Deployment

Whether you have internet connectivity or not, ZephyrGate adapts to your environment. Two configuration templates make setup simple, and the modular architecture lets you enable only what you need.

### Active Development

ZephyrGate is actively developed with regular updates, new features, and community feedback integration. The plugin architecture ensures extensibility for future needs.

### Open Source

ZephyrGate is open source, allowing you to inspect, modify, and contribute to the codebase. No vendor lock-in, no hidden costs, complete transparency.

---

**Ready to transform your Meshtastic network? Get started with ZephyrGate today.**
