#!/usr/bin/env python3
"""
Validation script for the testing infrastructure.
Tests the infrastructure without requiring pytest to be installed.
"""
import sys
import asyncio
import tempfile
from pathlib import Path

# Add the tests directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "tests"))

def test_imports():
    """Test that all test modules can be imported."""
    print("Testing imports...")
    
    try:
        from tests.mocks.meshtastic_mocks import MockMeshtasticInterface, MockMeshtasticInterfaceFactory
        from tests.mocks.external_service_mocks import MockWeatherService, MockEmailService, MockAIService
        from tests.base import BaseTestCase, AsyncTestCase, DatabaseTestCase
        from tests.utils import MessageTestHelper, ConfigTestHelper, FileTestHelper
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_mock_meshtastic_interface():
    """Test the mock Meshtastic interface."""
    print("\nTesting MockMeshtasticInterface...")
    
    try:
        from tests.mocks.meshtastic_mocks import MockMeshtasticInterface
        
        # Create interface
        interface = MockMeshtasticInterface("serial", port="/dev/ttyUSB0", node_id="!12345678")
        
        # Test initial state
        assert not interface.connected
        assert interface.node_id == "!12345678"
        assert interface.interface_type == "serial"
        assert interface.port == "/dev/ttyUSB0"
        
        # Add a node
        interface.add_node("!87654321", "TEST", "Test Node", 40.7128, -74.0060)
        assert len(interface.nodes) == 1
        
        node_info = interface.get_node_info("!87654321")
        assert node_info is not None
        assert node_info.user["shortName"] == "TEST"
        
        print("✅ MockMeshtasticInterface tests passed")
        return True
    except Exception as e:
        print(f"❌ MockMeshtasticInterface test failed: {e}")
        return False


async def test_async_mock_interface():
    """Test async functionality of mock interface."""
    print("\nTesting async MockMeshtasticInterface...")
    
    try:
        from tests.mocks.meshtastic_mocks import MockMeshtasticInterface
        
        interface = MockMeshtasticInterface()
        
        # Test connection
        result = await interface.connect()
        assert result is True
        assert interface.connected is True
        
        # Test message sending
        result = await interface.send_message("Test message")
        assert result is True
        assert len(interface.sent_messages) == 1
        assert interface.sent_messages[0].text == "Test message"
        
        # Test message receiving
        received_messages = []
        
        async def message_callback(message):
            received_messages.append(message)
        
        interface.add_message_callback(message_callback)
        await interface.simulate_received_message("Hello test")
        
        assert len(received_messages) == 1
        assert received_messages[0].text == "Hello test"
        
        # Test disconnection
        await interface.disconnect()
        assert interface.connected is False
        
        print("✅ Async MockMeshtasticInterface tests passed")
        return True
    except Exception as e:
        print(f"❌ Async MockMeshtasticInterface test failed: {e}")
        return False


def test_external_service_mocks():
    """Test external service mocks."""
    print("\nTesting external service mocks...")
    
    try:
        from tests.mocks.external_service_mocks import MockWeatherService, MockEmailService, MockAIService
        
        # Test weather service
        weather = MockWeatherService()
        assert len(weather.api_calls) == 0
        weather.set_weather_data({"current": {"temperature": 30.0}})
        assert weather.weather_data["current"]["temperature"] == 30.0
        
        # Test email service
        email = MockEmailService()
        assert not email.smtp_connected
        assert not email.imap_connected
        assert len(email.sent_emails) == 0
        
        email.add_received_email("test@example.com", "Test", "Body")
        assert len(email.received_emails) == 1
        
        # Test AI service
        ai = MockAIService()
        ai.set_response("test", "Test response")
        assert ai.responses["test"] == "Test response"
        
        print("✅ External service mocks tests passed")
        return True
    except Exception as e:
        print(f"❌ External service mocks test failed: {e}")
        return False


async def test_async_external_services():
    """Test async functionality of external service mocks."""
    print("\nTesting async external service mocks...")
    
    try:
        from tests.mocks.external_service_mocks import MockWeatherService, MockEmailService, MockAIService
        
        # Test weather service
        weather = MockWeatherService()
        current = await weather.get_current_weather(40.7128, -74.0060)
        assert "temperature" in current
        assert len(weather.api_calls) == 1
        
        # Test email service
        email = MockEmailService()
        await email.connect_smtp("smtp.test.com", 587, "user", "pass")
        assert email.smtp_connected
        
        result = await email.send_email("test@example.com", "Subject", "Body")
        assert result is True
        assert len(email.sent_emails) == 1
        
        # Test AI service
        ai = MockAIService()
        response = await ai.generate_response("Hello AI")
        assert isinstance(response, str)
        assert len(response) > 0
        
        print("✅ Async external service mocks tests passed")
        return True
    except Exception as e:
        print(f"❌ Async external service mocks test failed: {e}")
        return False


def test_base_classes():
    """Test base test classes."""
    print("\nTesting base test classes...")
    
    try:
        from tests.base import BaseTestCase, DatabaseTestCase, TestDataFactory
        
        # Test BaseTestCase
        base_test = BaseTestCase()
        base_test.setup_method()
        
        temp_file = base_test.create_temp_file("test content")
        assert temp_file.exists()
        assert temp_file.read_text() == "test content"
        
        base_test.teardown_method()
        
        # Test TestDataFactory
        user_data = TestDataFactory.create_user("!12345678", "TEST")
        assert user_data["node_id"] == "!12345678"
        assert user_data["short_name"] == "TEST"
        
        sos_data = TestDataFactory.create_sos_incident("sos_001", "!12345678")
        assert sos_data["id"] == "sos_001"
        assert sos_data["sender_id"] == "!12345678"
        
        print("✅ Base test classes tests passed")
        return True
    except Exception as e:
        print(f"❌ Base test classes test failed: {e}")
        return False


def test_utilities():
    """Test utility classes."""
    print("\nTesting utility classes...")
    
    try:
        from tests.utils import MessageTestHelper, ConfigTestHelper, FileTestHelper
        
        # Test MessageTestHelper
        message = MessageTestHelper.create_test_message("Hello world")
        assert message["content"] == "Hello world"
        assert "id" in message
        assert "timestamp" in message
        
        sos_msg = MessageTestHelper.create_sos_message("SOS", "Need help")
        assert sos_msg["content"] == "SOS Need help"
        
        # Test ConfigTestHelper
        config = ConfigTestHelper.create_test_config()
        assert "database" in config
        assert "meshtastic" in config
        assert "services" in config
        
        # Test FileTestHelper
        temp_file = FileTestHelper.create_temp_file("test content")
        assert temp_file.exists()
        assert temp_file.read_text() == "test content"
        temp_file.unlink()  # Clean up
        
        print("✅ Utility classes tests passed")
        return True
    except Exception as e:
        print(f"❌ Utility classes test failed: {e}")
        return False


def test_configuration_files():
    """Test that configuration files are valid."""
    print("\nTesting configuration files...")
    
    try:
        import json
        
        # Test pytest.ini exists and is readable
        pytest_ini = Path("pytest.ini")
        assert pytest_ini.exists(), "pytest.ini not found"
        
        # Test sample config YAML exists (don't parse without yaml module)
        config_yaml = Path("tests/data/sample_config.yaml")
        assert config_yaml.exists(), "sample_config.yaml not found"
        
        # Basic content check
        config_content = config_yaml.read_text()
        assert "database:" in config_content
        assert "meshtastic:" in config_content
        
        # Test sample users JSON
        users_json = Path("tests/data/sample_users.json")
        assert users_json.exists(), "sample_users.json not found"
        
        with open(users_json) as f:
            users_data = json.load(f)
        assert isinstance(users_data, list)
        assert len(users_data) > 0
        
        # Test sample messages JSON
        messages_json = Path("tests/data/sample_messages.json")
        assert messages_json.exists(), "sample_messages.json not found"
        
        with open(messages_json) as f:
            messages_data = json.load(f)
        assert isinstance(messages_data, list)
        assert len(messages_data) > 0
        
        print("✅ Configuration files tests passed")
        return True
    except Exception as e:
        print(f"❌ Configuration files test failed: {e}")
        return False


async def main():
    """Run all validation tests."""
    print("ZephyrGate Testing Infrastructure Validation")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Mock Meshtastic Interface", test_mock_meshtastic_interface),
        ("Async Mock Interface", test_async_mock_interface),
        ("External Service Mocks", test_external_service_mocks),
        ("Async External Services", test_async_external_services),
        ("Base Classes", test_base_classes),
        ("Utilities", test_utilities),
        ("Configuration Files", test_configuration_files),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            failed += 1
    
    print(f"\n{'=' * 50}")
    print(f"Validation Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All validation tests passed! Testing infrastructure is ready.")
        return True
    else:
        print(f"\n💥 {failed} validation tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)