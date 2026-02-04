"""
Emergency Service Plugin

Wraps the EmergencyResponseService as a plugin for the ZephyrGate plugin system.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from models.message import Message

# Import from local emergency modules
from .emergency.emergency_service import EmergencyResponseService
from .emergency.menu_system import EmergencyMenuSystem


class EmergencyServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Emergency Response Service.
    
    Provides:
    - SOS alert handling
    - Incident management
    - Responder coordination
    - Escalation system
    - Check-in system
    """
    
    async def initialize(self) -> bool:
        """Initialize the emergency service plugin"""
        self.logger.info("Initializing Emergency Service Plugin")
        
        try:
            # Create the emergency service instance with plugin config
            self.emergency_service = EmergencyResponseService(self.config)
            
            # Set up message callback to use plugin's send_message
            self.emergency_service.set_message_callback(self._send_emergency_message)
            
            # Start the emergency service
            await self.emergency_service.start()
            
            # Create menu system
            self.menu_system = EmergencyMenuSystem(self.emergency_service)
            
            # Register message handler with high priority for emergencies
            self.register_message_handler(
                self._handle_message,
                priority=10  # High priority for emergency messages
            )
            
            # Register emergency commands
            await self._register_emergency_commands()
            
            # Note: Escalation manager runs its own background tasks
            # No need to schedule additional tasks here
            
            self.logger.info("Emergency Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize emergency service: {e}", exc_info=True)
            return False
    
    async def _register_emergency_commands(self):
        """Register emergency service commands with the plugin system"""
        # Main emergency menu command
        self.register_command(
            "emergency",
            self._handle_emergency_menu_command,
            "Access emergency management system (submenu)",
            priority=10  # High priority
        )
        
        # Quick SOS command (always available at top level for emergencies)
        self.register_command(
            "sos",
            self._handle_sos_command,
            "Send emergency SOS alert (quick access)",
            priority=10  # High priority
        )
    
    async def _handle_message(self, message: Message) -> bool:
        """
        Handle incoming messages through the emergency service.
        
        Returns True if message was handled, False otherwise.
        """
        try:
            # Let the emergency service process the message
            response = await self.emergency_service.handle_message(message)
            
            if response:
                # Send the response
                await self.send_message(
                    response.content,
                    recipient_id=response.recipient_id,
                    priority=response.priority
                )
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in emergency service: {e}", exc_info=True)
            return False
    
    async def _send_emergency_message(self, message: Message):
        """Callback for emergency service to send messages"""
        try:
            await self.send_message(
                message.content,
                recipient_id=message.recipient_id,
                priority=message.priority
            )
        except Exception as e:
            self.logger.error(f"Error sending emergency message: {e}")
    
    async def _handle_emergency_menu_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle emergency menu command - enters emergency submenu"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Build command string from args
            command = ' '.join(args) if args else ''
            
            # Process command through menu system
            return await self.menu_system.process_command(sender_id, command, context)
            
        except Exception as e:
            self.logger.error(f"Error in emergency menu command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_sos_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick SOS command (always available at top level)"""
        try:
            message_text = " ".join(args) if args else "Emergency assistance needed"
            
            # Create a message object for the emergency service
            message = Message(
                content=f"SOS {message_text}",
                sender_id=context.get('sender_id', 'unknown'),
                recipient_id=None,
                metadata=context.get('metadata', {})
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "🚨 SOS alert sent"
                
        except Exception as e:
            self.logger.error(f"Error in SOS command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up emergency service resources"""
        self.logger.info("Cleaning up Emergency Service Plugin")
        
        try:
            if hasattr(self, 'emergency_service') and self.emergency_service:
                await self.emergency_service.stop()
            
            self.logger.info("Emergency Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up emergency service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get emergency service status"""
        status = {
            'service': 'emergency',
            'running': hasattr(self, 'emergency_service') and self.emergency_service._running,
            'features': {
                'sos_handling': True,
                'escalation': self.get_config('auto_escalate', True),
                'check_in': True
            }
        }
        
        # Add incident stats if available
        if hasattr(self, 'emergency_service') and hasattr(self.emergency_service, 'incident_manager'):
            try:
                incidents = self.emergency_service.incident_manager.get_active_incidents()
                status['active_incidents'] = len(incidents)
            except:
                pass
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="emergency_service",
            version="1.0.0",
            description="Emergency response service with SOS handling and incident management",
            author="ZephyrGate Team",
            priority=PluginPriority.CRITICAL
        )
