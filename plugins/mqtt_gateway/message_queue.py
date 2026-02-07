"""
Message queue for MQTT Gateway

Implements a FIFO queue with priority support for queuing messages
when the MQTT broker is unavailable.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from src.models.message import Message, MessagePriority


@dataclass
class QueuedMQTTMessage:
    """Message queued for MQTT publishing"""
    message: Message
    topic: str
    payload: bytes
    qos: int
    priority: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3

    def __lt__(self, other):
        """Compare messages by priority (higher priority first), then timestamp (older first)"""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority comes first
        return self.timestamp < other.timestamp  # Older messages first


class MessageQueue:
    """
    FIFO queue with priority support for MQTT messages.
    
    Features:
    - FIFO ordering with priority levels
    - Maximum size enforcement with overflow handling
    - Statistics tracking
    - Thread-safe async operations
    """

    def __init__(self, max_size: int = 1000, logger: Optional[logging.Logger] = None):
        """
        Initialize message queue.
        
        Args:
            max_size: Maximum number of messages in queue
            logger: Logger instance for queue operations
        """
        self.max_size = max_size
        self.logger = logger or logging.getLogger(__name__)
        
        # Separate queues for each priority level
        self._queues: Dict[int, deque] = {
            MessagePriority.EMERGENCY.value: deque(),
            MessagePriority.HIGH.value: deque(),
            MessagePriority.NORMAL.value: deque(),
            MessagePriority.LOW.value: deque(),
        }
        
        # Statistics
        self._stats = {
            'enqueued': 0,
            'dequeued': 0,
            'dropped': 0,
            'overflow_drops': 0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def enqueue(self, message: Message, topic: str, payload: bytes, 
                     qos: int = 0, priority: Optional[int] = None) -> bool:
        """
        Add a message to the queue.
        
        Args:
            message: The Meshtastic message
            topic: MQTT topic to publish to
            payload: Message payload bytes
            qos: MQTT QoS level
            priority: Message priority (uses message.priority if not specified)
        
        Returns:
            True if message was enqueued, False if queue is full and message was dropped
        """
        async with self._lock:
            # Determine priority
            if priority is None:
                priority = message.priority.value
            
            # Check if queue is full
            if self.size() >= self.max_size:
                # Drop oldest message from lowest priority queue
                dropped = self._drop_oldest()
                if dropped:
                    self._stats['overflow_drops'] += 1
                    # Log queue overflow with details (Requirement 11.4)
                    self.logger.warning(
                        f"Queue overflow: dropped oldest message - "
                        f"dropped_priority={dropped.priority}, "
                        f"dropped_topic={dropped.topic}, "
                        f"queue_size={self.size()}/{self.max_size}, "
                        f"new_message_priority={priority}"
                    )
                else:
                    # All queues are empty (shouldn't happen, but handle it)
                    self.logger.error(
                        f"Queue full but no messages to drop - "
                        f"queue_size={self.size()}/{self.max_size}"
                    )
                    return False
            
            # Create queued message
            queued_msg = QueuedMQTTMessage(
                message=message,
                topic=topic,
                payload=payload,
                qos=qos,
                priority=priority
            )
            
            # Add to appropriate priority queue
            self._queues[priority].append(queued_msg)
            self._stats['enqueued'] += 1
            
            # Log enqueue with queue status (Requirement 11.4)
            self.logger.debug(
                f"Enqueued message - "
                f"topic={topic}, "
                f"priority={priority}, "
                f"queue_size={self.size()}/{self.max_size}, "
                f"priority_breakdown={self._get_priority_breakdown()}"
            )
            
            return True

    async def dequeue(self) -> Optional[QueuedMQTTMessage]:
        """
        Remove and return the highest priority message from the queue.
        
        Returns:
            The next message to process, or None if queue is empty
        """
        async with self._lock:
            # Check queues in priority order (highest to lowest)
            for priority in sorted(self._queues.keys(), reverse=True):
                if self._queues[priority]:
                    msg = self._queues[priority].popleft()
                    self._stats['dequeued'] += 1
                    
                    # Log dequeue with queue status (Requirement 11.4)
                    self.logger.debug(
                        f"Dequeued message - "
                        f"topic={msg.topic}, "
                        f"priority={priority}, "
                        f"retry_count={msg.retry_count}/{msg.max_retries}, "
                        f"queue_size={self.size()}/{self.max_size}, "
                        f"priority_breakdown={self._get_priority_breakdown()}"
                    )
                    
                    return msg
            
            return None

    def size(self) -> int:
        """
        Get the total number of messages in the queue.
        
        Returns:
            Total number of queued messages across all priorities
        """
        return sum(len(q) for q in self._queues.values())

    def is_full(self) -> bool:
        """
        Check if the queue is at maximum capacity.
        
        Returns:
            True if queue is full, False otherwise
        """
        return self.size() >= self.max_size

    def is_empty(self) -> bool:
        """
        Check if the queue is empty.
        
        Returns:
            True if queue is empty, False otherwise
        """
        return self.size() == 0

    async def clear(self) -> None:
        """Clear all messages from the queue."""
        async with self._lock:
            total_cleared = self.size()
            
            for queue in self._queues.values():
                queue.clear()
            
            # Log queue clear with count (Requirement 11.4)
            self.logger.info(
                f"Queue cleared - "
                f"messages_cleared={total_cleared}, "
                f"total_enqueued={self._stats['enqueued']}, "
                f"total_dequeued={self._stats['dequeued']}, "
                f"total_dropped={self._stats['dropped']}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary containing queue statistics
        """
        return {
            'size': self.size(),
            'max_size': self.max_size,
            'enqueued': self._stats['enqueued'],
            'dequeued': self._stats['dequeued'],
            'dropped': self._stats['dropped'],
            'overflow_drops': self._stats['overflow_drops'],
            'priority_breakdown': {
                priority: len(queue) 
                for priority, queue in self._queues.items()
            }
        }

    def _drop_oldest(self) -> Optional[QueuedMQTTMessage]:
        """
        Drop the oldest message from the lowest priority non-empty queue.
        
        Returns:
            The dropped message, or None if all queues are empty
        """
        # Check queues in priority order (lowest to highest)
        for priority in sorted(self._queues.keys()):
            if self._queues[priority]:
                dropped = self._queues[priority].popleft()
                self._stats['dropped'] += 1
                return dropped
        
        return None

    def _get_priority_breakdown(self) -> str:
        """
        Get a string representation of queue sizes by priority.
        
        Returns:
            String like "E:0,H:2,N:5,L:3" showing count per priority
        """
        priority_names = {
            MessagePriority.EMERGENCY.value: 'E',
            MessagePriority.HIGH.value: 'H',
            MessagePriority.NORMAL.value: 'N',
            MessagePriority.LOW.value: 'L',
        }
        
        breakdown = []
        for priority in sorted(self._queues.keys(), reverse=True):
            name = priority_names.get(priority, str(priority))
            count = len(self._queues[priority])
            breakdown.append(f"{name}:{count}")
        
        return ','.join(breakdown)
