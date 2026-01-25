"""
BBS Service Plugin

Wraps the BBS (Bulletin Board System) service as a plugin for the ZephyrGate plugin system.
This allows the BBS service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from bbs.bulletin_service import BulletinService
from bbs.mail_service import MailService
from bbs.channel_service import ChannelService
from bbs.menu_system import BBSMenuSystem
from bbs.database import BBSDatabase
from models.message import Message


class BBSServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the BBS (Bulletin Board System) Service.
    
    Provides:
    - Bulletin board for public messages
    - Private mail system
    - Channel directory
    - Menu-driven interface
    - Message synchronization
    """
    
    async def initialize(self) -> bool:
        """Initialize the BBS service plugin"""
        self.logger.info("Initializing BBS Service Plugin")
        
        try:
            # Initialize BBS database
            db_path = self.get_config('database.path', 'data/bbs.db')
            self.bbs_db = BBSDatabase(db_path)
            await self.bbs_db.initialize()
            
            # Create service instances
            self.bulletin_service = BulletinService(self.bbs_db, self.config)
            self.mail_service = MailService(self.bbs_db, self.config)
            self.channel_service = ChannelService(self.bbs_db, self.config)
            
            # Create menu system
            self.menu_system = BBSMenuSystem(
                self.bulletin_service,
                self.mail_service,
                self.channel_service,
                self.config
            )
            
            # Register BBS commands
            await self._register_bbs_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            self.logger.info("BBS Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize BBS service: {e}", exc_info=True)
            return False
    
    async def _register_bbs_commands(self):
        """Register BBS commands with the plugin system"""
        # Main BBS command
        self.register_command(
            "bbs",
            self._handle_bbs_command,
            "Access the Bulletin Board System",
            priority=50
        )
        
        # Read bulletin command
        self.register_command(
            "read",
            self._handle_read_command,
            "Read a bulletin by ID",
            priority=50
        )
        
        # Post bulletin command
        self.register_command(
            "post",
            self._handle_post_command,
            "Post a new bulletin",
            priority=50
        )
        
        # Mail command
        self.register_command(
            "mail",
            self._handle_mail_command,
            "Access mail system",
            priority=50
        )
        
        # Directory command
        self.register_command(
            "directory",
            self._handle_directory_command,
            "View channel directory",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for BBS service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is a BBS-related message
            content = message.content.lower().strip()
            
            # Let BBS commands be handled by command handlers
            if content.startswith(('bbs', 'read', 'post', 'mail', 'directory')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in BBS service: {e}", exc_info=True)
            return False
    
    async def _handle_bbs_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle main BBS command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            if not args:
                # Show main menu
                return await self.menu_system.show_main_menu(sender_id)
            
            # Handle menu navigation
            menu_option = args[0].lower()
            return await self.menu_system.handle_menu_selection(sender_id, menu_option, args[1:])
            
        except Exception as e:
            self.logger.error(f"Error in BBS command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_read_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle read bulletin command"""
        try:
            if not args:
                # List recent bulletins
                bulletins = await self.bulletin_service.list_bulletins(limit=10)
                if not bulletins:
                    return "No bulletins available"
                
                result = "📋 Recent Bulletins:\n"
                for bulletin in bulletins:
                    result += f"{bulletin.id}: {bulletin.subject} (by {bulletin.author})\n"
                result += "\nUse 'read <id>' to read a bulletin"
                return result
            
            # Read specific bulletin
            bulletin_id = args[0]
            bulletin = await self.bulletin_service.get_bulletin(bulletin_id)
            
            if not bulletin:
                return f"Bulletin {bulletin_id} not found"
            
            # Mark as read
            sender_id = context.get('sender_id', 'unknown')
            await self.bulletin_service.mark_read(bulletin_id, sender_id)
            
            return (
                f"📋 Bulletin {bulletin.id}\n"
                f"From: {bulletin.author}\n"
                f"Subject: {bulletin.subject}\n"
                f"Date: {bulletin.created_at}\n"
                f"\n{bulletin.content}"
            )
            
        except Exception as e:
            self.logger.error(f"Error in read command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_post_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle post bulletin command"""
        try:
            if len(args) < 2:
                return "Usage: post <subject> <content>"
            
            sender_id = context.get('sender_id', 'unknown')
            subject = args[0]
            content = ' '.join(args[1:])
            
            # Create bulletin
            bulletin = await self.bulletin_service.create_bulletin(
                author=sender_id,
                subject=subject,
                content=content
            )
            
            return f"✅ Bulletin posted successfully (ID: {bulletin.id})"
            
        except Exception as e:
            self.logger.error(f"Error in post command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_mail_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle mail command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            if not args:
                # Show inbox
                messages = await self.mail_service.get_inbox(sender_id, limit=10)
                if not messages:
                    return "📬 No mail"
                
                result = "📬 Inbox:\n"
                for msg in messages:
                    status = "📩" if msg.status == "unread" else "📧"
                    result += f"{status} {msg.id}: {msg.subject} (from {msg.sender})\n"
                result += "\nUse 'mail read <id>' to read a message"
                return result
            
            action = args[0].lower()
            
            if action == "read" and len(args) > 1:
                # Read specific mail
                mail_id = args[1]
                mail = await self.mail_service.get_mail(mail_id, sender_id)
                
                if not mail:
                    return f"Mail {mail_id} not found"
                
                # Mark as read
                await self.mail_service.mark_read(mail_id)
                
                return (
                    f"📧 Mail {mail.id}\n"
                    f"From: {mail.sender}\n"
                    f"To: {mail.recipient}\n"
                    f"Subject: {mail.subject}\n"
                    f"Date: {mail.created_at}\n"
                    f"\n{mail.content}"
                )
            
            elif action == "send" and len(args) > 3:
                # Send mail
                recipient = args[1]
                subject = args[2]
                content = ' '.join(args[3:])
                
                mail = await self.mail_service.send_mail(
                    sender=sender_id,
                    recipient=recipient,
                    subject=subject,
                    content=content
                )
                
                return f"✅ Mail sent successfully (ID: {mail.id})"
            
            else:
                return "Usage: mail [read <id> | send <recipient> <subject> <content>]"
            
        except Exception as e:
            self.logger.error(f"Error in mail command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_directory_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle directory command"""
        try:
            channels = await self.channel_service.list_channels()
            
            if not channels:
                return "No channels in directory"
            
            result = "📻 Channel Directory:\n"
            for channel in channels:
                result += f"{channel.channel_number}: {channel.name} - {channel.description}\n"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in directory command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up BBS service resources"""
        self.logger.info("Cleaning up BBS Service Plugin")
        
        try:
            if hasattr(self, 'bbs_db') and self.bbs_db:
                await self.bbs_db.close()
            
            self.logger.info("BBS Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up BBS service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get BBS service status"""
        status = {
            'service': 'bbs',
            'running': True,
            'features': {
                'bulletins': True,
                'mail': True,
                'channels': True,
                'menu_system': True
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="bbs_service",
            version="1.0.0",
            description="Bulletin Board System with mail, bulletins, and channel directory",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
