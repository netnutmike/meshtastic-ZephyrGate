"""
Property-Based Tests for Plugin Manifest System

Tests universal properties of manifest validation using Hypothesis.
"""

import pytest
from hypothesis import given, settings, strategies as st
from pathlib import Path
import tempfile
import yaml

from src.core.plugin_manifest import (
    PluginManifest,
    PluginDependency,
    CommandCapability,
    TaskCapability,
    MenuCapability,
    ManifestLoader
)


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
    # Plugin names should be non-empty strings with reasonable characters
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and not x.startswith('-') and not x.startswith('_')))


@st.composite
def valid_description(draw):
    """Generate valid descriptions"""
    return draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip()))


@st.composite
def valid_author(draw):
    """Generate valid author names"""
    return draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))


@st.composite
def valid_plugin_dependency(draw):
    """Generate valid plugin dependencies"""
    name = draw(valid_plugin_name())
    # Generate valid version specifiers or None
    version = draw(st.one_of(
        st.none(),
        st.sampled_from(['>=', '==', '<=', '>', '<', '~=']).flatmap(
            lambda op: valid_semver().map(lambda v: f"{op}{v}")
        )
    ))
    optional = draw(st.booleans())
    return PluginDependency(name=name, version=version, optional=optional)


@st.composite
def valid_command_capability(draw):
    """Generate valid command capabilities"""
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip()))
    description = draw(st.text(max_size=200))
    usage = draw(st.text(max_size=100))
    return CommandCapability(name=name, description=description, usage=usage)


@st.composite
def valid_task_capability(draw):
    """Generate valid task capabilities"""
    name = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    # Either interval or cron, not both
    use_interval = draw(st.booleans())
    if use_interval:
        interval = draw(st.integers(min_value=1, max_value=86400))
        return TaskCapability(name=name, interval=interval)
    else:
        cron = draw(st.text(min_size=1, max_size=50))
        return TaskCapability(name=name, cron=cron)


@st.composite
def valid_menu_capability(draw):
    """Generate valid menu capabilities"""
    menu = draw(st.text(min_size=1, max_size=30).filter(lambda x: x.strip()))
    label = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    command = draw(st.text(min_size=1, max_size=30).filter(lambda x: x.strip()))
    description = draw(st.text(max_size=200))
    return MenuCapability(menu=menu, label=label, command=command, description=description)


@st.composite
def valid_manifest(draw):
    """Generate valid plugin manifests"""
    name = draw(valid_plugin_name())
    version = draw(valid_semver())
    description = draw(valid_description())
    author = draw(valid_author())
    
    # Optional fields
    author_email = draw(st.one_of(st.none(), st.emails()))
    license_type = draw(st.one_of(st.none(), st.sampled_from(['MIT', 'Apache-2.0', 'GPL-3.0', 'BSD-3-Clause'])))
    homepage = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    # ZephyrGate compatibility
    min_version = draw(st.one_of(st.none(), valid_semver()))
    max_version = draw(st.one_of(st.none(), valid_semver()))
    
    # Dependencies
    plugin_deps = draw(st.lists(valid_plugin_dependency(), max_size=5))
    # Python dependencies should be non-empty, non-whitespace strings
    python_deps = draw(st.lists(
        st.text(
            alphabet=st.characters(blacklist_characters='\r\n\t'),
            min_size=1,
            max_size=50
        ).filter(lambda x: x.strip()),
        max_size=5
    ))
    
    # Capabilities
    commands = draw(st.lists(valid_command_capability(), max_size=10))
    tasks = draw(st.lists(valid_task_capability(), max_size=5))
    menus = draw(st.lists(valid_menu_capability(), max_size=5))
    
    # Configuration
    config_schema_file = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    default_config = draw(st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.booleans(), st.integers(), st.text(max_size=50)),
        max_size=5
    ))
    
    # Permissions
    permissions = draw(st.lists(
        st.sampled_from(['send_messages', 'database_access', 'http_requests', 'schedule_tasks']),
        max_size=4,
        unique=True
    ))
    
    return PluginManifest(
        name=name,
        version=version,
        description=description,
        author=author,
        author_email=author_email,
        license=license_type,
        homepage=homepage,
        min_zephyrgate_version=min_version,
        max_zephyrgate_version=max_version,
        plugin_dependencies=plugin_deps,
        python_dependencies=python_deps,
        commands=commands,
        scheduled_tasks=tasks,
        menu_items=menus,
        config_schema_file=config_schema_file,
        default_config=default_config,
        permissions=permissions
    )


# Property Tests

class TestManifestCompleteness:
    """
    Feature: third-party-plugin-system, Property 24: Manifest completeness
    
    For any plugin package, the manifest file should contain all required fields
    (name, version, description, author) and should pass validation.
    
    Validates: Requirements 11.1, 11.5
    """
    
    @settings(max_examples=100)
    @given(manifest=valid_manifest())
    def test_valid_manifest_passes_validation(self, manifest):
        """
        Property: Valid manifests with all required fields should pass validation.
        
        For any manifest with valid name, version, description, and author,
        the validation should return no errors.
        """
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) == 0, f"Valid manifest should have no errors, but got: {errors}"
        assert manifest.is_valid(), "Valid manifest should return True for is_valid()"
    
    @settings(max_examples=100)
    @given(manifest=valid_manifest())
    def test_manifest_round_trip_preserves_data(self, manifest):
        """
        Property: Converting manifest to dict and back should preserve all data.
        
        For any valid manifest, converting to dictionary and back should result
        in an equivalent manifest.
        """
        # Act
        manifest_dict = manifest.to_dict()
        reconstructed = PluginManifest.from_dict(manifest_dict)
        
        # Assert - check all required fields are preserved
        assert reconstructed.name == manifest.name
        assert reconstructed.version == manifest.version
        assert reconstructed.description == manifest.description
        assert reconstructed.author == manifest.author
        assert reconstructed.author_email == manifest.author_email
        assert reconstructed.license == manifest.license
        assert reconstructed.homepage == manifest.homepage
        assert reconstructed.min_zephyrgate_version == manifest.min_zephyrgate_version
        assert reconstructed.max_zephyrgate_version == manifest.max_zephyrgate_version
        assert len(reconstructed.plugin_dependencies) == len(manifest.plugin_dependencies)
        assert len(reconstructed.python_dependencies) == len(manifest.python_dependencies)
        assert len(reconstructed.commands) == len(manifest.commands)
        assert len(reconstructed.scheduled_tasks) == len(manifest.scheduled_tasks)
        assert len(reconstructed.menu_items) == len(manifest.menu_items)
        assert reconstructed.config_schema_file == manifest.config_schema_file
        assert reconstructed.permissions == manifest.permissions
    
    @settings(max_examples=100)
    @given(
        name=st.one_of(st.none(), st.just(""), st.text(max_size=0)),
        version=valid_semver(),
        description=valid_description(),
        author=valid_author()
    )
    def test_missing_name_fails_validation(self, name, version, description, author):
        """
        Property: Manifests without a valid name should fail validation.
        
        For any manifest with missing, empty, or whitespace-only name,
        validation should return an error about the name field.
        """
        # Arrange
        manifest = PluginManifest(
            name=name if name else "",
            version=version,
            description=description,
            author=author
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Manifest with invalid name should have validation errors"
        assert any("name" in error.lower() for error in errors), \
            f"Should have error about name field, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=st.one_of(st.none(), st.just(""), st.text(max_size=0)),
        description=valid_description(),
        author=valid_author()
    )
    def test_missing_version_fails_validation(self, name, version, description, author):
        """
        Property: Manifests without a valid version should fail validation.
        
        For any manifest with missing, empty, or whitespace-only version,
        validation should return an error about the version field.
        """
        # Arrange
        manifest = PluginManifest(
            name=name,
            version=version if version else "",
            description=description,
            author=author
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Manifest with invalid version should have validation errors"
        assert any("version" in error.lower() for error in errors), \
            f"Should have error about version field, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=st.text(min_size=1, max_size=20).filter(
            lambda v: not v.strip().startswith(tuple('0123456789'))
        ),
        description=valid_description(),
        author=valid_author()
    )
    def test_invalid_version_format_fails_validation(self, name, version, description, author):
        """
        Property: Manifests with invalid version format should fail validation.
        
        For any manifest with a version that doesn't match semver format (X.Y.Z),
        validation should return an error about the version format.
        """
        # Arrange
        manifest = PluginManifest(
            name=name,
            version=version,
            description=description,
            author=author
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Manifest with invalid version format should have validation errors"
        assert any("version" in error.lower() and "format" in error.lower() for error in errors), \
            f"Should have error about version format, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=valid_semver(),
        description=st.one_of(st.none(), st.just(""), st.text(max_size=0)),
        author=valid_author()
    )
    def test_missing_description_fails_validation(self, name, version, description, author):
        """
        Property: Manifests without a valid description should fail validation.
        
        For any manifest with missing, empty, or whitespace-only description,
        validation should return an error about the description field.
        """
        # Arrange
        manifest = PluginManifest(
            name=name,
            version=version,
            description=description if description else "",
            author=author
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Manifest with invalid description should have validation errors"
        assert any("description" in error.lower() for error in errors), \
            f"Should have error about description field, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=valid_semver(),
        description=valid_description(),
        author=st.one_of(st.none(), st.just(""), st.text(max_size=0))
    )
    def test_missing_author_fails_validation(self, name, version, description, author):
        """
        Property: Manifests without a valid author should fail validation.
        
        For any manifest with missing, empty, or whitespace-only author,
        validation should return an error about the author field.
        """
        # Arrange
        manifest = PluginManifest(
            name=name,
            version=version,
            description=description,
            author=author if author else ""
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Manifest with invalid author should have validation errors"
        assert any("author" in error.lower() for error in errors), \
            f"Should have error about author field, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(manifest=valid_manifest())
    def test_manifest_yaml_round_trip(self, manifest):
        """
        Property: Writing manifest to YAML and reading back should preserve data.
        
        For any valid manifest, writing to YAML file and reading back should
        result in an equivalent manifest.
        """
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "manifest.yaml"
            
            # Act - write to YAML
            with open(yaml_path, 'w') as f:
                yaml.dump(manifest.to_dict(), f)
            
            # Act - read from YAML
            loaded_manifest = PluginManifest.from_yaml(yaml_path)
            
            # Assert - check required fields are preserved
            assert loaded_manifest.name == manifest.name
            assert loaded_manifest.version == manifest.version
            assert loaded_manifest.description == manifest.description
            assert loaded_manifest.author == manifest.author
            
            # Validate the loaded manifest
            errors = loaded_manifest.validate()
            assert len(errors) == 0, f"Loaded manifest should be valid, but got errors: {errors}"
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=valid_semver(),
        description=valid_description(),
        author=valid_author(),
        task_name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    def test_task_without_interval_or_cron_fails_validation(self, name, version, description, author, task_name):
        """
        Property: Scheduled tasks must have either interval or cron specified.
        
        For any scheduled task without interval or cron, validation should fail.
        """
        # Arrange
        task = TaskCapability(name=task_name, interval=None, cron=None)
        manifest = PluginManifest(
            name=name,
            version=version,
            description=description,
            author=author,
            scheduled_tasks=[task]
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Task without interval or cron should fail validation"
        assert any("interval" in error.lower() or "cron" in error.lower() for error in errors), \
            f"Should have error about interval or cron, but got: {errors}"
        assert not manifest.is_valid()
    
    @settings(max_examples=100)
    @given(
        name=valid_plugin_name(),
        version=valid_semver(),
        description=valid_description(),
        author=valid_author(),
        task_name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        interval=st.integers(max_value=0)
    )
    def test_task_with_non_positive_interval_fails_validation(self, name, version, description, author, task_name, interval):
        """
        Property: Scheduled tasks with non-positive intervals should fail validation.
        
        For any scheduled task with interval <= 0, validation should fail.
        """
        # Arrange
        task = TaskCapability(name=task_name, interval=interval)
        manifest = PluginManifest(
            name=name,
            version=version,
            description=description,
            author=author,
            scheduled_tasks=[task]
        )
        
        # Act
        errors = manifest.validate()
        
        # Assert
        assert len(errors) > 0, "Task with non-positive interval should fail validation"
        assert any("interval" in error.lower() and "positive" in error.lower() for error in errors), \
            f"Should have error about positive interval, but got: {errors}"
        assert not manifest.is_valid()
