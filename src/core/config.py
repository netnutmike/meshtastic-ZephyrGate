"""
Configuration Management System for ZephyrGate

Handles loading configuration from environment variables, config files,
and provides validation and runtime updates.
"""

import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ConfigSource:
    """Configuration source definition"""
    name: str
    priority: int
    loader: Callable
    path: Optional[str] = None


class ConfigurationError(Exception):
    """Configuration-related errors"""
    pass


class ConfigurationManager:
    """
    Manages system configuration with support for multiple sources,
    validation, and runtime updates.
    """
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config: Dict[str, Any] = {}
        self.watchers: Dict[str, List[Callable]] = {}
        self.sources: List[ConfigSource] = []
        self.logger = logging.getLogger(__name__)
        
        # Default configuration values
        self.defaults = {
            "app": {
                "name": "ZephyrGate",
                "version": "1.0.0",
                "debug": False,
                "log_level": "INFO"
            },
            "meshtastic": {
                "interfaces": [],
                "retry_interval": 30,
                "message_timeout": 300,
                "max_message_size": 228
            },
            "database": {
                "path": "data/zephyrgate.db",
                "backup_interval": 3600,
                "max_connections": 10
            },
            "services": {
                "bbs": {"enabled": True},
                "emergency": {"enabled": True},
                "bot": {"enabled": True},
                "weather": {"enabled": True},
                "email": {"enabled": False},
                "web": {"enabled": True, "port": 8080}
            },
            "logging": {
                "level": "INFO",
                "file": "logs/zephyrgate.log",
                "max_size": "10MB",
                "backup_count": 5
            },
            "plugins": {
                "paths": ["plugins", "examples/plugins"],
                "auto_discover": True,
                "auto_load": True,
                "enabled_plugins": [],
                "disabled_plugins": [],
                "health_check_interval": 60,
                "failure_threshold": 5,
                "restart_backoff_base": 2,
                "restart_backoff_max": 300,
                "max_http_requests_per_minute": 100,
                "max_storage_size_mb": 100,
                "task_timeout": 300
            }
        }
        
        self._setup_sources()
        
    def _setup_sources(self):
        """Set up configuration sources in priority order"""
        # Environment variables (highest priority = lowest number)
        self.sources.append(ConfigSource(
            name="environment",
            priority=4,
            loader=self._load_from_env
        ))
        
        # Local config file
        local_config_path = str(self.config_dir / "config.yaml")
        self.sources.append(ConfigSource(
            name="local_config",
            priority=3,
            loader=lambda: self._load_from_file(local_config_path),
            path=local_config_path
        ))
        
        # Default config file
        default_config_path = str(self.config_dir / "default.yaml")
        self.sources.append(ConfigSource(
            name="default_config",
            priority=2,
            loader=lambda: self._load_from_file(default_config_path),
            path=default_config_path
        ))
        
        # Built-in defaults (lowest priority = highest number)
        self.sources.append(ConfigSource(
            name="defaults",
            priority=1,
            loader=lambda: self.defaults
        ))
    
    def load_config(self) -> None:
        """Load configuration from all sources"""
        self.logger.info("Loading configuration from all sources")
        
        # Sort sources by priority
        sorted_sources = sorted(self.sources, key=lambda x: x.priority, reverse=True)
        
        # Start with empty config
        merged_config = {}
        
        # Load from each source (lowest priority first)
        for source in reversed(sorted_sources):
            try:
                source_config = source.loader()
                if source_config:
                    merged_config = self._deep_merge(merged_config, source_config)
                    self.logger.debug(f"Loaded configuration from {source.name}")
            except Exception as e:
                self.logger.warning(f"Failed to load config from {source.name}: {e}")
        
        self.config = merged_config
        self._validate_config()
        self.logger.info("Configuration loaded successfully")
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        
        # Map environment variables to config keys
        env_mappings = {
            "ZEPHYR_DEBUG": "app.debug",
            "ZEPHYR_LOG_LEVEL": "app.log_level",
            "ZEPHYR_DB_PATH": "database.path",
            "ZEPHYR_WEB_PORT": "services.web.port",
            "ZEPHYR_MESHTASTIC_INTERFACES": "meshtastic.interfaces"
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif config_key == "meshtastic.interfaces":
                    # Parse JSON array for interfaces
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON in {env_var}: {value}")
                        continue
                
                self._set_nested_value(config, config_key, value)
        
        return config
    
    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from YAML or JSON file"""
        path = Path(file_path)
        
        if not path.exists():
            return {}
        
        try:
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    self.logger.warning(f"Unsupported config file format: {path}")
                    return {}
        except Exception as e:
            self.logger.error(f"Error loading config file {path}: {e}")
            return {}
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _set_nested_value(self, config: Dict, key_path: str, value: Any) -> None:
        """Set a nested configuration value using dot notation"""
        keys = key_path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        errors = []
        
        # Validate required sections
        required_sections = ['app', 'database', 'services']
        for section in required_sections:
            if section not in self.config:
                errors.append(f"Missing required configuration section: {section}")
        
        # Validate database path
        db_path = self.get('database.path')
        if db_path:
            db_dir = Path(db_path).parent
            if not db_dir.exists():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create database directory {db_dir}: {e}")
        
        # Validate web port
        web_port = self.get('services.web.port')
        if web_port and (not isinstance(web_port, int) or web_port < 1 or web_port > 65535):
            errors.append(f"Invalid web port: {web_port}")
        
        # Validate log level
        log_level = self.get('app.log_level', 'INFO')
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level.upper() not in valid_levels:
            errors.append(f"Invalid log level: {log_level}")
        
        if errors:
            raise ConfigurationError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        current = self.config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation"""
        self._set_nested_value(self.config, key, value)
        
        # Notify watchers
        if key in self.watchers:
            for callback in self.watchers[key]:
                try:
                    callback(key, value)
                except Exception as e:
                    self.logger.error(f"Error in config watcher for {key}: {e}")
    
    def watch(self, key: str, callback: Callable[[str, Any], None]) -> None:
        """Watch for configuration changes"""
        if key not in self.watchers:
            self.watchers[key] = []
        self.watchers[key].append(callback)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.get(section, {})
    
    def is_service_enabled(self, service: str) -> bool:
        """Check if a service is enabled"""
        return self.get(f'services.{service}.enabled', False)
    
    def get_meshtastic_interfaces(self) -> List[Dict[str, Any]]:
        """Get Meshtastic interface configurations"""
        return self.get('meshtastic.interfaces', [])
    
    def get_plugin_paths(self) -> List[str]:
        """Get plugin discovery paths"""
        return self.get('plugins.paths', ['plugins', 'examples/plugins'])
    
    def is_plugin_auto_discover_enabled(self) -> bool:
        """Check if automatic plugin discovery is enabled"""
        return self.get('plugins.auto_discover', True)
    
    def is_plugin_auto_load_enabled(self) -> bool:
        """Check if automatic plugin loading is enabled"""
        return self.get('plugins.auto_load', True)
    
    def get_enabled_plugins(self) -> List[str]:
        """Get list of explicitly enabled plugins (empty = all)"""
        return self.get('plugins.enabled_plugins', [])
    
    def get_disabled_plugins(self) -> List[str]:
        """Get list of explicitly disabled plugins"""
        return self.get('plugins.disabled_plugins', [])
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        Check if a specific plugin is enabled.
        
        Logic:
        - If plugin is in disabled_plugins list, return False
        - If enabled_plugins list is empty, return True (all enabled by default)
        - If enabled_plugins list is not empty, return True only if plugin is in the list
        """
        disabled = self.get_disabled_plugins()
        if plugin_name in disabled:
            return False
        
        enabled = self.get_enabled_plugins()
        if not enabled:  # Empty list means all plugins enabled
            return True
        
        return plugin_name in enabled
    
    def get_plugin_health_check_interval(self) -> int:
        """Get plugin health check interval in seconds"""
        return self.get('plugins.health_check_interval', 60)
    
    def get_plugin_failure_threshold(self) -> int:
        """Get plugin failure threshold before disabling"""
        return self.get('plugins.failure_threshold', 5)
    
    def get_plugin_restart_backoff_base(self) -> int:
        """Get base backoff time for plugin restarts"""
        return self.get('plugins.restart_backoff_base', 2)
    
    def get_plugin_restart_backoff_max(self) -> int:
        """Get maximum backoff time for plugin restarts"""
        return self.get('plugins.restart_backoff_max', 300)
    
    def get_plugin_http_rate_limit(self) -> int:
        """Get HTTP request rate limit per plugin per minute"""
        return self.get('plugins.max_http_requests_per_minute', 100)
    
    def get_plugin_storage_limit_mb(self) -> int:
        """Get storage size limit per plugin in MB"""
        return self.get('plugins.max_storage_size_mb', 100)
    
    def get_plugin_task_timeout(self) -> int:
        """Get maximum task execution timeout in seconds"""
        return self.get('plugins.task_timeout', 300)
    
    def export_config(self, file_path: str) -> None:
        """Export current configuration to file"""
        path = Path(file_path)
        
        try:
            with open(path, 'w') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(self.config, f, default_flow_style=False, indent=2)
                elif path.suffix.lower() == '.json':
                    json.dump(self.config, f, indent=2)
                else:
                    raise ValueError(f"Unsupported file format: {path.suffix}")
            
            self.logger.info(f"Configuration exported to {path}")
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            raise ConfigurationError(f"Export failed: {e}")


# Global configuration manager instance
config_manager = ConfigurationManager()