"""
Mock objects for Meshtastic interfaces and related components.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import dataclass


@dataclass
class MockMeshtasticMessage:
    """Mock Meshtastic message object."""
    id: str
    sender: str
    recipient: Optional[str]
    channel: int
    text: str
    timestamp: datetime
    snr: Optional[float] = None
    rssi: Optional[float] = None
    hop_limit: int = 3
    want_ack: bool = False


@dataclass
class MockNodeInfo:
    """Mock node information."""
    num: int
    user: Dict[str, Any]
    position: Optional[Dict[str, Any]] = None
    device_metrics: Optional[Dict[str, Any]] = None


class MockMeshtasticInterface:
    """Mock Meshtastic interface for testing."""
    
    def __init__(self, interface_type: str = "serial", **kwargs):
        self.interface_type = interface_type
        self.connected = False
        self.node_id = kwargs.get("node_id", "!12345678")
        self.channel = kwargs.get("channel", 0)
        self.message_callbacks: List[Callable] = []
        self.connection_callbacks: List[Callable] = []
        self.nodes: Dict[str, MockNodeInfo] = {}
        self.sent_messages: List[MockMeshtasticMessage] = []
        self.received_messages: List[MockMeshtasticMessage] = []
        
        # Configuration based on interface type
        if interface_type == "serial":
            self.port = kwargs.get("port", "/dev/ttyUSB0")
        elif interface_type == "tcp":
            self.host = kwargs.get("host", "localhost")
            self.port = kwargs.get("port", 4403)
        elif interface_type == "ble":
            self.address = kwargs.get("address", "AA:BB:CC:DD:EE:FF")
    
    async def connect(self) -> bool:
        """Mock connection to Meshtastic device."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True
        
        # Notify connection callbacks
        for callback in self.connection_callbacks:
            await callback(True)
        
        return True
    
    async def disconnect(self):
        """Mock disconnection from Meshtastic device."""
        self.connected = False
        
        # Notify connection callbacks
        for callback in self.connection_callbacks:
            await callback(False)
    
    async def send_message(self, text: str, destination: Optional[str] = None, 
                          channel: int = 0, want_ack: bool = False) -> bool:
        """Mock sending a message."""
        if not self.connected:
            raise ConnectionError("Interface not connected")
        
        message = MockMeshtasticMessage(
            id=f"msg_{len(self.sent_messages):04d}",
            sender=self.node_id,
            recipient=destination,
            channel=channel,
            text=text,
            timestamp=datetime.utcnow(),
            want_ack=want_ack
        )
        
        self.sent_messages.append(message)
        await asyncio.sleep(0.05)  # Simulate transmission delay
        return True
    
    def add_message_callback(self, callback: Callable):
        """Add callback for received messages."""
        self.message_callbacks.append(callback)
    
    def add_connection_callback(self, callback: Callable):
        """Add callback for connection status changes."""
        self.connection_callbacks.append(callback)
    
    async def simulate_received_message(self, text: str, sender: str = "!87654321",
                                       channel: int = 0, snr: float = 10.0,
                                       rssi: float = -50.0):
        """Simulate receiving a message from the mesh."""
        message = MockMeshtasticMessage(
            id=f"rx_{len(self.received_messages):04d}",
            sender=sender,
            recipient=self.node_id,
            channel=channel,
            text=text,
            timestamp=datetime.utcnow(),
            snr=snr,
            rssi=rssi
        )
        
        self.received_messages.append(message)
        
        # Notify message callbacks
        for callback in self.message_callbacks:
            await callback(message)
    
    def add_node(self, node_id: str, short_name: str, long_name: str = "",
                 lat: Optional[float] = None, lon: Optional[float] = None,
                 altitude: Optional[float] = None):
        """Add a mock node to the network."""
        user_info = {
            "id": node_id,
            "shortName": short_name,
            "longName": long_name or short_name
        }
        
        position_info = None
        if lat is not None and lon is not None:
            position_info = {
                "latitude": lat,
                "longitude": lon,
                "altitude": altitude or 0
            }
        
        self.nodes[node_id] = MockNodeInfo(
            num=len(self.nodes) + 1,
            user=user_info,
            position=position_info
        )
    
    def get_nodes(self) -> Dict[str, MockNodeInfo]:
        """Get all known nodes."""
        return self.nodes.copy()
    
    def get_node_info(self, node_id: str) -> Optional[MockNodeInfo]:
        """Get information about a specific node."""
        return self.nodes.get(node_id)


class MockMeshtasticInterfaceFactory:
    """Factory for creating mock Meshtastic interfaces."""
    
    @staticmethod
    def create_serial_interface(port: str = "/dev/ttyUSB0", **kwargs) -> MockMeshtasticInterface:
        """Create a mock serial interface."""
        return MockMeshtasticInterface("serial", port=port, **kwargs)
    
    @staticmethod
    def create_tcp_interface(host: str = "localhost", port: int = 4403, **kwargs) -> MockMeshtasticInterface:
        """Create a mock TCP interface."""
        return MockMeshtasticInterface("tcp", host=host, port=port, **kwargs)
    
    @staticmethod
    def create_ble_interface(address: str = "AA:BB:CC:DD:EE:FF", **kwargs) -> MockMeshtasticInterface:
        """Create a mock BLE interface."""
        return MockMeshtasticInterface("ble", address=address, **kwargs)


# Factory functions for creating mock interfaces (pytest fixtures will be added when pytest is available)
def create_mock_meshtastic_interface():
    """Create a mock Meshtastic interface with default nodes."""
    interface = MockMeshtasticInterface()
    
    # Add some default nodes
    interface.add_node("!12345678", "TEST1", "Test Node One", 40.7128, -74.0060)
    interface.add_node("!87654321", "TEST2", "Test Node Two", 40.7589, -73.9851)
    interface.add_node("!11111111", "AIRCRAFT", "High Altitude Node", 40.7500, -74.0000, 10000)
    
    return interface


def create_mock_multiple_interfaces():
    """Create multiple mock interfaces for testing."""
    return {
        "serial_0": MockMeshtasticInterfaceFactory.create_serial_interface(node_id="!12345678"),
        "tcp_0": MockMeshtasticInterfaceFactory.create_tcp_interface(node_id="!87654321"),
        "ble_0": MockMeshtasticInterfaceFactory.create_ble_interface(node_id="!11111111")
    }


# Pytest fixtures (only available when pytest is installed)
try:
    import pytest
    
    @pytest.fixture
    def mock_meshtastic_interface():
        """Provide a mock Meshtastic interface."""
        return create_mock_meshtastic_interface()

    @pytest.fixture
    def mock_serial_interface():
        """Provide a mock serial Meshtastic interface."""
        return MockMeshtasticInterfaceFactory.create_serial_interface()

    @pytest.fixture
    def mock_tcp_interface():
        """Provide a mock TCP Meshtastic interface."""
        return MockMeshtasticInterfaceFactory.create_tcp_interface()

    @pytest.fixture
    def mock_ble_interface():
        """Provide a mock BLE Meshtastic interface."""
        return MockMeshtasticInterfaceFactory.create_ble_interface()

    @pytest.fixture
    def mock_multiple_interfaces():
        """Provide multiple mock interfaces for testing."""
        return create_mock_multiple_interfaces()

except ImportError:
    # pytest not available, skip fixture definitions
    pass