"""
Property-Based Tests for Plugin Discovery and Dependency Validation

Tests universal properties of plugin discovery and dependency validation using Hypothesis.
"""

import pytest
import asyncio
import tempfile
import yaml
from hypothesis import given, settings, strategies as st
from pathlib import Path
from unittest.mock import Mock

from src.core.plugin_manager import PluginManager
from src.core.config import ConfigurationManager
from src.core.plugin_manifest import PluginManifest, PluginDependency


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


@st.composite
def plugin_directory_structure(draw):
    """
    Generate a valid plugin directory structure.
    
    Returns a tuple of (plugin_name, has_manifest, manifest_data)
    """
    plugin_name = draw(valid_plugin_name())
    has_manifest = draw(st.booleans())
    
    manifest_data = None
    if has_manifest:
        manifest_data = {
            'name': plugin_name,
            'version': draw(valid_semver()),
            'description': draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
            'author': draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
        }
    
    return (plugin_name, has_manifest, manifest_data)


@st.composite
def plugin_with_dependencies(draw):
    """
    Generate a plugin with dependencies.
    
    Returns a tuple of (plugin_name, dependencies, manifest_data)
    """
    plugin_name = draw(valid_plugin_name())
    
    # Generate 0-3 dependencies
    num_deps = draw(st.integers(min_value=0, max_value=3))
    dependencies = []
    
    for _ in range(num_deps):
        dep_name = draw(valid_plugin_name().filter(lambda x: x != plugin_name))
        optional = draw(st.booleans())
        version = draw(st.one_of(
            st.none(),
            st.sampled_from(['>=', '==']).flatmap(
                lambda op: valid_semver().map(lambda v: f"{op}{v}")
            )
        ))
        dependencies.append({
            'name': dep_name,
            'version': version,
            'optional': optional
        })
    
    manifest_data = {
        'name': plugin_name,
        'version': draw(valid_semver()),
        'description': draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        'author': draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
        'dependencies': {
            'plugins': dependencies
        }
    }
    
    return (plugin_name, dependencies, manifest_data)


# Helper functions

def create_plugin_directory(base_path: Path, plugin_name: str, has_manifest: bool = False, manifest_data: dict = None):
    """Create a plugin directory with __init__.py and optionally manifest.yaml"""
    plugin_dir = base_path / plugin_name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py
    init_file = plugin_dir / "__init__.py"
    init_file.write_text("# Plugin module\n")
    
    # Create manifest.yaml if requested
    if has_manifest and manifest_data:
        manifest_file = plugin_dir / "manifest.yaml"
        with open(manifest_file, 'w') as f:
            yaml.dump(manifest_data, f)
    
    return plugin_dir


def create_mock_config_manager(plugin_paths: list = None, only_custom_paths: bool = False):
    """
    Create a mock configuration manager.
    
    Args:
        plugin_paths: List of plugin paths to use
        only_custom_paths: If True, only use the provided paths (don't include defaults)
    """
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


# Property Tests

class TestPluginDiscovery:
    """
    Feature: third-party-plugin-system, Property 11: Plugin discovery
    
    For any directory path containing a valid plugin (with __init__.py and manifest.yaml),
    the discovery process should identify and list that plugin.
    
    Validates: Requirements 7.1
    """
    
    @settings(max_examples=100)
    @given(plugin_structure=plugin_directory_structure())
    def test_discovers_valid_plugin_with_init_file(self, plugin_structure):
        """
        Property: Any directory with __init__.py should be discovered as a plugin.
        
        For any plugin directory containing __init__.py (with or without manifest),
        the discovery process should identify it.
        """
        plugin_name, has_manifest, manifest_data = plugin_structure
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create plugin directory
            create_plugin_directory(plugin_path, plugin_name, has_manifest, manifest_data)
            
            # Create plugin manager with this path
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            
            # Clear default plugin paths to only use our test directory
            plugin_manager.plugin_paths = [plugin_path]
            
            # Discover plugins
            discovered = asyncio.run(plugin_manager.discover_plugins())
            
            # Assert
            assert plugin_name in discovered, \
                f"Plugin {plugin_name} should be discovered (has_manifest={has_manifest})"
    
    @settings(max_examples=100)
    @given(
        plugin_names=st.lists(
            valid_plugin_name(),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    def test_discovers_all_valid_plugins_in_directory(self, plugin_names):
        """
        Property: All valid plugins in a directory should be discovered.
        
        For any set of valid plugin directories in a path, all should be discovered.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create multiple plugin directories
            for plugin_name in plugin_names:
                create_plugin_directory(plugin_path, plugin_name, has_manifest=False)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            
            # Clear default plugin paths to only use our test directory
            plugin_manager.plugin_paths = [plugin_path]
            
            # Discover plugins
            discovered = asyncio.run(plugin_manager.discover_plugins())
            
            # Assert - all plugins should be discovered
            for plugin_name in plugin_names:
                assert plugin_name in discovered, \
                    f"Plugin {plugin_name} should be discovered"
            
            assert len(discovered) == len(plugin_names), \
                f"Should discover exactly {len(plugin_names)} plugins, but found {len(discovered)}"
    
    @settings(max_examples=100)
    @given(plugin_name=valid_plugin_name())
    def test_does_not_discover_directory_without_init_file(self, plugin_name):
        """
        Property: Directories without __init__.py should not be discovered.
        
        For any directory without __init__.py, it should not be discovered as a plugin.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create directory without __init__.py
            plugin_dir = plugin_path / plugin_name
            plugin_dir.mkdir(parents=True, exist_ok=True)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            
            # Clear default plugin paths to only use our test directory
            plugin_manager.plugin_paths = [plugin_path]
            
            # Discover plugins
            discovered = asyncio.run(plugin_manager.discover_plugins())
            
            # Assert
            assert plugin_name not in discovered, \
                f"Plugin {plugin_name} should not be discovered without __init__.py"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        manifest_data=st.fixed_dictionaries({
            'name': valid_plugin_name(),
            'version': valid_semver(),
            'description': st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
            'author': st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
        })
    )
    def test_discovers_plugin_with_valid_manifest(self, plugin_name, manifest_data):
        """
        Property: Plugins with valid manifests should be discovered.
        
        For any plugin with a valid manifest.yaml, it should be discovered.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create plugin with valid manifest
            create_plugin_directory(plugin_path, plugin_name, has_manifest=True, manifest_data=manifest_data)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            
            # Clear default plugin paths to only use our test directory
            plugin_manager.plugin_paths = [plugin_path]
            
            # Discover plugins
            discovered = asyncio.run(plugin_manager.discover_plugins())
            
            # Assert
            assert plugin_name in discovered, \
                f"Plugin {plugin_name} with valid manifest should be discovered"
    
    @settings(max_examples=100)
    @given(plugin_name=valid_plugin_name())
    def test_skips_plugin_with_invalid_manifest(self, plugin_name):
        """
        Property: Plugins with invalid manifests should be skipped.
        
        For any plugin with an invalid manifest (missing required fields),
        it should not be discovered.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create plugin with invalid manifest (missing required fields)
            plugin_dir = plugin_path / plugin_name
            plugin_dir.mkdir(parents=True, exist_ok=True)
            
            # Create __init__.py
            (plugin_dir / "__init__.py").write_text("# Plugin\n")
            
            # Create invalid manifest (missing required fields)
            manifest_file = plugin_dir / "manifest.yaml"
            with open(manifest_file, 'w') as f:
                yaml.dump({'name': plugin_name}, f)  # Missing version, description, author
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            
            # Clear default plugin paths to only use our test directory
            plugin_manager.plugin_paths = [plugin_path]
            
            # Discover plugins
            discovered = asyncio.run(plugin_manager.discover_plugins())
            
            # Assert - plugin should be skipped due to invalid manifest
            assert plugin_name not in discovered, \
                f"Plugin {plugin_name} with invalid manifest should not be discovered"


class TestDependencyValidation:
    """
    Feature: third-party-plugin-system, Property 12: Dependency validation
    
    For any plugin with declared dependencies, the Plugin System should verify
    all required dependencies are available before allowing the plugin to load,
    and should report any missing dependencies.
    
    Validates: Requirements 7.2, 7.3
    """
    
    @settings(max_examples=100)
    @given(plugin_data=plugin_with_dependencies())
    def test_validates_all_dependencies_present(self, plugin_data):
        """
        Property: When all dependencies are present, validation passes.
        
        For any plugin with dependencies, if all required dependency directories exist,
        the pre-load dependency validation should pass (not report missing dependencies).
        """
        plugin_name, dependencies, manifest_data = plugin_data
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create main plugin
            create_plugin_directory(plugin_path, plugin_name, has_manifest=True, manifest_data=manifest_data)
            
            # Create all dependency plugins
            for dep in dependencies:
                dep_manifest = {
                    'name': dep['name'],
                    'version': '1.0.0',
                    'description': 'Dependency plugin',
                    'author': 'Test'
                }
                create_plugin_directory(plugin_path, dep['name'], has_manifest=True, manifest_data=dep_manifest)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Load manifest and validate dependencies
            manifest = PluginManifest.from_dict(manifest_data)
            dep_errors = plugin_manager._validate_dependencies(manifest)
            
            # Assert - should have no dependency errors for required dependencies
            required_deps = [d for d in dependencies if not d.get('optional', False)]
            if required_deps:
                # Check that no required dependencies are reported as missing
                for dep in required_deps:
                    assert not any(dep['name'] in error for error in dep_errors), \
                        f"Required dependency {dep['name']} should not be reported as missing when it exists"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        dep_name=valid_plugin_name()
    )
    def test_reports_missing_required_dependency(self, plugin_name, dep_name):
        """
        Property: Missing required dependencies should be reported.
        
        For any plugin with a required dependency that doesn't exist,
        dependency validation should report the missing dependency.
        """
        # Ensure plugin and dependency have different names
        if plugin_name == dep_name:
            dep_name = dep_name + "_dep"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create plugin with required dependency
            manifest_data = {
                'name': plugin_name,
                'version': '1.0.0',
                'description': 'Test plugin',
                'author': 'Test',
                'dependencies': {
                    'plugins': [
                        {'name': dep_name, 'optional': False}
                    ]
                }
            }
            create_plugin_directory(plugin_path, plugin_name, has_manifest=True, manifest_data=manifest_data)
            
            # Do NOT create the dependency plugin
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Load manifest and validate dependencies
            manifest = PluginManifest.from_dict(manifest_data)
            dep_errors = plugin_manager._validate_dependencies(manifest)
            
            # Assert - should report missing dependency
            assert len(dep_errors) > 0, \
                f"Should report missing required dependency {dep_name}"
            assert any(dep_name in error for error in dep_errors), \
                f"Error message should mention missing dependency {dep_name}, but got: {dep_errors}"
    
    @settings(max_examples=100)
    @given(
        plugin_name=valid_plugin_name(),
        dep_name=valid_plugin_name()
    )
    def test_allows_missing_optional_dependency(self, plugin_name, dep_name):
        """
        Property: Missing optional dependencies should not be reported as errors.
        
        For any plugin with an optional dependency that doesn't exist,
        dependency validation should not report it as an error.
        """
        # Ensure plugin and dependency have different names
        if plugin_name == dep_name:
            dep_name = dep_name + "_dep"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create plugin with optional dependency
            manifest_data = {
                'name': plugin_name,
                'version': '1.0.0',
                'description': 'Test plugin',
                'author': 'Test',
                'dependencies': {
                    'plugins': [
                        {'name': dep_name, 'optional': True}
                    ]
                }
            }
            create_plugin_directory(plugin_path, plugin_name, has_manifest=True, manifest_data=manifest_data)
            
            # Do NOT create the dependency plugin
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Load manifest and validate dependencies
            manifest = PluginManifest.from_dict(manifest_data)
            dep_errors = plugin_manager._validate_dependencies(manifest)
            
            # Assert - should not report missing optional dependency as an error
            assert len(dep_errors) == 0, \
                f"Should not report missing optional dependency {dep_name} as an error, but got: {dep_errors}"
    
    @settings(max_examples=100)
    @given(
        plugin_names=st.lists(
            valid_plugin_name(),
            min_size=2,
            max_size=4,
            unique=True
        )
    )
    def test_validates_dependency_chain(self, plugin_names):
        """
        Property: Dependency chains should be validated.
        
        For any chain of plugin dependencies (A depends on B, B depends on C),
        all dependencies in the chain should pass validation when all exist.
        """
        if len(plugin_names) < 2:
            return  # Need at least 2 plugins for a chain
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir)
            
            # Create a dependency chain: each plugin depends on the next
            manifests = []
            for i, plugin_name in enumerate(plugin_names):
                if i < len(plugin_names) - 1:
                    # Has a dependency on the next plugin
                    manifest_data = {
                        'name': plugin_name,
                        'version': '1.0.0',
                        'description': f'Plugin {i}',
                        'author': 'Test',
                        'dependencies': {
                            'plugins': [
                                {'name': plugin_names[i + 1], 'optional': False}
                            ]
                        }
                    }
                else:
                    # Last plugin has no dependencies
                    manifest_data = {
                        'name': plugin_name,
                        'version': '1.0.0',
                        'description': f'Plugin {i}',
                        'author': 'Test'
                    }
                
                create_plugin_directory(plugin_path, plugin_name, has_manifest=True, manifest_data=manifest_data)
                manifests.append(manifest_data)
            
            # Create plugin manager
            config_manager = create_mock_config_manager([str(plugin_path)])
            plugin_manager = PluginManager(config_manager)
            plugin_manager.plugin_paths = [plugin_path]
            
            # Validate each plugin's dependencies
            for i, manifest_data in enumerate(manifests):
                manifest = PluginManifest.from_dict(manifest_data)
                dep_errors = plugin_manager._validate_dependencies(manifest)
                
                # Assert - should have no dependency errors since all plugins exist
                assert len(dep_errors) == 0, \
                    f"Plugin {plugin_names[i]} should have no dependency errors when chain is complete, but got: {dep_errors}"
