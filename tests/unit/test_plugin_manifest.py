"""
Unit Tests for Plugin Manifest System

Tests specific examples and edge cases for manifest validation.
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from src.core.plugin_manifest import (
    PluginManifest,
    PluginDependency,
    CommandCapability,
    TaskCapability,
    MenuCapability,
    ManifestLoader
)


class TestPluginDependency:
    """Test PluginDependency data model"""
    
    def test_create_dependency(self):
        """Test creating a plugin dependency"""
        dep = PluginDependency(name="test_plugin", version=">=1.0.0", optional=False)
        
        assert dep.name == "test_plugin"
        assert dep.version == ">=1.0.0"
        assert dep.optional is False
    
    def test_dependency_from_dict(self):
        """Test creating dependency from dictionary"""
        data = {
            "name": "test_plugin",
            "version": ">=1.0.0",
            "optional": True
        }
        
        dep = PluginDependency.from_dict(data)
        
        assert dep.name == "test_plugin"
        assert dep.version == ">=1.0.0"
        assert dep.optional is True
    
    def test_dependency_to_dict(self):
        """Test converting dependency to dictionary"""
        dep = PluginDependency(name="test_plugin", version=">=1.0.0", optional=True)
        
        result = dep.to_dict()
        
        assert result["name"] == "test_plugin"
        assert result["version"] == ">=1.0.0"
        assert result["optional"] is True


class TestCommandCapability:
    """Test CommandCapability data model"""
    
    def test_create_command(self):
        """Test creating a command capability"""
        cmd = CommandCapability(
            name="test",
            description="Test command",
            usage="test [args]"
        )
        
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.usage == "test [args]"
    
    def test_command_from_dict(self):
        """Test creating command from dictionary"""
        data = {
            "name": "test",
            "description": "Test command",
            "usage": "test [args]"
        }
        
        cmd = CommandCapability.from_dict(data)
        
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.usage == "test [args]"


class TestTaskCapability:
    """Test TaskCapability data model"""
    
    def test_create_task_with_interval(self):
        """Test creating a task with interval"""
        task = TaskCapability(name="hourly_task", interval=3600)
        
        assert task.name == "hourly_task"
        assert task.interval == 3600
        assert task.cron is None
    
    def test_create_task_with_cron(self):
        """Test creating a task with cron expression"""
        task = TaskCapability(name="daily_task", cron="0 0 * * *")
        
        assert task.name == "daily_task"
        assert task.cron == "0 0 * * *"
        assert task.interval is None


class TestMenuCapability:
    """Test MenuCapability data model"""
    
    def test_create_menu_item(self):
        """Test creating a menu item"""
        menu = MenuCapability(
            menu="utilities",
            label="My Plugin",
            command="myplugin",
            description="Access my plugin features"
        )
        
        assert menu.menu == "utilities"
        assert menu.label == "My Plugin"
        assert menu.command == "myplugin"
        assert menu.description == "Access my plugin features"


class TestPluginManifest:
    """Test PluginManifest data model and validation"""
    
    def test_create_minimal_manifest(self):
        """Test creating a minimal valid manifest"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author"
        )
        
        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.description == "A test plugin"
        assert manifest.author == "Test Author"
        assert manifest.is_valid()
    
    def test_validate_minimal_manifest(self):
        """Test validation of minimal manifest"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author"
        )
        
        errors = manifest.validate()
        
        assert len(errors) == 0
        assert manifest.is_valid()
    
    def test_validate_missing_name(self):
        """Test validation fails with missing name"""
        manifest = PluginManifest(
            name="",
            version="1.0.0",
            description="A test plugin",
            author="Test Author"
        )
        
        errors = manifest.validate()
        
        assert len(errors) > 0
        assert any("name" in error.lower() for error in errors)
        assert not manifest.is_valid()
    
    def test_validate_invalid_version_format(self):
        """Test validation fails with invalid version format"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",  # Missing patch version
            description="A test plugin",
            author="Test Author"
        )
        
        errors = manifest.validate()
        
        assert len(errors) > 0
        assert any("version" in error.lower() and "format" in error.lower() for error in errors)
        assert not manifest.is_valid()
    
    def test_manifest_to_dict(self):
        """Test converting manifest to dictionary"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            author_email="test@example.com",
            license="MIT"
        )
        
        result = manifest.to_dict()
        
        assert result["name"] == "test_plugin"
        assert result["version"] == "1.0.0"
        assert result["description"] == "A test plugin"
        assert result["author"] == "Test Author"
        assert result["author_email"] == "test@example.com"
        assert result["license"] == "MIT"
    
    def test_manifest_from_dict(self):
        """Test creating manifest from dictionary"""
        data = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "author": "Test Author",
            "author_email": "test@example.com",
            "license": "MIT"
        }
        
        manifest = PluginManifest.from_dict(data)
        
        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.description == "A test plugin"
        assert manifest.author == "Test Author"
        assert manifest.author_email == "test@example.com"
        assert manifest.license == "MIT"
    
    def test_manifest_with_dependencies(self):
        """Test manifest with plugin dependencies"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            plugin_dependencies=[
                PluginDependency(name="weather", version=">=1.0.0", optional=False),
                PluginDependency(name="bbs", version=">=1.0.0", optional=True)
            ],
            python_dependencies=["requests>=2.28.0", "aiohttp>=3.8.0"]
        )
        
        errors = manifest.validate()
        
        assert len(errors) == 0
        assert len(manifest.plugin_dependencies) == 2
        assert len(manifest.python_dependencies) == 2
    
    def test_manifest_with_capabilities(self):
        """Test manifest with various capabilities"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            commands=[
                CommandCapability(name="test", description="Test command")
            ],
            scheduled_tasks=[
                TaskCapability(name="hourly", interval=3600)
            ],
            menu_items=[
                MenuCapability(menu="utilities", label="Test", command="test")
            ]
        )
        
        errors = manifest.validate()
        
        assert len(errors) == 0
        assert len(manifest.commands) == 1
        assert len(manifest.scheduled_tasks) == 1
        assert len(manifest.menu_items) == 1
    
    def test_manifest_yaml_round_trip(self):
        """Test writing and reading manifest from YAML"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            author_email="test@example.com"
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "manifest.yaml"
            
            # Write to YAML
            with open(yaml_path, 'w') as f:
                yaml.dump(manifest.to_dict(), f)
            
            # Read from YAML
            loaded_manifest = PluginManifest.from_yaml(yaml_path)
            
            assert loaded_manifest.name == manifest.name
            assert loaded_manifest.version == manifest.version
            assert loaded_manifest.description == manifest.description
            assert loaded_manifest.author == manifest.author
            assert loaded_manifest.author_email == manifest.author_email


class TestManifestLoader:
    """Test ManifestLoader utility class"""
    
    def test_load_from_directory_success(self):
        """Test loading manifest from directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            # Create manifest file
            manifest_data = {
                "name": "test_plugin",
                "version": "1.0.0",
                "description": "A test plugin",
                "author": "Test Author"
            }
            
            manifest_path = plugin_dir / "manifest.yaml"
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest_data, f)
            
            # Load manifest
            manifest = ManifestLoader.load_from_directory(plugin_dir)
            
            assert manifest is not None
            assert manifest.name == "test_plugin"
            assert manifest.version == "1.0.0"
    
    def test_load_from_directory_missing_file(self):
        """Test loading from directory without manifest file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            # No manifest file created
            manifest = ManifestLoader.load_from_directory(plugin_dir)
            
            assert manifest is None
    
    def test_load_from_directory_invalid_manifest(self):
        """Test loading invalid manifest from directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            
            # Create invalid manifest (missing required fields)
            manifest_data = {
                "name": "test_plugin"
                # Missing version, description, author
            }
            
            manifest_path = plugin_dir / "manifest.yaml"
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest_data, f)
            
            # Load manifest
            manifest = ManifestLoader.load_from_directory(plugin_dir)
            
            assert manifest is None
    
    def test_validate_manifest_file_success(self):
        """Test validating a valid manifest file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_data = {
                "name": "test_plugin",
                "version": "1.0.0",
                "description": "A test plugin",
                "author": "Test Author"
            }
            
            manifest_path = Path(tmpdir) / "manifest.yaml"
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest_data, f)
            
            is_valid, errors = ManifestLoader.validate_manifest_file(manifest_path)
            
            assert is_valid
            assert len(errors) == 0
    
    def test_validate_manifest_file_invalid(self):
        """Test validating an invalid manifest file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_data = {
                "name": "test_plugin",
                "version": "invalid_version",  # Invalid format
                "description": "A test plugin",
                "author": "Test Author"
            }
            
            manifest_path = Path(tmpdir) / "manifest.yaml"
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest_data, f)
            
            is_valid, errors = ManifestLoader.validate_manifest_file(manifest_path)
            
            assert not is_valid
            assert len(errors) > 0
