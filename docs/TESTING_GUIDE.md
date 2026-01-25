# ZephyrGate Comprehensive Testing Guide

**Version**: 1.0  
**Last Updated**: 2026-01-25  
**Status**: Complete Testing Framework

## Table of Contents

1. [Overview](#overview)
2. [Testing Environment Setup](#testing-environment-setup)
3. [Testing Methods](#testing-methods)
4. [Core System Testing](#core-system-testing)
5. [Plugin Testing](#plugin-testing)
6. [Integration Testing](#integration-testing)
7. [Performance Testing](#performance-testing)
8. [Meshtastic Connection Testing](#meshtastic-connection-testing)
9. [Automated Testing](#automated-testing)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This guide provides comprehensive testing procedures for all ZephyrGate features, including:
- **8 Service Plugins**: Bot, Emergency, BBS, Weather, Email, Asset, Web, Ping
- **Core Systems**: Message routing, plugin management, database, health monitoring
- **Meshtastic Integration**: Device connection, message reception/transmission
- **40+ Commands**: Across all service plugins
- **Scheduled Tasks**: Background jobs and automation
- **Web Interface**: Admin panel and plugin management

### Testing Objectives

1. **Functional Testing**: Verify all features work as designed
2. **Integration Testing**: Ensure components work together
3. **Performance Testing**: Validate system under load
4. **Reliability Testing**: Test error handling and recovery
5. **User Acceptance**: Confirm usability and workflows

---

## Testing Environment Setup

### Prerequisites

**Hardware:**
- Meshtastic device (LoRa radio)
- USB connection to computer
- Optional: Second Meshtastic device for end-to-end testing

**Software:**
- Python 3.8+
- ZephyrGate installed
- Meshtastic CLI tools
- Database (SQLite)

### Environment Configuration


#### 1. Install Test Dependencies

```bash
# Install ZephyrGate with test dependencies
pip install -r requirements.txt

# Install Meshtastic CLI
pip install meshtastic

# Install testing tools
pip install pytest pytest-asyncio hypothesis
```

#### 2. Configure Test Environment

Create `config/config.yaml` for testing:

```yaml
environment: development
database:
  path: "data/zephyrgate_test.db"
  
meshtastic:
  interface_primary:
    type: "serial"
    port: "/dev/cu.usbmodem9070698283041"  # Adjust for your device
    
plugins:
  paths:
    - "plugins"
    - "examples/plugins"
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "bbs_service"
    - "weather_service"
    - "email_service"
    - "asset_service"
    - "web_service"
    - "ping_responder"
```

#### 3. Initialize Test Database

```bash
# Create test database
python -c "from src.core.database import DatabaseManager; db = DatabaseManager('data/zephyrgate_test.db'); db.initialize()"
```

#### 4. Start ZephyrGate

```bash
# Start in development mode
python -m src.main

# Or use the start script
./start.sh
```

---

## Testing Methods

### Method 1: Live Meshtastic Testing

Send messages from a physical Meshtastic device.

**Advantages:**
- Real-world testing
- Tests full message flow
- Validates radio communication

**Setup:**
```bash
# Start ZephyrGate
python -m src.main

# Monitor logs in another terminal
tail -f logs/zephyrgate_dev.log
```

**Send Test Message:**
From your Meshtastic device, send: `ping`

### Method 2: Meshtastic CLI Testing

Use the Meshtastic CLI to send test messages.

**Advantages:**
- Scriptable
- Repeatable
- No need for second device

**Commands:**
```bash
# Check device connection
meshtastic --port /dev/cu.usbmodem9070698283041 --info

# Send test message
meshtastic --port /dev/cu.usbmodem9070698283041 --sendtext "help"

# Monitor messages
meshtastic --port /dev/cu.usbmodem9070698283041 --listen
```

### Method 3: Automated Test Suite

Run the automated test suite.

**Advantages:**
- Comprehensive coverage
- Fast execution
- Regression testing

**Commands:**
```bash
# Run all tests
pytest

# Run specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/property/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/integration/test_plugin_system_integration.py
```

### Method 4: Web Interface Testing

Test through the web admin interface.

**Advantages:**
- Visual feedback
- User experience testing
- Plugin management testing

**Access:**
```
http://localhost:8080
```

### Method 5: Direct API Testing

Test internal APIs directly with Python scripts.

**Advantages:**
- Precise control
- Component isolation
- Debug capabilities

**Example:**
```python
import asyncio
from src.core.message_router import CoreMessageRouter
from src.models.message import Message, MessageType

async def test_command():
    router = CoreMessageRouter(config)
    msg = Message(
        id="test_1",
        sender_id="!test",
        content="ping",
        message_type=MessageType.TEXT
    )
    await router.route_message(msg)

asyncio.run(test_command())
```

---


## Core System Testing

### 1. System Startup Testing

**Objective**: Verify ZephyrGate starts correctly with all components.

**Test Steps:**
```bash
# 1. Start ZephyrGate
python -m src.main

# 2. Check logs for successful startup
grep "ZephyrGate started successfully" logs/zephyrgate_dev.log

# 3. Verify all components initialized
grep "initialized" logs/zephyrgate_dev.log | tail -20
```

**Expected Results:**
- ✅ Configuration loaded
- ✅ Database initialized
- ✅ Plugin manager started
- ✅ Message router active
- ✅ Health monitor running
- ✅ Meshtastic interface connected
- ✅ All enabled plugins loaded

**Success Criteria:**
- No ERROR messages in logs
- All plugins show "Successfully started"
- Meshtastic connection established

### 2. Configuration Testing

**Objective**: Verify configuration loading and validation.

**Test Cases:**

| Test Case | Action | Expected Result |
|-----------|--------|-----------------|
| Valid config | Start with valid config.yaml | System starts successfully |
| Missing config | Remove config.yaml | Uses default.yaml |
| Invalid YAML | Corrupt config syntax | Error message, uses defaults |
| Invalid values | Set invalid port number | Validation error, uses defaults |
| Environment override | Set ENV variables | ENV values take precedence |

**Test Steps:**
```bash
# Test 1: Valid configuration
python -m src.main
# Check: System starts normally

# Test 2: Missing configuration
mv config/config.yaml config/config.yaml.bak
python -m src.main
# Check: Uses default.yaml

# Test 3: Invalid configuration
echo "invalid: yaml: syntax:" > config/config.yaml
python -m src.main
# Check: Error logged, uses defaults

# Restore configuration
mv config/config.yaml.bak config/config.yaml
```

### 3. Database Testing

**Objective**: Verify database operations.

**Test Steps:**
```bash
# 1. Initialize database
python -c "from src.core.database import DatabaseManager; db = DatabaseManager(); db.initialize()"

# 2. Check database file exists
ls -la data/zephyrgate_dev.db

# 3. Verify tables created
sqlite3 data/zephyrgate_dev.db ".tables"

# 4. Test data insertion
python -c "
from src.core.database import DatabaseManager
db = DatabaseManager()
db.execute('INSERT INTO messages (sender_id, content) VALUES (?, ?)', ('test', 'test message'))
"

# 5. Test data retrieval
sqlite3 data/zephyrgate_dev.db "SELECT * FROM messages LIMIT 5;"
```

**Expected Results:**
- ✅ Database file created
- ✅ All tables exist
- ✅ Data can be inserted
- ✅ Data can be queried
- ✅ No corruption errors

### 4. Message Router Testing

**Objective**: Verify message routing to correct handlers.

**Test Steps:**
```bash
# 1. Check router initialization
grep "Message router" logs/zephyrgate_dev.log

# 2. Verify service registration
grep "Registered service" logs/zephyrgate_dev.log

# 3. Send test message via Meshtastic
# From device: "ping"

# 4. Check routing logs
grep "Routing message" logs/zephyrgate_dev.log | tail -5

# 5. Verify handler execution
grep "Command handled" logs/zephyrgate_dev.log | tail -5
```

**Expected Results:**
- ✅ Router starts successfully
- ✅ All services registered
- ✅ Messages routed to correct handler
- ✅ Responses sent back
- ✅ No routing errors

### 5. Plugin Manager Testing

**Objective**: Verify plugin discovery, loading, and management.

**Test Cases:**

| Test Case | Action | Expected Result |
|-----------|--------|-----------------|
| Plugin discovery | Start system | All plugins in paths discovered |
| Plugin loading | Enable plugin | Plugin loaded successfully |
| Plugin initialization | Load plugin | initialize() called, returns True |
| Plugin start | Start plugin | start() called, returns True |
| Plugin stop | Stop plugin | stop() called, cleanup performed |
| Plugin reload | Reload plugin | Old instance stopped, new loaded |
| Dependency check | Load with deps | Dependencies validated |
| Version check | Load plugin | ZephyrGate version validated |

**Test Steps:**
```bash
# 1. Check plugin discovery
grep "Discovered.*plugins" logs/zephyrgate_dev.log

# 2. Check plugin loading
grep "Loading plugin" logs/zephyrgate_dev.log

# 3. Check plugin initialization
grep "initialized" logs/zephyrgate_dev.log | grep plugin

# 4. Check plugin start
grep "Successfully started plugin" logs/zephyrgate_dev.log

# 5. List loaded plugins
# Via web interface: http://localhost:8080/plugins
# Or check logs for plugin status
```

### 6. Health Monitoring Testing

**Objective**: Verify health monitoring and reporting.

**Test Steps:**
```bash
# 1. Check health monitor start
grep "Health monitor" logs/zephyrgate_dev.log

# 2. Check periodic health checks
grep "Health check" logs/zephyrgate_dev.log | tail -10

# 3. View health status
# Via web interface: http://localhost:8080/health
# Or via API call:
curl http://localhost:8080/api/health

# 4. Simulate unhealthy condition
# Stop a critical service and check detection

# 5. Verify alerts
grep "UNHEALTHY" logs/zephyrgate_dev.log
```

**Expected Results:**
- ✅ Health monitor active
- ✅ Periodic checks running
- ✅ All components healthy
- ✅ Unhealthy conditions detected
- ✅ Alerts generated

---


## Plugin Testing

### Plugin 1: Bot Service

**Commands**: `help`, `ping`, `info`, `history`, `games`, `play`

#### Test Plan: Bot Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| BOT-001 | help | `help` | List of all commands | ⏳ |
| BOT-002 | help specific | `help ping` | Help for ping command | ⏳ |
| BOT-003 | ping | `ping` | "Pong! Bot service is running." | ⏳ |
| BOT-004 | info | `info weather` | Information about weather | ⏳ |
| BOT-005 | history | `history` | Last 10 messages | ⏳ |
| BOT-006 | history count | `history 5` | Last 5 messages | ⏳ |
| BOT-007 | games | `games` | List of available games | ⏳ |
| BOT-008 | play | `play blackjack` | Start blackjack game | ⏳ |

**Detailed Test Steps:**

```bash
# Test BOT-001: Help command
echo "Test: help command"
# Send from Meshtastic: help
# Expected: List of commands with descriptions

# Test BOT-002: Help for specific command
# Send from Meshtastic: help ping
# Expected: "ping - Test bot responsiveness"

# Test BOT-003: Ping command
# Send from Meshtastic: ping
# Expected: "Pong! Bot service is running."

# Test BOT-004: Info command
# Send from Meshtastic: info weather
# Expected: Information about weather services

# Test BOT-005: History command
# Send from Meshtastic: history
# Expected: Last 10 messages with timestamps

# Test BOT-006: History with count
# Send from Meshtastic: history 5
# Expected: Last 5 messages

# Test BOT-007: Games list
# Send from Meshtastic: games
# Expected: List of games (blackjack, dopewars, lemonade, golf, trivia)

# Test BOT-008: Play game
# Send from Meshtastic: play blackjack
# Expected: Game starts, shows initial hand
```

**Verification:**
```bash
# Check bot service logs
grep "bot_service" logs/zephyrgate_dev.log | tail -20

# Check command execution
grep "Command.*handled" logs/zephyrgate_dev.log | grep -E "(help|ping|info|history|games|play)"
```

### Plugin 2: Emergency Service

**Commands**: `sos`, `sosp`, `sosf`, `sosm`, `cancel`, `respond`, `status`, `incidents`, `checkin`

#### Test Plan: Emergency Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| EMG-001 | sos | `sos Test emergency` | Alert created, incident ID assigned | ⏳ |
| EMG-002 | sos police | `sosp Need police` | Police emergency alert | ⏳ |
| EMG-003 | sos fire | `sosf Fire spotted` | Fire emergency alert | ⏳ |
| EMG-004 | sos medical | `sosm Medical help` | Medical emergency alert | ⏳ |
| EMG-005 | respond | `respond 12345` | Registered as responder | ⏳ |
| EMG-006 | status | `status` | Show active incidents | ⏳ |
| EMG-007 | status specific | `status 12345` | Show incident details | ⏳ |
| EMG-008 | incidents | `incidents` | List all active incidents | ⏳ |
| EMG-009 | checkin | `checkin` | Check-in recorded | ⏳ |
| EMG-010 | cancel | `cancel` | SOS cancelled | ⏳ |

**Detailed Test Steps:**

```bash
# Test EMG-001: SOS command
# Send from Meshtastic: sos Test emergency at campsite
# Expected: 
# - Alert broadcast
# - Incident ID assigned (e.g., #12345)
# - Location recorded
# - Responders notified

# Test EMG-002: Police SOS
# Send from Meshtastic: sosp Need police assistance
# Expected: Police emergency alert with type indicator

# Test EMG-003: Fire SOS
# Send from Meshtastic: sosf Wildfire spotted
# Expected: Fire emergency alert

# Test EMG-004: Medical SOS
# Send from Meshtastic: sosm Injured hiker
# Expected: Medical emergency alert

# Test EMG-005: Respond to incident
# Send from Meshtastic: respond 12345
# Expected: "You are now responding to incident #12345"

# Test EMG-006: Check status
# Send from Meshtastic: status
# Expected: Your active incidents and responder status

# Test EMG-007: Check specific incident
# Send from Meshtastic: status 12345
# Expected: Details of incident #12345

# Test EMG-008: List all incidents
# Send from Meshtastic: incidents
# Expected: All active incidents with details

# Test EMG-009: Check in
# Send from Meshtastic: checkin
# Expected: Check-in recorded, next check-in time

# Test EMG-010: Cancel SOS
# Send from Meshtastic: cancel
# Expected: "Emergency alert cancelled"
```

**Verification:**
```bash
# Check emergency service logs
grep "emergency_service" logs/zephyrgate_dev.log | tail -30

# Check incident creation
grep "Incident.*created" logs/zephyrgate_dev.log

# Check database for incidents
sqlite3 data/zephyrgate_dev.db "SELECT * FROM emergency_incidents;"
```

**⚠️ IMPORTANT**: Never test SOS on production/live networks!

### Plugin 3: BBS Service

**Commands**: `bbs`, `read`, `post`, `mail`, `directory`

#### Test Plan: BBS Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| BBS-001 | bbs menu | `bbs` | Main BBS menu | ⏳ |
| BBS-002 | read list | `read` | List of bulletins | ⏳ |
| BBS-003 | read specific | `read 1` | Bulletin #1 content | ⏳ |
| BBS-004 | post | `post Test Subject Test content` | Bulletin posted | ⏳ |
| BBS-005 | mail inbox | `mail` | Inbox with messages | ⏳ |
| BBS-006 | mail read | `mail read 1` | Message #1 content | ⏳ |
| BBS-007 | mail send | `mail send User Subject Content` | Mail sent | ⏳ |
| BBS-008 | directory | `directory` | Channel directory | ⏳ |
| BBS-009 | menu navigation | `bbs` then `1` | Navigate to bulletins | ⏳ |

**Detailed Test Steps:**

```bash
# Test BBS-001: BBS menu
# Send: bbs
# Expected: Menu with options 1-6

# Test BBS-002: Read bulletins list
# Send: read
# Expected: List of recent bulletins with IDs

# Test BBS-003: Read specific bulletin
# Send: read 1
# Expected: Full content of bulletin #1

# Test BBS-004: Post bulletin
# Send: post Trail Update North trail closed
# Expected: "Bulletin posted successfully, ID: #X"

# Test BBS-005: Check mail
# Send: mail
# Expected: Inbox with message list

# Test BBS-006: Read mail
# Send: mail read 1
# Expected: Full message content

# Test BBS-007: Send mail
# Send: mail send Bob Meeting Tomorrow at 10am
# Expected: "Mail sent successfully"

# Test BBS-008: Channel directory
# Send: directory
# Expected: List of channels with descriptions

# Test BBS-009: Menu navigation
# Send: bbs
# Wait for menu
# Send: 1
# Expected: Bulletin list
```

**Verification:**
```bash
# Check BBS logs
grep "bbs_service" logs/zephyrgate_dev.log | tail -20

# Check database
sqlite3 data/zephyrgate_dev.db "SELECT * FROM bulletins LIMIT 5;"
sqlite3 data/zephyrgate_dev.db "SELECT * FROM mail_messages LIMIT 5;"
```

### Plugin 4: Weather Service

**Commands**: `wx`, `weather`, `forecast`, `alerts`

#### Test Plan: Weather Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| WX-001 | wx current | `wx` | Current weather at location | ⏳ |
| WX-002 | wx location | `wx Seattle` | Weather for Seattle | ⏳ |
| WX-003 | wx zip | `wx 98101` | Weather for ZIP code | ⏳ |
| WX-004 | wx coords | `wx 47.6,-122.3` | Weather for coordinates | ⏳ |
| WX-005 | weather detailed | `weather` | Detailed weather info | ⏳ |
| WX-006 | forecast | `forecast` | 3-day forecast | ⏳ |
| WX-007 | forecast days | `forecast 5` | 5-day forecast | ⏳ |
| WX-008 | forecast location | `forecast 3 Portland` | 3-day for Portland | ⏳ |
| WX-009 | alerts | `alerts` | Active weather alerts | ⏳ |
| WX-010 | alerts location | `alerts Denver` | Alerts for Denver | ⏳ |

**Detailed Test Steps:**

```bash
# Test WX-001: Current weather
# Send: wx
# Expected: Temperature, conditions, humidity, wind

# Test WX-002: Weather for city
# Send: wx Seattle
# Expected: Current weather for Seattle, WA

# Test WX-003: Weather by ZIP
# Send: wx 98101
# Expected: Weather for that ZIP code

# Test WX-004: Weather by coordinates
# Send: wx 47.6062,-122.3321
# Expected: Weather for those coordinates

# Test WX-005: Detailed weather
# Send: weather
# Expected: Comprehensive weather data

# Test WX-006: Forecast
# Send: forecast
# Expected: 3-day forecast with highs/lows

# Test WX-007: Extended forecast
# Send: forecast 5
# Expected: 5-day forecast

# Test WX-008: Forecast for location
# Send: forecast 3 Portland
# Expected: 3-day forecast for Portland

# Test WX-009: Weather alerts
# Send: alerts
# Expected: Active alerts or "No active alerts"

# Test WX-010: Alerts for location
# Send: alerts Denver
# Expected: Alerts for Denver area
```

**Verification:**
```bash
# Check weather service logs
grep "weather_service" logs/zephyrgate_dev.log | tail -20

# Check API calls
grep "Weather API" logs/zephyrgate_dev.log | tail -10
```

**Note**: Weather service requires internet connection and API keys configured.

### Plugin 5: Email Service

**Commands**: `email send`, `email check`, `send`, `check`

#### Test Plan: Email Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| EMAIL-001 | send | `send user@example.com Test Hello` | Email sent | ⏳ |
| EMAIL-002 | send long | `email send user@example.com Subject Long message...` | Email sent | ⏳ |
| EMAIL-003 | check | `check` | List new emails | ⏳ |
| EMAIL-004 | check empty | `check` | "No new emails" | ⏳ |
| EMAIL-005 | invalid email | `send invalid Test` | Error message | ⏳ |
| EMAIL-006 | missing subject | `send user@example.com` | Error message | ⏳ |

**Detailed Test Steps:**

```bash
# Test EMAIL-001: Send email
# Send: send john@example.com Meeting Update Meeting at 3pm
# Expected: "Email sent successfully"

# Test EMAIL-002: Send with long message
# Send: email send team@company.com Status Report All systems operational, no issues
# Expected: Email sent

# Test EMAIL-003: Check emails
# Send: check
# Expected: List of new emails with subjects

# Test EMAIL-004: Check when empty
# Send: check
# Expected: "No new emails"

# Test EMAIL-005: Invalid email address
# Send: send invalid-email Test Message
# Expected: "Invalid email address"

# Test EMAIL-006: Missing subject
# Send: send user@example.com
# Expected: "Subject and message required"
```

**Verification:**
```bash
# Check email service logs
grep "email_service" logs/zephyrgate_dev.log | tail -20

# Check SMTP/IMAP connections
grep -E "(SMTP|IMAP)" logs/zephyrgate_dev.log | tail -10
```

**Note**: Email service requires SMTP/IMAP configuration in config.yaml.

### Plugin 6: Asset Tracking Service

**Commands**: `track`, `locate`, `status`, `checkin`, `checkout`

#### Test Plan: Asset Tracking Service

| Test ID | Command | Input | Expected Output | Status |
|---------|---------|-------|-----------------|--------|
| ASSET-001 | track register | `track VEHICLE-1` | Asset registered | ⏳ |
| ASSET-002 | track update | `track VEHICLE-1 47.6 -122.3` | Location updated | ⏳ |
| ASSET-003 | locate all | `locate` | List all assets | ⏳ |
| ASSET-004 | locate specific | `locate VEHICLE-1` | Asset location | ⏳ |
| ASSET-005 | status | `status VEHICLE-1` | Asset status details | ⏳ |
| ASSET-006 | checkin | `checkin PERSON-1` | Checked in | ⏳ |
| ASSET-007 | checkout | `checkout PERSON-1` | Checked out | ⏳ |

**Detailed Test Steps:**

```bash
# Test ASSET-001: Register asset
# Send: track VEHICLE-1
# Expected: "Asset VEHICLE-1 registered for tracking"

# Test ASSET-002: Update location
# Send: track VEHICLE-1 47.6062 -122.3321
# Expected: "Asset VEHICLE-1 location updated"

# Test ASSET-003: Locate all assets
# Send: locate
# Expected: List of all tracked assets with locations

# Test ASSET-004: Locate specific asset
# Send: locate VEHICLE-1
# Expected: Detailed location of VEHICLE-1

# Test ASSET-005: Asset status
# Send: status VEHICLE-1
# Expected: Status, location, last update, history

# Test ASSET-006: Check in
# Send: checkin PERSON-JOHN
# Expected: "PERSON-JOHN checked in"

# Test ASSET-007: Check out
# Send: checkout PERSON-JOHN
# Expected: "PERSON-JOHN checked out"
```

**Verification:**
```bash
# Check asset service logs
grep "asset_service" logs/zephyrgate_dev.log | tail -20

# Check database
sqlite3 data/zephyrgate_dev.db "SELECT * FROM assets;"
sqlite3 data/zephyrgate_dev.db "SELECT * FROM asset_locations ORDER BY timestamp DESC LIMIT 10;"
```

### Plugin 7: Web Service

**Features**: Web admin interface, plugin management, system monitoring

#### Test Plan: Web Service

| Test ID | Feature | Action | Expected Result | Status |
|---------|---------|--------|-----------------|--------|
| WEB-001 | Start server | Access http://localhost:8080 | Homepage loads | ⏳ |
| WEB-002 | Plugin list | Navigate to /plugins | List of plugins | ⏳ |
| WEB-003 | Plugin enable | Enable disabled plugin | Plugin enabled | ⏳ |
| WEB-004 | Plugin disable | Disable enabled plugin | Plugin disabled | ⏳ |
| WEB-005 | Plugin reload | Reload plugin | Plugin reloaded | ⏳ |
| WEB-006 | System status | View /health | System health info | ⏳ |
| WEB-007 | Logs view | View /logs | Recent log entries | ⏳ |
| WEB-008 | Config view | View /config | Configuration display | ⏳ |
| WEB-009 | WebSocket | Connect to /ws | Real-time updates | ⏳ |

**Detailed Test Steps:**

```bash
# Test WEB-001: Access web interface
curl http://localhost:8080
# Or open in browser: http://localhost:8080
# Expected: Homepage with navigation

# Test WEB-002: Plugin management page
curl http://localhost:8080/plugins
# Or browser: http://localhost:8080/plugins
# Expected: List of all plugins with status

# Test WEB-003: Enable plugin
# Via browser: Click "Enable" on disabled plugin
# Expected: Plugin enabled, status updated

# Test WEB-004: Disable plugin
# Via browser: Click "Disable" on enabled plugin
# Expected: Plugin disabled, status updated

# Test WEB-005: Reload plugin
# Via browser: Click "Reload" on plugin
# Expected: Plugin reloaded, new instance

# Test WEB-006: System health
curl http://localhost:8080/api/health
# Expected: JSON with system health metrics

# Test WEB-007: View logs
curl http://localhost:8080/api/logs?lines=50
# Expected: Last 50 log lines

# Test WEB-008: View configuration
curl http://localhost:8080/api/config
# Expected: Current configuration (sensitive data masked)

# Test WEB-009: WebSocket connection
# Use browser console or wscat:
wscat -c ws://localhost:8080/ws
# Expected: Connection established, real-time updates
```

**Verification:**
```bash
# Check web service logs
grep "web_service" logs/zephyrgate_dev.log | tail -20

# Check HTTP requests
grep "HTTP" logs/zephyrgate_dev.log | tail -20
```

### Plugin 8: Ping Responder

**Commands**: Auto-responds to pings

#### Test Plan: Ping Responder

| Test ID | Feature | Action | Expected Result | Status |
|---------|---------|--------|-----------------|--------|
| PING-001 | Auto-respond | Send "ping" | Auto-response | ⏳ |
| PING-002 | Case insensitive | Send "PING" | Auto-response | ⏳ |
| PING-003 | Partial match | Send "ping test" | Auto-response | ⏳ |

**Detailed Test Steps:**

```bash
# Test PING-001: Basic ping
# Send: ping
# Expected: Automatic "Pong!" response

# Test PING-002: Case variations
# Send: PING
# Expected: Response regardless of case

# Test PING-003: Ping in message
# Send: ping test
# Expected: Response if configured to match partial
```

---


## Integration Testing

### End-to-End Message Flow

**Objective**: Test complete message flow from Meshtastic device to response.

**Test Steps:**

```bash
# 1. Start ZephyrGate
python -m src.main

# 2. Monitor logs
tail -f logs/zephyrgate_dev.log

# 3. Send message from Meshtastic device
# From device: "ping"

# 4. Verify message reception
# Log should show: "Received TEXT_MESSAGE from [node_id]"

# 5. Verify routing
# Log should show: "Routing message to handlers"

# 6. Verify command execution
# Log should show: "Command 'ping' handled by bot_service"

# 7. Verify response
# Log should show: "Sending response: Pong!"

# 8. Check device for response
# Device should receive: "Pong! Bot service is running."
```

**Expected Timeline:**
- Message received: < 1 second
- Command routed: < 0.1 seconds
- Command executed: < 0.5 seconds
- Response sent: < 1 second
- **Total**: < 3 seconds end-to-end

### Multi-Plugin Interaction

**Objective**: Test plugins working together.

**Scenario 1: Emergency + Asset Tracking**

```bash
# 1. Register asset
Send: track RESPONDER-1

# 2. Create emergency
Send: sos Test emergency

# 3. Respond to emergency
Send: respond 12345

# 4. Update responder location
Send: track RESPONDER-1 47.6 -122.3

# 5. Check incident status
Send: status 12345

# Expected: Incident shows responder with location
```

**Scenario 2: BBS + Email Integration**

```bash
# 1. Post bulletin
Send: post Announcement Important meeting tomorrow

# 2. Send email notification
Send: send team@example.com Bulletin Posted Check BBS for announcement

# 3. Check mail
Send: mail

# Expected: Bulletin posted, email sent, mail system working
```

**Scenario 3: Weather + Emergency**

```bash
# 1. Check weather
Send: wx

# 2. Check alerts
Send: alerts

# 3. If severe weather, send SOS
Send: sos Severe weather, seeking shelter

# Expected: Weather data retrieved, emergency created
```

### Scheduled Tasks Testing

**Objective**: Verify scheduled tasks execute correctly.

**Test Steps:**

```bash
# 1. Check scheduled tasks in config
grep -A 10 "scheduled_tasks" config/config.yaml

# 2. Monitor task execution
grep "Scheduled task" logs/zephyrgate_dev.log | tail -20

# 3. Verify task results
# Check database or logs for task output

# 4. Test task failure handling
# Simulate task failure and verify error handling
```

**Common Scheduled Tasks:**
- Weather updates (every 30 minutes)
- Health checks (every 5 minutes)
- Database cleanup (daily)
- Email polling (every 10 minutes)
- Asset location updates (every 15 minutes)

### Database Integrity Testing

**Objective**: Verify database operations across plugins.

**Test Steps:**

```bash
# 1. Create data in multiple plugins
Send: sos Test emergency
Send: post Test Bulletin Test content
Send: track ASSET-1

# 2. Check database
sqlite3 data/zephyrgate_dev.db << EOF
SELECT COUNT(*) FROM emergency_incidents;
SELECT COUNT(*) FROM bulletins;
SELECT COUNT(*) FROM assets;
SELECT COUNT(*) FROM messages;
EOF

# 3. Verify foreign key constraints
sqlite3 data/zephyrgate_dev.db "PRAGMA foreign_key_check;"

# 4. Check for orphaned records
# Run database integrity checks

# 5. Test concurrent access
# Send multiple commands simultaneously
```

### Error Handling and Recovery

**Objective**: Test system resilience.

**Test Scenarios:**

```bash
# Scenario 1: Invalid command
Send: invalidcommand
# Expected: "Unknown command" or help message

# Scenario 2: Malformed command
Send: sos
# Expected: "Usage: sos <message>"

# Scenario 3: Plugin failure
# Stop a plugin and send command
# Expected: Error message, system continues

# Scenario 4: Database error
# Corrupt database and restart
# Expected: Database recreated or error handled

# Scenario 5: Network interruption
# Disconnect Meshtastic device
# Expected: Reconnection attempt, queued messages

# Scenario 6: High load
# Send 100 commands rapidly
# Expected: All processed, no crashes
```

---

## Performance Testing

### Load Testing

**Objective**: Test system under high message volume.

**Test Script:**

```python
# load_test.py
import asyncio
from src.core.message_router import CoreMessageRouter
from src.models.message import Message, MessageType
from datetime import datetime

async def send_messages(count=100):
    router = CoreMessageRouter(config)
    
    for i in range(count):
        msg = Message(
            id=f"test_{i}",
            sender_id="!test",
            content=f"ping {i}",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        await router.route_message(msg)
        
    print(f"Sent {count} messages")

asyncio.run(send_messages(100))
```

**Metrics to Monitor:**
- Message processing time
- Memory usage
- CPU usage
- Database query time
- Response time

**Performance Targets:**
- Message processing: < 100ms per message
- Memory usage: < 500MB
- CPU usage: < 50% average
- Database queries: < 50ms
- Response time: < 1 second

### Stress Testing

**Objective**: Find system limits.

**Test Cases:**

```bash
# Test 1: Rapid commands
# Send 1000 commands in 10 seconds
# Monitor: System stability, error rate

# Test 2: Large messages
# Send messages at max size (237 bytes for Meshtastic)
# Monitor: Processing time, memory

# Test 3: Concurrent users
# Simulate 50 simultaneous users
# Monitor: Response time, queue depth

# Test 4: Long-running operations
# Start multiple games, create emergencies
# Monitor: Resource usage over time

# Test 5: Database stress
# Create 10,000 records
# Monitor: Query performance, disk usage
```

### Memory Leak Testing

**Objective**: Detect memory leaks.

**Test Steps:**

```bash
# 1. Start ZephyrGate
python -m src.main

# 2. Monitor memory usage
watch -n 5 'ps aux | grep "python -m src.main" | grep -v grep | awk "{print \$4}"'

# 3. Send continuous commands for 1 hour
# Use load test script

# 4. Check memory growth
# Memory should stabilize, not continuously grow

# 5. Check for memory leaks
# Use memory profiler:
pip install memory_profiler
python -m memory_profiler src/main.py
```

---

## Meshtastic Connection Testing

### Device Connection

**Objective**: Verify Meshtastic device connection.

**Test Steps:**

```bash
# 1. Check device is connected
ls -la /dev/cu.usbmodem* # macOS
ls -la /dev/ttyUSB* # Linux
ls -la /dev/ttyACM* # Linux alternative

# 2. Test with Meshtastic CLI
meshtastic --port /dev/cu.usbmodem9070698283041 --info

# Expected output:
# - Device name
# - Firmware version
# - Node ID
# - Channel info

# 3. Check ZephyrGate connection
grep "Meshtastic.*connected" logs/zephyrgate_dev.log

# 4. Verify message reception
meshtastic --port /dev/cu.usbmodem9070698283041 --listen
# Send message from another device
# Check if ZephyrGate receives it
```

### Message Reception

**Objective**: Verify messages are received correctly.

**Test Steps:**

```bash
# 1. Start ZephyrGate with verbose logging
python -m src.main --log-level DEBUG

# 2. Send test message from another device
# From device: "test message"

# 3. Check logs for reception
grep "Received.*TEXT_MESSAGE" logs/zephyrgate_dev.log | tail -5

# 4. Verify message content
grep "test message" logs/zephyrgate_dev.log

# 5. Check message parsing
# Verify sender ID, timestamp, channel extracted correctly
```

### Message Transmission

**Objective**: Verify responses are sent correctly.

**Test Steps:**

```bash
# 1. Send command that generates response
# From device: "ping"

# 2. Check logs for transmission
grep "Sending.*message" logs/zephyrgate_dev.log | tail -5

# 3. Verify response received on device
# Device should show: "Pong! Bot service is running."

# 4. Check transmission errors
grep "Failed to send" logs/zephyrgate_dev.log

# 5. Verify message queue
# Check if messages are queued when device unavailable
```

### Multi-Device Testing

**Objective**: Test with multiple Meshtastic devices.

**Setup:**
- Device A: Connected to ZephyrGate
- Device B: Remote device for testing
- Device C: Optional third device

**Test Scenarios:**

```bash
# Scenario 1: Direct message
# Device B → Device A (ZephyrGate)
# Send: ping
# Expected: Response from ZephyrGate

# Scenario 2: Broadcast message
# Device B → All devices
# Send: help
# Expected: ZephyrGate responds

# Scenario 3: Multi-hop message
# Device C → Device B → Device A (ZephyrGate)
# Send: wx
# Expected: Weather response reaches Device C

# Scenario 4: Simultaneous messages
# Device B and C send at same time
# Expected: Both processed correctly
```

### Channel Testing

**Objective**: Test different Meshtastic channels.

**Test Steps:**

```bash
# 1. Configure multiple channels
# In Meshtastic app: Set up channels 0-7

# 2. Send messages on different channels
# Channel 0: ping
# Channel 1: sos test
# Channel 2: wx

# 3. Verify ZephyrGate receives all channels
grep "channel" logs/zephyrgate_dev.log | tail -20

# 4. Test channel-specific responses
# Verify responses go to correct channel
```

---


## Automated Testing

### Running the Test Suite

**Full Test Suite:**

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

**Test Categories:**

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Property-based tests only
pytest tests/property/

# Specific test file
pytest tests/unit/test_plugin_manager.py

# Specific test function
pytest tests/unit/test_plugin_manager.py::test_plugin_discovery

# Tests matching pattern
pytest -k "emergency"
```

### Unit Tests

**Coverage Areas:**
- Plugin manager
- Message router
- Database operations
- Configuration loading
- Command handlers
- Individual services

**Example Test Execution:**

```bash
# Test plugin manager
pytest tests/unit/test_plugin_manager.py -v

# Test message router
pytest tests/unit/test_message_router.py -v

# Test emergency service
pytest tests/unit/test_emergency_service.py -v

# Test BBS service
pytest tests/unit/test_bbs_sync_service.py -v

# Test weather service
pytest tests/unit/test_weather_service.py -v
```

### Integration Tests

**Coverage Areas:**
- End-to-end workflows
- Multi-plugin interactions
- Database integration
- External API integration
- Web interface

**Example Test Execution:**

```bash
# Test plugin system integration
pytest tests/integration/test_plugin_system_integration.py -v

# Test emergency integration
pytest tests/integration/test_emergency_integration.py -v

# Test BBS integration
pytest tests/integration/test_bbs_functionality.py -v

# Test weather integration
pytest tests/integration/test_weather_integration.py -v

# Test web admin
pytest tests/integration/test_web_admin_integration.py -v
```

### Property-Based Tests

**Coverage Areas:**
- Command routing properties
- Configuration validation
- Error handling
- Message routing
- Plugin lifecycle

**Example Test Execution:**

```bash
# Test command routing properties
pytest tests/property/test_command_routing_properties.py -v

# Test manifest properties
pytest tests/property/test_manifest_properties.py -v

# Test error handling properties
pytest tests/property/test_error_handling_properties.py -v

# Test with more examples
pytest tests/property/ --hypothesis-show-statistics
```

### Continuous Integration

**GitHub Actions Workflow:**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

### Test Data Management

**Creating Test Data:**

```bash
# Create test database
python -c "
from src.core.database import DatabaseManager
db = DatabaseManager('data/test.db')
db.initialize()
"

# Populate test data
sqlite3 data/test.db << EOF
INSERT INTO messages (sender_id, content) VALUES ('!test1', 'test message 1');
INSERT INTO messages (sender_id, content) VALUES ('!test2', 'test message 2');
INSERT INTO bulletins (author, subject, content) VALUES ('TestUser', 'Test', 'Content');
EOF

# Clean test data
rm data/test.db
```

### Mock Testing

**Mocking Meshtastic Interface:**

```python
# tests/mocks/meshtastic_mocks.py
from unittest.mock import Mock, MagicMock

class MockMeshtasticInterface:
    def __init__(self):
        self.connected = True
        self.messages = []
    
    def send_text(self, text, destination=None):
        self.messages.append(text)
        return True
    
    def on_receive(self, callback):
        self.callback = callback
    
    def simulate_message(self, text, sender="!test"):
        msg = Mock()
        msg.text = text
        msg.from_id = sender
        self.callback(msg)
```

**Using Mocks in Tests:**

```python
# tests/unit/test_with_mock.py
from tests.mocks.meshtastic_mocks import MockMeshtasticInterface

def test_message_handling():
    interface = MockMeshtasticInterface()
    router = MessageRouter(interface)
    
    # Simulate incoming message
    interface.simulate_message("ping")
    
    # Verify response
    assert "Pong" in interface.messages[0]
```

---

## Troubleshooting

### Common Issues

#### Issue 1: No Response to Commands

**Symptoms:**
- Commands sent but no response
- Logs show message received but not processed

**Diagnosis:**

```bash
# Check if message router is running
grep "Message router" logs/zephyrgate_dev.log

# Check if services are registered
grep "Registered service" logs/zephyrgate_dev.log

# Check for command routing
grep "Routing.*command" logs/zephyrgate_dev.log

# Check for errors
grep ERROR logs/zephyrgate_dev.log | tail -20
```

**Solutions:**

1. **Restart ZephyrGate**
   ```bash
   ./stop.sh
   ./start.sh
   ```

2. **Check plugin status**
   ```bash
   grep "plugin.*started" logs/zephyrgate_dev.log
   ```

3. **Verify configuration**
   ```bash
   cat config/config.yaml | grep -A 5 enabled_plugins
   ```

#### Issue 2: Meshtastic Not Connecting

**Symptoms:**
- "Failed to connect to Meshtastic device"
- No messages received

**Diagnosis:**

```bash
# Check device connection
ls -la /dev/cu.usbmodem* # macOS
ls -la /dev/ttyUSB* # Linux

# Test with Meshtastic CLI
meshtastic --port /dev/cu.usbmodem9070698283041 --info

# Check permissions
ls -l /dev/cu.usbmodem9070698283041

# Check if another process is using device
lsof | grep usbmodem
```

**Solutions:**

1. **Fix permissions**
   ```bash
   sudo chmod 666 /dev/cu.usbmodem9070698283041
   ```

2. **Kill conflicting process**
   ```bash
   # Find process
   lsof | grep usbmodem
   # Kill it
   kill -9 <PID>
   ```

3. **Update port in config**
   ```yaml
   meshtastic:
     interface_primary:
       port: "/dev/cu.usbmodem9070698283041"
   ```

#### Issue 3: Plugin Not Loading

**Symptoms:**
- Plugin listed but not starting
- "Failed to load plugin" errors

**Diagnosis:**

```bash
# Check plugin discovery
grep "Discovered.*plugin" logs/zephyrgate_dev.log

# Check loading errors
grep "Failed to load.*plugin" logs/zephyrgate_dev.log

# Check plugin manifest
cat plugins/plugin_name/manifest.yaml

# Check plugin code
python -c "import plugins.plugin_name"
```

**Solutions:**

1. **Check manifest syntax**
   ```bash
   python -c "import yaml; yaml.safe_load(open('plugins/plugin_name/manifest.yaml'))"
   ```

2. **Check dependencies**
   ```bash
   pip install -r plugins/plugin_name/requirements.txt
   ```

3. **Check Python syntax**
   ```bash
   python -m py_compile plugins/plugin_name/plugin.py
   ```

#### Issue 4: Database Errors

**Symptoms:**
- "Database locked" errors
- "Table doesn't exist" errors

**Diagnosis:**

```bash
# Check database file
ls -la data/zephyrgate_dev.db

# Check database integrity
sqlite3 data/zephyrgate_dev.db "PRAGMA integrity_check;"

# Check tables
sqlite3 data/zephyrgate_dev.db ".tables"

# Check for locks
lsof | grep zephyrgate_dev.db
```

**Solutions:**

1. **Reinitialize database**
   ```bash
   mv data/zephyrgate_dev.db data/zephyrgate_dev.db.bak
   python -c "from src.core.database import DatabaseManager; db = DatabaseManager(); db.initialize()"
   ```

2. **Fix permissions**
   ```bash
   chmod 666 data/zephyrgate_dev.db
   ```

3. **Close other connections**
   ```bash
   # Kill processes using database
   lsof | grep zephyrgate_dev.db
   ```

#### Issue 5: High Memory Usage

**Symptoms:**
- Memory usage > 90%
- System slowdown
- Out of memory errors

**Diagnosis:**

```bash
# Check memory usage
ps aux | grep "python -m src.main"

# Monitor over time
watch -n 5 'ps aux | grep "python -m src.main" | grep -v grep'

# Check for memory leaks
python -m memory_profiler src/main.py
```

**Solutions:**

1. **Restart ZephyrGate**
   ```bash
   ./stop.sh
   ./start.sh
   ```

2. **Reduce plugin count**
   ```yaml
   # Disable unused plugins in config.yaml
   enabled_plugins:
     - "bot_service"
     - "emergency_service"
   ```

3. **Clear old data**
   ```bash
   # Clean old messages
   sqlite3 data/zephyrgate_dev.db "DELETE FROM messages WHERE timestamp < datetime('now', '-7 days');"
   ```

#### Issue 6: Web Interface Not Accessible

**Symptoms:**
- Cannot access http://localhost:8080
- Connection refused

**Diagnosis:**

```bash
# Check if web service is running
grep "web_service" logs/zephyrgate_dev.log

# Check port binding
netstat -an | grep 8080
lsof -i :8080

# Check firewall
# macOS: System Preferences → Security & Privacy → Firewall
# Linux: sudo ufw status
```

**Solutions:**

1. **Check web service enabled**
   ```yaml
   # In config.yaml
   enabled_plugins:
     - "web_service"
   ```

2. **Change port if conflict**
   ```yaml
   web:
     port: 8081
   ```

3. **Check firewall rules**
   ```bash
   # Allow port 8080
   sudo ufw allow 8080
   ```

### Debug Mode

**Enable Debug Logging:**

```yaml
# config.yaml
logging:
  level: DEBUG
  file: "logs/zephyrgate_dev.log"
```

**Or via command line:**

```bash
python -m src.main --log-level DEBUG
```

**Debug Output:**

```bash
# Watch debug logs
tail -f logs/zephyrgate_dev.log | grep DEBUG

# Filter by component
tail -f logs/zephyrgate_dev.log | grep "plugin_manager"
tail -f logs/zephyrgate_dev.log | grep "message_router"
tail -f logs/zephyrgate_dev.log | grep "meshtastic"
```

### Getting Help

**Resources:**
- Documentation: `docs/` directory
- User Manual: `docs/USER_MANUAL.md`
- Admin Guide: `docs/ADMIN_GUIDE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- GitHub Issues: Report bugs and request features

**Log Collection:**

```bash
# Collect logs for support
tar -czf zephyrgate-logs.tar.gz logs/ config/config.yaml

# Sanitize sensitive data before sharing
sed -i 's/password: .*/password: REDACTED/' config/config.yaml
```

---

## Test Checklist

### Pre-Deployment Testing

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All property tests pass
- [ ] Manual testing completed for all plugins
- [ ] Performance testing shows acceptable metrics
- [ ] Memory leak testing shows no leaks
- [ ] Meshtastic connection stable
- [ ] Web interface accessible and functional
- [ ] Database operations working correctly
- [ ] Error handling tested
- [ ] Recovery from failures tested
- [ ] Documentation reviewed and updated

### Plugin-Specific Testing

**Bot Service:**
- [ ] help command works
- [ ] ping command works
- [ ] info command works
- [ ] history command works
- [ ] games command works
- [ ] play command works
- [ ] All games functional

**Emergency Service:**
- [ ] sos command creates incident
- [ ] respond command registers responder
- [ ] status command shows incidents
- [ ] incidents command lists all
- [ ] checkin command records check-in
- [ ] cancel command cancels SOS
- [ ] All emergency types work (sosp, sosf, sosm)

**BBS Service:**
- [ ] bbs menu displays
- [ ] read command lists bulletins
- [ ] post command creates bulletin
- [ ] mail command shows inbox
- [ ] mail send works
- [ ] directory command shows channels
- [ ] Menu navigation works

**Weather Service:**
- [ ] wx command shows current weather
- [ ] weather command shows detailed info
- [ ] forecast command shows forecast
- [ ] alerts command shows alerts
- [ ] Location formats work (city, ZIP, coords)
- [ ] API integration working

**Email Service:**
- [ ] send command sends email
- [ ] check command retrieves emails
- [ ] SMTP connection working
- [ ] IMAP connection working
- [ ] Email formatting correct

**Asset Service:**
- [ ] track command registers assets
- [ ] locate command finds assets
- [ ] status command shows details
- [ ] checkin command works
- [ ] checkout command works
- [ ] Location updates working

**Web Service:**
- [ ] Web interface loads
- [ ] Plugin management works
- [ ] System status displays
- [ ] Logs viewable
- [ ] Configuration viewable
- [ ] WebSocket updates working

**Ping Responder:**
- [ ] Auto-responds to pings
- [ ] Case insensitive matching
- [ ] Configurable responses

### System Testing

- [ ] System starts successfully
- [ ] All plugins load
- [ ] Configuration valid
- [ ] Database initialized
- [ ] Message routing works
- [ ] Health monitoring active
- [ ] Scheduled tasks running
- [ ] Error handling working
- [ ] Logging functional
- [ ] Performance acceptable

### Integration Testing

- [ ] End-to-end message flow works
- [ ] Multi-plugin interactions work
- [ ] Database integrity maintained
- [ ] External APIs accessible
- [ ] Meshtastic communication stable
- [ ] Web interface integrated
- [ ] Scheduled tasks execute
- [ ] Error recovery works

---

## Test Results Template

```markdown
# Test Results - [Date]

## Environment
- ZephyrGate Version: 
- Python Version: 
- OS: 
- Meshtastic Device: 
- Firmware Version: 

## Test Summary
- Total Tests: 
- Passed: 
- Failed: 
- Skipped: 
- Duration: 

## Plugin Tests
### Bot Service: ✅ PASS / ❌ FAIL
- help: ✅
- ping: ✅
- info: ✅
- history: ✅
- games: ✅
- play: ✅

### Emergency Service: ✅ PASS / ❌ FAIL
- sos: ✅
- respond: ✅
- status: ✅
- incidents: ✅
- checkin: ✅
- cancel: ✅

[Continue for all plugins...]

## Issues Found
1. [Issue description]
   - Severity: High/Medium/Low
   - Status: Open/Fixed
   - Notes: 

## Performance Metrics
- Average response time: 
- Memory usage: 
- CPU usage: 
- Message throughput: 

## Recommendations
1. [Recommendation]
2. [Recommendation]

## Sign-off
Tested by: 
Date: 
Approved: Yes/No
```

---

**End of Testing Guide**

For questions or issues, refer to:
- User Manual: `docs/USER_MANUAL.md`
- Admin Guide: `docs/ADMIN_GUIDE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Plugin Development: `docs/PLUGIN_DEVELOPMENT.md`
