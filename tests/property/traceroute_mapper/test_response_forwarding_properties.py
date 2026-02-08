"""
Property-Based Tests for Traceroute Response Forwarding

Tests Properties:
- Property 13: Traceroute Response Forwarding
- Property 34: All Traceroute Messages Forwarded
- Property 35: Traceroute Message Field Preservation

Validates Requirements:
- 7.2: Forward traceroute responses to message router
- 14.1: Forward all traceroute messages for MQTT publishing
- 14.4: Preserve all message fields including route array
- 14.5: Forward responses from other nodes as well
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from models.message import Message, MessageType, MessagePriority
from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin


# Strategy for generating valid node IDs
node_id_strategy = st.builds(
    lambda suffix: f"!{suffix}",
    suffix=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=4,
        max_size=11
    )
)

# Strategy for generating route arrays
route_strategy = st.lists(
    st.dictionaries(
        keys=st.sampled_from(['node_id', 'snr', 'rssi']),
        values=st.one_of(
            node_id_strategy,
            st.floats(min_value=-30.0, max_value=20.0),
            st.floats(min_value=-120.0, max_value=-30.0)
        )
    ),
    min_size=1,
    max_size=7
)


@pytest.mark.asyncio
@given(
    sender_id=node_id_strategy,
    route=route_strategy
)
@settings(max_examples=10, deadline=2000)
async def test_property_13_traceroute_response_forwarding(sender_id, route):
    """
    Property 13: Traceroute Response Forwarding
    
    For any traceroute response received from the mesh, the message should
    be forwarded to the Message_Router for normal message processing
    (including MQTT publishing).
    
    Validates: Requirements 7.2
    """
    # Create mock plugin manager with message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 10,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_responses': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute response message
    response_message = Message(
        id='response-123',
        sender_id=sender_id,
        message_type=MessageType.ROUTING,
        content='',
        metadata={
            'traceroute': True,
            'route': route,
            'request_id': 'test-request-123'
        }
    )
    
    # Handle the traceroute response
    await plugin._handle_traceroute_response(response_message)
    
    # Property: Message should be forwarded to message router
    assert message_router.send_message.called, \
        f"Message router send_message should be called for traceroute response from {sender_id}"
    
    # Get the message that was forwarded
    call_args = message_router.send_message.call_args
    assert call_args is not None, "send_message should have been called with arguments"
    
    forwarded_message = call_args[0][0]
    
    # Verify the same message was forwarded
    assert forwarded_message.id == response_message.id, \
        f"Forwarded message ID should match original: {response_message.id}"
    assert forwarded_message.sender_id == sender_id, \
        f"Forwarded message sender should be {sender_id}"


@pytest.mark.asyncio
@given(
    sender_id=node_id_strategy,
    route=route_strategy
)
@settings(max_examples=10, deadline=2000)
async def test_property_34_all_traceroute_messages_forwarded(sender_id, route):
    """
    Property 34: All Traceroute Messages Forwarded
    
    For any traceroute message (sent by us or received from other nodes),
    the message should be forwarded to the Message_Router for normal processing.
    
    This test verifies that responses from OTHER nodes (not our requests) are
    also forwarded.
    
    Validates: Requirements 14.1, 14.5
    """
    # Create mock plugin manager with message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 10,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_responses': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute response from ANOTHER node (not our request)
    # This simulates receiving a traceroute response that was NOT initiated by us
    response_message = Message(
        id='other-node-response-123',
        sender_id=sender_id,
        message_type=MessageType.ROUTING,
        content='',
        metadata={
            'traceroute': True,
            'route': route,
            # No request_id or different request_id - this is from another node
            'request_id': 'unknown-request-456'
        }
    )
    
    # Handle the traceroute response
    await plugin._handle_traceroute_response(response_message)
    
    # Property: Message should STILL be forwarded even though it's not our request
    assert message_router.send_message.called, \
        f"Message router should forward traceroute responses from other nodes (sender={sender_id})"
    
    # Verify the message was forwarded
    call_args = message_router.send_message.call_args
    forwarded_message = call_args[0][0]
    
    assert forwarded_message.sender_id == sender_id, \
        f"Should forward responses from other nodes: {sender_id}"


@pytest.mark.asyncio
@given(
    sender_id=node_id_strategy,
    route=route_strategy
)
@settings(max_examples=10, deadline=2000)
async def test_property_35_traceroute_message_field_preservation(sender_id, route):
    """
    Property 35: Traceroute Message Field Preservation
    
    For any traceroute message forwarded, all Meshtastic protobuf fields
    should be preserved, including the route array with SNR/RSSI values
    for each hop.
    
    Validates: Requirements 14.4
    """
    # Create mock plugin manager with message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 10,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_responses': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute response with full metadata
    original_metadata = {
        'traceroute': True,
        'route': route,
        'request_id': 'test-request-789',
        'custom_field': 'custom_value'  # Additional field to test preservation
    }
    
    response_message = Message(
        id='response-789',
        sender_id=sender_id,
        recipient_id='!gateway',
        message_type=MessageType.ROUTING,
        content='',
        hop_count=3,
        snr=5.2,
        rssi=-85,
        metadata=original_metadata
    )
    
    # Handle the traceroute response
    await plugin._handle_traceroute_response(response_message)
    
    # Get the forwarded message
    call_args = message_router.send_message.call_args
    forwarded_message = call_args[0][0]
    
    # Property: All message fields should be preserved
    assert forwarded_message.id == response_message.id, \
        "Message ID should be preserved"
    
    assert forwarded_message.sender_id == response_message.sender_id, \
        "Sender ID should be preserved"
    
    assert forwarded_message.recipient_id == response_message.recipient_id, \
        "Recipient ID should be preserved"
    
    assert forwarded_message.message_type == response_message.message_type, \
        "Message type should be preserved"
    
    assert forwarded_message.hop_count == response_message.hop_count, \
        "Hop count should be preserved"
    
    assert forwarded_message.snr == response_message.snr, \
        "SNR should be preserved"
    
    assert forwarded_message.rssi == response_message.rssi, \
        "RSSI should be preserved"
    
    # Verify metadata is preserved
    assert forwarded_message.metadata is not None, \
        "Metadata should be preserved"
    
    assert forwarded_message.metadata.get('traceroute') == True, \
        "Traceroute flag should be preserved in metadata"
    
    assert forwarded_message.metadata.get('route') == route, \
        "Route array should be preserved in metadata"
    
    assert forwarded_message.metadata.get('request_id') == 'test-request-789', \
        "Request ID should be preserved in metadata"
    
    assert forwarded_message.metadata.get('custom_field') == 'custom_value', \
        "Custom metadata fields should be preserved"


@pytest.mark.asyncio
@given(
    sender_ids=st.lists(node_id_strategy, min_size=2, max_size=5, unique=True),
    routes=st.lists(route_strategy, min_size=2, max_size=5)
)
@settings(max_examples=10, deadline=3000)
async def test_property_34_multiple_responses_forwarded(sender_ids, routes):
    """
    Property 34: Multiple Traceroute Responses Forwarded
    
    For any sequence of traceroute responses received, all messages should
    be forwarded to the Message_Router.
    
    Validates: Requirements 14.1, 14.5
    """
    # Ensure we have matching routes for each sender
    if len(routes) < len(sender_ids):
        routes = routes * ((len(sender_ids) // len(routes)) + 1)
    routes = routes[:len(sender_ids)]
    
    # Create mock plugin manager with message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 60,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_responses': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Send multiple traceroute responses
    for sender_id, route in zip(sender_ids, routes):
        response_message = Message(
            id=f'response-{sender_id}',
            sender_id=sender_id,
            message_type=MessageType.ROUTING,
            content='',
            metadata={
                'traceroute': True,
                'route': route,
                'request_id': f'request-{sender_id}'
            }
        )
        
        await plugin._handle_traceroute_response(response_message)
    
    # Property: All responses should be forwarded
    assert message_router.send_message.call_count == len(sender_ids), \
        f"All {len(sender_ids)} responses should be forwarded, got {message_router.send_message.call_count}"
    
    # Verify each sender's response was forwarded
    forwarded_senders = set()
    for call in message_router.send_message.call_args_list:
        forwarded_message = call[0][0]
        forwarded_senders.add(forwarded_message.sender_id)
    
    assert forwarded_senders == set(sender_ids), \
        f"All senders should have responses forwarded. Expected {set(sender_ids)}, got {forwarded_senders}"
