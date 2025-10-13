"""
Working unit tests for Emergency Response Service
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import tempfile
import os

from src.services.emergency.incident_manager import IncidentManager
from src.services.emergency.responder_coordinator import ResponderCoordinator
from src.services.emergency.emergency_service import EmergencyResponseService
from src.models.message import Message, SOSType, IncidentStatus, MessagePriority
from src.core.database import initialize_database
from tests.base import BaseTestCase


class TestIncidentManagerWorking(BaseTestCase):
    """Test incident manager functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Create temporary database
        self.temp_db = tempfile.mktemp(suffix='.db')
        initialize_database(self.temp_db)
        self.manager = IncidentManager()
    
    def teardown_method(self):
        """Clean up test environment"""
        super().teardown_method()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)
    
    def test_sos_command_parsing(self):
        """Test SOS command parsing"""
        test_cases = [
            ("SOS", (SOSType.SOS, "")),
            ("SOS Help me", (SOSType.SOS, " Help me")),  # Note: space preserved
            ("SOSP Police needed", (SOSType.SOSP, " Police needed")),
            ("SOSF Fire emergency", (SOSType.SOSF, " Fire emergency")),
            ("SOSM Medical help", (SOSType.SOSM, " Medical help")),
            ("Not an SOS", None)
        ]
        
        for message, expected in test_cases:
            result = self.manager.parse_sos_command(message)
            assert result == expected, f"Failed for message: {message}"
    
    def test_incident_creation(self):
        """Test incident creation"""
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
        assert retrieved is not None
        assert retrieved.id == incident.id
        
        # Test get by sender
        sender_incidents = self.manager.get_incidents_by_sender("!patient456")
        assert len(sender_incidents) == 1
        assert sender_incidents[0].id == incident.id
        
        # Test get active incidents
        active_incidents = self.manager.get_active_incidents()
        assert len(active_incidents) == 1
        assert active_incidents[0].id == incident.id


class TestResponderCoordinatorWorking(BaseTestCase):
    """Test responder coordinator functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Create temporary database
        self.temp_db = tempfile.mktemp(suffix='.db')
        initialize_database(self.temp_db)
        self.incident_manager = IncidentManager()
        self.coordinator = ResponderCoordinator(self.incident_manager)
    
    def teardown_method(self):
        """Clean up test environment"""
        super().teardown_method()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)
    
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
            assert result == expected, f"Failed for message: {message}"
    
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
        assert success is True
        assert "Acknowledged SOS incident" in message
        assert len(incidents) == 1
        assert "!responder1" in incidents[0].acknowledgers


class TestEmergencyServiceWorking(BaseTestCase):
    """Test emergency response service"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Create temporary database
        self.temp_db = tempfile.mktemp(suffix='.db')
        initialize_database(self.temp_db)
        self.service = EmergencyResponseService()
        self.service.set_message_callback(Mock())
    
    def teardown_method(self):
        """Clean up test environment"""
        super().teardown_method()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test service start/stop lifecycle"""
        # Test starting service
        await self.service.start()
        assert self.service._running is True
        
        # Test stopping service
        await self.service.stop()
        assert self.service._running is False
    
    @pytest.mark.asyncio
    async def test_sos_message_handling(self):
        """Test SOS message handling"""
        # Create SOS message
        sos_message = Message(
            content="SOS Need help immediately!",
            sender_id="!12345678",
            metadata={'latitude': 40.7128, 'longitude': -74.0060}
        )
        
        # Handle SOS message
        response = await self.service.handle_message(sos_message)
        
        # Verify response
        assert response is not None
        assert "SOS ALERT SENT" in response.content
        assert "Incident ID:" in response.content
        assert response.priority == MessagePriority.EMERGENCY
        
        # Verify emergency broadcast was sent
        self.service.message_callback.assert_called()
        broadcast_call = self.service.message_callback.call_args[0][0]
        assert "EMERGENCY ALERT" in broadcast_call.content
        assert broadcast_call.recipient_id == "^all"
    
    @pytest.mark.asyncio
    async def test_responder_acknowledgment_flow(self):
        """Test complete responder acknowledgment flow"""
        # Create SOS incident first
        sos_message = Message(content="SOS Help needed", sender_id="!victim123")
        await self.service.handle_message(sos_message)
        
        # Get the created incident
        incidents = self.service.incident_manager.get_active_incidents()
        assert len(incidents) == 1
        incident = incidents[0]
        
        # Responder acknowledges
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


if __name__ == '__main__':
    pytest.main([__file__])