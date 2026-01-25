"""
System Monitoring Module for Web Administration

Provides real-time system monitoring, node tracking, and health metrics.
"""

import asyncio
import json
import logging
import psutil
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    from ...models.message import Message
except ImportError:
    from models.message import Message


logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_total: int
    disk_percent: float
    disk_used: int
    disk_total: int
    network_sent: int
    network_recv: int
    uptime: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NodeStatus:
    """Node status information"""
    node_id: str
    short_name: str
    long_name: str
    hardware: str
    role: str
    battery_level: Optional[int] = None
    voltage: Optional[float] = None
    snr: Optional[float] = None
    rssi: Optional[float] = None
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    location: Optional[Dict[str, float]] = None
    is_online: bool = True
    hops_away: int = 0


@dataclass
class AlertInfo:
    """Alert/incident information"""
    id: str
    type: str
    severity: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class ServiceStatus:
    """Service status information"""
    name: str
    status: str  # running, stopped, error
    uptime: int
    last_restart: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None


class SystemMonitor:
    """
    System monitoring service that tracks system health,
    node status, and active alerts.
    """
    
    def __init__(self, plugin_manager=None):
        self.plugin_manager = plugin_manager
        self.logger = logger
        
        # Monitoring data
        self.system_metrics: List[SystemMetrics] = []
        self.nodes: Dict[str, NodeStatus] = {}
        self.alerts: Dict[str, AlertInfo] = {}
        self.services: Dict[str, ServiceStatus] = {}
        
        # Configuration
        self.metrics_history_limit = 100
        self.node_timeout = 300  # 5 minutes
        self.metrics_interval = 30  # 30 seconds
        
        # Monitoring tasks
        self.monitoring_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Network statistics baseline
        self.network_stats_baseline = None
        self.start_time = time.time()
        
        self.logger.info("SystemMonitor initialized")
    
    async def start(self):
        """Start system monitoring"""
        try:
            # Initialize network baseline
            net_io = psutil.net_io_counters()
            self.network_stats_baseline = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv
            }
            
            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.logger.info("System monitoring started")
            
        except Exception as e:
            self.logger.error(f"Failed to start system monitoring: {e}")
            raise
    
    async def stop(self):
        """Stop system monitoring"""
        try:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("System monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping system monitoring: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                self.system_metrics.append(metrics)
                
                # Limit history
                if len(self.system_metrics) > self.metrics_history_limit:
                    self.system_metrics.pop(0)
                
                # Update service status
                await self._update_service_status()
                
                await asyncio.sleep(self.metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.metrics_interval)
    
    async def _cleanup_loop(self):
        """Cleanup loop for stale data"""
        while True:
            try:
                await self._cleanup_stale_nodes()
                await self._cleanup_old_alerts()
                
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network usage (delta from baseline)
            net_io = psutil.net_io_counters()
            network_sent = net_io.bytes_sent - self.network_stats_baseline['bytes_sent']
            network_recv = net_io.bytes_recv - self.network_stats_baseline['bytes_recv']
            
            # System uptime
            uptime = int(time.time() - self.start_time)
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_total=memory.total,
                disk_percent=disk.percent,
                disk_used=disk.used,
                disk_total=disk.total,
                network_sent=network_sent,
                network_recv=network_recv,
                uptime=uptime
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            # Return default metrics on error
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used=0,
                memory_total=0,
                disk_percent=0.0,
                disk_used=0,
                disk_total=0,
                network_sent=0,
                network_recv=0,
                uptime=0
            )
    
    async def _update_service_status(self):
        """Update service status information"""
        if not self.plugin_manager:
            return
        
        try:
            # Get plugin status from plugin manager
            running_plugins = getattr(self.plugin_manager, 'get_running_plugins', lambda: [])()
            
            for plugin_name in running_plugins:
                if plugin_name not in self.services:
                    self.services[plugin_name] = ServiceStatus(
                        name=plugin_name,
                        status="running",
                        uptime=0
                    )
                else:
                    self.services[plugin_name].status = "running"
                    self.services[plugin_name].uptime += self.metrics_interval
            
            # Mark non-running plugins as stopped
            for service_name in list(self.services.keys()):
                if service_name not in running_plugins:
                    self.services[service_name].status = "stopped"
                    self.services[service_name].uptime = 0
            
        except Exception as e:
            self.logger.error(f"Error updating service status: {e}")
    
    async def _cleanup_stale_nodes(self):
        """Remove nodes that haven't been seen recently"""
        try:
            current_time = datetime.now(timezone.utc)
            stale_nodes = []
            
            for node_id, node in self.nodes.items():
                time_diff = (current_time - node.last_seen).total_seconds()
                if time_diff > self.node_timeout:
                    node.is_online = False
                    if time_diff > self.node_timeout * 2:  # Remove after 10 minutes
                        stale_nodes.append(node_id)
            
            for node_id in stale_nodes:
                del self.nodes[node_id]
                self.logger.debug(f"Removed stale node: {node_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up stale nodes: {e}")
    
    async def _cleanup_old_alerts(self):
        """Remove old resolved alerts"""
        try:
            current_time = datetime.now(timezone.utc)
            old_alerts = []
            
            for alert_id, alert in self.alerts.items():
                if alert.resolved:
                    time_diff = (current_time - alert.timestamp).total_seconds()
                    if time_diff > 3600:  # Remove resolved alerts after 1 hour
                        old_alerts.append(alert_id)
            
            for alert_id in old_alerts:
                del self.alerts[alert_id]
                self.logger.debug(f"Removed old alert: {alert_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old alerts: {e}")
    
    def update_node_status(self, message: Message):
        """Update node status from received message"""
        try:
            node_id = message.sender_id
            
            # Create or update node
            if node_id not in self.nodes:
                self.nodes[node_id] = NodeStatus(
                    node_id=node_id,
                    short_name=f"Node-{node_id[-4:]}",
                    long_name=f"Unknown Node {node_id}",
                    hardware="Unknown",
                    role="CLIENT"
                )
            
            node = self.nodes[node_id]
            node.last_seen = datetime.now(timezone.utc)
            node.is_online = True
            node.hops_away = message.hop_count
            
            # Update signal metrics
            if message.snr is not None:
                node.snr = message.snr
            if message.rssi is not None:
                node.rssi = message.rssi
            
            self.logger.debug(f"Updated node status: {node_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating node status: {e}")
    
    def add_alert(self, alert_type: str, severity: str, message: str, source: str) -> str:
        """Add a new alert"""
        try:
            alert_id = f"{source}_{alert_type}_{int(time.time())}"
            
            alert = AlertInfo(
                id=alert_id,
                type=alert_type,
                severity=severity,
                message=message,
                source=source,
                timestamp=datetime.now(timezone.utc)
            )
            
            self.alerts[alert_id] = alert
            self.logger.info(f"Added alert: {alert_id} - {message}")
            
            return alert_id
            
        except Exception as e:
            self.logger.error(f"Error adding alert: {e}")
            return ""
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        try:
            if alert_id in self.alerts:
                self.alerts[alert_id].acknowledged = True
                self.logger.info(f"Acknowledged alert: {alert_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error acknowledging alert: {e}")
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            if alert_id in self.alerts:
                self.alerts[alert_id].resolved = True
                self.alerts[alert_id].acknowledged = True
                self.logger.info(f"Resolved alert: {alert_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error resolving alert: {e}")
            return False
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics"""
        return self.system_metrics[-1] if self.system_metrics else None
    
    def get_metrics_history(self, limit: int = 50) -> List[SystemMetrics]:
        """Get system metrics history"""
        return self.system_metrics[-limit:] if self.system_metrics else []
    
    def get_online_nodes(self) -> List[NodeStatus]:
        """Get list of online nodes"""
        return [node for node in self.nodes.values() if node.is_online]
    
    def get_all_nodes(self) -> List[NodeStatus]:
        """Get list of all nodes"""
        return list(self.nodes.values())
    
    def get_active_alerts(self) -> List[AlertInfo]:
        """Get list of active (unresolved) alerts"""
        return [alert for alert in self.alerts.values() if not alert.resolved]
    
    def get_all_alerts(self) -> List[AlertInfo]:
        """Get list of all alerts"""
        return list(self.alerts.values())
    
    def get_service_status(self) -> List[ServiceStatus]:
        """Get list of service statuses"""
        return list(self.services.values())
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system summary for dashboard"""
        current_metrics = self.get_current_metrics()
        online_nodes = self.get_online_nodes()
        active_alerts = self.get_active_alerts()
        services = self.get_service_status()
        
        return {
            "system_status": "healthy" if current_metrics and current_metrics.cpu_percent < 80 else "warning",
            "uptime": current_metrics.uptime if current_metrics else 0,
            "cpu_percent": current_metrics.cpu_percent if current_metrics else 0,
            "memory_percent": current_metrics.memory_percent if current_metrics else 0,
            "disk_percent": current_metrics.disk_percent if current_metrics else 0,
            "node_count": len(online_nodes),
            "total_nodes": len(self.nodes),
            "active_alerts": len(active_alerts),
            "running_services": len([s for s in services if s.status == "running"]),
            "total_services": len(services),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert monitoring data to dictionary for JSON serialization"""
        return {
            "metrics": [
                {
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "memory_used": m.memory_used,
                    "memory_total": m.memory_total,
                    "disk_percent": m.disk_percent,
                    "disk_used": m.disk_used,
                    "disk_total": m.disk_total,
                    "network_sent": m.network_sent,
                    "network_recv": m.network_recv,
                    "uptime": m.uptime,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in self.system_metrics[-10:]  # Last 10 metrics
            ],
            "nodes": [
                {
                    "node_id": n.node_id,
                    "short_name": n.short_name,
                    "long_name": n.long_name,
                    "hardware": n.hardware,
                    "role": n.role,
                    "battery_level": n.battery_level,
                    "voltage": n.voltage,
                    "snr": n.snr,
                    "rssi": n.rssi,
                    "last_seen": n.last_seen.isoformat(),
                    "location": n.location,
                    "is_online": n.is_online,
                    "hops_away": n.hops_away
                }
                for n in self.nodes.values()
            ],
            "alerts": [
                {
                    "id": a.id,
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message,
                    "source": a.source,
                    "timestamp": a.timestamp.isoformat(),
                    "acknowledged": a.acknowledged,
                    "resolved": a.resolved
                }
                for a in self.alerts.values()
            ],
            "services": [
                {
                    "name": s.name,
                    "status": s.status,
                    "uptime": s.uptime,
                    "last_restart": s.last_restart.isoformat() if s.last_restart else None,
                    "error_count": s.error_count,
                    "last_error": s.last_error
                }
                for s in self.services.values()
            ],
            "summary": self.get_system_summary()
        }