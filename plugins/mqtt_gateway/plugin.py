"""
MQTT Gateway Plugin for ZephyrGate

Forwards Meshtastic mesh messages to MQTT brokers following the official
Meshtastic MQTT protocol standards. This plugin implements one-way (uplink only)
message forwarding with support for both protobuf and JSON formats.

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.enhanced_plugin import EnhancedPlugin
from core.plugin_manager import PluginMetadata
from models.message import Message, MessageType

# Import MQTT Gateway components
from plugins.mqtt_gateway.mqtt_client import MQTTClient
from plugins.mqtt_gateway.message_formatter import MessageFormatter
from plugins.mqtt_gateway.message_queue import MessageQueue
from plugins.mqtt_gateway.rate_limiter import RateLimiter


class MQTTGatewayPlugin(EnhancedPlugin):
    """
    MQTT Gateway Plugin
    
    Forwards Meshtastic mesh messages to MQTT brokers following the official
    Meshtastic MQTT protocol. Supports:
    - One-way uplink (mesh to MQTT)
    - Protobuf and JSON message formats
    - Encrypted and plaintext payloads
    - Message queuing when broker is unavailable
    - Rate limiting and exponential backoff
    - Per-channel configuration
    """
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        """
        Initialize the MQTT Gateway plugin.
        
        Args:
            name: Plugin name
            config: Plugin configuration dictionary
            plugin_manager: Reference to the plugin manager
        """
        super().__init__(name, config, plugin_manager)
        
        # Plugin state
        self.enabled = False
        self.initialized = False
        
        # Component references (will be initialized in initialize())
        self.mqtt_client = None
        self.message_formatter = None
        self.message_queue = None
        self.rate_limiter = None
        
        # Configuration cache
        self._config_cache = {}
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_published': 0,
            'messages_queued': 0,
            'messages_dropped': 0,
            'publish_errors': 0,
            'last_publish_time': None,
            'connected': False
        }
        
        # Background tasks
        self._background_tasks = []
        
    async def initialize(self) -> bool:
        """
        Initialize the plugin with configuration.
        
        This method:
        1. Loads and validates configuration
        2. Initializes sub-components (MQTT client, formatter, queue, rate limiter)
        3. Registers with the message router
        
        Returns:
            True if initialization successful, False otherwise
            
        Requirements: 1.4, 10.1, 10.2
        """
        self.logger.info("Initializing MQTT Gateway plugin")
        
        try:
            # Load configuration
            self.enabled = self.get_config("enabled", False)
            
            if not self.enabled:
                self.logger.info("MQTT Gateway is disabled in configuration")
                return False
            
            # Validate and cache configuration
            if not self._load_and_validate_config():
                self.logger.error("Configuration validation failed")
                return False
            
            # Initialize MQTT client
            self.mqtt_client = MQTTClient(self._config_cache, self.logger)
            self.logger.info("MQTT client initialized")
            
            # Initialize message formatter
            self.message_formatter = MessageFormatter(self._config_cache, self.logger)
            self.logger.info("Message formatter initialized")
            
            # Initialize message queue
            queue_max_size = self._config_cache.get('queue_max_size', 1000)
            self.message_queue = MessageQueue(max_size=queue_max_size, logger=self.logger)
            self.logger.info(f"Message queue initialized (max_size={queue_max_size})")
            
            # Initialize rate limiter
            max_msgs_per_sec = self._config_cache.get('max_messages_per_second', 10)
            burst_multiplier = self._config_cache.get('burst_multiplier', 2)
            self.rate_limiter = RateLimiter(
                max_messages_per_second=max_msgs_per_sec,
                burst_multiplier=burst_multiplier,
                logger=self.logger
            )
            self.logger.info(f"Rate limiter initialized (max_rate={max_msgs_per_sec} msg/s)")
            
            # Register message handler to receive all mesh messages
            self.register_message_handler(self._handle_mesh_message, priority=100)
            
            self.initialized = True
            self.logger.info("MQTT Gateway plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MQTT Gateway plugin: {e}", exc_info=True)
            return False
    
    def _load_and_validate_config(self) -> bool:
        """
        Load and validate plugin configuration.
        
        Validates all required parameters and applies defaults for optional ones.
        Stores validated configuration in _config_cache for quick access.
        
        Returns:
            True if configuration is valid, False otherwise
            
        Requirements: 9.2, 9.3, 9.4
        """
        try:
            # Broker connection settings (Required)
            broker_address = self.get_config('broker_address', 'mqtt.meshtastic.org')
            if not isinstance(broker_address, str):
                self.logger.error(f"Configuration validation failed: broker_address must be a string, got {type(broker_address).__name__}")
                return False
            if not broker_address or not broker_address.strip():
                self.logger.error("Configuration validation failed: broker_address cannot be empty")
                return False
            self._config_cache['broker_address'] = broker_address.strip()
            
            # Broker port (Optional, default: 1883)
            broker_port = self.get_config('broker_port', 1883)
            if not isinstance(broker_port, int):
                self.logger.error(f"Configuration validation failed: broker_port must be an integer, got {type(broker_port).__name__}")
                return False
            if broker_port < 1 or broker_port > 65535:
                self.logger.error(f"Configuration validation failed: broker_port must be between 1 and 65535, got {broker_port}")
                return False
            self._config_cache['broker_port'] = broker_port
            
            # Authentication (Optional)
            username = self.get_config('username', '')
            if not isinstance(username, str):
                self.logger.error(f"Configuration validation failed: username must be a string, got {type(username).__name__}")
                return False
            self._config_cache['username'] = username
            
            password = self.get_config('password', '')
            if not isinstance(password, str):
                self.logger.error(f"Configuration validation failed: password must be a string, got {type(password).__name__}")
                return False
            self._config_cache['password'] = password
            
            # TLS/SSL settings (Optional)
            tls_enabled = self.get_config('tls_enabled', False)
            if not isinstance(tls_enabled, bool):
                self.logger.error(f"Configuration validation failed: tls_enabled must be a boolean, got {type(tls_enabled).__name__}")
                return False
            self._config_cache['tls_enabled'] = tls_enabled
            
            ca_cert = self.get_config('ca_cert', '')
            if not isinstance(ca_cert, str):
                self.logger.error(f"Configuration validation failed: ca_cert must be a string, got {type(ca_cert).__name__}")
                return False
            self._config_cache['ca_cert'] = ca_cert
            
            client_cert = self.get_config('client_cert', '')
            if not isinstance(client_cert, str):
                self.logger.error(f"Configuration validation failed: client_cert must be a string, got {type(client_cert).__name__}")
                return False
            self._config_cache['client_cert'] = client_cert
            
            client_key = self.get_config('client_key', '')
            if not isinstance(client_key, str):
                self.logger.error(f"Configuration validation failed: client_key must be a string, got {type(client_key).__name__}")
                return False
            self._config_cache['client_key'] = client_key
            
            # Topic configuration (Optional)
            root_topic = self.get_config('root_topic', 'msh/US')
            if not isinstance(root_topic, str):
                self.logger.error(f"Configuration validation failed: root_topic must be a string, got {type(root_topic).__name__}")
                return False
            if not root_topic or not root_topic.strip():
                self.logger.error("Configuration validation failed: root_topic cannot be empty")
                return False
            # Validate topic doesn't contain MQTT wildcards
            if '+' in root_topic or '#' in root_topic:
                self.logger.error(f"Configuration validation failed: root_topic cannot contain MQTT wildcards (+ or #), got '{root_topic}'")
                return False
            self._config_cache['root_topic'] = root_topic.strip()
            
            region = self.get_config('region', 'US')
            if not isinstance(region, str):
                self.logger.error(f"Configuration validation failed: region must be a string, got {type(region).__name__}")
                return False
            if not region or not region.strip():
                self.logger.error("Configuration validation failed: region cannot be empty")
                return False
            if len(region.strip()) < 2 or len(region.strip()) > 10:
                self.logger.error(f"Configuration validation failed: region must be between 2 and 10 characters, got '{region}' (length {len(region.strip())})")
                return False
            self._config_cache['region'] = region.strip()
            
            # Message format (Optional, default: json)
            format_value = self.get_config('format', 'json')
            if not isinstance(format_value, str):
                self.logger.error(f"Configuration validation failed: format must be a string, got {type(format_value).__name__}")
                return False
            if format_value not in ['json', 'protobuf']:
                self.logger.error(f"Configuration validation failed: format must be 'json' or 'protobuf', got '{format_value}'")
                return False
            self._config_cache['format'] = format_value
            
            encryption_enabled = self.get_config('encryption_enabled', False)
            if not isinstance(encryption_enabled, bool):
                self.logger.error(f"Configuration validation failed: encryption_enabled must be a boolean, got {type(encryption_enabled).__name__}")
                return False
            self._config_cache['encryption_enabled'] = encryption_enabled
            
            # Rate limiting (Optional)
            max_msgs = self.get_config('max_messages_per_second', 10)
            if not isinstance(max_msgs, (int, float)):
                self.logger.error(f"Configuration validation failed: max_messages_per_second must be a number, got {type(max_msgs).__name__}")
                return False
            if max_msgs < 1 or max_msgs > 1000:
                self.logger.error(f"Configuration validation failed: max_messages_per_second must be between 1 and 1000, got {max_msgs}")
                return False
            self._config_cache['max_messages_per_second'] = int(max_msgs)
            
            burst_multiplier = self.get_config('burst_multiplier', 2)
            if not isinstance(burst_multiplier, (int, float)):
                self.logger.error(f"Configuration validation failed: burst_multiplier must be a number, got {type(burst_multiplier).__name__}")
                return False
            # Check for NaN and infinity
            import math
            if math.isnan(burst_multiplier) or math.isinf(burst_multiplier):
                self.logger.error(f"Configuration validation failed: burst_multiplier cannot be NaN or infinity, got {burst_multiplier}")
                return False
            if burst_multiplier < 1 or burst_multiplier > 10:
                self.logger.error(f"Configuration validation failed: burst_multiplier must be between 1 and 10, got {burst_multiplier}")
                return False
            self._config_cache['burst_multiplier'] = float(burst_multiplier)
            
            # Queue configuration (Optional)
            queue_size = self.get_config('queue_max_size', 1000)
            if not isinstance(queue_size, int):
                self.logger.error(f"Configuration validation failed: queue_max_size must be an integer, got {type(queue_size).__name__}")
                return False
            if queue_size < 10 or queue_size > 100000:
                self.logger.error(f"Configuration validation failed: queue_max_size must be between 10 and 100000, got {queue_size}")
                return False
            self._config_cache['queue_max_size'] = queue_size
            
            queue_persist = self.get_config('queue_persist', False)
            if not isinstance(queue_persist, bool):
                self.logger.error(f"Configuration validation failed: queue_persist must be a boolean, got {type(queue_persist).__name__}")
                return False
            self._config_cache['queue_persist'] = queue_persist
            
            # Reconnection settings (Optional)
            reconnect_enabled = self.get_config('reconnect_enabled', True)
            if not isinstance(reconnect_enabled, bool):
                self.logger.error(f"Configuration validation failed: reconnect_enabled must be a boolean, got {type(reconnect_enabled).__name__}")
                return False
            self._config_cache['reconnect_enabled'] = reconnect_enabled
            
            reconnect_initial_delay = self.get_config('reconnect_initial_delay', 1)
            if not isinstance(reconnect_initial_delay, (int, float)):
                self.logger.error(f"Configuration validation failed: reconnect_initial_delay must be a number, got {type(reconnect_initial_delay).__name__}")
                return False
            # Check for NaN and infinity
            import math
            if math.isnan(reconnect_initial_delay) or math.isinf(reconnect_initial_delay):
                self.logger.error(f"Configuration validation failed: reconnect_initial_delay cannot be NaN or infinity, got {reconnect_initial_delay}")
                return False
            if reconnect_initial_delay < 0.1 or reconnect_initial_delay > 60:
                self.logger.error(f"Configuration validation failed: reconnect_initial_delay must be between 0.1 and 60 seconds, got {reconnect_initial_delay}")
                return False
            self._config_cache['reconnect_initial_delay'] = float(reconnect_initial_delay)
            
            reconnect_max_delay = self.get_config('reconnect_max_delay', 60)
            if not isinstance(reconnect_max_delay, (int, float)):
                self.logger.error(f"Configuration validation failed: reconnect_max_delay must be a number, got {type(reconnect_max_delay).__name__}")
                return False
            # Check for NaN and infinity
            if math.isnan(reconnect_max_delay) or math.isinf(reconnect_max_delay):
                self.logger.error(f"Configuration validation failed: reconnect_max_delay cannot be NaN or infinity, got {reconnect_max_delay}")
                return False
            if reconnect_max_delay < 1 or reconnect_max_delay > 3600:
                self.logger.error(f"Configuration validation failed: reconnect_max_delay must be between 1 and 3600 seconds, got {reconnect_max_delay}")
                return False
            self._config_cache['reconnect_max_delay'] = float(reconnect_max_delay)
            
            # Validate reconnect_max_delay >= reconnect_initial_delay
            if self._config_cache['reconnect_max_delay'] < self._config_cache['reconnect_initial_delay']:
                self.logger.error(f"Configuration validation failed: reconnect_max_delay ({self._config_cache['reconnect_max_delay']}) must be >= reconnect_initial_delay ({self._config_cache['reconnect_initial_delay']})")
                return False
            
            reconnect_multiplier = self.get_config('reconnect_multiplier', 2.0)
            if not isinstance(reconnect_multiplier, (int, float)):
                self.logger.error(f"Configuration validation failed: reconnect_multiplier must be a number, got {type(reconnect_multiplier).__name__}")
                return False
            # Check for NaN and infinity
            if math.isnan(reconnect_multiplier) or math.isinf(reconnect_multiplier):
                self.logger.error(f"Configuration validation failed: reconnect_multiplier cannot be NaN or infinity, got {reconnect_multiplier}")
                return False
            if reconnect_multiplier < 1.0 or reconnect_multiplier > 10.0:
                self.logger.error(f"Configuration validation failed: reconnect_multiplier must be between 1.0 and 10.0, got {reconnect_multiplier}")
                return False
            self._config_cache['reconnect_multiplier'] = float(reconnect_multiplier)
            
            max_reconnect_attempts = self.get_config('max_reconnect_attempts', -1)
            if not isinstance(max_reconnect_attempts, int):
                self.logger.error(f"Configuration validation failed: max_reconnect_attempts must be an integer, got {type(max_reconnect_attempts).__name__}")
                return False
            if max_reconnect_attempts < -1:
                self.logger.error(f"Configuration validation failed: max_reconnect_attempts must be >= -1 (use -1 for infinite), got {max_reconnect_attempts}")
                return False
            self._config_cache['max_reconnect_attempts'] = max_reconnect_attempts
            
            # Logging settings (Optional)
            log_level = self.get_config('log_level', 'INFO')
            if not isinstance(log_level, str):
                self.logger.error(f"Configuration validation failed: log_level must be a string, got {type(log_level).__name__}")
                return False
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if log_level.upper() not in valid_log_levels:
                self.logger.error(f"Configuration validation failed: log_level must be one of {valid_log_levels}, got '{log_level}'")
                return False
            self._config_cache['log_level'] = log_level.upper()
            
            log_published_messages = self.get_config('log_published_messages', True)
            if not isinstance(log_published_messages, bool):
                self.logger.error(f"Configuration validation failed: log_published_messages must be a boolean, got {type(log_published_messages).__name__}")
                return False
            self._config_cache['log_published_messages'] = log_published_messages
            
            # Channel configuration (Optional)
            channels = self.get_config('channels', [])
            if not isinstance(channels, list):
                self.logger.error(f"Configuration validation failed: channels must be a list, got {type(channels).__name__}")
                return False
            
            # Validate each channel configuration
            for i, channel in enumerate(channels):
                if not isinstance(channel, dict):
                    self.logger.error(f"Configuration validation failed: channels[{i}] must be a dictionary, got {type(channel).__name__}")
                    return False
                
                # Validate channel name (required)
                if 'name' not in channel:
                    self.logger.error(f"Configuration validation failed: channels[{i}] missing required field 'name'")
                    return False
                
                channel_name = channel['name']
                if not isinstance(channel_name, str):
                    self.logger.error(f"Configuration validation failed: channels[{i}].name must be a string, got {type(channel_name).__name__}")
                    return False
                if not channel_name or not channel_name.strip():
                    self.logger.error(f"Configuration validation failed: channels[{i}].name cannot be empty")
                    return False
                
                # Validate uplink_enabled (optional, default: True)
                if 'uplink_enabled' in channel:
                    uplink_enabled = channel['uplink_enabled']
                    if not isinstance(uplink_enabled, bool):
                        self.logger.error(f"Configuration validation failed: channels[{i}].uplink_enabled must be a boolean, got {type(uplink_enabled).__name__}")
                        return False
                
                # Validate message_types (optional, default: [])
                if 'message_types' in channel:
                    message_types = channel['message_types']
                    if not isinstance(message_types, list):
                        self.logger.error(f"Configuration validation failed: channels[{i}].message_types must be a list, got {type(message_types).__name__}")
                        return False
                    
                    valid_message_types = [
                        'text', 'position', 'nodeinfo', 'telemetry', 'routing', 'admin',
                        'traceroute', 'neighborinfo', 'detection_sensor', 'reply', 'ip_tunnel',
                        'paxcounter', 'serial', 'store_forward', 'range_test', 'private', 'atak'
                    ]
                    
                    for j, msg_type in enumerate(message_types):
                        if not isinstance(msg_type, str):
                            self.logger.error(f"Configuration validation failed: channels[{i}].message_types[{j}] must be a string, got {type(msg_type).__name__}")
                            return False
                        if msg_type not in valid_message_types:
                            self.logger.error(f"Configuration validation failed: channels[{i}].message_types[{j}] has invalid value '{msg_type}', must be one of {valid_message_types}")
                            return False
            
            self._config_cache['channels'] = channels
            
            self.logger.info(f"Configuration validated successfully: "
                           f"broker={self._config_cache['broker_address']}:{self._config_cache['broker_port']}, "
                           f"format={self._config_cache['format']}, "
                           f"channels={len(self._config_cache['channels'])}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation error: {e}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """
        Start the plugin.
        
        This method:
        1. Connects to the MQTT broker
        2. Starts background tasks for queue processing
        3. Begins accepting messages from the mesh
        
        Returns:
            True if started successfully, False otherwise
            
        Requirements: 1.4, 2.1
        """
        if not self.initialized:
            self.logger.error("Cannot start plugin: not initialized")
            return False
        
        # Log startup with configuration details (Requirement 11.1)
        self.logger.info(
            f"Starting MQTT Gateway plugin - "
            f"broker={self._config_cache.get('broker_address')}:{self._config_cache.get('broker_port')}, "
            f"format={self._config_cache.get('format')}, "
            f"encryption={self._config_cache.get('encryption_enabled')}, "
            f"max_rate={self._config_cache.get('max_messages_per_second')} msg/s, "
            f"queue_max={self._config_cache.get('queue_max_size')}"
        )
        
        try:
            # Connect to MQTT broker
            if self.mqtt_client:
                connected = await self.mqtt_client.connect()
                if connected:
                    self.stats['connected'] = True
                    # Log successful connection (Requirement 11.1)
                    self.logger.info(
                        f"Connected to MQTT broker - "
                        f"broker={self._config_cache.get('broker_address')}:{self._config_cache.get('broker_port')}, "
                        f"tls={'enabled' if self._config_cache.get('tls_enabled') else 'disabled'}"
                    )
                else:
                    # Log connection failure (Requirement 11.3)
                    self.logger.warning(
                        f"Failed to connect to MQTT broker, will retry in background - "
                        f"broker={self._config_cache.get('broker_address')}:{self._config_cache.get('broker_port')}"
                    )
                    # Start reconnection in background
                    asyncio.create_task(self.mqtt_client.reconnect())
            
            # Start background queue processing task
            task = asyncio.create_task(self._process_queue_loop())
            self._background_tasks.append(task)
            self.logger.info("Started queue processing background task")
            
            self.logger.info("MQTT Gateway plugin started successfully")
            return True
            
        except Exception as e:
            # Log startup error with stack trace (Requirement 11.3)
            self.logger.error(
                f"Failed to start MQTT Gateway plugin - "
                f"error={e}",
                exc_info=True
            )
            return False
    
    async def stop(self) -> bool:
        """
        Stop the plugin.
        
        This method:
        1. Disconnects from the MQTT broker
        2. Stops background tasks
        3. Flushes the message queue
        4. Cleans up resources
        
        Returns:
            True if stopped successfully, False otherwise
            
        Requirements: 8.5
        """
        # Log shutdown with statistics (Requirement 11.1)
        self.logger.info(
            f"Stopping MQTT Gateway plugin - "
            f"messages_received={self.stats['messages_received']}, "
            f"messages_published={self.stats['messages_published']}, "
            f"messages_queued={self.stats['messages_queued']}, "
            f"messages_dropped={self.stats['messages_dropped']}, "
            f"publish_errors={self.stats['publish_errors']}"
        )
        
        try:
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._background_tasks.clear()
            self.logger.info("Stopped background tasks")
            
            # Disconnect from MQTT broker
            if self.mqtt_client:
                await self.mqtt_client.disconnect()
                # Log disconnection (Requirement 11.1)
                self.logger.info(
                    f"Disconnected from MQTT broker - "
                    f"broker={self._config_cache.get('broker_address')}:{self._config_cache.get('broker_port')}"
                )
            
            # Clear message queue
            if self.message_queue:
                queue_size = self.message_queue.size()
                await self.message_queue.clear()
                # Log queue clear (Requirement 11.4)
                if queue_size > 0:
                    self.logger.warning(
                        f"Cleared message queue on shutdown - "
                        f"messages_lost={queue_size}"
                    )
            
            self.stats['connected'] = False
            self.logger.info("MQTT Gateway plugin stopped successfully")
            return True
            
        except Exception as e:
            # Log shutdown error with stack trace (Requirement 11.3)
            self.logger.error(
                f"Error stopping MQTT Gateway plugin - "
                f"error={e}",
                exc_info=True
            )
            return False
    
    async def _handle_mesh_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """
        Handle incoming message from the mesh network.
        
        This is the main entry point for messages from the message router.
        Messages are filtered, formatted, and forwarded to MQTT asynchronously.
        
        Args:
            message: The message received from the mesh
            context: Message context (timestamp, plugin_name, etc.)
            
        Returns:
            None (this plugin doesn't generate responses)
            
        Requirements: 4.1, 10.2, 10.3
        """
        try:
            self.stats['messages_received'] += 1
            
            # Quick validation - don't process if not enabled
            if not self.enabled or not self.initialized:
                return None
            
            # Log incoming message (Requirement 11.2)
            self.logger.debug(
                f"Received mesh message - "
                f"id={message.id}, "
                f"type={message.message_type.value}, "
                f"sender={message.sender_id}, "
                f"channel={message.channel}, "
                f"total_received={self.stats['messages_received']}"
            )
            
            # Check if message should be forwarded
            if not self._should_forward_message(message):
                self.logger.debug(
                    f"Message filtered out - "
                    f"id={message.id}, "
                    f"type={message.message_type.value}, "
                    f"channel={message.channel}, "
                    f"reason=uplink_disabled_or_type_filtered"
                )
                return None
            
            # Format and publish message asynchronously (don't block message router)
            asyncio.create_task(self._publish_message_async(message))
            
            return None
            
        except Exception as e:
            # Log error with stack trace (Requirement 11.3)
            self.logger.error(
                f"Error handling mesh message - "
                f"id={message.id if message else 'unknown'}, "
                f"error={e}",
                exc_info=True
            )
            return None
    
    def _should_forward_message(self, message: Message) -> bool:
        """
        Determine if a message should be forwarded to MQTT.
        
        Checks:
        - Channel uplink configuration
        - Message type filtering
        - Other filtering criteria
        
        Args:
            message: The message to check
            
        Returns:
            True if message should be forwarded, False otherwise
            
        Requirements: 4.2, 4.3, 12.1, 12.2, 12.3
        """
        if not self.message_formatter:
            return False
        
        # Check if uplink is enabled for this channel
        if not self.message_formatter.is_uplink_enabled(message.channel):
            self.logger.debug(f"Uplink disabled for channel {message.channel}")
            return False
        
        # Check message type filtering
        if not self.message_formatter.should_forward_message(message):
            self.logger.debug(f"Message type {message.message_type} filtered for channel {message.channel}")
            return False
        
        return True
    
    async def _publish_message_async(self, message: Message):
        """
        Publish a message to MQTT asynchronously.
        
        This method:
        1. Formats the message (protobuf or JSON)
        2. Waits for rate limiter
        3. Publishes to MQTT or queues if disconnected
        4. Updates statistics
        
        Handles errors gracefully:
        - Serialization errors (invalid message data)
        - Rate limiter errors
        - Publish errors (connection lost, broker errors)
        - Queue errors (overflow)
        
        Args:
            message: The message to publish
            
        Requirements: 10.3, 7.1, 4.5, 8.4
        """
        try:
            # Format message based on configuration
            format_type = self._config_cache.get('format', 'json')
            topic = None
            payload = None
            
            try:
                # Generate topic path first (less likely to fail)
                topic = self.message_formatter.get_topic_path(message)
                
                # Format message payload
                if format_type == 'protobuf':
                    payload = self.message_formatter.format_protobuf(message)
                else:  # json
                    payload = self.message_formatter.format_json(message).encode('utf-8')
                    
            except ValueError as e:
                # Serialization error - log and skip this message (Requirement 11.3)
                self.logger.error(
                    f"Failed to format message - "
                    f"id={message.id}, "
                    f"type={message.message_type.value}, "
                    f"sender={message.sender_id}, "
                    f"format={format_type}, "
                    f"error={e}",
                    exc_info=True
                )
                self.stats['publish_errors'] += 1
                return
            except Exception as e:
                # Unexpected serialization error (Requirement 11.3)
                self.logger.error(
                    f"Unexpected error formatting message - "
                    f"id={message.id}, "
                    f"type={message.message_type.value}, "
                    f"sender={message.sender_id}, "
                    f"error={e}",
                    exc_info=True
                )
                self.stats['publish_errors'] += 1
                return
            
            # Validate formatted data
            if not topic:
                self.logger.error(
                    f"Failed to generate topic path - "
                    f"id={message.id}, "
                    f"sender={message.sender_id}, "
                    f"channel={message.channel}"
                )
                self.stats['publish_errors'] += 1
                return
            
            if not payload:
                self.logger.warning(
                    f"Empty payload for message - "
                    f"id={message.id}, "
                    f"topic={topic}, "
                    f"skipping"
                )
                return
            
            # Wait for rate limiter
            try:
                await self.rate_limiter.acquire()
            except Exception as e:
                # Rate limiter error - log but continue (Requirement 11.3)
                self.logger.error(
                    f"Rate limiter error - "
                    f"id={message.id}, "
                    f"error={e}",
                    exc_info=True
                )
                # Continue anyway - better to publish than drop the message
            
            # Publish or queue based on connection status
            if self.mqtt_client.is_connected():
                # Publish directly to MQTT
                try:
                    success = await self.mqtt_client.publish(topic, payload, qos=0)
                    
                    if success:
                        self.stats['messages_published'] += 1
                        self.stats['last_publish_time'] = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
                        
                        # Log successful publish (Requirement 11.2)
                        if self._config_cache.get('log_published_messages', True):
                            self.logger.info(
                                f"Published message to MQTT - "
                                f"id={message.id}, "
                                f"topic={topic}, "
                                f"type={message.message_type.value}, "
                                f"sender={message.sender_id}, "
                                f"size={len(payload)} bytes, "
                                f"total_published={self.stats['messages_published']}"
                            )
                    else:
                        # Publish failed, queue for retry
                        try:
                            await self.message_queue.enqueue(message, topic, payload)
                            self.stats['messages_queued'] += 1
                            # Log queue event (Requirement 11.4)
                            self.logger.warning(
                                f"Publish failed, queued message for retry - "
                                f"id={message.id}, "
                                f"topic={topic}, "
                                f"queue_size={self.message_queue.size()}"
                            )
                        except Exception as e:
                            # Log queue error (Requirement 11.3)
                            self.logger.error(
                                f"Failed to queue message after publish failure - "
                                f"id={message.id}, "
                                f"topic={topic}, "
                                f"error={e}",
                                exc_info=True
                            )
                            self.stats['messages_dropped'] += 1
                            
                except Exception as e:
                    # Unexpected publish error (Requirement 11.3)
                    self.logger.error(
                        f"Unexpected error during publish - "
                        f"id={message.id}, "
                        f"topic={topic}, "
                        f"error={e}",
                        exc_info=True
                    )
                    self.stats['publish_errors'] += 1
                    
                    # Try to queue the message
                    try:
                        await self.message_queue.enqueue(message, topic, payload)
                        self.stats['messages_queued'] += 1
                        # Log queue event (Requirement 11.4)
                        self.logger.info(
                            f"Queued message after publish error - "
                            f"id={message.id}, "
                            f"topic={topic}, "
                            f"queue_size={self.message_queue.size()}"
                        )
                    except Exception as queue_error:
                        # Log queue error (Requirement 11.3)
                        self.logger.error(
                            f"Failed to queue message after error - "
                            f"id={message.id}, "
                            f"topic={topic}, "
                            f"error={queue_error}",
                            exc_info=True
                        )
                        self.stats['messages_dropped'] += 1
            else:
                # Not connected, queue message
                try:
                    await self.message_queue.enqueue(message, topic, payload)
                    self.stats['messages_queued'] += 1
                    # Log queue event (Requirement 11.4)
                    self.logger.debug(
                        f"Not connected, queued message - "
                        f"id={message.id}, "
                        f"topic={topic}, "
                        f"queue_size={self.message_queue.size()}"
                    )
                except Exception as e:
                    # Queue error - message will be dropped (Requirement 11.3)
                    self.logger.error(
                        f"Failed to queue message while disconnected - "
                        f"id={message.id}, "
                        f"topic={topic}, "
                        f"error={e}",
                        exc_info=True
                    )
                    self.stats['messages_dropped'] += 1
            
        except Exception as e:
            # Catch-all for any unexpected errors (Requirement 11.3)
            self.logger.error(
                f"Unexpected error in _publish_message_async - "
                f"id={message.id if message else 'unknown'}, "
                f"error={e}",
                exc_info=True
            )
            self.stats['publish_errors'] += 1
    
    async def _process_queue_loop(self):
        """
        Background task to process queued messages.
        
        Runs continuously while the plugin is active, processing queued messages
        when the MQTT broker connection is restored.
        
        Handles errors gracefully:
        - Queue errors (empty queue, dequeue failures)
        - Publish errors (connection lost, broker errors)
        - Rate limiter errors
        
        Requirements: 8.3, 8.4
        """
        self.logger.info("Queue processing loop started")
        
        while True:
            try:
                # Process queue when connected and queue is not empty
                if self.mqtt_client.is_connected() and not self.message_queue.is_empty():
                    queue_size = self.message_queue.size()
                    
                    # Log queue processing start if queue has messages (Requirement 11.4)
                    if queue_size > 0:
                        self.logger.info(
                            f"Processing message queue - "
                            f"queue_size={queue_size}, "
                            f"connected=True"
                        )
                    
                    # Dequeue a message
                    try:
                        queued_msg = await self.message_queue.dequeue()
                    except Exception as e:
                        # Log dequeue error (Requirement 11.3)
                        self.logger.error(
                            f"Error dequeuing message - "
                            f"error={e}",
                            exc_info=True
                        )
                        await asyncio.sleep(1)
                        continue
                    
                    if queued_msg:
                        # Wait for rate limiter
                        try:
                            await self.rate_limiter.acquire()
                        except Exception as e:
                            # Rate limiter error - log but continue (Requirement 11.3)
                            self.logger.error(
                                f"Rate limiter error in queue processing - "
                                f"error={e}",
                                exc_info=True
                            )
                            # Continue anyway - better to publish than drop the message
                        
                        # Try to publish
                        try:
                            success = await self.mqtt_client.publish(
                                queued_msg.topic,
                                queued_msg.payload,
                                qos=queued_msg.qos
                            )
                            
                            if success:
                                self.stats['messages_published'] += 1
                                self.stats['last_publish_time'] = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
                                
                                # Log successful publish of queued message (Requirement 11.2)
                                if self._config_cache.get('log_published_messages', True):
                                    self.logger.info(
                                        f"Published queued message - "
                                        f"id={queued_msg.message.id}, "
                                        f"topic={queued_msg.topic}, "
                                        f"retry_count={queued_msg.retry_count}, "
                                        f"queue_size={self.message_queue.size()}"
                                    )
                            else:
                                # Publish failed, check retry count
                                if queued_msg.retry_count < queued_msg.max_retries:
                                    # Re-queue for retry
                                    queued_msg.retry_count += 1
                                    try:
                                        await self.message_queue.enqueue(
                                            queued_msg.message,
                                            queued_msg.topic,
                                            queued_msg.payload,
                                            qos=queued_msg.qos,
                                            priority=queued_msg.priority
                                        )
                                        # Log re-queue (Requirement 11.4)
                                        self.logger.warning(
                                            f"Publish failed, re-queued - "
                                            f"id={queued_msg.message.id}, "
                                            f"topic={queued_msg.topic}, "
                                            f"retry={queued_msg.retry_count}/{queued_msg.max_retries}"
                                        )
                                    except Exception as e:
                                        # Failed to re-queue - message will be dropped (Requirement 11.3)
                                        self.logger.error(
                                            f"Failed to re-queue message - "
                                            f"id={queued_msg.message.id}, "
                                            f"topic={queued_msg.topic}, "
                                            f"error={e}",
                                            exc_info=True
                                        )
                                        self.stats['messages_dropped'] += 1
                                else:
                                    # Max retries exceeded, drop message (Requirement 11.3)
                                    self.stats['messages_dropped'] += 1
                                    self.logger.error(
                                        f"Message dropped after max retries - "
                                        f"id={queued_msg.message.id}, "
                                        f"topic={queued_msg.topic}, "
                                        f"retries={queued_msg.max_retries}"
                                    )
                                    
                        except Exception as e:
                            # Unexpected publish error (Requirement 11.3)
                            self.logger.error(
                                f"Unexpected error publishing queued message - "
                                f"id={queued_msg.message.id}, "
                                f"topic={queued_msg.topic}, "
                                f"error={e}",
                                exc_info=True
                            )
                            
                            # Try to re-queue if retries remain
                            if queued_msg.retry_count < queued_msg.max_retries:
                                queued_msg.retry_count += 1
                                try:
                                    await self.message_queue.enqueue(
                                        queued_msg.message,
                                        queued_msg.topic,
                                        queued_msg.payload,
                                        qos=queued_msg.qos,
                                        priority=queued_msg.priority
                                    )
                                    # Log re-queue (Requirement 11.4)
                                    self.logger.info(
                                        f"Re-queued message after error - "
                                        f"id={queued_msg.message.id}, "
                                        f"retry={queued_msg.retry_count}/{queued_msg.max_retries}"
                                    )
                                except Exception as queue_error:
                                    # Log queue error (Requirement 11.3)
                                    self.logger.error(
                                        f"Failed to re-queue after error - "
                                        f"id={queued_msg.message.id}, "
                                        f"error={queue_error}",
                                        exc_info=True
                                    )
                                    self.stats['messages_dropped'] += 1
                            else:
                                self.stats['messages_dropped'] += 1
                                # Log drop (Requirement 11.3)
                                self.logger.error(
                                    f"Message dropped after max retries - "
                                    f"id={queued_msg.message.id}, "
                                    f"retries={queued_msg.max_retries}"
                                )
                
                # Update connection status in stats
                try:
                    self.stats['connected'] = self.mqtt_client.is_connected() if self.mqtt_client else False
                except Exception as e:
                    self.logger.warning(f"Error checking connection status: {e}")
                    self.stats['connected'] = False
                
                # Sleep to avoid busy-waiting
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                self.logger.info("Queue processing loop cancelled")
                break
            except Exception as e:
                # Catch-all for unexpected errors in the loop (Requirement 11.3)
                self.logger.error(
                    f"Unexpected error in queue processing loop - "
                    f"error={e}",
                    exc_info=True
                )
                await asyncio.sleep(5)  # Wait longer after unexpected errors
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get plugin health status.
        
        Returns comprehensive health status including:
        - Connection status
        - Queue size and statistics
        - Message counters
        - Error counts
        - Rate limiter statistics
        - MQTT client statistics
        
        Returns:
            Dictionary containing health status and statistics
            
        Requirements: 11.1, 11.4
        """
        # Get queue statistics
        queue_size = self.message_queue.size() if self.message_queue else 0
        queue_max_size = self._config_cache.get('queue_max_size', 1000) if self._config_cache else 1000
        queue_utilization = (queue_size / queue_max_size * 100) if queue_max_size > 0 else 0
        
        # Get MQTT client statistics
        mqtt_stats = {}
        if self.mqtt_client:
            try:
                mqtt_stats = self.mqtt_client.get_stats()
            except Exception as e:
                self.logger.warning(f"Failed to get MQTT client stats: {e}")
        
        # Get rate limiter statistics
        rate_limiter_stats = {}
        if self.rate_limiter:
            try:
                rate_limiter_stats = self.rate_limiter.get_statistics()
            except Exception as e:
                self.logger.warning(f"Failed to get rate limiter stats: {e}")
        
        # Build comprehensive health status
        health_status = {
            # Overall health
            'healthy': self.enabled and self.initialized and self.stats['connected'],
            'enabled': self.enabled,
            'initialized': self.initialized,
            
            # Connection status (Requirement 11.1)
            'connected': self.stats['connected'],
            'connection_count': mqtt_stats.get('connection_count', 0),
            'disconnection_count': mqtt_stats.get('disconnection_count', 0),
            'reconnection_count': mqtt_stats.get('reconnection_count', 0),
            'last_connect_time': mqtt_stats.get('last_connect_time').isoformat() if mqtt_stats.get('last_connect_time') else None,
            'last_disconnect_time': mqtt_stats.get('last_disconnect_time').isoformat() if mqtt_stats.get('last_disconnect_time') else None,
            
            # Message counters (Requirement 11.4)
            'messages_received': self.stats['messages_received'],
            'messages_published': self.stats['messages_published'],
            'messages_queued': self.stats['messages_queued'],
            'messages_dropped': self.stats['messages_dropped'],
            'last_publish_time': self.stats['last_publish_time'].isoformat() if self.stats['last_publish_time'] else None,
            
            # Error counts (Requirement 11.4)
            'publish_errors': self.stats['publish_errors'],
            'mqtt_publish_errors': mqtt_stats.get('publish_errors', 0),
            
            # Queue statistics (Requirement 11.4)
            'queue_size': queue_size,
            'queue_max_size': queue_max_size,
            'queue_utilization_percent': round(queue_utilization, 2),
            
            # Rate limiter statistics (Requirement 11.4)
            'rate_limit': {
                'max_messages_per_second': rate_limiter_stats.get('max_messages_per_second', 0),
                'burst_capacity': rate_limiter_stats.get('burst_capacity', 0),
                'current_tokens': round(rate_limiter_stats.get('current_tokens', 0), 2),
                'messages_allowed': rate_limiter_stats.get('messages_allowed', 0),
                'messages_delayed': rate_limiter_stats.get('messages_delayed', 0),
                'total_wait_time': round(rate_limiter_stats.get('total_wait_time', 0), 3),
                'max_wait_time': round(rate_limiter_stats.get('max_wait_time', 0), 3),
                'avg_wait_time': round(rate_limiter_stats.get('avg_wait_time', 0), 3),
            },
        }
        
        return health_status
    
    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.
        
        Returns:
            Plugin metadata object
        """
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="MQTT Gateway for forwarding Meshtastic mesh messages to MQTT brokers",
            author="ZephyrGate Team"
        )
    
    async def cleanup(self) -> bool:
        """
        Clean up plugin resources.
        
        Called when the plugin is being unloaded.
        
        Returns:
            True if cleanup successful, False otherwise
        """
        return await self.stop()


def create_plugin(name: str, config: dict, plugin_manager):
    """
    Factory function to create plugin instance.
    
    Args:
        name: Plugin name
        config: Plugin configuration
        plugin_manager: Plugin manager instance
        
    Returns:
        MQTTGatewayPlugin instance
    """
    return MQTTGatewayPlugin(name, config, plugin_manager)
