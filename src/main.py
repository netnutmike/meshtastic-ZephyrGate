"""
ZephyrGate Main Application Entry Point

This is the main entry point for the ZephyrGate unified Meshtastic gateway application.
It initializes all core systems and starts the application with full service integration.
"""

import asyncio
import signal
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import ConfigurationManager
from core.logging import initialize_logging, get_logger
from core.database import initialize_database
from core.plugin_manager import PluginManager, PluginPriority
from core.message_router import CoreMessageRouter
from core.health_monitor import HealthMonitor, HealthAlert, AlertSeverity
from core.service_manager import ServiceManager, ServiceOperation
from core.interfaces import InterfaceManager, InterfaceConfig


class ZephyrGateApplication:
    """Main ZephyrGate application class with full service integration"""
    
    def __init__(self):
        # Core components
        self.config_manager: Optional[ConfigurationManager] = None
        self.db_manager = None
        self.plugin_manager: Optional[PluginManager] = None
        self.message_router: Optional[CoreMessageRouter] = None
        self.interface_manager: Optional[InterfaceManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.service_manager: Optional[ServiceManager] = None
        self.logger = None
        self.event_loop = None  # Store event loop reference
        
        # Application state
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.startup_tasks = []
        
        # Service configuration
        self.service_configs = {}
        self.enabled_services = []
    
    async def initialize(self):
        """Initialize all application components"""
        try:
            # Store event loop reference for thread-safe message handling
            self.event_loop = asyncio.get_event_loop()
            
            # Initialize configuration
            self.config_manager = ConfigurationManager()
            self.config_manager.load_config()
            
            # Initialize logging
            initialize_logging(self.config_manager.config)
            self.logger = get_logger('main')
            
            self.logger.info("ZephyrGate starting up...")
            self.logger.info(f"Version: {self.config_manager.get('app.version', '1.1.0')}")
            self.logger.info(f"Debug mode: {self.config_manager.get('app.debug', False)}")
            
            # Initialize database
            await self._initialize_database()
            
            # Initialize core message router
            await self._initialize_message_router()
            
            # Initialize Meshtastic interface manager
            await self._initialize_interface_manager()
            
            # Initialize plugin manager
            await self._initialize_plugin_manager()
            
            # Initialize health monitor
            await self._initialize_health_monitor()
            
            # Initialize service manager
            await self._initialize_service_manager()
            
            # Load service configurations
            await self._load_service_configurations()
            
            self.logger.info("Core systems initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize application: {e}", exc_info=True)
            else:
                # Fallback if logger not initialized
                import sys
                sys.stderr.write(f"Failed to initialize application: {e}\n")
                traceback.print_exc()
            raise
    
    async def _initialize_database(self):
        """Initialize database system"""
        self.logger.info("Initializing database...")
        
        db_path = self.config_manager.get('database.path', 'data/zephyrgate.db')
        max_connections = self.config_manager.get('database.max_connections', 10)
        
        self.db_manager = initialize_database(db_path, max_connections)
        
        # Ensure database schema is up to date
        await self._ensure_database_schema()
        
        self.logger.info("Database initialized successfully")
    
    async def _ensure_database_schema(self):
        """Ensure database schema is current"""
        try:
            # Create message history table if it doesn't exist
            self.db_manager.execute_update("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    recipient_id TEXT,
                    channel INTEGER,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    interface_id TEXT,
                    hop_count INTEGER DEFAULT 0,
                    snr REAL,
                    rssi REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create system events table
            self.db_manager.execute_update("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create message routing log table
            self.db_manager.execute_update("""
                CREATE TABLE IF NOT EXISTS message_routing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    target_services TEXT,
                    successful_routes TEXT,
                    failed_routes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.logger.debug("Database schema verified")
            
        except Exception as e:
            self.logger.error(f"Failed to ensure database schema: {e}")
            raise
    
    async def _initialize_message_router(self):
        """Initialize core message router"""
        self.logger.info("Initializing message router...")
        
        self.message_router = CoreMessageRouter(self.config_manager, self.db_manager)
        
        self.logger.info("Message router initialized successfully")
    
    async def _initialize_interface_manager(self):
        """Initialize Meshtastic interface manager"""
        self.logger.info("Initializing interface manager...")
        
        # Create interface manager with message callback
        self.interface_manager = InterfaceManager(self._handle_incoming_message)
        
        # Load interface configurations
        interface_configs = self.config_manager.get('meshtastic.interfaces', [])
        
        self.logger.debug(f"Loaded interface configs: {interface_configs}")
        self.logger.debug(f"Number of interfaces: {len(interface_configs) if interface_configs else 0}")
        
        if not interface_configs:
            self.logger.warning("No Meshtastic interfaces configured")
        else:
            # Add each configured interface
            for config_dict in interface_configs:
                try:
                    self.logger.debug(f"Processing interface config: {config_dict}")
                    
                    # Determine connection string based on interface type
                    iface_type = config_dict.get('type', 'serial')
                    connection_string = ""
                    metadata = {}
                    
                    if iface_type == 'serial':
                        connection_string = config_dict.get('port', '')
                        metadata['baudrate'] = config_dict.get('baud_rate', 921600)
                    elif iface_type == 'tcp':
                        host = config_dict.get('host', 'localhost')
                        port = config_dict.get('tcp_port', 4403)
                        connection_string = f"{host}:{port}"
                    elif iface_type == 'ble':
                        connection_string = config_dict.get('ble_address', '')
                    
                    self.logger.debug(f"Connection string: {connection_string}")
                    
                    # Create InterfaceConfig from dict
                    interface_config = InterfaceConfig(
                        id=config_dict.get('id', f"interface_{len(self.interface_manager.interfaces)}"),
                        type=iface_type,
                        enabled=config_dict.get('enabled', True),
                        connection_string=connection_string,
                        retry_interval=config_dict.get('retry_interval', 30),
                        max_retries=config_dict.get('max_retries', 5),
                        timeout=config_dict.get('timeout', 30),
                        metadata=metadata
                    )
                    
                    self.logger.debug(f"Created InterfaceConfig: {interface_config}")
                    
                    await self.interface_manager.add_interface(interface_config)
                    self.logger.info(f"Added interface: {interface_config.id} ({interface_config.type})")
                    
                    # Register interface with message router if available
                    if self.message_router:
                        # Get the actual interface instance from the interface manager
                        if interface_config.id in self.interface_manager.interfaces:
                            interface_instance = self.interface_manager.interfaces[interface_config.id]
                            self.message_router.register_interface(interface_config.id, interface_instance)
                            self.logger.info(f"Registered interface {interface_config.id} with message router")
                    
                except Exception as e:
                    self.logger.error(f"Failed to add interface: {e}")
        
        self.logger.info("Interface manager initialized successfully")
    
    def _handle_incoming_message(self, message, interface_id: str):
        """Handle incoming messages from Meshtastic interfaces"""
        try:
            self.logger.debug(f"Received message from {interface_id}: {message.content if hasattr(message, 'content') else message}")
            
            # Route message through the message router
            if self.message_router and self.event_loop:
                # Use call_soon_threadsafe to schedule the coroutine from another thread
                self.event_loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(
                        self.message_router.process_message(message, interface_id)
                    )
                )
            else:
                if not self.message_router:
                    self.logger.warning("Message router not available, message dropped")
                if not self.event_loop:
                    self.logger.warning("Event loop not available, message dropped")
                
        except Exception as e:
            self.logger.error(f"Error handling incoming message: {e}")
            self.logger.debug(traceback.format_exc())
    
    async def _initialize_plugin_manager(self):
        """Initialize plugin manager"""
        self.logger.info("Initializing plugin manager...")
        
        self.plugin_manager = PluginManager(self.config_manager)
        
        # Set message router reference for plugins to use
        if self.message_router:
            self.plugin_manager.message_router = self.message_router
            self.logger.debug("Set message router on plugin manager")
        
        # Discover available plugins
        discovered_plugins = await self.plugin_manager.discover_plugins()
        self.logger.info(f"Discovered {len(discovered_plugins)} plugins: {discovered_plugins}")
        
        self.logger.info("Plugin manager initialized successfully")
    
    async def _initialize_health_monitor(self):
        """Initialize health monitoring system"""
        self.logger.info("Initializing health monitor...")
        
        health_config = self.config_manager.get('health_monitor', {})
        self.health_monitor = HealthMonitor(health_config)
        
        # Add alert callback for logging critical alerts
        self.health_monitor.add_alert_callback(self._handle_health_alert)
        
        self.logger.info("Health monitor initialized successfully")
    
    async def _initialize_service_manager(self):
        """Initialize service management system"""
        self.logger.info("Initializing service manager...")
        
        self.service_manager = ServiceManager(self.plugin_manager, self.config_manager)
        
        # Add operation callback for logging
        self.service_manager.add_operation_callback(self._handle_service_operation)
        
        self.logger.info("Service manager initialized successfully")
    
    async def _load_service_configurations(self):
        """Load configurations for all services"""
        self.logger.info("Loading service configurations...")
        
        # Services are now loaded as plugins through the plugin system
        # This method is kept for backward compatibility
        # All services should be configured in the plugins.enabled_plugins list in config.yaml
        
        self.logger.info("Services are now managed through the plugin system")
        self.logger.info("Configure enabled services in plugins.enabled_plugins in config.yaml")
    
    async def start_services(self):
        """Start all enabled services using service manager"""
        self.logger.info("Starting services...")
        
        # Get enabled plugins from configuration
        enabled_plugins = self.config_manager.get_enabled_plugins()
        
        if not enabled_plugins:
            self.logger.info("No plugins explicitly enabled, will auto-load discovered plugins")
        else:
            self.logger.info(f"Loading enabled plugins: {enabled_plugins}")
        
        # Load enabled plugins
        for plugin_name in enabled_plugins:
            # Get plugin-specific config if available
            plugin_config = self.config_manager.get(f'plugins.{plugin_name}', {})
            
            # Also check for service config (for backward compatibility)
            if not plugin_config:
                plugin_config = self.config_manager.get(f'services.{plugin_name}', {})
            
            try:
                success = await self.plugin_manager.load_plugin(plugin_name, plugin_config)
                if success:
                    self.logger.info(f"Loaded plugin: {plugin_name}")
                else:
                    self.logger.error(f"Failed to load plugin: {plugin_name}")
            except Exception as e:
                self.logger.error(f"Error loading plugin {plugin_name}: {e}")
        
        # Start all loaded plugins
        success = await self.plugin_manager.start_all_plugins()
        if not success:
            self.logger.warning("Some plugins failed to start")
        
        # Register plugins with message router
        await self._register_services_with_router()
        
        # Set command handler reference in bot service for active plugin filtering
        await self._setup_bot_command_filtering()
        
        # Start message router
        await self.message_router.start()
        
        # Start health monitoring
        await self._start_health_monitoring()
        
        self.logger.info("Services started successfully")
    
    async def _register_services_with_router(self):
        """Register all running services with the message router"""
        running_plugins = self.plugin_manager.get_running_plugins()
        
        # Mapping of plugin names to classifier service names
        service_name_mapping = {
            'bot_service': 'bot',
            'emergency_service': 'emergency',
            'bbs_service': 'bbs',
            'weather_service': 'weather',
            'email_service': 'email',
            'asset_service': 'asset',
            'web_service': 'web'
        }
        
        for plugin_name in running_plugins:
            plugin_info = self.plugin_manager.get_plugin_info(plugin_name)
            if plugin_info and plugin_info.instance:
                # Register with full plugin name
                self.message_router.register_service(plugin_name, plugin_info.instance)
                self.logger.debug(f"Registered service {plugin_name} with message router")
                
                # Also register with short name for classifier compatibility
                if plugin_name in service_name_mapping:
                    short_name = service_name_mapping[plugin_name]
                    self.message_router.register_service(short_name, plugin_info.instance)
                    self.logger.debug(f"Registered service {short_name} (alias for {plugin_name}) with message router")
    
    async def _setup_bot_command_filtering(self):
        """Set up bot service to filter commands based on active plugins"""
        try:
            # Get the bot service instance
            bot_plugin = self.plugin_manager.get_plugin_info('bot_service')
            if bot_plugin and bot_plugin.instance:
                bot_service = bot_plugin.instance
                
                # Set the main command handler reference for filtering
                if hasattr(bot_service, 'set_main_command_handler'):
                    bot_service.set_main_command_handler(self.message_router.command_handler)
                    self.logger.info("Configured bot service to filter commands by active plugins")
                else:
                    self.logger.warning("Bot service doesn't have set_main_command_handler method")
            else:
                self.logger.debug("Bot service not loaded, skipping command filtering setup")
        except Exception as e:
            self.logger.error(f"Failed to setup bot command filtering: {e}")
    
    async def stop_services(self):
        """Stop all services gracefully using service manager"""
        self.logger.info("Stopping services...")
        
        # Stop message router first
        if self.message_router:
            await self.message_router.stop()
        
        # Stop health monitoring
        if self.health_monitor:
            await self.health_monitor.stop()
        
        # Stop all services using service manager (handles dependencies)
        if self.service_manager:
            results = await self.service_manager.stop_all_services()
            failed_services = [name for name, success in results.items() if not success]
            if failed_services:
                self.logger.warning(f"Failed to stop services: {failed_services}")
        else:
            # Fallback to plugin manager
            await self.plugin_manager.stop_all_plugins()
        
        self.logger.info("Services stopped successfully")
    
    async def start(self):
        """Start the application"""
        await self.initialize()
        
        self.running = True
        self.logger.info("ZephyrGate is now running")
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Start all services
            await self.start_services()
            
            # Main application loop
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def _main_loop(self):
        """Main application event loop"""
        self.logger.info("Entering main application loop")
        
        # Create monitoring tasks
        monitoring_tasks = [
            asyncio.create_task(self._health_monitor_loop()),
            asyncio.create_task(self._stats_reporter_loop())
        ]
        
        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            self.logger.info("Shutdown signal received")
            
        finally:
            # Cancel monitoring tasks
            for task in monitoring_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*monitoring_tasks, return_exceptions=True)
    
    async def _health_monitor_loop(self):
        """Monitor system health"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check plugin health
                if self.plugin_manager:
                    stats = self.plugin_manager.get_plugin_stats()
                    failed_plugins = [
                        name for name, info in stats['plugins'].items()
                        if not info['health']['is_healthy']
                    ]
                    
                    if failed_plugins:
                        self.logger.warning(f"Unhealthy plugins detected: {failed_plugins}")
                
                # Check message router health
                if self.message_router:
                    router_stats = self.message_router.get_stats()
                    queue_size = router_stats.get('queue_size', 0)
                    
                    if queue_size > 100:
                        self.logger.warning(f"Message queue backlog: {queue_size} messages")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitor: {e}")
    
    async def _stats_reporter_loop(self):
        """Report system statistics periodically"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                if self.plugin_manager and self.message_router:
                    plugin_stats = self.plugin_manager.get_plugin_stats()
                    router_stats = self.message_router.get_stats()
                    
                    self.logger.info(
                        f"System Stats - "
                        f"Plugins: {plugin_stats['running_plugins']}/{plugin_stats['total_plugins']} running, "
                        f"Messages: {router_stats['messages_received']} received, "
                        f"{router_stats['messages_sent']} sent, "
                        f"Queue: {router_stats['queue_size']}"
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in stats reporter: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    async def shutdown(self):
        """Shutdown the application gracefully"""
        if not self.running:
            return
        
        self.logger.info("Shutting down ZephyrGate...")
        self.running = False
        
        try:
            # Stop services
            await self.stop_services()
            
            # Stop Meshtastic interfaces
            if self.interface_manager:
                self.logger.info("Stopping Meshtastic interfaces...")
                await self.interface_manager.stop_all()
            
            # Close database connections
            if self.db_manager:
                self.db_manager.close()
            
            self.logger.info("ZephyrGate shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            'running': self.running,
            'enabled_services': self.enabled_services,
            'plugins': {},
            'message_router': {},
            'database': {'connected': self.db_manager is not None}
        }
        
        if self.plugin_manager:
            status['plugins'] = self.plugin_manager.get_plugin_stats()
        
        if self.message_router:
            status['message_router'] = self.message_router.get_stats()
        
        return status
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a specific service using service manager"""
        if self.service_manager:
            self.logger.info(f"Restarting service: {service_name}")
            return await self.service_manager.restart_service(service_name)
        elif self.plugin_manager:
            self.logger.info(f"Restarting service via plugin manager: {service_name}")
            return await self.plugin_manager.restart_plugin(service_name)
        else:
            return False
    
    async def reload_configuration(self):
        """Reload configuration and update services"""
        self.logger.info("Reloading configuration...")
        
        try:
            # Reload configuration
            self.config_manager.load_config()
            
            # Update service configurations
            await self._load_service_configurations()
            
            # Notify services of configuration changes
            if self.plugin_manager:
                for plugin_name in self.plugin_manager.get_running_plugins():
                    plugin_info = self.plugin_manager.get_plugin_info(plugin_name)
                    if plugin_info and plugin_info.instance:
                        # Update plugin configuration
                        new_config = self.service_configs.get(plugin_name, {}).get('config', {})
                        plugin_info.config.update(new_config)
            
            self.logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            raise
    
    async def _start_health_monitoring(self):
        """Start health monitoring for all services"""
        if not self.health_monitor:
            return
        
        # Register all services for health monitoring
        if self.plugin_manager:
            for service_name in self.plugin_manager.get_running_plugins():
                self.health_monitor.register_service(service_name)
        
        # Start health monitoring
        await self.health_monitor.start()
        
        self.logger.info("Health monitoring started")
    
    def _handle_health_alert(self, alert: HealthAlert):
        """Handle health alerts"""
        if alert.severity == AlertSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL HEALTH ALERT - {alert.source}: {alert.message}")
            
            # Store alert in database
            try:
                self.db_manager.execute_update(
                    """
                    INSERT INTO system_events (event_type, source, data)
                    VALUES (?, ?, ?)
                    """,
                    (
                        'health_alert',
                        alert.source,
                        f"[{alert.severity.value.upper()}] {alert.message}"
                    )
                )
            except Exception as e:
                self.logger.error(f"Failed to store health alert: {e}")
        
        elif alert.severity == AlertSeverity.ERROR:
            self.logger.error(f"HEALTH ERROR - {alert.source}: {alert.message}")
        
        elif alert.severity == AlertSeverity.WARNING:
            self.logger.warning(f"HEALTH WARNING - {alert.source}: {alert.message}")
    
    async def _health_monitor_loop(self):
        """Enhanced health monitoring loop with service integration"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check plugin health
                if self.plugin_manager:
                    stats = self.plugin_manager.get_plugin_stats()
                    failed_plugins = [
                        name for name, info in stats['plugins'].items()
                        if not info['health']['is_healthy']
                    ]
                    
                    if failed_plugins:
                        self.logger.warning(f"Unhealthy plugins detected: {failed_plugins}")
                        
                        # Attempt to restart failed plugins
                        for plugin_name in failed_plugins:
                            try:
                                success = await self.plugin_manager.restart_plugin(plugin_name)
                                if success:
                                    self.logger.info(f"Successfully restarted plugin: {plugin_name}")
                                else:
                                    self.logger.error(f"Failed to restart plugin: {plugin_name}")
                            except Exception as e:
                                self.logger.error(f"Error restarting plugin {plugin_name}: {e}")
                
                # Check message router health
                if self.message_router:
                    router_stats = self.message_router.get_stats()
                    queue_size = router_stats.get('queue_size', 0)
                    
                    if queue_size > 100:
                        self.logger.warning(f"Message queue backlog: {queue_size} messages")
                    
                    # Update health monitor with message router metrics
                    if self.health_monitor:
                        self.health_monitor.system_health.message_queue_size = queue_size
                        self.health_monitor.system_health.active_connections = len(router_stats.get('registered_interfaces', []))
                
                # Check database health
                if self.db_manager:
                    try:
                        # Simple database health check
                        self.db_manager.execute_query("SELECT 1")
                    except Exception as e:
                        self.logger.error(f"Database health check failed: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in enhanced health monitor: {e}")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status including health metrics"""
        status = self.get_system_status()
        
        # Add health monitoring data
        if self.health_monitor:
            health_status = self.health_monitor.get_system_status()
            status['health'] = health_status
            
            # Add performance metrics
            performance_metrics = self.health_monitor.get_performance_metrics()
            status['performance'] = performance_metrics
        
        return status
    
    async def handle_system_command(self, command: str, args: List[str] = None) -> str:
        """Handle system management commands"""
        args = args or []
        
        try:
            if command == 'status':
                status = self.get_comprehensive_status()
                return f"System Status: {status['plugins']['running_plugins']}/{status['plugins']['total_plugins']} services running"
            
            elif command == 'restart_service' and args:
                service_name = args[0]
                success = await self.restart_service(service_name)
                return f"Service {service_name} restart: {'successful' if success else 'failed'}"
            
            elif command == 'reload_config':
                await self.reload_configuration()
                return "Configuration reloaded successfully"
            
            elif command == 'health':
                if self.health_monitor:
                    health_status = self.health_monitor.get_system_status()
                    system_status = health_status['system_health']['status']
                    return f"System health: {system_status}"
                else:
                    return "Health monitoring not available"
            
            elif command == 'alerts':
                if self.health_monitor:
                    alerts = self.health_monitor.get_system_status()['alerts']
                    return f"Active alerts: {alerts['total']} (Critical: {alerts['critical']}, Errors: {alerts['error']}, Warnings: {alerts['warning']})"
                else:
                    return "Health monitoring not available"
            
            elif command == 'performance':
                if self.health_monitor:
                    metrics = self.health_monitor.get_performance_metrics()
                    cpu = metrics.get('cpu_usage', {}).get('avg', 0)
                    memory = metrics.get('memory_usage', {}).get('avg', 0)
                    return f"Performance - CPU: {cpu:.1f}%, Memory: {memory:.1f}%"
                else:
                    return "Performance monitoring not available"
            
            else:
                return f"Unknown system command: {command}"
        
        except Exception as e:
            self.logger.error(f"Error handling system command {command}: {e}")
            return f"Error executing command: {e}"
    
    def _handle_service_operation(self, operation: ServiceOperation):
        """Handle service operation events"""
        if operation.success:
            self.logger.info(
                f"Service operation completed: {operation.action.value} {operation.service_name} "
                f"in {operation.duration.total_seconds():.2f}s"
            )
        else:
            self.logger.error(
                f"Service operation failed: {operation.action.value} {operation.service_name} - "
                f"{operation.error_message}"
            )
        
        # Store operation in database
        try:
            self.db_manager.execute_update(
                """
                INSERT INTO system_events (event_type, source, data)
                VALUES (?, ?, ?)
                """,
                (
                    'service_operation',
                    operation.service_name,
                    f"{operation.action.value}: {'success' if operation.success else 'failed'} - {operation.error_message or 'OK'}"
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to store service operation: {e}")
    
    async def graceful_shutdown(self, timeout: int = 30) -> bool:
        """Perform graceful shutdown with timeout"""
        self.logger.info(f"Starting graceful shutdown with {timeout}s timeout")
        
        if self.service_manager:
            return await self.service_manager.graceful_shutdown(timeout)
        else:
            # Fallback shutdown
            try:
                await asyncio.wait_for(self.stop_services(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                self.logger.error(f"Graceful shutdown timed out after {timeout}s")
                return False
    
    def get_service_management_status(self) -> Dict[str, Any]:
        """Get comprehensive service management status"""
        status = {
            'service_manager_available': self.service_manager is not None,
            'services': {},
            'operations_history': []
        }
        
        if self.service_manager:
            status['services'] = self.service_manager.get_all_services_status()
            status['operations_history'] = self.service_manager.get_operations_history(10)
        
        return status


async def main():
    """Main entry point"""
    app = ZephyrGateApplication()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger = get_logger('main')
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger = get_logger('main')
        logger.error(f"Application failed to start: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        sys.exit(0)
    except Exception as e:
        # Log fatal errors to stderr
        sys.stderr.write(f"Fatal error: {e}\n")
        sys.exit(1)