"""
Property-Based Tests for Traceroute Response Parsing

Tests Property 39: Traceroute Response Route Parsing
Tests Property 40: Traceroute Response Signal Parsing

Validates: Requirements 18.4, 18.5

**Validates: Requirements 18.4, 18.5**
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.traceroute_manager import TracerouteManager, TracerouteResult
from src.models.message import Message, MessageType, MessagePriority


# Strategy builders for generating test data

@composite
def valid_node_id(draw):
    """Generate valid Meshtastic node IDs"""
    # Meshtastic node IDs are typically in format !xxxxxxxx (8 hex chars)
    hex_chars = '0123456789abcdef'
    node_hex = ''.join(draw(st.lists(st.sampled_from(hex_chars), min_size=8, max_size=8)))
    return f"!{node_hex}"


@composite
def valid_snr_value(draw):
    """Generate valid SNR values (typically -20 to +20 dB)"""
    return draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False))


@composite
def valid_rssi_value(draw):
    """Generate valid RSSI values (typically -120 to -30 dBm)"""
    return draw(st.floats(min_value=-120.0, max_value=-30.0, allow_nan=False, allow_infinity=False))


@composite
def route_hop_dict(draw):
    """Generate a route hop as a dictionary with node_id, snr, and rssi"""
    return {
        'node_id': draw(valid_node_id()),
        'snr': draw(valid_snr_value()),
        'rssi': draw(valid_rssi_value())
    }


@composite
def route_hop_dict_optional_signals(draw):
    """Generate a route hop with optional SNR/RSSI values"""
    hop = {'node_id': draw(valid_node_id())}
    
    # Randomly include or exclude SNR
    if draw(st.booleans()):
        hop['snr'] = draw(valid_snr_value())
    
    # Randomly include or exclude RSSI
    if draw(st.booleans()):
        hop['rssi'] = draw(valid_rssi_value())
    
    return hop


@composite
def route_array_dicts(draw):
    """Generate a route array with dictionary hops"""
    num_hops = draw(st.integers(min_value=1, max_value=10))
    return draw(st.lists(route_hop_dict(), min_size=num_hops, max_size=num_hops))


@composite
def route_array_strings(draw):
    """Generate a route array with string node IDs only"""
    num_hops = draw(st.integers(min_value=1, max_value=10))
    return draw(st.lists(valid_node_id(), min_size=num_hops, max_size=num_hops))


@composite
def route_array_mixed(draw):
    """Generate a route array with mixed dict and string hops"""
    num_hops = draw(st.integers(min_value=2, max_value=10))
    route = []
    for _ in range(num_hops):
        if draw(st.booleans()):
            route.append(draw(route_hop_dict()))
        else:
            route.append(draw(valid_node_id()))
    return route


def create_traceroute_response_message(route_data, request_id=None, sender_id=None):
    """Create a traceroute response message from route data"""
    if request_id is None:
        request_id = f"req-{hash(str(route_data)) % 10000}"
    if sender_id is None:
        sender_id = "!test1234"
    
    message = Message(
        id=f"msg-{hash(str(route_data)) % 10000}",
        sender_id=sender_id,
        message_type=MessageType.ROUTING,
        content="",
        metadata={
            'traceroute': True,
            'route': route_data,
            'request_id': request_id
        }
    )
    
    return message


# Property Tests

class TestTracerouteResponseRouteParsingProperty:
    """
    Feature: network-traceroute-mapper, Property 39: Traceroute Response Route Parsing
    
    Tests that for any traceroute response received, the system correctly parses
    the route array to extract the list of node IDs in the path.
    
    **Validates: Requirements 18.4**
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_dicts())
    @pytest.mark.asyncio
    async def test_parse_route_from_dict_format(self, route_data):
        """
        Property: For any traceroute response with route data in dictionary format,
        the system should correctly extract all node IDs in order.
        
        **Validates: Requirements 18.4**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a traceroute response message
        message = create_traceroute_response_message(route_data)
        
        # Parse the route
        parsed_route = manager.parse_route_from_response(message)
        
        # Extract expected node IDs from route_data
        expected_route = [hop['node_id'] for hop in route_data]
        
        # Verify the parsed route matches expected
        assert len(parsed_route) == len(expected_route), (
            f"Parsed route length {len(parsed_route)} should match "
            f"expected length {len(expected_route)}"
        )
        
        for i, (parsed_node, expected_node) in enumerate(zip(parsed_route, expected_route)):
            assert parsed_node == expected_node, (
                f"Node at position {i} should be {expected_node}, got {parsed_node}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_strings())
    @pytest.mark.asyncio
    async def test_parse_route_from_string_format(self, route_data):
        """
        Property: For any traceroute response with route data as simple strings,
        the system should correctly extract all node IDs in order.
        
        **Validates: Requirements 18.4**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a traceroute response message with string route
        message = create_traceroute_response_message(route_data)
        
        # Parse the route
        parsed_route = manager.parse_route_from_response(message)
        
        # Verify the parsed route matches expected
        assert len(parsed_route) == len(route_data), (
            f"Parsed route length {len(parsed_route)} should match "
            f"expected length {len(route_data)}"
        )
        
        for i, (parsed_node, expected_node) in enumerate(zip(parsed_route, route_data)):
            assert parsed_node == expected_node, (
                f"Node at position {i} should be {expected_node}, got {parsed_node}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_mixed())
    @pytest.mark.asyncio
    async def test_parse_route_from_mixed_format(self, route_data):
        """
        Property: For any traceroute response with mixed route data (some dicts,
        some strings), the system should correctly extract all node IDs in order.
        
        **Validates: Requirements 18.4**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a traceroute response message
        message = create_traceroute_response_message(route_data)
        
        # Parse the route
        parsed_route = manager.parse_route_from_response(message)
        
        # Extract expected node IDs from route_data
        expected_route = []
        for hop in route_data:
            if isinstance(hop, dict):
                expected_route.append(hop['node_id'])
            else:
                expected_route.append(hop)
        
        # Verify the parsed route matches expected
        assert len(parsed_route) == len(expected_route), (
            f"Parsed route length {len(parsed_route)} should match "
            f"expected length {len(expected_route)}"
        )
        
        for i, (parsed_node, expected_node) in enumerate(zip(parsed_route, expected_route)):
            assert parsed_node == expected_node, (
                f"Node at position {i} should be {expected_node}, got {parsed_node}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        route_data=st.lists(route_hop_dict_optional_signals(), min_size=1, max_size=10)
    )
    @pytest.mark.asyncio
    async def test_parse_route_with_missing_node_ids(self, route_data):
        """
        Property: For any traceroute response where some hops are missing node_id,
        the system should skip those hops and only include valid node IDs.
        
        **Validates: Requirements 18.4**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Randomly remove some node_ids
        modified_route = []
        expected_nodes = []
        for hop in route_data:
            hop_copy = hop.copy()
            # Keep node_id for half, remove for half
            if len(expected_nodes) < len(route_data) // 2:
                # Keep the node_id
                modified_route.append(hop_copy)
                expected_nodes.append(hop_copy['node_id'])
            else:
                # Remove the node_id
                hop_copy.pop('node_id', None)
                if hop_copy:  # Only add if there's still data
                    modified_route.append(hop_copy)
        
        # Create message
        message = create_traceroute_response_message(modified_route)
        
        # Parse the route
        parsed_route = manager.parse_route_from_response(message)
        
        # Verify only valid node IDs are included
        assert len(parsed_route) == len(expected_nodes), (
            f"Parsed route should only include hops with node_id: "
            f"expected {len(expected_nodes)}, got {len(parsed_route)}"
        )
        
        for i, (parsed_node, expected_node) in enumerate(zip(parsed_route, expected_nodes)):
            assert parsed_node == expected_node, (
                f"Node at position {i} should be {expected_node}, got {parsed_node}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(num_hops=st.integers(min_value=1, max_value=20))
    @pytest.mark.asyncio
    async def test_route_length_preserved(self, num_hops):
        """
        Property: For any traceroute response with N hops, the parsed route
        should contain exactly N node IDs.
        
        **Validates: Requirements 18.4**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Generate route with specific number of hops
        route_data = [
            {
                'node_id': f"!{i:08x}",
                'snr': float(i),
                'rssi': float(-50 - i)
            }
            for i in range(num_hops)
        ]
        
        # Create message
        message = create_traceroute_response_message(route_data)
        
        # Parse the route
        parsed_route = manager.parse_route_from_response(message)
        
        # Verify length is preserved
        assert len(parsed_route) == num_hops, (
            f"Parsed route should have {num_hops} hops, got {len(parsed_route)}"
        )


class TestTracerouteResponseSignalParsingProperty:
    """
    Feature: network-traceroute-mapper, Property 40: Traceroute Response Signal Parsing
    
    Tests that for any traceroute response received, the system correctly extracts
    SNR and RSSI values for each hop in the route.
    
    **Validates: Requirements 18.5**
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_dicts())
    @pytest.mark.asyncio
    async def test_parse_signal_values_from_dict_format(self, route_data):
        """
        Property: For any traceroute response with route data in dictionary format
        containing SNR and RSSI values, the system should correctly extract all
        signal values in order.
        
        **Validates: Requirements 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a traceroute response message
        message = create_traceroute_response_message(route_data)
        
        # Parse signal values
        snr_values, rssi_values = manager.parse_signal_values_from_response(message)
        
        # Extract expected values from route_data
        expected_snr = [hop['snr'] for hop in route_data]
        expected_rssi = [hop['rssi'] for hop in route_data]
        
        # Verify SNR values
        assert len(snr_values) == len(expected_snr), (
            f"SNR values length {len(snr_values)} should match "
            f"expected length {len(expected_snr)}"
        )
        
        for i, (parsed_snr, expected_snr_val) in enumerate(zip(snr_values, expected_snr)):
            assert abs(parsed_snr - expected_snr_val) < 0.01, (
                f"SNR at position {i} should be {expected_snr_val}, got {parsed_snr}"
            )
        
        # Verify RSSI values
        assert len(rssi_values) == len(expected_rssi), (
            f"RSSI values length {len(rssi_values)} should match "
            f"expected length {len(expected_rssi)}"
        )
        
        for i, (parsed_rssi, expected_rssi_val) in enumerate(zip(rssi_values, expected_rssi)):
            assert abs(parsed_rssi - expected_rssi_val) < 0.01, (
                f"RSSI at position {i} should be {expected_rssi_val}, got {parsed_rssi}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_strings())
    @pytest.mark.asyncio
    async def test_parse_signal_values_from_string_format(self, route_data):
        """
        Property: For any traceroute response with route data as simple strings
        (no signal data), the system should return zero values for SNR and RSSI.
        
        **Validates: Requirements 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a traceroute response message with string route
        message = create_traceroute_response_message(route_data)
        
        # Parse signal values
        snr_values, rssi_values = manager.parse_signal_values_from_response(message)
        
        # Verify all values are 0.0 (no signal data available)
        assert len(snr_values) == len(route_data), (
            f"SNR values length should match route length {len(route_data)}"
        )
        assert len(rssi_values) == len(route_data), (
            f"RSSI values length should match route length {len(route_data)}"
        )
        
        for i, snr in enumerate(snr_values):
            assert snr == 0.0, (
                f"SNR at position {i} should be 0.0 (no data), got {snr}"
            )
        
        for i, rssi in enumerate(rssi_values):
            assert rssi == 0.0, (
                f"RSSI at position {i} should be 0.0 (no data), got {rssi}"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        route_data=st.lists(route_hop_dict_optional_signals(), min_size=1, max_size=10)
    )
    @pytest.mark.asyncio
    async def test_parse_signal_values_with_missing_data(self, route_data):
        """
        Property: For any traceroute response where some hops are missing SNR or
        RSSI values, the system should use 0.0 for missing values.
        
        **Validates: Requirements 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create message
        message = create_traceroute_response_message(route_data)
        
        # Parse signal values
        snr_values, rssi_values = manager.parse_signal_values_from_response(message)
        
        # Verify lengths match
        assert len(snr_values) == len(route_data), (
            f"SNR values length should match route length {len(route_data)}"
        )
        assert len(rssi_values) == len(route_data), (
            f"RSSI values length should match route length {len(route_data)}"
        )
        
        # Verify values match expected (0.0 for missing)
        for i, hop in enumerate(route_data):
            expected_snr = hop.get('snr', 0.0)
            expected_rssi = hop.get('rssi', 0.0)
            
            if expected_snr == 0.0:
                assert snr_values[i] == 0.0, (
                    f"Missing SNR at position {i} should be 0.0, got {snr_values[i]}"
                )
            else:
                assert abs(snr_values[i] - expected_snr) < 0.01, (
                    f"SNR at position {i} should be {expected_snr}, got {snr_values[i]}"
                )
            
            if expected_rssi == 0.0:
                assert rssi_values[i] == 0.0, (
                    f"Missing RSSI at position {i} should be 0.0, got {rssi_values[i]}"
                )
            else:
                assert abs(rssi_values[i] - expected_rssi) < 0.01, (
                    f"RSSI at position {i} should be {expected_rssi}, got {rssi_values[i]}"
                )
    
    @settings(max_examples=10, deadline=5000)
    @given(num_hops=st.integers(min_value=1, max_value=20))
    @pytest.mark.asyncio
    async def test_signal_values_length_matches_route_length(self, num_hops):
        """
        Property: For any traceroute response with N hops, the SNR and RSSI
        value lists should each contain exactly N values.
        
        **Validates: Requirements 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Generate route with specific number of hops
        route_data = [
            {
                'node_id': f"!{i:08x}",
                'snr': float(i),
                'rssi': float(-50 - i)
            }
            for i in range(num_hops)
        ]
        
        # Create message
        message = create_traceroute_response_message(route_data)
        
        # Parse signal values
        snr_values, rssi_values = manager.parse_signal_values_from_response(message)
        
        # Verify lengths match
        assert len(snr_values) == num_hops, (
            f"SNR values should have {num_hops} entries, got {len(snr_values)}"
        )
        assert len(rssi_values) == num_hops, (
            f"RSSI values should have {num_hops} entries, got {len(rssi_values)}"
        )


class TestTracerouteResponseHandlingIntegration:
    """
    Integration tests for complete response handling
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_dicts())
    @pytest.mark.asyncio
    async def test_handle_response_creates_result_with_correct_data(self, route_data):
        """
        Property: For any traceroute response, handle_traceroute_response should
        create a TracerouteResult with correctly parsed route and signal data.
        
        **Validates: Requirements 18.4, 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a pending traceroute first
        target_node = route_data[-1]['node_id'] if route_data else "!test1234"
        request_id = await manager.send_traceroute(target_node)
        
        # Create a response message
        message = Message(
            id=f"msg-response",
            sender_id=target_node,
            message_type=MessageType.ROUTING,
            content="",
            metadata={
                'traceroute': True,
                'route': route_data,
                'request_id': request_id
            }
        )
        
        # Handle the response
        result = await manager.handle_traceroute_response(message)
        
        # Verify result was created
        assert result is not None, "Result should be created for valid response"
        
        # Verify route was parsed correctly
        expected_route = [hop['node_id'] for hop in route_data]
        assert result.route == expected_route, (
            f"Result route should match expected: {expected_route}"
        )
        
        # Verify signal values were parsed correctly
        expected_snr = [hop['snr'] for hop in route_data]
        expected_rssi = [hop['rssi'] for hop in route_data]
        
        assert len(result.snr_values) == len(expected_snr), (
            f"Result SNR values length should match expected"
        )
        assert len(result.rssi_values) == len(expected_rssi), (
            f"Result RSSI values length should match expected"
        )
        
        # Verify hop count
        assert result.hop_count == len(route_data), (
            f"Result hop_count should be {len(route_data)}, got {result.hop_count}"
        )
        
        # Verify success flag
        assert result.success is True, "Result should be marked as successful"
        
        # Verify target node
        assert result.node_id == target_node, (
            f"Result node_id should be {target_node}, got {result.node_id}"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_dicts())
    @pytest.mark.asyncio
    async def test_handle_response_removes_pending_request(self, route_data):
        """
        Property: For any traceroute response, handle_traceroute_response should
        remove the corresponding pending request.
        
        **Validates: Requirements 18.4, 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Create a pending traceroute
        target_node = route_data[-1]['node_id'] if route_data else "!test1234"
        request_id = await manager.send_traceroute(target_node)
        
        # Verify it's pending
        assert manager.is_pending(request_id), "Request should be pending before response"
        
        # Create and handle response
        message = Message(
            id=f"msg-response",
            sender_id=target_node,
            message_type=MessageType.ROUTING,
            content="",
            metadata={
                'traceroute': True,
                'route': route_data,
                'request_id': request_id
            }
        )
        
        result = await manager.handle_traceroute_response(message)
        
        # Verify it's no longer pending
        assert not manager.is_pending(request_id), (
            "Request should not be pending after response"
        )
        assert result is not None, "Result should be created"
    
    @settings(max_examples=10, deadline=5000)
    @given(route_data=route_array_dicts())
    @pytest.mark.asyncio
    async def test_handle_response_updates_statistics(self, route_data):
        """
        Property: For any traceroute response, handle_traceroute_response should
        update the responses_received statistic.
        
        **Validates: Requirements 18.4, 18.5**
        """
        # Create manager
        manager = TracerouteManager(max_hops=7, timeout_seconds=60, max_retries=3)
        
        # Get initial statistics
        initial_stats = manager.get_statistics()
        initial_responses = initial_stats['responses_received']
        
        # Create a pending traceroute
        target_node = route_data[-1]['node_id'] if route_data else "!test1234"
        request_id = await manager.send_traceroute(target_node)
        
        # Create and handle response
        message = Message(
            id=f"msg-response",
            sender_id=target_node,
            message_type=MessageType.ROUTING,
            content="",
            metadata={
                'traceroute': True,
                'route': route_data,
                'request_id': request_id
            }
        )
        
        result = await manager.handle_traceroute_response(message)
        
        # Get updated statistics
        updated_stats = manager.get_statistics()
        
        # Verify statistics were updated
        assert updated_stats['responses_received'] == initial_responses + 1, (
            f"responses_received should increase by 1, "
            f"was {initial_responses}, now {updated_stats['responses_received']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
