"""
File and Sensor Monitoring Services

Provides file change monitoring with broadcasting and external sensor
integration framework for environmental monitoring.
"""

import asyncio
import json
import logging
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any, Union
from dataclasses import dataclass, field
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Create dummy classes for when watchdog is not available
    class FileSystemEventHandler:
        pass
    
    class FileSystemEvent:
        def __init__(self):
            self.src_path = ""
            self.event_type = ""
            self.is_directory = False
    
    class Observer:
        def schedule(self, handler, path, recursive=False):
            pass
        
        def start(self):
            pass
        
        def stop(self):
            pass
        
        def join(self, timeout=None):
            pass

from .models import EnvironmentalReading, Location


@dataclass
class FileChangeEvent:
    """File change event data"""
    file_path: str
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    timestamp: datetime = field(default_factory=datetime.utcnow)
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    old_path: Optional[str] = None  # For move events
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorConfig:
    """External sensor configuration"""
    sensor_id: str
    sensor_type: str
    connection_type: str  # 'serial', 'tcp', 'http', 'mqtt'
    connection_params: Dict[str, Any] = field(default_factory=dict)
    poll_interval: int = 60  # seconds
    enabled: bool = True
    location: Optional[Location] = None
    thresholds: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FileMonitorHandler(FileSystemEventHandler):
    """File system event handler for watchdog"""
    
    def __init__(self, file_monitor: 'FileMonitor'):
        self.file_monitor = file_monitor
        self.logger = logging.getLogger(__name__)
    
    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event"""
        if event.is_directory:
            return
        
        try:
            self.file_monitor._handle_file_event(event)
        except Exception as e:
            self.logger.error(f"Error handling file event: {e}")


class FileMonitor:
    """
    File change monitoring system with broadcasting capabilities
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Monitoring configuration
        self.enabled = config.get('enabled', False)
        self.watch_paths = config.get('watch_paths', [])
        self.watch_patterns = config.get('watch_patterns', ['*'])
        self.ignore_patterns = config.get('ignore_patterns', ['*.tmp', '*.log'])
        self.broadcast_changes = config.get('broadcast_changes', True)
        self.max_file_size = config.get('max_file_size_mb', 10) * 1024 * 1024
        
        # File monitoring state
        self.observers: List[Observer] = []
        self.monitored_files: Dict[str, Dict[str, Any]] = {}
        self.recent_events: List[FileChangeEvent] = []
        self.max_recent_events = 100
        
        # Callbacks
        self.change_callbacks: List[Callable[[FileChangeEvent], None]] = []
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start file monitoring"""
        if not self.enabled or self.running:
            return
        
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Watchdog not available, file monitoring disabled")
            return
        
        self.running = True
        
        # Set up file watchers
        for watch_path in self.watch_paths:
            try:
                path = Path(watch_path)
                if path.exists():
                    observer = Observer()
                    handler = FileMonitorHandler(self)
                    observer.schedule(handler, str(path), recursive=True)
                    observer.start()
                    self.observers.append(observer)
                    self.logger.info(f"Started monitoring {watch_path}")
                else:
                    self.logger.warning(f"Watch path does not exist: {watch_path}")
            except Exception as e:
                self.logger.error(f"Failed to start monitoring {watch_path}: {e}")
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("File monitor started")
    
    async def stop(self):
        """Stop file monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop observers
        for observer in self.observers:
            try:
                observer.stop()
                observer.join(timeout=5)
            except Exception as e:
                self.logger.error(f"Error stopping file observer: {e}")
        
        self.observers.clear()
        
        # Stop cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("File monitor stopped")
    
    def add_change_callback(self, callback: Callable[[FileChangeEvent], None]):
        """Add callback for file change events"""
        self.change_callbacks.append(callback)
    
    def _handle_file_event(self, event: FileSystemEvent):
        """Handle file system event from watchdog"""
        try:
            # Filter by patterns
            if not self._should_monitor_file(event.src_path):
                return
            
            # Determine event type
            event_type = 'unknown'
            if event.event_type == 'created':
                event_type = 'created'
            elif event.event_type == 'modified':
                event_type = 'modified'
            elif event.event_type == 'deleted':
                event_type = 'deleted'
            elif event.event_type == 'moved':
                event_type = 'moved'
            
            # Get file information
            file_size = None
            file_hash = None
            
            if event_type != 'deleted' and os.path.exists(event.src_path):
                try:
                    stat = os.stat(event.src_path)
                    file_size = stat.st_size
                    
                    # Calculate hash for small files
                    if file_size <= self.max_file_size:
                        file_hash = self._calculate_file_hash(event.src_path)
                except Exception as e:
                    self.logger.warning(f"Failed to get file info for {event.src_path}: {e}")
            
            # Create change event
            change_event = FileChangeEvent(
                file_path=event.src_path,
                event_type=event_type,
                file_size=file_size,
                file_hash=file_hash,
                old_path=getattr(event, 'dest_path', None),
                metadata={
                    'watchdog_event_type': event.event_type,
                    'is_directory': event.is_directory
                }
            )
            
            # Store recent event
            self.recent_events.append(change_event)
            if len(self.recent_events) > self.max_recent_events:
                self.recent_events.pop(0)
            
            # Update monitored files
            self._update_monitored_file(change_event)
            
            # Trigger callbacks
            for callback in self.change_callbacks:
                try:
                    callback(change_event)
                except Exception as e:
                    self.logger.error(f"Error in file change callback: {e}")
            
            self.logger.debug(f"File {event_type}: {event.src_path}")
            
        except Exception as e:
            self.logger.error(f"Error handling file event: {e}")
    
    def _should_monitor_file(self, file_path: str) -> bool:
        """Check if file should be monitored based on patterns"""
        import fnmatch
        
        file_name = os.path.basename(file_path)
        
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return False
        
        # Check watch patterns
        if not self.watch_patterns or '*' in self.watch_patterns:
            return True
        
        for pattern in self.watch_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True
        
        return False
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def _update_monitored_file(self, change_event: FileChangeEvent):
        """Update monitored file information"""
        file_path = change_event.file_path
        
        if change_event.event_type == 'deleted':
            # Remove from monitored files
            if file_path in self.monitored_files:
                del self.monitored_files[file_path]
        else:
            # Update or add file info
            self.monitored_files[file_path] = {
                'last_modified': change_event.timestamp,
                'size': change_event.file_size,
                'hash': change_event.file_hash,
                'event_count': self.monitored_files.get(file_path, {}).get('event_count', 0) + 1
            }
    
    async def _cleanup_loop(self):
        """Background cleanup task"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in file monitor cleanup: {e}")
    
    async def _cleanup_old_events(self):
        """Clean up old events"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Remove old events
        self.recent_events = [
            event for event in self.recent_events
            if event.timestamp > cutoff_time
        ]
        
        self.logger.debug(f"File monitor cleanup: {len(self.recent_events)} events retained")
    
    def get_recent_events(self, hours_back: int = 1) -> List[FileChangeEvent]:
        """Get recent file change events"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        return [
            event for event in self.recent_events
            if event.timestamp > cutoff_time
        ]
    
    def get_monitored_files(self) -> Dict[str, Dict[str, Any]]:
        """Get currently monitored files"""
        return self.monitored_files.copy()


class SensorInterface:
    """Base class for sensor interfaces"""
    
    def __init__(self, config: SensorConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to sensor"""
        raise NotImplementedError
    
    async def disconnect(self):
        """Disconnect from sensor"""
        raise NotImplementedError
    
    async def read_data(self) -> Optional[EnvironmentalReading]:
        """Read data from sensor"""
        raise NotImplementedError
    
    def validate_reading(self, reading: EnvironmentalReading) -> bool:
        """Validate sensor reading"""
        # Basic validation - override in subclasses
        return reading.readings is not None and len(reading.readings) > 0


class SerialSensorInterface(SensorInterface):
    """Serial sensor interface"""
    
    def __init__(self, config: SensorConfig):
        super().__init__(config)
        self.serial_connection = None
    
    async def connect(self) -> bool:
        """Connect to serial sensor"""
        try:
            import serial_asyncio
            
            port = self.config.connection_params.get('port', '/dev/ttyUSB0')
            baudrate = self.config.connection_params.get('baudrate', 9600)
            timeout = self.config.connection_params.get('timeout', 1.0)
            
            self.serial_connection = await serial_asyncio.open_serial_connection(
                url=port,
                baudrate=baudrate,
                timeout=timeout
            )
            
            self.connected = True
            self.logger.info(f"Connected to serial sensor {self.config.sensor_id} on {port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to serial sensor {self.config.sensor_id}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from serial sensor"""
        if self.serial_connection:
            try:
                self.serial_connection[1].close()
                await self.serial_connection[1].wait_closed()
            except Exception as e:
                self.logger.error(f"Error disconnecting serial sensor: {e}")
        
        self.connected = False
    
    async def read_data(self) -> Optional[EnvironmentalReading]:
        """Read data from serial sensor"""
        if not self.connected or not self.serial_connection:
            return None
        
        try:
            reader, writer = self.serial_connection
            
            # Send read command if specified
            read_command = self.config.connection_params.get('read_command')
            if read_command:
                writer.write(read_command.encode())
                await writer.drain()
            
            # Read response
            data = await reader.readline()
            response = data.decode().strip()
            
            # Parse response (this is sensor-specific)
            readings = self._parse_sensor_data(response)
            
            if readings:
                reading = EnvironmentalReading(
                    sensor_id=self.config.sensor_id,
                    sensor_type=self.config.sensor_type,
                    location=self.config.location,
                    readings=readings,
                    metadata={
                        'connection_type': 'serial',
                        'raw_data': response
                    }
                )
                
                return reading
            
        except Exception as e:
            self.logger.error(f"Failed to read from serial sensor {self.config.sensor_id}: {e}")
        
        return None
    
    def _parse_sensor_data(self, data: str) -> Dict[str, float]:
        """Parse sensor data - override in specific sensor implementations"""
        # Default implementation tries to parse JSON
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return {k: float(v) for k, v in parsed.items() if isinstance(v, (int, float))}
        except:
            pass
        
        # Try to parse comma-separated values
        try:
            values = data.split(',')
            readings = {}
            for i, value in enumerate(values):
                try:
                    readings[f'value_{i}'] = float(value.strip())
                except ValueError:
                    continue
            return readings
        except:
            pass
        
        return {}


class HTTPSensorInterface(SensorInterface):
    """HTTP sensor interface"""
    
    def __init__(self, config: SensorConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self) -> bool:
        """Connect to HTTP sensor"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(
                total=self.config.connection_params.get('timeout', 30)
            )
            
            self.session = aiohttp.ClientSession(timeout=timeout)
            self.connected = True
            
            self.logger.info(f"Connected to HTTP sensor {self.config.sensor_id}")
            return True
            
        except ImportError:
            self.logger.error(f"aiohttp not available for HTTP sensor {self.config.sensor_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to HTTP sensor {self.config.sensor_id}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from HTTP sensor"""
        if self.session:
            await self.session.close()
        self.connected = False
    
    async def read_data(self) -> Optional[EnvironmentalReading]:
        """Read data from HTTP sensor"""
        if not self.connected or not self.session:
            return None
        
        try:
            url = self.config.connection_params.get('url')
            method = self.config.connection_params.get('method', 'GET')
            headers = self.config.connection_params.get('headers', {})
            
            if not url:
                self.logger.error(f"No URL configured for HTTP sensor {self.config.sensor_id}")
                return None
            
            async with self.session.request(method, url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    readings = self._parse_sensor_data(data)
                    
                    if readings:
                        reading = EnvironmentalReading(
                            sensor_id=self.config.sensor_id,
                            sensor_type=self.config.sensor_type,
                            location=self.config.location,
                            readings=readings,
                            metadata={
                                'connection_type': 'http',
                                'url': url,
                                'status_code': response.status
                            }
                        )
                        
                        return reading
                else:
                    self.logger.warning(f"HTTP sensor {self.config.sensor_id} returned status {response.status}")
            
        except Exception as e:
            self.logger.error(f"Failed to read from HTTP sensor {self.config.sensor_id}: {e}")
        
        return None
    
    def _parse_sensor_data(self, data: Any) -> Dict[str, float]:
        """Parse HTTP sensor data"""
        readings = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    readings[key] = float(value)
                elif isinstance(value, dict):
                    # Flatten nested dictionaries
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, (int, float)):
                            readings[f"{key}_{nested_key}"] = float(nested_value)
        
        return readings


class SensorManager:
    """
    External sensor integration framework
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Sensor configuration
        self.enabled = config.get('enabled', False)
        self.sensors: Dict[str, SensorInterface] = {}
        self.sensor_configs: Dict[str, SensorConfig] = {}
        
        # Monitoring state
        self.running = False
        self.poll_tasks: Dict[str, asyncio.Task] = {}
        
        # Callbacks
        self.reading_callbacks: List[Callable[[EnvironmentalReading], None]] = []
        self.alert_callbacks: List[Callable[[EnvironmentalReading], None]] = []
        
        # Load sensor configurations
        self._load_sensor_configs()
    
    def _load_sensor_configs(self):
        """Load sensor configurations"""
        sensors_config = self.config.get('sensors', [])
        
        for sensor_config in sensors_config:
            try:
                config = SensorConfig(
                    sensor_id=sensor_config['sensor_id'],
                    sensor_type=sensor_config['sensor_type'],
                    connection_type=sensor_config['connection_type'],
                    connection_params=sensor_config.get('connection_params', {}),
                    poll_interval=sensor_config.get('poll_interval', 60),
                    enabled=sensor_config.get('enabled', True),
                    location=self._parse_location(sensor_config.get('location')),
                    thresholds=sensor_config.get('thresholds', {}),
                    metadata=sensor_config.get('metadata', {})
                )
                
                self.sensor_configs[config.sensor_id] = config
                
            except Exception as e:
                self.logger.error(f"Failed to load sensor config: {e}")
    
    def _parse_location(self, location_config: Optional[Dict[str, Any]]) -> Optional[Location]:
        """Parse location from configuration"""
        if not location_config:
            return None
        
        return Location(
            latitude=location_config.get('latitude', 0.0),
            longitude=location_config.get('longitude', 0.0),
            name=location_config.get('name')
        )
    
    async def start(self):
        """Start sensor monitoring"""
        if not self.enabled or self.running:
            return
        
        self.running = True
        
        # Initialize and connect sensors
        for sensor_id, config in self.sensor_configs.items():
            if not config.enabled:
                continue
            
            try:
                # Create sensor interface
                if config.connection_type == 'serial':
                    sensor = SerialSensorInterface(config)
                elif config.connection_type == 'http':
                    sensor = HTTPSensorInterface(config)
                else:
                    self.logger.warning(f"Unsupported sensor connection type: {config.connection_type}")
                    continue
                
                # Connect to sensor
                if await sensor.connect():
                    self.sensors[sensor_id] = sensor
                    
                    # Start polling task
                    self.poll_tasks[sensor_id] = asyncio.create_task(
                        self._sensor_poll_loop(sensor_id)
                    )
                    
                    self.logger.info(f"Started monitoring sensor {sensor_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to start sensor {sensor_id}: {e}")
        
        self.logger.info("Sensor manager started")
    
    async def stop(self):
        """Stop sensor monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop polling tasks
        for task in self.poll_tasks.values():
            task.cancel()
        
        if self.poll_tasks:
            await asyncio.gather(*self.poll_tasks.values(), return_exceptions=True)
        
        self.poll_tasks.clear()
        
        # Disconnect sensors
        for sensor in self.sensors.values():
            try:
                await sensor.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting sensor: {e}")
        
        self.sensors.clear()
        
        self.logger.info("Sensor manager stopped")
    
    def add_reading_callback(self, callback: Callable[[EnvironmentalReading], None]):
        """Add callback for sensor readings"""
        self.reading_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable[[EnvironmentalReading], None]):
        """Add callback for sensor alerts"""
        self.alert_callbacks.append(callback)
    
    async def _sensor_poll_loop(self, sensor_id: str):
        """Polling loop for a specific sensor"""
        sensor = self.sensors.get(sensor_id)
        config = self.sensor_configs.get(sensor_id)
        
        if not sensor or not config:
            return
        
        while self.running:
            try:
                # Read sensor data
                reading = await sensor.read_data()
                
                if reading and sensor.validate_reading(reading):
                    # Trigger reading callbacks
                    for callback in self.reading_callbacks:
                        try:
                            callback(reading)
                        except Exception as e:
                            self.logger.error(f"Error in reading callback: {e}")
                    
                    # Check thresholds for alerts
                    if self._check_thresholds(reading, config):
                        for callback in self.alert_callbacks:
                            try:
                                callback(reading)
                            except Exception as e:
                                self.logger.error(f"Error in alert callback: {e}")
                
                await asyncio.sleep(config.poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in sensor poll loop for {sensor_id}: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def _check_thresholds(self, reading: EnvironmentalReading, config: SensorConfig) -> bool:
        """Check if reading exceeds configured thresholds"""
        if not config.thresholds:
            return False
        
        for param, threshold in config.thresholds.items():
            if reading.is_threshold_exceeded(param, threshold, 'greater'):
                return True
        
        return False
    
    def get_sensor_readings(self) -> List[EnvironmentalReading]:
        """Get latest readings from all sensors"""
        # This would typically return cached readings
        # For now, return empty list as readings are handled via callbacks
        return []
    
    def get_sensor_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all sensors"""
        status = {}
        
        for sensor_id, sensor in self.sensors.items():
            config = self.sensor_configs.get(sensor_id)
            status[sensor_id] = {
                'connected': sensor.connected,
                'sensor_type': config.sensor_type if config else 'unknown',
                'connection_type': config.connection_type if config else 'unknown',
                'enabled': config.enabled if config else False
            }
        
        return status


class FileSensorMonitoringService:
    """
    Combined file and sensor monitoring service
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize components
        self.file_monitor = FileMonitor(config.get('file_monitoring', {}))
        self.sensor_manager = SensorManager(config.get('sensor_monitoring', {}))
        
        # Service state
        self.running = False
        
        # Callbacks
        self.alert_callbacks: List[Callable[[Any], None]] = []
    
    async def start(self):
        """Start file and sensor monitoring"""
        if self.running:
            return
        
        self.running = True
        
        # Set up callbacks
        self.file_monitor.add_change_callback(self._handle_file_change)
        self.sensor_manager.add_reading_callback(self._handle_sensor_reading)
        self.sensor_manager.add_alert_callback(self._handle_sensor_alert)
        
        # Start components
        await asyncio.gather(
            self.file_monitor.start(),
            self.sensor_manager.start(),
            return_exceptions=True
        )
        
        self.logger.info("File and sensor monitoring service started")
    
    async def stop(self):
        """Stop file and sensor monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop components
        await asyncio.gather(
            self.file_monitor.stop(),
            self.sensor_manager.stop(),
            return_exceptions=True
        )
        
        self.logger.info("File and sensor monitoring service stopped")
    
    def add_alert_callback(self, callback: Callable[[Any], None]):
        """Add alert callback"""
        self.alert_callbacks.append(callback)
    
    def _handle_file_change(self, change_event: FileChangeEvent):
        """Handle file change events"""
        self.logger.info(f"File {change_event.event_type}: {change_event.file_path}")
        
        # Broadcast to alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(change_event)
            except Exception as e:
                self.logger.error(f"Error in file change alert callback: {e}")
    
    def _handle_sensor_reading(self, reading: EnvironmentalReading):
        """Handle sensor readings"""
        self.logger.debug(f"Sensor reading from {reading.sensor_id}: {reading.readings}")
    
    def _handle_sensor_alert(self, reading: EnvironmentalReading):
        """Handle sensor alerts"""
        self.logger.info(f"Sensor alert from {reading.sensor_id}: {reading.readings}")
        
        # Broadcast to alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(reading)
            except Exception as e:
                self.logger.error(f"Error in sensor alert callback: {e}")
    
    def get_recent_file_changes(self, hours_back: int = 1) -> List[FileChangeEvent]:
        """Get recent file changes"""
        return self.file_monitor.get_recent_events(hours_back)
    
    def get_sensor_readings(self) -> List[EnvironmentalReading]:
        """Get sensor readings"""
        return self.sensor_manager.get_sensor_readings()
    
    def get_sensor_status(self) -> Dict[str, Dict[str, Any]]:
        """Get sensor status"""
        return self.sensor_manager.get_sensor_status()
    
    def get_monitored_files(self) -> Dict[str, Dict[str, Any]]:
        """Get monitored files"""
        return self.file_monitor.get_monitored_files()