#!/usr/bin/env python3
"""
Villages Events Service Plugin Example

This example demonstrates how to use the Villages Events Service plugin
to fetch and display events from The Villages community calendar.

The plugin integrates the python-villages-events project into ZephyrGate,
allowing users to query events through Meshtastic messages.

Usage Examples:
    # Basic usage (uses defaults from config)
    villages-events
    
    # Get this week's events in JSON format
    villages-events --format json --date-range this-week
    
    # Get sports events at a specific location
    villages-events --category sports --location Brownwood+Paddock+Square
    
    # Get help
    villages-help

Configuration:
    Add to config/config.yaml:
    
    plugins:
      villages_events_service:
        enabled: true
        format: meshtastic
        date_range: today
        category: entertainment
        location: town-squares
        venue_mappings:
          Brownwood: BW
          Sawgrass: SG
          Spanish Springs: SS
          Lake Sumter: LS
        output_fields:
          - location.title
          - title

Output Formats:
    - meshtastic: Compact format for Meshtastic (venue,title#venue,title#)
    - json: Structured JSON array
    - csv: Comma-separated values with headers
    - plain: Human-readable plain text

Date Ranges:
    - today: Today's events (default)
    - tomorrow: Tomorrow's events
    - this-week: This week's events
    - next-week: Next week's events
    - this-month: This month's events
    - next-month: Next month's events
    - all: All events (no date filter)

Categories:
    - entertainment: Entertainment events (default)
    - arts-and-crafts: Arts and crafts events
    - health-and-wellness: Health and wellness events
    - recreation: Recreation events
    - social-clubs: Social club events
    - special-events: Special events
    - sports: Sports events
    - all: All categories

Locations:
    - town-squares: All town squares (default)
    - Brownwood+Paddock+Square: Brownwood Paddock Square
    - Spanish+Springs+Town+Square: Spanish Springs Town Square
    - Lake+Sumter+Landing+Market+Square: Lake Sumter Landing
    - Sawgrass+Grove: Sawgrass Grove
    - The+Sharon: The Sharon
    - sports-recreation: Sports & recreation venues
    - all: All locations

Example Responses:
    
    Meshtastic format (compact):
    >>> villages-events
    BW,John Doe Band#SS,Jane Smith#SG,The Band#
    
    JSON format (detailed):
    >>> villages-events --format json
    [
      {
        "location.title": "BW",
        "title": "John Doe Band"
      },
      {
        "location.title": "SS",
        "title": "Jane Smith"
      }
    ]
    
    Plain text format (readable):
    >>> villages-events --format plain
    location.title: BW, title: John Doe Band
    location.title: SS, title: Jane Smith

Notes:
    - This plugin is location-specific to The Villages, FL
    - It's disabled by default in the configuration
    - Requires the python-villages-events project to be present
    - Requires 'requests' and 'pyyaml' Python packages

See Also:
    - plugins/villages_events_service/README.md - Plugin documentation
    - python-villages-events/README.md - Villages Events project documentation
    - docs/PLUGIN_DEVELOPMENT.md - Plugin development guide
"""

# This is a documentation file showing usage examples.
# The actual plugin implementation is in plugins/villages_events_service/plugin.py

if __name__ == "__main__":
    print(__doc__)
