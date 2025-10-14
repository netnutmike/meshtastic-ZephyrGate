"""
Asset Tracking Data Models

Defines data structures for asset tracking, check-in/check-out operations,
and accountability reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class CheckInAction(Enum):
    """Check-in action types"""
    CHECKIN = "checkin"
    CHECKOUT = "checkout"


class AssetStatus(Enum):
    """Asset status types"""
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    UNKNOWN = "unknown"


@dataclass
class CheckInRecord:
    """Represents a check-in/check-out record"""
    id: Optional[int] = None
    node_id: str = ""
    action: CheckInAction = CheckInAction.CHECKIN
    notes: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'node_id': self.node_id,
            'action': self.action.value,
            'notes': self.notes,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckInRecord':
        """Create from dictionary (database row)"""
        return cls(
            id=data.get('id'),
            node_id=data.get('node_id', ''),
            action=CheckInAction(data.get('action', 'checkin')),
            notes=data.get('notes'),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat()))
        )


@dataclass
class AssetInfo:
    """Information about an asset (user/node)"""
    node_id: str
    short_name: str
    long_name: Optional[str] = None
    status: AssetStatus = AssetStatus.UNKNOWN
    last_checkin: Optional[datetime] = None
    last_checkout: Optional[datetime] = None
    current_notes: Optional[str] = None
    checkin_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'node_id': self.node_id,
            'short_name': self.short_name,
            'long_name': self.long_name,
            'status': self.status.value,
            'last_checkin': self.last_checkin.isoformat() if self.last_checkin else None,
            'last_checkout': self.last_checkout.isoformat() if self.last_checkout else None,
            'current_notes': self.current_notes,
            'checkin_count': self.checkin_count
        }


@dataclass
class ChecklistSummary:
    """Summary of current checklist status"""
    total_users: int = 0
    checked_in_users: int = 0
    checked_out_users: int = 0
    unknown_status_users: int = 0
    assets: List[AssetInfo] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_users': self.total_users,
            'checked_in_users': self.checked_in_users,
            'checked_out_users': self.checked_out_users,
            'unknown_status_users': self.unknown_status_users,
            'assets': [asset.to_dict() for asset in self.assets]
        }


@dataclass
class CheckInStats:
    """Statistics about check-in activity"""
    total_checkins: int = 0
    total_checkouts: int = 0
    unique_users: int = 0
    most_active_user: Optional[str] = None
    most_active_count: int = 0
    recent_activity: List[CheckInRecord] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_checkins': self.total_checkins,
            'total_checkouts': self.total_checkouts,
            'unique_users': self.unique_users,
            'most_active_user': self.most_active_user,
            'most_active_count': self.most_active_count,
            'recent_activity': [record.to_dict() for record in self.recent_activity]
        }