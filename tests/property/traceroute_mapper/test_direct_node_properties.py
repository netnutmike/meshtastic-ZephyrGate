"""
Property-Based Tests for Direct Node Detection

Tests Property 1: Direct Node Exclusion
Tests Property 3: Direct Node Classification
Validates: Requirements 2.1, 2.3

**Validates: Requirements 2.1, 2.3**
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
def node_with_hop_count(draw):
    """Generate a node with a specific hop count"""
    node_id = draw(valid_node_id())
    hop_count = draw(st.integers(min_value=0, max_value=10))
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    role = draw(st.one_of(st.none(), st.sampled_from(['CLIENT', 'ROUTER', 'REPEATER'])))
    
    return {
        'node_id': node_id,
        'hop_count': hop_count,
        'snr': snr,
        'rssi': rssi,
        'role': role
    }


@composite
def direct_node(draw):
    """Generate a node that should be classified as direct (hop_count <= 1)"""
    node_id = draw(valid_node_id())
    hop_count = draw(st.integers(min_value=0, max_value=1))
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    role = draw(st.one_of(st.none(), st.sampled_from(['CLIENT', 'ROUTER', 'REPEATER'])))
    
    return {
        'node_id': node_id,
        'hop_count': hop_count,
        'snr': snr,
        'rssi': rssi,
        'role': role,
        'is_direct': True  # Expected classification
    }


@composite
def indirect_node(draw):
    """Generate a node that should be classified as indirect (hop_count > 1)"""
    node_id = draw(valid_node_id())
    hop_count = draw(st.integers(min_value=2, max_value=10))
    snr = draw(st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)))
    rssi = draw(st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)))
    role = draw(st.one_of(st.none(), st.sampled_from(['CLIENT', 'ROUTER', 'REPEATER'])))
    
    return {
        'node_id': node_id,
        'hop_count': hop_count,
        'snr': snr,
        'rssi': rssi,
        'role': role,
        'is_direct': False  # Expected classification
    }


@composite
def mixed_node_list(draw):
    """Generate a list of mixed direct and indirect nodes"""
    direct_nodes = draw(st.lists(direct_node(), min_size=1, max_size=20))
    indirect_nodes = draw(st.lists(indirect_node(), min_size=1, max_size=20))
    
    # Ensure unique node IDs
    all_nodes = direct_nodes + indirect_nodes
    seen_ids = set()
    unique_nodes = []
    for node in all_nodes:
        if node['node_id'] not in seen_ids:
            seen_ids.add(node['node_id'])
            unique_nodes.append(node)
    
    return unique_nodes


# Property Tests

class TestDirectNodeExclusionProperty:
    """
    Feature: network-traceroute-mapper, Property 1: Direct Node Exclusion
    
    Tests that nodes classified as Direct_Node (hop_count <= 1) are not queued
    for traceroute when skip_direct_nodes is enabled.
    
    **Validates: Requirements 2.1, 2.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(nodes=mixed_node_list())
    def test_direct_nodes_not_traced_when_skip_enabled(self, nodes):
        """
        Property: For any node that is classified as a Direct_Node (appears in 
        neighbor list or has hop_count <= 1), the Traceroute_Mapper should not 
        queue a traceroute request for that node when skip_direct_nodes is enabled.
        
        **Validates: Requirements 2.1, 2.3**
        """
        # Configure tracker to skip direct nodes
        config = {'skip_direct_nodes': True}
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,  # Let the tracker determine based on hop_count
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        nodes_to_trace = []
        for node in nodes:
            if tracker.should_trace_node(node['node_id']):
                nodes_to_trace.append(node['node_id'])
        
        # Verify that no direct nodes are in the trace list
        for node in nodes:
            node_state = tracker.get_node_state(node['node_id'])
            if node_state and node_state.is_direct:
                assert node['node_id'] not in nodes_to_trace, (
                    f"Direct node {node['node_id']} (hop_count={node['hop_count']}) "
                    f"should not be queued for traceroute when skip_direct_nodes is enabled"
                )
    
    @settings(max_examples=20, deadline=None)
    @given(nodes=mixed_node_list())
    def test_direct_nodes_traced_when_skip_disabled(self, nodes):
        """
        Property: For any node that is classified as a Direct_Node, the 
        Traceroute_Mapper should queue a traceroute request when 
        skip_direct_nodes is disabled.
        
        **Validates: Requirements 2.1**
        """
        # Configure tracker to NOT skip direct nodes
        config = {'skip_direct_nodes': False}
        tracker = NodeStateTracker(config)
        
        # Update all nodes in the tracker
        for node in nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,  # Let the tracker determine based on hop_count
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Check which nodes should be traced
        nodes_to_trace = []
        for node in nodes:
            if tracker.should_trace_node(node['node_id']):
                nodes_to_trace.append(node['node_id'])
        
        # Verify that direct nodes ARE in the trace list when skip is disabled
        for node in nodes:
            node_state = tracker.get_node_state(node['node_id'])
            if node_state and node_state.is_direct:
                assert node['node_id'] in nodes_to_trace, (
                    f"Direct node {node['node_id']} (hop_count={node['hop_count']}) "
                    f"should be queued for traceroute when skip_direct_nodes is disabled"
                )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        hop_count=st.integers(min_value=0, max_value=1),
        snr=st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)),
        rssi=st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False))
    )
    def test_direct_node_exclusion_with_hop_count(self, node_id, hop_count, snr, rssi):
        """
        Property: For any node with hop_count <= 1, the node should be classified
        as direct and excluded from tracing when skip_direct_nodes is enabled.
        
        **Validates: Requirements 2.1, 2.3**
        """
        config = {'skip_direct_nodes': True}
        tracker = NodeStateTracker(config)
        
        # Update node with hop_count <= 1
        tracker.update_node(
            node_id=node_id,
            is_direct=False,  # Let tracker determine from hop_count
            hop_count=hop_count,
            snr=snr,
            rssi=rssi
        )
        
        # Verify node is classified as direct
        assert tracker.is_direct_node(node_id), (
            f"Node {node_id} with hop_count={hop_count} should be classified as direct"
        )
        
        # Verify node should not be traced
        assert not tracker.should_trace_node(node_id), (
            f"Direct node {node_id} (hop_count={hop_count}) should not be traced "
            f"when skip_direct_nodes is enabled"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        hop_count=st.integers(min_value=2, max_value=10),
        snr=st.one_of(st.none(), st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)),
        rssi=st.one_of(st.none(), st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False))
    )
    def test_indirect_node_not_excluded(self, node_id, hop_count, snr, rssi):
        """
        Property: For any node with hop_count > 1, the node should be classified
        as indirect and NOT excluded from tracing when skip_direct_nodes is enabled.
        
        **Validates: Requirements 2.1, 2.3**
        """
        config = {'skip_direct_nodes': True}
        tracker = NodeStateTracker(config)
        
        # Update node with hop_count > 1
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=hop_count,
            snr=snr,
            rssi=rssi
        )
        
        # Verify node is classified as indirect
        assert not tracker.is_direct_node(node_id), (
            f"Node {node_id} with hop_count={hop_count} should be classified as indirect"
        )
        
        # Verify node should be traced
        assert tracker.should_trace_node(node_id), (
            f"Indirect node {node_id} (hop_count={hop_count}) should be traced "
            f"when skip_direct_nodes is enabled"
        )


class TestDirectNodeClassificationProperty:
    """
    Feature: network-traceroute-mapper, Property 3: Direct Node Classification
    
    Tests that nodes are correctly classified as direct or indirect based on
    hop count and signal strength indicators.
    
    **Validates: Requirements 2.1, 2.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(node=node_with_hop_count())
    def test_node_classification_based_on_hop_count(self, node):
        """
        Property: For any node, the classification as direct or indirect should
        be determined by hop_count: hop_count <= 1 means direct, hop_count > 1
        means indirect.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Update node
        tracker.update_node(
            node_id=node['node_id'],
            is_direct=False,  # Let tracker determine from hop_count
            hop_count=node['hop_count'],
            snr=node['snr'],
            rssi=node['rssi'],
            role=node['role']
        )
        
        # Check classification
        is_direct = tracker.is_direct_node(node['node_id'])
        expected_direct = node['hop_count'] <= 1
        
        assert is_direct == expected_direct, (
            f"Node {node['node_id']} with hop_count={node['hop_count']} "
            f"should be classified as {'direct' if expected_direct else 'indirect'}, "
            f"but was classified as {'direct' if is_direct else 'indirect'}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        hop_count=st.integers(min_value=0, max_value=1)
    )
    def test_hop_count_zero_or_one_is_direct(self, node_id, hop_count):
        """
        Property: For any node with hop_count of 0 or 1, the node should be
        classified as direct regardless of SNR/RSSI values.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Update node with hop_count 0 or 1
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=hop_count,
            snr=None,
            rssi=None
        )
        
        # Verify classification
        assert tracker.is_direct_node(node_id), (
            f"Node {node_id} with hop_count={hop_count} should be classified as direct"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        hop_count=st.integers(min_value=2, max_value=10),
        snr=st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False),
        rssi=st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)
    )
    def test_hop_count_greater_than_one_is_indirect(self, node_id, hop_count, snr, rssi):
        """
        Property: For any node with hop_count > 1, the node should be classified
        as indirect even with strong SNR/RSSI values.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Update node with hop_count > 1 but strong signals
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=hop_count,
            snr=snr,
            rssi=rssi
        )
        
        # Verify classification
        assert not tracker.is_direct_node(node_id), (
            f"Node {node_id} with hop_count={hop_count} should be classified as indirect "
            f"even with SNR={snr} and RSSI={rssi}"
        )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        is_direct_explicit=st.booleans()
    )
    def test_explicit_direct_flag_overrides_hop_count(self, node_id, is_direct_explicit):
        """
        Property: For any node, if is_direct is explicitly set to True in update_node,
        it should override hop_count-based detection.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Update node with explicit is_direct flag
        tracker.update_node(
            node_id=node_id,
            is_direct=is_direct_explicit,
            hop_count=5,  # Would normally be indirect
            snr=None,
            rssi=None
        )
        
        # Verify classification matches explicit flag OR hop_count detection
        # (is_direct=True overrides, but is_direct=False can be overridden by hop_count)
        is_classified_direct = tracker.is_direct_node(node_id)
        
        if is_direct_explicit:
            # Explicit True should result in direct classification
            assert is_classified_direct, (
                f"Node {node_id} with explicit is_direct=True should be classified as direct"
            )
        else:
            # Explicit False with hop_count=5 should be indirect
            assert not is_classified_direct, (
                f"Node {node_id} with is_direct=False and hop_count=5 should be classified as indirect"
            )
    
    @settings(max_examples=20, deadline=None)
    @given(nodes=st.lists(node_with_hop_count(), min_size=10, max_size=50))
    def test_classification_consistency_across_updates(self, nodes):
        """
        Property: For any sequence of node updates, the classification should
        remain consistent based on the most recent hop_count value.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Ensure unique node IDs
        seen_ids = set()
        unique_nodes = []
        for node in nodes:
            if node['node_id'] not in seen_ids:
                seen_ids.add(node['node_id'])
                unique_nodes.append(node)
        
        # Update all nodes
        for node in unique_nodes:
            tracker.update_node(
                node_id=node['node_id'],
                is_direct=False,
                hop_count=node['hop_count'],
                snr=node['snr'],
                rssi=node['rssi'],
                role=node['role']
            )
        
        # Verify each node's classification
        for node in unique_nodes:
            is_direct = tracker.is_direct_node(node['node_id'])
            expected_direct = node['hop_count'] <= 1
            
            assert is_direct == expected_direct, (
                f"Node {node['node_id']} classification inconsistent: "
                f"hop_count={node['hop_count']}, is_direct={is_direct}, "
                f"expected_direct={expected_direct}"
            )
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        initial_hop_count=st.integers(min_value=2, max_value=10),
        updated_hop_count=st.integers(min_value=0, max_value=1)
    )
    def test_node_reclassification_on_hop_count_change(self, node_id, initial_hop_count, updated_hop_count):
        """
        Property: For any node that changes from indirect (hop_count > 1) to
        direct (hop_count <= 1), the classification should update accordingly.
        
        **Validates: Requirements 2.3**
        """
        config = {}
        tracker = NodeStateTracker(config)
        
        # Initial update - indirect
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=initial_hop_count,
            snr=None,
            rssi=None
        )
        
        # Verify initial classification
        assert not tracker.is_direct_node(node_id), (
            f"Node {node_id} should initially be indirect with hop_count={initial_hop_count}"
        )
        
        # Update to direct
        tracker.update_node(
            node_id=node_id,
            is_direct=False,
            hop_count=updated_hop_count,
            snr=None,
            rssi=None
        )
        
        # Verify updated classification
        assert tracker.is_direct_node(node_id), (
            f"Node {node_id} should be reclassified as direct with hop_count={updated_hop_count}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
