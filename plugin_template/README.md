# ZephyrGate Plugin Template

This directory contains templates used by the `create_plugin.py` script to generate new plugins.

## Template Files

- `__init__.py.template` - Plugin package initialization
- `plugin.py.template` - Main plugin class implementation
- `manifest.yaml.template` - Plugin metadata and capabilities
- `config_schema.json.template` - Configuration schema
- `README.md.template` - Plugin documentation
- `requirements.txt.template` - Python dependencies
- `handlers/` - Command and message handler templates
- `tasks/` - Scheduled task templates
- `utils/` - Utility function templates
- `tests/` - Test templates

## Template Syntax

Templates support the following placeholders:

### Simple Variables

`{{variable_name}}` - Replaced with the value from the variables dictionary

### Conditional Blocks

`{{#if variable_name}}...{{/if}}` - Content is included only if variable is truthy

Conditional blocks support nesting.

## Available Variables

- `plugin_name` - Plugin name (lowercase with underscores)
- `plugin_class` - Plugin class name (PascalCase)
- `plugin_description` - Plugin description
- `plugin_author` - Plugin author name
- `plugin_email` - Plugin author email (optional)
- `plugin_version` - Plugin version
- `plugin_license` - Plugin license
- `current_year` - Current year
- `has_commands` - Whether plugin includes command handlers
- `has_scheduled_tasks` - Whether plugin includes scheduled tasks
- `has_menu_items` - Whether plugin includes BBS menu items
- `has_http` - Whether plugin includes HTTP client utilities
- `has_storage` - Whether plugin includes data storage

## Customizing Templates

To customize the generated plugins:

1. Edit the template files in this directory
2. Use `{{variable_name}}` for values that should be replaced
3. Use `{{#if feature}}...{{/if}}` for optional sections
4. Test your changes by generating a plugin with `create_plugin.py`

## Example

```python
# In template:
{{#if has_commands}}
def handle_command(self, args):
    return f"Hello from {{plugin_name}}!"
{{/if}}

# Generated output (with has_commands=true, plugin_name="my_plugin"):
def handle_command(self, args):
    return f"Hello from my_plugin!"
```
