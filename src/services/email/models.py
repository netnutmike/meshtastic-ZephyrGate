"""
Email Gateway Data Models

Data structures for email gateway functionality including email messages,
queue items, blocklist entries, and configuration models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class EmailDirection(Enum):
    """Direction of email processing"""
    MESH_TO_EMAIL = "mesh_to_email"
    EMAIL_TO_MESH = "email_to_mesh"
    BROADCAST = "broadcast"
    GROUP_MESSAGE = "group_message"


class EmailStatus(Enum):
    """Status of email processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"
    BLOCKED = "blocked"
    EXPIRED = "expired"


class EmailPriority(Enum):
    """Email processing priority"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    EMERGENCY = 5


@dataclass
class EmailAddress:
    """Email address with optional display name"""
    address: str
    name: Optional[str] = None
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.address}>"
        return self.address
    
    @classmethod
    def parse(cls, email_str: str) -> 'EmailAddress':
        """Parse email string into EmailAddress object"""
        email_str = email_str.strip()
        
        if '<' in email_str and '>' in email_str:
            # Format: "Name <email@domain.com>"
            name_part = email_str[:email_str.find('<')].strip().strip('"\'')
            email_part = email_str[email_str.find('<')+1:email_str.find('>')].strip()
            return cls(address=email_part, name=name_part if name_part else None)
        else:
            # Format: "email@domain.com"
            return cls(address=email_str)


@dataclass
class EmailMessage:
    """Email message data structure"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    direction: EmailDirection = EmailDirection.MESH_TO_EMAIL
    status: EmailStatus = EmailStatus.PENDING
    priority: EmailPriority = EmailPriority.NORMAL
    
    # Email headers
    from_address: Optional[EmailAddress] = None
    to_addresses: List[EmailAddress] = field(default_factory=list)
    cc_addresses: List[EmailAddress] = field(default_factory=list)
    bcc_addresses: List[EmailAddress] = field(default_factory=list)
    reply_to: Optional[EmailAddress] = None
    subject: str = ""
    
    # Content
    body_text: str = ""
    body_html: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Mesh network context
    mesh_sender_id: Optional[str] = None
    mesh_sender_name: Optional[str] = None
    mesh_recipient_id: Optional[str] = None
    mesh_channel: Optional[int] = None
    mesh_interface_id: Optional[str] = None
    
    # Processing metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_delay_seconds: int = 300  # 5 minutes
    expires_at: Optional[datetime] = None
    
    # Error tracking
    last_error: Optional[str] = None
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Tags and metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str, error_type: str = "general"):
        """Add error to history"""
        self.last_error = error
        self.error_history.append({
            'timestamp': datetime.utcnow(),
            'error': error,
            'error_type': error_type,
            'retry_count': self.retry_count
        })
        self.updated_at = datetime.utcnow()
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return (
            self.status in [EmailStatus.FAILED, EmailStatus.RETRY] and
            self.retry_count < self.max_retries and
            (self.expires_at is None or datetime.utcnow() < self.expires_at)
        )
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        return self.expires_at is not None and datetime.utcnow() > self.expires_at


@dataclass
class EmailQueueItem:
    """Email queue item for processing"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email_message: EmailMessage = field(default_factory=EmailMessage)
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    processing_started_at: Optional[datetime] = None
    processing_node: Optional[str] = None
    
    def is_ready_for_processing(self) -> bool:
        """Check if item is ready for processing"""
        return (
            datetime.utcnow() >= self.scheduled_at and
            self.processing_started_at is None and
            not self.email_message.is_expired()
        )


@dataclass
class BlocklistEntry:
    """Email blocklist entry"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email_pattern: str = ""  # Email address or pattern (supports wildcards)
    reason: str = ""
    blocked_by: Optional[str] = None  # User who added the block
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    
    # Block statistics
    block_count: int = 0
    last_blocked_at: Optional[datetime] = None
    
    def matches(self, email_address: str) -> bool:
        """Check if email address matches this blocklist entry"""
        if not self.is_active:
            return False
        
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        
        email_lower = email_address.lower()
        pattern_lower = self.email_pattern.lower()
        
        # Exact match
        if pattern_lower == email_lower:
            return True
        
        # Wildcard patterns
        if '*' in pattern_lower:
            import fnmatch
            return fnmatch.fnmatch(email_lower, pattern_lower)
        
        # Domain match (if pattern starts with @)
        if pattern_lower.startswith('@'):
            domain = pattern_lower[1:]
            return email_lower.endswith('@' + domain)
        
        return False
    
    def record_block(self):
        """Record that this entry blocked an email"""
        self.block_count += 1
        self.last_blocked_at = datetime.utcnow()


@dataclass
class EmailConfiguration:
    """Email service configuration"""
    # SMTP settings
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout: int = 30
    
    # IMAP settings
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True
    imap_timeout: int = 30
    imap_folder: str = "INBOX"
    imap_check_interval: int = 300  # 5 minutes
    
    # Gateway settings
    gateway_email: str = ""  # Main gateway email address
    gateway_name: str = "Meshtastic Gateway"
    
    # Message processing
    max_message_size: int = 1024 * 1024  # 1MB
    max_attachments: int = 5
    max_attachment_size: int = 512 * 1024  # 512KB
    message_retention_days: int = 30
    
    # Queue settings
    queue_max_size: int = 1000
    queue_batch_size: int = 10
    queue_processing_interval: int = 60  # 1 minute
    retry_delay_seconds: int = 300  # 5 minutes
    max_retries: int = 3
    
    # Security settings
    enable_blocklist: bool = True
    enable_sender_verification: bool = True
    authorized_senders: List[str] = field(default_factory=list)
    authorized_domains: List[str] = field(default_factory=list)
    enable_spam_detection: bool = True
    spam_keywords: List[str] = field(default_factory=list)
    
    # Broadcast settings
    enable_broadcasts: bool = True
    broadcast_authorized_senders: List[str] = field(default_factory=list)
    broadcast_confirmation_required: bool = True
    
    # Tag-based messaging
    enable_tag_messaging: bool = True
    tag_prefix: str = "#"
    
    # Formatting settings
    email_footer: str = "\n\n---\nSent via Meshtastic Gateway"
    mesh_message_prefix: str = "[Email] "
    include_original_headers: bool = False
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.smtp_host:
            errors.append("SMTP host is required")
        
        if not self.smtp_username:
            errors.append("SMTP username is required")
        
        if not self.smtp_password:
            errors.append("SMTP password is required")
        
        if not self.imap_host:
            errors.append("IMAP host is required")
        
        if not self.imap_username:
            errors.append("IMAP username is required")
        
        if not self.imap_password:
            errors.append("IMAP password is required")
        
        if not self.gateway_email:
            errors.append("Gateway email address is required")
        
        if self.smtp_port <= 0 or self.smtp_port > 65535:
            errors.append("Invalid SMTP port")
        
        if self.imap_port <= 0 or self.imap_port > 65535:
            errors.append("Invalid IMAP port")
        
        if self.max_message_size <= 0:
            errors.append("Max message size must be positive")
        
        if self.queue_max_size <= 0:
            errors.append("Queue max size must be positive")
        
        return errors


@dataclass
class EmailStatistics:
    """Email gateway statistics"""
    # Message counts
    total_messages_processed: int = 0
    mesh_to_email_count: int = 0
    email_to_mesh_count: int = 0
    broadcast_count: int = 0
    group_message_count: int = 0
    
    # Status counts
    sent_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    retry_count: int = 0
    
    # Queue statistics
    current_queue_size: int = 0
    max_queue_size_reached: int = 0
    average_processing_time_seconds: float = 0.0
    
    # Error statistics
    smtp_errors: int = 0
    imap_errors: int = 0
    parsing_errors: int = 0
    validation_errors: int = 0
    
    # Security statistics
    blocked_senders: int = 0
    spam_detected: int = 0
    unauthorized_attempts: int = 0
    
    # Performance metrics
    messages_per_hour: float = 0.0
    uptime_seconds: int = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)
    
    def reset(self):
        """Reset statistics"""
        self.__init__()
        self.last_reset = datetime.utcnow()


@dataclass
class UserEmailMapping:
    """Mapping between mesh users and email addresses"""
    mesh_user_id: str = ""
    mesh_user_name: str = ""
    email_address: str = ""
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    # Preferences
    receive_broadcasts: bool = True
    receive_group_messages: bool = True
    email_format: str = "text"  # "text" or "html"
    include_mesh_metadata: bool = False
    
    def has_tag(self, tag: str) -> bool:
        """Check if user has a specific tag"""
        return tag.lower() in [t.lower() for t in self.tags]
    
    def add_tag(self, tag: str):
        """Add a tag to the user"""
        if not self.has_tag(tag):
            self.tags.append(tag)
    
    def remove_tag(self, tag: str):
        """Remove a tag from the user"""
        self.tags = [t for t in self.tags if t.lower() != tag.lower()]