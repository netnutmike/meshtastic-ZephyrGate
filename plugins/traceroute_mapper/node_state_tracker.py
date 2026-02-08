"""
Node State Tracker for Network Traceroute Mapper

This module tracks the state of all known nodes on the mesh network,
including whether they are directly heard or indirect, last seen times,
and traceroute history.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging


@dataclass
class NodeState:
    """State of a node on the mesh network"""
    node_id: str
    is_direct: bool
    last_seen: datetime
    last_traced: Optional[datetime] = None
    next_recheck: Optional[datetime] = None
    last_trace_success: bool = False
    trace_count: int = 0
    failure_count: int = 0
    snr: Optional[float] = None
    rssi: Optional[float] = None
    was_offline: bool = False
    role: Optional[str] = None


class NodeStateTracker:
    """
    Tracks the state of all known nodes on the mesh network.
    
    Responsibilities:
    - Maintain node state (last seen, last traced, direct/indirect)
    - Determine if a node is directly heard or indirect
    - Track node online/offline transitions
    - Provide node filtering (blacklist, whitelist, role, SNR threshold)
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the NodeStateTracker.
        
        Args:
            config: Configuration dictionary with filtering settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Node state storage
        self._nodes: Dict[str, NodeState] = {}
        
        # Filtering configuration
        self._blacklist: Set[str] = set(config.get('blacklist', []))
        self._whitelist: Set[str] = set(config.get('whitelist', []))
        self._exclude_roles: Set[str] = set(config.get('exclude_roles', []))
        self._min_snr_threshold: Optional[float] = config.get('min_snr_threshold')
        self._skip_direct_nodes: bool = config.get('skip_direct_nodes', True)
        
        self.logger.info(
            f"NodeStateTracker initialized with blacklist={len(self._blacklist)}, "
            f"whitelist={len(self._whitelist)}, exclude_roles={self._exclude_roles}, "
            f"min_snr_threshold={self._min_snr_threshold}, skip_direct={self._skip_direct_nodes}"
        )
    
    def update_node(
        self,
        node_id: str,
        is_direct: bool,
        snr: Optional[float] = None,
        rssi: Optional[float] = None,
        role: Optional[str] = None,
        hop_count: Optional[int] = None
    ) -> None:
        """
        Update the state of a node.
        
        Args:
            node_id: The node identifier
            is_direct: Whether the node is directly heard (one hop away)
            snr: Signal-to-noise ratio (if available)
            rssi: Received signal strength indicator (if available)
            role: Node role (e.g., CLIENT, ROUTER, etc.)
            hop_count: Number of hops to reach the node (if available)
        """
        now = datetime.now()
        
        # Check if node exists
        if node_id in self._nodes:
            node = self._nodes[node_id]
            
            # Track if node was offline and came back
            was_offline = node.was_offline
            node.was_offline = False
            
            # Update state
            previous_is_direct = node.is_direct
            node.is_direct = is_direct or self._is_direct_from_signals(hop_count, snr, rssi)
            node.last_seen = now
            
            # Update signal values if provided
            if snr is not None:
                node.snr = snr
            if rssi is not None:
                node.rssi = rssi
            if role is not None:
                node.role = role
            
            # Log transition from indirect to direct
            if not previous_is_direct and node.is_direct:
                self.logger.debug(
                    f"Node {node_id} transitioned from indirect to direct "
                    f"(hop_count={hop_count}, snr={snr}, rssi={rssi})"
                )
            
            # Log node coming back online
            if was_offline:
                self.logger.info(f"Node {node_id} came back online")
        else:
            # Create new node state
            is_direct_final = is_direct or self._is_direct_from_signals(hop_count, snr, rssi)
            self._nodes[node_id] = NodeState(
                node_id=node_id,
                is_direct=is_direct_final,
                last_seen=now,
                snr=snr,
                rssi=rssi,
                role=role
            )
            self.logger.debug(
                f"New node discovered: {node_id} (direct={is_direct_final}, "
                f"hop_count={hop_count}, snr={snr}, rssi={rssi})"
            )
    
    def _is_direct_from_signals(
        self,
        hop_count: Optional[int],
        snr: Optional[float],
        rssi: Optional[float]
    ) -> bool:
        """
        Determine if a node is direct based on hop count and signal strength.
        
        A node is considered direct if:
        - hop_count is 0 or 1
        
        Note: SNR/RSSI alone don't determine direct status, as these can be
        reported for indirect nodes as well. Only hop_count is reliable.
        
        Args:
            hop_count: Number of hops to reach the node
            snr: Signal-to-noise ratio
            rssi: Received signal strength indicator
            
        Returns:
            True if the node appears to be directly heard
        """
        # Check hop count - this is the most reliable indicator
        if hop_count is not None and hop_count <= 1:
            return True
        
        return False
    
    def get_node_state(self, node_id: str) -> Optional[NodeState]:
        """
        Get the state of a specific node.
        
        Args:
            node_id: The node identifier
            
        Returns:
            NodeState if the node exists, None otherwise
        """
        return self._nodes.get(node_id)
    
    def is_direct_node(self, node_id: str) -> bool:
        """
        Check if a node is directly heard.
        
        Args:
            node_id: The node identifier
            
        Returns:
            True if the node is direct, False otherwise
        """
        node = self._nodes.get(node_id)
        return node.is_direct if node else False
    
    def should_trace_node(self, node_id: str) -> bool:
        """
        Determine if a node should be traced based on filtering rules.
        
        Filtering rules applied in order:
        1. Skip if node doesn't exist
        2. Skip if direct node and skip_direct_nodes is enabled
        3. Apply whitelist (if configured)
        4. Apply blacklist
        5. Apply role filtering
        6. Apply SNR threshold
        
        Args:
            node_id: The node identifier
            
        Returns:
            True if the node should be traced, False otherwise
        """
        node = self._nodes.get(node_id)
        if not node:
            self.logger.debug(f"Node {node_id} not found, cannot trace")
            return False
        
        # Skip direct nodes if configured
        if self._skip_direct_nodes and node.is_direct:
            self.logger.debug(f"Skipping direct node {node_id}")
            return False
        
        # Apply whitelist (if configured, only trace whitelisted nodes)
        if self._whitelist and node_id not in self._whitelist:
            self.logger.debug(f"Node {node_id} not in whitelist, skipping")
            return False
        
        # Apply blacklist
        if node_id in self._blacklist:
            self.logger.debug(f"Node {node_id} is blacklisted, skipping")
            return False
        
        # Apply role filtering
        if node.role and node.role in self._exclude_roles:
            self.logger.debug(f"Node {node_id} has excluded role {node.role}, skipping")
            return False
        
        # Apply SNR threshold
        if self._min_snr_threshold is not None:
            if node.snr is None or node.snr < self._min_snr_threshold:
                self.logger.debug(
                    f"Node {node_id} SNR {node.snr} below threshold "
                    f"{self._min_snr_threshold}, skipping"
                )
                return False
        
        return True
    
    def get_nodes_needing_trace(self) -> List[str]:
        """
        Get a list of node IDs that need to be traced.
        
        Returns nodes that:
        - Pass all filtering rules
        - Are indirect nodes (if skip_direct_nodes is enabled)
        - Have never been traced OR need a recheck
        
        Returns:
            List of node IDs that need tracing
        """
        now = datetime.now()
        nodes_needing_trace = []
        
        for node_id, node in self._nodes.items():
            # Check if node should be traced (filtering)
            if not self.should_trace_node(node_id):
                continue
            
            # Check if node needs tracing
            if node.last_traced is None:
                # Never traced
                nodes_needing_trace.append(node_id)
            elif node.next_recheck and now >= node.next_recheck:
                # Recheck is due
                nodes_needing_trace.append(node_id)
        
        return nodes_needing_trace
    
    def mark_node_traced(
        self,
        node_id: str,
        success: bool,
        next_recheck: Optional[datetime] = None
    ) -> None:
        """
        Mark a node as traced and update its state.
        
        This method implements Property 9 (Recheck Scheduling After Success) and
        Property 10 (Recheck Timer Reset) by automatically scheduling the next
        recheck based on the configured recheck_interval_hours.
        
        Args:
            node_id: The node identifier
            success: Whether the traceroute was successful
            next_recheck: When to recheck this node (if None, calculated automatically)
            
        Requirements: 5.1, 5.4
        """
        node = self._nodes.get(node_id)
        if not node:
            self.logger.warning(f"Cannot mark unknown node {node_id} as traced")
            return
        
        now = datetime.now()
        node.last_traced = now
        node.last_trace_success = success
        node.trace_count += 1
        
        if success:
            node.failure_count = 0  # Reset failure count on success
            
            # Property 9 & 10: Schedule next recheck after successful trace
            # If next_recheck is provided, use it; otherwise calculate it
            if next_recheck is not None:
                node.next_recheck = next_recheck
            elif self.config.get('recheck_enabled', True):
                # Calculate next recheck time based on recheck_interval_hours
                recheck_interval_hours = self.config.get('recheck_interval_hours', 6)
                if recheck_interval_hours > 0:
                    node.next_recheck = now + timedelta(hours=recheck_interval_hours)
                    self.logger.debug(
                        f"Scheduled recheck for {node_id} at {node.next_recheck}"
                    )
            
            self.logger.debug(
                f"Node {node_id} traced successfully (total traces: {node.trace_count})"
            )
        else:
            node.failure_count += 1
            self.logger.debug(
                f"Node {node_id} trace failed (failures: {node.failure_count})"
            )
    
    def mark_node_offline(self, node_id: str) -> None:
        """
        Mark a node as offline.
        
        Args:
            node_id: The node identifier
        """
        node = self._nodes.get(node_id)
        if node:
            node.was_offline = True
            self.logger.debug(f"Node {node_id} marked as offline")
    
    def get_all_nodes(self) -> Dict[str, NodeState]:
        """
        Get all tracked nodes.
        
        Returns:
            Dictionary of node_id -> NodeState
        """
        return self._nodes.copy()
    
    def get_direct_nodes(self) -> List[str]:
        """
        Get all direct nodes.
        
        Returns:
            List of node IDs that are direct
        """
        return [node_id for node_id, node in self._nodes.items() if node.is_direct]
    
    def get_indirect_nodes(self) -> List[str]:
        """
        Get all indirect nodes.
        
        Returns:
            List of node IDs that are indirect
        """
        return [node_id for node_id, node in self._nodes.items() if not node.is_direct]
    
    def get_nodes_back_online(self) -> List[str]:
        """
        Get nodes that were offline and came back online.
        
        Returns:
            List of node IDs that came back online
        """
        return [
            node_id for node_id, node in self._nodes.items()
            if node.was_offline
        ]
    
    def load_state(self, nodes: Dict[str, NodeState]) -> None:
        """
        Load node state from persisted data.
        
        Args:
            nodes: Dictionary of node_id -> NodeState
        """
        self._nodes = nodes.copy()
        self.logger.info(f"Loaded state for {len(self._nodes)} nodes")
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about tracked nodes.
        
        Returns:
            Dictionary with statistics
        """
        total_nodes = len(self._nodes)
        direct_nodes = len(self.get_direct_nodes())
        indirect_nodes = len(self.get_indirect_nodes())
        traced_nodes = sum(1 for node in self._nodes.values() if node.last_traced)
        
        return {
            'total_nodes': total_nodes,
            'direct_nodes': direct_nodes,
            'indirect_nodes': indirect_nodes,
            'traced_nodes': traced_nodes,
            'untraced_nodes': total_nodes - traced_nodes
        }
