"""
Simple unit tests for Emergency Response Service
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.emergency.incident_manager import IncidentManager
from src.services.emergency.responder_coordinator import ResponderCoordinator
from src.services.emergency.emergency_service import EmergencyResponseService
from src.models.message import Message, SOSType, IncidentStatus, MessagePriority
from tests.base import BaseTestCase


class TestIncidentManager(BaseTestCase):
    """Test incident manager functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Mock the database
        self.db_mock = Mock()
        with patch('src.services.emergency.incident_manager.get_database', return_value=self.db_mock):
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
            assert result == expected
    
    def test_incident_creation(self):
        """Test incident creation"""
        # Mock database execute_update to succeed
        self.db_mock.execute_update.return_value = 1
        
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
        
        # Verify database was called
        self.db_mock.execute_update.assert_called_once()


class TestResponderCoordinator(BaseTestCase):
    """Test responder coordinator functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Mock the database and incident manager
        self.db_mock = Mock()
        with patch('src.services.emergency.incident_manager.get_database', return_value=self.db_mock):
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
            assert result == expected


class TestEmergencyService(BaseTestCase):
    """Test emergency response service"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        # Mock the database
        self.db_mock = Mock()
        with patch('src.services.emergency.incident_manager.get_database', return_value=self.db_mock):
            self.service = EmergencyResponseService()
        self.service.set_message_callback(Mock())
    
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
        # Mock database operations
        self.db_mock.execute_update.return_value = 1
        
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


if __name__ == '__main__':
    pytest.main([__file__])