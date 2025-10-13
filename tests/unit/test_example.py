"""
Example unit tests demonstrating the testing infrastructure.
"""
import pytest
from tests.base import BaseTestCase, AsyncTestCase
from tests.utils import MessageTestHelper, AssertionHelper


class TestExampleUnit(BaseTestCase):
    """Example unit test class."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        # Example test using base test case
        temp_file = self.create_temp_file("test content")
        assert temp_file.exists()
        assert temp_file.read_text() == "test content"
    
    def test_message_helper(self, message_helper):
        """Test message helper functionality."""
        message = message_helper.create_test_message("Hello world")
        assert message["content"] == "Hello world"
        assert message["sender_id"] == "!12345678"
        assert "id" in message
        assert "timestamp" in message
    
    def test_sos_message_creation(self, message_helper):
        """Test SOS message creation."""
        sos_msg = message_helper.create_sos_message("SOS", "Need help at location")
        assert sos_msg["content"] == "SOS Need help at location"
        
        sos_msg_no_text = message_helper.create_sos_message("SOSP")
        assert sos_msg_no_text["content"] == "SOSP"


class TestExampleAsync(AsyncTestCase):
    """Example async test class."""
    
    async def test_async_functionality(self):
        """Test async functionality."""
        # Example async test
        result = await self.async_operation()
        assert result == "async_result"
    
    async def test_wait_for_condition(self):
        """Test waiting for conditions."""
        counter = {"value": 0}
        
        async def increment():
            counter["value"] += 1
        
        # Start incrementing in background
        import asyncio
        task = asyncio.create_task(self.increment_periodically(increment))
        
        # Wait for condition
        success = await self.wait_for_condition(lambda: counter["value"] >= 3, timeout=1.0)
        task.cancel()
        
        assert success
        assert counter["value"] >= 3
    
    async def async_operation(self):
        """Example async operation."""
        import asyncio
        await asyncio.sleep(0.01)
        return "async_result"
    
    async def increment_periodically(self, increment_func):
        """Periodically increment a counter."""
        import asyncio
        while True:
            await increment_func()
            await asyncio.sleep(0.1)


@pytest.mark.unit
class TestMockInfrastructure:
    """Test the mock infrastructure itself."""
    
    def test_mock_meshtastic_interface(self, mock_meshtastic_interface):
        """Test mock Meshtastic interface."""
        interface = mock_meshtastic_interface
        
        # Test initial state
        assert not interface.connected
        assert interface.node_id == "!12345678"
        assert len(interface.nodes) == 3  # From fixture setup
        
        # Test nodes
        assert "!12345678" in interface.nodes
        assert "!87654321" in interface.nodes
        assert "!11111111" in interface.nodes
        
        # Check aircraft node
        aircraft_node = interface.get_node_info("!11111111")
        assert aircraft_node is not None
        assert aircraft_node.position["altitude"] == 10000
    
    async def test_mock_interface_connection(self, mock_meshtastic_interface):
        """Test mock interface connection."""
        interface = mock_meshtastic_interface
        
        # Test connection
        result = await interface.connect()
        assert result is True
        assert interface.connected is True
        
        # Test disconnection
        await interface.disconnect()
        assert interface.connected is False
    
    async def test_mock_message_sending(self, mock_meshtastic_interface):
        """Test mock message sending."""
        interface = mock_meshtastic_interface
        await interface.connect()
        
        # Send message
        result = await interface.send_message("Test message")
        assert result is True
        assert len(interface.sent_messages) == 1
        
        sent_msg = interface.sent_messages[0]
        assert sent_msg.text == "Test message"
        assert sent_msg.sender == interface.node_id
    
    async def test_mock_message_receiving(self, mock_meshtastic_interface):
        """Test mock message receiving."""
        interface = mock_meshtastic_interface
        received_messages = []
        
        # Add callback
        async def message_callback(message):
            received_messages.append(message)
        
        interface.add_message_callback(message_callback)
        
        # Simulate received message
        await interface.simulate_received_message("Hello from mesh")
        
        assert len(received_messages) == 1
        assert received_messages[0].text == "Hello from mesh"
    
    def test_mock_external_services(self, mock_external_services):
        """Test mock external services."""
        services = mock_external_services
        
        assert "weather" in services
        assert "email" in services
        assert "ai" in services
        assert "redis" in services
        assert "http" in services
    
    async def test_mock_weather_service(self, mock_weather_service):
        """Test mock weather service."""
        weather = mock_weather_service
        
        # Test current weather
        current = await weather.get_current_weather(40.7128, -74.0060)
        assert "temperature" in current
        assert current["temperature"] == 22.5
        
        # Test forecast
        forecast = await weather.get_forecast(40.7128, -74.0060, 2)
        assert len(forecast) == 2
        assert "high" in forecast[0]
        
        # Test alerts
        alerts = await weather.get_alerts(40.7128, -74.0060)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "severe"