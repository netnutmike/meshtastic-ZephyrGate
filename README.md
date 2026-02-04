# ZephyrGate - Unified Meshtastic Gateway

<div align="center">

**A comprehensive Meshtastic gateway that unifies emergency response, communication, and information services into a single, powerful platform.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/your-repo/zephyrgate/actions)

[Features](#features) • [Quick Start](#quick-start) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

## Overview

ZephyrGate consolidates the functionality of multiple other meshtastic tools into a single, comprehensive communication platform for Meshtastic mesh networks. It provides emergency response capabilities, bulletin board systems, interactive features, weather services, and email integration—all designed to operate both online and offline with a web-based administration interface.

### Key Benefits

- **🚨 Emergency Ready**: Comprehensive SOS alert system with responder coordination
- **📡 Always Connected**: Multi-interface Meshtastic support (Serial, TCP, BLE)
- **💬 Community Hub**: Full-featured BBS with mail, bulletins, and directory services
- **🤖 Intelligent Bot**: Auto-responses, games, and information lookup services
- **🌤️ Weather Aware**: Multi-source weather data and emergency alerting
- **📧 Email Bridge**: Seamless mesh-to-email communication
- **🔌 Extensible**: Third-party plugin system for custom features
- **🐳 Easy Deploy**: Docker-based deployment with production-ready configurations
- **🔧 Web Admin**: Real-time monitoring and management interface

## Features

### 🚨 Emergency Response System

- **Multiple Alert Types**: SOS, SOSP (Police), SOSF (Fire), SOSM (Medical)
- **Responder Coordination**: Track who's responding to each incident
- **Automatic Escalation**: Unacknowledged alerts escalate to wider audience
- **Check-in System**: Periodic check-ins with SOS users
- **Incident Tracking**: Complete audit trail of emergency responses

### 📋 Bulletin Board System (BBS)

- **Private Mail System**: Send and receive personal messages
- **Public Bulletins**: Community message boards with threading
- **Channel Directory**: Information about available communication channels
- **JS8Call Integration**: Bridge between JS8Call and mesh networks
- **Multi-Node Sync**: Synchronization between multiple BBS nodes
- **Hierarchical Menu System**: Easy navigation through main, BBS, mail, and utilities menus
- **Plugin Menu Integration**: Third-party plugins can add custom menu items
- **Session Management**: Automatic session cleanup and timeout handling

### 🤖 Interactive Bot and Auto-Response

- **Stateless Command System**: All commands work globally without session state for better off-grid reliability
- **Keyword Detection**: Automatic responses to monitored keywords
- **Emergency Keywords**: Special handling for emergency-related terms
- **Interactive Games**: BlackJack, DopeWars, Lemonade Stand, Golf Simulator, and more
- **Educational Features**: Ham radio test questions, quizzes, surveys
- **Information Services**: Weather, Wikipedia search, network statistics
- **AI Integration**: Support for local LLM services with aircraft detection
- **Global Command Access**: Commands work from anywhere without menu navigation

### 🌤️ Weather and Alert Services

- **Multi-Source Data**: NOAA, Open-Meteo, and other weather providers
- **Emergency Alerts**: FEMA iPAWS/EAS, NOAA weather alerts, USGS earthquake data
- **Location-Based**: Geographic filtering for relevant alerts
- **Offline Capable**: Cached data when internet connectivity is lost
- **Environmental Monitoring**: Proximity detection, RF monitoring, sensor integration

### 📧 Email Gateway Integration

- **Bidirectional Bridge**: Send emails from mesh, receive emails on mesh
- **Group Messaging**: Tag-based group communications
- **Broadcast Support**: Network-wide announcements via email
- **Security Features**: Blocklists, sender authentication, spam filtering
- **Queue Management**: Reliable delivery with retry logic

### 🌐 Web Administration Interface

- **Real-Time Dashboard**: Live system status and network monitoring
- **User Management**: Profiles, permissions, and subscription management
- **Configuration Editor**: Web-based configuration with validation
- **Message Monitoring**: Live message feeds with filtering and search
- **Performance Metrics**: System health and usage analytics
- **Plugin Management**: Install, configure, and monitor third-party plugins

### 📦 Asset Tracking and Scheduling

- **Check-in/Check-out**: Track personnel and equipment
- **Automated Scheduling**: Time-based broadcasts and maintenance tasks
- **Accountability Reports**: Current status and historical data
- **Integration Ready**: Works with emergency response system

### 🔌 Third-Party Plugin System

- **Extensible Architecture**: Add custom features without modifying core code
- **Manifest-Based Discovery**: YAML manifests define plugin metadata and dependencies
- **Enhanced Plugin API**: Comprehensive base class with helper methods
- **Command Registration**: Register custom commands with priority-based routing
- **Message Handlers**: Process all incoming messages with filtering
- **Scheduled Tasks**: Cron-style and interval-based task execution
- **BBS Menu Integration**: Add custom menu items to the bulletin board system
- **HTTP Client Utilities**: Built-in support for external API calls with rate limiting
- **Plugin Storage**: Isolated key-value storage with TTL support
- **Configuration Management**: Schema-based configuration with validation
- **Inter-Plugin Messaging**: Event-based communication between plugins
- **Health Monitoring**: Automatic health checks and restart on failure
- **Template Generator**: Quick-start tool for creating new plugins
- **Example Plugins**: Weather alerts, data logging, custom commands, and more
- **Property-Based Testing**: Comprehensive test coverage for plugin system

## Quick Start

### 🐳 Docker Installation (Easiest)

The fastest way to get ZephyrGate running:

```bash
# Pull and run from Docker Hub
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest

# Access web interface at http://localhost:8080
```

**Or use Docker Compose:**

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/docker/docker-compose.simple.yml
mv docker-compose.simple.yml docker-compose.yml

# Start services
docker-compose up -d
```

**📖 For detailed Docker instructions, see the [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md)**

### 🚀 Manual Installation

For manual installation on Linux/macOS:

```bash
# 1. Download ZephyrGate
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate

# 2. Run the interactive installer
./install.sh

# 3. Start ZephyrGate
./start.sh
```

The installer will:
- ✅ Check and install system requirements
- ✅ Set up Python virtual environment
- ✅ Configure your Meshtastic connection
- ✅ Let you choose which plugins to enable
- ✅ Create configuration files
- ✅ Optionally set up as a system service

**📖 For detailed installation instructions, see the [Installation Guide](docs/INSTALLATION.md)**

### ⚡ First Steps

After installation:

1. **Access web admin** at http://localhost:8080
   - Default credentials: `admin` / `admin` (change immediately!)
2. **Test connectivity** by sending `ping` from another mesh device
3. **Configure plugins** through the web interface or config file
4. **Explore features** - try commands like `help`, `wx`, `bbs`
5. **Read the docs** - Check out the [User Manual](docs/USER_MANUAL.md)

## Architecture

ZephyrGate uses a modular, plugin-based architecture with clear separation of concerns:

- **Message Router**: Central hub for all Meshtastic communications with priority-based routing
- **Plugin System**: Manifest-based plugin discovery with dependency management
- **Service Modules**: Independent, pluggable feature modules (Emergency, BBS, Weather, etc.)
- **Web Interface**: FastAPI-based administration and monitoring with WebSocket support
- **Database Layer**: SQLite with automatic migrations and connection pooling
- **Menu System**: Hierarchical BBS menus with plugin integration

### Core Components

- **Emergency Response**: SOS alerts and incident management with responder coordination
- **BBS Service**: Bulletin boards, mail, and directory services with multi-node sync
- **Interactive Bot**: Stateless command system with games and information services
- **Weather Service**: Multi-source weather data and emergency alerting
- **Email Gateway**: Bidirectional email integration with queue management
- **Web Admin**: Real-time monitoring and configuration interface
- **Asset Tracking**: Personnel and equipment management with check-in/out
- **Plugin System**: Third-party plugin support with comprehensive API

### Plugin System Architecture

- **Manifest-Based Discovery**: YAML manifests define plugin metadata and dependencies
- **Enhanced Plugin API**: Base class with helper methods for common operations
- **Command Registration**: Priority-based command routing with conflict resolution
- **Menu Integration**: Plugins can register custom BBS menu items
- **Scheduled Tasks**: Cron-style and interval-based task execution
- **Event System**: Pub/sub event system for inter-plugin communication
- **Health Monitoring**: Automatic health checks and restart on failure
- **Configuration Management**: Schema-based configuration with validation
- **Storage Layer**: Isolated key-value storage with TTL support

## Developing Plugins

ZephyrGate supports third-party plugins that can extend functionality without modifying the core codebase. The plugin system provides a comprehensive API with manifest-based discovery and dependency management.

### Quick Start: Create Your First Plugin

1. **Generate a plugin template:**

   ```bash
   python create_plugin.py
   # Follow the interactive prompts
   ```

2. **Implement your plugin:**

   ```python
   from src.core.enhanced_plugin import EnhancedPlugin
   from src.core.plugin_manager import PluginMetadata

   class MyPlugin(EnhancedPlugin):
       async def initialize(self):
           # Register a command handler
           self.register_command("hello", self.handle_hello, "Say hello")
           
           # Schedule a periodic task
           self.register_scheduled_task(
               "hourly_update",
               interval=3600,  # Run every hour
               handler=self.hourly_task
           )
           
           # Register a BBS menu item
           self.register_menu_item(
               menu="utilities",
               label="My Plugin",
               handler=self.menu_handler,
               description="Access my plugin features"
           )
           
           return True
       
       async def handle_hello(self, args, context):
           """Handle the 'hello' command"""
           sender = context.get('sender_id', 'Unknown')
           return f"Hello {sender}! 👋"
       
       async def hourly_task(self):
           """Run every hour"""
           await self.send_message("Hourly update!", broadcast=True)
       
       async def menu_handler(self, context):
           """Handle BBS menu selection"""
           return "Plugin menu accessed!"
       
       def get_metadata(self) -> PluginMetadata:
           return PluginMetadata(
               name="my_plugin",
               version="1.0.0",
               description="My awesome plugin",
               author="Your Name"
           )
   ```

3. **Create a manifest file (manifest.yaml):**

   ```yaml
   name: my_plugin
   version: 1.0.0
   description: "My awesome plugin"
   author: "Your Name"
   
   # ZephyrGate compatibility
   zephyrgate:
     min_version: "1.1.0"
   
   # Dependencies
   dependencies:
     plugins: []
     python_packages:
       - requests>=2.28.0
   
   # Configuration schema
   config_schema:
     type: object
     properties:
       api_key:
         type: string
         description: "API key for external service"
       update_interval:
         type: integer
         default: 3600
   ```

4. **Configure your plugin:**

   ```yaml
   # config/config.yaml
   plugins:
     paths:
       - "plugins"
     enabled_plugins:
       - my_plugin
     
     my_plugin:
       api_key: "your-api-key"
       update_interval: 1800
   ```

5. **Test your plugin:**
   ```bash
   python src/main.py
   # Send "hello" from a mesh device
   ```

### Plugin Capabilities

- **Command Handlers**: Process custom commands from mesh messages with priority routing
- **Message Handlers**: React to all incoming messages with filtering and context
- **Scheduled Tasks**: Execute periodic actions (cron or interval-based)
- **BBS Menu Items**: Add custom menu entries to the bulletin board system
- **HTTP Requests**: Make external API calls with built-in rate limiting and retry logic
- **Data Storage**: Store plugin-specific data with TTL support and automatic cleanup
- **Inter-Plugin Messaging**: Communicate with other plugins via event system
- **Configuration**: Schema-based configuration with validation and hot-reload
- **Health Monitoring**: Automatic health checks with restart on failure
- **Logging**: Integrated logging with plugin-specific log routing
- **Core Service Access**: Access database, message router, and other core services
- **Permission System**: Role-based access control for plugin features

### Learn More

- **[Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md)** - Complete guide to creating plugins (60+ pages)
- **[Enhanced Plugin API](docs/ENHANCED_PLUGIN_API.md)** - Full API reference with examples
- **[Plugin Menu Integration](docs/PLUGIN_MENU_INTEGRATION.md)** - Adding custom BBS menu items
- **[Plugin Template Generator](docs/PLUGIN_TEMPLATE_GENERATOR.md)** - Tool documentation
- **[Example Plugins](examples/plugins/)** - 8 working examples to learn from
- **[Property-Based Testing](docs/TESTING_GUIDE.md)** - Testing your plugins

## Configuration

ZephyrGate uses hierarchical YAML configuration:

```yaml
# Basic configuration example
app:
  name: "ZephyrGate"
  environment: "production"
  log_level: "INFO"

meshtastic:
  interfaces:
    primary:
      type: "serial"
      device: "/dev/ttyUSB0"
      baudrate: 921600

services:
  emergency:
    enabled: true
    escalation_timeout: 300
  bbs:
    enabled: true
    sync_interval: 3600
  weather:
    enabled: true
    providers: ["noaa", "openmeteo"]

plugins:
  paths:
    - "plugins"
    - "/opt/zephyrgate/plugins"
  auto_discover: true
  enabled_plugins:
    - weather_alert
    - data_logger
    - custom_commands
```

### Configuration Sources (in order of precedence):

1. Environment variables (`ZEPHYR_*`)
2. Local configuration file (`config/local.yaml`)
3. Environment-specific file (`config/production.yaml`)
4. Default configuration (`config/default.yaml`)

## Documentation

### 📚 User Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 5 minutes
- **[Installation Guide](docs/INSTALLATION.md)** - Step-by-step installation for all platforms
- **[Docker Deployment](docs/DOCKER_DEPLOYMENT.md)** - Docker and Docker Compose deployment
- **[User Manual](docs/USER_MANUAL.md)** - Complete command reference and usage guide (50+ pages)
- **[Command Reference](docs/COMMAND_REFERENCE.md)** - Quick command lookup
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Command cheat sheet
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Features Overview](docs/FEATURES_OVERVIEW.md)** - Detailed feature descriptions

### 🔧 Administrator Documentation

- **[Admin Guide](docs/ADMIN_GUIDE.md)** - System administration and configuration (40+ pages)
- **[Maintenance Guide](docs/MAINTENANCE_GUIDE.md)** - Backup, monitoring, and updates
- **[Testing Guide](docs/TESTING_GUIDE.md)** - Testing infrastructure and procedures (50+ pages)

### 👩‍💻 Developer Documentation

- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Development setup and guidelines
- **[Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md)** - Create custom plugins (60+ pages)
- **[Enhanced Plugin API](docs/ENHANCED_PLUGIN_API.md)** - Complete API reference
- **[Plugin Menu Integration](docs/PLUGIN_MENU_INTEGRATION.md)** - Add custom BBS menu items
- **[Plugin Template Generator](docs/PLUGIN_TEMPLATE_GENERATOR.md)** - Quick-start tool for plugins
- **[Example Plugins](examples/plugins/README.md)** - 8 working examples
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project

## System Requirements

### Minimum Requirements

- **OS**: Linux (Ubuntu 20.04+, CentOS 8+, Debian 11+)
- **CPU**: 2 cores, 1.5 GHz
- **RAM**: 2 GB
- **Storage**: 10 GB available space
- **Python**: 3.9+
- **Database**: SQLite 3.35+

### Recommended Requirements

- **OS**: Ubuntu 22.04 LTS
- **CPU**: 4 cores, 2.5 GHz
- **RAM**: 4 GB
- **Storage**: 50 GB SSD
- **Network**: 1 Gbps connection

### Hardware Compatibility

- **Meshtastic Devices**: All supported hardware
- **Interfaces**: Serial (USB), TCP, Bluetooth LE
- **Architectures**: AMD64, ARM64, ARM/v7

## Deployment Options

### 🐳 Production Docker

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d
```

### ☁️ Cloud Platforms

- **AWS**: EC2 + RDS + S3 integration
- **Google Cloud**: Compute Engine + Cloud SQL
- **Azure**: Container Instances + Azure Database
- **DigitalOcean**: Droplets + Managed Databases

### 🏠 Self-Hosted

- **Raspberry Pi**: ARM64 support for edge deployment
- **Home Server**: Docker or manual installation
- **VPS**: Cloud VPS with Docker deployment

## Security

ZephyrGate implements multiple security layers:

- **Authentication**: JWT-based with configurable expiration
- **Authorization**: Role-based access control (RBAC)
- **Encryption**: TLS/SSL for web interface, GPG for backups
- **Input Validation**: Comprehensive sanitization and validation
- **Rate Limiting**: Protection against abuse and DoS
- **Audit Logging**: Complete activity audit trails

## Monitoring and Backup

### Built-in Monitoring

- **Health Checks**: Service health and dependency status
- **Metrics**: Prometheus-compatible metrics endpoint
- **Logging**: Structured JSON logging with multiple outputs
- **Alerting**: Configurable alerts for system events

### Automated Backups

- **Scheduled**: Daily, weekly, monthly backup schedules
- **Incremental**: Space-efficient incremental backups
- **Encrypted**: GPG encryption for sensitive data
- **Cloud Storage**: S3, Google Cloud Storage, Azure Blob

## Community and Support

### Getting Help

- **📖 Documentation**: Comprehensive guides and references
- **🐛 Issue Tracker**: Bug reports and feature requests
- **💬 Discussions**: Community Q&A and general discussion

### Contributing

We welcome contributions! Ways to help:

- **Code**: Bug fixes, features, optimizations
- **Documentation**: Improvements, translations, examples
- **Testing**: Bug reports, compatibility testing
- **Community**: Support other users, share experiences

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

ZephyrGate builds upon the excellent work of several Meshtastic community projects:

- **GuardianBridge** - Emergency response and monitoring
- **meshing-around** - Interactive bot and games
- **TC2-BBS-mesh** - Bulletin board system

Special thanks to:

- The Meshtastic project and community
- All contributors to the original projects
- Beta testers and early adopters
- The open-source community

---

<div align="center">

**[⬆ Back to Top](#zephyrgate---unified-meshtastic-gateway)**

Made with ❤️ by the ZephyrGate community

</div>
