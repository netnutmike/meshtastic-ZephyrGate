# ZephyrGate Testing Infrastructure

This directory contains the comprehensive testing infrastructure for ZephyrGate, including unit tests, integration tests, mock objects, and testing utilities.

## Directory Structure

```
tests/
├── README.md                    # This file
├── conftest.py                  # Global pytest configuration and fixtures
├── base.py                      # Base test classes
├── utils.py                     # Testing utilities and helpers
├── data/                        # Test data files
│   ├── sample_config.yaml       # Sample configuration for testing
│   ├── sample_users.json        # Sample user data
│   └── sample_messages.json     # Sample message data
├── mocks/                       # Mock objects
│   ├── __init__.py
│   ├── meshtastic_mocks.py      # Mock Meshtastic interfaces
│   └── external_service_mocks.py # Mock external services
├── unit/                        # Unit tests
│   ├── __init__.py
│   └── test_example.py          # Example unit tests
└── integration/                 # Integration tests
    ├── __init__.py
    └── test_example.py          # Example integration tests
```

## Running Tests

### Prerequisites

Install the required testing dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov
```

### Basic Test Commands

```bash
# Run all tests
pytest

# Run unit tests only
pytest -m unit

# Run integration tests only
pytest -m integration

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest -n 4

# Run specific test file
pytest tests/unit/test_example.py

# Run specific test function
pytest tests/unit/test_example.py::TestExampleUnit::test_basic_functionality
```

### Using the Test Runner Script

The project includes a convenient test runner script:

```bash
# Run all tests
python run_tests.py

# Run unit tests only
python run_tests.py --unit

# Run integration tests only
python run_tests.py --integration

# Run tests with coverage
python run_tests.py --coverage

# Run tests excluding slow ones
python run_tests.py --fast

# Run tests in parallel
python run_tests.py --parallel 4
```

### Using Make Commands

If you have `make` available:

```bash
# Run all tests
make test

# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run tests with coverage
make test-coverage

# Run fast tests (excluding slow ones)
make test-fast
```

## Test Markers

The testing infrastructure uses pytest markers to categorize tests:

- `unit`: Unit tests
- `integration`: Integration tests
- `slow`: Slow running tests
- `external`: Tests requiring external services
- `meshtastic`: Tests requiring Meshtastic hardware
- `network`: Tests requiring network connectivity
- `database`: Tests requiring database
- `redis`: Tests requiring Redis
- `email`: Tests requiring email services
- `weather`: Tests requiring weather APIs
- `ai`: Tests requiring AI services

## Base Test Classes

### BaseTestCase

Basic test case with common functionality:

```python
from tests.base import BaseTestCase

class TestMyFeature(BaseTestCase):
    def test_something(self):
        # Create temporary file
        temp_file = self.create_temp_file("content")
        assert temp_file.exists()
        
        # Add mock patch (automatically cleaned up)
        mock_obj = self.add_patch("module.function")
        mock_obj.return_value = "mocked"
```

### AsyncTestCase

For testing async functionality:

```python
from tests.base import AsyncTestCase

class TestAsyncFeature(AsyncTestCase):
    async def test_async_operation(self):
        # Wait for condition
        success = await self.wait_for_condition(
            lambda: some_condition(), 
            timeout=1.0
        )
        assert success
```

### DatabaseTestCase

For database-related tests:

```python
from tests.base import DatabaseTestCase

class TestDatabaseFeature(DatabaseTestCase):
    def test_database_operation(self):
        # Create test database
        db_path = self.create_test_database()
        
        # Insert test data
        users = [{"node_id": "!12345678", "short_name": "TEST"}]
        self.insert_test_data("users", users)
```

### IntegrationTestCase

For comprehensive integration tests:

```python
from tests.base import IntegrationTestCase

class TestIntegration(IntegrationTestCase):
    async def test_full_workflow(self):
        # Set up database
        db_path = self.create_test_database()
        
        # Create mock interface
        interface = self.create_mock_interface("test")
        await interface.connect()
        
        # Simulate message
        await self.simulate_message_received("test", "Hello")
        
        # Use external services
        weather = await self.weather_service.get_current_weather(40.7, -74.0)
```

## Mock Objects

### Meshtastic Mocks

Mock Meshtastic interfaces for testing without hardware:

```python
from tests.mocks.meshtastic_mocks import MockMeshtasticInterface

# Create mock interface
interface = MockMeshtasticInterface("serial", port="/dev/ttyUSB0")
await interface.connect()

# Send message
await interface.send_message("Test message")

# Simulate received message
await interface.simulate_received_message("Hello from mesh")

# Add nodes
interface.add_node("!12345678", "TEST", "Test Node", 40.7128, -74.0060)
```

### External Service Mocks

Mock external services for testing without dependencies:

```python
from tests.mocks.external_service_mocks import MockWeatherService, MockEmailService

# Weather service
weather = MockWeatherService()
current = await weather.get_current_weather(40.7128, -74.0060)

# Email service
email = MockEmailService()
await email.connect_smtp("smtp.example.com", 587, "user", "pass")
await email.send_email("test@example.com", "Subject", "Body")
```

## Test Utilities

### Message Helper

Create test messages easily:

```python
from tests.utils import MessageTestHelper

helper = MessageTestHelper()

# Create basic message
msg = helper.create_test_message("Hello world")

# Create SOS message
sos_msg = helper.create_sos_message("SOS", "Need help")

# Create command message
cmd_msg = helper.create_command_message("ping")
```

### Config Helper

Manage test configurations:

```python
from tests.utils import ConfigTestHelper

helper = ConfigTestHelper()

# Create test config
config = helper.create_test_config({
    "services": {"bbs": {"enabled": True}}
})

# Create config file
config_file = helper.create_config_file(config, "yaml")
```

### Database Helper

Database testing utilities:

```python
from tests.utils import DatabaseTestHelper

helper = DatabaseTestHelper()

# Insert test users
users = [{"node_id": "!12345678", "short_name": "TEST"}]
helper.insert_test_users(db_path, users)

# Count rows
count = helper.count_table_rows(db_path, "users")

# Get data
data = helper.get_table_data(db_path, "users", "short_name = 'TEST'")
```

## Test Data

The `tests/data/` directory contains sample data files:

- `sample_config.yaml`: Complete configuration example
- `sample_users.json`: Sample user profiles
- `sample_messages.json`: Sample message data

These files can be used in tests to provide realistic data scenarios.

## Writing New Tests

### Unit Tests

1. Create test file in `tests/unit/`
2. Use appropriate base class
3. Add test markers
4. Use mock objects for dependencies

```python
import pytest
from tests.base import BaseTestCase

@pytest.mark.unit
class TestMyModule(BaseTestCase):
    def test_functionality(self):
        # Test implementation
        pass
```

### Integration Tests

1. Create test file in `tests/integration/`
2. Use IntegrationTestCase
3. Set up required infrastructure
4. Test complete workflows

```python
import pytest
from tests.base import IntegrationTestCase

@pytest.mark.integration
class TestMyIntegration(IntegrationTestCase):
    async def test_workflow(self):
        # Integration test implementation
        pass
```

## Continuous Integration

The testing infrastructure is designed to work in CI environments:

- All external dependencies are mocked
- Tests can run without hardware
- Parallel execution supported
- Coverage reporting included
- Multiple Python versions supported

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Async Test Failures**: Use AsyncTestCase for async tests
3. **Database Errors**: Use DatabaseTestCase for database tests
4. **Mock Issues**: Check mock setup and cleanup

### Debugging Tests

```bash
# Run with verbose output
pytest -v

# Run with debug output
pytest -s

# Run specific test with debugging
pytest -v -s tests/unit/test_example.py::TestExampleUnit::test_basic_functionality

# Use pdb for debugging
pytest --pdb
```

### Performance

For faster test execution:

```bash
# Skip slow tests
pytest -m "not slow"

# Run in parallel
pytest -n auto

# Use fast test runner
python run_tests.py --fast
```

## Contributing

When adding new tests:

1. Follow existing patterns and conventions
2. Use appropriate base classes
3. Add proper test markers
4. Include docstrings
5. Mock external dependencies
6. Clean up resources in teardown
7. Add to appropriate test category (unit/integration)

The testing infrastructure is designed to be comprehensive, maintainable, and easy to use. It provides the foundation for reliable testing of all ZephyrGate components.