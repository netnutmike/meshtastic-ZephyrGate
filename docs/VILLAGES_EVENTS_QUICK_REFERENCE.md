# Villages Events Service - Quick Reference

Quick reference guide for the Villages Events Service plugin.

## Overview

The Villages Events Service plugin fetches entertainment events from The Villages community calendar (Florida) and provides formatted event data over Meshtastic or other communication channels.

**Note:** This is a location-specific plugin for The Villages, FL area. It's disabled by default.

## Quick Start

### 1. Enable the Plugin

Add to `config/config.yaml`:

```yaml
plugins:
  villages_events_service:
    enabled: true
```

### 2. Basic Commands

```
villages-events                    # Get today's events (default format)
villages-help                      # Show help message
```

## Command Reference

### villages-events

Fetch events from The Villages calendar.

**Syntax:**
```
villages-events [--format FORMAT] [--date-range RANGE] [--category CATEGORY] [--location LOCATION]
```

**Options:**

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--format` | meshtastic, json, csv, plain | meshtastic | Output format |
| `--date-range` | today, tomorrow, this-week, next-week, this-month, next-month, all | today | Date range filter |
| `--category` | entertainment, arts-and-crafts, health-and-wellness, recreation, social-clubs, special-events, sports, all | entertainment | Event category |
| `--location` | town-squares, all, or specific location | town-squares | Event location |

**Examples:**

```bash
# Today's events (default)
villages-events

# This week's events in JSON
villages-events --format json --date-range this-week

# Sports events at Brownwood
villages-events --category sports --location Brownwood+Paddock+Square

# All events, all categories, all locations
villages-events --date-range all --category all --location all --format json
```

### villages-help

Show help message with available commands and options.

**Syntax:**
```
villages-help
```

## Output Formats

### Meshtastic (Default)
Compact format optimized for Meshtastic messaging:
```
BW,John Doe Band#SS,Jane Smith#SG,The Band#
```
Format: `venue,title#venue,title#`

### JSON
Structured JSON array:
```json
[
  {"location.title": "BW", "title": "John Doe Band"},
  {"location.title": "SS", "title": "Jane Smith"}
]
```

### CSV
Comma-separated values with headers:
```
location.title,title
BW,John Doe Band
SS,Jane Smith
```

### Plain Text
Human-readable format:
```
location.title: BW, title: John Doe Band
location.title: SS, title: Jane Smith
```

## Date Ranges

| Value | Description |
|-------|-------------|
| `today` | Today's events (default) |
| `tomorrow` | Tomorrow's events |
| `this-week` | This week's events |
| `next-week` | Next week's events |
| `this-month` | This month's events |
| `next-month` | Next month's events |
| `all` | All events (no date filter) |

## Categories

| Value | Description |
|-------|-------------|
| `entertainment` | Entertainment events (default) |
| `arts-and-crafts` | Arts and crafts events |
| `health-and-wellness` | Health and wellness events |
| `recreation` | Recreation events |
| `social-clubs` | Social club events |
| `special-events` | Special events |
| `sports` | Sports events |
| `all` | All categories |

## Locations

| Value | Description |
|-------|-------------|
| `town-squares` | All town squares (default) |
| `Brownwood+Paddock+Square` | Brownwood Paddock Square |
| `Spanish+Springs+Town+Square` | Spanish Springs Town Square |
| `Lake+Sumter+Landing+Market+Square` | Lake Sumter Landing |
| `Sawgrass+Grove` | Sawgrass Grove |
| `The+Sharon` | The Sharon |
| `sports-recreation` | Sports & recreation venues |
| `all` | All locations |

## Configuration

### Basic Configuration

```yaml
plugins:
  villages_events_service:
    enabled: true
    format: meshtastic
    date_range: today
    category: entertainment
    location: town-squares
```

### Advanced Configuration

```yaml
plugins:
  villages_events_service:
    enabled: true
    format: json
    date_range: this-week
    category: all
    location: all
    timeout: 10
    
    # Customize venue abbreviations
    venue_mappings:
      Brownwood: BW
      Sawgrass: SG
      Spanish Springs: SS
      Lake Sumter: LS
    
    # Customize output fields
    output_fields:
      - location.title
      - title
      - start.date
```

### Available Output Fields

| Field | Description |
|-------|-------------|
| `title` | Event title |
| `description` | Full event description |
| `excerpt` | Short event description |
| `category` | Event category |
| `start.date` | Event start date/time |
| `end.date` | Event end date/time |
| `location.title` | Venue name (abbreviated) |
| `location.category` | Venue category |
| `address.streetAddress` | Street address |
| `address.locality` | City/locality |
| `url` | Event URL |

## Common Use Cases

### Daily Morning Events
```
villages-events --format plain
```

### Weekly Event Summary
```
villages-events --date-range this-week --format json
```

### Sports Schedule
```
villages-events --category sports --date-range this-week
```

### Specific Venue Events
```
villages-events --location Brownwood+Paddock+Square --date-range today
```

### All Upcoming Events
```
villages-events --date-range all --category all --location all --format json
```

## Troubleshooting

### Plugin Not Loading

**Problem:** Plugin doesn't appear in plugin list

**Solutions:**
1. Check `enabled: true` in config
2. Verify `python-villages-events` directory exists
3. Check logs for import errors
4. Ensure `requests` and `pyyaml` are installed

### No Events Found

**Problem:** Empty output or "No events found" message

**Solutions:**
1. This is normal when no events are scheduled
2. Try different date ranges: `--date-range this-week`
3. Try different categories: `--category all`
4. Try different locations: `--location all`

### API Errors

**Problem:** "Error fetching events" message

**Solutions:**
1. Check internet connection
2. Verify The Villages API is accessible
3. Check timeout setting (increase if needed)
4. Review logs for detailed error messages

### Invalid Arguments

**Problem:** "Invalid format/date-range/category/location" error

**Solutions:**
1. Check spelling of option values
2. Use `villages-help` to see valid options
3. Refer to this quick reference for valid values

## Tips

1. **Start Simple:** Use default settings first, then customize
2. **Test Formats:** Try different formats to see what works best
3. **Use Filters:** Combine date-range, category, and location for specific results
4. **Check Logs:** Review logs for detailed error information
5. **Customize Output:** Adjust `output_fields` for your needs

## See Also

- [Plugin README](../plugins/villages_events_service/README.md) - Detailed plugin documentation
- [Villages Events Project](../python-villages-events/README.md) - Underlying project documentation
- [Plugin Development Guide](PLUGIN_DEVELOPMENT.md) - Creating custom plugins
- [Configuration Guide](YAML_CONFIGURATION_GUIDE.md) - YAML configuration details

## Support

For issues or questions:
1. Check this quick reference
2. Review the plugin README
3. Check ZephyrGate logs
4. Verify The Villages API is accessible
5. Review python-villages-events documentation
