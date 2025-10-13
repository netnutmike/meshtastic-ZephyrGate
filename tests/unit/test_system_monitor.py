"""
Unit tests for System Monitor
"""

import asyncio
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.services.web.system_monitor import (
    SystemMonitor, SystemMetrics, NodeStatus, AlertInfo, ServiceStatus
)
from src.models.message import Message, MessageType


class TestSystemMonitor:
    """Test system monitor functionality"""
    
    @pytest.fixture
    def system_monitor(self):
        return SystemMonitor()
    
    def test_init(self, system_monitor):
        """Test system monitor initialization"""
        assert system_monitor.system_metrics == []
        assert system_monitor.nodes == {}
        assert system_monitor.alerts == {}
        assert system_monitor.services == {}
        assert system_monitor.metrics_history_limit == 100
        assert system_monitor.node_timeout == 300
        assert system_monitor.metrics_interval == 30
    
    @pytest.mark.asyncio
    async def test_start_stop(self, system_monitor):
        """Test starting and stopping system monitor"""
        # Mock psutil to avoid actual system calls
        with patch('src.services.web.system_monitor.psutil.net_io_counters') as mock_net_io:
            mock_net_io.return_value = Mock(bytes_sent=1000, bytes_recv=2000)
            
            # Start monitor
            await system_monitor.start()
            assert system_monitor.monitoring_task is not None
            assert system_monitor.cleanup_task is not None
            
            # Stop monitor
            await system_monitor.stop()
    
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, system_monitor):
        """Test system metrics collection"""
        with patch('src.services.web.system_monitor.psutil') as mock_psutil:
            # Mock psutil functions
            mock_psutil.cpu_percent.return_value = 25.5
            mock_psutil.virtual_memory.return_value = Mock(
                percent=60.0, used=4000000000, total=8000000000
            )
            mock_psutil.disk_usage.return_value = Mock(
                percent=45.0, used=100000000000, total=250000000000
            )
            mock_psutil.net_io_counters.return_value = Mock(
                bytes_sent=5000, bytes_recv=10000
            )
            
            # Set baseline
            system_monitor.network_stats_baseline = {
                'bytes_sent': 1000,
                'bytes_recv': 2000
            }
            
            metrics = await system_monitor._collect_system_metrics()
            
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 25.5
            assert metrics.memory_percent == 60.0
            assert metrics.memory_used == 4000000000
            assert metrics.memory_total == 8000000000
            assert metrics.disk_percent == 45.0
            assert metrics.network_sent == 4000  # 5000 - 1000
            assert metrics.network_recv == 8000  # 10000 - 2000
    
    def test_update_node_status(self, system_monitor):
        """Test node status updates"""
        # Create test message
        message = Message(
            id="test_msg",
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Test message",
            timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            interface_id="serial0",
            hop_count=2,
            snr=5.5,
            rssi=-85
        )
        
        # Update node status
        system_monitor.update_node_status(message)
        
        # Check node was created
        assert "!12345678" in system_monitor.nodes
        node = system_monitor.nodes["!12345678"]
        
        assert node.node_id == "!12345678"
        assert node.is_online is True
        assert node.hops_away == 2
        assert node.snr == 5.5
        assert node.rssi == -85
    
    def test_add_alert(self, system_monitor):
        """Test adding alerts"""
        alert_id = system_monitor.add_alert(
            alert_type="system_error",
            severity="high",
            message="Test alert message",
            source="test_service"
        )
        
        assert alert_id != ""
        assert alert_id in system_monitor.alerts
        
        alert = system_monitor.alerts[alert_id]
        assert alert.type == "system_error"
        assert alert.severity == "high"
        assert alert.message == "Test alert message"
        assert alert.source == "test_service"
        assert alert.acknowledged is False
        assert alert.resolved is False
    
    def test_acknowledge_alert(self, system_monitor):
        """Test acknowledging alerts"""
        # Add alert first
        alert_id = system_monitor.add_alert(
            alert_type="test",
            severity="medium",
            message="Test alert",
            source="test"
        )
        
        # Acknowledge alert
        success = system_monitor.acknowledge_alert(alert_id)
        assert success is True
        assert system_monitor.alerts[alert_id].acknowledged is True
        
        # Test non-existent alert
        success = system_monitor.acknowledge_alert("nonexistent")
        assert success is False
    
    def test_resolve_alert(self, system_monitor):
        """Test resolving alerts"""
        # Add alert first
        alert_id = system_monitor.add_alert(
            alert_type="test",
            severity="low",
            message="Test alert",
            source="test"
        )
        
        # Resolve alert
        success = system_monitor.resolve_alert(alert_id)
        assert success is True
        assert system_monitor.alerts[alert_id].resolved is True
        assert system_monitor.alerts[alert_id].acknowledged is True
        
        # Test non-existent alert
        success = system_monitor.resolve_alert("nonexistent")
        assert success is False
    
    def test_get_online_nodes(self, system_monitor):
        """Test getting online nodes"""
        # Add online node
        message1 = Message(
            id="msg1", sender_id="!11111111", recipient_id=None,
            channel=0, content="Test", timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT, interface_id="serial0"
        )
        system_monitor.update_node_status(message1)
        
        # Add offline node
        system_monitor.nodes["!22222222"] = NodeStatus(
            node_id="!22222222",
            short_name="Offline",
            long_name="Offline Node",
            hardware="Unknown",
            role="CLIENT",
            is_online=False
        )
        
        online_nodes = system_monitor.get_online_nodes()
        assert len(online_nodes) == 1
        assert online_nodes[0].node_id == "!11111111"
        assert online_nodes[0].is_online is True
    
    def test_get_active_alerts(self, system_monitor):
        """Test getting active alerts"""
        # Add active alert
        alert_id1 = system_monitor.add_alert("error", "high", "Active alert", "test")
        
        # Add resolved alert
        alert_id2 = system_monitor.add_alert("warning", "medium", "Resolved alert", "test")
        system_monitor.resolve_alert(alert_id2)
        
        active_alerts = system_monitor.get_active_alerts()
        assert len(active_alerts) == 1
        assert active_alerts[0].id == alert_id1
        assert active_alerts[0].resolved is False
    
    def test_get_system_summary(self, system_monitor):
        """Test getting system summary"""
        # Add some test data
        system_monitor.system_metrics.append(SystemMetrics(
            cpu_percent=50.0,
            memory_percent=70.0,
            memory_used=4000000000,
            memory_total=8000000000,
            disk_percent=30.0,
            disk_used=100000000000,
            disk_total=500000000000,
            network_sent=1000,
            network_recv=2000,
            uptime=3600
        ))
        
        # Add node
        message = Message(
            id="msg", sender_id="!12345678", recipient_id=None,
            channel=0, content="Test", timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT, interface_id="serial0"
        )
        system_monitor.update_node_status(message)
        
        # Add alert
        system_monitor.add_alert("test", "low", "Test alert", "test")
        
        summary = system_monitor.get_system_summary()
        
        assert summary["system_status"] == "healthy"  # CPU < 80%
        assert summary["uptime"] == 3600
        assert summary["cpu_percent"] == 50.0
        assert summary["memory_percent"] == 70.0
        assert summary["disk_percent"] == 30.0
        assert summary["node_count"] == 1
        assert summary["total_nodes"] == 1
        assert summary["active_alerts"] == 1
        assert "last_updated" in summary
    
    def test_to_dict(self, system_monitor):
        """Test converting to dictionary"""
        # Add test data
        system_monitor.system_metrics.append(SystemMetrics(
            cpu_percent=25.0,
            memory_percent=50.0,
            memory_used=2000000000,
            memory_total=4000000000,
            disk_percent=40.0,
            disk_used=50000000000,
            disk_total=125000000000,
            network_sent=500,
            network_recv=1000,
            uptime=1800
        ))
        
        message = Message(
            id="msg", sender_id="!87654321", recipient_id=None,
            channel=0, content="Test", timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT, interface_id="serial0"
        )
        system_monitor.update_node_status(message)
        
        system_monitor.add_alert("info", "low", "Info alert", "test")
        
        data = system_monitor.to_dict()
        
        assert "metrics" in data
        assert "nodes" in data
        assert "alerts" in data
        assert "services" in data
        assert "summary" in data
        
        assert len(data["metrics"]) == 1
        assert len(data["nodes"]) == 1
        assert len(data["alerts"]) == 1
        
        # Check metric data
        metric = data["metrics"][0]
        assert metric["cpu_percent"] == 25.0
        assert metric["memory_percent"] == 50.0
        
        # Check node data
        node = data["nodes"][0]
        assert node["node_id"] == "!87654321"
        assert node["is_online"] is True
        
        # Check alert data
        alert = data["alerts"][0]
        assert alert["type"] == "info"
        assert alert["severity"] == "low"


@pytest.mark.asyncio
async def test_system_monitor_integration():
    """Integration test for system monitor"""
    monitor = SystemMonitor()
    
    try:
        # Mock psutil to avoid actual system calls
        with patch('src.services.web.system_monitor.psutil.net_io_counters') as mock_net_io:
            mock_net_io.return_value = Mock(bytes_sent=1000, bytes_recv=2000)
            
            # Start monitor
            await monitor.start()
            
            # Add some test data
            message = Message(
                id="integration_test",
                sender_id="!ABCDEF12",
                recipient_id=None,
                channel=0,
                content="Integration test message",
                timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT,
                interface_id="serial0",
                snr=3.2,
                rssi=-90
            )
            
            monitor.update_node_status(message)
            monitor.add_alert("test", "medium", "Integration test alert", "test_suite")
            
            # Verify data
            nodes = monitor.get_online_nodes()
            assert len(nodes) == 1
            assert nodes[0].node_id == "!ABCDEF12"
            
            alerts = monitor.get_active_alerts()
            assert len(alerts) == 1
            assert alerts[0].message == "Integration test alert"
            
            summary = monitor.get_system_summary()
            assert summary["node_count"] == 1
            assert summary["active_alerts"] == 1
            
    finally:
        # Clean up
        await monitor.stop()


if __name__ == "__main__":
    pytest.main([__file__])