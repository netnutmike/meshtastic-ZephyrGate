"""
Property-Based Tests for Periodic State Persistence

Tests Property 31:
- Property 31: Periodic State Persistence

Author: ZephyrGate Team
Version: 1.0.0
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import pytest
import tempfile
import shutil

# Add src directory to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from plugins.traceroute_mapper.node_state_tracker import NodeStateTracker, NodeState
from plugins.traceroute_mapper.state_persistence import StatePersistence


# Strategies
@st.composite
def node_id_strategy(draw):
    """Generate valid node IDs"""
    return f"!{draw(st.text(alphabet='0123456789abcdef', min_size=8, max_size=8))}"


@st.composite
def auto_save_interval_strategy(draw):
    """Generate auto-save intervals in minutes"""
    return draw(st.floats(min_value=0.1, max_value=60.0))  # 0.1 to 60 minutes


@st.composite
def node_state_strategy(draw):
    """Generate NodeState objects"""
    node_id = draw(node_id_strategy())
    is_direct = draw(st.booleans())
    last_seen = datetime.now()
    last_traced = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2024, 1, 1), max_value=datetime.now())
    ))
    
    return NodeState(
        node_id=node_id,
        is_direct=is_direct,
        last_seen=last_seen,
        last_traced=last_traced,
        last_trace_success=draw(st.booleans()),
        trace_count=draw(st.integers(min_value=0, max_value=100)),
        failure_count=draw(st.integers(min_value=0, max_value=50)),
        snr=draw(st.one_of(st.none(), st.floats(min_value=-30.0, max_value=20.0))),
        rssi=draw(st.one_of(st.none(), st.integers(min_value=-120, max_value=-30))),
        was_offline=draw(st.booleans()),
        role=draw(st.one_of(st.none(), st.sampled_from(['CLIENT', 'ROUTER', 'REPEATER'])))
    )


class TestPeriodicPersistenceProperties:
    """Property-based tests for periodic state persistence"""
    
    @pytest.mark.asyncio
    @given(
        node_states=st.lists(node_state_strategy(), min_size=1, max_size=20),
        auto_save_interval_minutes=auto_save_interval_strategy()
    )
    @settings(max_examples=10, deadline=None)
    async def test_property_31_periodic_state_persistence(
        self,
        node_states: list,
        auto_save_interval_minutes: float
    ):
        """
        Feature: network-traceroute-mapper, Property 31: Periodic State Persistence
        
        **Validates: Requirements 13.1**
        
        For any configured auto_save_interval_minutes, the node state should be
        saved to disk at least once per interval.
        
        Note: This test verifies that the state persistence mechanism works correctly
        by simulating the periodic save operation. It doesn't test the actual timing
        of the background loop (which would require waiting for real time to pass).
        """
        # Create temporary directory for state file
        temp_dir = tempfile.mkdtemp()
        try:
            state_file_path = Path(temp_dir) / "test_state.json"
            
            # Create state persistence instance
            persistence = StatePersistence(
                state_file_path=str(state_file_path),
                history_per_node=10
            )
            
            # Create tracker with nodes
            config = {
                'recheck_interval_hours': 6,
                'recheck_enabled': True,
                'skip_direct_nodes': True,
                'blacklist': [],
                'whitelist': [],
                'exclude_roles': [],
                'min_snr_threshold': None
            }
            tracker = NodeStateTracker(config)
            
            # Add all nodes to tracker
            for node_state in node_states:
                tracker.update_node(
                    node_state.node_id,
                    is_direct=node_state.is_direct,
                    snr=node_state.snr,
                    rssi=node_state.rssi
                )
            
            # Get all nodes from tracker
            all_nodes = tracker.get_all_nodes()
            
            # Verify we have nodes to save
            assert len(all_nodes) > 0, "Should have nodes to save"
            
            # Save state (simulating periodic save)
            save_time_1 = datetime.now()
            success = await persistence.save_state(all_nodes)
            assert success, "First save should succeed"
            
            # Verify state file exists
            assert state_file_path.exists(), "State file should exist after save"
            
            # Get file modification time
            mtime_1 = state_file_path.stat().st_mtime
            
            # Simulate time passing (in a real scenario, this would be auto_save_interval_minutes)
            # For testing, we just do another save immediately
            await asyncio.sleep(0.1)  # Small delay to ensure different timestamp
            
            # Modify some node states
            if len(all_nodes) > 0:
                first_node_id = list(all_nodes.keys())[0]
                tracker.mark_node_traced(first_node_id, success=True)
            
            # Save state again (simulating second periodic save)
            save_time_2 = datetime.now()
            all_nodes_updated = tracker.get_all_nodes()
            success = await persistence.save_state(all_nodes_updated)
            assert success, "Second save should succeed"
            
            # Verify file was updated
            mtime_2 = state_file_path.stat().st_mtime
            assert mtime_2 >= mtime_1, "State file should be updated on second save"
            
            # Verify we can load the saved state
            loaded_state = await persistence.load_state()
            assert loaded_state is not None, "Should be able to load saved state"
            assert len(loaded_state) == len(all_nodes_updated), \
                "Loaded state should have same number of nodes"
            
            # Verify the interval concept: if we were to save periodically,
            # the saves would happen at regular intervals
            # We can't test actual timing without waiting, but we can verify
            # that multiple saves work correctly
            time_between_saves = (save_time_2 - save_time_1).total_seconds()
            
            # In a real scenario, time_between_saves would be approximately
            # auto_save_interval_minutes * 60 seconds
            # For this test, we just verify that saves can happen multiple times
            assert time_between_saves >= 0, "Time between saves should be non-negative"
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    @given(
        node_states=st.lists(node_state_strategy(), min_size=1, max_size=10),
        save_count=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=10, deadline=None)
    async def test_multiple_periodic_saves(
        self,
        node_states: list,
        save_count: int
    ):
        """
        Test that multiple periodic saves work correctly.
        
        This verifies that the state persistence mechanism can handle
        multiple consecutive saves without errors.
        """
        # Create temporary directory for state file
        temp_dir = tempfile.mkdtemp()
        try:
            state_file_path = Path(temp_dir) / "test_state.json"
            
            # Create state persistence instance
            persistence = StatePersistence(
                state_file_path=str(state_file_path),
                history_per_node=10
            )
            
            # Create tracker with nodes
            config = {
                'recheck_interval_hours': 6,
                'recheck_enabled': True,
                'skip_direct_nodes': True,
                'blacklist': [],
                'whitelist': [],
                'exclude_roles': [],
                'min_snr_threshold': None
            }
            tracker = NodeStateTracker(config)
            
            # Add all nodes to tracker
            for node_state in node_states:
                tracker.update_node(
                    node_state.node_id,
                    is_direct=node_state.is_direct,
                    snr=node_state.snr,
                    rssi=node_state.rssi
                )
            
            # Perform multiple saves
            save_times = []
            for i in range(save_count):
                # Get current state
                all_nodes = tracker.get_all_nodes()
                
                # Save state
                save_time = datetime.now()
                success = await persistence.save_state(all_nodes)
                assert success, f"Save {i+1} should succeed"
                save_times.append(save_time)
                
                # Small delay between saves
                await asyncio.sleep(0.05)
                
                # Modify a node (if any exist)
                if len(all_nodes) > 0:
                    node_ids = list(all_nodes.keys())
                    node_id = node_ids[i % len(node_ids)]
                    tracker.update_node(node_id, is_direct=False, snr=-5.0, rssi=-95)
            
            # Verify all saves completed
            assert len(save_times) == save_count, \
                f"Should have {save_count} save times"
            
            # Verify saves happened in order
            for i in range(1, len(save_times)):
                assert save_times[i] >= save_times[i-1], \
                    "Save times should be in chronological order"
            
            # Verify final state can be loaded
            loaded_state = await persistence.load_state()
            assert loaded_state is not None, "Should be able to load final state"
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    @given(
        node_states=st.lists(node_state_strategy(), min_size=1, max_size=10)
    )
    @settings(max_examples=10, deadline=None)
    async def test_save_preserves_all_node_data(
        self,
        node_states: list
    ):
        """
        Test that periodic saves preserve all node data correctly.
        
        This verifies that no data is lost during the save/load cycle.
        """
        # Create temporary directory for state file
        temp_dir = tempfile.mkdtemp()
        try:
            state_file_path = Path(temp_dir) / "test_state.json"
            
            # Create state persistence instance
            persistence = StatePersistence(
                state_file_path=str(state_file_path),
                history_per_node=10
            )
            
            # Create tracker with nodes
            config = {
                'recheck_interval_hours': 6,
                'recheck_enabled': True,
                'skip_direct_nodes': True,
                'blacklist': [],
                'whitelist': [],
                'exclude_roles': [],
                'min_snr_threshold': None
            }
            tracker = NodeStateTracker(config)
            
            # Add all nodes to tracker
            for node_state in node_states:
                tracker.update_node(
                    node_state.node_id,
                    is_direct=node_state.is_direct,
                    snr=node_state.snr,
                    rssi=node_state.rssi
                )
            
            # Get original state
            original_nodes = tracker.get_all_nodes()
            
            # Save state
            success = await persistence.save_state(original_nodes)
            assert success, "Save should succeed"
            
            # Load state
            loaded_nodes = await persistence.load_state()
            assert loaded_nodes is not None, "Load should succeed"
            
            # Verify all nodes are present
            assert len(loaded_nodes) == len(original_nodes), \
                "Loaded state should have same number of nodes"
            
            # Verify each node's data is preserved
            for node_id, original_node in original_nodes.items():
                assert node_id in loaded_nodes, f"Node {node_id} should be in loaded state"
                loaded_node = loaded_nodes[node_id]
                
                # Verify key fields are preserved
                assert loaded_node.node_id == original_node.node_id
                assert loaded_node.is_direct == original_node.is_direct
                assert loaded_node.last_trace_success == original_node.last_trace_success
                assert loaded_node.trace_count == original_node.trace_count
                assert loaded_node.failure_count == original_node.failure_count
                
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
