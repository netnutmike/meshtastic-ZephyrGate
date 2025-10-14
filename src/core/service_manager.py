"""
Service Management Interface for ZephyrGate

Provides comprehensive service management capabilities:
- Service start/stop/restart functionality
- Service status monitoring and reporting
- Configuration hot-reloading
- Graceful shutdown with cleanup
- Service dependency management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
import json

from .logging import get_logger
from .plugin_manager import PluginManager, PluginStatus
from .config import ConfigurationManager


class ServiceAction(Enum):
    """Service management actions"""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    RELOAD_CONFIG = "reload_config"
    HEALTH_CHECK = "health_check"


class ServiceState(Enum):
    """Service states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ServiceOperation:
    """Service operation tracking"""
    service_name: str
    action: ServiceAction
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get operation duration"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if operation is completed"""
        return self.completed_at is not None


@dataclass
class ServiceInfo:
    """Comprehensive service information"""
    name: str
    state: ServiceState = ServiceState.UNKNOWN
    plugin_status: Optional[PluginStatus] = None
    start_time: Optional[datetime] = None
    uptime: Optional[timedelta] = None
    restart_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    health_status: str = "unknown"
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def update_from_plugin_info(self, plugin_info):
        """Update service info from plugin manager info"""
        if plugin_info:
            self.plugin_status = plugin_info.status
            self.start_time = plugin_info.start_time
            self.uptime = plugin_info.get_uptime()
            self.config = plugin_info.config
            self.error_count = plugin_info.health.failure_count
            self.restart_count = plugin_info.health.restart_count
            self.last_error = plugin_info.health.last_error
            self.last_error_time = plugin_info.health.last_error_time
            
            # Map plugin status to service state
            if plugin_info.status == PluginStatus.RUNNING:
                self.state = ServiceState.RUNNING
            elif plugin_info.status == PluginStatus.STOPPED:
                self.state = ServiceState.STOPPED
            elif plugin_info.status == PluginStatus.STARTING:
                self.state = ServiceState.STARTING
            elif plugin_info.status == PluginStatus.STOPPING:
                self.state = ServiceState.STOPPING
            elif plugin_info.status == PluginStatus.FAILED:
                self.state = ServiceState.ERROR
            else:
                self.state = ServiceState.UNKNOWN


class ServiceManager:
    """
    Comprehensive service management system
    """
    
    def __init__(self, plugin_manager: PluginManager, config_manager: ConfigurationManager):
        self.plugin_manager = plugin_manager
        self.config_manager = config_manager
        self.logger = get_logger('service_manager')
        
        # Service tracking
        self.services: Dict[str, ServiceInfo] = {}
        self.operations: List[ServiceOperation] = []
        self.max_operations_history = 100
        
        # Operation callbacks
        self.operation_callbacks: List[Callable[[ServiceOperation], None]] = []
        
        # Service dependencies
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.reverse_dependencies: Dict[str, Set[str]] = {}
        
        # Configuration watching
        self.config_watchers: Dict[str, Callable] = {}
        
        # Graceful shutdown
        self.shutdown_timeout = 30  # seconds
        self.shutdown_in_progress = False
        
        self.logger.info("Service manager initialized")
    
    def register_service(self, service_name: str, dependencies: List[str] = None):
        """Register a service for management"""
        dependencies = dependencies or []
        
        # Create service info
        service_info = ServiceInfo(
            name=service_name,
            dependencies=dependencies
        )
        
        self.services[service_name] = service_info
        
        # Update dependency graph
        self.dependency_graph[service_name] = set(dependencies)
        
        # Update reverse dependencies
        for dep in dependencies:
            if dep not in self.reverse_dependencies:
                self.reverse_dependencies[dep] = set()
            self.reverse_dependencies[dep].add(service_name)
        
        self.logger.info(f"Registered service: {service_name} with dependencies: {dependencies}")
    
    def unregister_service(self, service_name: str):
        """Unregister a service"""
        if service_name in self.services:
            del self.services[service_name]
        
        if service_name in self.dependency_graph:
            del self.dependency_graph[service_name]
        
        # Remove from reverse dependencies
        for deps in self.reverse_dependencies.values():
            deps.discard(service_name)
        
        if service_name in self.reverse_dependencies:
            del self.reverse_dependencies[service_name]
        
        self.logger.info(f"Unregistered service: {service_name}")
    
    async def start_service(self, service_name: str, force: bool = False) -> bool:
        """Start a service with dependency checking"""
        if service_name not in self.services:
            self.logger.error(f"Service {service_name} not registered")
            return False
        
        service_info = self.services[service_name]
        
        # Check if already running
        if service_info.state == ServiceState.RUNNING and not force:
            self.logger.info(f"Service {service_name} already running")
            return True
        
        # Create operation
        operation = ServiceOperation(service_name=service_name, action=ServiceAction.START)
        self.operations.append(operation)
        
        try:
            # Update state
            service_info.state = ServiceState.STARTING
            
            # Check dependencies
            if not force:
                missing_deps = await self._check_dependencies(service_name)
                if missing_deps:
                    raise RuntimeError(f"Missing dependencies: {missing_deps}")
            
            # Start the service via plugin manager
            success = await self.plugin_manager.start_plugin(service_name)
            
            if success:
                service_info.state = ServiceState.RUNNING
                service_info.start_time = datetime.utcnow()
                operation.success = True
                self.logger.info(f"Successfully started service: {service_name}")
            else:
                service_info.state = ServiceState.ERROR
                operation.error_message = "Plugin manager failed to start service"
                self.logger.error(f"Failed to start service: {service_name}")
            
            return success
            
        except Exception as e:
            service_info.state = ServiceState.ERROR
            service_info.last_error = str(e)
            service_info.last_error_time = datetime.utcnow()
            service_info.error_count += 1
            
            operation.error_message = str(e)
            self.logger.error(f"Error starting service {service_name}: {e}")
            return False
            
        finally:
            operation.completed_at = datetime.utcnow()
            self._notify_operation_callbacks(operation)
            self._update_service_info(service_name)
    
    async def stop_service(self, service_name: str, force: bool = False) -> bool:
        """Stop a service with dependent checking"""
        if service_name not in self.services:
            self.logger.error(f"Service {service_name} not registered")
            return False
        
        service_info = self.services[service_name]
        
        # Check if already stopped
        if service_info.state == ServiceState.STOPPED and not force:
            self.logger.info(f"Service {service_name} already stopped")
            return True
        
        # Create operation
        operation = ServiceOperation(service_name=service_name, action=ServiceAction.STOP)
        self.operations.append(operation)
        
        try:
            # Update state
            service_info.state = ServiceState.STOPPING
            
            # Check dependents
            if not force:
                running_dependents = await self._check_running_dependents(service_name)
                if running_dependents:
                    raise RuntimeError(f"Cannot stop service with running dependents: {running_dependents}")
            
            # Stop the service via plugin manager
            success = await self.plugin_manager.stop_plugin(service_name)
            
            if success:
                service_info.state = ServiceState.STOPPED
                service_info.start_time = None
                service_info.uptime = None
                operation.success = True
                self.logger.info(f"Successfully stopped service: {service_name}")
            else:
                service_info.state = ServiceState.ERROR
                operation.error_message = "Plugin manager failed to stop service"
                self.logger.error(f"Failed to stop service: {service_name}")
            
            return success
            
        except Exception as e:
            service_info.state = ServiceState.ERROR
            service_info.last_error = str(e)
            service_info.last_error_time = datetime.utcnow()
            service_info.error_count += 1
            
            operation.error_message = str(e)
            self.logger.error(f"Error stopping service {service_name}: {e}")
            return False
            
        finally:
            operation.completed_at = datetime.utcnow()
            self._notify_operation_callbacks(operation)
            self._update_service_info(service_name)
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        if service_name not in self.services:
            self.logger.error(f"Service {service_name} not registered")
            return False
        
        service_info = self.services[service_name]
        
        # Create operation
        operation = ServiceOperation(service_name=service_name, action=ServiceAction.RESTART)
        self.operations.append(operation)
        
        try:
            service_info.state = ServiceState.RESTARTING
            
            # Stop then start
            stop_success = await self.stop_service(service_name, force=True)
            if not stop_success:
                raise RuntimeError("Failed to stop service during restart")
            
            # Wait a moment before starting
            await asyncio.sleep(1)
            
            start_success = await self.start_service(service_name, force=True)
            if not start_success:
                raise RuntimeError("Failed to start service during restart")
            
            service_info.restart_count += 1
            operation.success = True
            self.logger.info(f"Successfully restarted service: {service_name}")
            return True
            
        except Exception as e:
            service_info.state = ServiceState.ERROR
            service_info.last_error = str(e)
            service_info.last_error_time = datetime.utcnow()
            service_info.error_count += 1
            
            operation.error_message = str(e)
            self.logger.error(f"Error restarting service {service_name}: {e}")
            return False
            
        finally:
            operation.completed_at = datetime.utcnow()
            self._notify_operation_callbacks(operation)
            self._update_service_info(service_name)
    
    async def reload_service_config(self, service_name: str) -> bool:
        """Reload configuration for a service"""
        if service_name not in self.services:
            self.logger.error(f"Service {service_name} not registered")
            return False
        
        # Create operation
        operation = ServiceOperation(service_name=service_name, action=ServiceAction.RELOAD_CONFIG)
        self.operations.append(operation)
        
        try:
            # Get plugin instance
            plugin_info = self.plugin_manager.get_plugin_info(service_name)
            if not plugin_info or not plugin_info.instance:
                raise RuntimeError("Service not loaded or no instance available")
            
            # Reload configuration
            new_config = self.config_manager.get(f'services.{service_name}', {})
            
            # Update plugin configuration
            plugin_info.config.update(new_config)
            
            # Notify service of configuration change if it supports it
            if hasattr(plugin_info.instance, 'reload_config'):
                await plugin_info.instance.reload_config(new_config)
            
            operation.success = True
            self.logger.info(f"Successfully reloaded config for service: {service_name}")
            return True
            
        except Exception as e:
            operation.error_message = str(e)
            self.logger.error(f"Error reloading config for service {service_name}: {e}")
            return False
            
        finally:
            operation.completed_at = datetime.utcnow()
            self._notify_operation_callbacks(operation)
            self._update_service_info(service_name)
    
    async def health_check_service(self, service_name: str) -> Dict[str, Any]:
        """Perform health check on a service"""
        if service_name not in self.services:
            return {'status': 'error', 'message': 'Service not registered'}
        
        # Create operation
        operation = ServiceOperation(service_name=service_name, action=ServiceAction.HEALTH_CHECK)
        self.operations.append(operation)
        
        try:
            # Get plugin instance
            plugin_info = self.plugin_manager.get_plugin_info(service_name)
            if not plugin_info or not plugin_info.instance:
                return {'status': 'error', 'message': 'Service not loaded'}
            
            # Perform health check
            is_healthy = await plugin_info.instance.health_check()
            
            health_result = {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'uptime_seconds': plugin_info.get_uptime().total_seconds() if plugin_info.get_uptime() else 0,
                'error_count': plugin_info.health.failure_count,
                'restart_count': plugin_info.health.restart_count
            }
            
            # Update service info
            service_info = self.services[service_name]
            service_info.health_status = health_result['status']
            
            operation.success = True
            operation.metadata = health_result
            
            return health_result
            
        except Exception as e:
            health_result = {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            operation.error_message = str(e)
            self.logger.error(f"Error performing health check for service {service_name}: {e}")
            return health_result
            
        finally:
            operation.completed_at = datetime.utcnow()
            self._notify_operation_callbacks(operation)
    
    async def start_all_services(self) -> Dict[str, bool]:
        """Start all registered services in dependency order"""
        self.logger.info("Starting all services...")
        
        # Calculate startup order
        startup_order = self._calculate_startup_order()
        results = {}
        
        for service_name in startup_order:
            if service_name in self.services:
                success = await self.start_service(service_name)
                results[service_name] = success
                
                if not success:
                    self.logger.error(f"Failed to start service {service_name}, continuing with others")
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        self.logger.info(f"Started {successful}/{total} services successfully")
        return results
    
    async def stop_all_services(self) -> Dict[str, bool]:
        """Stop all running services in reverse dependency order"""
        self.logger.info("Stopping all services...")
        
        # Calculate shutdown order (reverse of startup)
        startup_order = self._calculate_startup_order()
        shutdown_order = list(reversed(startup_order))
        
        results = {}
        
        for service_name in shutdown_order:
            if service_name in self.services:
                service_info = self.services[service_name]
                if service_info.state == ServiceState.RUNNING:
                    success = await self.stop_service(service_name, force=True)
                    results[service_name] = success
                else:
                    results[service_name] = True  # Already stopped
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        self.logger.info(f"Stopped {successful}/{total} services successfully")
        return results
    
    async def graceful_shutdown(self, timeout: Optional[int] = None) -> bool:
        """Perform graceful shutdown of all services"""
        timeout = timeout or self.shutdown_timeout
        self.shutdown_in_progress = True
        
        self.logger.info(f"Starting graceful shutdown with {timeout}s timeout")
        
        try:
            # Stop all services with timeout
            shutdown_task = asyncio.create_task(self.stop_all_services())
            
            try:
                results = await asyncio.wait_for(shutdown_task, timeout=timeout)
                success = all(results.values())
                
                if success:
                    self.logger.info("Graceful shutdown completed successfully")
                else:
                    self.logger.warning("Some services failed to stop gracefully")
                
                return success
                
            except asyncio.TimeoutError:
                self.logger.error(f"Graceful shutdown timed out after {timeout}s")
                shutdown_task.cancel()
                return False
                
        finally:
            self.shutdown_in_progress = False
    
    def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific service"""
        if service_name not in self.services:
            return None
        
        service_info = self.services[service_name]
        self._update_service_info(service_name)
        
        return {
            'name': service_info.name,
            'state': service_info.state.value,
            'plugin_status': service_info.plugin_status.value if service_info.plugin_status else None,
            'uptime_seconds': service_info.uptime.total_seconds() if service_info.uptime else 0,
            'restart_count': service_info.restart_count,
            'error_count': service_info.error_count,
            'last_error': service_info.last_error,
            'last_error_time': service_info.last_error_time.isoformat() if service_info.last_error_time else None,
            'health_status': service_info.health_status,
            'dependencies': service_info.dependencies,
            'dependents': service_info.dependents
        }
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all registered services"""
        status = {}
        
        for service_name in self.services:
            service_status = self.get_service_status(service_name)
            if service_status:
                status[service_name] = service_status
        
        return status
    
    def get_operations_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent operations history"""
        recent_operations = self.operations[-limit:] if limit > 0 else self.operations
        
        return [
            {
                'service_name': op.service_name,
                'action': op.action.value,
                'started_at': op.started_at.isoformat(),
                'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                'duration_seconds': op.duration.total_seconds() if op.duration else None,
                'success': op.success,
                'error_message': op.error_message
            }
            for op in recent_operations
        ]
    
    def add_operation_callback(self, callback: Callable[[ServiceOperation], None]):
        """Add callback for service operations"""
        self.operation_callbacks.append(callback)
    
    async def _check_dependencies(self, service_name: str) -> List[str]:
        """Check if service dependencies are running"""
        missing_deps = []
        
        if service_name in self.dependency_graph:
            for dep_name in self.dependency_graph[service_name]:
                if dep_name in self.services:
                    dep_info = self.services[dep_name]
                    if dep_info.state != ServiceState.RUNNING:
                        missing_deps.append(dep_name)
                else:
                    missing_deps.append(dep_name)
        
        return missing_deps
    
    async def _check_running_dependents(self, service_name: str) -> List[str]:
        """Check if service has running dependents"""
        running_dependents = []
        
        if service_name in self.reverse_dependencies:
            for dependent_name in self.reverse_dependencies[service_name]:
                if dependent_name in self.services:
                    dependent_info = self.services[dependent_name]
                    if dependent_info.state == ServiceState.RUNNING:
                        running_dependents.append(dependent_name)
        
        return running_dependents
    
    def _calculate_startup_order(self) -> List[str]:
        """Calculate service startup order based on dependencies"""
        # Topological sort
        in_degree = {name: 0 for name in self.services.keys()}
        
        # Calculate in-degrees
        for service_name, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[service_name] += 1
        
        # Queue for services with no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        startup_order = []
        
        while queue:
            service_name = queue.pop(0)
            startup_order.append(service_name)
            
            # Update in-degrees for dependent services
            if service_name in self.reverse_dependencies:
                for dependent in self.reverse_dependencies[service_name]:
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            queue.append(dependent)
        
        # Check for circular dependencies
        if len(startup_order) != len(self.services):
            remaining = set(self.services.keys()) - set(startup_order)
            self.logger.warning(f"Circular dependencies detected: {remaining}")
            startup_order.extend(remaining)
        
        return startup_order
    
    def _update_service_info(self, service_name: str):
        """Update service info from plugin manager"""
        if service_name not in self.services:
            return
        
        service_info = self.services[service_name]
        plugin_info = self.plugin_manager.get_plugin_info(service_name)
        
        if plugin_info:
            service_info.update_from_plugin_info(plugin_info)
    
    def _notify_operation_callbacks(self, operation: ServiceOperation):
        """Notify operation callbacks"""
        for callback in self.operation_callbacks:
            try:
                callback(operation)
            except Exception as e:
                self.logger.error(f"Error in operation callback: {e}")
        
        # Maintain operations history limit
        if len(self.operations) > self.max_operations_history:
            self.operations = self.operations[-self.max_operations_history:]