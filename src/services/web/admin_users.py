"""
Web Admin User Management

Manages web administration users with role-based access control.
Users are stored in the configuration file with hashed passwords.
"""

import yaml
import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for web administration"""
    ADMIN = "admin"  # Full access to all features
    VIEWER = "viewer"  # Read-only access, no broadcast/config/user management


@dataclass
class WebAdminUser:
    """Web administration user"""
    username: str
    password_hash: str
    role: UserRole
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role.value,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_password_change": self.last_password_change.isoformat() if self.last_password_change else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebAdminUser':
        """Create from dictionary"""
        return cls(
            username=data["username"],
            password_hash=data["password_hash"],
            role=UserRole(data["role"]),
            email=data.get("email"),
            full_name=data.get("full_name"),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None,
            last_password_change=datetime.fromisoformat(data["last_password_change"]) if data.get("last_password_change") else None
        )


class WebAdminUserManager:
    """
    Manages web administration users with role-based access control.
    Users are stored in config/web_users.yaml with hashed passwords.
    """
    
    def __init__(self, config_file: str = "config/web_users.yaml"):
        self.config_file = Path(config_file)
        self.users: Dict[str, WebAdminUser] = {}
        self.logger = logger
        
        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load users from config
        self._load_users()
        
        # Create default admin user if no users exist
        if not self.users:
            self._create_default_admin()
        
        self.logger.info(f"WebAdminUserManager initialized with {len(self.users)} users")
    
    def _load_users(self):
        """Load users from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    users_data = data.get('users', {})
                    
                    for username, user_data in users_data.items():
                        try:
                            self.users[username] = WebAdminUser.from_dict(user_data)
                        except Exception as e:
                            self.logger.error(f"Error loading user {username}: {e}")
                
                self.logger.info(f"Loaded {len(self.users)} users from {self.config_file}")
            else:
                self.logger.info(f"No user config file found at {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error loading users from {self.config_file}: {e}")
    
    def _save_users(self):
        """Save users to config file"""
        try:
            data = {
                'users': {
                    username: user.to_dict()
                    for username, user in self.users.items()
                },
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Saved {len(self.users)} users to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving users to {self.config_file}: {e}")
            return False
    
    def _create_default_admin(self):
        """Create default admin user"""
        try:
            default_password = "admin123"
            admin_user = WebAdminUser(
                username="admin",
                password_hash=self.hash_password(default_password),
                role=UserRole.ADMIN,
                full_name="Default Administrator",
                created_at=datetime.now(timezone.utc),
                last_password_change=datetime.now(timezone.utc)
            )
            
            self.users["admin"] = admin_user
            self._save_users()
            
            self.logger.warning(
                f"Created default admin user with password '{default_password}'. "
                "Please change this password immediately!"
            )
        except Exception as e:
            self.logger.error(f"Error creating default admin user: {e}")
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> str:
        """Hash password with salt using SHA-256"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Combine password and salt
        salted = f"{password}{salt}".encode('utf-8')
        
        # Hash with SHA-256
        hashed = hashlib.sha256(salted).hexdigest()
        
        # Return salt:hash format
        return f"{salt}:{hashed}"
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            if ':' not in password_hash:
                return False
            
            salt, stored_hash = password_hash.split(':', 1)
            
            # Hash the provided password with the stored salt
            salted = f"{password}{salt}".encode('utf-8')
            computed_hash = hashlib.sha256(salted).hexdigest()
            
            # Compare hashes
            return computed_hash == stored_hash
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[WebAdminUser]:
        """Authenticate user with username and password"""
        try:
            user = self.users.get(username)
            
            if not user:
                self.logger.warning(f"Authentication failed: user '{username}' not found")
                return None
            
            if not user.is_active:
                self.logger.warning(f"Authentication failed: user '{username}' is inactive")
                return None
            
            if not self.verify_password(password, user.password_hash):
                self.logger.warning(f"Authentication failed: invalid password for user '{username}'")
                return None
            
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            self._save_users()
            
            self.logger.info(f"User '{username}' authenticated successfully")
            return user
            
        except Exception as e:
            self.logger.error(f"Error authenticating user '{username}': {e}")
            return None
    
    def create_user(self, username: str, password: str, role: UserRole, 
                   email: Optional[str] = None, full_name: Optional[str] = None) -> bool:
        """Create a new user"""
        try:
            if username in self.users:
                self.logger.warning(f"User '{username}' already exists")
                return False
            
            user = WebAdminUser(
                username=username,
                password_hash=self.hash_password(password),
                role=role,
                email=email,
                full_name=full_name,
                created_at=datetime.now(timezone.utc),
                last_password_change=datetime.now(timezone.utc)
            )
            
            self.users[username] = user
            self._save_users()
            
            self.logger.info(f"Created user '{username}' with role '{role.value}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating user '{username}': {e}")
            return False
    
    def update_user(self, username: str, email: Optional[str] = None, 
                   full_name: Optional[str] = None, role: Optional[UserRole] = None,
                   is_active: Optional[bool] = None) -> bool:
        """Update user information"""
        try:
            user = self.users.get(username)
            if not user:
                self.logger.warning(f"User '{username}' not found")
                return False
            
            if email is not None:
                user.email = email
            if full_name is not None:
                user.full_name = full_name
            if role is not None:
                user.role = role
            if is_active is not None:
                user.is_active = is_active
            
            self._save_users()
            
            self.logger.info(f"Updated user '{username}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating user '{username}': {e}")
            return False
    
    def change_password(self, username: str, new_password: str) -> bool:
        """Change user password"""
        try:
            user = self.users.get(username)
            if not user:
                self.logger.warning(f"User '{username}' not found")
                return False
            
            user.password_hash = self.hash_password(new_password)
            user.last_password_change = datetime.now(timezone.utc)
            
            self._save_users()
            
            self.logger.info(f"Changed password for user '{username}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error changing password for '{username}': {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        try:
            if username not in self.users:
                self.logger.warning(f"User '{username}' not found")
                return False
            
            # Prevent deleting the last admin user
            if self.users[username].role == UserRole.ADMIN:
                admin_count = sum(1 for u in self.users.values() if u.role == UserRole.ADMIN and u.is_active)
                if admin_count <= 1:
                    self.logger.error("Cannot delete the last active admin user")
                    return False
            
            del self.users[username]
            self._save_users()
            
            self.logger.info(f"Deleted user '{username}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting user '{username}': {e}")
            return False
    
    def get_user(self, username: str) -> Optional[WebAdminUser]:
        """Get user by username"""
        return self.users.get(username)
    
    def get_all_users(self) -> List[WebAdminUser]:
        """Get all users"""
        return list(self.users.values())
    
    def has_permission(self, username: str, permission: str) -> bool:
        """Check if user has a specific permission"""
        user = self.users.get(username)
        if not user or not user.is_active:
            return False
        
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Viewer has read-only permissions
        if user.role == UserRole.VIEWER:
            return permission in ["read", "view"]
        
        return False
    
    def can_access_feature(self, username: str, feature: str) -> bool:
        """Check if user can access a specific feature"""
        user = self.users.get(username)
        if not user or not user.is_active:
            return False
        
        # Admin can access everything
        if user.role == UserRole.ADMIN:
            return True
        
        # Viewer cannot access these features
        restricted_features = ["broadcast", "user_management", "configuration", "service_control"]
        
        if user.role == UserRole.VIEWER and feature in restricted_features:
            return False
        
        return True
