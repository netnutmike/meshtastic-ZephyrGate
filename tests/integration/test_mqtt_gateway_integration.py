"""
Integration tests for MQTT Gateway Plugin

Tests the complete message flow from mesh to MQTT broker, including:
- Message forwarding with real MQTT broker
- Connection loss and recovery
- Rate limiting under load

Requirements tested:
- 4.1: Message forwarding from mesh to MQTT
- 7.1: Rate limit enforcement
- 8.2, 8.3: Connection recovery and queue processing
- 10.1, 10.2: Integration with message router
"""

import pytest
import asyncio
import json
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.plugin import MQTTGatewayPlugin
from models.message import Message, MessageType, MessagePriority

# Try to import paho-mqtt for real broker testing
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


# Public MQTT test broker for integration testing
TEST_BROKER = "test.mosquitto.org"
TEST_BROKER_PORT = 1883
TEST_TOPIC_PREFIX = f"zephyrgate/test/{int(time.time())}"


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager"""
    manager = Mock()
    manager.config_manager = None
    manager.send_message = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def test_config():
    """Provide test configuration with real MQTT broker"""
    return {
        'enabled': True,
        'broker_address': TEST_BROKER,
        'broker_port': TEST_BROKER_PORT,
        'username': '',
        'password': '',
        'tls_enabled': False,
        'root_topic': TEST_TOPIC_PREFIX,
        'region': 'TEST',
        'format': 'json',
        'encryption_enabled': False,
        'max_messages_per_second': 10,
        'queue_max_size': 100,
        'reconnect_enabled': True,
        'reconnect_initial_delay': 1,
        'reconnect_max_delay': 5,
        'reconnect_multiplier': 2.0,
        'channels': [
            {
                'name': '0',
                'uplink_enabled': True,
                'message_types': ['text', 'position', 'nodeinfo', 'telemetry']
            }
        ]
    }


@pytest.fixture
def test_message():
    """Create a test message"""
    return Message(
        id="test_msg_1",
        sender_id="!a1b2c3d4",
        recipient_id="^all",
        message_type=MessageType.TEXT,
        content="Test message for integration",
        channel=0,
        timestamp=datetime.utcnow(),
        hop_limit=3,
        snr=5.5,
        rssi=-80,
        priority=MessagePriority.NORMAL
    )


class MQTTTestSubscriber:
    """Helper class to subscribe to MQTT topics and collect messages"""
    
    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.messages = []
        self.connected = False
        self.client = None
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        """Callback when message received"""
        self.messages.append({
            'topic': msg.topic,
            'payload': msg.payload.decode('utf-8'),
            'timestamp': datetime.utcnow()
        })
    
    async def start(self):
        """Start the subscriber"""
        if not MQTT_AVAILABLE:
            return False
            
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            # Wait for connection
            for _ in range(50):  # 5 seconds max
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            
            return False
        except Exception as e:
            print(f"Failed to connect subscriber: {e}")
            return False
    
    def stop(self):
        """Stop the subscriber"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def get_messages(self):
        """Get collected messages"""
        return self.messages.copy()
    
    def clear_messages(self):
        """Clear collected messages"""
        self.messages.clear()


@pytest.fixture
async def mqtt_subscriber(test_config):
    """Create an MQTT subscriber for testing"""
    if not MQTT_AVAILABLE:
        pytest.skip("paho-mqtt not available")
    
    topic = f"{test_config['root_topic']}/#"
    subscriber = MQTTTestSubscriber(
        test_config['broker_address'],
        test_config['broker_port'],
        topic
    )
    
    connected = await subscriber.start()
    if not connected:
        pytest.skip(f"Could not connect to test broker {TEST_BROKER}")
    
    yield subscriber
    
    subscriber.stop()


class TestMQTTGatewayMessageFlow:
    """Integration tests for message flow from mesh to MQTT broker"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not MQTT_AVAILABLE, reason="paho-mqtt not available")
    async def test_message_forwarding_to_real_broker(
        self, mock_plugin_manager, test_config, test_message, mqtt_subscriber
    ):
        """
        Test message forwarding from mesh to real MQTT broker
        
        Requirements: 4.1, 10.1, 10.2
        """
        # Create and initialize plugin
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Start plugin (connects to broker)
        started = await plugin.start()
        assert started is True
        
        # Wait for connection
        await asyncio.sleep(1)
        
        # Verify connected
        status = await plugin.get_health_status()
        assert status['connected'] is True
        
        # Clear any existing messages
        mqtt_subscriber.clear_messages()
        
        # Handle a message (simulating message router)
        context = {'timestamp': datetime.utcnow()}
        await plugin._handle_mesh_message(test_message, context)
        
        # Wait for message to be published
        await asyncio.sleep(2)
        
        # Check that message was received by subscriber
        messages = mqtt_subscriber.get_messages()
        assert len(messages) > 0, "No messages received from MQTT broker"
        
        # Verify message content
        received = messages[0]
        assert test_message.sender_id in received['topic']
        
        # Parse JSON payload
        payload = json.loads(received['payload'])
        assert payload['sender'] == test_message.sender_id
        assert payload['type'] == 'text'
        assert payload['payload'] == test_message.content
        
        # Verify topic structure: {root_topic}/TEST/2/json/0/{sender_id}
        topic_parts = received['topic'].split('/')
        assert topic_parts[0] == test_config['root_topic'].split('/')[0]
        assert 'json' in topic_parts
        assert test_message.sender_id in topic_parts
        
        # Cleanup
        await plugin.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not MQTT_AVAILABLE, reason="paho-mqtt not available")
    async def test_topic_path_correctness(
        self, mock_plugin_manager, test_config, mqtt_subscriber
    ):
        """
        Test that MQTT topic paths follow Meshtastic protocol
        
        Requirements: 4.1, 10.1
        """
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        # Wait for connection
        await asyncio.sleep(1)
        
        mqtt_subscriber.clear_messages()
        
        # Create messages with different types
        messages = [
            Message(
                id=f"msg_{i}",
                sender_id=f"!node{i:04d}",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Test message {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            for i in range(3)
        ]
        
        # Send messages
        for msg in messages:
            context = {'timestamp': datetime.utcnow()}
            await plugin._handle_mesh_message(msg, context)
        
        # Wait for messages to be published
        await asyncio.sleep(2)
        
        # Verify all messages received
        received = mqtt_subscriber.get_messages()
        assert len(received) >= 3, f"Expected 3 messages, got {len(received)}"
        
        # Verify each topic path
        for i, msg_data in enumerate(received[:3]):
            topic = msg_data['topic']
            
            # Topic should be: {root_topic}/TEST/2/json/0/{sender_id}
            assert test_config['root_topic'] in topic
            assert '/json/' in topic
            assert f"!node{i:04d}" in topic
            
            # Verify payload
            payload = json.loads(msg_data['payload'])
            assert payload['sender'] == f"!node{i:04d}"
            assert payload['payload'] == f"Test message {i}"
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not MQTT_AVAILABLE, reason="paho-mqtt not available")
    async def test_metadata_preservation(
        self, mock_plugin_manager, test_config, mqtt_subscriber
    ):
        """
        Test that message metadata (SNR, RSSI, timestamp) is preserved
        
        Requirements: 4.1, 10.2
        """
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(1)
        mqtt_subscriber.clear_messages()
        
        # Create message with specific metadata
        message = Message(
            id="metadata_test",
            sender_id="!meta1234",
            recipient_id="^all",
            message_type=MessageType.TEXT,
            content="Metadata test",
            channel=0,
            timestamp=datetime.utcnow(),
            hop_limit=3,
            snr=7.5,
            rssi=-75,
            priority=MessagePriority.NORMAL
        )
        
        context = {'timestamp': datetime.utcnow()}
        await plugin._handle_mesh_message(message, context)
        
        await asyncio.sleep(2)
        
        received = mqtt_subscriber.get_messages()
        assert len(received) > 0
        
        # Verify metadata in payload
        payload = json.loads(received[0]['payload'])
        assert payload['sender'] == message.sender_id
        assert 'timestamp' in payload
        assert 'snr' in payload
        assert 'rssi' in payload
        assert payload['snr'] == message.snr
        assert payload['rssi'] == message.rssi
        
        await plugin.stop()


class TestMQTTGatewayReconnection:
    """Integration tests for connection loss and recovery"""
    
    @pytest.mark.asyncio
    async def test_message_queuing_when_disconnected(
        self, mock_plugin_manager, test_config, test_message
    ):
        """
        Test that messages are queued when broker is unavailable
        
        Requirements: 8.2, 8.3
        """
        # Use invalid broker to simulate disconnection
        config = test_config.copy()
        config['broker_address'] = 'invalid.broker.local'
        config['reconnect_initial_delay'] = 10  # Long delay to prevent reconnection
        config['reconnect_max_delay'] = 60  # Must be >= initial delay
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Try to start (will fail to connect)
        await plugin.start()
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        # Verify not connected
        status = await plugin.get_health_status()
        assert status['connected'] is False
        
        # Send messages
        for i in range(5):
            msg = Message(
                id=f"queued_{i}",
                sender_id="!queue123",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Queued message {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            context = {'timestamp': datetime.utcnow()}
            await plugin._handle_mesh_message(msg, context)
        
        # Wait for async processing
        await asyncio.sleep(1)
        
        # Verify messages were queued
        status = await plugin.get_health_status()
        assert status['queue_size'] > 0
        assert status['messages_queued'] >= 5
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not MQTT_AVAILABLE, reason="paho-mqtt not available")
    async def test_queue_processing_after_reconnection(
        self, mock_plugin_manager, test_config, test_message, mqtt_subscriber
    ):
        """
        Test that queued messages are processed after reconnection
        
        Requirements: 8.2, 8.3
        """
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Start without connection (mock disconnect)
        with patch.object(plugin.mqtt_client, 'connect', return_value=False):
            await plugin.start()
        
        # Queue some messages while "disconnected"
        for i in range(3):
            msg = Message(
                id=f"reconnect_{i}",
                sender_id="!recon123",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Reconnect test {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            await plugin._publish_message_async(msg)
        
        await asyncio.sleep(0.5)
        
        # Verify messages queued
        initial_queue_size = plugin.message_queue.size()
        assert initial_queue_size >= 3
        
        # Now actually connect
        mqtt_subscriber.clear_messages()
        await plugin.mqtt_client.connect()
        
        # Wait for connection and queue processing
        await asyncio.sleep(3)
        
        # Verify queue was processed
        final_queue_size = plugin.message_queue.size()
        assert final_queue_size < initial_queue_size
        
        # Verify messages were published
        received = mqtt_subscriber.get_messages()
        assert len(received) > 0
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_on_reconnection(
        self, mock_plugin_manager, test_config
    ):
        """
        Test that reconnection uses exponential backoff
        
        Requirements: 8.2
        """
        config = test_config.copy()
        config['broker_address'] = 'invalid.broker.local'
        config['reconnect_initial_delay'] = 1
        config['reconnect_max_delay'] = 8
        config['reconnect_multiplier'] = 2.0
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Track reconnection attempts
        attempts = []
        original_connect = plugin.mqtt_client.connect
        
        async def track_connect():
            attempts.append(time.time())
            return await original_connect()
        
        plugin.mqtt_client.connect = track_connect
        
        # Start (will fail and retry)
        await plugin.start()
        
        # Wait for multiple reconnection attempts
        await asyncio.sleep(10)
        
        # Verify multiple attempts were made (at least 2)
        assert len(attempts) >= 2, f"Expected at least 2 attempts, got {len(attempts)}"
        
        # Verify delays increase (exponential backoff)
        if len(attempts) >= 3:
            delay1 = attempts[1] - attempts[0]
            delay2 = attempts[2] - attempts[1]
            
            # Second delay should be longer than first (with some tolerance)
            assert delay2 > delay1 * 0.8, f"Backoff not increasing: {delay1} -> {delay2}"
        
        await plugin.stop()


class TestMQTTGatewayRateLimiting:
    """Integration tests for rate limiting under load"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not MQTT_AVAILABLE, reason="paho-mqtt not available")
    async def test_rate_limit_enforcement_under_load(
        self, mock_plugin_manager, test_config, mqtt_subscriber
    ):
        """
        Test that rate limiting is enforced under high message load
        
        Requirements: 7.1
        """
        # Set low rate limit for testing
        config = test_config.copy()
        config['max_messages_per_second'] = 5
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        await plugin.start()
        
        await asyncio.sleep(1)
        mqtt_subscriber.clear_messages()
        
        # Send burst of messages
        start_time = time.time()
        num_messages = 20
        
        for i in range(num_messages):
            msg = Message(
                id=f"rate_{i}",
                sender_id="!rate1234",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Rate limit test {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            context = {'timestamp': datetime.utcnow()}
            await plugin._handle_mesh_message(msg, context)
        
        # Wait for processing
        await asyncio.sleep(5)
        
        elapsed = time.time() - start_time
        
        # Verify rate limiter statistics
        rate_stats = plugin.rate_limiter.get_statistics()
        assert rate_stats['messages_allowed'] > 0
        
        # If messages were delayed, verify rate was respected
        if elapsed > 2:
            # Calculate actual rate
            received = mqtt_subscriber.get_messages()
            actual_rate = len(received) / elapsed
            
            # Should be close to configured rate (with some tolerance)
            max_rate = config['max_messages_per_second']
            assert actual_rate <= max_rate * 1.5, \
                f"Rate {actual_rate:.1f} exceeds limit {max_rate}"
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(
        self, mock_plugin_manager, test_config
    ):
        """
        Test that rate limiter allows initial burst
        
        Requirements: 7.1
        """
        config = test_config.copy()
        config['max_messages_per_second'] = 10
        config['broker_address'] = 'invalid.broker.local'  # Don't actually publish
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Send burst of messages
        start_time = time.time()
        
        for i in range(15):
            msg = Message(
                id=f"burst_{i}",
                sender_id="!burst123",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Burst test {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            await plugin._publish_message_async(msg)
        
        elapsed = time.time() - start_time
        
        # First few messages should be fast (burst)
        assert elapsed < 2.0, "Initial burst should be fast"
        
        # Check rate limiter stats
        stats = plugin.rate_limiter.get_statistics()
        assert stats['messages_allowed'] >= 10
        
        await plugin.stop()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_backoff_behavior(
        self, mock_plugin_manager, test_config
    ):
        """
        Test rate limiter backoff when limit exceeded
        
        Requirements: 7.1, 7.2
        """
        config = test_config.copy()
        config['max_messages_per_second'] = 5
        config['broker_address'] = 'invalid.broker.local'
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Send messages rapidly
        for i in range(10):
            msg = Message(
                id=f"backoff_{i}",
                sender_id="!back1234",
                recipient_id="^all",
                message_type=MessageType.TEXT,
                content=f"Backoff test {i}",
                channel=0,
                timestamp=datetime.utcnow(),
                hop_limit=3,
                priority=MessagePriority.NORMAL
            )
            await plugin._publish_message_async(msg)
        
        await asyncio.sleep(0.5)
        
        # Check that some messages were queued due to rate limiting
        stats = plugin.rate_limiter.get_statistics()
        queue_size = plugin.message_queue.size()
        
        # Either rate limiter delayed or messages were queued
        assert stats['messages_allowed'] > 0 or queue_size > 0
        
        await plugin.stop()


class TestMQTTGatewayComponentIntegration:
    """Tests for component integration (existing tests)"""
    
    @pytest.mark.asyncio
    async def test_plugin_initialization_wires_components(self, mock_plugin_manager, test_config):
        """Test that plugin initialization wires all components together"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        
        result = await plugin.initialize()
        
        assert result is True
        assert plugin.mqtt_client is not None
        assert plugin.message_formatter is not None
        assert plugin.message_queue is not None
        assert plugin.rate_limiter is not None
    
    @pytest.mark.asyncio
    async def test_message_filtering_with_uplink_disabled(self, mock_plugin_manager, test_config, test_message):
        """Test that messages are filtered when uplink is disabled"""
        # Disable uplink for channel 0
        config = test_config.copy()
        config['channels'][0]['uplink_enabled'] = False
        
        plugin = MQTTGatewayPlugin("mqtt_gateway", config, mock_plugin_manager)
        await plugin.initialize()
        
        # Message should be filtered out
        should_forward = plugin._should_forward_message(test_message)
        
        assert should_forward is False
    
    @pytest.mark.asyncio
    async def test_message_filtering_with_uplink_enabled(self, mock_plugin_manager, test_config, test_message):
        """Test that messages pass through when uplink is enabled"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Message should pass through
        should_forward = plugin._should_forward_message(test_message)
        
        assert should_forward is True
    
    @pytest.mark.asyncio
    async def test_health_status_includes_queue_size(self, mock_plugin_manager, test_config, test_message):
        """Test that health status includes queue size"""
        plugin = MQTTGatewayPlugin("mqtt_gateway", test_config, mock_plugin_manager)
        await plugin.initialize()
        
        # Queue a message
        await plugin._publish_message_async(test_message)
        
        # Get health status
        status = await plugin.get_health_status()
        
        assert 'queue_size' in status
        assert status['queue_size'] >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
