"""
Plugin Configuration Management for ZephyrGate

Provides configuration patterns and validation for plugins.
"""

import json
import jsonschema
from typing import Any, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from pathlib import Path

from .config import ConfigurationManager


@dataclass
class ConfigField:
    """Configuration field definition"""
    name: str
    type: Type
    default: Any = None
    required: bool = False
    description: str = ""
    validation: Optional[Dict[str, Any]] = None
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format"""
        schema = {
            "description": self.description
        }
        
        # Map Python types to JSON schema types
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        if self.type in type_mapping:
            schema["type"] = type_mapping[self.type]
        
        if self.default is not None:
            schema["default"] = self.default
        
        if self.validation:
            schema.update(self.validation)
        
        return schema


@dataclass
class ConfigSection:
    """Configuration section definition"""
    name: str
    description: str = ""
    fields: List[ConfigField] = field(default_factory=list)
    required: bool = False
    
    def add_field(self, field: ConfigField):
        """Add a field to this section"""
        self.fields.append(field)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format"""
        schema = {
            "type": "object",
            "description": self.description,
            "properties": {},
            "required": []
        }
        
        for field in self.fields:
            schema["properties"][field.name] = field.to_schema()
            if field.required:
                schema["required"].append(field.name)
        
        return schema


class PluginConfigurationSchema:
    """Plugin configuration schema builder"""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.sections: List[ConfigSection] = []
        self.global_fields: List[ConfigField] = []
    
    def add_section(self, section: ConfigSection):
        """Add a configuration section"""
        self.sections.append(section)
    
    def add_field(self, field: ConfigField):
        """Add a global field (not in a section)"""
        self.global_fields.append(field)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to complete JSON schema"""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{self.plugin_name} Configuration",
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Add global fields
        for field in self.global_fields:
            schema["properties"][field.name] = field.to_schema()
            if field.required:
                schema["required"].append(field.name)
        
        # Add sections
        for section in self.sections:
            schema["properties"][section.name] = section.to_schema()
            if section.required:
                schema["required"].append(section.name)
        
        return schema
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        config = {}
        
        # Add global field defaults
        for field in self.global_fields:
            if field.default is not None:
                config[field.name] = field.default
        
        # Add section defaults
        for section in self.sections:
            section_config = {}
            for field in section.fields:
                if field.default is not None:
                    section_config[field.name] = field.default
            
            if section_config:
                config[section.name] = section_config
        
        return config


class PluginConfigurationManager:
    """Manages plugin configurations with validation and schema support"""
    
    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.validators: Dict[str, jsonschema.Validator] = {}
    
    def register_plugin_schema(self, plugin_name: str, schema: Dict[str, Any]):
        """Register a plugin's configuration schema"""
        self.schemas[plugin_name] = schema
        
        # Create validator
        try:
            self.validators[plugin_name] = jsonschema.Draft7Validator(schema)
        except Exception as e:
            raise ValueError(f"Invalid schema for plugin {plugin_name}: {e}")
    
    def validate_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration against its schema"""
        if plugin_name not in self.validators:
            return True  # No schema means no validation
        
        validator = self.validators[plugin_name]
        
        try:
            validator.validate(config)
            return True
        except jsonschema.ValidationError as e:
            raise ValueError(f"Configuration validation failed for {plugin_name}: {e.message}")
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Get configuration for a plugin"""
        plugin_config_key = f"plugins.{plugin_name}"
        return self.config_manager.get(plugin_config_key, {})
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]):
        """Set configuration for a plugin with validation"""
        # Validate configuration
        self.validate_plugin_config(plugin_name, config)
        
        # Set configuration
        plugin_config_key = f"plugins.{plugin_name}"
        self.config_manager.set(plugin_config_key, config)
    
    def update_plugin_config(self, plugin_name: str, updates: Dict[str, Any]):
        """Update specific configuration values for a plugin"""
        current_config = self.get_plugin_config(plugin_name)
        
        # Deep merge updates
        updated_config = self._deep_merge(current_config, updates)
        
        # Validate and set
        self.set_plugin_config(plugin_name, updated_config)
    
    def get_plugin_schema(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a plugin"""
        return self.schemas.get(plugin_name)
    
    def get_all_plugin_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all plugins"""
        plugins_config = self.config_manager.get("plugins", {})
        return plugins_config
    
    def export_plugin_config(self, plugin_name: str, file_path: str):
        """Export plugin configuration to file"""
        config = self.get_plugin_config(plugin_name)
        
        path = Path(file_path)
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def import_plugin_config(self, plugin_name: str, file_path: str):
        """Import plugin configuration from file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(path, 'r') as f:
            config = json.load(f)
        
        self.set_plugin_config(plugin_name, config)
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


# Common configuration field builders
class ConfigFieldBuilder:
    """Builder for common configuration fields"""
    
    @staticmethod
    def string_field(name: str, default: str = "", required: bool = False, 
                    description: str = "", min_length: int = None, max_length: int = None) -> ConfigField:
        """Create a string configuration field"""
        validation = {}
        if min_length is not None:
            validation["minLength"] = min_length
        if max_length is not None:
            validation["maxLength"] = max_length
        
        return ConfigField(
            name=name,
            type=str,
            default=default,
            required=required,
            description=description,
            validation=validation if validation else None
        )
    
    @staticmethod
    def integer_field(name: str, default: int = 0, required: bool = False,
                     description: str = "", minimum: int = None, maximum: int = None) -> ConfigField:
        """Create an integer configuration field"""
        validation = {}
        if minimum is not None:
            validation["minimum"] = minimum
        if maximum is not None:
            validation["maximum"] = maximum
        
        return ConfigField(
            name=name,
            type=int,
            default=default,
            required=required,
            description=description,
            validation=validation if validation else None
        )
    
    @staticmethod
    def boolean_field(name: str, default: bool = False, required: bool = False,
                     description: str = "") -> ConfigField:
        """Create a boolean configuration field"""
        return ConfigField(
            name=name,
            type=bool,
            default=default,
            required=required,
            description=description
        )
    
    @staticmethod
    def list_field(name: str, default: List = None, required: bool = False,
                  description: str = "", item_type: str = None) -> ConfigField:
        """Create a list configuration field"""
        validation = {}
        if item_type:
            validation["items"] = {"type": item_type}
        
        return ConfigField(
            name=name,
            type=list,
            default=default or [],
            required=required,
            description=description,
            validation=validation if validation else None
        )
    
    @staticmethod
    def enum_field(name: str, choices: List[str], default: str = None, 
                  required: bool = False, description: str = "") -> ConfigField:
        """Create an enum configuration field"""
        validation = {"enum": choices}
        
        return ConfigField(
            name=name,
            type=str,
            default=default or choices[0],
            required=required,
            description=description,
            validation=validation
        )


# Common configuration sections
def create_database_section() -> ConfigSection:
    """Create a standard database configuration section"""
    section = ConfigSection(
        name="database",
        description="Database configuration"
    )
    
    section.add_field(ConfigFieldBuilder.string_field(
        "path", 
        default="data/plugin.db",
        description="Database file path"
    ))
    
    section.add_field(ConfigFieldBuilder.integer_field(
        "max_connections",
        default=10,
        minimum=1,
        maximum=100,
        description="Maximum database connections"
    ))
    
    section.add_field(ConfigFieldBuilder.integer_field(
        "timeout",
        default=30,
        minimum=1,
        description="Database operation timeout in seconds"
    ))
    
    return section


def create_logging_section() -> ConfigSection:
    """Create a standard logging configuration section"""
    section = ConfigSection(
        name="logging",
        description="Logging configuration"
    )
    
    section.add_field(ConfigFieldBuilder.enum_field(
        "level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        description="Log level"
    ))
    
    section.add_field(ConfigFieldBuilder.string_field(
        "file",
        default="logs/plugin.log",
        description="Log file path"
    ))
    
    section.add_field(ConfigFieldBuilder.boolean_field(
        "console",
        default=True,
        description="Enable console logging"
    ))
    
    return section


def create_api_section() -> ConfigSection:
    """Create a standard API configuration section"""
    section = ConfigSection(
        name="api",
        description="API configuration"
    )
    
    section.add_field(ConfigFieldBuilder.string_field(
        "base_url",
        required=True,
        description="API base URL"
    ))
    
    section.add_field(ConfigFieldBuilder.string_field(
        "api_key",
        description="API key for authentication"
    ))
    
    section.add_field(ConfigFieldBuilder.integer_field(
        "timeout",
        default=30,
        minimum=1,
        description="API request timeout in seconds"
    ))
    
    section.add_field(ConfigFieldBuilder.integer_field(
        "retry_attempts",
        default=3,
        minimum=0,
        description="Number of retry attempts for failed requests"
    ))
    
    return section