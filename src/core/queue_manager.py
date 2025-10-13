"""
Message Queue and Rate Limiting System for ZephyrGate

Implements priority-based message queuing, rate limiting, and message chunking
to respect Meshtastic constraints and ensure reliable message delivery.
"""

import asyncio
import heapq
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import json

from ..models.message import Message, MessagePriority, QueuedMessage
from .logging import get_logger


class QueueType(Enum):
    """Message queue types"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    RETRY = "retry"
    PRIORITY = "priority"


@dataclass
class QueueStats:
    """Queue statistics"""
    messages_queued: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_dropped: int = 0
    average_wait_time: float = 0.0
    queue_size: int = 0
    max_queue_size: int = 0
    
    def update_wait_time(self, wait_time: float):
        """Update average wait time"""
        if self.messages_processed == 0:
            self.average_wait_time = wait_time
        else:
            # Exponential moving average
            self.average_wait_time = (self.average_wait_time * 0.9) + (wait_time * 0.1)


@dataclass
class RateLimitRule:
    """Rate limiting rule"""
    key_pattern: str
    max_tokens: float
    refill_rate: float  # tokens per second
    burst_size: float
    window_seconds: int = 60
    
    def matches_key(self, key: str) -> bool:
        """Check if key matches this rule"""
        import re
        return bool(re.match(self.key_pattern, key))


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    max_tokens: float
    tokens: float
    refill_rate: float
    last_refill: datetime
    burst_size: float = 0
    
    def __post_init__(self):
        if self.burst_size == 0:
            self.burst_size = self.max_tokens
    
    def can_consume(self, tokens: float = 1.0) -> bool:
        """Check if tokens can be consumed"""
        self._refill()
        return self.tokens >= tokens
    
    def consume(self, tokens: float = 1.0) -> bool:
        """Consume tokens if available"""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        
        # Add tokens based on refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def get_wait_time(self, tokens: float = 1.0) -> float:
        """Get time to wait before tokens are available"""
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


@dataclass
class PriorityQueueItem:
    """Priority queue item wrapper"""
    priority: int
    timestamp: datetime
    message: QueuedMessage
    queue_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __lt__(self, other):
        # Higher priority first, then older messages first
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


class MessageChunker:
    """Handles message chunking for large messages"""
    
    def __init__(self, max_message_size: int = 228, chunk_overhead: int = 20):
        self.max_message_size = max_message_size
        self.chunk_overhead = chunk_overhead
        self.max_chunk_size = max_message_size - chunk_overhead
        self.logger = get_logger('message_chunker')
        
        # Track chunk reassembly
        self.chunk_buffers: Dict[str, Dict[int, str]] = {}
        self.chunk_metadata: Dict[str, Dict[str, Any]] = {}
        self.chunk_timeouts: Dict[str, datetime] = {}
    
    def needs_chunking(self, message: Message) -> bool:
        """Check if message needs to be chunked"""
        content_size = len(message.content.encode('utf-8'))
        return content_size > self.max_chunk_size
    
    def chunk_message(self, message: Message) -> List[Message]:
        """Split message into chunks"""
        if not self.needs_chunking(message):
            return [message]
        
        content = message.content
        content_bytes = content.encode('utf-8')
        
        # Calculate number of chunks needed
        total_chunks = (len(content_bytes) + self.max_chunk_size - 1) // self.max_chunk_size
        chunk_id = str(uuid.uuid4())[:8]
        
        chunks = []
        
        for i in range(total_chunks):
            start_byte = i * self.max_chunk_size
            end_byte = min(start_byte + self.max_chunk_size, len(content_bytes))
            
            # Extract chunk content (handle UTF-8 boundaries)
            chunk_bytes = content_bytes[start_byte:end_byte]
            
            # Ensure we don't break UTF-8 characters
            try:
                chunk_content = chunk_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Find the last complete UTF-8 character
                for j in range(len(chunk_bytes) - 1, -1, -1):
                    try:
                        chunk_content = chunk_bytes[:j].decode('utf-8')
                        # Adjust end_byte for next chunk
                        end_byte = start_byte + j
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Fallback: use original content with replacement
                    chunk_content = chunk_bytes.decode('utf-8', errors='replace')
            
            # Create chunk header
            chunk_header = f"[{i+1}/{total_chunks}:{chunk_id}]"
            full_chunk_content = f"{chunk_header} {chunk_content}"
            
            # Create chunk message
            chunk_msg = Message(
                id=f"{message.id}_chunk_{i}",
                sender_id=message.sender_id,
                recipient_id=message.recipient_id,
                channel=message.channel,
                content=full_chunk_content,
                message_type=message.message_type,
                priority=message.priority,
                metadata={
                    **message.metadata,
                    'is_chunk': True,
                    'chunk_id': chunk_id,
                    'chunk_index': i,
                    'total_chunks': total_chunks,
                    'original_message_id': message.id
                }
            )
            
            chunks.append(chunk_msg)
        
        self.logger.info(f"Chunked message {message.id} into {total_chunks} parts")
        return chunks
    
    def process_chunk(self, message: Message) -> Optional[Message]:
        """Process incoming chunk and reassemble if complete"""
        if not message.metadata.get('is_chunk'):
            return message
        
        chunk_id = message.metadata.get('chunk_id')
        chunk_index = message.metadata.get('chunk_index')
        total_chunks = message.metadata.get('total_chunks')
        
        if not all([chunk_id, chunk_index is not None, total_chunks]):
            self.logger.warning("Invalid chunk metadata")
            return None
        
        # Extract chunk content (remove header)
        content = message.content
        header_end = content.find('] ')
        if header_end != -1:
            chunk_content = content[header_end + 2:]
        else:
            chunk_content = content
        
        # Initialize chunk buffer if needed
        if chunk_id not in self.chunk_buffers:
            self.chunk_buffers[chunk_id] = {}
            self.chunk_metadata[chunk_id] = {
                'total_chunks': total_chunks,
                'original_message_id': message.metadata.get('original_message_id'),
                'sender_id': message.sender_id,
                'recipient_id': message.recipient_id,
                'channel': message.channel,
                'message_type': message.message_type,
                'priority': message.priority,
                'first_chunk_time': datetime.utcnow()
            }
            self.chunk_timeouts[chunk_id] = datetime.utcnow() + timedelta(minutes=5)
        
        # Store chunk
        self.chunk_buffers[chunk_id][chunk_index] = chunk_content
        
        # Check if all chunks received
        if len(self.chunk_buffers[chunk_id]) == total_chunks:
            # Reassemble message
            full_content = ''
            for i in range(total_chunks):
                if i in self.chunk_buffers[chunk_id]:
                    full_content += self.chunk_buffers[chunk_id][i]
                else:
                    self.logger.error(f"Missing chunk {i} for message {chunk_id}")
                    return None
            
            # Create reassembled message
            metadata = self.chunk_metadata[chunk_id]
            reassembled_message = Message(
                id=metadata.get('original_message_id', str(uuid.uuid4())),
                sender_id=metadata['sender_id'],
                recipient_id=metadata['recipient_id'],
                channel=metadata['channel'],
                content=full_content,
                message_type=metadata['message_type'],
                priority=metadata['priority'],
                metadata={'reassembled_from_chunks': True}
            )
            
            # Clean up
            del self.chunk_buffers[chunk_id]
            del self.chunk_metadata[chunk_id]
            del self.chunk_timeouts[chunk_id]
            
            self.logger.info(f"Reassembled message {chunk_id} from {total_chunks} chunks")
            return reassembled_message
        
        # Not all chunks received yet
        return None
    
    def cleanup_expired_chunks(self):
        """Clean up expired chunk buffers"""
        now = datetime.utcnow()
        expired_chunks = [
            chunk_id for chunk_id, timeout in self.chunk_timeouts.items()
            if now > timeout
        ]
        
        for chunk_id in expired_chunks:
            self.logger.warning(f"Cleaning up expired chunk buffer: {chunk_id}")
            self.chunk_buffers.pop(chunk_id, None)
            self.chunk_metadata.pop(chunk_id, None)
            self.chunk_timeouts.pop(chunk_id, None)


class RateLimiter:
    """Rate limiting system with multiple rules and token buckets"""
    
    def __init__(self):
        self.logger = get_logger('rate_limiter')
        self.buckets: Dict[str, TokenBucket] = {}
        self.rules: List[RateLimitRule] = []
        self.global_bucket: Optional[TokenBucket] = None
        
        # Default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Set up default rate limiting rules"""
        # Global rate limit
        self.global_bucket = TokenBucket(
            max_tokens=10.0,
            tokens=10.0,
            refill_rate=1.0,  # 1 message per second
            last_refill=datetime.utcnow()
        )
        
        # Per-sender rate limits
        self.rules.extend([
            RateLimitRule(
                key_pattern=r'sender_.*',
                max_tokens=5.0,
                refill_rate=0.2,  # 1 message per 5 seconds per sender
                burst_size=3.0
            ),
            RateLimitRule(
                key_pattern=r'emergency_.*',
                max_tokens=10.0,
                refill_rate=2.0,  # Emergency messages get higher rate
                burst_size=5.0
            ),
            RateLimitRule(
                key_pattern=r'channel_.*',
                max_tokens=20.0,
                refill_rate=1.0,  # 1 message per second per channel
                burst_size=10.0
            )
        ])
    
    def add_rule(self, rule: RateLimitRule):
        """Add a rate limiting rule"""
        self.rules.append(rule)
        self.logger.info(f"Added rate limit rule: {rule.key_pattern}")
    
    def can_send(self, key: str, tokens: float = 1.0) -> bool:
        """Check if message can be sent"""
        # Check global rate limit
        if self.global_bucket and not self.global_bucket.can_consume(tokens):
            return False
        
        # Check specific bucket
        bucket = self._get_bucket(key)
        if bucket and not bucket.can_consume(tokens):
            return False
        
        return True
    
    def consume(self, key: str, tokens: float = 1.0) -> bool:
        """Consume tokens for sending"""
        # Consume from global bucket
        if self.global_bucket and not self.global_bucket.consume(tokens):
            return False
        
        # Consume from specific bucket
        bucket = self._get_bucket(key)
        if bucket and not bucket.consume(tokens):
            # Refund global tokens
            if self.global_bucket:
                self.global_bucket.tokens = min(
                    self.global_bucket.max_tokens,
                    self.global_bucket.tokens + tokens
                )
            return False
        
        return True
    
    def get_wait_time(self, key: str, tokens: float = 1.0) -> float:
        """Get time to wait before tokens are available"""
        wait_times = []
        
        # Check global bucket
        if self.global_bucket:
            wait_times.append(self.global_bucket.get_wait_time(tokens))
        
        # Check specific bucket
        bucket = self._get_bucket(key)
        if bucket:
            wait_times.append(bucket.get_wait_time(tokens))
        
        return max(wait_times) if wait_times else 0.0
    
    def _get_bucket(self, key: str) -> Optional[TokenBucket]:
        """Get or create token bucket for key"""
        if key in self.buckets:
            return self.buckets[key]
        
        # Find matching rule
        for rule in self.rules:
            if rule.matches_key(key):
                bucket = TokenBucket(
                    max_tokens=rule.max_tokens,
                    tokens=rule.max_tokens,
                    refill_rate=rule.refill_rate,
                    last_refill=datetime.utcnow(),
                    burst_size=rule.burst_size
                )
                self.buckets[key] = bucket
                return bucket
        
        return None
    
    def cleanup_old_buckets(self, max_age_hours: int = 24):
        """Clean up old unused buckets"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        expired_keys = [
            key for key, bucket in self.buckets.items()
            if bucket.last_refill < cutoff_time
        ]
        
        for key in expired_keys:
            del self.buckets[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit buckets")


class QueueManager:
    """Manages message queues with priority handling and rate limiting"""
    
    def __init__(self, max_queue_size: int = 1000):
        self.logger = get_logger('queue_manager')
        self.max_queue_size = max_queue_size
        
        # Queue components
        self.rate_limiter = RateLimiter()
        self.chunker = MessageChunker()
        
        # Priority queues
        self.outbound_queue: List[PriorityQueueItem] = []
        self.inbound_queue = asyncio.Queue()
        self.retry_queue: List[PriorityQueueItem] = []
        
        # Processing tasks
        self.processing_tasks: Set[asyncio.Task] = set()
        self.running = False
        
        # Statistics
        self.stats = {
            'outbound': QueueStats(),
            'inbound': QueueStats(),
            'retry': QueueStats()
        }
        
        # Message tracking
        self.pending_messages: Dict[str, datetime] = {}
        
        self.logger.info("Queue manager initialized")
    
    async def start(self):
        """Start queue processing"""
        if self.running:
            return
        
        self.running = True
        self.logger.info("Starting queue manager")
        
        # Start processing tasks
        tasks = [
            asyncio.create_task(self._process_outbound_queue()),
            asyncio.create_task(self._process_inbound_queue()),
            asyncio.create_task(self._process_retry_queue()),
            asyncio.create_task(self._cleanup_task())
        ]
        
        for task in tasks:
            self.processing_tasks.add(task)
            task.add_done_callback(self.processing_tasks.discard)
        
        self.logger.info("Queue manager started")
    
    async def stop(self):
        """Stop queue processing"""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping queue manager")
        
        # Cancel processing tasks
        for task in self.processing_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.processing_tasks:
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        
        self.logger.info("Queue manager stopped")
    
    async def queue_outbound_message(self, message: Message, priority: Optional[MessagePriority] = None) -> bool:
        """Queue message for outbound processing"""
        if len(self.outbound_queue) >= self.max_queue_size:
            self.stats['outbound'].messages_dropped += 1
            self.logger.warning("Outbound queue full, dropping message")
            return False
        
        # Use message priority or default
        msg_priority = priority or message.priority
        
        # Create queued message
        queued_msg = QueuedMessage(message=message)
        
        # Create priority queue item
        queue_item = PriorityQueueItem(
            priority=msg_priority.value,
            timestamp=datetime.utcnow(),
            message=queued_msg
        )
        
        # Add to priority queue
        heapq.heappush(self.outbound_queue, queue_item)
        
        # Update stats
        self.stats['outbound'].messages_queued += 1
        self.stats['outbound'].queue_size = len(self.outbound_queue)
        self.stats['outbound'].max_queue_size = max(
            self.stats['outbound'].max_queue_size,
            self.stats['outbound'].queue_size
        )
        
        # Track message
        self.pending_messages[message.id] = datetime.utcnow()
        
        self.logger.debug(f"Queued outbound message {message.id} with priority {msg_priority.name}")
        return True
    
    async def queue_inbound_message(self, message: Message) -> bool:
        """Queue message for inbound processing"""
        try:
            await self.inbound_queue.put(message)
            self.stats['inbound'].messages_queued += 1
            self.stats['inbound'].queue_size = self.inbound_queue.qsize()
            self.stats['inbound'].max_queue_size = max(
                self.stats['inbound'].max_queue_size,
                self.stats['inbound'].queue_size
            )
            
            self.logger.debug(f"Queued inbound message {message.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue inbound message: {e}")
            self.stats['inbound'].messages_dropped += 1
            return False
    
    def set_outbound_processor(self, processor: callable):
        """Set callback for processing outbound messages"""
        self.outbound_processor = processor
    
    def set_inbound_processor(self, processor: callable):
        """Set callback for processing inbound messages"""
        self.inbound_processor = processor
    
    async def _process_outbound_queue(self):
        """Process outbound message queue"""
        while self.running:
            try:
                if not self.outbound_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get highest priority message
                queue_item = heapq.heappop(self.outbound_queue)
                message = queue_item.message.message
                
                # Calculate wait time
                queue_time = datetime.utcnow() - queue_item.timestamp
                self.stats['outbound'].update_wait_time(queue_time.total_seconds())
                
                # Check rate limiting
                rate_key = f"sender_{message.sender_id}"
                if not self.rate_limiter.can_send(rate_key):
                    wait_time = self.rate_limiter.get_wait_time(rate_key)
                    
                    if wait_time > 0:
                        # Re-queue with delay
                        await asyncio.sleep(min(wait_time, 1.0))
                        heapq.heappush(self.outbound_queue, queue_item)
                        continue
                
                # Chunk message if needed
                chunks = self.chunker.chunk_message(message)
                
                # Process each chunk
                success = True
                for chunk in chunks:
                    # Consume rate limit tokens
                    if not self.rate_limiter.consume(rate_key):
                        success = False
                        break
                    
                    # Send message (via callback)
                    if hasattr(self, 'outbound_processor'):
                        try:
                            await self.outbound_processor(chunk)
                        except Exception as e:
                            self.logger.error(f"Outbound processor failed: {e}")
                            success = False
                            break
                
                # Update stats
                if success:
                    self.stats['outbound'].messages_processed += 1
                    self.pending_messages.pop(message.id, None)
                else:
                    # Handle retry
                    if queue_item.message.should_retry():
                        queue_item.message.schedule_retry()
                        heapq.heappush(self.retry_queue, queue_item)
                        self.logger.info(f"Scheduled retry for message {message.id}")
                    else:
                        self.stats['outbound'].messages_failed += 1
                        self.pending_messages.pop(message.id, None)
                        self.logger.error(f"Message {message.id} failed after max retries")
                
                # Update queue size
                self.stats['outbound'].queue_size = len(self.outbound_queue)
                
            except Exception as e:
                self.logger.error(f"Error processing outbound queue: {e}")
                await asyncio.sleep(1)
    
    async def _process_inbound_queue(self):
        """Process inbound message queue"""
        while self.running:
            try:
                # Get message with timeout
                try:
                    message = await asyncio.wait_for(
                        self.inbound_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process chunks
                processed_message = self.chunker.process_chunk(message)
                
                if processed_message:
                    # Send to processor
                    if hasattr(self, 'inbound_processor'):
                        try:
                            await self.inbound_processor(processed_message)
                            self.stats['inbound'].messages_processed += 1
                        except Exception as e:
                            self.logger.error(f"Inbound processor failed: {e}")
                            self.stats['inbound'].messages_failed += 1
                    else:
                        self.stats['inbound'].messages_processed += 1
                
                # Update queue size
                self.stats['inbound'].queue_size = self.inbound_queue.qsize()
                
            except Exception as e:
                self.logger.error(f"Error processing inbound queue: {e}")
                await asyncio.sleep(1)
    
    async def _process_retry_queue(self):
        """Process retry queue"""
        while self.running:
            try:
                if not self.retry_queue:
                    await asyncio.sleep(1)
                    continue
                
                # Check for messages ready to retry
                now = datetime.utcnow()
                ready_items = []
                
                while self.retry_queue:
                    item = self.retry_queue[0]
                    if (item.message.next_retry is None or 
                        now >= item.message.next_retry):
                        ready_items.append(heapq.heappop(self.retry_queue))
                    else:
                        break
                
                # Move ready items back to outbound queue
                for item in ready_items:
                    heapq.heappush(self.outbound_queue, item)
                    self.logger.debug(f"Moved message {item.message.message.id} from retry to outbound queue")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error processing retry queue: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_task(self):
        """Periodic cleanup task"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean up rate limiter
                self.rate_limiter.cleanup_old_buckets()
                
                # Clean up expired chunks
                self.chunker.cleanup_expired_chunks()
                
                # Clean up old pending messages
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                expired_messages = [
                    msg_id for msg_id, timestamp in self.pending_messages.items()
                    if timestamp < cutoff_time
                ]
                
                for msg_id in expired_messages:
                    del self.pending_messages[msg_id]
                
                if expired_messages:
                    self.logger.debug(f"Cleaned up {len(expired_messages)} expired pending messages")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            'outbound': {
                'messages_queued': self.stats['outbound'].messages_queued,
                'messages_processed': self.stats['outbound'].messages_processed,
                'messages_failed': self.stats['outbound'].messages_failed,
                'messages_dropped': self.stats['outbound'].messages_dropped,
                'queue_size': len(self.outbound_queue),
                'max_queue_size': self.stats['outbound'].max_queue_size,
                'average_wait_time': self.stats['outbound'].average_wait_time
            },
            'inbound': {
                'messages_queued': self.stats['inbound'].messages_queued,
                'messages_processed': self.stats['inbound'].messages_processed,
                'messages_failed': self.stats['inbound'].messages_failed,
                'messages_dropped': self.stats['inbound'].messages_dropped,
                'queue_size': self.inbound_queue.qsize(),
                'max_queue_size': self.stats['inbound'].max_queue_size,
                'average_wait_time': self.stats['inbound'].average_wait_time
            },
            'retry': {
                'queue_size': len(self.retry_queue)
            },
            'rate_limiter': {
                'active_buckets': len(self.rate_limiter.buckets),
                'rules_count': len(self.rate_limiter.rules)
            },
            'chunker': {
                'active_chunk_buffers': len(self.chunker.chunk_buffers)
            },
            'pending_messages': len(self.pending_messages)
        }