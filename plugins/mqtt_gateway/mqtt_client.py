"""
MQTT Client Wrapper for ZephyrGate MQTT Gateway

Provides an async wrapper around paho-mqtt with connection management,
TLS/SSL support, and automatic reconnection with exponential backoff.

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import asyncio
import logging
import ssl
from enum import Enum
from typing import Dict, Any, Optional, Callable
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    raise ImportError("paho-mqtt library is required. Install with: pip install paho-mqtt>=1.6.1")


class ConnectionState(Enum):
    """MQTT connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    RECONNECTING = "reconnecting"


class MQTTClient:
    """
    Async MQTT client wrapper for paho-mqtt.
    
    Provides:
    - Async connection management
    - TLS/SSL configuration
    - Automatic reconnection with exponential backoff
    - Connection state tracking
    - Message publishing with QoS support
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """
        Initialize MQTT client.
        
        Args:
            config: Configuration dictionary containing:
                - broker_address: MQTT broker hostname/IP (required)
                - broker_port: MQTT broker port (default: 1883)
                - username: MQTT username (optional)
                - password: MQTT password (optional)
                - tls_enabled: Enable TLS/SSL (default: False)
                - ca_cert: Path to CA certificate (optional)
                - client_cert: Path to client certificate (optional)
                - client_key: Path to client key (optional)
                - reconnect_enabled: Enable automatic reconnection (default: True)
                - reconnect_initial_delay: Initial reconnection delay in seconds (default: 1)
                - reconnect_max_delay: Maximum reconnection delay in seconds (default: 60)
                - reconnect_multiplier: Backoff multiplier (default: 2.0)
                - max_reconnect_attempts: Maximum reconnection attempts, -1 for infinite (default: -1)
            logger: Logger instance (optional)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._state_lock = asyncio.Lock()
        
        # Reconnection state
        self._reconnect_attempt = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        
        # Statistics
        self.stats = {
            'connection_count': 0,
            'disconnection_count': 0,
            'reconnection_count': 0,
            'messages_published': 0,
            'publish_errors': 0,
            'last_connect_time': None,
            'last_disconnect_time': None,
        }
        
        # Create paho-mqtt client
        self._client = mqtt.Client(
            client_id=f"zephyrgate_{id(self)}",
            clean_session=True,
            protocol=mqtt.MQTTv311
        )
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish = self._on_publish
        
        # Event for connection status
        self._connected_event = asyncio.Event()
        self._disconnected_event = asyncio.Event()
        self._disconnected_event.set()  # Initially disconnected
        
        # Configure client
        self._configure_client()
    
    def _configure_client(self):
        """
        Configure the MQTT client with credentials and TLS settings.
        
        Requirements: 2.1, 2.2, 2.3
        """
        # Set username and password if provided
        username = self.config.get('username', '')
        password = self.config.get('password', '')
        if username:
            self._client.username_pw_set(username, password)
            self.logger.debug(f"Set MQTT credentials for user: {username}")
        
        # Configure TLS/SSL if enabled
        if self.config.get('tls_enabled', False):
            try:
                ca_cert = self.config.get('ca_cert', None)
                client_cert = self.config.get('client_cert', None)
                client_key = self.config.get('client_key', None)
                
                # Set TLS parameters
                self._client.tls_set(
                    ca_certs=ca_cert if ca_cert else None,
                    certfile=client_cert if client_cert else None,
                    keyfile=client_key if client_key else None,
                    cert_reqs=ssl.CERT_REQUIRED if ca_cert else ssl.CERT_NONE,
                    tls_version=ssl.PROTOCOL_TLS,
                    ciphers=None
                )
                
                # Disable hostname verification if no CA cert provided
                if not ca_cert:
                    self._client.tls_insecure_set(True)
                
                self.logger.info("TLS/SSL enabled for MQTT connection")
                
            except Exception as e:
                self.logger.error(f"Failed to configure TLS/SSL: {e}", exc_info=True)
                raise
    
    async def connect(self) -> bool:
        """
        Connect to the MQTT broker.
        
        Handles connection errors gracefully:
        - Network errors (broker unreachable)
        - Authentication failures
        - TLS/SSL errors
        - Timeout errors
        
        Returns:
            True if connection successful, False otherwise
            
        Requirements: 2.1, 2.4, 8.4
        """
        async with self._state_lock:
            if self._state == ConnectionState.CONNECTED:
                self.logger.warning("Already connected to MQTT broker")
                return True
            
            if self._state == ConnectionState.CONNECTING:
                self.logger.warning("Connection already in progress")
                return False
            
            self._state = ConnectionState.CONNECTING
        
        try:
            broker_address = self.config['broker_address']
            broker_port = self.config.get('broker_port', 1883)
            
            self.logger.info(f"Connecting to MQTT broker at {broker_address}:{broker_port}")
            
            # Clear the connected event
            self._connected_event.clear()
            self._disconnected_event.clear()
            
            # Connect asynchronously
            try:
                self._client.connect_async(
                    host=broker_address,
                    port=broker_port,
                    keepalive=60
                )
            except ValueError as e:
                # Invalid broker address or port
                self.logger.error(f"Invalid broker configuration: {e}")
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                self._disconnected_event.set()
                return False
            except OSError as e:
                # Network error (e.g., DNS resolution failure, network unreachable)
                self.logger.error(f"Network error connecting to broker: {e}")
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                self._disconnected_event.set()
                return False
            
            # Start the network loop
            try:
                self._client.loop_start()
            except Exception as e:
                self.logger.error(f"Failed to start MQTT network loop: {e}", exc_info=True)
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                self._disconnected_event.set()
                return False
            
            # Wait for connection with timeout
            try:
                await asyncio.wait_for(self._connected_event.wait(), timeout=10.0)
                self.logger.info("Successfully connected to MQTT broker")
                return True
            except asyncio.TimeoutError:
                self.logger.error(f"Connection timeout after 10 seconds - broker may be unreachable at {broker_address}:{broker_port}")
                # Stop the network loop on timeout
                try:
                    self._client.loop_stop()
                except Exception as e:
                    self.logger.warning(f"Error stopping network loop after timeout: {e}")
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                self._disconnected_event.set()
                return False
            
        except KeyError as e:
            # Missing required configuration
            self.logger.error(f"Missing required configuration parameter: {e}")
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            self._disconnected_event.set()
            return False
        except ssl.SSLError as e:
            # TLS/SSL error
            self.logger.error(f"TLS/SSL error connecting to broker: {e}", exc_info=True)
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            self._disconnected_event.set()
            return False
        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Unexpected error connecting to MQTT broker: {e}", exc_info=True)
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            self._disconnected_event.set()
            return False
    
    async def disconnect(self) -> None:
        """
        Disconnect from the MQTT broker.
        
        Requirements: 2.1
        """
        async with self._state_lock:
            if self._state == ConnectionState.DISCONNECTED:
                self.logger.debug("Already disconnected from MQTT broker")
                return
            
            self._state = ConnectionState.DISCONNECTING
        
        try:
            # Stop automatic reconnection
            self._should_reconnect = False
            
            # Cancel reconnection task if running
            if self._reconnect_task and not self._reconnect_task.done():
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("Disconnecting from MQTT broker")
            
            # Disconnect from broker
            self._client.disconnect()
            
            # Stop the network loop
            self._client.loop_stop()
            
            # Wait for disconnection
            await asyncio.wait_for(self._disconnected_event.wait(), timeout=5.0)
            
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            
            self.logger.info("Disconnected from MQTT broker")
            
        except asyncio.TimeoutError:
            self.logger.warning("Disconnect timeout, forcing disconnection")
            self._client.loop_stop()
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            self._disconnected_event.set()
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}", exc_info=True)
            async with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
            self._disconnected_event.set()
    
    async def reconnect(self) -> bool:
        """
        Reconnect to the MQTT broker with exponential backoff.
        
        Returns:
            True if reconnection successful, False otherwise
            
        Requirements: 2.5, 2.6, 8.2
        """
        if not self.config.get('reconnect_enabled', True):
            self.logger.info("Reconnection is disabled in configuration")
            return False
        
        async with self._state_lock:
            if self._state == ConnectionState.CONNECTED:
                self.logger.debug("Already connected, no need to reconnect")
                return True
            
            if self._state == ConnectionState.RECONNECTING:
                self.logger.debug("Reconnection already in progress")
                return False
            
            self._state = ConnectionState.RECONNECTING
        
        initial_delay = self.config.get('reconnect_initial_delay', 1)
        max_delay = self.config.get('reconnect_max_delay', 60)
        multiplier = self.config.get('reconnect_multiplier', 2.0)
        max_attempts = self.config.get('max_reconnect_attempts', -1)
        
        self._reconnect_attempt = 0
        
        while self._should_reconnect:
            # Check if we've exceeded max attempts
            if max_attempts > 0 and self._reconnect_attempt >= max_attempts:
                self.logger.error(
                    f"Maximum reconnection attempts ({max_attempts}) exceeded - "
                    f"giving up reconnection to {self.config.get('broker_address', 'unknown')}"
                )
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                return False
            
            # Calculate backoff delay
            delay = self._calculate_backoff_delay(
                self._reconnect_attempt,
                initial_delay,
                max_delay,
                multiplier
            )
            
            # Log reconnection attempt with backoff details (Requirement 11.1, 11.5)
            self.logger.info(
                f"Reconnection attempt {self._reconnect_attempt + 1} "
                f"in {delay:.1f} seconds - "
                f"broker={self.config.get('broker_address', 'unknown')}:{self.config.get('broker_port', 1883)}, "
                f"backoff_multiplier={multiplier}, "
                f"max_delay={max_delay}s"
            )
            
            # Wait for backoff delay
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                self.logger.info("Reconnection cancelled")
                async with self._state_lock:
                    self._state = ConnectionState.DISCONNECTED
                return False
            
            # Attempt to connect
            self._reconnect_attempt += 1
            success = await self.connect()
            
            if success:
                self.logger.info(
                    f"Reconnection successful after {self._reconnect_attempt} attempts - "
                    f"total_wait_time={(sum(self._calculate_backoff_delay(i, initial_delay, max_delay, multiplier) for i in range(self._reconnect_attempt))):.1f}s"
                )
                self.stats['reconnection_count'] += 1
                self._reconnect_attempt = 0
                return True
            
            self.logger.warning(
                f"Reconnection attempt {self._reconnect_attempt} failed - "
                f"will retry with exponential backoff"
            )
        
        async with self._state_lock:
            self._state = ConnectionState.DISCONNECTED
        return False
    
    def _calculate_backoff_delay(
        self,
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float
    ) -> float:
        """
        Calculate exponential backoff delay.
        
        Formula: min(initial_delay * (multiplier ^ attempt), max_delay)
        
        Args:
            attempt: Current attempt number (0-indexed)
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Backoff multiplier
            
        Returns:
            Delay in seconds
            
        Requirements: 2.5, 2.6
        """
        delay = initial_delay * (multiplier ** attempt)
        return min(delay, max_delay)
    
    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False
    ) -> bool:
        """
        Publish a message to an MQTT topic.
        
        Handles publish errors gracefully:
        - Connection lost during publish
        - Invalid topic or payload
        - Broker errors (rate limiting, quota exceeded)
        - Network errors
        
        Args:
            topic: MQTT topic to publish to
            payload: Message payload (bytes)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message on the broker
            
        Returns:
            True if publish successful, False otherwise
            
        Requirements: 4.1, 8.4
        """
        if not self.is_connected():
            self.logger.warning("Cannot publish: not connected to MQTT broker")
            return False
        
        # Validate inputs
        if not topic:
            self.logger.error("Cannot publish: empty topic")
            self.stats['publish_errors'] += 1
            return False
        
        if not isinstance(payload, bytes):
            self.logger.error(f"Cannot publish: payload must be bytes, got {type(payload)}")
            self.stats['publish_errors'] += 1
            return False
        
        if qos not in (0, 1, 2):
            self.logger.error(f"Cannot publish: invalid QoS level {qos}, must be 0, 1, or 2")
            self.stats['publish_errors'] += 1
            return False
        
        try:
            result = self._client.publish(topic, payload, qos=qos, retain=retain)
            
            # Check result code
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.stats['messages_published'] += 1
                # Log successful publish with details (Requirement 11.2)
                self.logger.debug(
                    f"Published message to MQTT - "
                    f"topic={topic}, "
                    f"size={len(payload)} bytes, "
                    f"qos={qos}, "
                    f"retain={retain}, "
                    f"mid={result.mid}"
                )
                return True
            elif result.rc == mqtt.MQTT_ERR_NO_CONN:
                # Log connection error (Requirement 11.3)
                self.logger.error(
                    f"Publish failed: not connected to broker - "
                    f"topic={topic}, "
                    f"size={len(payload)} bytes"
                )
                self.stats['publish_errors'] += 1
                return False
            elif result.rc == mqtt.MQTT_ERR_QUEUE_SIZE:
                # Log rate limiting error (Requirement 11.5)
                self.logger.error(
                    f"Publish failed: internal queue full (rate limiting) - "
                    f"topic={topic}, "
                    f"size={len(payload)} bytes, "
                    f"broker may be rate limiting"
                )
                self.stats['publish_errors'] += 1
                return False
            else:
                # Log other publish errors (Requirement 11.3)
                self.logger.error(
                    f"Publish failed with return code: {result.rc} - "
                    f"topic={topic}, "
                    f"size={len(payload)} bytes"
                )
                self.stats['publish_errors'] += 1
                return False
                
        except ValueError as e:
            # Invalid topic or payload (Requirement 11.3)
            self.logger.error(
                f"Invalid publish parameters: {e} - "
                f"topic={topic}, "
                f"payload_type={type(payload).__name__}, "
                f"qos={qos}",
                exc_info=True
            )
            self.stats['publish_errors'] += 1
            return False
        except OSError as e:
            # Network error during publish (Requirement 11.3)
            self.logger.error(
                f"Network error during publish: {e} - "
                f"topic={topic}, "
                f"size={len(payload)} bytes, "
                f"broker={self.config.get('broker_address', 'unknown')}",
                exc_info=True
            )
            self.stats['publish_errors'] += 1
            return False
        except Exception as e:
            # Catch-all for unexpected errors (Requirement 11.3)
            self.logger.error(
                f"Unexpected error publishing message: {e} - "
                f"topic={topic}, "
                f"size={len(payload)} bytes",
                exc_info=True
            )
            self.stats['publish_errors'] += 1
            return False
    
    def is_connected(self) -> bool:
        """
        Check if connected to MQTT broker.
        
        Returns:
            True if connected, False otherwise
        """
        return self._state == ConnectionState.CONNECTED
    
    def get_state(self) -> ConnectionState:
        """
        Get current connection state.
        
        Returns:
            Current ConnectionState
        """
        return self._state
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()
    
    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback for successful connection.
        
        Args:
            client: MQTT client instance
            userdata: User data
            flags: Connection flags
            rc: Return code
        """
        if rc == 0:
            # Log successful connection with broker details (Requirement 11.1)
            broker_address = self.config.get('broker_address', 'unknown')
            broker_port = self.config.get('broker_port', 1883)
            tls_enabled = self.config.get('tls_enabled', False)
            username = self.config.get('username', '')
            # Handle flags being None or dict
            session_present = flags.get('session present', False) if isinstance(flags, dict) else False
            
            self.logger.info(
                f"MQTT connection established - "
                f"broker={broker_address}:{broker_port}, "
                f"tls={'enabled' if tls_enabled else 'disabled'}, "
                f"username={username if username else 'anonymous'}, "
                f"clean_session={session_present}"
            )
            asyncio.create_task(self._handle_connect_success())
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Connection refused - unknown error ({rc})")
            
            # Log connection failure with broker details (Requirement 11.3)
            broker_address = self.config.get('broker_address', 'unknown')
            broker_port = self.config.get('broker_port', 1883)
            username = self.config.get('username', '')
            
            self.logger.error(
                f"MQTT connection failed: {error_msg} - "
                f"broker={broker_address}:{broker_port}, "
                f"username={username if username else 'anonymous'}"
            )
            asyncio.create_task(self._handle_connect_failure())
    
    async def _handle_connect_success(self):
        """Handle successful connection."""
        async with self._state_lock:
            self._state = ConnectionState.CONNECTED
        
        self.stats['connection_count'] += 1
        self.stats['last_connect_time'] = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        self._reconnect_attempt = 0
        self._should_reconnect = True
        
        self._connected_event.set()
        self._disconnected_event.clear()
    
    async def _handle_connect_failure(self):
        """Handle connection failure."""
        async with self._state_lock:
            self._state = ConnectionState.DISCONNECTED
        
        self._connected_event.clear()
        self._disconnected_event.set()
    
    def _on_disconnect(self, client, userdata, rc):
        """
        Callback for disconnection.
        
        Args:
            client: MQTT client instance
            userdata: User data
            rc: Return code (0 = clean disconnect, >0 = unexpected disconnect)
        """
        # Log disconnection event with details (Requirement 11.1, 11.3)
        broker_address = self.config.get('broker_address', 'unknown')
        broker_port = self.config.get('broker_port', 1883)
        
        if rc == 0:
            self.logger.info(
                f"MQTT disconnected cleanly - "
                f"broker={broker_address}:{broker_port}"
            )
        else:
            self.logger.warning(
                f"MQTT disconnected unexpectedly (rc={rc}) - "
                f"broker={broker_address}:{broker_port}, "
                f"will attempt reconnection"
            )
        
        asyncio.create_task(self._handle_disconnect(rc))
    
    async def _handle_disconnect(self, rc: int):
        """
        Handle disconnection event.
        
        Args:
            rc: Return code (0 = clean disconnect, >0 = unexpected disconnect)
        """
        async with self._state_lock:
            previous_state = self._state
            self._state = ConnectionState.DISCONNECTED
        
        self.stats['disconnection_count'] += 1
        self.stats['last_disconnect_time'] = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        
        self._connected_event.clear()
        self._disconnected_event.set()
        
        # Log disconnection statistics (Requirement 11.1)
        self.logger.info(
            f"Disconnection statistics - "
            f"total_connections={self.stats['connection_count']}, "
            f"total_disconnections={self.stats['disconnection_count']}, "
            f"messages_published={self.stats['messages_published']}, "
            f"publish_errors={self.stats['publish_errors']}"
        )
        
        # Attempt reconnection if it was an unexpected disconnect
        if rc != 0 and self._should_reconnect and previous_state == ConnectionState.CONNECTED:
            self.logger.info("Starting automatic reconnection due to unexpected disconnect")
            self._reconnect_task = asyncio.create_task(self.reconnect())
    
    def _on_publish(self, client, userdata, mid):
        """
        Callback for successful publish.
        
        Args:
            client: MQTT client instance
            userdata: User data
            mid: Message ID
        """
        self.logger.debug(f"Message {mid} published successfully")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        return False
