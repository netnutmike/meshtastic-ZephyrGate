"""
User Management Module for Web Administration

Provides user profile management, permissions, subscriptions, and activity tracking.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    from ...models.message import Message
except ImportError:
    from models.message import Message


logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """User permission levels"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SYSTEM = "system"


class SubscriptionType(Enum):
    """Subscription types"""
    WEATHER_ALERTS = "weather_alerts"
    WEATHER_FORECASTS = "weather_forecasts"
    EMERGENCY_ALERTS = "emergency_alerts"
    SYSTEM_NOTIFICATIONS = "system_notifications"
    BBS_NOTIFICATIONS = "bbs_notifications"


@dataclass
class UserActivity:
    """User activity record"""
    timestamp: datetime
    action: str
    details: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class UserProfile:
    """Complete user profile"""
    node_id: str
    short_name: str
    long_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    permissions: Set[PermissionLevel] = field(default_factory=set)
    subscriptions: Set[SubscriptionType] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: Optional[datetime] = None
    last_login: Optional[datetime] = None
    location: Optional[Dict[str, float]] = None
    is_active: bool = True
    notes: str = ""
    activity_history: List[UserActivity] = field(default_factory=list)
    
    # Statistics
    message_count: int = 0
    last_message_time: Optional[datetime] = None
    favorite_channels: List[int] = field(default_factory=list)


@dataclass
class UserStats:
    """User statistics summary"""
    total_users: int
    active_users: int
    new_users_today: int
    total_messages: int
    messages_today: int
    top_users: List[Dict[str, Any]]
    permission_distribution: Dict[str, int]
    subscription_distribution: Dict[str, int]


class UserManager:
    """
    User management service for handling user profiles,
    permissions, subscriptions, and activity tracking.
    """
    
    def __init__(self, database_manager=None):
        self.database_manager = database_manager
        self.logger = logger
        
        # In-memory user storage (would be replaced with database in production)
        self.users: Dict[str, UserProfile] = {}
        
        # Activity tracking
        self.activity_history_limit = 1000
        
        # Default permissions for new users
        self.default_permissions = {PermissionLevel.READ}
        self.default_subscriptions = {
            SubscriptionType.EMERGENCY_ALERTS,
            SubscriptionType.SYSTEM_NOTIFICATIONS
        }
        
        self.logger.info("UserManager initialized")
    
    def create_user(self, node_id: str, short_name: str, long_name: str = "") -> UserProfile:
        """Create a new user profile"""
        try:
            if node_id in self.users:
                self.logger.warning(f"User {node_id} already exists")
                return self.users[node_id]
            
            user = UserProfile(
                node_id=node_id,
                short_name=short_name,
                long_name=long_name or short_name,
                permissions=self.default_permissions.copy(),
                subscriptions=self.default_subscriptions.copy()
            )
            
            self.users[node_id] = user
            
            # Log activity
            self._log_user_activity(
                node_id,
                "user_created",
                f"User profile created for {short_name}"
            )
            
            self.logger.info(f"Created user profile for {node_id} ({short_name})")
            return user
            
        except Exception as e:
            self.logger.error(f"Error creating user {node_id}: {e}")
            raise
    
    def get_user(self, node_id: str) -> Optional[UserProfile]:
        """Get user profile by node ID"""
        return self.users.get(node_id)
    
    def update_user(self, node_id: str, **kwargs) -> bool:
        """Update user profile"""
        try:
            user = self.users.get(node_id)
            if not user:
                self.logger.warning(f"User {node_id} not found for update")
                return False
            
            # Update allowed fields
            allowed_fields = {
                'short_name', 'long_name', 'email', 'phone', 'address',
                'location', 'is_active', 'notes'
            }
            
            updated_fields = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(user, field, value)
                    updated_fields.append(field)
            
            if updated_fields:
                self._log_user_activity(
                    node_id,
                    "profile_updated",
                    f"Updated fields: {', '.join(updated_fields)}"
                )
                
                self.logger.info(f"Updated user {node_id}: {updated_fields}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating user {node_id}: {e}")
            return False
    
    def delete_user(self, node_id: str) -> bool:
        """Delete user profile"""
        try:
            if node_id not in self.users:
                self.logger.warning(f"User {node_id} not found for deletion")
                return False
            
            user = self.users[node_id]
            del self.users[node_id]
            
            self.logger.info(f"Deleted user {node_id} ({user.short_name})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting user {node_id}: {e}")
            return False
    
    def update_permissions(self, node_id: str, permissions: Set[PermissionLevel]) -> bool:
        """Update user permissions"""
        try:
            user = self.users.get(node_id)
            if not user:
                self.logger.warning(f"User {node_id} not found for permission update")
                return False
            
            old_permissions = user.permissions.copy()
            user.permissions = permissions
            
            self._log_user_activity(
                node_id,
                "permissions_updated",
                f"Changed from {[p.value for p in old_permissions]} to {[p.value for p in permissions]}"
            )
            
            self.logger.info(f"Updated permissions for {node_id}: {[p.value for p in permissions]}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating permissions for {node_id}: {e}")
            return False
    
    def update_subscriptions(self, node_id: str, subscriptions: Set[SubscriptionType]) -> bool:
        """Update user subscriptions"""
        try:
            user = self.users.get(node_id)
            if not user:
                self.logger.warning(f"User {node_id} not found for subscription update")
                return False
            
            old_subscriptions = user.subscriptions.copy()
            user.subscriptions = subscriptions
            
            self._log_user_activity(
                node_id,
                "subscriptions_updated",
                f"Changed from {[s.value for s in old_subscriptions]} to {[s.value for s in subscriptions]}"
            )
            
            self.logger.info(f"Updated subscriptions for {node_id}: {[s.value for s in subscriptions]}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating subscriptions for {node_id}: {e}")
            return False
    
    def add_tag(self, node_id: str, tag: str) -> bool:
        """Add tag to user"""
        try:
            user = self.users.get(node_id)
            if not user:
                return False
            
            if tag not in user.tags:
                user.tags.add(tag)
                self._log_user_activity(node_id, "tag_added", f"Added tag: {tag}")
                self.logger.info(f"Added tag '{tag}' to user {node_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding tag to {node_id}: {e}")
            return False
    
    def remove_tag(self, node_id: str, tag: str) -> bool:
        """Remove tag from user"""
        try:
            user = self.users.get(node_id)
            if not user:
                return False
            
            if tag in user.tags:
                user.tags.remove(tag)
                self._log_user_activity(node_id, "tag_removed", f"Removed tag: {tag}")
                self.logger.info(f"Removed tag '{tag}' from user {node_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing tag from {node_id}: {e}")
            return False
    
    def get_users_by_tag(self, tag: str) -> List[UserProfile]:
        """Get all users with a specific tag"""
        return [user for user in self.users.values() if tag in user.tags]
    
    def get_users_by_permission(self, permission: PermissionLevel) -> List[UserProfile]:
        """Get all users with a specific permission"""
        return [user for user in self.users.values() if permission in user.permissions]
    
    def get_users_by_subscription(self, subscription: SubscriptionType) -> List[UserProfile]:
        """Get all users with a specific subscription"""
        return [user for user in self.users.values() if subscription in user.subscriptions]
    
    def update_user_activity(self, node_id: str, message: Message):
        """Update user activity from message"""
        try:
            user = self.users.get(node_id)
            if not user:
                # Auto-create user if they don't exist
                user = self.create_user(
                    node_id=node_id,
                    short_name=f"User-{node_id[-4:]}",
                    long_name=f"Auto-created user {node_id}"
                )
            
            # Update activity
            user.last_seen = message.timestamp
            user.message_count += 1
            user.last_message_time = message.timestamp
            
            # Track favorite channels
            if message.channel not in user.favorite_channels:
                user.favorite_channels.append(message.channel)
            
            # Limit favorite channels list
            if len(user.favorite_channels) > 10:
                user.favorite_channels.pop(0)
            
            self.logger.debug(f"Updated activity for user {node_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating user activity for {node_id}: {e}")
    
    def _log_user_activity(self, node_id: str, action: str, details: str, 
                          ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log user activity"""
        try:
            user = self.users.get(node_id)
            if not user:
                return
            
            activity = UserActivity(
                timestamp=datetime.now(timezone.utc),
                action=action,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            user.activity_history.append(activity)
            
            # Limit activity history
            if len(user.activity_history) > self.activity_history_limit:
                user.activity_history.pop(0)
            
        except Exception as e:
            self.logger.error(f"Error logging activity for {node_id}: {e}")
    
    def get_user_stats(self) -> UserStats:
        """Get user statistics"""
        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            total_users = len(self.users)
            active_users = len([u for u in self.users.values() if u.is_active])
            
            new_users_today = len([
                u for u in self.users.values() 
                if u.created_at >= today_start
            ])
            
            total_messages = sum(u.message_count for u in self.users.values())
            
            messages_today = sum(
                u.message_count for u in self.users.values()
                if u.last_message_time and u.last_message_time >= today_start
            )
            
            # Top users by message count
            top_users = sorted(
                [
                    {
                        "node_id": u.node_id,
                        "short_name": u.short_name,
                        "message_count": u.message_count,
                        "last_seen": u.last_seen.isoformat() if u.last_seen else None
                    }
                    for u in self.users.values()
                ],
                key=lambda x: x["message_count"],
                reverse=True
            )[:10]
            
            # Permission distribution
            permission_dist = {}
            for perm in PermissionLevel:
                permission_dist[perm.value] = len(self.get_users_by_permission(perm))
            
            # Subscription distribution
            subscription_dist = {}
            for sub in SubscriptionType:
                subscription_dist[sub.value] = len(self.get_users_by_subscription(sub))
            
            return UserStats(
                total_users=total_users,
                active_users=active_users,
                new_users_today=new_users_today,
                total_messages=total_messages,
                messages_today=messages_today,
                top_users=top_users,
                permission_distribution=permission_dist,
                subscription_distribution=subscription_dist
            )
            
        except Exception as e:
            self.logger.error(f"Error getting user stats: {e}")
            return UserStats(
                total_users=0, active_users=0, new_users_today=0,
                total_messages=0, messages_today=0, top_users=[],
                permission_distribution={}, subscription_distribution={}
            )
    
    def search_users(self, query: str, limit: int = 50) -> List[UserProfile]:
        """Search users by name, node ID, or email"""
        try:
            query = query.lower()
            results = []
            
            for user in self.users.values():
                if (query in user.node_id.lower() or
                    query in user.short_name.lower() or
                    query in user.long_name.lower() or
                    (user.email and query in user.email.lower())):
                    results.append(user)
                    
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching users: {e}")
            return []
    
    def get_all_users(self, active_only: bool = False) -> List[UserProfile]:
        """Get all users"""
        if active_only:
            return [user for user in self.users.values() if user.is_active]
        return list(self.users.values())
    
    def export_users(self) -> Dict[str, Any]:
        """Export user data for backup"""
        try:
            return {
                "users": {
                    node_id: {
                        "node_id": user.node_id,
                        "short_name": user.short_name,
                        "long_name": user.long_name,
                        "email": user.email,
                        "phone": user.phone,
                        "address": user.address,
                        "tags": list(user.tags),
                        "permissions": [p.value for p in user.permissions],
                        "subscriptions": [s.value for s in user.subscriptions],
                        "created_at": user.created_at.isoformat(),
                        "last_seen": user.last_seen.isoformat() if user.last_seen else None,
                        "last_login": user.last_login.isoformat() if user.last_login else None,
                        "location": user.location,
                        "is_active": user.is_active,
                        "notes": user.notes,
                        "message_count": user.message_count,
                        "last_message_time": user.last_message_time.isoformat() if user.last_message_time else None,
                        "favorite_channels": user.favorite_channels,
                        "activity_history": [
                            {
                                "timestamp": a.timestamp.isoformat(),
                                "action": a.action,
                                "details": a.details,
                                "ip_address": a.ip_address,
                                "user_agent": a.user_agent
                            }
                            for a in user.activity_history[-100:]  # Last 100 activities
                        ]
                    }
                    for node_id, user in self.users.items()
                },
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_users": len(self.users)
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting users: {e}")
            return {}
    
    def import_users(self, data: Dict[str, Any]) -> bool:
        """Import user data from backup"""
        try:
            if "users" not in data:
                self.logger.error("Invalid import data: missing 'users' key")
                return False
            
            imported_count = 0
            
            for node_id, user_data in data["users"].items():
                try:
                    # Create user profile
                    user = UserProfile(
                        node_id=user_data["node_id"],
                        short_name=user_data["short_name"],
                        long_name=user_data["long_name"],
                        email=user_data.get("email"),
                        phone=user_data.get("phone"),
                        address=user_data.get("address"),
                        tags=set(user_data.get("tags", [])),
                        permissions=set(PermissionLevel(p) for p in user_data.get("permissions", [])),
                        subscriptions=set(SubscriptionType(s) for s in user_data.get("subscriptions", [])),
                        created_at=datetime.fromisoformat(user_data["created_at"]),
                        last_seen=datetime.fromisoformat(user_data["last_seen"]) if user_data.get("last_seen") else None,
                        last_login=datetime.fromisoformat(user_data["last_login"]) if user_data.get("last_login") else None,
                        location=user_data.get("location"),
                        is_active=user_data.get("is_active", True),
                        notes=user_data.get("notes", ""),
                        message_count=user_data.get("message_count", 0),
                        last_message_time=datetime.fromisoformat(user_data["last_message_time"]) if user_data.get("last_message_time") else None,
                        favorite_channels=user_data.get("favorite_channels", [])
                    )
                    
                    # Import activity history
                    for activity_data in user_data.get("activity_history", []):
                        activity = UserActivity(
                            timestamp=datetime.fromisoformat(activity_data["timestamp"]),
                            action=activity_data["action"],
                            details=activity_data["details"],
                            ip_address=activity_data.get("ip_address"),
                            user_agent=activity_data.get("user_agent")
                        )
                        user.activity_history.append(activity)
                    
                    self.users[node_id] = user
                    imported_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error importing user {node_id}: {e}")
                    continue
            
            self.logger.info(f"Imported {imported_count} users")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing users: {e}")
            return False