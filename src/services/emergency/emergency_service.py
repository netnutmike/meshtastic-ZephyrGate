"""
Emergency Response Service

Main service that coordinates all emergency response functionality:
- SOS alert handling with multiple incident support
- Responder coordination and incident tracking
- Escalation system for unacknowledged alerts
- Check-in system for active SOS users
- Incident resolution and clearing
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable

from models.message import Message, SOSIncident, SOSType, IncidentStatus, MessagePriority
from core.database import get_database
from .incident_manager import IncidentManager
from .responder_coordinator import ResponderCoordinator
from .escalation_manager import EscalationManager


class EmergencyResponseService:
    """
    Main emergency response service that coordinates all emergency functionality
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize managers
        self.incident_manager = IncidentManager()
        self.responder_coordinator = ResponderCoordinator(self.incident_manager)
        self.escalation_manager = EscalationManager(self.incident_manager)
        
        # Message callback for sending responses
        self.message_callback: Optional[Callable[[Message], None]] = None
        
        # Clearing commands
        self.clearing_commands = {
            'CLEAR': IncidentStatus.CLEARED,
            'CANCEL': IncidentStatus.CANCELLED,
            'SAFE': IncidentStatus.CLEARED
        }
        
        # Service state
        self._running = False
    
    async def start(self):
        """Start the emergency response service"""
        if self._running:
            return
        
        self._running = True
        await self.escalation_manager.start()
        
        self.logger.info("Emergency Response Service started")
    
    async def stop(self):
        """Stop the emergency response service"""
        if not self._running:
            return
        
        self._running = False
        await self.escalation_manager.stop()
        
        self.logger.info("Emergency Response Service stopped")
    
    def set_message_callback(self, callback: Callable[[Message], None]):
        """
        Set callback function for sending messages
        
        Args:
            callback: Function to call when sending messages
        """
        self.message_callback = callback
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """
        Handle incoming message for emergency response
        
        Args:
            message: The incoming message to process
            
        Returns:
            Response message if applicable, None otherwise
        """
        content = message.content.strip()
        sender_id = message.sender_id
        
        try:
            # Check for SOS commands
            sos_result = self.incident_manager.parse_sos_command(content)
            if sos_result:
                return await self._handle_sos_command(sender_id, sos_result, message)
            
            # Check for responder commands
            response_result = self.responder_coordinator.parse_response_command(content)
            if response_result:
                return await self._handle_responder_command(sender_id, response_result, message)
            
            # Check for clearing commands
            clearing_result = self._parse_clearing_command(content)
            if clearing_result:
                return await self._handle_clearing_command(sender_id, clearing_result, message)
            
            # Check for check-in responses
            if self._is_checkin_response(content):
                return await self._handle_checkin_response(sender_id, content, message)
            
            # Check for status commands
            if content.upper() in ['ACTIVE', 'ALERTSTATUS', 'INCIDENTS']:
                return await self._handle_status_command(sender_id, message)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error handling emergency message: {e}")
            return Message(
                content=f"Error processing emergency command: {str(e)}",
                sender_id="EMERGENCY_SYSTEM",
                recipient_id=sender_id,
                priority=MessagePriority.NORMAL
            )
    
    async def _handle_sos_command(
        self,
        sender_id: str,
        sos_result: Tuple[SOSType, str],
        original_message: Message
    ) -> Message:
        """Handle SOS command"""
        sos_type, additional_message = sos_result
        
        # Get user location if available
        location = None
        if hasattr(original_message, 'metadata') and original_message.metadata:
            lat = original_message.metadata.get('latitude')
            lon = original_message.metadata.get('longitude')
            if lat is not None and lon is not None:
                location = (lat, lon)
        
        # Create incident
        incident = self.incident_manager.create_incident(
            incident_type=sos_type,
            sender_id=sender_id,
            message=additional_message,
            location=location
        )
        
        # Register for escalation
        self.escalation_manager.register_incident_for_escalation(incident)
        
        # Start check-in monitoring
        self.escalation_manager.start_checkin_monitoring(incident)
        
        # Create emergency broadcast
        emergency_broadcast = self._create_emergency_broadcast(incident)
        if self.message_callback:
            self.message_callback(emergency_broadcast)
        
        # Create response to sender
        response_content = f"🚨 SOS ALERT SENT 🚨\n"
        response_content += f"Incident ID: {incident.id[:8]}\n"
        response_content += f"Type: {sos_type.value}\n"
        response_content += f"Time: {incident.timestamp.strftime('%H:%M:%S')}\n"
        response_content += "Emergency services have been notified.\n"
        response_content += "Help is on the way. Stay calm and safe."
        
        if additional_message:
            response_content += f"\nYour message: {additional_message}"
        
        self.logger.critical(f"SOS ALERT: {sos_type.value} from {sender_id} - {additional_message}")
        
        return Message(
            content=response_content,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id=sender_id,
            priority=MessagePriority.EMERGENCY,
            metadata={'incident_id': incident.id}
        )
    
    async def _handle_responder_command(
        self,
        sender_id: str,
        response_result: Tuple[str, str, str],
        original_message: Message
    ) -> Message:
        """Handle responder command"""
        action_type, incident_id, additional_message = response_result
        
        success, response_msg, affected_incidents = self.responder_coordinator.handle_responder_action(
            responder_id=sender_id,
            action_type=action_type,
            incident_id=incident_id,
            message=additional_message
        )
        
        if success and affected_incidents:
            # Cancel escalation for acknowledged incidents
            for incident in affected_incidents:
                if action_type in ['acknowledge', 'responding']:
                    self.escalation_manager.cancel_escalation(incident.id)
            
            # Send notifications about responder actions
            for incident in affected_incidents:
                notification = self.responder_coordinator.create_notification_message(
                    incident=incident,
                    action=action_type,
                    responder_id=sender_id,
                    additional_message=additional_message
                )
                if self.message_callback:
                    self.message_callback(notification)
        
        return Message(
            content=response_msg,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id=sender_id,
            priority=MessagePriority.HIGH if success else MessagePriority.NORMAL
        )
    
    async def _handle_clearing_command(
        self,
        sender_id: str,
        clearing_result: Tuple[str, str, str],
        original_message: Message
    ) -> Message:
        """Handle incident clearing command"""
        command, incident_id, additional_message = clearing_result
        status = self.clearing_commands[command]
        
        # Get incidents to clear
        if incident_id:
            incidents = [self.incident_manager.get_incident(incident_id)]
            incidents = [i for i in incidents if i is not None]
        else:
            # Clear all active incidents from this sender
            incidents = [i for i in self.incident_manager.get_incidents_by_sender(sender_id) 
                        if i.is_active()]
        
        if not incidents:
            return Message(
                content="No active incidents found to clear.",
                sender_id="EMERGENCY_SYSTEM",
                recipient_id=sender_id,
                priority=MessagePriority.NORMAL
            )
        
        cleared_incidents = []
        for incident in incidents:
            # Check if sender can clear this incident
            if incident.sender_id == sender_id or self._is_authorized_to_clear(sender_id, incident):
                if self.incident_manager.clear_incident(incident.id, sender_id, status):
                    cleared_incidents.append(incident)
                    
                    # Stop escalation and check-in monitoring
                    self.escalation_manager.cancel_escalation(incident.id)
                    self.escalation_manager.stop_checkin_monitoring(incident.sender_id)
        
        if cleared_incidents:
            # Create clearing broadcast
            clearing_broadcast = self._create_clearing_broadcast(cleared_incidents, sender_id, command)
            if self.message_callback:
                self.message_callback(clearing_broadcast)
            
            if len(cleared_incidents) == 1:
                incident = cleared_incidents[0]
                response_msg = f"✅ Incident {incident.id[:8]} marked as {status.value.upper()}"
            else:
                response_msg = f"✅ {len(cleared_incidents)} incidents marked as {status.value.upper()}"
            
            if additional_message:
                response_msg += f"\nMessage: {additional_message}"
        else:
            response_msg = "No incidents were cleared. Check permissions or incident IDs."
        
        return Message(
            content=response_msg,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id=sender_id,
            priority=MessagePriority.HIGH
        )
    
    async def _handle_checkin_response(
        self,
        sender_id: str,
        content: str,
        original_message: Message
    ) -> Message:
        """Handle check-in response"""
        # Extract message after common check-in responses
        checkin_responses = ['OK', 'SAFE', 'GOOD', 'FINE', 'CHECKIN']
        message = content
        
        for response in checkin_responses:
            if content.upper().startswith(response):
                message = content[len(response):].strip()
                break
        
        success, response_msg = self.escalation_manager.handle_checkin_response(sender_id, message)
        
        return Message(
            content=response_msg,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id=sender_id,
            priority=MessagePriority.NORMAL
        )
    
    async def _handle_status_command(self, sender_id: str, original_message: Message) -> Message:
        """Handle status request command"""
        active_incidents = self.incident_manager.get_active_incidents()
        
        if not active_incidents:
            return Message(
                content="No active emergency incidents.",
                sender_id="EMERGENCY_SYSTEM",
                recipient_id=sender_id,
                priority=MessagePriority.NORMAL
            )
        
        # Create status summary
        content = f"📋 Active Emergency Incidents ({len(active_incidents)})\n\n"
        
        for incident in active_incidents[:5]:  # Limit to 5 most recent
            content += f"🚨 {incident.id[:8]} - {incident.incident_type.value}\n"
            content += f"From: {incident.sender_id}\n"
            content += f"Status: {incident.status.value.title()}\n"
            content += f"Time: {incident.timestamp.strftime('%H:%M:%S')}\n"
            
            if incident.responders:
                content += f"Responders: {len(incident.responders)}\n"
            
            if incident.escalated:
                content += "⚠️ ESCALATED\n"
            
            content += "\n"
        
        if len(active_incidents) > 5:
            content += f"... and {len(active_incidents) - 5} more incidents\n"
        
        # Add escalation status
        escalation_status = self.escalation_manager.get_escalation_status()
        if escalation_status['pending_escalations'] > 0:
            content += f"\n⏰ {escalation_status['pending_escalations']} pending escalations\n"
        
        if escalation_status['active_checkins'] > 0:
            content += f"📞 {escalation_status['active_checkins']} active check-ins\n"
        
        return Message(
            content=content,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id=sender_id,
            priority=MessagePriority.NORMAL
        )
    
    def _parse_clearing_command(self, content: str) -> Optional[Tuple[str, str, str]]:
        """Parse clearing command"""
        content_upper = content.strip().upper()
        
        for command in self.clearing_commands.keys():
            if content_upper.startswith(command):
                remaining = content[len(command):].strip()
                
                # Extract incident ID if provided
                incident_id = ""
                additional_message = remaining
                
                if remaining:
                    parts = remaining.split(None, 1)
                    if parts and (parts[0].startswith('!') or len(parts[0]) > 8):
                        incident_id = parts[0]
                        additional_message = parts[1] if len(parts) > 1 else ""
                
                return command, incident_id, additional_message
        
        return None
    
    def _is_checkin_response(self, content: str) -> bool:
        """Check if message is a check-in response"""
        content_upper = content.strip().upper()
        checkin_responses = ['OK', 'SAFE', 'GOOD', 'FINE', 'CHECKIN', 'STATUS']
        
        return any(content_upper.startswith(response) for response in checkin_responses)
    
    def _is_authorized_to_clear(self, user_id: str, incident: SOSIncident) -> bool:
        """Check if user is authorized to clear an incident"""
        # For now, allow responders and acknowledgers to clear incidents
        return (user_id in incident.responders or 
                user_id in incident.acknowledgers or
                user_id == incident.sender_id)
    
    def _create_emergency_broadcast(self, incident: SOSIncident) -> Message:
        """Create emergency broadcast message"""
        # Determine urgency emoji based on incident type
        type_emojis = {
            'SOS': '🚨',
            'SOSP': '👮',
            'SOSF': '🚒',
            'SOSM': '🚑'
        }
        
        emoji = type_emojis.get(incident.incident_type.value, '🚨')
        
        content = f"{emoji} EMERGENCY ALERT {emoji}\n"
        content += f"Type: {incident.incident_type.value}\n"
        content += f"From: {incident.sender_id}\n"
        content += f"Incident: {incident.id[:8]}\n"
        content += f"Time: {incident.timestamp.strftime('%H:%M:%S')}\n"
        
        if incident.message:
            content += f"Message: {incident.message}\n"
        
        if incident.location:
            content += f"Location: {incident.location[0]:.6f}, {incident.location[1]:.6f}\n"
        
        content += "\n🆘 IMMEDIATE RESPONSE REQUIRED 🆘\n"
        content += "Reply with 'ACK' to acknowledge or 'RESPONDING' if you can help."
        
        return Message(
            content=content,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id="^all",  # Broadcast to all
            priority=MessagePriority.EMERGENCY,
            metadata={
                'incident_id': incident.id,
                'incident_type': incident.incident_type.value,
                'emergency_broadcast': True
            }
        )
    
    def _create_clearing_broadcast(
        self,
        incidents: List[SOSIncident],
        cleared_by: str,
        command: str
    ) -> Message:
        """Create incident clearing broadcast"""
        if len(incidents) == 1:
            incident = incidents[0]
            content = f"✅ INCIDENT RESOLVED\n"
            content += f"Incident: {incident.id[:8]}\n"
            content += f"Type: {incident.incident_type.value}\n"
            content += f"From: {incident.sender_id}\n"
            content += f"Cleared by: {cleared_by}\n"
            content += f"Status: {command}\n"
            content += f"Time: {datetime.utcnow().strftime('%H:%M:%S')}"
        else:
            content = f"✅ MULTIPLE INCIDENTS RESOLVED\n"
            content += f"Count: {len(incidents)}\n"
            content += f"Cleared by: {cleared_by}\n"
            content += f"Status: {command}\n"
            content += f"Time: {datetime.utcnow().strftime('%H:%M:%S')}\n\n"
            
            for incident in incidents:
                content += f"• {incident.id[:8]} ({incident.incident_type.value})\n"
        
        return Message(
            content=content,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id="^all",  # Broadcast to all
            priority=MessagePriority.HIGH,
            metadata={
                'incident_clearing': True,
                'cleared_by': cleared_by,
                'incident_count': len(incidents)
            }
        )
    
    def get_service_status(self) -> Dict[str, any]:
        """Get emergency service status"""
        active_incidents = self.incident_manager.get_active_incidents()
        incident_summary = self.incident_manager.get_incident_summary()
        escalation_status = self.escalation_manager.get_escalation_status()
        responder_assignments = self.responder_coordinator.get_responder_assignments()
        
        return {
            'running': self._running,
            'active_incidents': len(active_incidents),
            'incident_summary': incident_summary,
            'escalation_status': escalation_status,
            'responder_assignments': len(responder_assignments),
            'total_responders': len(set().union(*responder_assignments.values())) if responder_assignments else 0
        }