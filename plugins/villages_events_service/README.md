# Villages Events Service Plugin

A ZephyrGate plugin that fetches entertainment events from The Villages API and provides formatted event data over Meshtastic or other communication channels.

## Overview

This plugin integrates the `python-villages-events` project into ZephyrGate, allowing users to query The Villages community events calendar through Meshtastic messages or other supported communication methods.

## Features

- Fetch events from The Villages calendar
- Multiple output formats: Meshtastic, JSON, CSV, Plain text
- Filter by date range (today, tomorrow, this week, next week, etc.)
- Filter by category (entertainment, sports, arts-and-crafts, etc.)
- Filter by location (town squares, specific venues, etc.)
- Customizable venue abbreviations
- Configurable output fields

## Installation

This plugin requires the `python-villages-events` project to be present in the repository root directory.

### Dependencies

The plugin requires the following Python packages:
- `requests` - HTTP library for API requests
- `pyyaml` - YAML parser for configuration

These should already be installed if you have the main ZephyrGate dependencies.

## Configuration

The plugin is **disabled by default** since it's specific to The Villages community in Florida. To enable it, add the following to your `config/config.yaml`:

```yaml
plugins:
  villages_events_service:
    enabled: true
    format: meshtastic          # Default output format
    date_range: today            # Default date range
    category: entertainment      # Default category
    location: town-squares       # Default location
    timeout: 10                  # HTTP timeout in seconds
    
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
```

### Configuration Options

#### Format Options
- `meshtastic` - Compact format optimized for Meshtastic (default)
- `json` - Structured JSON output
- `csv` - Comma-separated values with headers
- `plain` - Human-readable plain text

#### Date Range Options
- `today` - Today's events (default)
- `tomorrow` - Tomorrow's events
- `this-week` - This week's events
- `next-week` - Next week's events
- `this-month` - This month's events
- `next-month` - Next month's events
- `all` - All events (no date filter)

#### Category Options
- `entertainment` - Entertainment events (default)
- `arts-and-crafts` - Arts and crafts events
- `health-and-wellness` - Health and wellness events
- `recreation` - Recreation events
- `social-clubs` - Social club events
- `special-events` - Special events
- `sports` - Sports events
- `all` - All categories

#### Location Options
- `town-squares` - All town squares (default)
- `Brownwood+Paddock+Square` - Brownwood Paddock Square
- `Spanish+Springs+Town+Square` - Spanish Springs Town Square
- `Lake+Sumter+Landing+Market+Square` - Lake Sumter Landing
- `Sawgrass+Grove` - Sawgrass Grove
- `The+Sharon` - The Sharon
- `sports-recreation` - Sports & recreation venues
- `all` - All locations

See the manifest.yaml for the complete list of location options.

#### Output Fields

You can customize which fields from the API response are included in the output:

Available fields:
- `title` - Event title
- `description` - Full event description
- `excerpt` - Short event description
- `category` - Event category
- `start.date` - Event start date/time
- `end.date` - Event end date/time
- `location.title` - Venue name (abbreviated)
- `address.streetAddress` - Street address
- `address.locality` - City/locality
- `url` - Event URL
- And more (see python-villages-events documentation)

## Usage

### Basic Commands

**Fetch today's events (using defaults):**
```
villages-events
```

**Fetch events with custom format:**
```
villages-events --format json
```

**Fetch this week's events:**
```
villages-events --date-range this-week
```

**Fetch sports events:**
```
villages-events --category sports
```

**Fetch events at a specific location:**
```
villages-events --location Brownwood+Paddock+Square
```

**Combine multiple options:**
```
villages-events --format json --date-range next-week --category entertainment
```

### Get Help

```
villages-help
```

### Scheduled Broadcasts

The plugin can be used with ZephyrGate's scheduled broadcasts feature to automatically send event updates at specified times, just like the weather plugin.

**Example: Daily morning events at 7 AM**

Add to `config/config.yaml` under `scheduled_broadcasts`:

```yaml
scheduled_broadcasts:
  enabled: true
  broadcasts:
    - name: "Daily Villages Events"
      plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        user_id: "system"
        format_type: "meshtastic"
        date_range: "today"
        category: "entertainment"
        location: "town-squares"
      schedule_type: "cron"
      cron_expression: "0 7 * * *"  # 7 AM daily
      channel: 0
      priority: "normal"
      enabled: true
```

**Example: Weekly events summary every Monday**

```yaml
    - name: "Weekly Villages Events"
      plugin_name: "villages_events_service"
      plugin_method: "get_events_report"
      plugin_args:
        user_id: "system"
        format_type: "plain"
        date_range: "this-week"
        category: "all"
        location: "town-squares"
      schedule_type: "cron"
      cron_expression: "0 8 * * 1"  # 8 AM every Monday
      channel: 0
      priority: "normal"
      enabled: true
```

**See also:** `examples/villages_events_scheduled_broadcasts.yaml` for more examples including:
- Daily morning/evening updates
- Weekly summaries
- Category-specific broadcasts (sports, arts, etc.)
- Location-specific broadcasts
- Tomorrow's events preview
- Next week's events preview

## Examples

### Example 1: Quick Event Check
```
User: villages-events
Bot: Brownwood,John Doe Band#Spanish Springs,Jane Smith#Sawgrass,The Band#
```

### Example 2: This Week's Sports Events
```
User: villages-events --date-range this-week --category sports --format plain
Bot: location.title: Brownwood, title: Golf Tournament
location.title: Spanish Springs, title: Tennis Match
```

### Example 3: Detailed JSON Output
```
User: villages-events --format json --date-range tomorrow
Bot: [
  {
    "location.title": "Brownwood",
    "title": "Live Music Night"
  },
  {
    "location.title": "Spanish Springs",
    "title": "Dance Performance"
  }
]
```

## How It Works

The plugin follows this workflow:

1. **Token Extraction** - Fetches authentication token from The Villages CDN
2. **Session Establishment** - Creates HTTP session with proper cookies
3. **API Request** - Makes authenticated request to The Villages events API
4. **Event Processing** - Processes events and applies venue abbreviations
5. **Output Formatting** - Formats events according to selected format
6. **Message Response** - Returns formatted data to the user

## Troubleshooting

### Plugin Not Loading

If the plugin fails to load, check:
1. The `python-villages-events` directory exists in the repository root
2. The plugin is enabled in your configuration
3. Required dependencies (`requests`, `pyyaml`) are installed
4. Check logs for import errors

### No Events Found

This is normal when:
- No events are scheduled for the selected date range
- The category/location filters exclude all events

Try:
- Using `--date-range all` to see all upcoming events
- Using `--category all` and `--location all` to remove filters

### API Errors

If you see API errors:
1. Check your internet connection
2. Verify The Villages API is accessible
3. Check if the API structure has changed (see python-villages-events project)

## Development

### Project Structure

```
plugins/villages_events_service/
├── __init__.py          # Package initialization
├── plugin.py            # Main plugin implementation
├── manifest.yaml        # Plugin manifest
└── README.md           # This file
```

### Adding New Features

To add new features:
1. Modify `plugin.py` to add new commands or functionality
2. Update `manifest.yaml` to reflect new capabilities
3. Update this README with usage examples

## License

This plugin is licensed under GPL-3.0, matching the license of the python-villages-events project it integrates.

## Credits

- Based on the `python-villages-events` project
- Integrated into ZephyrGate by the ZephyrGate Team
- The Villages for providing the public API

## Support

For issues specific to this plugin, check:
1. This README for configuration and usage
2. The python-villages-events documentation for API details
3. ZephyrGate logs for error messages
4. The Villages API status if experiencing connectivity issues
