"""
Escalation and Check-in Management

Handles escalation of unacknowledged incidents and check-in systems:
- Automatic escalation for unacknowledged incidents
- Periodic check-in system for active SOS users
- Unresponsive user detection and alerting
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from models.message import SOSIncident, IncidentStatus, Message, MessagePriority
from .incident_manager import IncidentManager


@dataclass
class CheckInRequest:
    """Represents a check-in request"""
    incident_id: str
    sender_id: str
    request_time: datetime
    response_deadline: datetime
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class EscalationRule:
    """Defines escalation rules"""
    incident_type: str
    initial_timeout_minutes: int
    escalation_timeout_minutes: int
    max_escalations: int
    escalation_channels: List[str]


class EscalationManager:
    """Manages incident escalation and check-in systems"""
    
    def __init__(self, incident_manager: IncidentManager):
        self.logger = logging.getLogger(__name__)
        self.incident_manager = incident_manager
        
        # Escalation configuration
        self.escalation_rules = {
            'SOS': EscalationRule('SOS', 5, 10, 3, ['emergency', 'general']),
            'SOSP': EscalationRule('SOSP', 3, 8, 3, ['emergency', 'police']),
            'SOSF': EscalationRule('SOSF', 2, 5, 3, ['emergency', 'fire']),
            'SOSM': EscalationRule('SOSM', 2, 5, 3, ['emergency', 'medical'])
        }
        
        # Check-in configuration
        self.checkin_interval_minutes = 15  # Check-in every 15 minutes
        self.checkin_timeout_minutes = 5    # 5 minutes to respond to check-in
        self.max_missed_checkins = 2        # Max missed check-ins before alert
        
        # Tracking data
        self.pending_escalations: Dict[str, datetime] = {}
        self.escalation_counts: Dict[str, int] = {}
        self.active_checkins: Dict[str, CheckInRequest] = {}
        self.missed_checkins: Dict[str, int] = {}
        self.last_checkin_times: Dict[str, datetime] = {}
        
        # Background task control
        self._running = False
        self._escalation_task: Optional[asyncio.Task] = None
        self._checkin_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the escalation and check-in background tasks"""
        if self._running:
            return
        
        self._running = True
        self._escalation_task = asyncio.create_task(self._escalation_loop())
        self._checkin_task = asyncio.create_task(self._checkin_loop())
        
        self.logger.info("Escalation and check-in manager started")
    
    async def stop(self):
        """Stop the background tasks"""
        self._running = False
        
        if self._escalation_task:
            self._escalation_task.cancel()
            try:
                await self._escalation_task
            except asyncio.CancelledError:
                pass
        
        if self._checkin_task:
            self._checkin_task.cancel()
            try:
                await self._checkin_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Escalation and check-in manager stopped")
    
    def register_incident_for_escalation(self, incident: SOSIncident):
        """
        Register an incident for potential escalation
        
        Args:
            incident: The SOS incident to monitor
        """
        rule = self.escalation_rules.get(incident.incident_type.value)
        if not rule:
            self.logger.warning(f"No escalation rule for incident type {incident.incident_type.value}")
            return
        
        # Calculate initial escalation time
        escalation_time = incident.timestamp + timedelta(minutes=rule.initial_timeout_minutes)
        self.pending_escalations[incident.id] = escalation_time
        self.escalation_counts[incident.id] = 0
        
        self.logger.info(f"Registered incident {incident.id} for escalation at {escalation_time}")
    
    def cancel_escalation(self, incident_id: str):
        """
        Cancel escalation for an incident (when acknowledged)
        
        Args:
            incident_id: The incident ID to cancel escalation for
        """
        if incident_id in self.pending_escalations:
            del self.pending_escalations[incident_id]
            self.logger.info(f"Cancelled escalation for incident {incident_id}")
        
        if incident_id in self.escalation_counts:
            del self.escalation_counts[incident_id]
    
    def start_checkin_monitoring(self, incident: SOSIncident):
        """
        Start check-in monitoring for an active SOS user
        
        Args:
            incident: The SOS incident to monitor
        """
        self.last_checkin_times[incident.sender_id] = datetime.utcnow()
        self.missed_checkins[incident.sender_id] = 0
        
        self.logger.info(f"Started check-in monitoring for user {incident.sender_id}")
    
    def stop_checkin_monitoring(self, sender_id: str):
        """
        Stop check-in monitoring for a user
        
        Args:
            sender_id: The user to stop monitoring
        """
        if sender_id in self.last_checkin_times:
            del self.last_checkin_times[sender_id]
        
        if sender_id in self.missed_checkins:
            del self.missed_checkins[sender_id]
        
        # Cancel any active check-in requests
        to_remove = [req_id for req_id, req in self.active_checkins.items() 
                    if req.sender_id == sender_id]
        for req_id in to_remove:
            del self.active_checkins[req_id]
        
        self.logger.info(f"Stopped check-in monitoring for user {sender_id}")
    
    def handle_checkin_response(self, sender_id: str, message: str = "") -> Tuple[bool, str]:
        """
        Handle a check-in response from a user
        
        Args:
            sender_id: The user responding to check-in
            message: Optional message from user
            
        Returns:
            Tuple of (success, response_message)
        """
        # Find active check-in request for this user
        active_request = None
        request_id = None
        
        for req_id, request in self.active_checkins.items():
            if request.sender_id == sender_id:
                active_request = request
                request_id = req_id
                break
        
        if not active_request:
            return False, "No active check-in request found."
        
        # Remove the active request
        del self.active_checkins[request_id]
        
        # Update last check-in time and reset missed count
        self.last_checkin_times[sender_id] = datetime.utcnow()
        self.missed_checkins[sender_id] = 0
        
        response_msg = f"✅ Check-in received from {sender_id}"
        if message:
            response_msg += f"\nMessage: {message}"
        
        self.logger.info(f"Check-in response received from {sender_id}")
        return True, response_msg
    
    async def _escalation_loop(self):
        """Background loop for handling escalations"""
        while self._running:
            try:
                await self._process_escalations()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in escalation loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _checkin_loop(self):
        """Background loop for handling check-ins"""
        while self._running:
            try:
                await self._process_checkins()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in check-in loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _process_escalations(self):
        """Process pending escalations"""
        current_time = datetime.utcnow()
        escalations_to_process = []
        
        # Find incidents ready for escalation
        for incident_id, escalation_time in self.pending_escalations.items():
            if current_time >= escalation_time:
                escalations_to_process.append(incident_id)
        
        # Process escalations
        for incident_id in escalations_to_process:
            await self._escalate_incident(incident_id)
    
    async def _escalate_incident(self, incident_id: str):
        """Escalate a specific incident"""
        incident = self.incident_manager.get_incident(incident_id)
        if not incident or not incident.is_active():
            # Incident no longer active, remove from escalation
            self.cancel_escalation(incident_id)
            return
        
        # Check if incident has been acknowledged
        if incident.acknowledgers:
            # Incident acknowledged, cancel escalation
            self.cancel_escalation(incident_id)
            return
        
        # Get escalation rule
        rule = self.escalation_rules.get(incident.incident_type.value)
        if not rule:
            self.cancel_escalation(incident_id)
            return
        
        # Increment escalation count
        escalation_count = self.escalation_counts.get(incident_id, 0) + 1
        self.escalation_counts[incident_id] = escalation_count
        
        # Mark incident as escalated in database
        self.incident_manager.escalate_incident(incident_id)
        
        # Create escalation message
        escalation_msg = self._create_escalation_message(incident, escalation_count)
        
        # Schedule next escalation if under limit
        if escalation_count < rule.max_escalations:
            next_escalation = datetime.utcnow() + timedelta(minutes=rule.escalation_timeout_minutes)
            self.pending_escalations[incident_id] = next_escalation
        else:
            # Max escalations reached
            self.cancel_escalation(incident_id)
        
        self.logger.warning(f"Escalated incident {incident_id} (escalation #{escalation_count})")
        
        # Here you would send the escalation message through the message router
        # For now, we'll just log it
        self.logger.info(f"Escalation message: {escalation_msg.content}")
    
    async def _process_checkins(self):
        """Process check-in monitoring and requests"""
        current_time = datetime.utcnow()
        
        # Process active check-in requests (check for timeouts)
        expired_requests = []
        for req_id, request in self.active_checkins.items():
            if current_time >= request.response_deadline:
                expired_requests.append(req_id)
        
        # Handle expired check-in requests
        for req_id in expired_requests:
            request = self.active_checkins[req_id]
            await self._handle_missed_checkin(request)
            del self.active_checkins[req_id]
        
        # Check if new check-ins are needed
        for sender_id, last_checkin in self.last_checkin_times.items():
            time_since_checkin = current_time - last_checkin
            
            if time_since_checkin >= timedelta(minutes=self.checkin_interval_minutes):
                # Check if there's already an active request
                has_active_request = any(req.sender_id == sender_id 
                                       for req in self.active_checkins.values())
                
                if not has_active_request:
                    await self._send_checkin_request(sender_id)
    
    async def _send_checkin_request(self, sender_id: str):
        """Send a check-in request to a user"""
        # Find the active incident for this user
        active_incidents = self.incident_manager.get_incidents_by_sender(sender_id)
        active_incident = None
        
        for incident in active_incidents:
            if incident.is_active():
                active_incident = incident
                break
        
        if not active_incident:
            # No active incident, stop monitoring
            self.stop_checkin_monitoring(sender_id)
            return
        
        # Create check-in request
        request_id = f"checkin_{sender_id}_{datetime.utcnow().timestamp()}"
        request = CheckInRequest(
            incident_id=active_incident.id,
            sender_id=sender_id,
            request_time=datetime.utcnow(),
            response_deadline=datetime.utcnow() + timedelta(minutes=self.checkin_timeout_minutes)
        )
        
        self.active_checkins[request_id] = request
        
        # Create check-in message
        checkin_msg = self._create_checkin_message(active_incident, request)
        
        self.logger.info(f"Sent check-in request to {sender_id}")
        
        # Here you would send the check-in message through the message router
        # For now, we'll just log it
        self.logger.info(f"Check-in message: {checkin_msg.content}")
    
    async def _handle_missed_checkin(self, request: CheckInRequest):
        """Handle a missed check-in response"""
        missed_count = self.missed_checkins.get(request.sender_id, 0) + 1
        self.missed_checkins[request.sender_id] = missed_count
        
        self.logger.warning(f"User {request.sender_id} missed check-in #{missed_count}")
        
        if missed_count >= self.max_missed_checkins:
            # User is unresponsive, create alert
            alert_msg = self._create_unresponsive_alert(request, missed_count)
            
            self.logger.error(f"User {request.sender_id} is unresponsive after {missed_count} missed check-ins")
            
            # Here you would send the alert through the message router
            # For now, we'll just log it
            self.logger.info(f"Unresponsive alert: {alert_msg.content}")
        else:
            # Try again with shorter interval
            await asyncio.sleep(300)  # Wait 5 minutes before next attempt
            await self._send_checkin_request(request.sender_id)
    
    def _create_escalation_message(self, incident: SOSIncident, escalation_count: int) -> Message:
        """Create escalation message"""
        content = f"🚨 ESCALATED SOS ALERT #{escalation_count} 🚨\n"
        content += f"Incident: {incident.id[:8]}\n"
        content += f"Type: {incident.incident_type.value}\n"
        content += f"From: {incident.sender_id}\n"
        content += f"Time: {incident.timestamp.strftime('%H:%M:%S')}\n"
        
        if incident.message:
            content += f"Message: {incident.message}\n"
        
        if incident.location:
            content += f"Location: {incident.location[0]:.6f}, {incident.location[1]:.6f}\n"
        
        content += f"\n⚠️ NO RESPONSE AFTER {escalation_count} ESCALATION(S)\n"
        content += "IMMEDIATE ATTENTION REQUIRED!\n"
        content += "Reply with 'ACK' or 'RESPONDING' to acknowledge."
        
        return Message(
            content=content,
            sender_id="ESCALATION_SYSTEM",
            recipient_id="^all",
            priority=MessagePriority.EMERGENCY,
            metadata={
                'incident_id': incident.id,
                'escalation_count': escalation_count,
                'incident_type': incident.incident_type.value
            }
        )
    
    def _create_checkin_message(self, incident: SOSIncident, request: CheckInRequest) -> Message:
        """Create check-in request message"""
        content = f"📞 SOS Check-in Required\n"
        content += f"Incident: {incident.id[:8]}\n"
        content += f"Please respond within {self.checkin_timeout_minutes} minutes\n"
        content += "Reply with your status or 'OK' if you're safe.\n"
        content += "If you need immediate help, send another SOS."
        
        return Message(
            content=content,
            sender_id="CHECKIN_SYSTEM",
            recipient_id=request.sender_id,
            priority=MessagePriority.HIGH,
            metadata={
                'incident_id': incident.id,
                'checkin_request_id': f"checkin_{request.sender_id}_{request.request_time.timestamp()}",
                'response_deadline': request.response_deadline.isoformat()
            }
        )
    
    def _create_unresponsive_alert(self, request: CheckInRequest, missed_count: int) -> Message:
        """Create unresponsive user alert"""
        incident = self.incident_manager.get_incident(request.incident_id)
        
        content = f"🔴 UNRESPONSIVE USER ALERT 🔴\n"
        content += f"User: {request.sender_id}\n"
        content += f"Incident: {request.incident_id[:8]}\n"
        
        if incident:
            content += f"Type: {incident.incident_type.value}\n"
            content += f"Original Time: {incident.timestamp.strftime('%H:%M:%S')}\n"
            if incident.location:
                content += f"Last Location: {incident.location[0]:.6f}, {incident.location[1]:.6f}\n"
        
        content += f"\n⚠️ MISSED {missed_count} CHECK-INS\n"
        content += "USER MAY NEED IMMEDIATE ASSISTANCE!\n"
        content += "Consider dispatching emergency services."
        
        return Message(
            content=content,
            sender_id="UNRESPONSIVE_ALERT_SYSTEM",
            recipient_id="^all",
            priority=MessagePriority.EMERGENCY,
            metadata={
                'incident_id': request.incident_id,
                'unresponsive_user': request.sender_id,
                'missed_checkins': missed_count
            }
        )
    
    def get_escalation_status(self) -> Dict[str, any]:
        """Get current escalation status"""
        return {
            'pending_escalations': len(self.pending_escalations),
            'escalation_counts': self.escalation_counts.copy(),
            'active_checkins': len(self.active_checkins),
            'monitored_users': len(self.last_checkin_times),
            'missed_checkins': self.missed_checkins.copy()
        }