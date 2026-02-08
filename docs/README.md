# ZephyrGate Documentation

Welcome to the ZephyrGate documentation! This directory contains comprehensive guides for users, administrators, and developers.

## 📚 Documentation Index

### Getting Started

| Document | Description | Audience |
|----------|-------------|----------|
| [Quick Start Guide](QUICK_START.md) | Get up and running in 5 minutes | All Users |
| [Admin Guide](ADMIN_GUIDE.md) | Complete installation, configuration, and deployment guide | Administrators |
| [Quick Reference](QUICK_REFERENCE.md) | Command cheat sheet and quick tips | All Users |

### User Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [User Manual](USER_MANUAL.md) | Complete command reference and usage guide (50+ pages) | End Users |
| [Command Reference](COMMAND_REFERENCE.md) | Comprehensive command listing with examples | End Users |
| [Features Overview](FEATURES_OVERVIEW.md) | Detailed feature descriptions and capabilities | All Users |
| [Auto-Responder Quick Reference](AUTO_RESPONDER_QUICK_REFERENCE.md) | Quick reference for auto-response configuration | Administrators |
| [Scheduled Broadcasts Reference](SCHEDULED_BROADCASTS_PLUGIN_REFERENCE.md) | Scheduled broadcasts and plugin calls | Administrators |
| [GC Forecast Quick Reference](GC_FORECAST_QUICK_REFERENCE.md) | Compact weather forecast format | All Users |
| [Villages Events Quick Reference](VILLAGES_EVENTS_QUICK_REFERENCE.md) | Quick reference for Villages Events Service plugin | Villages Residents |
| [Villages Events Scheduled Broadcasts](VILLAGES_EVENTS_SCHEDULED_BROADCASTS.md) | Automated event updates guide | Villages Residents |
| [Troubleshooting Guide](TROUBLESHOOTING.md) | Common issues and solutions | All Users |

### Administrator Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Admin Guide](ADMIN_GUIDE.md) | Complete system administration guide including installation, configuration, Docker deployment, MQTT Gateway, auto-response, scheduled broadcasts, maintenance, backup, and troubleshooting | Administrators |
| [Testing Guide](TESTING_GUIDE.md) | Testing infrastructure and procedures (50+ pages) | Administrators, Developers |

### Developer Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Developer Guide](DEVELOPER_GUIDE.md) | Development setup and contribution guidelines | Developers |
| [Plugin Development Guide](PLUGIN_DEVELOPMENT.md) | Complete guide to creating plugins (60+ pages) | Plugin Developers |
| [Enhanced Plugin API](ENHANCED_PLUGIN_API.md) | Full API reference for plugin development | Plugin Developers |
| [Plugin Menu Integration](PLUGIN_MENU_INTEGRATION.md) | Adding custom BBS menu items | Plugin Developers |
| [Plugin Template Generator](PLUGIN_TEMPLATE_GENERATOR.md) | Using the plugin template tool | Plugin Developers |

## 🎯 Quick Navigation

### I want to...

**Install ZephyrGate**
- → Start with [Admin Guide - Installation](ADMIN_GUIDE.md#installation) section

**Learn the commands**
- → Check [User Manual](USER_MANUAL.md) or [Command Reference](COMMAND_REFERENCE.md)

**Configure auto-responses or scheduled broadcasts**
- → See [Admin Guide - Auto-Response](ADMIN_GUIDE.md#auto-response-configuration) and [Admin Guide - Scheduled Broadcasts](ADMIN_GUIDE.md#scheduled-broadcasts)

**Set up MQTT Gateway**
- → Follow [Admin Guide - MQTT Gateway](ADMIN_GUIDE.md#mqtt-gateway) section

**Develop a plugin**
- → Read [Plugin Development Guide](PLUGIN_DEVELOPMENT.md) and [Enhanced Plugin API](ENHANCED_PLUGIN_API.md)

**Troubleshoot an issue**
- → See [Troubleshooting Guide](TROUBLESHOOTING.md) or [Admin Guide - Troubleshooting](ADMIN_GUIDE.md#troubleshooting)

**Deploy to production**
- → Follow [Admin Guide - Docker Deployment](ADMIN_GUIDE.md#docker-deployment) section

**Contribute code**
- → Read [Developer Guide](DEVELOPER_GUIDE.md) and [Testing Guide](TESTING_GUIDE.md)

## 📖 Documentation Statistics

- **Total Documents**: 21 comprehensive guides
- **Total Pages**: ~280 pages of documentation
- **Total Lines**: ~23,000 lines
- **Last Updated**: 2026-02-07 (Version 2.0)

## 🔄 Recent Updates (v2.0)

### New Features Documented
- **MQTT Gateway**: Complete setup and configuration guide
- **Network Traceroute Mapper**: Automatic network topology mapping
- **Enhanced Auto-Response**: Custom rules, plugin calls, AI integration
- **Scheduled Broadcasts**: Plugin-powered dynamic content, shell commands
- **Compact Weather Format**: GC forecast for bandwidth-constrained networks

### Documentation Consolidation
- **Admin Guide**: Consolidated 9 separate guides into one comprehensive resource
  - Installation, Docker deployment, MQTT Gateway, auto-response configuration
  - Scheduled broadcasts, maintenance, backup, troubleshooting
- **Removed Redundant Guides**: Eliminated duplicate content across multiple files
- **Improved Organization**: Clear separation between admin, user, and developer docs

### Updated Documentation
- **Features Overview**: Reorganized with highlights first, detailed features below
- **Admin Guide**: Complete rewrite with all new features and consolidated content
- **Quick References**: Updated for new features and configuration options

## 📝 Documentation Standards

All ZephyrGate documentation follows these standards:

- **Markdown Format**: All docs use GitHub-flavored Markdown
- **Code Examples**: Working, tested code samples
- **Version Tags**: Clearly marked version-specific information
- **Cross-References**: Links between related documents
- **Table of Contents**: All major docs include TOC
- **Examples**: Real-world usage examples
- **Screenshots**: Visual aids where helpful

## 🤝 Contributing to Documentation

Found an error or want to improve the docs? We welcome contributions!

1. **Small fixes**: Submit a pull request directly
2. **Major changes**: Open an issue first to discuss
3. **New guides**: Propose in GitHub Discussions

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

## 📋 Document Descriptions

### Quick Start Guide
5-minute introduction to ZephyrGate with essential commands and first steps. Perfect for new users who want to get started immediately.

### Admin Guide
**The comprehensive administrator resource** covering:
- Installation (manual and Docker)
- Configuration management
- Plugin system
- Auto-response configuration with custom rules
- Scheduled broadcasts with plugin calls and shell commands
- MQTT Gateway setup and configuration
- Service management
- User management and permissions
- Security configuration
- Monitoring and maintenance procedures
- Backup and recovery
- Performance tuning
- Troubleshooting
- Docker deployment (single container and Docker Compose)

This guide consolidates what were previously 9 separate guides into one well-organized resource.

### User Manual
The complete user reference covering:
- All 50+ commands with examples
- Service-specific features
- Emergency response procedures
- BBS system usage
- Weather and alert services
- Email gateway configuration
- Interactive games and features

### Command Reference
Quick command lookup with:
- Alphabetical command listing
- Syntax and parameters
- Usage examples
- Related commands
- Service categories

### Features Overview
Detailed feature descriptions in sales-page format:
- High-level highlights and key benefits
- Deep dive into each feature
- Configuration examples
- Use cases and deployment options

### Plugin Development Guide
Complete plugin development reference:
- Plugin architecture overview
- EnhancedPlugin base class
- Command registration
- Message handling
- Scheduled tasks
- BBS menu integration
- Configuration management
- Data storage
- HTTP client usage
- Testing plugins
- Example plugins

### Enhanced Plugin API
Full API reference including:
- All public methods and properties
- Parameter descriptions
- Return values
- Code examples
- Best practices
- Common patterns

### Plugin Menu Integration
Guide to BBS menu customization:
- Menu system architecture
- Registering menu items
- Menu command handlers
- Session management
- Context passing
- Examples and patterns

### Testing Guide
Comprehensive testing documentation:
- Test infrastructure overview
- Unit testing guidelines
- Integration testing
- Property-based testing
- Test utilities and fixtures
- Running tests
- Writing new tests
- CI/CD integration

### Troubleshooting Guide
Common issues and solutions:
- Installation problems
- Connection issues
- Plugin errors
- Performance problems
- Database issues
- Configuration errors
- Diagnostic procedures

### Quick References
- **Auto-Responder**: Configuration syntax and examples
- **Scheduled Broadcasts**: Plugin calls and shell commands
- **GC Forecast**: Compact weather format for bandwidth-constrained networks
- **Villages Events**: Event service integration
- **Command Reference**: Quick command lookup

### Developer Guide
Development environment setup:
- Setting up development environment
- Code organization
- Coding standards
- Git workflow
- Testing requirements
- Pull request process
- Code review guidelines

## 🔗 External Resources

- **GitHub Repository**: https://github.com/YOUR_REPO/zephyrgate
- **Docker Hub**: https://hub.docker.com/r/YOUR_USERNAME/zephyrgate
- **Issue Tracker**: https://github.com/YOUR_REPO/zephyrgate/issues
- **Discussions**: https://github.com/YOUR_REPO/zephyrgate/discussions
- **Meshtastic Docs**: https://meshtastic.org/docs/

## 📞 Getting Help

- **Documentation**: Start here!
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Examples**: Check the `examples/` directory
- **Tests**: Look at test files for usage examples

---

**Version**: 1.1.0  
**Last Updated**: 2026-02-04  
**Maintained by**: ZephyrGate Development Team
