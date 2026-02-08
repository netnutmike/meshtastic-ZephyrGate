"""
Property-Based Tests for Node Filtering

Tests Property 17: Blacklist Filtering
Tests Property 18: Whitelist Filtering
Tests Property 19: Blacklist and Whitelist Precedence
Tests Property 20: Role Filtering
Tests Property 21: SNR Threshold Filtering
Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.node_state_tracker import NodeState, NodeStateTracker


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    # Node IDs are in format !xxxxxxxx where x is hex digit
    hex_part = ''.join(draw(st.lists(
        st.sampled_from('0123456789abcdef'),
        min_size=8,
        max_size=8
    )))
    return f'!{hex_part}'


@composite
def valid_role(draw):
    """Generate valid Meshtastic node roles"""
    return draw(st.sampled_from([
        'CLIENT', 'CLIENT_MUTE', 'ROUTER', 'ROUTER_CLIENT', 'REPEATER',
        'TRACKER', 'SENSOR', 'TAK', 'CLIENT_HIDDEN', 'LOST_AND_FOUND', 'TAK_TRACKER'
    ]))



@composite
def indirect_node_with_properties(draw):
    """Generate an indirect node with various properties"""
    node_id = draw(valid_node_id())
    hop_count = draw(st.integers(min_value=2, max_value=10))
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    role = draw(st.one_of(st.none(), valid_role()))
    
    return {
        'node_id': node_id,
        'hop_count': hop_count,
        'snr': snr,
        'rssi': rssi,
        'role': role,
        'is_direct': False
    }


@composite
def node_list_with_unique_ids(draw):
    """Generate a list of nodes with unique IDs"""
    nodes = draw(st.lists(indirect_node_with_properties(), min_size=1, max_size=30))
    
    # Ensure unique node IDs
    seen_ids = set()
    unique_nodes = []
    for node in nodes:
        if node['node_id'] not in seen_ids:
            seen_ids.add(node['node_id'])
            unique_nodes.append(node)
    
    assume(len(unique_nodes) > 0)  # Ensure we have at least one unique node
    return unique_nodes


# Property Tests

class TestBlacklistFilteringProperty:
    """
    Feature: network-traceroute-mapper, Property 17: Blacklist Filtering
    
    Tests that nodes on the configured blacklist are not queued for traceroute.
    
    **Validates: Requirements 9.1**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        blacklist_indices=st.lists(st.integers(min_value=0, max_value=29), max_size=10, unique=True)
    )
    def test_blacklisted_nodes_not_traced(self, nodes, blacklist_indices):
        """
        Property: For any node on the configured blacklist, the Traceroute_Mapper
        should not queue a traceroute request for that node.
        
        **Validates: Requirements 9.1**
        """
        # Select nodes to blacklist based on indices
        blacklist = []
        for idx in blacklist_indices:
            if idx < len(nodes):
                blacklist.append(nodes[idx]['node_id'])
        
        # Configure tracker with blacklist
        config = {
            'blacklist': blacklist,
            'skip_direct_nodes': False  # Don't skip direct nodes for this test
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            
            if node['node_id'] in blacklist:
                assert not should_trace, (
                    f"Blacklisted node {node['node_id']} should not be traced"
                )
            else:
                # Non-blacklisted nodes should be traced (assuming no other filters)
                assert should_trace, (
                    f"Non-blacklisted node {node['node_id']} should be traced"
                )

    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        blacklist=st.lists(valid_node_id(), min_size=1, max_size=20, unique=True)
    )
    def test_any_blacklisted_node_excluded(self, node_id, blacklist):
        """
        Property: For any node ID in the blacklist, should_trace_node should
        return False.
        
        **Validates: Requirements 9.1**
        """
        # Add the node_id to blacklist
        blacklist_with_node = blacklist + [node_id]
        
        config = {
            'blacklist': blacklist_with_node,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0
        )
        
        # Verify node is not traced
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} in blacklist should not be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids()
    )
    def test_empty_blacklist_traces_all_nodes(self, nodes):
        """
        Property: For any set of nodes with an empty blacklist, all nodes
        should be eligible for tracing (subject to other filters).
        
        **Validates: Requirements 9.1**
        """
        config = {
            'blacklist': [],
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # All nodes should be traceable
        for node in nodes:
            assert tracker.should_trace_node(node['node_id']), (
                f"Node {node['node_id']} should be traced with empty blacklist"
            )


class TestWhitelistFilteringProperty:
    """
    Feature: network-traceroute-mapper, Property 18: Whitelist Filtering
    
    Tests that when a whitelist is configured, only nodes on the whitelist
    are queued for traceroute.
    
    **Validates: Requirements 9.2**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        whitelist_indices=st.lists(st.integers(min_value=0, max_value=29), min_size=1, max_size=10, unique=True)
    )
    def test_only_whitelisted_nodes_traced(self, nodes, whitelist_indices):
        """
        Property: For any node when a whitelist is configured, the Traceroute_Mapper
        should only queue traceroute requests for nodes on the whitelist.
        
        **Validates: Requirements 9.2**
        """
        # Select nodes to whitelist based on indices
        whitelist = []
        for idx in whitelist_indices:
            if idx < len(nodes):
                whitelist.append(nodes[idx]['node_id'])
        
        assume(len(whitelist) > 0)  # Ensure we have at least one whitelisted node
        
        # Configure tracker with whitelist
        config = {
            'whitelist': whitelist,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            
            if node['node_id'] in whitelist:
                assert should_trace, (
                    f"Whitelisted node {node['node_id']} should be traced"
                )
            else:
                assert not should_trace, (
                    f"Non-whitelisted node {node['node_id']} should not be traced"
                )

    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        whitelist=st.lists(valid_node_id(), min_size=1, max_size=20, unique=True)
    )
    def test_node_not_in_whitelist_excluded(self, node_id, whitelist):
        """
        Property: For any node ID not in the whitelist (when whitelist is configured),
        should_trace_node should return False.
        
        **Validates: Requirements 9.2**
        """
        # Ensure node_id is NOT in whitelist
        assume(node_id not in whitelist)
        
        config = {
            'whitelist': whitelist,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0
        )
        
        # Verify node is not traced
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} not in whitelist should not be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        other_nodes=st.lists(valid_node_id(), max_size=10, unique=True)
    )
    def test_node_in_whitelist_included(self, node_id, other_nodes):
        """
        Property: For any node ID in the whitelist, should_trace_node should
        return True (assuming no other filters exclude it).
        
        **Validates: Requirements 9.2**
        """
        # Ensure node_id is not in other_nodes
        other_nodes = [n for n in other_nodes if n != node_id]
        
        # Create whitelist with node_id
        whitelist = [node_id] + other_nodes
        
        config = {
            'whitelist': whitelist,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0
        )
        
        # Verify node is traced
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} in whitelist should be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids()
    )
    def test_empty_whitelist_traces_all_nodes(self, nodes):
        """
        Property: For any set of nodes with an empty whitelist, all nodes
        should be eligible for tracing (no whitelist filtering applied).
        
        **Validates: Requirements 9.2**
        """
        config = {
            'whitelist': [],
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # All nodes should be traceable
        for node in nodes:
            assert tracker.should_trace_node(node['node_id']), (
                f"Node {node['node_id']} should be traced with empty whitelist"
            )


class TestBlacklistWhitelistPrecedenceProperty:
    """
    Feature: network-traceroute-mapper, Property 19: Blacklist and Whitelist Precedence
    
    Tests that when both blacklist and whitelist are configured, a node should
    be traced if and only if it is on the whitelist AND not on the blacklist.
    
    **Validates: Requirements 9.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        whitelist_indices=st.lists(st.integers(min_value=0, max_value=29), min_size=1, max_size=15, unique=True),
        blacklist_indices=st.lists(st.integers(min_value=0, max_value=29), min_size=1, max_size=10, unique=True)
    )
    def test_blacklist_whitelist_precedence(self, nodes, whitelist_indices, blacklist_indices):
        """
        Property: For any configuration with both blacklist and whitelist, a node
        should be traced if and only if it is on the whitelist AND not on the blacklist.
        
        **Validates: Requirements 9.3**
        """
        # Select nodes for whitelist and blacklist
        whitelist = []
        blacklist = []
        
        for idx in whitelist_indices:
            if idx < len(nodes):
                whitelist.append(nodes[idx]['node_id'])
        
        for idx in blacklist_indices:
            if idx < len(nodes):
                blacklist.append(nodes[idx]['node_id'])
        
        assume(len(whitelist) > 0)  # Ensure we have at least one whitelisted node
        
        # Configure tracker with both whitelist and blacklist
        config = {
            'whitelist': whitelist,
            'blacklist': blacklist,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            in_whitelist = node['node_id'] in whitelist
            in_blacklist = node['node_id'] in blacklist
            
            # Node should be traced if and only if it's in whitelist AND not in blacklist
            expected_trace = in_whitelist and not in_blacklist
            
            assert should_trace == expected_trace, (
                f"Node {node['node_id']} precedence error: "
                f"in_whitelist={in_whitelist}, in_blacklist={in_blacklist}, "
                f"should_trace={should_trace}, expected={expected_trace}"
            )

    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        whitelist=st.lists(valid_node_id(), min_size=1, max_size=10, unique=True),
        blacklist=st.lists(valid_node_id(), min_size=1, max_size=10, unique=True)
    )
    def test_node_in_both_lists_excluded(self, node_id, whitelist, blacklist):
        """
        Property: For any node that is in both whitelist and blacklist,
        the blacklist should take precedence and the node should not be traced.
        
        **Validates: Requirements 9.3**
        """
        # Add node_id to both lists
        whitelist_with_node = whitelist + [node_id]
        blacklist_with_node = blacklist + [node_id]
        
        config = {
            'whitelist': whitelist_with_node,
            'blacklist': blacklist_with_node,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0
        )
        
        # Verify node is not traced (blacklist takes precedence)
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} in both whitelist and blacklist should not be traced "
            f"(blacklist takes precedence)"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        whitelist=st.lists(valid_node_id(), min_size=1, max_size=10, unique=True),
        blacklist=st.lists(valid_node_id(), min_size=1, max_size=10, unique=True)
    )
    def test_node_in_whitelist_only_included(self, node_id, whitelist, blacklist):
        """
        Property: For any node that is in whitelist but not in blacklist,
        the node should be traced.
        
        **Validates: Requirements 9.3**
        """
        # Ensure node_id is not in blacklist
        assume(node_id not in blacklist)
        
        # Add node_id to whitelist only
        whitelist_with_node = whitelist + [node_id]
        
        config = {
            'whitelist': whitelist_with_node,
            'blacklist': blacklist,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0
        )
        
        # Verify node is traced
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} in whitelist but not blacklist should be traced"
        )


class TestRoleFilteringProperty:
    """
    Feature: network-traceroute-mapper, Property 20: Role Filtering
    
    Tests that nodes with roles in the configured exclude_roles list are not
    queued for traceroute.
    
    **Validates: Requirements 9.4**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        exclude_roles=st.lists(valid_role(), min_size=1, max_size=5, unique=True)
    )
    def test_excluded_roles_not_traced(self, nodes, exclude_roles):
        """
        Property: For any node with a role in the configured exclude_roles list,
        the Traceroute_Mapper should not queue a traceroute request for that node.
        
        **Validates: Requirements 9.4**
        """
        # Configure tracker with excluded roles
        config = {
            'exclude_roles': exclude_roles,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            
            if node['role'] and node['role'] in exclude_roles:
                assert not should_trace, (
                    f"Node {node['node_id']} with excluded role {node['role']} "
                    f"should not be traced"
                )
            else:
                # Nodes without excluded roles should be traced
                assert should_trace, (
                    f"Node {node['node_id']} with role {node['role']} "
                    f"(not in exclude_roles) should be traced"
                )

    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        role=valid_role(),
        exclude_roles=st.lists(valid_role(), min_size=1, max_size=5, unique=True)
    )
    def test_node_with_excluded_role_not_traced(self, node_id, role, exclude_roles):
        """
        Property: For any node with a role in exclude_roles, should_trace_node
        should return False.
        
        **Validates: Requirements 9.4**
        """
        # Add the role to exclude_roles
        exclude_roles_with_role = exclude_roles + [role]
        
        config = {
            'exclude_roles': exclude_roles_with_role,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with the excluded role
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0,
            role=role
        )
        
        # Verify node is not traced
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} with excluded role {role} should not be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        role=valid_role(),
        exclude_roles=st.lists(valid_role(), max_size=5, unique=True)
    )
    def test_node_with_allowed_role_traced(self, node_id, role, exclude_roles):
        """
        Property: For any node with a role not in exclude_roles, should_trace_node
        should return True (assuming no other filters exclude it).
        
        **Validates: Requirements 9.4**
        """
        # Ensure role is not in exclude_roles
        assume(role not in exclude_roles)
        
        config = {
            'exclude_roles': exclude_roles,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with an allowed role
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0,
            role=role
        )
        
        # Verify node is traced
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} with allowed role {role} should be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        exclude_roles=st.lists(valid_role(), min_size=1, max_size=5, unique=True)
    )
    def test_node_with_no_role_traced(self, node_id, exclude_roles):
        """
        Property: For any node with no role (role=None), should_trace_node
        should return True even if exclude_roles is configured.
        
        **Validates: Requirements 9.4**
        """
        config = {
            'exclude_roles': exclude_roles,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with no role
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=5.0,
            rssi=-85.0,
            role=None
        )
        
        # Verify node is traced (no role means not excluded)
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} with no role should be traced even with exclude_roles configured"
        )


class TestSNRThresholdFilteringProperty:
    """
    Feature: network-traceroute-mapper, Property 21: SNR Threshold Filtering
    
    Tests that when a min_snr_threshold is configured, only nodes with SNR
    greater than or equal to the threshold are queued for traceroute.
    
    **Validates: Requirements 9.5**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        min_snr_threshold=st.floats(min_value=-20, max_value=10, allow_nan=False, allow_infinity=False)
    )
    def test_snr_threshold_filtering(self, nodes, min_snr_threshold):
        """
        Property: For any node when a min_snr_threshold is configured, the
        Traceroute_Mapper should only queue traceroute requests for nodes with
        SNR >= min_snr_threshold.
        
        **Validates: Requirements 9.5**
        """
        # Configure tracker with SNR threshold
        config = {
            'min_snr_threshold': min_snr_threshold,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            
            if node['snr'] is None:
                # Nodes with no SNR should not be traced when threshold is set
                assert not should_trace, (
                    f"Node {node['node_id']} with no SNR should not be traced "
                    f"when min_snr_threshold={min_snr_threshold}"
                )
            elif node['snr'] >= min_snr_threshold:
                # Nodes with SNR >= threshold should be traced
                assert should_trace, (
                    f"Node {node['node_id']} with SNR {node['snr']} >= threshold "
                    f"{min_snr_threshold} should be traced"
                )
            else:
                # Nodes with SNR < threshold should not be traced
                assert not should_trace, (
                    f"Node {node['node_id']} with SNR {node['snr']} < threshold "
                    f"{min_snr_threshold} should not be traced"
                )

    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        snr=st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False),
        min_snr_threshold=st.floats(min_value=-20, max_value=10, allow_nan=False, allow_infinity=False)
    )
    def test_node_above_snr_threshold_traced(self, node_id, snr, min_snr_threshold):
        """
        Property: For any node with SNR >= min_snr_threshold, should_trace_node
        should return True (assuming no other filters exclude it).
        
        **Validates: Requirements 9.5**
        """
        # Ensure SNR is above or equal to threshold
        assume(snr >= min_snr_threshold)
        
        config = {
            'min_snr_threshold': min_snr_threshold,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with SNR above threshold
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=snr,
            rssi=-85.0
        )
        
        # Verify node is traced
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} with SNR {snr} >= threshold {min_snr_threshold} "
            f"should be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        snr=st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False),
        min_snr_threshold=st.floats(min_value=-20, max_value=10, allow_nan=False, allow_infinity=False)
    )
    def test_node_below_snr_threshold_not_traced(self, node_id, snr, min_snr_threshold):
        """
        Property: For any node with SNR < min_snr_threshold, should_trace_node
        should return False.
        
        **Validates: Requirements 9.5**
        """
        # Ensure SNR is below threshold
        assume(snr < min_snr_threshold)
        
        config = {
            'min_snr_threshold': min_snr_threshold,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with SNR below threshold
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=snr,
            rssi=-85.0
        )
        
        # Verify node is not traced
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} with SNR {snr} < threshold {min_snr_threshold} "
            f"should not be traced"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        min_snr_threshold=st.floats(min_value=-20, max_value=10, allow_nan=False, allow_infinity=False)
    )
    def test_node_with_no_snr_not_traced_when_threshold_set(self, node_id, min_snr_threshold):
        """
        Property: For any node with no SNR value (SNR=None) when min_snr_threshold
        is configured, should_trace_node should return False.
        
        **Validates: Requirements 9.5**
        """
        config = {
            'min_snr_threshold': min_snr_threshold,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node with no SNR
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=None,
            rssi=-85.0
        )
        
        # Verify node is not traced
        assert not tracker.should_trace_node(node_id), (
            f"Node {node_id} with no SNR should not be traced when "
            f"min_snr_threshold={min_snr_threshold} is configured"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        snr=st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)
    )
    def test_node_traced_when_no_snr_threshold_configured(self, node_id, snr):
        """
        Property: For any node when min_snr_threshold is None (not configured),
        all nodes should be traced regardless of their SNR value.
        
        **Validates: Requirements 9.5**
        """
        config = {
            'min_snr_threshold': None,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update the node
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=3,
            snr=snr,
            rssi=-85.0
        )
        
        # Verify node is traced (no threshold means no SNR filtering)
        assert tracker.should_trace_node(node_id), (
            f"Node {node_id} with SNR {snr} should be traced when "
            f"min_snr_threshold is not configured"
        )


class TestCombinedFilteringProperty:
    """
    Feature: network-traceroute-mapper, Combined Filtering Tests
    
    Tests that all filtering rules work correctly when combined.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        nodes=node_list_with_unique_ids(),
        whitelist_indices=st.lists(st.integers(min_value=0, max_value=29), min_size=1, max_size=15, unique=True),
        blacklist_indices=st.lists(st.integers(min_value=0, max_value=29), max_size=5, unique=True),
        exclude_roles=st.lists(valid_role(), max_size=3, unique=True),
        min_snr_threshold=st.one_of(
            st.none(),
            st.floats(min_value=-15, max_value=5, allow_nan=False, allow_infinity=False)
        )
    )
    def test_all_filters_combined(self, nodes, whitelist_indices, blacklist_indices, 
                                   exclude_roles, min_snr_threshold):
        """
        Property: For any configuration with multiple filters (whitelist, blacklist,
        role filtering, SNR threshold), all filters should be applied correctly
        in the proper order.
        
        **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
        """
        # Select nodes for whitelist and blacklist
        whitelist = []
        blacklist = []
        
        for idx in whitelist_indices:
            if idx < len(nodes):
                whitelist.append(nodes[idx]['node_id'])
        
        for idx in blacklist_indices:
            if idx < len(nodes):
                blacklist.append(nodes[idx]['node_id'])
        
        assume(len(whitelist) > 0)
        
        # Configure tracker with all filters
        config = {
            'whitelist': whitelist,
            'blacklist': blacklist,
            'exclude_roles': exclude_roles,
            'min_snr_threshold': min_snr_threshold,
            'skip_direct_nodes': False
        }
        tracker = NodeStateTracker(config)
        
        # Update all nodes
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=node['is_direct'],
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check each node against all filters
        for node in nodes:
            should_trace = tracker.should_trace_node(node['node_id'])
            
            # Determine expected result based on all filters
            # 1. Must be in whitelist
            if node['node_id'] not in whitelist:
                assert not should_trace, (
                    f"Node {node['node_id']} not in whitelist should not be traced"
                )
                continue
            
            # 2. Must not be in blacklist
            if node['node_id'] in blacklist:
                assert not should_trace, (
                    f"Node {node['node_id']} in blacklist should not be traced"
                )
                continue
            
            # 3. Must not have excluded role
            if node['role'] and node['role'] in exclude_roles:
                assert not should_trace, (
                    f"Node {node['node_id']} with excluded role {node['role']} "
                    f"should not be traced"
                )
                continue
            
            # 4. Must meet SNR threshold (if configured)
            if min_snr_threshold is not None:
                if node['snr'] is None or node['snr'] < min_snr_threshold:
                    assert not should_trace, (
                        f"Node {node['node_id']} with SNR {node['snr']} below "
                        f"threshold {min_snr_threshold} should not be traced"
                    )
                    continue
            
            # If all filters pass, node should be traced
            assert should_trace, (
                f"Node {node['node_id']} passed all filters but was not traced: "
                f"in_whitelist=True, in_blacklist=False, role={node['role']}, "
                f"snr={node['snr']}, threshold={min_snr_threshold}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
