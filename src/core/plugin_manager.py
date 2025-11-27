"""
Plugin Management System for ZephyrGate

Provides dynamic loading, lifecycle management, dependency resolution,
and health monitoring for service modules.
"""

import asyncio
import importlib
import inspect
import json
import logging
import sys
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Callable
import uuid

from .config import ConfigurationManager
from .logging import get_logger
from .plugin_manifest import PluginManifest, ManifestLoader


class PluginStatus(Enum):
    """Plugin status enumeration"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DISABLED = "disabled"


class PluginPriority(Enum):
    """Plugin priority levels for startup order"""
    CRITICAL = 1    # Core services that must start first
    HIGH = 2        # Important services
    NORMAL = 3      # Standard services
    LOW = 4         # Optional services


@dataclass
class PluginDependency:
    """Plugin dependency specification"""
    name: str
    version: Optional[str] = None
    optional: bool = False


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[PluginDependency] = field(default_factory=list)
    priority: PluginPriority = PluginPriority.NORMAL
    enabled: bool = True
    config_schema: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate metadata after initialization"""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Plugin name must be a non-empty string")
        if not self.version or not isinstance(self.version, str):
            raise ValueError("Plugin version must be a non-empty string")


@dataclass
class PluginHealth:
    """Plugin health monitoring data"""
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    heartbeat_interval: float = 30.0  # seconds
    failure_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    restart_count: int = 0
    max_failures: int = 3
    max_restarts: int = 5
    consecutive_successes: int = 0
    success_threshold_for_reset: int = 10  # Reset failure count after this many successes
    last_restart_time: Optional[datetime] = None
    restart_backoff_seconds: float = 1.0  # Initial backoff
    max_backoff_seconds: float = 300.0  # Max 5 minutes
    
    def is_healthy(self) -> bool:
        """Check if plugin is healthy"""
        now = datetime.utcnow()
        heartbeat_timeout = timedelta(seconds=self.heartbeat_interval * 2)
        
        return (
            self.failure_count < self.max_failures and
            self.restart_count < self.max_restarts and
            (now - self.last_heartbeat) < heartbeat_timeout
        )
    
    def record_heartbeat(self):
        """Record a heartbeat"""
        self.last_heartbeat = datetime.utcnow()
    
    def record_failure(self, error: str):
        """Record a failure"""
        self.failure_count += 1
        self.consecutive_successes = 0  # Reset success counter
        self.last_error = error
        self.last_error_time = datetime.utcnow()
    
    def record_success(self):
        """Record a successful operation"""
        self.consecutive_successes += 1
        
        # Reset failure count after threshold consecutive successes
        if self.consecutive_successes >= self.success_threshold_for_reset:
            if self.failure_count > 0:
                self.failure_count = 0
                self.consecutive_successes = 0
    
    def record_restart(self):
        """Record a restart"""
        self.restart_count += 1
        self.last_restart_time = datetime.utcnow()
        # Don't reset failure count on restart - let successful operations do that
    
    def get_restart_delay(self) -> float:
        """Calculate exponential backoff delay for next restart"""
        if self.restart_count == 0:
            return 0.0
        
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s, ... up to max
        delay = min(
            self.restart_backoff_seconds * (2 ** (self.restart_count - 1)),
            self.max_backoff_seconds
        )
        return delay
    
    def should_attempt_restart(self) -> bool:
        """Check if restart should be attempted"""
        # Don't restart if max restarts exceeded
        if self.restart_count >= self.max_restarts:
            return False
        
        # Check if enough time has passed since last restart (backoff)
        if self.last_restart_time:
            delay = self.get_restart_delay()
            time_since_restart = (datetime.utcnow() - self.last_restart_time).total_seconds()
            if time_since_restart < delay:
                return False
        
        return True
    
    def reset(self):
        """Reset health metrics"""
        self.failure_count = 0
        self.restart_count = 0
        self.consecutive_successes = 0
        self.last_error = None
        self.last_error_time = None
        self.last_restart_time = None
        self.record_heartbeat()


@dataclass
class PluginInfo:
    """Complete plugin information"""
    metadata: PluginMetadata
    status: PluginStatus = PluginStatus.UNLOADED
    instance: Optional['BasePlugin'] = None
    module: Optional[Any] = None
    health: PluginHealth = field(default_factory=PluginHealth)
    load_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)
    manifest: Optional[PluginManifest] = None  # Plugin manifest if available
    plugin_path: Optional[Path] = None  # Path to plugin directory
    
    def get_uptime(self) -> Optional[timedelta]:
        """Get plugin uptime"""
        if self.start_time and self.status == PluginStatus.RUNNING:
            return datetime.utcnow() - self.start_time
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive plugin metrics"""
        uptime = self.get_uptime()
        return {
            'status': self.status.value,
            'uptime_seconds': uptime.total_seconds() if uptime else 0,
            'load_time': self.load_time.isoformat() if self.load_time else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'health': {
                'is_healthy': self.health.is_healthy(),
                'failure_count': self.health.failure_count,
                'restart_count': self.health.restart_count,
                'consecutive_successes': self.health.consecutive_successes,
                'last_error': self.health.last_error,
                'last_error_time': self.health.last_error_time.isoformat() if self.health.last_error_time else None,
                'last_heartbeat': self.health.last_heartbeat.isoformat(),
                'last_restart_time': self.health.last_restart_time.isoformat() if self.health.last_restart_time else None,
                'next_restart_delay': self.health.get_restart_delay()
            }
        }


class BasePlugin(ABC):
    """
    Abstract base class for all ZephyrGate plugins.
    
    All service modules must inherit from this class and implement
    the required abstract methods.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: 'PluginManager'):
        self.name = name
        self.config = config
        self.plugin_manager = plugin_manager
        self.logger = get_logger(f'plugin_{name}')
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        
        # Plugin communication
        self._message_handlers: Dict[str, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the plugin.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        Start the plugin.
        
        Returns:
            bool: True if start successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the plugin.
        
        Returns:
            bool: True if stop successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """
        Clean up plugin resources.
        
        Returns:
            bool: True if cleanup successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.
        
        Returns:
            PluginMetadata: Plugin metadata
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Perform health check.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        return self.is_running
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """Register a message handler"""
        self._message_handlers[message_type] = handler
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def handle_message(self, message_type: str, message: Any) -> Any:
        """Handle incoming message"""
        if message_type in self._message_handlers:
            try:
                return await self._message_handlers[message_type](message)
            except Exception as e:
                self.logger.error(f"Error handling message {message_type}: {e}")
                return None
        return None
    
    async def emit_event(self, event_type: str, data: Any = None):
        """Emit an event to the plugin manager"""
        await self.plugin_manager.handle_plugin_event(self.name, event_type, data)
    
    def create_task(self, coro) -> asyncio.Task:
        """Create and track an async task"""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
    
    async def wait_for_stop(self):
        """Wait for stop signal"""
        await self._stop_event.wait()
    
    def signal_stop(self):
        """Signal the plugin to stop"""
        self._stop_event.set()
    
    async def cancel_tasks(self):
        """Cancel all plugin tasks"""
        for task in self._tasks.copy():
            if not task.done():
                task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


class PluginManager:
    """
    Manages the lifecycle of plugins including loading, starting, stopping,
    dependency resolution, and health monitoring.
    """
    
    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        self.logger = get_logger('plugin_manager')
        
        # Plugin storage
        self.plugins: Dict[str, PluginInfo] = {}
        self.plugin_paths: List[Path] = []
        
        # Dependency management
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.startup_order: List[str] = []
        
        # Health monitoring
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.health_check_interval = 30.0  # seconds
        
        # Event handling
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Plugin state persistence
        self._plugin_state_file = Path("data/plugin_state.json")
        self._enabled_plugins: Set[str] = set()
        self._disabled_plugins: Set[str] = set()
        
        # Plugin discovery paths
        self._setup_plugin_paths()
        
        # Load persisted plugin state
        self._load_plugin_state()
        
        self.logger.info("Plugin manager initialized")
    
    def _setup_plugin_paths(self):
        """Set up plugin discovery paths"""
        # Default plugin paths
        base_path = Path(__file__).parent.parent
        self.plugin_paths = [
            base_path / "services",
            Path("plugins"),  # External plugins directory
        ]
        
        # Add configured plugin paths
        additional_paths = self.config_manager.get('plugins.paths', [])
        for path_str in additional_paths:
            path = Path(path_str).expanduser()  # Expand ~ to home directory
            if path.exists():
                self.plugin_paths.append(path)
                self.logger.debug(f"Added plugin path: {path}")
    
    def _load_plugin_state(self):
        """Load persisted plugin state from disk"""
        try:
            if self._plugin_state_file.exists():
                with open(self._plugin_state_file, 'r') as f:
                    state = json.load(f)
                    self._enabled_plugins = set(state.get('enabled', []))
                    self._disabled_plugins = set(state.get('disabled', []))
                    self.logger.info(f"Loaded plugin state: {len(self._enabled_plugins)} enabled, {len(self._disabled_plugins)} disabled")
            else:
                self.logger.debug("No plugin state file found, starting fresh")
        except Exception as e:
            self.logger.error(f"Failed to load plugin state: {e}")
            self._enabled_plugins = set()
            self._disabled_plugins = set()
    
    def _save_plugin_state(self):
        """Save plugin state to disk for persistence across restarts"""
        try:
            # Ensure data directory exists
            self._plugin_state_file.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                'enabled': list(self._enabled_plugins),
                'disabled': list(self._disabled_plugins),
                'last_updated': datetime.utcnow().isoformat()
            }
            
            with open(self._plugin_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            self.logger.debug("Saved plugin state to disk")
        except Exception as e:
            self.logger.error(f"Failed to save plugin state: {e}")
    
    async def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in configured paths.
        
        Scans configured plugin directories for valid plugins. A valid plugin
        must have:
        - A directory with __init__.py
        - Optionally, a manifest.yaml file for third-party plugins
        
        Returns:
            List[str]: List of discovered plugin names
        """
        discovered = []
        
        for plugin_path in self.plugin_paths:
            if not plugin_path.exists():
                self.logger.debug(f"Plugin path does not exist: {plugin_path}")
                continue
            
            self.logger.debug(f"Scanning for plugins in {plugin_path}")
            
            # Look for Python packages (directories with __init__.py)
            for item in plugin_path.iterdir():
                if not item.is_dir():
                    continue
                
                # Check if it's a valid Python package
                if not (item / "__init__.py").exists():
                    continue
                
                plugin_name = item.name
                
                # Skip if already discovered
                if plugin_name in self.plugins:
                    continue
                
                # Check for manifest.yaml (third-party plugins)
                manifest_path = item / "manifest.yaml"
                if manifest_path.exists():
                    # Try to load and validate manifest
                    manifest = ManifestLoader.load_from_directory(item)
                    if manifest:
                        discovered.append(plugin_name)
                        self.logger.debug(f"Discovered third-party plugin: {plugin_name} (with manifest)")
                    else:
                        self.logger.warning(f"Plugin {plugin_name} has invalid manifest, skipping")
                else:
                    # Internal plugin without manifest
                    discovered.append(plugin_name)
                    self.logger.debug(f"Discovered internal plugin: {plugin_name} (no manifest)")
        
        self.logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered
    
    async def load_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load a plugin by name.
        
        For third-party plugins with manifests:
        - Validates manifest
        - Checks ZephyrGate version compatibility
        - Validates dependencies
        
        Args:
            plugin_name: Name of the plugin to load
            config: Optional plugin configuration
            
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        if plugin_name in self.plugins:
            self.logger.warning(f"Plugin {plugin_name} already loaded")
            return True
        
        self.logger.info(f"Loading plugin: {plugin_name}")
        
        # Create plugin info
        plugin_info = PluginInfo(
            metadata=PluginMetadata(
                name=plugin_name,
                version="unknown",
                description="",
                author=""
            ),
            config=config or {}
        )
        
        try:
            plugin_info.status = PluginStatus.LOADING
            self.plugins[plugin_name] = plugin_info
            
            # Find plugin directory and check for manifest
            plugin_dir = self._find_plugin_directory(plugin_name)
            if not plugin_dir:
                raise FileNotFoundError(f"Plugin directory not found: {plugin_name}")
            
            plugin_info.plugin_path = plugin_dir
            
            # Load manifest if it exists
            manifest_path = plugin_dir / "manifest.yaml"
            if manifest_path.exists():
                manifest = ManifestLoader.load_from_directory(plugin_dir)
                if not manifest:
                    raise ValueError(f"Invalid manifest for plugin: {plugin_name}")
                
                plugin_info.manifest = manifest
                
                # Check ZephyrGate version compatibility
                if not self._check_version_compatibility(manifest):
                    raise RuntimeError(
                        f"Plugin {plugin_name} is not compatible with this ZephyrGate version. "
                        f"Required: {manifest.min_zephyrgate_version} - {manifest.max_zephyrgate_version}"
                    )
                
                # Validate dependencies (but don't check if they're loaded yet)
                dep_errors = self._validate_dependencies(manifest)
                if dep_errors:
                    raise RuntimeError(
                        f"Plugin {plugin_name} has dependency issues: {'; '.join(dep_errors)}"
                    )
                
                self.logger.info(f"Loaded manifest for plugin {plugin_name} v{manifest.version}")
            
            # Find and import the plugin module
            module = await self._import_plugin_module(plugin_name)
            if not module:
                raise ImportError(f"Could not import plugin module: {plugin_name}")
            
            plugin_info.module = module
            
            # Find the plugin class
            plugin_class = self._find_plugin_class(module)
            if not plugin_class:
                raise ValueError(f"No valid plugin class found in {plugin_name}")
            
            # Create plugin instance
            plugin_instance = plugin_class(plugin_name, plugin_info.config, self)
            plugin_info.instance = plugin_instance
            
            # Get metadata from instance
            plugin_info.metadata = plugin_instance.get_metadata()
            
            # Initialize the plugin
            if not await plugin_instance.initialize():
                raise RuntimeError(f"Plugin {plugin_name} initialization failed")
            
            plugin_info.status = PluginStatus.LOADED
            plugin_info.load_time = datetime.utcnow()
            
            self.logger.info(f"Successfully loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            self.logger.debug(traceback.format_exc())
            
            plugin_info.status = PluginStatus.FAILED
            plugin_info.health.record_failure(str(e))
            
            return False
    
    def _find_plugin_directory(self, plugin_name: str) -> Optional[Path]:
        """Find the directory containing a plugin"""
        for plugin_path in self.plugin_paths:
            plugin_dir = plugin_path / plugin_name
            if plugin_dir.exists() and plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
                return plugin_dir
        return None
    
    def _check_version_compatibility(self, manifest: PluginManifest) -> bool:
        """
        Check if plugin is compatible with current ZephyrGate version.
        
        Args:
            manifest: Plugin manifest
            
        Returns:
            bool: True if compatible, False otherwise
        """
        # Get ZephyrGate version from config
        zephyrgate_version = self.config_manager.get('app.version', '1.0.0')
        
        # If no version constraints specified, assume compatible
        if not manifest.min_zephyrgate_version and not manifest.max_zephyrgate_version:
            return True
        
        # Parse versions (simple comparison for now)
        def parse_version(version_str: str) -> tuple:
            """Parse version string into tuple of integers"""
            try:
                parts = version_str.split('.')
                return tuple(int(p) for p in parts[:3])  # major.minor.patch
            except (ValueError, AttributeError):
                return (0, 0, 0)
        
        current_version = parse_version(zephyrgate_version)
        
        # Check minimum version
        if manifest.min_zephyrgate_version:
            min_version = parse_version(manifest.min_zephyrgate_version)
            if current_version < min_version:
                self.logger.warning(
                    f"ZephyrGate version {zephyrgate_version} is below minimum "
                    f"required version {manifest.min_zephyrgate_version}"
                )
                return False
        
        # Check maximum version
        if manifest.max_zephyrgate_version:
            max_version = parse_version(manifest.max_zephyrgate_version)
            if current_version > max_version:
                self.logger.warning(
                    f"ZephyrGate version {zephyrgate_version} is above maximum "
                    f"supported version {manifest.max_zephyrgate_version}"
                )
                return False
        
        return True
    
    def _validate_dependencies(self, manifest: PluginManifest) -> List[str]:
        """
        Validate plugin dependencies.
        
        Checks that all required plugin dependencies are available (but not
        necessarily loaded yet). This is a pre-load validation.
        
        Args:
            manifest: Plugin manifest
            
        Returns:
            List of error messages (empty if all dependencies are valid)
        """
        errors = []
        
        for dep in manifest.plugin_dependencies:
            # Skip optional dependencies
            if dep.optional:
                continue
            
            # Check if dependency plugin exists in any plugin path
            dep_found = False
            for plugin_path in self.plugin_paths:
                dep_dir = plugin_path / dep.name
                if dep_dir.exists() and (dep_dir / "__init__.py").exists():
                    dep_found = True
                    break
            
            if not dep_found:
                errors.append(f"Required plugin dependency '{dep.name}' not found")
        
        return errors
    
    async def _import_plugin_module(self, plugin_name: str):
        """Import plugin module dynamically"""
        for plugin_path in self.plugin_paths:
            module_path = plugin_path / plugin_name
            if module_path.exists() and (module_path / "__init__.py").exists():
                try:
                    # Add plugin path to sys.path temporarily
                    if str(plugin_path) not in sys.path:
                        sys.path.insert(0, str(plugin_path))
                    
                    # Import the module
                    module = importlib.import_module(plugin_name)
                    return module
                    
                except Exception as e:
                    self.logger.error(f"Error importing {plugin_name} from {plugin_path}: {e}")
                    continue
        
        return None
    
    def _find_plugin_class(self, module) -> Optional[Type[BasePlugin]]:
        """Find the plugin class in the module"""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BasePlugin) and 
                obj != BasePlugin):
                return obj
        return None
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            bool: True if unloaded successfully, False otherwise
        """
        if plugin_name not in self.plugins:
            self.logger.warning(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        try:
            # Stop the plugin if running
            if plugin_info.status == PluginStatus.RUNNING:
                await self.stop_plugin(plugin_name)
            
            # Clean up the plugin
            if plugin_info.instance:
                await plugin_info.instance.cleanup()
            
            # Remove from plugins
            del self.plugins[plugin_name]
            
            # Remove from dependency graph
            if plugin_name in self.dependency_graph:
                del self.dependency_graph[plugin_name]
            
            # Remove from startup order
            if plugin_name in self.startup_order:
                self.startup_order.remove(plugin_name)
            
            self.logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    async def start_plugin(self, plugin_name: str) -> bool:
        """
        Start a plugin.
        
        Args:
            plugin_name: Name of the plugin to start
            
        Returns:
            bool: True if started successfully, False otherwise
        """
        if plugin_name not in self.plugins:
            self.logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        if plugin_info.status == PluginStatus.RUNNING:
            self.logger.warning(f"Plugin {plugin_name} already running")
            return True
        
        if plugin_info.status != PluginStatus.LOADED:
            self.logger.error(f"Plugin {plugin_name} not in loaded state (current: {plugin_info.status})")
            return False
        
        try:
            plugin_info.status = PluginStatus.STARTING
            
            # Check dependencies
            if not await self._check_dependencies(plugin_name):
                raise RuntimeError(f"Dependencies not satisfied for {plugin_name}")
            
            # Start the plugin
            if not await plugin_info.instance.start():
                raise RuntimeError(f"Plugin {plugin_name} start method returned False")
            
            plugin_info.status = PluginStatus.RUNNING
            plugin_info.start_time = datetime.utcnow()
            plugin_info.health.reset()
            
            self.logger.info(f"Successfully started plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start plugin {plugin_name}: {e}")
            plugin_info.status = PluginStatus.FAILED
            plugin_info.health.record_failure(str(e))
            return False
    
    async def stop_plugin(self, plugin_name: str) -> bool:
        """
        Stop a plugin.
        
        Args:
            plugin_name: Name of the plugin to stop
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if plugin_name not in self.plugins:
            self.logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        if plugin_info.status != PluginStatus.RUNNING:
            self.logger.warning(f"Plugin {plugin_name} not running (current: {plugin_info.status})")
            return True
        
        try:
            plugin_info.status = PluginStatus.STOPPING
            
            # Signal stop to plugin
            plugin_info.instance.signal_stop()
            
            # Stop the plugin
            if not await plugin_info.instance.stop():
                self.logger.warning(f"Plugin {plugin_name} stop method returned False")
            
            # Cancel any remaining tasks
            await plugin_info.instance.cancel_tasks()
            
            plugin_info.status = PluginStatus.STOPPED
            plugin_info.start_time = None
            
            self.logger.info(f"Successfully stopped plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            plugin_info.status = PluginStatus.FAILED
            plugin_info.health.record_failure(str(e))
            return False
    
    async def restart_plugin(self, plugin_name: str) -> bool:
        """
        Restart a plugin.
        
        Args:
            plugin_name: Name of the plugin to restart
            
        Returns:
            bool: True if restarted successfully, False otherwise
        """
        if plugin_name not in self.plugins:
            self.logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        plugin_info.health.record_restart()
        
        self.logger.info(f"Restarting plugin: {plugin_name}")
        
        # Stop the plugin
        if plugin_info.status == PluginStatus.RUNNING:
            if not await self.stop_plugin(plugin_name):
                return False
        
        # Start the plugin
        return await self.start_plugin(plugin_name)
    
    async def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable and load a plugin dynamically without system restart.
        
        Args:
            plugin_name: Name of the plugin to enable
            
        Returns:
            bool: True if enabled successfully, False otherwise
        """
        self.logger.info(f"Enabling plugin: {plugin_name}")
        
        # Update state tracking
        self._enabled_plugins.add(plugin_name)
        self._disabled_plugins.discard(plugin_name)
        self._save_plugin_state()
        
        # If plugin is already loaded, just start it
        if plugin_name in self.plugins:
            plugin_info = self.plugins[plugin_name]
            if plugin_info.status == PluginStatus.RUNNING:
                self.logger.info(f"Plugin {plugin_name} is already running")
                return True
            elif plugin_info.status == PluginStatus.LOADED:
                return await self.start_plugin(plugin_name)
            elif plugin_info.status == PluginStatus.STOPPED:
                return await self.start_plugin(plugin_name)
            else:
                self.logger.warning(f"Plugin {plugin_name} is in state {plugin_info.status}, attempting to reload")
                await self.unload_plugin(plugin_name)
        
        # Load the plugin
        if not await self.load_plugin(plugin_name):
            return False
        
        # Start the plugin
        return await self.start_plugin(plugin_name)
    
    async def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable and unload a plugin gracefully.
        
        Args:
            plugin_name: Name of the plugin to disable
            
        Returns:
            bool: True if disabled successfully, False otherwise
        """
        self.logger.info(f"Disabling plugin: {plugin_name}")
        
        # Update state tracking
        self._disabled_plugins.add(plugin_name)
        self._enabled_plugins.discard(plugin_name)
        self._save_plugin_state()
        
        if plugin_name not in self.plugins:
            self.logger.warning(f"Plugin {plugin_name} not found")
            return True  # Already disabled
        
        # Stop the plugin if running
        plugin_info = self.plugins[plugin_name]
        if plugin_info.status == PluginStatus.RUNNING:
            if not await self.stop_plugin(plugin_name):
                self.logger.error(f"Failed to stop plugin {plugin_name}")
                return False
        
        # Unload the plugin
        return await self.unload_plugin(plugin_name)
    
    async def _check_dependencies(self, plugin_name: str) -> bool:
        """
        Check if plugin dependencies are satisfied at runtime.
        
        This checks that all required dependencies are loaded and running.
        
        Args:
            plugin_name: Name of the plugin to check
            
        Returns:
            bool: True if all dependencies are satisfied, False otherwise
        """
        if plugin_name not in self.plugins:
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        # Check dependencies from manifest if available
        if plugin_info.manifest:
            for dependency in plugin_info.manifest.plugin_dependencies:
                if dependency.name not in self.plugins:
                    if not dependency.optional:
                        self.logger.error(f"Required dependency {dependency.name} not found for {plugin_name}")
                        return False
                    else:
                        self.logger.warning(f"Optional dependency {dependency.name} not found for {plugin_name}")
                        continue
                
                dep_plugin = self.plugins[dependency.name]
                if dep_plugin.status != PluginStatus.RUNNING:
                    if not dependency.optional:
                        self.logger.error(f"Required dependency {dependency.name} not running for {plugin_name}")
                        return False
        
        # Also check dependencies from metadata (for backward compatibility)
        for dependency in plugin_info.metadata.dependencies:
            if dependency.name not in self.plugins:
                if not dependency.optional:
                    self.logger.error(f"Required dependency {dependency.name} not found for {plugin_name}")
                    return False
                else:
                    self.logger.warning(f"Optional dependency {dependency.name} not found for {plugin_name}")
                    continue
            
            dep_plugin = self.plugins[dependency.name]
            if dep_plugin.status != PluginStatus.RUNNING:
                if not dependency.optional:
                    self.logger.error(f"Required dependency {dependency.name} not running for {plugin_name}")
                    return False
        
        return True
    
    def _build_dependency_graph(self):
        """Build dependency graph for startup ordering"""
        self.dependency_graph.clear()
        
        for plugin_name, plugin_info in self.plugins.items():
            deps = set()
            for dependency in plugin_info.metadata.dependencies:
                if not dependency.optional and dependency.name in self.plugins:
                    deps.add(dependency.name)
            self.dependency_graph[plugin_name] = deps
    
    def _calculate_startup_order(self) -> List[str]:
        """Calculate plugin startup order based on dependencies and priorities"""
        self._build_dependency_graph()
        
        # Topological sort with priority consideration
        in_degree = {name: 0 for name in self.plugins.keys()}
        
        # Calculate in-degrees
        for plugin_name, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[plugin_name] += 1
        
        # Priority queue (lower priority value = higher priority)
        from heapq import heappush, heappop
        queue = []
        
        # Add plugins with no dependencies
        for plugin_name, degree in in_degree.items():
            if degree == 0:
                priority = self.plugins[plugin_name].metadata.priority.value
                heappush(queue, (priority, plugin_name))
        
        startup_order = []
        
        while queue:
            _, plugin_name = heappop(queue)
            startup_order.append(plugin_name)
            
            # Update in-degrees for dependent plugins
            for dependent, deps in self.dependency_graph.items():
                if plugin_name in deps:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        priority = self.plugins[dependent].metadata.priority.value
                        heappush(queue, (priority, dependent))
        
        # Check for circular dependencies
        if len(startup_order) != len(self.plugins):
            remaining = set(self.plugins.keys()) - set(startup_order)
            self.logger.error(f"Circular dependencies detected in plugins: {remaining}")
            # Add remaining plugins anyway
            startup_order.extend(remaining)
        
        return startup_order
    
    def should_auto_start_plugin(self, plugin_name: str) -> bool:
        """
        Check if a plugin should be auto-started based on persisted state.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            bool: True if plugin should be auto-started
        """
        # If explicitly disabled, don't start
        if plugin_name in self._disabled_plugins:
            return False
        
        # If explicitly enabled, start
        if plugin_name in self._enabled_plugins:
            return True
        
        # Otherwise, use plugin's metadata enabled flag
        if plugin_name in self.plugins:
            return self.plugins[plugin_name].metadata.enabled
        
        return False
    
    async def start_all_plugins(self) -> bool:
        """
        Start all loaded plugins in dependency order.
        
        Returns:
            bool: True if all plugins started successfully, False otherwise
        """
        self.startup_order = self._calculate_startup_order()
        
        self.logger.info(f"Starting plugins in order: {self.startup_order}")
        
        success = True
        for plugin_name in self.startup_order:
            if plugin_name in self.plugins:
                # Check if plugin should be auto-started based on persisted state
                if self.should_auto_start_plugin(plugin_name):
                    if not await self.start_plugin(plugin_name):
                        success = False
                        # Continue starting other plugins even if one fails
                else:
                    self.logger.debug(f"Skipping plugin {plugin_name} (disabled in persisted state)")
        
        # Start health monitoring
        if not self.health_monitor_task or self.health_monitor_task.done():
            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        
        return success
    
    async def stop_all_plugins(self) -> bool:
        """
        Stop all running plugins in reverse dependency order.
        
        Returns:
            bool: True if all plugins stopped successfully, False otherwise
        """
        # Stop health monitoring
        if self.health_monitor_task and not self.health_monitor_task.done():
            self.health_monitor_task.cancel()
        
        # Stop plugins in reverse order
        reverse_order = list(reversed(self.startup_order))
        
        self.logger.info(f"Stopping plugins in order: {reverse_order}")
        
        success = True
        for plugin_name in reverse_order:
            if plugin_name in self.plugins:
                if not await self.stop_plugin(plugin_name):
                    success = False
        
        return success
    
    async def _health_monitor_loop(self):
        """Health monitoring loop"""
        self.logger.info("Starting plugin health monitoring")
        
        try:
            while True:
                await asyncio.sleep(self.health_check_interval)
                await self._check_plugin_health()
        except asyncio.CancelledError:
            self.logger.info("Plugin health monitoring stopped")
        except Exception as e:
            self.logger.error(f"Error in health monitoring: {e}")
    
    async def _check_plugin_health(self):
        """Check health of all running plugins"""
        for plugin_name, plugin_info in self.plugins.items():
            if plugin_info.status == PluginStatus.RUNNING:
                try:
                    # Perform health check
                    is_healthy = await plugin_info.instance.health_check()
                    
                    if is_healthy:
                        plugin_info.health.record_heartbeat()
                        plugin_info.health.record_success()
                    else:
                        plugin_info.health.record_failure("Health check failed")
                        
                        # Check if plugin needs restart
                        if not plugin_info.health.is_healthy():
                            await self._handle_unhealthy_plugin(plugin_name, plugin_info)
                
                except Exception as e:
                    self.logger.error(f"Health check failed for {plugin_name}: {e}")
                    plugin_info.health.record_failure(str(e))
                    
                    # Check if plugin needs restart
                    if not plugin_info.health.is_healthy():
                        await self._handle_unhealthy_plugin(plugin_name, plugin_info)
    
    async def _handle_unhealthy_plugin(self, plugin_name: str, plugin_info: PluginInfo):
        """Handle an unhealthy plugin with restart or disable logic"""
        # Check if we've exceeded max failures
        if plugin_info.health.failure_count >= plugin_info.health.max_failures:
            # Check if we've exceeded max restarts
            if plugin_info.health.restart_count >= plugin_info.health.max_restarts:
                self.logger.error(
                    f"Plugin {plugin_name} has exceeded maximum restart attempts "
                    f"({plugin_info.health.max_restarts}). Disabling plugin."
                )
                plugin_info.status = PluginStatus.DISABLED
                
                # Stop the plugin
                try:
                    await self.stop_plugin(plugin_name)
                except Exception as e:
                    self.logger.error(f"Error stopping failed plugin {plugin_name}: {e}")
                
                return
            
            # Check if we should attempt restart (respects backoff)
            if plugin_info.health.should_attempt_restart():
                delay = plugin_info.health.get_restart_delay()
                self.logger.warning(
                    f"Plugin {plugin_name} is unhealthy (failures: {plugin_info.health.failure_count}, "
                    f"restarts: {plugin_info.health.restart_count}). "
                    f"Attempting restart with {delay:.1f}s backoff..."
                )
                
                # Restart the plugin
                success = await self.restart_plugin(plugin_name)
                
                if not success:
                    self.logger.error(f"Failed to restart plugin {plugin_name}")
            else:
                delay = plugin_info.health.get_restart_delay()
                time_since_restart = 0.0
                if plugin_info.health.last_restart_time:
                    time_since_restart = (datetime.utcnow() - plugin_info.health.last_restart_time).total_seconds()
                
                self.logger.debug(
                    f"Plugin {plugin_name} restart delayed due to backoff "
                    f"(waited {time_since_restart:.1f}s of {delay:.1f}s)"
                )
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information"""
        return self.plugins.get(plugin_name)
    
    def get_all_plugins(self) -> Dict[str, PluginInfo]:
        """Get all plugin information"""
        return self.plugins.copy()
    
    def get_running_plugins(self) -> List[str]:
        """Get list of running plugin names"""
        return [
            name for name, info in self.plugins.items()
            if info.status == PluginStatus.RUNNING
        ]
    
    async def handle_plugin_event(self, plugin_name: str, event_type: str, data: Any = None):
        """Handle events from plugins"""
        self.logger.debug(f"Plugin event from {plugin_name}: {event_type}")
        
        # Call registered event handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(plugin_name, data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type}: {e}")
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def send_message_to_plugin(self, plugin_name: str, message_type: str, message: Any) -> Any:
        """Send message to a specific plugin"""
        if plugin_name not in self.plugins:
            return None
        
        plugin_info = self.plugins[plugin_name]
        if plugin_info.status != PluginStatus.RUNNING or not plugin_info.instance:
            return None
        
        try:
            return await plugin_info.instance.handle_message(message_type, message)
        except Exception as e:
            self.logger.error(f"Error sending message to {plugin_name}: {e}")
            return None
    
    def get_plugin_stats(self) -> Dict[str, Any]:
        """Get plugin manager statistics"""
        stats = {
            'total_plugins': len(self.plugins),
            'running_plugins': len(self.get_running_plugins()),
            'failed_plugins': len([p for p in self.plugins.values() if p.status == PluginStatus.FAILED]),
            'disabled_plugins_count': len([p for p in self.plugins.values() if p.status == PluginStatus.DISABLED]),
            'enabled_plugins': list(self._enabled_plugins),
            'disabled_plugins': list(self._disabled_plugins),
            'plugins': {}
        }
        
        for name, info in self.plugins.items():
            stats['plugins'][name] = info.get_metrics()
        
        return stats
    
    def get_plugin_state(self) -> Dict[str, Any]:
        """
        Get current plugin state for persistence.
        
        Returns:
            Dictionary containing enabled and disabled plugin lists
        """
        return {
            'enabled': list(self._enabled_plugins),
            'disabled': list(self._disabled_plugins)
        }