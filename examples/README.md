# ZephyrGate Examples

This directory contains example code and demonstrations for various ZephyrGate features.

## Available Examples

### GC Forecast Example (`gc_forecast_example.py`)

**Purpose**: Demonstrates the compact weather forecast format (GC format) compatible with Meshtastic

**Features Demonstrated**:
- Compact weather output format
- Customizable separators and fields
- Icon code mappings
- Hours-based forecasting
- Programmatic usage
- Scheduled broadcast configuration

**Usage**:
```bash
# Run the example script
python3 examples/gc_forecast_example.py
```

**What It Shows**:
1. Basic forecast with default settings
2. Custom number of hours
3. Forecast with preamble
4. Custom separators
5. Custom fields
6. Meshtastic-optimized format
7. Status bar format
8. Programmatic usage
9. Scheduled broadcast configuration
10. Icon code reference
11. Available fields reference

**Documentation**:
- User Guide: `docs/GC_FORECAST_GUIDE.md`
- Quick Reference: `docs/GC_FORECAST_QUICK_REFERENCE.md`
- Integration Details: `GC_FORECAST_INTEGRATION.md`

**Example Output**:
```
#76#1pm,9,75,0.0#2pm,9,76,0.0#3pm,9,76,0.0#4pm,9,75,0.0#5pm,9,74,0.0#
```

**Use Cases**:
- Meshtastic weather broadcasts (fits in 237-byte limit)
- Status bar weather displays
- Automated weather updates
- Bandwidth-constrained communications

---

### AI Integration Example (`ai_integration_example.py`)

**Purpose**: Demonstrates AI service integration

**Features**:
- AI service configuration
- Message processing with AI
- Context management
- Response handling

---

### Auto Response Example (`auto_response_example.py`)

**Purpose**: Demonstrates automatic response system

**Features**:
- Pattern matching
- Automatic replies
- Response templates
- Conditional responses

---

### BBS Sync Example (`bbs_sync_example.py`)

**Purpose**: Demonstrates BBS synchronization

**Features**:
- Bulletin board sync
- Message exchange
- Node coordination
- Data consistency

---

### JS8Call Integration Example (`js8call_integration_example.py`)

**Purpose**: Demonstrates JS8Call radio integration

**Features**:
- JS8Call protocol
- Radio messaging
- Frequency management
- Signal handling

---

## Plugin Examples

For plugin development examples, see the `plugins/` subdirectory:

- **Hello World Plugin** - Basic plugin structure
- **Weather Alert Plugin** - HTTP requests and scheduling
- **Menu Example Plugin** - BBS menu integration
- **Data Logger Plugin** - Data storage and retrieval
- **Multi-Command Plugin** - Multiple command handlers
- **Scheduled Task Plugin** - Background task scheduling
- **Core Services Plugin** - Inter-plugin messaging

See `examples/plugins/README.md` for detailed plugin examples.

## Quick Start

### Running Examples

Most examples can be run directly:

```bash
# Run an example
python3 examples/gc_forecast_example.py

# Run with virtual environment
source .venv/bin/activate
python3 examples/gc_forecast_example.py
```

### Using Examples as Templates

1. Copy the example to your project
2. Modify for your specific needs
3. Test thoroughly
4. Deploy to production

## Example Categories

### Weather Examples
- `gc_forecast_example.py` - Compact weather format

### Integration Examples
- `ai_integration_example.py` - AI service integration
- `js8call_integration_example.py` - Radio integration
- `bbs_sync_example.py` - BBS synchronization

### Automation Examples
- `auto_response_example.py` - Automatic responses

### Plugin Examples
- See `examples/plugins/` directory

## Documentation

Each example includes:
- Purpose and use case
- Features demonstrated
- Usage instructions
- Expected output
- Related documentation

## Best Practices

1. **Read the Documentation**: Check related docs before using examples
2. **Test Safely**: Test examples in development environment first
3. **Understand the Code**: Review code before adapting for production
4. **Check Dependencies**: Ensure all required packages are installed
5. **Error Handling**: Add proper error handling for production use

## Contributing Examples

When contributing new examples:

1. **Clear Purpose**: Example should demonstrate specific feature
2. **Documentation**: Include inline comments and docstrings
3. **Working Code**: Ensure example runs without errors
4. **Output Examples**: Show expected output
5. **Use Cases**: Explain when to use the example
6. **Update README**: Add entry to this README

## Support

- **Documentation**: See `docs/` directory
- **Plugin Development**: `docs/PLUGIN_DEVELOPMENT.md`
- **API Reference**: `docs/ENHANCED_PLUGIN_API.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

## License

Examples are provided under the same license as ZephyrGate.
