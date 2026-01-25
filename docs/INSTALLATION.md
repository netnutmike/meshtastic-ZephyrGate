# ZephyrGate Installation Guide

This guide will walk you through installing ZephyrGate on your system. Choose between Docker (easiest) or manual installation.

## Table of Contents

- [Installation Methods](#installation-methods)
- [Docker Installation (Recommended)](#docker-installation-recommended)
- [Manual Installation](#manual-installation)
- [System Requirements](#system-requirements)
- [Configuration](#configuration)
- [Starting ZephyrGate](#starting-zephyrgate)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Installation Methods

ZephyrGate can be installed in two ways:

### 🐳 Docker (Recommended - Easiest)

**Best for:**
- Quick deployment
- Easy updates
- Consistent environment
- All platforms (Linux, macOS, Windows)

**Pros:**
- One command installation
- No dependency management
- Easy backup and migration
- Isolated from host system

**Cons:**
- Requires Docker installed
- Slightly more resource usage

[Jump to Docker Installation](#docker-installation-recommended)

### 📦 Manual Installation

**Best for:**
- Development
- Custom modifications
- Systems without Docker
- Maximum performance

**Pros:**
- Direct access to code
- Lower resource usage
- More control

**Cons:**
- More setup steps
- Manual dependency management
- Platform-specific issues

[Jump to Manual Installation](#manual-installation)

---

## Docker Installation (Recommended)

### Prerequisites

Install Docker on your system:

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Logout and login again
```

**Raspberry Pi:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker pi
# Logout and login again
```

**macOS:**
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)

**Windows:**
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Enable WSL 2 backend

### Method 1: Docker Run (Simplest)

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

### Method 2: Docker Compose (Recommended)

**Step 1: Create project directory**
```bash
mkdir zephyrgate && cd zephyrgate
```

**Step 2: Create docker-compose.yml**
```bash
cat > docker-compose.yml << 'EOF'
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
      - /dev/ttyUSB0:/dev/ttyUSB0  # Adjust for your device
    
    environment:
      - TZ=America/New_York  # Change to your timezone
      - ZEPHYR_LOG_LEVEL=INFO
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF
```

**Step 3: Start services**
```bash
docker-compose up -d
```

**Step 4: View logs**
```bash
docker-compose logs -f
```

### Docker Commands

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

# Check status
docker-compose ps
```

### Docker Configuration

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `UTC` | Timezone (e.g., America/New_York) |
| `ZEPHYR_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `ZEPHYR_WEB_PORT` | `8080` | Web interface port |
| `ZEPHYR_DEBUG` | `false` | Enable debug mode |

**Custom Configuration:**

Create `config/config.yaml` and mount it:

```yaml
# docker-compose.yml
volumes:
  - ./config/config.yaml:/app/config/config.yaml:ro
```

**For detailed Docker documentation, see [Docker Deployment Guide](DOCKER_DEPLOYMENT.md)**

---

## Manual Installation

## System Requirements

### Hardware
- **Raspberry Pi** (3, 4, or 5) - Recommended
- **Any Linux-based system** (x86_64, ARM)
- **Minimum**: 512MB RAM, 1GB storage
- **Recommended**: 1GB+ RAM, 4GB+ storage
- **Meshtastic device** connected via USB or network

### Software
- **Operating System**: 
  - Raspberry Pi OS (Raspbian)
  - Ubuntu 20.04+
  - Debian 10+
  - Other Linux distributions
- **Python**: 3.8 or higher
- **Internet connection** (for initial setup)

## Quick Install

The easiest way to install ZephyrGate is using the automated installer:

```bash
# 1. Download or clone ZephyrGate
git clone https://github.com/yourusername/zephyrgate.git
cd zephyrgate

# 2. Run the installer
./install.sh

# 3. Follow the interactive prompts

# 4. Start ZephyrGate
./start.sh
```

That's it! The installer will:
- Check system requirements
- Install missing dependencies
- Set up Python virtual environment
- Configure your Meshtastic connection
- Let you choose which plugins to enable
- Create configuration files
- Optionally set up as a system service

## Detailed Installation Steps

### Step 1: Download ZephyrGate

**Option A: Using Git (Recommended)**
```bash
git clone https://github.com/yourusername/zephyrgate.git
cd zephyrgate
```

**Option B: Download ZIP**
1. Download the ZIP file from GitHub
2. Extract it: `unzip zephyrgate-main.zip`
3. Enter directory: `cd zephyrgate-main`

### Step 2: Run the Installer

Make the installer executable and run it:

```bash
chmod +x install.sh
./install.sh
```

### Step 3: System Requirements Check

The installer will check for required software:
- Python 3.8+
- pip (Python package manager)
- venv (Python virtual environment)
- git (optional)

If anything is missing, the installer will offer to install it for you.

### Step 4: Meshtastic Configuration

You'll be asked how your Meshtastic device connects:

**Serial (USB) Connection:**
- Most common for Raspberry Pi
- Select option 1
- Choose your serial port (usually `/dev/ttyUSB0` or `/dev/ttyACM0`)

**TCP (Network) Connection:**
- For devices connected via WiFi/Ethernet
- Select option 2
- Enter IP address and port (default: localhost:4403)

**Skip Configuration:**
- Select option 3 to configure manually later
- Edit `config/config.yaml` after installation

### Step 5: Plugin Selection

Choose which features you want to enable:

**Recommended Plugins** (pre-selected):
- **bot_service**: Interactive bot with commands and games
- **emergency_service**: SOS and emergency response
- **web_service**: Web-based admin interface

**Optional Plugins**:
- **bbs_service**: Bulletin board and mail system
- **weather_service**: Weather forecasts and alerts
- **email_service**: Email gateway
- **asset_service**: Asset tracking

You can enable/disable plugins later by editing `config/config.yaml`.

### Step 6: System Service (Optional)

The installer will ask if you want ZephyrGate to start automatically on boot.

**Yes**: ZephyrGate runs as a system service
- Starts automatically on boot
- Restarts automatically if it crashes
- Managed with `systemctl` commands

**No**: Manual start/stop
- Run `./start.sh` to start
- Press Ctrl+C to stop

### Step 7: Installation Complete!

The installer will show you next steps and important information.

## Configuration

### Configuration File

The main configuration file is `config/config.yaml`. You can edit it with any text editor:

```bash
nano config/config.yaml
```

### Key Configuration Sections

**Meshtastic Interface:**
```yaml
meshtastic:
  interfaces:
    - id: "primary"
      type: "serial"
      port: "/dev/ttyUSB0"
      baud_rate: 921600
```

**Enabled Plugins:**
```yaml
plugins:
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "web_service"
```

**Web Interface:**
```yaml
web:
  host: "0.0.0.0"
  port: 8080
  auth:
    enabled: true
    default_username: "admin"
    default_password: "admin"
```

**⚠️ Important**: Change the default admin password after first login!

### Finding Your Serial Port

If you're not sure which serial port your Meshtastic device uses:

```bash
# List USB devices
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Or use dmesg to see recent connections
dmesg | grep tty
```

Common ports:
- `/dev/ttyUSB0` - USB serial adapter
- `/dev/ttyACM0` - USB CDC device
- `/dev/ttyAMA0` - Raspberry Pi GPIO serial

## Starting ZephyrGate

### Manual Start

```bash
./start.sh
```

Press `Ctrl+C` to stop.

### System Service

If you installed as a system service:

```bash
# Start
sudo systemctl start zephyrgate

# Stop
sudo systemctl stop zephyrgate

# Restart
sudo systemctl restart zephyrgate

# Check status
sudo systemctl status zephyrgate

# View logs
sudo journalctl -u zephyrgate -f
```

### Accessing the Web Interface

If you enabled the web_service plugin:

1. Open a web browser
2. Go to: `http://localhost:8080` (or your Pi's IP address)
3. Login with:
   - Username: `admin`
   - Password: `admin` (change this!)

## Troubleshooting

### Permission Denied on Serial Port

If you get a permission error accessing the serial port:

```bash
# Add your user to the dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

### Python Version Too Old

If your system has an old Python version:

```bash
# Ubuntu/Debian
sudo apt-get install python3.9

# Or use deadsnakes PPA for newer versions
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11
```

### Virtual Environment Issues

If the virtual environment fails to create:

```bash
# Install venv package
sudo apt-get install python3-venv

# Or try with virtualenv
pip3 install virtualenv
virtualenv .venv
```

### Meshtastic Device Not Found

1. Check USB connection
2. Verify device is powered on
3. Check serial port: `ls -l /dev/tty*`
4. Try different USB port
5. Check dmesg: `dmesg | tail -20`

### Port Already in Use

If port 8080 is already in use:

1. Edit `config/config.yaml`
2. Change `web.port` to a different port (e.g., 8081)
3. Restart ZephyrGate

### Logs

Check logs for detailed error information:

```bash
# Application logs
tail -f logs/zephyrgate.log

# System service logs
sudo journalctl -u zephyrgate -f
```

## Updating ZephyrGate

To update to the latest version:

```bash
# Stop ZephyrGate
./stop.sh  # or: sudo systemctl stop zephyrgate

# Pull latest changes
git pull

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart ZephyrGate
./start.sh  # or: sudo systemctl start zephyrgate
```

## Uninstallation

To completely remove ZephyrGate:

```bash
# Stop and disable service (if installed)
sudo systemctl stop zephyrgate
sudo systemctl disable zephyrgate
sudo rm /etc/systemd/system/zephyrgate.service
sudo systemctl daemon-reload

# Remove ZephyrGate directory
cd ..
rm -rf zephyrgate

# Optional: Remove dependencies
sudo apt-get remove python3-pip python3-venv
```

## Advanced Installation

### Custom Installation Directory

```bash
# Install to a specific directory
git clone https://github.com/yourusername/zephyrgate.git /opt/zephyrgate
cd /opt/zephyrgate
./install.sh
```

### Multiple Instances

You can run multiple ZephyrGate instances with different configurations:

```bash
# Create separate directories
cp -r zephyrgate zephyrgate-instance2
cd zephyrgate-instance2

# Edit config to use different ports and devices
nano config/config.yaml

# Run with different service name
# Edit install.sh to change service name before running
```

### Docker Installation

For Docker users, see [DOCKER.md](DOCKER.md) for containerized deployment.

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs: `tail -f logs/zephyrgate.log`
3. Check [GitHub Issues](https://github.com/yourusername/zephyrgate/issues)
4. Join our community chat
5. Read the [User Manual](USER_MANUAL.md)

## Next Steps

After installation:

1. **Change default password** in web interface
2. **Configure plugins** for your needs
3. **Test Meshtastic connection** - send a test message
4. **Explore features** - try different commands
5. **Read documentation**:
   - [User Manual](USER_MANUAL.md) - How to use ZephyrGate
   - [Admin Guide](ADMIN_GUIDE.md) - System administration
   - [Plugin Development](PLUGIN_DEVELOPMENT.md) - Create custom plugins

## Security Recommendations

1. **Change default passwords** immediately
2. **Use firewall** to restrict web interface access
3. **Keep system updated**: `sudo apt-get update && sudo apt-get upgrade`
4. **Use strong passwords** for web interface
5. **Limit network exposure** - bind web interface to localhost if not needed remotely
6. **Regular backups** of configuration and database

## Performance Tips

### Raspberry Pi Optimization

```bash
# Increase swap space for better performance
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
```

### Log Rotation

Logs are automatically rotated, but you can adjust settings in `config/config.yaml`:

```yaml
logging:
  max_file_size: 10485760  # 10MB
  backup_count: 5  # Keep 5 old log files
```

## Support

- **Documentation**: [docs/](.)
- **Issues**: GitHub Issues
- **Community**: Discord/Matrix
- **Email**: support@zephyrgate.example.com

---

**Happy Meshing!** 📡
