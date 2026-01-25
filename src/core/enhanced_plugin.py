"""
Enhanced Plugin Base Class for Third-Party Plugin Development

Provides developer-friendly helper methods for creating ZephyrGate plugins.
"""

import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime, timedelta

import aiohttp

from .plugin_manager import BasePlugin, PluginManager
from .plugin_interfaces import (
    BaseCommandHandler,
    BaseMessageHandler,
    PluginMessage,
    PluginMessageType,
    PluginEvent,
    PluginEventType,
    PluginResponse
)
from .plugin_scheduler import PluginScheduler, ScheduledTask as SchedulerTask
try:
    from ..models.message import Message, MessageType
except ImportError:
    from models.message import Message, MessageType
from .logging import log_plugin_error
from .plugin_core_services import PermissionDeniedError


class EnhancedCommandHandler(BaseCommandHandler):
    """Enhanced command handler with plugin integration"""
    
    def __init__(self, plugin_name: str, command: str, handler: Callable, 
                 help_text: str = "", priority: int = 100):
        super().__init__([command])
        self.plugin_name = plugin_name
        self.command = command
        self.handler = handler
        self.priority = priority
        self.add_help(command, help_text)
    
    async def handle_command(self, command: str, args: List[str], 
                           context: Dict[str, Any]) -> str:
        """Handle command by delegating to registered handler"""
        try:
            return await self.handler(args, context)
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def get_priority(self) -> int:
        """Get handler priority"""
        return self.priority


class EnhancedMessageHandler(BaseMessageHandler):
    """Enhanced message handler with plugin integration"""
    
    def __init__(self, plugin_name: str, handler: Callable, priority: int = 100):
        super().__init__(priority)
        self.plugin_name = plugin_name
        self.handler = handler
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Handle message by delegating to registered handler"""
        try:
            return await self.handler(message, context)
        except Exception as e:
            return None
    
    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the message"""
        # Let the plugin decide via the handler
        return True


# ScheduledTask is now imported from plugin_scheduler module


class TokenBucket:
    """Token bucket rate limiter implementation"""
    
    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum bucket capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = datetime.utcnow()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if rate limit exceeded
        """
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_update).total_seconds()
            
            # Add tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Check if enough tokens available
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False


class HTTPRequestError(Exception):
    """Exception raised for HTTP request errors"""
    pass


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    pass


class PluginHTTPClient:
    """HTTP client for plugins with rate limiting and error handling"""
    
    def __init__(self, plugin_name: str, rate_limit: int = 100, max_retries: int = 3):
        """
        Initialize HTTP client.
        
        Args:
            plugin_name: Name of the plugin using this client
            rate_limit: Maximum requests per minute
            max_retries: Maximum number of retry attempts
        """
        self.plugin_name = plugin_name
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Token bucket rate limiter: rate_limit requests per minute
        # Convert to requests per second for token bucket
        tokens_per_second = rate_limit / 60.0
        self.rate_limiter = TokenBucket(rate=tokens_per_second, capacity=rate_limit)
    
    async def _ensure_session(self):
        """Ensure HTTP session is created"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _make_request(self, method: str, url: str, 
                           params: Optional[Dict] = None,
                           data: Optional[Dict] = None,
                           timeout: int = 30, 
                           headers: Optional[Dict] = None,
                           retry_count: int = 0) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET or POST)
            url: URL to request
            params: Query parameters (for GET)
            data: Request body data (for POST)
            timeout: Request timeout in seconds
            headers: HTTP headers
            retry_count: Current retry attempt number
            
        Returns:
            Response data as dictionary
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            HTTPRequestError: If request fails after all retries
        """
        # Check rate limit
        if not await self.rate_limiter.acquire():
            raise RateLimitExceeded(f"Rate limit exceeded for plugin {self.plugin_name}")
        
        await self._ensure_session()
        
        try:
            if method == "GET":
                async with self.session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == "POST":
                async with self.session.post(
                    url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise HTTPRequestError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientResponseError as e:
            # Don't retry on client errors (4xx)
            if 400 <= e.status < 500:
                raise HTTPRequestError(f"HTTP {e.status} error: {str(e)}")
            
            # Retry on server errors (5xx) if retries available
            if retry_count < self.max_retries:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, url, params, data, timeout, headers, retry_count + 1
                )
            
            raise HTTPRequestError(f"HTTP request failed after {retry_count} retries: {str(e)}")
            
        except aiohttp.ClientConnectionError as e:
            # Retry on connection errors if retries available
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, url, params, data, timeout, headers, retry_count + 1
                )
            
            raise HTTPRequestError(f"Connection error after {retry_count} retries: {str(e)}")
            
        except asyncio.TimeoutError:
            # Retry on timeout if retries available
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, url, params, data, timeout, headers, retry_count + 1
                )
            
            raise HTTPRequestError(f"Request timeout after {retry_count} retries")
            
        except aiohttp.ClientError as e:
            # Generic client error - retry if available
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, url, params, data, timeout, headers, retry_count + 1
                )
            
            raise HTTPRequestError(f"HTTP request failed after {retry_count} retries: {str(e)}")
    
    async def get(self, url: str, params: Optional[Dict] = None,
                  timeout: int = 30, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP GET request with automatic retries.
        
        Args:
            url: URL to request
            params: Query parameters
            timeout: Request timeout in seconds
            headers: HTTP headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            HTTPRequestError: If request fails after all retries
            
        Example:
            data = await client.get("https://api.example.com/data", 
                                   params={"key": "value"})
        """
        return await self._make_request("GET", url, params=params, 
                                       timeout=timeout, headers=headers)
    
    async def post(self, url: str, data: Optional[Dict] = None,
                   timeout: int = 30, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP POST request with automatic retries.
        
        Args:
            url: URL to request
            data: Request body data
            timeout: Request timeout in seconds
            headers: HTTP headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            HTTPRequestError: If request fails after all retries
            
        Example:
            result = await client.post("https://api.example.com/submit",
                                      data={"message": "Hello"})
        """
        return await self._make_request("POST", url, data=data,
                                       timeout=timeout, headers=headers)
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()


class PluginStorage:
    """Storage interface for plugin data with database persistence"""
    
    def __init__(self, plugin_name: str, plugin_manager: PluginManager):
        self.plugin_name = plugin_name
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger(f"{__name__}.{plugin_name}")
        self._init_storage()
    
    def _init_storage(self):
        """Initialize plugin storage table if needed"""
        try:
            from src.core.database import get_database
            self.db = get_database()
        except Exception as e:
            self.logger.warning(f"Database not available, using in-memory storage: {e}")
            self.db = None
            self._storage: Dict[str, Any] = {}
            self._expiry: Dict[str, datetime] = {}
    
    async def store_data(self, key: str, data: Any, ttl: Optional[int] = None):
        """
        Store data with optional TTL.
        
        Args:
            key: Storage key
            data: Data to store (must be JSON serializable)
            ttl: Time to live in seconds (optional)
        """
        if self.db is None:
            # Fallback to in-memory storage
            namespaced_key = f"{self.plugin_name}:{key}"
            self._storage[namespaced_key] = data
            if ttl:
                self._expiry[namespaced_key] = datetime.utcnow() + timedelta(seconds=ttl)
            elif namespaced_key in self._expiry:
                del self._expiry[namespaced_key]
            return
        
        # Calculate expiry time
        expires_at = None
        if ttl:
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        
        # Serialize data to JSON
        value_json = json.dumps(data)
        
        # Store in database
        try:
            self.db.execute_update("""
                INSERT OR REPLACE INTO plugin_storage 
                (plugin_name, key, value, expires_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (self.plugin_name, key, value_json, expires_at))
        except Exception as e:
            self.logger.error(f"Error storing data: {e}")
            raise
    
    async def retrieve_data(self, key: str, default: Any = None) -> Any:
        """
        Retrieve stored data.
        
        Args:
            key: Storage key
            default: Default value if key not found
            
        Returns:
            Stored data or default value
        """
        if self.db is None:
            # Fallback to in-memory storage
            namespaced_key = f"{self.plugin_name}:{key}"
            if namespaced_key not in self._storage:
                return default
            if namespaced_key in self._expiry:
                if datetime.utcnow() >= self._expiry[namespaced_key]:
                    del self._storage[namespaced_key]
                    del self._expiry[namespaced_key]
                    return default
            return self._storage[namespaced_key]
        
        try:
            rows = self.db.execute_query("""
                SELECT value, expires_at FROM plugin_storage
                WHERE plugin_name = ? AND key = ?
            """, (self.plugin_name, key))
            
            if not rows:
                return default
            
            row = rows[0]
            
            # Check expiration
            if row['expires_at']:
                expires_at = datetime.fromisoformat(row['expires_at'])
                if datetime.utcnow() >= expires_at:
                    # Expired, delete and return default
                    await self.delete_data(key)
                    return default
            
            # Deserialize and return data
            return json.loads(row['value'])
            
        except Exception as e:
            self.logger.error(f"Error retrieving data: {e}")
            return default
    
    async def delete_data(self, key: str) -> bool:
        """
        Delete stored data.
        
        Args:
            key: Storage key
            
        Returns:
            True if data was deleted, False if key didn't exist
        """
        if self.db is None:
            # Fallback to in-memory storage
            namespaced_key = f"{self.plugin_name}:{key}"
            if namespaced_key in self._storage:
                del self._storage[namespaced_key]
                if namespaced_key in self._expiry:
                    del self._expiry[namespaced_key]
                return True
            return False
        
        try:
            rowcount = self.db.execute_update("""
                DELETE FROM plugin_storage
                WHERE plugin_name = ? AND key = ?
            """, (self.plugin_name, key))
            return rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting data: {e}")
            return False
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        """
        List storage keys with optional prefix filter.
        
        Args:
            prefix: Key prefix filter
            
        Returns:
            List of matching keys
        """
        if self.db is None:
            # Fallback to in-memory storage
            plugin_prefix = f"{self.plugin_name}:"
            full_prefix = f"{plugin_prefix}{prefix}"
            keys = []
            for key in self._storage.keys():
                if key.startswith(full_prefix):
                    keys.append(key[len(plugin_prefix):])
            return keys
        
        try:
            # Use LIKE for prefix matching
            pattern = f"{prefix}%"
            rows = self.db.execute_query("""
                SELECT key FROM plugin_storage
                WHERE plugin_name = ? AND key LIKE ?
            """, (self.plugin_name, pattern))
            
            return [row['key'] for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error listing keys: {e}")
            return []


class EnhancedPlugin(BasePlugin):
    """
    Enhanced base class for third-party plugins with developer-friendly helper methods.
    
    This class extends BasePlugin with convenient methods for:
    - Command registration
    - Message handling
    - Scheduled tasks
    - BBS menu integration
    - Mesh messaging
    - Configuration management
    - Data storage
    - HTTP requests
    """
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: PluginManager):
        super().__init__(name, config, plugin_manager)
        
        # Enhanced features
        self._command_handlers: Dict[str, EnhancedCommandHandler] = {}
        self._message_handler: Optional[EnhancedMessageHandler] = None
        self._menu_items: List[Dict[str, Any]] = []
        
        # Utilities
        self._http_client = PluginHTTPClient(name)
        self._storage = PluginStorage(name, plugin_manager)
        self._scheduler = PluginScheduler(name, mesh_interface=None)  # mesh_interface can be set later
        
        # Core service access
        self._core_services = None
        if hasattr(plugin_manager, 'core_service_access'):
            self._core_services = plugin_manager.core_service_access
        
        # Register configuration change callback
        if hasattr(plugin_manager, 'config_manager'):
            if hasattr(plugin_manager.config_manager, 'register_config_change_callback'):
                plugin_manager.config_manager.register_config_change_callback(
                    name, self._handle_config_changed
                )
    
    def register_command(self, command: str, handler: Callable,
                        help_text: str = "", priority: int = 100):
        """
        Register a command handler.
        
        Args:
            command: Command name (without prefix)
            handler: Async function that takes (args: List[str], context: Dict) -> str
            help_text: Help text for the command
            priority: Handler priority (lower = higher priority)
            
        Example:
            async def my_command(args, context):
                return f"Hello {context.get('sender_id', 'unknown')}"
            
            self.register_command("hello", my_command, "Say hello")
        """
        cmd_handler = EnhancedCommandHandler(
            self.name,
            command,
            handler,
            help_text,
            priority
        )
        self._command_handlers[command] = cmd_handler
        
        # Register with message router if available
        if hasattr(self.plugin_manager, 'message_router'):
            self.plugin_manager.message_router.register_plugin_command(
                self.name, command, handler, help_text, priority, cmd_handler
            )
        
        self.logger.info(f"Registered command: {command}")
    
    def register_message_handler(self, handler: Callable, priority: int = 100):
        """
        Register a message handler for all incoming messages.
        
        Args:
            handler: Async function that takes (message: Message, context: Dict) -> Optional[Any]
            priority: Handler priority (lower = higher priority)
            
        Example:
            async def handle_message(message, context):
                if message.type == MessageType.TEXT:
                    # Process text message
                    pass
            
            self.register_message_handler(handle_message)
        """
        self._message_handler = EnhancedMessageHandler(self.name, handler, priority)
        self.logger.info(f"Registered message handler")
    
    async def handle_message(self, message: Message) -> Optional[Any]:
        """
        Handle incoming message by routing through registered message handler.
        This method is called by the message router.
        
        Args:
            message: The message to handle
            
        Returns:
            Optional response from the handler
        """
        if self._message_handler:
            from datetime import datetime
            context = {
                'plugin_name': self.name,
                'timestamp': datetime.utcnow()
            }
            try:
                return await self._message_handler.handle_message(message, context)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")
                return None
        return None
    
    def register_scheduled_task(self, name: str, handler: Callable,
                               interval: Optional[int] = None,
                               cron: Optional[str] = None):
        """
        Register a scheduled task that runs at regular intervals or on a cron schedule.
        
        Args:
            name: Task name (unique within plugin)
            handler: Async function that takes no arguments
            interval: Interval in seconds (for interval-based scheduling)
            cron: Cron expression (for cron-style scheduling)
            
        Note: Either interval or cron must be provided, but not both.
            
        Example:
            # Interval-based
            async def hourly_update():
                data = await self.http_get("https://api.example.com/data")
                await self.send_message(f"Update: {data}")
            
            self.register_scheduled_task("hourly_update", hourly_update, interval=3600)
            
            # Cron-based
            async def daily_report():
                await self.send_message("Daily report")
            
            self.register_scheduled_task("daily_report", daily_report, cron="0 0 * * *")
        """
        task = self._scheduler.register_task(name, handler, interval=interval, cron=cron)
        self.logger.info(f"Registered scheduled task: {name} " +
                        (f"(interval: {interval}s)" if interval else f"(cron: {cron})"))
    
    def register_menu_item(self, menu: str, label: str, handler: Callable,
                          description: str = "", admin_only: bool = False,
                          command: Optional[str] = None, order: int = 100):
        """
        Register a BBS menu item.
        
        Args:
            menu: Menu name (e.g., "main", "utilities")
            label: Menu item label
            handler: Async function that takes (context: Dict) -> str
            description: Menu item description
            admin_only: Whether item is admin-only
            command: Command to trigger (defaults to lowercase label)
            order: Display order (lower = earlier)
            
        Example:
            async def my_menu_handler(context):
                return "Menu item selected!"
            
            self.register_menu_item("utilities", "My Plugin", my_menu_handler)
        """
        # Generate command from label if not provided
        if command is None:
            command = label.lower().replace(' ', '_')
        
        menu_item = {
            'plugin': self.name,
            'menu': menu,
            'label': label,
            'command': command,
            'handler': handler,
            'description': description,
            'admin_only': admin_only,
            'order': order
        }
        self._menu_items.append(menu_item)
        
        # Register with plugin menu registry if available
        if hasattr(self.plugin_manager, 'plugin_menu_registry'):
            self.plugin_manager.plugin_menu_registry.register_menu_item(
                plugin_name=self.name,
                menu=menu,
                label=label,
                command=command,
                handler=handler,
                description=description,
                admin_only=admin_only,
                order=order
            )
        
        self.logger.info(f"Registered menu item: {label} (command: {command}) in {menu}")
    
    async def send_message(self, content: str, destination: Optional[str] = None,
                          channel: Optional[int] = None) -> bool:
        """
        Send a message to the mesh network.
        
        Args:
            content: Message content
            destination: Destination node ID (None for broadcast)
            channel: Channel number (None for default)
            
        Returns:
            True if message was queued successfully
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            try:
                await self.send_message("Hello mesh!", destination="!abc123")
            except PermissionDeniedError:
                self.logger.error("No permission to send messages")
        """
        try:
            # Use core service access if available
            if self._core_services:
                return await self._core_services.message_routing.send_mesh_message(
                    self.name, content, destination, channel
                )
            
            # Fallback to direct message creation
            message = Message(
                id=f"{self.name}_{datetime.utcnow().timestamp()}",
                message_type=MessageType.TEXT,
                content=content,
                sender_id=self.name,
                recipient_id=destination,
                channel=channel or 0,
                timestamp=datetime.utcnow()
            )
            
            # Send via plugin manager's message router
            # This is a simplified implementation - actual routing would go through
            # the message router
            self.logger.info(f"Sending message: {content[:50]}...")
            return True
            
        except PermissionDeniedError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False
    
    def get_config(self, key: str, default: Any = None, value_type: Optional[type] = None) -> Any:
        """
        Get configuration value with optional type safety.
        
        Args:
            key: Configuration key (dot notation supported)
            default: Default value if key not found
            value_type: Expected type for validation (optional)
            
        Returns:
            Configuration value
            
        Raises:
            TypeError: If value type doesn't match expected type
            
        Example:
            api_key = self.get_config("api_key", "", str)
            interval = self.get_config("update_interval", 300, int)
        """
        # Use config manager if available for type-safe retrieval
        if hasattr(self.plugin_manager, 'config_manager'):
            try:
                return self.plugin_manager.config_manager.get_config_value(
                    self.name, key, default, value_type
                )
            except (AttributeError, TypeError) as e:
                if value_type:
                    raise
                # Fall through to manual retrieval
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        # Type checking if requested
        if value_type is not None and value is not None:
            if not isinstance(value, value_type):
                raise TypeError(
                    f"Configuration value for {key} has type {type(value).__name__}, "
                    f"expected {value_type.__name__}"
                )
        
        return value
    
    def set_config(self, key: str, value: Any):
        """
        Set configuration value.
        
        Args:
            key: Configuration key (dot notation supported)
            value: Value to set
            
        Example:
            self.set_config("last_update", datetime.utcnow().isoformat())
        """
        # Support dot notation for nested keys
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def get_secure_config(self, key: str, default: str = "") -> str:
        """
        Get a secure configuration value (like API credentials) with decryption.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Decrypted value
            
        Example:
            api_key = self.get_secure_config("api_key")
        """
        if hasattr(self.plugin_manager, 'config_manager'):
            return self.plugin_manager.config_manager.retrieve_secure_value(
                self.name, key, default
            )
        return default
    
    def set_secure_config(self, key: str, value: str):
        """
        Set a secure configuration value (like API credentials) with encryption.
        
        Args:
            key: Configuration key
            value: Value to encrypt and store
            
        Example:
            self.set_secure_config("api_key", "secret_key_123")
        """
        if hasattr(self.plugin_manager, 'config_manager'):
            self.plugin_manager.config_manager.store_secure_value(
                self.name, key, value
            )
    
    def _handle_config_changed(self, changed_keys: Dict[str, Any], new_config: Dict[str, Any]):
        """
        Internal handler for configuration changes.
        
        Args:
            changed_keys: Dictionary of changed keys and their new values
            new_config: Complete new configuration
        """
        # Update internal config
        self.config = new_config
        
        # Call plugin's on_config_changed if implemented
        if hasattr(self, 'on_config_changed'):
            try:
                self.on_config_changed(changed_keys, new_config)
            except Exception as e:
                self.logger.error(f"Error in on_config_changed callback: {e}")
    
    def on_config_changed(self, changed_keys: Dict[str, Any], new_config: Dict[str, Any]):
        """
        Override this method to handle configuration changes.
        
        Args:
            changed_keys: Dictionary of changed keys and their new values
            new_config: Complete new configuration
            
        Example:
            def on_config_changed(self, changed_keys, new_config):
                if "api_key" in changed_keys:
                    self.logger.info("API key was updated")
                    # Reinitialize API client
        """
        pass
    
    async def store_data(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store plugin data with optional TTL.
        
        Args:
            key: Storage key
            value: Value to store (must be JSON serializable)
            ttl: Time to live in seconds (optional)
            
        Example:
            await self.store_data("cache:weather", weather_data, ttl=3600)
        """
        await self._storage.store_data(key, value, ttl)
    
    async def retrieve_data(self, key: str, default: Any = None) -> Any:
        """
        Retrieve stored plugin data.
        
        Args:
            key: Storage key
            default: Default value if key not found
            
        Returns:
            Stored value or default
            
        Example:
            weather_data = await self.retrieve_data("cache:weather")
        """
        return await self._storage.retrieve_data(key, default)
    
    async def http_get(self, url: str, params: Optional[Dict] = None,
                      timeout: int = 30, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP GET request with automatic retries.
        
        Args:
            url: URL to request
            params: Query parameters
            timeout: Request timeout in seconds
            headers: HTTP headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            HTTPRequestError: If request fails after all retries
            
        Example:
            try:
                data = await self.http_get("https://api.example.com/data", 
                                          params={"key": api_key})
            except RateLimitExceeded:
                self.logger.warning("Rate limit exceeded")
            except HTTPRequestError as e:
                self.logger.error(f"Request failed: {e}")
        """
        return await self._http_client.get(url, params, timeout, headers)
    
    async def http_post(self, url: str, data: Optional[Dict] = None,
                       timeout: int = 30, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP POST request with automatic retries.
        
        Args:
            url: URL to request
            data: Request body data
            timeout: Request timeout in seconds
            headers: HTTP headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            HTTPRequestError: If request fails after all retries
            
        Example:
            try:
                result = await self.http_post("https://api.example.com/submit",
                                             data={"message": "Hello"})
            except RateLimitExceeded:
                self.logger.warning("Rate limit exceeded")
            except HTTPRequestError as e:
                self.logger.error(f"Request failed: {e}")
        """
        return await self._http_client.post(url, data, timeout, headers)
    
    def get_scheduler(self) -> PluginScheduler:
        """
        Get the plugin scheduler for advanced scheduling operations.
        
        Returns:
            PluginScheduler instance
            
        Example:
            scheduler = self.get_scheduler()
            status = scheduler.get_task_status("my_task")
        """
        return self._scheduler
    
    def log_error(self, error_type: str, error_message: str, 
                  context: Optional[Dict[str, Any]] = None,
                  exception: Optional[Exception] = None):
        """
        Log a structured error with context.
        
        Args:
            error_type: Type of error (e.g., 'HTTPError', 'ConfigurationError')
            error_message: Error message
            context: Additional context information
            exception: Exception object (stack trace will be extracted)
            
        Example:
            try:
                data = await self.http_get(url)
            except HTTPRequestError as e:
                self.log_error(
                    "HTTPError",
                    "Failed to fetch data",
                    context={"url": url},
                    exception=e
                )
        """
        stack_trace = None
        if exception:
            stack_trace = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ))
        
        log_plugin_error(
            self.logger,
            self.name,
            error_type,
            error_message,
            context=context,
            stack_trace=stack_trace
        )
    
    async def start(self) -> bool:
        """
        Start the plugin and all registered scheduled tasks.
        
        Override this method to add custom startup logic, but make sure
        to call super().start() to start scheduled tasks.
        """
        self.is_running = True
        
        # Start all scheduled tasks
        await self._scheduler.start_all()
        self.logger.info(f"Started all scheduled tasks")
        
        return True
    
    async def stop(self) -> bool:
        """
        Stop the plugin and all scheduled tasks.
        
        Override this method to add custom shutdown logic, but make sure
        to call super().stop() to stop scheduled tasks.
        """
        self.is_running = False
        
        # Unregister all commands
        if hasattr(self.plugin_manager, 'message_router'):
            self.plugin_manager.message_router.unregister_plugin_commands(self.name)
        
        # Unregister all menu items
        if hasattr(self.plugin_manager, 'plugin_menu_registry'):
            self.plugin_manager.plugin_menu_registry.unregister_plugin_menu_items(self.name)
        
        # Stop all scheduled tasks
        await self._scheduler.stop_all()
        self.logger.info(f"Stopped all scheduled tasks")
        
        return True
    
    def get_node_info(self, node_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about a mesh node.
        
        Args:
            node_id: Node ID (None for local node)
            
        Returns:
            Node information dictionary or None if not found
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            node_info = self.get_node_info("!abc123")
            if node_info:
                self.logger.info(f"Node status: {node_info['status']}")
        """
        if self._core_services:
            return self._core_services.system_state.get_node_info(self.name, node_id)
        return None
    
    def get_network_status(self) -> Dict[str, Any]:
        """
        Get current network status.
        
        Returns:
            Network status dictionary
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            status = self.get_network_status()
            self.logger.info(f"Network connected: {status['connected']}")
        """
        if self._core_services:
            return self._core_services.system_state.get_network_status(self.name)
        return {'connected': False}
    
    def get_plugin_list(self) -> List[str]:
        """
        Get list of running plugins.
        
        Returns:
            List of plugin names
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            plugins = self.get_plugin_list()
            self.logger.info(f"Running plugins: {', '.join(plugins)}")
        """
        if self._core_services:
            return self._core_services.system_state.get_plugin_list(self.name)
        return []
    
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of another plugin.
        
        Args:
            plugin_name: Name of the plugin to query
            
        Returns:
            Plugin status dictionary or None if not found
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            status = self.get_plugin_status("weather")
            if status and status['is_running']:
                self.logger.info("Weather plugin is running")
        """
        if self._core_services:
            return self._core_services.system_state.get_plugin_status(self.name, plugin_name)
        return None
    
    async def send_to_plugin(self, target_plugin: str, message_type: str,
                            data: Any) -> Optional[PluginResponse]:
        """
        Send a message to another plugin.
        
        Args:
            target_plugin: Name of the target plugin
            message_type: Type of message
            data: Message data
            
        Returns:
            Response from target plugin or None
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            response = await self.send_to_plugin(
                "weather",
                "get_forecast",
                {"location": "Seattle"}
            )
            if response and response.success:
                forecast = response.data
        """
        if self._core_services:
            return await self._core_services.inter_plugin.send_to_plugin(
                self.name, target_plugin, message_type, data
            )
        return None
    
    async def broadcast_to_plugins(self, message_type: str, data: Any) -> List[PluginResponse]:
        """
        Broadcast a message to all plugins.
        
        Args:
            message_type: Type of message
            data: Message data
            
        Returns:
            List of responses from plugins
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
            
        Example:
            responses = await self.broadcast_to_plugins(
                "system_alert",
                {"level": "warning", "message": "Low battery"}
            )
            for response in responses:
                if response.success:
                    self.logger.info(f"Plugin acknowledged: {response.data}")
        """
        if self._core_services:
            return await self._core_services.inter_plugin.broadcast_to_plugins(
                self.name, message_type, data
            )
        return []
    
    def register_inter_plugin_handler(self, handler):
        """
        Register a handler for inter-plugin messages.
        
        Args:
            handler: Async function that takes (message: PluginMessage) -> Any
            
        Example:
            async def handle_plugin_message(message):
                if message.metadata.get('message_type') == 'ping':
                    return 'pong'
                return None
            
            self.register_inter_plugin_handler(handle_plugin_message)
        """
        if self._core_services:
            self._core_services.inter_plugin.register_message_handler(self.name, handler)
    
    async def cleanup(self) -> bool:
        """
        Clean up plugin resources.
        
        Override this method to add custom cleanup logic, but make sure
        to call super().cleanup() to clean up HTTP client.
        """
        # Close HTTP client
        await self._http_client.close()
        
        return True


# Re-export ScheduledTask for convenience
from .plugin_scheduler import ScheduledTask

__all__ = [
    'EnhancedCommandHandler',
    'EnhancedMessageHandler',
    'PluginHTTPClient',
    'PluginStorage',
    'EnhancedPlugin',
    'ScheduledTask',
]
