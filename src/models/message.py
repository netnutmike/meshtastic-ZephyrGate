"""
Message data models for ZephyrGate

Defines the core message structures used throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid


class MessageType(Enum):
    """Message type enumeration"""
    TEXT = "text"
    POSITION = "position"
    NODEINFO = "nodeinfo"
    ROUTING = "routing"
    ADMIN = "admin"
    TELEMETRY = "telemetry"
    RANGE_TEST = "range_test"
    DETECTION_SENSOR = "detection_sensor"
    REPLY = "reply"
    IP_TUNNEL = "ip_tunnel"
    SERIAL = "serial"
    STORE_FORWARD = "store_forward"
    UNKNOWN = "unknown"


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    EMERGENCY = 4


class SOSType(Enum):
    """SOS alert types"""
    SOS = "SOS"          # General emergency
    SOSP = "SOSP"        # Police needed
    SOSF = "SOSF"        # Fire/EMS needed
    SOSM = "SOSM"        # Medical emergency


class IncidentStatus(Enum):
    """SOS incident status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESPONDING = "responding"
    CLEARED = "cleared"
    CANCELLED = "cancelled"


@dataclass
class Message:
    """Core message structure"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    recipient_id: Optional[str] = None
    channel: int = 0
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_type: MessageType = MessageType.TEXT
    interface_id: str = ""
    hop_count: int = 0
    snr: Optional[float] = None
    rssi: Optional[float] = None
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_direct_message(self) -> bool:
        """Check if this is a direct message"""
        return self.recipient_id is not None and self.recipient_id != "^all"
    
    def is_broadcast(self) -> bool:
        """Check if this is a broadcast message"""
        return self.recipient_id is None or self.recipient_id == "^all"
    
    def get_signal_quality(self) -> str:
        """Get human-readable signal quality"""
        if self.snr is not None and self.rssi is not None:
            if self.snr > 5:
                return "Excellent"
            elif self.snr > 0:
                return "Good"
            elif self.snr > -5:
                return "Fair"
            else:
                return "Poor"
        return "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'channel': self.channel,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'message_type': self.message_type.value,
            'interface_id': self.interface_id,
            'hop_count': self.hop_count,
            'snr': self.snr,
            'rssi': self.rssi,
            'priority': self.priority.value,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        msg = cls()
        msg.id = data.get('id', str(uuid.uuid4()))
        msg.sender_id = data.get('sender_id', '')
        msg.recipient_id = data.get('recipient_id')
        msg.channel = data.get('channel', 0)
        msg.content = data.get('content', '')
        
        # Parse timestamp
        timestamp_str = data.get('timestamp')
        if timestamp_str:
            if isinstance(timestamp_str, str):
                msg.timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                msg.timestamp = timestamp_str
        
        # Parse message type
        msg_type = data.get('message_type', 'text')
        try:
            msg.message_type = MessageType(msg_type)
        except ValueError:
            msg.message_type = MessageType.UNKNOWN
        
        msg.interface_id = data.get('interface_id', '')
        msg.hop_count = data.get('hop_count', 0)
        msg.snr = data.get('snr')
        msg.rssi = data.get('rssi')
        
        # Parse priority
        priority = data.get('priority', 'normal')
        try:
            msg.priority = MessagePriority(priority) if isinstance(priority, int) else MessagePriority[priority.upper()]
        except (ValueError, KeyError):
            msg.priority = MessagePriority.NORMAL
        
        msg.metadata = data.get('metadata', {})
        
        return msg


@dataclass
class QueuedMessage:
    """Message in the processing queue"""
    message: Message
    retry_count: int = 0
    max_retries: int = 3
    next_retry: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def should_retry(self) -> bool:
        """Check if message should be retried"""
        if self.retry_count >= self.max_retries:
            return False
        
        if self.next_retry is None:
            return True
        
        return datetime.utcnow() >= self.next_retry
    
    def schedule_retry(self, delay_seconds: int = 30):
        """Schedule next retry attempt"""
        self.retry_count += 1
        self.next_retry = datetime.utcnow().replace(
            second=datetime.utcnow().second + delay_seconds
        )


@dataclass
class UserProfile:
    """User profile data"""
    node_id: str
    short_name: str
    long_name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    permissions: Dict[str, bool] = field(default_factory=dict)
    subscriptions: Dict[str, bool] = field(default_factory=dict)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    location: Optional[Tuple[float, float]] = None
    altitude: Optional[float] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return self.permissions.get(permission, False)
    
    def is_subscribed(self, service: str) -> bool:
        """Check if user is subscribed to a service"""
        return self.subscriptions.get(service, False)
    
    def has_tag(self, tag: str) -> bool:
        """Check if user has specific tag"""
        return tag in self.tags
    
    def is_high_altitude(self, threshold: float = 1000.0) -> bool:
        """Check if user is at high altitude (potential aircraft)"""
        return self.altitude is not None and self.altitude > threshold


@dataclass
class SOSIncident:
    """SOS incident data"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: SOSType = SOSType.SOS
    sender_id: str = ""
    message: str = ""
    location: Optional[Tuple[float, float]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: IncidentStatus = IncidentStatus.ACTIVE
    responders: List[str] = field(default_factory=list)
    acknowledgers: List[str] = field(default_factory=list)
    escalated: bool = False
    cleared_by: Optional[str] = None
    cleared_at: Optional[datetime] = None
    
    def add_responder(self, responder_id: str):
        """Add responder to incident"""
        if responder_id not in self.responders:
            self.responders.append(responder_id)
    
    def add_acknowledger(self, acknowledger_id: str):
        """Add acknowledger to incident"""
        if acknowledger_id not in self.acknowledgers:
            self.acknowledgers.append(acknowledger_id)
    
    def is_active(self) -> bool:
        """Check if incident is still active"""
        return self.status in [IncidentStatus.ACTIVE, IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESPONDING]


@dataclass
class BBSMessage:
    """BBS message data"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    board: str = "general"
    sender_id: str = ""
    sender_name: str = ""
    subject: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    read_by: List[str] = field(default_factory=list)
    
    def mark_read_by(self, user_id: str):
        """Mark message as read by user"""
        if user_id not in self.read_by:
            self.read_by.append(user_id)
    
    def is_read_by(self, user_id: str) -> bool:
        """Check if message was read by user"""
        return user_id in self.read_by


@dataclass
class InterfaceConfig:
    """Meshtastic interface configuration"""
    id: str
    type: str  # 'serial', 'tcp', 'ble'
    enabled: bool = True
    connection_string: str = ""
    retry_interval: int = 30
    max_retries: int = 5
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for this interface"""
        params = {
            'timeout': self.timeout,
            'retry_interval': self.retry_interval,
            'max_retries': self.max_retries
        }
        
        if self.type == 'serial':
            params['port'] = self.connection_string
            params['baudrate'] = self.metadata.get('baudrate', 115200)
        elif self.type == 'tcp':
            if ':' in self.connection_string:
                host, port = self.connection_string.split(':', 1)
                params['host'] = host
                params['port'] = int(port)
            else:
                params['host'] = self.connection_string
                params['port'] = 4403  # Default Meshtastic TCP port
        elif self.type == 'ble':
            params['address'] = self.connection_string
        
        return params