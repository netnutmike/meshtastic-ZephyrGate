"""
Unit tests for error handling in MQTT Gateway components

Tests comprehensive error handling for:
- Connection errors (MQTT client)
- Serialization errors (message formatter)
- Queue overflow handling (message queue)
- Rate limit error handling (rate limiter)

Requirements: 2.4, 8.4, 8.5
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
import sys
import ssl

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.mqtt_client import MQTTClient, ConnectionState
from plugins.mqtt_gateway.message_formatter import MessageFormatter
from plugins.mqtt_gateway.message_queue import MessageQueue
from plugins.mqtt_gateway.rate_limiter import RateLimiter
from models.message import Message, MessageType


class TestMQTTClientConnectionErrors:
    """
    Test connection error handling in MQTT client
    
    **Validates: Requirements 2.4, 8.4**
    """
    
    @pytest.mark.asyncio
    async def test_connect_with_invalid_broker_address(self):
        """Test connection with invalid broker address"""
        config = {
            'broker_address': '',  # Empty address
            'broker_port': 1883,
            'reconnect_enabled': True
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.connect_async.side_effect = ValueError("Invalid broker address")
            
            client = MQTTClient(config)
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
            assert client._state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_with_network_error(self):
        """Test connection with network error (DNS failure, network unreachable)"""
        config = {
            'broker_address': 'nonexistent.broker.invalid',
            'broker_port': 1883,
            'reconnect_enabled': True
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.connect_async.side_effect = OSError("Network unreachable")
            
            client = MQTTClient(config)
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
            assert client._state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_with_tls_error(self):
        """Test connection with TLS/SSL error"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 8883,
            'tls_enabled': True,
            'ca_cert': '/invalid/path/ca.crt',
            'reconnect_enabled': True
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.tls_set.side_effect = ssl.SSLError("Certificate verification failed")
            
            # Should raise during initialization
            with pytest.raises(ssl.SSLError):
                client = MQTTClient(config)
    
    @pytest.mark.asyncio
    async def test_connect_with_missing_config(self):
        """Test connection with missing required configuration"""
        config = {
            # Missing broker_address
            'broker_port': 1883,
            'reconnect_enabled': True
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            client = MQTTClient(config)
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_connect_network_loop_start_failure(self):
        """Test connection when network loop fails to start"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883,
            'reconnect_enabled': True
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.loop_start.side_effect = Exception("Failed to start network loop")
            
            client = MQTTClient(config)
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
            assert client._state == ConnectionState.DISCONNECTED


class TestMQTTClientPublishErrors:
    """
    Test publish error handling in MQTT client
    
    **Validates: Requirements 8.4**
    """
    
    @pytest.mark.asyncio
    async def test_publish_with_empty_topic(self):
        """Test publish with empty topic"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            client = MQTTClient(config)
            client._state = ConnectionState.CONNECTED
            
            result = await client.publish('', b'payload')
            
            assert result is False
            assert client.stats['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_publish_with_invalid_payload_type(self):
        """Test publish with non-bytes payload"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            client = MQTTClient(config)
            client._state = ConnectionState.CONNECTED
            
            result = await client.publish('test/topic', 'not bytes')  # Should be bytes
            
            assert result is False
            assert client.stats['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_publish_with_invalid_qos(self):
        """Test publish with invalid QoS level"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            client = MQTTClient(config)
            client._state = ConnectionState.CONNECTED
            
            result = await client.publish('test/topic', b'payload', qos=5)  # Invalid QoS
            
            assert result is False
            assert client.stats['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_publish_with_network_error(self):
        """Test publish with network error"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.publish.side_effect = OSError("Network error")
            
            client = MQTTClient(config)
            client._state = ConnectionState.CONNECTED
            
            result = await client.publish('test/topic', b'payload')
            
            assert result is False
            assert client.stats['publish_errors'] == 1
    
    @pytest.mark.asyncio
    async def test_publish_with_invalid_topic_characters(self):
        """Test publish with invalid topic characters"""
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.publish.side_effect = ValueError("Invalid topic")
            
            client = MQTTClient(config)
            client._state = ConnectionState.CONNECTED
            
            result = await client.publish('test/+/invalid', b'payload')
            
            assert result is False
            assert client.stats['publish_errors'] == 1


class TestMessageFormatterSerializationErrors:
    """
    Test serialization error handling in message formatter
    
    **Validates: Requirements 8.4**
    """
    
    def test_format_protobuf_with_none_message(self):
        """Test protobuf formatting with None message"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        with pytest.raises(ValueError, match="Message cannot be None"):
            formatter.format_protobuf(None)
    
    def test_format_protobuf_with_missing_sender_id(self):
        """Test protobuf formatting with missing sender_id"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='',  # Empty sender_id
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        with pytest.raises(ValueError, match="Message must have a sender_id"):
            formatter.format_protobuf(message)
    
    def test_format_protobuf_with_invalid_channel(self):
        """Test protobuf formatting with invalid channel"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel='invalid',  # Should be int
            content='test',
            message_type=MessageType.TEXT
        )
        
        with pytest.raises(ValueError, match="Invalid channel"):
            formatter.format_protobuf(message)
    
    def test_format_json_with_none_message(self):
        """Test JSON formatting with None message"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        with pytest.raises(ValueError, match="Message cannot be None"):
            formatter.format_json(None)
    
    def test_format_json_with_missing_sender_id(self):
        """Test JSON formatting with missing sender_id"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='',  # Empty sender_id
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        with pytest.raises(ValueError, match="Message must have a sender_id"):
            formatter.format_json(message)
    
    def test_format_json_with_invalid_channel(self):
        """Test JSON formatting with invalid channel"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel='invalid',  # Should be int
            content='test',
            message_type=MessageType.TEXT
        )
        
        with pytest.raises(ValueError, match="Invalid channel"):
            formatter.format_json(message)
    
    def test_format_protobuf_with_none_content(self):
        """Test protobuf formatting handles None content gracefully"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel=0,
            content=None,  # None content
            message_type=MessageType.TEXT
        )
        
        # Should not raise, should handle gracefully
        protobuf_bytes = formatter.format_protobuf(message)
        assert protobuf_bytes is not None
    
    def test_format_json_with_none_content(self):
        """Test JSON formatting handles None content gracefully"""
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        message = Message(
            sender_id='!test1234',
            channel=0,
            content=None,  # None content
            message_type=MessageType.TEXT
        )
        
        # Should not raise, should handle gracefully
        json_str = formatter.format_json(message)
        assert json_str is not None
        
        import json
        json_obj = json.loads(json_str)
        assert json_obj['payload'] == ''  # Should be empty string


class TestMessageQueueOverflowHandling:
    """
    Test queue overflow handling
    
    **Validates: Requirements 4.6, 7.4, 8.5**
    """
    
    @pytest.mark.asyncio
    async def test_queue_overflow_drops_oldest(self):
        """Test that queue overflow drops oldest message"""
        queue = MessageQueue(max_size=3)
        
        # Create test messages
        msg1 = Message(sender_id='!msg1', channel=0, message_type=MessageType.TEXT)
        msg2 = Message(sender_id='!msg2', channel=0, message_type=MessageType.TEXT)
        msg3 = Message(sender_id='!msg3', channel=0, message_type=MessageType.TEXT)
        msg4 = Message(sender_id='!msg4', channel=0, message_type=MessageType.TEXT)
        
        # Fill queue to capacity
        await queue.enqueue(msg1, 'topic1', b'payload1')
        await queue.enqueue(msg2, 'topic2', b'payload2')
        await queue.enqueue(msg3, 'topic3', b'payload3')
        
        assert queue.size() == 3
        
        # Add one more - should drop oldest (msg1)
        await queue.enqueue(msg4, 'topic4', b'payload4')
        
        assert queue.size() == 3
        assert queue.get_statistics()['overflow_drops'] == 1
        
        # Dequeue and verify msg1 was dropped
        queued_msg = await queue.dequeue()
        assert queued_msg.message.sender_id == '!msg2'  # msg1 was dropped
    
    @pytest.mark.asyncio
    async def test_queue_overflow_statistics(self):
        """Test that queue overflow is tracked in statistics"""
        queue = MessageQueue(max_size=2)
        
        msg1 = Message(sender_id='!msg1', channel=0, message_type=MessageType.TEXT)
        msg2 = Message(sender_id='!msg2', channel=0, message_type=MessageType.TEXT)
        msg3 = Message(sender_id='!msg3', channel=0, message_type=MessageType.TEXT)
        
        await queue.enqueue(msg1, 'topic1', b'payload1')
        await queue.enqueue(msg2, 'topic2', b'payload2')
        await queue.enqueue(msg3, 'topic3', b'payload3')  # Overflow
        
        stats = queue.get_statistics()
        assert stats['overflow_drops'] == 1
        assert stats['dropped'] == 1
    
    @pytest.mark.asyncio
    async def test_queue_overflow_with_priorities(self):
        """Test that queue overflow drops from lowest priority"""
        queue = MessageQueue(max_size=3)
        
        from src.models.message import MessagePriority
        
        # Add messages with different priorities
        msg_low = Message(sender_id='!low', channel=0, message_type=MessageType.TEXT, priority=MessagePriority.LOW)
        msg_normal = Message(sender_id='!normal', channel=0, message_type=MessageType.TEXT, priority=MessagePriority.NORMAL)
        msg_high = Message(sender_id='!high', channel=0, message_type=MessageType.TEXT, priority=MessagePriority.HIGH)
        
        await queue.enqueue(msg_low, 'topic1', b'payload1', priority=MessagePriority.LOW.value)
        await queue.enqueue(msg_normal, 'topic2', b'payload2', priority=MessagePriority.NORMAL.value)
        await queue.enqueue(msg_high, 'topic3', b'payload3', priority=MessagePriority.HIGH.value)
        
        # Add another high priority - should drop the low priority message
        msg_high2 = Message(sender_id='!high2', channel=0, message_type=MessageType.TEXT, priority=MessagePriority.HIGH)
        await queue.enqueue(msg_high2, 'topic4', b'payload4', priority=MessagePriority.HIGH.value)
        
        # Dequeue all and verify low priority was dropped
        messages = []
        while not queue.is_empty():
            queued_msg = await queue.dequeue()
            messages.append(queued_msg.message.sender_id)
        
        assert '!low' not in messages  # Low priority was dropped
        assert '!high2' in messages  # New high priority was added


class TestRateLimiterErrorHandling:
    """
    Test rate limiter error handling
    
    **Validates: Requirements 7.1, 8.4**
    """
    
    @pytest.mark.asyncio
    async def test_rate_limiter_handles_time_errors(self):
        """Test rate limiter handles time calculation errors gracefully"""
        limiter = RateLimiter(max_messages_per_second=10.0)
        
        # Simulate time going backwards
        with patch('time.monotonic', side_effect=[100.0, 99.0]):  # Time goes backwards
            # Should not raise exception
            result = await limiter.acquire()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_handles_refill_errors(self):
        """Test rate limiter handles refill errors gracefully"""
        limiter = RateLimiter(max_messages_per_second=10.0)
        
        # Mock _refill_tokens to raise an exception
        with patch.object(limiter, '_refill_tokens', side_effect=Exception("Refill error")):
            # Should not raise exception, should allow message through
            result = await limiter.acquire()
            assert result is True
            assert limiter._stats['messages_allowed'] >= 1
    
    @pytest.mark.asyncio
    async def test_rate_limiter_handles_wait_time_calculation_errors(self):
        """Test rate limiter handles wait time calculation errors gracefully"""
        limiter = RateLimiter(max_messages_per_second=10.0)
        
        # Exhaust tokens
        limiter.tokens = 0
        
        # Mock get_wait_time to raise an exception
        with patch.object(limiter, 'get_wait_time', side_effect=Exception("Wait time error")):
            # Should not raise exception, should use default wait time
            result = await limiter.acquire()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_handles_cancellation(self):
        """Test rate limiter handles asyncio cancellation properly"""
        limiter = RateLimiter(max_messages_per_second=1.0)
        
        # Exhaust tokens to force a wait
        limiter.tokens = 0
        
        # Create a task that will be cancelled
        async def acquire_with_cancel():
            await limiter.acquire()
        
        task = asyncio.create_task(acquire_with_cancel())
        
        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        task.cancel()
        
        # Should raise CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task


class TestDecryptionErrorHandling:
    """
    Test decryption error handling in message formatter
    
    **Validates: Requirements 6.5**
    
    Requirement 6.5: WHEN a message cannot be decrypted THEN the MQTT_Gateway 
    SHALL log the error and forward the encrypted payload
    """
    
    def test_encryption_enabled_forwards_encrypted_payload(self):
        """Test that encryption enabled mode forwards encrypted payload without decryption"""
        config = {
            'region': 'US',
            'encryption_enabled': True,  # Encryption mode - no decryption
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Create message with encrypted payload
        message = Message(
            sender_id='!test1234',
            channel=0,
            content=None,  # No decrypted content
            message_type=MessageType.TEXT,
            metadata={
                'encrypted_payload': b'\x01\x02\x03\x04\x05',  # Encrypted data
            }
        )
        
        # Format as protobuf - should use encrypted payload
        protobuf_bytes = formatter.format_protobuf(message)
        assert protobuf_bytes is not None
        
        # Verify the encrypted payload was included
        from meshtastic.protobuf import mqtt_pb2
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Should have encrypted field set (not decoded)
        assert envelope.packet.HasField('encrypted')
        assert envelope.packet.encrypted == b'\x01\x02\x03\x04\x05'
        assert not envelope.packet.HasField('decoded')
    
    def test_decryption_disabled_uses_plaintext(self):
        """Test that decryption disabled mode uses plaintext content"""
        config = {
            'region': 'US',
            'encryption_enabled': False,  # Decryption mode
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Create message with plaintext content (successfully decrypted)
        message = Message(
            sender_id='!test1234',
            channel=0,
            content='Hello World',  # Decrypted content
            message_type=MessageType.TEXT
        )
        
        # Format as protobuf - should use decoded field
        protobuf_bytes = formatter.format_protobuf(message)
        assert protobuf_bytes is not None
        
        # Verify the decoded payload was included
        from meshtastic.protobuf import mqtt_pb2
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Should have decoded field set (not encrypted)
        assert envelope.packet.HasField('decoded')
        assert not envelope.packet.HasField('encrypted')
        assert envelope.packet.decoded.payload == b'Hello World'
    
    def test_missing_encrypted_payload_uses_empty(self):
        """Test that missing encrypted payload uses empty bytes"""
        config = {
            'region': 'US',
            'encryption_enabled': True,  # Encryption mode
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Create message without encrypted payload
        message = Message(
            sender_id='!test1234',
            channel=0,
            content='test',
            message_type=MessageType.TEXT,
            metadata={}  # No encrypted_payload
        )
        
        # Should not raise, should use empty encrypted field
        protobuf_bytes = formatter.format_protobuf(message)
        assert protobuf_bytes is not None
        
        from meshtastic.protobuf import mqtt_pb2
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        
        # Should have empty encrypted field
        assert envelope.packet.HasField('encrypted')
        assert envelope.packet.encrypted == b''
    
    def test_invalid_encrypted_payload_type_logs_warning(self, caplog):
        """Test that invalid encrypted payload type is logged"""
        import logging
        
        config = {
            'region': 'US',
            'encryption_enabled': True,  # Encryption mode
            'channels': []
        }
        
        # Create logger that captures warnings
        logger = logging.getLogger('test_decryption')
        logger.setLevel(logging.WARNING)
        
        formatter = MessageFormatter(config, logger=logger)
        
        # Create message with invalid encrypted payload type
        message = Message(
            sender_id='!test1234',
            channel=0,
            content=None,
            message_type=MessageType.TEXT,
            metadata={
                'encrypted_payload': 'not bytes',  # Invalid type
            }
        )
        
        # Format should succeed but log warning and use empty
        with caplog.at_level(logging.WARNING):
            protobuf_bytes = formatter.format_protobuf(message)
            assert protobuf_bytes is not None
            
            # Check that warning was logged
            assert any('encrypted_payload is not bytes' in record.message 
                      for record in caplog.records)
        
        # Verify empty encrypted field was used
        from meshtastic.protobuf import mqtt_pb2
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(protobuf_bytes)
        assert envelope.packet.encrypted == b''


class TestIntegratedErrorHandling:
    """
    Test integrated error handling across components
    
    **Validates: Requirements 2.4, 8.4, 8.5**
    """
    
    @pytest.mark.asyncio
    async def test_serialization_error_does_not_crash_plugin(self):
        """Test that serialization errors don't crash the plugin"""
        # This would be tested in the plugin integration tests
        # Here we verify that formatter errors are caught
        config = {
            'region': 'US',
            'encryption_enabled': False,
            'channels': []
        }
        formatter = MessageFormatter(config)
        
        # Create invalid message
        invalid_message = Message(
            sender_id='',  # Invalid
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError):
            formatter.format_json(invalid_message)
        
        # Formatter should still work for valid messages
        valid_message = Message(
            sender_id='!test1234',
            channel=0,
            content='test',
            message_type=MessageType.TEXT
        )
        
        json_str = formatter.format_json(valid_message)
        assert json_str is not None
    
    @pytest.mark.asyncio
    async def test_connection_error_allows_queuing(self):
        """Test that connection errors allow messages to be queued"""
        queue = MessageQueue(max_size=100)
        
        # Simulate connection error by not connecting
        # Messages should be queued
        msg = Message(sender_id='!test1234', channel=0, message_type=MessageType.TEXT)
        
        result = await queue.enqueue(msg, 'test/topic', b'payload')
        assert result is True
        assert queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_does_not_block_forever(self):
        """Test that rate limiter errors don't block forever"""
        limiter = RateLimiter(max_messages_per_second=10.0)
        
        # Even with errors, acquire should eventually return
        with patch.object(limiter, '_refill_tokens', side_effect=Exception("Error")):
            result = await asyncio.wait_for(limiter.acquire(), timeout=1.0)
            assert result is True
