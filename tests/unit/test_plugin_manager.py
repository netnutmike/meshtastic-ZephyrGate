"""
Unit tests for the Plugin Management System
"""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.core.plugin_manager import (
    PluginManager, BasePlugin, PluginStatus, PluginPriority,
    PluginMetadata, PluginDependency, PluginHealth, PluginInfo
)
from src.core.config import ConfigurationManager


class MockPlugin(BasePlugin):
    """Mock plugin for testing"""
    
    def __init__(self, name: str, config: dict, plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.initialized = False
        self.started = False
        self.stopped = False
        self.cleaned_up = False
        self.should_fail_init = False
        self.should_fail_start = False
        self.should_fail_stop = False
        self.should_fail_health = False
    
    async def initialize(self) -> bool:
        if self.should_fail_init:
            return False
        self.initialized = True
        return True
    
    async def start(self) -> bool:
        if self.should_fail_start:
            return False
        self.started = True
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        if self.should_fail_stop:
            return False
        self.stopped = True
        self.is_running = False
        return True
    
    async def cleanup(self) -> bool:
        self.cleaned_up = True
        return True
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Mock plugin for testing",
            author="Test Author",
            priority=PluginPriority.NORMAL
        )
    
    async def health_check(self) -> bool:
        if self.should_fail_health:
            return False
        return self.is_running


class MockPluginWithDependencies(MockPlugin):
    """Mock plugin with dependencies"""
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Mock plugin with dependencies",
            author="Test Author",
            dependencies=[
                PluginDependency("dependency1", optional=False),
                PluginDependency("dependency2", optional=True)
            ],
            priority=PluginPriority.LOW
        )


@pytest.fixture
def config_manager():
    """Create a test configuration manager"""
    config_mgr = ConfigurationManager()
    config_mgr.config = {
        "plugins": {
            "paths": [],
            "health_check_interval": 1.0
        }
    }
    return config_mgr


@pytest.fixture
def plugin_manager(config_manager):
    """Create a test plugin manager"""
    return PluginManager(config_manager)


@pytest.fixture
def temp_plugin_dir():
    """Create a temporary directory for plugin testing"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestPluginMetadata:
    """Test plugin metadata functionality"""
    
    def test_plugin_metadata_creation(self):
        """Test creating plugin metadata"""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author"
        )
        
        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.author == "Test Author"
        assert metadata.priority == PluginPriority.NORMAL
        assert metadata.enabled is True
        assert len(metadata.dependencies) == 0
    
    def test_plugin_metadata_with_dependencies(self):
        """Test plugin metadata with dependencies"""
        deps = [
            PluginDependency("dep1", version="1.0.0", optional=False),
            PluginDependency("dep2", optional=True)
        ]
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            dependencies=deps,
            priority=PluginPriority.HIGH
        )
        
        assert len(metadata.dependencies) == 2
        assert metadata.dependencies[0].name == "dep1"
        assert metadata.dependencies[0].version == "1.0.0"
        assert metadata.dependencies[0].optional is False
        assert metadata.dependencies[1].name == "dep2"
        assert metadata.dependencies[1].optional is True
        assert metadata.priority == PluginPriority.HIGH
    
    def test_plugin_metadata_validation(self):
        """Test plugin metadata validation"""
        # Test invalid name
        with pytest.raises(ValueError, match="Plugin name must be a non-empty string"):
            PluginMetadata(name="", version="1.0.0", description="Test", author="Test")
        
        # Test invalid version
        with pytest.raises(ValueError, match="Plugin version must be a non-empty string"):
            PluginMetadata(name="test", version="", description="Test", author="Test")


class TestPluginHealth:
    """Test plugin health monitoring"""
    
    def test_plugin_health_creation(self):
        """Test creating plugin health tracker"""
        health = PluginHealth()
        
        assert health.failure_count == 0
        assert health.restart_count == 0
        assert health.last_error is None
        assert health.max_failures == 3
        assert health.max_restarts == 5
        assert health.is_healthy() is True
    
    def test_plugin_health_heartbeat(self):
        """Test plugin heartbeat recording"""
        health = PluginHealth()
        old_heartbeat = health.last_heartbeat
        
        # Wait a bit and record heartbeat
        import time
        time.sleep(0.01)
        health.record_heartbeat()
        
        assert health.last_heartbeat > old_heartbeat
        assert health.is_healthy() is True
    
    def test_plugin_health_failure_recording(self):
        """Test failure recording"""
        health = PluginHealth()
        
        health.record_failure("Test error")
        
        assert health.failure_count == 1
        assert health.last_error == "Test error"
        assert health.last_error_time is not None
        assert health.is_healthy() is True  # Still healthy with 1 failure
        
        # Record more failures
        health.record_failure("Another error")
        health.record_failure("Third error")
        
        assert health.failure_count == 3
        assert health.is_healthy() is False  # Now unhealthy
    
    def test_plugin_health_restart_recording(self):
        """Test restart recording"""
        health = PluginHealth()
        
        # Record failures
        health.record_failure("Error 1")
        health.record_failure("Error 2")
        assert health.failure_count == 2
        
        # Record restart
        health.record_restart()
        
        assert health.restart_count == 1
        assert health.failure_count == 0  # Reset on restart
        assert health.is_healthy() is True
    
    def test_plugin_health_timeout(self):
        """Test health timeout detection"""
        health = PluginHealth(heartbeat_interval=0.1)  # 0.1 second interval
        
        # Initially healthy
        assert health.is_healthy() is True
        
        # Wait for timeout
        import time
        time.sleep(0.3)  # Wait longer than 2 * interval
        
        assert health.is_healthy() is False
    
    def test_plugin_health_reset(self):
        """Test health reset"""
        health = PluginHealth()
        
        # Record some failures and restarts
        health.record_failure("Error 1")
        health.record_failure("Error 2")
        health.record_restart()
        
        assert health.failure_count == 0  # Reset by restart
        assert health.restart_count == 1
        
        # Full reset
        health.reset()
        
        assert health.failure_count == 0
        assert health.restart_count == 0
        assert health.last_error is None
        assert health.last_error_time is None
        assert health.is_healthy() is True


class TestBasePlugin:
    """Test base plugin functionality"""
    
    @pytest.mark.asyncio
    async def test_base_plugin_creation(self, plugin_manager):
        """Test creating a base plugin"""
        config = {"test_key": "test_value"}
        plugin = MockPlugin("test_plugin", config, plugin_manager)
        
        assert plugin.name == "test_plugin"
        assert plugin.config == config
        assert plugin.plugin_manager == plugin_manager
        assert plugin.is_running is False
        assert len(plugin._tasks) == 0
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self, plugin_manager):
        """Test plugin lifecycle methods"""
        plugin = MockPlugin("test_plugin", {}, plugin_manager)
        
        # Initialize
        result = await plugin.initialize()
        assert result is True
        assert plugin.initialized is True
        
        # Start
        result = await plugin.start()
        assert result is True
        assert plugin.started is True
        assert plugin.is_running is True
        
        # Health check
        result = await plugin.health_check()
        assert result is True
        
        # Stop
        result = await plugin.stop()
        assert result is True
        assert plugin.stopped is True
        assert plugin.is_running is False
        
        # Cleanup
        result = await plugin.cleanup()
        assert result is True
        assert plugin.cleaned_up is True
    
    @pytest.mark.asyncio
    async def test_plugin_failure_scenarios(self, plugin_manager):
        """Test plugin failure scenarios"""
        plugin = MockPlugin("test_plugin", {}, plugin_manager)
        
        # Test initialization failure
        plugin.should_fail_init = True
        result = await plugin.initialize()
        assert result is False
        
        # Test start failure
        plugin.should_fail_init = False
        plugin.should_fail_start = True
        await plugin.initialize()
        result = await plugin.start()
        assert result is False
        
        # Test health check failure
        plugin.should_fail_start = False
        plugin.should_fail_health = True
        await plugin.start()
        result = await plugin.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_plugin_task_management(self, plugin_manager):
        """Test plugin task management"""
        plugin = MockPlugin("test_plugin", {}, plugin_manager)
        
        # Create a test task
        async def test_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        task = plugin.create_task(test_task())
        assert len(plugin._tasks) == 1
        
        # Wait for task completion
        result = await task
        assert result == "completed"
        
        # Task should be automatically removed
        await asyncio.sleep(0.01)  # Give time for cleanup
        assert len(plugin._tasks) == 0
    
    @pytest.mark.asyncio
    async def test_plugin_stop_signal(self, plugin_manager):
        """Test plugin stop signaling"""
        plugin = MockPlugin("test_plugin", {}, plugin_manager)
        
        # Create a task that waits for stop signal
        async def waiting_task():
            await plugin.wait_for_stop()
            return "stopped"
        
        task = plugin.create_task(waiting_task())
        
        # Signal stop
        plugin.signal_stop()
        
        # Task should complete
        result = await task
        assert result == "stopped"


class TestPluginManager:
    """Test plugin manager functionality"""
    
    @pytest.mark.asyncio
    async def test_plugin_manager_creation(self, plugin_manager):
        """Test creating plugin manager"""
        assert len(plugin_manager.plugins) == 0
        assert len(plugin_manager.plugin_paths) > 0
        assert plugin_manager.health_monitor_task is None
    
    @pytest.mark.asyncio
    async def test_plugin_discovery(self, plugin_manager, temp_plugin_dir):
        """Test plugin discovery"""
        # Add temp directory to plugin paths
        plugin_manager.plugin_paths.append(temp_plugin_dir)
        
        # Create mock plugin directories
        (temp_plugin_dir / "plugin1").mkdir()
        (temp_plugin_dir / "plugin1" / "__init__.py").touch()
        
        (temp_plugin_dir / "plugin2").mkdir()
        (temp_plugin_dir / "plugin2" / "__init__.py").touch()
        
        # Create non-plugin directory (no __init__.py)
        (temp_plugin_dir / "not_a_plugin").mkdir()
        
        # Discover plugins
        discovered = await plugin_manager.discover_plugins()
        
        assert "plugin1" in discovered
        assert "plugin2" in discovered
        assert "not_a_plugin" not in discovered
    
    @pytest.mark.asyncio
    async def test_manual_plugin_loading(self, plugin_manager):
        """Test manually loading a plugin"""
        # Mock the import process
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                # Setup mocks
                mock_module = Mock()
                mock_import.return_value = mock_module
                mock_find.return_value = MockPlugin
                
                # Load plugin
                result = await plugin_manager.load_plugin("test_plugin", {"key": "value"})
                
                assert result is True
                assert "test_plugin" in plugin_manager.plugins
                
                plugin_info = plugin_manager.plugins["test_plugin"]
                assert plugin_info.status == PluginStatus.LOADED
                assert plugin_info.instance is not None
                assert plugin_info.instance.initialized is True
                assert plugin_info.config == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_plugin_loading_failure(self, plugin_manager):
        """Test plugin loading failure scenarios"""
        # Test import failure
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            mock_import.return_value = None
            
            result = await plugin_manager.load_plugin("bad_plugin")
            
            assert result is False
            assert "bad_plugin" in plugin_manager.plugins
            assert plugin_manager.plugins["bad_plugin"].status == PluginStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_plugin_start_stop(self, plugin_manager):
        """Test starting and stopping plugins"""
        # Load a plugin first
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                mock_find.return_value = MockPlugin
                
                await plugin_manager.load_plugin("test_plugin")
        
        # Start plugin
        result = await plugin_manager.start_plugin("test_plugin")
        assert result is True
        
        plugin_info = plugin_manager.plugins["test_plugin"]
        assert plugin_info.status == PluginStatus.RUNNING
        assert plugin_info.instance.started is True
        assert plugin_info.start_time is not None
        
        # Stop plugin
        result = await plugin_manager.stop_plugin("test_plugin")
        assert result is True
        
        assert plugin_info.status == PluginStatus.STOPPED
        assert plugin_info.instance.stopped is True
        assert plugin_info.start_time is None
    
    @pytest.mark.asyncio
    async def test_plugin_restart(self, plugin_manager):
        """Test restarting a plugin"""
        # Load and start a plugin
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                mock_find.return_value = MockPlugin
                
                await plugin_manager.load_plugin("test_plugin")
                await plugin_manager.start_plugin("test_plugin")
        
        plugin_info = plugin_manager.plugins["test_plugin"]
        old_restart_count = plugin_info.health.restart_count
        
        # Restart plugin
        result = await plugin_manager.restart_plugin("test_plugin")
        assert result is True
        
        assert plugin_info.status == PluginStatus.RUNNING
        assert plugin_info.health.restart_count == old_restart_count + 1
    
    @pytest.mark.asyncio
    async def test_dependency_resolution(self, plugin_manager):
        """Test plugin dependency resolution"""
        # Load plugins with dependencies
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                
                # Load dependency first
                mock_find.return_value = MockPlugin
                await plugin_manager.load_plugin("dependency1")
                await plugin_manager.start_plugin("dependency1")
                
                # Load plugin with dependencies
                mock_find.return_value = MockPluginWithDependencies
                await plugin_manager.load_plugin("dependent_plugin")
        
        # Check dependency resolution
        result = await plugin_manager._check_dependencies("dependent_plugin")
        assert result is True
        
        # Start dependent plugin
        result = await plugin_manager.start_plugin("dependent_plugin")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_startup_order_calculation(self, plugin_manager):
        """Test plugin startup order calculation"""
        # Create plugins with different priorities and dependencies
        plugins_data = [
            ("critical_plugin", MockPlugin, PluginPriority.CRITICAL, []),
            ("high_plugin", MockPlugin, PluginPriority.HIGH, []),
            ("normal_plugin", MockPlugin, PluginPriority.NORMAL, []),
            ("low_plugin", MockPlugin, PluginPriority.LOW, [])
        ]
        
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                
                for name, plugin_class, priority, deps in plugins_data:
                    # Create custom plugin class with specific priority
                    class CustomPlugin(plugin_class):
                        def get_metadata(self):
                            return PluginMetadata(
                                name=name,
                                version="1.0.0",
                                description="Test plugin",
                                author="Test",
                                priority=priority,
                                dependencies=[PluginDependency(d) for d in deps]
                            )
                    
                    mock_find.return_value = CustomPlugin
                    await plugin_manager.load_plugin(name)
        
        # Calculate startup order
        startup_order = plugin_manager._calculate_startup_order()
        
        # Critical should come first, low should come last
        critical_index = startup_order.index("critical_plugin")
        low_index = startup_order.index("low_plugin")
        
        assert critical_index < low_index
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, plugin_manager):
        """Test plugin health monitoring"""
        # Load and start a plugin
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                mock_find.return_value = MockPlugin
                
                await plugin_manager.load_plugin("test_plugin")
                await plugin_manager.start_plugin("test_plugin")
        
        plugin_info = plugin_manager.plugins["test_plugin"]
        
        # Manually trigger health check
        await plugin_manager._check_plugin_health()
        
        # Plugin should still be healthy
        assert plugin_info.health.is_healthy() is True
        
        # Make plugin unhealthy
        plugin_info.instance.should_fail_health = True
        plugin_info.health.failure_count = 3  # Exceed threshold
        
        # Mock restart to avoid actual restart during test
        with patch.object(plugin_manager, 'restart_plugin') as mock_restart:
            mock_restart.return_value = True
            
            await plugin_manager._check_plugin_health()
            
            # Should have attempted restart
            mock_restart.assert_called_once_with("test_plugin")
    
    @pytest.mark.asyncio
    async def test_plugin_unloading(self, plugin_manager):
        """Test unloading plugins"""
        # Load and start a plugin
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                mock_find.return_value = MockPlugin
                
                await plugin_manager.load_plugin("test_plugin")
                await plugin_manager.start_plugin("test_plugin")
        
        assert "test_plugin" in plugin_manager.plugins
        
        # Unload plugin
        result = await plugin_manager.unload_plugin("test_plugin")
        assert result is True
        assert "test_plugin" not in plugin_manager.plugins
    
    @pytest.mark.asyncio
    async def test_start_stop_all_plugins(self, plugin_manager):
        """Test starting and stopping all plugins"""
        # Load multiple plugins
        with patch.object(plugin_manager, '_import_plugin_module') as mock_import:
            with patch.object(plugin_manager, '_find_plugin_class') as mock_find:
                mock_import.return_value = Mock()
                mock_find.return_value = MockPlugin
                
                await plugin_manager.load_plugin("plugin1")
                await plugin_manager.load_plugin("plugin2")
        
        # Start all plugins
        result = await plugin_manager.start_all_plugins()
        assert result is True
        
        running_plugins = plugin_manager.get_running_plugins()
        assert len(running_plugins) == 2
        assert "plugin1" in running_plugins
        assert "plugin2" in running_plugins
        
        # Stop all plugins
        result = await plugin_manager.stop_all_plugins()
        assert result is True
        
        running_plugins = plugin_manager.get_running_plugins()
        assert len(running_plugins) == 0
    
    def test_plugin_info_retrieval(self, plugin_manager):
        """Test retrieving plugin information"""
        # Initially no plugins
        all_plugins = plugin_manager.get_all_plugins()
        assert len(all_plugins) == 0
        
        # Get specific plugin (doesn't exist)
        plugin_info = plugin_manager.get_plugin_info("nonexistent")
        assert plugin_info is None
        
        # Get running plugins (none)
        running = plugin_manager.get_running_plugins()
        assert len(running) == 0
    
    def test_plugin_stats(self, plugin_manager):
        """Test plugin statistics"""
        stats = plugin_manager.get_plugin_stats()
        
        assert "total_plugins" in stats
        assert "running_plugins" in stats
        assert "failed_plugins" in stats
        assert "plugins" in stats
        
        assert stats["total_plugins"] == 0
        assert stats["running_plugins"] == 0
        assert stats["failed_plugins"] == 0


if __name__ == "__main__":
    pytest.main([__file__])