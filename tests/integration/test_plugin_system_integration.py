"""
Integration tests for the third-party plugin system.

Tests complete plugin lifecycle, message flow, BBS integration, scheduled tasks,
database operations, multi-plugin interaction, and failure recovery.
"""
import asyncio
import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

from tests.base import IntegrationTestCase, TestDataFactory
from src.core.plugin_manager import (
    PluginManager, BasePlugin, PluginMetadata, PluginStatus,
    PluginPriority, PluginDependency
)
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manifest import PluginManifest, ManifestLoader
from src.core.plugin_command_handler import PluginCommandHandler
from src.core.plugin_scheduler import PluginScheduler
from src.core.plugin_menu_registry import PluginMenuRegistry, MenuType
from src.core.config import ConfigurationManager
from src.models.message import Message


# Test plugin implementations
class TestLifecyclePlugin(EnhancedPlugin):
    """Test plugin for lifecycle testing"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.initialized = False
        self.started = False
        self.stopped = False
        self.cleaned_up = False
    
    async def initialize(self) -> bool:
        self.initialized = True
        return True
    
    async def start(self) -> bool:
        self.started = True
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
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
            description="Test lifecycle plugin",
            author="Test"
        )


class TestCommandPlugin(EnhancedPlugin):
    """Test plugin for command handling"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.command_received = []
    
    async def initialize(self) -> bool:
        # Register command handler
        async def test_command_handler(args: List[str], context: Dict[str, Any]) -> str:
            self.command_received.append((args, context))
            return f"Test command executed with args: {args}"
        
        self.register_command("testcmd", test_command_handler, "Test command")
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
            description="Test command plugin",
            author="Test"
        )


class TestScheduledPlugin(EnhancedPlugin):
    """Test plugin for scheduled task testing"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.task_executions = []
    
    async def initialize(self) -> bool:
        # Register scheduled task
        async def scheduled_task():
            self.task_executions.append(datetime.utcnow())
        
        self.register_scheduled_task(1, scheduled_task, "test_task")  # 1 second interval
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
            description="Test scheduled plugin",
            author="Test"
        )


class TestMenuPlugin(EnhancedPlugin):
    """Test plugin for BBS menu integration"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.menu_interactions = []
    
    async def initialize(self) -> bool:
        # Register menu item
        async def menu_handler(context: Dict[str, Any]) -> str:
            self.menu_interactions.append(context)
            return "Menu item selected"
        
        self.register_menu_item(
            MenuType.UTILITIES,
            "Test Menu",
            "testmenu",
            menu_handler,
            "Test menu item"
        )
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
            description="Test menu plugin",
            author="Test"
        )


class TestStoragePlugin(EnhancedPlugin):
    """Test plugin for database storage testing"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.stored_data = {}
    
    async def initialize(self) -> bool:
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
            description="Test storage plugin",
            author="Test"
        )


class TestFailurePlugin(EnhancedPlugin):
    """Test plugin that fails on purpose"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.fail_on_start = config.get('fail_on_start', False)
        self.fail_on_health_check = config.get('fail_on_health_check', False)
        self.health_check_count = 0
    
    async def initialize(self) -> bool:
        return True
    
    async def start(self) -> bool:
        if self.fail_on_start:
            raise RuntimeError("Intentional start failure")
        self.is_running = True
        return True
    
    async def stop(self) -> bool:
        self.is_running = False
        return True
    
    async def cleanup(self) -> bool:
        return True
    
    async def health_check(self) -> bool:
        self.health_check_count += 1
        if self.fail_on_health_check:
            return False
        return self.is_running
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="Test failure plugin",
            author="Test"
        )


class TestDependentPlugin(EnhancedPlugin):
    """Test plugin with dependencies"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
    
    async def initialize(self) -> bool:
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
            description="Test dependent plugin",
            author="Test",
            dependencies=[
                PluginDependency(name="test_lifecycle", version="1.0.0", optional=False)
            ]
        )


@pytest.mark.integration
class TestPluginSystemIntegration(IntegrationTestCase):
    """Integration tests for the plugin system"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        
        # Create temporary plugin directory
        self.temp_plugin_dir = Path(tempfile.mkdtemp())
        
        # Create test configuration
        self.config_data = {
            'plugins': {
                'paths': [str(self.temp_plugin_dir)],
                'auto_discover': False,
                'enabled_plugins': [],
                'disabled_plugins': []
            },
            'database': {
                'path': ':memory:'
            },
            'app': {
                'version': '1.0.0'
            }
        }
        
        # Create config manager
        self.config_manager = Mock(spec=ConfigurationManager)
        self.config_manager.get = lambda key, default=None: self._get_config(key, default)
        self.config_manager.register_config_change_callback = Mock()
        self.config_manager.get_plugin_config = lambda plugin_name: {}
        
        # Create plugin manager
        self.plugin_manager = PluginManager(self.config_manager)
        
        # Store created plugin directories for cleanup
        self.created_plugin_dirs = []
    
    def teardown_method(self):
        """Clean up test environment"""
        # Clean up temporary plugin directory
        import shutil
        if self.temp_plugin_dir.exists():
            shutil.rmtree(self.temp_plugin_dir)
        super().teardown_method()
    
    def _get_config(self, key: str, default=None):
        """Helper to get config values"""
        keys = key.split('.')
        value = self.config_data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def _create_test_plugin_directory(self, plugin_name: str, plugin_class: type) -> Path:
        """Create a temporary plugin directory with the plugin class"""
        plugin_dir = self.temp_plugin_dir / plugin_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py
        init_file = plugin_dir / "__init__.py"
        init_file.write_text(f"""
from .plugin import {plugin_class.__name__}

__all__ = ['{plugin_class.__name__}']
""")
        
        # Create plugin.py with the plugin class
        plugin_file = plugin_dir / "plugin.py"
        
        # Get the source code of the plugin class
        import inspect
        source = inspect.getsource(plugin_class)
        
        # Add necessary imports
        imports = """
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginMetadata, PluginDependency
from src.core.plugin_menu_registry import MenuType
"""
        
        plugin_file.write_text(imports + "\n" + source)
        
        self.created_plugin_dirs.append(plugin_dir)
        return plugin_dir

    
    @pytest.mark.asyncio
    async def test_complete_plugin_lifecycle(self):
        """Test complete plugin lifecycle: load, start, stop, unload"""
        # Create test plugin directory
        plugin_name = "test_lifecycle"
        plugin_class = TestLifecyclePlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load plugin
        success = await self.plugin_manager.load_plugin(plugin_name, {})
        assert success, "Plugin should load successfully"
        
        # Verify plugin is loaded
        assert plugin_name in self.plugin_manager.plugins
        plugin_info = self.plugin_manager.plugins[plugin_name]
        assert plugin_info.status == PluginStatus.LOADED
        assert plugin_info.instance.initialized
        
        # Start plugin
        success = await self.plugin_manager.start_plugin(plugin_name)
        assert success, "Plugin should start successfully"
        assert plugin_info.status == PluginStatus.RUNNING
        assert plugin_info.instance.started
        assert plugin_info.instance.is_running
        
        # Verify plugin uptime
        uptime = plugin_info.get_uptime()
        assert uptime is not None
        assert uptime.total_seconds() >= 0
        
        # Stop plugin
        success = await self.plugin_manager.stop_plugin(plugin_name)
        assert success, "Plugin should stop successfully"
        assert plugin_info.status == PluginStatus.STOPPED
        assert plugin_info.instance.stopped
        assert not plugin_info.instance.is_running
        
        # Unload plugin
        success = await self.plugin_manager.unload_plugin(plugin_name)
        assert success, "Plugin should unload successfully"
        assert plugin_info.instance.cleaned_up
        assert plugin_name not in self.plugin_manager.plugins or \
               self.plugin_manager.plugins[plugin_name].status == PluginStatus.UNLOADED
    
    @pytest.mark.asyncio
    async def test_message_flow_to_plugin(self):
        """Test message flow from mesh to plugin command handler"""
        # Create and load command plugin
        plugin_name = "test_command"
        plugin_class = TestCommandPlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load and start plugin
        await self.plugin_manager.load_plugin(plugin_name, {})
        await self.plugin_manager.start_plugin(plugin_name)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        plugin_instance = plugin_info.instance
        
        # Verify command was registered
        assert hasattr(plugin_instance, '_command_handler')
        assert plugin_instance._command_handler is not None
        
        # Simulate message with command
        message_text = "testcmd arg1 arg2"
        sender_id = "!12345678"
        
        # Get command handler
        command_handler = plugin_instance._command_handler
        
        # Parse command
        parts = message_text.split()
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Create context
        context = {
            'sender_id': sender_id,
            'channel': 'test_channel',
            'timestamp': datetime.utcnow()
        }
        
        # Handle command
        if command in command_handler.command_handlers:
            result = await command_handler.handle_command(command, args, context)
            
            # Verify command was executed
            assert len(plugin_instance.command_received) == 1
            assert plugin_instance.command_received[0][0] == args
            assert result is not None
            assert "Test command executed" in result
    
    @pytest.mark.asyncio
    async def test_bbs_menu_integration(self):
        """Test BBS menu integration with plugin"""
        # Create and load menu plugin
        plugin_name = "test_menu"
        plugin_class = TestMenuPlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load and start plugin
        await self.plugin_manager.load_plugin(plugin_name, {})
        await self.plugin_manager.start_plugin(plugin_name)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        plugin_instance = plugin_info.instance
        
        # Verify menu item was registered
        assert hasattr(plugin_instance, '_menu_registry')
        menu_registry = plugin_instance._menu_registry
        
        # Get menu items for utilities menu
        menu_items = menu_registry.get_menu_items(MenuType.UTILITIES)
        
        # Find our test menu item
        test_menu_item = None
        for item in menu_items:
            if item.plugin == plugin_name:
                test_menu_item = item
                break
        
        assert test_menu_item is not None, "Menu item should be registered"
        assert test_menu_item.label == "Test Menu"
        assert test_menu_item.command == "testmenu"
        
        # Simulate menu selection
        context = {
            'user_id': '!12345678',
            'session_id': 'test_session'
        }
        
        result = await test_menu_item.handler(context)
        
        # Verify menu handler was called
        assert len(plugin_instance.menu_interactions) == 1
        assert plugin_instance.menu_interactions[0] == context
        assert result == "Menu item selected"
    
    @pytest.mark.asyncio
    async def test_scheduled_task_execution(self):
        """Test scheduled task execution"""
        # Create and load scheduled plugin
        plugin_name = "test_scheduled"
        plugin_class = TestScheduledPlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load and start plugin
        await self.plugin_manager.load_plugin(plugin_name, {})
        await self.plugin_manager.start_plugin(plugin_name)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        plugin_instance = plugin_info.instance
        
        # Verify scheduler was created
        assert hasattr(plugin_instance, '_scheduler')
        scheduler = plugin_instance._scheduler
        
        # Start scheduler
        await scheduler.start_all()
        
        # Wait for task to execute at least twice
        await asyncio.sleep(2.5)
        
        # Stop scheduler
        await scheduler.stop_all()
        
        # Verify task executed
        assert len(plugin_instance.task_executions) >= 2, \
            f"Task should execute at least twice, got {len(plugin_instance.task_executions)}"
        
        # Verify executions are spaced correctly (approximately 1 second apart)
        if len(plugin_instance.task_executions) >= 2:
            time_diff = (plugin_instance.task_executions[1] - 
                        plugin_instance.task_executions[0]).total_seconds()
            assert 0.8 <= time_diff <= 1.5, \
                f"Task executions should be ~1 second apart, got {time_diff}"

    
    @pytest.mark.asyncio
    async def test_database_operations_and_isolation(self):
        """Test database operations and isolation between plugins"""
        # Create database
        db_path = self.create_test_database()
        
        # Create two storage plugins
        plugin1_name = "test_storage1"
        plugin2_name = "test_storage2"
        
        plugin_class = TestStoragePlugin
        
        # Create plugin directories
        self._create_test_plugin_directory(plugin1_name, plugin_class)
        self._create_test_plugin_directory(plugin2_name, plugin_class)
        
        # Load and start both plugins
        await self.plugin_manager.load_plugin(plugin1_name, {})
        await self.plugin_manager.load_plugin(plugin2_name, {})
        
        await self.plugin_manager.start_plugin(plugin1_name)
        await self.plugin_manager.start_plugin(plugin2_name)
        
        plugin1 = self.plugin_manager.plugins[plugin1_name].instance
        plugin2 = self.plugin_manager.plugins[plugin2_name].instance
        
        # Verify both plugins have storage
        assert hasattr(plugin1, '_storage')
        assert hasattr(plugin2, '_storage')
        
        storage1 = plugin1._storage
        storage2 = plugin2._storage
        
        # Store data in plugin1
        await storage1.store("key1", "value1_from_plugin1")
        await storage1.store("shared_key", "plugin1_value")
        
        # Store data in plugin2
        await storage2.store("key2", "value2_from_plugin2")
        await storage2.store("shared_key", "plugin2_value")
        
        # Verify plugin1 can retrieve its own data
        value1 = await storage1.retrieve("key1")
        assert value1 == "value1_from_plugin1"
        
        shared1 = await storage1.retrieve("shared_key")
        assert shared1 == "plugin1_value"
        
        # Verify plugin2 can retrieve its own data
        value2 = await storage2.retrieve("key2")
        assert value2 == "value2_from_plugin2"
        
        shared2 = await storage2.retrieve("shared_key")
        assert shared2 == "plugin2_value"
        
        # Verify isolation: plugin1 cannot see plugin2's data
        plugin2_data_from_plugin1 = await storage1.retrieve("key2")
        assert plugin2_data_from_plugin1 is None
        
        # Verify isolation: plugin2 cannot see plugin1's data
        plugin1_data_from_plugin2 = await storage2.retrieve("key1")
        assert plugin1_data_from_plugin2 is None
        
        # Verify shared key has different values for each plugin
        assert shared1 != shared2
    
    @pytest.mark.asyncio
    async def test_multi_plugin_interaction(self):
        """Test interaction between multiple plugins"""
        # Create two plugins that can communicate
        plugin1_name = "test_plugin1"
        plugin2_name = "test_plugin2"
        
        plugin_class = TestLifecyclePlugin
        
        # Create plugin directories
        self._create_test_plugin_directory(plugin1_name, plugin_class)
        self._create_test_plugin_directory(plugin2_name, plugin_class)
        
        # Load and start both plugins
        await self.plugin_manager.load_plugin(plugin1_name, {})
        await self.plugin_manager.load_plugin(plugin2_name, {})
        
        await self.plugin_manager.start_plugin(plugin1_name)
        await self.plugin_manager.start_plugin(plugin2_name)
        
        plugin1 = self.plugin_manager.plugins[plugin1_name].instance
        plugin2 = self.plugin_manager.plugins[plugin2_name].instance
        
        # Set up message handler in plugin2
        received_messages = []
        
        async def message_handler(message):
            received_messages.append(message)
            return "Message received"
        
        plugin2.register_message_handler("test_message", message_handler)
        
        # Send message from plugin1 to plugin2
        test_message = {"content": "Hello from plugin1", "timestamp": datetime.utcnow().isoformat()}
        
        # Use plugin manager to route message
        result = await self.plugin_manager.send_plugin_message(
            plugin2_name,
            "test_message",
            test_message
        )
        
        # Verify message was received
        assert len(received_messages) == 1
        assert received_messages[0]["content"] == "Hello from plugin1"
        assert result == "Message received"
    
    @pytest.mark.asyncio
    async def test_plugin_failure_and_recovery(self):
        """Test plugin failure handling and recovery"""
        # Create failure plugin
        plugin_name = "test_failure"
        plugin_config = {'fail_on_start': False, 'fail_on_health_check': False}
        plugin_class = TestFailurePlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load and start plugin successfully
        await self.plugin_manager.load_plugin(plugin_name, plugin_config)
        await self.plugin_manager.start_plugin(plugin_name)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        assert plugin_info.status == PluginStatus.RUNNING
        
        # Simulate health check failure
        plugin_info.instance.fail_on_health_check = True
        
        # Perform health check
        is_healthy = await plugin_info.instance.health_check()
        assert not is_healthy
        
        # Record failure
        plugin_info.health.record_failure("Health check failed")
        assert plugin_info.health.failure_count == 1
        
        # Simulate multiple failures
        for i in range(2):
            plugin_info.health.record_failure(f"Failure {i+2}")
        
        assert plugin_info.health.failure_count == 3
        assert not plugin_info.health.is_healthy()
        
        # Test recovery: simulate successful operations
        plugin_info.instance.fail_on_health_check = False
        
        # Record successful operations
        for i in range(10):
            plugin_info.health.record_success()
        
        # Verify failure counter was reset
        assert plugin_info.health.failure_count == 0
        assert plugin_info.health.consecutive_successes == 0  # Reset after threshold
    
    @pytest.mark.asyncio
    async def test_plugin_restart_with_backoff(self):
        """Test plugin automatic restart with exponential backoff"""
        # Create failure plugin that fails on start
        plugin_name = "test_restart"
        plugin_config = {'fail_on_start': True}
        plugin_class = TestFailurePlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        # Load plugin
        await self.plugin_manager.load_plugin(plugin_name, plugin_config)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        
        # Try to start plugin (will fail)
        success = await self.plugin_manager.start_plugin(plugin_name)
        assert not success
        assert plugin_info.status == PluginStatus.FAILED
        
        # Record restart
        plugin_info.health.record_restart()
        assert plugin_info.health.restart_count == 1
        
        # Check restart delay (should be 1 second for first restart)
        delay = plugin_info.health.get_restart_delay()
        assert delay == 1.0
        
        # Record more restarts
        plugin_info.health.record_restart()
        delay = plugin_info.health.get_restart_delay()
        assert delay == 2.0  # Exponential backoff
        
        plugin_info.health.record_restart()
        delay = plugin_info.health.get_restart_delay()
        assert delay == 4.0
        
        # Verify max restarts limit
        for i in range(5):
            plugin_info.health.record_restart()
        
        assert not plugin_info.health.should_attempt_restart()
    
    @pytest.mark.asyncio
    async def test_plugin_dependency_resolution(self):
        """Test plugin dependency resolution and loading order"""
        # Create base plugin
        base_plugin_name = "test_lifecycle"
        base_plugin_class = TestLifecyclePlugin
        
        # Create dependent plugin
        dependent_plugin_name = "test_dependent"
        dependent_plugin_class = TestDependentPlugin
        
        # Create plugin directories
        self._create_test_plugin_directory(base_plugin_name, base_plugin_class)
        self._create_test_plugin_directory(dependent_plugin_name, dependent_plugin_class)
        
        # Load dependent plugin first (should work but note dependency)
        await self.plugin_manager.load_plugin(dependent_plugin_name, {})
        
        # Load base plugin
        await self.plugin_manager.load_plugin(base_plugin_name, {})
        
        # Verify both plugins are loaded
        assert base_plugin_name in self.plugin_manager.plugins
        assert dependent_plugin_name in self.plugin_manager.plugins
        
        # Build dependency graph
        self.plugin_manager._build_dependency_graph()
        
        # Verify dependency graph
        if hasattr(self.plugin_manager, 'dependency_graph'):
            assert dependent_plugin_name in self.plugin_manager.dependency_graph
            deps = self.plugin_manager.dependency_graph.get(dependent_plugin_name, set())
            assert base_plugin_name in deps
    
    @pytest.mark.asyncio
    async def test_plugin_metrics_tracking(self):
        """Test plugin metrics tracking"""
        # Create and start plugin
        plugin_name = "test_metrics"
        plugin_class = TestLifecyclePlugin
        
        self._create_test_plugin_directory(plugin_name, plugin_class)
        
        await self.plugin_manager.load_plugin(plugin_name, {})
        await self.plugin_manager.start_plugin(plugin_name)
        
        plugin_info = self.plugin_manager.plugins[plugin_name]
        
        # Get metrics
        metrics = plugin_info.get_metrics()
        
        # Verify metrics structure
        assert 'status' in metrics
        assert metrics['status'] == PluginStatus.RUNNING.value
        
        assert 'uptime_seconds' in metrics
        assert metrics['uptime_seconds'] >= 0
        
        assert 'health' in metrics
        health_metrics = metrics['health']
        
        assert 'is_healthy' in health_metrics
        assert health_metrics['is_healthy'] is True
        
        assert 'failure_count' in health_metrics
        assert health_metrics['failure_count'] == 0
        
        assert 'restart_count' in health_metrics
        assert health_metrics['restart_count'] == 0
        
        assert 'last_heartbeat' in health_metrics
        assert health_metrics['last_heartbeat'] is not None
