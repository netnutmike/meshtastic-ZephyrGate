"""
Property-Based Tests for Dynamic Plugin Lifecycle Management

Tests universal properties of dynamic plugin enable/disable and state persistence using Hypothesis.
"""

import pytest
import asyncio
import tempfile
import yaml
import json
from hypothesis import given, settings, strategies as st
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.core.plugin_manager import (
    PluginManager, 
    BasePlugin, 
    PluginMetadata, 
    PluginPriority,
    PluginStatus
)
from src.core.config import ConfigurationManager


# Strategies for generating test data

@st.composite
def valid_semver(draw):
    """Generate valid semantic version strings"""
    major = draw(st.integers(min_value=0, max_value=99))
    minor = draw(st.integers(min_value=0, max_value=99))
    patch = draw(st.integers(min_value=0, max_value=99))
    return f"{major}.{minor}.{patch}"


@st.composite
def valid_plugin_name(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() and not x.startswith('_') and x.isidentifier()))


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


def create_test_plugin_directory(base_path: Path, plugin_name: str):
    """Create a minimal test plugin directory"""
    plugin_dir = base_path / plugin_name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py with a simple plugin class
    init_content = f'''
from src.core.plugin_manager import BasePlugin, PluginMetadata, PluginPriority

class TestPlugin(BasePlugin):
    """Test plugin for lifecycle testing"""
    
    def __init__(self, name, config, plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.initialized = False
        self.started = False
        self.stopped = False
        self.cleaned_up = False
    
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

class TestDynamicPluginLifecycle:
    """
    Feature: third-party-plugin-system, Property 13: Dynamic plugin lifecycle
    
    For any valid plugin, enabling it should load and start the plugin without
    system restart, and disabling it should stop and unload the plugin gracefully
    with all resources cleaned up.
    
    Validates: Requirements 7.4, 7.5
    """
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_enable_plugin_loads_and_starts_without_restart(self, plugin_name):
        """
        Property: Enabling a plugin should load and start it without system restart.
        
        For any valid plugin, calling enable_plugin() should:
        1. Load the plugin
        2. Start the plugin
        3. Result in plugin status being RUNNING
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin (should load and start)
            result = asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Assert - plugin should be enabled successfully
            assert result is True, \
                f"enable_plugin() should return True for valid plugin {plugin_name}"
            
            # Assert - plugin should be in plugins dict
            assert plugin_name in plugin_manager.plugins, \
                f"Plugin {plugin_name} should be loaded after enable_plugin()"
            
            # Assert - plugin should be running
            plugin_info = plugin_manager.plugins[plugin_name]
            assert plugin_info.status == PluginStatus.RUNNING, \
                f"Plugin {plugin_name} should be RUNNING after enable_plugin(), but is {plugin_info.status}"
            
            # Assert - plugin instance should be initialized and started
            assert plugin_info.instance is not None, \
                f"Plugin {plugin_name} should have an instance"
            assert plugin_info.instance.initialized is True, \
                f"Plugin {plugin_name} should be initialized"
            assert plugin_info.instance.started is True, \
                f"Plugin {plugin_name} should be started"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_disable_plugin_stops_and_unloads_gracefully(self, plugin_name):
        """
        Property: Disabling a plugin should stop and unload it gracefully.
        
        For any running plugin, calling disable_plugin() should:
        1. Stop the plugin
        2. Clean up resources
        3. Unload the plugin
        4. Result in plugin being removed from plugins dict
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin first
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Get reference to plugin instance before disabling
            plugin_instance = plugin_manager.plugins[plugin_name].instance
            
            # Disable the plugin
            result = asyncio.run(plugin_manager.disable_plugin(plugin_name))
            
            # Assert - disable should succeed
            assert result is True, \
                f"disable_plugin() should return True for plugin {plugin_name}"
            
            # Assert - plugin should be removed from plugins dict
            assert plugin_name not in plugin_manager.plugins, \
                f"Plugin {plugin_name} should be unloaded after disable_plugin()"
            
            # Assert - plugin instance should have been stopped and cleaned up
            assert plugin_instance.stopped is True, \
                f"Plugin {plugin_name} should be stopped"
            assert plugin_instance.cleaned_up is True, \
                f"Plugin {plugin_name} should be cleaned up"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_plugin_state_persists_across_manager_instances(self, plugin_name):
        """
        Property: Plugin enabled/disabled state should persist across restarts.
        
        For any plugin, if it is enabled in one plugin manager instance,
        a new plugin manager instance should remember that state.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            state_file = Path(tmpdir) / "plugin_state.json"
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # First plugin manager instance - enable plugin
            config_manager1 = create_mock_config_manager([str(plugin_path)])
            plugin_manager1 = PluginManager(config_manager1)
            plugin_manager1.plugin_paths = [plugin_path]
            plugin_manager1._plugin_state_file = state_file
            
            # Enable the plugin
            asyncio.run(plugin_manager1.enable_plugin(plugin_name))
            
            # Assert - state file should exist
            assert state_file.exists(), \
                f"Plugin state file should be created after enabling {plugin_name}"
            
            # Assert - state file should contain enabled plugin
            with open(state_file, 'r') as f:
                state = json.load(f)
            assert plugin_name in state['enabled'], \
                f"Plugin {plugin_name} should be in enabled list in state file"
            
            # Create second plugin manager instance (simulating restart)
            config_manager2 = create_mock_config_manager([str(plugin_path)])
            plugin_manager2 = PluginManager(config_manager2)
            plugin_manager2.plugin_paths = [plugin_path]
            plugin_manager2._plugin_state_file = state_file
            
            # Load state (happens in __init__)
            plugin_manager2._load_plugin_state()
            
            # Assert - second instance should remember enabled state
            assert plugin_name in plugin_manager2._enabled_plugins, \
                f"Plugin {plugin_name} should be in enabled set after loading state"
            
            # Assert - should_auto_start_plugin should return True
            assert plugin_manager2.should_auto_start_plugin(plugin_name) is True, \
                f"Plugin {plugin_name} should auto-start based on persisted state"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_disabled_plugin_state_persists_across_manager_instances(self, plugin_name):
        """
        Property: Disabled plugin state should persist across restarts.
        
        For any plugin, if it is disabled in one plugin manager instance,
        a new plugin manager instance should remember that state and not auto-start it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            state_file = Path(tmpdir) / "plugin_state.json"
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # First plugin manager instance
            config_manager1 = create_mock_config_manager([str(plugin_path)])
            plugin_manager1 = PluginManager(config_manager1)
            plugin_manager1.plugin_paths = [plugin_path]
            plugin_manager1._plugin_state_file = state_file
            
            # Enable then disable the plugin
            asyncio.run(plugin_manager1.enable_plugin(plugin_name))
            asyncio.run(plugin_manager1.disable_plugin(plugin_name))
            
            # Assert - state file should contain disabled plugin
            with open(state_file, 'r') as f:
                state = json.load(f)
            assert plugin_name in state['disabled'], \
                f"Plugin {plugin_name} should be in disabled list in state file"
            
            # Create second plugin manager instance (simulating restart)
            config_manager2 = create_mock_config_manager([str(plugin_path)])
            plugin_manager2 = PluginManager(config_manager2)
            plugin_manager2.plugin_paths = [plugin_path]
            plugin_manager2._plugin_state_file = state_file
            
            # Load state
            plugin_manager2._load_plugin_state()
            
            # Assert - second instance should remember disabled state
            assert plugin_name in plugin_manager2._disabled_plugins, \
                f"Plugin {plugin_name} should be in disabled set after loading state"
            
            # Assert - should_auto_start_plugin should return False
            assert plugin_manager2.should_auto_start_plugin(plugin_name) is False, \
                f"Plugin {plugin_name} should not auto-start based on persisted disabled state"
    
    @settings(max_examples=100, deadline=5000)
    @given(
        plugin_names=st.lists(
            valid_plugin_name(),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    def test_multiple_plugins_state_persists_independently(self, plugin_names):
        """
        Property: Multiple plugins' states should persist independently.
        
        For any set of plugins, each plugin's enabled/disabled state should
        persist independently without affecting other plugins.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            state_file = Path(tmpdir) / "plugin_state.json"
            
            # Create test plugins
            for plugin_name in plugin_names:
                create_test_plugin_directory(plugin_path, plugin_name)
            
            # First plugin manager instance
            config_manager1 = create_mock_config_manager([str(plugin_path)])
            plugin_manager1 = PluginManager(config_manager1)
            plugin_manager1.plugin_paths = [plugin_path]
            plugin_manager1._plugin_state_file = state_file
            
            # Enable some plugins, disable others
            enabled_plugins = plugin_names[:len(plugin_names)//2]
            disabled_plugins = plugin_names[len(plugin_names)//2:]
            
            for plugin_name in enabled_plugins:
                asyncio.run(plugin_manager1.enable_plugin(plugin_name))
            
            for plugin_name in disabled_plugins:
                # Enable first, then disable to ensure it's in disabled state
                asyncio.run(plugin_manager1.enable_plugin(plugin_name))
                asyncio.run(plugin_manager1.disable_plugin(plugin_name))
            
            # Create second plugin manager instance
            config_manager2 = create_mock_config_manager([str(plugin_path)])
            plugin_manager2 = PluginManager(config_manager2)
            plugin_manager2.plugin_paths = [plugin_path]
            plugin_manager2._plugin_state_file = state_file
            
            # Load state
            plugin_manager2._load_plugin_state()
            
            # Assert - enabled plugins should be remembered
            for plugin_name in enabled_plugins:
                assert plugin_name in plugin_manager2._enabled_plugins, \
                    f"Enabled plugin {plugin_name} should be in enabled set"
                assert plugin_manager2.should_auto_start_plugin(plugin_name) is True, \
                    f"Enabled plugin {plugin_name} should auto-start"
            
            # Assert - disabled plugins should be remembered
            for plugin_name in disabled_plugins:
                assert plugin_name in plugin_manager2._disabled_plugins, \
                    f"Disabled plugin {plugin_name} should be in disabled set"
                assert plugin_manager2.should_auto_start_plugin(plugin_name) is False, \
                    f"Disabled plugin {plugin_name} should not auto-start"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_enable_already_running_plugin_is_idempotent(self, plugin_name):
        """
        Property: Enabling an already running plugin should be idempotent.
        
        For any running plugin, calling enable_plugin() again should succeed
        without causing errors or restarting the plugin.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable the plugin
            result1 = asyncio.run(plugin_manager.enable_plugin(plugin_name))
            assert result1 is True
            
            # Get start time
            start_time1 = plugin_manager.plugins[plugin_name].start_time
            
            # Enable again (should be idempotent)
            result2 = asyncio.run(plugin_manager.enable_plugin(plugin_name))
            
            # Assert - second enable should succeed
            assert result2 is True, \
                f"Enabling already running plugin {plugin_name} should succeed"
            
            # Assert - plugin should still be running
            assert plugin_manager.plugins[plugin_name].status == PluginStatus.RUNNING, \
                f"Plugin {plugin_name} should still be RUNNING"
            
            # Assert - start time should not change (plugin not restarted)
            start_time2 = plugin_manager.plugins[plugin_name].start_time
            assert start_time1 == start_time2, \
                f"Plugin {plugin_name} should not be restarted when enabling already running plugin"
    
    @settings(max_examples=100, deadline=5000)
    @given(plugin_name=valid_plugin_name())
    def test_disable_already_disabled_plugin_is_idempotent(self, plugin_name):
        """
        Property: Disabling an already disabled plugin should be idempotent.
        
        For any disabled plugin, calling disable_plugin() again should succeed
        without causing errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create test plugin
            create_test_plugin_directory(plugin_path, plugin_name)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Enable then disable the plugin
            asyncio.run(plugin_manager.enable_plugin(plugin_name))
            result1 = asyncio.run(plugin_manager.disable_plugin(plugin_name))
            assert result1 is True
            
            # Disable again (should be idempotent)
            result2 = asyncio.run(plugin_manager.disable_plugin(plugin_name))
            
            # Assert - second disable should succeed
            assert result2 is True, \
                f"Disabling already disabled plugin {plugin_name} should succeed"
            
            # Assert - plugin should not be in plugins dict
            assert plugin_name not in plugin_manager.plugins, \
                f"Plugin {plugin_name} should remain unloaded"
