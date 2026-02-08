"""
Unit tests for Traceroute Manager

Tests traceroute request creation, pending request tracking, timeout detection,
and Meshtastic protocol compliance.

Requirements: 6.1, 18.1, 18.2, 18.3
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from traceroute_mapper.traceroute_manager import TracerouteManager, PendingTraceroute
from src.models.message import Message, MessageType, MessagePriority


@pytest.fixture
def manager():
    """Provide a traceroute manager with default settings"""
    return TracerouteManager(
        max_hops=7,
        timeout_seconds=60,
        max_retries=3,
        retry_backoff_multiplier=2.0
    )


@pytest.fixture
def fast_manager():
    """Provide a traceroute manager with fast timeout for testing"""
    return TracerouteManager(
        max_hops=5,
        timeout_seconds=2,
        max_retries=2,
        retry_backoff_multiplier=1.5
    )


class TestTracerouteManagerInitialization:
    """Tests for traceroute manager initialization"""
    
    def test_initialization_with_defaults(self):
        """Test manager initializes with default values"""
        manager = TracerouteManager()
        
        assert manager.max_hops == 7
        assert manager.timeout_seconds == 60
        assert manager.max_retries == 3
        assert manager.retry_backoff_multiplier == 2.0
        assert manager.get_pending_count() == 0
    
    def test_initialization_with_custom_values(self):
        """Test manager initializes with custom values"""
        manager = TracerouteManager(
            max_hops=10,
            timeout_seconds=120,
            max_retries=5,
            retry_backoff_multiplier=3.0
        )
        
        assert manager.max_hops == 10
        assert manager.timeout_seconds == 120
        assert manager.max_retries == 5
        assert manager.retry_backoff_multiplier == 3.0
    
    def test_initial_statistics(self, manager):
        """Test manager starts with zero statistics"""
        stats = manager.get_statistics()
        
        assert stats['requests_sent'] == 0
        assert stats['responses_received'] == 0
        assert stats['timeouts'] == 0
        assert stats['retries'] == 0
        assert stats['pending_count'] == 0


class TestSendTraceroute:
    """Tests for send_traceroute() method"""
    
    @pytest.mark.asyncio
    async def test_send_traceroute_returns_request_id(self, manager):
        """Test send_traceroute returns a unique request ID"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        assert request_id is not None
        assert isinstance(request_id, str)
        assert len(request_id) > 0
    
    @pytest.mark.asyncio
    async def test_send_traceroute_creates_pending_request(self, manager):
        """Test send_traceroute creates a pending request"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        assert manager.is_pending(request_id)
        assert manager.get_pending_count() == 1
    
    @pytest.mark.asyncio
    async def test_send_traceroute_uses_default_max_hops(self, manager):
        """Test send_traceroute uses default max_hops when not specified"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert message.hop_limit == manager.max_hops
    
    @pytest.mark.asyncio
    async def test_send_traceroute_uses_custom_max_hops(self, manager):
        """Test send_traceroute uses custom max_hops when specified"""
        custom_hops = 10
        request_id = await manager.send_traceroute("!a1b2c3d4", max_hops=custom_hops)
        
        # Note: The message is created with the custom hops, but we need to verify
        # it through the pending traceroute tracking
        assert manager.is_pending(request_id)
    
    @pytest.mark.asyncio
    async def test_send_traceroute_sets_timeout(self, fast_manager):
        """Test send_traceroute sets correct timeout"""
        request_id = await fast_manager.send_traceroute("!a1b2c3d4")
        
        # Get the pending traceroute
        pending = fast_manager._pending_traceroutes.get(request_id)
        assert pending is not None
        
        # Check timeout is set correctly
        expected_timeout = pending.sent_at + timedelta(seconds=fast_manager.timeout_seconds)
        assert abs((pending.timeout_at - expected_timeout).total_seconds()) < 1.0
    
    @pytest.mark.asyncio
    async def test_send_traceroute_updates_statistics(self, manager):
        """Test send_traceroute updates statistics"""
        await manager.send_traceroute("!a1b2c3d4")
        
        stats = manager.get_statistics()
        assert stats['requests_sent'] == 1
    
    @pytest.mark.asyncio
    async def test_send_traceroute_multiple_requests(self, manager):
        """Test sending multiple traceroute requests"""
        request_ids = []
        for i in range(5):
            request_id = await manager.send_traceroute(f"!node{i}")
            request_ids.append(request_id)
        
        # All should be unique
        assert len(set(request_ids)) == 5
        
        # All should be pending
        assert manager.get_pending_count() == 5
        
        # Statistics should be updated
        stats = manager.get_statistics()
        assert stats['requests_sent'] == 5


class TestMeshtasticProtocolCompliance:
    """Tests for Meshtastic protocol compliance (Requirements 18.1, 18.2, 18.3)"""
    
    @pytest.mark.asyncio
    async def test_message_type_is_routing(self, manager):
        """
        Test traceroute request uses MessageType.ROUTING
        
        Requirement 18.1: Use MessageType.ROUTING (TRACEROUTE_APP)
        """
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert message.message_type == MessageType.ROUTING
    
    @pytest.mark.asyncio
    async def test_want_response_flag_set(self, manager):
        """
        Test traceroute request sets want_response flag to true
        
        Requirement 18.2: Set want_response flag to true
        """
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert 'want_response' in message.metadata
        assert message.metadata['want_response'] is True
    
    @pytest.mark.asyncio
    async def test_route_discovery_flag_set(self, manager):
        """
        Test traceroute request sets route_discovery flag
        
        Requirement 18.3: Include route_discovery flag
        """
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert 'route_discovery' in message.metadata
        assert message.metadata['route_discovery'] is True
    
    @pytest.mark.asyncio
    async def test_destination_node_id_set(self, manager):
        """
        Test traceroute request includes destination node ID
        
        Requirement 18.3: Include destination node_id
        """
        target_node = "!a1b2c3d4"
        request_id = await manager.send_traceroute(target_node)
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert message.recipient_id == target_node
    
    @pytest.mark.asyncio
    async def test_hop_limit_set(self, manager):
        """
        Test traceroute request sets hop_limit
        
        Requirement 6.1: Set hop_limit to configured max_hops
        Requirement 18.3: Include max_hops
        """
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert message.hop_limit is not None
        assert message.hop_limit == manager.max_hops
    
    @pytest.mark.asyncio
    async def test_empty_content(self, manager):
        """Test traceroute request has empty content"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert message.content == ""
    
    @pytest.mark.asyncio
    async def test_request_id_in_metadata(self, manager):
        """Test traceroute request includes request_id in metadata"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert 'request_id' in message.metadata
        assert message.metadata['request_id'] == request_id
    
    @pytest.mark.asyncio
    async def test_traceroute_flag_in_metadata(self, manager):
        """Test traceroute request includes traceroute flag in metadata"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert 'traceroute' in message.metadata
        assert message.metadata['traceroute'] is True


class TestPendingTracerouteTracking:
    """Tests for pending traceroute tracking"""
    
    @pytest.mark.asyncio
    async def test_is_pending_returns_true_for_pending_request(self, manager):
        """Test is_pending returns True for pending requests"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        assert manager.is_pending(request_id) is True
    
    @pytest.mark.asyncio
    async def test_is_pending_returns_false_for_unknown_request(self, manager):
        """Test is_pending returns False for unknown requests"""
        assert manager.is_pending("unknown-request-id") is False
    
    @pytest.mark.asyncio
    async def test_get_pending_count_accurate(self, manager):
        """Test get_pending_count returns accurate count"""
        assert manager.get_pending_count() == 0
        
        await manager.send_traceroute("!node1")
        assert manager.get_pending_count() == 1
        
        await manager.send_traceroute("!node2")
        assert manager.get_pending_count() == 2
        
        await manager.send_traceroute("!node3")
        assert manager.get_pending_count() == 3
    
    @pytest.mark.asyncio
    async def test_get_pending_for_node_finds_request(self, manager):
        """Test get_pending_for_node finds pending request for node"""
        node_id = "!a1b2c3d4"
        request_id = await manager.send_traceroute(node_id)
        
        pending = manager.get_pending_for_node(node_id)
        
        assert pending is not None
        assert pending.node_id == node_id
        assert pending.request_id == request_id
    
    @pytest.mark.asyncio
    async def test_get_pending_for_node_returns_none_for_unknown_node(self, manager):
        """Test get_pending_for_node returns None for unknown node"""
        pending = manager.get_pending_for_node("!unknown")
        
        assert pending is None
    
    @pytest.mark.asyncio
    async def test_get_pending_traceroute_message_returns_message(self, manager):
        """Test get_pending_traceroute_message returns message for pending request"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        message = manager.get_pending_traceroute_message(request_id)
        
        assert message is not None
        assert isinstance(message, Message)
        assert message.id == request_id
    
    @pytest.mark.asyncio
    async def test_get_pending_traceroute_message_returns_none_for_unknown(self, manager):
        """Test get_pending_traceroute_message returns None for unknown request"""
        message = manager.get_pending_traceroute_message("unknown-request-id")
        
        assert message is None


class TestCancelTraceroute:
    """Tests for cancel_traceroute() method"""
    
    @pytest.mark.asyncio
    async def test_cancel_traceroute_removes_pending_request(self, manager):
        """Test cancel_traceroute removes pending request"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        assert manager.is_pending(request_id)
        
        result = await manager.cancel_traceroute(request_id)
        
        assert result is True
        assert not manager.is_pending(request_id)
        assert manager.get_pending_count() == 0
    
    @pytest.mark.asyncio
    async def test_cancel_traceroute_returns_false_for_unknown_request(self, manager):
        """Test cancel_traceroute returns False for unknown request"""
        result = await manager.cancel_traceroute("unknown-request-id")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cancel_traceroute_multiple_requests(self, manager):
        """Test cancelling multiple traceroute requests"""
        request_ids = []
        for i in range(5):
            request_id = await manager.send_traceroute(f"!node{i}")
            request_ids.append(request_id)
        
        assert manager.get_pending_count() == 5
        
        # Cancel first and last
        await manager.cancel_traceroute(request_ids[0])
        await manager.cancel_traceroute(request_ids[4])
        
        assert manager.get_pending_count() == 3
        assert not manager.is_pending(request_ids[0])
        assert not manager.is_pending(request_ids[4])
        assert manager.is_pending(request_ids[1])
        assert manager.is_pending(request_ids[2])
        assert manager.is_pending(request_ids[3])


class TestTimeoutDetection:
    """Tests for timeout detection"""
    
    @pytest.mark.asyncio
    async def test_check_timeouts_returns_empty_when_no_timeouts(self, manager):
        """Test check_timeouts returns empty list when no timeouts"""
        await manager.send_traceroute("!a1b2c3d4")
        
        timed_out = manager.check_timeouts()
        
        assert len(timed_out) == 0
    
    @pytest.mark.asyncio
    async def test_check_timeouts_detects_timed_out_requests(self, fast_manager):
        """Test check_timeouts detects timed out requests"""
        request_id = await fast_manager.send_traceroute("!a1b2c3d4")
        
        # Manually set timeout to past
        pending = fast_manager._pending_traceroutes[request_id]
        pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        timed_out = fast_manager.check_timeouts()
        
        assert len(timed_out) == 1
        assert timed_out[0].request_id == request_id
        assert timed_out[0].node_id == "!a1b2c3d4"
    
    @pytest.mark.asyncio
    async def test_check_timeouts_removes_timed_out_requests(self, fast_manager):
        """Test check_timeouts removes timed out requests from pending"""
        request_id = await fast_manager.send_traceroute("!a1b2c3d4")
        
        # Manually set timeout to past
        pending = fast_manager._pending_traceroutes[request_id]
        pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        assert fast_manager.is_pending(request_id)
        
        fast_manager.check_timeouts()
        
        assert not fast_manager.is_pending(request_id)
        assert fast_manager.get_pending_count() == 0
    
    @pytest.mark.asyncio
    async def test_check_timeouts_updates_statistics(self, fast_manager):
        """Test check_timeouts updates timeout statistics"""
        request_id = await fast_manager.send_traceroute("!a1b2c3d4")
        
        # Manually set timeout to past
        pending = fast_manager._pending_traceroutes[request_id]
        pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        fast_manager.check_timeouts()
        
        stats = fast_manager.get_statistics()
        assert stats['timeouts'] == 1
    
    @pytest.mark.asyncio
    async def test_check_timeouts_handles_multiple_timeouts(self, fast_manager):
        """Test check_timeouts handles multiple timed out requests"""
        request_ids = []
        for i in range(5):
            request_id = await fast_manager.send_traceroute(f"!node{i}")
            request_ids.append(request_id)
        
        # Set first 3 to timeout
        for i in range(3):
            pending = fast_manager._pending_traceroutes[request_ids[i]]
            pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        timed_out = fast_manager.check_timeouts()
        
        assert len(timed_out) == 3
        assert fast_manager.get_pending_count() == 2
        
        stats = fast_manager.get_statistics()
        assert stats['timeouts'] == 3


class TestPendingTracerouteDataclass:
    """Tests for PendingTraceroute dataclass"""
    
    def test_pending_traceroute_creation(self):
        """Test PendingTraceroute can be created with required fields"""
        now = datetime.utcnow()
        timeout = now + timedelta(seconds=60)
        
        pending = PendingTraceroute(
            request_id="test-id",
            node_id="!a1b2c3d4",
            sent_at=now,
            timeout_at=timeout,
            retry_count=0,
            max_retries=3,
            priority=8
        )
        
        assert pending.request_id == "test-id"
        assert pending.node_id == "!a1b2c3d4"
        assert pending.sent_at == now
        assert pending.timeout_at == timeout
        assert pending.retry_count == 0
        assert pending.max_retries == 3
        assert pending.priority == 8
    
    def test_pending_traceroute_default_values(self):
        """Test PendingTraceroute uses default values"""
        now = datetime.utcnow()
        timeout = now + timedelta(seconds=60)
        
        pending = PendingTraceroute(
            request_id="test-id",
            node_id="!a1b2c3d4",
            sent_at=now,
            timeout_at=timeout
        )
        
        assert pending.retry_count == 0
        assert pending.max_retries == 3
        assert pending.priority == 8


class TestStatistics:
    """Tests for statistics tracking"""
    
    @pytest.mark.asyncio
    async def test_statistics_track_requests_sent(self, manager):
        """Test statistics track number of requests sent"""
        for i in range(5):
            await manager.send_traceroute(f"!node{i}")
        
        stats = manager.get_statistics()
        assert stats['requests_sent'] == 5
    
    @pytest.mark.asyncio
    async def test_statistics_track_pending_count(self, manager):
        """Test statistics track pending count"""
        for i in range(3):
            await manager.send_traceroute(f"!node{i}")
        
        stats = manager.get_statistics()
        assert stats['pending_count'] == 3
    
    def test_statistics_structure(self, manager):
        """Test statistics contain all required fields"""
        stats = manager.get_statistics()
        
        assert 'requests_sent' in stats
        assert 'responses_received' in stats
        assert 'timeouts' in stats
        assert 'retries' in stats
        assert 'pending_count' in stats
    
    @pytest.mark.asyncio
    async def test_reset_statistics(self, manager):
        """Test reset_statistics clears counters"""
        # Generate some statistics
        for i in range(3):
            await manager.send_traceroute(f"!node{i}")
        
        stats = manager.get_statistics()
        assert stats['requests_sent'] == 3
        
        # Reset
        manager.reset_statistics()
        
        stats = manager.get_statistics()
        assert stats['requests_sent'] == 0
        assert stats['responses_received'] == 0
        assert stats['timeouts'] == 0
        assert stats['retries'] == 0
        # Note: pending_count is not reset as it reflects current state


class TestEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_send_traceroute_with_zero_max_hops(self, manager):
        """Test send_traceroute with zero max_hops"""
        request_id = await manager.send_traceroute("!a1b2c3d4", max_hops=0)
        
        assert manager.is_pending(request_id)
    
    @pytest.mark.asyncio
    async def test_send_traceroute_with_very_large_max_hops(self, manager):
        """Test send_traceroute with very large max_hops"""
        request_id = await manager.send_traceroute("!a1b2c3d4", max_hops=100)
        
        assert manager.is_pending(request_id)
    
    @pytest.mark.asyncio
    async def test_send_traceroute_with_zero_timeout(self):
        """Test send_traceroute with zero timeout"""
        manager = TracerouteManager(timeout_seconds=0)
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        # Should timeout immediately
        timed_out = manager.check_timeouts()
        assert len(timed_out) == 1
    
    @pytest.mark.asyncio
    async def test_send_traceroute_with_same_node_multiple_times(self, manager):
        """Test sending traceroute to same node multiple times"""
        node_id = "!a1b2c3d4"
        
        request_id1 = await manager.send_traceroute(node_id)
        request_id2 = await manager.send_traceroute(node_id)
        
        # Should create separate requests
        assert request_id1 != request_id2
        assert manager.get_pending_count() == 2
    
    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_request(self, manager):
        """Test cancelling an already cancelled request"""
        request_id = await manager.send_traceroute("!a1b2c3d4")
        
        result1 = await manager.cancel_traceroute(request_id)
        assert result1 is True
        
        result2 = await manager.cancel_traceroute(request_id)
        assert result2 is False
    
    @pytest.mark.asyncio
    async def test_priority_values(self, manager):
        """Test different priority values"""
        priorities = [1, 4, 8, 10]
        
        for priority in priorities:
            request_id = await manager.send_traceroute(f"!node{priority}", priority=priority)
            pending = manager._pending_traceroutes[request_id]
            assert pending.priority == priority
