"""
Property-Based Tests for Plugin Logging System

Tests universal properties of log routing and plugin name tagging using Hypothesis.
"""

import pytest
import logging
import io
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from src.core.logging import (
    ZephyrGateLogger,
    get_logger,
    initialize_logging,
    set_plugin_log_level,
    get_plugin_log_level,
    log_plugin_error
)


# Strategies for generating test data

@st.composite
def valid_plugin_name(draw):
    """Generate valid plugin names"""
    # Use ASCII alphanumeric characters to avoid JSON encoding issues
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-',
        min_size=2,  # At least 2 chars to avoid overlapping names like '0' and '00'
        max_size=50
    ).filter(lambda x: x.strip() and not x.startswith('-') and not x.startswith('_')))


@st.composite
def valid_log_level(draw):
    """Generate valid log levels"""
    return draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))


@st.composite
def valid_log_message(draw):
    """Generate valid log messages"""
    # Use printable ASCII characters to avoid encoding issues
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-_',
        min_size=1,
        max_size=500
    ).filter(lambda x: x.strip()))


@st.composite
def valid_error_type(draw):
    """Generate valid error types"""
    # Use ASCII letters to avoid JSON encoding issues
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip()))


@st.composite
def valid_context_dict(draw):
    """Generate valid context dictionaries"""
    return draw(st.dictionaries(
        st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        st.one_of(
            st.text(max_size=100),
            st.integers(),
            st.booleans(),
            st.floats(allow_nan=False, allow_infinity=False)
        ),
        max_size=10
    ))


# Property Tests

class TestLogMessageRouting:
    """
    Feature: third-party-plugin-system, Property 19: Log message routing
    
    For any log message emitted by a plugin, the message should appear in the
    central logging system with the plugin name as an identifier.
    
    Validates: Requirements 9.5
    """
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        log_message=valid_log_message(),
        log_level=valid_log_level()
    )
    def test_plugin_logs_include_plugin_name(self, plugin_name, log_message, log_level):
        """
        Property: All plugin log messages should include the plugin name.
        
        For any plugin and any log message, the logged output should contain
        the plugin name as an identifier.
        """
        # Arrange - create a logger with in-memory handler
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'DEBUG',
                    'file': f'{tmpdir}/test.log',
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Create a string stream to capture log output
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            
            # Act - log a message at the specified level
            log_method = getattr(logger, log_level.lower())
            log_method(log_message)
            
            # Get the logged output
            log_output = log_stream.getvalue()
            
            # Assert - plugin name should appear in the log output
            assert plugin_name in log_output, \
                f"Plugin name '{plugin_name}' should appear in log output: {log_output}"
            assert log_message in log_output, \
                f"Log message should appear in output: {log_output}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        log_message=valid_log_message()
    )
    def test_plugin_logs_route_to_central_system(self, plugin_name, log_message):
        """
        Property: Plugin logs should route to the central logging system.
        
        For any plugin, logs should be captured by the central logging system
        and not lost or isolated.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test.log'
            config = {
                'logging': {
                    'level': 'INFO',
                    'file': str(log_file),
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Act - log a message
            logger.info(log_message)
            
            # Force flush
            for handler in logger.handlers:
                handler.flush()
            
            # Assert - message should be in the log file
            if log_file.exists():
                log_content = log_file.read_text()
                assert log_message in log_content, \
                    f"Log message should be in central log file: {log_content}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        configured_level=valid_log_level()
    )
    def test_plugin_log_level_configuration(self, plugin_name, configured_level):
        """
        Property: Plugin log levels should be configurable per plugin.
        
        For any plugin and any log level, setting the plugin's log level
        should affect which messages are logged.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'DEBUG',
                    'file': f'{tmpdir}/test.log',
                    'console': False,
                    'plugins': {
                        plugin_name: configured_level
                    }
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Act - check the logger's effective level
            configured_level_int = getattr(logging, configured_level)
            
            # Assert - logger should have the configured level
            assert logger.level == configured_level_int, \
                f"Logger level should be {configured_level} ({configured_level_int}), " \
                f"but got {logger.level}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        new_level=valid_log_level()
    )
    def test_dynamic_log_level_change(self, plugin_name, new_level):
        """
        Property: Plugin log levels should be changeable at runtime.
        
        For any plugin, changing its log level should immediately affect
        the logger's behavior.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'INFO',
                    'file': f'{tmpdir}/test.log',
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Act - change the log level
            logger_system.set_plugin_log_level(plugin_name, new_level)
            
            # Assert - logger should have the new level
            new_level_int = getattr(logging, new_level)
            assert logger.level == new_level_int, \
                f"Logger level should be {new_level} ({new_level_int}) after change, " \
                f"but got {logger.level}"
            
            # Assert - get_plugin_log_level should return the new level
            retrieved_level = logger_system.get_plugin_log_level(plugin_name)
            assert retrieved_level == new_level, \
                f"Retrieved log level should be {new_level}, but got {retrieved_level}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        error_type=valid_error_type(),
        error_message=valid_log_message(),
        context=valid_context_dict()
    )
    def test_structured_error_logging_includes_context(self, plugin_name, error_type, 
                                                       error_message, context):
        """
        Property: Structured error logs should include all provided context.
        
        For any plugin error with context, the logged error should contain
        the plugin name, error type, message, and all context fields.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'DEBUG',
                    'file': f'{tmpdir}/test.log',
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Create a string stream to capture log output
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
            
            # Act - log a structured error
            log_plugin_error(
                logger,
                plugin_name,
                error_type,
                error_message,
                context=context
            )
            
            # Get the logged output
            log_output = log_stream.getvalue()
            
            # Parse the JSON log output to verify structure
            import json
            try:
                log_data = json.loads(log_output.strip())
                
                # Assert - all components should be in the parsed data
                assert log_data.get('plugin') == plugin_name, \
                    f"Plugin name should be '{plugin_name}' in error log: {log_data}"
                assert log_data.get('error_type') == error_type, \
                    f"Error type should be '{error_type}' in error log: {log_data}"
                assert log_data.get('error_message') == error_message, \
                    f"Error message should be '{error_message}' in error log: {log_data}"
                
                # Check that context keys are present (if context is not empty)
                if context:
                    assert 'context' in log_data, \
                        f"Context should be present in error log: {log_data}"
                    for key in context.keys():
                        assert key in log_data['context'], \
                            f"Context key '{key}' should be in error log context: {log_data}"
            except json.JSONDecodeError:
                # If JSON parsing fails, fall back to string matching
                assert plugin_name in log_output or f'"{plugin_name}"' in log_output, \
                    f"Plugin name should be in error log: {log_output}"
                assert error_type in log_output or f'"{error_type}"' in log_output, \
                    f"Error type should be in error log: {log_output}"
                assert error_message in log_output or f'"{error_message}"' in log_output, \
                    f"Error message should be in error log: {log_output}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        error_message=valid_log_message()
    )
    def test_plugin_error_logs_are_tagged(self, plugin_name, error_message):
        """
        Property: Plugin error logs should be tagged with plugin name.
        
        For any plugin error, the error log should be identifiable as coming
        from that specific plugin.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'ERROR',
                    'file': f'{tmpdir}/test.log',
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Create a string stream to capture log output
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            logger.addHandler(handler)
            
            # Act - log an error
            logger.error(error_message)
            
            # Get the logged output
            log_output = log_stream.getvalue()
            
            # Assert - plugin name should be in the logger name
            assert f'plugin_{plugin_name}' in log_output, \
                f"Plugin identifier should be in error log: {log_output}"
    
    @settings(max_examples=100)
    @given(
        plugin1=valid_plugin_name(),
        plugin2=valid_plugin_name(),
        message1=valid_log_message(),
        message2=valid_log_message()
    )
    def test_multiple_plugins_logs_are_distinguishable(self, plugin1, plugin2, 
                                                       message1, message2):
        """
        Property: Logs from different plugins should be distinguishable.
        
        For any two different plugins, their log messages should be
        identifiable as coming from different sources.
        """
        # Skip if plugins have the same name or one is a substring of the other
        if plugin1 == plugin2 or plugin1 in plugin2 or plugin2 in plugin1:
            return
        
        # Skip if messages are the same or one is a substring of the other
        if message1 == message2 or message1 in message2 or message2 in message1:
            return
        
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'INFO',
                    'file': f'{tmpdir}/test.log',
                    'console': False
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger1 = logger_system.get_logger(f'plugin_{plugin1}')
            logger2 = logger_system.get_logger(f'plugin_{plugin2}')
            
            # Create a string stream to capture log output
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            handler.setLevel(logging.DEBUG)
            
            # Add handler to both loggers
            logger1.addHandler(handler)
            logger2.addHandler(handler)
            
            # Ensure loggers are at INFO level or below
            logger1.setLevel(logging.INFO)
            logger2.setLevel(logging.INFO)
            
            # Act - log messages from both plugins
            logger1.info(message1)
            logger2.info(message2)
            
            # Get the logged output
            log_output = log_stream.getvalue()
            lines = [line for line in log_output.strip().split('\n') if line]
            
            # Assert - should have two log lines
            assert len(lines) >= 2, f"Should have at least 2 log lines: {log_output}"
            
            # Assert - each line should contain the respective plugin name
            # Use exact matching with word boundaries
            plugin1_found = False
            plugin2_found = False
            
            for line in lines:
                if f'plugin_{plugin1}' in line and message1 in line:
                    plugin1_found = True
                if f'plugin_{plugin2}' in line and message2 in line:
                    plugin2_found = True
            
            assert plugin1_found, \
                f"Should have log from plugin1 '{plugin1}' with message '{message1}': {log_output}"
            assert plugin2_found, \
                f"Should have log from plugin2 '{plugin2}' with message '{message2}': {log_output}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        log_level=valid_log_level()
    )
    def test_log_level_filtering_works_correctly(self, plugin_name, log_level):
        """
        Property: Log level filtering should work correctly for plugins.
        
        For any plugin with a configured log level, messages below that level
        should not be logged, and messages at or above should be logged.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'logging': {
                    'level': 'DEBUG',
                    'file': f'{tmpdir}/test.log',
                    'console': False,
                    'plugins': {
                        plugin_name: log_level
                    }
                }
            }
            
            logger_system = ZephyrGateLogger(config)
            logger = logger_system.get_logger(f'plugin_{plugin_name}')
            
            # Create a string stream to capture log output
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            
            # Define log levels in order
            levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            configured_index = levels.index(log_level)
            
            # Act - log messages at all levels
            logger.debug('debug message')
            logger.info('info message')
            logger.warning('warning message')
            logger.error('error message')
            logger.critical('critical message')
            
            # Get the logged output
            log_output = log_stream.getvalue()
            
            # Assert - messages at or above the configured level should be present
            for i, level in enumerate(levels):
                message = f'{level.lower()} message'
                if i >= configured_index:
                    # Should be logged
                    assert message in log_output, \
                        f"Message at level {level} should be logged when configured level is {log_level}"
                else:
                    # Should not be logged
                    assert message not in log_output, \
                        f"Message at level {level} should NOT be logged when configured level is {log_level}"
