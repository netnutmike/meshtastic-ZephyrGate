# ZephyrGate Configuration Files

This directory contains configuration files for ZephyrGate.

## Files

### config-example.yaml
**Comprehensive example configuration with detailed comments and examples.**

This file includes:
- Complete configuration options for all services
- Detailed comments explaining each setting
- Examples for all plugins
- Quick start instructions
- Tips and best practices
- Links to documentation

**Usage:**
```bash
# For new installations
cp config/config-example.yaml config/config.yaml
# Edit config.yaml with your settings
nano config/config.yaml
```

### config.yaml
**Your active configuration file** (not included in repository)

This is the file ZephyrGate actually uses. Create it by copying `config-example.yaml` and customizing for your installation.

**Minimum required settings:**
1. `meshtastic.interfaces` - Your radio connection
2. `services.weather.default_location` - Your location

### default.yaml
**Default values for all configuration options**

This file provides defaults for any settings not specified in `config.yaml`. You don't need to edit this file - it's used as a fallback.

### auto_response_examples.yaml
**Auto-responder configuration examples**

Comprehensive examples for the auto-responder system. See `docs/AUTO_RESPONDER_GUIDE.md` for complete documentation.

## Quick Start

### 1. Create Your Configuration

```bash
cd config
cp config-example.yaml config.yaml
```

### 2. Edit Minimum Required Settings

Edit `config.yaml` and configure:

**Meshtastic Interface:**
```yaml
meshtastic:
  interfaces:
    - id: "primary"
      type: "serial"
      port: "/dev/ttyUSB0"  # Change to your port
      baud_rate: 921600
```

**Weather Location:**
```yaml
services:
  weather:
    default_location:
      zipcode: "10001"  # Change to your ZIP code
      country: "US"
```

### 3. Start ZephyrGate

```bash
cd ..
python3 src/main.py
```

## Configuration Hierarchy

ZephyrGate uses a layered configuration system:

1. **default.yaml** - Base defaults
2. **config.yaml** - Your customizations (overrides defaults)
3. **Environment variables** - Runtime overrides (optional)

Settings in `config.yaml` override those in `default.yaml`.

## Common Configuration Tasks

### Change Serial Port

```yaml
meshtastic:
  interfaces:
    - type: "serial"
      port: "/dev/ttyUSB0"  # Linux
      # port: "/dev/cu.usbmodem*"  # macOS
      # port: "COM3"  # Windows
```

### Enable/Disable Services

```yaml
services:
  bbs:
    enabled: true  # Enable BBS
  emergency:
    enabled: false  # Disable emergency service
  weather:
    enabled: true  # Enable weather
```

### Configure Weather Location

**Option 1: ZIP Code (US only)**
```yaml
services:
  weather:
    default_location:
      zipcode: "10001"
      country: "US"
```

**Option 2: Coordinates (worldwide)**
```yaml
services:
  weather:
    default_location:
      latitude: 40.7128
      longitude: -74.0060
      name: "New York, NY"
```

**Option 3: City Name (worldwide)**
```yaml
services:
  weather:
    default_location:
      location_name: "New York, New York"
```

### Add Scheduled Broadcast

```yaml
scheduled_broadcasts:
  broadcasts:
    - name: "Morning Greeting"
      message: "Good morning!"
      schedule_type: "cron"
      cron_expression: "0 8 * * *"  # 8 AM daily
      channel: 0
      enabled: true
```

### Configure Auto-Responder

```yaml
services:
  bot:
    auto_response:
      custom_rules:
        - keywords: ['test']
          response: "Test received!"
          priority: 5
          enabled: true
```

### Enable Web Interface

```yaml
services:
  web:
    enabled: true
    port: 8080
    auth:
      default_username: "admin"
      default_password: "changeme"  # CHANGE THIS!
```

### Configure Email Gateway

```yaml
services:
  email:
    enabled: true
    smtp:
      host: "smtp.gmail.com"
      username: "your-email@gmail.com"
      password: "your-app-password"
    imap:
      host: "imap.gmail.com"
      username: "your-email@gmail.com"
      password: "your-app-password"
```

## Configuration Validation

ZephyrGate validates your configuration on startup. Check the logs for any errors:

```bash
tail -f logs/zephyrgate.log
```

Common validation errors:
- Missing required fields
- Invalid values (e.g., negative numbers where positive expected)
- Invalid cron expressions
- Invalid file paths

## Environment-Specific Configurations

You can maintain multiple configuration files for different environments:

```bash
# Development
cp config-example.yaml config-dev.yaml

# Production
cp config-example.yaml config-prod.yaml

# Testing
cp config-example.yaml config-test.yaml
```

Then specify which to use:
```bash
python3 src/main.py --config config-dev.yaml
```

## Security Best Practices

1. **Change default passwords:**
   ```yaml
   services:
     web:
       auth:
         default_password: "use-a-strong-password"
   ```

2. **Restrict admin access:**
   ```yaml
   security:
     admin_nodes: ["!your-node-id"]
   ```

3. **Enable rate limiting:**
   ```yaml
   security:
     rate_limiting:
       enabled: true
   ```

4. **Protect your config file:**
   ```bash
   chmod 600 config/config.yaml
   ```

5. **Don't commit config.yaml to git:**
   - It's already in `.gitignore`
   - Contains sensitive information (passwords, API keys)

## Backup and Restore

### Backup Configuration

```bash
# Backup your config
cp config/config.yaml config/config.yaml.backup

# Or with timestamp
cp config/config.yaml config/config.yaml.$(date +%Y%m%d)
```

### Restore Configuration

```bash
# Restore from backup
cp config/config.yaml.backup config/config.yaml
```

## Troubleshooting

### Configuration Not Loading

1. Check file exists: `ls -l config/config.yaml`
2. Check file permissions: `chmod 644 config/config.yaml`
3. Check YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"`
4. Check logs: `tail -f logs/zephyrgate.log`

### Invalid YAML Syntax

Common YAML mistakes:
- Inconsistent indentation (use spaces, not tabs)
- Missing colons after keys
- Unquoted strings with special characters
- Missing quotes around values with colons

Use a YAML validator:
```bash
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### Service Not Starting

1. Check service is enabled in config
2. Check required dependencies are configured
3. Check logs for specific error messages
4. Verify plugin is in enabled_plugins list (if using explicit list)

## Documentation

- **Complete Guide:** `docs/YAML_CONFIGURATION_GUIDE.md`
- **Quick Start:** `docs/QUICK_START.md`
- **Admin Guide:** `docs/ADMIN_GUIDE.md`
- **Auto-Responder:** `docs/AUTO_RESPONDER_GUIDE.md`
- **Scheduled Broadcasts:** `docs/SCHEDULED_BROADCASTS_GUIDE.md`
- **Weather Service:** `docs/GC_FORECAST_GUIDE.md`

## Support

For help with configuration:
1. Check the documentation in `docs/`
2. Review example configurations in this directory
3. Check logs in `logs/zephyrgate.log`
4. See `docs/TROUBLESHOOTING.md` for common issues

## Version History

- **v1.0.0** - Initial configuration system
- **v1.1.0** - Added plugin system configuration
- **v1.2.0** - Added auto-responder configuration
- **v1.3.0** - Added scheduled broadcasts
- **v1.4.0** - Added GC forecast format
