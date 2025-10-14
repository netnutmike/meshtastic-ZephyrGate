# Docker Compose Configuration Guide for ZephyrGate

This guide explains how to use YAML configuration files when running ZephyrGate with Docker Compose.

## Configuration File Location

**Yes, you can absolutely use YAML config files with Docker Compose!** Here's where to put them:

### Default Location
Place your configuration files in the **`./config`** directory (relative to your docker-compose.yml file):

```
your-project/
├── docker-compose.yml
├── config/                    ← Put your YAML configs here
│   ├── config.yaml           ← Main configuration file
│   ├── production.yaml       ← Environment-specific config
│   ├── local.yaml           ← Local overrides
│   └── default.yaml         ← Default settings
├── data/                     ← Database and app data
├── logs/                     ← Log files
└── ...
```

### Volume Mounting
The Docker Compose file mounts the config directory as:
```yaml
volumes:
  - zephyr_config:/app/config
```

Where `zephyr_config` is defined as:
```yaml
zephyr_config:
  driver: local
  driver_opts:
    type: none
    o: bind
    device: ${CONFIG_DIR:-./config}  # Defaults to ./config
```

## Configuration Options

### 1. **Use Default Location** (Recommended)
```bash
# Create config directory
mkdir -p config

# Copy template and customize
cp config/config.template.yaml config/config.yaml
# Edit config/config.yaml with your settings

# Start with Docker Compose
docker-compose up -d
```

### 2. **Custom Config Directory**
You can specify a different config directory using environment variables:

```bash
# Set custom config directory
export CONFIG_DIR=/path/to/your/config

# Or use .env file
echo "CONFIG_DIR=/path/to/your/config" >> .env

# Start services
docker-compose up -d
```

### 3. **Environment-Specific Configs**
ZephyrGate supports hierarchical configuration loading:

```bash
config/
├── default.yaml      # Base configuration
├── production.yaml   # Production overrides
├── development.yaml  # Development overrides
└── local.yaml       # Local user overrides (highest priority)
```

## Step-by-Step Setup

### 1. **Create Your Configuration**
```bash
# Create the config directory
mkdir -p config

# Copy the template
cp config/config.template.yaml config/config.yaml

# Edit your configuration
nano config/config.yaml  # or use your preferred editor
```

### 2. **Key Configuration Areas**

**Meshtastic Interface:**
```yaml
meshtastic:
  interfaces:
    - type: "serial"
      port: "/dev/ttyUSB0"  # This will be available inside the container
      baud_rate: 921600
      name: "Primary Radio"
```

**Services to Enable:**
```yaml
services:
  emergency:
    enabled: true
    responders: ["!12345678"]  # Add your responder node IDs
  
  weather:
    enabled: true
    default_location:
      latitude: 40.7128    # Set your location
      longitude: -74.0060
  
  web:
    enabled: true
    auth:
      default_password: "YourSecurePassword"  # Change this!
```

### 3. **Start with Docker Compose**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f zephyrgate

# Check status
docker-compose ps
```

## Sample Configuration File

Here's a complete example `config/config.yaml` for Docker Compose deployment:

```yaml
# ZephyrGate Docker Compose Configuration

app:
  name: "ZephyrGate"
  debug: false
  log_level: "INFO"

# Configure your Meshtastic interfaces
meshtastic:
  interfaces:
    # Serial interface (most common)
    - type: "serial"
      port: "/dev/ttyUSB0"  # Adjust for your system
      baud_rate: 921600
      name: "Primary Radio"
    
    # TCP interface example (for WiFi-enabled devices)
    # - type: "tcp"
    #   host: "192.168.1.100"
    #   port: 4403
    #   name: "WiFi Radio"

# Database location (inside container)
database:
  path: "data/zephyrgate.db"

# Enable/disable services as needed
services:
  bbs:
    enabled: true
  
  emergency:
    enabled: true
    responders: ["!12345678", "!87654321"]  # Add your responder node IDs
    escalation_timeout: 1800  # 30 minutes
  
  bot:
    enabled: true
    auto_response: true
    new_node_greeting: true
  
  weather:
    enabled: true
    default_location:
      latitude: 40.7128   # Set your coordinates
      longitude: -74.0060
    alerts:
      fema_ipaws: true
      noaa_weather: true
      usgs_earthquake: true
  
  # Email gateway (optional - requires email server setup)
  email:
    enabled: false
    smtp:
      host: "smtp.gmail.com"
      port: 587
      username: "your-email@gmail.com"
      password: "your-app-password"
  
  web:
    enabled: true
    port: 8080
    auth:
      default_username: "admin"
      default_password: "CHANGE_THIS_PASSWORD"  # IMPORTANT: Change this!

# Security settings
security:
  trusted_nodes: []
  admin_nodes: ["!12345678"]  # Add admin node IDs
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60

# Logging
logging:
  level: "INFO"
  file: "logs/zephyrgate.log"
  console: true
```

## Environment Variable Override

You can also override config values using environment variables in your `.env` file:

```bash
# .env file
ZEPHYR_LOG_LEVEL=DEBUG
ZEPHYR_WEB_PORT=8080
ZEPHYR_DEBUG=true
CONFIG_DIR=./config
DATA_DIR=./data
LOG_DIR=./logs
```

## Configuration Hierarchy

ZephyrGate loads configuration in this order (later files override earlier ones):

1. `config/default.yaml` (built-in defaults)
2. `config/production.yaml` (environment-specific)
3. `config/local.yaml` (local overrides)
4. Environment variables (`ZEPHYR_*`)

## Production Example

For production deployment, create a `config/production.yaml`:

```yaml
app:
  debug: false
  log_level: "WARNING"

security:
  rate_limiting:
    enabled: true
    max_requests_per_minute: 30

services:
  web:
    auth:
      default_password: "VerySecureProductionPassword"

logging:
  level: "WARNING"
  console: false  # Only log to file in production
```

## Docker Compose Commands

```bash
# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f zephyrgate

# Stop services
docker-compose down

# Restart a specific service
docker-compose restart zephyrgate

# Update and restart
docker-compose pull && docker-compose up -d

# View service status
docker-compose ps

# Execute commands in container
docker-compose exec zephyrgate bash
```

## Troubleshooting

### Configuration Not Loading
- Ensure config files are in the `./config` directory
- Check file permissions (should be readable)
- Verify YAML syntax with `yamllint config/config.yaml`

### Device Access Issues
- Ensure your Meshtastic device is connected to `/dev/ttyUSB0` (or adjust path)
- Check that the device is accessible: `ls -la /dev/ttyUSB*`
- Verify the device path in your config matches the actual device

### Permission Issues
- Ensure the config directory is readable: `chmod -R 755 config/`
- Check that data and logs directories are writable: `chmod -R 755 data/ logs/`

### Web Interface Not Accessible
- Verify the port mapping in docker-compose.yml matches your config
- Check firewall settings
- Ensure the web service is enabled in your config

## Security Notes

1. **Change Default Passwords**: Always change the default web interface password
2. **Limit Admin Access**: Only add trusted node IDs to `admin_nodes`
3. **Use HTTPS**: In production, use the nginx proxy with SSL certificates
4. **Regular Updates**: Keep Docker images updated with `docker-compose pull`

The configuration files will be automatically loaded by the application when it starts in the Docker container!