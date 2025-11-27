# Design Document: Third-Party Plugin System

## Overview

This design enhances ZephyrGate's existing plugin architecture to support third-party plugin development. The current system has a robust internal plugin infrastructure used by core services (weather, BBS, emergency, etc.). This enhancement will expose that infrastructure through well-defined APIs, add plugin discovery and validation mechanisms, and provide comprehensive developer documentation.

The design maintains backward compatibility with existing internal plugins while adding new capabilities for external developers. Key additions include:

- Plugin manifest system for metadata and dependency declaration
- Enhanced plugin discovery from external directories
- Developer-friendly base classes and utilities
- Comprehensive documentation and examples
- Plugin template generator
- Enhanced monitoring and error isolation

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ZephyrGate Core                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Plugin Manager (Enhanced)                  │ │
│  │  - Discovery  - Loading  - Lifecycle  - Health         │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Plugin API Layer (New)                     │ │
│  │  - Base Classes  - Utilities  - Interfaces             │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Core Services (Message Router, Database)        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│ Internal       │  │ Third-Party     │  │ Third-Party    │
│ Plugins        │  │ Plugin 1        │  │ Plugin 2       │
│ (Weather, BBS) │  │ (External Dir)  │  │ (External Dir) │
└────────────────┘  └─────────────────┘  └────────────────┘
```

### Plugin Directory Structure

```
plugins/
├── my_plugin/
│   ├── __init__.py           # Plugin entry point
│   ├── plugin.py             # Main plugin class
│   ├── manifest.yaml         # Plugin metadata
│   ├── config_schema.json    # Configuration schema
│   ├── handlers/             # Command/message handlers
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   └── messages.py
│   ├── tasks/                # Scheduled tasks
│   │   ├── __init__.py
│   │   └── scheduled.py
│   ├── utils/                # Plugin utilities
│   │   └── __init__.py
│   ├── tests/                # Plugin tests
│   │   └── test_plugin.py
│   ├── README.md             # Plugin documentation
│   └── requirements.txt      # Python dependencies
```

## Components and Interfaces

### 1. Plugin Manifest System

**Purpose**: Declare plugin metadata, dependencies, and capabilities

**Manifest Format** (manifest.yaml):
```yaml
name: my_plugin
version: 1.0.0
description: "Example plugin for ZephyrGate"
author: "Developer Name"
author_email: "dev@example.com"
license: "MIT"
homepage: "https://github.com/user/my_plugin"

# ZephyrGate compatibility
zephyrgate:
  min_version: "1.0.0"
  max_version: "2.0.0"

# Dependencies
dependencies:
  plugins:
    - name: weather
      version: ">=1.0.0"
      optional: false
    - name: bbs
      version: ">=1.0.0"
      optional: true
  python_packages:
    - requests>=2.28.0
    - aiohttp>=3.8.0

# Plugin capabilities
capabilities:
  commands:
    - name: mycommand
      description: "My custom command"
      usage: "mycommand [args]"
  scheduled_tasks:
    - name: hourly_update
      interval: 3600
  menu_items:
    - menu: utilities
      label: "My Plugin"
      command: myplugin

# Configuration
config:
  schema_file: "config_schema.json"
  defaults:
    enabled: true
    api_key: ""
    update_interval: 300

# Permissions required
permissions:
  - send_messages
  - database_access
  - http_requests
  - schedule_tasks
```

### 2. Enhanced Plugin Base Class

**Purpose**: Provide developer-friendly base class with common functionality

**Key Methods**:
- `register_command(command, handler, help_text)` - Register command handler
- `register_message_handler(handler, priority)` - Register message handler
- `register_scheduled_task(interval, handler)` - Register scheduled task
- `register_menu_item(menu, label, handler)` - Register BBS menu item
- `send_message(content, destination, channel)` - Send mesh message
- `get_config(key, default)` - Get configuration value
- `store_data(key, value, ttl)` - Store plugin data
- `retrieve_data(key, default)` - Retrieve plugin data
- `http_get(url, params, timeout)` - Make HTTP GET request
- `http_post(url, data, timeout)` - Make HTTP POST request
- `get_node_info(node_id)` - Get mesh node information
- `emit_event(event_type, data)` - Emit plugin event

### 3. Plugin Discovery and Loading

**Purpose**: Discover and load plugins from configured directories

**Discovery Process**:
1. Scan configured plugin directories
2. Look for directories containing `__init__.py` and `manifest.yaml`
3. Parse and validate manifest
4. Check ZephyrGate version compatibility
5. Verify dependencies
6. Load plugin module
7. Instantiate plugin class
8. Initialize plugin

**Configuration** (config.yaml):
```yaml
plugins:
  paths:
    - "plugins"
    - "/opt/zephyrgate/plugins"
    - "~/.zephyrgate/plugins"
  
  auto_discover: true
  auto_load: true
  
  enabled_plugins:
    - weather
    - bbs
    - my_plugin
  
  disabled_plugins:
    - experimental_plugin
```

### 4. Command Handler System

**Purpose**: Route commands to appropriate plugin handlers

**Implementation**:
```python
class PluginCommandHandler(BaseCommandHandler):
    """Enhanced command handler for plugins"""
    
    def __init__(self, plugin_name: str):
        super().__init__([])
        self.plugin_name = plugin_name
        self.command_handlers: Dict[str, Callable] = {}
        self.command_help: Dict[str, str] = {}
    
    def register_command(self, command: str, handler: Callable, 
                        help_text: str = "", priority: int = 100):
        """Register a command handler"""
        self.command_handlers[command.lower()] = handler
        self.command_help[command.lower()] = help_text
        if command not in self.commands:
            self.commands.append(command)
    
    async def handle_command(self, command: str, args: List[str], 
                           context: Dict[str, Any]) -> str:
        """Handle command"""
        if command in self.command_handlers:
            try:
                return await self.command_handlers[command](args, context)
            except Exception as e:
                self.logger.error(f"Error in command handler: {e}")
                return f"Error executing command: {str(e)}"
        return f"Unknown command: {command}"
```

### 5. Scheduled Task System

**Purpose**: Execute plugin tasks on schedules

**Implementation**:
```python
class PluginScheduler:
    """Scheduler for plugin tasks"""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running_tasks: Set[asyncio.Task] = set()
    
    def register_task(self, name: str, interval: int, 
                     handler: Callable, cron: str = None):
        """Register a scheduled task"""
        task = ScheduledTask(
            name=name,
            plugin=self.plugin_name,
            interval=interval,
            cron=cron,
            handler=handler
        )
        self.tasks[name] = task
    
    async def start_all(self):
        """Start all scheduled tasks"""
        for task in self.tasks.values():
            asyncio_task = asyncio.create_task(self._run_task(task))
            self.running_tasks.add(asyncio_task)
    
    async def _run_task(self, task: ScheduledTask):
        """Run a scheduled task"""
        while True:
            try:
                await task.handler()
                await asyncio.sleep(task.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduled task: {e}")
                await asyncio.sleep(task.interval)
```

### 6. BBS Menu Integration

**Purpose**: Allow plugins to add menu items to BBS

**Implementation**:
```python
class PluginMenuRegistry:
    """Registry for plugin menu items"""
    
    def __init__(self):
        self.menu_items: Dict[MenuType, List[PluginMenuItem]] = {}
    
    def register_menu_item(self, plugin_name: str, menu: MenuType,
                          label: str, command: str, handler: Callable,
                          description: str = "", admin_only: bool = False):
        """Register a plugin menu item"""
        item = PluginMenuItem(
            plugin=plugin_name,
            menu=menu,
            label=label,
            command=command,
            handler=handler,
            description=description,
            admin_only=admin_only
        )
        
        if menu not in self.menu_items:
            self.menu_items[menu] = []
        self.menu_items[menu].append(item)
    
    def get_menu_items(self, menu: MenuType) -> List[PluginMenuItem]:
        """Get menu items for a specific menu"""
        return self.menu_items.get(menu, [])
```

### 7. HTTP Client Utilities

**Purpose**: Provide HTTP client with rate limiting and error handling

**Implementation**:
```python
class PluginHTTPClient:
    """HTTP client for plugins with rate limiting"""
    
    def __init__(self, plugin_name: str, rate_limit: int = 100):
        self.plugin_name = plugin_name
        self.rate_limiter = RateLimiter(rate_limit)
        self.session = aiohttp.ClientSession()
    
    async def get(self, url: str, params: Dict = None, 
                 timeout: int = 30, headers: Dict = None) -> Dict:
        """Make HTTP GET request"""
        if not await self.rate_limiter.acquire():
            raise RateLimitExceeded("HTTP rate limit exceeded")
        
        try:
            async with self.session.get(url, params=params, 
                                       timeout=timeout, 
                                       headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise HTTPRequestError(f"HTTP request failed: {e}")
    
    async def post(self, url: str, data: Dict = None, 
                  timeout: int = 30, headers: Dict = None) -> Dict:
        """Make HTTP POST request"""
        if not await self.rate_limiter.acquire():
            raise RateLimitExceeded("HTTP rate limit exceeded")
        
        try:
            async with self.session.post(url, json=data, 
                                        timeout=timeout,
                                        headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise HTTPRequestError(f"HTTP request failed: {e}")
```

### 8. Plugin Storage Interface

**Purpose**: Provide key-value storage for plugin data

**Implementation**:
```python
class PluginStorage:
    """Storage interface for plugins"""
    
    def __init__(self, plugin_name: str, db_manager: DatabaseManager):
        self.plugin_name = plugin_name
        self.db = db_manager
        self._init_storage()
    
    def _init_storage(self):
        """Initialize plugin storage table"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS plugin_storage (
                plugin_name TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (plugin_name, key)
            )
        """)
    
    async def store(self, key: str, value: Any, ttl: int = None):
        """Store data with optional TTL"""
        expires_at = None
        if ttl:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        value_json = json.dumps(value)
        
        await self.db.execute("""
            INSERT OR REPLACE INTO plugin_storage 
            (plugin_name, key, value, expires_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (self.plugin_name, key, value_json, expires_at))
    
    async def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve stored data"""
        row = await self.db.fetch_one("""
            SELECT value, expires_at FROM plugin_storage
            WHERE plugin_name = ? AND key = ?
        """, (self.plugin_name, key))
        
        if not row:
            return default
        
        # Check expiration
        if row['expires_at'] and datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
            await self.delete(key)
            return default
        
        return json.loads(row['value'])
    
    async def delete(self, key: str) -> bool:
        """Delete stored data"""
        result = await self.db.execute("""
            DELETE FROM plugin_storage
            WHERE plugin_name = ? AND key = ?
        """, (self.plugin_name, key))
        return result.rowcount > 0
```

## Data Models

### Plugin Manifest Model

```python
@dataclass
class PluginManifest:
    """Plugin manifest data model"""
    name: str
    version: str
    description: str
    author: str
    author_email: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    
    # Compatibility
    min_zephyrgate_version: Optional[str] = None
    max_zephyrgate_version: Optional[str] = None
    
    # Dependencies
    plugin_dependencies: List[PluginDependency] = field(default_factory=list)
    python_dependencies: List[str] = field(default_factory=list)
    
    # Capabilities
    commands: List[CommandCapability] = field(default_factory=list)
    scheduled_tasks: List[TaskCapability] = field(default_factory=list)
    menu_items: List[MenuCapability] = field(default_factory=list)
    
    # Configuration
    config_schema_file: Optional[str] = None
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Permissions
    permissions: List[str] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'PluginManifest':
        """Load manifest from YAML file"""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate manifest and return list of errors"""
        errors = []
        
        if not self.name:
            errors.append("Plugin name is required")
        if not self.version:
            errors.append("Plugin version is required")
        if not self.description:
            errors.append("Plugin description is required")
        
        # Validate version format
        if self.version and not re.match(r'^\d+\.\d+\.\d+', self.version):
            errors.append("Invalid version format (use semver)")
        
        return errors
```

### Plugin Context Model

```python
@dataclass
class PluginContext:
    """Context provided to plugin handlers"""
    plugin_name: str
    message: Optional[Message] = None
    sender_id: Optional[str] = None
    sender_profile: Optional[UserProfile] = None
    channel: Optional[str] = None
    is_dm: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_data: Dict[str, Any] = field(default_factory=dict)
    
    def get_sender_name(self) -> str:
        """Get sender display name"""
        if self.sender_profile:
            return self.sender_profile.display_name or self.sender_profile.node_id
        return self.sender_id or "Unknown"
```

### Scheduled Task Model

```python
@dataclass
class ScheduledTask:
    """Scheduled task definition"""
    name: str
    plugin: str
    interval: Optional[int] = None  # seconds
    cron: Optional[str] = None  # cron expression
    handler: Callable = None
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
```

### Plugin Menu Item Model

```python
@dataclass
class PluginMenuItem:
    """Plugin menu item definition"""
    plugin: str
    menu: MenuType
    label: str
    command: str
    handler: Callable
    description: str = ""
    admin_only: bool = False
    enabled: bool = True
    order: int = 100  # Display order
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property Reflection

After reviewing all identified testable properties, several can be consolidated:

- Properties 1.2, 1.3, 1.4, 1.5 all relate to command routing and can be combined into comprehensive command handling properties
- Properties 2.1-2.5 all relate to menu system integration and can be consolidated
- Properties 3.1, 3.2, 3.4, 3.5 relate to scheduled task execution and can be combined
- Properties 7.2, 7.3, 7.4, 7.5 relate to plugin lifecycle management and can be consolidated
- Properties 8.1, 8.3, 8.4, 8.5 relate to configuration validation and can be combined
- Properties 12.1-12.5 all relate to error isolation and can be consolidated into comprehensive error handling properties

This consolidation reduces redundancy while maintaining comprehensive coverage of all requirements.

### Correctness Properties

Property 1: Command routing completeness
*For any* command registered by a plugin, when a message containing that command is received, the Plugin System should route the message to that plugin's command handler with complete context (sender, channel, timestamp).
**Validates: Requirements 1.2, 1.4**

Property 2: Command priority ordering
*For any* set of plugins registering the same command with different priorities, the Plugin System should execute handlers in priority order (lowest priority value first).
**Validates: Requirements 1.3**

Property 3: Message sending capability
*For any* plugin command handler or scheduled task, calling the send_message method should successfully queue the message for delivery to the mesh network.
**Validates: Requirements 1.5, 3.2**

Property 4: Menu item registration
*For any* menu item registered by a plugin, querying that menu should return the item in the results with correct label, command, and handler reference.
**Validates: Requirements 2.1**

Property 5: Menu handler routing
*For any* registered menu item, when a user selects that item, the BBS System should invoke the plugin's menu handler with user and session context.
**Validates: Requirements 2.2, 2.4**

Property 6: Menu item lifecycle
*For any* registered menu item, calling the removal method should result in the item no longer appearing in subsequent menu queries.
**Validates: Requirements 2.5**

Property 7: Scheduled task execution
*For any* scheduled task with an interval, the task should execute at approximately that interval (within 10% tolerance), and failures should not prevent future executions.
**Validates: Requirements 3.1, 3.4**

Property 8: Task cancellation on plugin stop
*For any* plugin with scheduled tasks, stopping the plugin should cancel all tasks such that no further executions occur.
**Validates: Requirements 3.5**

Property 9: HTTP client error handling
*For any* HTTP request that encounters a network error (timeout, connection refused, etc.), the HTTP client should return an error result rather than raising an unhandled exception.
**Validates: Requirements 4.3**

Property 10: Rate limiting enforcement
*For any* sequence of HTTP requests from a plugin exceeding the rate limit, subsequent requests should be rejected until the rate limit window resets.
**Validates: Requirements 4.5**

Property 11: Plugin discovery
*For any* directory path containing a valid plugin (with __init__.py and manifest.yaml), the discovery process should identify and list that plugin.
**Validates: Requirements 7.1**

Property 12: Dependency validation
*For any* plugin with declared dependencies, the Plugin System should verify all required dependencies are available before allowing the plugin to load, and should report any missing dependencies.
**Validates: Requirements 7.2, 7.3**

Property 13: Dynamic plugin lifecycle
*For any* valid plugin, enabling it should load and start the plugin without system restart, and disabling it should stop and unload the plugin gracefully with all resources cleaned up.
**Validates: Requirements 7.4, 7.5**

Property 14: Configuration validation
*For any* plugin with a configuration schema, providing configuration that violates the schema should prevent the plugin from starting and should log validation errors.
**Validates: Requirements 8.1, 8.3**

Property 15: Configuration merging
*For any* plugin with default configuration values, the final configuration should contain all defaults merged with user-provided values, with user values taking precedence.
**Validates: Requirements 8.4**

Property 16: Configuration change notification
*For any* running plugin, when its configuration is updated, the plugin's on_config_changed callback should be invoked with the changed keys and values.
**Validates: Requirements 8.2**

Property 17: Health monitoring and restart
*For any* plugin that fails health checks, the Plugin System should attempt automatic restart with exponential backoff, and should disable the plugin after exceeding the failure threshold.
**Validates: Requirements 9.2, 9.3**

Property 18: Plugin metrics tracking
*For any* running plugin, querying its status should return current metrics including status, uptime, failure count, and restart count.
**Validates: Requirements 9.1**

Property 19: Log message routing
*For any* log message emitted by a plugin, the message should appear in the central logging system with the plugin name as an identifier.
**Validates: Requirements 9.5**

Property 20: Database isolation
*For any* plugin using database storage, the plugin should only be able to access its own tables and data, not other plugins' data.
**Validates: Requirements 10.1**

Property 21: Message routing to mesh
*For any* message sent by a plugin via the message sending interface, the message should be queued and routed according to the destination and channel parameters.
**Validates: Requirements 10.2**

Property 22: Permission enforcement
*For any* plugin attempting to use a capability it doesn't have permission for, the access should be denied and an error should be returned.
**Validates: Requirements 10.5**

Property 23: Inter-plugin messaging
*For any* message sent from one plugin to another via the inter-plugin messaging mechanism, the message should be delivered to the target plugin's message handler.
**Validates: Requirements 10.4**

Property 24: Manifest completeness
*For any* plugin package, the manifest file should contain all required fields (name, version, description, author) and should pass validation.
**Validates: Requirements 11.1, 11.5**

Property 25: Error isolation
*For any* unhandled exception raised in plugin code (initialization, message handling, scheduled tasks), the Plugin System should catch the exception, log it with details, and continue operating without crashing.
**Validates: Requirements 12.1, 12.2, 12.3**

Property 26: Failure threshold enforcement
*For any* plugin that fails repeatedly, once the failure count exceeds the configured threshold, the plugin should be automatically disabled.
**Validates: Requirements 12.4**

Property 27: Failure counter reset
*For any* plugin with previous failures, after a configurable number of consecutive successful operations, the failure counter should be reset to zero.
**Validates: Requirements 12.5**

## Error Handling

### Plugin Error Categories

1. **Load-Time Errors**
   - Missing or invalid manifest
   - Unmet dependencies
   - Invalid Python syntax
   - Import errors
   - **Handling**: Mark plugin as failed, log detailed error, continue loading other plugins

2. **Initialization Errors**
   - Configuration validation failures
   - Resource allocation failures
   - Database initialization errors
   - **Handling**: Mark plugin as failed, log error, allow retry after configuration fix

3. **Runtime Errors**
   - Command handler exceptions
   - Message handler exceptions
   - Scheduled task exceptions
   - HTTP request failures
   - **Handling**: Log error, increment failure counter, continue operation, disable if threshold exceeded

4. **Shutdown Errors**
   - Resource cleanup failures
   - Task cancellation timeouts
   - **Handling**: Log error, force cleanup after timeout, continue shutdown process

### Error Recovery Strategies

1. **Automatic Restart**: For transient failures, attempt restart with exponential backoff
2. **Graceful Degradation**: Disable failing plugin while keeping system operational
3. **Error Reporting**: Detailed error logs with stack traces for debugging
4. **Health Monitoring**: Continuous health checks to detect and respond to failures
5. **Circuit Breaker**: Temporarily disable plugin after repeated failures, allow manual re-enable

### Error Logging Format

```python
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "ERROR",
    "plugin": "my_plugin",
    "error_type": "RuntimeError",
    "error_message": "Failed to fetch data from API",
    "stack_trace": "...",
    "context": {
        "command": "mycommand",
        "sender": "!abc123",
        "attempt": 1
    }
}
```

## Testing Strategy

### Unit Testing

Unit tests will verify specific functionality and edge cases:

1. **Manifest Parsing**: Test valid and invalid manifest files
2. **Configuration Validation**: Test schema validation with various inputs
3. **Command Registration**: Test command handler registration and lookup
4. **Menu Integration**: Test menu item registration and removal
5. **Storage Operations**: Test key-value storage CRUD operations
6. **HTTP Client**: Test request handling, timeouts, and error cases
7. **Error Handling**: Test exception catching and logging

### Property-Based Testing

Property-based tests will verify universal properties across all inputs using the **Hypothesis** library for Python. Each property-based test will run a minimum of 100 iterations with randomly generated inputs.

**Property Test Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(...)
def test_property_name(...):
    # Test implementation
```

**Property Test Tagging**:
Each property-based test must include a comment explicitly referencing the design document property:
```python
# Feature: third-party-plugin-system, Property 1: Command routing completeness
```

**Key Property Tests**:

1. **Command Routing**: Generate random commands and verify routing to correct handlers
2. **Priority Ordering**: Generate plugins with random priorities and verify execution order
3. **Configuration Merging**: Generate random default and user configs, verify merge correctness
4. **Dependency Resolution**: Generate random dependency graphs, verify resolution or error reporting
5. **Rate Limiting**: Generate random request sequences, verify rate limit enforcement
6. **Error Isolation**: Generate random exceptions in plugin code, verify system continues
7. **Manifest Validation**: Generate random manifest data, verify validation correctness

### Integration Testing

Integration tests will verify plugin system works with real ZephyrGate components:

1. **End-to-End Plugin Loading**: Load real plugin from directory, verify all lifecycle phases
2. **Message Flow**: Send mesh message, verify plugin receives and processes it
3. **BBS Integration**: Register menu item, verify it appears in BBS menu
4. **Scheduled Tasks**: Register task, verify it executes on schedule
5. **Database Integration**: Store and retrieve data, verify isolation between plugins
6. **Multi-Plugin Interaction**: Load multiple plugins, verify they can communicate

### Test Organization

```
tests/
├── unit/
│   ├── test_plugin_manifest.py
│   ├── test_plugin_config.py
│   ├── test_command_handler.py
│   ├── test_menu_integration.py
│   ├── test_plugin_storage.py
│   └── test_http_client.py
├── property/
│   ├── test_command_routing_properties.py
│   ├── test_config_properties.py
│   ├── test_dependency_properties.py
│   ├── test_error_handling_properties.py
│   └── test_lifecycle_properties.py
└── integration/
    ├── test_plugin_lifecycle.py
    ├── test_message_flow.py
    ├── test_bbs_integration.py
    └── test_multi_plugin.py
```

## Documentation Structure

### Developer Documentation

**Location**: `docs/PLUGIN_DEVELOPMENT.md`

**Sections**:
1. **Getting Started**
   - Overview of plugin system
   - Quick start tutorial
   - "Hello World" plugin example

2. **Plugin Architecture**
   - Plugin lifecycle
   - Base classes and interfaces
   - Plugin manifest format

3. **API Reference**
   - BasePlugin class methods
   - Command handler API
   - Message handler API
   - Scheduled task API
   - BBS menu API
   - Storage API
   - HTTP client API
   - Configuration API

4. **Advanced Topics**
   - Inter-plugin communication
   - Database access
   - Permission system
   - Error handling best practices
   - Performance considerations

5. **Testing Plugins**
   - Unit testing approach
   - Mocking ZephyrGate interfaces
   - Integration testing
   - Debugging techniques

6. **Packaging and Distribution**
   - Directory structure
   - Manifest requirements
   - Dependency management
   - Versioning guidelines

7. **Troubleshooting**
   - Common errors and solutions
   - Debugging tools
   - Log analysis
   - Performance profiling

### Example Plugins

**Location**: `examples/plugins/`

**Examples to Include**:

1. **hello_world**: Minimal plugin with command handler
2. **weather_alert**: Plugin that fetches data and sends scheduled messages
3. **custom_menu**: Plugin that adds BBS menu items
4. **data_logger**: Plugin that uses storage and database
5. **multi_command**: Plugin with multiple command handlers
6. **scheduled_reporter**: Plugin with multiple scheduled tasks
7. **plugin_communicator**: Plugin that interacts with other plugins

### Plugin Template

**Location**: `templates/plugin_template/`

**Template Structure**:
```
plugin_template/
├── __init__.py
├── plugin.py
├── manifest.yaml
├── config_schema.json
├── handlers/
│   ├── __init__.py
│   └── commands.py
├── tasks/
│   ├── __init__.py
│   └── scheduled.py
├── tests/
│   └── test_plugin.py
├── README.md
└── requirements.txt
```

**Template Generator Script**: `scripts/create_plugin.py`

```bash
python scripts/create_plugin.py --name my_plugin --author "Your Name"
```

## Implementation Notes

### Backward Compatibility

- Existing internal plugins (weather, BBS, emergency) continue to work without changes
- New plugin API is additive, doesn't break existing functionality
- Configuration format remains compatible with existing config files

### Performance Considerations

- Plugin discovery is cached to avoid repeated filesystem scans
- Command routing uses hash maps for O(1) lookup
- Scheduled tasks use efficient timer implementation
- Rate limiting uses token bucket algorithm
- Database queries use connection pooling

### Security Considerations

- Plugins run in same process but with permission boundaries
- Configuration validation prevents injection attacks
- HTTP client enforces rate limits and timeouts
- Database access is isolated per plugin
- File system access is restricted to plugin directories
- No arbitrary code execution from configuration

### Migration Path

1. **Phase 1**: Implement enhanced plugin base classes and manifest system
2. **Phase 2**: Add plugin discovery and loading from external directories
3. **Phase 3**: Implement developer documentation and examples
4. **Phase 4**: Create plugin template generator
5. **Phase 5**: Migrate one internal plugin to new system as validation
6. **Phase 6**: Release to external developers with beta documentation

## Dependencies

### Python Packages

- `pyyaml>=6.0` - Manifest parsing
- `jsonschema>=4.17.0` - Configuration validation
- `aiohttp>=3.8.0` - HTTP client
- `hypothesis>=6.68.0` - Property-based testing

### Internal Dependencies

- Core plugin manager (existing)
- Message router (existing)
- Database manager (existing)
- Configuration manager (existing)
- BBS menu system (existing)

### External Dependencies

None - system is self-contained

## Future Enhancements

1. **Plugin Marketplace**: Central registry for discovering and installing plugins
2. **Plugin Sandboxing**: Run plugins in separate processes for isolation
3. **Hot Reload**: Reload plugins without stopping ZephyrGate
4. **Plugin Metrics**: Detailed performance metrics and profiling
5. **Plugin Debugging**: Interactive debugger for plugin development
6. **Plugin Versioning**: Support multiple versions of same plugin
7. **Plugin Dependencies**: Automatic dependency resolution and installation
8. **Plugin Signing**: Cryptographic signatures for plugin verification
