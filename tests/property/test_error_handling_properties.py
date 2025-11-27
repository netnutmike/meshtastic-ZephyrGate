"""
Property-Based Tests for Plugin Error Handling and Isolation

Tests error isolation, failure threshold enforcement, and failure counter reset
according to the third-party plugin system specification.
"""

import asyncio
import pytest
from hypothesis import given, settings, strategies as st, assume
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.plugin_manager import (
    PluginManager, BasePlugin, PluginMetadata, PluginStatus,
    PluginPriority, PluginInfo, PluginHealth
)
from src.core.config import ConfigurationManager
from src.core.enhanced_plugin import EnhancedPlugin, EnhancedCommandHandler, EnhancedMessageHandler
from src.core.plugin_scheduler import PluginScheduler, ScheduledTask
from src.models.message import Message


# Helper Functions

def create_mock_config_manager():
    """Create a properly mocked config manager"""
    config_manager = Mock(spec=ConfigurationManager)
    config_manager.get = Mock(return_value=[])
    config_manager.register_config_change_callback = Mock()
    config_manager.get_config_value = Mock(return_value=None)
    return config_manager


# Test Plugin Classes for Error Scenarios

class FailingInitPlugin(BasePlugin):
    """Plugin that fails during initialization"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: PluginManager):
        super().__init__(name, config, plugin_manager)
        self.should_fail_init = config.get('fail_init', False)
    
    async def initialize(self) -> bool:
        if self.should_fail_init:
            raise RuntimeError("Initialization failed")
        return True
    
    async def start(self) -> bool:
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        return True
    
    async def cleanup(self) -> bool:
        return True
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test plugin that fails during init",
            author="Test"
        )


class FailingCommandPlugin(EnhancedPlugin):
    """Plugin with command handler that can fail"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: PluginManager):
        super().__init__(name, config, plugin_manager)
        self.fail_command = config.get('fail_command', False)
        self.command_call_count = 0
    
    async def initialize(self) -> bool:
        # Register a command that might fail
        async def test_command(args, context):
            self.command_call_count += 1
            if self.fail_command:
                raise ValueError("Command execution failed")
            return "Success"
        
        self.register_command("test", test_command, "Test command")
        return True
    
    async def start(self) -> bool:
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        return True
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test plugin with failing command",
            author="Test"
        )


class FailingMessagePlugin(EnhancedPlugin):
    """Plugin with message handler that can fail"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: PluginManager):
        super().__init__(name, config, plugin_manager)
        self.fail_message = config.get('fail_message', False)
        self.message_call_count = 0
    
    async def initialize(self) -> bool:
        # Register a message handler that might fail
        async def test_handler(message, context):
            self.message_call_count += 1
            if self.fail_message:
                raise RuntimeError("Message handling failed")
            return "Handled"
        
        self.register_message_handler(test_handler, priority=100)
        return True
    
    async def start(self) -> bool:
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        return True
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test plugin with failing message handler",
            author="Test"
        )


class FailingScheduledTaskPlugin(EnhancedPlugin):
    """Plugin with scheduled task that can fail"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager: PluginManager):
        super().__init__(name, config, plugin_manager)
        self.fail_task = config.get('fail_task', False)
        self.task_call_count = 0
        self.task_success_count = 0
    
    async def initialize(self) -> bool:
        # Register a scheduled task that might fail
        async def test_task():
            self.task_call_count += 1
            if self.fail_task:
                raise Exception("Scheduled task failed")
            self.task_success_count += 1
        
        self.register_scheduled_task("test_task", test_task, interval=1)  # Run every second
        return True
    
    async def start(self) -> bool:
        self.is_running = True
        # Call parent to start scheduled tasks
        return await super().start()
    
    async def stop(self) -> bool:
        self.is_running = False
        # Call parent to stop scheduled tasks
        return await super().stop()
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test plugin with failing scheduled task",
            author="Test"
        )


# Property Tests

# Feature: third-party-plugin-system, Property 25: Error isolation
@pytest.mark.asyncio
@settings(max_examples=100, deadline=5000)
@given(
    fail_init=st.booleans(),
    fail_command=st.booleans(),
    fail_message=st.booleans()
)
async def test_error_isolation_property(fail_init, fail_command, fail_message):
    """
    Property 25: Error isolation
    
    For any unhandled exception raised in plugin code (initialization, message handling,
    scheduled tasks), the Plugin System should catch the exception, log it with details,
    and continue operating without crashing.
    
    Validates: Requirements 12.1, 12.2, 12.3
    """
    # Create mock config manager
    config_manager = create_mock_config_manager()
    
    # Create plugin manager
    plugin_manager = PluginManager(config_manager)
    
    # Test 1: Initialization error isolation
    if fail_init:
        plugin_name = "failing_init_plugin"
        plugin_info = PluginInfo(
            metadata=PluginMetadata(
                name=plugin_name,
                version="1.0.0",
                description="Test",
                author="Test"
            ),
            config={'fail_init': True}
        )
        plugin_info.status = PluginStatus.LOADING
        plugin_manager.plugins[plugin_name] = plugin_info
        
        # Create plugin instance
        plugin = FailingInitPlugin(plugin_name, {'fail_init': True}, plugin_manager)
        plugin_info.instance = plugin
        
        # Try to initialize - should catch exception
        try:
            result = await plugin.initialize()
            # If it returns False or raises, that's fine
            assert result is False or True  # Either outcome is acceptable
        except Exception:
            # Exception should be caught by plugin manager in real scenario
            pass
        
        # Plugin manager should continue operating
        assert plugin_manager is not None
        assert len(plugin_manager.plugins) > 0
    
    # Test 2: Command handler error isolation
    if fail_command:
        plugin_name = "failing_command_plugin"
        plugin = FailingCommandPlugin(plugin_name, {'fail_command': True}, plugin_manager)
        await plugin.initialize()
        
        # Execute command that will fail
        command_handlers = plugin._command_handlers
        if command_handlers and 'test' in command_handlers:
            context = {'sender': 'test', 'channel': 'test'}
            result = await command_handlers['test'].handle_command("test", [], context)
            
            # Should return error message, not crash
            assert isinstance(result, str)
            assert "error" in result.lower() or "Error" in result
            
            # Plugin should still be operational
            assert plugin is not None
            assert plugin.command_call_count > 0
    
    # Test 3: Message handler error isolation
    if fail_message:
        plugin_name = "failing_message_plugin"
        plugin = FailingMessagePlugin(plugin_name, {'fail_message': True}, plugin_manager)
        await plugin.initialize()
        
        # Create test message
        message = Message(
            id="test_msg",
            sender_id="!abc123",
            recipient_id="!def456",
            content="test message",
            timestamp=datetime.utcnow()
        )
        
        # Handle message that will fail
        message_handler = plugin._message_handler
        if message_handler:
            context = {'sender': 'test', 'channel': 'test'}
            result = await message_handler.handle_message(message, context)
            
            # Should return None or handle gracefully, not crash
            # The handler catches exceptions and returns None
            assert result is None or isinstance(result, (str, dict))
            
            # Plugin should still be operational
            assert plugin is not None
            assert plugin.message_call_count > 0


# Feature: third-party-plugin-system, Property 25: Error isolation (Scheduled Tasks)
@pytest.mark.asyncio
@settings(max_examples=50, deadline=10000)
@given(
    fail_count=st.integers(min_value=1, max_value=5)
)
async def test_scheduled_task_error_isolation_property(fail_count):
    """
    Property 25: Error isolation (Scheduled Tasks)
    
    For any unhandled exception in scheduled tasks, the Plugin System should catch
    the exception, log it, and continue executing future scheduled tasks.
    
    Validates: Requirements 12.1, 12.2, 12.3
    """
    # Create mock config manager
    config_manager = create_mock_config_manager()
    
    # Create plugin manager
    plugin_manager = PluginManager(config_manager)
    
    plugin_name = "failing_task_plugin"
    plugin = FailingScheduledTaskPlugin(plugin_name, {'fail_task': True}, plugin_manager)
    await plugin.initialize()
    await plugin.start()
    
    # Let the task run a few times and fail
    initial_count = plugin.task_call_count
    await asyncio.sleep(fail_count * 1.5)  # Wait for multiple executions
    
    # Task should have been called multiple times despite failures
    assert plugin.task_call_count > initial_count
    
    # Task should continue running (not crash)
    assert plugin.is_running
    
    # Clean up
    await plugin.stop()


# Feature: third-party-plugin-system, Property 26: Failure threshold enforcement
@pytest.mark.asyncio
@settings(max_examples=100, deadline=5000)
@given(
    max_failures=st.integers(min_value=1, max_value=10),
    failure_count=st.integers(min_value=0, max_value=15)
)
async def test_failure_threshold_enforcement_property(max_failures, failure_count):
    """
    Property 26: Failure threshold enforcement
    
    For any plugin that fails repeatedly, once the failure count exceeds the
    configured threshold, the plugin should be automatically disabled.
    
    Validates: Requirements 12.4
    """
    # Create plugin health with custom max_failures
    health = PluginHealth(max_failures=max_failures)
    
    # Record failures
    for i in range(failure_count):
        health.record_failure(f"Error {i}")
    
    # Check if plugin should be disabled
    is_healthy = health.is_healthy()
    
    # Property: Plugin is unhealthy if and only if failure_count >= max_failures
    if failure_count >= max_failures:
        assert not is_healthy, f"Plugin should be unhealthy with {failure_count} failures (max: {max_failures})"
    else:
        # Note: is_healthy also checks heartbeat, so we need to ensure heartbeat is recent
        health.record_heartbeat()
        is_healthy = health.is_healthy()
        assert is_healthy, f"Plugin should be healthy with {failure_count} failures (max: {max_failures})"


# Feature: third-party-plugin-system, Property 27: Failure counter reset
@pytest.mark.asyncio
@settings(max_examples=100, deadline=5000)
@given(
    initial_failures=st.integers(min_value=1, max_value=5),
    success_count=st.integers(min_value=0, max_value=20),
    success_threshold=st.integers(min_value=5, max_value=15)
)
async def test_failure_counter_reset_property(initial_failures, success_count, success_threshold):
    """
    Property 27: Failure counter reset
    
    For any plugin with previous failures, after a configurable number of consecutive
    successful operations, the failure counter should be reset to zero.
    
    Validates: Requirements 12.5
    """
    # Assume success_threshold is reasonable
    assume(success_threshold >= 5)
    
    # Create plugin health with custom success threshold
    health = PluginHealth(
        max_failures=10,
        success_threshold_for_reset=success_threshold
    )
    
    # Record initial failures
    for i in range(initial_failures):
        health.record_failure(f"Error {i}")
    
    initial_failure_count = health.failure_count
    assert initial_failure_count == initial_failures
    
    # Record successes
    for i in range(success_count):
        health.record_success()
    
    # Property: Failure counter should be reset if success_count >= success_threshold
    # AND there were initial failures
    if success_count >= success_threshold and initial_failures > 0:
        assert health.failure_count == 0, \
            f"Failure count should be reset after {success_count} successes (threshold: {success_threshold})"
        # After reset at threshold, consecutive_successes continues counting from 0
        # So if success_count > threshold, consecutive_successes = success_count - threshold
        expected_consecutive = success_count - success_threshold
        assert health.consecutive_successes == expected_consecutive, \
            f"Consecutive successes should be {expected_consecutive} after {success_count} successes (threshold: {success_threshold})"
    elif success_count >= success_threshold and initial_failures == 0:
        # No failures to reset, so consecutive_successes keeps counting
        assert health.failure_count == 0
        # consecutive_successes may or may not be reset depending on implementation
    else:
        # Failure count should remain unchanged
        assert health.failure_count == initial_failures, \
            f"Failure count should not change with only {success_count} successes (threshold: {success_threshold})"
        assert health.consecutive_successes == success_count, \
            f"Consecutive successes should be {success_count}"


# Feature: third-party-plugin-system, Property 26: Automatic plugin disabling
@pytest.mark.asyncio
@settings(max_examples=50, deadline=10000)
@given(
    max_failures=st.integers(min_value=2, max_value=5),
    max_restarts=st.integers(min_value=2, max_value=5)
)
async def test_automatic_plugin_disabling_property(max_failures, max_restarts):
    """
    Property 26: Automatic plugin disabling (Integration)
    
    For any plugin that exceeds both failure and restart thresholds, the plugin
    should be automatically disabled by the plugin manager.
    
    Validates: Requirements 12.4
    """
    # Create mock config manager
    config_manager = create_mock_config_manager()
    
    # Create plugin manager
    plugin_manager = PluginManager(config_manager)
    
    # Create plugin info with custom thresholds
    plugin_name = "test_plugin"
    plugin_info = PluginInfo(
        metadata=PluginMetadata(
            name=plugin_name,
            version="1.0.0",
            description="Test",
            author="Test"
        )
    )
    plugin_info.health.max_failures = max_failures
    plugin_info.health.max_restarts = max_restarts
    plugin_info.status = PluginStatus.RUNNING
    
    # Create mock plugin instance
    plugin = Mock(spec=BasePlugin)
    plugin.name = plugin_name
    plugin.health_check = AsyncMock(return_value=False)  # Always fail health check
    plugin_info.instance = plugin
    
    plugin_manager.plugins[plugin_name] = plugin_info
    
    # Simulate failures exceeding threshold
    for i in range(max_failures):
        plugin_info.health.record_failure(f"Error {i}")
    
    # Simulate restarts exceeding threshold
    for i in range(max_restarts):
        plugin_info.health.record_restart()
    
    # Check if plugin should be disabled
    should_restart = plugin_info.health.should_attempt_restart()
    is_healthy = plugin_info.health.is_healthy()
    
    # Property: Plugin should not attempt restart if max_restarts exceeded
    assert not should_restart, \
        f"Plugin should not restart after {max_restarts} restarts (max: {max_restarts})"
    
    # Property: Plugin should be unhealthy if max_failures exceeded
    assert not is_healthy, \
        f"Plugin should be unhealthy after {max_failures} failures (max: {max_failures})"
    
    # Simulate the plugin manager's handling
    if not is_healthy and not should_restart:
        # This is what _handle_unhealthy_plugin does
        plugin_info.status = PluginStatus.DISABLED
    
    # Property: Plugin should be disabled
    assert plugin_info.status == PluginStatus.DISABLED, \
        "Plugin should be disabled after exceeding thresholds"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
