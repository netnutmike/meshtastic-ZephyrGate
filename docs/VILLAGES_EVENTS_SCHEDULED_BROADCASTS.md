# Villages Events - Scheduled Broadcasts Guide

Complete guide for using the Villages Events Service plugin with ZephyrGate's scheduled broadcasts feature.

## Overview

The Villages Events Service plugin can be integrated with ZephyrGate's scheduled broadcasts system to automatically send event updates at specified times. This is similar to how the weather plugin sends automated weather forecasts.

## Quick Start

### 1. Enable the Plugin

First, enable the Villages Events plugin in `config/config.yaml`:

```yaml
plugins:
  villages_events_service:
    enabled: true
```

### 2. Add Scheduled Broadcast

Add a scheduled broadcast configuration under `scheduled_broadcasts`:

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

### 3. Restart ZephyrGate

Restart ZephyrGate to load the new configuration.

## Plugin Method

The plugin exposes the `get_events_report` method for scheduled broadcasts:

```python
async def get_events_report(
    user_id: str = 'system',
    format_type: str = None,
    date_range: str = None,
    category: str = None,
    location: str = None
) -> str
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | string | Yes | 'system' | User ID for logging |
| `format_type` | string | No | Config default | Output format (meshtastic, json, csv, plain) |
| `date_range` | string | No | Config default | Date range filter |
| `category` | string | No | Config default | Category filter |
| `location` | string | No | Config default | Location filter |

### Return Value

Returns a formatted string containing the events data, ready to be broadcast.

## Configuration Examples

### Daily Updates

#### Morning Events (7 AM)
```yaml
- name: "Morning Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
    category: "entertainment"
    location: "town-squares"
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  priority: "normal"
  enabled: true
```

#### Evening Update (5 PM)
```yaml
- name: "Evening Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "plain"
    date_range: "today"
    category: "entertainment"
    location: "town-squares"
  schedule_type: "cron"
  cron_expression: "0 17 * * *"
  channel: 0
  priority: "normal"
  enabled: true
```

### Weekly Updates

#### Monday Morning Summary
```yaml
- name: "Weekly Events Summary"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "json"
    date_range: "this-week"
    category: "all"
    location: "town-squares"
  schedule_type: "cron"
  cron_expression: "0 8 * * 1"  # Monday at 8 AM
  channel: 0
  priority: "normal"
  enabled: true
```

#### Friday Weekend Preview
```yaml
- name: "Weekend Preview"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "plain"
    date_range: "this-week"
    category: "entertainment"
    location: "town-squares"
  schedule_type: "cron"
  cron_expression: "0 15 * * 5"  # Friday at 3 PM
  channel: 0
  priority: "normal"
  enabled: true
```

### Category-Specific Updates

#### Daily Sports Events
```yaml
- name: "Daily Sports"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
    category: "sports"
    location: "all"
  schedule_type: "cron"
  cron_expression: "0 6 * * *"  # 6 AM daily
  channel: 0
  priority: "normal"
  enabled: true
```

#### Weekly Arts & Crafts
```yaml
- name: "Weekly Arts"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "plain"
    date_range: "this-week"
    category: "arts-and-crafts"
    location: "all"
  schedule_type: "cron"
  cron_expression: "0 9 * * 1"  # Monday at 9 AM
  channel: 0
  priority: "low"
  enabled: true
```

### Location-Specific Updates

#### Brownwood Daily Events
```yaml
- name: "Brownwood Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
    category: "all"
    location: "Brownwood+Paddock+Square"
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  priority: "normal"
  enabled: true
```

#### Spanish Springs Daily Events
```yaml
- name: "Spanish Springs Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
    category: "all"
    location: "Spanish+Springs+Town+Square"
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  priority: "normal"
  enabled: true
```

### Advanced Schedules

#### Multiple Daily Updates
```yaml
# Morning
- name: "Events - Morning"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
  schedule_type: "cron"
  cron_expression: "0 7 * * *"
  channel: 0
  priority: "normal"
  enabled: true

# Afternoon
- name: "Events - Afternoon"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
  schedule_type: "cron"
  cron_expression: "0 14 * * *"
  channel: 0
  priority: "normal"
  enabled: true

# Evening
- name: "Events - Evening"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "meshtastic"
    date_range: "today"
  schedule_type: "cron"
  cron_expression: "0 18 * * *"
  channel: 0
  priority: "normal"
  enabled: true
```

#### Tomorrow's Events Preview
```yaml
- name: "Tomorrow's Events"
  plugin_name: "villages_events_service"
  plugin_method: "get_events_report"
  plugin_args:
    user_id: "system"
    format_type: "plain"
    date_range: "tomorrow"
    category: "all"
    location: "town-squares"
  schedule_type: "cron"
  cron_expression: "0 20 * * *"  # 8 PM daily
  channel: 0
  priority: "normal"
  enabled: true
```

## Cron Expression Reference

Cron expressions use the format: `minute hour day month day_of_week`

### Common Patterns

| Expression | Description |
|------------|-------------|
| `0 7 * * *` | Every day at 7:00 AM |
| `0 7 * * 1` | Every Monday at 7:00 AM |
| `0 7 * * 1-5` | Every weekday at 7:00 AM |
| `0 7 * * 0,6` | Every weekend at 7:00 AM |
| `0 7,14,18 * * *` | Every day at 7 AM, 2 PM, and 6 PM |
| `0 */2 * * *` | Every 2 hours |
| `30 8 1 * *` | 8:30 AM on the 1st of every month |
| `0 8 * * 1` | Every Monday at 8:00 AM |
| `0 15 * * 5` | Every Friday at 3:00 PM |
| `0 20 * * 0` | Every Sunday at 8:00 PM |

### Time Examples

| Time | Expression |
|------|------------|
| 6:00 AM | `0 6 * * *` |
| 7:00 AM | `0 7 * * *` |
| 8:00 AM | `0 8 * * *` |
| 12:00 PM | `0 12 * * *` |
| 2:00 PM | `0 14 * * *` |
| 5:00 PM | `0 17 * * *` |
| 6:00 PM | `0 18 * * *` |
| 8:00 PM | `0 20 * * *` |

## Output Format Considerations

### Meshtastic Format (Recommended for Mesh Networks)

**Pros:**
- Most compact format
- Minimal bandwidth usage
- Fast transmission

**Cons:**
- Less human-readable
- Limited information

**Best for:**
- Daily updates on mesh networks
- Bandwidth-constrained environments
- Quick event summaries

**Example output:**
```
BW,John Doe Band#SS,Jane Smith#SG,The Band#
```

### Plain Text Format

**Pros:**
- Human-readable
- Clear and easy to understand
- Good for detailed information

**Cons:**
- Larger message size
- More bandwidth usage

**Best for:**
- Weekly summaries
- Detailed event information
- Non-bandwidth-constrained channels

**Example output:**
```
location.title: BW, title: John Doe Band
location.title: SS, title: Jane Smith
```

### JSON Format

**Pros:**
- Structured data
- Machine-readable
- Complete information

**Cons:**
- Largest message size
- Most bandwidth usage

**Best for:**
- Integration with other systems
- Data processing
- Archival purposes

**Example output:**
```json
[
  {"location.title": "BW", "title": "John Doe Band"},
  {"location.title": "SS", "title": "Jane Smith"}
]
```

### CSV Format

**Pros:**
- Spreadsheet-compatible
- Structured data
- Moderate size

**Cons:**
- Moderate bandwidth usage
- Less human-readable than plain text

**Best for:**
- Data export
- Spreadsheet import
- Structured logging

**Example output:**
```
location.title,title
BW,John Doe Band
SS,Jane Smith
```

## Best Practices

### 1. Choose Appropriate Schedules

- **Daily updates**: 7 AM for morning events, 5-8 PM for evening previews
- **Weekly summaries**: Monday morning for week ahead
- **Weekend previews**: Friday afternoon
- **Category-specific**: Match schedule to event type (sports early morning, arts mid-morning)

### 2. Select Optimal Formats

- Use **meshtastic** format for daily updates on mesh networks
- Use **plain** format for weekly summaries
- Use **json** format for integration with other systems
- Consider bandwidth when choosing format

### 3. Manage Broadcast Frequency

- Avoid too frequent updates (hourly may be excessive)
- Consider your audience's needs
- Monitor mesh network congestion
- Adjust based on feedback

### 4. Use Appropriate Priorities

- **high**: Emergency or critical events
- **normal**: Daily updates, important summaries
- **low**: Weekly summaries, optional information

### 5. Test Before Production

- Start with `enabled: false` and test manually
- Use short intervals for initial testing
- Monitor logs for errors
- Verify output format and content
- Adjust schedule and format as needed

## Troubleshooting

### Broadcast Not Sending

**Check:**
1. Plugin is enabled: `villages_events_service.enabled: true`
2. Scheduled broadcasts are enabled: `scheduled_broadcasts.enabled: true`
3. Specific broadcast is enabled: `enabled: true`
4. Cron expression is valid
5. Check logs for errors

### Empty or No Events

**This is normal when:**
- No events are scheduled for the selected filters
- API returns empty results

**Solutions:**
- Use broader filters (`date_range: this-week`, `category: all`)
- Check The Villages calendar manually
- Verify API is accessible

### Format Issues

**Check:**
- `format_type` is valid (meshtastic, json, csv, plain)
- Output fields are configured correctly
- Venue mappings are set up

### API Errors

**Check:**
- Internet connection
- The Villages API is accessible
- Timeout setting (increase if needed)
- Review logs for detailed errors

## Monitoring

### Check Logs

Monitor ZephyrGate logs for scheduled broadcast execution:

```bash
tail -f logs/zephyrgate.log | grep "villages_events"
```

### Verify Broadcasts

Check that broadcasts are being sent:
- Monitor mesh network for messages
- Check web interface for sent messages
- Review logs for successful executions

### Adjust as Needed

Based on monitoring:
- Adjust schedule times
- Change output format
- Modify filters
- Update priorities

## Examples File

See `examples/villages_events_scheduled_broadcasts.yaml` for a comprehensive collection of example configurations including:

- Daily morning/evening updates
- Weekly summaries
- Category-specific broadcasts
- Location-specific broadcasts
- Multiple daily updates
- Tomorrow's events preview
- Next week's events preview

## See Also

- [Scheduled Broadcasts Guide](SCHEDULED_BROADCASTS_GUIDE.md) - General scheduled broadcasts documentation
- [Villages Events Quick Reference](VILLAGES_EVENTS_QUICK_REFERENCE.md) - Plugin command reference
- [Plugin README](../plugins/villages_events_service/README.md) - Plugin documentation
- [YAML Configuration Guide](YAML_CONFIGURATION_GUIDE.md) - YAML configuration details

## Support

For issues or questions:
1. Check this guide for configuration examples
2. Review the scheduled broadcasts guide
3. Check ZephyrGate logs for errors
4. Verify plugin is enabled and working
5. Test manually with `villages-events` command first
