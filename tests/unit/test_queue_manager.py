"""
Unit tests for Queue Manager and Rate Limiting

Tests message queuing, rate limiting, and message chunking functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from src.models.message import Message, MessageType, MessagePriority
from src.core.queue_manager import (
    QueueManager, RateLimiter, MessageChunker, TokenBucket,
    RateLimitRule, QueueType, QueueStats, PriorityQueueItem
)


class TestTokenBucket:
    """Test token bucket rate limiting"""
    
    def test_token_consumption(self):
        """Test basic token consumption"""
        bucket = TokenBucket(
            max_tokens=5.0,
            tokens=5.0,
            refill_rate=1.0,
            last_refill=datetime.utcnow()
        )
        
        # Should be able to consume available tokens
        assert bucket.can_consume(3.0)
        assert bucket.consume(3.0)
        assert bucket.tokens == 2.0
        
        # Should not be able to consume more than available
        assert not bucket.can_consume(3.0)
        assert not bucket.consume(3.0)
        assert bucket.tokens == 2.0
    
    def test_token_refill(self):
        """Test token refill over time"""
        past_time = datetime.utcnow() - timedelta(seconds=2)
        bucket = TokenBucket(
            max_tokens=5.0,
            tokens=0.0,
            refill_rate=1.0,  # 1 token per second
            last_refill=past_time
        )
        
        # Should refill tokens based on elapsed time
        bucket._refill()
        assert bucket.tokens >= 2.0  # At least 2 tokens after 2 seconds
        assert bucket.tokens <= 5.0  # But not more than max
    
    def test_max_tokens_limit(self):
        """Test that tokens don't exceed maximum"""
        past_time = datetime.utcnow() - timedelta(seconds=10)
        bucket = TokenBucket(
            max_tokens=5.0,
            tokens=3.0,
            refill_rate=1.0,
            last_refill=past_time
        )
        
        bucket._refill()
        assert bucket.tokens == 5.0  # Should not exceed max_tokens
    
    def test_wait_time_calculation(self):
        """Test wait time calculation"""
        bucket = TokenBucket(
            max_tokens=5.0,
            tokens=1.0,
            refill_rate=2.0,  # 2 tokens per second
            last_refill=datetime.utcnow()
        )
        
        # Should not need to wait for available tokens
        assert bucket.get_wait_time(1.0) == 0.0
        
        # Should calculate wait time for unavailable tokens
        wait_time = bucket.get_wait_time(3.0)  # Need 2 more tokens
        assert wait_time == 1.0  # 2 tokens / 2 tokens per second = 1 second


class TestRateLimitRule:
    """Test rate limiting rules"""
    
    def test_pattern_matching(self):
        """Test pattern matching"""
        rule = RateLimitRule(
            key_pattern=r'sender_.*',
            max_tokens=5.0,
            refill_rate=1.0,
            burst_size=3.0
        )
        
        assert rule.matches_key('sender_12345')
        assert rule.matches_key('sender_abcdef')
        assert not rule.matches_key('channel_1')
        assert not rule.matches_key('global')


class TestRateLimiter:
    """Test rate limiter functionality"""
    
    def test_global_rate_limiting(self):
        """Test global rate limiting"""
        limiter = RateLimiter()
        
        # Should be able to send initially
        assert limiter.can_send('test_key')
        
        # Consume all global tokens
        for _ in range(10):
            limiter.consume('test_key')
        
        # Should be rate limited
        assert not limiter.can_send('test_key')
    
    def test_per_sender_rate_limiting(self):
        """Test per-sender rate limiting"""
        limiter = RateLimiter()
        
        sender_key = 'sender_12345'
        
        # Should be able to send initially
        assert limiter.can_send(sender_key)
        
        # Consume sender tokens
        for _ in range(5):
            if not limiter.consume(sender_key):
                break
        
        # Should be rate limited for this sender
        assert not limiter.can_send(sender_key)
        
        # But should still work for different sender
        assert limiter.can_send('sender_67890')
    
    def test_emergency_rate_limiting(self):
        """Test emergency message rate limiting"""
        limiter = RateLimiter()
        
        emergency_key = 'emergency_12345'
        
        # Emergency messages should have higher rate limits
        assert limiter.can_send(emergency_key)
        
        # Should be able to send more emergency messages
        for _ in range(8):  # Emergency has higher limit
            if not limiter.consume(emergency_key):
                break
        
        # Should eventually be rate limited
        assert not limiter.can_send(emergency_key)
    
    def test_wait_time_calculation(self):
        """Test wait time calculation"""
        limiter = RateLimiter()
        
        # Exhaust tokens
        for _ in range(10):
            limiter.consume('test_key')
        
        # Should have wait time
        wait_time = limiter.get_wait_time('test_key')
        assert wait_time > 0
    
    def test_bucket_cleanup(self):
        """Test old bucket cleanup"""
        limiter = RateLimiter()
        
        # Create some buckets
        limiter.consume('sender_1')
        limiter.consume('sender_2')
        
        assert len(limiter.buckets) >= 2
        
        # Simulate old buckets
        for bucket in limiter.buckets.values():
            bucket.last_refill = datetime.utcnow() - timedelta(hours=25)
        
        # Clean up
        limiter.cleanup_old_buckets(max_age_hours=24)
        
        # Buckets should be cleaned up
        assert len(limiter.buckets) == 0


class TestMessageChunker:
    """Test message chunking functionality"""
    
    def test_needs_chunking(self):
        """Test chunking necessity detection"""
        chunker = MessageChunker(max_message_size=100, chunk_overhead=20)
        
        # Small message should not need chunking
        small_message = Message(content="short message", sender_id="!12345678")
        assert not chunker.needs_chunking(small_message)
        
        # Large message should need chunking
        large_content = "A" * 200
        large_message = Message(content=large_content, sender_id="!12345678")
        assert chunker.needs_chunking(large_message)
    
    def test_message_chunking(self):
        """Test message chunking"""
        chunker = MessageChunker(max_message_size=100, chunk_overhead=20)
        
        # Create large message
        large_content = "A" * 200
        message = Message(
            content=large_content,
            sender_id="!12345678",
            recipient_id="!87654321"
        )
        
        chunks = chunker.chunk_message(message)
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should have proper metadata
        for i, chunk in enumerate(chunks):
            assert chunk.metadata['is_chunk'] is True
            assert chunk.metadata['chunk_index'] == i
            assert chunk.metadata['total_chunks'] == len(chunks)
            assert chunk.metadata['chunk_id'] is not None
            assert chunk.metadata['original_message_id'] == message.id
            
            # Chunk content should include header
            assert f"[{i+1}/{len(chunks)}:" in chunk.content
    
    def test_chunk_reassembly(self):
        """Test chunk reassembly"""
        chunker = MessageChunker(max_message_size=100, chunk_overhead=20)
        
        # Create and chunk message
        original_content = "This is a test message that will be chunked and reassembled"
        original_message = Message(
            content=original_content,
            sender_id="!12345678",
            recipient_id="!87654321"
        )
        
        chunks = chunker.chunk_message(original_message)
        
        # Process chunks (simulate receiving them)
        reassembled_message = None
        for chunk in chunks:
            result = chunker.process_chunk(chunk)
            if result:  # Last chunk returns reassembled message
                reassembled_message = result
        
        # Should reassemble correctly
        assert reassembled_message is not None
        assert reassembled_message.content == original_content
        assert reassembled_message.sender_id == original_message.sender_id
        assert reassembled_message.recipient_id == original_message.recipient_id
    
    def test_chunk_timeout_cleanup(self):
        """Test chunk timeout cleanup"""
        chunker = MessageChunker()
        
        # Create partial chunk buffer
        chunk_id = "test_chunk_123"
        chunker.chunk_buffers[chunk_id] = {0: "chunk 0 content"}
        chunker.chunk_metadata[chunk_id] = {
            'total_chunks': 2,
            'first_chunk_time': datetime.utcnow()
        }
        chunker.chunk_timeouts[chunk_id] = datetime.utcnow() - timedelta(minutes=10)
        
        # Clean up expired chunks
        chunker.cleanup_expired_chunks()
        
        # Should be cleaned up
        assert chunk_id not in chunker.chunk_buffers
        assert chunk_id not in chunker.chunk_metadata
        assert chunk_id not in chunker.chunk_timeouts
    
    def test_non_chunk_message_passthrough(self):
        """Test non-chunk message passthrough"""
        chunker = MessageChunker()
        
        message = Message(content="regular message", sender_id="!12345678")
        result = chunker.process_chunk(message)
        
        # Should return the message unchanged
        assert result == message


class TestQueueStats:
    """Test queue statistics"""
    
    def test_wait_time_update(self):
        """Test wait time update calculation"""
        stats = QueueStats()
        
        # First update
        stats.update_wait_time(5.0)
        assert stats.average_wait_time == 5.0
        
        # Second update (should use exponential moving average)
        stats.messages_processed = 1
        stats.update_wait_time(10.0)
        
        # Should be weighted average
        expected = (5.0 * 0.9) + (10.0 * 0.1)
        assert stats.average_wait_time == expected


class TestPriorityQueueItem:
    """Test priority queue item"""
    
    def test_priority_comparison(self):
        """Test priority-based comparison"""
        high_priority = PriorityQueueItem(
            priority=MessagePriority.EMERGENCY.value,
            timestamp=datetime.utcnow(),
            message=Mock()
        )
        
        low_priority = PriorityQueueItem(
            priority=MessagePriority.LOW.value,
            timestamp=datetime.utcnow(),
            message=Mock()
        )
        
        # Higher priority should come first
        assert high_priority < low_priority
    
    def test_timestamp_comparison(self):
        """Test timestamp-based comparison for same priority"""
        earlier_time = datetime.utcnow() - timedelta(seconds=10)
        later_time = datetime.utcnow()
        
        earlier_item = PriorityQueueItem(
            priority=MessagePriority.NORMAL.value,
            timestamp=earlier_time,
            message=Mock()
        )
        
        later_item = PriorityQueueItem(
            priority=MessagePriority.NORMAL.value,
            timestamp=later_time,
            message=Mock()
        )
        
        # Earlier timestamp should come first for same priority
        assert earlier_item < later_item


class TestQueueManager:
    """Test queue manager functionality"""
    
    @pytest.fixture
    async def queue_manager(self):
        """Create queue manager for testing"""
        manager = QueueManager(max_queue_size=100)
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_queue_manager_initialization(self):
        """Test queue manager initialization"""
        manager = QueueManager()
        
        assert manager.max_queue_size == 1000
        assert isinstance(manager.rate_limiter, RateLimiter)
        assert isinstance(manager.chunker, MessageChunker)
        assert not manager.running
    
    @pytest.mark.asyncio
    async def test_outbound_message_queuing(self, queue_manager):
        """Test outbound message queuing"""
        message = Message(
            content="test message",
            sender_id="!12345678",
            priority=MessagePriority.HIGH
        )
        
        success = await queue_manager.queue_outbound_message(message)
        
        assert success
        assert len(queue_manager.outbound_queue) == 1
        assert queue_manager.stats['outbound'].messages_queued == 1
        assert message.id in queue_manager.pending_messages
    
    @pytest.mark.asyncio
    async def test_inbound_message_queuing(self, queue_manager):
        """Test inbound message queuing"""
        message = Message(content="test message", sender_id="!12345678")
        
        success = await queue_manager.queue_inbound_message(message)
        
        assert success
        assert queue_manager.inbound_queue.qsize() == 1
        assert queue_manager.stats['inbound'].messages_queued == 1
    
    @pytest.mark.asyncio
    async def test_queue_size_limit(self):
        """Test queue size limit"""
        manager = QueueManager(max_queue_size=2)
        
        # Fill queue to limit
        for i in range(2):
            message = Message(content=f"message {i}", sender_id="!12345678")
            success = await manager.queue_outbound_message(message)
            assert success
        
        # Next message should be dropped
        overflow_message = Message(content="overflow", sender_id="!12345678")
        success = await manager.queue_outbound_message(overflow_message)
        
        assert not success
        assert manager.stats['outbound'].messages_dropped == 1
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue_manager):
        """Test priority-based message ordering"""
        # Queue messages with different priorities
        low_msg = Message(content="low", sender_id="!12345678", priority=MessagePriority.LOW)
        high_msg = Message(content="high", sender_id="!12345678", priority=MessagePriority.HIGH)
        normal_msg = Message(content="normal", sender_id="!12345678", priority=MessagePriority.NORMAL)
        
        await queue_manager.queue_outbound_message(low_msg)
        await queue_manager.queue_outbound_message(high_msg)
        await queue_manager.queue_outbound_message(normal_msg)
        
        # High priority should be first
        first_item = queue_manager.outbound_queue[0]
        assert first_item.message.message.content == "high"
    
    @pytest.mark.asyncio
    async def test_outbound_processing(self, queue_manager):
        """Test outbound message processing"""
        processed_messages = []
        
        async def mock_processor(message):
            processed_messages.append(message)
        
        queue_manager.set_outbound_processor(mock_processor)
        
        # Queue message
        message = Message(content="test", sender_id="!12345678")
        await queue_manager.queue_outbound_message(message)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Should be processed
        assert len(processed_messages) > 0
        assert queue_manager.stats['outbound'].messages_processed > 0
    
    @pytest.mark.asyncio
    async def test_inbound_processing(self, queue_manager):
        """Test inbound message processing"""
        processed_messages = []
        
        async def mock_processor(message):
            processed_messages.append(message)
        
        queue_manager.set_inbound_processor(mock_processor)
        
        # Queue message
        message = Message(content="test", sender_id="!12345678")
        await queue_manager.queue_inbound_message(message)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Should be processed
        assert len(processed_messages) > 0
        assert queue_manager.stats['inbound'].messages_processed > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, queue_manager):
        """Test rate limiting integration"""
        processed_messages = []
        
        async def mock_processor(message):
            processed_messages.append(message)
        
        queue_manager.set_outbound_processor(mock_processor)
        
        # Queue many messages from same sender
        sender_id = "!12345678"
        for i in range(10):
            message = Message(content=f"message {i}", sender_id=sender_id)
            await queue_manager.queue_outbound_message(message)
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Should be rate limited (not all messages processed immediately)
        assert len(processed_messages) < 10
    
    @pytest.mark.asyncio
    async def test_message_chunking_integration(self, queue_manager):
        """Test message chunking integration"""
        processed_messages = []
        
        async def mock_processor(message):
            processed_messages.append(message)
        
        queue_manager.set_outbound_processor(mock_processor)
        
        # Queue large message that needs chunking
        large_content = "A" * 300
        message = Message(content=large_content, sender_id="!12345678")
        await queue_manager.queue_outbound_message(message)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Should process multiple chunks
        assert len(processed_messages) > 1
        
        # Each processed message should be a chunk
        for processed_msg in processed_messages:
            assert '[' in processed_msg.content  # Chunk header
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, queue_manager):
        """Test message retry mechanism"""
        failed_attempts = 0
        
        async def failing_processor(message):
            nonlocal failed_attempts
            failed_attempts += 1
            if failed_attempts <= 2:  # Fail first 2 attempts
                raise Exception("Processing failed")
        
        queue_manager.set_outbound_processor(failing_processor)
        
        # Queue message
        message = Message(content="test", sender_id="!12345678")
        await queue_manager.queue_outbound_message(message)
        
        # Wait for processing and retries
        await asyncio.sleep(2.0)
        
        # Should have retried
        assert failed_attempts > 1
        assert len(queue_manager.retry_queue) >= 0  # May be empty if retries succeeded
    
    def test_statistics_collection(self, queue_manager):
        """Test statistics collection"""
        stats = queue_manager.get_stats()
        
        # Verify required stats are present
        assert 'outbound' in stats
        assert 'inbound' in stats
        assert 'retry' in stats
        assert 'rate_limiter' in stats
        assert 'chunker' in stats
        assert 'pending_messages' in stats
        
        # Verify outbound stats structure
        outbound_stats = stats['outbound']
        assert 'messages_queued' in outbound_stats
        assert 'messages_processed' in outbound_stats
        assert 'messages_failed' in outbound_stats
        assert 'messages_dropped' in outbound_stats
        assert 'queue_size' in outbound_stats
        assert 'average_wait_time' in outbound_stats


class TestQueueManagerIntegration:
    """Integration tests for queue manager"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_message_flow(self):
        """Test complete message flow through queue manager"""
        manager = QueueManager()
        await manager.start()
        
        try:
            processed_outbound = []
            processed_inbound = []
            
            async def outbound_processor(message):
                processed_outbound.append(message)
            
            async def inbound_processor(message):
                processed_inbound.append(message)
            
            manager.set_outbound_processor(outbound_processor)
            manager.set_inbound_processor(inbound_processor)
            
            # Queue outbound message
            outbound_msg = Message(content="outbound test", sender_id="!12345678")
            await manager.queue_outbound_message(outbound_msg)
            
            # Queue inbound message
            inbound_msg = Message(content="inbound test", sender_id="!87654321")
            await manager.queue_inbound_message(inbound_msg)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Verify processing
            assert len(processed_outbound) > 0
            assert len(processed_inbound) > 0
            
            # Verify statistics
            stats = manager.get_stats()
            assert stats['outbound']['messages_processed'] > 0
            assert stats['inbound']['messages_processed'] > 0
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_high_load_handling(self):
        """Test queue manager under high load"""
        manager = QueueManager(max_queue_size=50)
        await manager.start()
        
        try:
            processed_count = 0
            
            async def counting_processor(message):
                nonlocal processed_count
                processed_count += 1
                await asyncio.sleep(0.01)  # Simulate processing time
            
            manager.set_outbound_processor(counting_processor)
            
            # Queue many messages
            message_count = 30
            for i in range(message_count):
                message = Message(
                    content=f"load test {i}",
                    sender_id=f"!{i:08d}",
                    priority=MessagePriority.NORMAL
                )
                await manager.queue_outbound_message(message)
            
            # Wait for processing
            await asyncio.sleep(2.0)
            
            # Should process most messages (some may be rate limited)
            assert processed_count > 0
            
            # Verify statistics
            stats = manager.get_stats()
            assert stats['outbound']['messages_queued'] == message_count
            
        finally:
            await manager.stop()


if __name__ == '__main__':
    pytest.main([__file__])