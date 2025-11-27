"""
Plugin Manifest System for ZephyrGate

Provides manifest parsing, validation, and data models for third-party plugins.
"""

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logging import get_logger


logger = get_logger('plugin_manifest')


@dataclass
class PluginDependency:
    """Plugin dependency specification"""
    name: str
    version: Optional[str] = None
    optional: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginDependency':
        """Create from dictionary"""
        return cls(
            name=data.get('name', ''),
            version=data.get('version'),
            optional=data.get('optional', False)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {'name': self.name, 'optional': self.optional}
        if self.version:
            result['version'] = self.version
        return result


@dataclass
class CommandCapability:
    """Command capability declaration"""
    name: str
    description: str = ""
    usage: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandCapability':
        """Create from dictionary"""
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            usage=data.get('usage', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'description': self.description,
            'usage': self.usage
        }


@dataclass
class TaskCapability:
    """Scheduled task capability declaration"""
    name: str
    interval: Optional[int] = None
    cron: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskCapability':
        """Create from dictionary"""
        return cls(
            name=data.get('name', ''),
            interval=data.get('interval'),
            cron=data.get('cron')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {'name': self.name}
        if self.interval is not None:
            result['interval'] = self.interval
        if self.cron:
            result['cron'] = self.cron
        return result


@dataclass
class MenuCapability:
    """Menu item capability declaration"""
    menu: str
    label: str
    command: str
    description: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MenuCapability':
        """Create from dictionary"""
        return cls(
            menu=data.get('menu', ''),
            label=data.get('label', ''),
            command=data.get('command', ''),
            description=data.get('description', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'menu': self.menu,
            'label': self.label,
            'command': self.command,
            'description': self.description
        }


@dataclass
class PluginManifest:
    """Plugin manifest data model with validation"""
    name: str
    version: str
    description: str
    author: str
    author_email: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    
    # ZephyrGate compatibility
    min_zephyrgate_version: Optional[str] = None
    max_zephyrgate_version: Optional[str] = None
    
    # Dependencies
    plugin_dependencies: List[PluginDependency] = field(default_factory=list)
    python_dependencies: List[str] = field(default_factory=list)
    
    # Capabilities
    commands: List[CommandCapability] = field(default_factory=list)
    scheduled_tasks: List[TaskCapability] = field(default_factory=list)
    menu_items: List[MenuCapability] = field(default_factory=list)
    
    # Configuration
    config_schema_file: Optional[str] = None
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Permissions
    permissions: List[str] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'PluginManifest':
        """
        Load manifest from YAML file.
        
        Args:
            yaml_path: Path to manifest.yaml file
            
        Returns:
            PluginManifest instance
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If manifest data is invalid
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {yaml_path}")
        
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse manifest YAML: {e}")
        
        if not data:
            raise ValueError("Manifest file is empty")
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginManifest':
        """
        Create manifest from dictionary.
        
        Args:
            data: Dictionary containing manifest data
            
        Returns:
            PluginManifest instance
        """
        # Extract ZephyrGate compatibility
        zephyrgate_config = data.get('zephyrgate', {})
        
        # Extract dependencies
        dependencies_config = data.get('dependencies', {})
        plugin_deps = []
        if 'plugins' in dependencies_config:
            for dep_data in dependencies_config['plugins']:
                plugin_deps.append(PluginDependency.from_dict(dep_data))
        
        python_deps = dependencies_config.get('python_packages', [])
        
        # Extract capabilities
        capabilities_config = data.get('capabilities', {})
        commands = []
        if 'commands' in capabilities_config:
            for cmd_data in capabilities_config['commands']:
                commands.append(CommandCapability.from_dict(cmd_data))
        
        scheduled_tasks = []
        if 'scheduled_tasks' in capabilities_config:
            for task_data in capabilities_config['scheduled_tasks']:
                scheduled_tasks.append(TaskCapability.from_dict(task_data))
        
        menu_items = []
        if 'menu_items' in capabilities_config:
            for menu_data in capabilities_config['menu_items']:
                menu_items.append(MenuCapability.from_dict(menu_data))
        
        # Extract configuration
        config_section = data.get('config', {})
        
        return cls(
            name=data.get('name', ''),
            version=data.get('version', ''),
            description=data.get('description', ''),
            author=data.get('author', ''),
            author_email=data.get('author_email'),
            license=data.get('license'),
            homepage=data.get('homepage'),
            min_zephyrgate_version=zephyrgate_config.get('min_version'),
            max_zephyrgate_version=zephyrgate_config.get('max_version'),
            plugin_dependencies=plugin_deps,
            python_dependencies=python_deps,
            commands=commands,
            scheduled_tasks=scheduled_tasks,
            menu_items=menu_items,
            config_schema_file=config_section.get('schema_file'),
            default_config=config_section.get('defaults', {}),
            permissions=data.get('permissions', [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert manifest to dictionary.
        
        Returns:
            Dictionary representation of manifest
        """
        result = {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author
        }
        
        if self.author_email:
            result['author_email'] = self.author_email
        if self.license:
            result['license'] = self.license
        if self.homepage:
            result['homepage'] = self.homepage
        
        # ZephyrGate compatibility
        if self.min_zephyrgate_version or self.max_zephyrgate_version:
            result['zephyrgate'] = {}
            if self.min_zephyrgate_version:
                result['zephyrgate']['min_version'] = self.min_zephyrgate_version
            if self.max_zephyrgate_version:
                result['zephyrgate']['max_version'] = self.max_zephyrgate_version
        
        # Dependencies
        if self.plugin_dependencies or self.python_dependencies:
            result['dependencies'] = {}
            if self.plugin_dependencies:
                result['dependencies']['plugins'] = [
                    dep.to_dict() for dep in self.plugin_dependencies
                ]
            if self.python_dependencies:
                result['dependencies']['python_packages'] = self.python_dependencies
        
        # Capabilities
        if self.commands or self.scheduled_tasks or self.menu_items:
            result['capabilities'] = {}
            if self.commands:
                result['capabilities']['commands'] = [
                    cmd.to_dict() for cmd in self.commands
                ]
            if self.scheduled_tasks:
                result['capabilities']['scheduled_tasks'] = [
                    task.to_dict() for task in self.scheduled_tasks
                ]
            if self.menu_items:
                result['capabilities']['menu_items'] = [
                    menu.to_dict() for menu in self.menu_items
                ]
        
        # Configuration
        if self.config_schema_file or self.default_config:
            result['config'] = {}
            if self.config_schema_file:
                result['config']['schema_file'] = self.config_schema_file
            if self.default_config:
                result['config']['defaults'] = self.default_config
        
        # Permissions
        if self.permissions:
            result['permissions'] = self.permissions
        
        return result
    
    def validate(self) -> List[str]:
        """
        Validate manifest and return list of errors.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Required fields
        if not self.name or not isinstance(self.name, str) or not self.name.strip():
            errors.append("Plugin name is required and must be a non-empty string")
        
        if not self.version or not isinstance(self.version, str) or not self.version.strip():
            errors.append("Plugin version is required and must be a non-empty string")
        
        if not self.description or not isinstance(self.description, str) or not self.description.strip():
            errors.append("Plugin description is required and must be a non-empty string")
        
        if not self.author or not isinstance(self.author, str) or not self.author.strip():
            errors.append("Plugin author is required and must be a non-empty string")
        
        # Validate version format (semver: major.minor.patch)
        if self.version and not re.match(r'^\d+\.\d+\.\d+', self.version):
            errors.append(f"Invalid version format '{self.version}' (expected semver: X.Y.Z)")
        
        # Validate ZephyrGate version format if provided
        if self.min_zephyrgate_version and not re.match(r'^\d+\.\d+\.\d+', self.min_zephyrgate_version):
            errors.append(f"Invalid min_zephyrgate_version format '{self.min_zephyrgate_version}' (expected semver: X.Y.Z)")
        
        if self.max_zephyrgate_version and not re.match(r'^\d+\.\d+\.\d+', self.max_zephyrgate_version):
            errors.append(f"Invalid max_zephyrgate_version format '{self.max_zephyrgate_version}' (expected semver: X.Y.Z)")
        
        # Validate dependencies
        for dep in self.plugin_dependencies:
            if not dep.name or not isinstance(dep.name, str) or not dep.name.strip():
                errors.append(f"Plugin dependency name is required and must be a non-empty string")
            
            # Version can be a comparison operator followed by a version number
            # Examples: >=1.0.0, ==2.1.3, ~=1.2.0, >=0.1.0
            if dep.version and not re.match(r'^[><=!~]+\s*\d+(\.\d+)*', dep.version):
                errors.append(f"Invalid dependency version format '{dep.version}' for plugin '{dep.name}'")
        
        # Validate python dependencies format
        for dep in self.python_dependencies:
            if not isinstance(dep, str) or not dep.strip():
                errors.append(f"Python dependency must be a non-empty string")
        
        # Validate command capabilities
        for cmd in self.commands:
            if not cmd.name or not isinstance(cmd.name, str) or not cmd.name.strip():
                errors.append(f"Command name is required and must be a non-empty string")
        
        # Validate scheduled task capabilities
        for task in self.scheduled_tasks:
            if not task.name or not isinstance(task.name, str) or not task.name.strip():
                errors.append(f"Scheduled task name is required and must be a non-empty string")
            
            if task.interval is None and task.cron is None:
                errors.append(f"Scheduled task '{task.name}' must have either interval or cron specified")
            
            if task.interval is not None and not isinstance(task.interval, int):
                errors.append(f"Scheduled task '{task.name}' interval must be an integer")
            
            if task.interval is not None and task.interval <= 0:
                errors.append(f"Scheduled task '{task.name}' interval must be positive")
        
        # Validate menu item capabilities
        for menu in self.menu_items:
            if not menu.menu or not isinstance(menu.menu, str) or not menu.menu.strip():
                errors.append(f"Menu item menu is required and must be a non-empty string")
            
            if not menu.label or not isinstance(menu.label, str) or not menu.label.strip():
                errors.append(f"Menu item label is required and must be a non-empty string")
            
            if not menu.command or not isinstance(menu.command, str) or not menu.command.strip():
                errors.append(f"Menu item command is required and must be a non-empty string")
        
        # Validate permissions
        for perm in self.permissions:
            if not isinstance(perm, str) or not perm.strip():
                errors.append(f"Permission must be a non-empty string")
        
        return errors
    
    def is_valid(self) -> bool:
        """
        Check if manifest is valid.
        
        Returns:
            True if manifest is valid, False otherwise
        """
        return len(self.validate()) == 0


class ManifestLoader:
    """Utility class for loading and validating plugin manifests"""
    
    @staticmethod
    def load_from_directory(plugin_dir: Path) -> Optional[PluginManifest]:
        """
        Load manifest from plugin directory.
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            PluginManifest if found and valid, None otherwise
        """
        manifest_path = plugin_dir / "manifest.yaml"
        
        if not manifest_path.exists():
            logger.warning(f"No manifest.yaml found in {plugin_dir}")
            return None
        
        try:
            manifest = PluginManifest.from_yaml(manifest_path)
            
            # Validate manifest
            errors = manifest.validate()
            if errors:
                logger.error(f"Manifest validation failed for {plugin_dir}:")
                for error in errors:
                    logger.error(f"  - {error}")
                return None
            
            logger.info(f"Successfully loaded manifest for plugin '{manifest.name}' from {plugin_dir}")
            return manifest
            
        except FileNotFoundError as e:
            logger.error(f"Manifest file not found: {e}")
            return None
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse manifest YAML in {plugin_dir}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid manifest data in {plugin_dir}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading manifest from {plugin_dir}: {e}")
            return None
    
    @staticmethod
    def validate_manifest_file(manifest_path: Path) -> tuple[bool, List[str]]:
        """
        Validate a manifest file.
        
        Args:
            manifest_path: Path to manifest.yaml file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            manifest = PluginManifest.from_yaml(manifest_path)
            errors = manifest.validate()
            return (len(errors) == 0, errors)
        except Exception as e:
            return (False, [str(e)])
