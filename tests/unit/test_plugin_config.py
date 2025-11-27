"""
Unit tests for Plugin Configuration System
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from src.core.plugin_config import (
    ConfigField, ConfigSection, PluginConfigurationSchema,
    PluginConfigurationManager, ConfigFieldBuilder,
    create_database_section, create_logging_section, create_api_section
)
from src.core.config import ConfigurationManager


class TestConfigField:
    """Test configuration field functionality"""
    
    def test_config_field_creation(self):
        """Test creating configuration fields"""
        field = ConfigField(
            name="test_field",
            type=str,
            default="default_value",
            required=True,
            description="Test field description"
        )
        
        assert field.name == "test_field"
        assert field.type == str
        assert field.default == "default_value"
        assert field.required is True
        assert field.description == "Test field description"
    
    def test_config_field_to_schema(self):
        """Test converting config field to JSON schema"""
        field = ConfigField(
            name="string_field",
            type=str,
            default="default",
            description="A string field",
            validation={"minLength": 1, "maxLength": 100}
        )
        
        schema = field.to_schema()
        
        assert schema["type"] == "string"
        assert schema["default"] == "default"
        assert schema["description"] == "A string field"
        assert schema["minLength"] == 1
        assert schema["maxLength"] == 100
    
    def test_config_field_type_mapping(self):
        """Test type mapping to JSON schema types"""
        test_cases = [
            (str, "string"),
            (int, "integer"),
            (float, "number"),
            (bool, "boolean"),
            (list, "array"),
            (dict, "object")
        ]
        
        for python_type, json_type in test_cases:
            field = ConfigField(name="test", type=python_type)
            schema = field.to_schema()
            assert schema["type"] == json_type


class TestConfigSection:
    """Test configuration section functionality"""
    
    def test_config_section_creation(self):
        """Test creating configuration sections"""
        section = ConfigSection(
            name="test_section",
            description="Test section description"
        )
        
        assert section.name == "test_section"
        assert section.description == "Test section description"
        assert len(section.fields) == 0
        assert section.required is False
    
    def test_config_section_add_field(self):
        """Test adding fields to sections"""
        section = ConfigSection(name="test_section")
        
        field1 = ConfigField(name="field1", type=str)
        field2 = ConfigField(name="field2", type=int, required=True)
        
        section.add_field(field1)
        section.add_field(field2)
        
        assert len(section.fields) == 2
        assert field1 in section.fields
        assert field2 in section.fields
    
    def test_config_section_to_schema(self):
        """Test converting section to JSON schema"""
        section = ConfigSection(
            name="test_section",
            description="Test section"
        )
        
        field1 = ConfigField(name="field1", type=str, default="default1")
        field2 = ConfigField(name="field2", type=int, required=True)
        
        section.add_field(field1)
        section.add_field(field2)
        
        schema = section.to_schema()
        
        assert schema["type"] == "object"
        assert schema["description"] == "Test section"
        assert "field1" in schema["properties"]
        assert "field2" in schema["properties"]
        assert "field2" in schema["required"]
        assert "field1" not in schema["required"]


class TestPluginConfigurationSchema:
    """Test plugin configuration schema builder"""
    
    def test_schema_creation(self):
        """Test creating plugin configuration schema"""
        schema = PluginConfigurationSchema("test_plugin")
        
        assert schema.plugin_name == "test_plugin"
        assert len(schema.sections) == 0
        assert len(schema.global_fields) == 0
    
    def test_schema_add_global_field(self):
        """Test adding global fields to schema"""
        schema = PluginConfigurationSchema("test_plugin")
        
        field = ConfigField(name="enabled", type=bool, default=True)
        schema.add_field(field)
        
        assert len(schema.global_fields) == 1
        assert field in schema.global_fields
    
    def test_schema_add_section(self):
        """Test adding sections to schema"""
        schema = PluginConfigurationSchema("test_plugin")
        
        section = ConfigSection(name="database")
        section.add_field(ConfigField(name="path", type=str, default="db.sqlite"))
        
        schema.add_section(section)
        
        assert len(schema.sections) == 1
        assert section in schema.sections
    
    def test_schema_to_json_schema(self):
        """Test converting to complete JSON schema"""
        schema = PluginConfigurationSchema("test_plugin")
        
        # Add global field
        schema.add_field(ConfigField(name="enabled", type=bool, default=True, required=True))
        
        # Add section
        section = ConfigSection(name="database", required=True)
        section.add_field(ConfigField(name="path", type=str, default="db.sqlite"))
        schema.add_section(section)
        
        json_schema = schema.to_schema()
        
        assert json_schema["title"] == "test_plugin Configuration"
        assert json_schema["type"] == "object"
        assert "enabled" in json_schema["properties"]
        assert "database" in json_schema["properties"]
        assert "enabled" in json_schema["required"]
        assert "database" in json_schema["required"]
    
    def test_schema_get_default_config(self):
        """Test getting default configuration"""
        schema = PluginConfigurationSchema("test_plugin")
        
        # Add global field with default
        schema.add_field(ConfigField(name="enabled", type=bool, default=True))
        
        # Add section with fields
        section = ConfigSection(name="database")
        section.add_field(ConfigField(name="path", type=str, default="db.sqlite"))
        section.add_field(ConfigField(name="timeout", type=int, default=30))
        schema.add_section(section)
        
        default_config = schema.get_default_config()
        
        assert default_config["enabled"] is True
        assert default_config["database"]["path"] == "db.sqlite"
        assert default_config["database"]["timeout"] == 30


class TestConfigFieldBuilder:
    """Test configuration field builder utilities"""
    
    def test_string_field_builder(self):
        """Test string field builder"""
        field = ConfigFieldBuilder.string_field(
            name="test_string",
            default="default_value",
            required=True,
            description="Test string field",
            min_length=1,
            max_length=100
        )
        
        assert field.name == "test_string"
        assert field.type == str
        assert field.default == "default_value"
        assert field.required is True
        assert field.description == "Test string field"
        assert field.validation["minLength"] == 1
        assert field.validation["maxLength"] == 100
    
    def test_integer_field_builder(self):
        """Test integer field builder"""
        field = ConfigFieldBuilder.integer_field(
            name="test_int",
            default=42,
            required=True,
            description="Test integer field",
            minimum=0,
            maximum=100
        )
        
        assert field.name == "test_int"
        assert field.type == int
        assert field.default == 42
        assert field.required is True
        assert field.validation["minimum"] == 0
        assert field.validation["maximum"] == 100
    
    def test_boolean_field_builder(self):
        """Test boolean field builder"""
        field = ConfigFieldBuilder.boolean_field(
            name="test_bool",
            default=True,
            description="Test boolean field"
        )
        
        assert field.name == "test_bool"
        assert field.type == bool
        assert field.default is True
        assert field.required is False
    
    def test_list_field_builder(self):
        """Test list field builder"""
        field = ConfigFieldBuilder.list_field(
            name="test_list",
            default=["item1", "item2"],
            description="Test list field",
            item_type="string"
        )
        
        assert field.name == "test_list"
        assert field.type == list
        assert field.default == ["item1", "item2"]
        assert field.validation["items"]["type"] == "string"
    
    def test_enum_field_builder(self):
        """Test enum field builder"""
        choices = ["option1", "option2", "option3"]
        field = ConfigFieldBuilder.enum_field(
            name="test_enum",
            choices=choices,
            default="option2",
            description="Test enum field"
        )
        
        assert field.name == "test_enum"
        assert field.type == str
        assert field.default == "option2"
        assert field.validation["enum"] == choices


class TestPluginConfigurationManager:
    """Test plugin configuration manager"""
    
    @pytest.fixture
    def config_manager(self):
        """Create test configuration manager"""
        config_mgr = ConfigurationManager()
        config_mgr.config = {
            "plugins": {
                "test_plugin": {
                    "enabled": True,
                    "database": {
                        "path": "test.db"
                    }
                }
            }
        }
        return config_mgr
    
    @pytest.fixture
    def plugin_config_manager(self, config_manager):
        """Create plugin configuration manager"""
        return PluginConfigurationManager(config_manager)
    
    def test_schema_registration(self, plugin_config_manager):
        """Test registering plugin schema"""
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True}
            },
            "required": ["enabled"]
        }
        
        plugin_config_manager.register_plugin_schema("test_plugin", schema)
        
        assert "test_plugin" in plugin_config_manager.schemas
        assert "test_plugin" in plugin_config_manager.validators
    
    def test_invalid_schema_registration(self, plugin_config_manager):
        """Test registering invalid schema"""
        # jsonschema is lenient, so we test with a schema that will cause validation issues
        # Instead, we'll test that a malformed schema structure causes issues
        invalid_schema = "not a dict"  # Schema must be a dict
        
        with pytest.raises((ValueError, TypeError)):
            plugin_config_manager.register_plugin_schema("test_plugin", invalid_schema)
    
    def test_config_validation_success(self, plugin_config_manager):
        """Test successful configuration validation"""
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "timeout": {"type": "integer", "minimum": 1}
            },
            "required": ["enabled"]
        }
        
        plugin_config_manager.register_plugin_schema("test_plugin", schema)
        
        valid_config = {
            "enabled": True,
            "timeout": 30
        }
        
        errors = plugin_config_manager.validate_plugin_config("test_plugin", valid_config)
        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"
    
    def test_config_validation_failure(self, plugin_config_manager):
        """Test configuration validation failure"""
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "timeout": {"type": "integer", "minimum": 1}
            },
            "required": ["enabled"]
        }
        
        plugin_config_manager.register_plugin_schema("test_plugin", schema)
        
        invalid_config = {
            "timeout": -1  # Missing required 'enabled', invalid timeout
        }
        
        errors = plugin_config_manager.validate_plugin_config("test_plugin", invalid_config)
        assert len(errors) > 0, "Invalid config should have validation errors"
        # Should have errors for both missing required field and invalid value
        assert any("enabled" in error or "required" in error.lower() for error in errors)
    
    def test_get_plugin_config(self, plugin_config_manager):
        """Test getting plugin configuration"""
        config = plugin_config_manager.get_plugin_config("test_plugin")
        
        assert config["enabled"] is True
        assert config["database"]["path"] == "test.db"
    
    def test_get_nonexistent_plugin_config(self, plugin_config_manager):
        """Test getting configuration for nonexistent plugin"""
        config = plugin_config_manager.get_plugin_config("nonexistent_plugin")
        
        assert config == {}
    
    def test_set_plugin_config(self, plugin_config_manager):
        """Test setting plugin configuration"""
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"}
            }
        }
        
        plugin_config_manager.register_plugin_schema("new_plugin", schema)
        
        new_config = {"enabled": False}
        plugin_config_manager.set_plugin_config("new_plugin", new_config)
        
        # Verify config was set
        retrieved_config = plugin_config_manager.get_plugin_config("new_plugin")
        assert retrieved_config["enabled"] is False
    
    def test_update_plugin_config(self, plugin_config_manager):
        """Test updating plugin configuration"""
        updates = {
            "enabled": False,
            "database": {
                "timeout": 60
            }
        }
        
        plugin_config_manager.update_plugin_config("test_plugin", updates)
        
        updated_config = plugin_config_manager.get_plugin_config("test_plugin")
        assert updated_config["enabled"] is False
        assert updated_config["database"]["path"] == "test.db"  # Preserved
        assert updated_config["database"]["timeout"] == 60  # Added
    
    def test_get_plugin_schema(self, plugin_config_manager):
        """Test getting plugin schema"""
        schema = {"type": "object", "properties": {}}
        plugin_config_manager.register_plugin_schema("test_plugin", schema)
        
        retrieved_schema = plugin_config_manager.get_plugin_schema("test_plugin")
        assert retrieved_schema == schema
        
        # Test nonexistent schema
        nonexistent_schema = plugin_config_manager.get_plugin_schema("nonexistent")
        assert nonexistent_schema is None
    
    def test_get_all_plugin_configs(self, plugin_config_manager):
        """Test getting all plugin configurations"""
        all_configs = plugin_config_manager.get_all_plugin_configs()
        
        assert "test_plugin" in all_configs
        assert all_configs["test_plugin"]["enabled"] is True
    
    def test_export_import_plugin_config(self, plugin_config_manager):
        """Test exporting and importing plugin configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            # Export config
            plugin_config_manager.export_plugin_config("test_plugin", temp_file)
            
            # Verify file was created and contains correct data
            with open(temp_file, 'r') as f:
                exported_data = json.load(f)
            
            assert exported_data["enabled"] is True
            assert exported_data["database"]["path"] == "test.db"
            
            # Modify the exported data
            exported_data["enabled"] = False
            with open(temp_file, 'w') as f:
                json.dump(exported_data, f)
            
            # Import modified config
            plugin_config_manager.import_plugin_config("test_plugin", temp_file)
            
            # Verify config was updated
            updated_config = plugin_config_manager.get_plugin_config("test_plugin")
            assert updated_config["enabled"] is False
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def test_import_nonexistent_file(self, plugin_config_manager):
        """Test importing from nonexistent file"""
        with pytest.raises(FileNotFoundError):
            plugin_config_manager.import_plugin_config("test_plugin", "nonexistent.json")


class TestCommonConfigSections:
    """Test common configuration section builders"""
    
    def test_database_section(self):
        """Test database configuration section"""
        section = create_database_section()
        
        assert section.name == "database"
        assert len(section.fields) == 3
        
        field_names = [f.name for f in section.fields]
        assert "path" in field_names
        assert "max_connections" in field_names
        assert "timeout" in field_names
    
    def test_logging_section(self):
        """Test logging configuration section"""
        section = create_logging_section()
        
        assert section.name == "logging"
        assert len(section.fields) == 3
        
        field_names = [f.name for f in section.fields]
        assert "level" in field_names
        assert "file" in field_names
        assert "console" in field_names
        
        # Check enum field for level
        level_field = next(f for f in section.fields if f.name == "level")
        assert level_field.validation["enum"] == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    def test_api_section(self):
        """Test API configuration section"""
        section = create_api_section()
        
        assert section.name == "api"
        assert len(section.fields) == 4
        
        field_names = [f.name for f in section.fields]
        assert "base_url" in field_names
        assert "api_key" in field_names
        assert "timeout" in field_names
        assert "retry_attempts" in field_names
        
        # Check required field
        base_url_field = next(f for f in section.fields if f.name == "base_url")
        assert base_url_field.required is True


if __name__ == "__main__":
    pytest.main([__file__])