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
    async def test_multiple_sos_types(self):
        """Test different SOS alert types"""
        sos_types = [
            ("SOS", SOSType.SOS),
            ("SOSP", SOSType.SOSP),
            ("SOSF", SOSType.SOSF),
            ("SOSM", SOSType.SOSM)
        ]
        
        for command, expected_type in sos_types:
            message = Message(
                content=f"{command} Emergency situation",
                sender_id=f"!user{command}"
            )
            
            response = await self.service.handle_message(message)
            
            self.assertIsNotNone(response)
            self.assertIn("SOS ALERT SENT", response.content)
            
            # Find the created incident
            incidents = self.service.incident_manager.get_incidents_by_sender(f"!user{command}")
            self.assertEqual(len(incidents), 1)
            self.assertEqual(incidents[0].incident_type, expected_type)
    
    @pytest.mark.asyncio
    async def test_responder_acknowledgment(self):
        """Test responder acknowledgment functionality"""
        # Create SOS incident first
        sos_message = Message(content="SOS Help needed", sender_id="!victim123")
        await self.service.handle_message(sos_message)
        
        # Get the created incident
        incidents = self.service.incident_manager.get_active_incidents()
        self.assertEqual(len(incidents), 1)
        incident = incidents[0]
        
        # Responder acknowledges
        ack_message = Message(
            content=f"ACK {incident.id} On my way",
            sender_id="!responder1"
        )
        
        response = await self.service.handle_message(ack_message)
        
        # Verify acknowledgment response
        self.assertIsNotNone(response)
        self.assertIn("Acknowledged SOS incident", response.content)
        self.assertIn("On my way", response.content)
        
        # Verify incident was updated
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        self.assertIn("!responder1", updated_incident.acknowledgers)
        self.assertEqual(updated_incident.status, IncidentStatus.ACKNOWLEDGED)
    
    async def test_responder_responding(self):
        """Test responder indicating they are responding"""
        # Create SOS incident
        sos_message = Message(content="SOS Medical emergency", sender_id="!victim456")
        await self.service.handle_message(sos_message)
        
        incident = self.service.incident_manager.get_active_incidents()[0]
        
        # Responder indicates responding
        responding_message = Message(
            content=f"RESPONDING {incident.id} ETA 10 minutes",
            sender_id="!responder2"
        )
        
        response = await self.service.handle_message(responding_message)
        
        # Verify response
        self.assertIsNotNone(response)
        self.assertIn("Responding to SOS incident", response.content)
        self.assertIn("ETA 10 minutes", response.content)
        
        # Verify incident was updated
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        self.assertIn("!responder2", updated_incident.responders)
        self.assertEqual(updated_incident.status, IncidentStatus.RESPONDING)
    
    async def test_multiple_incident_handling(self):
        """Test handling multiple concurrent incidents"""
        # Create multiple SOS incidents
        incidents = []
        for i in range(3):
            sos_message = Message(
                content=f"SOS Emergency {i+1}",
                sender_id=f"!victim{i+1}"
            )
            await self.service.handle_message(sos_message)
        
        # Verify all incidents were created
        active_incidents = self.service.incident_manager.get_active_incidents()
        self.assertEqual(len(active_incidents), 3)
        
        # Responder acknowledges all incidents (no specific ID)
        ack_message = Message(content="ACK All incidents", sender_id="!responder1")
        response = await self.service.handle_message(ack_message)
        
        # Verify response mentions multiple incidents
        self.assertIn("Acknowledged 3 active incidents", response.content)
        
        # Verify all incidents were acknowledged
        for incident in active_incidents:
            updated_incident = self.service.incident_manager.get_incident(incident.id)
            self.assertIn("!responder1", updated_incident.acknowledgers)
    
    async def test_incident_clearing(self):
        """Test incident clearing functionality"""
        # Create SOS incident
        sos_message = Message(content="SOS False alarm", sender_id="!victim789")
        await self.service.handle_message(sos_message)
        
        incident = self.service.incident_manager.get_active_incidents()[0]
        
        # Clear the incident
        clear_message = Message(
            content=f"CLEAR {incident.id} False alarm resolved",
            sender_id="!victim789"  # Same sender can clear
        )
        
        response = await self.service.handle_message(clear_message)
        
        # Verify clearing response
        self.assertIsNotNone(response)
        self.assertIn("marked as CLEARED", response.content)
        
        # Verify incident was cleared
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        self.assertEqual(updated_incident.status, IncidentStatus.CLEARED)
        self.assertEqual(updated_incident.cleared_by, "!victim789")
        self.assertIsNotNone(updated_incident.cleared_at)
        
        # Verify clearing broadcast was sent
        self.service.message_callback.assert_called()
    
    async def test_incident_cancellation(self):
        """Test incident cancellation"""
        # Create SOS incident
        sos_message = Message(content="SOSM Heart attack", sender_id="!patient123")
        await self.service.handle_message(sos_message)
        
        incident = self.service.incident_manager.get_active_incidents()[0]
        
        # Cancel the incident
        cancel_message = Message(
            content=f"CANCEL {incident.id} Situation resolved",
            sender_id="!patient123"
        )
        
        response = await self.service.handle_message(cancel_message)
        
        # Verify cancellation
        self.assertIn("marked as CANCELLED", response.content)
        
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        self.assertEqual(updated_incident.status, IncidentStatus.CANCELLED)
    
    async def test_status_command(self):
        """Test status command functionality"""
        # Create some incidents
        for i in range(2):
            sos_message = Message(
                content=f"SOS Emergency {i+1}",
                sender_id=f"!user{i+1}"
            )
            await self.service.handle_message(sos_message)
        
        # Request status
        status_message = Message(content="ACTIVE", sender_id="!requester")
        response = await self.service.handle_message(status_message)
        
        # Verify status response
        self.assertIsNotNone(response)
        self.assertIn("Active Emergency Incidents (2)", response.content)
        self.assertIn("SOS", response.content)
    
    async def test_checkin_response(self):
        """Test check-in response handling"""
        # Create SOS incident to start monitoring
        sos_message = Message(content="SOS Need help", sender_id="!victim999")
        await self.service.handle_message(sos_message)
        
        # Simulate check-in response
        checkin_message = Message(content="OK I'm safe now", sender_id="!victim999")
        response = await self.service.handle_message(checkin_message)
        
        # Verify check-in was processed
        self.assertIsNotNone(response)
        # Note: Actual check-in processing depends on escalation manager state
    
    async def test_unauthorized_clearing(self):
        """Test that unauthorized users cannot clear incidents"""
        # Create SOS incident
        sos_message = Message(content="SOS Help needed", sender_id="!victim111")
        await self.service.handle_message(sos_message)
        
        incident = self.service.incident_manager.get_active_incidents()[0]
        
        # Try to clear from different user
        clear_message = Message(
            content=f"CLEAR {incident.id}",
            sender_id="!unauthorized"
        )
        
        response = await self.service.handle_message(clear_message)
        
        # Verify clearing was rejected
        self.assertIn("No incidents were cleared", response.content)
        
        # Verify incident is still active
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        self.assertEqual(updated_incident.status, IncidentStatus.ACTIVE)
    
    async def test_service_lifecycle(self):
        """Test service start/stop lifecycle"""
        # Test starting service
        await self.service.start()
        self.assertTrue(self.service._running)
        
        # Test stopping service
        await self.service.stop()
        self.assertFalse(self.service._running)
    
    async def test_service_status(self):
        """Test service status reporting"""
        # Create some test data
        sos_message = Message(content="SOS Test", sender_id="!test123")
        await self.service.handle_message(sos_message)
        
        # Get service status
        status = self.service.get_service_status()
        
        # Verify status structure
        self.assertIn('running', status)
        self.assertIn('active_incidents', status)
        self.assertIn('incident_summary', status)
        self.assertIn('escalation_status', status)
        self.assertIn('responder_assignments', status)
        
        self.assertEqual(status['active_incidents'], 1)


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
    
    def test_incident_status_updates(self):
        """Test incident status updates"""
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!test789"
        )
        
        # Update status
        success = self.manager.update_incident_status(incident.id, IncidentStatus.ACKNOWLEDGED)
        self.assertTrue(success)
        
        # Verify update
        updated = self.manager.get_incident(incident.id)
        self.assertEqual(updated.status, IncidentStatus.ACKNOWLEDGED)
    
    def test_responder_management(self):
        """Test adding responders and acknowledgers"""
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim123"
        )
        
        # Add responder
        success = self.manager.add_responder(incident.id, "!responder1")
        self.assertTrue(success)
        
        # Add acknowledger
        success = self.manager.add_acknowledger(incident.id, "!responder2")
        self.assertTrue(success)
        
        # Verify updates
        updated = self.manager.get_incident(incident.id)
        self.assertIn("!responder1", updated.responders)
        self.assertIn("!responder2", updated.acknowledgers)
        self.assertEqual(updated.status, IncidentStatus.ACKNOWLEDGED)
    
    def test_incident_escalation(self):
        """Test incident escalation"""
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim456"
        )
        
        # Escalate incident
        success = self.manager.escalate_incident(incident.id)
        self.assertTrue(success)
        
        # Verify escalation
        updated = self.manager.get_incident(incident.id)
        self.assertTrue(updated.escalated)
    
    def test_incident_clearing(self):
        """Test incident clearing"""
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim789"
        )
        
        # Clear incident
        success = self.manager.clear_incident(incident.id, "!responder1", IncidentStatus.CLEARED)
        self.assertTrue(success)
        
        # Verify clearing
        updated = self.manager.get_incident(incident.id)
        self.assertEqual(updated.status, IncidentStatus.CLEARED)
        self.assertEqual(updated.cleared_by, "!responder1")
        self.assertIsNotNone(updated.cleared_at)


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
    
    def test_responding_handling(self):
        """Test responder responding handling"""
        # Create incident
        incident = self.incident_manager.create_incident(
            incident_type=SOSType.SOSF,
            sender_id="!victim456"
        )
        
        # Handle responding
        success, message, incidents = self.coordinator.handle_responder_action(
            responder_id="!responder2",
            action_type="responding",
            incident_id=incident.id,
            message="ETA 5 minutes"
        )
        
        # Verify responding
        self.assertTrue(success)
        self.assertIn("Responding to SOS incident", message)
        self.assertEqual(len(incidents), 1)
        self.assertIn("!responder2", incidents[0].responders)
        self.assertEqual(incidents[0].status, IncidentStatus.RESPONDING)
    
    def test_multiple_incident_response(self):
        """Test responding to multiple incidents"""
        # Create multiple incidents
        incidents = []
        for i in range(2):
            incident = self.incident_manager.create_incident(
                incident_type=SOSType.SOS,
                sender_id=f"!victim{i+1}"
            )
            incidents.append(incident)
        
        # Acknowledge all incidents (no specific ID)
        success, message, affected = self.coordinator.handle_responder_action(
            responder_id="!responder1",
            action_type="acknowledge",
            incident_id="",  # No specific incident
            message="Acknowledging all"
        )
        
        # Verify all incidents were acknowledged
        self.assertTrue(success)
        self.assertIn("Acknowledged 2 active incidents", message)
        self.assertEqual(len(affected), 2)
    
    def test_notification_message_creation(self):
        """Test notification message creation"""
        incident = self.incident_manager.create_incident(
            incident_type=SOSType.SOSM,
            sender_id="!victim789"
        )
        
        # Create notification
        notification = self.coordinator.create_notification_message(
            incident=incident,
            action="acknowledge",
            responder_id="!responder1",
            additional_message="On my way"
        )
        
        # Verify notification
        self.assertIn("SOS Update", notification.content)
        self.assertIn("SOSM", notification.content)
        self.assertIn("!responder1", notification.content)
        self.assertIn("On my way", notification.content)
        self.assertEqual(notification.priority, MessagePriority.HIGH)
        self.assertEqual(notification.recipient_id, "^all")
    
    def test_incident_status_summary(self):
        """Test incident status summary"""
        incident = self.incident_manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim123",
            message="Help needed",
            location=(40.7128, -74.0060)
        )
        
        # Add some responders
        self.incident_manager.add_acknowledger(incident.id, "!responder1")
        self.incident_manager.add_responder(incident.id, "!responder2")
        
        # Get status summary
        summary = self.coordinator.get_incident_status_summary(incident.id)
        
        # Verify summary content
        self.assertIsNotNone(summary)
        self.assertIn("SOS Incident", summary)
        self.assertIn("!victim123", summary)
        self.assertIn("Help needed", summary)
        self.assertIn("40.712800, -74.006000", summary)
        self.assertIn("!responder1", summary)
        self.assertIn("!responder2", summary)


if __name__ == '__main__':
    pytest.main([__file__])