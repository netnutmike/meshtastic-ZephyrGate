"""
Property-Based Tests for Plugin Configuration System

Tests universal properties that should hold across all plugin configurations.
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
import jsonschema

from src.core.plugin_config import (
    PluginConfigurationManager,
    ConfigField,
    ConfigSection,
    PluginConfigurationSchema
)
from src.core.config import ConfigurationManager


# Strategy builders for generating test data

@composite
def json_schema_type(draw):
    """Generate valid JSON schema types"""
    return draw(st.sampled_from(["string", "integer", "number", "boolean", "array", "object"]))


@composite
def config_field_strategy(draw, required=st.booleans()):
    """Generate valid configuration fields"""
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), blacklist_characters='.')))
    field_type = draw(st.sampled_from([str, int, float, bool, list, dict]))
    is_required = draw(required)
    description = draw(st.text(max_size=100))
    
    # Generate appropriate default value based on type
    if field_type == str:
        default = draw(st.text(max_size=50))
    elif field_type == int:
        default = draw(st.integers(min_value=-1000, max_value=1000))
    elif field_type == float:
        default = draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    elif field_type == bool:
        default = draw(st.booleans())
    elif field_type == list:
        default = draw(st.lists(st.text(max_size=10), max_size=5))
    else:  # dict
        default = draw(st.dictionaries(st.text(min_size=1, max_size=10), st.text(max_size=10), max_size=3))
    
    return ConfigField(
        name=name,
        type=field_type,
        default=default,
        required=is_required,
        description=description
    )


@composite
def config_section_strategy(draw):
    """Generate valid configuration sections"""
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))))
    description = draw(st.text(max_size=100))
    fields = draw(st.lists(config_field_strategy(), min_size=1, max_size=5))
    
    section = ConfigSection(name=name, description=description)
    for field in fields:
        section.add_field(field)
    
    return section


@composite
def plugin_schema_strategy(draw):
    """Generate valid plugin configuration schemas"""
    plugin_name = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), blacklist_characters=' ')))
    
    schema = PluginConfigurationSchema(plugin_name)
    
    # Add global fields
    num_global_fields = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_global_fields):
        field = draw(config_field_strategy())
        schema.add_field(field)
    
    # Add sections
    num_sections = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_sections):
        section = draw(config_section_strategy())
        schema.add_section(section)
    
    return schema


@composite
def config_dict_from_schema(draw, schema_obj):
    """Generate configuration dictionary that matches a schema"""
    json_schema = schema_obj.to_schema()
    config = {}
    
    # Generate values for properties
    for prop_name, prop_schema in json_schema.get("properties", {}).items():
        prop_type = prop_schema.get("type")
        
        # Use default if available
        if "default" in prop_schema:
            config[prop_name] = prop_schema["default"]
        elif prop_type == "string":
            config[prop_name] = draw(st.text(max_size=50))
        elif prop_type == "integer":
            minimum = prop_schema.get("minimum", -1000)
            maximum = prop_schema.get("maximum", 1000)
            config[prop_name] = draw(st.integers(min_value=minimum, max_value=maximum))
        elif prop_type == "number":
            config[prop_name] = draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
        elif prop_type == "boolean":
            config[prop_name] = draw(st.booleans())
        elif prop_type == "array":
            config[prop_name] = draw(st.lists(st.text(max_size=10), max_size=5))
        elif prop_type == "object":
            # For nested objects, use defaults or empty dict
            config[prop_name] = prop_schema.get("default", {})
    
    return config


# Property Tests

class TestConfigurationValidationProperties:
    """
    Feature: third-party-plugin-system, Property 14: Configuration validation
    
    Tests that configuration validation correctly identifies valid and invalid configurations.
    """
    
    @settings(max_examples=100, deadline=None)
    @given(plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))))
    def test_valid_config_passes_validation(self, plugin_name):
        """
        Property: For any plugin schema with valid configuration matching defaults,
        validation should succeed with no errors.
        
        Validates: Requirements 8.1, 8.3
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Create a simple schema
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "timeout": {"type": "integer", "default": 30, "minimum": 1}
            }
        }
        default_config = {"enabled": True, "timeout": 30}
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema, default_config)
        
        # Valid config matching schema
        valid_config = {"enabled": True, "timeout": 30}
        
        # Validation should return empty error list
        errors = plugin_config_mgr.validate_plugin_config(plugin_name, valid_config)
        
        # Should have no errors
        assert len(errors) == 0, f"Valid config failed validation: {errors}"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        invalid_value=st.one_of(st.text(), st.integers(), st.booleans())
    )
    def test_invalid_type_fails_validation(self, plugin_name, invalid_value):
        """
        Property: For any plugin schema with a typed field, providing a value of the wrong type
        should result in validation errors.
        
        Validates: Requirements 8.1, 8.3
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Create a simple schema with a string field
        schema = {
            "type": "object",
            "properties": {
                "string_field": {"type": "string"},
                "int_field": {"type": "integer"},
                "bool_field": {"type": "boolean"}
            },
            "required": ["string_field"]
        }
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Create config with wrong type for string_field
        if isinstance(invalid_value, str):
            # String is valid for string_field, so use it for int_field instead
            invalid_config = {
                "string_field": "valid",
                "int_field": invalid_value  # String where int expected
            }
        elif isinstance(invalid_value, int):
            # Int is invalid for string_field
            invalid_config = {
                "string_field": invalid_value  # Int where string expected
            }
        else:  # bool
            # Bool is invalid for string_field
            invalid_config = {
                "string_field": invalid_value  # Bool where string expected
            }
        
        # Validation should return errors
        errors = plugin_config_mgr.validate_plugin_config(plugin_name, invalid_config)
        
        # Should have at least one error for type mismatch
        assert len(errors) > 0, "Invalid type should produce validation errors"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        required_field_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')))
    )
    def test_missing_required_field_fails_validation(self, plugin_name, required_field_name):
        """
        Property: For any plugin schema with required fields, omitting a required field
        should result in validation errors.
        
        Validates: Requirements 8.1, 8.3
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Create schema with required field
        schema = {
            "type": "object",
            "properties": {
                required_field_name: {"type": "string"}
            },
            "required": [required_field_name]
        }
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Create config without required field
        invalid_config = {}
        
        # Validation should return errors
        errors = plugin_config_mgr.validate_plugin_config(plugin_name, invalid_config)
        
        # Should have at least one error for missing required field
        assert len(errors) > 0, "Missing required field should produce validation errors"
        assert any(required_field_name in error or "required" in error.lower() for error in errors), \
            f"Error should mention missing required field: {errors}"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        min_value=st.integers(min_value=1, max_value=50),
        test_value=st.integers(min_value=-100, max_value=100)
    )
    def test_constraint_validation(self, plugin_name, min_value, test_value):
        """
        Property: For any plugin schema with constraints (min/max), values violating
        constraints should fail validation.
        
        Validates: Requirements 8.1, 8.3
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Create schema with minimum constraint
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": "integer",
                    "minimum": min_value
                }
            }
        }
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Create config
        config = {"value": test_value}
        
        # Validation result should match constraint
        errors = plugin_config_mgr.validate_plugin_config(plugin_name, config)
        
        if test_value < min_value:
            # Should have errors
            assert len(errors) > 0, f"Value {test_value} < {min_value} should fail validation"
        else:
            # Should have no errors
            assert len(errors) == 0, f"Value {test_value} >= {min_value} should pass validation, got errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestConfigurationMergingProperties:
    """
    Feature: third-party-plugin-system, Property 15: Configuration merging
    
    Tests that configuration merging correctly combines defaults with user values.
    """
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        default_value=st.text(max_size=50),
        user_value=st.text(max_size=50)
    )
    def test_user_config_overrides_defaults(self, plugin_name, default_value, user_value):
        """
        Property: For any plugin with default configuration, when user provides a value
        for the same key, the user value should take precedence in the merged config.
        
        Validates: Requirements 8.4
        """
        assume(default_value != user_value)  # Only test when values differ
        
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {plugin_name: {"key": user_value}}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register with defaults
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        default_config = {"key": default_value}
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema, default_config)
        
        # Get merged config
        merged_config = plugin_config_mgr.get_plugin_config(plugin_name, merge_defaults=True)
        
        # User value should override default
        assert merged_config["key"] == user_value, \
            f"User value {user_value} should override default {default_value}"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        default_keys=st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll', 'Lu'))), min_size=1, max_size=5, unique=True),
        user_keys=st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll', 'Lu'))), min_size=1, max_size=5, unique=True)
    )
    def test_merged_config_contains_all_keys(self, plugin_name, default_keys, user_keys):
        """
        Property: For any plugin with default and user configuration, the merged config
        should contain all keys from both defaults and user config.
        
        Validates: Requirements 8.4
        """
        # Create default and user configs
        default_config = {key: f"default_{key}" for key in default_keys}
        user_config = {key: f"user_{key}" for key in user_keys}
        
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {plugin_name: user_config}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register with defaults
        schema = {
            "type": "object",
            "properties": {key: {"type": "string"} for key in set(default_keys + user_keys)},
            "additionalProperties": True
        }
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema, default_config)
        
        # Get merged config
        merged_config = plugin_config_mgr.get_plugin_config(plugin_name, merge_defaults=True)
        
        # All default keys should be present
        for key in default_keys:
            assert key in merged_config, f"Default key {key} should be in merged config"
        
        # All user keys should be present
        for key in user_keys:
            assert key in merged_config, f"User key {key} should be in merged config"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        nested_key=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll', 'Lu'))),
        default_nested_value=st.text(max_size=20),
        user_nested_value=st.text(max_size=20)
    )
    def test_nested_config_merging(self, plugin_name, nested_key, default_nested_value, user_nested_value):
        """
        Property: For any plugin with nested configuration, merging should work recursively,
        preserving nested structure.
        
        Validates: Requirements 8.4
        """
        assume(default_nested_value != user_nested_value)
        
        # Create nested configs
        default_config = {
            "section": {
                nested_key: default_nested_value,
                "default_only": "default"
            }
        }
        user_config = {
            "section": {
                nested_key: user_nested_value,
                "user_only": "user"
            }
        }
        
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {plugin_name: user_config}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register with defaults
        schema = {
            "type": "object",
            "properties": {
                "section": {
                    "type": "object",
                    "additionalProperties": True
                }
            },
            "additionalProperties": True
        }
        
        plugin_config_mgr.register_plugin_schema(plugin_name, schema, default_config)
        
        # Get merged config
        merged_config = plugin_config_mgr.get_plugin_config(plugin_name, merge_defaults=True)
        
        # Check nested merging
        assert "section" in merged_config
        assert merged_config["section"][nested_key] == user_nested_value, "User value should override"
        assert merged_config["section"]["default_only"] == "default", "Default-only key should be preserved"
        assert merged_config["section"]["user_only"] == "user", "User-only key should be present"


class TestConfigurationChangeNotificationProperties:
    """
    Feature: third-party-plugin-system, Property 16: Configuration change notification
    
    Tests that configuration change callbacks are invoked correctly.
    """
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        initial_value=st.text(max_size=50),
        new_value=st.text(max_size=50)
    )
    def test_callback_invoked_on_config_change(self, plugin_name, initial_value, new_value):
        """
        Property: For any plugin with a registered callback, when configuration changes,
        the callback should be invoked with the changed keys.
        
        Validates: Requirements 8.2
        """
        assume(initial_value != new_value)  # Only test actual changes
        
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {plugin_name: {"key": initial_value}}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register schema
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Track callback invocations
        callback_invoked = []
        
        def callback(changed_keys, new_config):
            callback_invoked.append((changed_keys, new_config))
        
        # Register callback
        plugin_config_mgr.register_config_change_callback(plugin_name, callback)
        
        # Update config
        new_config = {"key": new_value}
        plugin_config_mgr.set_plugin_config(plugin_name, new_config, notify_changes=True)
        
        # Callback should have been invoked
        assert len(callback_invoked) == 1, "Callback should be invoked once"
        
        changed_keys, received_config = callback_invoked[0]
        assert "key" in changed_keys, "Changed key should be in changed_keys dict"
        assert changed_keys["key"] == new_value, "Changed key should have new value"
        assert received_config["key"] == new_value, "New config should have new value"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        value=st.text(max_size=50)
    )
    def test_callback_not_invoked_when_disabled(self, plugin_name, value):
        """
        Property: For any plugin with a registered callback, when configuration is set
        with notify_changes=False, the callback should not be invoked.
        
        Validates: Requirements 8.2
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register schema
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Track callback invocations
        callback_invoked = []
        
        def callback(changed_keys, new_config):
            callback_invoked.append((changed_keys, new_config))
        
        # Register callback
        plugin_config_mgr.register_config_change_callback(plugin_name, callback)
        
        # Set config with notifications disabled
        new_config = {"key": value}
        plugin_config_mgr.set_plugin_config(plugin_name, new_config, notify_changes=False)
        
        # Callback should not have been invoked
        assert len(callback_invoked) == 0, "Callback should not be invoked when notify_changes=False"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        num_callbacks=st.integers(min_value=1, max_value=5),
        value=st.text(max_size=50)
    )
    def test_all_callbacks_invoked(self, plugin_name, num_callbacks, value):
        """
        Property: For any plugin with multiple registered callbacks, when configuration changes,
        all callbacks should be invoked.
        
        Validates: Requirements 8.2
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        config_mgr.config = {"plugins": {}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register schema
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Track callback invocations
        callback_counters = [0] * num_callbacks
        
        def make_callback(index):
            def callback(changed_keys, new_config):
                callback_counters[index] += 1
            return callback
        
        # Register multiple callbacks
        for i in range(num_callbacks):
            plugin_config_mgr.register_config_change_callback(plugin_name, make_callback(i))
        
        # Update config
        new_config = {"key": value}
        plugin_config_mgr.set_plugin_config(plugin_name, new_config, notify_changes=True)
        
        # All callbacks should have been invoked
        for i, count in enumerate(callback_counters):
            assert count == 1, f"Callback {i} should be invoked once, was invoked {count} times"
    
    @settings(max_examples=100, deadline=None)
    @given(
        plugin_name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        unchanged_value=st.text(max_size=50)
    )
    def test_callback_not_invoked_when_no_changes(self, plugin_name, unchanged_value):
        """
        Property: For any plugin with a registered callback, when configuration is set
        to the same value, the callback should not be invoked (no actual changes).
        
        Validates: Requirements 8.2
        """
        # Create config manager
        config_mgr = ConfigurationManager()
        initial_config = {"key": unchanged_value}
        config_mgr.config = {"plugins": {plugin_name: initial_config.copy()}}
        plugin_config_mgr = PluginConfigurationManager(config_mgr)
        
        # Register schema
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        plugin_config_mgr.register_plugin_schema(plugin_name, schema)
        
        # Track callback invocations
        callback_invoked = []
        
        def callback(changed_keys, new_config):
            callback_invoked.append((changed_keys, new_config))
        
        # Register callback
        plugin_config_mgr.register_config_change_callback(plugin_name, callback)
        
        # Set config to same value
        plugin_config_mgr.set_plugin_config(plugin_name, initial_config, notify_changes=True)
        
        # Callback should not be invoked if no changes detected
        # (or invoked with empty changed_keys)
        if len(callback_invoked) > 0:
            changed_keys, _ = callback_invoked[0]
            assert len(changed_keys) == 0, "No keys should be marked as changed when values are identical"
