"""
Message History and Store-and-Forward Service

Implements message history storage and retrieval, store-and-forward functionality
for offline users, message replay system with filtering options, and message
chunking for large responses.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
import json

from models.message import Message, MessageType, MessagePriority
from core.database import get_database
from core.plugin_interfaces import BaseMessageHandler, PluginCommunicationInterface


@dataclass
class MessageFilter:
    """Filter criteria for message history queries"""
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    channel: Optional[int] = None
    content_pattern: Optional[str] = None
    message_type: Optional[MessageType] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interface_id: Optional[str] = None
    min_snr: Optional[float] = None
    max_hop_count: Optional[int] = None
    limit: int = 50
    offset: int = 0


@dataclass
class StoredMessage:
    """Stored message for offline users"""
    id: str
    recipient_id: str
    sender_id: str
    content: str
    timestamp: datetime
    priority: MessagePriority
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    last_attempt: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OfflineUser:
    """Offline user tracking"""
    node_id: str
    last_seen: datetime
    pending_messages: List[str] = field(default_factory=list)
    notification_sent: bool = False
    max_offline_hours: int = 24


class MessageHistoryService(BaseMessageHandler):
    """
    Service for message history storage, retrieval, and store-and-forward functionality
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Core components
        self.communication: Optional[PluginCommunicationInterface] = None
        self.db = None  # Will be set when database is available
        
        # Configuration
        self.history_retention_days = self.config.get('history_retention_days', 30)
        self.max_offline_messages = self.config.get('max_offline_messages', 50)
        self.offline_message_ttl_hours = self.config.get('offline_message_ttl_hours', 72)
        self.max_message_chunk_size = self.config.get('max_message_chunk_size', 200)
        self.store_forward_enabled = self.config.get('store_forward_enabled', True)
        
        # Store-and-forward tracking
        self.offline_users: Dict[str, OfflineUser] = {}
        self.pending_messages: Dict[str, StoredMessage] = {}
        
        # Message chunking for large responses
        self.chunk_responses = self.config.get('chunk_responses', True)
        
        # Service state
        self._running = False
        
        # Initialize default configuration
        self._initialize_default_config()
    
    def _initialize_default_config(self):
        """Initialize default configuration values"""
        default_config = {
            'history_retention_days': 30,
            'max_offline_messages': 50,
            'offline_message_ttl_hours': 72,
            'max_message_chunk_size': 200,
            'store_forward_enabled': True,
            'chunk_responses': True,
            'offline_check_interval': 300,  # 5 minutes
            'cleanup_interval': 3600,  # 1 hour
            'max_history_results': 100,
            'enable_message_search': True,
            'enable_replay_system': True
        }
        
        # Merge with provided config
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    async def start(self):
        """Start the message history service"""
        if self._running:
            return
        
        self._running = True
        
        # Load offline users and pending messages
        await self._load_offline_users()
        await self._load_pending_messages()
        
        # Start background tasks
        asyncio.create_task(self._offline_check_task())
        asyncio.create_task(self._cleanup_task())
        
        self.logger.info("Message History Service started")
    
    async def stop(self):
        """Stop the message history service"""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("Message History Service stopped")
    
    def set_communication_interface(self, communication: PluginCommunicationInterface):
        """Set the communication interface for plugin communication"""
        self.communication = communication
    
    async def handle_message(self, message: Message, user_profile=None) -> Optional[Message]:
        """
        Handle incoming message for history storage and store-and-forward processing
        
        Args:
            message: The incoming message to process
            user_profile: User profile information
            
        Returns:
            Response message if applicable, None otherwise
        """
        if not self._running:
            return None
        
        try:
            # Store message in history
            await self._store_message_in_history(message)
            
            # Check for store-and-forward commands first
            content = message.content.strip().lower()
            
            if content.startswith('history'):
                await self._update_user_activity(message.sender_id)
                return await self._handle_history_command(message, user_profile)
            elif content.startswith('messages'):
                await self._update_user_activity(message.sender_id)
                return await self._handle_messages_command(message, user_profile)
            elif content.startswith('replay'):
                await self._update_user_activity(message.sender_id)
                return await self._handle_replay_command(message, user_profile)
            elif content == 'pending':
                # Don't deliver pending messages when user is just checking them
                await self._update_user_activity(message.sender_id, deliver_pending=False)
                return await self._handle_pending_command(message, user_profile)
            
            # Update user activity (this will deliver pending messages for regular messages)
            await self._update_user_activity(message.sender_id)
            
            # Check if this is a direct message that needs store-and-forward
            if message.recipient_id and message.recipient_id != "^all":
                await self._handle_store_and_forward(message)
            
        except Exception as e:
            self.logger.error(f"Error handling message in history service: {e}")
        
        return None
    
    async def _store_message_in_history(self, message: Message):
        """Store message in database history"""
        try:
            db = get_database()
            db.execute_update(
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
            
            self.logger.debug(f"Stored message {message.id} in history")
            
        except Exception as e:
            self.logger.error(f"Failed to store message in history: {e}")
    
    async def _update_user_activity(self, user_id: str, deliver_pending: bool = True):
        """Update user's last seen timestamp"""
        try:
            db = get_database()
            db.execute_update(
                "UPDATE users SET last_seen = ? WHERE node_id = ?",
                (datetime.utcnow().isoformat(), user_id)
            )
            
            # Remove from offline users if they were offline and deliver pending messages
            if user_id in self.offline_users and deliver_pending:
                # Deliver pending messages
                await self._deliver_pending_messages(user_id)
                del self.offline_users[user_id]
                
        except Exception as e:
            self.logger.error(f"Failed to update user activity for {user_id}: {e}")
    
    async def _handle_history_command(self, message: Message, user_profile) -> Optional[Message]:
        """Handle history command to retrieve message history"""
        parts = message.content.strip().split()
        
        # Parse command arguments
        filter_criteria = MessageFilter()
        
        if len(parts) > 1:
            # Parse arguments
            for i, part in enumerate(parts[1:], 1):
                if part.startswith('sender:'):
                    filter_criteria.sender_id = part[7:]
                elif part.startswith('channel:'):
                    try:
                        filter_criteria.channel = int(part[8:])
                    except ValueError:
                        pass
                elif part.startswith('hours:'):
                    try:
                        hours = int(part[6:])
                        filter_criteria.start_time = datetime.utcnow() - timedelta(hours=hours)
                    except ValueError:
                        pass
                elif part.startswith('limit:'):
                    try:
                        filter_criteria.limit = min(int(part[6:]), self.config['max_history_results'])
                    except ValueError:
                        pass
                elif part.startswith('search:'):
                    filter_criteria.content_pattern = part[7:]
        
        # Default to last 24 hours if no time filter specified
        if not filter_criteria.start_time:
            filter_criteria.start_time = datetime.utcnow() - timedelta(hours=24)
        
        # Retrieve messages
        messages = await self._get_message_history(filter_criteria)
        
        if not messages:
            response = "📜 No messages found matching your criteria."
        else:
            response = f"📜 Message History ({len(messages)} messages):\n\n"
            
            for msg in messages[-10:]:  # Show last 10 messages
                timestamp = msg['timestamp'][:16]  # YYYY-MM-DD HH:MM
                sender = msg['sender_id'][-4:]  # Last 4 chars of node ID
                content = msg['content'][:50]  # First 50 chars
                if len(msg['content']) > 50:
                    content += "..."
                
                response += f"{timestamp} {sender}: {content}\n"
            
            if len(messages) > 10:
                response += f"\n... and {len(messages) - 10} more messages"
        
        return self._create_response_message(response, message)
    
    async def _handle_messages_command(self, message: Message, user_profile) -> Optional[Message]:
        """Handle messages command to show recent messages"""
        parts = message.content.strip().split()
        limit = 5  # Default limit
        
        if len(parts) > 1:
            try:
                limit = min(int(parts[1]), 20)  # Max 20 messages
            except ValueError:
                pass
        
        # Get recent messages
        filter_criteria = MessageFilter(
            start_time=datetime.utcnow() - timedelta(hours=1),
            limit=limit
        )
        
        messages = await self._get_message_history(filter_criteria)
        
        if not messages:
            response = "📨 No recent messages found."
        else:
            response = f"📨 Recent Messages ({len(messages)}):\n\n"
            
            for msg in messages:
                timestamp = msg['timestamp'][11:16]  # HH:MM
                sender = msg['sender_id'][-4:]
                content = msg['content'][:40]
                if len(msg['content']) > 40:
                    content += "..."
                
                response += f"{timestamp} {sender}: {content}\n"
        
        return self._create_response_message(response, message)
    
    async def _handle_replay_command(self, message: Message, user_profile) -> Optional[Message]:
        """Handle replay command to replay messages with filtering"""
        parts = message.content.strip().split()
        
        if len(parts) < 2:
            response = "📺 Usage: replay <hours> [sender:nodeID] [channel:N] [search:text]"
            return self._create_response_message(response, message)
        
        try:
            hours = int(parts[1])
            if hours > 24:
                hours = 24  # Limit to 24 hours
        except ValueError:
            response = "❌ Invalid hours parameter. Use: replay <hours>"
            return self._create_response_message(response, message)
        
        # Parse additional filters
        filter_criteria = MessageFilter(
            start_time=datetime.utcnow() - timedelta(hours=hours),
            limit=50
        )
        
        for part in parts[2:]:
            if part.startswith('sender:'):
                filter_criteria.sender_id = part[7:]
            elif part.startswith('channel:'):
                try:
                    filter_criteria.channel = int(part[8:])
                except ValueError:
                    pass
            elif part.startswith('search:'):
                filter_criteria.content_pattern = part[7:]
        
        # Get messages
        messages = await self._get_message_history(filter_criteria)
        
        if not messages:
            response = f"📺 No messages found in the last {hours} hours."
        else:
            # Chunk the response if it's too large
            response_parts = []
            current_part = f"📺 Message Replay - Last {hours} hours ({len(messages)} messages):\n\n"
            
            for msg in messages:
                timestamp = msg['timestamp'][11:16]  # HH:MM
                sender = msg['sender_id'][-4:]
                channel_info = f"Ch{msg['channel']}" if msg['channel'] != 0 else ""
                content = msg['content']
                
                line = f"{timestamp} {sender} {channel_info}: {content}\n"
                
                # Check if adding this line would exceed chunk size
                if len(current_part + line) > self.max_message_chunk_size:
                    response_parts.append(current_part)
                    current_part = line
                else:
                    current_part += line
            
            # Add the last part
            if current_part.strip():
                response_parts.append(current_part)
            
            # Send chunked responses
            if len(response_parts) == 1:
                return self._create_response_message(response_parts[0], message)
            else:
                # Send multiple messages for large responses
                await self._send_chunked_response(response_parts, message)
                return None
        
        return self._create_response_message(response, message)
    
    async def _handle_pending_command(self, message: Message, user_profile) -> Optional[Message]:
        """Handle pending command to show pending messages for user"""
        user_id = message.sender_id
        
        # Check for pending messages
        pending = [msg for msg in self.pending_messages.values() 
                  if msg.recipient_id == user_id]
        
        if not pending:
            response = "📬 No pending messages."
        else:
            response = f"📬 You have {len(pending)} pending messages:\n\n"
            
            for msg in pending[:5]:  # Show first 5
                timestamp = msg.timestamp.strftime("%m-%d %H:%M")
                sender = msg.sender_id[-4:]
                content = msg.content[:40]
                if len(msg.content) > 40:
                    content += "..."
                
                response += f"{timestamp} from {sender}: {content}\n"
            
            if len(pending) > 5:
                response += f"\n... and {len(pending) - 5} more messages"
            
            response += "\n💡 These messages will be delivered automatically when you're active."
        
        return self._create_response_message(response, message)
    
    async def _handle_store_and_forward(self, message: Message):
        """Handle store-and-forward for direct messages to offline users"""
        if not self.store_forward_enabled:
            return
        
        recipient_id = message.recipient_id
        if not recipient_id or recipient_id == "^all":
            return
        
        # Check if recipient is online
        is_online = await self._is_user_online(recipient_id)
        
        if not is_online:
            # Store message for offline user
            await self._store_offline_message(message)
            self.logger.info(f"Stored message for offline user {recipient_id}")
    
    async def _is_user_online(self, user_id: str) -> bool:
        """Check if user is currently online"""
        try:
            db = get_database()
            rows = db.execute_query(
                "SELECT last_seen FROM users WHERE node_id = ?",
                (user_id,)
            )
            
            if not rows:
                return False
            
            last_seen_str = rows[0]['last_seen']
            if not last_seen_str:
                return False
            
            last_seen = datetime.fromisoformat(last_seen_str)
            offline_threshold = datetime.utcnow() - timedelta(minutes=10)
            
            return last_seen > offline_threshold
            
        except Exception as e:
            self.logger.error(f"Error checking if user {user_id} is online: {e}")
            return False
    
    async def _store_offline_message(self, message: Message):
        """Store message for offline user"""
        recipient_id = message.recipient_id
        
        # Check if user has too many pending messages
        user_pending_count = len([msg for msg in self.pending_messages.values() 
                                 if msg.recipient_id == recipient_id])
        
        if user_pending_count >= self.max_offline_messages:
            self.logger.warning(f"User {recipient_id} has too many pending messages, dropping oldest")
            # Remove oldest message for this user
            oldest_msg_id = None
            oldest_time = datetime.utcnow()
            
            for msg_id, msg in self.pending_messages.items():
                if msg.recipient_id == recipient_id and msg.timestamp < oldest_time:
                    oldest_time = msg.timestamp
                    oldest_msg_id = msg_id
            
            if oldest_msg_id:
                del self.pending_messages[oldest_msg_id]
        
        # Create stored message
        stored_msg = StoredMessage(
            id=message.id,
            recipient_id=recipient_id,
            sender_id=message.sender_id,
            content=message.content,
            timestamp=message.timestamp,
            priority=message.priority,
            expires_at=datetime.utcnow() + timedelta(hours=self.offline_message_ttl_hours),
            metadata={
                'channel': message.channel,
                'interface_id': message.interface_id,
                'original_message_type': message.message_type.value
            }
        )
        
        self.pending_messages[message.id] = stored_msg
        
        # Add user to offline tracking
        if recipient_id not in self.offline_users:
            self.offline_users[recipient_id] = OfflineUser(
                node_id=recipient_id,
                last_seen=datetime.utcnow() - timedelta(hours=1)  # Assume offline
            )
        
        self.offline_users[recipient_id].pending_messages.append(message.id)
        
        # Store in database for persistence
        try:
            db = get_database()
            db.execute_update(
                """
                INSERT OR REPLACE INTO system_config (key, value)
                VALUES (?, ?)
                """,
                (f"pending_message_{message.id}", json.dumps({
                    'recipient_id': recipient_id,
                    'sender_id': message.sender_id,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'priority': message.priority.value,
                    'expires_at': stored_msg.expires_at.isoformat(),
                    'metadata': stored_msg.metadata
                }))
            )
        except Exception as e:
            self.logger.error(f"Failed to persist offline message: {e}")
    
    async def _deliver_pending_messages(self, user_id: str):
        """Deliver pending messages to user who came online"""
        if user_id not in self.offline_users:
            return
        
        offline_user = self.offline_users[user_id]
        delivered_count = 0
        
        for msg_id in offline_user.pending_messages[:]:
            if msg_id in self.pending_messages:
                stored_msg = self.pending_messages[msg_id]
                
                # Check if message hasn't expired
                if datetime.utcnow() < stored_msg.expires_at:
                    # Create delivery message
                    delivery_msg = Message(
                        sender_id="system",
                        recipient_id=user_id,
                        content=f"📬 Offline message from {stored_msg.sender_id[-4:]}: {stored_msg.content}",
                        priority=stored_msg.priority,
                        metadata={'is_offline_delivery': True}
                    )
                    
                    # Send via communication interface
                    if self.communication:
                        try:
                            await self.communication.send_mesh_message(delivery_msg)
                            delivered_count += 1
                        except Exception as e:
                            self.logger.error(f"Failed to deliver offline message: {e}")
                
                # Remove from pending
                del self.pending_messages[msg_id]
                offline_user.pending_messages.remove(msg_id)
                
                # Remove from database
                try:
                    db = get_database()
                    db.execute_update(
                        "DELETE FROM system_config WHERE key = ?",
                        (f"pending_message_{msg_id}",)
                    )
                except Exception as e:
                    self.logger.error(f"Failed to remove pending message from database: {e}")
        
        if delivered_count > 0:
            # Send summary message
            summary_msg = Message(
                sender_id="system",
                recipient_id=user_id,
                content=f"📬 Delivered {delivered_count} offline messages. Send 'pending' to see any remaining.",
                priority=MessagePriority.NORMAL
            )
            
            if self.communication:
                try:
                    await self.communication.send_mesh_message(summary_msg)
                except Exception as e:
                    self.logger.error(f"Failed to send delivery summary: {e}")
            
            self.logger.info(f"Delivered {delivered_count} offline messages to {user_id}")
    
    async def _get_message_history(self, filter_criteria: MessageFilter) -> List[Dict[str, Any]]:
        """Retrieve message history based on filter criteria"""
        try:
            db = get_database()
            
            # Build query
            query_parts = ["SELECT * FROM message_history WHERE 1=1"]
            params = []
            
            if filter_criteria.sender_id:
                query_parts.append("AND sender_id = ?")
                params.append(filter_criteria.sender_id)
            
            if filter_criteria.recipient_id:
                query_parts.append("AND recipient_id = ?")
                params.append(filter_criteria.recipient_id)
            
            if filter_criteria.channel is not None:
                query_parts.append("AND channel = ?")
                params.append(filter_criteria.channel)
            
            if filter_criteria.content_pattern:
                query_parts.append("AND content LIKE ?")
                params.append(f"%{filter_criteria.content_pattern}%")
            
            if filter_criteria.start_time:
                query_parts.append("AND timestamp >= ?")
                params.append(filter_criteria.start_time.isoformat())
            
            if filter_criteria.end_time:
                query_parts.append("AND timestamp <= ?")
                params.append(filter_criteria.end_time.isoformat())
            
            if filter_criteria.interface_id:
                query_parts.append("AND interface_id = ?")
                params.append(filter_criteria.interface_id)
            
            if filter_criteria.min_snr is not None:
                query_parts.append("AND snr >= ?")
                params.append(filter_criteria.min_snr)
            
            if filter_criteria.max_hop_count is not None:
                query_parts.append("AND hop_count <= ?")
                params.append(filter_criteria.max_hop_count)
            
            # Add ordering and limits
            query_parts.append("ORDER BY timestamp DESC")
            query_parts.append("LIMIT ? OFFSET ?")
            params.extend([filter_criteria.limit, filter_criteria.offset])
            
            query = " ".join(query_parts)
            
            rows = db.execute_query(query, tuple(params))
            return [dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve message history: {e}")
            return []
    
    async def _send_chunked_response(self, response_parts: List[str], original_message: Message):
        """Send chunked response for large messages"""
        if not self.communication:
            return
        
        for i, part in enumerate(response_parts):
            chunk_msg = Message(
                sender_id="system",
                recipient_id=original_message.sender_id,
                content=f"[{i+1}/{len(response_parts)}] {part}",
                priority=MessagePriority.NORMAL,
                metadata={'is_chunked_response': True}
            )
            
            try:
                await self.communication.send_mesh_message(chunk_msg)
                # Small delay between chunks
                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Failed to send chunk {i+1}: {e}")
    
    def _create_response_message(self, content: str, original_message: Message) -> Message:
        """Create response message"""
        return Message(
            sender_id="system",
            recipient_id=original_message.sender_id,
            content=content,
            priority=MessagePriority.NORMAL,
            metadata={'response_to': original_message.id}
        )
    
    async def _load_offline_users(self):
        """Load offline users from database"""
        try:
            db = get_database()
            
            # Find users who haven't been seen recently
            offline_threshold = datetime.utcnow() - timedelta(minutes=10)
            rows = db.execute_query(
                "SELECT node_id, last_seen FROM users WHERE last_seen < ?",
                (offline_threshold.isoformat(),)
            )
            
            for row in rows:
                user_id = row['node_id']
                last_seen_str = row['last_seen']
                
                if last_seen_str:
                    last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = datetime.utcnow() - timedelta(hours=24)
                
                self.offline_users[user_id] = OfflineUser(
                    node_id=user_id,
                    last_seen=last_seen
                )
            
            self.logger.info(f"Loaded {len(self.offline_users)} offline users")
            
        except Exception as e:
            self.logger.error(f"Failed to load offline users: {e}")
    
    async def _load_pending_messages(self):
        """Load pending messages from database"""
        try:
            db = get_database()
            rows = db.execute_query(
                "SELECT key, value FROM system_config WHERE key LIKE 'pending_message_%'"
            )
            
            for row in rows:
                try:
                    msg_data = json.loads(row['value'])
                    msg_id = row['key'][16:]  # Remove 'pending_message_' prefix
                    
                    stored_msg = StoredMessage(
                        id=msg_id,
                        recipient_id=msg_data['recipient_id'],
                        sender_id=msg_data['sender_id'],
                        content=msg_data['content'],
                        timestamp=datetime.fromisoformat(msg_data['timestamp']),
                        priority=MessagePriority(msg_data['priority']),
                        expires_at=datetime.fromisoformat(msg_data['expires_at']),
                        metadata=msg_data.get('metadata', {})
                    )
                    
                    # Check if message hasn't expired
                    if datetime.utcnow() < stored_msg.expires_at:
                        self.pending_messages[msg_id] = stored_msg
                        
                        # Add to offline user tracking
                        recipient_id = stored_msg.recipient_id
                        if recipient_id not in self.offline_users:
                            self.offline_users[recipient_id] = OfflineUser(
                                node_id=recipient_id,
                                last_seen=datetime.utcnow() - timedelta(hours=1)
                            )
                        
                        self.offline_users[recipient_id].pending_messages.append(msg_id)
                    else:
                        # Remove expired message
                        db.execute_update(
                            "DELETE FROM system_config WHERE key = ?",
                            (row['key'],)
                        )
                
                except Exception as e:
                    self.logger.error(f"Failed to load pending message {row['key']}: {e}")
            
            self.logger.info(f"Loaded {len(self.pending_messages)} pending messages")
            
        except Exception as e:
            self.logger.error(f"Failed to load pending messages: {e}")
    
    async def _offline_check_task(self):
        """Periodic task to check for offline users and manage store-and-forward"""
        while self._running:
            try:
                await asyncio.sleep(self.config['offline_check_interval'])
                
                # Check for users who came back online
                online_users = []
                for user_id in list(self.offline_users.keys()):
                    if await self._is_user_online(user_id):
                        online_users.append(user_id)
                
                # Deliver pending messages to online users
                for user_id in online_users:
                    await self._deliver_pending_messages(user_id)
                
                # Update offline user list
                await self._update_offline_users()
                
            except Exception as e:
                self.logger.error(f"Error in offline check task: {e}")
    
    async def _cleanup_task(self):
        """Periodic cleanup task"""
        while self._running:
            try:
                await asyncio.sleep(self.config['cleanup_interval'])
                
                # Clean up expired pending messages
                expired_messages = []
                now = datetime.utcnow()
                
                for msg_id, stored_msg in self.pending_messages.items():
                    if now >= stored_msg.expires_at:
                        expired_messages.append(msg_id)
                
                for msg_id in expired_messages:
                    stored_msg = self.pending_messages[msg_id]
                    del self.pending_messages[msg_id]
                    
                    # Remove from offline user tracking
                    recipient_id = stored_msg.recipient_id
                    if recipient_id in self.offline_users:
                        if msg_id in self.offline_users[recipient_id].pending_messages:
                            self.offline_users[recipient_id].pending_messages.remove(msg_id)
                    
                    # Remove from database
                    try:
                        db = get_database()
                        db.execute_update(
                            "DELETE FROM system_config WHERE key = ?",
                            (f"pending_message_{msg_id}",)
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to remove expired message from database: {e}")
                
                if expired_messages:
                    self.logger.info(f"Cleaned up {len(expired_messages)} expired pending messages")
                
                # Clean up old message history
                await self._cleanup_old_history()
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
    
    async def _update_offline_users(self):
        """Update offline users list"""
        try:
            db = get_database()
            
            # Find users who haven't been seen recently
            offline_threshold = datetime.utcnow() - timedelta(minutes=10)
            rows = db.execute_query(
                "SELECT node_id, last_seen FROM users WHERE last_seen < ?",
                (offline_threshold.isoformat(),)
            )
            
            current_offline = set()
            for row in rows:
                user_id = row['node_id']
                current_offline.add(user_id)
                
                if user_id not in self.offline_users:
                    last_seen_str = row['last_seen']
                    if last_seen_str:
                        last_seen = datetime.fromisoformat(last_seen_str)
                    else:
                        last_seen = datetime.utcnow() - timedelta(hours=24)
                    
                    self.offline_users[user_id] = OfflineUser(
                        node_id=user_id,
                        last_seen=last_seen
                    )
            
            # Remove users who are no longer offline
            for user_id in list(self.offline_users.keys()):
                if user_id not in current_offline:
                    del self.offline_users[user_id]
            
        except Exception as e:
            self.logger.error(f"Failed to update offline users: {e}")
    
    async def _cleanup_old_history(self):
        """Clean up old message history"""
        try:
            db = get_database()
            cutoff_date = datetime.utcnow() - timedelta(days=self.history_retention_days)
            
            result = db.execute_update(
                "DELETE FROM message_history WHERE created_at < ?",
                (cutoff_date.isoformat(),)
            )
            
            if result > 0:
                self.logger.info(f"Cleaned up {result} old message history records")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old history: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            'offline_users': len(self.offline_users),
            'pending_messages': len(self.pending_messages),
            'store_forward_enabled': self.store_forward_enabled,
            'history_retention_days': self.history_retention_days,
            'max_offline_messages': self.max_offline_messages,
            'offline_message_ttl_hours': self.offline_message_ttl_hours
        }