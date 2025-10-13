"""
Unit tests for Emergency Response Service

Tests all emergency response functionality including:
- SOS alert creation and responder notification
- Multiple incident handling and coordination
- Escalation and check-in functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.services.emergency.emergency_service import EmergencyResponseService
from src.services.emergency.incident_manager import IncidentManager
from src.services.emergency.responder_coordinator import ResponderCoordinator
from src.services.emergency.escalation_manager import EscalationManager
from src.models.message import Message, SOSIncident, SOSType, IncidentStatus, MessagePriority
from tests.base import BaseTestCase


class TestEmergencyResponseService(BaseTestCase):
    """Test emergency response service functionality"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        self.service = EmergencyResponseService()
        self.service.set_message_callback(Mock())
    
    @pytest.mark.asyncio
    async def test_sos_alert_creation(self):
        """Test SOS alert creation and notification"""
        # Create SOS message
        sos_message = Message(
            content="SOS Need help immediately!",
            sender_id="!12345678",
            metadata={'latitude': 40.7128, 'longitude': -74.0060}
        )
        
        # Handle SOS message
        response = await self.service.handle_message(sos_message)
        
        # Verify response
        self.assertIsNotNone(response)
        self.assertIn("SOS ALERT SENT", response.content)
        self.assertIn("Incident ID:", response.content)
        self.assertEqual(response.priority, MessagePriority.EMERGENCY)
        
        # Verify incident was created
        active_incidents = self.service.incident_manager.get_active_incidents()
        self.assertEqual(len(active_incidents), 1)
        
        incident = active_incidents[0]
        self.assertEqual(incident.incident_type, SOSType.SOS)
        self.assertEqual(incident.sender_id, "!12345678")
        self.assertEqual(incident.message, "Need help immediately!")
        self.assertEqual(incident.location, (40.7128, -74.0060))
        self.assertEqual(incident.status, IncidentStatus.ACTIVE)
        
        # Verify emergency broadcast was sent
        self.service.message_callback.assert_called()
        broadcast_call = self.service.message_callback.call_args[0][0]
        self.assertIn("EMERGENCY ALERT", broadcast_call.content)
        self.assertEqual(broadcast_call.recipient_id, "^all")
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test service start/stop lifecycle"""
        # Test starting service
        await self.service.start()
        self.assertTrue(self.service._running)
        
        # Test stopping service
        await self.service.stop()
        self.assertFalse(self.service._running)


class TestIncidentManager(BaseTestCase):
    """Test incident manager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        self.manager = IncidentManager()
    
    def test_sos_command_parsing(self):
        """Test SOS command parsing"""
        test_cases = [
            ("SOS", (SOSType.SOS, "")),
            ("SOS Help me", (SOSType.SOS, "Help me")),
            ("SOSP Police needed", (SOSType.SOSP, "Police needed")),
            ("SOSF Fire emergency", (SOSType.SOSF, "Fire emergency")),
            ("SOSM Medical help", (SOSType.SOSM, "Medical help")),
            ("Not an SOS", None)
        ]
        
        for message, expected in test_cases:
            result = self.manager.parse_sos_command(message)
            self.assertEqual(result, expected)
    
    def test_incident_creation(self):
        """Test incident creation"""
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!test123",
            message="Test emergency",
            location=(40.7128, -74.0060)
        )
        
        # Verify incident properties
        self.assertEqual(incident.incident_type, SOSType.SOS)
        self.assertEqual(incident.sender_id, "!test123")
        self.assertEqual(incident.message, "Test emergency")
        self.assertEqual(incident.location, (40.7128, -74.0060))
        self.assertEqual(incident.status, IncidentStatus.ACTIVE)
        self.assertIsNotNone(incident.id)
        self.assertIsInstance(incident.timestamp, datetime)
    
    def test_incident_retrieval(self):
        """Test incident retrieval"""
        # Create incident
        incident = self.manager.create_incident(
            incident_type=SOSType.SOSM,
            sender_id="!patient456",
            message="Medical emergency"
        )
        
        # Test get by ID
        retrieved = self.manager.get_incident(incident.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, incident.id)
        
        # Test get by sender
        sender_incidents = self.manager.get_incidents_by_sender("!patient456")
        self.assertEqual(len(sender_incidents), 1)
        self.assertEqual(sender_incidents[0].id, incident.id)
        
        # Test get active incidents
        active_incidents = self.manager.get_active_incidents()
        self.assertEqual(len(active_incidents), 1)
        self.assertEqual(active_incidents[0].id, incident.id)


class TestResponderCoordinator(BaseTestCase):
    """Test responder coordinator functionality"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        self.incident_manager = IncidentManager()
        self.coordinator = ResponderCoordinator(self.incident_manager)
    
    def test_response_command_parsing(self):
        """Test response command parsing"""
        test_cases = [
            ("ACK", ("acknowledge", "", "")),
            ("ACK incident123", ("acknowledge", "incident123", "")),
            ("RESPONDING incident456 On my way", ("responding", "incident456", "On my way")),
            ("ON_SCENE", ("on_scene", "", "")),
            ("CLEAR", ("clear_response", "", "")),
            ("Not a response", None)
        ]
        
        for message, expected in test_cases:
            result = self.coordinator.parse_response_command(message)
            self.assertEqual(result, expected)
    
    def test_acknowledgment_handling(self):
        """Test responder acknowledgment handling"""
        # Create incident
        incident = self.incident_manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim123"
        )
        
        # Handle acknowledgment
        success, message, incidents = self.coordinator.handle_responder_action(
            responder_id="!responder1",
            action_type="acknowledge",
            incident_id=incident.id,
            message="I can help"
        )
        
        # Verify acknowledgment
        self.assertTrue(success)
        self.assertIn("Acknowledged SOS incident", message)
        self.assertEqual(len(incidents), 1)
        self.assertIn("!responder1", incidents[0].acknowledgers)


if __name__ == '__main__':
    pytest.main([__file__])