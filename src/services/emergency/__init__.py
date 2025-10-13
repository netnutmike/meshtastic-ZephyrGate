"""
Emergency Response Service Module

Provides comprehensive emergency response capabilities including:
- SOS alert handling and incident management
- Responder coordination and tracking
- Escalation systems for unacknowledged alerts
- Check-in systems for active SOS users
"""

from .emergency_service import EmergencyResponseService
from .incident_manager import IncidentManager
from .responder_coordinator import ResponderCoordinator
from .escalation_manager import EscalationManager

__all__ = [
    'EmergencyResponseService',
    'IncidentManager', 
    'ResponderCoordinator',
    'EscalationManager'
]