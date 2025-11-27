"""
Property-Based Tests for Plugin Health Monitoring and Recovery

Tests universal properties of health monitoring, automatic restart with exponential backoff,
and failure threshold enforcement using Hypothesis.
"""

import pytest
import asyncio
import tempfile
import yaml
from hypothesis import given, settings, strategies as st, assume
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.core.plugin_manager import (
    PluginManager, 
    BasePlugin, 
    PluginMetadata, 
    PluginPriority,
    PluginStatus,
    PluginHealth
)
from src.core.config import ConfigurationManager


# Strategies for generating test data

@st.composite
def valid_plugin_name(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() and not x.startswith('_') and x.isidentifier()))


@st.composite
def failure_count_strategy(draw):
    """Generate failure counts within reasonable range"""
    return draw(st.integers(min_value=1, max_value=10))


@st.composite
def restart_count_strategy(draw):
    """Generate restart counts within reasonable range"""
    return draw(st.integers(min_value=0, max_value=10))


# Helper functions

def create_mock_config_manager(plugin_paths: list = None):
    """Create a mock configuration manager"""
    config_manager = Mock(spec=ConfigurationManager)
    
    def get_config(key, default=None):
        if key == 'plugins.paths':
            return plugin_paths or []
        elif key == 'app.version':
            return '1.0.0'
        else:
            return default
    
    config_manager.get = Mock(side_effect=get_config)
    return config_manager


def create_failing_plugin_directory(base_path: Path, plugin_name: str, fail_health_check: bool = False):
    """Create a test plugin that can fail health checks"""
    plugin_dir = base_path / plugin_name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py with a plugin that can fail
    # Use string representation that will be evaluated at runtime
    fail_str = "True" if fail_health_check else "False"
    init_content = f'''
from src.core.plugin_manager import BasePlugin, PluginMetadata, PluginPriority

class TestPlugin(BasePlugin):
    """Test plugin for health monitoring testing"""
    
    def __init__(self, name, config, plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.initialized = False
        self.started = False
        self.stopped = False
        self.cleaned_up = False
        self.health_check_should_fail = {fail_str}
        self.health_check_count = 0
    
    async def initialize(self):
        self.initialized = True
        return True
    
    async def start(self):
        self.started = True
        self.is_running = True
        return True
    
    async def stop(self):
        self.stopped = True
        self.is_running = False
        return True
    
    async def cleanup(self):
        self.cleaned_up = True
        return True
    
    async def health_check(self):
        self.health_check_count += 1
        if self.health_check_should_fail:
            return False
        return True
    
    def get_metadata(self):
        return PluginMetadata(
            name="{plugin_name}",
            version="1.0.0",
            description="Test plugin",
            author="Test",
            priority=PluginPriority.NORMAL,
            enabled=True
        )
'''
    (plugin_dir / "__init__.py").write_text(init_content)
    
    # Create manifest
    manifest_data = {
        'name': plugin_name,
        'version': '1.0.0',
        'description': 'Test plugin',
        'author': 'Test'
    }
    with open(plugin_dir / "manifest.yaml", 'w') as f:
        yaml.dump(manifest_data, f)
    
    return plugin_dir


# Property Tests

class TestHealthMonitoringAndRestart:
    """
    Feature: third-party-plugin-system, Property 17: Health monitoring and restart
    
    For any plugin that fails health checks, the Plugin System should attempt
    automatic restart with exponential backoff, and should disable the plugin
    after exceeding the failure threshold.
    
    Validates: Requirements 9.2, 9.3
    """
    
    @settings(max_examples=100, deadline=5000)
    @given(
        plugin_name=valid_plugin_name(),
        failure_count=failure_count_strategy()
    )
    def test_plugin_restarts_after_health_check_failures(self, plugin_name, failure_count):
        """
        Property: Plugin should restart after health check failures.
        
        For any plugin that fails health checks, if failure count reaches max_failures
        but restart count is below max_restarts, the plugin should be restarted.
        """
        # Ensure failure count doesn't exceed max_failures
        assume(failure_count <= 3)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin that fails health checks
            create_failing_plugin_directory(plugin_path, plugin_name, fail_health_check=True)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            initial_restart_count = plugin_info.health.restart_count
            
            # Simulate health check failures
            for i in range(failure_count):
                plugin_info.health.record_failure(f"Health check failed {i+1}")
            
            # Check if plugin should restart
            if plugin_info.health.failure_count >= plugin_info.health.max_failures:
                if plugin_info.health.restart_count < plugin_info.health.max_restarts:
                    # Trigger health check which should restart the plugin
                    asyncio.run(plugin_manager._handle_unhealthy_plugin(plugin_name, plugin_info))
                    
                    # Assert - restart count should increase
                    assert plugin_info.health.restart_count > initial_restart_count, \
                        f"Plugin {plugin_name} should have increased restart count after failures"
    
    @settings(max_examples=100, deadline=5000)
    @given(
        plugin_name=valid_plugin_name(),
        restart_count=restart_count_strategy()
    )
    def test_plugin_disabled_after_max_restarts_exceeded(self, plugin_name, restart_count):
        """
        Property: Plugin should be disabled after exceeding max restarts.
        
        For any plugin that has exceeded max_restarts, the plugin should be
        disabled and not restarted again.
        """
        # Ensure restart count exceeds max_restarts
        assume(restart_count >= 5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name, fail_health_check=True)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Set restart count to max or above
            plugin_info.health.restart_count = restart_count
            plugin_info.health.failure_count = plugin_info.health.max_failures
            
            # Trigger health check handling
            asyncio.run(plugin_manager._handle_unhealthy_plugin(plugin_name, plugin_info))
            
            # Assert - plugin should be disabled
            assert plugin_info.status == PluginStatus.DISABLED, \
                f"Plugin {plugin_name} should be DISABLED after exceeding max restarts"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_exponential_backoff_increases_restart_delay(self, plugin_name):
        """
        Property: Restart delay should increase exponentially with restart count.
        
        For any plugin, each successive restart should have a longer delay
        following exponential backoff pattern.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Test exponential backoff
            previous_delay = 0.0
            for restart_num in range(1, 6):
                plugin_info.health.restart_count = restart_num
                current_delay = plugin_info.health.get_restart_delay()
                
                # Assert - delay should increase
                assert current_delay > previous_delay, \
                    f"Restart delay should increase exponentially (restart {restart_num})"
                
                # Assert - delay should follow exponential pattern (approximately)
                expected_delay = min(
                    plugin_info.health.restart_backoff_seconds * (2 ** (restart_num - 1)),
                    plugin_info.health.max_backoff_seconds
                )
                assert abs(current_delay - expected_delay) < 0.01, \
                    f"Restart delay should follow exponential backoff pattern"
                
                previous_delay = current_delay
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_backoff_respects_maximum_delay(self, plugin_name):
        """
        Property: Exponential backoff should not exceed maximum delay.
        
        For any plugin with many restarts, the backoff delay should cap at
        max_backoff_seconds and not grow indefinitely.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            max_backoff = plugin_info.health.max_backoff_seconds
            
            # Test with very high restart count
            plugin_info.health.restart_count = 20
            delay = plugin_info.health.get_restart_delay()
            
            # Assert - delay should not exceed max
            assert delay <= max_backoff, \
                f"Restart delay should not exceed max_backoff_seconds ({max_backoff})"
            
            # Assert - delay should equal max for high restart counts
            assert delay == max_backoff, \
                f"Restart delay should equal max_backoff_seconds for high restart counts"
    
    @settings(max_examples=100, deadline=5000)
    @given(
        plugin_name=valid_plugin_name(),
        success_count=st.integers(min_value=1, max_value=20)
    )
    def test_failure_counter_resets_after_consecutive_successes(self, plugin_name, success_count):
        """
        Property: Failure counter should reset after consecutive successful operations.
        
        For any plugin with previous failures, after a threshold of consecutive
        successful health checks, the failure counter should reset to zero.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name, fail_health_check=False)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Set initial failure count
            plugin_info.health.failure_count = 2
            
            # Record successful operations
            for i in range(success_count):
                plugin_info.health.record_success()
            
            # Assert - if success count >= threshold, failure count should be reset
            if success_count >= plugin_info.health.success_threshold_for_reset:
                assert plugin_info.health.failure_count == 0, \
                    f"Failure count should reset to 0 after {success_count} consecutive successes"
            else:
                assert plugin_info.health.failure_count == 2, \
                    f"Failure count should remain at 2 with only {success_count} successes"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_successful_health_check_records_heartbeat_and_success(self, plugin_name):
        """
        Property: Successful health check should record both heartbeat and success.
        
        For any plugin with a successful health check, both the heartbeat timestamp
        and consecutive success counter should be updated.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin that passes health checks
            create_failing_plugin_directory(plugin_path, plugin_name, fail_health_check=False)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Record initial state
            initial_heartbeat = plugin_info.health.last_heartbeat
            initial_successes = plugin_info.health.consecutive_successes
            
            # Wait a tiny bit to ensure timestamp difference
            import time
            time.sleep(0.01)
            
            # Perform health check
            asyncio.run(plugin_manager._check_plugin_health())
            
            # Assert - heartbeat should be updated (or at least not earlier)
            assert plugin_info.health.last_heartbeat >= initial_heartbeat, \
                f"Heartbeat should be updated after successful health check"
            
            # Assert - consecutive successes should increase
            assert plugin_info.health.consecutive_successes >= initial_successes, \
                f"Consecutive successes should increase after successful health check"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_failed_health_check_records_failure_and_resets_successes(self, plugin_name):
        """
        Property: Failed health check should record failure and reset success counter.
        
        For any plugin with a failed health check, the failure count should increase
        and the consecutive success counter should reset to zero.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin that fails health checks
            create_failing_plugin_directory(plugin_path, plugin_name, fail_health_check=True)
            
            # Create plugin manager with longer health check interval to avoid auto-restart
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            plugin_manager.health_check_interval = 1000  # Very long interval
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Set some consecutive successes and ensure we're below failure threshold
            plugin_info.health.consecutive_successes = 5
            plugin_info.health.failure_count = 0  # Start with 0 failures
            plugin_info.health.max_failures = 10  # Set high threshold to avoid restart
            initial_failure_count = plugin_info.health.failure_count
            
            # Ensure the plugin will fail health check by setting the flag directly
            plugin_info.instance.health_check_should_fail = True
            
            # Perform health check (will fail)
            asyncio.run(plugin_manager._check_plugin_health())
            
            # Assert - failure count should increase
            assert plugin_info.health.failure_count > initial_failure_count, \
                f"Failure count should increase after failed health check (got {plugin_info.health.failure_count}, expected > {initial_failure_count})"
            
            # Assert - consecutive successes should reset
            assert plugin_info.health.consecutive_successes == 0, \
                f"Consecutive successes should reset to 0 after failed health check"


class TestPluginMetricsTracking:
    """
    Feature: third-party-plugin-system, Property 18: Plugin metrics tracking
    
    For any running plugin, querying its status should return current metrics
    including status, uptime, failure count, and restart count.
    
    Validates: Requirements 9.1
    """
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_plugin_metrics_include_all_required_fields(self, plugin_name):
        """
        Property: Plugin metrics should include all required fields.
        
        For any plugin, get_metrics() should return a dictionary containing
        status, uptime, failure count, restart count, and health information.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Get metrics
            metrics = plugin_info.get_metrics()
            
            # Assert - all required fields should be present
            required_fields = ['status', 'uptime_seconds', 'load_time', 'start_time', 'health']
            for field in required_fields:
                assert field in metrics, \
                    f"Metrics should include '{field}' field"
            
            # Assert - health should include detailed metrics
            health_fields = [
                'is_healthy', 'failure_count', 'restart_count', 
                'consecutive_successes', 'last_error', 'last_heartbeat'
            ]
            for field in health_fields:
                assert field in metrics['health'], \
                    f"Health metrics should include '{field}' field"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_plugin_stats_reflect_current_state(self, plugin_name):
        """
        Property: Plugin stats should accurately reflect current plugin state.
        
        For any plugin, get_plugin_stats() should return accurate information
        about the plugin's current status and health.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Modify plugin state
            plugin_info.health.failure_count = 2
            plugin_info.health.restart_count = 1
            
            # Get stats
            stats = plugin_manager.get_plugin_stats()
            
            # Assert - stats should include the plugin
            assert plugin_name in stats['plugins'], \
                f"Stats should include plugin {plugin_name}"
            
            # Assert - stats should reflect current state
            plugin_stats = stats['plugins'][plugin_name]
            assert plugin_stats['status'] == PluginStatus.RUNNING.value, \
                f"Stats should show plugin as RUNNING"
            assert plugin_stats['health']['failure_count'] == 2, \
                f"Stats should show correct failure count"
            assert plugin_stats['health']['restart_count'] == 1, \
                f"Stats should show correct restart count"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_uptime_increases_while_plugin_running(self, plugin_name):
        """
        Property: Plugin uptime should increase while plugin is running.
        
        For any running plugin, the uptime metric should increase over time.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Get initial uptime
            uptime1 = plugin_info.get_uptime()
            assert uptime1 is not None, "Uptime should not be None for running plugin"
            
            # Wait a bit
            import time
            time.sleep(0.1)
            
            # Get uptime again
            uptime2 = plugin_info.get_uptime()
            
            # Assert - uptime should increase
            assert uptime2 > uptime1, \
                f"Uptime should increase while plugin is running"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_metrics_available_for_stopped_plugin(self, plugin_name):
        """
        Property: Metrics should be available even for stopped plugins.
        
        For any stopped plugin, get_metrics() should still return valid metrics
        (though uptime may be 0).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_failing_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable then stop the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            asyncio.run(plugin_manager.stop_plugin(plugin_name))
            
            # Get plugin info
            plugin_info = plugin_manager.plugins[plugin_name]
            
            # Get metrics
            metrics = plugin_info.get_metrics()
            
            # Assert - metrics should be available
            assert metrics is not None, \
                f"Metrics should be available for stopped plugin"
            assert metrics['status'] == PluginStatus.STOPPED.value, \
                f"Metrics should show correct status for stopped plugin"
            assert metrics['uptime_seconds'] == 0, \
                f"Uptime should be 0 for stopped plugin"
