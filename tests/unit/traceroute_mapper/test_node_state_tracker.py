"""
Unit tests for NodeStateTracker component
"""

import pytest
from datetime import datetime, timedelta
from plugins.traceroute_mapper.node_state_tracker import NodeState, NodeStateTracker


class TestNodeState:
    """Test NodeState dataclass"""
    
    def test_node_state_creation(self):
        """Test creating a NodeState instance"""
        now = datetime.now()
        node = NodeState(
            node_id="!a1b2c3d4",
            is_direct=False,
            last_seen=now,
            snr=-5.2,
            rssi=-95
        )
        
        assert node.node_id == "!a1b2c3d4"
        assert node.is_direct is False
        assert node.last_seen == now
        assert node.snr == -5.2
        assert node.rssi == -95
        assert node.last_traced is None
        assert node.trace_count == 0
        assert node.failure_count == 0
    
    def test_node_state_defaults(self):
        """Test NodeState default values"""
        now = datetime.now()
        node = NodeState(
            node_id="!test",
            is_direct=True,
            last_seen=now
        )
        
        assert node.last_traced is None
        assert node.next_recheck is None
        assert node.last_trace_success is False
        assert node.trace_count == 0
        assert node.failure_count == 0
        assert node.snr is None
        assert node.rssi is None
        assert node.was_offline is False
        assert node.role is None


class TestNodeStateTracker:
    """Test NodeStateTracker component"""
    
    def test_initialization(self):
        """Test NodeStateTracker initialization"""
        config = {
            'blacklist': ['!bad1', '!bad2'],
            'whitelist': ['!good1', '!good2'],
            'exclude_roles': ['CLIENT'],
            'min_snr_threshold': -10.0,
            'skip_direct_nodes': True
        }
        
        tracker = NodeStateTracker(config)
        
        assert tracker._blacklist == {'!bad1', '!bad2'}
        assert tracker._whitelist == {'!good1', '!good2'}
        assert tracker._exclude_roles == {'CLIENT'}
        assert tracker._min_snr_threshold == -10.0
        assert tracker._skip_direct_nodes is True
    
    def test_update_node_new(self):
        """Test updating a new node"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(
            node_id="!test1",
            is_direct=False,
            snr=-5.0,
            rssi=-90,
            role="ROUTER",
            hop_count=2  # Explicitly set hop_count > 1 to ensure indirect
        )
        
        node = tracker.get_node_state("!test1")
        assert node is not None
        assert node.node_id == "!test1"
        assert node.is_direct is False
        assert node.snr == -5.0
        assert node.rssi == -90
        assert node.role == "ROUTER"
    
    def test_update_node_existing(self):
        """Test updating an existing node"""
        tracker = NodeStateTracker({})
        
        # Create node
        tracker.update_node(node_id="!test1", is_direct=False, snr=-5.0)
        
        # Update node
        tracker.update_node(node_id="!test1", is_direct=False, snr=-3.0, rssi=-85)
        
        node = tracker.get_node_state("!test1")
        assert node.snr == -3.0
        assert node.rssi == -85
    
    def test_is_direct_from_hop_count(self):
        """Test direct node detection from hop count"""
        tracker = NodeStateTracker({})
        
        # Hop count 0 should be direct
        tracker.update_node(node_id="!test1", is_direct=False, hop_count=0)
        assert tracker.is_direct_node("!test1") is True
        
        # Hop count 1 should be direct
        tracker.update_node(node_id="!test2", is_direct=False, hop_count=1)
        assert tracker.is_direct_node("!test2") is True
        
        # Hop count 2 should not be direct (unless explicitly set)
        tracker.update_node(node_id="!test3", is_direct=False, hop_count=2)
        assert tracker.is_direct_node("!test3") is False
    
    def test_is_direct_from_signals(self):
        """Test direct node detection from signal strength"""
        tracker = NodeStateTracker({})
        
        # Node with hop_count 0 should be direct
        tracker.update_node(node_id="!test1", is_direct=False, hop_count=0, snr=-5.0)
        assert tracker.is_direct_node("!test1") is True
        
        # Node with hop_count 1 should be direct
        tracker.update_node(node_id="!test2", is_direct=False, hop_count=1, rssi=-85)
        assert tracker.is_direct_node("!test2") is True
        
        # Node with hop_count > 1 should not be direct (even with SNR/RSSI)
        tracker.update_node(node_id="!test3", is_direct=False, hop_count=2, snr=-5.0)
        assert tracker.is_direct_node("!test3") is False
    
    def test_direct_node_transition(self):
        """Test node transitioning from indirect to direct"""
        tracker = NodeStateTracker({})
        
        # Start as indirect
        tracker.update_node(node_id="!test1", is_direct=False)
        assert tracker.is_direct_node("!test1") is False
        
        # Transition to direct
        tracker.update_node(node_id="!test1", is_direct=True)
        assert tracker.is_direct_node("!test1") is True
    
    def test_should_trace_node_direct_skip(self):
        """Test skipping direct nodes when configured"""
        config = {'skip_direct_nodes': True}
        tracker = NodeStateTracker(config)
        
        # Direct node should not be traced
        tracker.update_node(node_id="!direct", is_direct=True)
        assert tracker.should_trace_node("!direct") is False
        
        # Indirect node should be traced
        tracker.update_node(node_id="!indirect", is_direct=False)
        assert tracker.should_trace_node("!indirect") is True
    
    def test_should_trace_node_direct_allow(self):
        """Test allowing direct nodes when configured"""
        config = {'skip_direct_nodes': False}
        tracker = NodeStateTracker(config)
        
        # Direct node should be traced
        tracker.update_node(node_id="!direct", is_direct=True)
        assert tracker.should_trace_node("!direct") is True
    
    def test_should_trace_node_blacklist(self):
        """Test blacklist filtering"""
        config = {'blacklist': ['!bad1', '!bad2']}
        tracker = NodeStateTracker(config)
        
        # Blacklisted node should not be traced
        tracker.update_node(node_id="!bad1", is_direct=False)
        assert tracker.should_trace_node("!bad1") is False
        
        # Non-blacklisted node should be traced
        tracker.update_node(node_id="!good1", is_direct=False)
        assert tracker.should_trace_node("!good1") is True
    
    def test_should_trace_node_whitelist(self):
        """Test whitelist filtering"""
        config = {'whitelist': ['!good1', '!good2']}
        tracker = NodeStateTracker(config)
        
        # Whitelisted node should be traced
        tracker.update_node(node_id="!good1", is_direct=False)
        assert tracker.should_trace_node("!good1") is True
        
        # Non-whitelisted node should not be traced
        tracker.update_node(node_id="!other", is_direct=False)
        assert tracker.should_trace_node("!other") is False
    
    def test_should_trace_node_whitelist_and_blacklist(self):
        """Test whitelist and blacklist precedence"""
        config = {
            'whitelist': ['!good1', '!good2', '!bad1'],
            'blacklist': ['!bad1']
        }
        tracker = NodeStateTracker(config)
        
        # Node on whitelist but also blacklisted should not be traced
        tracker.update_node(node_id="!bad1", is_direct=False)
        assert tracker.should_trace_node("!bad1") is False
        
        # Node on whitelist and not blacklisted should be traced
        tracker.update_node(node_id="!good1", is_direct=False)
        assert tracker.should_trace_node("!good1") is True
        
        # Node not on whitelist should not be traced
        tracker.update_node(node_id="!other", is_direct=False)
        assert tracker.should_trace_node("!other") is False
    
    def test_should_trace_node_role_filtering(self):
        """Test role-based filtering"""
        config = {'exclude_roles': ['CLIENT', 'REPEATER']}
        tracker = NodeStateTracker(config)
        
        # Node with excluded role should not be traced
        tracker.update_node(node_id="!client", is_direct=False, role="CLIENT")
        assert tracker.should_trace_node("!client") is False
        
        # Node with allowed role should be traced
        tracker.update_node(node_id="!router", is_direct=False, role="ROUTER")
        assert tracker.should_trace_node("!router") is True
        
        # Node with no role should be traced
        tracker.update_node(node_id="!unknown", is_direct=False)
        assert tracker.should_trace_node("!unknown") is True
    
    def test_should_trace_node_snr_threshold(self):
        """Test SNR threshold filtering"""
        config = {'min_snr_threshold': -10.0, 'skip_direct_nodes': False}
        tracker = NodeStateTracker(config)
        
        # Node with SNR above threshold should be traced
        tracker.update_node(node_id="!good", is_direct=False, hop_count=2, snr=-5.0)
        assert tracker.should_trace_node("!good") is True
        
        # Node with SNR below threshold should not be traced
        tracker.update_node(node_id="!bad", is_direct=False, hop_count=2, snr=-15.0)
        assert tracker.should_trace_node("!bad") is False
        
        # Node with no SNR should not be traced
        tracker.update_node(node_id="!unknown", is_direct=False, hop_count=2)
        assert tracker.should_trace_node("!unknown") is False
    
    def test_get_nodes_needing_trace(self):
        """Test getting nodes that need tracing"""
        tracker = NodeStateTracker({})
        
        # Add nodes
        tracker.update_node(node_id="!never_traced", is_direct=False)
        tracker.update_node(node_id="!traced", is_direct=False)
        tracker.update_node(node_id="!direct", is_direct=True)
        
        # Mark one as traced
        tracker.mark_node_traced("!traced", success=True)
        
        # Get nodes needing trace
        nodes = tracker.get_nodes_needing_trace()
        
        # Only never_traced should be in the list (direct is skipped by default)
        assert "!never_traced" in nodes
        assert "!traced" not in nodes
        assert "!direct" not in nodes
    
    def test_get_nodes_needing_trace_with_recheck(self):
        """Test getting nodes that need recheck"""
        tracker = NodeStateTracker({})
        
        # Add node and mark as traced with recheck in the past
        tracker.update_node(node_id="!recheck", is_direct=False)
        past_time = datetime.now() - timedelta(hours=1)
        tracker.mark_node_traced("!recheck", success=True, next_recheck=past_time)
        
        # Get nodes needing trace
        nodes = tracker.get_nodes_needing_trace()
        
        # Node should need recheck
        assert "!recheck" in nodes
    
    def test_mark_node_traced_success(self):
        """Test marking node as successfully traced"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!test", is_direct=False)
        
        next_recheck = datetime.now() + timedelta(hours=6)
        tracker.mark_node_traced("!test", success=True, next_recheck=next_recheck)
        
        node = tracker.get_node_state("!test")
        assert node.last_traced is not None
        assert node.last_trace_success is True
        assert node.trace_count == 1
        assert node.failure_count == 0
        assert node.next_recheck == next_recheck
    
    def test_mark_node_traced_failure(self):
        """Test marking node as failed trace"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!test", is_direct=False)
        
        tracker.mark_node_traced("!test", success=False)
        
        node = tracker.get_node_state("!test")
        assert node.last_traced is not None
        assert node.last_trace_success is False
        assert node.trace_count == 1
        assert node.failure_count == 1
    
    def test_mark_node_traced_multiple(self):
        """Test marking node as traced multiple times"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!test", is_direct=False)
        
        # First trace - success
        tracker.mark_node_traced("!test", success=True)
        node = tracker.get_node_state("!test")
        assert node.trace_count == 1
        assert node.failure_count == 0
        
        # Second trace - failure
        tracker.mark_node_traced("!test", success=False)
        node = tracker.get_node_state("!test")
        assert node.trace_count == 2
        assert node.failure_count == 1
        
        # Third trace - success (should reset failure count)
        tracker.mark_node_traced("!test", success=True)
        node = tracker.get_node_state("!test")
        assert node.trace_count == 3
        assert node.failure_count == 0
    
    def test_mark_node_offline(self):
        """Test marking node as offline"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!test", is_direct=False)
        tracker.mark_node_offline("!test")
        
        node = tracker.get_node_state("!test")
        assert node.was_offline is True
    
    def test_node_back_online(self):
        """Test detecting node coming back online"""
        tracker = NodeStateTracker({})
        
        # Create node and mark offline
        tracker.update_node(node_id="!test", is_direct=False)
        tracker.mark_node_offline("!test")
        
        # Update node (simulating it coming back online)
        tracker.update_node(node_id="!test", is_direct=False)
        
        node = tracker.get_node_state("!test")
        assert node.was_offline is False
    
    def test_get_all_nodes(self):
        """Test getting all nodes"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!test1", is_direct=False)
        tracker.update_node(node_id="!test2", is_direct=True)
        tracker.update_node(node_id="!test3", is_direct=False)
        
        nodes = tracker.get_all_nodes()
        assert len(nodes) == 3
        assert "!test1" in nodes
        assert "!test2" in nodes
        assert "!test3" in nodes
    
    def test_get_direct_nodes(self):
        """Test getting direct nodes"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!direct1", is_direct=True)
        tracker.update_node(node_id="!indirect1", is_direct=False)
        tracker.update_node(node_id="!direct2", is_direct=True)
        
        direct_nodes = tracker.get_direct_nodes()
        assert len(direct_nodes) == 2
        assert "!direct1" in direct_nodes
        assert "!direct2" in direct_nodes
        assert "!indirect1" not in direct_nodes
    
    def test_get_indirect_nodes(self):
        """Test getting indirect nodes"""
        tracker = NodeStateTracker({})
        
        tracker.update_node(node_id="!direct1", is_direct=True)
        tracker.update_node(node_id="!indirect1", is_direct=False)
        tracker.update_node(node_id="!indirect2", is_direct=False)
        
        indirect_nodes = tracker.get_indirect_nodes()
        assert len(indirect_nodes) == 2
        assert "!indirect1" in indirect_nodes
        assert "!indirect2" in indirect_nodes
        assert "!direct1" not in indirect_nodes
    
    def test_get_nodes_back_online(self):
        """Test getting nodes that came back online"""
        tracker = NodeStateTracker({})
        
        # Create nodes
        tracker.update_node(node_id="!online", is_direct=False)
        tracker.update_node(node_id="!offline", is_direct=False)
        
        # Mark one as offline
        tracker.mark_node_offline("!offline")
        
        nodes_back = tracker.get_nodes_back_online()
        assert len(nodes_back) == 1
        assert "!offline" in nodes_back
        assert "!online" not in nodes_back
    
    def test_load_state(self):
        """Test loading state from persisted data"""
        tracker = NodeStateTracker({})
        
        # Create some state
        now = datetime.now()
        nodes = {
            "!test1": NodeState(
                node_id="!test1",
                is_direct=False,
                last_seen=now,
                trace_count=5
            ),
            "!test2": NodeState(
                node_id="!test2",
                is_direct=True,
                last_seen=now,
                trace_count=2
            )
        }
        
        # Load state
        tracker.load_state(nodes)
        
        # Verify state was loaded
        assert len(tracker.get_all_nodes()) == 2
        node1 = tracker.get_node_state("!test1")
        assert node1.trace_count == 5
        node2 = tracker.get_node_state("!test2")
        assert node2.trace_count == 2
    
    def test_get_statistics(self):
        """Test getting statistics"""
        tracker = NodeStateTracker({})
        
        # Add nodes
        tracker.update_node(node_id="!direct1", is_direct=True)
        tracker.update_node(node_id="!indirect1", is_direct=False)
        tracker.update_node(node_id="!indirect2", is_direct=False)
        
        # Mark one as traced
        tracker.mark_node_traced("!indirect1", success=True)
        
        stats = tracker.get_statistics()
        assert stats['total_nodes'] == 3
        assert stats['direct_nodes'] == 1
        assert stats['indirect_nodes'] == 2
        assert stats['traced_nodes'] == 1
        assert stats['untraced_nodes'] == 2
