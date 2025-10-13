"""
Integration tests for Emergency Response System

Tests end-to-end emergency response workflows including:
- Complete SOS alert and response workflows
- Multi-responder coordination scenarios
- Escalation and check-in integration
- Database persistence and recovery
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.services.emergency.emergency_service import EmergencyResponseService
from src.models.message import Message, SOSType, IncidentStatus, MessagePriority
from src.core.database import get_database
from tests.base import BaseTestCase


class TestEmergencyIntegration(BaseTestCase):
    """Integration tests for emergency response system"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        self.service = EmergencyResponseService()
        self.sent_messages = []
        
        # Mock message callback to capture sent messages
        def capture_message(message):
            self.sent_messages.append(message)
        
        self.service.set_message_callback(capture_message)
    
    async def test_complete_sos_workflow(self):
        """Test complete SOS workflow from alert to resolution"""
        await self.service.start()
        
        try:
            # Step 1: SOS alert is sent
            sos_message = Message(
                content="SOS Car accident on Highway 101",
                sender_id="!victim123",
                metadata={'latitude': 37.7749, 'longitude': -122.4194}
            )
            
            response = await self.service.handle_message(sos_message)
            
            # Verify SOS response
            self.assertIn("SOS ALERT SENT", response.content)
            self.assertEqual(len(self.sent_messages), 1)  # Emergency broadcast
            
            broadcast = self.sent_messages[0]
            self.assertIn("EMERGENCY ALERT", broadcast.content)
            self.assertEqual(broadcast.recipient_id, "^all")
            
            # Get created incident
            incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(incidents), 1)
            incident = incidents[0]
            
            # Step 2: First responder acknowledges
            ack_message = Message(
                content=f"ACK {incident.id} Fire department responding",
                sender_id="!fire_dept"
            )
            
            self.sent_messages.clear()
            response = await self.service.handle_message(ack_message)
            
            # Verify acknowledgment
            self.assertIn("Acknowledged SOS incident", response.content)
            self.assertEqual(len(self.sent_messages), 1)  # Notification broadcast
            
            # Step 3: Second responder indicates responding
            responding_message = Message(
                content=f"RESPONDING {incident.id} Ambulance ETA 8 minutes",
                sender_id="!ambulance"
            )
            
            self.sent_messages.clear()
            response = await self.service.handle_message(responding_message)
            
            # Verify responding
            self.assertIn("Responding to SOS incident", response.content)
            self.assertEqual(len(self.sent_messages), 1)  # Notification broadcast
            
            # Step 4: Check incident status
            status_message = Message(content="ACTIVE", sender_id="!dispatcher")
            response = await self.service.handle_message(status_message)
            
            # Verify status shows active incident with responders
            self.assertIn("Active Emergency Incidents (1)", response.content)
            self.assertIn("Responders: 2", response.content)
            
            # Step 5: Incident is resolved
            clear_message = Message(
                content=f"CLEAR {incident.id} Situation resolved, no injuries",
                sender_id="!victim123"
            )
            
            self.sent_messages.clear()
            response = await self.service.handle_message(clear_message)
            
            # Verify clearing
            self.assertIn("marked as CLEARED", response.content)
            self.assertEqual(len(self.sent_messages), 1)  # Clearing broadcast
            
            clearing_broadcast = self.sent_messages[0]
            self.assertIn("INCIDENT RESOLVED", clearing_broadcast.content)
            
            # Verify incident is no longer active
            active_incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(active_incidents), 0)
            
        finally:
            await self.service.stop()
    
    async def test_multiple_concurrent_incidents(self):
        """Test handling multiple concurrent incidents"""
        await self.service.start()
        
        try:
            # Create multiple SOS incidents
            incidents_data = [
                ("SOS Medical emergency", "!patient1", SOSType.SOS),
                ("SOSF House fire", "!homeowner", SOSType.SOSF),
                ("SOSP Break-in in progress", "!victim2", SOSType.SOSP)
            ]
            
            created_incidents = []
            
            for content, sender, expected_type in incidents_data:
                message = Message(content=content, sender_id=sender)
                response = await self.service.handle_message(message)
                
                self.assertIn("SOS ALERT SENT", response.content)
                
                # Find the created incident
                sender_incidents = self.service.incident_manager.get_incidents_by_sender(sender)
                self.assertEqual(len(sender_incidents), 1)
                self.assertEqual(sender_incidents[0].incident_type, expected_type)
                created_incidents.append(sender_incidents[0])
            
            # Verify all incidents are active
            active_incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(active_incidents), 3)
            
            # Multi-responder acknowledges all incidents
            ack_message = Message(
                content="ACK Emergency coordinator responding to all",
                sender_id="!coordinator"
            )
            
            response = await self.service.handle_message(ack_message)
            self.assertIn("Acknowledged 3 active incidents", response.content)
            
            # Specific responders for specific incidents
            fire_response = Message(
                content=f"RESPONDING {created_incidents[1].id} Fire truck dispatched",
                sender_id="!fire_truck"
            )
            
            police_response = Message(
                content=f"RESPONDING {created_incidents[2].id} Police unit en route",
                sender_id="!police_unit"
            )
            
            await self.service.handle_message(fire_response)
            await self.service.handle_message(police_response)
            
            # Verify responder assignments
            assignments = self.service.responder_coordinator.get_responder_assignments()
            self.assertEqual(len(assignments), 3)  # All incidents have responders
            
            # Clear one incident
            clear_message = Message(
                content=f"CLEAR {created_incidents[0].id} False alarm",
                sender_id="!patient1"
            )
            
            await self.service.handle_message(clear_message)
            
            # Verify only 2 incidents remain active
            active_incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(active_incidents), 2)
            
        finally:
            await self.service.stop()
    
    async def test_escalation_workflow(self):
        """Test escalation workflow for unacknowledged incidents"""
        await self.service.start()
        
        try:
            # Create SOS incident
            sos_message = Message(
                content="SOSM Heart attack",
                sender_id="!patient999"
            )
            
            await self.service.handle_message(sos_message)
            
            # Get the incident
            incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(incidents), 1)
            incident = incidents[0]
            
            # Verify escalation was registered
            escalation_status = self.service.escalation_manager.get_escalation_status()
            self.assertEqual(escalation_status['pending_escalations'], 1)
            
            # Simulate time passing without acknowledgment
            # (In real scenario, this would be handled by background task)
            
            # Acknowledge the incident to cancel escalation
            ack_message = Message(
                content=f"ACK {incident.id} Paramedics dispatched",
                sender_id="!paramedic"
            )
            
            await self.service.handle_message(ack_message)
            
            # Verify escalation was cancelled
            escalation_status = self.service.escalation_manager.get_escalation_status()
            self.assertEqual(escalation_status['pending_escalations'], 0)
            
        finally:
            await self.service.stop()
    
    async def test_check_in_workflow(self):
        """Test check-in workflow for active SOS users"""
        await self.service.start()
        
        try:
            # Create SOS incident
            sos_message = Message(
                content="SOS Lost in wilderness",
                sender_id="!hiker123"
            )
            
            await self.service.handle_message(sos_message)
            
            # Verify check-in monitoring started
            escalation_status = self.service.escalation_manager.get_escalation_status()
            self.assertEqual(escalation_status['monitored_users'], 1)
            
            # Simulate check-in response
            checkin_message = Message(
                content="OK Still safe, found shelter",
                sender_id="!hiker123"
            )
            
            response = await self.service.handle_message(checkin_message)
            
            # Note: Actual check-in processing depends on active check-in requests
            # This tests the message handling pathway
            
        finally:
            await self.service.stop()
    
    async def test_database_persistence(self):
        """Test that incidents are properly persisted in database"""
        await self.service.start()
        
        try:
            # Create incident
            sos_message = Message(
                content="SOS Database test",
                sender_id="!test_user",
                metadata={'latitude': 40.0, 'longitude': -74.0}
            )
            
            await self.service.handle_message(sos_message)
            
            # Get incident from service
            incidents = self.service.incident_manager.get_active_incidents()
            self.assertEqual(len(incidents), 1)
            original_incident = incidents[0]
            
            # Verify incident is in database
            db = get_database()
            db_incidents = db.execute_query(
                "SELECT * FROM sos_incidents WHERE id = ?",
                (original_incident.id,)
            )
            
            self.assertEqual(len(db_incidents), 1)
            db_incident = db_incidents[0]
            
            # Verify database fields
            self.assertEqual(db_incident['incident_type'], 'SOS')
            self.assertEqual(db_incident['sender_id'], '!test_user')
            self.assertEqual(db_incident['message'], 'Database test')
            self.assertEqual(db_incident['location_lat'], 40.0)
            self.assertEqual(db_incident['location_lon'], -74.0)
            self.assertEqual(db_incident['status'], 'active')
            
            # Add responder and verify persistence
            ack_message = Message(
                content=f"ACK {original_incident.id}",
                sender_id="!responder_db"
            )
            
            await self.service.handle_message(ack_message)
            
            # Check database was updated
            db_incidents = db.execute_query(
                "SELECT * FROM sos_incidents WHERE id = ?",
                (original_incident.id,)
            )
            
            updated_db_incident = db_incidents[0]
            self.assertEqual(updated_db_incident['status'], 'acknowledged')
            
            # Verify acknowledgers were stored
            import json
            acknowledgers = json.loads(updated_db_incident['acknowledgers'])
            self.assertIn('!responder_db', acknowledgers)
            
        finally:
            await self.service.stop()
    
    async def test_service_recovery_after_restart(self):
        """Test that service can recover incidents after restart"""
        # Create and start first service instance
        service1 = EmergencyResponseService()
        await service1.start()
        
        try:
            # Create incident
            sos_message = Message(
                content="SOS Recovery test",
                sender_id="!recovery_user"
            )
            
            await service1.handle_message(sos_message)
            
            # Get incident ID
            incidents = service1.incident_manager.get_active_incidents()
            self.assertEqual(len(incidents), 1)
            incident_id = incidents[0].id
            
        finally:
            await service1.stop()
        
        # Create new service instance (simulating restart)
        service2 = EmergencyResponseService()
        await service2.start()
        
        try:
            # Verify incident can be retrieved
            recovered_incident = service2.incident_manager.get_incident(incident_id)
            self.assertIsNotNone(recovered_incident)
            self.assertEqual(recovered_incident.sender_id, "!recovery_user")
            self.assertEqual(recovered_incident.message, "Recovery test")
            
            # Verify incident is in active list
            active_incidents = service2.incident_manager.get_active_incidents()
            self.assertEqual(len(active_incidents), 1)
            self.assertEqual(active_incidents[0].id, incident_id)
            
        finally:
            await service2.stop()
    
    async def test_error_handling(self):
        """Test error handling in emergency workflows"""
        await self.service.start()
        
        try:
            # Test invalid incident ID
            invalid_ack = Message(
                content="ACK invalid_incident_id",
                sender_id="!responder"
            )
            
            response = await self.service.handle_message(invalid_ack)
            self.assertIn("No active incidents found", response.content)
            
            # Test clearing non-existent incident
            invalid_clear = Message(
                content="CLEAR non_existent_id",
                sender_id="!user"
            )
            
            response = await self.service.handle_message(invalid_clear)
            self.assertIn("No active incidents found", response.content)
            
            # Test status when no incidents
            status_message = Message(content="ACTIVE", sender_id="!user")
            response = await self.service.handle_message(status_message)
            self.assertIn("No active emergency incidents", response.content)
            
        finally:
            await self.service.stop()


if __name__ == '__main__':
    pytest.main([__file__])