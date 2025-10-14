"""
System Health Monitoring for ZephyrGate

Comprehensive health monitoring system that tracks:
- Service health and performance
- System resource usage
- Message processing metrics
- Error rates and patterns
- Performance bottlenecks
"""

import asyncio
import logging
import psutil
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import json

from .logging import get_logger


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Individual health metric"""
    name: str
    value: float
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: HealthStatus = HealthStatus.HEALTHY
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    description: str = ""
    
    def evaluate_status(self) -> HealthStatus:
        """Evaluate health status based on thresholds"""
        if self.threshold_critical is not None and self.value >= self.threshold_critical:
            self.status = HealthStatus.CRITICAL
        elif self.threshold_warning is not None and self.value >= self.threshold_warning:
            self.status = HealthStatus.WARNING
        else:
            self.status = HealthStatus.HEALTHY
        
        return self.status


@dataclass
class HealthAlert:
    """Health monitoring alert"""
    id: str
    severity: AlertSeverity
    source: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceHealth:
    """Health information for a service"""
    service_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    response_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    uptime: timedelta = field(default_factory=timedelta)
    metrics: Dict[str, HealthMetric] = field(default_factory=dict)
    alerts: List[HealthAlert] = field(default_factory=list)
    
    def get_error_rate(self) -> float:
        """Calculate error rate percentage"""
        total = self.error_count + self.success_count
        return (self.error_count / total * 100) if total > 0 else 0.0
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.error_count + self.success_count
        return (self.success_count / total * 100) if total > 0 else 0.0


@dataclass
class SystemHealth:
    """Overall system health information"""
    status: HealthStatus = HealthStatus.HEALTHY
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, float] = field(default_factory=dict)
    uptime: timedelta = field(default_factory=timedelta)
    load_average: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    active_connections: int = 0
    message_queue_size: int = 0
    
    def evaluate_status(self) -> HealthStatus:
        """Evaluate overall system health"""
        if (self.cpu_usage > 90 or self.memory_usage > 90 or 
            self.disk_usage > 95 or self.message_queue_size > 1000):
            self.status = HealthStatus.CRITICAL
        elif (self.cpu_usage > 70 or self.memory_usage > 70 or 
              self.disk_usage > 80 or self.message_queue_size > 500):
            self.status = HealthStatus.WARNING
        else:
            self.status = HealthStatus.HEALTHY
        
        return self.status


class PerformanceTracker:
    """Track performance metrics over time"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self.logger = get_logger('performance_tracker')
    
    def record_metric(self, name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a performance metric"""
        timestamp = timestamp or datetime.utcnow()
        self.metrics[name].append((timestamp, value))
    
    def get_metric_history(self, name: str, duration: Optional[timedelta] = None) -> List[Tuple[datetime, float]]:
        """Get metric history for a specific duration"""
        if name not in self.metrics:
            return []
        
        if duration is None:
            return list(self.metrics[name])
        
        cutoff_time = datetime.utcnow() - duration
        return [(ts, val) for ts, val in self.metrics[name] if ts >= cutoff_time]
    
    def get_metric_stats(self, name: str, duration: Optional[timedelta] = None) -> Dict[str, float]:
        """Get statistical summary of a metric"""
        history = self.get_metric_history(name, duration)
        
        if not history:
            return {}
        
        values = [val for _, val in history]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else 0.0
        }
    
    def detect_anomalies(self, name: str, threshold_multiplier: float = 2.0) -> List[Tuple[datetime, float]]:
        """Detect anomalies in metric data"""
        history = self.get_metric_history(name, timedelta(hours=1))
        
        if len(history) < 10:
            return []
        
        values = [val for _, val in history]
        avg = sum(values) / len(values)
        
        # Simple anomaly detection based on deviation from average
        threshold = avg * threshold_multiplier
        
        anomalies = []
        for ts, val in history:
            if val > threshold:
                anomalies.append((ts, val))
        
        return anomalies


class HealthMonitor:
    """
    Comprehensive system health monitoring
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = get_logger('health_monitor')
        
        # Health tracking
        self.system_health = SystemHealth()
        self.service_health: Dict[str, ServiceHealth] = {}
        self.alerts: List[HealthAlert] = []
        self.performance_tracker = PerformanceTracker()
        
        # Monitoring configuration
        self.check_interval = self.config.get('check_interval', 30)  # seconds
        self.alert_cooldown = self.config.get('alert_cooldown', 300)  # seconds
        self.max_alerts = self.config.get('max_alerts', 100)
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[HealthAlert], None]] = []
        
        # Monitoring state
        self.monitoring_task: Optional[asyncio.Task] = None
        self.start_time = datetime.utcnow()
        self.last_alert_times: Dict[str, datetime] = {}
        
        # System resource monitoring
        self.process = psutil.Process()
        
        self.logger.info("Health monitor initialized")
    
    async def start(self):
        """Start health monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.logger.warning("Health monitoring already running")
            return
        
        self.logger.info("Starting health monitoring")
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop health monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Update system health
                await self._update_system_health()
                
                # Update service health
                await self._update_service_health()
                
                # Check for alerts
                await self._check_alerts()
                
                # Clean up old data
                await self._cleanup_old_data()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
    
    async def _update_system_health(self):
        """Update system-level health metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_health.cpu_usage = cpu_percent
            self.performance_tracker.record_metric('cpu_usage', cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self.system_health.memory_usage = memory_percent
            self.performance_tracker.record_metric('memory_usage', memory_percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_health.disk_usage = disk_percent
            self.performance_tracker.record_metric('disk_usage', disk_percent)
            
            # Network I/O
            net_io = psutil.net_io_counters()
            self.system_health.network_io = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
            
            # Load average (Unix-like systems)
            try:
                self.system_health.load_average = psutil.getloadavg()
            except AttributeError:
                # Windows doesn't have load average
                pass
            
            # Uptime
            self.system_health.uptime = datetime.utcnow() - self.start_time
            
            # Evaluate overall system status
            self.system_health.evaluate_status()
            
        except Exception as e:
            self.logger.error(f"Error updating system health: {e}")
    
    async def _update_service_health(self):
        """Update health for all registered services"""
        for service_name, service_health in self.service_health.items():
            try:
                # Check if service is responsive
                start_time = time.time()
                
                # This would be implemented by each service
                # For now, we'll simulate a health check
                is_healthy = await self._check_service_health(service_name)
                
                response_time = time.time() - start_time
                service_health.response_time = response_time
                service_health.last_heartbeat = datetime.utcnow()
                
                if is_healthy:
                    service_health.status = HealthStatus.HEALTHY
                    service_health.success_count += 1
                else:
                    service_health.status = HealthStatus.CRITICAL
                    service_health.error_count += 1
                
                # Record performance metrics
                self.performance_tracker.record_metric(
                    f'service_{service_name}_response_time', 
                    response_time
                )
                
            except Exception as e:
                self.logger.error(f"Error updating health for service {service_name}: {e}")
                service_health.status = HealthStatus.CRITICAL
                service_health.error_count += 1
    
    async def _check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        # This is a placeholder - actual implementation would depend on service interfaces
        # Services should implement a health_check method
        return True
    
    async def _check_alerts(self):
        """Check for alert conditions and generate alerts"""
        # System-level alerts
        await self._check_system_alerts()
        
        # Service-level alerts
        await self._check_service_alerts()
        
        # Performance anomaly alerts
        await self._check_performance_alerts()
    
    async def _check_system_alerts(self):
        """Check for system-level alert conditions"""
        # High CPU usage
        if self.system_health.cpu_usage > 90:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "system",
                f"High CPU usage: {self.system_health.cpu_usage:.1f}%"
            )
        elif self.system_health.cpu_usage > 70:
            await self._create_alert(
                AlertSeverity.WARNING,
                "system",
                f"Elevated CPU usage: {self.system_health.cpu_usage:.1f}%"
            )
        
        # High memory usage
        if self.system_health.memory_usage > 90:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "system",
                f"High memory usage: {self.system_health.memory_usage:.1f}%"
            )
        elif self.system_health.memory_usage > 70:
            await self._create_alert(
                AlertSeverity.WARNING,
                "system",
                f"Elevated memory usage: {self.system_health.memory_usage:.1f}%"
            )
        
        # High disk usage
        if self.system_health.disk_usage > 95:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "system",
                f"Critical disk usage: {self.system_health.disk_usage:.1f}%"
            )
        elif self.system_health.disk_usage > 80:
            await self._create_alert(
                AlertSeverity.WARNING,
                "system",
                f"High disk usage: {self.system_health.disk_usage:.1f}%"
            )
    
    async def _check_service_alerts(self):
        """Check for service-level alert conditions"""
        for service_name, service_health in self.service_health.items():
            # Service down
            if service_health.status == HealthStatus.CRITICAL:
                await self._create_alert(
                    AlertSeverity.CRITICAL,
                    service_name,
                    f"Service {service_name} is not responding"
                )
            
            # High error rate
            error_rate = service_health.get_error_rate()
            if error_rate > 50:
                await self._create_alert(
                    AlertSeverity.ERROR,
                    service_name,
                    f"High error rate for {service_name}: {error_rate:.1f}%"
                )
            elif error_rate > 20:
                await self._create_alert(
                    AlertSeverity.WARNING,
                    service_name,
                    f"Elevated error rate for {service_name}: {error_rate:.1f}%"
                )
            
            # Slow response time
            if service_health.response_time > 5.0:
                await self._create_alert(
                    AlertSeverity.WARNING,
                    service_name,
                    f"Slow response time for {service_name}: {service_health.response_time:.2f}s"
                )
    
    async def _check_performance_alerts(self):
        """Check for performance anomalies"""
        # Check for CPU usage spikes
        cpu_anomalies = self.performance_tracker.detect_anomalies('cpu_usage')
        if cpu_anomalies:
            latest_anomaly = cpu_anomalies[-1]
            await self._create_alert(
                AlertSeverity.WARNING,
                "performance",
                f"CPU usage spike detected: {latest_anomaly[1]:.1f}%"
            )
        
        # Check for memory usage spikes
        memory_anomalies = self.performance_tracker.detect_anomalies('memory_usage')
        if memory_anomalies:
            latest_anomaly = memory_anomalies[-1]
            await self._create_alert(
                AlertSeverity.WARNING,
                "performance",
                f"Memory usage spike detected: {latest_anomaly[1]:.1f}%"
            )
    
    async def _create_alert(self, severity: AlertSeverity, source: str, message: str, metadata: Dict[str, Any] = None):
        """Create a new alert with cooldown logic"""
        alert_key = f"{source}:{message}"
        
        # Check cooldown
        if alert_key in self.last_alert_times:
            time_since_last = datetime.utcnow() - self.last_alert_times[alert_key]
            if time_since_last.total_seconds() < self.alert_cooldown:
                return  # Skip alert due to cooldown
        
        # Create alert
        alert = HealthAlert(
            id=f"{int(datetime.utcnow().timestamp())}_{source}",
            severity=severity,
            source=source,
            message=message,
            metadata=metadata or {}
        )
        
        # Add to alerts list
        self.alerts.append(alert)
        self.last_alert_times[alert_key] = datetime.utcnow()
        
        # Maintain max alerts limit
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
        
        self.logger.warning(f"Health alert [{severity.value}] {source}: {message}")
    
    async def _cleanup_old_data(self):
        """Clean up old alerts and metrics"""
        # Remove old alerts (keep last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.alerts = [alert for alert in self.alerts if alert.timestamp >= cutoff_time]
        
        # Clean up old alert cooldown entries
        expired_keys = [
            key for key, timestamp in self.last_alert_times.items()
            if datetime.utcnow() - timestamp > timedelta(hours=1)
        ]
        for key in expired_keys:
            del self.last_alert_times[key]
    
    def register_service(self, service_name: str):
        """Register a service for health monitoring"""
        if service_name not in self.service_health:
            self.service_health[service_name] = ServiceHealth(service_name=service_name)
            self.logger.info(f"Registered service for health monitoring: {service_name}")
    
    def unregister_service(self, service_name: str):
        """Unregister a service from health monitoring"""
        if service_name in self.service_health:
            del self.service_health[service_name]
            self.logger.info(f"Unregistered service from health monitoring: {service_name}")
    
    def add_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """Add a callback for alert notifications"""
        self.alert_callbacks.append(callback)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'system_health': {
                'status': self.system_health.status.value,
                'cpu_usage': self.system_health.cpu_usage,
                'memory_usage': self.system_health.memory_usage,
                'disk_usage': self.system_health.disk_usage,
                'uptime_seconds': self.system_health.uptime.total_seconds(),
                'load_average': self.system_health.load_average
            },
            'services': {
                name: {
                    'status': health.status.value,
                    'error_rate': health.get_error_rate(),
                    'success_rate': health.get_success_rate(),
                    'response_time': health.response_time,
                    'uptime_seconds': health.uptime.total_seconds()
                }
                for name, health in self.service_health.items()
            },
            'alerts': {
                'total': len(self.alerts),
                'critical': len([a for a in self.alerts if a.severity == AlertSeverity.CRITICAL]),
                'error': len([a for a in self.alerts if a.severity == AlertSeverity.ERROR]),
                'warning': len([a for a in self.alerts if a.severity == AlertSeverity.WARNING]),
                'recent': [
                    {
                        'severity': alert.severity.value,
                        'source': alert.source,
                        'message': alert.message,
                        'timestamp': alert.timestamp.isoformat()
                    }
                    for alert in self.alerts[-10:]  # Last 10 alerts
                ]
            }
        }
    
    def get_performance_metrics(self, duration: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get performance metrics for a specific duration"""
        duration = duration or timedelta(hours=1)
        
        metrics = {}
        for metric_name in ['cpu_usage', 'memory_usage', 'disk_usage']:
            stats = self.performance_tracker.get_metric_stats(metric_name, duration)
            if stats:
                metrics[metric_name] = stats
        
        return metrics
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self.logger.info(f"Alert {alert_id} acknowledged")
                return True
        
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                self.logger.info(f"Alert {alert_id} resolved")
                return True
        
        return False