# ZephyrGate Administrator Guide

## Table of Contents

1. [Installation and Deployment](#installation-and-deployment)
2. [Configuration Management](#configuration-management)
3. [Service Management](#service-management)
4. [User Management](#user-management)
5. [Security Configuration](#security-configuration)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Backup and Recovery](#backup-and-recovery)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)
10. [Integration Setup](#integration-setup)

## Installation and Deployment

### Docker Deployment (Recommended)

#### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum, 4GB recommended
- 10GB disk space minimum
- Linux, macOS, or Windows with WSL2

#### Quick Start with Docker Compose

1. **Clone or Download Configuration**:
   ```bash
   mkdir zephyrgate
   cd zephyrgate
   wget https://raw.githubusercontent.com/your-repo/zephyrgate/main/docker-compose.yml
   ```

2. **Create Environment File**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start Services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify Installation**:
   ```bash
   docker-compose logs -f zephyrgate
   ```

#### Production Docker Deployment

1. **Create Production Configuration**:
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

2. **Configure Reverse Proxy** (nginx example):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

### Manual Installation

#### System Requirements
- Python 3.9+
- SQLite 3.35+
- Redis (optional, for caching)
- 2GB RAM minimum
- 10GB disk space

#### Installation Steps

1. **Install Dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip python3-venv sqlite3 git
   
   # CentOS/RHEL
   sudo yum install python3 python3-pip sqlite git
   
   # macOS
   brew install python sqlite
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
   sudo -u zephyrgate python3 -m venv venv
   sudo -u zephyrgate ./venv/bin/pip install -r requirements.txt
   ```

4. **Create Configuration**:
   ```bash
   sudo -u zephyrgate cp config/config.template.yaml config/config.yaml
   # Edit configuration as needed
   ```

5. **Create Systemd Service**:
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
   ExecStart=/opt/zephyrgate/venv/bin/python src/main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

6. **Enable and Start Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable zephyrgate
   sudo systemctl start zephyrgate
   ```

## Configuration Management

### Configuration File Structure

ZephyrGate uses YAML configuration files with the following hierarchy:

1. **Default Configuration**: `config/default.yaml`
2. **Environment Configuration**: `config/{environment}.yaml`
3. **Local Configuration**: `config/local.yaml`
4. **Environment Variables**: Override any configuration value

### Core Configuration Sections

#### Application Settings
```yaml
app:
  name: "ZephyrGate"
  version: "1.0.0"
  environment: "production"
  debug: false
  log_level: "INFO"
  
server:
  host: "0.0.0.0"
  port: 8080
  workers: 4
```

#### Database Configuration
```yaml
database:
  url: "sqlite:///data/zephyrgate.db"
  pool_size: 10
  max_overflow: 20
  echo: false
  
  # Migration settings
  auto_migrate: true
  backup_before_migrate: true
```

#### Meshtastic Interface Configuration
```yaml
meshtastic:
  interfaces:
    primary:
      type: "serial"
      device: "/dev/ttyUSB0"
      baudrate: 921600
      
    secondary:
      type: "tcp"
      host: "192.168.1.100"
      port: 4403
      
    bluetooth:
      type: "ble"
      address: "AA:BB:CC:DD:EE:FF"
      
  # Global settings
  message_timeout: 30
  retry_attempts: 3
  rate_limit: 10  # messages per minute
```

#### Service Module Configuration
```yaml
services:
  emergency:
    enabled: true
    escalation_timeout: 300  # 5 minutes
    check_in_interval: 600   # 10 minutes
    
  bbs:
    enabled: true
    sync_interval: 3600      # 1 hour
    max_message_size: 1000
    
  weather:
    enabled: true
    update_interval: 1800    # 30 minutes
    providers:
      - noaa
      - openmeteo
      
  email:
    enabled: true
    smtp:
      host: "smtp.gmail.com"
      port: 587
      username: "your-email@gmail.com"
      password: "your-app-password"
    imap:
      host: "imap.gmail.com"
      port: 993
      username: "your-email@gmail.com"
      password: "your-app-password"
```

### Environment Variables

All configuration values can be overridden with environment variables using the format:
`ZEPHYR_{SECTION}_{SUBSECTION}_{KEY}`

Examples:
```bash
export ZEPHYR_APP_LOG_LEVEL=DEBUG
export ZEPHYR_DATABASE_URL=postgresql://user:pass@localhost/zephyr
export ZEPHYR_MESHTASTIC_INTERFACES_PRIMARY_DEVICE=/dev/ttyACM0
```

### Configuration Validation

ZephyrGate validates configuration on startup:

```bash
# Test configuration
python src/main.py --config-test

# Validate specific configuration file
python src/main.py --config config/production.yaml --config-test
```

## Service Management

### Service Architecture

ZephyrGate uses a modular service architecture where each major feature is implemented as a separate service module:

- **Core Services**: Message Router, Configuration Manager, Database Manager
- **Feature Services**: Emergency, BBS, Weather, Email, Bot, Web Admin
- **Support Services**: Logging, Health Monitor, Plugin Manager

### Managing Services

#### Via Web Interface

1. **Access Admin Panel**: Navigate to `http://your-server:8080/admin`
2. **Service Management**: Go to System → Services
3. **Control Services**: Start, stop, restart, or configure individual services

#### Via Command Line

```bash
# Check service status
python src/main.py --status

# Start specific service
python src/main.py --start-service emergency

# Stop specific service
python src/main.py --stop-service weather

# Restart service
python src/main.py --restart-service bbs

# Reload configuration
python src/main.py --reload-config
```

#### Via API

```bash
# Get service status
curl http://localhost:8080/api/services/status

# Start service
curl -X POST http://localhost:8080/api/services/emergency/start

# Stop service
curl -X POST http://localhost:8080/api/services/weather/stop
```

### Service Configuration

Each service can be individually configured:

```yaml
services:
  emergency:
    enabled: true
    config:
      escalation_timeout: 300
      responder_groups: ["SAR", "FIRE", "POLICE"]
      auto_clear_timeout: 3600
      
  bbs:
    enabled: true
    config:
      max_bulletins: 1000
      bulletin_retention_days: 30
      sync_peers:
        - "192.168.1.101:4404"
        - "192.168.1.102:4404"
```

### Health Monitoring

ZephyrGate includes comprehensive health monitoring:

```bash
# Check overall health
curl http://localhost:8080/health

# Detailed health check
curl http://localhost:8080/health/detailed

# Service-specific health
curl http://localhost:8080/health/services/emergency
```

Health check endpoints return:
- **200 OK**: Service healthy
- **503 Service Unavailable**: Service unhealthy
- **404 Not Found**: Service not found/disabled

## User Management

### User Database Schema

Users are stored in the SQLite database with the following structure:

```sql
CREATE TABLE users (
    node_id TEXT PRIMARY KEY,
    short_name TEXT NOT NULL,
    long_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    tags TEXT,           -- JSON array
    permissions TEXT,    -- JSON object
    subscriptions TEXT,  -- JSON object
    last_seen DATETIME,
    location_lat REAL,
    location_lon REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Managing Users via Web Interface

1. **Access User Management**: Admin Panel → Users
2. **View Users**: Browse all registered users
3. **Edit User**: Click on user to edit profile, permissions, subscriptions
4. **Bulk Operations**: Select multiple users for bulk actions

### Managing Users via Command Line

```bash
# List all users
python src/main.py --list-users

# Add user
python src/main.py --add-user --node-id "!12345678" --name "John Doe"

# Update user permissions
python src/main.py --update-user --node-id "!12345678" --permissions '{"admin": true}'

# Delete user
python src/main.py --delete-user --node-id "!12345678"
```

### User Permissions System

ZephyrGate uses a role-based permission system:

#### Default Roles

```yaml
roles:
  admin:
    permissions:
      - "admin.*"
      - "emergency.manage"
      - "bbs.moderate"
      - "email.broadcast"
      
  responder:
    permissions:
      - "emergency.respond"
      - "emergency.view"
      - "bbs.post"
      
  user:
    permissions:
      - "bbs.read"
      - "bbs.post"
      - "weather.view"
      - "bot.interact"
```

#### Custom Permissions

```yaml
# Individual user permissions
user_permissions:
  "!12345678":
    permissions:
      - "emergency.respond"
      - "bbs.moderate"
      - "email.send"
    tags:
      - "SAR"
      - "ADMIN"
```

### Subscription Management

Users can subscribe to various services:

```yaml
subscriptions:
  weather: true
  alerts: true
  forecasts: false
  emergency_notifications: true
  bbs_notifications: false
```

## Security Configuration

### Authentication and Authorization

#### Web Interface Security

```yaml
security:
  web:
    session_timeout: 3600  # 1 hour
    max_login_attempts: 5
    lockout_duration: 900   # 15 minutes
    
    # Password requirements
    password_policy:
      min_length: 8
      require_uppercase: true
      require_lowercase: true
      require_numbers: true
      require_special: true
```

#### API Security

```yaml
api:
  authentication:
    type: "jwt"
    secret_key: "your-secret-key"
    token_expiry: 3600
    
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
```

### Network Security

#### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 8080/tcp  # Web interface
sudo ufw allow 4403/tcp  # Meshtastic TCP (if used)
sudo ufw deny 22/tcp     # Disable SSH if not needed
```

#### SSL/TLS Configuration

```yaml
server:
  ssl:
    enabled: true
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"
    ca_file: "/path/to/ca.pem"
```

### Data Security

#### Database Encryption

```yaml
database:
  encryption:
    enabled: true
    key_file: "/secure/path/to/db.key"
    algorithm: "AES-256-GCM"
```

#### Backup Encryption

```yaml
backup:
  encryption:
    enabled: true
    gpg_recipient: "admin@yourorg.com"
    compression: true
```

## Monitoring and Maintenance

### System Monitoring

#### Built-in Monitoring

ZephyrGate includes comprehensive monitoring:

```yaml
monitoring:
  enabled: true
  metrics:
    - system_resources
    - service_health
    - message_throughput
    - error_rates
    
  alerts:
    email: "admin@yourorg.com"
    thresholds:
      cpu_usage: 80
      memory_usage: 85
      disk_usage: 90
      error_rate: 5
```

#### External Monitoring Integration

```yaml
# Prometheus integration
prometheus:
  enabled: true
  port: 9090
  path: "/metrics"
  
# Grafana dashboard
grafana:
  dashboard_url: "http://grafana:3000"
  api_key: "your-api-key"
```

### Log Management

#### Log Configuration

```yaml
logging:
  level: "INFO"
  format: "json"
  
  handlers:
    file:
      enabled: true
      path: "/app/logs/zephyrgate.log"
      max_size: "100MB"
      backup_count: 5
      
    syslog:
      enabled: true
      facility: "local0"
      
    elasticsearch:
      enabled: false
      hosts: ["elasticsearch:9200"]
      index: "zephyrgate-logs"
```

#### Log Analysis

```bash
# View recent logs
tail -f /app/logs/zephyrgate.log

# Search for errors
grep "ERROR" /app/logs/zephyrgate.log

# Analyze message patterns
grep "message_received" /app/logs/zephyrgate.log | wc -l
```

### Performance Monitoring

#### Key Metrics to Monitor

1. **Message Throughput**: Messages per minute/hour
2. **Response Times**: Command response latency
3. **Error Rates**: Failed commands/messages
4. **Resource Usage**: CPU, memory, disk usage
5. **Service Health**: Individual service status

#### Performance Dashboards

Create monitoring dashboards for:
- System overview
- Service-specific metrics
- Network performance
- User activity
- Error tracking

### Maintenance Tasks

#### Daily Tasks
- Check system health
- Review error logs
- Monitor resource usage
- Verify backup completion

#### Weekly Tasks
- Analyze performance trends
- Review user activity
- Update security patches
- Clean old log files

#### Monthly Tasks
- Full system backup
- Performance optimization
- Security audit
- Configuration review

## Backup and Recovery

### Automated Backup System

#### Backup Configuration

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  
  targets:
    database:
      enabled: true
      retention_days: 30
      
    configuration:
      enabled: true
      retention_days: 90
      
    logs:
      enabled: true
      retention_days: 7
      
  storage:
    local:
      path: "/backup/zephyrgate"
      
    s3:
      enabled: false
      bucket: "zephyrgate-backups"
      region: "us-west-2"
```

#### Manual Backup

```bash
# Full system backup
python src/main.py --backup --type full --output /backup/full-$(date +%Y%m%d).tar.gz

# Database only
python src/main.py --backup --type database --output /backup/db-$(date +%Y%m%d).sql

# Configuration only
python src/main.py --backup --type config --output /backup/config-$(date +%Y%m%d).tar.gz
```

### Disaster Recovery

#### Recovery Procedures

1. **Complete System Recovery**:
   ```bash
   # Stop services
   sudo systemctl stop zephyrgate
   
   # Restore from backup
   tar -xzf /backup/full-20231201.tar.gz -C /
   
   # Restore database
   sqlite3 /app/data/zephyrgate.db < /backup/db-20231201.sql
   
   # Start services
   sudo systemctl start zephyrgate
   ```

2. **Database Recovery**:
   ```bash
   # Backup current database
   cp /app/data/zephyrgate.db /app/data/zephyrgate.db.backup
   
   # Restore from backup
   sqlite3 /app/data/zephyrgate.db < /backup/db-20231201.sql
   
   # Restart application
   sudo systemctl restart zephyrgate
   ```

3. **Configuration Recovery**:
   ```bash
   # Backup current config
   cp -r /app/config /app/config.backup
   
   # Restore configuration
   tar -xzf /backup/config-20231201.tar.gz -C /app/
   
   # Reload configuration
   python src/main.py --reload-config
   ```

#### Recovery Testing

Regularly test recovery procedures:

```bash
# Test database restore
python src/main.py --test-restore --backup /backup/db-latest.sql

# Validate configuration
python src/main.py --config-test --config /backup/config/config.yaml

# Test full system restore in staging environment
```

## Troubleshooting

### Common Issues and Solutions

#### Service Won't Start

1. **Check Configuration**:
   ```bash
   python src/main.py --config-test
   ```

2. **Check Permissions**:
   ```bash
   ls -la /app/data/
   chown -R zephyrgate:zephyrgate /app/data/
   ```

3. **Check Dependencies**:
   ```bash
   pip check
   pip install -r requirements.txt
   ```

#### Database Issues

1. **Database Corruption**:
   ```bash
   # Check database integrity
   sqlite3 /app/data/zephyrgate.db "PRAGMA integrity_check;"
   
   # Repair if needed
   sqlite3 /app/data/zephyrgate.db ".recover" | sqlite3 /app/data/zephyrgate_recovered.db
   ```

2. **Migration Failures**:
   ```bash
   # Check migration status
   python src/main.py --migration-status
   
   # Force migration
   python src/main.py --migrate --force
   ```

#### Network Connectivity Issues

1. **Meshtastic Connection**:
   ```bash
   # Test serial connection
   python -c "import serial; s=serial.Serial('/dev/ttyUSB0', 921600); print('OK')"
   
   # Test TCP connection
   telnet 192.168.1.100 4403
   ```

2. **Internet Services**:
   ```bash
   # Test weather API
   curl "https://api.weather.gov/points/40.7128,-74.0060"
   
   # Test email connectivity
   telnet smtp.gmail.com 587
   ```

### Diagnostic Tools

#### Built-in Diagnostics

```bash
# System health check
python src/main.py --health-check

# Network diagnostics
python src/main.py --network-test

# Service diagnostics
python src/main.py --service-test --service emergency

# Performance test
python src/main.py --performance-test
```

#### Log Analysis Tools

```bash
# Error analysis
grep -E "(ERROR|CRITICAL)" /app/logs/zephyrgate.log | tail -20

# Performance analysis
grep "response_time" /app/logs/zephyrgate.log | awk '{print $NF}' | sort -n

# Message flow analysis
grep "message_" /app/logs/zephyrgate.log | grep "$(date +%Y-%m-%d)"
```

## Performance Tuning

### Database Optimization

```yaml
database:
  # Connection pooling
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  
  # Query optimization
  query_cache_size: 1000
  statement_timeout: 30
  
  # Maintenance
  auto_vacuum: "incremental"
  cache_size: 10000
```

### Memory Management

```yaml
app:
  # Memory limits
  max_memory_mb: 1024
  
  # Cache settings
  cache:
    type: "redis"
    url: "redis://localhost:6379/0"
    max_memory: "256mb"
    
  # Message queue
  queue:
    max_size: 10000
    batch_size: 100
```

### Network Optimization

```yaml
meshtastic:
  # Connection optimization
  connection_pool_size: 5
  connection_timeout: 10
  read_timeout: 30
  
  # Message optimization
  message_compression: true
  batch_messages: true
  max_batch_size: 10
```

## Integration Setup

### Weather Service Integration

#### NOAA Configuration

```yaml
weather:
  noaa:
    enabled: true
    api_key: "your-api-key"  # Optional
    base_url: "https://api.weather.gov"
    timeout: 30
    cache_duration: 1800
```

#### Open-Meteo Configuration

```yaml
weather:
  openmeteo:
    enabled: true
    base_url: "https://api.open-meteo.com/v1"
    timeout: 30
    cache_duration: 1800
```

### Email Integration

#### Gmail Configuration

```yaml
email:
  smtp:
    host: "smtp.gmail.com"
    port: 587
    security: "starttls"
    username: "your-email@gmail.com"
    password: "your-app-password"  # Use app-specific password
    
  imap:
    host: "imap.gmail.com"
    port: 993
    security: "ssl"
    username: "your-email@gmail.com"
    password: "your-app-password"
```

#### Office 365 Configuration

```yaml
email:
  smtp:
    host: "smtp.office365.com"
    port: 587
    security: "starttls"
    username: "your-email@yourorg.com"
    password: "your-password"
    
  imap:
    host: "outlook.office365.com"
    port: 993
    security: "ssl"
    username: "your-email@yourorg.com"
    password: "your-password"
```

### AI Service Integration

#### Local LLM (Ollama)

```yaml
ai:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    model: "llama2"
    timeout: 30
    max_tokens: 500
```

#### OpenAI API

```yaml
ai:
  openai:
    enabled: true
    api_key: "your-api-key"
    model: "gpt-3.5-turbo"
    max_tokens: 500
    temperature: 0.7
```

### JS8Call Integration

```yaml
js8call:
  enabled: true
  host: "localhost"
  port: 2442
  groups: ["MESH", "EMCOMM", "ARES"]
  urgent_keywords: ["URGENT", "EMERGENCY", "SOS"]
```

This administrator guide provides comprehensive information for deploying, configuring, and maintaining ZephyrGate. Regular review and updates of these procedures will ensure optimal system performance and reliability.