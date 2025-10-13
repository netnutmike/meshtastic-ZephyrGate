"""
BBS Data Models for ZephyrGate

Comprehensive data models for the Bulletin Board System including
bulletins, mail, channels, and JS8Call integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid
import hashlib


class BBSMessageType(Enum):
    """BBS message types"""
    BULLETIN = "bulletin"
    MAIL = "mail"
    CHANNEL_INFO = "channel_info"
    JS8CALL = "js8call"


class MailStatus(Enum):
    """Mail message status"""
    UNREAD = "unread"
    READ = "read"
    DELETED = "deleted"


class ChannelType(Enum):
    """Channel types"""
    REPEATER = "repeater"
    SIMPLEX = "simplex"
    DIGITAL = "digital"
    EMERGENCY = "emergency"
    OTHER = "other"


class JS8CallPriority(Enum):
    """JS8Call message priority"""
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"


@dataclass
class BBSBulletin:
    """BBS bulletin message"""
    id: int = 0  # Auto-increment database ID
    board: str = "general"
    sender_id: str = ""
    sender_name: str = ""
    subject: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    read_by: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Ensure read_by is a set"""
        if isinstance(self.read_by, list):
            self.read_by = set(self.read_by)
    
    def mark_read_by(self, user_id: str):
        """Mark bulletin as read by user"""
        self.read_by.add(user_id)
    
    def is_read_by(self, user_id: str) -> bool:
        """Check if bulletin was read by user"""
        return user_id in self.read_by
    
    def get_preview(self, max_length: int = 100) -> str:
        """Get content preview"""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'board': self.board,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'subject': self.subject,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'unique_id': self.unique_id,
            'read_by': list(self.read_by)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BBSBulletin':
        """Create from dictionary"""
        bulletin = cls()
        bulletin.id = data.get('id', 0)
        bulletin.board = data.get('board', 'general')
        bulletin.sender_id = data.get('sender_id', '')
        bulletin.sender_name = data.get('sender_name', '')
        bulletin.subject = data.get('subject', '')
        bulletin.content = data.get('content', '')
        bulletin.unique_id = data.get('unique_id', str(uuid.uuid4()))
        bulletin.read_by = set(data.get('read_by', []))
        
        # Parse timestamp
        timestamp_str = data.get('timestamp')
        if timestamp_str:
            if isinstance(timestamp_str, str):
                bulletin.timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                bulletin.timestamp = timestamp_str
        
        return bulletin


@dataclass
class BBSMail:
    """BBS mail message"""
    id: int = 0  # Auto-increment database ID
    sender_id: str = ""
    sender_name: str = ""
    recipient_id: str = ""
    subject: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: MailStatus = MailStatus.UNREAD
    
    def mark_read(self):
        """Mark mail as read"""
        if self.status == MailStatus.UNREAD:
            self.status = MailStatus.READ
            self.read_at = datetime.utcnow()
    
    def is_read(self) -> bool:
        """Check if mail is read"""
        return self.status == MailStatus.READ
    
    def is_unread(self) -> bool:
        """Check if mail is unread"""
        return self.status == MailStatus.UNREAD
    
    def get_age_string(self) -> str:
        """Get human-readable age"""
        now = datetime.utcnow()
        delta = now - self.timestamp
        
        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'recipient_id': self.recipient_id,
            'subject': self.subject,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'unique_id': self.unique_id,
            'status': self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BBSMail':
        """Create from dictionary"""
        mail = cls()
        mail.id = data.get('id', 0)
        mail.sender_id = data.get('sender_id', '')
        mail.sender_name = data.get('sender_name', '')
        mail.recipient_id = data.get('recipient_id', '')
        mail.subject = data.get('subject', '')
        mail.content = data.get('content', '')
        mail.unique_id = data.get('unique_id', str(uuid.uuid4()))
        
        # Parse timestamps
        timestamp_str = data.get('timestamp')
        if timestamp_str:
            if isinstance(timestamp_str, str):
                mail.timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                mail.timestamp = timestamp_str
        
        read_at_str = data.get('read_at')
        if read_at_str:
            if isinstance(read_at_str, str):
                mail.read_at = datetime.fromisoformat(read_at_str.replace('Z', '+00:00'))
            else:
                mail.read_at = read_at_str
        
        # Parse status
        status_str = data.get('status', 'unread')
        try:
            mail.status = MailStatus(status_str)
        except ValueError:
            mail.status = MailStatus.UNREAD
        
        return mail


@dataclass
class BBSChannel:
    """BBS channel directory entry"""
    id: int = 0  # Auto-increment database ID
    name: str = ""
    frequency: str = ""
    description: str = ""
    channel_type: ChannelType = ChannelType.OTHER
    location: str = ""
    coverage_area: str = ""
    tone: str = ""
    offset: str = ""
    added_by: str = ""
    added_at: datetime = field(default_factory=datetime.utcnow)
    verified: bool = False
    active: bool = True
    
    def get_full_description(self) -> str:
        """Get full channel description"""
        parts = [self.name]
        
        if self.frequency:
            parts.append(f"Freq: {self.frequency}")
        
        if self.tone:
            parts.append(f"Tone: {self.tone}")
        
        if self.offset:
            parts.append(f"Offset: {self.offset}")
        
        if self.location:
            parts.append(f"Location: {self.location}")
        
        if self.description:
            parts.append(self.description)
        
        return " | ".join(parts)
    
    def matches_search(self, query: str) -> bool:
        """Check if channel matches search query"""
        query = query.lower()
        searchable_fields = [
            self.name.lower(),
            self.frequency.lower(),
            self.description.lower(),
            self.location.lower(),
            self.coverage_area.lower(),
            self.channel_type.value.lower()
        ]
        
        return any(query in field for field in searchable_fields)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'frequency': self.frequency,
            'description': self.description,
            'channel_type': self.channel_type.value,
            'location': self.location,
            'coverage_area': self.coverage_area,
            'tone': self.tone,
            'offset': self.offset,
            'added_by': self.added_by,
            'added_at': self.added_at.isoformat(),
            'verified': self.verified,
            'active': self.active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BBSChannel':
        """Create from dictionary"""
        channel = cls()
        channel.id = data.get('id', 0)
        channel.name = data.get('name', '')
        channel.frequency = data.get('frequency', '')
        channel.description = data.get('description', '')
        channel.location = data.get('location', '')
        channel.coverage_area = data.get('coverage_area', '')
        channel.tone = data.get('tone', '')
        channel.offset = data.get('offset', '')
        channel.added_by = data.get('added_by', '')
        channel.verified = data.get('verified', False)
        channel.active = data.get('active', True)
        
        # Parse channel type
        channel_type_str = data.get('channel_type', 'other')
        try:
            channel.channel_type = ChannelType(channel_type_str)
        except ValueError:
            channel.channel_type = ChannelType.OTHER
        
        # Parse timestamp
        added_at_str = data.get('added_at')
        if added_at_str:
            if isinstance(added_at_str, str):
                channel.added_at = datetime.fromisoformat(added_at_str.replace('Z', '+00:00'))
            else:
                channel.added_at = added_at_str
        
        return channel


@dataclass
class JS8CallMessage:
    """JS8Call integration message"""
    id: int = 0  # Auto-increment database ID
    callsign: str = ""
    group: str = ""
    message: str = ""
    frequency: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: JS8CallPriority = JS8CallPriority.NORMAL
    forwarded_to_mesh: bool = False
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def is_urgent(self) -> bool:
        """Check if message is urgent"""
        return self.priority in [JS8CallPriority.URGENT, JS8CallPriority.EMERGENCY]
    
    def is_emergency(self) -> bool:
        """Check if message is emergency"""
        return self.priority == JS8CallPriority.EMERGENCY
    
    def should_forward_to_mesh(self) -> bool:
        """Check if message should be forwarded to mesh"""
        return not self.forwarded_to_mesh and (self.is_urgent() or self.is_emergency())
    
    def generate_mesh_message(self) -> str:
        """Generate message for mesh forwarding"""
        prefix = ""
        if self.is_emergency():
            prefix = "🚨 EMERGENCY JS8Call: "
        elif self.is_urgent():
            prefix = "⚠️ URGENT JS8Call: "
        else:
            prefix = "📻 JS8Call: "
        
        return f"{prefix}{self.callsign} on {self.frequency}: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'callsign': self.callsign,
            'group': self.group,
            'message': self.message,
            'frequency': self.frequency,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'forwarded_to_mesh': self.forwarded_to_mesh,
            'unique_id': self.unique_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JS8CallMessage':
        """Create from dictionary"""
        msg = cls()
        msg.id = data.get('id', 0)
        msg.callsign = data.get('callsign', '')
        msg.group = data.get('group', '')
        msg.message = data.get('message', '')
        msg.frequency = data.get('frequency', '')
        msg.forwarded_to_mesh = data.get('forwarded_to_mesh', False)
        msg.unique_id = data.get('unique_id', str(uuid.uuid4()))
        
        # Parse priority
        priority_str = data.get('priority', 'normal')
        try:
            msg.priority = JS8CallPriority(priority_str)
        except ValueError:
            msg.priority = JS8CallPriority.NORMAL
        
        # Parse timestamp
        timestamp_str = data.get('timestamp')
        if timestamp_str:
            if isinstance(timestamp_str, str):
                msg.timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                msg.timestamp = timestamp_str
        
        return msg


@dataclass
class BBSSession:
    """BBS user session state"""
    user_id: str
    current_menu: str = "main"
    menu_stack: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def push_menu(self, menu: str):
        """Push current menu to stack and set new menu"""
        self.menu_stack.append(self.current_menu)
        self.current_menu = menu
        self.last_activity = datetime.utcnow()
    
    def pop_menu(self) -> str:
        """Pop menu from stack"""
        if self.menu_stack:
            self.current_menu = self.menu_stack.pop()
        else:
            self.current_menu = "main"
        self.last_activity = datetime.utcnow()
        return self.current_menu
    
    def set_context(self, key: str, value: Any):
        """Set context value"""
        self.context[key] = value
        self.last_activity = datetime.utcnow()
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value"""
        return self.context.get(key, default)
    
    def clear_context(self):
        """Clear session context"""
        self.context.clear()
        self.last_activity = datetime.utcnow()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session is expired"""
        now = datetime.utcnow()
        delta = now - self.last_activity
        return delta.total_seconds() > (timeout_minutes * 60)


def generate_unique_id(content: str, sender_id: str, timestamp: datetime) -> str:
    """Generate unique ID for BBS messages to prevent duplicates"""
    # Create a hash from content, sender, and timestamp
    hash_input = f"{content}:{sender_id}:{timestamp.isoformat()}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def validate_bulletin_subject(subject: str) -> bool:
    """Validate bulletin subject"""
    if not subject or len(subject.strip()) == 0:
        return False
    if len(subject) > 100:
        return False
    return True


def validate_bulletin_content(content: str) -> bool:
    """Validate bulletin content"""
    if not content or len(content.strip()) == 0:
        return False
    if len(content) > 2000:  # Reasonable limit for mesh networks
        return False
    return True


def validate_mail_subject(subject: str) -> bool:
    """Validate mail subject"""
    if not subject or len(subject.strip()) == 0:
        return False
    if len(subject) > 100:
        return False
    return True


def validate_mail_content(content: str) -> bool:
    """Validate mail content"""
    if not content or len(content.strip()) == 0:
        return False
    if len(content) > 1000:  # Smaller limit for private mail
        return False
    return True


def validate_channel_name(name: str) -> bool:
    """Validate channel name"""
    if not name or len(name.strip()) == 0:
        return False
    if len(name) > 50:
        return False
    return True


def validate_frequency(frequency: str) -> bool:
    """Validate frequency format"""
    if not frequency:
        return True  # Optional field
    
    # Basic frequency validation (MHz format)
    try:
        freq_parts = frequency.replace('MHz', '').replace('mhz', '').strip()
        float(freq_parts)
        return True
    except ValueError:
        return False