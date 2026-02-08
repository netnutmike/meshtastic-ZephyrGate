# ZephyrGate Administrator Guide

**Complete guide for installing, configuring, and maintaining ZephyrGate**

---

## Table of Contents

1. [Installation](#installation)
2. [Configuration Management](#configuration-management)
3. [Plugin System](#plugin-system)
4. [Auto-Response Configuration](#auto-response-configuration)
5. [Scheduled Broadcasts](#scheduled-broadcasts)
6. [MQTT Gateway](#mqtt-gateway)
7. [Service Management](#service-management)
8. [User Management](#user-management)
9. [Security](#security)
10. [Monitoring and Maintenance](#monitoring-and-maintenance)
11. [Backup and Recovery](#backup-and-recovery)
12. [Performance Tuning](#performance-tuning)
13. [Troubleshooting](#troubleshooting)
14. [Docker Deployment](#docker-deployment)

---

## Installation

### Quick Installation Methods

**Docker (Recommended - Easiest):**
```bash
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest
```

**Manual Installation:**
```bash
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate
./install.sh
./start.sh
```

For detailed installation instructions, see:
- [Docker Deployment](#docker-deployment) section below
- [QUICK_START.md](QUICK_START.md) for step-by-step guide

### System Requirements

**Minimum:**
- 1 CPU core
- 512 MB RAM
- 1 GB storage
- Python 3.8+ (manual install)
- Docker 20.10+ (Docker install)

**Recommended:**
- 2 CPU cores
- 1 GB RAM
- 5 GB storage

---

## Configuration Management

### Configuration File Structure

ZephyrGate uses YAML configuration files with hierarchical loading:

1. **Default Configuration**: `config/default.yaml` (base settings)
2. **Environment Configuration**: `config/{environment}.yaml` (environment-specific)
3. **Local Configuration**: `config/config.yaml` (your settings)
4. **Environment Variables**: Override any value with `ZEPHYR_*` variables

### Core Configuration

**Application Settings:**
```yaml
app:
  name: "ZephyrGate"
  environment: "production"  # production, development, testing
  debug: false
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Database Configuration:**
```yaml
database:
  path: "data/zephyrgate.db"
  max_connections: 10
  backup_interval: 86400  # Daily backups (seconds)
  auto_vacuum: true
  wal_mode: true
```

**Meshtastic Interface:**
```yaml
meshtastic:
  interfaces:
    # Serial (USB) connection
    - id: "primary"
      type: "serial"
      port: "/dev/ttyUSB0"
      baud_rate: 921600
      enabled: true
      
    # TCP (Network) connection
    - id: "secondary"
      type: "tcp"
      host: "192.168.1.100"
      tcp_port: 4403
      enabled: false
  
  retry_interval: 30
  max_messages_per_minute: 20
  timeout: 30
```

**Finding Your Serial Port:**
```bash
# List USB devices
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Common ports:
# /dev/ttyUSB0 - USB serial adapter
# /dev/ttyACM0 - USB CDC device
# /dev/ttyAMA0 - Raspberry Pi GPIO serial
```

**Logging Configuration:**
```yaml
logging:
  level: "INFO"
  console: true
  file: "logs/zephyrgate.log"
  max_file_size: 10485760  # 10MB
  backup_count: 5
  
  # Per-service log levels
  services:
    core: "INFO"
    plugin_manager: "INFO"
    message_router: "DEBUG"
```

### Environment Variables

Override any configuration value:

```bash
# Format: ZEPHYR_{SECTION}_{KEY}
export ZEPHYR_APP_LOG_LEVEL=DEBUG
export ZEPHYR_DATABASE_PATH=/custom/path/db.sqlite
export ZEPHYR_MESHTASTIC_INTERFACES_0_PORT=/dev/ttyACM0
```

---

## Plugin System

### Plugin Configuration

```yaml
plugins:
  # Plugin discovery paths
  paths:
    - "plugins"                    # Built-in plugins
    - "examples/plugins"           # Example plugins
    - "/opt/zephyrgate/plugins"   # System-wide plugins
    - "~/.zephyrgate/plugins"     # User-specific plugins
  
  # Automatic discovery and loading
  auto_discover: true
  auto_load: true
  
  # Plugin control
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "bbs_service"
    - "weather_service"
    - "email_service"
    - "asset_service"
    - "web_service"
    - "mqtt_gateway"
    - "traceroute_mapper"
  
  # Health monitoring
  health_check_interval: 60
  failure_threshold: 5
  restart_backoff_base: 2
  restart_backoff_max: 300
```

### Managing Plugins

**Via Web Interface:**
1. Navigate to **Admin Panel → Plugins**
2. View all discovered plugins with status
3. Enable/disable plugins with one click
4. Configure plugin settings
5. View plugin logs and metrics

**Via Configuration File:**
```yaml
plugins:
  enabled_plugins:
    - "bot_service"
    - "my_custom_plugin"
  
  disabled_plugins:
    - "experimental_plugin"
```

**Via Command Line:**
```bash
# List all plugins
python src/main.py --list-plugins

# Enable a plugin
python src/main.py --enable-plugin my_plugin

# Disable a plugin
python src/main.py --disable-plugin my_plugin
```

---

## Auto-Response Configuration

The auto-response system provides intelligent, automated responses to messages based on configurable rules.

> **For complete details, see:** [AUTO_RESPONDER_QUICK_REFERENCE.md](AUTO_RESPONDER_QUICK_REFERENCE.md)

### Basic Configuration

```yaml
services:
  bot:
    enabled: true
    auto_response: true
    
    auto_response:
      enabled: true
      response_rate_limit: 10  # Max responses per hour per user
      cooldown_seconds: 30     # Seconds between responses
      
      # Emergency keywords
      emergency_keywords:
        - 'help'
        - 'emergency'
        - 'urgent'
        - 'mayday'
        - 'sos'
        - 'distress'
      
      # New node greeting
      greeting_enabled: true
      greeting_message: 'Welcome to the mesh! Send "help" for commands.'
      greeting_delay_hours: 24  # Wait 24 hours before greeting again
      
      # Emergency escalation
      emergency_escalation_delay: 300  # 5 minutes
```

### Custom Auto-Response Rules

Add custom rules to respond to specific keywords:

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        # Test response
        - keywords: ['test', 'testing']
          response: "✅ Test received! Signal is good."
          priority: 15
          cooldown_seconds: 30
          max_responses_per_hour: 20
          enabled: true
        
        # Network info
        - keywords: ['info', 'about']
          response: |
            📡 ZephyrGate Mesh Network
            Coverage: Local Area
            Send 'help' for commands
          priority: 40
          cooldown_seconds: 120
          enabled: true
```

### One-Time Greeting

To only greet new nodes once (never seen before):

```yaml
services:
  bot:
    auto_response:
      greeting_enabled: true
      greeting_delay_hours: -1  # Only greet new nodes once ever
      greeting_message: |
        🎉 Welcome to the ZephyrGate Mesh Network!
        
        Quick Start:
        • Send 'help' for all commands
        • Send 'weather' for conditions
        • Send 'bbs' for bulletins
        
        This is a one-time welcome message.
```

---

## Scheduled Broadcasts

Automate messages and tasks with powerful scheduling options.

> **For complete details, see:** [SCHEDULED_BROADCASTS_PLUGIN_REFERENCE.md](SCHEDULED_BROADCASTS_PLUGIN_REFERENCE.md)

### Basic Scheduled Broadcast

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

### Schedule Types

**Cron Schedule (specific times):**
```yaml
broadcasts:
  - name: "Daily Weather"
    message: "Check weather with 'wx' command"
    schedule_type: "cron"
    cron_expression: "0 7 * * *"  # 7 AM daily
```

**Interval Schedule (regular intervals):**
```yaml
broadcasts:
  - name: "Hourly Beacon"
    message: "📡 Network operational"
    schedule_type: "interval"
    interval_seconds: 3600  # Every hour
```

**One-Time Schedule:**
```yaml
broadcasts:
  - name: "Special Event"
    message: "🎉 Event starting now!"
    schedule_type: "one_time"
    scheduled_time: "2024-12-25T12:00:00"
```

### Plugin-Powered Broadcasts

Call plugin functions to generate dynamic content:

```yaml
scheduled_broadcasts:
  broadcasts:
    # Weather forecast
    - name: "Morning Weather"
      plugin_name: "weather_service"
      plugin_method: "get_forecast_report"
      plugin_args:
        user_id: "system"
        days: 3
      schedule_type: "cron"
      cron_expression: "0 7 * * *"
      hop_limit: 3
    
    # Compact weather (GC format)
    - name: "Compact Weather"
      plugin_name: "weather_service"
      plugin_method: "get_gc_forecast"
      plugin_args:
        hours: 8
        fields: ["hour", "icon", "temp", "precip"]
      schedule_type: "cron"
      cron_expression: "0 6,12,18 * * *"  # 3x daily
```

### Shell Command Broadcasts

Execute commands and broadcast results:

```yaml
scheduled_broadcasts:
  broadcasts:
    - name: "System Uptime"
      command: "uptime"
      prefix: "📊 System Status:"
      timeout: 10
      max_output_length: 200
      schedule_type: "cron"
      cron_expression: "0 12 * * *"
```

### Common Cron Expressions

```
"0 8 * * *"      - Every day at 8:00 AM
"0 */6 * * *"    - Every 6 hours
"30 12 * * *"    - Every day at 12:30 PM
"0 9 * * 1"      - Every Monday at 9:00 AM
"*/15 * * * *"   - Every 15 minutes
"0 8 * * 1-5"    - Weekdays at 8 AM
```


---

## MQTT Gateway

The MQTT Gateway forwards messages from your Meshtastic mesh network to MQTT brokers for cloud integration and visualization.

> **For complete details, see:** Plugin README at `plugins/mqtt_gateway/README.md`

### Quick Setup

```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  format: "json"
  region: "US"
  
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

### Complete Configuration

```yaml
mqtt_gateway:
  enabled: true
  
  # Broker connection
  broker_address: "mqtt.meshtastic.org"
  broker_port: 1883
  username: ""
  password: ""
  
  # TLS/SSL (optional)
  tls_enabled: false
  ca_cert: ""
  client_cert: ""
  client_key: ""
  
  # Topic configuration
  root_topic: "msh/US"
  region: "US"
  
  # Message format
  format: "json"  # or "protobuf"
  encryption_enabled: false
  
  # Rate limiting
  max_messages_per_second: 10
  burst_multiplier: 2
  
  # Message queue
  queue_max_size: 1000
  queue_persist: false
  
  # Reconnection
  reconnect_enabled: true
  reconnect_initial_delay: 1
  reconnect_max_delay: 60
  
  # Channel configuration
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position", "nodeinfo", "telemetry"]
```

### Common Use Cases

**Monitor Mesh Remotely:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.meshtastic.org"
  format: "json"
  channels:
    - name: "LongFast"
      uplink_enabled: true
```

**Private Broker with TLS:**
```yaml
mqtt_gateway:
  enabled: true
  broker_address: "mqtt.example.com"
  broker_port: 8883
  username: "meshtastic_gateway"
  password: "secure_password"
  tls_enabled: true
  ca_cert: "/etc/ssl/certs/ca-certificates.crt"
```

**Selective Message Forwarding:**
```yaml
mqtt_gateway:
  channels:
    - name: "LongFast"
      uplink_enabled: true
      message_types: ["text", "position"]  # Only text and GPS
    
    - name: "Admin"
      uplink_enabled: false  # Don't forward admin channel
```

### Subscribing to Messages

```bash
# Subscribe to all messages in a region
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/#" -v

# Subscribe to specific channel
mosquitto_sub -h mqtt.meshtastic.org -t "msh/US/2/json/LongFast/#" -v

# Subscribe with authentication
mosquitto_sub -h mqtt.example.com -u username -P password -t "msh/US/2/json/#" -v
```

### Troubleshooting MQTT

**Check Connection:**
```bash
# Test MQTT connection
mosquitto_pub -h mqtt.meshtastic.org -t "test/topic" -m "test message"

# View logs
tail -f logs/zephyrgate.log | grep mqtt_gateway
```

**Common Issues:**
- **Cannot connect**: Check broker address, port, and credentials
- **Messages not forwarding**: Verify channel configuration and `uplink_enabled: true`
- **Queue overflow**: Increase `queue_max_size` or fix broker connection

---

## Service Management

### Managing Services

**Via Systemd (if installed as service):**
```bash
# Start ZephyrGate
sudo systemctl start zephyrgate

# Stop ZephyrGate
sudo systemctl stop zephyrgate

# Restart ZephyrGate
sudo systemctl restart zephyrgate

# Check status
sudo systemctl status zephyrgate

# Enable auto-start on boot
sudo systemctl enable zephyrgate

# View logs
sudo journalctl -u zephyrgate -f
```

**Via Scripts:**
```bash
# Start ZephyrGate
./start.sh

# Stop ZephyrGate
./stop.sh

# Restart
./stop.sh && ./start.sh
```

**Via Web Interface:**
1. Navigate to **Admin Panel → System**
2. Use service controls to start/stop/restart
3. View real-time status and metrics

### Service Health Monitoring

```bash
# Check overall health
curl http://localhost:8080/health

# Detailed health check
curl http://localhost:8080/health/detailed

# Plugin health
curl http://localhost:8080/api/plugins/health
```

---

## User Management

### User Database

Users are automatically registered when they send messages. Manage users via web interface or command line.

**Via Web Interface:**
1. Navigate to **Admin Panel → Users**
2. View all registered users
3. Edit user profiles and permissions
4. Manage subscriptions
5. View user activity

**Via Command Line:**
```bash
# List all users
python src/main.py --list-users

# View user details
python src/main.py --user-info "!12345678"

# Update user
python src/main.py --update-user "!12345678" --name "John Doe" --email "john@example.com"

# Set user permissions
python src/main.py --set-permissions "!12345678" --permissions "admin,responder"
```

### User Permissions

```yaml
permissions:
  admin:
    - "system.manage"
    - "users.manage"
    - "plugins.manage"
    - "emergency.manage"
  
  responder:
    - "emergency.respond"
    - "emergency.view"
  
  moderator:
    - "bbs.moderate"
    - "bbs.delete"
  
  user:
    - "bbs.read"
    - "bbs.post"
    - "weather.view"
```

---

## Security

### Web Interface Security

```yaml
web:
  auth:
    enabled: true
    session_timeout: 3600
    require_auth: true
    default_username: "admin"
    default_password: "admin"  # CHANGE THIS!
    
  security:
    max_login_attempts: 5
    lockout_duration: 900
    csrf_protection: true
    secure_cookies: true
```

**⚠️ Important**: Change the default admin password immediately after installation!

### Network Security

```bash
# Configure firewall
sudo ufw enable
sudo ufw allow 8080/tcp  # Web interface
sudo ufw allow 22/tcp    # SSH (if needed)

# For Meshtastic TCP
sudo ufw allow 4403/tcp
```

### SSL/TLS Configuration

```yaml
web:
  ssl:
    enabled: true
    cert_file: "/etc/ssl/certs/zephyrgate.crt"
    key_file: "/etc/ssl/private/zephyrgate.key"
```

**Generate self-signed certificate:**
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### API Security

```yaml
api:
  authentication:
    enabled: true
    type: "jwt"
    secret_key: "your-secret-key-change-this"
    token_expiry: 3600
  
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
```

### Best Practices

1. **Change default passwords** immediately
2. **Use TLS/SSL** in production
3. **Restrict web interface** to localhost if not needed remotely
4. **Use strong passwords** (16+ characters)
5. **Keep system updated**: `sudo apt-get update && sudo apt-get upgrade`
6. **Regular backups** of configuration and database
7. **Monitor logs** for suspicious activity
8. **Use firewall** to restrict access

---

## Monitoring and Maintenance

### Daily Maintenance

**Automated Health Checks:**
```bash
#!/bin/bash
# daily-health-check.sh

# Check service status
systemctl is-active --quiet zephyrgate && echo "✓ Service running" || echo "✗ Service down"

# Check web interface
curl -f -s http://localhost:8080/health > /dev/null && echo "✓ Web interface OK" || echo "✗ Web interface down"

# Check disk space
df -h /opt/zephyrgate

# Check memory usage
free -h

# Check database integrity
sqlite3 /opt/zephyrgate/data/zephyrgate.db "PRAGMA integrity_check;"
```

### Log Management

**View Logs:**
```bash
# Real-time logs
tail -f logs/zephyrgate.log

# Search for errors
grep "ERROR" logs/zephyrgate.log

# View last 100 lines
tail -n 100 logs/zephyrgate.log

# Service logs (if systemd)
sudo journalctl -u zephyrgate -f
```

**Log Rotation:**
```yaml
logging:
  max_file_size: 10485760  # 10MB
  backup_count: 5  # Keep 5 old log files
```

### Performance Monitoring

**System Metrics:**
```bash
# System resources
curl http://localhost:8080/api/system/resources

# Message throughput
curl http://localhost:8080/api/metrics/messages

# Plugin performance
curl http://localhost:8080/api/plugins/metrics
```

**Monitor Resources:**
```bash
# CPU and memory usage
top -bn1 | grep zephyrgate

# Disk usage
du -sh /opt/zephyrgate/*

# Network connections
netstat -tlnp | grep :8080
```

### Weekly Maintenance

**Database Optimization:**
```bash
#!/bin/bash
# optimize-database.sh

DB_PATH="/opt/zephyrgate/data/zephyrgate.db"

# Backup before optimization
cp $DB_PATH "$DB_PATH.backup.$(date +%Y%m%d)"

# Optimize database
sqlite3 $DB_PATH << EOF
ANALYZE;
REINDEX;
VACUUM;
ANALYZE;
EOF

echo "Database optimization completed"
```

**Log Cleanup:**
```bash
#!/bin/bash
# log-cleanup.sh

LOG_DIR="/opt/zephyrgate/logs"
RETENTION_DAYS=30

# Compress old logs
find $LOG_DIR -name "*.log.*" -mtime +1 -exec gzip {} \;

# Remove old compressed logs
find $LOG_DIR -name "*.log.*.gz" -mtime +$RETENTION_DAYS -delete

echo "Log cleanup completed"
```

---

## Backup and Recovery

### Automated Backups

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  
  targets:
    database: true
    configuration: true
    logs: false
  
  retention_days: 30
  
  storage:
    local:
      path: "/backup/zephyrgate"
```

### Manual Backup

**Full Backup:**
```bash
#!/bin/bash
# full-backup.sh

BACKUP_DIR="/backup/zephyrgate"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Database backup
sqlite3 /opt/zephyrgate/data/zephyrgate.db ".backup '$BACKUP_DIR/database-$DATE.sqlite'"

# Configuration backup
tar -czf $BACKUP_DIR/config-$DATE.tar.gz -C /opt/zephyrgate config/

# Application data backup
tar -czf $BACKUP_DIR/data-$DATE.tar.gz -C /opt/zephyrgate data/ --exclude=data/zephyrgate.db

echo "Backup completed: $DATE"
```

**Database Only:**
```bash
# Backup database
cp data/zephyrgate.db backups/zephyrgate-$(date +%Y%m%d).db

# Or use SQLite backup command
sqlite3 data/zephyrgate.db ".backup 'backups/zephyrgate-$(date +%Y%m%d).sqlite'"
```

### Restore from Backup

```bash
#!/bin/bash
# restore-system.sh

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

# Stop services
systemctl stop zephyrgate

# Restore database
cp "$BACKUP_FILE" /opt/zephyrgate/data/zephyrgate.db

# Set permissions
chown zephyrgate:zephyrgate /opt/zephyrgate/data/zephyrgate.db
chmod 644 /opt/zephyrgate/data/zephyrgate.db

# Start services
systemctl start zephyrgate

echo "Restore completed"
```

---

## Performance Tuning

### Database Optimization

```yaml
database:
  max_connections: 20
  wal_mode: true
  auto_vacuum: true
  cache_size: 10000
  vacuum_interval: 86400  # Daily
```

### Memory Management

```yaml
app:
  max_memory_mb: 1024
  
  cache:
    enabled: true
    max_size_mb: 256
    ttl_seconds: 3600
```

### Message Queue Optimization

```yaml
message_router:
  queue_size: 10000
  batch_size: 100
  worker_threads: 4
  timeout: 30
```

### Raspberry Pi Optimization

```bash
# Increase swap space
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
```


---

## Troubleshooting

> **For detailed troubleshooting, see:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Common Issues

**Service Won't Start:**
```bash
# Check configuration
python src/main.py --config-test

# Check logs
tail -f logs/zephyrgate.log

# Check permissions
ls -la data/
chmod 755 data/
```

**Database Issues:**
```bash
# Check database integrity
sqlite3 data/zephyrgate.db "PRAGMA integrity_check;"

# Backup and repair
cp data/zephyrgate.db data/zephyrgate.db.backup
sqlite3 data/zephyrgate.db ".recover" | sqlite3 data/zephyrgate_new.db
```

**Meshtastic Connection Issues:**
```bash
# Check serial port
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Test connection
python -c "import serial; s=serial.Serial('/dev/ttyUSB0', 921600); print('OK')"

# Check permissions
sudo usermod -a -G dialout $USER
# Log out and back in
```

**Plugin Issues:**
```bash
# List plugins
python src/main.py --list-plugins

# Check plugin health
curl http://localhost:8080/api/plugins/health

# View plugin logs
grep "plugin_name" logs/zephyrgate.log
```

**Permission Denied on Serial Port:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

**Port Already in Use:**
1. Edit `config/config.yaml`
2. Change `web.port` to a different port (e.g., 8081)
3. Restart ZephyrGate

### Diagnostic Commands

```bash
# System health check
curl http://localhost:8080/health/detailed

# Check configuration
python src/main.py --config-test

# Test database
sqlite3 data/zephyrgate.db "SELECT COUNT(*) FROM users;"

# Check disk space
df -h

# Check memory
free -h

# Check processes
ps aux | grep zephyrgate
```

---

## Docker Deployment

> **For complete Docker documentation, see:** [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) (if available)

### Quick Docker Setup

**Using Docker Run:**
```bash
# Find your Meshtastic device
ls -la /dev/ttyUSB* /dev/ttyACM*

# Run ZephyrGate
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  -v zephyr_logs:/app/logs \
  -v zephyr_config:/app/config \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest

# Access web interface
open http://localhost:8080
```

### Docker Compose (Recommended)

**Create docker-compose.yml:**
```yaml
version: '3.8'

services:
  zephyrgate:
    image: YOUR_USERNAME/zephyrgate:latest
    container_name: zephyrgate
    restart: unless-stopped
    
    ports:
      - "8080:8080"
    
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    
    environment:
      - TZ=America/New_York
      - ZEPHYR_LOG_LEVEL=INFO
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Docker Commands:**
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# View logs
docker-compose logs -f

# Update to latest version
docker-compose pull
docker-compose up -d
```

### Docker Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `UTC` | Timezone (e.g., America/New_York) |
| `ZEPHYR_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `ZEPHYR_WEB_PORT` | `8080` | Web interface port |
| `ZEPHYR_DEBUG` | `false` | Enable debug mode |

### Production Docker Configuration

```yaml
version: '3.8'

services:
  zephyrgate:
    image: YOUR_USERNAME/zephyrgate:1.0.0  # Use specific version
    container_name: zephyrgate-prod
    restart: unless-stopped
    
    ports:
      - "127.0.0.1:8080:8080"  # Only localhost
    
    volumes:
      - /opt/zephyrgate/data:/app/data
      - /opt/zephyrgate/logs:/app/logs
      - /opt/zephyrgate/config:/app/config:ro
    
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    
    environment:
      - ZEPHYR_APP_ENVIRONMENT=production
      - ZEPHYR_DEBUG=false
      - ZEPHYR_LOG_LEVEL=INFO
      - TZ=America/New_York
    
    security_opt:
      - no-new-privileges:true
    
    user: "1000:1000"
    
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
    
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

### Docker Troubleshooting

**Container Won't Start:**
```bash
# Check logs
docker logs zephyrgate

# Check if port is in use
sudo lsof -i :8080

# Check device permissions
ls -la /dev/ttyUSB0

# Run with debug mode
docker run -e ZEPHYR_DEBUG=true -e ZEPHYR_LOG_LEVEL=DEBUG ...
```

**Device Not Found:**
```bash
# List devices
ls -la /dev/tty*

# Check if device is passed correctly
docker inspect zephyrgate | grep -A 10 Devices

# Try privileged mode (temporary)
docker run --privileged ...
```

**Permission Denied:**
```bash
# Add user to dialout group
sudo usermod -aG dialout $USER

# Logout and login again
```

---

## Additional Configuration

### Weather Service

```yaml
weather:
  enabled: true
  
  providers:
    noaa:
      enabled: true
      cache_duration: 600
    
    openmeteo:
      enabled: true
      cache_duration: 600
  
  alerts:
    enabled: true
    check_interval: 300
    sources:
      - "noaa"
      - "fema_ipaws"
      - "usgs_earthquake"
```

### Email Gateway

```yaml
email:
  enabled: true
  check_interval: 300
  
  smtp:
    enabled: true
    host: "smtp.gmail.com"
    port: 587
    use_tls: true
    username: "your-email@gmail.com"
    password: "your-app-password"
  
  imap:
    enabled: true
    host: "imap.gmail.com"
    port: 993
    use_ssl: true
    username: "your-email@gmail.com"
    password: "your-app-password"
```

### BBS Service

```yaml
bbs:
  enabled: true
  
  database:
    path: "data/bbs.db"
  
  bulletins:
    max_subject_length: 100
    max_content_length: 1000
    retention_days: 90
  
  mail:
    max_inbox_size: 100
    retention_days: 30
```

### Emergency Service

```yaml
emergency:
  enabled: true
  
  emergency_keywords:
    - "sos"
    - "emergency"
    - "help"
    - "mayday"
  
  escalation_delay: 300  # 5 minutes
  auto_escalate: true
  check_in_interval: 600  # 10 minutes
```

### Network Traceroute Mapper

```yaml
traceroute_mapper:
  enabled: false  # Disabled by default
  
  traceroutes_per_minute: 1
  max_hops: 7
  recheck_interval_hours: 6
  skip_direct_nodes: true
  
  forward_to_mqtt: true
  
  quiet_hours:
    enabled: false
    start_time: "22:00"
    end_time: "06:00"
```

---

## Integration Setup

### Weather API Keys

**NOAA (US):**
- No API key required
- Free for non-commercial use

**Open-Meteo:**
- No API key required
- Global coverage

### Email Setup

**Gmail:**
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use in configuration

**Office 365:**
```yaml
smtp:
  host: "smtp.office365.com"
  port: 587
imap:
  host: "outlook.office365.com"
  port: 993
```

### AI Integration

**Ollama (Local):**
```yaml
ai:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    model: "llama2"
```

**OpenAI:**
```yaml
ai:
  openai:
    enabled: true
    api_key: "your-api-key"
    model: "gpt-3.5-turbo"
```

---

## Additional Resources

### Documentation

- **Quick Start**: [QUICK_START.md](QUICK_START.md) - Get started quickly
- **User Manual**: [USER_MANUAL.md](USER_MANUAL.md) - End-user documentation
- **Developer Guide**: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Development documentation
- **Testing Guide**: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures
- **Features Overview**: [FEATURES_OVERVIEW.md](FEATURES_OVERVIEW.md) - Complete feature list

### Quick References

- **Auto-Responder**: [AUTO_RESPONDER_QUICK_REFERENCE.md](AUTO_RESPONDER_QUICK_REFERENCE.md)
- **Scheduled Broadcasts**: [SCHEDULED_BROADCASTS_PLUGIN_REFERENCE.md](SCHEDULED_BROADCASTS_PLUGIN_REFERENCE.md)
- **GC Forecast**: [GC_FORECAST_QUICK_REFERENCE.md](GC_FORECAST_QUICK_REFERENCE.md)
- **Command Reference**: [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md)
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

### Plugin Documentation

- **MQTT Gateway**: `plugins/mqtt_gateway/README.md`
- **Villages Events**: `plugins/villages_events_service/README.md`
- **Plugin Development**: [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md)

### Configuration Examples

- **Auto-Response Examples**: `examples/auto_response_examples.yaml`
- **Scheduled Broadcasts**: `examples/villages_events_scheduled_broadcasts.yaml`
- **Config Templates**: `config/config-example.yaml`, `config/config-example-no-internet.yaml`

---

## Support

For additional help:
- **Documentation**: Review all docs in `docs/` directory
- **Logs**: Check `tail -f logs/zephyrgate.log`
- **GitHub Issues**: Report bugs and request features
- **Community**: Join discussions and share experiences

---

**Last Updated:** February 2026  
**Version:** 2.0 with Plugin System

