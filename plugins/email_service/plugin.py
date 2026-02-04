"""
Email Service Plugin

Wraps the Email Gateway service as a plugin for the ZephyrGate plugin system.
This allows the email service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import from src modules
from core.enhanced_plugin import EnhancedPlugin
from models.message import Message

# Import from local email modules
from .email.email_service import EmailGatewayService


class EmailServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Email Gateway Service.
    
    Provides:
    - Email to mesh gateway
    - Mesh to email gateway
    - Email checking and sending
    - SMTP and IMAP integration
    """
    
    async def initialize(self) -> bool:
        """Initialize the email service plugin"""
        self.logger.info("Initializing Email Service Plugin")
        
        try:
            # Create the email service instance with proper arguments
            self.email_service = EmailGatewayService(
                name=self.name,
                config=self.config,
                plugin_manager=self.plugin_manager
            )
            
            # Initialize the email service
            await self.email_service.start()
            
            # Register email commands
            await self._register_email_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            # Register scheduled task for checking email
            check_interval = self.get_config('check_interval', 300)
            if isinstance(check_interval, str):
                check_interval = int(check_interval)
            
            if check_interval > 0:
                self.register_scheduled_task(
                    name="check_email",
                    handler=self._check_email_task,
                    interval=check_interval
                )
            
            self.logger.info("Email Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize email service: {e}", exc_info=True)
            return False
    
    async def _register_email_commands(self):
        """Register email commands with the plugin system"""
        # Email command
        self.register_command(
            "email",
            self._handle_email_command,
            "Send or check email",
            priority=50
        )
        
        # Send command
        self.register_command(
            "send",
            self._handle_send_command,
            "Send an email",
            priority=50
        )
        
        # Check command
        self.register_command(
            "check",
            self._handle_check_command,
            "Check for new emails",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for email service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is an email-related message
            content = message.content.lower().strip()
            
            # Let email commands be handled by command handlers
            if content.startswith(('email', 'send', 'check')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in email service: {e}", exc_info=True)
            return False
    
    async def _handle_email_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle email command"""
        try:
            if not args:
                return "Usage: email [send <to> <subject> <body> | check]"
            
            action = args[0].lower()
            
            if action == "send" and len(args) >= 4:
                to_address = args[1]
                subject = args[2]
                body = ' '.join(args[3:])
                
                if hasattr(self.email_service, 'send_email'):
                    success = await self.email_service.send_email(to_address, subject, body)
                    return "✅ Email sent successfully" if success else "❌ Failed to send email"
                else:
                    return "Email sending not available"
            
            elif action == "check":
                if hasattr(self.email_service, 'check_email'):
                    count = await self.email_service.check_email()
                    return f"📧 {count} new email(s)" if count > 0 else "No new emails"
                else:
                    return "Email checking not available"
            
            else:
                return "Usage: email [send <to> <subject> <body> | check]"
            
        except Exception as e:
            self.logger.error(f"Error in email command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_send_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle send email command"""
        try:
            if len(args) < 3:
                return "Usage: send <to> <subject> <body>"
            
            to_address = args[0]
            subject = args[1]
            body = ' '.join(args[2:])
            
            if hasattr(self.email_service, 'send_email'):
                success = await self.email_service.send_email(to_address, subject, body)
                return "✅ Email sent successfully" if success else "❌ Failed to send email"
            else:
                return "Email sending not available"
            
        except Exception as e:
            self.logger.error(f"Error in send command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_check_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle check email command"""
        try:
            if hasattr(self.email_service, 'check_email'):
                count = await self.email_service.check_email()
                return f"📧 {count} new email(s)" if count > 0 else "No new emails"
            else:
                return "Email checking not available"
            
        except Exception as e:
            self.logger.error(f"Error in check command: {e}")
            return f"Error: {str(e)}"
    
    async def _check_email_task(self):
        """Scheduled task to check for new emails"""
        try:
            if hasattr(self.email_service, 'check_email'):
                await self.email_service.check_email()
        except Exception as e:
            self.logger.error(f"Error in check email task: {e}")
    
    async def cleanup(self):
        """Clean up email service resources"""
        self.logger.info("Cleaning up Email Service Plugin")
        
        try:
            if hasattr(self, 'email_service') and self.email_service:
                await self.email_service.stop()
            
            self.logger.info("Email Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up email service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get email service status"""
        status = {
            'service': 'email',
            'running': hasattr(self, 'email_service') and self.email_service is not None,
            'features': {
                'send': True,
                'receive': True,
                'smtp': self.get_config('smtp.enabled', True),
                'imap': self.get_config('imap.enabled', True)
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="email_service",
            version="1.0.0",
            description="Email gateway service for sending and receiving emails via mesh",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
