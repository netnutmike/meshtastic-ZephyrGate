"""
Unit tests for StatePersistence component
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from plugins.traceroute_mapper.state_persistence import StatePersistence
from plugins.traceroute_mapper.node_state_tracker import NodeState


class TestStatePersistence:
    """Test StatePersistence component"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def state_file_path(self, temp_dir):
        """Get path to test state file"""
        return str(Path(temp_dir) / "test_state.json")
    
    @pytest.fixture
    def persistence(self, state_file_path):
        """Create StatePersistence instance"""
        return StatePersistence(state_file_path, history_per_node=10)
    
    def test_initialization(self, state_file_path):
        """Test StatePersistence initialization"""
        persistence = StatePersistence(state_file_path, history_per_node=5)
        
        assert persistence.state_file_path == Path(state_file_path)
        assert persistence.history_per_node == 5
        assert persistence.state_file_path.parent.exists()
    
    @pytest.mark.asyncio
    async def test_save_state_empty(self, persistence):
        """Test saving empty state"""
        result = await persistence.save_state({})
        
        assert result is True
        assert persistence.state_file_path.exists()
        
        # Verify file contents
        with open(persistence.state_file_path, 'r') as f:
            data = json.load(f)
        
        assert data['version'] == '1.0'
        assert 'last_saved' in data
        assert data['nodes'] == {}
    
    @pytest.mark.asyncio
    async def test_save_state_single_node(self, persistence):
        """Test saving state with a single node"""
        now = datetime.now()
        node_state = NodeState(
            node_id="!test1",
            is_direct=False,
            last_seen=now,
            snr=-5.0,
            rssi=-90
        )
        
        result = await persistence.save_state({"!test1": node_state})
        
        assert result is True
        assert persistence.state_file_path.exists()
        
        # Verify file contents
        with open(persistence.state_file_path, 'r') as f:
            data = json.load(f)
        
        assert len(data['nodes']) == 1
        assert '!test1' in data['nodes']
        assert data['nodes']['!test1']['node_id'] == '!test1'
        assert data['nodes']['!test1']['is_direct'] is False
        assert data['nodes']['!test1']['snr'] == -5.0
        assert data['nodes']['!test1']['rssi'] == -90
    
    @pytest.mark.asyncio
    async def test_save_state_multiple_nodes(self, persistence):
        """Test saving state with multiple nodes"""
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
            ),
            "!test3": NodeState(
                node_id="!test3",
                is_direct=False,
                last_seen=now,
                last_traced=now - timedelta(hours=1),
                trace_count=10
            )
        }
        
        result = await persistence.save_state(nodes)
        
        assert result is True
        
        # Verify file contents
        with open(persistence.state_file_path, 'r') as f:
            data = json.load(f)
        
        assert len(data['nodes']) == 3
        assert data['nodes']['!test1']['trace_count'] == 5
        assert data['nodes']['!test2']['trace_count'] == 2
        assert data['nodes']['!test3']['trace_count'] == 10
    
    @pytest.mark.asyncio
    async def test_save_state_with_datetime_fields(self, persistence):
        """Test saving state with datetime fields"""
        now = datetime.now()
        last_traced = now - timedelta(hours=2)
        next_recheck = now + timedelta(hours=4)
        
        node_state = NodeState(
            node_id="!test1",
            is_direct=False,
            last_seen=now,
            last_traced=last_traced,
            next_recheck=next_recheck
        )
        
        result = await persistence.save_state({"!test1": node_state})
        
        assert result is True
        
        # Verify datetime fields are serialized as ISO format strings
        with open(persistence.state_file_path, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data['nodes']['!test1']['last_seen'], str)
        assert isinstance(data['nodes']['!test1']['last_traced'], str)
        assert isinstance(data['nodes']['!test1']['next_recheck'], str)
    
    @pytest.mark.asyncio
    async def test_load_state_missing_file(self, persistence):
        """Test loading state when file doesn't exist"""
        result = await persistence.load_state()
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_load_state_empty(self, persistence):
        """Test loading empty state"""
        # Save empty state first
        await persistence.save_state({})
        
        # Load it back
        result = await persistence.load_state()
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_load_state_single_node(self, persistence):
        """Test loading state with a single node"""
        now = datetime.now()
        node_state = NodeState(
            node_id="!test1",
            is_direct=False,
            last_seen=now,
            snr=-5.0,
            rssi=-90,
            trace_count=3
        )
        
        # Save state
        await persistence.save_state({"!test1": node_state})
        
        # Load it back
        result = await persistence.load_state()
        
        assert len(result) == 1
        assert "!test1" in result
        
        loaded_node = result["!test1"]
        assert loaded_node.node_id == "!test1"
        assert loaded_node.is_direct is False
        assert loaded_node.snr == -5.0
        assert loaded_node.rssi == -90
        assert loaded_node.trace_count == 3
    
    @pytest.mark.asyncio
    async def test_load_state_multiple_nodes(self, persistence):
        """Test loading state with multiple nodes"""
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
        
        # Save state
        await persistence.save_state(nodes)
        
        # Load it back
        result = await persistence.load_state()
        
        assert len(result) == 2
        assert result["!test1"].trace_count == 5
        assert result["!test2"].trace_count == 2
    
    @pytest.mark.asyncio
    async def test_load_state_with_datetime_fields(self, persistence):
        """Test loading state with datetime fields"""
        now = datetime.now()
        last_traced = now - timedelta(hours=2)
        next_recheck = now + timedelta(hours=4)
        
        node_state = NodeState(
            node_id="!test1",
            is_direct=False,
            last_seen=now,
            last_traced=last_traced,
            next_recheck=next_recheck
        )
        
        # Save state
        await persistence.save_state({"!test1": node_state})
        
        # Load it back
        result = await persistence.load_state()
        
        loaded_node = result["!test1"]
        assert isinstance(loaded_node.last_seen, datetime)
        assert isinstance(loaded_node.last_traced, datetime)
        assert isinstance(loaded_node.next_recheck, datetime)
        
        # Verify datetime values are approximately correct (within 1 second)
        assert abs((loaded_node.last_seen - now).total_seconds()) < 1
        assert abs((loaded_node.last_traced - last_traced).total_seconds()) < 1
        assert abs((loaded_node.next_recheck - next_recheck).total_seconds()) < 1
    
    @pytest.mark.asyncio
    async def test_save_load_round_trip(self, persistence):
        """Test that save and load preserve all node state fields"""
        now = datetime.now()
        original_nodes = {
            "!test1": NodeState(
                node_id="!test1",
                is_direct=False,
                last_seen=now,
                last_traced=now - timedelta(hours=1),
                next_recheck=now + timedelta(hours=5),
                last_trace_success=True,
                trace_count=7,
                failure_count=2,
                snr=-3.5,
                rssi=-88,
                was_offline=False,
                role="ROUTER"
            ),
            "!test2": NodeState(
                node_id="!test2",
                is_direct=True,
                last_seen=now,
                snr=10.0,
                rssi=-70,
                role="CLIENT"
            )
        }
        
        # Save state
        save_result = await persistence.save_state(original_nodes)
        assert save_result is True
        
        # Load state
        loaded_nodes = await persistence.load_state()
        
        # Verify all fields are preserved
        assert len(loaded_nodes) == 2
        
        node1 = loaded_nodes["!test1"]
        assert node1.node_id == "!test1"
        assert node1.is_direct is False
        assert node1.last_trace_success is True
        assert node1.trace_count == 7
        assert node1.failure_count == 2
        assert node1.snr == -3.5
        assert node1.rssi == -88
        assert node1.was_offline is False
        assert node1.role == "ROUTER"
        
        node2 = loaded_nodes["!test2"]
        assert node2.node_id == "!test2"
        assert node2.is_direct is True
        assert node2.snr == 10.0
        assert node2.rssi == -70
        assert node2.role == "CLIENT"
    
    @pytest.mark.asyncio
    async def test_load_state_corrupted_json(self, persistence):
        """Test loading state from corrupted JSON file"""
        # Write corrupted JSON to file
        persistence.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(persistence.state_file_path, 'w') as f:
            f.write("{ invalid json content }")
        
        # Load should return empty dict and backup corrupted file
        result = await persistence.load_state()
        
        assert result == {}
        
        # Verify backup file was created
        backup_files = list(persistence.state_file_path.parent.glob("*.corrupted.*.json"))
        assert len(backup_files) > 0
    
    @pytest.mark.asyncio
    async def test_load_state_invalid_node_data(self, persistence):
        """Test loading state with invalid node data"""
        # Create state file with invalid node data
        state_data = {
            'version': '1.0',
            'last_saved': datetime.now().isoformat(),
            'nodes': {
                '!test1': {
                    'node_id': '!test1',
                    'is_direct': False,
                    'last_seen': 'invalid-datetime',  # Invalid datetime
                    'snr': -5.0
                },
                '!test2': {
                    'node_id': '!test2',
                    'is_direct': True,
                    'last_seen': datetime.now().isoformat()
                }
            }
        }
        
        with open(persistence.state_file_path, 'w') as f:
            json.dump(state_data, f)
        
        # Load should skip invalid node but load valid ones
        result = await persistence.load_state()
        
        # Only test2 should be loaded (test1 has invalid datetime)
        assert len(result) == 1
        assert '!test2' in result
        assert '!test1' not in result
    
    @pytest.mark.asyncio
    async def test_save_traceroute_history(self, persistence):
        """Test saving traceroute history"""
        now = datetime.now()
        result_data = {
            'timestamp': now,
            'success': True,
            'hop_count': 3,
            'route': ['!gateway', '!relay1', '!target'],
            'snr_values': [10.0, 5.0, -2.0],
            'rssi_values': [-75, -85, -92],
            'duration_ms': 1500.0
        }
        
        save_result = await persistence.save_traceroute_history('!target', result_data)
        
        assert save_result is True
        assert persistence.state_file_path.exists()
    
    @pytest.mark.asyncio
    async def test_get_traceroute_history_empty(self, persistence):
        """Test getting history for node with no history"""
        result = await persistence.get_traceroute_history('!test1')
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_save_and_get_traceroute_history(self, persistence):
        """Test saving and retrieving traceroute history"""
        now = datetime.now()
        result_data = {
            'timestamp': now,
            'success': True,
            'hop_count': 3,
            'route': ['!gateway', '!relay1', '!target'],
            'snr_values': [10.0, 5.0, -2.0],
            'rssi_values': [-75, -85, -92],
            'duration_ms': 1500.0
        }
        
        # Save history
        await persistence.save_traceroute_history('!target', result_data)
        
        # Get history
        history = await persistence.get_traceroute_history('!target')
        
        assert len(history) == 1
        assert history[0]['success'] is True
        assert history[0]['hop_count'] == 3
        assert len(history[0]['route']) == 3
        assert isinstance(history[0]['timestamp'], datetime)
    
    @pytest.mark.asyncio
    async def test_traceroute_history_limit(self, persistence):
        """Test that traceroute history respects the limit per node"""
        now = datetime.now()
        
        # Save more entries than the limit
        for i in range(15):
            result_data = {
                'timestamp': now + timedelta(minutes=i),
                'success': True,
                'hop_count': 3,
                'route': ['!gateway', '!relay1', '!target'],
                'snr_values': [10.0, 5.0, -2.0],
                'rssi_values': [-75, -85, -92],
                'duration_ms': 1500.0
            }
            await persistence.save_traceroute_history('!target', result_data)
        
        # Get history
        history = await persistence.get_traceroute_history('!target')
        
        # Should only have the last 10 entries (history_per_node=10)
        assert len(history) == 10
        
        # Verify they are the most recent ones
        assert history[0]['timestamp'] == now + timedelta(minutes=5)
        assert history[-1]['timestamp'] == now + timedelta(minutes=14)
    
    @pytest.mark.asyncio
    async def test_traceroute_history_multiple_nodes(self, persistence):
        """Test traceroute history for multiple nodes"""
        now = datetime.now()
        
        # Save history for multiple nodes
        for node_id in ['!node1', '!node2', '!node3']:
            result_data = {
                'timestamp': now,
                'success': True,
                'hop_count': 2,
                'route': ['!gateway', node_id],
                'snr_values': [10.0, 5.0],
                'rssi_values': [-75, -85],
                'duration_ms': 1000.0
            }
            await persistence.save_traceroute_history(node_id, result_data)
        
        # Get history for each node
        history1 = await persistence.get_traceroute_history('!node1')
        history2 = await persistence.get_traceroute_history('!node2')
        history3 = await persistence.get_traceroute_history('!node3')
        
        assert len(history1) == 1
        assert len(history2) == 1
        assert len(history3) == 1
        
        assert history1[0]['route'][-1] == '!node1'
        assert history2[0]['route'][-1] == '!node2'
        assert history3[0]['route'][-1] == '!node3'
    
    @pytest.mark.asyncio
    async def test_get_traceroute_history_with_limit(self, persistence):
        """Test getting traceroute history with a limit"""
        now = datetime.now()
        
        # Save 5 entries
        for i in range(5):
            result_data = {
                'timestamp': now + timedelta(minutes=i),
                'success': True,
                'hop_count': 3,
                'route': ['!gateway', '!relay1', '!target'],
                'snr_values': [10.0, 5.0, -2.0],
                'rssi_values': [-75, -85, -92],
                'duration_ms': 1500.0
            }
            await persistence.save_traceroute_history('!target', result_data)
        
        # Get only last 3 entries
        history = await persistence.get_traceroute_history('!target', limit=3)
        
        assert len(history) == 3
        assert history[0]['timestamp'] == now + timedelta(minutes=2)
        assert history[-1]['timestamp'] == now + timedelta(minutes=4)
    
    @pytest.mark.asyncio
    async def test_state_and_history_coexist(self, persistence):
        """Test that node state and traceroute history can coexist in the same file"""
        now = datetime.now()
        
        # Save node state
        node_state = NodeState(
            node_id="!test1",
            is_direct=False,
            last_seen=now,
            trace_count=5
        )
        await persistence.save_state({"!test1": node_state})
        
        # Save traceroute history
        result_data = {
            'timestamp': now,
            'success': True,
            'hop_count': 3,
            'route': ['!gateway', '!relay1', '!test1'],
            'snr_values': [10.0, 5.0, -2.0],
            'rssi_values': [-75, -85, -92],
            'duration_ms': 1500.0
        }
        await persistence.save_traceroute_history('!test1', result_data)
        
        # Load node state
        loaded_nodes = await persistence.load_state()
        assert len(loaded_nodes) == 1
        assert loaded_nodes['!test1'].trace_count == 5
        
        # Get traceroute history
        history = await persistence.get_traceroute_history('!test1')
        assert len(history) == 1
        assert history[0]['success'] is True
    
    @pytest.mark.asyncio
    async def test_save_state_creates_parent_directory(self, temp_dir):
        """Test that save_state creates parent directory if it doesn't exist"""
        nested_path = str(Path(temp_dir) / "nested" / "dir" / "state.json")
        persistence = StatePersistence(nested_path)
        
        # Parent directory should be created during initialization
        assert Path(nested_path).parent.exists()
        
        # Save should work
        result = await persistence.save_state({})
        assert result is True
        assert Path(nested_path).exists()
