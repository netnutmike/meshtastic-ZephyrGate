# YAML Configuration Guide

## Complete Guide to Configuring Auto-Responses and Scheduled Broadcasts

**Everything is configured in YAML - no Python code changes needed!**

---

## Table of Contents

1. [Custom Auto-Response Rules](#custom-auto-response-rules)
2. [Scheduled Broadcasts](#scheduled-broadcasts)
3. [One-Time Greeting](#one-time-greeting)
4. [Complete Examples](#complete-examples)
5. [Testing Your Configuration](#testing-your-configuration)

---

## Custom Auto-Response Rules

### Basic Setup

Add custom auto-response rules to `config/config.yaml`:

```yaml
services:
  bot:
    auto_response:
      enabled: true
      
      # Your custom rules
      custom_rules:
        - keywords: ['test', 'testing']
          response: "✅ Test received! Signal is good."
          priority: 15
          cooldown_seconds: 30
          max_responses_per_hour: 10
          enabled: true
```

### Rule Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `keywords` | list | Yes | - | Words/phrases that trigger response |
| `response` | string | Yes | - | Message to send when triggered |
| `priority` | integer | No | 50 | Processing order (lower = higher priority) |
| `cooldown_seconds` | integer | No | 30 | Seconds between responses to same user |
| `max_responses_per_hour` | integer | No | 10 | Max responses per hour per user |
| `enabled` | boolean | No | true | Enable/disable this rule |
| `emergency` | boolean | No | false | Mark as emergency (with escalation) |
| `match_type` | string | No | "contains" | How to match keywords |
| `case_sensitive` | boolean | No | false | Case-sensitive matching |
| `channels` | list | No | [] | Whitelist channels (empty = all) |
| `exclude_channels` | list | No | [] | Blacklist channels |
| `direct_message_only` | boolean | No | false | Only respond to DMs |

### Example: Test Message Response

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        - keywords: ['test', 'testing', 'test123']
          response: |
            ✅ TEST RECEIVED
            Your message was received successfully.
            Signal quality: Good
          priority: 15
          cooldown_seconds: 30
          max_responses_per_hour: 20
          enabled: true
```

### Example: Network Information

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        - keywords: ['info', 'network info', 'about']
          response: |
            📡 ZephyrGate Mesh Network
            Coverage: Local Area
            Send 'help' for commands
          priority: 40
          cooldown_seconds: 120
          max_responses_per_hour: 5
          enabled: true
```

### Example: Multiple Custom Rules

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        # Test response
        - keywords: ['test']
          response: "✅ Test OK"
          priority: 15
          cooldown_seconds: 20
          enabled: true
        
        # Echo response
        - keywords: ['echo', 'repeat']
          response: "📡 Echo test successful"
          priority: 15
          cooldown_seconds: 30
          enabled: true
        
        # Signal report
        - keywords: ['signal', 'how copy']
          response: "📶 Signal: Loud and clear"
          priority: 20
          cooldown_seconds: 60
          enabled: true
        
        # Network info
        - keywords: ['info', 'about']
          response: "📡 ZephyrGate Mesh Network"
          priority: 40
          cooldown_seconds: 120
          enabled: true
```

---

## Scheduled Broadcasts

### Basic Setup

Add scheduled broadcasts to `config/config.yaml`:

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Morning Announcement"
      message: "☀️ Good morning! Network is active."
      schedule_type: "cron"
      cron_expression: "0 8 * * *"  # 8:00 AM daily
      channel: 0
      priority: "normal"
      enabled: true
```

### Broadcast Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Descriptive name for the broadcast |
| `message` | string | Yes | Content to send (can be multi-line) |
| `schedule_type` | string | Yes | "cron", "interval", or "one_time" |
| `cron_expression` | string | For cron | Cron format schedule |
| `interval_seconds` | integer | For interval | Seconds between broadcasts |
| `scheduled_time` | string | For one_time | ISO timestamp (YYYY-MM-DDTHH:MM:SS) |
| `channel` | integer | No (default 0) | Channel to broadcast on |
| `priority` | string | No (default "normal") | "low", "normal", "high", "emergency" |
| `enabled` | boolean | No (default true) | Enable/disable broadcast |

### Schedule Types

#### 1. Cron Schedule

Send at specific times using cron expressions:

```yaml
broadcasts:
  # Every day at 8:00 AM
  - name: "Morning Announcement"
    message: "☀️ Good morning!"
    schedule_type: "cron"
    cron_expression: "0 8 * * *"
    channel: 0
    priority: "normal"
    enabled: true
  
  # Every day at 8:00 PM
  - name: "Evening Announcement"
    message: "🌙 Good evening!"
    schedule_type: "cron"
    cron_expression: "0 20 * * *"
    channel: 0
    priority: "normal"
    enabled: true
  
  # Every Monday at 9:00 AM
  - name: "Weekly Net Reminder"
    message: "📻 Weekly net today at 7 PM"
    schedule_type: "cron"
    cron_expression: "0 9 * * 1"
    channel: 0
    priority: "normal"
    enabled: true
```

**Cron Expression Format:**
```
minute hour day month day_of_week

Examples:
"0 8 * * *"      - Every day at 8:00 AM
"0 */6 * * *"    - Every 6 hours
"30 12 * * *"    - Every day at 12:30 PM
"0 9 * * 1"      - Every Monday at 9:00 AM
"0 18 * * 5"     - Every Friday at 6:00 PM
"*/15 * * * *"   - Every 15 minutes
```

#### 2. Interval Schedule

Send at regular intervals:

```yaml
broadcasts:
  # Every hour
  - name: "Hourly Status"
    message: "📊 Network status: Operational"
    schedule_type: "interval"
    interval_seconds: 3600  # 1 hour
    channel: 0
    priority: "normal"
    enabled: true
  
  # Every 6 hours
  - name: "Weather Reminder"
    message: "🌤️ Weather update available"
    schedule_type: "interval"
    interval_seconds: 21600  # 6 hours
    channel: 0
    priority: "normal"
    enabled: true
  
  # Every 30 minutes
  - name: "Quick Beacon"
    message: "✅ Network active"
    schedule_type: "interval"
    interval_seconds: 1800  # 30 minutes
    channel: 0
    priority: "low"
    enabled: true
```

**Common Intervals:**
- 1 hour: `3600`
- 6 hours: `21600`
- 12 hours: `43200`
- 24 hours: `86400`
- 30 minutes: `1800`
- 15 minutes: `900`

#### 3. One-Time Schedule

Send once at a specific time:

```yaml
broadcasts:
  # Special event
  - name: "Special Event"
    message: "🎉 Special event starting now!"
    schedule_type: "one_time"
    scheduled_time: "2024-12-25T12:00:00"
    channel: 0
    priority: "high"
    enabled: true
  
  # Maintenance notice
  - name: "Maintenance Window"
    message: "🔧 Maintenance begins in 1 hour"
    schedule_type: "one_time"
    scheduled_time: "2024-12-20T02:00:00"
    channel: 0
    priority: "high"
    enabled: true
```

**Time Format:** ISO 8601 format `YYYY-MM-DDTHH:MM:SS`

---

## One-Time Greeting

### Only Greet New Nodes Once

Set `greeting_delay_hours` to `-1` to only greet nodes that have never been seen before:

```yaml
services:
  bot:
    auto_response:
      greeting_enabled: true
      greeting_delay_hours: -1  # Only greet new nodes once ever
      greeting_message: |
        🎉 Welcome to the ZephyrGate Mesh Network!
        
        You're now connected to our community.
        
        Quick Start:
        • Send 'help' for all commands
        • Send 'weather' for conditions
        • Send 'bbs' for bulletins
        
        Emergency? Send 'emergency' or 'sos'
        
        This is a one-time welcome message.
```

### Greeting Modes

| Value | Behavior |
|-------|----------|
| `-1` | Only greet truly new nodes (never seen before) |
| `0` | Greet every time (not recommended) |
| `24` | Greet once per day |
| `168` | Greet once per week |

---

## Complete Examples

### Example 1: Test Response Only

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    
    auto_response:
      enabled: true
      
      custom_rules:
        - keywords: ['test', 'testing']
          response: "✅ Test received! Signal is good."
          priority: 15
          cooldown_seconds: 30
          max_responses_per_hour: 20
          enabled: true
```

### Example 2: Multiple Custom Responses

```yaml
services:
  bot:
    auto_response:
      enabled: true
      greeting_delay_hours: -1  # One-time greeting
      
      custom_rules:
        # Test
        - keywords: ['test']
          response: "✅ Test OK"
          priority: 15
          cooldown_seconds: 20
          enabled: true
        
        # Info
        - keywords: ['info', 'about']
          response: "📡 ZephyrGate Mesh Network"
          priority: 40
          cooldown_seconds: 120
          enabled: true
        
        # Contact
        - keywords: ['contact', 'admin']
          response: "📞 Admin: [Your Callsign]"
          priority: 50
          cooldown_seconds: 300
          enabled: true
```

### Example 3: Daily Broadcasts

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    # Morning
    - name: "Morning Announcement"
      message: "☀️ Good morning! Network is active."
      schedule_type: "cron"
      cron_expression: "0 8 * * *"
      channel: 0
      priority: "normal"
      enabled: true
    
    # Evening
    - name: "Evening Announcement"
      message: "🌙 Good evening! Network operational."
      schedule_type: "cron"
      cron_expression: "0 20 * * *"
      channel: 0
      priority: "normal"
      enabled: true
```

### Example 4: Hourly Beacon

```yaml
scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Hourly Beacon"
      message: "📡 Network beacon - All systems operational"
      schedule_type: "interval"
      interval_seconds: 3600  # Every hour
      channel: 0
      priority: "low"
      enabled: true
```

### Example 5: Complete Setup

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    
    auto_response:
      enabled: true
      greeting_enabled: true
      greeting_delay_hours: -1  # One-time only
      greeting_message: "Welcome! Send 'help' for commands."
      
      custom_rules:
        - keywords: ['test']
          response: "✅ Test OK"
          priority: 15
          cooldown_seconds: 30
          enabled: true
        
        - keywords: ['info']
          response: "📡 ZephyrGate Mesh"
          priority: 40
          cooldown_seconds: 120
          enabled: true

scheduled_broadcasts:
  enabled: true
  
  broadcasts:
    - name: "Morning Net"
      message: "☀️ Good morning! Network active."
      schedule_type: "cron"
      cron_expression: "0 8 * * *"
      channel: 0
      priority: "normal"
      enabled: true
    
    - name: "Hourly Beacon"
      message: "📡 Network operational"
      schedule_type: "interval"
      interval_seconds: 3600
      channel: 0
      priority: "low"
      enabled: true
```

---

## Testing Your Configuration

### 1. Validate YAML Syntax

```bash
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### 2. Restart Service

```bash
./stop.sh && ./start.sh
```

### 3. Check Logs

```bash
tail -f logs/zephyrgate.log | grep -E "(custom|broadcast|greeting)"
```

### 4. Test Custom Rules

Send test messages:
- `test` - Should trigger test response
- `info` - Should trigger info response
- Any custom keywords you configured

### 5. Verify Scheduled Broadcasts

Check logs for:
- `"Loaded scheduled broadcast from config"`
- `"Broadcasting message:"`
- `"Broadcast sent successfully"`

### 6. Test Greeting

Connect a new node or clear greeting history to test one-time greeting.

---

## Troubleshooting

### Custom Rules Not Working

**Check:**
1. `bot.enabled: true`
2. `auto_response: true`
3. `custom_rules` is properly indented
4. Keywords are in list format: `['keyword1', 'keyword2']`
5. Response is a string
6. Rule is `enabled: true`

**Debug:**
```yaml
logging:
  services:
    bot: "DEBUG"
```

### Scheduled Broadcasts Not Sending

**Check:**
1. `scheduled_broadcasts.enabled: true`
2. Broadcast is `enabled: true`
3. Schedule type matches parameters (cron needs cron_expression, etc.)
4. Cron expression is valid
5. Time format is correct for one_time broadcasts

**Debug:**
```bash
tail -f logs/zephyrgate.log | grep -i broadcast
```

### One-Time Greeting Not Working

**Check:**
1. `greeting_enabled: true`
2. `greeting_delay_hours: -1`
3. Node is truly new (not in database)

**Reset greeting history:**
```bash
# Development only - clears all data!
rm data/zephyrgate_dev.db
```

---

## Best Practices

### Custom Rules

1. **Start Simple** - Add one rule, test, then add more
2. **Use Appropriate Priorities** - Lower numbers = higher priority
3. **Set Reasonable Cooldowns** - Prevent spam
4. **Test Keywords** - Make sure they don't conflict
5. **Keep Responses Concise** - < 200 characters ideal

### Scheduled Broadcasts

1. **Start with Long Intervals** - Test with hours, not minutes
2. **Use Low Priority for Frequent Broadcasts** - Reduce network impact
3. **Test Cron Expressions** - Verify timing is correct
4. **Monitor Network Traffic** - Adjust frequency as needed
5. **Disable When Not Needed** - Set `enabled: false`

### General

1. **Backup Configuration** - Before making changes
2. **Test in Development** - Use test config first
3. **Monitor Logs** - Watch for errors
4. **Document Changes** - Note what you configured
5. **Restart After Changes** - Configuration loads on startup

---

## Related Documentation

- [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md) - Complete auto-responder guide
- [AUTO_RESPONDER_QUICK_REFERENCE.md](AUTO_RESPONDER_QUICK_REFERENCE.md) - Quick reference
- [auto_response_examples.yaml](../config/auto_response_examples.yaml) - 24 complete examples

---

## Support

For issues:
1. Check this guide
2. Review example configurations
3. Enable debug logging
4. Check logs for errors
5. Verify YAML syntax
