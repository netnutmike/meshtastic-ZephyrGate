"""
Property-based tests for MQTT exponential backoff calculation

Tests universal properties of the exponential backoff algorithm used for
MQTT reconnection attempts.

Property 11: Exponential Backoff Calculation
**Validates: Requirements 2.5, 2.6, 7.2, 8.2**
"""

import pytest
from hypothesis import given, strategies as st, assume
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.mqtt_gateway.mqtt_client import MQTTClient


# Strategy for generating valid configuration parameters
@st.composite
def backoff_config_strategy(draw):
    """Generate valid backoff configuration parameters"""
    initial_delay = draw(st.floats(min_value=0.1, max_value=10.0))
    max_delay = draw(st.floats(min_value=initial_delay, max_value=300.0))
    multiplier = draw(st.floats(min_value=1.1, max_value=5.0))
    
    return {
        'broker_address': 'mqtt.example.com',
        'broker_port': 1883,
        'reconnect_initial_delay': initial_delay,
        'reconnect_max_delay': max_delay,
        'reconnect_multiplier': multiplier,
    }


class TestExponentialBackoffProperties:
    """
    Property-based tests for exponential backoff calculation.
    
    **Feature: mqtt-gateway, Property 11: Exponential Backoff Calculation**
    
    For any reconnection attempt number N, the backoff delay should be
    min(initial_delay * (multiplier ^ N), max_delay) where initial_delay,
    multiplier, and max_delay are configuration parameters.
    """
    
    @given(
        config=backoff_config_strategy(),
        attempt=st.integers(min_value=0, max_value=20)
    )
    def test_backoff_formula_correctness(self, config, attempt):
        """
        Property: Backoff delay follows the exponential formula
        
        For any attempt number, the calculated delay should match:
        min(initial_delay * (multiplier ^ attempt), max_delay)
        """
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Calculate expected delay
        expected_delay = min(initial_delay * (multiplier ** attempt), max_delay)
        
        # Get actual delay from client
        actual_delay = client._calculate_backoff_delay(
            attempt=attempt,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Verify they match (with small tolerance for floating point)
        assert abs(actual_delay - expected_delay) < 0.0001, \
            f"Backoff delay mismatch: expected {expected_delay}, got {actual_delay}"
    
    @given(
        config=backoff_config_strategy(),
        attempt=st.integers(min_value=0, max_value=100)
    )
    def test_backoff_never_exceeds_max_delay(self, config, attempt):
        """
        Property: Backoff delay never exceeds max_delay
        
        For any attempt number, the calculated delay should never be
        greater than the configured max_delay.
        """
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Get actual delay
        actual_delay = client._calculate_backoff_delay(
            attempt=attempt,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Verify it doesn't exceed max
        assert actual_delay <= max_delay, \
            f"Backoff delay {actual_delay} exceeds max_delay {max_delay}"
    
    @given(
        config=backoff_config_strategy(),
        attempt=st.integers(min_value=0, max_value=100)
    )
    def test_backoff_is_non_negative(self, config, attempt):
        """
        Property: Backoff delay is always non-negative
        
        For any attempt number, the calculated delay should be >= 0.
        """
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Get actual delay
        actual_delay = client._calculate_backoff_delay(
            attempt=attempt,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Verify it's non-negative
        assert actual_delay >= 0, \
            f"Backoff delay {actual_delay} is negative"
    
    @given(
        config=backoff_config_strategy()
    )
    def test_backoff_first_attempt_equals_initial_delay(self, config):
        """
        Property: First attempt (attempt=0) returns initial_delay
        
        For attempt number 0, the backoff delay should equal initial_delay
        (since multiplier^0 = 1).
        """
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Get delay for first attempt
        actual_delay = client._calculate_backoff_delay(
            attempt=0,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Should equal initial_delay (or max_delay if initial > max, but our strategy prevents this)
        expected = min(initial_delay, max_delay)
        assert abs(actual_delay - expected) < 0.0001, \
            f"First attempt delay {actual_delay} doesn't match initial_delay {expected}"
    
    @given(
        config=backoff_config_strategy(),
        attempt1=st.integers(min_value=0, max_value=50),
        attempt2=st.integers(min_value=0, max_value=50)
    )
    def test_backoff_monotonically_increases_until_max(self, config, attempt1, attempt2):
        """
        Property: Backoff delay increases monotonically (or stays at max)
        
        For any two attempt numbers where attempt1 < attempt2, the delay
        for attempt2 should be >= delay for attempt1 (until max_delay is reached).
        """
        # Ensure attempt1 < attempt2
        if attempt1 >= attempt2:
            attempt1, attempt2 = attempt2, attempt1
        
        assume(attempt1 < attempt2)
        
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Get delays for both attempts
        delay1 = client._calculate_backoff_delay(
            attempt=attempt1,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        delay2 = client._calculate_backoff_delay(
            attempt=attempt2,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # delay2 should be >= delay1 (monotonically increasing)
        assert delay2 >= delay1, \
            f"Backoff not monotonic: delay at attempt {attempt2} ({delay2}) < delay at attempt {attempt1} ({delay1})"
    
    @given(
        initial_delay=st.floats(min_value=0.1, max_value=10.0),
        max_delay=st.floats(min_value=0.1, max_value=10.0),
        multiplier=st.floats(min_value=1.1, max_value=5.0),
        attempt=st.integers(min_value=0, max_value=20)
    )
    def test_backoff_with_various_parameter_combinations(
        self, initial_delay, max_delay, multiplier, attempt
    ):
        """
        Property: Backoff calculation works with any valid parameter combination
        
        The backoff calculation should handle any combination of valid parameters
        without errors or invalid results.
        """
        # Create config
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883,
            'reconnect_initial_delay': initial_delay,
            'reconnect_max_delay': max_delay,
            'reconnect_multiplier': multiplier,
        }
        
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        # Calculate delay
        actual_delay = client._calculate_backoff_delay(
            attempt=attempt,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Verify basic properties
        assert actual_delay >= 0, "Delay is negative"
        assert actual_delay <= max(initial_delay, max_delay), "Delay exceeds maximum possible"
        assert isinstance(actual_delay, (int, float)), "Delay is not numeric"
    
    @given(
        config=backoff_config_strategy()
    )
    def test_backoff_eventually_reaches_max_delay(self, config):
        """
        Property: Backoff eventually reaches and stays at max_delay
        
        For sufficiently large attempt numbers, the backoff delay should
        reach max_delay and stay there.
        """
        # Create client with test config
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        initial_delay = config['reconnect_initial_delay']
        max_delay = config['reconnect_max_delay']
        multiplier = config['reconnect_multiplier']
        
        # Calculate delay for a very large attempt number
        large_attempt = 100
        actual_delay = client._calculate_backoff_delay(
            attempt=large_attempt,
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier
        )
        
        # Should equal max_delay
        assert abs(actual_delay - max_delay) < 0.0001, \
            f"Large attempt delay {actual_delay} doesn't reach max_delay {max_delay}"


class TestBackoffEdgeCases:
    """Test edge cases for backoff calculation"""
    
    def test_backoff_with_multiplier_one(self):
        """
        Edge case: multiplier = 1.0 means constant delay
        
        When multiplier is 1.0, all delays should equal initial_delay
        (or max_delay if initial > max).
        """
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883,
            'reconnect_initial_delay': 5.0,
            'reconnect_max_delay': 60.0,
            'reconnect_multiplier': 1.0,
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        # All attempts should have same delay
        for attempt in range(10):
            delay = client._calculate_backoff_delay(
                attempt=attempt,
                initial_delay=5.0,
                max_delay=60.0,
                multiplier=1.0
            )
            assert delay == 5.0, f"Delay at attempt {attempt} is {delay}, expected 5.0"
    
    def test_backoff_with_initial_equals_max(self):
        """
        Edge case: initial_delay = max_delay means constant delay
        
        When initial_delay equals max_delay, all delays should be constant.
        """
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883,
            'reconnect_initial_delay': 30.0,
            'reconnect_max_delay': 30.0,
            'reconnect_multiplier': 2.0,
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        # All attempts should have same delay
        for attempt in range(10):
            delay = client._calculate_backoff_delay(
                attempt=attempt,
                initial_delay=30.0,
                max_delay=30.0,
                multiplier=2.0
            )
            assert delay == 30.0, f"Delay at attempt {attempt} is {delay}, expected 30.0"
    
    def test_backoff_with_zero_attempt(self):
        """
        Edge case: attempt = 0 should return initial_delay
        
        The first attempt (0) should always return initial_delay.
        """
        config = {
            'broker_address': 'mqtt.example.com',
            'broker_port': 1883,
            'reconnect_initial_delay': 2.5,
            'reconnect_max_delay': 60.0,
            'reconnect_multiplier': 2.0,
        }
        
        with patch('plugins.mqtt_gateway.mqtt_client.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = MQTTClient(config)
        
        delay = client._calculate_backoff_delay(
            attempt=0,
            initial_delay=2.5,
            max_delay=60.0,
            multiplier=2.0
        )
        
        assert delay == 2.5, f"First attempt delay is {delay}, expected 2.5"
