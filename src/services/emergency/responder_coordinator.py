"""
Responder Coordination System

Handles responder acknowledgment, response tracking, and coordination for SOS incidents:
- Responder acknowledgment and response tracking
- Multiple incident handling with incident selection
- Notification system for responders and stakeholders
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from src.models.message import SOSIncident, IncidentStatus, UserProfile, Message, MessagePriority
from src.core.database import get_database
from .incident_manager import IncidentManager


@dataclass
class ResponderAction:
    """Represents a responder action"""
    responder_id: str
    incident_id: str
    action_type: str  # 'ACK', 'RESPONDING', 'ON_SCENE', 'CLEAR'
    timestamp: datetime
    message: str = ""


class ResponderCoordinator:
    """Coordinates responder activities and notifications"""
    
    def __init__(self, incident_manager: IncidentManager):
        self.logger = logging.getLogger(__name__)
        self.incident_manager = incident_manager
        self.db = get_database()
        
        # Response command patterns
        self.response_commands = {
            'ACK': 'acknowledge',
            'ACKNOWLEDGE': 'acknowledge', 
            'RESPONDING': 'responding',
            'ONSCENE': 'on_scene',
            'ON_SCENE': 'on_scene'
        }
        
        # Track active responders per incident
        self.active_responders: Dict[str, Set[str]] = {}
    
    def parse_response_command(self, message_content: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse responder command from message content
        
        Args:
            message_content: The message content to parse
            
        Returns:
            Tuple of (action_type, incident_id, additional_message) or None
        """
        content = message_content.strip().upper()
        
        for command, action_type in self.response_commands.items():
            if content.startswith(command):
                # Extract remaining content after command
                remaining = message_content[len(command):].strip()
                
                # Check if incident ID is specified
                incident_id = ""
                additional_message = remaining
                
                # Look for incident ID pattern (first word that looks like an ID)
                if remaining:
                    parts = remaining.split(None, 1)
                    if parts and (parts[0].startswith('!') or len(parts[0]) > 8):
                        incident_id = parts[0]
                        additional_message = parts[1] if len(parts) > 1 else ""
                
                return action_type, incident_id, additional_message
        
        return None
    
    def handle_responder_action(
        self,
        responder_id: str,
        action_type: str,
        incident_id: str = "",
        message: str = ""
    ) -> Tuple[bool, str, List[SOSIncident]]:
        """
        Handle a responder action
        
        Args:
            responder_id: Node ID of the responder
            action_type: Type of action (acknowledge, responding, etc.)
            incident_id: Specific incident ID (optional)
            message: Additional message from responder
            
        Returns:
            Tuple of (success, response_message, affected_incidents)
        """
        try:
            if action_type == 'acknowledge':
                return self._handle_acknowledgment(responder_id, incident_id, message)
            elif action_type == 'responding':
                return self._handle_responding(responder_id, incident_id, message)
            elif action_type == 'on_scene':
                return self._handle_on_scene(responder_id, incident_id, message)

            else:
                return False, f"Unknown action type: {action_type}", []
                
        except Exception as e:
            self.logger.error(f"Error handling responder action: {e}")
            return False, f"Error processing response: {str(e)}", []
    
    def _handle_acknowledgment(
        self,
        responder_id: str,
        incident_id: str,
        message: str
    ) -> Tuple[bool, str, List[SOSIncident]]:
        """Handle responder acknowledgment"""
        incidents = self._get_target_incidents(incident_id)
        
        if not incidents:
            return False, "No active incidents found to acknowledge.", []
        
        affected_incidents = []
        
        for incident in incidents:
            # Add acknowledger to incident
            if self.incident_manager.add_acknowledger(incident.id, responder_id):
                # Get the updated incident
                updated_incident = self.incident_manager.get_incident(incident.id)
                if updated_incident:
                    affected_incidents.append(updated_incident)
                
                # Track active responder
                if incident.id not in self.active_responders:
                    self.active_responders[incident.id] = set()
                self.active_responders[incident.id].add(responder_id)
                
                self.logger.info(f"Responder {responder_id} acknowledged incident {incident.id}")
        
        if affected_incidents:
            if len(affected_incidents) == 1:
                incident = affected_incidents[0]
                response_msg = f"✅ Acknowledged SOS incident {incident.id[:8]} from {incident.sender_id}"
                if message:
                    response_msg += f"\nMessage: {message}"
            else:
                response_msg = f"✅ Acknowledged {len(affected_incidents)} active incidents"
                if message:
                    response_msg += f"\nMessage: {message}"
            
            return True, response_msg, affected_incidents
        else:
            return False, "Failed to acknowledge incidents.", []
    
    def _handle_responding(
        self,
        responder_id: str,
        incident_id: str,
        message: str
    ) -> Tuple[bool, str, List[SOSIncident]]:
        """Handle responder indicating they are responding"""
        incidents = self._get_target_incidents(incident_id)
        
        if not incidents:
            return False, "No active incidents found to respond to.", []
        
        affected_incidents = []
        
        for incident in incidents:
            # Add responder to incident
            if self.incident_manager.add_responder(incident.id, responder_id):
                # Update incident status to responding
                self.incident_manager.update_incident_status(incident.id, IncidentStatus.RESPONDING)
                
                # Get updated incident
                updated_incident = self.incident_manager.get_incident(incident.id)
                if updated_incident:
                    affected_incidents.append(updated_incident)
                
                # Track active responder
                if incident.id not in self.active_responders:
                    self.active_responders[incident.id] = set()
                self.active_responders[incident.id].add(responder_id)
                
                self.logger.info(f"Responder {responder_id} responding to incident {incident.id}")
        
        if affected_incidents:
            if len(affected_incidents) == 1:
                incident = affected_incidents[0]
                response_msg = f"🚨 Responding to SOS incident {incident.id[:8]} from {incident.sender_id}"
                if message:
                    response_msg += f"\nMessage: {message}"
            else:
                response_msg = f"🚨 Responding to {len(affected_incidents)} active incidents"
                if message:
                    response_msg += f"\nMessage: {message}"
            
            return True, response_msg, affected_incidents
        else:
            return False, "Failed to register response to incidents.", []
    
    def _handle_on_scene(
        self,
        responder_id: str,
        incident_id: str,
        message: str
    ) -> Tuple[bool, str, List[SOSIncident]]:
        """Handle responder indicating they are on scene"""
        incidents = self._get_target_incidents(incident_id)
        
        if not incidents:
            return False, "No active incidents found.", []
        
        affected_incidents = []
        
        for incident in incidents:
            # Ensure responder is added to incident
            self.incident_manager.add_responder(incident.id, responder_id)
            
            # Get updated incident
            updated_incident = self.incident_manager.get_incident(incident.id)
            if updated_incident:
                affected_incidents.append(updated_incident)
            
            self.logger.info(f"Responder {responder_id} on scene for incident {incident.id}")
        
        if affected_incidents:
            if len(affected_incidents) == 1:
                incident = affected_incidents[0]
                response_msg = f"📍 On scene for SOS incident {incident.id[:8]} from {incident.sender_id}"
                if message:
                    response_msg += f"\nMessage: {message}"
            else:
                response_msg = f"📍 On scene for {len(affected_incidents)} incidents"
                if message:
                    response_msg += f"\nMessage: {message}"
            
            return True, response_msg, affected_incidents
        else:
            return False, "Failed to register on-scene status.", []
    
    def _handle_clear_response(
        self,
        responder_id: str,
        incident_id: str,
        message: str
    ) -> Tuple[bool, str, List[SOSIncident]]:
        """Handle responder clearing their response"""
        incidents = self._get_target_incidents(incident_id)
        
        if not incidents:
            return False, "No active incidents found to clear response from.", []
        
        affected_incidents = []
        
        for incident in incidents:
            # Remove responder from active responders
            if incident.id in self.active_responders:
                self.active_responders[incident.id].discard(responder_id)
                if not self.active_responders[incident.id]:
                    del self.active_responders[incident.id]
            
            affected_incidents.append(incident)
            self.logger.info(f"Responder {responder_id} cleared response from incident {incident.id}")
        
        if affected_incidents:
            if len(affected_incidents) == 1:
                incident = affected_incidents[0]
                response_msg = f"🔄 Cleared response from SOS incident {incident.id[:8]}"
                if message:
                    response_msg += f"\nMessage: {message}"
            else:
                response_msg = f"🔄 Cleared response from {len(affected_incidents)} incidents"
                if message:
                    response_msg += f"\nMessage: {message}"
            
            return True, response_msg, affected_incidents
        else:
            return False, "Failed to clear response from incidents.", []
    
    def _get_target_incidents(self, incident_id: str) -> List[SOSIncident]:
        """Get target incidents for responder action"""
        if incident_id:
            # Specific incident requested
            incident = self.incident_manager.get_incident(incident_id)
            return [incident] if incident and incident.is_active() else []
        else:
            # All active incidents
            return self.incident_manager.get_active_incidents()
    
    def get_responder_assignments(self) -> Dict[str, List[str]]:
        """
        Get current responder assignments
        
        Returns:
            Dictionary mapping incident IDs to lists of responder IDs
        """
        assignments = {}
        active_incidents = self.incident_manager.get_active_incidents()
        
        for incident in active_incidents:
            if incident.responders:
                assignments[incident.id] = incident.responders.copy()
        
        return assignments
    
    def get_responder_workload(self) -> Dict[str, int]:
        """
        Get responder workload (number of active incidents per responder)
        
        Returns:
            Dictionary mapping responder IDs to incident counts
        """
        workload = {}
        active_incidents = self.incident_manager.get_active_incidents()
        
        for incident in active_incidents:
            for responder_id in incident.responders:
                workload[responder_id] = workload.get(responder_id, 0) + 1
        
        return workload
    
    def create_notification_message(
        self,
        incident: SOSIncident,
        action: str,
        responder_id: str,
        additional_message: str = ""
    ) -> Message:
        """
        Create notification message for incident updates
        
        Args:
            incident: The SOS incident
            action: The action taken (acknowledged, responding, etc.)
            responder_id: ID of the responder
            additional_message: Additional message content
            
        Returns:
            Message object for notification
        """
        # Create notification content
        action_emojis = {
            'acknowledge': '✅',
            'responding': '🚨',
            'on_scene': '📍',
            'clear_response': '🔄'
        }
        
        emoji = action_emojis.get(action, '📢')
        
        content = f"{emoji} SOS Update - Incident {incident.id[:8]}\n"
        content += f"Type: {incident.incident_type.value}\n"
        content += f"From: {incident.sender_id}\n"
        content += f"Action: {action.replace('_', ' ').title()}\n"
        content += f"Responder: {responder_id}\n"
        
        if additional_message:
            content += f"Message: {additional_message}\n"
        
        # Add incident details
        if incident.message:
            content += f"Original: {incident.message}\n"
        
        content += f"Status: {incident.status.value.title()}\n"
        content += f"Responders: {len(incident.responders)}\n"
        content += f"Time: {incident.timestamp.strftime('%H:%M:%S')}"
        
        return Message(
            content=content,
            sender_id="EMERGENCY_SYSTEM",
            recipient_id="^all",  # Broadcast to all
            priority=MessagePriority.HIGH,
            metadata={
                'incident_id': incident.id,
                'incident_type': incident.incident_type.value,
                'action': action,
                'responder_id': responder_id
            }
        )
    
    def get_incident_status_summary(self, incident_id: str) -> Optional[str]:
        """
        Get a summary of incident status and responders
        
        Args:
            incident_id: The incident ID
            
        Returns:
            Formatted status summary or None if incident not found
        """
        incident = self.incident_manager.get_incident(incident_id)
        if not incident:
            return None
        
        summary = f"📋 SOS Incident {incident.id[:8]} Status\n"
        summary += f"Type: {incident.incident_type.value}\n"
        summary += f"From: {incident.sender_id}\n"
        summary += f"Status: {incident.status.value.title()}\n"
        summary += f"Time: {incident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if incident.message:
            summary += f"Message: {incident.message}\n"
        
        if incident.location:
            summary += f"Location: {incident.location[0]:.6f}, {incident.location[1]:.6f}\n"
        
        if incident.acknowledgers:
            summary += f"Acknowledged by: {', '.join(incident.acknowledgers)}\n"
        
        if incident.responders:
            summary += f"Responders: {', '.join(incident.responders)}\n"
        
        if incident.escalated:
            summary += "⚠️ ESCALATED\n"
        
        if incident.cleared_by:
            summary += f"Cleared by: {incident.cleared_by} at {incident.cleared_at.strftime('%H:%M:%S')}\n"
        
        return summary