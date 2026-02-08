"""
Traceroute Manager for Network Traceroute Mapper

Manages traceroute request sending and response handling, including:
- Sending Meshtastic-compliant traceroute requests
- Tracking pending traceroute requests with timeout tracking
- Handling traceroute responses
- Implementing retry logic with exponential backoff
"""

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any

# Add src directory to path for imports (same as plugin)
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from models.message import Message, MessageType, MessagePriority


@dataclass
class PendingTraceroute:
    """
    Tracks a pending traceroute request awaiting response.
    
    Attributes:
        request_id: Unique identifier for this traceroute request
        node_id: Target node ID for the traceroute
        sent_at: Timestamp when the request was sent
        timeout_at: Timestamp when the request should timeout
        retry_count: Number of retry attempts made
        max_retries: Maximum number of retry attempts allowed
        priority: Priority level of this request (1-10)
    """
    request_id: str
    node_id: str
    sent_at: datetime
    timeout_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 8


@dataclass
class TracerouteResult:
    """
    Result of a completed traceroute.
    
    Attributes:
        node_id: Target node ID that was traced
        timestamp: When the traceroute completed
        success: Whether the traceroute was successful
        hop_count: Number of hops in the route
        route: List of node IDs in the path from source to destination
        snr_values: SNR values for each hop in the route
        rssi_values: RSSI values for each hop in the route
        duration_ms: Duration of the traceroute in milliseconds
        error_message: Error message if traceroute failed
    """
    node_id: str
    timestamp: datetime
    success: bool
    hop_count: int
    route: List[str] = field(default_factory=list)
    snr_values: List[float] = field(default_factory=list)
    rssi_values: List[float] = field(default_factory=list)
    duration_ms: float = 0.0
    error_message: Optional[str] = None


class TracerouteManager:
    """
    Manages traceroute request sending and response handling.
    
    Responsibilities:
    - Send traceroute requests to Meshtastic interface
    - Track pending traceroute requests
    - Handle traceroute responses
    - Implement retry logic with exponential backoff
    - Timeout detection for failed traceroutes
    - Forward traceroute messages to message router for MQTT publishing
    """
    
    def __init__(
        self,
        max_hops: int = 7,
        timeout_seconds: int = 60,
        max_retries: int = 3,
        retry_backoff_multiplier: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize TracerouteManager.
        
        Args:
            max_hops: Maximum number of hops for traceroute requests
            timeout_seconds: Timeout duration for traceroute requests
            max_retries: Maximum number of retry attempts
            retry_backoff_multiplier: Multiplier for exponential backoff
            logger: Logger instance (creates new one if not provided)
        """
        self.max_hops = max_hops
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_multiplier = retry_backoff_multiplier
        self.logger = logger or logging.getLogger(__name__)
        
        # Track pending traceroute requests
        self._pending_traceroutes: Dict[str, PendingTraceroute] = {}
        
        # Statistics
        self._stats = {
            'requests_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'retries': 0
        }
    
    async def send_traceroute(
        self,
        node_id: str,
        priority: int = 8,
        max_hops: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> str:
        """
        Create and send a traceroute request to a target node.
        
        Creates a Meshtastic-compliant traceroute request message with:
        - MessageType.ROUTING (TRACEROUTE_APP in Meshtastic)
        - hop_limit set to max_hops
        - want_response flag set to true in metadata
        - route_discovery flag set to true in metadata
        
        Args:
            node_id: Target node ID to traceroute
            priority: Priority level for this request (1-10)
            max_hops: Maximum hops (uses default if None)
            timeout_seconds: Timeout duration (uses default if None)
            max_retries: Maximum retries (uses default if None)
        
        Returns:
            request_id: Unique identifier for this traceroute request
        
        Requirements:
            - 6.1: Set hop_limit to configured max_hops
            - 18.1: Use MessageType.ROUTING (TRACEROUTE_APP)
            - 18.2: Set want_response flag to true
            - 18.3: Include destination node_id and max_hops
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Use provided values or defaults
        hops = max_hops if max_hops is not None else self.max_hops
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        retries = max_retries if max_retries is not None else self.max_retries
        
        # Calculate timeout timestamp
        sent_at = datetime.utcnow()
        timeout_at = sent_at + timedelta(seconds=timeout)
        
        # Create Meshtastic-compliant traceroute request
        message = Message(
            id=request_id,
            recipient_id=node_id,
            message_type=MessageType.ROUTING,  # TRACEROUTE_APP in Meshtastic
            content="",  # Empty content for traceroute
            hop_limit=hops,  # Set max hops for traceroute
            priority=MessagePriority.NORMAL,
            metadata={
                'want_response': True,  # Request response from destination
                'route_discovery': True,  # Enable route discovery
                'request_id': request_id,  # Track this request
                'traceroute': True  # Mark as traceroute message
            }
        )
        
        # Track pending traceroute
        pending = PendingTraceroute(
            request_id=request_id,
            node_id=node_id,
            sent_at=sent_at,
            timeout_at=timeout_at,
            retry_count=0,
            max_retries=retries,
            priority=priority
        )
        self._pending_traceroutes[request_id] = pending
        
        # Update statistics
        self._stats['requests_sent'] += 1
        
        # Log the traceroute request
        self.logger.info(
            f"Sending traceroute to {node_id} "
            f"(request_id={request_id}, max_hops={hops}, "
            f"timeout={timeout}s, priority={priority})"
        )
        
        # Note: The actual sending of the message to the Meshtastic interface
        # will be handled by the plugin's message routing system.
        # This method creates the message and tracks it as pending.
        # The plugin will need to retrieve this message and send it.
        
        return request_id
    
    def get_pending_traceroute(self, request_id: str) -> Optional[PendingTraceroute]:
        """
        Get a pending traceroute by request ID.
        
        Args:
            request_id: The request ID to look up
        
        Returns:
            PendingTraceroute object if found, None otherwise
        """
        return self._pending_traceroutes.get(request_id)
    
    def get_pending_traceroute_message(self, request_id: str) -> Optional[Message]:
        """
        Get the message for a pending traceroute request.
        
        This method allows the plugin to retrieve the message that needs to be sent.
        
        Args:
            request_id: The request ID returned by send_traceroute()
        
        Returns:
            Message object if request is pending, None otherwise
        """
        pending = self._pending_traceroutes.get(request_id)
        if not pending:
            return None
        
        # Recreate the message from the pending traceroute
        message = Message(
            id=request_id,
            recipient_id=pending.node_id,
            message_type=MessageType.ROUTING,
            content="",
            hop_limit=self.max_hops,
            priority=MessagePriority.NORMAL,
            metadata={
                'want_response': True,
                'route_discovery': True,
                'request_id': request_id,
                'traceroute': True
            }
        )
        
        return message
    
    def is_pending(self, request_id: str) -> bool:
        """
        Check if a traceroute request is pending.
        
        Args:
            request_id: Request ID to check
        
        Returns:
            True if request is pending, False otherwise
        """
        return request_id in self._pending_traceroutes
    
    def get_pending_count(self) -> int:
        """
        Get the number of pending traceroute requests.
        
        Returns:
            Number of pending requests
        """
        return len(self._pending_traceroutes)
    
    def get_pending_for_node(self, node_id: str) -> Optional[PendingTraceroute]:
        """
        Get pending traceroute for a specific node.
        
        Args:
            node_id: Node ID to check
        
        Returns:
            PendingTraceroute if one exists for this node, None otherwise
        """
        for pending in self._pending_traceroutes.values():
            if pending.node_id == node_id:
                return pending
        return None
    
    async def cancel_traceroute(self, request_id: str) -> bool:
        """
        Cancel a pending traceroute request.
        
        Args:
            request_id: Request ID to cancel
        
        Returns:
            True if request was cancelled, False if not found
        """
        if request_id in self._pending_traceroutes:
            pending = self._pending_traceroutes.pop(request_id)
            self.logger.debug(
                f"Cancelled traceroute to {pending.node_id} "
                f"(request_id={request_id})"
            )
            return True
        return False
    
    def check_timeouts(self) -> List[PendingTraceroute]:
        """
        Check for timed out traceroute requests.
        
        Returns:
            List of timed out PendingTraceroute objects
        """
        now = datetime.utcnow()
        timed_out = []
        
        for request_id, pending in list(self._pending_traceroutes.items()):
            if now >= pending.timeout_at:
                timed_out.append(pending)
                self._pending_traceroutes.pop(request_id)
                self._stats['timeouts'] += 1
                
                self.logger.warning(
                    f"Traceroute to {pending.node_id} timed out "
                    f"(request_id={request_id}, "
                    f"retry_count={pending.retry_count})"
                )
        
        return timed_out
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get traceroute manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            **self._stats,
            'pending_count': len(self._pending_traceroutes)
        }
    
    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            'requests_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'retries': 0
        }

    async def handle_traceroute_response(self, message: Message) -> Optional[TracerouteResult]:
        """
        Handle a traceroute response message.
        
        Parses the route array from the response metadata, extracts node IDs,
        SNR, and RSSI values, matches the response to a pending request, and
        calculates response time.
        
        Args:
            message: The traceroute response message
        
        Returns:
            TracerouteResult if response was successfully processed, None otherwise
        
        Requirements:
            - 18.4: Parse route array to extract node IDs
            - 18.5: Extract SNR and RSSI values from route entries
        """
        # Check if this is a traceroute response
        if not self._is_traceroute_response(message):
            self.logger.debug(f"Message {message.id} is not a traceroute response")
            return None
        
        # Extract request_id from metadata
        request_id = message.metadata.get('request_id')
        if not request_id:
            self.logger.warning(
                f"Traceroute response from {message.sender_id} missing request_id"
            )
            return None
        
        # Find the pending traceroute
        pending = self._pending_traceroutes.get(request_id)
        if not pending:
            self.logger.debug(
                f"Received traceroute response for unknown request {request_id}"
            )
            return None
        
        # Calculate response time
        now = datetime.utcnow()
        duration_ms = (now - pending.sent_at).total_seconds() * 1000.0
        
        # Parse the route array from metadata
        route_data = message.metadata.get('route', [])
        
        # Extract node IDs, SNR, and RSSI values
        route = []
        snr_values = []
        rssi_values = []
        
        for hop in route_data:
            if isinstance(hop, dict):
                # Extract node_id
                node_id = hop.get('node_id', '')
                if node_id:
                    route.append(node_id)
                
                # Extract SNR (may be None)
                snr = hop.get('snr')
                if snr is not None:
                    snr_values.append(float(snr))
                else:
                    snr_values.append(0.0)
                
                # Extract RSSI (may be None)
                rssi = hop.get('rssi')
                if rssi is not None:
                    rssi_values.append(float(rssi))
                else:
                    rssi_values.append(0.0)
            elif isinstance(hop, str):
                # Simple format: just node IDs
                route.append(hop)
                snr_values.append(0.0)
                rssi_values.append(0.0)
        
        # Create result
        result = TracerouteResult(
            node_id=pending.node_id,
            timestamp=now,
            success=True,
            hop_count=len(route),
            route=route,
            snr_values=snr_values,
            rssi_values=rssi_values,
            duration_ms=duration_ms
        )
        
        # Remove from pending
        self._pending_traceroutes.pop(request_id)
        
        # Update statistics
        self._stats['responses_received'] += 1
        
        # Log the successful traceroute
        self.logger.info(
            f"Traceroute to {pending.node_id} completed successfully "
            f"(request_id={request_id}, hops={len(route)}, "
            f"duration={duration_ms:.1f}ms, route={' -> '.join(route)})"
        )
        
        return result
    
    def _is_traceroute_response(self, message: Message) -> bool:
        """
        Check if a message is a traceroute response.
        
        Args:
            message: Message to check
        
        Returns:
            True if message is a traceroute response, False otherwise
        """
        # Check message type
        if message.message_type != MessageType.ROUTING:
            return False
        
        # Check for traceroute flag in metadata
        if not message.metadata.get('traceroute', False):
            return False
        
        # Check for route data in metadata
        if 'route' not in message.metadata:
            return False
        
        return True
    
    def parse_route_from_response(self, message: Message) -> List[str]:
        """
        Parse the route array from a traceroute response to extract node IDs.
        
        Args:
            message: Traceroute response message
        
        Returns:
            List of node IDs in the path from source to destination
        
        Requirements:
            - 18.4: Parse route array to extract node IDs
        """
        route_data = message.metadata.get('route', [])
        route = []
        
        for hop in route_data:
            if isinstance(hop, dict):
                node_id = hop.get('node_id', '')
                if node_id:
                    route.append(node_id)
            elif isinstance(hop, str):
                route.append(hop)
        
        return route
    
    def parse_signal_values_from_response(self, message: Message) -> tuple[List[float], List[float]]:
        """
        Parse SNR and RSSI values from a traceroute response.
        
        Args:
            message: Traceroute response message
        
        Returns:
            Tuple of (snr_values, rssi_values) lists
        
        Requirements:
            - 18.5: Extract SNR and RSSI values from route entries
        """
        route_data = message.metadata.get('route', [])
        snr_values = []
        rssi_values = []
        
        for hop in route_data:
            if isinstance(hop, dict):
                # Extract SNR (may be None)
                snr = hop.get('snr')
                if snr is not None:
                    snr_values.append(float(snr))
                else:
                    snr_values.append(0.0)
                
                # Extract RSSI (may be None)
                rssi = hop.get('rssi')
                if rssi is not None:
                    rssi_values.append(float(rssi))
                else:
                    rssi_values.append(0.0)
            else:
                # No signal data available
                snr_values.append(0.0)
                rssi_values.append(0.0)
        
        return snr_values, rssi_values

    def calculate_retry_delay(self, retry_count: int, initial_delay: float = 5.0, max_delay: float = 300.0) -> float:
        """
        Calculate exponential backoff delay for retry attempts.
        
        Args:
            retry_count: Current retry attempt number (0-indexed)
            initial_delay: Initial delay in seconds (default: 5.0)
            max_delay: Maximum delay in seconds (default: 300.0)
        
        Returns:
            Delay in seconds for this retry attempt
        
        Requirements:
            - 11.3: Implement exponential backoff between retry attempts
        """
        # Calculate exponential backoff: initial_delay * (multiplier ^ retry_count)
        delay = initial_delay * (self.retry_backoff_multiplier ** retry_count)
        
        # Cap at max_delay
        delay = min(delay, max_delay)
        
        return delay
    
    async def schedule_retry(self, pending: PendingTraceroute) -> bool:
        """
        Schedule a retry for a failed traceroute request.
        
        Args:
            pending: The PendingTraceroute that failed
        
        Returns:
            True if retry was scheduled, False if max retries exceeded
        
        Requirements:
            - 11.1: Retry up to configured maximum retry attempts
            - 11.3: Apply exponential backoff between attempts
            - 11.6: Remove request from queue when max retries exceeded
        """
        # Check if we've exceeded max retries
        if pending.retry_count >= pending.max_retries:
            self.logger.warning(
                f"Max retries ({pending.max_retries}) exceeded for traceroute to {pending.node_id} "
                f"(request_id={pending.request_id})"
            )
            return False
        
        # Increment retry count
        pending.retry_count += 1
        
        # Calculate backoff delay
        delay = self.calculate_retry_delay(pending.retry_count - 1)
        
        # Update timeout for retry
        now = datetime.utcnow()
        pending.sent_at = now + timedelta(seconds=delay)
        pending.timeout_at = pending.sent_at + timedelta(seconds=self.timeout_seconds)
        
        # Put back in pending traceroutes (will be sent after delay)
        self._pending_traceroutes[pending.request_id] = pending
        
        # Update statistics
        self._stats['retries'] += 1
        
        self.logger.info(
            f"Scheduled retry {pending.retry_count}/{pending.max_retries} for traceroute to {pending.node_id} "
            f"(request_id={pending.request_id}, delay={delay:.1f}s)"
        )
        
        return True
    
    def get_ready_requests(self) -> List[PendingTraceroute]:
        """
        Get pending traceroute requests that are ready to be sent.
        
        A request is ready if its sent_at time has passed (for retries with backoff delay).
        
        Returns:
            List of PendingTraceroute objects ready to be sent
        """
        now = datetime.utcnow()
        ready = []
        
        for pending in self._pending_traceroutes.values():
            if pending.sent_at <= now:
                ready.append(pending)
        
        return ready
