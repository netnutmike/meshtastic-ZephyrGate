# Changelog

All notable changes to ZephyrGate will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-04

### Added

#### Plugin System Enhancements
- **Plugin Menu Registry**: Centralized registry for plugin menu items with BBS integration
- **Enhanced Plugin API**: Comprehensive base class with helper methods for common operations
- **Plugin Command Handler**: Dedicated command routing system for plugin commands
- **Plugin Scheduler**: Cron-style and interval-based task scheduling for plugins
- **Plugin Core Services**: Unified service access layer for plugins
- **Plugin Configuration**: Schema-based configuration with validation and hot-reload
- **Plugin Storage**: Isolated key-value storage with TTL support
- **HTTP Client Utilities**: Built-in rate limiting and retry logic for external APIs
- **Inter-Plugin Messaging**: Event-based communication between plugins
- **Health Monitoring**: Automatic plugin health checks and restart capabilities
- **Template Generator**: Interactive tool for creating new plugins (`create_plugin.py`)

#### Menu System Improvements
- **Stateless Bot Commands**: All bot/game commands work globally without session state
- **Hierarchical BBS Menus**: Improved navigation with main, BBS, mail, and utilities menus
- **Plugin Menu Integration**: Third-party plugins can register custom menu items
- **Menu Command Registry**: Centralized command registration and routing
- **Session Management**: Automatic session cleanup and timeout handling

#### Testing Infrastructure
- **Property-Based Tests**: 15+ property-based test suites for core functionality
  - Command routing properties
  - Config management properties
  - Error handling properties
  - Health monitoring properties
  - HTTP client properties
  - Inter-plugin messaging properties
  - Lifecycle properties
  - Log routing properties
  - Manifest validation properties
  - Menu integration properties
  - Message routing properties
  - Permission enforcement properties
  - Plugin discovery properties
  - Scheduling properties
  - Storage properties
- **Integration Tests**: Enhanced plugin system integration tests
- **Unit Tests**: Comprehensive coverage for all plugin components

#### Documentation
- **Enhanced Plugin API Reference**: Complete API documentation with examples
- **Plugin Menu Integration Guide**: How to add custom BBS menu items
- **Plugin Template Generator Guide**: Using the template generator tool
- **Example Plugins**: 8 working examples demonstrating various features
  - Core services example
  - Data logger
  - Hello world
  - Menu integration example
  - Multi-command example
  - Scheduled task example
  - Weather alert example
- **Plugin Development Guide**: Comprehensive guide for plugin developers

### Changed

#### Architecture
- **Menu System Refactoring**: Moved from stateful to stateless bot commands for better off-grid reliability
- **Plugin Loading**: Improved manifest-based plugin discovery and validation
- **Command Routing**: Priority-based routing with plugin command isolation
- **Service Integration**: Plugins now access core services through unified interface
- **Configuration Management**: Hierarchical config with environment variable support

#### Code Quality
- **Logging Improvements**: Replaced print statements with proper logging throughout
- **Error Handling**: Better error messages and graceful degradation
- **Type Hints**: Added comprehensive type annotations
- **Documentation**: Inline documentation and docstrings for all public APIs

#### Performance
- **Plugin Initialization**: Parallel plugin loading for faster startup
- **Command Dispatch**: Optimized command routing with caching
- **Menu Rendering**: Reduced overhead in menu generation
- **Database Queries**: Optimized queries for session and menu data

### Improved

#### Developer Experience
- **Plugin Template**: Comprehensive template with best practices
- **Example Code**: Working examples for all major features
- **API Documentation**: Complete reference with code samples
- **Error Messages**: Clear, actionable error messages
- **Debugging**: Better logging and diagnostic information

#### User Experience
- **Command Consistency**: Unified command syntax across all plugins
- **Help System**: Improved help text and command discovery
- **Menu Navigation**: Clearer menu structure and navigation
- **Response Times**: Faster command processing and menu rendering

#### System Reliability
- **Plugin Isolation**: Plugins run in isolated contexts with error boundaries
- **Health Checks**: Automatic detection and recovery from plugin failures
- **Resource Management**: Better memory and connection management
- **Graceful Degradation**: System continues operating if plugins fail

### Fixed
- **Session Cleanup**: Fixed memory leak in BBS session management
- **Command Conflicts**: Resolved command name collisions between plugins
- **Menu State**: Fixed issues with menu state persistence
- **Configuration Reload**: Fixed hot-reload of plugin configurations
- **Scheduled Tasks**: Fixed task scheduling and cancellation

### Removed
- **Duplicate Documentation**: Removed redundant documentation files
  - `WEATHER_LOCATION_SETUP.md` (integrated into USER_MANUAL.md)
  - `DEPLOYMENT_GUIDE.md` (consolidated into DOCKER_DEPLOYMENT.md)
  - `TROUBLESHOOTING_QUICK.md` (merged into TROUBLESHOOTING.md)
  - `DOCKER_QUICK_START.md` (consolidated into DOCKER_DEPLOYMENT.md)
- **Legacy Code**: Removed deprecated plugin interfaces
- **Debug Output**: Cleaned up debugging print statements from production code

### Technical Details

#### Plugin System Architecture
- **Manifest-Based Discovery**: Plugins defined by YAML manifests with metadata
- **Dependency Management**: Automatic dependency resolution and validation
- **Version Compatibility**: Semantic versioning with compatibility checks
- **Lifecycle Management**: Initialize, start, stop, cleanup hooks
- **Event System**: Pub/sub event system for inter-plugin communication

#### Menu System Architecture
- **Stateless Commands**: Bot commands work without session state
- **Hierarchical Menus**: BBS menus maintain session state for navigation
- **Plugin Integration**: Plugins register menu items via registry
- **Command Routing**: Priority-based routing with fallback handling
- **Context Passing**: Rich context objects for command handlers

#### Testing Coverage
- **Unit Tests**: 40+ test files covering core functionality
- **Integration Tests**: 20+ test files for end-to-end scenarios
- **Property Tests**: 15+ test files for invariant checking
- **Test Utilities**: Comprehensive mocking and fixture support
- **CI/CD Integration**: Automated testing on all commits

### Migration Notes

#### For Plugin Developers
- **Menu Registration**: Update to use new `register_menu_item()` API
- **Command Handlers**: Ensure handlers are async and return strings
- **Configuration**: Migrate to schema-based configuration
- **Storage**: Use new `store_data()` / `retrieve_data()` APIs
- **Scheduling**: Update to use `register_scheduled_task()`

#### For Administrators
- **Configuration**: Review plugin configurations in `config/config.yaml`
- **Manifests**: Ensure all plugins have valid manifest files
- **Dependencies**: Check plugin dependency compatibility
- **Permissions**: Review plugin permissions and access controls

#### Breaking Changes
- **Menu API**: Old menu registration methods deprecated
- **Command Registration**: Must use `register_command()` from EnhancedPlugin
- **Storage API**: Old storage methods removed, use new API
- **Configuration**: Plugin config structure changed to schema-based

### Known Issues
- None reported in this release

### Upgrade Instructions

1. **Backup your data**:
   ```bash
   ./scripts/backup.sh
   ```

2. **Update code**:
   ```bash
   git pull origin main
   ```

3. **Update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Update plugin manifests**: Ensure all custom plugins have valid manifest files

5. **Test configuration**:
   ```bash
   python src/main.py --validate-config
   ```

6. **Restart service**:
   ```bash
   ./stop.sh && ./start.sh
   ```

## [1.0.0] - 2026-01-25

### Added - Initial Release

#### Core Features
- **Plugin System**: Third-party plugin architecture with manifest-based discovery
- **Enhanced Plugin API**: Comprehensive API for plugin development
- **Message Router**: Priority-based command routing and message handling
- **Health Monitoring**: System health checks and monitoring
- **Database**: SQLite database with migration system
- **Configuration**: YAML-based configuration with validation

#### Service Plugins (8 Total)

1. **Bot Service**
   - Help system with command documentation
   - Ping/pong responsiveness testing
   - Information lookup services
   - Message history tracking
   - Interactive games (Blackjack, DopeWars, Lemonade Stand, Golf, Trivia)

2. **Emergency Service**
   - SOS alert system with multiple types (general, police, fire, medical)
   - Incident management and tracking
   - Responder coordination
   - Check-in system
   - Automatic escalation

3. **BBS Service**
   - Public bulletin board
   - Private mail system
   - Channel directory
   - Menu-driven interface
   - Multi-node synchronization

4. **Weather Service**
   - Current weather conditions
   - Multi-day forecasts
   - Weather alerts and warnings
   - Multiple location formats (city, ZIP, coordinates)
   - Multi-source data (NOAA, Open-Meteo)

5. **Email Service**
   - Bidirectional email gateway
   - SMTP sending
   - IMAP receiving
   - Message queuing
   - Spam filtering

6. **Asset Tracking Service**
   - Asset registration and tracking
   - Location updates
   - Check-in/check-out system
   - Status monitoring
   - History tracking

7. **Web Service**
   - Web-based administration interface
   - Real-time dashboard
   - Plugin management
   - System monitoring
   - Configuration editor
   - WebSocket support

8. **Ping Responder**
   - Automatic ping responses
   - Configurable response messages

#### Documentation (17 Documents, ~24,500 Lines)

**Getting Started**
- Quick Start Guide
- Installation Guide (Docker & Manual)
- Docker Deployment Guide
- Quick Reference Card

**User Documentation**
- User Manual (50 pages, 40+ commands)
- Features Overview
- Troubleshooting Guide
- Troubleshooting Quick Reference

**Administrator Documentation**
- Admin Guide (40 pages)
- Deployment Guide
- Maintenance Guide
- Testing Guide (50 pages, 70+ test cases)

**Developer Documentation**
- Developer Guide
- Plugin Development Guide
- Enhanced Plugin API Reference
- Plugin Menu Integration Guide
- Plugin Template Generator Guide

#### Docker Support
- Multi-architecture Docker images (amd64, arm64, arm/v7)
- Docker Compose configurations
- Production-ready Dockerfile
- Automated CI/CD with GitHub Actions
- Docker Hub publishing
- Health checks and monitoring

#### Testing
- Unit tests (40+ test files)
- Integration tests (20+ test files)
- Property-based tests (15+ test files)
- Comprehensive test coverage
- Automated test suite

#### Tools & Scripts
- Interactive installer (`install.sh`)
- Start/stop scripts
- Plugin template generator (`create_plugin.py`)
- Docker build script
- Backup scripts

#### Examples
- 8 example plugins
- Plugin development examples
- Configuration examples
- Docker Compose examples

### Technical Details

#### Requirements
- Python 3.10+
- SQLite database
- Meshtastic device (USB, TCP, or BLE)
- Optional: Redis for caching
- Optional: Nginx for reverse proxy

#### Supported Platforms
- Linux (x86_64, ARM64, ARMv7)
- macOS (Intel, Apple Silicon)
- Windows (via Docker)
- Raspberry Pi (3, 4, 5)

#### Architecture
- Plugin-based architecture
- Event-driven message routing
- Asynchronous processing
- Database-backed persistence
- RESTful API
- WebSocket real-time updates

#### Security
- Non-root Docker containers
- Read-only filesystems
- Resource limits
- Input validation
- Configuration encryption support
- Secure defaults

### Known Issues
- None reported in initial release

### Migration Notes
- First release, no migration needed

---

## Version History

- **1.1.0** (2026-02-04) - Cleanup and logging improvements
- **1.0.0** (2026-01-25) - Initial release

---

## Versioning

ZephyrGate follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backwards compatible manner
- **PATCH** version for backwards compatible bug fixes

## Release Process

1. Update version in:
   - `src/__init__.py`
   - `setup.py`
   - `VERSION` file
   - `CHANGELOG.md`

2. Create git tag:
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

3. GitHub Actions automatically:
   - Builds Docker images
   - Publishes to Docker Hub
   - Creates GitHub release

## Links

- [GitHub Repository](https://github.com/YOUR_REPO/zephyrgate)
- [Docker Hub](https://hub.docker.com/r/YOUR_USERNAME/zephyrgate)
- [Documentation](https://github.com/YOUR_REPO/zephyrgate/tree/main/docs)
- [Issue Tracker](https://github.com/YOUR_REPO/zephyrgate/issues)

---

**Current Version**: 1.1.0  
**Release Date**: 2026-02-04  
**Status**: Stable
