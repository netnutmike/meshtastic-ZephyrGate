# Villages Events Service Plugin - Summary

## Overview

The Villages Events Service plugin integrates the `python-villages-events` project into ZephyrGate, enabling users to query The Villages community events calendar through Meshtastic messages or other communication channels.

## Key Features

- ✅ Fetch events from The Villages API
- ✅ Multiple output formats (Meshtastic, JSON, CSV, Plain text)
- ✅ Filter by date range (today, tomorrow, this week, etc.)
- ✅ Filter by category (entertainment, sports, arts, etc.)
- ✅ Filter by location (town squares, specific venues)
- ✅ Customizable venue abbreviations
- ✅ Configurable output fields
- ✅ Disabled by default (location-specific)

## Installation Status

✅ **Plugin Created Successfully**

### Files Created

```
plugins/villages_events_service/
├── __init__.py                 # Package initialization
├── plugin.py                   # Main plugin implementation
├── manifest.yaml               # Plugin manifest
├── README.md                   # Detailed documentation
└── PLUGIN_SUMMARY.md          # This file

examples/
└── villages_events_example.py  # Usage examples

docs/
└── VILLAGES_EVENTS_QUICK_REFERENCE.md  # Quick reference guide

config/
└── config-example.yaml         # Updated with plugin config
```

## Quick Start

### 1. Enable the Plugin

Edit `config/config.yaml`:

```yaml
plugins:
  villages_events_service:
    enabled: true
```

### 2. Use the Commands

```bash
# Get today's events
villages-events

# Get this week's events in JSON
villages-events --format json --date-range this-week

# Get help
villages-help
```

## Configuration Example

```yaml
plugins:
  villages_events_service:
    enabled: true
    format: meshtastic
    date_range: today
    category: entertainment
    location: town-squares
    timeout: 10
    venue_mappings:
      Brownwood: BW
      Sawgrass: SG
      Spanish Springs: SS
      Lake Sumter: LS
    output_fields:
      - location.title
      - title
```

## Commands

### villages-events

Fetch events from The Villages calendar.

**Options:**
- `--format` - Output format (meshtastic, json, csv, plain)
- `--date-range` - Date range (today, tomorrow, this-week, etc.)
- `--category` - Event category (entertainment, sports, etc.)
- `--location` - Event location (town-squares, specific venue, etc.)

**Examples:**
```
villages-events
villages-events --format json --date-range this-week
villages-events --category sports --location Brownwood+Paddock+Square
```

### villages-help

Show help message with available commands and options.

## Output Formats

### Meshtastic (Default)
```
BW,John Doe Band#SS,Jane Smith#SG,The Band#
```

### JSON
```json
[
  {"location.title": "BW", "title": "John Doe Band"},
  {"location.title": "SS", "title": "Jane Smith"}
]
```

### CSV
```
location.title,title
BW,John Doe Band
SS,Jane Smith
```

### Plain Text
```
location.title: BW, title: John Doe Band
location.title: SS, title: Jane Smith
```

## Dependencies

- `requests` - HTTP library for API requests
- `pyyaml` - YAML parser for configuration
- `python-villages-events` - The Villages events project (included)

## Technical Details

### Plugin Architecture

The plugin follows the ZephyrGate plugin architecture:

1. **Inherits from EnhancedPlugin** - Uses the standard plugin base class
2. **Command Registration** - Registers `villages-events` and `villages-help` commands
3. **Configuration Management** - Loads settings from config.yaml
4. **Integration** - Imports and uses python-villages-events modules
5. **Error Handling** - Graceful error handling with user-friendly messages

### Integration Method

The plugin integrates the python-villages-events project by:

1. Adding the project directory to Python path
2. Importing required modules (config, token_fetcher, session_manager, etc.)
3. Wrapping the functionality in command handlers
4. Providing configuration through ZephyrGate's config system

### Data Flow

```
User Command
    ↓
Plugin Command Handler
    ↓
Fetch Auth Token (from The Villages CDN)
    ↓
Establish Session (with cookies)
    ↓
Fetch Events (from API)
    ↓
Process Events (apply filters, abbreviations)
    ↓
Format Output (meshtastic/json/csv/plain)
    ↓
Return to User
```

## Why Disabled by Default?

This plugin is **disabled by default** because:

1. **Location-Specific** - Only useful for residents of The Villages, FL
2. **External API** - Depends on The Villages API availability
3. **Niche Use Case** - Not applicable to most ZephyrGate users
4. **Optional Feature** - Users must explicitly enable it

## Testing

### Manual Testing

```bash
# Test plugin structure
python3 -c "import yaml; yaml.safe_load(open('plugins/villages_events_service/manifest.yaml'))"

# Test imports (requires python-villages-events)
python3 -c "import sys; sys.path.insert(0, 'python-villages-events'); from src.config import Config; print('✓ Imports work')"
```

### Integration Testing

1. Enable the plugin in config.yaml
2. Start ZephyrGate
3. Send `villages-events` command
4. Verify response with event data
5. Test different options (format, date-range, etc.)

## Troubleshooting

### Plugin Not Loading

**Check:**
- Plugin is enabled in config.yaml
- python-villages-events directory exists
- Required dependencies are installed
- Check logs for import errors

### No Events Found

**This is normal when:**
- No events are scheduled for the selected filters
- Try broader filters (--date-range all, --category all)

### API Errors

**Check:**
- Internet connection
- The Villages API is accessible
- Timeout setting (increase if needed)
- Review logs for detailed errors

## Future Enhancements

Potential improvements for future versions:

1. **Caching** - Cache event data to reduce API calls
2. **Scheduled Updates** - Automatically fetch and broadcast daily events
3. **Subscriptions** - Allow users to subscribe to specific categories
4. **Notifications** - Alert users about new events
5. **Favorites** - Save favorite venues or event types
6. **Calendar Integration** - Export to iCal format

## Documentation

- **Plugin README**: `plugins/villages_events_service/README.md`
- **Quick Reference**: `docs/VILLAGES_EVENTS_QUICK_REFERENCE.md`
- **Usage Examples**: `examples/villages_events_example.py`
- **Config Example**: `config/config-example.yaml`
- **Villages Events Project**: `python-villages-events/README.md`

## Support

For issues or questions:

1. Check the plugin README
2. Review the quick reference guide
3. Check ZephyrGate logs
4. Verify python-villages-events is present
5. Test The Villages API accessibility

## License

GPL-3.0 (matching the python-villages-events project)

## Credits

- Based on the `python-villages-events` project
- Integrated into ZephyrGate by the ZephyrGate Team
- The Villages for providing the public API

---

**Plugin Version**: 1.0.0  
**ZephyrGate Version**: 1.0.0+  
**Created**: 2026-02-06  
**Status**: ✅ Ready for use
