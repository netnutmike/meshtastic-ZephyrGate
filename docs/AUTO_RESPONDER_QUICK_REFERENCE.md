# Auto-Responder Quick Reference

**All configuration is done in YAML - no Python code changes needed!**

---

## Quick Setup

### 1. Enable Auto-Response

```yaml
# config/config.yaml
services:
  bot:
    enabled: true
    auto_response: true
```

### 2. Configure Settings

```yaml
services:
  bot:
    auto_response:
      enabled: true
      response_rate_limit: 10
      cooldown_seconds: 30
```

### 3. Restart Service

```bash
./stop.sh && ./start.sh
```

---

## Configuration File Location

- **Main Config**: `config/config.yaml`
- **Examples**: `config/auto_response_examples.yaml`

---

## Common Configurations

### Conservative (Low Traffic)
```yaml
services:
  bot:
    auto_response:
      cooldown_seconds: 60
      response_rate_limit: 5
```

### Moderate (Normal Traffic)
```yaml
services:
  bot:
    auto_response:
      cooldown_seconds: 30
      response_rate_limit: 10
```

### Permissive (High Traffic)
```yaml
services:
  bot:
    auto_response:
      cooldown_seconds: 10
      response_rate_limit: 20
```

---

## Emergency Configuration

### Standard Emergency
```yaml
services:
  bot:
    auto_response:
      emergency_keywords: ['help', 'emergency', 'sos', 'mayday']
      emergency_escalation_delay: 300  # 5 minutes
```

### Fast Escalation
```yaml
services:
  bot:
    auto_response:
      emergency_escalation_delay: 120  # 2 minutes
```

### Custom Emergency Message
```yaml
services:
  bot:
    auto_response:
      emergency_escalation_message: |
        🚨 EMERGENCY ALERT 🚨
        Unacknowledged emergency from {sender}
        Message: {message}
```

---

## Greeting Configuration

### Standard Greeting
```yaml
services:
  bot:
    auto_response:
      greeting_enabled: true
      greeting_message: 'Welcome! Send "help" for commands.'
      greeting_delay_hours: 24
```

### Custom Greeting
```yaml
services:
  bot:
    auto_response:
      greeting_message: |
        🎉 Welcome to the Mesh Network!
        
        Quick Start:
        • 'help' - Commands
        • 'weather' - Weather
        • 'bbs' - Bulletins
```

### Disable Greeting
```yaml
services:
  bot:
    auto_response:
      greeting_enabled: false
```

---

## Rate Limiting Quick Reference

| Setting | Purpose | Typical Values |
|---------|---------|----------------|
| `cooldown_seconds` | Time between responses | 10-120 seconds |
| `response_rate_limit` | Max per hour | 3-20 responses |

**Formula**: User can get max `response_rate_limit` responses per hour, but must wait `cooldown_seconds` between each.

---

## Default Auto-Response Rules

The system includes these built-in rules:

| Priority | Keywords | Response |
|----------|----------|----------|
| 1 | emergency, sos, help | Emergency alert with escalation |
| 10 | ping, test, cq | Pong response |
| 30 | status, sitrep | Network status |
| 40 | weather, wx | Weather info |
| 50 | help, ?, commands | Command list |
| 60 | games, play | Games list |
| 70 | hello, hi | Greeting |

Lower priority number = processed first

---

## Debugging

### Enable Debug Logging
```yaml
logging:
  services:
    bot: "DEBUG"
```

### View Logs
```bash
tail -f logs/zephyrgate.log | grep bot
```

### Check Configuration
```bash
python -c "import yaml; print(yaml.safe_load(open('config/config.yaml'))['services']['bot'])"
```

---

## Troubleshooting

### Bot Not Responding
✓ Check `bot.enabled: true`  
✓ Check `auto_response: true`  
✓ Check logs for errors  
✓ Restart service  

### Too Many Responses
↑ Increase `cooldown_seconds`  
↓ Decrease `response_rate_limit`  

### Emergency Not Escalating
✓ Check `emergency_keywords` not empty  
✓ Check `emergency_escalation_delay > 0`  
✓ Check emergency service plugin enabled  

### Greeting Not Working
✓ Check `greeting_enabled: true`  
✓ Check `greeting_delay_hours` setting  
✓ Node may have been greeted recently  

---

## Configuration by Network Size

### Small Network (< 10 nodes)
```yaml
cooldown_seconds: 30
response_rate_limit: 10
greeting_delay_hours: 24
```

### Medium Network (10-50 nodes)
```yaml
cooldown_seconds: 60
response_rate_limit: 5
greeting_delay_hours: 48
```

### Large Network (> 50 nodes)
```yaml
cooldown_seconds: 120
response_rate_limit: 3
greeting_delay_hours: 168
```

---

## Complete Configuration Example

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    keyword_monitoring: true
    new_node_greeting: true
    
    auto_response:
      enabled: true
      
      # Rate limiting
      response_rate_limit: 10
      cooldown_seconds: 30
      
      # Emergency
      emergency_keywords: ['help', 'emergency', 'sos', 'mayday']
      emergency_escalation_delay: 300
      emergency_escalation_message: 'EMERGENCY: {sender} - {message}'
      
      # Greeting
      greeting_enabled: true
      greeting_message: 'Welcome! Send "help" for commands.'
      greeting_delay_hours: 24
      
      # AI
      aircraft_responses: true
```

---

## Testing Your Configuration

### 1. Test Basic Response
Send: `ping`  
Expected: `🏓 Pong! Bot is active...`

### 2. Test Rate Limiting
Send `ping` multiple times quickly  
Expected: Only responds once per cooldown period

### 3. Test Emergency
Send: `emergency`  
Expected: Immediate response + escalation after delay

### 4. Test Greeting
Connect new node  
Expected: Welcome message sent once

---

## Full Documentation

See [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md) for:
- Complete configuration options
- Detailed explanations
- Advanced topics
- Integration guides
- Troubleshooting

---

## Configuration Examples

See `config/auto_response_examples.yaml` for:
- Rate limiting strategies
- Emergency configurations
- Greeting templates
- Network size examples

---

## Support

1. Check [AUTO_RESPONDER_GUIDE.md](AUTO_RESPONDER_GUIDE.md)
2. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Enable debug logging
4. Check `logs/zephyrgate.log`
5. Review `config/auto_response_examples.yaml`
