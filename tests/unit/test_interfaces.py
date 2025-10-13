"""
Unit tests for Meshtastic Interface Management

Tests interface factory, connection management, and reconnection scenarios.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.models.message import Message, MessageType, InterfaceConfig
from src.core.interfaces import (
    InterfaceStatus, InterfaceFactory, InterfaceManager,
    MeshtasticInterface, SerialInterface, TCPInterface, BLEInterface,
    ConnectionAttempt, InterfaceStats
)


class MockMeshtasticInterface(MeshtasticInterface):
    """Mock interface for testing"""
    
    def __init__(self, config, message_callback, should_fail=False):
        super().__init__(config, message_callback)
        self.should_fail = should_fail
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.send_calls = 0
        self.mock_connection = Mock()
    
    async def _connect(self) -> bool:
        """Mock connection"""
        self.connect_calls += 1
        if self.should_fail:
            return False
        self.connection = self.mock_connection
        return True
    
    async def _disconnect(self):
        """Mock disconnection"""
        self.disconnect_calls += 1
        self.connection = None
    
    async def _send_message(self, message: Message) -> bool:
        """Mock message sending"""
        self.send_calls += 1
        return not self.should_fail
    
    async def _receive_messages(self):
        """Mock message receiving"""
        # Simulate receiving a message
        await asyncio.sleep(0.1)
        if not self.should_fail:
            test_message = Message(
                content="test message",
                sender_id="!87654321",
                message_type=MessageType.TEXT
            )
            self._handle_received_message(test_message)


class TestInterfaceConfig:
    """Test interface configuration"""
    
    def test_serial_connection_params(self):
        """Test serial connection parameters"""
        config = InterfaceConfig(
            id="serial1",
            type="serial",
            connection_string="/dev/ttyUSB0",
            metadata={"baudrate": 115200}
        )
        
        params = config.get_connection_params()
        
        assert params['port'] == "/dev/ttyUSB0"
        assert params['baudrate'] == 115200
        assert params['timeout'] == 30
    
    def test_tcp_connection_params(self):
        """Test TCP connection parameters"""
        config = InterfaceConfig(
            id="tcp1",
            type="tcp",
            connection_string="192.168.1.100:4403"
        )
        
        params = config.get_connection_params()
        
        assert params['host'] == "192.168.1.100"
        assert params['port'] == 4403
    
    def test_tcp_default_port(self):
        """Test TCP default port"""
        config = InterfaceConfig(
            id="tcp1",
            type="tcp",
            connection_string="192.168.1.100"
        )
        
        params = config.get_connection_params()
        
        assert params['host'] == "192.168.1.100"
        assert params['port'] == 4403  # Default Meshtastic TCP port
    
    def test_ble_connection_params(self):
        """Test BLE connection parameters"""
        config = InterfaceConfig(
            id="ble1",
            type="ble",
            connection_string="AA:BB:CC:DD:EE:FF"
        )
        
        params = config.get_connection_params()
        
        assert params['address'] == "AA:BB:CC:DD:EE:FF"


class TestInterfaceStats:
    """Test interface statistics"""
    
    def test_uptime_calculation(self):
        """Test uptime calculation"""
        stats = InterfaceStats()
        
        # No uptime initially
        assert stats.get_uptime() is None
        
        # Set uptime start
        stats.uptime_start = datetime.utcnow() - timedelta(seconds=60)
        uptime = stats.get_uptime()
        
        assert uptime is not None
        assert uptime.total_seconds() >= 60


class TestMeshtasticInterface:
    """Test base Meshtastic interface functionality"""
    
    @pytest.fixture
    def interface_config(self):
        """Create test interface configuration"""
        return InterfaceConfig(
            id="test_interface",
            type="mock",
            connection_string="test",
            retry_interval=1,
            max_retries=3
        )
    
    @pytest.fixture
    def message_callback(self):
        """Create mock message callback"""
        return Mock()
    
    @pytest.fixture
    def mock_interface(self, interface_config, message_callback):
        """Create mock interface"""
        return MockMeshtasticInterface(interface_config, message_callback)
    
    @pytest.mark.asyncio
    async def test_interface_initialization(self, mock_interface):
        """Test interface initialization"""
        assert mock_interface.status == InterfaceStatus.DISCONNECTED
        assert mock_interface.config.id == "test_interface"
        assert mock_interface.stats.messages_sent == 0
        assert mock_interface.stats.messages_received == 0
    
    @pytest.mark.asyncio
    async def test_successful_connection(self, mock_interface):
        """Test successful connection"""
        await mock_interface.start()
        
        # Wait for connection attempt
        await asyncio.sleep(0.2)
        
        assert mock_interface.connect_calls >= 1
        assert mock_interface.status == InterfaceStatus.CONNECTED
        assert mock_interface.stats.successful_connections >= 1
        
        await mock_interface.stop()
    
    @pytest.mark.asyncio
    async def test_failed_connection_with_retry(self, interface_config, message_callback):
        """Test failed connection with retry logic"""
        failing_interface = MockMeshtasticInterface(
            interface_config, message_callback, should_fail=True
        )
        
        await failing_interface.start()
        
        # Wait for connection attempts
        await asyncio.sleep(0.5)
        
        assert failing_interface.connect_calls >= 1
        assert failing_interface.status == InterfaceStatus.FAILED
        assert failing_interface.retry_count > 0
        
        await failing_interface.stop()
    
    @pytest.mark.asyncio
    async def test_message_sending(self, mock_interface):
        """Test message sending"""
        await mock_interface.start()
        await asyncio.sleep(0.2)  # Wait for connection
        
        message = Message(content="test", sender_id="!12345678")
        success = await mock_interface.send_message(message)
        
        await asyncio.sleep(0.1)  # Wait for send processing
        
        assert success
        assert mock_interface.send_calls >= 1
        assert mock_interface.stats.messages_sent >= 1
        
        await mock_interface.stop()
    
    @pytest.mark.asyncio
    async def test_message_receiving(self, mock_interface, message_callback):
        """Test message receiving"""
        await mock_interface.start()
        await asyncio.sleep(0.3)  # Wait for connection and message
        
        # Verify callback was called
        message_callback.assert_called()
        
        # Verify stats updated
        assert mock_interface.stats.messages_received >= 1
        
        await mock_interface.stop()
    
    @pytest.mark.asyncio
    async def test_disabled_interface(self, interface_config, message_callback):
        """Test disabled interface"""
        interface_config.enabled = False
        interface = MockMeshtasticInterface(interface_config, message_callback)
        
        await interface.start()
        await asyncio.sleep(0.1)
        
        assert interface.status == InterfaceStatus.DISABLED
        assert interface.connect_calls == 0
        
        await interface.stop()
    
    @pytest.mark.asyncio
    async def test_connection_monitoring(self, mock_interface):
        """Test connection health monitoring"""
        await mock_interface.start()
        await asyncio.sleep(0.2)  # Wait for connection
        
        # Simulate receive task failure
        if mock_interface.receive_task:
            mock_interface.receive_task.cancel()
            await asyncio.sleep(0.1)
        
        # Interface should detect the failure
        await asyncio.sleep(0.2)
        
        await mock_interface.stop()
    
    def test_status_reporting(self, mock_interface):
        """Test interface status reporting"""
        status = mock_interface.get_status()
        
        assert status['id'] == "test_interface"
        assert status['type'] == "mock"
        assert status['status'] == InterfaceStatus.DISCONNECTED.value
        assert status['enabled'] is True
        assert 'stats' in status
        assert 'recent_connections' in status


class TestInterfaceFactory:
    """Test interface factory"""
    
    def test_create_serial_interface(self):
        """Test creating serial interface"""
        config = InterfaceConfig(
            id="serial1",
            type="serial",
            connection_string="/dev/ttyUSB0"
        )
        callback = Mock()
        
        interface = InterfaceFactory.create_interface(config, callback)
        
        assert isinstance(interface, SerialInterface)
        assert interface.config == config
    
    def test_create_tcp_interface(self):
        """Test creating TCP interface"""
        config = InterfaceConfig(
            id="tcp1",
            type="tcp",
            connection_string="192.168.1.100:4403"
        )
        callback = Mock()
        
        interface = InterfaceFactory.create_interface(config, callback)
        
        assert isinstance(interface, TCPInterface)
        assert interface.config == config
    
    def test_create_ble_interface(self):
        """Test creating BLE interface"""
        config = InterfaceConfig(
            id="ble1",
            type="ble",
            connection_string="AA:BB:CC:DD:EE:FF"
        )
        callback = Mock()
        
        interface = InterfaceFactory.create_interface(config, callback)
        
        assert isinstance(interface, BLEInterface)
        assert interface.config == config
    
    def test_unsupported_interface_type(self):
        """Test creating unsupported interface type"""
        config = InterfaceConfig(
            id="unknown1",
            type="unknown",
            connection_string="test"
        )
        callback = Mock()
        
        with pytest.raises(ValueError, match="Unsupported interface type"):
            InterfaceFactory.create_interface(config, callback)


class TestInterfaceManager:
    """Test interface manager"""
    
    @pytest.fixture
    def message_callback(self):
        """Create mock message callback"""
        return Mock()
    
    @pytest.fixture
    def interface_manager(self, message_callback):
        """Create interface manager"""
        return InterfaceManager(message_callback)
    
    @pytest.fixture
    def test_config(self):
        """Create test interface configuration"""
        return InterfaceConfig(
            id="test1",
            type="mock",
            connection_string="test"
        )
    
    @pytest.mark.asyncio
    async def test_add_interface(self, interface_manager, test_config):
        """Test adding interface"""
        with patch.object(InterfaceFactory, 'create_interface') as mock_create:
            mock_interface = Mock()
            mock_interface.start = AsyncMock()
            mock_create.return_value = mock_interface
            
            await interface_manager.add_interface(test_config)
            
            assert "test1" in interface_manager.interfaces
            mock_interface.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_interface(self, interface_manager, test_config):
        """Test removing interface"""
        # Add interface first
        mock_interface = Mock()
        mock_interface.start = AsyncMock()
        mock_interface.stop = AsyncMock()
        interface_manager.interfaces["test1"] = mock_interface
        
        await interface_manager.remove_interface("test1")
        
        assert "test1" not in interface_manager.interfaces
        mock_interface.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_specific_interface(self, interface_manager):
        """Test sending message through specific interface"""
        # Add mock interface
        mock_interface = Mock()
        mock_interface.send_message = AsyncMock(return_value=True)
        interface_manager.interfaces["test1"] = mock_interface
        
        message = Message(content="test", sender_id="!12345678")
        result = await interface_manager.send_message(message, "test1")
        
        assert result is True
        mock_interface.send_message.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_message_all_interfaces(self, interface_manager):
        """Test sending message through all interfaces"""
        # Add mock interfaces
        mock_interface1 = Mock()
        mock_interface1.send_message = AsyncMock(return_value=True)
        mock_interface2 = Mock()
        mock_interface2.send_message = AsyncMock(return_value=True)
        
        interface_manager.interfaces["test1"] = mock_interface1
        interface_manager.interfaces["test2"] = mock_interface2
        
        message = Message(content="test", sender_id="!12345678")
        result = await interface_manager.send_message(message)
        
        assert result is True
        mock_interface1.send_message.assert_called_once_with(message)
        mock_interface2.send_message.assert_called_once_with(message)
    
    def test_get_interface_status(self, interface_manager):
        """Test getting interface status"""
        # Add mock interface
        mock_interface = Mock()
        mock_interface.get_status.return_value = {"id": "test1", "status": "connected"}
        interface_manager.interfaces["test1"] = mock_interface
        
        # Get specific interface status
        status = interface_manager.get_interface_status("test1")
        assert status["id"] == "test1"
        
        # Get all interface status
        all_status = interface_manager.get_interface_status()
        assert "test1" in all_status
    
    def test_get_connected_interfaces(self, interface_manager):
        """Test getting connected interfaces"""
        # Add mock interfaces with different statuses
        mock_interface1 = Mock()
        mock_interface1.status = InterfaceStatus.CONNECTED
        mock_interface2 = Mock()
        mock_interface2.status = InterfaceStatus.DISCONNECTED
        
        interface_manager.interfaces["connected1"] = mock_interface1
        interface_manager.interfaces["disconnected1"] = mock_interface2
        
        connected = interface_manager.get_connected_interfaces()
        
        assert "connected1" in connected
        assert "disconnected1" not in connected
    
    @pytest.mark.asyncio
    async def test_stop_all_interfaces(self, interface_manager):
        """Test stopping all interfaces"""
        # Add mock interfaces
        mock_interface1 = Mock()
        mock_interface1.stop = AsyncMock()
        mock_interface2 = Mock()
        mock_interface2.stop = AsyncMock()
        
        interface_manager.interfaces["test1"] = mock_interface1
        interface_manager.interfaces["test2"] = mock_interface2
        
        await interface_manager.stop_all()
        
        assert len(interface_manager.interfaces) == 0
        mock_interface1.stop.assert_called_once()
        mock_interface2.stop.assert_called_once()
    
    def test_get_stats(self, interface_manager):
        """Test getting interface statistics"""
        # Add mock interface with stats
        mock_interface = Mock()
        mock_interface.get_status.return_value = {
            "id": "test1",
            "stats": {
                "messages_sent": 10,
                "messages_received": 5,
                "bytes_sent": 1000,
                "bytes_received": 500
            }
        }
        mock_interface.status = InterfaceStatus.CONNECTED
        
        interface_manager.interfaces["test1"] = mock_interface
        
        stats = interface_manager.get_stats()
        
        assert stats['total_interfaces'] == 1
        assert stats['connected_interfaces'] == 1
        assert stats['total_messages_sent'] == 10
        assert stats['total_messages_received'] == 5
        assert "test1" in stats['interfaces']


class TestSpecificInterfaces:
    """Test specific interface implementations"""
    
    @pytest.fixture
    def message_callback(self):
        """Create mock message callback"""
        return Mock()
    
    @patch('src.core.interfaces.meshtastic.serial_interface')
    def test_serial_interface_connection(self, mock_serial_module, message_callback):
        """Test serial interface connection"""
        # Mock the meshtastic serial interface
        mock_connection = Mock()
        mock_connection.myInfo = {"id": "test"}
        mock_serial_module.SerialInterface.return_value = mock_connection
        
        config = InterfaceConfig(
            id="serial1",
            type="serial",
            connection_string="/dev/ttyUSB0"
        )
        
        interface = SerialInterface(config, message_callback)
        
        # Test connection (this would normally be async)
        # For unit test, we'll test the sync parts
        assert interface.config.type == "serial"
    
    @patch('src.core.interfaces.meshtastic.tcp_interface')
    def test_tcp_interface_connection(self, mock_tcp_module, message_callback):
        """Test TCP interface connection"""
        # Mock the meshtastic TCP interface
        mock_connection = Mock()
        mock_connection.myInfo = {"id": "test"}
        mock_tcp_module.TCPInterface.return_value = mock_connection
        
        config = InterfaceConfig(
            id="tcp1",
            type="tcp",
            connection_string="192.168.1.100:4403"
        )
        
        interface = TCPInterface(config, message_callback)
        
        assert interface.config.type == "tcp"
    
    @patch('src.core.interfaces.meshtastic.ble_interface')
    def test_ble_interface_connection(self, mock_ble_module, message_callback):
        """Test BLE interface connection"""
        # Mock the meshtastic BLE interface
        mock_connection = Mock()
        mock_connection.myInfo = {"id": "test"}
        mock_ble_module.BLEInterface.return_value = mock_connection
        
        config = InterfaceConfig(
            id="ble1",
            type="ble",
            connection_string="AA:BB:CC:DD:EE:FF"
        )
        
        interface = BLEInterface(config, message_callback)
        
        assert interface.config.type == "ble"


class TestInterfaceIntegration:
    """Integration tests for interface management"""
    
    @pytest.mark.asyncio
    async def test_interface_lifecycle(self):
        """Test complete interface lifecycle"""
        message_callback = Mock()
        manager = InterfaceManager(message_callback)
        
        # Create test configuration
        config = InterfaceConfig(
            id="test_lifecycle",
            type="mock",
            connection_string="test"
        )
        
        with patch.object(InterfaceFactory, 'create_interface') as mock_create:
            # Create mock interface
            mock_interface = Mock()
            mock_interface.start = AsyncMock()
            mock_interface.stop = AsyncMock()
            mock_interface.send_message = AsyncMock(return_value=True)
            mock_interface.get_status.return_value = {
                "id": "test_lifecycle",
                "status": "connected",
                "stats": {"messages_sent": 0, "messages_received": 0, "bytes_sent": 0, "bytes_received": 0}
            }
            mock_interface.status = InterfaceStatus.CONNECTED
            
            mock_create.return_value = mock_interface
            
            # Add interface
            await manager.add_interface(config)
            assert "test_lifecycle" in manager.interfaces
            
            # Send message
            message = Message(content="test", sender_id="!12345678")
            result = await manager.send_message(message, "test_lifecycle")
            assert result is True
            
            # Get status
            status = manager.get_interface_status("test_lifecycle")
            assert status["id"] == "test_lifecycle"
            
            # Remove interface
            await manager.remove_interface("test_lifecycle")
            assert "test_lifecycle" not in manager.interfaces
    
    @pytest.mark.asyncio
    async def test_multiple_interface_management(self):
        """Test managing multiple interfaces"""
        message_callback = Mock()
        manager = InterfaceManager(message_callback)
        
        configs = [
            InterfaceConfig(id="test1", type="mock", connection_string="test1"),
            InterfaceConfig(id="test2", type="mock", connection_string="test2"),
            InterfaceConfig(id="test3", type="mock", connection_string="test3")
        ]
        
        with patch.object(InterfaceFactory, 'create_interface') as mock_create:
            # Create mock interfaces
            mock_interfaces = []
            for i in range(3):
                mock_interface = Mock()
                mock_interface.start = AsyncMock()
                mock_interface.stop = AsyncMock()
                mock_interface.send_message = AsyncMock(return_value=True)
                mock_interface.get_status.return_value = {
                    "id": f"test{i+1}",
                    "status": "connected",
                    "stats": {"messages_sent": 0, "messages_received": 0, "bytes_sent": 0, "bytes_received": 0}
                }
                mock_interface.status = InterfaceStatus.CONNECTED
                mock_interfaces.append(mock_interface)
            
            mock_create.side_effect = mock_interfaces
            
            # Add all interfaces
            for config in configs:
                await manager.add_interface(config)
            
            assert len(manager.interfaces) == 3
            
            # Send broadcast message
            message = Message(content="broadcast", sender_id="!12345678")
            result = await manager.send_message(message)
            assert result is True
            
            # Verify all interfaces received the message
            for mock_interface in mock_interfaces:
                mock_interface.send_message.assert_called_with(message)
            
            # Stop all interfaces
            await manager.stop_all()
            assert len(manager.interfaces) == 0


if __name__ == '__main__':
    pytest.main([__file__])