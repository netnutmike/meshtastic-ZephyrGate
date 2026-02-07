"""
Unit tests for MQTT Client wrapper

Tests connection management, TLS/SSL configuration, and connection state transitions
for the MQTTClient class.

Requirements: 2.1, 2.4
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.mqtt_client import MQTTClient, ConnectionState


@pytest.fixture
def basic_config():
    """Provide basic MQTT configuration"""
    return {
        'broker_address': 'mqtt.example.com',
        'broker_port': 1883,
        'username': '',
        'password': '',
        'tls_enabled': False,
        'reconnect_enabled': True,
        'reconnect_initial_delay': 1,
        'reconnect_max_delay': 60,
        'reconnect_multiplier': 2.0,
        'max_reconnect_attempts': -1
    }


@pytest.fixture
def tls_config():
    """Provide TLS-enabled MQTT configuration"""
    return {
        'broker_address': 'mqtt.example.com',
        'broker_port': 8883,
        'username': 'test_user',
        'password': 'test_pass',
        'tls_enabled': True,
        'ca_cert': '/path/to/ca.crt',
        'client_cert': '/path/to/client.crt',
        'client_key': '/path/to/client.key',
        'reconnect_enabled': True,
        'reconnect_initial_delay': 1,
        'reconnect_max_delay': 60,
        'reconnect_multiplier': 2.0,
        'max_reconnect_attempts': -1
    }


@pytest.fixture
def mock_mqtt_client():
    """Create a mock paho-mqtt client"""
    with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock publish result
        mock_result = MagicMock()
        mock_result.rc = 0  # MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result
        
        yield mock_client


class TestMQTTClientInitialization:
    """Tests for MQTT client initialization"""
    
    def test_initialization_with_basic_config(self, basic_config, mock_mqtt_client):
        """Test client initializes with basic configuration"""
        client = MQTTClient(basic_config)
        
        assert client.config == basic_config
        assert client._state == ConnectionState.DISCONNECTED
        assert client.stats['connection_count'] == 0
        assert client.stats['disconnection_count'] == 0
    
    def test_initialization_with_credentials(self, basic_config, mock_mqtt_client):
        """Test client initializes with username and password"""
        config = basic_config.copy()
        config['username'] = 'test_user'
        config['password'] = 'test_pass'
        
        client = MQTTClient(config)
        
        # Verify username_pw_set was called
        mock_mqtt_client.username_pw_set.assert_called_once_with('test_user', 'test_pass')
    
    def test_initialization_without_credentials(self, basic_config, mock_mqtt_client):
        """Test client initializes without credentials"""
        client = MQTTClient(basic_config)
        
        # Verify username_pw_set was not called
        mock_mqtt_client.username_pw_set.assert_not_called()
    
    def test_initialization_with_tls_enabled(self, tls_config, mock_mqtt_client):
        """Test client initializes with TLS/SSL enabled"""
        client = MQTTClient(tls_config)
        
        # Verify tls_set was called
        mock_mqtt_client.tls_set.assert_called_once()
        call_kwargs = mock_mqtt_client.tls_set.call_args[1]
        assert call_kwargs['ca_certs'] == '/path/to/ca.crt'
        assert call_kwargs['certfile'] == '/path/to/client.crt'
        assert call_kwargs['keyfile'] == '/path/to/client.key'
    
    def test_initialization_with_tls_no_ca_cert(self, basic_config, mock_mqtt_client):
        """Test client initializes with TLS but no CA certificate"""
        config = basic_config.copy()
        config['tls_enabled'] = True
        config['ca_cert'] = None
        
        client = MQTTClient(config)
        
        # Verify tls_set was called with None for ca_certs
        mock_mqtt_client.tls_set.assert_called_once()
        call_kwargs = mock_mqtt_client.tls_set.call_args[1]
        assert call_kwargs['ca_certs'] is None
        
        # Verify insecure mode was enabled
        mock_mqtt_client.tls_insecure_set.assert_called_once_with(True)
    
    def test_callbacks_are_set(self, basic_config, mock_mqtt_client):
        """Test MQTT callbacks are set during initialization"""
        client = MQTTClient(basic_config)
        
        assert mock_mqtt_client.on_connect is not None
        assert mock_mqtt_client.on_disconnect is not None
        assert mock_mqtt_client.on_publish is not None


class TestMQTTClientConnection:
    """Tests for MQTT client connection"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, basic_config, mock_mqtt_client):
        """Test successful connection to MQTT broker"""
        client = MQTTClient(basic_config)
        
        # Simulate successful connection
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        
        result = await client.connect()
        
        assert result is True
        assert client.is_connected() is True
        assert client._state == ConnectionState.CONNECTED
        assert client.stats['connection_count'] == 1
        
        # Verify connect_async was called
        mock_mqtt_client.connect_async.assert_called_once_with(
            host='mqtt.example.com',
            port=1883,
            keepalive=60
        )
        
        # Verify loop_start was called
        mock_mqtt_client.loop_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_timeout(self, basic_config, mock_mqtt_client):
        """Test connection timeout"""
        client = MQTTClient(basic_config)
        
        # Don't simulate connection callback - let it timeout
        result = await client.connect()
        
        assert result is False
        assert client.is_connected() is False
        assert client._state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, basic_config, mock_mqtt_client):
        """Test connecting when already connected"""
        client = MQTTClient(basic_config)
        
        # Simulate successful connection
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        result1 = await client.connect()
        
        # Try to connect again
        result2 = await client.connect()
        
        assert result1 is True
        assert result2 is True
        assert client.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_connect_with_invalid_credentials(self, basic_config, mock_mqtt_client):
        """Test connection with invalid credentials"""
        client = MQTTClient(basic_config)
        
        # Simulate connection failure (rc=4 = bad username/password)
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 4)
        
        asyncio.create_task(simulate_connect())
        
        result = await client.connect()
        
        assert result is False
        assert client.is_connected() is False
        assert client._state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_exception_handling(self, basic_config, mock_mqtt_client):
        """Test connection handles exceptions gracefully"""
        client = MQTTClient(basic_config)
        
        # Make connect_async raise an exception
        mock_mqtt_client.connect_async.side_effect = Exception("Connection error")
        
        result = await client.connect()
        
        assert result is False
        assert client.is_connected() is False
        assert client._state == ConnectionState.DISCONNECTED


class TestMQTTClientDisconnection:
    """Tests for MQTT client disconnection"""
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self, basic_config, mock_mqtt_client):
        """Test successful disconnection from MQTT broker"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Simulate disconnection
        async def simulate_disconnect():
            await asyncio.sleep(0.1)
            client._on_disconnect(mock_mqtt_client, None, 0)
        
        asyncio.create_task(simulate_disconnect())
        
        await client.disconnect()
        
        assert client.is_connected() is False
        assert client._state == ConnectionState.DISCONNECTED
        
        # Verify disconnect was called
        mock_mqtt_client.disconnect.assert_called_once()
        
        # Verify loop_stop was called
        mock_mqtt_client.loop_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, basic_config, mock_mqtt_client):
        """Test disconnecting when not connected"""
        client = MQTTClient(basic_config)
        
        # Should not raise exception
        await client.disconnect()
        
        assert client.is_connected() is False
        assert client._state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_disconnect_cancels_reconnection(self, basic_config, mock_mqtt_client):
        """Test disconnect cancels ongoing reconnection"""
        client = MQTTClient(basic_config)
        
        # Set state to RECONNECTING so disconnect doesn't return early
        client._state = ConnectionState.RECONNECTING
        client._disconnected_event.clear()
        
        # Create a long-running task to simulate reconnection
        async def long_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                # This is expected
                raise
        
        reconnect_task = asyncio.create_task(long_task())
        client._reconnect_task = reconnect_task
        
        # Simulate the disconnect callback to set the event
        async def trigger_disconnect_event():
            await asyncio.sleep(0.05)
            client._disconnected_event.set()
        
        asyncio.create_task(trigger_disconnect_event())
        
        # Disconnect should cancel the reconnection task
        await client.disconnect()
        
        # The _should_reconnect flag should be False (set by disconnect)
        assert client._should_reconnect is False
        
        # The task should be cancelled
        assert reconnect_task.cancelled()
        assert client._should_reconnect is False


class TestMQTTClientReconnection:
    """Tests for MQTT client reconnection"""
    
    @pytest.mark.asyncio
    async def test_reconnect_success(self, basic_config, mock_mqtt_client):
        """Test successful reconnection"""
        config = basic_config.copy()
        config['reconnect_initial_delay'] = 0.1  # Fast for testing
        client = MQTTClient(config)
        
        # Simulate successful connection on first attempt
        async def simulate_connect():
            await asyncio.sleep(0.05)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        
        result = await client.reconnect()
        
        assert result is True
        assert client.is_connected() is True
        assert client.stats['reconnection_count'] == 1
    
    @pytest.mark.asyncio
    async def test_reconnect_disabled(self, basic_config, mock_mqtt_client):
        """Test reconnection when disabled in config"""
        config = basic_config.copy()
        config['reconnect_enabled'] = False
        client = MQTTClient(config)
        
        result = await client.reconnect()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self, basic_config, mock_mqtt_client):
        """Test reconnection respects max attempts"""
        config = basic_config.copy()
        config['reconnect_initial_delay'] = 0.01  # Very fast for testing
        config['max_reconnect_attempts'] = 2
        client = MQTTClient(config)
        
        # Don't simulate successful connection - let it fail
        result = await client.reconnect()
        
        assert result is False
        assert client._reconnect_attempt == 2
    
    @pytest.mark.asyncio
    async def test_automatic_reconnection_on_disconnect(self, basic_config, mock_mqtt_client):
        """Test automatic reconnection after unexpected disconnect"""
        config = basic_config.copy()
        config['reconnect_initial_delay'] = 0.1
        client = MQTTClient(config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.05)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Simulate unexpected disconnect (rc != 0)
        client._on_disconnect(mock_mqtt_client, None, 1)
        
        # Wait a bit for reconnection task to start
        await asyncio.sleep(0.2)
        
        # Reconnection task should be created
        assert client._reconnect_task is not None


class TestMQTTClientPublish:
    """Tests for MQTT message publishing"""
    
    @pytest.mark.asyncio
    async def test_publish_success(self, basic_config, mock_mqtt_client):
        """Test successful message publishing"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Publish message
        result = await client.publish('test/topic', b'test payload', qos=1)
        
        assert result is True
        assert client.stats['messages_published'] == 1
        
        # Verify publish was called
        mock_mqtt_client.publish.assert_called_once_with(
            'test/topic',
            b'test payload',
            qos=1,
            retain=False
        )
    
    @pytest.mark.asyncio
    async def test_publish_when_not_connected(self, basic_config, mock_mqtt_client):
        """Test publishing when not connected"""
        client = MQTTClient(basic_config)
        
        result = await client.publish('test/topic', b'test payload')
        
        assert result is False
        assert client.stats['messages_published'] == 0
    
    @pytest.mark.asyncio
    async def test_publish_with_retain(self, basic_config, mock_mqtt_client):
        """Test publishing with retain flag"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Publish with retain
        result = await client.publish('test/topic', b'test payload', retain=True)
        
        assert result is True
        
        # Verify retain flag was passed
        call_kwargs = mock_mqtt_client.publish.call_args[1]
        assert call_kwargs['retain'] is True
    
    @pytest.mark.asyncio
    async def test_publish_error_handling(self, basic_config, mock_mqtt_client):
        """Test publish handles errors gracefully"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Make publish raise an exception
        mock_mqtt_client.publish.side_effect = Exception("Publish error")
        
        result = await client.publish('test/topic', b'test payload')
        
        assert result is False
        assert client.stats['publish_errors'] == 1


class TestMQTTClientStateTracking:
    """Tests for connection state tracking"""
    
    def test_initial_state(self, basic_config, mock_mqtt_client):
        """Test initial connection state"""
        client = MQTTClient(basic_config)
        
        assert client.get_state() == ConnectionState.DISCONNECTED
        assert client.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_state_transitions(self, basic_config, mock_mqtt_client):
        """Test connection state transitions"""
        client = MQTTClient(basic_config)
        
        # Initial state
        assert client.get_state() == ConnectionState.DISCONNECTED
        
        # Simulate connection
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Should be connected
        assert client.get_state() == ConnectionState.CONNECTED
        
        # Simulate disconnection
        async def simulate_disconnect():
            await asyncio.sleep(0.1)
            client._on_disconnect(mock_mqtt_client, None, 0)
        
        asyncio.create_task(simulate_disconnect())
        await client.disconnect()
        
        # Should be disconnected
        assert client.get_state() == ConnectionState.DISCONNECTED


class TestMQTTClientStatistics:
    """Tests for connection statistics"""
    
    @pytest.mark.asyncio
    async def test_connection_statistics(self, basic_config, mock_mqtt_client):
        """Test connection statistics are tracked"""
        client = MQTTClient(basic_config)
        
        # Connect
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        stats = client.get_stats()
        
        assert stats['connection_count'] == 1
        assert stats['last_connect_time'] is not None
    
    @pytest.mark.asyncio
    async def test_disconnection_statistics(self, basic_config, mock_mqtt_client):
        """Test disconnection statistics are tracked"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Disconnect
        async def simulate_disconnect():
            await asyncio.sleep(0.1)
            client._on_disconnect(mock_mqtt_client, None, 0)
        
        asyncio.create_task(simulate_disconnect())
        await client.disconnect()
        
        stats = client.get_stats()
        
        assert stats['disconnection_count'] == 1
        assert stats['last_disconnect_time'] is not None
    
    @pytest.mark.asyncio
    async def test_publish_statistics(self, basic_config, mock_mqtt_client):
        """Test publish statistics are tracked"""
        client = MQTTClient(basic_config)
        
        # Connect first
        async def simulate_connect():
            await asyncio.sleep(0.1)
            client._on_connect(mock_mqtt_client, None, None, 0)
        
        asyncio.create_task(simulate_connect())
        await client.connect()
        
        # Publish multiple messages
        await client.publish('test/topic1', b'payload1')
        await client.publish('test/topic2', b'payload2')
        await client.publish('test/topic3', b'payload3')
        
        stats = client.get_stats()
        
        assert stats['messages_published'] == 3


class TestBackoffCalculation:
    """Tests for exponential backoff calculation"""
    
    def test_backoff_calculation_first_attempt(self, basic_config, mock_mqtt_client):
        """Test backoff calculation for first attempt"""
        client = MQTTClient(basic_config)
        
        delay = client._calculate_backoff_delay(
            attempt=0,
            initial_delay=1,
            max_delay=60,
            multiplier=2.0
        )
        
        assert delay == 1
    
    def test_backoff_calculation_second_attempt(self, basic_config, mock_mqtt_client):
        """Test backoff calculation for second attempt"""
        client = MQTTClient(basic_config)
        
        delay = client._calculate_backoff_delay(
            attempt=1,
            initial_delay=1,
            max_delay=60,
            multiplier=2.0
        )
        
        assert delay == 2
    
    def test_backoff_calculation_third_attempt(self, basic_config, mock_mqtt_client):
        """Test backoff calculation for third attempt"""
        client = MQTTClient(basic_config)
        
        delay = client._calculate_backoff_delay(
            attempt=2,
            initial_delay=1,
            max_delay=60,
            multiplier=2.0
        )
        
        assert delay == 4
    
    def test_backoff_calculation_max_delay(self, basic_config, mock_mqtt_client):
        """Test backoff calculation respects max delay"""
        client = MQTTClient(basic_config)
        
        delay = client._calculate_backoff_delay(
            attempt=10,
            initial_delay=1,
            max_delay=60,
            multiplier=2.0
        )
        
        # 1 * 2^10 = 1024, but should be capped at 60
        assert delay == 60
    
    def test_backoff_calculation_different_multiplier(self, basic_config, mock_mqtt_client):
        """Test backoff calculation with different multiplier"""
        client = MQTTClient(basic_config)
        
        delay = client._calculate_backoff_delay(
            attempt=2,
            initial_delay=1,
            max_delay=60,
            multiplier=3.0
        )
        
        # 1 * 3^2 = 9
        assert delay == 9


class TestAsyncContextManager:
    """Tests for async context manager support"""
    
    @pytest.mark.asyncio
    async def test_context_manager_connect_disconnect(self, basic_config, mock_mqtt_client):
        """Test async context manager connects and disconnects"""
        # Simulate connection
        async def simulate_connect():
            await asyncio.sleep(0.1)
        
        with patch.object(MQTTClient, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(MQTTClient, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                mock_connect.return_value = True
                
                async with MQTTClient(basic_config) as client:
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()
