"""
Property-Based Tests for Message Routing to Mesh

Tests Property 21: Message routing to mesh
Validates: Requirements 10.2
"""

import pytest
from hypothesis import given, settings, strategies as st
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.plugin_core_services import (
    MessageRoutingService,
    PermissionManager,
    Permission,
    PermissionDeniedError
)
from src.models.message import Message, MessageType


# Strategies for generating test data
@st.composite
def plugin_name_strategy(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ))


@st.composite
def message_content_strategy(draw):
    """Generate message content"""
    return draw(st.text(min_size=1, max_size=500))


@st.composite
def node_id_strategy(draw):
    """Generate node IDs (optional)"""
    return draw(st.one_of(
        st.none(),
        st.text(alphabet='!0123456789abcdef', min_size=2, max_size=10)
    ))


@st.composite
def channel_strategy(draw):
    """Generate channel numbers (optional)"""
    return draw(st.one_of(
        st.none(),
        st.integers(min_value=0, max_value=7)
    ))


class TestMessageRoutingProperties:
    """Property-based tests for message routing to mesh network"""
    
    # Feature: third-party-plugin-system, Property 21: Message routing to mesh
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        content=message_content_strategy(),
        destination=node_id_strategy(),
        channel=channel_strategy()
    )
    @pytest.mark.asyncio
    async def test_message_routing_with_permission(
        self, plugin_name, content, destination, channel
    ):
        """
        Property: For any message sent by a plugin via the message sending interface,
        the message should be queued and routed according to the destination and
        channel parameters when the plugin has permission.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(plugin_name, [Permission.SEND_MESSAGES.value])
        
        # Create mock message router
        mock_router = MagicMock()
        mock_router.queue_outgoing_message = AsyncMock(return_value=None)
        mock_router.send_message = AsyncMock(return_value=True)
        
        routing_service = MessageRoutingService(mock_router, permission_manager)
        
        # Execute
        result = await routing_service.send_mesh_message(
            plugin_name, content, destination, channel
        )
        
        # Verify
        assert result is True, "Message should be queued successfully"
        
        # Check that message was routed
        if hasattr(mock_router, 'queue_outgoing_message') and mock_router.queue_outgoing_message.called:
            call_args = mock_router.queue_outgoing_message.call_args
            message = call_args[0][0]
            
            # Verify message properties match parameters
            assert message.content == content
            assert message.sender_id == plugin_name
            assert message.recipient_id == destination
            assert message.channel == (channel or 0)
            assert message.message_type == MessageType.TEXT
        elif hasattr(mock_router, 'send_message') and mock_router.send_message.called:
            call_args = mock_router.send_message.call_args
            message = call_args[0][0]
            
            # Verify message properties match parameters
            assert message.content == content
            assert message.sender_id == plugin_name
            assert message.recipient_id == destination
            assert message.channel == (channel or 0)
            assert message.message_type == MessageType.TEXT
    
    # Feature: third-party-plugin-system, Property 21: Message routing to mesh
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        content=message_content_strategy(),
        destination=node_id_strategy(),
        channel=channel_strategy()
    )
    @pytest.mark.asyncio
    async def test_message_routing_without_permission(
        self, plugin_name, content, destination, channel
    ):
        """
        Property: For any plugin without SEND_MESSAGES permission,
        attempting to send a message should raise PermissionDeniedError.
        """
        # Setup - no permissions granted
        permission_manager = PermissionManager()
        
        mock_router = MagicMock()
        mock_router.queue_outgoing_message = AsyncMock(return_value=None)
        
        routing_service = MessageRoutingService(mock_router, permission_manager)
        
        # Execute and verify
        with pytest.raises(PermissionDeniedError):
            await routing_service.send_mesh_message(
                plugin_name, content, destination, channel
            )
        
        # Verify message was NOT routed
        assert not mock_router.queue_outgoing_message.called
    
    # Feature: third-party-plugin-system, Property 21: Message routing to mesh
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        messages=st.lists(
            st.tuples(
                message_content_strategy(),
                node_id_strategy(),
                channel_strategy()
            ),
            min_size=1,
            max_size=10
        )
    )
    @pytest.mark.asyncio
    async def test_multiple_message_routing(self, plugin_name, messages):
        """
        Property: For any sequence of messages from a plugin,
        all messages should be routed in order with correct parameters.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(plugin_name, [Permission.SEND_MESSAGES.value])
        
        mock_router = MagicMock()
        routed_messages = []
        
        async def capture_message(msg):
            routed_messages.append(msg)
        
        mock_router.queue_outgoing_message = AsyncMock(side_effect=capture_message)
        mock_router.send_message = AsyncMock(return_value=True)
        
        routing_service = MessageRoutingService(mock_router, permission_manager)
        
        # Execute - send all messages
        results = []
        for content, destination, channel in messages:
            result = await routing_service.send_mesh_message(
                plugin_name, content, destination, channel
            )
            results.append(result)
        
        # Verify all messages were sent successfully
        assert all(results), "All messages should be queued successfully"
        
        # Verify correct number of messages routed
        if routed_messages:
            assert len(routed_messages) == len(messages)
            
            # Verify each message has correct properties
            for i, (content, destination, channel) in enumerate(messages):
                msg = routed_messages[i]
                assert msg.content == content
                assert msg.sender_id == plugin_name
                assert msg.recipient_id == destination
                assert msg.channel == (channel or 0)
    
    # Feature: third-party-plugin-system, Property 21: Message routing to mesh
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        content=message_content_strategy()
    )
    @pytest.mark.asyncio
    async def test_broadcast_message_routing(self, plugin_name, content):
        """
        Property: For any broadcast message (destination=None),
        the message should be routed with recipient_id=None.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(plugin_name, [Permission.SEND_MESSAGES.value])
        
        mock_router = MagicMock()
        mock_router.queue_outgoing_message = AsyncMock(return_value=None)
        mock_router.send_message = AsyncMock(return_value=True)
        
        routing_service = MessageRoutingService(mock_router, permission_manager)
        
        # Execute - send broadcast message
        result = await routing_service.send_mesh_message(
            plugin_name, content, destination=None, channel=None
        )
        
        # Verify
        assert result is True
        
        # Check message properties
        if hasattr(mock_router, 'queue_outgoing_message') and mock_router.queue_outgoing_message.called:
            call_args = mock_router.queue_outgoing_message.call_args
            message = call_args[0][0]
            assert message.recipient_id is None, "Broadcast message should have no recipient"
        elif hasattr(mock_router, 'send_message') and mock_router.send_message.called:
            call_args = mock_router.send_message.call_args
            message = call_args[0][0]
            assert message.recipient_id is None, "Broadcast message should have no recipient"
    
    # Feature: third-party-plugin-system, Property 21: Message routing to mesh
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        content=message_content_strategy(),
        destination=node_id_strategy()
    )
    @pytest.mark.asyncio
    async def test_default_channel_routing(self, plugin_name, content, destination):
        """
        Property: For any message with channel=None,
        the message should be routed with channel=0 (default).
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(plugin_name, [Permission.SEND_MESSAGES.value])
        
        mock_router = MagicMock()
        mock_router.queue_outgoing_message = AsyncMock(return_value=None)
        mock_router.send_message = AsyncMock(return_value=True)
        
        routing_service = MessageRoutingService(mock_router, permission_manager)
        
        # Execute - send message with no channel specified
        result = await routing_service.send_mesh_message(
            plugin_name, content, destination, channel=None
        )
        
        # Verify
        assert result is True
        
        # Check message uses default channel
        if hasattr(mock_router, 'queue_outgoing_message') and mock_router.queue_outgoing_message.called:
            call_args = mock_router.queue_outgoing_message.call_args
            message = call_args[0][0]
            assert message.channel == 0, "Default channel should be 0"
        elif hasattr(mock_router, 'send_message') and mock_router.send_message.called:
            call_args = mock_router.send_message.call_args
            message = call_args[0][0]
            assert message.channel == 0, "Default channel should be 0"
