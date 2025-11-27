"""
Plugin Configuration Management for ZephyrGate

Provides configuration patterns and validation for plugins.
"""

import json
import jsonschema
import logging
from typing import Any, Dict, List, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
from cryptography.fernet import Fernet
import base64
import os

from .config import ConfigurationManager

logger = logging.getLogger(__name__)


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
        self.config_change_callbacks: Dict[str, List[Callable]] = {}
        self.default_configs: Dict[str, Dict[str, Any]] = {}
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for secure storage"""
        key_file = Path("data/.config_encryption_key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Create new key
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(key_file, 0o600)
            return key
    
    def register_plugin_schema(self, plugin_name: str, schema: Dict[str, Any], 
                              default_config: Optional[Dict[str, Any]] = None):
        """
        Register a plugin's configuration schema with optional defaults.
        
        Args:
            plugin_name: Name of the plugin
            schema: JSON schema for validation
            default_config: Default configuration values
            
        Raises:
            ValueError: If schema is invalid
        """
        self.schemas[plugin_name] = schema
        
        if default_config:
            self.default_configs[plugin_name] = default_config
        
        # Create validator
        try:
            self.validators[plugin_name] = jsonschema.Draft7Validator(schema)
        except Exception as e:
            raise ValueError(f"Invalid schema for plugin {plugin_name}: {e}")
    
    def validate_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> List[str]:
        """
        Validate plugin configuration against its schema.
        
        Args:
            plugin_name: Name of the plugin
            config: Configuration to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        if plugin_name not in self.validators:
            return []  # No schema means no validation
        
        validator = self.validators[plugin_name]
        errors = []
        
        for error in validator.iter_errors(config):
            # Build a readable error message
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"{path}: {error.message}")
        
        return errors
    
    def get_plugin_config(self, plugin_name: str, merge_defaults: bool = True) -> Dict[str, Any]:
        """
        Get configuration for a plugin with optional default merging.
        
        Args:
            plugin_name: Name of the plugin
            merge_defaults: Whether to merge with default configuration
            
        Returns:
            Plugin configuration dictionary
        """
        plugin_config_key = f"plugins.{plugin_name}"
        user_config = self.config_manager.get(plugin_config_key, {})
        
        if merge_defaults and plugin_name in self.default_configs:
            # Merge defaults with user config (user config takes precedence)
            return self._deep_merge(self.default_configs[plugin_name], user_config)
        
        return user_config
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any], 
                         notify_changes: bool = True):
        """
        Set configuration for a plugin with validation.
        
        Args:
            plugin_name: Name of the plugin
            config: Configuration to set
            notify_changes: Whether to notify callbacks of changes
            
        Raises:
            ValueError: If configuration validation fails
        """
        # Validate configuration
        errors = self.validate_plugin_config(plugin_name, config)
        if errors:
            error_msg = f"Configuration validation failed for {plugin_name}:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Get old config for change detection
        old_config = self.get_plugin_config(plugin_name, merge_defaults=False)
        
        # Set configuration
        plugin_config_key = f"plugins.{plugin_name}"
        self.config_manager.set(plugin_config_key, config)
        
        # Notify callbacks if enabled
        if notify_changes:
            changed_keys = self._get_changed_keys(old_config, config)
            if changed_keys:
                self._notify_config_changed(plugin_name, changed_keys, config)
    
    def update_plugin_config(self, plugin_name: str, updates: Dict[str, Any], 
                           notify_changes: bool = True):
        """
        Update specific configuration values for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            updates: Configuration updates to apply
            notify_changes: Whether to notify callbacks of changes
        """
        current_config = self.get_plugin_config(plugin_name, merge_defaults=False)
        
        # Deep merge updates
        updated_config = self._deep_merge(current_config, updates)
        
        # Validate and set
        self.set_plugin_config(plugin_name, updated_config, notify_changes=notify_changes)
    
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
    
    def register_config_change_callback(self, plugin_name: str, callback: Callable[[Dict[str, Any], Dict[str, Any]], None]):
        """
        Register a callback to be notified when plugin configuration changes.
        
        Args:
            plugin_name: Name of the plugin
            callback: Callback function that receives (changed_keys, new_config)
        """
        if plugin_name not in self.config_change_callbacks:
            self.config_change_callbacks[plugin_name] = []
        
        self.config_change_callbacks[plugin_name].append(callback)
        logger.debug(f"Registered config change callback for plugin {plugin_name}")
    
    def unregister_config_change_callback(self, plugin_name: str, callback: Callable):
        """
        Unregister a configuration change callback.
        
        Args:
            plugin_name: Name of the plugin
            callback: Callback function to remove
        """
        if plugin_name in self.config_change_callbacks:
            try:
                self.config_change_callbacks[plugin_name].remove(callback)
                logger.debug(f"Unregistered config change callback for plugin {plugin_name}")
            except ValueError:
                pass
    
    def _notify_config_changed(self, plugin_name: str, changed_keys: Dict[str, Any], 
                              new_config: Dict[str, Any]):
        """
        Notify all registered callbacks of configuration changes.
        
        Args:
            plugin_name: Name of the plugin
            changed_keys: Dictionary of changed keys and their new values
            new_config: Complete new configuration
        """
        if plugin_name not in self.config_change_callbacks:
            return
        
        for callback in self.config_change_callbacks[plugin_name]:
            try:
                callback(changed_keys, new_config)
            except Exception as e:
                logger.error(f"Error in config change callback for {plugin_name}: {e}")
    
    def _get_changed_keys(self, old_config: Dict[str, Any], new_config: Dict[str, Any], 
                         prefix: str = "") -> Dict[str, Any]:
        """
        Get dictionary of changed keys between two configurations.
        
        Args:
            old_config: Old configuration
            new_config: New configuration
            prefix: Key prefix for nested keys
            
        Returns:
            Dictionary of changed keys with their new values
        """
        changed = {}
        
        # Check for new or changed keys
        for key, new_value in new_config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if key not in old_config:
                # New key
                changed[full_key] = new_value
            elif isinstance(new_value, dict) and isinstance(old_config[key], dict):
                # Recursively check nested dicts
                nested_changes = self._get_changed_keys(old_config[key], new_value, full_key)
                changed.update(nested_changes)
            elif new_value != old_config[key]:
                # Changed value
                changed[full_key] = new_value
        
        # Check for removed keys
        for key in old_config:
            if key not in new_config:
                full_key = f"{prefix}.{key}" if prefix else key
                changed[full_key] = None  # None indicates removal
        
        return changed
    
    def get_config_value(self, plugin_name: str, key: str, default: Any = None, 
                        value_type: Optional[Type] = None) -> Any:
        """
        Get a specific configuration value with type safety.
        
        Args:
            plugin_name: Name of the plugin
            key: Configuration key (dot notation supported)
            default: Default value if key not found
            value_type: Expected type for validation
            
        Returns:
            Configuration value
            
        Raises:
            TypeError: If value type doesn't match expected type
        """
        config = self.get_plugin_config(plugin_name)
        
        # Navigate using dot notation
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        # Type checking if requested
        if value_type is not None and value is not None:
            if not isinstance(value, value_type):
                raise TypeError(
                    f"Configuration value for {plugin_name}.{key} has type {type(value).__name__}, "
                    f"expected {value_type.__name__}"
                )
        
        return value
    
    def store_secure_value(self, plugin_name: str, key: str, value: str):
        """
        Store a secure value (like API credentials) with encryption.
        
        Args:
            plugin_name: Name of the plugin
            key: Configuration key
            value: Value to encrypt and store
        """
        # Encrypt the value
        encrypted = self._cipher.encrypt(value.encode())
        encrypted_b64 = base64.b64encode(encrypted).decode()
        
        # Store with special prefix to indicate encryption
        secure_key = f"_secure_{key}"
        current_config = self.get_plugin_config(plugin_name, merge_defaults=False)
        current_config[secure_key] = encrypted_b64
        
        self.set_plugin_config(plugin_name, current_config, notify_changes=False)
        logger.debug(f"Stored secure value for {plugin_name}.{key}")
    
    def retrieve_secure_value(self, plugin_name: str, key: str, default: str = "") -> str:
        """
        Retrieve a secure value with decryption.
        
        Args:
            plugin_name: Name of the plugin
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Decrypted value
        """
        secure_key = f"_secure_{key}"
        config = self.get_plugin_config(plugin_name, merge_defaults=False)
        
        if secure_key not in config:
            return default
        
        try:
            encrypted_b64 = config[secure_key]
            encrypted = base64.b64decode(encrypted_b64)
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secure value for {plugin_name}.{key}: {e}")
            return default
    
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