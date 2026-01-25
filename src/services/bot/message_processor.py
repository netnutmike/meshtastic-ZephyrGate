"""
Message Processing and Routing System

Handles message processing, routing, and dispatch for the interactive bot service.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set, Callable
from dataclasses import dataclass, field
from enum import Enum

from models.message import Message, MessageType, MessagePriority
from core.plugin_interfaces import MessageHandler, BaseMessageHandler


class MessageProcessingResult(Enum):
    """Results of message processing"""
    HANDLED = "handled"
    IGNORED = "ignored"
    ERROR = "error"
    DEFERRED = "deferred"


@dataclass
class ProcessingContext:
    """Context for message processing"""
    message: Message
    sender_id: str
    sender_name: str = ""
    is_direct_message: bool = False
    is_command: bool = False
    is_emergency: bool = False
    altitude: Optional[float] = None
    location: Optional[Tuple[float, float]] = None
    user_data: Dict[str, Any] = field(default_factory=dict)
    processing_start: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MessageRoute:
    """Routing information for messages"""
    handler: MessageHandler
    priority: int
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class MessageProcessor:
    """
    Central message processor that handles routing and dispatch
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Message handlers and routing
        self.message_handlers: List[MessageHandler] = []
        self.routes: List[MessageRoute] = []
        
        # Processing hooks
        self.pre_processing_hooks: List[Callable] = []
        self.post_processing_hooks: List[Callable] = []
        
        # Message filtering and classification
        self.command_patterns = [
            re.compile(r'^[!/](\w+)'),  # Commands starting with ! or /
            re.compile(r'^(\w+)$'),     # Single word commands
        ]
        
        self.emergency_patterns = [
            re.compile(r'\b(help|emergency|urgent|mayday|sos)\b', re.IGNORECASE),
            re.compile(r'\b(fire|medical|accident|injured)\b', re.IGNORECASE),
        ]
        
        # Message history and deduplication
        self.message_history: Dict[str, List[Message]] = {}
        self.processed_messages: Set[str] = set()
        self.duplicate_threshold = timedelta(seconds=30)
        
        # Statistics
        self.processing_stats = {
            'total_processed': 0,
            'handled': 0,
            'ignored': 0,
            'errors': 0,
            'deferred': 0,
            'duplicates': 0
        }
    
    def register_handler(self, handler: MessageHandler, priority: int = None) -> bool:
        """
        Register a message handler
        
        Args:
            handler: The message handler to register
            priority: Optional priority override
            
        Returns:
            True if handler was registered
        """
        try:
            # Use handler's priority if not overridden
            if priority is None:
                priority = handler.get_priority()
            
            # Create route
            route = MessageRoute(
                handler=handler,
                priority=priority
            )
            
            self.routes.append(route)
            self.message_handlers.append(handler)
            
            # Sort routes by priority
            self.routes.sort(key=lambda r: r.priority)
            
            self.logger.debug(f"Registered message handler with priority {priority}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering message handler: {e}")
            return False
    
    def unregister_handler(self, handler: MessageHandler) -> bool:
        """
        Unregister a message handler
        
        Args:
            handler: The message handler to unregister
            
        Returns:
            True if handler was unregistered
        """
        try:
            # Remove from handlers list
            if handler in self.message_handlers:
                self.message_handlers.remove(handler)
            
            # Remove from routes
            self.routes = [route for route in self.routes if route.handler != handler]
            
            self.logger.debug("Unregistered message handler")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unregistering message handler: {e}")
            return False
    
    async def process_message(self, message: Message) -> Tuple[MessageProcessingResult, Optional[Any]]:
        """
        Process a message through all registered handlers
        
        Args:
            message: The message to process
            
        Returns:
            Tuple of (processing result, response data)
        """
        try:
            self.processing_stats['total_processed'] += 1
            
            # Check for duplicates
            if await self._is_duplicate_message(message):
                self.processing_stats['duplicates'] += 1
                return MessageProcessingResult.IGNORED, None
            
            # Create processing context
            context = await self._create_processing_context(message)
            
            # Execute pre-processing hooks
            for hook in self.pre_processing_hooks:
                try:
                    await hook(context)
                except Exception as e:
                    self.logger.error(f"Pre-processing hook error: {e}")
            
            # Process through handlers
            result, response = await self._route_message(message, context)
            
            # Execute post-processing hooks
            for hook in self.post_processing_hooks:
                try:
                    await hook(context, result, response)
                except Exception as e:
                    self.logger.error(f"Post-processing hook error: {e}")
            
            # Update statistics
            self.processing_stats[result.value] += 1
            
            # Store in history
            await self._store_message_history(message)
            
            return result, response
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            self.processing_stats['errors'] += 1
            return MessageProcessingResult.ERROR, None
    
    async def _create_processing_context(self, message: Message) -> ProcessingContext:
        """Create processing context for a message"""
        context = ProcessingContext(
            message=message,
            sender_id=message.sender_id,
            is_direct_message=message.recipient_id is not None
        )
        
        # Classify message
        content = message.content.strip()
        
        # Check if it's a command
        context.is_command = any(pattern.match(content) for pattern in self.command_patterns)
        
        # Check for emergency keywords
        context.is_emergency = any(pattern.search(content) for pattern in self.emergency_patterns)
        
        # Extract altitude if available (for AI aircraft detection)
        altitude_match = re.search(r'altitude[:\s]+(\d+)', content, re.IGNORECASE)
        if altitude_match:
            try:
                context.altitude = float(altitude_match.group(1))
            except ValueError:
                pass
        
        return context
    
    async def _route_message(self, message: Message, context: ProcessingContext) -> Tuple[MessageProcessingResult, Optional[Any]]:
        """Route message through appropriate handlers"""
        responses = []
        handled = False
        
        for route in self.routes:
            if not route.enabled:
                continue
            
            handler = route.handler
            
            try:
                # Check if handler can process this message
                if not handler.can_handle(message):
                    continue
                
                # Check route conditions
                if not await self._check_route_conditions(route, context):
                    continue
                
                # Process message
                handler_context = {
                    'sender_id': context.sender_id,
                    'sender_name': context.sender_name,
                    'is_direct_message': context.is_direct_message,
                    'is_command': context.is_command,
                    'is_emergency': context.is_emergency,
                    'altitude': context.altitude,
                    'location': context.location,
                    'user_data': context.user_data,
                    'processing_start': context.processing_start
                }
                
                response = await handler.handle_message(message, handler_context)
                
                if response is not None:
                    responses.append(response)
                    handled = True
                    
                    # For high-priority handlers, stop processing
                    if route.priority < 50:
                        break
                
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")
                continue
        
        if handled:
            # Return the first (highest priority) response
            return MessageProcessingResult.HANDLED, responses[0] if responses else None
        else:
            return MessageProcessingResult.IGNORED, None
    
    async def _check_route_conditions(self, route: MessageRoute, context: ProcessingContext) -> bool:
        """Check if route conditions are met"""
        conditions = route.conditions
        
        if not conditions:
            return True
        
        # Check message type conditions
        if 'message_types' in conditions:
            if context.message.message_type not in conditions['message_types']:
                return False
        
        # Check channel conditions
        if 'channels' in conditions:
            if context.message.channel not in conditions['channels']:
                return False
        
        # Check direct message conditions
        if 'direct_message_only' in conditions:
            if conditions['direct_message_only'] and not context.is_direct_message:
                return False
        
        # Check command conditions
        if 'commands_only' in conditions:
            if conditions['commands_only'] and not context.is_command:
                return False
        
        # Check emergency conditions
        if 'emergency_only' in conditions:
            if conditions['emergency_only'] and not context.is_emergency:
                return False
        
        return True
    
    async def _is_duplicate_message(self, message: Message) -> bool:
        """Check if message is a duplicate"""
        # Create message signature using message ID if available, otherwise content + sender + timestamp
        if hasattr(message, 'id') and message.id:
            signature = f"id:{message.id}"
        else:
            signature = f"{message.sender_id}:{message.content}:{message.timestamp.isoformat()}"
        
        if signature in self.processed_messages:
            return True
        
        # Add to processed messages
        self.processed_messages.add(signature)
        
        # Clean old signatures (older than threshold)
        current_time = datetime.utcnow()
        signatures_to_remove = []
        
        for sig in self.processed_messages:
            try:
                if sig.startswith("id:"):
                    # For ID-based signatures, we can't determine age, so keep them
                    continue
                
                # Extract timestamp from signature
                timestamp_str = sig.split(':')[-1]
                timestamp = datetime.fromisoformat(timestamp_str)
                
                if current_time - timestamp > self.duplicate_threshold:
                    signatures_to_remove.append(sig)
            except (ValueError, IndexError):
                # Invalid signature format, remove it
                signatures_to_remove.append(sig)
        
        for sig in signatures_to_remove:
            self.processed_messages.discard(sig)
        
        return False
    
    async def _store_message_history(self, message: Message):
        """Store message in history for analysis"""
        sender_id = message.sender_id
        
        if sender_id not in self.message_history:
            self.message_history[sender_id] = []
        
        self.message_history[sender_id].append(message)
        
        # Keep only recent messages (last 100 per user)
        if len(self.message_history[sender_id]) > 100:
            self.message_history[sender_id] = self.message_history[sender_id][-100:]
    
    def get_message_history(self, sender_id: str, limit: int = 10) -> List[Message]:
        """Get recent message history for a user"""
        if sender_id not in self.message_history:
            return []
        
        return self.message_history[sender_id][-limit:]
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get message processing statistics"""
        total = self.processing_stats['total_processed']
        
        stats = self.processing_stats.copy()
        
        if total > 0:
            stats['percentages'] = {
                key: (value / total) * 100 
                for key, value in self.processing_stats.items() 
                if key != 'total_processed'
            }
        
        stats['active_handlers'] = len(self.message_handlers)
        stats['active_routes'] = len([r for r in self.routes if r.enabled])
        
        return stats
    
    def add_pre_processing_hook(self, hook: Callable):
        """Add a pre-processing hook"""
        self.pre_processing_hooks.append(hook)
    
    def add_post_processing_hook(self, hook: Callable):
        """Add a post-processing hook"""
        self.post_processing_hooks.append(hook)
    
    def set_route_condition(self, handler: MessageHandler, conditions: Dict[str, Any]):
        """Set conditions for a specific handler route"""
        for route in self.routes:
            if route.handler == handler:
                route.conditions = conditions
                break
    
    def enable_route(self, handler: MessageHandler, enabled: bool = True):
        """Enable or disable a specific route"""
        for route in self.routes:
            if route.handler == handler:
                route.enabled = enabled
                break
    
    def clear_message_history(self, sender_id: Optional[str] = None):
        """Clear message history for a user or all users"""
        if sender_id:
            self.message_history.pop(sender_id, None)
        else:
            self.message_history.clear()
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.processing_stats = {
            'total_processed': 0,
            'handled': 0,
            'ignored': 0,
            'errors': 0,
            'deferred': 0,
            'duplicates': 0
        }


class BotMessageRouter(BaseMessageHandler):
    """
    Message router that integrates with the bot service
    """
    
    def __init__(self, bot_service, priority: int = 50):
        super().__init__(priority)
        self.bot_service = bot_service
        self.processor = MessageProcessor()
        
        # Register bot service as a handler
        self.processor.register_handler(BotServiceHandler(bot_service), priority=10)
    
    def can_handle(self, message: Message) -> bool:
        """Check if this router can handle the message"""
        return message.message_type == MessageType.TEXT
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Route message through the processor"""
        result, response = await self.processor.process_message(message)
        
        if result == MessageProcessingResult.HANDLED:
            return response
        
        return None
    
    def register_handler(self, handler: MessageHandler, priority: int = None):
        """Register a message handler with the processor"""
        return self.processor.register_handler(handler, priority)
    
    def unregister_handler(self, handler: MessageHandler):
        """Unregister a message handler from the processor"""
        return self.processor.unregister_handler(handler)


class BotServiceHandler(BaseMessageHandler):
    """
    Handler that delegates to the bot service
    """
    
    def __init__(self, bot_service, priority: int = 100):
        super().__init__(priority)
        self.bot_service = bot_service
    
    def can_handle(self, message: Message) -> bool:
        """Check if bot service can handle the message"""
        return message.message_type == MessageType.TEXT
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Delegate to bot service"""
        return await self.bot_service.handle_message(message)