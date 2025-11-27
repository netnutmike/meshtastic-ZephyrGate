"""
Property-Based Tests for Inter-Plugin Messaging

Tests Property 23: Inter-plugin messaging
Validates: Requirements 10.4
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock

from src.core.plugin_core_services import (
    InterPluginMessaging,
    PermissionManager,
    Permission,
    PermissionDeniedError
)
from src.core.plugin_interfaces import PluginMessage, PluginMessageType, PluginResponse


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
def message_type_strategy(draw):
    """Generate message types"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ))


@st.composite
def message_data_strategy(draw):
    """Generate message data"""
    return draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=200),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
            max_size=5
        )
    ))


class TestInterPluginMessagingProperties:
    """Property-based tests for inter-plugin messaging"""
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=message_type_strategy(),
        data=message_data_strategy()
    )
    @pytest.mark.asyncio
    async def test_inter_plugin_message_delivery(
        self, source_plugin, target_plugin, message_type, data
    ):
        """
        Property: For any message sent from one plugin to another via the
        inter-plugin messaging mechanism, the message should be delivered
        to the target plugin's message handler when both plugins have permission.
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register handler for target plugin
        received_messages = []
        
        async def target_handler(message: PluginMessage):
            received_messages.append(message)
            return {"status": "received", "data": message.data}
        
        inter_plugin.register_message_handler(target_plugin, target_handler)
        
        # Execute
        response = await inter_plugin.send_to_plugin(
            source_plugin, target_plugin, message_type, data
        )
        
        # Verify message was delivered
        assert len(received_messages) == 1, "Message should be delivered to target handler"
        
        delivered_message = received_messages[0]
        assert delivered_message.source_plugin == source_plugin
        assert delivered_message.target_plugin == target_plugin
        assert delivered_message.data == data
        assert delivered_message.metadata.get('message_type') == message_type
        assert delivered_message.type == PluginMessageType.DIRECT_MESSAGE
        
        # Verify response
        assert response is not None
        assert response.success is True
        assert response.data == {"status": "received", "data": data}
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=message_type_strategy(),
        data=message_data_strategy()
    )
    @pytest.mark.asyncio
    async def test_inter_plugin_messaging_without_permission(
        self, source_plugin, target_plugin, message_type, data
    ):
        """
        Property: For any plugin without INTER_PLUGIN_MESSAGING permission,
        attempting to send a message to another plugin should raise PermissionDeniedError.
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup - no permissions granted
        permission_manager = PermissionManager()
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register handler for target plugin
        async def target_handler(message: PluginMessage):
            return {"status": "received"}
        
        inter_plugin.register_message_handler(target_plugin, target_handler)
        
        # Execute and verify
        with pytest.raises(PermissionDeniedError):
            await inter_plugin.send_to_plugin(
                source_plugin, target_plugin, message_type, data
            )
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugins=st.lists(plugin_name_strategy(), min_size=2, max_size=5, unique=True),
        message_type=message_type_strategy(),
        data=message_data_strategy()
    )
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_plugins(
        self, source_plugin, target_plugins, message_type, data
    ):
        """
        Property: For any broadcast message, all registered plugins
        (except the sender) should receive the message.
        """
        # Ensure source is not in target list
        target_plugins = [p for p in target_plugins if p != source_plugin]
        if not target_plugins:
            target_plugins = ["plugin1", "plugin2"]
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register handlers for all target plugins
        received_by_plugin = {}
        
        for target in target_plugins:
            received_by_plugin[target] = []
            
            async def make_handler(plugin_name):
                async def handler(message: PluginMessage):
                    received_by_plugin[plugin_name].append(message)
                    return {"plugin": plugin_name, "received": True}
                return handler
            
            handler = await make_handler(target)
            inter_plugin.register_message_handler(target, handler)
        
        # Execute broadcast
        responses = await inter_plugin.broadcast_to_plugins(
            source_plugin, message_type, data
        )
        
        # Verify all target plugins received the message
        assert len(responses) == len(target_plugins), \
            f"Should receive {len(target_plugins)} responses"
        
        for target in target_plugins:
            messages = received_by_plugin[target]
            assert len(messages) == 1, f"Plugin {target} should receive exactly one message"
            
            message = messages[0]
            assert message.source_plugin == source_plugin
            assert message.data == data
            assert message.metadata.get('message_type') == message_type
            assert message.type == PluginMessageType.BROADCAST
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=message_type_strategy()
    )
    @pytest.mark.asyncio
    async def test_message_to_unregistered_plugin(
        self, source_plugin, target_plugin, message_type
    ):
        """
        Property: For any message sent to a plugin with no registered handlers,
        the send operation should return None (no response).
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Don't register any handlers for target plugin
        
        # Execute
        response = await inter_plugin.send_to_plugin(
            source_plugin, target_plugin, message_type, {"test": "data"}
        )
        
        # Verify no response
        assert response is None, "Should return None when no handlers registered"
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        messages=st.lists(
            st.tuples(message_type_strategy(), message_data_strategy()),
            min_size=1,
            max_size=10
        )
    )
    @pytest.mark.asyncio
    async def test_multiple_message_sequence(
        self, source_plugin, target_plugin, messages
    ):
        """
        Property: For any sequence of messages sent from one plugin to another,
        all messages should be delivered in order.
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register handler that tracks message order
        received_messages = []
        
        async def target_handler(message: PluginMessage):
            received_messages.append(message)
            return {"index": len(received_messages) - 1}
        
        inter_plugin.register_message_handler(target_plugin, target_handler)
        
        # Execute - send all messages
        responses = []
        for msg_type, data in messages:
            response = await inter_plugin.send_to_plugin(
                source_plugin, target_plugin, msg_type, data
            )
            responses.append(response)
        
        # Verify all messages delivered in order
        assert len(received_messages) == len(messages), \
            "All messages should be delivered"
        
        for i, (msg_type, data) in enumerate(messages):
            message = received_messages[i]
            assert message.data == data
            assert message.metadata.get('message_type') == msg_type
            assert message.source_plugin == source_plugin
            assert message.target_plugin == target_plugin
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=message_type_strategy(),
        data=message_data_strategy()
    )
    @pytest.mark.asyncio
    async def test_handler_error_isolation(
        self, source_plugin, target_plugin, message_type, data
    ):
        """
        Property: For any message where the handler raises an exception,
        the error should be caught and returned in the response without
        propagating to the sender.
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register handler that raises an exception
        async def failing_handler(message: PluginMessage):
            raise ValueError("Handler error for testing")
        
        inter_plugin.register_message_handler(target_plugin, failing_handler)
        
        # Execute - should not raise exception
        response = await inter_plugin.send_to_plugin(
            source_plugin, target_plugin, message_type, data
        )
        
        # Verify error is captured in response
        assert response is not None
        assert response.success is False
        assert "Handler error for testing" in response.error
    
    # Feature: third-party-plugin-system, Property 23: Inter-plugin messaging
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=message_type_strategy(),
        data=message_data_strategy()
    )
    @pytest.mark.asyncio
    async def test_multiple_handlers_per_plugin(
        self, source_plugin, target_plugin, message_type, data
    ):
        """
        Property: For any plugin with multiple registered handlers,
        the first handler that returns a non-None value should provide the response.
        """
        # Ensure source and target are different
        if source_plugin == target_plugin:
            target_plugin = target_plugin + "_different"
        
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Register multiple handlers
        handler_calls = []
        
        async def handler1(message: PluginMessage):
            handler_calls.append(1)
            return {"handler": 1, "data": message.data}
        
        async def handler2(message: PluginMessage):
            handler_calls.append(2)
            return {"handler": 2, "data": message.data}
        
        inter_plugin.register_message_handler(target_plugin, handler1)
        inter_plugin.register_message_handler(target_plugin, handler2)
        
        # Execute
        response = await inter_plugin.send_to_plugin(
            source_plugin, target_plugin, message_type, data
        )
        
        # Verify first handler was called and provided response
        assert len(handler_calls) >= 1, "At least one handler should be called"
        assert response is not None
        assert response.success is True
        assert response.data["handler"] == handler_calls[0]
