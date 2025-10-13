"""
Interactive Bot Service Package

Provides intelligent auto-response, command handling, and interactive features
for the ZephyrGate mesh network gateway.
"""

from .interactive_bot_service import InteractiveBotService, AutoResponseRule, BotCommandHandler, BotMessageHandler
from .command_registry import CommandRegistry, CommandMetadata, CommandContext, CommandPermission
from .message_processor import MessageProcessor, BotMessageRouter, ProcessingContext, MessageProcessingResult

__all__ = [
    'InteractiveBotService',
    'AutoResponseRule', 
    'BotCommandHandler',
    'BotMessageHandler',
    'CommandRegistry',
    'CommandMetadata',
    'CommandContext', 
    'CommandPermission',
    'MessageProcessor',
    'BotMessageRouter',
    'ProcessingContext',
    'MessageProcessingResult'
]