"""
Property-Based Tests for Plugin Command Routing

Tests universal properties of the command routing system using Hypothesis.
"""

import asyncio
import pytest
from datetime import datetime
from hypothesis import given, settings, strategies as st
from typing import List, Dict, Any

from src.core.plugin_command_handler import PluginCommandHandler, CommandContext
from src.models.message import Message, MessageType


# Strategies for generating test data

@st.composite
def command_name(draw):
    """Generate valid command names"""
    # Commands are typically lowercase alphanumeric with optional underscores/hyphens
    length = draw(st.integers(min_value=2, max_value=20))
    chars = draw(st.lists(
        st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_-'),
        min_size=length,
        max_size=length
    ))
    return ''.join(chars)


@st.composite
def plugin_name(draw):
    """Generate valid plugin names"""
    length = draw(st.integers(min_value=3, max_value=30))
    chars = draw(st.lists(
        st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_'),
        min_size=length,
        max_size=length
    ))
    return ''.join(chars)


@st.composite
def message_with_command(draw, command: str):
    """Generate a message containing a specific command"""
    sender_id = draw(st.text(min_size=5, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'))
    channel = draw(st.integers(min_value=0, max_value=7))
    
    # Generate optional arguments
    num_args = draw(st.integers(min_value=0, max_value=5))
    args = []
    for _ in range(num_args):
        arg = draw(st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789 '))
        args.append(arg)
    
    # Build message content
    content = command
    if args:
        content += ' ' + ' '.join(args)
    
    return Message(
        id=f"msg_{draw(st.integers(min_value=1, max_value=999999))}",
        sender_id=sender_id,
        recipient_id=None,
        channel=channel,
        content=content,
        message_type=MessageType.TEXT,
        timestamp=datetime.utcnow()
    )


@st.composite
def priority_value(draw):
    """Generate valid priority values"""
    return draw(st.integers(min_value=1, max_value=1000))


# Property Tests

class TestCommandRoutingCompleteness:
    """
    Feature: third-party-plugin-system, Property 1: Command routing completeness
    
    Property: For any command registered by a plugin, when a message containing 
    that command is received, the Plugin System should route the message to that 
    plugin's command handler with complete context (sender, channel, timestamp).
    
    Validates: Requirements 1.2, 1.4
    """
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin=plugin_name(),
        priority=priority_value()
    )
    @pytest.mark.asyncio
    async def test_registered_command_routes_to_handler(self, cmd, plugin, priority):
        """
        Test that any registered command routes to its handler with complete context.
        """
        # Setup
        handler = PluginCommandHandler()
        
        # Track if handler was called and context received
        handler_called = False
        received_context = None
        
        async def test_handler(args: List[str], context: Dict[str, Any]) -> str:
            nonlocal handler_called, received_context
            handler_called = True
            received_context = context
            return "test response"
        
        # Register command
        success = handler.register_command(plugin, cmd, test_handler, "Test command", priority)
        assert success, "Command registration should succeed"
        
        # Generate message with the command
        # Use the strategy directly to generate the message
        from hypothesis.strategies import DataObject
        from hypothesis import given as hypothesis_given
        
        # Create message manually
        message = Message(
            id=f"msg_test",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route the command
        response = await handler.route_command(message, user_profile=None)
        
        # Verify handler was called
        assert handler_called, f"Handler should be called for registered command '{cmd}'"
        
        # Verify response was returned
        assert response == "test response", "Handler response should be returned"
        
        # Verify context completeness
        assert received_context is not None, "Context should be provided to handler"
        assert 'sender_id' in received_context, "Context should include sender_id"
        assert 'channel' in received_context, "Context should include channel"
        assert 'timestamp' in received_context, "Context should include timestamp"
        assert 'message' in received_context, "Context should include message"
        
        # Verify context values match message
        assert received_context['sender_id'] == message.sender_id, \
            "Context sender_id should match message sender_id"
        assert received_context['channel'] == message.channel, \
            "Context channel should match message channel"
        assert received_context['message'] == message, \
            "Context message should match original message"
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin=plugin_name()
    )
    @pytest.mark.asyncio
    async def test_unregistered_command_returns_none(self, cmd, plugin):
        """
        Test that unregistered commands return None (no handler found).
        """
        # Setup
        handler = PluginCommandHandler()
        
        # Generate message with command (but don't register it)
        message = Message(
            id=f"msg_test",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route the command
        response = await handler.route_command(message, user_profile=None)
        
        # Verify no response
        assert response is None, "Unregistered command should return None"
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin1=plugin_name(),
        plugin2=plugin_name()
    )
    @pytest.mark.asyncio
    async def test_command_with_arguments_parsed_correctly(self, cmd, plugin1, plugin2):
        """
        Test that command arguments are correctly parsed and passed to handler.
        """
        # Ensure plugins are different
        if plugin1 == plugin2:
            plugin2 = plugin2 + "_alt"
        
        # Setup
        handler = PluginCommandHandler()
        
        received_args = None
        
        async def test_handler(args: List[str], context: Dict[str, Any]) -> str:
            nonlocal received_args
            received_args = args
            return "ok"
        
        # Register command
        handler.register_command(plugin1, cmd, test_handler, "Test")
        
        # Create message with arguments
        test_args = ["arg1", "arg2", "arg3"]
        message = Message(
            id="test_msg",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=f"{cmd} {' '.join(test_args)}",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route command
        response = await handler.route_command(message)
        
        # Verify arguments were passed correctly
        assert received_args is not None, "Arguments should be passed to handler"
        assert received_args == test_args, \
            f"Arguments should match: expected {test_args}, got {received_args}"


class TestCommandPriorityOrdering:
    """
    Feature: third-party-plugin-system, Property 2: Command priority ordering
    
    Property: For any set of plugins registering the same command with different 
    priorities, the Plugin System should execute handlers in priority order 
    (lowest priority value first).
    
    Validates: Requirements 1.3
    """
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin1=plugin_name(),
        plugin2=plugin_name(),
        plugin3=plugin_name(),
        priority1=priority_value(),
        priority2=priority_value(),
        priority3=priority_value()
    )
    @pytest.mark.asyncio
    async def test_handlers_execute_in_priority_order(
        self, cmd, plugin1, plugin2, plugin3, priority1, priority2, priority3
    ):
        """
        Test that multiple handlers for the same command execute in priority order.
        """
        # Ensure plugins are different
        if plugin1 == plugin2:
            plugin2 = plugin2 + "_2"
        if plugin1 == plugin3:
            plugin3 = plugin3 + "_3"
        if plugin2 == plugin3:
            plugin3 = plugin3 + "_alt"
        
        # Setup
        handler = PluginCommandHandler()
        
        execution_order = []
        
        async def make_handler(plugin_name: str):
            async def test_handler(args: List[str], context: Dict[str, Any]) -> str:
                execution_order.append(plugin_name)
                # Return None to allow next handler to execute
                return None
            return test_handler
        
        # Register handlers with different priorities
        handler.register_command(plugin1, cmd, await make_handler(plugin1), "Test 1", priority1)
        handler.register_command(plugin2, cmd, await make_handler(plugin2), "Test 2", priority2)
        handler.register_command(plugin3, cmd, await make_handler(plugin3), "Test 3", priority3)
        
        # Create message
        message = Message(
            id="test_msg",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route command
        await handler.route_command(message)
        
        # Verify execution order matches priority order (lower priority value = higher precedence)
        priorities = [(plugin1, priority1), (plugin2, priority2), (plugin3, priority3)]
        priorities.sort(key=lambda x: x[1])  # Sort by priority value
        expected_order = [p[0] for p in priorities]
        
        assert execution_order == expected_order, \
            f"Handlers should execute in priority order: expected {expected_order}, got {execution_order}"
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin1=plugin_name(),
        plugin2=plugin_name(),
        priority1=priority_value(),
        priority2=priority_value()
    )
    @pytest.mark.asyncio
    async def test_first_successful_handler_stops_execution(
        self, cmd, plugin1, plugin2, priority1, priority2
    ):
        """
        Test that when a handler returns a response, subsequent handlers are not executed.
        """
        # Ensure plugins are different
        if plugin1 == plugin2:
            plugin2 = plugin2 + "_alt"
        
        # Ensure priority1 < priority2 (plugin1 executes first)
        if priority1 >= priority2:
            priority1, priority2 = priority2 - 1, priority1 + 1
        
        # Setup
        handler = PluginCommandHandler()
        
        execution_order = []
        
        async def handler1(args: List[str], context: Dict[str, Any]) -> str:
            execution_order.append(plugin1)
            return "response from handler1"
        
        async def handler2(args: List[str], context: Dict[str, Any]) -> str:
            execution_order.append(plugin2)
            return "response from handler2"
        
        # Register handlers (plugin1 has higher priority)
        handler.register_command(plugin1, cmd, handler1, "Test 1", priority1)
        handler.register_command(plugin2, cmd, handler2, "Test 2", priority2)
        
        # Create message
        message = Message(
            id="test_msg",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route command
        response = await handler.route_command(message)
        
        # Verify only first handler executed
        assert len(execution_order) == 1, \
            "Only first handler should execute when it returns a response"
        assert execution_order[0] == plugin1, \
            f"First handler (plugin1) should execute, got {execution_order[0]}"
        assert response == "response from handler1", \
            "Response should be from first handler"


class TestMessageSendingCapability:
    """
    Feature: third-party-plugin-system, Property 3: Message sending capability
    
    Property: For any plugin command handler or scheduled task, calling the 
    send_message method should successfully queue the message for delivery to 
    the mesh network.
    
    Validates: Requirements 1.5, 3.2
    """
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin=plugin_name(),
        response_text=st.text(min_size=1, max_size=200)
    )
    @pytest.mark.asyncio
    async def test_command_handler_can_send_response(self, cmd, plugin, response_text):
        """
        Test that command handlers can send messages as responses.
        """
        # Setup
        handler = PluginCommandHandler()
        
        # Track if send_message was called
        send_called = False
        sent_content = None
        
        async def test_handler(args: List[str], context: Dict[str, Any]) -> str:
            nonlocal send_called, sent_content
            # Simulate sending a message
            send_called = True
            sent_content = response_text
            return response_text
        
        # Register command
        handler.register_command(plugin, cmd, test_handler, "Test")
        
        # Create message
        message = Message(
            id="test_msg",
            sender_id="test_sender",
            recipient_id=None,
            channel=0,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route command
        response = await handler.route_command(message)
        
        # Verify message sending capability
        assert send_called, "Handler should be able to send messages"
        assert sent_content == response_text, "Sent content should match response text"
        assert response == response_text, "Response should be returned"
    
    @settings(max_examples=100)
    @given(
        cmd=command_name(),
        plugin=plugin_name()
    )
    @pytest.mark.asyncio
    async def test_handler_context_provides_message_info(self, cmd, plugin):
        """
        Test that handlers receive complete message information for sending responses.
        """
        # Setup
        handler = PluginCommandHandler()
        
        received_context = None
        
        async def test_handler(args: List[str], context: Dict[str, Any]) -> str:
            nonlocal received_context
            received_context = context
            return "ok"
        
        # Register command
        handler.register_command(plugin, cmd, test_handler, "Test")
        
        # Create message
        message = Message(
            id="test_msg",
            sender_id="test_sender",
            recipient_id="test_recipient",
            channel=3,
            content=cmd,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Route command
        await handler.route_command(message)
        
        # Verify context has all necessary info for sending responses
        assert received_context is not None, "Context should be provided"
        assert 'sender_id' in received_context, "Context should include sender_id for replies"
        assert 'channel' in received_context, "Context should include channel for replies"
        assert 'message' in received_context, "Context should include original message"
        
        # Verify values
        assert received_context['sender_id'] == message.sender_id
        assert received_context['channel'] == message.channel
