# Auto-Responder System Guide

## Overview

The ZephyrGate auto-responder system provides intelligent, automated responses to messages based on configurable rules defined in YAML configuration files. All configuration is done through YAML - no Python code changes required.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Location](#configuration-location)
3. [Basic Configuration](#basic-configuration)
4. [Auto-Response Settings](#auto-response-settings)
5. [Understanding Default Rules](#understanding-default-rules)
6. [Customizing Responses](#customizing-responses)
7. [Rate Limiting](#rate-limiting)
8. [Emergency Escalation](#emergency-escalation)
9. [New Node Greeting](#new-node-greeting)
10. [Monitoring and Statistics](#monitoring-and-statistics)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Enable Auto-Response

Edit `config/config.yaml`:

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    keyword_monitoring: true
```

### 2. Configure Basic Settings

```yaml
services:
  bot:
    auto_response:
      enabled: true
      response_rate_limit: 10  # Max responses per hour per user
      cooldown_seconds: 30     # Seconds between responses
```

### 3. Restart the Service

The system will automatically load the configuration and start responding to messages.

---

## Configuration Location

All auto-responder configuration is in:
- **Main Config**: `config/config.yaml`
- **Examples**: `config/auto_response_examples.yaml`

No Python code changes are needed!

---

## Basic Configuration

### Minimal Configuration

```yaml
services:
  bot:
    enabled: true
    auto_response: true
```

This enables the bot with default auto-response rules.

### Full Configuration

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    keyword_monitoring: true
    new_node_greeting: true
    
    auto_response:
      enabled: true
      emergency_keywords: ['help', 'emergency', 'urgent', 'mayday', 'sos', 'distress']
      greeting_enabled: true
      greeting_message: 'Welcome to the mesh network! Send "help" for available commands.'
      greeting_delay_hours: 24
      aircraft_responses: true
      emergency_escalation_delay: 300
      emergency_escalation_message: 'EMERGENCY ALERT: Unacknowledged emergency from {sender}: {message}'
      response_rate_limit: 10
      cooldown_seconds: 30
```

---

## Auto-Response Settings

### Core Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable auto-response system |
| `response_rate_limit` | integer | 10 | Max responses per hour per user |
| `cooldown_seconds` | integer | 30 | Seconds between responses to same user |

### Emergency Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `emergency_keywords` | list | ['help', 'emergency', ...] | Keywords that trigger emergency response |
| `emergency_escalation_delay` | integer | 300 | Seconds before escalating (5 minutes) |
| `emergency_escalation_message` | string | Template | Message sent when escalating |

### Greeting Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `greeting_enabled` | boolean | true | Greet new nodes automatically |
| `greeting_message` | string | Welcome message | Message sent to new nodes |
| `greeting_delay_hours` | integer | 24 | Hours before greeting same node again |

### AI Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `aircraft_responses` | boolean | true | Respond to aircraft messages with AI |

---

## Understanding Default Rules

The system includes these built-in auto-response rules (configured in Python, but you can override behavior via YAML settings):

### 1. Emergency Keywords (Priority 1)
- **Keywords**: help, emergency, urgent, mayday, sos, distress
- **Response**: "🚨 Emergency keywords detected. Alerting responders..."
- **Special**: Includes escalation after 5 minutes if no acknowledgment

### 2. Ping/Connectivity (Priority 10)
- **Keywords**: ping, test, cq
- **Response**: "🏓 Pong! Bot is active and responding."
- **Purpose**: Quick connectivity test

### 3. Network Status (Priority 30)
- **Keywords**: status, sitrep, network
- **Response**: "📊 Network Status: Active nodes detected..."
- **Purpose**: System status information

### 4. Weather (Priority 40)
- **Keywords**: weather, wx, forecast
- **Response**: "🌤️ Weather service available..."
- **Purpose**: Weather service information

### 5. Help (Priority 50)
- **Keywords**: help, ?, commands
- **Response**: "📋 Available commands: help, ping, status..."
- **Purpose**: Command listing

### 6. Games (Priority 60)
- **Keywords**: games, play, fun
- **Response**: "🎮 Games available: blackjack, hangman..."
- **Purpose**: Available games

### 7. Greetings (Priority 70)
- **Keywords**: hello, hi, hey, good morning, good evening
- **Response**: "👋 Hello! Welcome to the mesh network..."
- **Purpose**: Friendly greeting

---

## Customizing Responses

### Adjusting Rate Limits

Control how often the bot responds:

```yaml
services:
  bot:
    auto_response:
      # Global defaults for all rules
      response_rate_limit: 5   # Reduce to 5 responses per hour
      cooldown_seconds: 60     # Increase to 1 minute between responses
```

### Customizing Emergency Keywords

Add or remove emergency keywords:

```yaml
services:
  bot:
    auto_response:
      emergency_keywords:
        - 'help'
        - 'emergency'
        - 'urgent'
        - 'mayday'
        - 'sos'
        - 'distress'
        - 'fire'      # Add custom keyword
        - 'medical'   # Add custom keyword
```

### Customizing Greeting Message

Change the welcome message for new nodes:

```yaml
services:
  bot:
    auto_response:
      greeting_enabled: true
      greeting_message: |
        🎉 Welcome to our mesh network!
        
        Available services:
        • Send 'help' for commands
        • Send 'weather' for conditions
        • Send 'bbs' for bulletins
        
        Need assistance? Send 'emergency' for help.
      greeting_delay_hours: 48  # Greet less frequently
```

### Customizing Escalation

Adjust emergency escalation behavior:

```yaml
services:
  bot:
    auto_response:
      emergency_escalation_delay: 180  # 3 minutes instead of 5
      emergency_escalation_message: |
        🚨🚨 URGENT EMERGENCY ALERT 🚨🚨
        
        Unacknowledged emergency from {sender}
        Original message: {message}
        
        All available responders please acknowledge!
```

---

## Rate Limiting

### How Rate Limiting Works

The system tracks responses per user and applies two types of limits:

1. **Cooldown**: Minimum time between responses to the same user
2. **Hourly Limit**: Maximum total responses per hour per user

### Configuring Rate Limits

```yaml
services:
  bot:
    auto_response:
      # These are defaults applied to all auto-response rules
      cooldown_seconds: 30           # 30 seconds between responses
      response_rate_limit: 10        # Max 10 responses per hour
```

### Rate Limiting Strategies

**Conservative (Low Traffic)**
```yaml
cooldown_seconds: 60              # 1 minute
response_rate_limit: 5            # 5 per hour
```

**Moderate (Normal Traffic)**
```yaml
cooldown_seconds: 30              # 30 seconds
response_rate_limit: 10           # 10 per hour
```

**Permissive (High Traffic)**
```yaml
cooldown_seconds: 10              # 10 seconds
response_rate_limit: 20           # 20 per hour
```

**Emergency Only (Minimal Auto-Response)**
```yaml
cooldown_seconds: 300             # 5 minutes
response_rate_limit: 2            # 2 per hour
```

---

## Emergency Escalation

### How Escalation Works

1. User sends message with emergency keyword
2. Bot immediately responds with acknowledgment
3. System monitors for user response or emergency service acknowledgment
4. If no response after `emergency_escalation_delay` seconds:
   - Broadcast emergency alert to all channels
   - Notify emergency service plugin
   - Mark incident as escalated

### Configuring Escalation

```yaml
services:
  bot:
    auto_response:
      # Emergency keywords that trigger escalation
      emergency_keywords:
        - 'help'
        - 'emergency'
        - 'sos'
        - 'mayday'
      
      # Time before escalating (in seconds)
      emergency_escalation_delay: 300  # 5 minutes
      
      # Message broadcast when escalating
      emergency_escalation_message: |
        🚨 EMERGENCY ALERT 🚨
        Unacknowledged emergency from {sender}
        Message: {message}
        Time: {timestamp}
```

### Escalation Timing

**Fast Escalation (Critical Emergencies)**
```yaml
emergency_escalation_delay: 120  # 2 minutes
```

**Standard Escalation**
```yaml
emergency_escalation_delay: 300  # 5 minutes
```

**Slow Escalation (Non-Critical)**
```yaml
emergency_escalation_delay: 600  # 10 minutes
```

### Disabling Escalation

To disable automatic escalation but keep emergency responses:

```yaml
services:
  bot:
    auto_response:
      emergency_keywords: []  # Empty list disables emergency detection
```

Or disable the emergency service plugin entirely.

---

## New Node Greeting

### How Greeting Works

When a new node (never seen before, or not seen in `greeting_delay_hours`) sends a message:
1. System detects it's a new/returning node
2. Sends welcome message automatically
3. Records the greeting time
4. Won't greet again for `greeting_delay_hours`

### Configuring Greeting

```yaml
services:
  bot:
    auto_response:
      greeting_enabled: true
      greeting_message: 'Welcome! Send "help" for commands.'
      greeting_delay_hours: 24  # Don't greet same node for 24 hours
```

### Custom Greeting Messages

**Simple Greeting**
```yaml
greeting_message: 'Welcome to the network! Type "help" for assistance.'
```

**Detailed Greeting**
```yaml
greeting_message: |
  🎉 Welcome to the Mesh Network!
  
  Quick Start:
  • 'help' - Show all commands
  • 'weather' - Get weather info
  • 'bbs' - Read bulletins
  • 'games' - Play games
  
  For emergencies, send 'emergency'
```

**Minimal Greeting**
```yaml
greeting_message: 'Connected. Send "help" for commands.'
```

### Greeting Frequency

**Greet Once Per Day**
```yaml
greeting_delay_hours: 24
```

**Greet Once Per Week**
```yaml
greeting_delay_hours: 168  # 7 days
```

**Greet Every Time (Not Recommended)**
```yaml
greeting_delay_hours: 0
```

**Disable Greeting**
```yaml
greeting_enabled: false
```

---

## Monitoring and Statistics

### Viewing Statistics

Send the `status` command to see bot statistics:

```
status
```

Response includes:
- Number of active commands
- Number of auto-response rules
- AI integration status
- Response counts

### Log Monitoring

Enable debug logging to see auto-responder activity:

```yaml
logging:
  services:
    bot: "DEBUG"
```

This will log:
- Rule matching attempts
- Rate limit checks
- Emergency escalations
- Response tracking

### Statistics in Logs

Look for these log entries:
- `"Added auto-response rule with keywords: ..."` - Rule loaded
- `"Emergency keyword detected from ..."` - Emergency triggered
- `"Sent welcome greeting to new node: ..."` - New node greeted
- `"Escalating emergency from ..."` - Emergency escalated

---

## Best Practices

### 1. Start Conservative

Begin with restrictive rate limits and adjust based on usage:

```yaml
services:
  bot:
    auto_response:
      cooldown_seconds: 60
      response_rate_limit: 5
```

### 2. Monitor Logs

Enable INFO or DEBUG logging initially to understand behavior:

```yaml
logging:
  services:
    bot: "INFO"
```

### 3. Test Emergency Escalation

Test emergency keywords in a controlled environment before deploying.

### 4. Customize Greeting

Make the greeting message relevant to your network:

```yaml
greeting_message: |
  Welcome to [Your Network Name]!
  Coverage: [Your Coverage Area]
  Send 'help' for commands.
```

### 5. Adjust for Network Size

**Small Network (< 10 nodes)**
```yaml
cooldown_seconds: 30
response_rate_limit: 10
greeting_delay_hours: 24
```

**Medium Network (10-50 nodes)**
```yaml
cooldown_seconds: 60
response_rate_limit: 5
greeting_delay_hours: 48
```

**Large Network (> 50 nodes)**
```yaml
cooldown_seconds: 120
response_rate_limit: 3
greeting_delay_hours: 168
```

### 6. Emergency Keywords

Keep emergency keywords focused and unambiguous:

```yaml
emergency_keywords:
  - 'emergency'
  - 'sos'
  - 'mayday'
  # Avoid common words that might trigger false positives
```

---

## Troubleshooting

### Bot Not Responding

**Check Configuration**
```yaml
services:
  bot:
    enabled: true          # Must be true
    auto_response: true    # Must be true
```

**Check Logs**
```bash
tail -f logs/zephyrgate.log | grep bot
```

**Enable Debug Logging**
```yaml
logging:
  services:
    bot: "DEBUG"
```

### Too Many Responses

**Increase Cooldown**
```yaml
cooldown_seconds: 120  # Increase from 30 to 120
```

**Decrease Rate Limit**
```yaml
response_rate_limit: 3  # Decrease from 10 to 3
```

### Emergency Not Escalating

**Check Emergency Service**
Ensure emergency service plugin is enabled:
```yaml
plugins:
  enabled_plugins:
    - "emergency_service"
```

**Check Escalation Delay**
```yaml
emergency_escalation_delay: 300  # Must be > 0
```

**Check Emergency Keywords**
```yaml
emergency_keywords:
  - 'emergency'  # Must not be empty
  - 'sos'
```

### Greeting Not Working

**Check Greeting Enabled**
```yaml
greeting_enabled: true  # Must be true
```

**Check Greeting Delay**
```yaml
greeting_delay_hours: 24  # Node may have been greeted recently
```

**Clear Greeting History**
Delete the database to reset greeting history (development only):
```bash
rm data/zephyrgate_dev.db
```

### Rate Limiting Too Strict

**Relax Limits**
```yaml
cooldown_seconds: 10       # Reduce cooldown
response_rate_limit: 20    # Increase limit
```

### Configuration Not Loading

**Check YAML Syntax**
```bash
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

**Restart Service**
```bash
./stop.sh
./start.sh
```

**Check for Errors**
```bash
tail -f logs/zephyrgate.log
```

---

## Configuration Examples

See `config/auto_response_examples.yaml` for complete examples including:
- Different rate limiting strategies
- Custom emergency configurations
- Greeting message templates
- Network size configurations

---

## Related Documentation

- [SCHEDULED_BROADCASTS_GUIDE.md](SCHEDULED_BROADCASTS_GUIDE.md) - Scheduled message broadcasting
- [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) - Bot commands
- [USER_MANUAL.md](USER_MANUAL.md) - General user guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - General troubleshooting

---

## Advanced Topics

### Integration with Emergency Service

The auto-responder automatically integrates with the emergency service plugin when emergency keywords are detected. No additional configuration needed.

### Integration with AI Service

When AI service is enabled, the bot can respond to aircraft messages:

```yaml
services:
  bot:
    ai:
      enabled: true
      aircraft_detection: true
      altitude_threshold: 1000  # meters
```

### Message History Integration

The bot integrates with message history service automatically for offline message delivery and message replay.

---

## Support

For issues or questions:
1. Check this guide
2. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Check logs in `logs/zephyrgate.log`
4. Enable debug logging for detailed information
5. Review `config/auto_response_examples.yaml` for configuration examples
