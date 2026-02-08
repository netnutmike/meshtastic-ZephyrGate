"""
Property-Based Tests for Traceroute Request Forwarding

Tests Properties:
- Property 12: Traceroute Request Forwarding
- Property 14: Meshtastic Message Format Compliance

Validates Requirements:
- 7.1: Forward traceroute requests to message router
- 7.3: Use standard Meshtastic message format
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings, assume

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from models.message import Message, MessageType, MessagePriority
from plugins.traceroute_mapper.plugin import TracerouteMapperPlugin
from plugins.traceroute_mapper.priority_queue import TracerouteRequest


# Strategy for generating valid node IDs
node_id_strategy = st.builds(
    lambda suffix: f"!{suffix}",
    suffix=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=4,
        max_size=11
    )
)

# Strategy for generating priorities (1-10)
priority_strategy = st.integers(min_value=1, max_value=10)

# Strategy for generating reasons
reason_strategy = st.sampled_from([
    'new_indirect_node',
    'node_back_online',
    'periodic_recheck',
    'manual_request',
    'topology_change'
])


@pytest.mark.asyncio
@given(
    node_id=node_id_strategy,
    priority=priority_strategy,
    reason=reason_strategy
)
@settings(max_examples=10, deadline=2000)
async def test_property_12_traceroute_request_forwarding(node_id, priority, reason):
    """
    Property 12: Traceroute Request Forwarding
    
    For any traceroute request sent by the Traceroute_Mapper, the message
    should be forwarded to the Message_Router for normal message processing
    (including MQTT publishing).
    
    Validates: Requirements 7.1
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
        'log_traceroute_requests': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute request
    request = TracerouteRequest(
        request_id='test-request',
        node_id=node_id,
        priority=priority,
        reason=reason,
        queued_at=datetime.utcnow(),
        retry_count=0
    )
    
    # Send the traceroute request
    await plugin._send_traceroute_request(request)
    
    # Property: Message should be forwarded to message router
    # Verify send_message was called
    assert message_router.send_message.called, \
        f"Message router send_message should be called for traceroute to {node_id}"
    
    # Get the message that was sent
    call_args = message_router.send_message.call_args
    assert call_args is not None, "send_message should have been called with arguments"
    
    sent_message = call_args[0][0]  # First positional argument
    
    # Verify the message was sent to the correct node
    assert sent_message.recipient_id == node_id, \
        f"Message should be sent to {node_id}, got {sent_message.recipient_id}"


@pytest.mark.asyncio
@given(
    node_id=node_id_strategy,
    max_hops=st.integers(min_value=1, max_value=15)
)
@settings(max_examples=10, deadline=2000)
async def test_property_14_meshtastic_message_format_compliance(node_id, max_hops):
    """
    Property 14: Meshtastic Message Format Compliance
    
    For any traceroute message forwarded to the Message_Router, the message
    should be a valid Meshtastic Message object with all required fields
    (sender_id, recipient_id, message_type, content, metadata).
    
    Validates: Requirements 7.3
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
        'max_hops': max_hops,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_requests': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute request
    request = TracerouteRequest(
        request_id='test-request',
        node_id=node_id,
        priority=5,
        reason='test',
        queued_at=datetime.utcnow(),
        retry_count=0
    )
    
    # Send the traceroute request
    await plugin._send_traceroute_request(request)
    
    # Get the message that was sent
    call_args = message_router.send_message.call_args
    assert call_args is not None, "send_message should have been called"
    
    sent_message = call_args[0][0]
    
    # Property: Message should be a valid Meshtastic Message object
    assert isinstance(sent_message, Message), \
        f"Forwarded message should be a Message object, got {type(sent_message)}"
    
    # Verify required fields are present
    assert sent_message.recipient_id is not None, \
        "Message should have recipient_id"
    assert sent_message.recipient_id == node_id, \
        f"Message recipient_id should be {node_id}, got {sent_message.recipient_id}"
    
    assert sent_message.message_type is not None, \
        "Message should have message_type"
    assert sent_message.message_type == MessageType.ROUTING, \
        f"Traceroute message should use MessageType.ROUTING, got {sent_message.message_type}"
    
    assert sent_message.content is not None, \
        "Message should have content field (even if empty)"
    
    assert sent_message.metadata is not None, \
        "Message should have metadata"
    assert isinstance(sent_message.metadata, dict), \
        f"Message metadata should be a dict, got {type(sent_message.metadata)}"
    
    # Verify traceroute-specific metadata
    assert sent_message.metadata.get('want_response') is True, \
        "Traceroute message should have want_response=True in metadata"
    
    assert sent_message.metadata.get('route_discovery') is True, \
        "Traceroute message should have route_discovery=True in metadata"
    
    assert sent_message.metadata.get('traceroute') is True, \
        "Traceroute message should have traceroute=True in metadata"
    
    assert 'request_id' in sent_message.metadata, \
        "Traceroute message should have request_id in metadata"
    
    # Verify hop_limit is set correctly
    assert sent_message.hop_limit is not None, \
        "Message should have hop_limit"
    assert sent_message.hop_limit == max_hops, \
        f"Message hop_limit should be {max_hops}, got {sent_message.hop_limit}"


@pytest.mark.asyncio
@given(
    node_ids=st.lists(node_id_strategy, min_size=1, max_size=10, unique=True),
    priorities=st.lists(priority_strategy, min_size=1, max_size=10)
)
@settings(max_examples=10, deadline=3000)
async def test_property_12_multiple_requests_forwarded(node_ids, priorities):
    """
    Property 12: Multiple Traceroute Requests Forwarding
    
    For any sequence of traceroute requests sent by the Traceroute_Mapper,
    all messages should be forwarded to the Message_Router.
    
    Validates: Requirements 7.1
    """
    # Ensure we have matching priorities for each node
    assume(len(priorities) >= len(node_ids))
    priorities = priorities[:len(node_ids)]
    
    # Create mock plugin manager with message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=True)
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 60,  # Max allowed rate
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_requests': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Send multiple traceroute requests
    for node_id, priority in zip(node_ids, priorities):
        request = TracerouteRequest(
            request_id=f'test-request-{node_id}',
            node_id=node_id,
            priority=priority,
            reason='test',
            queued_at=datetime.utcnow(),
            retry_count=0
        )
        
        await plugin._send_traceroute_request(request)
    
    # Property: All messages should be forwarded to message router
    assert message_router.send_message.call_count == len(node_ids), \
        f"Message router should be called {len(node_ids)} times, got {message_router.send_message.call_count}"
    
    # Verify each node was sent a message
    sent_node_ids = set()
    for call in message_router.send_message.call_args_list:
        sent_message = call[0][0]
        sent_node_ids.add(sent_message.recipient_id)
    
    assert sent_node_ids == set(node_ids), \
        f"All nodes should receive traceroute requests. Expected {set(node_ids)}, got {sent_node_ids}"


@pytest.mark.asyncio
async def test_property_12_forwarding_failure_handling():
    """
    Property 12: Traceroute Request Forwarding Failure Handling
    
    When message router send_message fails, the plugin should handle the
    error gracefully and record the failure.
    
    Validates: Requirements 7.1
    """
    # Create mock plugin manager with failing message router
    plugin_manager = Mock()
    message_router = Mock()
    message_router.send_message = AsyncMock(return_value=False)  # Simulate failure
    plugin_manager.message_router = message_router
    
    # Create plugin with minimal config
    config = {
        'enabled': True,
        'traceroutes_per_minute': 10,
        'max_hops': 7,
        'timeout_seconds': 60,
        'max_retries': 3,
        'forward_to_mqtt': True,
        'log_traceroute_requests': False
    }
    
    plugin = TracerouteMapperPlugin('traceroute_mapper', config, plugin_manager)
    
    # Initialize plugin components
    await plugin.initialize()
    
    # Create a traceroute request
    request = TracerouteRequest(
        request_id='test-request',
        node_id='!test123',
        priority=5,
        reason='test',
        queued_at=datetime.utcnow(),
        retry_count=0
    )
    
    # Send the traceroute request
    await plugin._send_traceroute_request(request)
    
    # Property: Plugin should handle failure gracefully
    # Verify send_message was called
    assert message_router.send_message.called, \
        "Message router send_message should be called even if it fails"
    
    # Verify failure was recorded in statistics
    assert plugin.stats['traceroutes_failed'] > 0, \
        "Failed traceroute should be recorded in statistics"
    
    # Verify traceroute was NOT counted as sent
    assert plugin.stats['traceroutes_sent'] == 0, \
        "Failed traceroute should not be counted as sent"
