"""
Final working unit tests for Emergency Response Service
"""

import pytest
from unittest.mock import Mock
from datetime import datetime
import tempfile
import os

from src.services.emergency.incident_manager import IncidentManager
from src.services.emergency.responder_coordinator import ResponderCoordinator
from src.services.emergency.emergency_service import EmergencyResponseService
from src.models.message import Message, SOSType, IncidentStatus, MessagePriority
from src.core.database import initialize_database, get_database
from tests.base import BaseTestCase


class TestEmergencyResponseFinal(BaseTestCase):
    """Final comprehensive test for emergency response system"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Create temporary database
        self.temp_db = tempfile.mktemp(suffix='.db')
        initialize_database(self.temp_db)
        
        # Create test users first to avoid foreign key constraints
        db = get_database()
        test_users = [
            {
                'node_id': '!test123',
                'short_name': 'TEST1',
                'long_name': 'Test User 1',
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            },
            {
                'node_id': '!victim123',
                'short_name': 'VICTIM',
                'long_name': 'Test Victim',
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            },
            {
                'node_id': '!responder1',
                'short_name': 'RESP1',
                'long_name': 'Test Responder 1',
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            },
            {
                'node_id': '!12345678',
                'short_name': 'USER1',
                'long_name': 'Test User Emergency',
                'tags': '[]',
                'permissions': '{}',
                'subscriptions': '{}'
            }
        ]
        
        for user in test_users:
            db.execute_update(
                """INSERT INTO users (node_id, short_name, long_name, tags, permissions, subscriptions)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user['node_id'], user['short_name'], user['long_name'], 
                 user['tags'], user['permissions'], user['subscriptions'])
            )
        
        # Initialize services
        self.manager = IncidentManager()
        self.coordinator = ResponderCoordinator(self.manager)
        self.service = EmergencyResponseService()
        self.service.set_message_callback(Mock())
    
    def teardown_method(self):
        """Clean up test environment"""
        super().teardown_method()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)
    
    def test_sos_command_parsing(self):
        """Test SOS command parsing"""
        test_cases = [
            ("SOS", (SOSType.SOS, "")),
            ("SOS Help me", (SOSType.SOS, "Help me")),  # Trimmed space
            ("SOSP Police needed", (SOSType.SOSP, "Police needed")),
            ("SOSF Fire emergency", (SOSType.SOSF, "Fire emergency")),
            ("SOSM Medical help", (SOSType.SOSM, "Medical help")),
            ("Not an SOS", None)
        ]
        
        for message, expected in test_cases:
            result = self.manager.parse_sos_command(message)
            if expected is None:
                assert result is None, f"Failed for message: {message}"
            else:
                assert result is not None, f"Failed for message: {message}"
                assert result[0] == expected[0], f"Failed SOS type for message: {message}"
                # For the additional message, we need to account for the trimming
                assert result[1].strip() == expected[1], f"Failed additional message for message: {message}"
    
    def test_incident_creation_and_retrieval(self):
        """Test incident creation and retrieval"""
        # Create incident
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!test123",
            message="Test emergency",
            location=(40.7128, -74.0060)
        )
        
        # Verify incident properties
        assert incident.incident_type == SOSType.SOS
        assert incident.sender_id == "!test123"
        assert incident.message == "Test emergency"
        assert incident.location == (40.7128, -74.0060)
        assert incident.status == IncidentStatus.ACTIVE
        assert incident.id is not None
        assert isinstance(incident.timestamp, datetime)
        
        # Test retrieval
        retrieved = self.manager.get_incident(incident.id)
        assert retrieved is not None
        assert retrieved.id == incident.id
        
        # Test get by sender
        sender_incidents = self.manager.get_incidents_by_sender("!test123")
        assert len(sender_incidents) == 1
        assert sender_incidents[0].id == incident.id
        
        # Test get active incidents
        active_incidents = self.manager.get_active_incidents()
        assert len(active_incidents) == 1
        assert active_incidents[0].id == incident.id
    
    def test_responder_coordination(self):
        """Test responder coordination"""
        # Create incident
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!victim123"
        )
        
        # Test response command parsing
        result = self.coordinator.parse_response_command("ACK")
        assert result == ("acknowledge", "", "")
        
        result = self.coordinator.parse_response_command(f"ACK {incident.id} I can help")
        assert result == ("acknowledge", incident.id, "I can help")
        
        # Handle acknowledgment
        success, message, incidents = self.coordinator.handle_responder_action(
            responder_id="!responder1",
            action_type="acknowledge",
            incident_id=incident.id,
            message="I can help"
        )
        
        # Verify acknowledgment
        assert success is True
        assert "Acknowledged SOS incident" in message
        assert len(incidents) == 1
        assert "!responder1" in incidents[0].acknowledgers
        assert incidents[0].status == IncidentStatus.ACKNOWLEDGED
    
    @pytest.mark.asyncio
    async def test_emergency_service_lifecycle(self):
        """Test emergency service lifecycle"""
        # Test starting service
        await self.service.start()
        assert self.service._running is True
        
        # Test stopping service
        await self.service.stop()
        assert self.service._running is False
    
    @pytest.mark.asyncio
    async def test_complete_emergency_workflow(self):
        """Test complete emergency workflow"""
        # Step 1: Create SOS message
        sos_message = Message(
            content="SOS Need help immediately!",
            sender_id="!12345678",
            metadata={'latitude': 40.7128, 'longitude': -74.0060}
        )
        
        # Handle SOS message
        response = await self.service.handle_message(sos_message)
        
        # Verify SOS response
        assert response is not None
        assert "SOS ALERT SENT" in response.content
        assert "Incident ID:" in response.content
        assert response.priority == MessagePriority.EMERGENCY
        
        # Verify emergency broadcast was sent
        self.service.message_callback.assert_called()
        broadcast_call = self.service.message_callback.call_args[0][0]
        assert "EMERGENCY ALERT" in broadcast_call.content
        assert broadcast_call.recipient_id == "^all"
        
        # Step 2: Get the created incident
        incidents = self.service.incident_manager.get_active_incidents()
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.sender_id == "!12345678"
        assert "Need help immediately!" in incident.message
        
        # Step 3: Responder acknowledges
        ack_message = Message(
            content=f"ACK {incident.id} On my way",
            sender_id="!responder1"
        )
        
        response = await self.service.handle_message(ack_message)
        
        # Verify acknowledgment response
        assert response is not None
        assert "Acknowledged SOS incident" in response.content
        assert "On my way" in response.content
        
        # Verify incident was updated
        updated_incident = self.service.incident_manager.get_incident(incident.id)
        assert "!responder1" in updated_incident.acknowledgers
        assert updated_incident.status == IncidentStatus.ACKNOWLEDGED
        
        # Step 4: Clear the incident
        clear_message = Message(
            content=f"CLEAR {incident.id} Situation resolved",
            sender_id="!12345678"  # Original sender can clear
        )
        
        response = await self.service.handle_message(clear_message)
        
        # Verify clearing
        assert response is not None
        assert "marked as CLEARED" in response.content
        
        # Verify incident is no longer active
        active_incidents = self.service.incident_manager.get_active_incidents()
        assert len(active_incidents) == 0
        
        # But incident still exists in database
        cleared_incident = self.service.incident_manager.get_incident(incident.id)
        assert cleared_incident is not None
        assert cleared_incident.status == IncidentStatus.CLEARED
        assert cleared_incident.cleared_by == "!12345678"
    
    @pytest.mark.asyncio
    async def test_multiple_incident_types(self):
        """Test different SOS incident types"""
        incident_types = [
            ("SOS General emergency", SOSType.SOS),
            ("SOSP Police needed", SOSType.SOSP),
            ("SOSF Fire emergency", SOSType.SOSF),
            ("SOSM Medical help", SOSType.SOSM)
        ]
        
        created_incidents = []
        
        for content, expected_type in incident_types:
            message = Message(content=content, sender_id="!test123")
            response = await self.service.handle_message(message)
            
            assert response is not None
            assert "SOS ALERT SENT" in response.content
            
            # Find the created incident
            incidents = self.service.incident_manager.get_incidents_by_sender("!test123")
            # Get the most recent incident
            latest_incident = max(incidents, key=lambda x: x.timestamp)
            assert latest_incident.incident_type == expected_type
            created_incidents.append(latest_incident)
        
        # Verify all incidents are active
        active_incidents = self.service.incident_manager.get_active_incidents()
        assert len(active_incidents) == 4
    
    def test_service_status(self):
        """Test service status reporting"""
        # Create some test data
        incident = self.manager.create_incident(
            incident_type=SOSType.SOS,
            sender_id="!test123",
            message="Test incident"
        )
        
        # Get service status
        status = self.service.get_service_status()
        
        # Verify status structure
        assert 'running' in status
        assert 'active_incidents' in status
        assert 'incident_summary' in status
        assert 'escalation_status' in status
        assert 'responder_assignments' in status
        
        assert status['active_incidents'] == 1


if __name__ == '__main__':
    pytest.main([__file__])