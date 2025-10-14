"""
Core Message Router for ZephyrGate

Central hub for all message processing, routing, and distribution to service modules.
Handles Meshtastic interface management, message classification, and plugin coordination.
"""

import asyncio
import logging
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import uuid

from ..models.message import (
    Message, MessageType, MessagePriority, QueuedMessage, 
    UserProfile, SOSType, InterfaceConfig
)
from .config import ConfigurationManager
from .database import DatabaseManager
from .logging import get_logger


@dataclass
class RouteRule:
    """Message routing rule"""
    pattern: str
    service: str
    priority: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, message: Message, user: Optional[UserProfile] = None) -> bool:
        """Check if message matches this routing rule"""
        # Check content pattern
        if self.pattern and not re.search(self.pattern, message.content, re.IGNORECASE):
            return False
        
        # Check conditions
        for condition, value in self.conditions.items():
            if condition == 'message_type':
                if message.message_type.value != value:
                    return False
            elif condition == 'channel':
                if message.channel != value:
                    return False
            elif condition == 'is_dm':
                if message.is_direct_message() != value:
                    return False
            elif condition == 'sender_has_permission':
                if not user or not user.has_permission(value):
                    return False
            elif condition == 'sender_has_tag':
                if not user or not user.has_tag(value):
                    return False
        
        return True


@dataclass
class RateLimitBucket:
    """Rate limiting bucket for a specific key"""
    tokens: float
    last_refill: datetime
    max_tokens: float
    refill_rate: float  # tokens per second
    
    def can_consume(self, tokens: float = 1.0) -> bool:
        """Check if tokens can be consumed"""
        self._refill()
        return self.tokens >= tokens
    
    def consume(self, tokens: float = 1.0) -> bool:
        """Consume tokens if available"""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on time elapsed"""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class MessageClassifier:
    """Classifies incoming messages for routing"""
    
    def __init__(self):
        self.logger = get_logger('message_classifier')
        
        # SOS patterns
        self.sos_patterns = [
            r'\b(SOS|HELP|EMERGENCY|MAYDAY)\b',
            r'\bSOS[PFMH]?\b',  # SOSP, SOSF, SOSM, SOSH
        ]
        
        # BBS patterns
        self.bbs_patterns = [
            r'\b(BBS|BULLETIN|MAIL|MESSAGE)\b',
            r'^(bbshelp|bbslist|bbsread|bbspost|bbsdelete|bbsinfo|bbslink)',
        ]
        
        # Bot command patterns
        self.bot_patterns = [
            r'^(help|cmd|\?|ping|ack|cq|test|pong)\b',
            r'^(wx|weather|solar|earthquake|wiki|ask)',
            r'^(subscribe|unsubscribe|status|alerts|forecasts)',
            r'^(name/|phone/|address/|setemail|setsms)',
        ]
        
        # Email patterns
        self.email_patterns = [
            r'^email/',
            r'^(sms:|tagsend/|tagin/|tagout)',
        ]
    
    def classify_message(self, message: Message, user: Optional[UserProfile] = None) -> List[str]:
        """Classify message and return list of target services"""
        services = []
        content = message.content.strip()
        
        # Emergency response - highest priority
        if self._matches_patterns(content, self.sos_patterns):
            services.append('emergency')
            self.logger.info(f"Emergency message detected from {message.sender_id}")
        
        # BBS system
        if self._matches_patterns(content, self.bbs_patterns):
            services.append('bbs')
        
        # Interactive bot
        if self._matches_patterns(content, self.bot_patterns):
            services.append('bot')
        
        # Email gateway
        if self._matches_patterns(content, self.email_patterns):
            services.append('email')
        
        # Weather service (for weather-related keywords)
        if re.search(r'\b(weather|wx|forecast|alert|storm|rain|snow|wind)\b', content, re.IGNORECASE):
            services.append('weather')
        
        # Auto-response for new nodes or general queries
        if not services and (message.message_type == MessageType.NODEINFO or 
                           re.search(r'\b(hello|hi|hey|new|help)\b', content, re.IGNORECASE)):
            services.append('bot')
        
        # AI response for high-altitude nodes (potential aircraft)
        if user and user.is_high_altitude() and not services:
            services.append('bot')
            self.logger.info(f"High-altitude message from {message.sender_id} at {user.altitude}m")
        
        # Default to bot if no specific service matches
        if not services:
            services.append('bot')
        
        return services
    
    def _matches_patterns(self, content: str, patterns: List[str]) -> bool:
        """Check if content matches any of the patterns"""
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def extract_sos_type(self, content: str) -> SOSType:
        """Extract SOS type from message content"""
        content_upper = content.upper()
        
        if 'SOSP' in content_upper:
            return SOSType.SOSP
        elif 'SOSF' in content_upper:
            return SOSType.SOSF
        elif 'SOSM' in content_upper:
            return SOSType.SOSM
        else:
            return SOSType.SOS


class CoreMessageRouter:
    """
    Central message routing system with plugin architecture
    """
    
    def __init__(self, config_manager: ConfigurationManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = get_logger('message_router')
        
        # Core components
        self.classifier = MessageClassifier()
        self.interfaces: Dict[str, Any] = {}  # Will hold interface instances
        self.services: Dict[str, Any] = {}    # Will hold service instances
        
        # Message processing
        self.message_queue = asyncio.Queue()
        self.processing_tasks: Set[asyncio.Task] = set()
        self.route_rules: List[RouteRule] = []
        
        # Rate limiting
        self.rate_limiters: Dict[str, RateLimitBucket] = {}
        self.global_rate_limit = RateLimitBucket(
            tokens=10.0,
            last_refill=datetime.utcnow(),
            max_tokens=10.0,
            refill_rate=1.0  # 1 message per second globally
        )
        
        # Message chunking
        self.max_message_size = config_manager.get('meshtastic.max_message_size', 228)
        self.chunk_overhead = 20  # Overhead for chunk headers
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'messages_queued': 0,
            'messages_failed': 0,
            'services_called': defaultdict(int),
            'interfaces_active': 0,
            'uptime_start': datetime.utcnow()
        }
        
        # Message history for debugging
        self.recent_messages = deque(maxlen=100)
        
        self._setup_default_routes()
        self.logger.info("Core message router initialized")
    
    def _setup_default_routes(self):
        """Set up default routing rules"""
        # Emergency routes - highest priority
        self.route_rules.extend([
            RouteRule(
                pattern=r'\b(SOS|HELP|EMERGENCY|MAYDAY)\b',
                service='emergency',
                priority=100,
                conditions={'message_type': 'text'}
            ),
            RouteRule(
                pattern=r'^(ACK|RESPONDING|CLEAR|CANCEL|SAFE)\b',
                service='emergency',
                priority=90
            ),
        ])
        
        # BBS routes
        self.route_rules.extend([
            RouteRule(
                pattern=r'^(bbshelp|bbslist|bbsread|bbspost|bbsdelete|bbsinfo|bbslink)',
                service='bbs',
                priority=80
            ),
            RouteRule(
                pattern=r'\b(BBS|BULLETIN|MAIL)\b',
                service='bbs',
                priority=70
            ),
        ])
        
        # Email routes
        self.route_rules.extend([
            RouteRule(
                pattern=r'^email/',
                service='email',
                priority=75
            ),
            RouteRule(
                pattern=r'^(sms:|tagsend/|tagin/|tagout)',
                service='email',
                priority=75
            ),
        ])
        
        # Bot command routes
        self.route_rules.extend([
            RouteRule(
                pattern=r'^(help|cmd|\?|ping|ack|cq|test|pong)\b',
                service='bot',
                priority=60
            ),
            RouteRule(
                pattern=r'^(wx|weather|solar|earthquake|wiki|ask)',
                service='bot',
                priority=60
            ),
        ])
        
        # Default route to bot
        self.route_rules.append(
            RouteRule(
                pattern='',  # Matches everything
                service='bot',
                priority=1
            )
        )
        
        # Sort routes by priority (highest first)
        self.route_rules.sort(key=lambda r: r.priority, reverse=True)
    
    async def start(self):
        """Start the message router"""
        self.logger.info("Starting core message router")
        
        # Start message processing task
        task = asyncio.create_task(self._process_message_queue())
        self.processing_tasks.add(task)
        task.add_done_callback(self.processing_tasks.discard)
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_task())
        self.processing_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self.processing_tasks.discard)
        
        self.logger.info("Message router started successfully")
    
    async def stop(self):
        """Stop the message router"""
        self.logger.info("Stopping core message router")
        
        # Cancel all processing tasks
        for task in self.processing_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.processing_tasks:
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        
        self.logger.info("Message router stopped")
    
    def register_service(self, name: str, service_instance: Any):
        """Register a service module"""
        self.services[name] = service_instance
        self.logger.info(f"Registered service: {name}")
    
    def unregister_service(self, name: str):
        """Unregister a service module"""
        if name in self.services:
            del self.services[name]
            self.logger.info(f"Unregistered service: {name}")
    
    def register_interface(self, interface_id: str, interface_instance: Any):
        """Register a Meshtastic interface"""
        self.interfaces[interface_id] = interface_instance
        self.stats['interfaces_active'] = len(self.interfaces)
        self.logger.info(f"Registered interface: {interface_id}")
    
    def unregister_interface(self, interface_id: str):
        """Unregister a Meshtastic interface"""
        if interface_id in self.interfaces:
            del self.interfaces[interface_id]
            self.stats['interfaces_active'] = len(self.interfaces)
            self.logger.info(f"Unregistered interface: {interface_id}")
    
    async def process_message(self, message: Message, interface_id: str):
        """Process incoming message from Meshtastic interface"""
        message.interface_id = interface_id
        self.stats['messages_received'] += 1
        
        # Add to recent messages for debugging
        self.recent_messages.append({
            'timestamp': datetime.utcnow(),
            'message': message.to_dict(),
            'interface_id': interface_id
        })
        
        # Store message in database
        try:
            await self._store_message_history(message)
        except Exception as e:
            self.logger.error(f"Failed to store message history: {e}")
        
        # Queue message for processing
        queued_msg = QueuedMessage(message=message)
        await self.message_queue.put(queued_msg)
        self.stats['messages_queued'] += 1
        
        self.logger.debug(f"Queued message from {message.sender_id}: {message.content[:50]}...")
    
    async def send_message(self, message: Message, interface_id: Optional[str] = None) -> bool:
        """Send message through specified interface with rate limiting"""
        # Apply rate limiting
        sender_key = f"sender_{message.sender_id}"
        if not self._check_rate_limit(sender_key):
            self.logger.warning(f"Rate limit exceeded for sender {message.sender_id}")
            return False
        
        if not self.global_rate_limit.consume():
            self.logger.warning("Global rate limit exceeded")
            return False
        
        # Chunk message if too large
        chunks = self._chunk_message(message)
        
        # Send through interface(s)
        success = False
        interfaces_to_use = [interface_id] if interface_id else list(self.interfaces.keys())
        
        for iface_id in interfaces_to_use:
            if iface_id not in self.interfaces:
                continue
            
            interface = self.interfaces[iface_id]
            
            try:
                for chunk in chunks:
                    await self._send_through_interface(chunk, interface)
                    self.stats['messages_sent'] += 1
                
                success = True
                self.logger.debug(f"Sent message to {message.recipient_id or 'broadcast'} via {iface_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to send message via {iface_id}: {e}")
                self.stats['messages_failed'] += 1
        
        return success
    
    async def _process_message_queue(self):
        """Process messages from the queue"""
        while True:
            try:
                # Get message from queue with timeout
                try:
                    queued_msg = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the message
                await self._route_message(queued_msg)
                
            except Exception as e:
                self.logger.error(f"Error processing message queue: {e}")
                await asyncio.sleep(1)
    
    async def _route_message(self, queued_msg: QueuedMessage):
        """Route message to appropriate services with enhanced integration"""
        message = queued_msg.message
        
        try:
            # Get user profile
            user = await self._get_user_profile(message.sender_id)
            
            # Update user's last seen
            if user:
                user.last_seen = datetime.utcnow()
                await self._update_user_profile(user)
            
            # Classify message to determine target services
            target_services = self.classifier.classify_message(message, user)
            
            # Apply routing rules with priority ordering
            matched_rules = []
            for rule in self.route_rules:
                if rule.matches(message, user):
                    matched_rules.append(rule)
            
            # Sort by priority and add services
            matched_rules.sort(key=lambda r: r.priority, reverse=True)
            for rule in matched_rules:
                if rule.service not in target_services:
                    target_services.append(rule.service)
            
            # Create routing context
            routing_context = {
                'message': message,
                'user': user,
                'timestamp': datetime.utcnow(),
                'interface_id': message.interface_id,
                'is_retry': queued_msg.retry_count > 0,
                'retry_count': queued_msg.retry_count
            }
            
            # Route to services with enhanced error handling
            successful_routes = []
            failed_routes = []
            
            for service_name in target_services:
                if service_name in self.services:
                    try:
                        service = self.services[service_name]
                        
                        # Call service with enhanced context
                        if hasattr(service, 'handle_message_with_context'):
                            result = await service.handle_message_with_context(message, routing_context)
                        elif hasattr(service, 'handle_message'):
                            result = await service.handle_message(message, user)
                        else:
                            # Fallback for services without proper interface
                            self.logger.warning(f"Service {service_name} lacks proper message handling interface")
                            continue
                        
                        successful_routes.append(service_name)
                        self.stats['services_called'][service_name] += 1
                        
                        # Handle service responses
                        if result and isinstance(result, dict):
                            await self._handle_service_response(service_name, result, message)
                        
                    except Exception as e:
                        self.logger.error(f"Service {service_name} failed to handle message: {e}")
                        failed_routes.append((service_name, str(e)))
                        
                        # Retry logic for failed messages
                        if queued_msg.should_retry():
                            queued_msg.schedule_retry(delay_seconds=30)
                            await self.message_queue.put(queued_msg)
                            self.logger.info(f"Scheduled retry for message to {service_name}")
                else:
                    self.logger.warning(f"Service {service_name} not registered")
                    failed_routes.append((service_name, "Service not registered"))
            
            # Log routing results
            if successful_routes:
                self.logger.debug(f"Message routed successfully to: {successful_routes}")
            
            if failed_routes:
                self.logger.warning(f"Message routing failures: {failed_routes}")
            
            # Store routing information for debugging
            await self._store_routing_info(message, target_services, successful_routes, failed_routes)
            
        except Exception as e:
            self.logger.error(f"Error routing message: {e}")
            self.stats['messages_failed'] += 1
    
    def _check_rate_limit(self, key: str) -> bool:
        """Check rate limit for a specific key"""
        if key not in self.rate_limiters:
            self.rate_limiters[key] = RateLimitBucket(
                tokens=5.0,
                last_refill=datetime.utcnow(),
                max_tokens=5.0,
                refill_rate=0.2  # 1 message per 5 seconds per sender
            )
        
        return self.rate_limiters[key].can_consume()
    
    def _chunk_message(self, message: Message) -> List[Message]:
        """Chunk large messages into smaller pieces"""
        content = message.content
        max_chunk_size = self.max_message_size - self.chunk_overhead
        
        if len(content) <= max_chunk_size:
            return [message]
        
        chunks = []
        chunk_id = str(uuid.uuid4())[:8]
        total_chunks = (len(content) + max_chunk_size - 1) // max_chunk_size
        
        for i in range(total_chunks):
            start = i * max_chunk_size
            end = min(start + max_chunk_size, len(content))
            chunk_content = content[start:end]
            
            # Create chunk message
            chunk_msg = Message(
                id=f"{message.id}_chunk_{i}",
                sender_id=message.sender_id,
                recipient_id=message.recipient_id,
                channel=message.channel,
                content=f"[{i+1}/{total_chunks}:{chunk_id}] {chunk_content}",
                message_type=message.message_type,
                priority=message.priority,
                metadata={
                    **message.metadata,
                    'is_chunk': True,
                    'chunk_id': chunk_id,
                    'chunk_index': i,
                    'total_chunks': total_chunks
                }
            )
            
            chunks.append(chunk_msg)
        
        self.logger.info(f"Chunked message into {total_chunks} parts")
        return chunks
    
    async def _send_through_interface(self, message: Message, interface: Any):
        """Send message through a specific interface"""
        # This will be implemented when we have actual interface classes
        # For now, just log the action
        self.logger.debug(f"Sending message through interface: {message.content[:50]}...")
        
        # Simulate sending delay
        await asyncio.sleep(0.1)
    
    async def _store_message_history(self, message: Message):
        """Store message in database history"""
        try:
            self.db.execute_update(
                """
                INSERT INTO message_history 
                (message_id, sender_id, recipient_id, channel, content, timestamp, 
                 interface_id, hop_count, snr, rssi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.sender_id,
                    message.recipient_id,
                    message.channel,
                    message.content,
                    message.timestamp.isoformat(),
                    message.interface_id,
                    message.hop_count,
                    message.snr,
                    message.rssi
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to store message history: {e}")
    
    async def _get_user_profile(self, node_id: str) -> Optional[UserProfile]:
        """Get user profile from database"""
        try:
            user_data = self.db.get_user(node_id)
            if user_data:
                return UserProfile(
                    node_id=user_data['node_id'],
                    short_name=user_data['short_name'],
                    long_name=user_data['long_name'] or '',
                    email=user_data['email'],
                    phone=user_data['phone'],
                    address=user_data['address'],
                    tags=user_data['tags'],
                    permissions=user_data['permissions'],
                    subscriptions=user_data['subscriptions'],
                    last_seen=datetime.fromisoformat(user_data['last_seen']) if user_data['last_seen'] else datetime.utcnow(),
                    location=(user_data['location_lat'], user_data['location_lon']) if user_data['location_lat'] else None
                )
        except Exception as e:
            self.logger.error(f"Failed to get user profile for {node_id}: {e}")
        
        return None
    
    async def _update_user_profile(self, user: UserProfile):
        """Update user profile in database"""
        try:
            user_data = {
                'node_id': user.node_id,
                'short_name': user.short_name,
                'long_name': user.long_name,
                'email': user.email,
                'phone': user.phone,
                'address': user.address,
                'tags': user.tags,
                'permissions': user.permissions,
                'subscriptions': user.subscriptions,
                'last_seen': user.last_seen.isoformat(),
                'location_lat': user.location[0] if user.location else None,
                'location_lon': user.location[1] if user.location else None
            }
            
            self.db.upsert_user(user_data)
            
        except Exception as e:
            self.logger.error(f"Failed to update user profile for {user.node_id}: {e}")
    
    async def _cleanup_task(self):
        """Periodic cleanup task"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean up old rate limiters
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                expired_keys = [
                    key for key, bucket in self.rate_limiters.items()
                    if bucket.last_refill < cutoff_time
                ]
                
                for key in expired_keys:
                    del self.rate_limiters[key]
                
                if expired_keys:
                    self.logger.debug(f"Cleaned up {len(expired_keys)} expired rate limiters")
                
                # Clean up database
                self.db.cleanup_expired_data()
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        uptime = datetime.utcnow() - self.stats['uptime_start']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'queue_size': self.message_queue.qsize(),
            'active_rate_limiters': len(self.rate_limiters),
            'registered_services': list(self.services.keys()),
            'registered_interfaces': list(self.interfaces.keys()),
            'recent_messages_count': len(self.recent_messages)
        }
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for debugging"""
        return list(self.recent_messages)[-limit:]
    
    async def _handle_service_response(self, service_name: str, response: Dict[str, Any], original_message: Message):
        """Handle responses from services"""
        try:
            # Check if service wants to send a response message
            if 'response_message' in response:
                response_msg = response['response_message']
                if isinstance(response_msg, str):
                    # Create response message
                    reply = Message(
                        sender_id="system",
                        recipient_id=original_message.sender_id,
                        channel=original_message.channel,
                        content=response_msg,
                        message_type=MessageType.TEXT,
                        priority=response.get('priority', MessagePriority.NORMAL)
                    )
                    
                    # Send response
                    await self.send_message(reply, original_message.interface_id)
            
            # Handle broadcast requests
            if 'broadcast_message' in response:
                broadcast_msg = response['broadcast_message']
                if isinstance(broadcast_msg, str):
                    # Create broadcast message
                    broadcast = Message(
                        sender_id="system",
                        recipient_id=None,  # Broadcast
                        channel=original_message.channel,
                        content=broadcast_msg,
                        message_type=MessageType.TEXT,
                        priority=response.get('priority', MessagePriority.NORMAL)
                    )
                    
                    # Send broadcast
                    await self.send_message(broadcast)
            
            # Handle cross-service communication
            if 'notify_services' in response:
                notify_list = response['notify_services']
                notification_data = response.get('notification_data', {})
                
                for target_service in notify_list:
                    if target_service in self.services and target_service != service_name:
                        try:
                            target = self.services[target_service]
                            if hasattr(target, 'handle_service_notification'):
                                await target.handle_service_notification(service_name, notification_data)
                        except Exception as e:
                            self.logger.error(f"Failed to notify service {target_service}: {e}")
            
            # Handle priority escalation
            if response.get('escalate', False):
                escalated_msg = Message(
                    sender_id=original_message.sender_id,
                    recipient_id=original_message.recipient_id,
                    channel=original_message.channel,
                    content=original_message.content,
                    message_type=original_message.message_type,
                    priority=MessagePriority.EMERGENCY
                )
                
                # Re-route with emergency priority
                queued_msg = QueuedMessage(message=escalated_msg)
                await self.message_queue.put(queued_msg)
            
        except Exception as e:
            self.logger.error(f"Error handling service response from {service_name}: {e}")
    
    async def _store_routing_info(self, message: Message, target_services: List[str], 
                                successful_routes: List[str], failed_routes: List[Tuple[str, str]]):
        """Store routing information for debugging and analytics"""
        try:
            routing_data = {
                'message_id': message.id,
                'sender_id': message.sender_id,
                'target_services': target_services,
                'successful_routes': successful_routes,
                'failed_routes': [{'service': service, 'error': error} for service, error in failed_routes],
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Store in database
            self.db.execute_update(
                """
                INSERT INTO message_routing_log 
                (message_id, sender_id, target_services, successful_routes, failed_routes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.sender_id,
                    ','.join(target_services),
                    ','.join(successful_routes),
                    str(failed_routes),
                    datetime.utcnow().isoformat()
                )
            )
            
        except Exception as e:
            self.logger.debug(f"Failed to store routing info: {e}")
    
    async def broadcast_to_services(self, message_type: str, data: Any, exclude_services: List[str] = None):
        """Broadcast a message to all registered services"""
        exclude_services = exclude_services or []
        
        for service_name, service in self.services.items():
            if service_name not in exclude_services:
                try:
                    if hasattr(service, 'handle_broadcast'):
                        await service.handle_broadcast(message_type, data)
                except Exception as e:
                    self.logger.error(f"Failed to broadcast to service {service_name}: {e}")
    
    async def send_service_message(self, target_service: str, message_type: str, data: Any) -> Any:
        """Send a direct message to a specific service"""
        if target_service not in self.services:
            self.logger.warning(f"Target service {target_service} not registered")
            return None
        
        try:
            service = self.services[target_service]
            if hasattr(service, 'handle_service_message'):
                return await service.handle_service_message(message_type, data)
            else:
                self.logger.warning(f"Service {target_service} does not support direct messaging")
                return None
        except Exception as e:
            self.logger.error(f"Failed to send message to service {target_service}: {e}")
            return None
    
    def add_route_rule(self, rule: RouteRule):
        """Add a new routing rule"""
        self.route_rules.append(rule)
        self.route_rules.sort(key=lambda r: r.priority, reverse=True)
        self.logger.info(f"Added routing rule for service {rule.service} with priority {rule.priority}")
    
    def remove_route_rule(self, pattern: str, service: str):
        """Remove a routing rule"""
        self.route_rules = [
            rule for rule in self.route_rules 
            if not (rule.pattern == pattern and rule.service == service)
        ]
        self.logger.info(f"Removed routing rule for service {service}")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get status of all registered services"""
        status = {}
        
        for service_name, service in self.services.items():
            try:
                if hasattr(service, 'get_status'):
                    service_status = await service.get_status()
                else:
                    service_status = {'status': 'unknown', 'message': 'Service does not provide status'}
                
                status[service_name] = service_status
                
            except Exception as e:
                status[service_name] = {
                    'status': 'error',
                    'message': f'Failed to get status: {e}'
                }
        
        return status
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a specific service"""
        if service_name not in self.services:
            self.logger.error(f"Service {service_name} not registered")
            return False
        
        try:
            service = self.services[service_name]
            
            # Stop service if it has a stop method
            if hasattr(service, 'stop'):
                await service.stop()
            
            # Start service if it has a start method
            if hasattr(service, 'start'):
                await service.start()
            
            self.logger.info(f"Restarted service: {service_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restart service {service_name}: {e}")
            return False