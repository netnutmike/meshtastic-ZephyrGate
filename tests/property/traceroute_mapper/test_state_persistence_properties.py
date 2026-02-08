"""
Property-Based Tests for State Persistence

Tests Property 16: State Persistence Round Trip
Tests Property 32: State Completeness
Validates: Requirements 8.5, 13.2, 13.3

**Validates: Requirements 8.5, 13.2, 13.3**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime, timedelta
import tempfile
import shutil
import asyncio

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.state_persistence import StatePersistence
from plugins.traceroute_mapper.node_state_tracker import NodeState


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
def datetime_in_range(draw):
    """Generate datetime within a reasonable range"""
    # Generate datetime within last 30 days
    days_ago = draw(st.integers(min_value=0, max_value=30))
    hours = draw(st.integers(min_value=0, max_value=23))
    minutes = draw(st.integers(min_value=0, max_value=59))
    seconds = draw(st.integers(min_value=0, max_value=59))
    
    base_time = datetime.now() - timedelta(days=days_ago)
    return base_time.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)


@composite
def node_state_strategy(draw):
    """Generate a random NodeState object with all fields"""
    node_id = draw(valid_node_id())
    is_direct = draw(st.booleans())
    last_seen = draw(datetime_in_range())
    
    # Optional datetime fields
    last_traced = draw(st.one_of(
        st.none(),
        datetime_in_range()
    ))
    next_recheck = draw(st.one_of(
        st.none(),
        datetime_in_range()
    ))
    
    # Boolean and integer fields
    last_trace_success = draw(st.booleans())
    trace_count = draw(st.integers(min_value=0, max_value=1000))
    failure_count = draw(st.integers(min_value=0, max_value=100))
    was_offline = draw(st.booleans())
    
    # Optional float fields
    snr = draw(st.one_of(
        st.none(),
        st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False)
    ))
    rssi = draw(st.one_of(
        st.none(),
        st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False)
    ))
    
    # Optional role field
    role = draw(st.one_of(st.none(), valid_role()))
    
    return NodeState(
        node_id=node_id,
        is_direct=is_direct,
        last_seen=last_seen,
        last_traced=last_traced,
        next_recheck=next_recheck,
        last_trace_success=last_trace_success,
        trace_count=trace_count,
        failure_count=failure_count,
        snr=snr,
        rssi=rssi,
        was_offline=was_offline,
        role=role
    )


@composite
def node_state_dict_strategy(draw):
    """Generate a dictionary of NodeState objects with unique node IDs"""
    num_nodes = draw(st.integers(min_value=0, max_value=50))
    
    node_states = {}
    for _ in range(num_nodes):
        node_state = draw(node_state_strategy())
        # Ensure unique node IDs
        if node_state.node_id not in node_states:
            node_states[node_state.node_id] = node_state
    
    return node_states


# Property Tests

class TestStatePersistenceRoundTripProperty:
    """
    Feature: network-traceroute-mapper, Property 16: State Persistence Round Trip
    
    Tests that saving node state to disk and then loading it back produces
    equivalent NodeState objects with all fields preserved.
    
    **Validates: Requirements 8.5, 13.2, 13.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(node_states=node_state_dict_strategy())
    def test_save_load_round_trip_preserves_all_fields(self, node_states):
        """
        Property 16: State Persistence Round Trip
        
        For any set of NodeState objects, saving to disk and then loading should
        produce equivalent NodeState objects with all fields preserved.
        
        **Validates: Requirements 8.5, 13.2, 13.3**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance with temp file
            state_file_path = str(Path(temp_dir) / f"state_{id(node_states)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save state
            save_result = asyncio.run(persistence.save_state(node_states))
            assert save_result is True, "Save operation should succeed"
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Verify same number of nodes
            assert len(loaded_states) == len(node_states), (
                f"Loaded {len(loaded_states)} nodes but expected {len(node_states)}"
            )
            
            # Verify all node IDs are present
            assert set(loaded_states.keys()) == set(node_states.keys()), (
                "Loaded node IDs don't match original node IDs"
            )
            
            # Verify all fields for each node
            for node_id, original_state in node_states.items():
                loaded_state = loaded_states[node_id]
                
                # Check all fields are preserved
                assert loaded_state.node_id == original_state.node_id, (
                    f"Node ID mismatch for {node_id}"
                )
                assert loaded_state.is_direct == original_state.is_direct, (
                    f"is_direct mismatch for {node_id}: "
                    f"loaded={loaded_state.is_direct}, original={original_state.is_direct}"
                )
                assert loaded_state.last_trace_success == original_state.last_trace_success, (
                    f"last_trace_success mismatch for {node_id}"
                )
                assert loaded_state.trace_count == original_state.trace_count, (
                    f"trace_count mismatch for {node_id}: "
                    f"loaded={loaded_state.trace_count}, original={original_state.trace_count}"
                )
                assert loaded_state.failure_count == original_state.failure_count, (
                    f"failure_count mismatch for {node_id}: "
                    f"loaded={loaded_state.failure_count}, original={original_state.failure_count}"
                )
                assert loaded_state.was_offline == original_state.was_offline, (
                    f"was_offline mismatch for {node_id}"
                )
                assert loaded_state.role == original_state.role, (
                    f"role mismatch for {node_id}: "
                    f"loaded={loaded_state.role}, original={original_state.role}"
                )
                
                # Check optional float fields (with tolerance for floating point)
                if original_state.snr is None:
                    assert loaded_state.snr is None, (
                        f"snr should be None for {node_id}"
                    )
                else:
                    assert loaded_state.snr is not None, (
                        f"snr should not be None for {node_id}"
                    )
                    assert abs(loaded_state.snr - original_state.snr) < 0.001, (
                        f"snr mismatch for {node_id}: "
                        f"loaded={loaded_state.snr}, original={original_state.snr}"
                    )
                
                if original_state.rssi is None:
                    assert loaded_state.rssi is None, (
                        f"rssi should be None for {node_id}"
                    )
                else:
                    assert loaded_state.rssi is not None, (
                        f"rssi should not be None for {node_id}"
                    )
                    assert abs(loaded_state.rssi - original_state.rssi) < 0.001, (
                        f"rssi mismatch for {node_id}: "
                        f"loaded={loaded_state.rssi}, original={original_state.rssi}"
                    )
                
                # Check datetime fields (with tolerance for serialization)
                assert isinstance(loaded_state.last_seen, datetime), (
                    f"last_seen should be datetime for {node_id}"
                )
                assert abs((loaded_state.last_seen - original_state.last_seen).total_seconds()) < 1, (
                    f"last_seen mismatch for {node_id}: "
                    f"loaded={loaded_state.last_seen}, original={original_state.last_seen}"
                )
                
                if original_state.last_traced is None:
                    assert loaded_state.last_traced is None, (
                        f"last_traced should be None for {node_id}"
                    )
                else:
                    assert loaded_state.last_traced is not None, (
                        f"last_traced should not be None for {node_id}"
                    )
                    assert abs((loaded_state.last_traced - original_state.last_traced).total_seconds()) < 1, (
                        f"last_traced mismatch for {node_id}"
                    )
                
                if original_state.next_recheck is None:
                    assert loaded_state.next_recheck is None, (
                        f"next_recheck should be None for {node_id}"
                    )
                else:
                    assert loaded_state.next_recheck is not None, (
                        f"next_recheck should not be None for {node_id}"
                    )
                    assert abs((loaded_state.next_recheck - original_state.next_recheck).total_seconds()) < 1, (
                        f"next_recheck mismatch for {node_id}"
                    )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    @settings(max_examples=20, deadline=None)
    @given(node_state=node_state_strategy())
    def test_single_node_round_trip(self, node_state):
        """
        Property 16: State Persistence Round Trip (Single Node)
        
        For any single NodeState object, saving and loading should preserve
        all fields exactly.
        
        **Validates: Requirements 8.5, 13.2, 13.3**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_single_{id(node_state)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save single node
            node_states = {node_state.node_id: node_state}
            save_result = asyncio.run(persistence.save_state(node_states))
            assert save_result is True
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Verify node was loaded
            assert len(loaded_states) == 1
            assert node_state.node_id in loaded_states
            
            loaded_state = loaded_states[node_state.node_id]
            
            # Verify all critical fields
            assert loaded_state.node_id == node_state.node_id
            assert loaded_state.is_direct == node_state.is_direct
            assert loaded_state.trace_count == node_state.trace_count
            assert loaded_state.failure_count == node_state.failure_count
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    @settings(max_examples=20, deadline=None)
    @given(node_states=node_state_dict_strategy())
    def test_empty_state_round_trip(self, node_states):
        """
        Property 16: State Persistence Round Trip (Empty State)
        
        Saving and loading empty state should work correctly.
        
        **Validates: Requirements 8.5, 13.2**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / "state_empty.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save empty state
            save_result = asyncio.run(persistence.save_state({}))
            assert save_result is True
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Verify empty state
            assert len(loaded_states) == 0
            assert loaded_states == {}
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    @settings(max_examples=20, deadline=None)
    @given(node_states=node_state_dict_strategy())
    def test_multiple_save_load_cycles(self, node_states):
        """
        Property 16: State Persistence Round Trip (Multiple Cycles)
        
        Multiple save/load cycles should preserve state correctly.
        
        **Validates: Requirements 8.5, 13.2, 13.3**
        """
        # Skip if no nodes
        assume(len(node_states) > 0)
        
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_multi_{id(node_states)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Perform multiple save/load cycles
            for cycle in range(3):
                # Save state
                save_result = asyncio.run(persistence.save_state(node_states))
                assert save_result is True, f"Save failed on cycle {cycle}"
                
                # Load state
                loaded_states = asyncio.run(persistence.load_state())
                
                # Verify state is preserved
                assert len(loaded_states) == len(node_states), (
                    f"Node count mismatch on cycle {cycle}"
                )
                
                # Verify all node IDs are present
                assert set(loaded_states.keys()) == set(node_states.keys()), (
                    f"Node IDs mismatch on cycle {cycle}"
                )
                
                # Update node_states for next cycle (use loaded state)
                node_states = loaded_states
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestStateCompletenessProperty:
    """
    Feature: network-traceroute-mapper, Property 32: State Completeness
    
    Tests that saved node state includes all required fields: node_id, is_direct,
    last_seen, last_traced, and direct/indirect status.
    
    **Validates: Requirements 13.3**
    """
    
    @settings(max_examples=20, deadline=None)
    @given(node_states=node_state_dict_strategy())
    def test_saved_state_includes_required_fields(self, node_states):
        """
        Property 32: State Completeness
        
        For any saved node state, the persisted data should include node_id,
        is_direct, last_seen, last_traced, and direct/indirect status for each node.
        
        **Validates: Requirements 13.3**
        """
        # Skip if no nodes
        assume(len(node_states) > 0)
        
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_complete_{id(node_states)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save state
            save_result = asyncio.run(persistence.save_state(node_states))
            assert save_result is True
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Verify all required fields are present for each node
            for node_id, original_state in node_states.items():
                assert node_id in loaded_states, (
                    f"Node {node_id} not found in loaded state"
                )
                
                loaded_state = loaded_states[node_id]
                
                # Verify required fields are present and not None
                assert loaded_state.node_id is not None, (
                    f"node_id is None for {node_id}"
                )
                assert loaded_state.node_id == node_id, (
                    f"node_id mismatch for {node_id}"
                )
                
                assert loaded_state.is_direct is not None, (
                    f"is_direct is None for {node_id}"
                )
                assert isinstance(loaded_state.is_direct, bool), (
                    f"is_direct is not a boolean for {node_id}"
                )
                
                assert loaded_state.last_seen is not None, (
                    f"last_seen is None for {node_id}"
                )
                assert isinstance(loaded_state.last_seen, datetime), (
                    f"last_seen is not a datetime for {node_id}"
                )
                
                # last_traced can be None (node never traced)
                if loaded_state.last_traced is not None:
                    assert isinstance(loaded_state.last_traced, datetime), (
                        f"last_traced is not a datetime for {node_id}"
                    )
                
                # Verify direct/indirect status is preserved
                assert loaded_state.is_direct == original_state.is_direct, (
                    f"Direct/indirect status not preserved for {node_id}: "
                    f"loaded={loaded_state.is_direct}, original={original_state.is_direct}"
                )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    @settings(max_examples=20, deadline=None)
    @given(node_state=node_state_strategy())
    def test_single_node_has_all_required_fields(self, node_state):
        """
        Property 32: State Completeness (Single Node)
        
        For any single node, all required fields should be present after
        save/load cycle.
        
        **Validates: Requirements 13.3**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_fields_{id(node_state)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save single node
            node_states = {node_state.node_id: node_state}
            save_result = asyncio.run(persistence.save_state(node_states))
            assert save_result is True
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Verify node was loaded with all required fields
            assert len(loaded_states) == 1
            loaded_state = loaded_states[node_state.node_id]
            
            # Check required fields
            assert loaded_state.node_id == node_state.node_id
            assert isinstance(loaded_state.is_direct, bool)
            assert isinstance(loaded_state.last_seen, datetime)
            
            # last_traced can be None but if present must be datetime
            if loaded_state.last_traced is not None:
                assert isinstance(loaded_state.last_traced, datetime)
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    @settings(max_examples=20, deadline=None)
    @given(
        node_states=node_state_dict_strategy(),
        direct_ratio=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_direct_indirect_status_preserved(self, node_states, direct_ratio):
        """
        Property 32: State Completeness (Direct/Indirect Status)
        
        For any mix of direct and indirect nodes, the direct/indirect status
        should be preserved after save/load.
        
        **Validates: Requirements 13.3**
        """
        # Skip if no nodes
        assume(len(node_states) > 0)
        
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Set some nodes as direct, others as indirect based on ratio
            node_list = list(node_states.values())
            num_direct = int(len(node_list) * direct_ratio)
            
            for i, node_state in enumerate(node_list):
                node_state.is_direct = (i < num_direct)
            
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_status_{id(node_states)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=10)
            
            # Save state
            save_result = asyncio.run(persistence.save_state(node_states))
            assert save_result is True
            
            # Load state
            loaded_states = asyncio.run(persistence.load_state())
            
            # Count direct and indirect nodes in original and loaded
            original_direct = sum(1 for n in node_states.values() if n.is_direct)
            original_indirect = sum(1 for n in node_states.values() if not n.is_direct)
            
            loaded_direct = sum(1 for n in loaded_states.values() if n.is_direct)
            loaded_indirect = sum(1 for n in loaded_states.values() if not n.is_direct)
            
            # Verify counts match
            assert loaded_direct == original_direct, (
                f"Direct node count mismatch: loaded={loaded_direct}, original={original_direct}"
            )
            assert loaded_indirect == original_indirect, (
                f"Indirect node count mismatch: loaded={loaded_indirect}, original={original_indirect}"
            )
            
            # Verify each node's status is preserved
            for node_id, original_state in node_states.items():
                loaded_state = loaded_states[node_id]
                assert loaded_state.is_direct == original_state.is_direct, (
                    f"Direct/indirect status mismatch for {node_id}"
                )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestTracerouteHistoryLimitProperty:
    """
    Feature: network-traceroute-mapper, Property 33: Traceroute History Limit
    
    Tests that the system stores at most history_per_node successful traceroutes,
    keeping the most recent ones.
    
    **Validates: Requirements 13.4**
    """
    
    @composite
    def traceroute_result_strategy(draw):
        """Generate a random traceroute result"""
        # Generate route with 1-7 hops
        hop_count = draw(st.integers(min_value=1, max_value=7))
        route = [draw(valid_node_id()) for _ in range(hop_count)]
        
        # Generate SNR and RSSI values for each hop
        snr_values = [
            draw(st.floats(min_value=-30, max_value=20, allow_nan=False, allow_infinity=False))
            for _ in range(hop_count)
        ]
        rssi_values = [
            draw(st.floats(min_value=-120, max_value=-30, allow_nan=False, allow_infinity=False))
            for _ in range(hop_count)
        ]
        
        # Generate timestamp
        timestamp = draw(datetime_in_range())
        
        # Generate duration
        duration_ms = draw(st.floats(min_value=100, max_value=60000, allow_nan=False, allow_infinity=False))
        
        return {
            'timestamp': timestamp,
            'success': True,
            'hop_count': hop_count,
            'route': route,
            'snr_values': snr_values,
            'rssi_values': rssi_values,
            'duration_ms': duration_ms,
            'error_message': None
        }
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        history_limit=st.integers(min_value=1, max_value=20),
        num_results=st.integers(min_value=1, max_value=50)
    )
    def test_history_limit_enforced(self, node_id, history_limit, num_results):
        """
        Property 33: Traceroute History Limit
        
        For any node with traceroute history, the system should store at most
        history_per_node successful traceroutes, keeping the most recent ones.
        
        **Validates: Requirements 13.4**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance with specified history limit
            state_file_path = str(Path(temp_dir) / f"state_history_{id(node_id)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=history_limit)
            
            # Generate traceroute results with increasing timestamps
            base_time = datetime.now() - timedelta(days=30)
            results = []
            for i in range(num_results):
                result = {
                    'timestamp': base_time + timedelta(minutes=i),
                    'success': True,
                    'hop_count': 3,
                    'route': [f'!node{j:08x}' for j in range(3)],
                    'snr_values': [10.0, 5.0, 0.0],
                    'rssi_values': [-75.0, -85.0, -95.0],
                    'duration_ms': 1000.0,
                    'error_message': None
                }
                results.append(result)
                
                # Save each result
                save_result = asyncio.run(persistence.save_traceroute_history(node_id, result))
                assert save_result is True, f"Failed to save result {i}"
            
            # Load history
            history = asyncio.run(persistence.get_traceroute_history(node_id))
            
            # Verify history limit is enforced
            assert len(history) <= history_limit, (
                f"History contains {len(history)} entries but limit is {history_limit}"
            )
            
            # If we saved more results than the limit, verify we kept the most recent ones
            if num_results > history_limit:
                # History should contain exactly history_limit entries
                assert len(history) == history_limit, (
                    f"History should contain exactly {history_limit} entries when "
                    f"{num_results} results were saved"
                )
                
                # Verify we kept the most recent entries (last history_limit results)
                expected_results = results[-history_limit:]
                
                # Check that timestamps match (most recent entries)
                for i, (loaded, expected) in enumerate(zip(history, expected_results)):
                    assert abs((loaded['timestamp'] - expected['timestamp']).total_seconds()) < 1, (
                        f"Entry {i} timestamp mismatch: "
                        f"loaded={loaded['timestamp']}, expected={expected['timestamp']}"
                    )
            else:
                # History should contain all results
                assert len(history) == num_results, (
                    f"History should contain all {num_results} results when "
                    f"limit is {history_limit}"
                )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        history_limit=st.integers(min_value=1, max_value=20)
    )
    def test_history_keeps_most_recent(self, node_id, history_limit):
        """
        Property 33: Traceroute History Limit (Most Recent)
        
        When history exceeds the limit, the system should keep the most recent
        entries and discard the oldest ones.
        
        **Validates: Requirements 13.4**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_recent_{id(node_id)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=history_limit)
            
            # Save more results than the limit
            num_results = history_limit + 10
            base_time = datetime.now() - timedelta(days=30)
            
            saved_results = []
            for i in range(num_results):
                result = {
                    'timestamp': base_time + timedelta(minutes=i),
                    'success': True,
                    'hop_count': 2,
                    'route': [f'!node{j:08x}' for j in range(2)],
                    'snr_values': [10.0, 5.0],
                    'rssi_values': [-75.0, -85.0],
                    'duration_ms': 500.0,
                    'error_message': None
                }
                saved_results.append(result)
                asyncio.run(persistence.save_traceroute_history(node_id, result))
            
            # Load history
            history = asyncio.run(persistence.get_traceroute_history(node_id))
            
            # Verify we have exactly history_limit entries
            assert len(history) == history_limit, (
                f"Expected {history_limit} entries, got {len(history)}"
            )
            
            # Verify these are the most recent entries
            expected_results = saved_results[-history_limit:]
            
            # Check timestamps are in order and match expected
            for i in range(len(history)):
                loaded_time = history[i]['timestamp']
                expected_time = expected_results[i]['timestamp']
                
                assert abs((loaded_time - expected_time).total_seconds()) < 1, (
                    f"Entry {i} should be from most recent {history_limit} results"
                )
            
            # Verify timestamps are in chronological order (oldest to newest)
            for i in range(len(history) - 1):
                assert history[i]['timestamp'] <= history[i + 1]['timestamp'], (
                    f"History entries should be in chronological order"
                )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_ids=st.lists(valid_node_id(), min_size=2, max_size=10, unique=True),
        history_limit=st.integers(min_value=1, max_value=15),
        results_per_node=st.integers(min_value=1, max_value=30)
    )
    def test_history_limit_per_node_independent(self, node_ids, history_limit, results_per_node):
        """
        Property 33: Traceroute History Limit (Per Node)
        
        The history limit should be enforced independently for each node.
        Saving history for one node should not affect history for other nodes.
        
        **Validates: Requirements 13.4**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_multi_node_{id(node_ids)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=history_limit)
            
            # Save results for each node
            base_time = datetime.now() - timedelta(days=30)
            
            for node_id in node_ids:
                for i in range(results_per_node):
                    result = {
                        'timestamp': base_time + timedelta(minutes=i),
                        'success': True,
                        'hop_count': 2,
                        'route': [f'!gateway', node_id],
                        'snr_values': [10.0, 5.0],
                        'rssi_values': [-75.0, -85.0],
                        'duration_ms': 500.0,
                        'error_message': None
                    }
                    asyncio.run(persistence.save_traceroute_history(node_id, result))
            
            # Verify history limit for each node independently
            for node_id in node_ids:
                history = asyncio.run(persistence.get_traceroute_history(node_id))
                
                # Each node should have at most history_limit entries
                assert len(history) <= history_limit, (
                    f"Node {node_id} has {len(history)} entries but limit is {history_limit}"
                )
                
                # If we saved more than the limit, should have exactly history_limit
                if results_per_node > history_limit:
                    assert len(history) == history_limit, (
                        f"Node {node_id} should have exactly {history_limit} entries"
                    )
                else:
                    assert len(history) == results_per_node, (
                        f"Node {node_id} should have all {results_per_node} entries"
                    )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        history_limit=st.integers(min_value=5, max_value=20)
    )
    def test_history_limit_with_exact_limit(self, node_id, history_limit):
        """
        Property 33: Traceroute History Limit (Exact Limit)
        
        When exactly history_per_node results are saved, all should be retained.
        When one more is added, the oldest should be removed.
        
        **Validates: Requirements 13.4**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_exact_{id(node_id)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=history_limit)
            
            base_time = datetime.now() - timedelta(days=30)
            
            # Save exactly history_limit results
            for i in range(history_limit):
                result = {
                    'timestamp': base_time + timedelta(minutes=i),
                    'success': True,
                    'hop_count': 2,
                    'route': [f'!gateway', node_id],
                    'snr_values': [10.0, 5.0],
                    'rssi_values': [-75.0, -85.0],
                    'duration_ms': 500.0,
                    'error_message': None
                }
                asyncio.run(persistence.save_traceroute_history(node_id, result))
            
            # Load history - should have exactly history_limit entries
            history = asyncio.run(persistence.get_traceroute_history(node_id))
            assert len(history) == history_limit, (
                f"Should have exactly {history_limit} entries after saving {history_limit} results"
            )
            
            # Save one more result
            new_result = {
                'timestamp': base_time + timedelta(minutes=history_limit),
                'success': True,
                'hop_count': 2,
                'route': [f'!gateway', node_id],
                'snr_values': [10.0, 5.0],
                'rssi_values': [-75.0, -85.0],
                'duration_ms': 500.0,
                'error_message': None
            }
            asyncio.run(persistence.save_traceroute_history(node_id, new_result))
            
            # Load history again - should still have exactly history_limit entries
            history = asyncio.run(persistence.get_traceroute_history(node_id))
            assert len(history) == history_limit, (
                f"Should still have exactly {history_limit} entries after saving one more"
            )
            
            # Verify the oldest entry was removed (first timestamp should not be base_time)
            oldest_timestamp = history[0]['timestamp']
            assert oldest_timestamp > base_time, (
                f"Oldest entry should have been removed"
            )
            
            # Verify the newest entry is present
            newest_timestamp = history[-1]['timestamp']
            expected_newest = base_time + timedelta(minutes=history_limit)
            assert abs((newest_timestamp - expected_newest).total_seconds()) < 1, (
                f"Newest entry should be present"
            )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @settings(max_examples=20, deadline=None)
    @given(
        node_id=valid_node_id(),
        initial_limit=st.integers(min_value=5, max_value=15),
        num_results=st.integers(min_value=20, max_value=40)
    )
    def test_history_limit_boundary_conditions(self, node_id, initial_limit, num_results):
        """
        Property 33: Traceroute History Limit (Boundary Conditions)
        
        Test boundary conditions: saving 0 results, 1 result, limit-1 results,
        limit results, limit+1 results.
        
        **Validates: Requirements 13.4**
        """
        # Create temporary directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create persistence instance
            state_file_path = str(Path(temp_dir) / f"state_boundary_{id(node_id)}.json")
            persistence = StatePersistence(state_file_path, history_per_node=initial_limit)
            
            base_time = datetime.now() - timedelta(days=30)
            
            # Test saving results up to and beyond the limit
            for i in range(num_results):
                result = {
                    'timestamp': base_time + timedelta(minutes=i),
                    'success': True,
                    'hop_count': 2,
                    'route': [f'!gateway', node_id],
                    'snr_values': [10.0, 5.0],
                    'rssi_values': [-75.0, -85.0],
                    'duration_ms': 500.0,
                    'error_message': None
                }
                asyncio.run(persistence.save_traceroute_history(node_id, result))
                
                # Check history after each save
                history = asyncio.run(persistence.get_traceroute_history(node_id))
                
                # History should never exceed the limit
                assert len(history) <= initial_limit, (
                    f"After saving {i+1} results, history has {len(history)} entries "
                    f"but limit is {initial_limit}"
                )
                
                # History should contain min(i+1, initial_limit) entries
                expected_count = min(i + 1, initial_limit)
                assert len(history) == expected_count, (
                    f"After saving {i+1} results, expected {expected_count} entries "
                    f"but got {len(history)}"
                )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
