"""
Logging Configuration for ZephyrGate

Provides centralized logging setup with structured logging,
file rotation, and service-specific log levels.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Optional
import structlog
from datetime import datetime


class ZephyrGateLogger:
    """
    Centralized logging configuration for ZephyrGate
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging configuration"""
        # Get logging configuration
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO').upper()
        log_file = log_config.get('file', 'logs/zephyrgate.log')
        max_size = log_config.get('max_size', '10MB')
        backup_count = log_config.get('backup_count', 5)
        console_enabled = log_config.get('console', True)
        console_level = log_config.get('console_level', 'INFO').upper()
        
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # File handler with rotation
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self._parse_size(max_size),
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(getattr(logging, log_level))
            root_logger.addHandler(file_handler)
        
        # Console handler
        if console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(getattr(logging, console_level))
            root_logger.addHandler(console_handler)
        
        # Configure service-specific log levels
        service_levels = log_config.get('services', {})
        for service, level in service_levels.items():
            service_logger = logging.getLogger(f'zephyrgate.{service}')
            service_logger.setLevel(getattr(logging, level.upper()))
        
        # Suppress noisy third-party loggers
        self._configure_third_party_loggers()
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def _configure_third_party_loggers(self):
        """Configure third-party library loggers to reduce noise"""
        # Suppress verbose loggers
        noisy_loggers = [
            'urllib3.connectionpool',
            'requests.packages.urllib3',
            'asyncio',
            'aiohttp.access',
            'websockets.protocol',
            'meshtastic.serial_interface',
        ]
        
        for logger_name in noisy_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger for a specific component"""
        if name not in self.loggers:
            # Create logger with ZephyrGate prefix
            full_name = f'zephyrgate.{name}' if not name.startswith('zephyrgate') else name
            self.loggers[name] = logging.getLogger(full_name)
        
        return self.loggers[name]
    
    def get_structured_logger(self, name: str) -> structlog.BoundLogger:
        """Get a structured logger for a specific component"""
        return structlog.get_logger(f'zephyrgate.{name}')


# Global logger instance
_logger_instance: Optional[ZephyrGateLogger] = None


def initialize_logging(config: Dict) -> ZephyrGateLogger:
    """Initialize the global logging system"""
    global _logger_instance
    _logger_instance = ZephyrGateLogger(config)
    return _logger_instance


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    if _logger_instance is None:
        # Fallback to basic logging if not initialized
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(f'zephyrgate.{name}')
    
    return _logger_instance.get_logger(name)


def get_structured_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    if _logger_instance is None:
        # Initialize with minimal config
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    return structlog.get_logger(f'zephyrgate.{name}')


class LogContext:
    """Context manager for adding structured logging context"""
    
    def __init__(self, logger: structlog.BoundLogger, **context):
        self.logger = logger
        self.context = context
        self.bound_logger = None
    
    def __enter__(self):
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def log_function_call(logger: logging.Logger):
    """Decorator to log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed with error: {e}")
                raise
        return wrapper
    return decorator


def log_async_function_call(logger: logging.Logger):
    """Decorator to log async function calls"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Async {func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"Async {func.__name__} failed with error: {e}")
                raise
        return wrapper
    return decorator