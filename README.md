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

ZephyrGate consolidates the functionality of GuardianBridge, meshing-around, and TC2-BBS-mesh into a single, comprehensive communication platform for Meshtastic mesh networks. It provides emergency response capabilities, bulletin board systems, interactive features, weather services, and email integration—all designed to operate both online and offline with a web-based administration interface.

### Key Benefits

- **🚨 Emergency Ready**: Comprehensive SOS alert system with responder coordination
- **📡 Always Connected**: Multi-interface Meshtastic support (Serial, TCP, BLE)
- **💬 Community Hub**: Full-featured BBS with mail, bulletins, and directory services
- **🤖 Intelligent Bot**: Auto-responses, games, and information lookup services
- **🌤️ Weather Aware**: Multi-source weather data and emergency alerting
- **📧 Email Bridge**: Seamless mesh-to-email communication
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
- **Menu-Driven Interface**: Easy navigation through hierarchical menus

### 🤖 Interactive Bot and Auto-Response

- **Keyword Detection**: Automatic responses to monitored keywords
- **Emergency Keywords**: Special handling for emergency-related terms
- **Interactive Games**: BlackJack, DopeWars, Lemonade Stand, Golf Simulator, and more
- **Educational Features**: Ham radio test questions, quizzes, surveys
- **Information Services**: Weather, Wikipedia search, network statistics
- **AI Integration**: Support for local LLM services with aircraft detection

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

### 📦 Asset Tracking and Scheduling

- **Check-in/Check-out**: Track personnel and equipment
- **Automated Scheduling**: Time-based broadcasts and maintenance tasks
- **Accountability Reports**: Current status and historical data
- **Integration Ready**: Works with emergency response system

## Quick Start

### 🐳 Docker Deployment (Recommended)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-repo/zephyrgate.git
   cd zephyrgate
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start services:**

   ```bash
   docker-compose up -d
   ```

4. **Access the interface:**
   - Web Admin: http://localhost:8080
   - Default credentials: admin/admin (change immediately)

### 🔧 Manual Installation

1. **Install system dependencies:**

   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install -y python3 python3-pip python3-venv sqlite3 git

   # CentOS/RHEL
   sudo yum install -y python3 python3-pip sqlite git
   ```

2. **Set up application:**

   ```bash
   git clone https://github.com/your-repo/zephyrgate.git
   cd zephyrgate
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure:**

   ```bash
   cp config/config.template.yaml config/config.yaml
   # Edit config.yaml with your Meshtastic device settings
   ```

4. **Run:**
   ```bash
   python src/main.py
   ```

### ⚡ First Steps

1. **Connect your Meshtastic device** via USB or configure TCP/BLE connection
2. **Test connectivity** by sending `ping` from another mesh device
3. **Access web admin** at http://localhost:8080 to configure services
4. **Enable desired features** (weather, email, emergency response, etc.)
5. **Set up user profiles** and permissions through the web interface

## Architecture

ZephyrGate uses a modular, microservices-inspired architecture:

- **Message Router**: Central hub for all Meshtastic communications
- **Service Modules**: Independent, pluggable feature modules
- **Web Interface**: FastAPI-based administration and monitoring
- **Database Layer**: SQLite with automatic migrations
- **Plugin System**: Extensible architecture for custom features

### Core Components

- **Emergency Response**: SOS alerts and incident management
- **BBS Service**: Bulletin boards, mail, and directory services
- **Interactive Bot**: Auto-responses, games, and information services
- **Weather Service**: Multi-source weather data and alerting
- **Email Gateway**: Bidirectional email integration
- **Web Admin**: Real-time monitoring and configuration
- **Asset Tracking**: Personnel and equipment management

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
```

### Configuration Sources (in order of precedence):

1. Environment variables (`ZEPHYR_*`)
2. Local configuration file (`config/local.yaml`)
3. Environment-specific file (`config/production.yaml`)
4. Default configuration (`config/default.yaml`)

## Documentation

### 📚 User Documentation

- **[User Manual](docs/USER_MANUAL.md)** - Complete command reference and usage guide
- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 5 minutes
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Features Overview](docs/FEATURES_OVERVIEW.md)** - Detailed feature descriptions

### 🔧 Administrator Documentation

- **[Admin Guide](docs/ADMIN_GUIDE.md)** - Installation, configuration, and maintenance
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment strategies
- **[Maintenance Guide](docs/MAINTENANCE_GUIDE.md)** - Backup, monitoring, and updates

### 👩‍💻 Developer Documentation

- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Development setup and guidelines
- **[API Reference](docs/API_REFERENCE.md)** - REST API documentation
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
