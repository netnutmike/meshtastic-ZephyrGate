# ZephyrGate Administrator Guide

**Version 2.0** - Updated with Plugin System and New Features

## Table of Contents

1. [Installation and Deployment](#installation-and-deployment)
2. [Configuration Management](#configuration-management)
3. [Plugin System Configuration](#plugin-system-configuration)
4. [Service-Specific Configuration](#service-specific-configuration)
5. [Scheduled Tasks and Automation](#scheduled-tasks-and-automation)
6. [Service Management](#service-management)
7. [User Management](#user-management)
8. [Security Configuration](#security-configuration)
9. [Monitoring and Maintenance](#monitoring-and-maintenance)
10. [Backup and Recovery](#backup-and-recovery)
11. [Troubleshooting](#troubleshooting)
12. [Performance Tuning](#performance-tuning)
13. [Integration Setup](#integration-setup)

## Installation and Deployment

### Quick Installation (Recommended)

The easiest way to install ZephyrGate is using the interactive installer:

```bash
# 1. Clone repository
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate

# 2. Run interactive installer
./install.sh

# 3. Start ZephyrGate
./start.sh
```

The installer will:
- Check and install system requirements
- Set up Python virtual environment
- Configure Meshtastic connection
- Let you select plugins to enable
- Create configuration files
- Optionally set up as system service

For detailed installation instructions, see the [Installation Guide](INSTALLATION.md).

### Docker Deployment

#### Quick Start with Docker Compose

```bash
# 1. Clone and configure
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate
cp .env.example .env

# 2. Edit environment variables
nano .env

# 3. Start services
docker-compose up -d

# 4. Check logs
docker-compose logs -f zephyrgate
```


#### Production Docker Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  zephyrgate:
    image: zephyrgate:latest
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Manual Installation

#### System Requirements
- Python 3.8+
- SQLite 3.35+
- 2GB RAM minimum (4GB recommended)
- 10GB disk space

#### Installation Steps

1. **Install Dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip python3-venv sqlite3 git
   
   # CentOS/RHEL
   sudo yum install python3 python3-pip sqlite git
   ```

2. **Create Application User**:
   ```bash
   sudo useradd -r -s /bin/false zephyrgate
   sudo mkdir -p /opt/zephyrgate
   sudo chown zephyrgate:zephyrgate /opt/zephyrgate
   ```

3. **Install Application**:
   ```bash
   cd /opt/zephyrgate
   sudo -u zephyrgate git clone https://github.com/your-repo/zephyrgate.git .
   sudo -u zephyrgate python3 -m venv .venv
   sudo -u zephyrgate ./.venv/bin/pip install -r requirements.txt
   ```

4. **Create Systemd Service**:
   ```ini
   # /etc/systemd/system/zephyrgate.service
   [Unit]
   Description=ZephyrGate Meshtastic Gateway
   After=network.target
   
   [Service]
   Type=simple
   User=zephyrgate
   Group=zephyrgate
   WorkingDirectory=/opt/zephyrgate
   ExecStart=/opt/zephyrgate/.venv/bin/python src/main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

5. **Enable and Start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable zephyrgate
   sudo systemctl start zephyrgate
   ```


## Configuration Management

### Configuration File Structure

ZephyrGate uses YAML configuration files with hierarchical loading:

1. **Default Configuration**: `config/default.yaml` (base settings)
2. **Environment Configuration**: `config/{environment}.yaml` (environment-specific)
3. **Local Configuration**: `config/config.yaml` (your settings)
4. **Environment Variables**: Override any value with `ZEPHYR_*` variables

### Core Configuration Sections

#### Application Settings

```yaml
app:
  name: "ZephyrGate"
  version: "2.0.0"
  environment: "production"  # production, development, testing
  debug: false
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Database Configuration

```yaml
database:
  path: "data/zephyrgate.db"  # SQLite database file
  max_connections: 10
  backup_interval: 86400  # Daily backups (seconds)
  
  # Automatic maintenance
  auto_vacuum: true
  wal_mode: true  # Write-Ahead Logging for better concurrency
```

#### Meshtastic Interface Configuration

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
      
    # Bluetooth LE connection
    - id: "bluetooth"
      type: "ble"
      ble_address: "AA:BB:CC:DD:EE:FF"
      enabled: false
  
  # Global settings
  retry_interval: 30  # Reconnection interval (seconds)
  max_messages_per_minute: 20  # Rate limiting
  timeout: 30  # Command timeout (seconds)
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

#### Logging Configuration

```yaml
logging:
  level: "INFO"  # Global log level
  console: true  # Log to console
  console_level: "INFO"
  file: "logs/zephyrgate.log"
  max_file_size: 10485760  # 10MB
  backup_count: 5  # Keep 5 old log files
  
  # Per-service log levels
  services:
    core: "INFO"
    plugin_manager: "INFO"
    message_router: "DEBUG"
    bot_service: "INFO"
    emergency_service: "WARNING"
```

#### Security Configuration

```yaml
security:
  require_node_auth: false  # Require node authentication
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60
    burst_size: 10
  
  # Web interface security
  web:
    session_timeout: 3600  # 1 hour
    max_login_attempts: 5
    lockout_duration: 900  # 15 minutes
```

### Environment Variables

Override any configuration value using environment variables:

```bash
# Format: ZEPHYR_{SECTION}_{KEY}
export ZEPHYR_APP_LOG_LEVEL=DEBUG
export ZEPHYR_DATABASE_PATH=/custom/path/db.sqlite
export ZEPHYR_MESHTASTIC_INTERFACES_0_PORT=/dev/ttyACM0
```


## Plugin System Configuration

### Overview

ZephyrGate 2.0 introduces a comprehensive plugin system that allows both built-in services and third-party extensions to be managed uniformly. All major features (bot, emergency, BBS, weather, email, asset tracking, web admin) are now implemented as plugins.

### Plugin Configuration

```yaml
plugins:
  # Plugin discovery paths (searched in order)
  paths:
    - "plugins"                    # Built-in plugins
    - "examples/plugins"           # Example plugins
    - "/opt/zephyrgate/plugins"   # System-wide plugins
    - "~/.zephyrgate/plugins"     # User-specific plugins
  
  # Automatic discovery and loading
  auto_discover: true  # Scan paths for plugins
  auto_load: true      # Load discovered plugins on startup
  
  # Plugin control
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "bbs_service"
    - "weather_service"
    - "email_service"
    - "asset_service"
    - "web_service"
  
  # Explicitly disable plugins
  disabled_plugins: []
  
  # Health monitoring
  health_check_interval: 60     # Check every 60 seconds
  failure_threshold: 5          # Disable after 5 failures
  restart_backoff_base: 2       # Start with 2 second delay
  restart_backoff_max: 300      # Max 5 minute delay
  
  # Resource limits (per plugin)
  max_http_requests_per_minute: 100
  max_storage_size_mb: 100
  task_timeout: 300  # 5 minutes
```

### Plugin Discovery

**How Plugin Discovery Works:**

1. ZephyrGate scans each path in `plugins.paths`
2. Looks for directories containing:
   - `__init__.py` - Python package marker
   - `manifest.yaml` - Plugin metadata
   - `plugin.py` - Plugin implementation
3. Validates manifest and checks dependencies
4. Loads plugins that are enabled and not disabled

**Plugin Directory Structure:**

```
plugins/my_plugin/
├── __init__.py           # Package initialization
├── manifest.yaml         # Plugin metadata
├── plugin.py             # Main plugin class
├── config_schema.json    # Configuration schema (optional)
├── requirements.txt      # Python dependencies (optional)
└── README.md            # Documentation (optional)
```

### Managing Plugins

#### Via Web Interface

1. Navigate to **Admin Panel → Plugins**
2. View all discovered plugins with status
3. Enable/disable plugins with one click
4. Configure plugin settings
5. View plugin logs and metrics
6. Restart individual plugins

#### Via Configuration File

Edit `config/config.yaml`:

```yaml
plugins:
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "my_custom_plugin"  # Add your plugin
  
  disabled_plugins:
    - "experimental_plugin"  # Disable specific plugin
```

Then reload configuration:

```bash
# Restart ZephyrGate
./stop.sh && ./start.sh

# Or reload without restart (if supported)
kill -HUP $(pgrep -f "python.*main.py")
```

#### Via Command Line

```bash
# List all plugins
python src/main.py --list-plugins

# Enable a plugin
python src/main.py --enable-plugin my_plugin

# Disable a plugin
python src/main.py --disable-plugin my_plugin

# Reload plugins
python src/main.py --reload-plugins
```

### Plugin Health Monitoring

ZephyrGate automatically monitors plugin health:

**Health Check Process:**

1. Every `health_check_interval` seconds, check each plugin
2. If plugin fails health check, increment failure counter
3. If failures reach `failure_threshold`, disable plugin
4. Attempt automatic restart with exponential backoff
5. Log all health events for troubleshooting

**Viewing Plugin Health:**

```bash
# Via web interface
http://localhost:8080/admin/plugins

# Via API
curl http://localhost:8080/api/plugins/health

# Via logs
grep "plugin.*health" logs/zephyrgate.log
```

### Plugin Resource Limits

Protect system resources by limiting plugin usage:

```yaml
plugins:
  # HTTP rate limiting
  max_http_requests_per_minute: 100  # Per plugin
  
  # Storage limits
  max_storage_size_mb: 100  # Database storage per plugin
  
  # Execution limits
  task_timeout: 300  # Max task execution time (seconds)
  max_memory_mb: 512  # Memory limit per plugin (if supported)
```

**Monitoring Resource Usage:**

```bash
# View plugin resource usage
curl http://localhost:8080/api/plugins/resources

# Check specific plugin
curl http://localhost:8080/api/plugins/my_plugin/resources
```


## Service-Specific Configuration

All services are now implemented as plugins. Configure them under the service name or plugin name.

### Bot Service Plugin

The bot service provides interactive commands, games, and auto-response features.

```yaml
# Configuration can be under 'services.bot' or 'bot' section
bot:
  enabled: true
  
  # Auto-response configuration
  auto_response:
    enabled: true
    emergency_keywords:
      - "help"
      - "emergency"
      - "urgent"
      - "mayday"
      - "sos"
      - "distress"
    
    # New node greeting
    greeting_enabled: true
    greeting_message: "Welcome to the mesh! Send 'help' for commands."
    greeting_delay_hours: 24  # Wait 24 hours before greeting
    
    # Aircraft detection and responses
    aircraft_responses: true
    emergency_escalation_delay: 300  # 5 minutes
    
    # Rate limiting
    response_rate_limit: 10  # Max responses per hour
    cooldown_seconds: 30  # Cooldown between responses
  
  # Command system
  commands:
    enabled: true
    help_enabled: true
    permissions_enabled: false  # Require permissions for commands
  
  # AI integration
  ai:
    enabled: false
    provider: "ollama"  # ollama, openai
    model: "llama2"
    base_url: "http://localhost:11434"
    aircraft_detection: true
    altitude_threshold: 1000  # meters
  
  # Games
  games:
    enabled: true
    available_games:
      - "blackjack"
      - "dopewars"
      - "lemonade"
      - "golf"
  
  # Message history
  message_history:
    enabled: true
    retention_days: 30
    max_offline_messages: 50
  
  # Monitoring
  monitoring:
    new_node_detection: true
    node_activity_tracking: true
    response_analytics: true
```

**Bot Service Commands:**
- `help` - Show available commands
- `ping` - Test bot responsiveness
- `info <topic>` - Get information
- `history [count]` - View message history
- `games` - List available games
- `play <game>` - Start a game


### Emergency Service Plugin

Handles SOS alerts, incident management, and responder coordination.

```yaml
emergency:
  enabled: true
  
  # Emergency keywords that trigger alerts
  emergency_keywords:
    - "sos"
    - "emergency"
    - "help"
    - "mayday"
    - "urgent"
    - "distress"
  
  # Escalation settings
  escalation_delay: 300  # 5 minutes before escalation
  auto_escalate: true
  broadcast_channel: 0  # Channel for broadcasts
  
  # Check-in system
  check_in_interval: 600  # 10 minutes
  check_in_required: true
  missed_checkin_action: "escalate"  # escalate, notify, ignore
  
  # Responder management
  max_responders: 5
  responder_timeout: 3600  # 1 hour
  
  # Incident tracking
  incident_retention_days: 90
  auto_close_resolved: true
  auto_close_delay: 86400  # 24 hours
  
  # Notifications
  notify_on_sos: true
  notify_on_response: true
  notify_on_resolution: true
  
  # Responder groups
  responder_groups:
    - name: "SAR"
      priority: 1
      members: ["!12345678", "!87654321"]
    - name: "FIRE"
      priority: 2
      members: ["!11111111", "!22222222"]
    - name: "MEDICAL"
      priority: 3
      members: ["!33333333", "!44444444"]
```

**Emergency Service Commands:**
- `sos <message>` - Send emergency alert
- `cancel` - Cancel your active SOS
- `respond <incident_id>` - Respond to emergency
- `status` - Check emergency status
- `checkin` - Check in during emergency

**Emergency Alert Types:**
- `SOS` - General emergency
- `SOSP` - Police needed
- `SOSF` - Fire emergency
- `SOSM` - Medical emergency

### BBS Service Plugin

Bulletin board system with mail, bulletins, and channel directory.

```yaml
bbs:
  enabled: true
  
  # Database configuration
  database:
    path: "data/bbs.db"
  
  # Bulletin settings
  bulletins:
    max_subject_length: 100
    max_content_length: 1000
    retention_days: 90
    max_bulletins_per_user: 50
    moderation_enabled: false
  
  # Mail system
  mail:
    max_subject_length: 100
    max_content_length: 1000
    retention_days: 30
    max_inbox_size: 100
    attachment_support: false
  
  # Channel directory
  channels:
    max_name_length: 50
    max_description_length: 200
    auto_discover: true
  
  # Menu system
  menu:
    timeout: 300  # 5 minutes
    max_depth: 5
    show_help: true
  
  # Synchronization (multi-node BBS)
  sync:
    enabled: false
    peers:
      - "192.168.1.101:4404"
      - "192.168.1.102:4404"
    sync_interval: 3600  # 1 hour
    conflict_resolution: "newest"  # newest, oldest, manual
```

**BBS Service Commands:**
- `bbs` - Access BBS menu
- `read [id]` - Read bulletin
- `post <subject> <content>` - Post bulletin
- `mail` - Check mail
- `mail send <to> <subject> <content>` - Send mail
- `directory` - View channel directory


### Weather Service Plugin

Provides weather conditions, forecasts, and alerts from multiple sources.

```yaml
weather:
  enabled: true
  
  # Weather data providers
  providers:
    noaa:
      enabled: true
      api_key: ""  # Optional
      base_url: "https://api.weather.gov"
      timeout: 30
      cache_duration: 600  # 10 minutes
    
    openmeteo:
      enabled: true
      base_url: "https://api.open-meteo.com/v1"
      timeout: 30
      cache_duration: 600
  
  # Cache settings
  cache:
    ttl_seconds: 600  # 10 minutes
    max_entries: 1000
  
  # Weather alerts
  alerts:
    enabled: true
    check_interval: 300  # 5 minutes
    sources:
      - "noaa"
      - "fema_ipaws"
      - "usgs_earthquake"
    severity_filter: ["severe", "extreme"]  # Filter by severity
    notify_users: true
  
  # Location settings
  location:
    default_latitude: 0.0
    default_longitude: 0.0
    use_node_location: true  # Use node GPS if available
    location_accuracy: "city"  # city, county, state
  
  # Forecast settings
  forecast:
    default_days: 3
    max_days: 7
    include_hourly: false
  
  # Environmental monitoring
  environmental:
    enabled: false
    sensors:
      - type: "temperature"
        threshold_high: 35  # Celsius
        threshold_low: -10
      - type: "humidity"
        threshold_high: 90  # Percent
        threshold_low: 20
```

**Weather Service Commands:**
- `wx [location]` - Current weather
- `weather [location]` - Detailed weather
- `forecast [days] [location]` - Weather forecast
- `alerts [location]` - Active weather alerts

**Weather Data Sources:**
- **NOAA**: US National Weather Service (US only)
- **Open-Meteo**: Global weather data (worldwide)
- **FEMA iPAWS**: Emergency alerts (US)
- **USGS**: Earthquake data (global)

### Email Service Plugin

Email gateway for sending and receiving emails via mesh network.

```yaml
email:
  enabled: true
  
  # Check interval for new emails
  check_interval: 300  # 5 minutes (0 to disable)
  
  # SMTP configuration (outgoing mail)
  smtp:
    enabled: true
    host: "smtp.gmail.com"
    port: 587
    use_tls: true
    username: "your-email@gmail.com"
    password: "your-app-password"  # Use app-specific password
    from_address: "your-email@gmail.com"
    timeout: 30
  
  # IMAP configuration (incoming mail)
  imap:
    enabled: true
    host: "imap.gmail.com"
    port: 993
    use_ssl: true
    username: "your-email@gmail.com"
    password: "your-app-password"
    folder: "INBOX"
    mark_as_read: true
    timeout: 30
  
  # Email processing
  processing:
    max_size_kb: 100  # Max email size to process
    strip_html: true
    include_attachments: false
    subject_prefix: "[MESH]"
  
  # Filtering
  filters:
    whitelist: []  # Only process emails from these addresses
    blacklist: []  # Never process emails from these addresses
    spam_filter: true
  
  # Notifications
  notifications:
    notify_on_receive: true
    notify_recipients: ["!12345678"]  # Node IDs to notify
```

**Email Service Commands:**
- `email send <to> <subject> <body>` - Send email
- `email check` - Check for new emails
- `send <to> <subject> <body>` - Send email (shortcut)
- `check` - Check emails (shortcut)

**Email Gateway Setup:**

For Gmail:
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use app password in configuration

For Office 365:
```yaml
smtp:
  host: "smtp.office365.com"
  port: 587
imap:
  host: "outlook.office365.com"
  port: 993
```


### Asset Tracking Service Plugin

Track personnel, equipment, and assets with location monitoring.

```yaml
asset:
  enabled: true
  
  # Database configuration
  database:
    path: "data/assets.db"
  
  # Tracking settings
  tracking:
    update_interval: 300  # 5 minutes
    location_accuracy: 10  # meters
    auto_track_nodes: false  # Automatically track all nodes
    require_checkin: true
  
  # Geofencing
  geofencing:
    enabled: true
    alert_on_breach: true
    alert_recipients: ["!12345678"]
    zones:
      - name: "Base Camp"
        latitude: 40.7128
        longitude: -74.0060
        radius: 100  # meters
        alert_on_enter: false
        alert_on_exit: true
  
  # Asset types
  asset_types:
    - name: "Personnel"
      icon: "person"
      require_checkin: true
      checkin_interval: 3600  # 1 hour
    - name: "Vehicle"
      icon: "car"
      require_checkin: false
    - name: "Equipment"
      icon: "tool"
      require_checkin: false
  
  # Reporting
  reporting:
    daily_summary: true
    summary_time: "08:00"
    summary_recipients: ["!12345678"]
```

**Asset Service Commands:**
- `track <asset_id> [lat] [lon]` - Track asset
- `locate [asset_id]` - Locate asset
- `status <asset_id>` - Get asset status
- `checkin <asset_id>` - Check in asset
- `checkout <asset_id>` - Check out asset

### Web Admin Service Plugin

Web-based administration interface with real-time monitoring.

```yaml
web:
  enabled: true
  
  # Server configuration
  host: "0.0.0.0"  # Listen on all interfaces
  port: 8080
  debug: false
  
  # WebSocket configuration
  websocket:
    enabled: true
    ping_interval: 30  # seconds
    max_connections: 100
  
  # Authentication
  auth:
    enabled: true
    session_timeout: 3600  # 1 hour
    require_auth: true
    default_username: "admin"
    default_password: "admin"  # CHANGE THIS!
  
  # Security
  security:
    enabled: true
    max_login_attempts: 5
    lockout_duration: 900  # 15 minutes
    csrf_protection: true
    secure_cookies: true  # Requires HTTPS
  
  # Features
  features:
    dashboard: true
    plugin_management: true
    user_management: true
    system_monitoring: true
    log_viewer: true
    configuration_editor: true
  
  # Static files
  static_path: "src/services/web/static"
  template_path: "src/services/web/templates"
  
  # HTTPS (optional)
  ssl:
    enabled: false
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"
```

**Web Interface Access:**

1. Open browser: `http://localhost:8080`
2. Login with credentials (default: admin/admin)
3. **IMPORTANT**: Change default password immediately!

**Web Interface Features:**
- Real-time dashboard with system metrics
- Plugin management (enable/disable/configure)
- User management and permissions
- Message monitoring and search
- System logs viewer
- Configuration editor
- Performance metrics and graphs


## Scheduled Tasks and Automation

### Overview

ZephyrGate supports scheduled tasks for automation. Tasks can be configured at the system level or within individual plugins.

### System-Level Scheduled Tasks

Configure recurring tasks in the main configuration:

```yaml
scheduled_tasks:
  # Database maintenance
  - name: "database_vacuum"
    schedule: "0 2 * * *"  # Daily at 2 AM (cron format)
    enabled: true
    task: "system.database.vacuum"
  
  # Log rotation
  - name: "rotate_logs"
    schedule: "0 0 * * 0"  # Weekly on Sunday (cron format)
    enabled: true
    task: "system.logs.rotate"
  
  # Backup
  - name: "daily_backup"
    schedule: "0 3 * * *"  # Daily at 3 AM
    enabled: true
    task: "system.backup.full"
    config:
      destination: "/backup/zephyrgate"
      retention_days: 30
  
  # Health check report
  - name: "health_report"
    interval: 3600  # Every hour (interval in seconds)
    enabled: true
    task: "system.health.report"
    config:
      recipients: ["!12345678"]
  
  # Plugin health monitoring
  - name: "plugin_health_check"
    interval: 60  # Every minute
    enabled: true
    task: "plugins.health_check"
```

### Cron Schedule Format

Cron format: `minute hour day month weekday`

```
*     *     *     *     *
│     │     │     │     │
│     │     │     │     └─ Weekday (0-7, 0 and 7 = Sunday)
│     │     │     └─────── Month (1-12)
│     │     └───────────── Day of month (1-31)
│     └─────────────────── Hour (0-23)
└───────────────────────── Minute (0-59)
```

**Common Cron Examples:**

```yaml
# Every minute
schedule: "* * * * *"

# Every hour at minute 0
schedule: "0 * * * *"

# Every day at 2:30 AM
schedule: "30 2 * * *"

# Every Monday at 9 AM
schedule: "0 9 * * 1"

# First day of month at midnight
schedule: "0 0 1 * *"

# Every 15 minutes
schedule: "*/15 * * * *"

# Weekdays at 8 AM
schedule: "0 8 * * 1-5"

# Every 6 hours
schedule: "0 */6 * * *"
```

### Interval-Based Scheduling

For simpler recurring tasks, use interval (in seconds):

```yaml
scheduled_tasks:
  # Every 5 minutes
  - name: "check_weather"
    interval: 300
    task: "weather.check_alerts"
  
  # Every hour
  - name: "sync_bbs"
    interval: 3600
    task: "bbs.sync"
  
  # Every 30 seconds
  - name: "monitor_queue"
    interval: 30
    task: "system.monitor.queue"
```

### Plugin-Specific Scheduled Tasks

Plugins can register their own scheduled tasks:

```yaml
# Email service scheduled task
email:
  check_interval: 300  # Check every 5 minutes
  
# Weather service scheduled task
weather:
  alerts:
    check_interval: 300  # Check every 5 minutes
  
# Asset service scheduled task
asset:
  tracking:
    update_interval: 300  # Update every 5 minutes
  reporting:
    daily_summary: true
    summary_time: "08:00"  # Daily at 8 AM
```

### Task Configuration Options

```yaml
scheduled_tasks:
  - name: "task_name"
    
    # Scheduling (choose one)
    schedule: "0 * * * *"  # Cron format
    interval: 3600         # Interval in seconds
    
    # Task details
    enabled: true
    task: "module.function"  # Task to execute
    
    # Execution options
    timeout: 300  # Max execution time (seconds)
    retry_on_failure: true
    max_retries: 3
    retry_delay: 60  # Seconds between retries
    
    # Concurrency
    allow_concurrent: false  # Allow multiple instances
    
    # Configuration passed to task
    config:
      key: "value"
      recipients: ["!12345678"]
```

### Built-in System Tasks

ZephyrGate includes several built-in tasks:

**Database Tasks:**
- `system.database.vacuum` - Optimize database
- `system.database.backup` - Backup database
- `system.database.cleanup` - Clean old data

**Maintenance Tasks:**
- `system.logs.rotate` - Rotate log files
- `system.logs.cleanup` - Delete old logs
- `system.cache.clear` - Clear caches

**Monitoring Tasks:**
- `system.health.check` - Check system health
- `system.health.report` - Generate health report
- `plugins.health_check` - Check plugin health

**Backup Tasks:**
- `system.backup.full` - Full system backup
- `system.backup.database` - Database backup only
- `system.backup.config` - Configuration backup

### Managing Scheduled Tasks

#### Via Web Interface

1. Navigate to **Admin Panel → Scheduled Tasks**
2. View all scheduled tasks with next run time
3. Enable/disable tasks
4. Trigger manual execution
5. View task history and logs

#### Via Command Line

```bash
# List all scheduled tasks
python src/main.py --list-tasks

# Run task manually
python src/main.py --run-task database_vacuum

# Enable/disable task
python src/main.py --enable-task daily_backup
python src/main.py --disable-task health_report

# View task history
python src/main.py --task-history database_vacuum
```

#### Via API

```bash
# List tasks
curl http://localhost:8080/api/tasks

# Run task
curl -X POST http://localhost:8080/api/tasks/database_vacuum/run

# Get task status
curl http://localhost:8080/api/tasks/database_vacuum/status
```

### Task Monitoring

Monitor scheduled task execution:

```yaml
# Enable task monitoring
monitoring:
  tasks:
    enabled: true
    log_execution: true
    alert_on_failure: true
    alert_recipients: ["!12345678"]
    
    # Performance tracking
    track_duration: true
    slow_task_threshold: 300  # Warn if task takes > 5 minutes
```

**View Task Logs:**

```bash
# View task execution logs
grep "scheduled_task" logs/zephyrgate.log

# View specific task
grep "database_vacuum" logs/zephyrgate.log

# View failed tasks
grep "scheduled_task.*FAILED" logs/zephyrgate.log
```

### Example: Custom Scheduled Task

Create a custom scheduled task in a plugin:

```python
# In your plugin
class MyPlugin(EnhancedPlugin):
    async def initialize(self):
        # Register hourly task
        self.register_scheduled_task(
            interval=3600,  # Every hour
            handler=self.hourly_update,
            name="hourly_update"
        )
        
        # Register daily task with cron
        self.register_scheduled_task(
            cron="0 8 * * *",  # Daily at 8 AM
            handler=self.daily_report,
            name="daily_report"
        )
        
        return True
    
    async def hourly_update(self):
        """Run every hour"""
        self.logger.info("Running hourly update")
        # Your task logic here
    
    async def daily_report(self):
        """Run daily at 8 AM"""
        self.logger.info("Generating daily report")
        # Your task logic here
```


## Service Management

### Managing Services

#### Via Systemd (if installed as service)

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

# Disable auto-start
sudo systemctl disable zephyrgate

# View logs
sudo journalctl -u zephyrgate -f
```

#### Via Scripts

```bash
# Start ZephyrGate
./start.sh

# Stop ZephyrGate
./stop.sh

# Restart
./stop.sh && ./start.sh
```

#### Via Web Interface

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

## User Management

### User Database

Users are automatically registered when they send messages. Manage users via web interface or command line.

### Via Web Interface

1. Navigate to **Admin Panel → Users**
2. View all registered users
3. Edit user profiles and permissions
4. Manage subscriptions
5. View user activity

### Via Command Line

```bash
# List all users
python src/main.py --list-users

# View user details
python src/main.py --user-info "!12345678"

# Update user
python src/main.py --update-user "!12345678" --name "John Doe" --email "john@example.com"

# Set user permissions
python src/main.py --set-permissions "!12345678" --permissions "admin,responder"

# Delete user
python src/main.py --delete-user "!12345678"
```

### User Permissions

```yaml
# Define permission groups
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


## Security Configuration

### Web Interface Security

```yaml
web:
  auth:
    enabled: true
    session_timeout: 3600
    require_auth: true
    
  security:
    max_login_attempts: 5
    lockout_duration: 900
    csrf_protection: true
    secure_cookies: true
    
    # Password policy
    password_policy:
      min_length: 8
      require_uppercase: true
      require_lowercase: true
      require_numbers: true
      require_special: true
```

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

Generate self-signed certificate:

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

## Monitoring and Maintenance

### System Monitoring

```yaml
monitoring:
  enabled: true
  
  metrics:
    - system_resources
    - service_health
    - message_throughput
    - error_rates
    - plugin_health
  
  alerts:
    email: "admin@example.com"
    thresholds:
      cpu_usage: 80
      memory_usage: 85
      disk_usage: 90
      error_rate: 5
```

### Log Management

```yaml
logging:
  level: "INFO"
  console: true
  file: "logs/zephyrgate.log"
  max_file_size: 10485760  # 10MB
  backup_count: 5
  
  # Log rotation
  rotation:
    when: "midnight"
    interval: 1
    backup_count: 7
```

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

### Performance Monitoring

Monitor key metrics:

```bash
# System resources
curl http://localhost:8080/api/system/resources

# Message throughput
curl http://localhost:8080/api/metrics/messages

# Plugin performance
curl http://localhost:8080/api/plugins/metrics
```


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
    
    # Optional: Cloud storage
    s3:
      enabled: false
      bucket: "zephyrgate-backups"
      region: "us-west-2"
      access_key: "your-access-key"
      secret_key: "your-secret-key"
```

### Manual Backup

```bash
# Full backup
tar -czf zephyrgate-backup-$(date +%Y%m%d).tar.gz \
  data/ config/ logs/

# Database only
cp data/zephyrgate.db backups/zephyrgate-$(date +%Y%m%d).db

# Configuration only
tar -czf config-backup-$(date +%Y%m%d).tar.gz config/
```

### Restore from Backup

```bash
# Stop ZephyrGate
./stop.sh

# Restore database
cp backups/zephyrgate-20240101.db data/zephyrgate.db

# Restore configuration
tar -xzf config-backup-20240101.tar.gz

# Start ZephyrGate
./start.sh
```

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check configuration
python src/main.py --config-test

# Check logs
tail -f logs/zephyrgate.log

# Check permissions
ls -la data/
chmod 755 data/
```

#### Database Issues

```bash
# Check database integrity
sqlite3 data/zephyrgate.db "PRAGMA integrity_check;"

# Backup and repair
cp data/zephyrgate.db data/zephyrgate.db.backup
sqlite3 data/zephyrgate.db ".recover" | sqlite3 data/zephyrgate_new.db
```

#### Meshtastic Connection Issues

```bash
# Check serial port
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Test connection
python -c "import serial; s=serial.Serial('/dev/ttyUSB0', 921600); print('OK')"

# Check permissions
sudo usermod -a -G dialout $USER
# Log out and back in
```

#### Plugin Issues

```bash
# List plugins
python src/main.py --list-plugins

# Check plugin health
curl http://localhost:8080/api/plugins/health

# View plugin logs
grep "plugin_name" logs/zephyrgate.log

# Disable problematic plugin
# Edit config/config.yaml and add to disabled_plugins
```

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

## Performance Tuning

### Database Optimization

```yaml
database:
  # Connection pooling
  max_connections: 20
  
  # Performance settings
  wal_mode: true
  auto_vacuum: true
  cache_size: 10000
  
  # Maintenance
  vacuum_interval: 86400  # Daily
```

### Memory Management

```yaml
app:
  # Memory limits
  max_memory_mb: 1024
  
  # Cache settings
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

## Integration Setup

### Weather API Keys

**NOAA (US):**
- No API key required
- Free for non-commercial use
- Rate limited

**Open-Meteo:**
- No API key required
- Free for non-commercial use
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

## Additional Resources

- [Installation Guide](INSTALLATION.md) - Detailed installation instructions
- [User Manual](USER_MANUAL.md) - End-user documentation
- [Plugin Development](PLUGIN_DEVELOPMENT.md) - Create custom plugins
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Detailed troubleshooting
- [API Reference](API_REFERENCE.md) - REST API documentation

## Support

For additional help:
- Check documentation in `docs/` directory
- Review logs: `tail -f logs/zephyrgate.log`
- Search GitHub Issues
- Join community chat

---

**Last Updated:** January 2026  
**Version:** 2.0 with Plugin System
