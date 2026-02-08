"""
Priority Queue for Network Traceroute Mapper

This module implements a priority queue for traceroute requests with intelligent
ordering, duplicate detection, and configurable overflow handling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import IntEnum
import heapq
import logging


class TraceroutePriority(IntEnum):
    """Priority levels for traceroute requests (lower number = higher priority)"""
    NEW_NODE = 1          # New indirect node discovered
    CRITICAL = 2          # Manual request or critical path
    NODE_BACK_ONLINE = 4  # Node came back online
    TOPOLOGY_CHANGE = 6   # Detected topology change
    PERIODIC_RECHECK = 8  # Scheduled periodic recheck
    LOW_PRIORITY = 10     # Background discovery


@dataclass(order=True)
class TracerouteRequest:
    """
    Traceroute request in the queue.
    
    The dataclass is ordered by priority first, then by queued_at timestamp
    to ensure FIFO ordering for requests with the same priority.
    """
    # Fields used for ordering (must come first)
    priority: int
    queued_at: datetime = field(compare=True)
    
    # Fields not used for ordering
    request_id: str = field(compare=False)
    node_id: str = field(compare=False)
    reason: str = field(compare=False)
    retry_count: int = field(default=0, compare=False)


class PriorityQueue:
    """
    Priority queue for traceroute requests with intelligent ordering.
    
    Responsibilities:
    - Queue traceroute requests with priority levels (1-10)
    - Process requests in priority order (lowest number = highest priority)
    - Enforce maximum queue size
    - Handle queue overflow with configurable strategies
    - Prevent duplicate requests for the same node
    """
    
    def __init__(self, max_size: int = 500, overflow_strategy: str = "drop_lowest_priority"):
        """
        Initialize the PriorityQueue.
        
        Args:
            max_size: Maximum number of requests in the queue
            overflow_strategy: Strategy for handling queue overflow
                - "drop_lowest_priority": Drop lowest priority request when full
                - "drop_oldest": Drop oldest request when full
                - "drop_new": Reject new request when full
        """
        self.logger = logging.getLogger(__name__)
        self.max_size = max_size
        self.overflow_strategy = overflow_strategy
        
        # Priority queue (min-heap)
        self._heap: List[TracerouteRequest] = []
        
        # Track nodes currently in queue (for duplicate detection)
        self._queued_nodes: Set[str] = set()
        
        # Map node_id to request for quick lookup
        self._node_to_request: Dict[str, TracerouteRequest] = {}
        
        # Statistics
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_dropped = 0
        
        self.logger.info(
            f"PriorityQueue initialized with max_size={max_size}, "
            f"overflow_strategy={overflow_strategy}"
        )
    
    def enqueue(self, node_id: str, priority: int, reason: str, request_id: Optional[str] = None) -> bool:
        """
        Add a traceroute request to the queue.
        
        Args:
            node_id: The node identifier
            priority: Priority level (1-10, lower = higher priority)
            reason: Reason for the traceroute request
            request_id: Optional unique request ID (generated if not provided)
            
        Returns:
            True if the request was enqueued, False if rejected
        """
        # Check for duplicate
        if node_id in self._queued_nodes:
            # Update priority if new priority is higher (lower number)
            existing_request = self._node_to_request.get(node_id)
            if existing_request and priority < existing_request.priority:
                self.logger.debug(
                    f"Updating priority for node {node_id} from "
                    f"{existing_request.priority} to {priority}"
                )
                # Remove old request and add new one
                self._remove_from_heap(existing_request)
                self._queued_nodes.remove(node_id)
                del self._node_to_request[node_id]
            else:
                self.logger.debug(
                    f"Node {node_id} already in queue with priority "
                    f"{existing_request.priority if existing_request else 'unknown'}, skipping"
                )
                return False
        
        # Check if queue is full
        if self.is_full():
            if not self._handle_overflow(priority):
                self.logger.warning(
                    f"Queue full, rejecting request for node {node_id} "
                    f"(priority={priority}, strategy={self.overflow_strategy})"
                )
                self._total_dropped += 1
                return False
        
        # Create request
        if request_id is None:
            request_id = f"{node_id}_{datetime.now().timestamp()}"
        
        request = TracerouteRequest(
            request_id=request_id,
            node_id=node_id,
            priority=priority,
            reason=reason,
            queued_at=datetime.now(),
            retry_count=0
        )
        
        # Add to heap and tracking structures
        heapq.heappush(self._heap, request)
        self._queued_nodes.add(node_id)
        self._node_to_request[node_id] = request
        self._total_enqueued += 1
        
        self.logger.debug(
            f"Enqueued traceroute for node {node_id} with priority {priority} "
            f"(reason: {reason}, queue_size: {self.size()})"
        )
        
        return True
    
    def dequeue(self) -> Optional[TracerouteRequest]:
        """
        Remove and return the highest priority request from the queue.
        
        Requests are processed in priority order (lowest number first).
        Requests with the same priority are processed in FIFO order.
        
        Returns:
            TracerouteRequest if queue is not empty, None otherwise
        """
        if not self._heap:
            return None
        
        # Pop from heap
        request = heapq.heappop(self._heap)
        
        # Remove from tracking structures
        self._queued_nodes.discard(request.node_id)
        self._node_to_request.pop(request.node_id, None)
        self._total_dequeued += 1
        
        self.logger.debug(
            f"Dequeued traceroute for node {request.node_id} with priority "
            f"{request.priority} (queue_size: {self.size()})"
        )
        
        return request
    
    def remove(self, node_id: str) -> bool:
        """
        Remove a specific node's request from the queue.
        
        Args:
            node_id: The node identifier
            
        Returns:
            True if the request was removed, False if not found
        """
        if node_id not in self._queued_nodes:
            return False
        
        request = self._node_to_request.get(node_id)
        if not request:
            return False
        
        # Remove from heap
        self._remove_from_heap(request)
        
        # Remove from tracking structures
        self._queued_nodes.discard(node_id)
        self._node_to_request.pop(node_id, None)
        
        self.logger.debug(f"Removed traceroute request for node {node_id}")
        
        return True
    
    def contains(self, node_id: str) -> bool:
        """
        Check if a node has a pending request in the queue.
        
        Args:
            node_id: The node identifier
            
        Returns:
            True if the node has a pending request, False otherwise
        """
        return node_id in self._queued_nodes
    
    def clear(self) -> None:
        """Clear all requests from the queue."""
        count = len(self._heap)
        self._heap.clear()
        self._queued_nodes.clear()
        self._node_to_request.clear()
        self.logger.info(f"Cleared {count} requests from queue")
    
    def size(self) -> int:
        """
        Get the current size of the queue.
        
        Returns:
            Number of requests in the queue
        """
        return len(self._heap)
    
    def is_empty(self) -> bool:
        """
        Check if the queue is empty.
        
        Returns:
            True if the queue is empty, False otherwise
        """
        return len(self._heap) == 0
    
    def is_full(self) -> bool:
        """
        Check if the queue is full.
        
        Returns:
            True if the queue is at maximum capacity, False otherwise
        """
        return len(self._heap) >= self.max_size
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the queue.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'current_size': self.size(),
            'max_size': self.max_size,
            'total_enqueued': self._total_enqueued,
            'total_dequeued': self._total_dequeued,
            'total_dropped': self._total_dropped,
            'overflow_strategy': self.overflow_strategy
        }
    
    def _handle_overflow(self, new_priority: int) -> bool:
        """
        Handle queue overflow based on the configured strategy.
        
        Args:
            new_priority: Priority of the new request trying to be added
            
        Returns:
            True if space was made for the new request, False otherwise
        """
        if self.overflow_strategy == "drop_lowest_priority":
            return self._drop_lowest_priority(new_priority)
        elif self.overflow_strategy == "drop_oldest":
            return self._drop_oldest()
        elif self.overflow_strategy == "drop_new":
            return False
        else:
            self.logger.error(f"Unknown overflow strategy: {self.overflow_strategy}")
            return False
    
    def _drop_lowest_priority(self, new_priority: int) -> bool:
        """
        Drop the lowest priority request to make room for a higher priority one.
        
        Args:
            new_priority: Priority of the new request
            
        Returns:
            True if a lower priority request was dropped, False otherwise
        """
        if not self._heap:
            return False
        
        # Find the lowest priority request (highest priority number)
        lowest_priority_request = max(self._heap, key=lambda r: r.priority)
        
        # Only drop if the new request has higher priority
        if new_priority < lowest_priority_request.priority:
            self.logger.debug(
                f"Dropping lowest priority request for node "
                f"{lowest_priority_request.node_id} (priority={lowest_priority_request.priority}) "
                f"to make room for priority {new_priority}"
            )
            self.remove(lowest_priority_request.node_id)
            self._total_dropped += 1
            return True
        
        return False
    
    def _drop_oldest(self) -> bool:
        """
        Drop the oldest request to make room for a new one.
        
        Returns:
            True if a request was dropped, False otherwise
        """
        if not self._heap:
            return False
        
        # Find the oldest request (earliest queued_at)
        oldest_request = min(self._heap, key=lambda r: r.queued_at)
        
        self.logger.debug(
            f"Dropping oldest request for node {oldest_request.node_id} "
            f"(queued_at={oldest_request.queued_at})"
        )
        self.remove(oldest_request.node_id)
        self._total_dropped += 1
        return True
    
    def _remove_from_heap(self, request: TracerouteRequest) -> None:
        """
        Remove a specific request from the heap.
        
        This is an O(n) operation as we need to rebuild the heap.
        
        Args:
            request: The request to remove
        """
        try:
            self._heap.remove(request)
            heapq.heapify(self._heap)
        except ValueError:
            # Request not in heap (shouldn't happen, but handle gracefully)
            self.logger.warning(
                f"Request for node {request.node_id} not found in heap during removal"
            )
