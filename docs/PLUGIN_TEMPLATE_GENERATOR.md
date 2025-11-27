# Plugin Template Generator

The ZephyrGate Plugin Template Generator (`create_plugin.py`) is a command-line tool that generates a complete plugin structure from templates, making it easy to start developing new plugins.

## Quick Start

Generate a basic plugin:

```bash
python create_plugin.py my_plugin --author "Your Name"
```

Generate a plugin with specific features:

```bash
python create_plugin.py weather_bot \
  --author "Jane Smith" \
  --email "jane@example.com" \
  --description "Fetch and broadcast weather data" \
  --commands \
  --scheduled-tasks \
  --http \
  --storage
```

Generate a plugin with all features:

```bash
python create_plugin.py full_featured \
  --author "Dev Team" \
  --all-features
```

## Command-Line Options

### Required Arguments

- `name` - Plugin name (lowercase, alphanumeric, underscores only)
- `--author` - Plugin author name

### Optional Arguments

- `--email` - Plugin author email
- `--description` - Plugin description
- `--version` - Plugin version (default: 1.0.0)
- `--license` - Plugin license (default: MIT)
- `--output` - Output directory for plugin (default: plugins)

### Feature Flags

Include specific features in your plugin:

- `--commands` - Include command handler support
- `--scheduled-tasks` - Include scheduled task support
- `--menu-items` - Include BBS menu integration
- `--http` - Include HTTP client utilities
- `--storage` - Include data storage support
- `--all-features` - Include all available features

## Generated Structure

The generator creates the following directory structure:

```
my_plugin/
├── __init__.py              # Plugin package initialization
├── plugin.py                # Main plugin class
├── manifest.yaml            # Plugin metadata and capabilities
├── config_schema.json       # Configuration schema
├── README.md                # Plugin documentation
├── requirements.txt         # Python dependencies
├── handlers/                # Command and message handlers
│   ├── __init__.py
│   └── commands.py          # (if --commands specified)
├── tasks/                   # Scheduled tasks
│   ├── __init__.py
│   └── scheduled.py         # (if --scheduled-tasks specified)
├── utils/                   # Utility functions
│   └── __init__.py
└── tests/                   # Plugin tests
    ├── __init__.py
    └── test_plugin.py
```

## Generated Files

### plugin.py

The main plugin class that extends `EnhancedPlugin`. Includes:

- `initialize()` method with feature registration
- Command handlers (if `--commands` specified)
- Scheduled task handlers (if `--scheduled-tasks` specified)
- BBS menu handlers (if `--menu-items` specified)
- `shutdown()` method for cleanup
- `get_metadata()` method

### manifest.yaml

Plugin metadata including:

- Name, version, description, author
- ZephyrGate compatibility requirements
- Dependencies (plugins and Python packages)
- Declared capabilities (commands, tasks, menu items)
- Configuration defaults
- Required permissions

### config_schema.json

JSON Schema for plugin configuration validation. Includes schemas for:

- `enabled` - Enable/disable the plugin
- Feature-specific configuration options

### README.md

Complete plugin documentation with:

- Installation instructions
- Configuration options
- Usage examples
- Development guidelines

### tests/test_plugin.py

Basic unit tests for the plugin:

- Initialization tests
- Feature-specific tests
- Metadata validation

## Examples

### Weather Alert Plugin

```bash
python create_plugin.py weather_alerts \
  --author "John Doe" \
  --email "john@example.com" \
  --description "Fetch and broadcast weather alerts" \
  --commands \
  --scheduled-tasks \
  --http \
  --storage
```

This generates a plugin that can:
- Handle commands (e.g., `weather <location>`)
- Fetch data from weather APIs periodically
- Store cached weather data
- Send alerts to the mesh network

### Simple Command Plugin

```bash
python create_plugin.py hello_world \
  --author "Jane Smith" \
  --description "Simple greeting plugin" \
  --commands
```

This generates a minimal plugin with just command handling.

### BBS Menu Plugin

```bash
python create_plugin.py custom_menu \
  --author "Dev Team" \
  --description "Custom BBS menu integration" \
  --menu-items
```

This generates a plugin that adds custom menu items to the BBS system.

## Next Steps After Generation

1. **Review the generated files** - Familiarize yourself with the structure
2. **Edit manifest.yaml** - Add any dependencies your plugin needs
3. **Implement plugin logic** - Add your custom functionality to `plugin.py`
4. **Update configuration** - Modify `config_schema.json` for your needs
5. **Write tests** - Add tests in `tests/test_plugin.py`
6. **Install the plugin** - Copy to your plugins directory
7. **Enable in config** - Add to `enabled_plugins` in `config.yaml`

## Customizing Templates

The templates are located in the `plugin_template/` directory. You can customize them to match your preferences:

1. Edit template files in `plugin_template/`
2. Use `{{variable_name}}` for replaceable values
3. Use `{{#if feature}}...{{/if}}` for conditional sections
4. Test your changes by generating a plugin

See `plugin_template/README.md` for more details on template syntax.

## Validation

The generator validates:

- Plugin name format (lowercase, alphanumeric, underscores)
- Directory doesn't already exist
- All required arguments are provided

Generated files are:

- Syntactically valid Python code
- Valid YAML manifests
- Valid JSON schemas
- Ready to use without modification

## Troubleshooting

### "Invalid plugin name" error

Plugin names must:
- Start with a lowercase letter
- Contain only lowercase letters, numbers, and underscores
- Not contain spaces or special characters

Valid: `my_plugin`, `weather_bot`, `hello_world`
Invalid: `MyPlugin`, `weather-bot`, `Hello World`

### "Plugin directory already exists" error

The target directory already exists. Either:
- Choose a different plugin name
- Specify a different output directory with `--output`
- Remove the existing directory

### Generated plugin won't import

Make sure:
- The plugin directory is in your Python path
- All `__init__.py` files are present
- There are no syntax errors (run `python -m py_compile plugin.py`)

## See Also

- [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)
- [Enhanced Plugin API](ENHANCED_PLUGIN_API.md)
- [Plugin Examples](../examples/plugins/)
