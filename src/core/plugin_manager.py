"""
Plugin Management System for ZephyrGate

Provides dynamic loading, lifecycle management, dependency resolution,
and health monitoring for service modules.
"""

import asyncio
import importlib
import inspect
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
        self.last_error = error
        self.last_error_time = datetime.utcnow()
    
    def record_restart(self):
        """Record a restart"""
        self.restart_count += 1
        self.failure_count = 0  # Reset failure count on restart
    
    def reset(self):
        """Reset health metrics"""
        self.failure_count = 0
        self.restart_count = 0
        self.last_error = None
        self.last_error_time = None
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
    
    def get_uptime(self) -> Optional[timedelta]:
        """Get plugin uptime"""
        if self.start_time and self.status == PluginStatus.RUNNING:
            return datetime.utcnow() - self.start_time
        return None


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
        
        # Plugin discovery paths
        self._setup_plugin_paths()
        
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
            path = Path(path_str)
            if path.exists():
                self.plugin_paths.append(path)
    
    async def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in configured paths.
        
        Returns:
            List[str]: List of discovered plugin names
        """
        discovered = []
        
        for plugin_path in self.plugin_paths:
            if not plugin_path.exists():
                continue
            
            self.logger.debug(f"Scanning for plugins in {plugin_path}")
            
            # Look for Python packages (directories with __init__.py)
            for item in plugin_path.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    plugin_name = item.name
                    if plugin_name not in self.plugins:
                        discovered.append(plugin_name)
                        self.logger.debug(f"Discovered plugin: {plugin_name}")
        
        self.logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered
    
    async def load_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load a plugin by name.
        
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
    
    async def _check_dependencies(self, plugin_name: str) -> bool:
        """Check if plugin dependencies are satisfied"""
        if plugin_name not in self.plugins:
            return False
        
        plugin_info = self.plugins[plugin_name]
        
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
                plugin_info = self.plugins[plugin_name]
                if plugin_info.metadata.enabled:
                    if not await self.start_plugin(plugin_name):
                        success = False
                        # Continue starting other plugins even if one fails
        
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
                    else:
                        plugin_info.health.record_failure("Health check failed")
                        
                        # Check if plugin needs restart
                        if not plugin_info.health.is_healthy():
                            self.logger.warning(f"Plugin {plugin_name} is unhealthy, attempting restart")
                            await self.restart_plugin(plugin_name)
                
                except Exception as e:
                    self.logger.error(f"Health check failed for {plugin_name}: {e}")
                    plugin_info.health.record_failure(str(e))
    
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
            'plugins': {}
        }
        
        for name, info in self.plugins.items():
            stats['plugins'][name] = {
                'status': info.status.value,
                'uptime_seconds': info.get_uptime().total_seconds() if info.get_uptime() else 0,
                'health': {
                    'is_healthy': info.health.is_healthy(),
                    'failure_count': info.health.failure_count,
                    'restart_count': info.health.restart_count,
                    'last_error': info.health.last_error
                }
            }
        
        return stats