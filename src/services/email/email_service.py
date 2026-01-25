"""
Email Gateway Service Foundation

Main email service that provides two-way email gateway functionality,
email-to-mesh and mesh-to-email bridging, tag-based group messaging,
and email security features.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
import uuid

from core.plugin_manager import BasePlugin, PluginMetadata, PluginPriority
from core.plugin_interfaces import (
    BaseMessageHandler, BaseCommandHandler, 
    PluginCommunicationInterface
)
from models.message import Message, MessageType
from .models import (
    EmailMessage, EmailQueueItem, BlocklistEntry, EmailConfiguration,
    EmailStatistics, UserEmailMapping, EmailDirection, EmailStatus,
    EmailPriority, EmailAddress
)


class EmailMessageHandler(BaseMessageHandler):
    """Message handler for email-related messages"""
    
    def __init__(self, email_service: 'EmailGatewayService'):
        super().__init__(priority=60)
        self.email_service = email_service
    
    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the message"""
        content = message.content.lower().strip()
        
        # Email commands
        email_commands = [
            'email/', 'setemail', 'clearemail', 'emailstatus',
            'block/', 'unblock/', 'blocklist', 'broadcast/',
            'tagsend/', 'tagin/', 'tagout'
        ]
        
        return any(content.startswith(cmd) for cmd in email_commands)
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Handle email-related messages"""
        return await self.email_service.handle_email_command(message)


class EmailCommandHandler(BaseCommandHandler):
    """Command handler for email commands"""
    
    def __init__(self, email_service: 'EmailGatewayService'):
        commands = [
            'email', 'setemail', 'clearemail', 'emailstatus',
            'block', 'unblock', 'blocklist', 'broadcast',
            'tagsend', 'tagin', 'tagout', 'emailhelp'
        ]
        super().__init__(commands)
        self.email_service = email_service
        
        # Add help text
        self.add_help('email', 'Send email: email/to@domain.com/subject/message')
        self.add_help('setemail', 'Set your email address: setemail your@email.com')
        self.add_help('clearemail', 'Clear your email address')
        self.add_help('emailstatus', 'Check email gateway status')
        self.add_help('block', 'Block email address: block/spam@domain.com')
        self.add_help('unblock', 'Unblock email address: unblock/user@domain.com')
        self.add_help('blocklist', 'View blocked email addresses')
        self.add_help('broadcast', 'Send network broadcast via email (admin only)')
        self.add_help('tagsend', 'Send message to tagged users: tagsend/tag/message')
        self.add_help('tagin', 'Add yourself to a tag group: tagin/tagname')
        self.add_help('tagout', 'Remove yourself from a tag group: tagout/tagname')
        self.add_help('emailhelp', 'Show detailed email gateway help')
    
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """Handle email commands"""
        sender_id = context.get('sender_id', '')
        message = context.get('message')
        
        if command == 'email':
            return await self.email_service.handle_email_send_command(message)
        elif command == 'setemail':
            email = args[0] if args else ""
            return await self.email_service.set_user_email(sender_id, email)
        elif command == 'clearemail':
            return await self.email_service.clear_user_email(sender_id)
        elif command == 'emailstatus':
            return await self.email_service.get_email_status(sender_id)
        elif command == 'block':
            return await self.email_service.handle_block_command(message, sender_id)
        elif command == 'unblock':
            return await self.email_service.handle_unblock_command(message, sender_id)
        elif command == 'blocklist':
            return await self.email_service.get_blocklist_status(sender_id)
        elif command == 'broadcast':
            return await self.email_service.handle_broadcast_command(message, sender_id)
        elif command == 'tagsend':
            return await self.email_service.handle_tag_send_command(message, sender_id)
        elif command == 'tagin':
            tag = args[0] if args else ""
            return await self.email_service.add_user_tag(sender_id, tag)
        elif command == 'tagout':
            tag = args[0] if args else ""
            return await self.email_service.remove_user_tag(sender_id, tag)
        elif command == 'emailhelp':
            return await self.email_service.get_email_help()
        
        return f"Unknown email command: {command}"


class EmailGatewayService(BasePlugin):
    """
    Main email gateway service providing two-way email functionality
    """
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        
        # Configuration
        self.email_config = EmailConfiguration()
        self._load_configuration(config)
        
        # Core components
        self.message_queue: asyncio.Queue[EmailQueueItem] = asyncio.Queue(
            maxsize=self.email_config.queue_max_size
        )
        self.processing_queue: Dict[str, EmailQueueItem] = {}
        self.user_mappings: Dict[str, UserEmailMapping] = {}
        self.blocklist: Dict[str, BlocklistEntry] = {}
        self.statistics = EmailStatistics()
        
        # Email clients
        self.smtp_client = None
        self.imap_client = None
        
        # Data storage paths
        self.data_dir = Path(config.get('data_directory', 'data/email'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Background tasks
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.imap_monitor_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.statistics_task: Optional[asyncio.Task] = None
        
        # Message handlers
        self.message_handler = EmailMessageHandler(self)
        self.command_handler = EmailCommandHandler(self)
        
        # Communication interface
        self.comm: Optional[PluginCommunicationInterface] = None
        
        # Service state
        self.start_time = datetime.utcnow()
        
        self.logger.info(f"Email gateway service initialized with config: {config}")
    
    def _load_configuration(self, config: Dict[str, Any]):
        """Load and validate configuration"""
        email_config = config.get('email', {})
        
        # SMTP settings
        self.email_config.smtp_host = email_config.get('smtp_host', '')
        self.email_config.smtp_port = email_config.get('smtp_port', 587)
        self.email_config.smtp_username = email_config.get('smtp_username', '')
        self.email_config.smtp_password = email_config.get('smtp_password', '')
        self.email_config.smtp_use_tls = email_config.get('smtp_use_tls', True)
        self.email_config.smtp_use_ssl = email_config.get('smtp_use_ssl', False)
        self.email_config.smtp_timeout = email_config.get('smtp_timeout', 30)
        
        # IMAP settings
        self.email_config.imap_host = email_config.get('imap_host', '')
        self.email_config.imap_port = email_config.get('imap_port', 993)
        self.email_config.imap_username = email_config.get('imap_username', '')
        self.email_config.imap_password = email_config.get('imap_password', '')
        self.email_config.imap_use_ssl = email_config.get('imap_use_ssl', True)
        self.email_config.imap_timeout = email_config.get('imap_timeout', 30)
        self.email_config.imap_folder = email_config.get('imap_folder', 'INBOX')
        self.email_config.imap_check_interval = email_config.get('imap_check_interval', 300)
        
        # Gateway settings
        self.email_config.gateway_email = email_config.get('gateway_email', '')
        self.email_config.gateway_name = email_config.get('gateway_name', 'Meshtastic Gateway')
        
        # Security settings
        self.email_config.enable_blocklist = email_config.get('enable_blocklist', True)
        self.email_config.enable_sender_verification = email_config.get('enable_sender_verification', True)
        self.email_config.authorized_senders = email_config.get('authorized_senders', [])
        self.email_config.authorized_domains = email_config.get('authorized_domains', [])
        self.email_config.enable_spam_detection = email_config.get('enable_spam_detection', True)
        self.email_config.spam_keywords = email_config.get('spam_keywords', [
            'spam', 'viagra', 'casino', 'lottery', 'winner', 'congratulations',
            'urgent', 'act now', 'limited time', 'free money', 'click here'
        ])
        
        # Broadcast settings
        self.email_config.enable_broadcasts = email_config.get('enable_broadcasts', True)
        self.email_config.broadcast_authorized_senders = email_config.get('broadcast_authorized_senders', [])
        self.email_config.broadcast_confirmation_required = email_config.get('broadcast_confirmation_required', True)
        
        # Tag messaging
        self.email_config.enable_tag_messaging = email_config.get('enable_tag_messaging', True)
        self.email_config.tag_prefix = email_config.get('tag_prefix', '#')
        
        # Message processing
        self.email_config.max_message_size = email_config.get('max_message_size', 1024 * 1024)
        self.email_config.max_attachments = email_config.get('max_attachments', 5)
        self.email_config.max_attachment_size = email_config.get('max_attachment_size', 512 * 1024)
        self.email_config.message_retention_days = email_config.get('message_retention_days', 30)
        
        # Queue settings
        self.email_config.queue_max_size = email_config.get('queue_max_size', 1000)
        self.email_config.queue_batch_size = email_config.get('queue_batch_size', 10)
        self.email_config.queue_processing_interval = email_config.get('queue_processing_interval', 60)
        self.email_config.retry_delay_seconds = email_config.get('retry_delay_seconds', 300)
        self.email_config.max_retries = email_config.get('max_retries', 3)
        
        # Formatting
        self.email_config.email_footer = email_config.get('email_footer', '\n\n---\nSent via Meshtastic Gateway')
        self.email_config.mesh_message_prefix = email_config.get('mesh_message_prefix', '[Email] ')
        self.email_config.include_original_headers = email_config.get('include_original_headers', False)
    
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata"""
        return PluginMetadata(
            name="email_gateway_service",
            version="1.0.0",
            description="Two-way email gateway for mesh network communications",
            author="ZephyrGate",
            priority=PluginPriority.NORMAL
        )
    
    async def initialize(self) -> bool:
        """Initialize the email gateway service"""
        try:
            # Validate configuration
            config_errors = self.email_config.validate()
            if config_errors:
                self.logger.error(f"Email configuration errors: {config_errors}")
                return False
            
            # Initialize email clients
            from .smtp_client import SMTPClient
            from .imap_client import IMAPClient
            
            self.smtp_client = SMTPClient(self.email_config)
            self.imap_client = IMAPClient(self.email_config)
            
            # Add callback for incoming emails
            self.imap_client.add_message_callback(self._handle_incoming_email)
            
            # Start email clients
            await self.smtp_client.start()
            await self.imap_client.start()
            
            # Load persistent data
            await self._load_user_mappings()
            await self._load_blocklist()
            await self._load_statistics()
            
            # Register message and command handlers
            if hasattr(self.plugin_manager, 'register_message_handler'):
                await self.plugin_manager.register_message_handler(
                    self.message_handler, self.name
                )
            
            if hasattr(self.plugin_manager, 'register_command_handler'):
                await self.plugin_manager.register_command_handler(
                    self.command_handler, self.name
                )
            
            self.logger.info("Email gateway service initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize email gateway service: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the email gateway service"""
        try:
            if self.is_running:
                return True
            
            # Start background tasks
            self.queue_processor_task = self.create_task(self._queue_processor_loop())
            self.cleanup_task = self.create_task(self._cleanup_loop())
            self.statistics_task = self.create_task(self._statistics_loop())
            
            # Start IMAP monitoring if not already started
            if self.imap_client and not self.imap_client.is_monitoring:
                self.imap_monitor_task = self.create_task(self._start_imap_monitoring())
            
            self.is_running = True
            self.start_time = datetime.utcnow()
            self.logger.info("Email gateway service started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start email gateway service: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the email gateway service"""
        try:
            if not self.is_running:
                return True
            
            self.is_running = False
            self.signal_stop()
            
            # Cancel background tasks
            await self.cancel_tasks()
            
            # Save persistent data
            await self._save_user_mappings()
            await self._save_blocklist()
            await self._save_statistics()
            
            self.logger.info("Email gateway service stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop email gateway service: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up email gateway service resources"""
        try:
            # Close email clients
            if self.smtp_client:
                await self.smtp_client.stop()
            
            if self.imap_client:
                await self.imap_client.stop()
            
            # Clear queues and data
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            self.processing_queue.clear()
            
            self.logger.info("Email gateway service cleaned up")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup email gateway service: {e}")
            return False
    
    def set_communication_interface(self, comm: PluginCommunicationInterface):
        """Set the communication interface"""
        self.comm = comm
    
    # Command handling methods
    async def handle_email_command(self, message: Message) -> Optional[str]:
        """Handle email-related commands"""
        content = message.content.strip()
        sender_id = message.sender_id
        
        # Parse command and arguments
        parts = content.split('/')
        command = parts[0].lower()
        
        context = {
            'sender_id': sender_id,
            'message': message
        }
        
        # Map content-based commands to handler commands
        if command.startswith('email'):
            return await self.command_handler.handle_command('email', [], context)
        elif command.startswith('block'):
            return await self.command_handler.handle_command('block', [], context)
        elif command.startswith('unblock'):
            return await self.command_handler.handle_command('unblock', [], context)
        elif command.startswith('broadcast'):
            return await self.command_handler.handle_command('broadcast', [], context)
        elif command.startswith('tagsend'):
            return await self.command_handler.handle_command('tagsend', [], context)
        elif command.startswith('tagin'):
            return await self.command_handler.handle_command('tagin', [], context)
        elif command.startswith('tagout'):
            return await self.command_handler.handle_command('tagout', [], context)
        
        return None
    
    # Placeholder methods for subtasks (will be implemented in subsequent subtasks)
    async def handle_email_send_command(self, message: Message) -> str:
        """Handle email send command"""
        try:
            content = message.content.strip()
            sender_id = message.sender_id
            
            # Parse email command: email/to@domain.com/subject/message
            if not content.startswith('email/'):
                return "❌ Invalid email format. Use: email/to@domain.com/subject/message"
            
            parts = content[6:].split('/', 3)  # Remove 'email/' prefix
            if len(parts) < 3:
                return "❌ Invalid email format. Use: email/to@domain.com/subject/message"
            
            to_email = parts[0].strip()
            subject = parts[1].strip()
            body = parts[2].strip() if len(parts) > 2 else ""
            
            # Validate email address
            if '@' not in to_email or '.' not in to_email.split('@')[1]:
                return "❌ Invalid email address format"
            
            # Check if user has email configured (for reply-to)
            user_mapping = self.user_mappings.get(sender_id)
            
            # Create email message
            email_message = EmailMessage()
            email_message.direction = EmailDirection.MESH_TO_EMAIL
            email_message.priority = EmailPriority.NORMAL
            
            # Set sender info
            if user_mapping and user_mapping.email_address:
                email_message.from_address = EmailAddress(
                    address=user_mapping.email_address,
                    name=user_mapping.mesh_user_name or sender_id
                )
                email_message.reply_to = email_message.from_address
            else:
                email_message.from_address = EmailAddress(
                    address=self.email_config.gateway_email,
                    name=f"{self.email_config.gateway_name} ({sender_id})"
                )
            
            # Set recipient
            email_message.to_addresses = [EmailAddress.parse(to_email)]
            
            # Set subject and body
            email_message.subject = subject or f"Message from {sender_id}"
            
            # Format body with mesh context
            sender_name = getattr(message, 'sender_name', sender_id)
            mesh_info = f"From: {sender_name} ({sender_id})\n"
            mesh_info += f"Via: Meshtastic Gateway\n"
            mesh_info += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            
            email_message.body_text = mesh_info + body
            
            # Set mesh context
            email_message.mesh_sender_id = sender_id
            email_message.mesh_sender_name = sender_name
            email_message.mesh_channel = getattr(message, 'channel', None)
            email_message.mesh_interface_id = getattr(message, 'interface_id', None)
            
            # Queue for sending
            success = await self.queue_email_message(email_message)
            if success:
                self.statistics.total_messages_processed += 1
                self.statistics.mesh_to_email_count += 1
                return f"✅ Email queued for delivery to {to_email}"
            else:
                return "❌ Failed to queue email for delivery"
            
        except Exception as e:
            self.logger.error(f"Error handling email send command: {e}")
            return f"❌ Error sending email: {str(e)}"
    
    async def set_user_email(self, user_id: str, email: str) -> str:
        """Set user email address"""
        if not email:
            return "❌ Please provide an email address: setemail your@email.com"
        
        # Basic email validation
        if '@' not in email or '.' not in email.split('@')[1]:
            return "❌ Invalid email address format"
        
        # Create or update user mapping
        mapping = self.user_mappings.get(user_id, UserEmailMapping(mesh_user_id=user_id))
        mapping.email_address = email.lower().strip()
        mapping.last_used = datetime.utcnow()
        
        self.user_mappings[user_id] = mapping
        await self._save_user_mappings()
        
        return f"✅ Email address set to: {email}"
    
    async def clear_user_email(self, user_id: str) -> str:
        """Clear user email address"""
        if user_id in self.user_mappings:
            del self.user_mappings[user_id]
            await self._save_user_mappings()
            return "✅ Email address cleared"
        
        return "❌ No email address found to clear"
    
    async def get_email_status(self, user_id: str) -> str:
        """Get email gateway status for user"""
        mapping = self.user_mappings.get(user_id)
        
        status_lines = [
            "📧 Email Gateway Status:",
            f"Service: {'🟢 Online' if self.is_running else '🔴 Offline'}",
            f"Queue size: {self.message_queue.qsize()}/{self.email_config.queue_max_size}",
            f"Your email: {mapping.email_address if mapping else 'Not set'}",
        ]
        
        if mapping:
            status_lines.extend([
                f"Tags: {', '.join(mapping.tags) if mapping.tags else 'None'}",
                f"Broadcasts: {'✅' if mapping.receive_broadcasts else '❌'}",
                f"Group messages: {'✅' if mapping.receive_group_messages else '❌'}",
            ])
        
        return "\n".join(status_lines)
    
    async def handle_block_command(self, message: Message, sender_id: str) -> str:
        """Handle block command"""
        try:
            content = message.content.strip()
            
            # Check if user has admin privileges
            if not await self._is_admin_user(sender_id):
                return "❌ Only administrators can block email addresses"
            
            # Parse block command: block/email@domain.com or block/email@domain.com/reason
            if not content.startswith('block/'):
                return "❌ Invalid block format. Use: block/email@domain.com or block/email@domain.com/reason"
            
            parts = content[6:].split('/', 2)  # Remove 'block/' prefix
            if len(parts) < 1:
                return "❌ Please specify an email address to block"
            
            email_to_block = parts[0].strip().lower()
            reason = parts[1].strip() if len(parts) > 1 else "Blocked by administrator"
            
            # Validate email format
            if not email_to_block or '@' not in email_to_block:
                return "❌ Invalid email address format"
            
            # Check if already blocked
            for entry in self.blocklist.values():
                if entry.email_pattern.lower() == email_to_block:
                    return f"❌ Email address {email_to_block} is already blocked"
            
            # Create blocklist entry
            block_entry = BlocklistEntry(
                email_pattern=email_to_block,
                reason=reason,
                blocked_by=sender_id,
                is_active=True
            )
            
            self.blocklist[block_entry.id] = block_entry
            await self._save_blocklist()
            
            self.logger.info(f"Blocked email address {email_to_block} by {sender_id}: {reason}")
            return f"✅ Blocked email address: {email_to_block}"
            
        except Exception as e:
            self.logger.error(f"Error handling block command: {e}")
            return f"❌ Error blocking email: {str(e)}"
    
    async def handle_unblock_command(self, message: Message, sender_id: str) -> str:
        """Handle unblock command"""
        try:
            content = message.content.strip()
            
            # Check if user has admin privileges
            if not await self._is_admin_user(sender_id):
                return "❌ Only administrators can unblock email addresses"
            
            # Parse unblock command: unblock/email@domain.com
            if not content.startswith('unblock/'):
                return "❌ Invalid unblock format. Use: unblock/email@domain.com"
            
            email_to_unblock = content[8:].strip().lower()  # Remove 'unblock/' prefix
            
            if not email_to_unblock or '@' not in email_to_unblock:
                return "❌ Invalid email address format"
            
            # Find and remove blocklist entry
            entry_to_remove = None
            for entry_id, entry in self.blocklist.items():
                if entry.email_pattern.lower() == email_to_unblock:
                    entry_to_remove = entry_id
                    break
            
            if entry_to_remove:
                del self.blocklist[entry_to_remove]
                await self._save_blocklist()
                self.logger.info(f"Unblocked email address {email_to_unblock} by {sender_id}")
                return f"✅ Unblocked email address: {email_to_unblock}"
            else:
                return f"❌ Email address {email_to_unblock} is not blocked"
            
        except Exception as e:
            self.logger.error(f"Error handling unblock command: {e}")
            return f"❌ Error unblocking email: {str(e)}"
    
    async def get_blocklist_status(self, user_id: str) -> str:
        """Get blocklist status"""
        try:
            # Check if user has admin privileges
            if not await self._is_admin_user(user_id):
                return "❌ Only administrators can view the blocklist"
            
            active_blocks = [entry for entry in self.blocklist.values() if entry.is_active]
            
            if not active_blocks:
                return "📋 Email blocklist is empty"
            
            status_lines = [f"📋 Email Blocklist ({len(active_blocks)} entries):"]
            
            # Sort by creation date (most recent first)
            sorted_blocks = sorted(active_blocks, key=lambda x: x.created_at, reverse=True)
            
            for i, entry in enumerate(sorted_blocks[:10]):  # Show up to 10 entries
                age_days = (datetime.utcnow() - entry.created_at).days
                block_info = f"{i+1}. {entry.email_pattern}"
                
                if entry.block_count > 0:
                    block_info += f" (blocked {entry.block_count} times)"
                
                if age_days > 0:
                    block_info += f" - {age_days}d ago"
                
                if entry.reason and entry.reason != "Blocked by administrator":
                    block_info += f" - {entry.reason[:30]}..."
                
                status_lines.append(block_info)
            
            if len(active_blocks) > 10:
                status_lines.append(f"... and {len(active_blocks) - 10} more entries")
            
            return "\n".join(status_lines)
            
        except Exception as e:
            self.logger.error(f"Error getting blocklist status: {e}")
            return f"❌ Error retrieving blocklist: {str(e)}"
    
    async def handle_broadcast_command(self, message: Message, sender_id: str) -> str:
        """Handle broadcast command"""
        try:
            content = message.content.strip()
            
            # Check if broadcasts are enabled
            if not self.email_config.enable_broadcasts:
                return "❌ Broadcast functionality is disabled"
            
            # Check authorization
            user_mapping = self.user_mappings.get(sender_id)
            if not user_mapping or not user_mapping.email_address:
                return "❌ You must set an email address first to send broadcasts"
            
            # Check if user is authorized for broadcasts
            if not await self._is_broadcast_authorized(user_mapping.email_address):
                return "❌ You are not authorized to send broadcasts"
            
            # Parse broadcast command: broadcast/message
            if not content.startswith('broadcast/'):
                return "❌ Invalid broadcast format. Use: broadcast/your message"
            
            broadcast_message = content[10:].strip()  # Remove 'broadcast/' prefix
            if not broadcast_message:
                return "❌ Broadcast message cannot be empty"
            
            # Create broadcast email
            success = await self._send_network_broadcast_email(
                sender_id, user_mapping, broadcast_message
            )
            
            if success:
                return "✅ Network broadcast sent via email"
            else:
                return "❌ Failed to send network broadcast"
            
        except Exception as e:
            self.logger.error(f"Error handling broadcast command: {e}")
            return f"❌ Error sending broadcast: {str(e)}"
    
    async def handle_tag_send_command(self, message: Message, sender_id: str) -> str:
        """Handle tag send command"""
        try:
            content = message.content.strip()
            
            # Check if tag messaging is enabled
            if not self.email_config.enable_tag_messaging:
                return "❌ Tag messaging is disabled"
            
            # Parse tag send command: tagsend/tag/message
            if not content.startswith('tagsend/'):
                return "❌ Invalid tag send format. Use: tagsend/tagname/your message"
            
            parts = content[8:].split('/', 2)  # Remove 'tagsend/' prefix
            if len(parts) < 2:
                return "❌ Invalid tag send format. Use: tagsend/tagname/your message"
            
            tag = parts[0].strip().lower()
            tag_message = parts[1].strip()
            
            if not tag or not tag_message:
                return "❌ Tag name and message cannot be empty"
            
            # Validate tag name
            if not tag.isalnum():
                return "❌ Tag names must be alphanumeric"
            
            # Find users with the tag
            tagged_users = []
            for user_id, mapping in self.user_mappings.items():
                if mapping.has_tag(tag) and mapping.email_address:
                    tagged_users.append(mapping)
            
            if not tagged_users:
                return f"❌ No users found with tag: {tag}"
            
            # Get sender info
            sender_mapping = self.user_mappings.get(sender_id)
            sender_name = sender_mapping.mesh_user_name if sender_mapping else sender_id
            
            # Send tag message via email
            success = await self._send_tag_group_email(
                sender_id, sender_name, tag, tag_message, tagged_users
            )
            
            if success:
                return f"✅ Message sent to {len(tagged_users)} users with tag #{tag}"
            else:
                return f"❌ Failed to send message to tag group #{tag}"
            
        except Exception as e:
            self.logger.error(f"Error handling tag send command: {e}")
            return f"❌ Error sending tag message: {str(e)}"
    
    async def add_user_tag(self, user_id: str, tag: str) -> str:
        """Add tag to user"""
        if not tag:
            return "❌ Please provide a tag name: tagin/tagname"
        
        tag = tag.strip().lower()
        if not tag.isalnum():
            return "❌ Tag names must be alphanumeric"
        
        mapping = self.user_mappings.get(user_id, UserEmailMapping(mesh_user_id=user_id))
        mapping.add_tag(tag)
        self.user_mappings[user_id] = mapping
        await self._save_user_mappings()
        
        return f"✅ Added to tag group: {tag}"
    
    async def remove_user_tag(self, user_id: str, tag: str) -> str:
        """Remove tag from user"""
        if not tag:
            return "❌ Please provide a tag name: tagout/tagname"
        
        tag = tag.strip().lower()
        mapping = self.user_mappings.get(user_id)
        
        if not mapping or not mapping.has_tag(tag):
            return f"❌ You are not in tag group: {tag}"
        
        mapping.remove_tag(tag)
        await self._save_user_mappings()
        
        return f"✅ Removed from tag group: {tag}"
    
    async def get_email_help(self) -> str:
        """Get detailed email help"""
        help_text = """📧 Email Gateway Help:

Basic Commands:
• email/to@domain.com/subject/message - Send email
• setemail your@email.com - Set your email address
• clearemail - Clear your email address
• emailstatus - Check gateway status

Tag Messaging:
• tagin/tagname - Join a tag group
• tagout/tagname - Leave a tag group
• tagsend/tagname/message - Send to tag group

Admin Commands:
• block/spam@domain.com - Block email address
• unblock/user@domain.com - Unblock email address
• broadcast/message - Send network broadcast

The gateway bridges mesh and email communications bidirectionally."""
        
        return help_text
    
    # Queue management methods
    async def queue_email_message(self, email_message: EmailMessage, delay_seconds: int = 0) -> bool:
        """Queue an email message for processing"""
        try:
            scheduled_at = datetime.utcnow()
            if delay_seconds > 0:
                scheduled_at += timedelta(seconds=delay_seconds)
            
            queue_item = EmailQueueItem(
                email_message=email_message,
                scheduled_at=scheduled_at
            )
            
            await self.message_queue.put(queue_item)
            self.statistics.current_queue_size = self.message_queue.qsize()
            
            if self.statistics.current_queue_size > self.statistics.max_queue_size_reached:
                self.statistics.max_queue_size_reached = self.statistics.current_queue_size
            
            self.logger.debug(f"Queued email message: {email_message.id}")
            return True
            
        except asyncio.QueueFull:
            self.logger.error("Email queue is full, cannot queue message")
            return False
        except Exception as e:
            self.logger.error(f"Failed to queue email message: {e}")
            return False
    
    # Background task methods
    async def _queue_processor_loop(self):
        """Background task for processing email queue"""
        while self.is_running:
            try:
                # Process batch of messages
                batch_size = min(self.email_config.queue_batch_size, self.message_queue.qsize())
                
                for _ in range(batch_size):
                    try:
                        queue_item = await asyncio.wait_for(
                            self.message_queue.get(),
                            timeout=1.0
                        )
                        
                        if queue_item.is_ready_for_processing():
                            await self._process_email_queue_item(queue_item)
                        else:
                            # Re-queue if not ready
                            await self.message_queue.put(queue_item)
                        
                    except asyncio.TimeoutError:
                        break
                
                # Update statistics
                self.statistics.current_queue_size = self.message_queue.qsize()
                
                # Wait before next batch
                await asyncio.sleep(self.email_config.queue_processing_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in queue processor loop: {e}")
                await asyncio.sleep(60)
    
    async def _process_email_queue_item(self, queue_item: EmailQueueItem):
        """Process a single email queue item"""
        email_message = queue_item.email_message
        
        try:
            queue_item.processing_started_at = datetime.utcnow()
            self.processing_queue[queue_item.id] = queue_item
            
            # Process based on direction
            if email_message.direction == EmailDirection.MESH_TO_EMAIL:
                success = await self._process_mesh_to_email(email_message)
            elif email_message.direction == EmailDirection.EMAIL_TO_MESH:
                success = await self._process_email_to_mesh(email_message)
            elif email_message.direction == EmailDirection.BROADCAST:
                success = await self._process_broadcast_email(email_message)
            elif email_message.direction == EmailDirection.GROUP_MESSAGE:
                success = await self._process_group_message_email(email_message)
            else:
                success = False
                email_message.add_error(f"Unknown email direction: {email_message.direction}")
            
            if success:
                email_message.status = EmailStatus.SENT
                email_message.processed_at = datetime.utcnow()
                self.statistics.sent_count += 1
            else:
                if email_message.can_retry():
                    email_message.status = EmailStatus.RETRY
                    email_message.retry_count += 1
                    # Re-queue with delay
                    await self.queue_email_message(email_message, self.email_config.retry_delay_seconds)
                    self.statistics.retry_count += 1
                else:
                    email_message.status = EmailStatus.FAILED
                    self.statistics.failed_count += 1
            
        except Exception as e:
            self.logger.error(f"Error processing email queue item {queue_item.id}: {e}")
            email_message.add_error(str(e))
            email_message.status = EmailStatus.FAILED
            self.statistics.failed_count += 1
        
        finally:
            # Remove from processing queue
            if queue_item.id in self.processing_queue:
                del self.processing_queue[queue_item.id]
    
    # Placeholder processing methods (will be implemented in subtasks)
    async def _process_mesh_to_email(self, email_message: EmailMessage) -> bool:
        """Process mesh-to-email message"""
        try:
            self.logger.info(f"Processing mesh-to-email message: {email_message.id}")
            
            # Validate email message
            if not email_message.to_addresses:
                email_message.add_error("No recipients specified", "validation_error")
                self.statistics.validation_errors += 1
                return False
            
            # Check message size
            body_size = len((email_message.body_text or "").encode('utf-8'))
            if body_size > self.email_config.max_message_size:
                email_message.add_error(f"Message too large ({body_size} bytes)", "size_error")
                self.statistics.validation_errors += 1
                return False
            
            # Check for blocked recipients
            blocked_recipients = []
            for recipient in email_message.to_addresses:
                if await self._is_email_blocked(recipient.address):
                    blocked_recipients.append(recipient.address)
            
            if blocked_recipients:
                email_message.add_error(f"Blocked recipients: {blocked_recipients}", "blocked_recipient")
                self.statistics.blocked_count += 1
                return False
            
            # Send via SMTP client
            if not self.smtp_client:
                email_message.add_error("SMTP client not available", "smtp_error")
                self.statistics.smtp_errors += 1
                return False
            
            success = await self.smtp_client.send_email(email_message)
            
            if success:
                self.logger.info(f"Successfully sent mesh-to-email: {email_message.id}")
                
                # Send confirmation back to mesh if communication interface available
                if self.comm and email_message.mesh_sender_id:
                    confirmation_msg = f"✅ Email sent to {', '.join(addr.address for addr in email_message.to_addresses)}"
                    await self._send_mesh_confirmation(email_message.mesh_sender_id, confirmation_msg)
                
                return True
            else:
                self.logger.error(f"Failed to send mesh-to-email: {email_message.id}")
                self.statistics.smtp_errors += 1
                return False
            
        except Exception as e:
            self.logger.error(f"Error processing mesh-to-email {email_message.id}: {e}")
            email_message.add_error(str(e), "processing_error")
            return False
    
    async def _process_email_to_mesh(self, email_message: EmailMessage) -> bool:
        """Process email-to-mesh message"""
        try:
            self.logger.info(f"Processing email-to-mesh message: {email_message.id}")
            
            # Validate sender authorization
            if not await self._is_sender_authorized(email_message):
                email_message.add_error("Unauthorized sender", "authorization_error")
                self.statistics.unauthorized_attempts += 1
                return False
            
            # Check for spam
            if await self._is_spam_content(email_message):
                email_message.add_error("Spam content detected", "spam_error")
                self.statistics.spam_detected += 1
                return False
            
            # Parse email content for mesh commands
            from .email_parser import EmailParser
            parser = EmailParser()
            
            commands = parser.extract_mesh_commands(email_message.body_text or "")
            
            if not commands:
                email_message.add_error("No valid mesh commands found", "parsing_error")
                self.statistics.parsing_errors += 1
                return False
            
            # Process each command
            success_count = 0
            for command in commands:
                try:
                    if await self._process_mesh_command(email_message, command):
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"Error processing mesh command: {e}")
                    email_message.add_error(f"Command processing error: {e}", "command_error")
            
            # Consider successful if at least one command was processed
            if success_count > 0:
                self.logger.info(f"Successfully processed {success_count}/{len(commands)} commands from email: {email_message.id}")
                return True
            else:
                self.logger.error(f"Failed to process any commands from email: {email_message.id}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error processing email-to-mesh {email_message.id}: {e}")
            email_message.add_error(str(e), "processing_error")
            return False
    
    async def _process_broadcast_email(self, email_message: EmailMessage) -> bool:
        """Process broadcast email"""
        try:
            self.logger.info(f"Processing broadcast email: {email_message.id}")
            
            # Validate sender authorization for broadcasts
            if not email_message.from_address:
                email_message.add_error("No sender address", "validation_error")
                return False
            
            if not await self._is_broadcast_authorized(email_message.from_address.address):
                email_message.add_error("Unauthorized broadcast sender", "authorization_error")
                self.statistics.unauthorized_attempts += 1
                return False
            
            # Get all users who want to receive broadcasts
            broadcast_recipients = []
            for mapping in self.user_mappings.values():
                if mapping.receive_broadcasts and mapping.email_address:
                    broadcast_recipients.append(EmailAddress.parse(mapping.email_address))
            
            if not broadcast_recipients:
                email_message.add_error("No broadcast recipients found", "no_recipients")
                return False
            
            # Create broadcast email copies
            success_count = 0
            for recipient in broadcast_recipients:
                try:
                    # Create copy of email for each recipient
                    broadcast_copy = EmailMessage()
                    broadcast_copy.direction = EmailDirection.BROADCAST
                    broadcast_copy.priority = email_message.priority
                    broadcast_copy.from_address = email_message.from_address
                    broadcast_copy.to_addresses = [recipient]
                    broadcast_copy.subject = f"[Broadcast] {email_message.subject or 'Network Message'}"
                    broadcast_copy.body_text = email_message.body_text
                    broadcast_copy.body_html = email_message.body_html
                    
                    # Send via SMTP
                    if await self.smtp_client.send_email(broadcast_copy):
                        success_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error sending broadcast to {recipient.address}: {e}")
            
            # Consider successful if at least half were sent
            success_threshold = max(1, len(broadcast_recipients) // 2)
            if success_count >= success_threshold:
                self.logger.info(f"Broadcast sent to {success_count}/{len(broadcast_recipients)} recipients")
                self.statistics.broadcast_count += 1
                return True
            else:
                email_message.add_error(f"Only {success_count}/{len(broadcast_recipients)} broadcasts sent", "partial_failure")
                return False
            
        except Exception as e:
            self.logger.error(f"Error processing broadcast email {email_message.id}: {e}")
            email_message.add_error(str(e), "processing_error")
            return False
    
    async def _process_group_message_email(self, email_message: EmailMessage) -> bool:
        """Process group message email"""
        try:
            self.logger.info(f"Processing group message email: {email_message.id}")
            
            # Extract tags from email
            from .email_parser import EmailParser
            parser = EmailParser()
            
            tags = parser.extract_tags_from_subject(email_message.subject or "")
            if not tags:
                # Try to extract from body
                content = email_message.body_text or ""
                tag_matches = re.findall(rf'{self.email_config.tag_prefix}(\w+)', content)
                tags = [tag.lower() for tag in tag_matches]
            
            if not tags:
                email_message.add_error("No tags found in group message", "no_tags")
                return False
            
            # Find recipients for each tag
            all_recipients = set()
            for tag in tags:
                for mapping in self.user_mappings.values():
                    if mapping.has_tag(tag) and mapping.receive_group_messages and mapping.email_address:
                        all_recipients.add(mapping.email_address)
            
            if not all_recipients:
                email_message.add_error(f"No recipients found for tags: {tags}", "no_recipients")
                return False
            
            # Create group message copies
            success_count = 0
            for recipient_email in all_recipients:
                try:
                    # Create copy for each recipient
                    group_copy = EmailMessage()
                    group_copy.direction = EmailDirection.GROUP_MESSAGE
                    group_copy.priority = email_message.priority
                    group_copy.from_address = email_message.from_address
                    group_copy.to_addresses = [EmailAddress.parse(recipient_email)]
                    
                    # Format subject with tags
                    tag_str = ', '.join(f"#{tag}" for tag in tags)
                    group_copy.subject = f"[Tags: {tag_str}] {email_message.subject or 'Group Message'}"
                    
                    group_copy.body_text = email_message.body_text
                    group_copy.body_html = email_message.body_html
                    
                    # Send via SMTP
                    if await self.smtp_client.send_email(group_copy):
                        success_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error sending group message to {recipient_email}: {e}")
            
            # Consider successful if at least half were sent
            success_threshold = max(1, len(all_recipients) // 2)
            if success_count >= success_threshold:
                self.logger.info(f"Group message sent to {success_count}/{len(all_recipients)} recipients for tags: {tags}")
                self.statistics.group_message_count += 1
                return True
            else:
                email_message.add_error(f"Only {success_count}/{len(all_recipients)} group messages sent", "partial_failure")
                return False
            
        except Exception as e:
            self.logger.error(f"Error processing group message email {email_message.id}: {e}")
            email_message.add_error(str(e), "processing_error")
            return False
    
    async def _cleanup_loop(self):
        """Background task for cleanup"""
        while self.is_running:
            try:
                await self._cleanup_expired_messages()
                await self._cleanup_old_statistics()
                await asyncio.sleep(3600)  # Cleanup every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)
    
    async def _cleanup_expired_messages(self):
        """Clean up expired messages"""
        # This will be expanded when message persistence is implemented
        pass
    
    async def _cleanup_old_statistics(self):
        """Clean up old statistics"""
        # Reset statistics if they're too old
        if (datetime.utcnow() - self.statistics.last_reset).days > 30:
            self.statistics.reset()
            await self._save_statistics()
    
    async def _statistics_loop(self):
        """Background task for updating statistics"""
        while self.is_running:
            try:
                # Update uptime
                self.statistics.uptime_seconds = int(
                    (datetime.utcnow() - self.start_time).total_seconds()
                )
                
                # Calculate messages per hour
                if self.statistics.uptime_seconds > 0:
                    self.statistics.messages_per_hour = (
                        self.statistics.total_messages_processed * 3600.0 / 
                        self.statistics.uptime_seconds
                    )
                
                await asyncio.sleep(300)  # Update every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in statistics loop: {e}")
                await asyncio.sleep(60)
    
    # Data persistence methods
    async def _load_user_mappings(self):
        """Load user email mappings from file"""
        try:
            mappings_file = self.data_dir / "user_mappings.json"
            if mappings_file.exists():
                with open(mappings_file, 'r') as f:
                    data = json.load(f)
                
                for user_id, mapping_data in data.items():
                    mapping = UserEmailMapping(**mapping_data)
                    # Convert datetime strings back to datetime objects
                    if isinstance(mapping.created_at, str):
                        mapping.created_at = datetime.fromisoformat(mapping.created_at)
                    if isinstance(mapping.last_used, str) and mapping.last_used:
                        mapping.last_used = datetime.fromisoformat(mapping.last_used)
                    
                    self.user_mappings[user_id] = mapping
                
                self.logger.info(f"Loaded {len(self.user_mappings)} user email mappings")
        except Exception as e:
            self.logger.error(f"Failed to load user mappings: {e}")
    
    async def _save_user_mappings(self):
        """Save user email mappings to file"""
        try:
            mappings_file = self.data_dir / "user_mappings.json"
            data = {}
            
            for user_id, mapping in self.user_mappings.items():
                mapping_dict = {
                    'mesh_user_id': mapping.mesh_user_id,
                    'mesh_user_name': mapping.mesh_user_name,
                    'email_address': mapping.email_address,
                    'is_verified': mapping.is_verified,
                    'created_at': mapping.created_at.isoformat(),
                    'last_used': mapping.last_used.isoformat() if mapping.last_used else None,
                    'tags': mapping.tags,
                    'receive_broadcasts': mapping.receive_broadcasts,
                    'receive_group_messages': mapping.receive_group_messages,
                    'email_format': mapping.email_format,
                    'include_mesh_metadata': mapping.include_mesh_metadata
                }
                data[user_id] = mapping_dict
            
            with open(mappings_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to save user mappings: {e}")
    
    async def _load_blocklist(self):
        """Load email blocklist from file"""
        try:
            blocklist_file = self.data_dir / "blocklist.json"
            if blocklist_file.exists():
                with open(blocklist_file, 'r') as f:
                    data = json.load(f)
                
                for entry_id, entry_data in data.items():
                    entry = BlocklistEntry(**entry_data)
                    # Convert datetime strings back to datetime objects
                    if isinstance(entry.created_at, str):
                        entry.created_at = datetime.fromisoformat(entry.created_at)
                    if isinstance(entry.expires_at, str) and entry.expires_at:
                        entry.expires_at = datetime.fromisoformat(entry.expires_at)
                    if isinstance(entry.last_blocked_at, str) and entry.last_blocked_at:
                        entry.last_blocked_at = datetime.fromisoformat(entry.last_blocked_at)
                    
                    self.blocklist[entry_id] = entry
                
                self.logger.info(f"Loaded {len(self.blocklist)} blocklist entries")
        except Exception as e:
            self.logger.error(f"Failed to load blocklist: {e}")
    
    async def _save_blocklist(self):
        """Save email blocklist to file"""
        try:
            blocklist_file = self.data_dir / "blocklist.json"
            data = {}
            
            for entry_id, entry in self.blocklist.items():
                entry_dict = {
                    'id': entry.id,
                    'email_pattern': entry.email_pattern,
                    'reason': entry.reason,
                    'blocked_by': entry.blocked_by,
                    'created_at': entry.created_at.isoformat(),
                    'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                    'is_active': entry.is_active,
                    'block_count': entry.block_count,
                    'last_blocked_at': entry.last_blocked_at.isoformat() if entry.last_blocked_at else None
                }
                data[entry_id] = entry_dict
            
            with open(blocklist_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to save blocklist: {e}")
    
    async def _load_statistics(self):
        """Load statistics from file"""
        try:
            stats_file = self.data_dir / "statistics.json"
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    data = json.load(f)
                
                # Update statistics object
                for key, value in data.items():
                    if hasattr(self.statistics, key):
                        if key == 'last_reset' and isinstance(value, str):
                            setattr(self.statistics, key, datetime.fromisoformat(value))
                        else:
                            setattr(self.statistics, key, value)
                
                self.logger.info("Loaded email gateway statistics")
        except Exception as e:
            self.logger.error(f"Failed to load statistics: {e}")
    
    async def _save_statistics(self):
        """Save statistics to file"""
        try:
            stats_file = self.data_dir / "statistics.json"
            data = {
                'total_messages_processed': self.statistics.total_messages_processed,
                'mesh_to_email_count': self.statistics.mesh_to_email_count,
                'email_to_mesh_count': self.statistics.email_to_mesh_count,
                'broadcast_count': self.statistics.broadcast_count,
                'group_message_count': self.statistics.group_message_count,
                'sent_count': self.statistics.sent_count,
                'failed_count': self.statistics.failed_count,
                'blocked_count': self.statistics.blocked_count,
                'retry_count': self.statistics.retry_count,
                'current_queue_size': self.statistics.current_queue_size,
                'max_queue_size_reached': self.statistics.max_queue_size_reached,
                'average_processing_time_seconds': self.statistics.average_processing_time_seconds,
                'smtp_errors': self.statistics.smtp_errors,
                'imap_errors': self.statistics.imap_errors,
                'parsing_errors': self.statistics.parsing_errors,
                'validation_errors': self.statistics.validation_errors,
                'blocked_senders': self.statistics.blocked_senders,
                'spam_detected': self.statistics.spam_detected,
                'unauthorized_attempts': self.statistics.unauthorized_attempts,
                'messages_per_hour': self.statistics.messages_per_hour,
                'uptime_seconds': self.statistics.uptime_seconds,
                'last_reset': self.statistics.last_reset.isoformat()
            }
            
            with open(stats_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to save statistics: {e}")
    
    async def _start_imap_monitoring(self):
        """Start IMAP monitoring task"""
        try:
            if self.imap_client:
                await self.imap_client.start_monitoring()
        except Exception as e:
            self.logger.error(f"Failed to start IMAP monitoring: {e}")
    
    async def _handle_incoming_email(self, email_message: EmailMessage):
        """Handle incoming email from IMAP client"""
        try:
            self.logger.info(f"Received incoming email: {email_message.subject}")
            
            # Queue the email for processing
            await self.queue_email_message(email_message)
            
            # Update statistics
            self.statistics.total_messages_processed += 1
            self.statistics.email_to_mesh_count += 1
            
        except Exception as e:
            self.logger.error(f"Error handling incoming email: {e}")
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """Get comprehensive service statistics"""
        stats = {
            'service': {
                'is_running': self.is_running,
                'uptime_seconds': self.statistics.uptime_seconds,
                'start_time': self.start_time.isoformat() if hasattr(self, 'start_time') else None
            },
            'queue': {
                'current_size': self.statistics.current_queue_size,
                'max_size_reached': self.statistics.max_queue_size_reached,
                'processing_count': len(self.processing_queue)
            },
            'messages': {
                'total_processed': self.statistics.total_messages_processed,
                'mesh_to_email': self.statistics.mesh_to_email_count,
                'email_to_mesh': self.statistics.email_to_mesh_count,
                'broadcasts': self.statistics.broadcast_count,
                'group_messages': self.statistics.group_message_count,
                'sent': self.statistics.sent_count,
                'failed': self.statistics.failed_count,
                'blocked': self.statistics.blocked_count,
                'retries': self.statistics.retry_count
            },
            'errors': {
                'smtp_errors': self.statistics.smtp_errors,
                'imap_errors': self.statistics.imap_errors,
                'parsing_errors': self.statistics.parsing_errors,
                'validation_errors': self.statistics.validation_errors
            },
            'security': {
                'blocked_senders': self.statistics.blocked_senders,
                'spam_detected': self.statistics.spam_detected,
                'unauthorized_attempts': self.statistics.unauthorized_attempts,
                'blocklist_entries': len(self.blocklist)
            },
            'performance': {
                'messages_per_hour': self.statistics.messages_per_hour,
                'average_processing_time': self.statistics.average_processing_time_seconds
            }
        }
        
        # Add client statistics if available
        if self.smtp_client:
            stats['smtp'] = self.smtp_client.get_statistics()
        
        if self.imap_client:
            stats['imap'] = self.imap_client.get_statistics()
        
        return stats
    
    async def _is_email_blocked(self, email_address: str) -> bool:
        """Check if email address is blocked"""
        try:
            for entry in self.blocklist.values():
                if entry.matches(email_address):
                    entry.record_block()
                    self.logger.info(f"Blocked email address: {email_address} (matched: {entry.email_pattern})")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking email blocklist: {e}")
            return False
    
    async def _send_mesh_confirmation(self, recipient_id: str, message: str):
        """Send confirmation message back to mesh network"""
        try:
            if not self.comm:
                return
            
            from models.message import Message, MessageType
            
            confirmation = Message(
                sender_id="gateway",
                recipient_id=recipient_id,
                content=message,
                message_type=MessageType.TEXT,
                channel=0  # Use primary channel
            )
            
            await self.comm.send_mesh_message(confirmation)
            
        except Exception as e:
            self.logger.error(f"Error sending mesh confirmation: {e}")
    
    async def create_mesh_to_email_message(self, sender_id: str, sender_name: str, 
                                         to_email: str, subject: str, body: str,
                                         channel: Optional[int] = None,
                                         interface_id: Optional[str] = None) -> EmailMessage:
        """
        Create an email message from mesh network data
        
        Args:
            sender_id: Mesh sender ID
            sender_name: Mesh sender name
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            channel: Mesh channel (optional)
            interface_id: Mesh interface ID (optional)
            
        Returns:
            EmailMessage ready for processing
        """
        try:
            email_message = EmailMessage()
            email_message.direction = EmailDirection.MESH_TO_EMAIL
            email_message.priority = EmailPriority.NORMAL
            
            # Set sender info
            user_mapping = self.user_mappings.get(sender_id)
            if user_mapping and user_mapping.email_address:
                email_message.from_address = EmailAddress(
                    address=user_mapping.email_address,
                    name=user_mapping.mesh_user_name or sender_name
                )
                email_message.reply_to = email_message.from_address
            else:
                email_message.from_address = EmailAddress(
                    address=self.email_config.gateway_email,
                    name=f"{self.email_config.gateway_name} ({sender_name})"
                )
            
            # Set recipient
            email_message.to_addresses = [EmailAddress.parse(to_email)]
            
            # Set subject and body
            email_message.subject = subject or f"Message from {sender_name}"
            
            # Format body with mesh context
            mesh_info = f"From: {sender_name} ({sender_id})\n"
            mesh_info += f"Via: Meshtastic Gateway\n"
            mesh_info += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            if channel is not None:
                mesh_info += f"Channel: {channel}\n"
            if interface_id:
                mesh_info += f"Interface: {interface_id}\n"
            mesh_info += "\n"
            
            email_message.body_text = mesh_info + body
            
            # Set mesh context
            email_message.mesh_sender_id = sender_id
            email_message.mesh_sender_name = sender_name
            email_message.mesh_channel = channel
            email_message.mesh_interface_id = interface_id
            
            return email_message
            
        except Exception as e:
            self.logger.error(f"Error creating mesh-to-email message: {e}")
            raise
    
    async def send_mesh_to_email(self, sender_id: str, sender_name: str, 
                               to_email: str, subject: str, body: str,
                               channel: Optional[int] = None,
                               interface_id: Optional[str] = None,
                               priority: EmailPriority = EmailPriority.NORMAL) -> bool:
        """
        Send email from mesh network user
        
        Args:
            sender_id: Mesh sender ID
            sender_name: Mesh sender name
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            channel: Mesh channel (optional)
            interface_id: Mesh interface ID (optional)
            priority: Email priority
            
        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Create email message
            email_message = await self.create_mesh_to_email_message(
                sender_id, sender_name, to_email, subject, body, channel, interface_id
            )
            
            email_message.priority = priority
            
            # Queue for processing
            success = await self.queue_email_message(email_message)
            
            if success:
                self.statistics.total_messages_processed += 1
                self.statistics.mesh_to_email_count += 1
                self.logger.info(f"Queued mesh-to-email from {sender_id} to {to_email}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending mesh-to-email: {e}")
            return False
    
    async def validate_email_send_request(self, sender_id: str, to_email: str, 
                                        subject: str, body: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email send request
        
        Args:
            sender_id: Mesh sender ID
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if service is running
            if not self.is_running:
                return False, "Email service is not running"
            
            # Check SMTP client availability
            if not self.smtp_client or not self.smtp_client.is_connected:
                return False, "Email service is not connected"
            
            # Validate email address format
            if '@' not in to_email or '.' not in to_email.split('@')[1]:
                return False, "Invalid email address format"
            
            # Check if recipient is blocked
            if await self._is_email_blocked(to_email):
                return False, "Recipient email address is blocked"
            
            # Check message size
            total_size = len(subject.encode('utf-8')) + len(body.encode('utf-8'))
            if total_size > self.email_config.max_message_size:
                return False, f"Message too large ({total_size} bytes, max {self.email_config.max_message_size})"
            
            # Check queue capacity
            if self.message_queue.qsize() >= self.email_config.queue_max_size:
                return False, "Email queue is full, try again later"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error validating email send request: {e}")
            return False, f"Validation error: {e}"
    
    async def _is_sender_authorized(self, email_message: EmailMessage) -> bool:
        """Check if email sender is authorized"""
        try:
            if not email_message.from_address:
                return False
            
            sender_email = email_message.from_address.address.lower()
            
            # Check if sender verification is disabled
            if not self.email_config.enable_sender_verification:
                return True
            
            # Check authorized senders list
            authorized_senders = [addr.lower() for addr in self.email_config.authorized_senders]
            if sender_email in authorized_senders:
                return True
            
            # Check authorized domains
            if '@' in sender_email:
                domain = sender_email.split('@')[1]
                authorized_domains = [d.lower() for d in self.email_config.authorized_domains]
                if domain in authorized_domains:
                    return True
            
            # Check if sender has a user mapping (registered mesh user)
            for mapping in self.user_mappings.values():
                if mapping.email_address.lower() == sender_email:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking sender authorization: {e}")
            return False
    
    async def _is_spam_content(self, email_message: EmailMessage) -> bool:
        """Check if email content is spam"""
        try:
            if not self.email_config.enable_spam_detection:
                return False
            
            from .email_parser import EmailParser
            parser = EmailParser()
            
            # Check subject and body for spam
            content_to_check = []
            if email_message.subject:
                content_to_check.append(email_message.subject)
            if email_message.body_text:
                content_to_check.append(email_message.body_text)
            
            for content in content_to_check:
                is_spam, matched_keywords = parser.detect_spam_content(
                    content, self.email_config.spam_keywords
                )
                if is_spam:
                    self.logger.warning(f"Spam detected in email {email_message.id}: {matched_keywords}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking spam content: {e}")
            return False
    
    async def _process_mesh_command(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Process a single mesh command from email"""
        try:
            command_type = command.get('type', 'message')
            
            if command_type == 'broadcast':
                return await self._send_mesh_broadcast(email_message, command)
            elif command_type == 'tag_send':
                return await self._send_mesh_tag_message(email_message, command)
            elif command_type == 'direct_message':
                return await self._send_mesh_direct_message(email_message, command)
            elif command_type == 'mesh_command':
                return await self._send_mesh_command(email_message, command)
            elif command_type == 'message':
                return await self._send_mesh_message(email_message, command)
            else:
                self.logger.warning(f"Unknown command type: {command_type}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error processing mesh command {command_type}: {e}")
            return False
    
    async def _send_mesh_broadcast(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Send broadcast message to mesh network"""
        try:
            if not self.comm:
                return False
            
            content = command.get('content', '')
            if not content:
                return False
            
            # Format message with email context
            sender_name = email_message.from_address.name or email_message.from_address.address
            formatted_content = f"{self.email_config.mesh_message_prefix}[Broadcast from {sender_name}] {content}"
            
            from models.message import Message, MessageType
            
            broadcast_msg = Message(
                sender_id="email_gateway",
                recipient_id=None,  # Broadcast
                content=formatted_content,
                message_type=MessageType.TEXT,
                channel=0  # Primary channel
            )
            
            success = await self.comm.send_mesh_message(broadcast_msg)
            if success:
                self.logger.info(f"Sent mesh broadcast from email: {email_message.id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending mesh broadcast: {e}")
            return False
    
    async def _send_mesh_tag_message(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Send message to tagged users on mesh network"""
        try:
            if not self.comm:
                return False
            
            tag = command.get('tag', '')
            content = command.get('content', '')
            
            if not tag or not content:
                return False
            
            # Find users with the specified tag
            tagged_users = []
            for user_id, mapping in self.user_mappings.items():
                if mapping.has_tag(tag):
                    tagged_users.append(user_id)
            
            if not tagged_users:
                self.logger.warning(f"No users found with tag: {tag}")
                return False
            
            # Format message with email context
            sender_name = email_message.from_address.name or email_message.from_address.address
            formatted_content = f"{self.email_config.mesh_message_prefix}[Tag #{tag} from {sender_name}] {content}"
            
            from models.message import Message, MessageType
            
            # Send to each tagged user
            success_count = 0
            for user_id in tagged_users:
                try:
                    tag_msg = Message(
                        sender_id="email_gateway",
                        recipient_id=user_id,
                        content=formatted_content,
                        message_type=MessageType.TEXT,
                        channel=0
                    )
                    
                    if await self.comm.send_mesh_message(tag_msg):
                        success_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Error sending tag message to {user_id}: {e}")
            
            self.logger.info(f"Sent tag message to {success_count}/{len(tagged_users)} users")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error sending mesh tag message: {e}")
            return False
    
    async def _send_mesh_direct_message(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Send direct message to specific mesh user"""
        try:
            if not self.comm:
                return False
            
            recipient = command.get('recipient', '')
            content = command.get('content', '')
            
            if not recipient or not content:
                return False
            
            # Find recipient user ID
            recipient_id = await self._resolve_mesh_recipient(recipient)
            if not recipient_id:
                self.logger.warning(f"Could not resolve mesh recipient: {recipient}")
                return False
            
            # Format message with email context
            sender_name = email_message.from_address.name or email_message.from_address.address
            formatted_content = f"{self.email_config.mesh_message_prefix}[From {sender_name}] {content}"
            
            from models.message import Message, MessageType
            
            direct_msg = Message(
                sender_id="email_gateway",
                recipient_id=recipient_id,
                content=formatted_content,
                message_type=MessageType.TEXT,
                channel=0
            )
            
            success = await self.comm.send_mesh_message(direct_msg)
            if success:
                self.logger.info(f"Sent direct message from email to {recipient_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending mesh direct message: {e}")
            return False
    
    async def _send_mesh_command(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Send command to mesh network"""
        try:
            if not self.comm:
                return False
            
            mesh_command = command.get('command', '')
            if not mesh_command:
                return False
            
            # Format command with email context
            sender_name = email_message.from_address.name or email_message.from_address.address
            formatted_content = f"{self.email_config.mesh_message_prefix}[Command from {sender_name}] {mesh_command}"
            
            from models.message import Message, MessageType
            
            cmd_msg = Message(
                sender_id="email_gateway",
                recipient_id=None,  # Broadcast command
                content=formatted_content,
                message_type=MessageType.TEXT,
                channel=0
            )
            
            success = await self.comm.send_mesh_message(cmd_msg)
            if success:
                self.logger.info(f"Sent mesh command from email: {mesh_command}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending mesh command: {e}")
            return False
    
    async def _send_mesh_message(self, email_message: EmailMessage, command: Dict[str, Any]) -> bool:
        """Send general message to mesh network"""
        try:
            if not self.comm:
                return False
            
            content = command.get('content', '')
            if not content:
                return False
            
            # Check if there's a specific recipient in the subject
            from .email_parser import EmailParser
            parser = EmailParser()
            
            recipient_id = parser.extract_recipient_from_subject(email_message.subject or "")
            
            # Format message with email context
            sender_name = email_message.from_address.name or email_message.from_address.address
            formatted_content = f"{self.email_config.mesh_message_prefix}[From {sender_name}] {content}"
            
            from models.message import Message, MessageType
            
            mesh_msg = Message(
                sender_id="email_gateway",
                recipient_id=recipient_id,  # None for broadcast, specific ID for direct
                content=formatted_content,
                message_type=MessageType.TEXT,
                channel=0
            )
            
            success = await self.comm.send_mesh_message(mesh_msg)
            if success:
                msg_type = "direct message" if recipient_id else "broadcast"
                self.logger.info(f"Sent mesh {msg_type} from email: {email_message.id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending mesh message: {e}")
            return False
    
    async def _resolve_mesh_recipient(self, recipient: str) -> Optional[str]:
        """Resolve recipient name/ID to mesh user ID"""
        try:
            # If it looks like a mesh ID, return as-is
            if recipient.startswith('!') and len(recipient) == 9:
                return recipient
            
            # Search in user mappings by name or ID
            for user_id, mapping in self.user_mappings.items():
                if (mapping.mesh_user_name and mapping.mesh_user_name.lower() == recipient.lower()) or \
                   user_id.lower() == recipient.lower():
                    return user_id
            
            # If not found, assume it's a valid mesh ID
            return recipient
            
        except Exception as e:
            self.logger.error(f"Error resolving mesh recipient {recipient}: {e}")
            return None
    
    async def process_incoming_email_to_mesh(self, raw_email: bytes) -> bool:
        """
        Process raw incoming email and convert to mesh messages
        
        Args:
            raw_email: Raw email bytes
            
        Returns:
            True if processed successfully
        """
        try:
            import email
            from .email_parser import EmailParser
            
            # Parse raw email
            email_obj = email.message_from_bytes(raw_email)
            
            # Convert to EmailMessage
            parser = EmailParser()
            email_message = await self.imap_client._parse_email_to_message(email_obj)
            
            if not email_message:
                self.logger.error("Failed to parse incoming email")
                return False
            
            # Queue for processing
            success = await self.queue_email_message(email_message)
            
            if success:
                self.statistics.total_messages_processed += 1
                self.statistics.email_to_mesh_count += 1
                self.logger.info(f"Queued incoming email for mesh processing: {email_message.id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing incoming email to mesh: {e}")
            return False
    
    async def _is_broadcast_authorized(self, email_address: str) -> bool:
        """Check if email address is authorized to send broadcasts"""
        try:
            email_lower = email_address.lower()
            
            # Check broadcast authorized senders
            authorized_senders = [addr.lower() for addr in self.email_config.broadcast_authorized_senders]
            if email_lower in authorized_senders:
                return True
            
            # Check general authorized senders if broadcast list is empty
            if not self.email_config.broadcast_authorized_senders:
                general_authorized = [addr.lower() for addr in self.email_config.authorized_senders]
                if email_lower in general_authorized:
                    return True
                
                # Check authorized domains
                if '@' in email_address:
                    domain = email_address.split('@')[1].lower()
                    authorized_domains = [d.lower() for d in self.email_config.authorized_domains]
                    if domain in authorized_domains:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking broadcast authorization: {e}")
            return False
    
    async def _send_network_broadcast_email(self, sender_id: str, sender_mapping: UserEmailMapping, 
                                          message: str) -> bool:
        """Send network broadcast via email"""
        try:
            # Get all users who want to receive broadcasts
            broadcast_recipients = []
            for mapping in self.user_mappings.values():
                if mapping.receive_broadcasts and mapping.email_address and mapping.mesh_user_id != sender_id:
                    broadcast_recipients.append(mapping)
            
            if not broadcast_recipients:
                self.logger.warning("No broadcast recipients found")
                return False
            
            # Create broadcast email
            email_message = EmailMessage()
            email_message.direction = EmailDirection.BROADCAST
            email_message.priority = EmailPriority.HIGH
            
            # Set sender
            email_message.from_address = EmailAddress(
                address=sender_mapping.email_address,
                name=sender_mapping.mesh_user_name or sender_id
            )
            
            # Set recipients (BCC for privacy)
            email_message.bcc_addresses = [
                EmailAddress.parse(mapping.email_address) for mapping in broadcast_recipients
            ]
            
            # Set subject and body
            email_message.subject = f"[Network Broadcast] Message from {sender_mapping.mesh_user_name or sender_id}"
            
            broadcast_body = f"Network Broadcast Message\n\n"
            broadcast_body += f"From: {sender_mapping.mesh_user_name or sender_id} ({sender_id})\n"
            broadcast_body += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            broadcast_body += f"Message:\n{message}"
            
            email_message.body_text = broadcast_body
            
            # Set mesh context
            email_message.mesh_sender_id = sender_id
            email_message.mesh_sender_name = sender_mapping.mesh_user_name
            
            # Queue for sending
            success = await self.queue_email_message(email_message)
            
            if success:
                self.statistics.total_messages_processed += 1
                self.statistics.broadcast_count += 1
                self.logger.info(f"Queued network broadcast from {sender_id} to {len(broadcast_recipients)} recipients")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending network broadcast email: {e}")
            return False
    
    async def _send_tag_group_email(self, sender_id: str, sender_name: str, tag: str, 
                                  message: str, tagged_users: List[UserEmailMapping]) -> bool:
        """Send message to tag group via email"""
        try:
            # Create group email
            email_message = EmailMessage()
            email_message.direction = EmailDirection.GROUP_MESSAGE
            email_message.priority = EmailPriority.NORMAL
            
            # Set sender
            sender_mapping = self.user_mappings.get(sender_id)
            if sender_mapping and sender_mapping.email_address:
                email_message.from_address = EmailAddress(
                    address=sender_mapping.email_address,
                    name=sender_name
                )
            else:
                email_message.from_address = EmailAddress(
                    address=self.email_config.gateway_email,
                    name=f"{self.email_config.gateway_name} ({sender_name})"
                )
            
            # Set recipients (BCC for privacy)
            email_message.bcc_addresses = [
                EmailAddress.parse(mapping.email_address) for mapping in tagged_users
            ]
            
            # Set subject and body
            email_message.subject = f"[Tag #{tag}] Message from {sender_name}"
            
            tag_body = f"Tag Group Message\n\n"
            tag_body += f"Tag: #{tag}\n"
            tag_body += f"From: {sender_name} ({sender_id})\n"
            tag_body += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            tag_body += f"Message:\n{message}"
            
            email_message.body_text = tag_body
            
            # Set mesh context
            email_message.mesh_sender_id = sender_id
            email_message.mesh_sender_name = sender_name
            
            # Add tag to metadata
            email_message.tags = [tag]
            
            # Queue for sending
            success = await self.queue_email_message(email_message)
            
            if success:
                self.statistics.total_messages_processed += 1
                self.statistics.group_message_count += 1
                self.logger.info(f"Queued tag group message from {sender_id} to tag #{tag} ({len(tagged_users)} recipients)")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending tag group email: {e}")
            return False
    
    async def _is_admin_user(self, user_id: str) -> bool:
        """Check if user has admin privileges"""
        try:
            # Check if user is in admin list (from config or database)
            admin_users = self.config.get('admin_users', [])
            if user_id in admin_users:
                return True
            
            # Check user mapping for admin privileges
            user_mapping = self.user_mappings.get(user_id)
            if user_mapping and user_mapping.has_tag('admin'):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking admin privileges: {e}")
            return False
    
    async def add_to_blocklist(self, email_pattern: str, reason: str = "", 
                             blocked_by: str = "system", expires_at: Optional[datetime] = None) -> bool:
        """
        Add email address or pattern to blocklist
        
        Args:
            email_pattern: Email address or pattern to block
            reason: Reason for blocking
            blocked_by: Who blocked the address
            expires_at: Optional expiration time
            
        Returns:
            True if added successfully
        """
        try:
            email_pattern = email_pattern.lower().strip()
            
            # Check if already blocked
            for entry in self.blocklist.values():
                if entry.email_pattern == email_pattern:
                    self.logger.warning(f"Email pattern {email_pattern} is already blocked")
                    return False
            
            # Create blocklist entry
            block_entry = BlocklistEntry(
                email_pattern=email_pattern,
                reason=reason or "Added to blocklist",
                blocked_by=blocked_by,
                expires_at=expires_at,
                is_active=True
            )
            
            self.blocklist[block_entry.id] = block_entry
            await self._save_blocklist()
            
            self.logger.info(f"Added {email_pattern} to blocklist by {blocked_by}: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding to blocklist: {e}")
            return False
    
    async def remove_from_blocklist(self, email_pattern: str) -> bool:
        """
        Remove email address or pattern from blocklist
        
        Args:
            email_pattern: Email address or pattern to unblock
            
        Returns:
            True if removed successfully
        """
        try:
            email_pattern = email_pattern.lower().strip()
            
            # Find and remove entry
            entry_to_remove = None
            for entry_id, entry in self.blocklist.items():
                if entry.email_pattern == email_pattern:
                    entry_to_remove = entry_id
                    break
            
            if entry_to_remove:
                del self.blocklist[entry_to_remove]
                await self._save_blocklist()
                self.logger.info(f"Removed {email_pattern} from blocklist")
                return True
            else:
                self.logger.warning(f"Email pattern {email_pattern} not found in blocklist")
                return False
            
        except Exception as e:
            self.logger.error(f"Error removing from blocklist: {e}")
            return False
    
    async def validate_email_security(self, email_message: EmailMessage) -> Tuple[bool, Optional[str]]:
        """
        Validate email message against security policies
        
        Args:
            email_message: Email message to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check sender authorization
            if not await self._is_sender_authorized(email_message):
                self.statistics.unauthorized_attempts += 1
                return False, "Sender not authorized"
            
            # Check sender blocklist
            if email_message.from_address:
                is_blocked, block_reason = await self.is_email_blocked(email_message.from_address.address)
                if is_blocked:
                    self.statistics.blocked_count += 1
                    return False, f"Sender blocked: {block_reason}"
            
            # Check for spam content
            if await self._is_spam_content(email_message):
                self.statistics.spam_detected += 1
                return False, "Spam content detected"
            
            # Check message size
            content_size = len((email_message.body_text or "").encode('utf-8'))
            if content_size > self.email_config.max_message_size:
                self.statistics.validation_errors += 1
                return False, f"Message too large ({content_size} bytes)"
            
            # Check attachment limits
            if len(email_message.attachments) > self.email_config.max_attachments:
                self.statistics.validation_errors += 1
                return False, f"Too many attachments ({len(email_message.attachments)})"
            
            for attachment in email_message.attachments:
                if attachment.get('size', 0) > self.email_config.max_attachment_size:
                    self.statistics.validation_errors += 1
                    return False, f"Attachment too large ({attachment.get('size', 0)} bytes)"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error validating email security: {e}")
            return False, f"Validation error: {e}"