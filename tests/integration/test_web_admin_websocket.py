"""
WebSocket Integration Tests for Web Administration Interface

Tests real-time updates, WebSocket connections, and live data streaming.
"""

import asyncio
import json
import pytest
import websockets
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.services.web.web_admin_service import WebAdminService, WebSocketManager
from src.services.web.system_monitor import SystemMonitor, SystemMetrics, NodeStatus, AlertInfo
from src.models.message import Message, MessageType


class MockWebSocket:
    """Mock WebSocket for testing"""
    
    def __init__(self):
        self.messages_sent = []
        self.is_closed = False
        self.accept_called = False
    
    async def accept(self):
        self.accept_called = True
    
    async def send_text(self, message: str):
        if not self.is_closed:
            self.messages_sent.append(message)
    
    async def close(self):
        self.is_closed = True


class TestWebSocketIntegration:
    """Test WebSocket functionality and real-time updates"""
    
    @pytest.fixture
    def websocket_manager(self):
        """Create WebSocket manager for testing"""
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket"""
        return MockWebSocket()
    
    @pytest.fixture
    def system_monitor(self):
        """Create system monitor for testing"""
        return SystemMonitor()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, websocket_manager, mock_websocket):
        """Test WebSocket connection lifecycle"""
        client_id = "test_client_1"
        permissions = {"read", "write", "admin"}
        
        # Test connection
        await websocket_manager.connect(mock_websocket, client_id, permissions)
        
        assert mock_websocket.accept_called
        assert client_id in websocket_manager.active_connections
        assert websocket_manager.connection_permissions[client_id] == permissions
        
        # Test disconnection
        websocket_manager.disconnect(client_id)
        
        assert client_id not in websocket_manager.active_connections
        assert client_id not in websocket_manager.connection_permissions
    
    @pytest.mark.asyncio
    async def test_personal_message_sending(self, websocket_manager, mock_websocket):
        """Test sending personal messages to specific clients"""
        client_id = "test_client_2"
        permissions = {"read"}
        
        # Connect client
        await websocket_manager.connect(mock_websocket, client_id, permissions)
        
        # Send personal message
        test_message = "Personal test message"
        await websocket_manager.send_personal_message(test_message, client_id)
        
        assert len(mock_websocket.messages_sent) == 1
        assert mock_websocket.messages_sent[0] == test_message
        
        # Test sending to non-existent client
        await websocket_manager.send_personal_message("No one", "nonexistent_client")
        # Should not raise error, just silently fail
        assert len(mock_websocket.messages_sent) == 1  # No new messages
    
    @pytest.mark.asyncio
    async def test_broadcast_messaging(self, websocket_manager):
        """Test broadcasting messages to multiple clients"""
        # Create multiple mock clients
        clients = {}
        for i in range(3):
            client_id = f"client_{i}"
            mock_ws = MockWebSocket()
            permissions = {"read"} if i < 2 else {"write"}  # First two have read, last has write
            
            await websocket_manager.connect(mock_ws, client_id, permissions)
            clients[client_id] = mock_ws
        
        # Broadcast message requiring read permission
        test_message = "Broadcast to readers"
        await websocket_manager.broadcast(test_message, permission_required="read")
        
        # Check that only clients with read permission received the message
        assert len(clients["client_0"].messages_sent) == 1
        assert len(clients["client_1"].messages_sent) == 1
        assert len(clients["client_2"].messages_sent) == 0  # No read permission
        
        assert clients["client_0"].messages_sent[0] == test_message
        assert clients["client_1"].messages_sent[0] == test_message
        
        # Broadcast message without permission requirement
        general_message = "General broadcast"
        await websocket_manager.broadcast(general_message)
        
        # All clients should receive this message
        for client_ws in clients.values():
            assert general_message in client_ws.messages_sent
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, websocket_manager):
        """Test WebSocket error handling"""
        # Create mock WebSocket that raises exception on send
        class FailingWebSocket(MockWebSocket):
            async def send_text(self, message: str):
                raise Exception("Connection failed")
        
        failing_ws = FailingWebSocket()
        client_id = "failing_client"
        
        await websocket_manager.connect(failing_ws, client_id, {"read"})
        
        # Sending message should handle the exception gracefully
        await websocket_manager.send_personal_message("Test", client_id)
        
        # Client should be automatically disconnected after error
        assert client_id not in websocket_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_real_time_system_updates(self, websocket_manager, system_monitor):
        """Test real-time system status updates"""
        # Connect client
        mock_ws = MockWebSocket()
        client_id = "system_monitor_client"
        await websocket_manager.connect(mock_ws, client_id, {"system:monitor"})
        
        # Simulate system metrics update
        with patch('src.services.web.system_monitor.psutil') as mock_psutil:
            mock_psutil.cpu_percent.return_value = 75.0
            mock_psutil.virtual_memory.return_value = Mock(
                percent=80.0, used=6000000000, total=8000000000
            )
            mock_psutil.disk_usage.return_value = Mock(
                percent=60.0, used=300000000000, total=500000000000
            )
            mock_psutil.net_io_counters.return_value = Mock(
                bytes_sent=10000, bytes_recv=20000
            )
            
            system_monitor.network_stats_baseline = {
                'bytes_sent': 5000,
                'bytes_recv': 10000
            }
            
            # Collect metrics
            metrics = await system_monitor._collect_system_metrics()
            
            # Simulate broadcasting metrics update
            metrics_data = {
                "type": "system_metrics",
                "data": {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "disk_percent": metrics.disk_percent,
                    "timestamp": metrics.timestamp.isoformat()
                }
            }
            
            await websocket_manager.broadcast(
                json.dumps(metrics_data),
                permission_required="system:monitor"
            )
            
            # Verify client received the update
            assert len(mock_ws.messages_sent) == 1
            received_data = json.loads(mock_ws.messages_sent[0])
            assert received_data["type"] == "system_metrics"
            assert received_data["data"]["cpu_percent"] == 75.0
            assert received_data["data"]["memory_percent"] == 80.0
    
    @pytest.mark.asyncio
    async def test_real_time_node_updates(self, websocket_manager, system_monitor):
        """Test real-time node status updates"""
        # Connect client
        mock_ws = MockWebSocket()
        client_id = "node_monitor_client"
        await websocket_manager.connect(mock_ws, client_id, {"node:monitor"})
        
        # Simulate node status update
        test_message = Message(
            id="test_msg_001",
            sender_id="!ABCD1234",
            recipient_id=None,
            channel=0,
            content="Test message from node",
            timestamp=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            interface_id="serial0",
            hop_count=1,
            snr=8.5,
            rssi=-75
        )
        
        # Update node status
        system_monitor.update_node_status(test_message)
        
        # Get updated node
        node = system_monitor.nodes["!ABCD1234"]
        
        # Simulate broadcasting node update
        node_update = {
            "type": "node_update",
            "data": {
                "node_id": node.node_id,
                "short_name": node.short_name,
                "is_online": node.is_online,
                "snr": node.snr,
                "rssi": node.rssi,
                "last_seen": node.last_seen.isoformat(),
                "hops_away": node.hops_away
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(node_update),
            permission_required="node:monitor"
        )
        
        # Verify client received the update
        assert len(mock_ws.messages_sent) == 1
        received_data = json.loads(mock_ws.messages_sent[0])
        assert received_data["type"] == "node_update"
        assert received_data["data"]["node_id"] == "!ABCD1234"
        assert received_data["data"]["snr"] == 8.5
        assert received_data["data"]["rssi"] == -75
    
    @pytest.mark.asyncio
    async def test_real_time_alert_updates(self, websocket_manager, system_monitor):
        """Test real-time alert notifications"""
        # Connect client
        mock_ws = MockWebSocket()
        client_id = "alert_client"
        await websocket_manager.connect(mock_ws, client_id, {"alert:receive"})
        
        # Add alert
        alert_id = system_monitor.add_alert(
            alert_type="system_error",
            severity="high",
            message="Critical system error detected",
            source="system_monitor"
        )
        
        alert = system_monitor.alerts[alert_id]
        
        # Simulate broadcasting alert
        alert_update = {
            "type": "new_alert",
            "data": {
                "id": alert.id,
                "type": alert.type,
                "severity": alert.severity,
                "message": alert.message,
                "source": alert.source,
                "timestamp": alert.timestamp.isoformat(),
                "acknowledged": alert.acknowledged,
                "resolved": alert.resolved
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(alert_update),
            permission_required="alert:receive"
        )
        
        # Verify client received the alert
        assert len(mock_ws.messages_sent) == 1
        received_data = json.loads(mock_ws.messages_sent[0])
        assert received_data["type"] == "new_alert"
        assert received_data["data"]["severity"] == "high"
        assert received_data["data"]["message"] == "Critical system error detected"
    
    @pytest.mark.asyncio
    async def test_real_time_message_updates(self, websocket_manager):
        """Test real-time message/chat updates"""
        # Connect client
        mock_ws = MockWebSocket()
        client_id = "chat_client"
        await websocket_manager.connect(mock_ws, client_id, {"message:read"})
        
        # Simulate new message
        new_message = {
            "type": "new_message",
            "data": {
                "id": "msg_12345",
                "sender_id": "!USER001",
                "sender_name": "TestUser",
                "channel": 0,
                "content": "Hello from the mesh!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_type": "text",
                "interface_id": "serial0",
                "snr": 6.2,
                "rssi": -80
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(new_message),
            permission_required="message:read"
        )
        
        # Verify client received the message
        assert len(mock_ws.messages_sent) == 1
        received_data = json.loads(mock_ws.messages_sent[0])
        assert received_data["type"] == "new_message"
        assert received_data["data"]["content"] == "Hello from the mesh!"
        assert received_data["data"]["sender_id"] == "!USER001"
    
    @pytest.mark.asyncio
    async def test_multiple_client_management(self, websocket_manager):
        """Test managing multiple WebSocket clients"""
        clients = {}
        num_clients = 10
        
        # Connect multiple clients
        for i in range(num_clients):
            client_id = f"client_{i}"
            mock_ws = MockWebSocket()
            permissions = {"read"} if i % 2 == 0 else {"write"}
            
            await websocket_manager.connect(mock_ws, client_id, permissions)
            clients[client_id] = mock_ws
        
        assert len(websocket_manager.active_connections) == num_clients
        
        # Broadcast to all clients
        await websocket_manager.broadcast("Message to all")
        
        # All clients should receive the message
        for mock_ws in clients.values():
            assert len(mock_ws.messages_sent) == 1
            assert mock_ws.messages_sent[0] == "Message to all"
        
        # Broadcast with permission filter
        await websocket_manager.broadcast("Message to readers", permission_required="read")
        
        # Only clients with read permission should receive this message
        read_clients = [clients[f"client_{i}"] for i in range(0, num_clients, 2)]  # Even indices
        write_clients = [clients[f"client_{i}"] for i in range(1, num_clients, 2)]  # Odd indices
        
        for mock_ws in read_clients:
            assert len(mock_ws.messages_sent) == 2  # Both messages
            assert mock_ws.messages_sent[1] == "Message to readers"
        
        for mock_ws in write_clients:
            assert len(mock_ws.messages_sent) == 1  # Only first message
        
        # Disconnect half the clients
        for i in range(0, num_clients, 2):
            websocket_manager.disconnect(f"client_{i}")
        
        assert len(websocket_manager.active_connections) == num_clients // 2
    
    @pytest.mark.asyncio
    async def test_websocket_message_queuing(self, websocket_manager):
        """Test message queuing when WebSocket is temporarily unavailable"""
        # This test simulates what happens when a WebSocket connection fails
        # but we want to queue messages for when it reconnects
        
        # Create a WebSocket that fails after first message
        class UnreliableWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__()
                self.send_count = 0
                self.should_fail = False
            
            async def send_text(self, message: str):
                self.send_count += 1
                if self.should_fail:
                    raise Exception("Connection temporarily unavailable")
                await super().send_text(message)
        
        unreliable_ws = UnreliableWebSocket()
        client_id = "unreliable_client"
        
        await websocket_manager.connect(unreliable_ws, client_id, {"read"})
        
        # Send first message (should succeed)
        await websocket_manager.send_personal_message("Message 1", client_id)
        assert len(unreliable_ws.messages_sent) == 1
        
        # Make WebSocket fail
        unreliable_ws.should_fail = True
        
        # Send second message (should fail and disconnect client)
        await websocket_manager.send_personal_message("Message 2", client_id)
        
        # Client should be disconnected after failure
        assert client_id not in websocket_manager.active_connections
        assert len(unreliable_ws.messages_sent) == 1  # Only first message received
    
    @pytest.mark.asyncio
    async def test_websocket_performance_under_load(self, websocket_manager):
        """Test WebSocket performance under high message load"""
        # Connect multiple clients
        clients = {}
        num_clients = 50
        
        for i in range(num_clients):
            client_id = f"load_client_{i}"
            mock_ws = MockWebSocket()
            await websocket_manager.connect(mock_ws, client_id, {"read"})
            clients[client_id] = mock_ws
        
        # Send many messages rapidly
        num_messages = 100
        messages = [f"Load test message {i}" for i in range(num_messages)]
        
        import time
        start_time = time.time()
        
        for message in messages:
            await websocket_manager.broadcast(message)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify all messages were sent to all clients
        for mock_ws in clients.values():
            assert len(mock_ws.messages_sent) == num_messages
            assert mock_ws.messages_sent == messages
        
        # Performance check - should handle 50 clients * 100 messages reasonably fast
        total_messages_sent = num_clients * num_messages
        messages_per_second = total_messages_sent / duration
        
        # Should be able to handle at least 1000 messages per second
        assert messages_per_second > 1000, f"Performance too slow: {messages_per_second:.2f} msg/sec"
    
    @pytest.mark.asyncio
    async def test_websocket_data_serialization(self, websocket_manager):
        """Test serialization of complex data structures over WebSocket"""
        mock_ws = MockWebSocket()
        client_id = "data_client"
        await websocket_manager.connect(mock_ws, client_id, {"read"})
        
        # Test complex data structure
        complex_data = {
            "type": "complex_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "nodes": [
                    {
                        "id": "!NODE001",
                        "name": "Test Node 1",
                        "metrics": {
                            "snr": 5.5,
                            "rssi": -85,
                            "battery": 75
                        },
                        "location": {
                            "lat": 40.7128,
                            "lon": -74.0060
                        },
                        "active": True
                    },
                    {
                        "id": "!NODE002",
                        "name": "Test Node 2",
                        "metrics": {
                            "snr": 3.2,
                            "rssi": -92,
                            "battery": 45
                        },
                        "location": None,
                        "active": False
                    }
                ],
                "alerts": [
                    {
                        "id": "alert_001",
                        "severity": "high",
                        "message": "Low battery warning",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                ],
                "statistics": {
                    "total_nodes": 2,
                    "active_nodes": 1,
                    "message_count": 1234,
                    "uptime": 86400
                }
            }
        }
        
        # Send complex data
        await websocket_manager.send_personal_message(json.dumps(complex_data), client_id)
        
        # Verify data was sent correctly
        assert len(mock_ws.messages_sent) == 1
        received_data = json.loads(mock_ws.messages_sent[0])
        
        assert received_data["type"] == "complex_update"
        assert len(received_data["data"]["nodes"]) == 2
        assert received_data["data"]["nodes"][0]["id"] == "!NODE001"
        assert received_data["data"]["nodes"][0]["metrics"]["snr"] == 5.5
        assert received_data["data"]["statistics"]["total_nodes"] == 2
    
    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup(self, websocket_manager):
        """Test proper cleanup of WebSocket connections"""
        # Connect multiple clients
        client_ids = [f"cleanup_client_{i}" for i in range(5)]
        
        for client_id in client_ids:
            mock_ws = MockWebSocket()
            await websocket_manager.connect(mock_ws, client_id, {"read"})
        
        assert len(websocket_manager.active_connections) == 5
        assert len(websocket_manager.connection_permissions) == 5
        
        # Disconnect all clients
        for client_id in client_ids:
            websocket_manager.disconnect(client_id)
        
        # Verify complete cleanup
        assert len(websocket_manager.active_connections) == 0
        assert len(websocket_manager.connection_permissions) == 0
        
        # Verify no memory leaks by checking internal state
        assert websocket_manager.active_connections == {}
        assert websocket_manager.connection_permissions == {}


@pytest.mark.asyncio
async def test_websocket_integration_with_web_service():
    """Integration test combining WebSocket with full web service"""
    # Create mock plugin manager
    mock_plugin_manager = Mock()
    mock_plugin_manager.config_manager = Mock()
    mock_plugin_manager.config_manager.get = Mock(return_value=None)
    mock_plugin_manager.get_running_plugins = Mock(return_value=["test"])
    
    config = {
        "host": "127.0.0.1",
        "port": 8083,
        "secret_key": "websocket-test-secret",
        "debug": True
    }
    
    # Create and initialize service
    service = WebAdminService(config, mock_plugin_manager)
    await service.initialize()
    
    try:
        # Test WebSocket manager integration
        websocket_manager = service.websocket_manager
        
        # Connect mock client
        mock_ws = MockWebSocket()
        client_id = "integration_client"
        permissions = {"system:monitor", "message:read", "alert:receive"}
        
        await websocket_manager.connect(mock_ws, client_id, permissions)
        
        # Simulate system update
        system_update = {
            "type": "system_status",
            "data": {
                "status": "healthy",
                "uptime": 3600,
                "cpu_percent": 45.0,
                "memory_percent": 60.0,
                "active_nodes": 5,
                "active_alerts": 1
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(system_update),
            permission_required="system:monitor"
        )
        
        # Verify client received update
        assert len(mock_ws.messages_sent) == 1
        received_data = json.loads(mock_ws.messages_sent[0])
        assert received_data["type"] == "system_status"
        assert received_data["data"]["status"] == "healthy"
        
        # Test multiple update types
        message_update = {
            "type": "new_message",
            "data": {
                "sender": "!TEST001",
                "content": "Integration test message",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(message_update),
            permission_required="message:read"
        )
        
        alert_update = {
            "type": "new_alert",
            "data": {
                "severity": "medium",
                "message": "Integration test alert",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        await websocket_manager.broadcast(
            json.dumps(alert_update),
            permission_required="alert:receive"
        )
        
        # Verify all updates received
        assert len(mock_ws.messages_sent) == 3
        
        # Check message types
        message_types = [json.loads(msg)["type"] for msg in mock_ws.messages_sent]
        assert "system_status" in message_types
        assert "new_message" in message_types
        assert "new_alert" in message_types
        
    finally:
        # Clean up
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])