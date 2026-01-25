"""
Emergency Service Plugin

Wraps the EmergencyResponseService as a plugin for the ZephyrGate plugin system.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from emergency.emergency_service import EmergencyResponseService
from models.message import Message


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
        self.register_command(
            "sos",
            self._handle_sos_command,
            "Send emergency SOS alert",
            priority=10  # High priority
        )
        
        self.register_command(
            "cancel",
            self._handle_cancel_command,
            "Cancel active SOS alert",
            priority=10
        )
        
        self.register_command(
            "respond",
            self._handle_respond_command,
            "Respond to an SOS alert",
            priority=10
        )
        
        self.register_command(
            "status",
            self._handle_status_command,
            "Check emergency status",
            priority=10
        )
        
        self.register_command(
            "incidents",
            self._handle_incidents_command,
            "List active incidents",
            priority=10
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
    
    async def _handle_sos_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle SOS command"""
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
                return "SOS alert sent"
                
        except Exception as e:
            self.logger.error(f"Error in SOS command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_cancel_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle cancel command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Create a message object for the emergency service
            message = Message(
                content="CANCEL",
                sender_id=sender_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "No active SOS to cancel"
                
        except Exception as e:
            self.logger.error(f"Error in cancel command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_respond_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle respond command"""
        try:
            if not args:
                return "Usage: respond <incident_id>"
            
            incident_id = args[0]
            sender_id = context.get('sender_id', 'unknown')
            
            # Create a message object for the emergency service
            message = Message(
                content=f"RESPOND {incident_id}",
                sender_id=sender_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return f"Responded to incident {incident_id}"
                
        except Exception as e:
            self.logger.error(f"Error in respond command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_status_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle status command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Create a message object for the emergency service
            message = Message(
                content="ACTIVE",
                sender_id=sender_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "No active incidents"
                
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_incidents_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle incidents list command"""
        try:
            # Get active incidents from incident manager
            if hasattr(self.emergency_service, 'incident_manager'):
                incidents = self.emergency_service.incident_manager.get_active_incidents()
                
                if not incidents:
                    return "No active incidents"
                
                result = ["Active Incidents:", "=" * 40]
                for incident in incidents:
                    result.append(f"ID: {incident.incident_id}")
                    result.append(f"Type: {incident.incident_type.value}")
                    result.append(f"From: {incident.sender_id}")
                    result.append(f"Status: {incident.status.value}")
                    result.append("")
                
                return "\n".join(result)
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error in incidents command: {e}")
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
