"""
Example integration tests demonstrating the testing infrastructure.
"""
import pytest
from tests.base import IntegrationTestCase, TestDataFactory


@pytest.mark.integration
class TestExampleIntegration(IntegrationTestCase):
    """Example integration test class."""
    
    async def test_database_integration(self):
        """Test database integration."""
        # Create test database
        db_path = self.create_test_database()
        
        # Insert test data
        test_users = [
            TestDataFactory.create_user("!12345678", "TEST1", email="test1@example.com"),
            TestDataFactory.create_user("!87654321", "TEST2", email="test2@example.com")
        ]
        self.insert_test_data("users", test_users)
        
        # Verify data was inserted
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 2
    
    async def test_meshtastic_message_flow(self):
        """Test complete message flow through system."""
        # Create mock interface
        interface = self.create_mock_interface("test_interface")
        await interface.connect()
        
        # Set up message tracking
        received_messages = []
        
        async def track_messages(message):
            received_messages.append(message)
        
        interface.add_message_callback(track_messages)
        
        # Simulate receiving a message
        await self.simulate_message_received("test_interface", "Hello integration test")
        
        # Verify message was received
        assert len(received_messages) == 1
        assert received_messages[0].text == "Hello integration test"
        
        # Send a response
        await interface.send_message("Response message")
        
        # Verify message was sent
        assert len(interface.sent_messages) == 1
        assert interface.sent_messages[0].text == "Response message"
    
    async def test_external_service_integration(self):
        """Test integration with external services."""
        # Test weather service
        weather_data = await self.weather_service.get_current_weather(40.7128, -74.0060)
        assert "temperature" in weather_data
        
        # Test email service
        await self.email_service.connect_smtp("smtp.example.com", 587, "user", "pass")
        result = await self.email_service.send_email("test@example.com", "Test", "Body")
        assert result is True
        assert len(self.email_service.sent_emails) == 1
        
        # Test AI service
        response = await self.ai_service.generate_response("Hello AI")
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Test Redis service
        await self.redis_service.connect()
        await self.redis_service.set("test_key", "test_value")
        value = await self.redis_service.get("test_key")
        assert value == "test_value"
    
    async def test_sos_workflow_integration(self):
        """Test complete SOS workflow integration."""
        # Set up database
        db_path = self.create_test_database()
        
        # Create test users
        users = [
            TestDataFactory.create_user("!12345678", "USER1", tags=["user"]),
            TestDataFactory.create_user("!87654321", "RESP1", tags=["responder"])
        ]
        self.insert_test_data("users", users)
        
        # Create mock interface
        interface = self.create_mock_interface("sos_test")
        await interface.connect()
        
        # Simulate SOS message
        await self.simulate_message_received("sos_test", "SOS Need help at location", "!12345678")
        
        # Verify SOS was processed (this would be done by the actual service)
        # For now, just verify the message was received
        assert len(self.message_history) == 1
        assert self.message_history[0][0] == "received"
        assert "SOS" in self.message_history[0][1]
    
    async def test_bbs_workflow_integration(self):
        """Test complete BBS workflow integration."""
        # Set up database
        db_path = self.create_test_database()
        
        # Create test users
        users = [
            TestDataFactory.create_user("!12345678", "USER1"),
            TestDataFactory.create_user("!87654321", "USER2")
        ]
        self.insert_test_data("users", users)
        
        # Create mock interface
        interface = self.create_mock_interface("bbs_test")
        await interface.connect()
        
        # Simulate BBS commands
        await self.simulate_message_received("bbs_test", "bbslist", "!12345678")
        await self.simulate_message_received("bbs_test", "bbspost Test Subject|Test bulletin content", "!12345678")
        
        # Verify commands were received
        assert len(self.message_history) == 2
        commands = [msg[1].split()[0] for msg in self.message_history if msg[0] == "received"]
        assert "bbslist" in commands
        assert "bbspost" in commands


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration(IntegrationTestCase):
    """Performance-related integration tests."""
    
    async def test_message_throughput(self):
        """Test message processing throughput."""
        interface = self.create_mock_interface("perf_test")
        await interface.connect()
        
        # Send multiple messages rapidly
        import time
        start_time = time.time()
        
        for i in range(100):
            await interface.send_message(f"Message {i}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify all messages were sent
        assert len(interface.sent_messages) == 100
        
        # Check throughput (should be much faster than 1 second for 100 messages)
        assert duration < 1.0, f"Message sending took too long: {duration}s"
    
    async def test_concurrent_interfaces(self):
        """Test multiple concurrent interfaces."""
        interfaces = {}
        
        # Create multiple interfaces
        for i in range(5):
            interface_id = f"concurrent_{i}"
            interface = self.create_mock_interface(interface_id, node_id=f"!1234567{i}")
            await interface.connect()
            interfaces[interface_id] = interface
        
        # Send messages on all interfaces concurrently
        import asyncio
        tasks = []
        
        for interface_id, interface in interfaces.items():
            task = asyncio.create_task(interface.send_message(f"Message from {interface_id}"))
            tasks.append(task)
        
        # Wait for all messages to be sent
        results = await asyncio.gather(*tasks)
        
        # Verify all messages were sent successfully
        assert all(results)
        for interface in interfaces.values():
            assert len(interface.sent_messages) == 1