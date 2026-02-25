"""
Web Administration Service for ZephyrGate

Provides web-based administration interface with FastAPI framework.
Implements authentication, session management, and administrative functions.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from core.plugin_manager import BasePlugin, PluginMetadata
from core.plugin_interfaces import (
    PluginCommunicationInterface, MessageHandler, CommandHandler,
    PluginMessage, PluginEvent, PluginEventType, PluginMessageType
)
try:
    from ...models.message import Message, MessageType
except ImportError:
    from models.message import Message, MessageType
from .system_monitor import SystemMonitor
from .user_manager import UserManager, PermissionLevel, SubscriptionType
from .scheduler import BroadcastScheduler, ScheduleType, RecurrencePattern, BroadcastStatus
from .security import SecurityManager, SecurityPolicy, AuditEventType, SecurityLevel


logger = logging.getLogger(__name__)


# Pydantic models for API
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserProfile(BaseModel):
    username: str
    role: str
    permissions: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None


class SystemStatus(BaseModel):
    status: str
    uptime: int
    active_plugins: List[str]
    node_count: int
    message_count: int
    active_incidents: int
    last_updated: datetime


class NodeInfo(BaseModel):
    node_id: str
    short_name: str
    long_name: str
    hardware: str
    role: str
    battery_level: Optional[int] = None
    snr: Optional[float] = None
    last_seen: datetime
    location: Optional[Dict[str, float]] = None


class MessageInfo(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    recipient_id: Optional[str] = None
    channel: int
    content: str
    timestamp: datetime
    message_type: str
    interface_id: str


class BroadcastMessage(BaseModel):
    content: str
    channel: Optional[int] = None
    interface_id: Optional[str] = None
    scheduled_time: Optional[datetime] = None


class ConfigUpdate(BaseModel):
    key: str
    value: Any


class UserProfileResponse(BaseModel):
    node_id: str
    short_name: str
    long_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tags: List[str]
    permissions: List[str]
    subscriptions: List[str]
    created_at: datetime
    last_seen: Optional[datetime] = None
    last_login: Optional[datetime] = None
    location: Optional[Dict[str, float]] = None
    is_active: bool
    notes: str
    message_count: int
    last_message_time: Optional[datetime] = None
    favorite_channels: List[int]


class UserUpdateRequest(BaseModel):
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class PermissionUpdateRequest(BaseModel):
    permissions: List[str]


class SubscriptionUpdateRequest(BaseModel):
    subscriptions: List[str]


class TagRequest(BaseModel):
    tag: str


class UserStatsResponse(BaseModel):
    total_users: int
    active_users: int
    new_users_today: int
    total_messages: int
    messages_today: int
    top_users: List[Dict[str, Any]]
    permission_distribution: Dict[str, int]
    subscription_distribution: Dict[str, int]


class MessageTemplateResponse(BaseModel):
    id: str
    name: str
    content: str
    description: str
    variables: List[str]
    category: str
    created_at: datetime
    created_by: str
    usage_count: int


class CreateTemplateRequest(BaseModel):
    name: str
    content: str
    description: str = ""
    variables: List[str] = []
    category: str = "general"


class ScheduledBroadcastResponse(BaseModel):
    id: str
    name: str
    content: str
    channel: Optional[int] = None
    interface_id: Optional[str] = None
    schedule_type: str
    scheduled_time: Optional[datetime] = None
    recurrence_pattern: Optional[str] = None
    interval_minutes: Optional[int] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    created_at: datetime
    created_by: str
    is_active: bool
    template_id: Optional[str] = None
    variables: Dict[str, str]
    last_sent: Optional[datetime] = None
    next_send: Optional[datetime] = None
    send_count: int
    status: str


class ScheduleBroadcastRequest(BaseModel):
    name: str
    content: str = ""
    channel: Optional[int] = None
    interface_id: Optional[str] = None
    scheduled_time: datetime
    schedule_type: str = "one_time"
    recurrence_pattern: Optional[str] = None
    interval_minutes: Optional[int] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    template_id: Optional[str] = None
    variables: Dict[str, str] = {}


class BroadcastHistoryResponse(BaseModel):
    id: str
    schedule_id: Optional[str]
    content: str
    channel: Optional[int]
    interface_id: Optional[str]
    sent_at: datetime
    sent_by: str
    status: str
    error_message: Optional[str] = None
    recipient_count: int


class ImmediateBroadcastRequest(BaseModel):
    content: str
    channel: Optional[int] = None
    interface_id: Optional[str] = None


class MessageSearchRequest(BaseModel):
    query: Optional[str] = None
    sender_id: Optional[str] = None
    channel: Optional[int] = None
    interface_id: Optional[str] = None
    message_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class DirectMessageRequest(BaseModel):
    recipient_id: str
    content: str
    interface_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    sender_id: str
    sender_name: Optional[str] = None
    recipient_id: Optional[str] = None
    channel: int
    content: str
    timestamp: datetime
    message_type: str
    interface_id: str
    hop_count: int = 0
    snr: Optional[float] = None
    rssi: Optional[float] = None


class ChatStatsResponse(BaseModel):
    total_messages: int
    messages_today: int
    active_channels: List[int]
    top_senders: List[Dict[str, Any]]
    message_types: Dict[str, int]
    hourly_activity: List[Dict[str, Any]]


class ConfigurationResponse(BaseModel):
    section: str
    key: str
    value: Any
    description: Optional[str] = None
    data_type: str
    is_required: bool = False
    default_value: Any = None


class ConfigurationUpdateRequest(BaseModel):
    section: str
    key: str
    value: Any


class ConfigurationBackupResponse(BaseModel):
    backup_id: str
    timestamp: datetime
    description: str
    size: int
    sections: List[str]


class ServiceStatusResponse(BaseModel):
    name: str
    status: str
    uptime: int
    last_restart: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    is_enabled: bool = True
    dependencies: List[str] = []


class ServiceActionRequest(BaseModel):
    action: str  # start, stop, restart, enable, disable


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_permissions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str, permissions: Set[str]):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_permissions[client_id] = permissions
        logger.info(f"WebSocket client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """Remove WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_permissions:
            del self.connection_permissions[client_id]
        logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_personal_message(self, message: str, client_id: str):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: str, permission_required: Optional[str] = None):
        """Broadcast message to all connected clients with permission"""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            # Check permission if required
            if permission_required:
                client_permissions = self.connection_permissions.get(client_id, set())
                if permission_required not in client_permissions:
                    continue
            
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)


class Role:
    """User role definitions"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    GUEST = "guest"


class Permission:
    """Permission definitions"""
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"
    
    # User management permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_ADMIN = "user:admin"
    
    # Message permissions
    MESSAGE_READ = "message:read"
    MESSAGE_SEND = "message:send"
    MESSAGE_BROADCAST = "message:broadcast"
    MESSAGE_DELETE = "message:delete"
    
    # Service permissions
    SERVICE_READ = "service:read"
    SERVICE_CONTROL = "service:control"
    SERVICE_CONFIG = "service:config"
    
    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"


# Role-based permission mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: {
        Permission.SYSTEM_ADMIN, Permission.SYSTEM_CONFIG, Permission.SYSTEM_MONITOR,
        Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE, Permission.USER_ADMIN,
        Permission.MESSAGE_READ, Permission.MESSAGE_SEND, Permission.MESSAGE_BROADCAST, Permission.MESSAGE_DELETE,
        Permission.SERVICE_READ, Permission.SERVICE_CONTROL, Permission.SERVICE_CONFIG,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT
    },
    Role.OPERATOR: {
        Permission.SYSTEM_MONITOR,
        Permission.USER_READ, Permission.USER_WRITE,
        Permission.MESSAGE_READ, Permission.MESSAGE_SEND, Permission.MESSAGE_BROADCAST,
        Permission.SERVICE_READ, Permission.SERVICE_CONTROL,
        Permission.AUDIT_READ
    },
    Role.VIEWER: {
        Permission.SYSTEM_MONITOR,
        Permission.USER_READ,
        Permission.MESSAGE_READ,
        Permission.SERVICE_READ,
        Permission.AUDIT_READ
    },
    Role.GUEST: {
        Permission.SYSTEM_MONITOR,
        Permission.MESSAGE_READ
    }
}


class AuthenticationManager:
    """Enhanced authentication and session management with SecurityManager integration"""
    
    def __init__(self, secret_key: str, security_manager: SecurityManager, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.security_manager = security_manager
        
        # Default admin user (should be configured properly in production)
        admin_password = "admin123"  # Change in production
        admin_hash, admin_salt = self.security_manager.hash_password(admin_password)
        
        self.users = {
            "admin": {
                "username": "admin",
                "password_hash": admin_hash,
                "password_salt": admin_salt,
                "role": Role.ADMIN,
                "permissions": ROLE_PERMISSIONS[Role.ADMIN],
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
                "last_login": None,
                "login_count": 0
            }
        }
    
    def authenticate_user(self, username: str, password: str, ip_address: str, 
                         user_agent: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials with security manager integration"""
        try:
            # Check if IP is allowed
            if not self.security_manager.is_ip_allowed(ip_address):
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="authentication",
                    action="ip_blocked",
                    details={"reason": "ip_not_allowed"},
                    security_level=SecurityLevel.HIGH,
                    success=False
                )
                return None
            
            # Check if user is locked out
            if self.security_manager.is_user_locked_out(username):
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="authentication",
                    action="login_blocked",
                    details={"reason": "user_locked_out"},
                    security_level=SecurityLevel.MEDIUM,
                    success=False
                )
                return None
            
            # Get user
            user = self.users.get(username)
            if not user or not user.get("is_active", True):
                self.security_manager.record_login_attempt(username, ip_address, False, user_agent)
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="authentication",
                    action="login_failed",
                    details={"reason": "invalid_user"},
                    security_level=SecurityLevel.MEDIUM,
                    success=False
                )
                return None
            
            # Verify password
            if not self.security_manager.verify_password(
                password, user["password_hash"], user["password_salt"]
            ):
                self.security_manager.record_login_attempt(username, ip_address, False, user_agent)
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="authentication",
                    action="login_failed",
                    details={"reason": "invalid_password"},
                    security_level=SecurityLevel.MEDIUM,
                    success=False
                )
                return None
            
            # Successful authentication
            self.security_manager.record_login_attempt(username, ip_address, True, user_agent)
            
            # Update user login info
            user["last_login"] = datetime.now(timezone.utc)
            user["login_count"] = user.get("login_count", 0) + 1
            
            return user
            
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            self.security_manager.log_audit_event(
                event_type=AuditEventType.LOGIN_FAILURE,
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="authentication",
                action="login_error",
                details={"error": str(e)},
                security_level=SecurityLevel.HIGH,
                success=False,
                error_message=str(e)
            )
            return None
    
    def create_session(self, user: Dict[str, Any], ip_address: str, 
                      user_agent: str) -> Optional[str]:
        """Create user session using SecurityManager"""
        try:
            username = user["username"]
            permissions = user.get("permissions", set())
            
            session = self.security_manager.create_session(
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                permissions=permissions
            )
            
            if session:
                return session.session_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def validate_session(self, session_id: str, ip_address: str) -> Optional[Dict[str, Any]]:
        """Validate session using SecurityManager"""
        try:
            session = self.security_manager.validate_session(session_id, ip_address)
            if not session:
                return None
            
            # Get user info from WebAdminUserManager instead of self.users
            from .admin_users import WebAdminUserManager
            user_manager = WebAdminUserManager()
            user = user_manager.get_user(session.user_id)
            
            if not user or not user.is_active:
                self.security_manager.invalidate_session(session_id)
                return None
            
            return {
                "username": session.user_id,
                "role": user.role.value,
                "permissions": session.permissions,
                "session": session
            }
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return None
    
    def logout(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        return self.security_manager.invalidate_session(session_id)
    
    def has_permission(self, permissions: Set[str], required_permission: str) -> bool:
        """Check if user has required permission"""
        return required_permission in permissions or Permission.SYSTEM_ADMIN in permissions
    
    def create_user(self, username: str, password: str, role: str, 
                   created_by: str, ip_address: str, user_agent: str) -> bool:
        """Create new user with audit logging"""
        try:
            if username in self.users:
                return False
            
            # Validate password strength
            password_validation = self.security_manager.validate_password_strength(password)
            if not password_validation["valid"]:
                return False
            
            # Hash password
            password_hash, password_salt = self.security_manager.hash_password(password)
            
            # Create user
            self.users[username] = {
                "username": username,
                "password_hash": password_hash,
                "password_salt": password_salt,
                "role": role,
                "permissions": ROLE_PERMISSIONS.get(role, set()),
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
                "last_login": None,
                "login_count": 0
            }
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.USER_CREATED,
                user_id=created_by,
                user_name=created_by,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="user_management",
                action="user_created",
                details={"new_user": username, "role": role},
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
    
    def update_user_password(self, username: str, new_password: str, 
                           updated_by: str, ip_address: str, user_agent: str) -> bool:
        """Update user password with audit logging"""
        try:
            user = self.users.get(username)
            if not user:
                return False
            
            # Validate password strength
            password_validation = self.security_manager.validate_password_strength(new_password)
            if not password_validation["valid"]:
                return False
            
            # Hash new password
            password_hash, password_salt = self.security_manager.hash_password(new_password)
            
            # Update user
            user["password_hash"] = password_hash
            user["password_salt"] = password_salt
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.PASSWORD_CHANGE,
                user_id=updated_by,
                user_name=updated_by,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="user_management",
                action="password_changed",
                details={"target_user": username},
                security_level=SecurityLevel.HIGH,
                success=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return False
    
    def delete_user(self, username: str, deleted_by: str, 
                   ip_address: str, user_agent: str) -> bool:
        """Delete user with audit logging"""
        try:
            if username not in self.users or username == "admin":
                return False
            
            user_info = self.users[username].copy()
            del self.users[username]
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.USER_DELETED,
                user_id=deleted_by,
                user_name=deleted_by,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="user_management",
                action="user_deleted",
                details={"deleted_user": username, "role": user_info.get("role")},
                security_level=SecurityLevel.HIGH,
                success=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False


class WebAdminService(BasePlugin):
    """
    Web Administration Service
    
    Provides web-based interface for system administration, monitoring,
    and management of the ZephyrGate system.
    """
    
    def __init__(self, config: Dict[str, Any], plugin_manager):
        super().__init__("web_admin", config, plugin_manager)
        
        # Configuration
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 8080)
        self.secret_key = config.get("secret_key", "your-secret-key-change-in-production")
        self.debug = config.get("debug", False)
        
        # Initialize components
        security_policy = SecurityPolicy(
            max_login_attempts=config.get("max_login_attempts", 5),
            lockout_duration=config.get("lockout_duration", 900),
            session_timeout=config.get("session_timeout", 3600),
            password_min_length=config.get("password_min_length", 8),
            allowed_ip_ranges=config.get("allowed_ip_ranges", []),
            audit_retention_days=config.get("audit_retention_days", 90)
        )
        self.security_manager = SecurityManager(security_policy)
        self.auth_manager = AuthenticationManager(self.secret_key, self.security_manager)
        self.websocket_manager = WebSocketManager()
        self.system_monitor = SystemMonitor(plugin_manager)
        self.user_manager = UserManager()
        self.scheduler = BroadcastScheduler(message_sender=self._send_message_via_router)
        
        # FastAPI app
        self.app = FastAPI(
            title="ZephyrGate Web Administration",
            description="Web-based administration interface for ZephyrGate",
            version="1.0.0",
            debug=self.debug
        )
        
        # Security
        self.security = HTTPBearer()
        
        # Setup middleware
        self._setup_middleware()
        
        # Setup routes
        self._setup_routes()
        
        # Static files and templates
        self._setup_static_files()
        
        # Server instance
        self.server = None
        self.server_task = None
        
        # System data cache
        self.system_status_cache = {}
        self.nodes_cache = {}
        self.messages_cache = []
        self.cache_update_interval = 30  # seconds
        
        # Real-time update task
        self.update_task = None
        
        self.logger.info("WebAdminService initialized")
    
    def _setup_middleware(self):
        """Setup FastAPI middleware"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure properly for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Trusted host middleware
        self.app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Configure properly for production
        )
    
    def _setup_static_files(self):
        """Setup static files and templates"""
        # Create static and templates directories if they don't exist
        static_dir = Path(__file__).parent / "static"
        templates_dir = Path(__file__).parent / "templates"
        
        static_dir.mkdir(exist_ok=True)
        templates_dir.mkdir(exist_ok=True)
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Setup templates
        self.templates = Jinja2Templates(directory=str(templates_dir))
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        # Authentication dependency
        async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(self.security), req: Request = None):
            try:
                payload = jwt.decode(credentials.credentials, self.secret_key, algorithms=["HS256"])
                username = payload.get("sub")
                if username is None:
                    raise HTTPException(status_code=401, detail="Invalid authentication credentials")
                token_data = {"username": username, "payload": payload}
            except JWTError as e:
                self.logger.error(f"JWT decode error: {e}")
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            
            # Get client IP
            client_ip = req.client.host if req and req.client else "unknown"
            
            # Validate session if session_id is in token
            session_id = token_data.get("payload", {}).get("session_id")
            if session_id:
                self.logger.info(f"Validating session {session_id} for user {username} from IP {client_ip}")
                self.logger.info(f"Active sessions count: {len(self.security_manager.active_sessions)}")
                self.logger.info(f"Session exists in active_sessions: {session_id in self.security_manager.active_sessions}")
                
                session_data = self.auth_manager.validate_session(session_id, client_ip)
                if not session_data:
                    self.logger.warning(f"Session validation failed for {session_id}, user {username}, IP {client_ip}")
                    raise HTTPException(status_code=401, detail="Session expired or invalid")
                
                return session_data
            
            # Fallback - get user from WebAdminUserManager
            from .admin_users import WebAdminUserManager
            user_manager = WebAdminUserManager()
            user = user_manager.get_user(token_data["username"])
            
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive")
            
            return {
                "username": user.username,
                "role": user.role.value,
                "permissions": ["admin"] if user.role.value == "admin" else ["read"],
                "session": None
            }
        
        # Permission dependency
        def require_permission(permission: str):
            def permission_dependency(user_data: dict = Depends(get_current_user)):
                permissions = user_data.get("permissions", set())
                if not self.auth_manager.has_permission(permissions, permission):
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                return user_data["username"]
            return permission_dependency
        
        # Authentication routes
        @self.app.post("/api/auth/login", response_model=LoginResponse)
        async def login(request: LoginRequest, req: Request):
            # Get client IP and user agent
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            # Check if IP is allowed
            if not self.security_manager.is_ip_allowed(client_ip):
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    user_id=request.username,
                    user_name=request.username,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    resource="authentication",
                    action="blocked_ip_attempt",
                    details={"ip": client_ip},
                    security_level=SecurityLevel.HIGH,
                    success=False
                )
                raise HTTPException(status_code=403, detail="Access denied from this IP address")
            
            # Check if user is locked out
            if self.security_manager.is_user_locked_out(request.username):
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    user_id=request.username,
                    user_name=request.username,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    resource="authentication",
                    action="locked_out_attempt",
                    details={},
                    security_level=SecurityLevel.MEDIUM,
                    success=False
                )
                raise HTTPException(status_code=423, detail="Account temporarily locked due to too many failed attempts")
            
            # Authenticate user with WebAdminUserManager
            from .admin_users import WebAdminUserManager
            user_manager = WebAdminUserManager()
            user = user_manager.authenticate(request.username, request.password)
            
            # Record login attempt
            login_success = user is not None
            self.security_manager.record_login_attempt(
                user_id=request.username,
                ip_address=client_ip,
                success=login_success,
                user_agent=user_agent
            )
            
            if not user:
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    user_id=request.username,
                    user_name=request.username,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    resource="authentication",
                    action="invalid_credentials",
                    details={},
                    security_level=SecurityLevel.MEDIUM,
                    success=False
                )
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Create session - convert WebAdminUser to dict for auth_manager
            # Get proper permissions based on role
            role_permissions = ROLE_PERMISSIONS.get(user.role.value, set())
            
            user_dict = {
                "username": user.username,
                "role": user.role.value,
                "permissions": role_permissions,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
            
            session_id = self.auth_manager.create_session(user_dict, client_ip, user_agent)
            if not session_id:
                raise HTTPException(status_code=500, detail="Failed to create session")
            
            session = self.security_manager.active_sessions.get(session_id)
            
            if not session:
                raise HTTPException(status_code=500, detail="Failed to create session")
            
            # Create access token using JWT directly
            to_encode = {"sub": user.username, "session_id": session.session_id}
            expire = datetime.now(timezone.utc) + timedelta(seconds=self.security_manager.policy.session_timeout)
            to_encode.update({"exp": expire})
            access_token = jwt.encode(to_encode, self.secret_key, algorithm="HS256")
            
            return LoginResponse(
                access_token=access_token,
                expires_in=self.security_manager.policy.session_timeout
            )
        
        @self.app.post("/api/auth/logout")
        async def logout(credentials: HTTPAuthorizationCredentials = Depends(self.security), req: Request = None):
            try:
                payload = jwt.decode(credentials.credentials, self.secret_key, algorithms=["HS256"])
                session_id = payload.get("session_id")
                if session_id:
                    self.security_manager.invalidate_session(session_id)
            except JWTError:
                pass  # Invalid token, but still return success
            
            return {"success": True, "message": "Logged out successfully"}
        
        @self.app.get("/api/auth/profile", response_model=UserProfile)
        async def get_profile(user_data: dict = Depends(get_current_user)):
            username = user_data["username"]
            
            # Get user from WebAdminUserManager
            from .admin_users import WebAdminUserManager
            user_manager = WebAdminUserManager()
            user = user_manager.get_user(username)
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            return UserProfile(
                username=user.username,
                role=user.role.value,
                permissions=user_data.get("permissions", []),
                created_at=user.created_at.isoformat() if user.created_at else None,
                last_login=user.last_login.isoformat() if user.last_login else None
            )
        
        # User Management routes (Admin only)
        @self.app.get("/api/admin/users")
        async def get_all_admin_users(username: str = Depends(require_permission("admin"))):
            """Get all web admin users"""
            try:
                from .admin_users import WebAdminUserManager
                user_manager = WebAdminUserManager()
                users = user_manager.get_all_users()
                
                return [
                    {
                        "username": u.username,
                        "full_name": u.full_name,
                        "email": u.email,
                        "role": u.role.value,
                        "is_active": u.is_active,
                        "created_at": u.created_at.isoformat() if u.created_at else None,
                        "last_login": u.last_login.isoformat() if u.last_login else None
                    }
                    for u in users
                ]
            except Exception as e:
                self.logger.error(f"Error getting users: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/admin/users/{target_username}")
        async def get_admin_user(target_username: str, username: str = Depends(require_permission("admin"))):
            """Get specific web admin user"""
            try:
                from .admin_users import WebAdminUserManager
                user_manager = WebAdminUserManager()
                user = user_manager.get_user(target_username)
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return {
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role.value,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error getting user {target_username}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/admin/users")
        async def create_admin_user(user_data: dict, username: str = Depends(require_permission("admin"))):
            """Create new web admin user"""
            try:
                from .admin_users import WebAdminUserManager, UserRole
                user_manager = WebAdminUserManager()
                
                if not user_data.get("username") or not user_data.get("password"):
                    raise HTTPException(status_code=400, detail="Username and password are required")
                
                role = UserRole(user_data.get("role", "viewer"))
                
                success = user_manager.create_user(
                    username=user_data["username"],
                    password=user_data["password"],
                    role=role,
                    email=user_data.get("email"),
                    full_name=user_data.get("full_name")
                )
                
                if not success:
                    raise HTTPException(status_code=400, detail="User already exists")
                
                return {"success": True, "message": "User created successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error creating user: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/admin/users/{target_username}")
        async def update_admin_user(target_username: str, user_data: dict, username: str = Depends(require_permission("admin"))):
            """Update web admin user"""
            try:
                from .admin_users import WebAdminUserManager, UserRole
                user_manager = WebAdminUserManager()
                
                role = UserRole(user_data["role"]) if "role" in user_data else None
                
                success = user_manager.update_user(
                    username=target_username,
                    email=user_data.get("email"),
                    full_name=user_data.get("full_name"),
                    role=role,
                    is_active=user_data.get("is_active")
                )
                
                # Update password if provided
                if user_data.get("password"):
                    user_manager.change_password(target_username, user_data["password"])
                
                if not success:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return {"success": True, "message": "User updated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating user {target_username}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/admin/users/{target_username}/password")
        async def change_admin_user_password(target_username: str, password_data: dict, username: str = Depends(require_permission("admin"))):
            """Change web admin user password"""
            try:
                from .admin_users import WebAdminUserManager
                user_manager = WebAdminUserManager()
                
                if not password_data.get("password"):
                    raise HTTPException(status_code=400, detail="Password is required")
                
                success = user_manager.change_password(target_username, password_data["password"])
                
                if not success:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return {"success": True, "message": "Password changed successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error changing password for {target_username}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/admin/users/{target_username}")
        async def delete_admin_user(target_username: str, username: str = Depends(require_permission("admin"))):
            """Delete web admin user"""
            try:
                from .admin_users import WebAdminUserManager
                user_manager = WebAdminUserManager()
                
                success = user_manager.delete_user(target_username)
                
                if not success:
                    raise HTTPException(status_code=400, detail="Cannot delete user (may be last admin or not found)")
                
                return {"success": True, "message": "User deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting user {target_username}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # System status routes
        @self.app.get("/api/system/status", response_model=SystemStatus)
        async def get_system_status(username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))):
            return await self._get_system_status()
        
        @self.app.get("/api/system/nodes", response_model=List[NodeInfo])
        async def get_nodes(username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))):
            return await self._get_nodes()
        
        @self.app.get("/api/system/messages", response_model=List[MessageInfo])
        async def get_messages(
            limit: int = 100,
            offset: int = 0,
            username: str = Depends(require_permission(Permission.MESSAGE_READ))
        ):
            return await self._get_messages(limit, offset)
        
        # System monitoring routes
        @self.app.get("/api/system/metrics")
        async def get_system_metrics(
            limit: int = 50,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            metrics = self.system_monitor.get_metrics_history(limit)
            return [
                {
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "memory_used": m.memory_used,
                    "memory_total": m.memory_total,
                    "disk_percent": m.disk_percent,
                    "disk_used": m.disk_used,
                    "disk_total": m.disk_total,
                    "network_sent": m.network_sent,
                    "network_recv": m.network_recv,
                    "uptime": m.uptime,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in metrics
            ]
        
        @self.app.get("/api/system/alerts")
        async def get_alerts(
            active_only: bool = True,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            alerts = self.system_monitor.get_active_alerts() if active_only else self.system_monitor.get_all_alerts()
            return [
                {
                    "id": a.id,
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message,
                    "source": a.source,
                    "timestamp": a.timestamp.isoformat(),
                    "acknowledged": a.acknowledged,
                    "resolved": a.resolved
                }
                for a in alerts
            ]
        
        @self.app.post("/api/system/alerts/{alert_id}/acknowledge")
        async def acknowledge_alert(
            alert_id: str,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            success = self.system_monitor.acknowledge_alert(alert_id)
            return {"success": success, "alert_id": alert_id}
        
        @self.app.post("/api/system/alerts/{alert_id}/resolve")
        async def resolve_alert(
            alert_id: str,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            success = self.system_monitor.resolve_alert(alert_id)
            return {"success": success, "alert_id": alert_id}
        
        @self.app.get("/api/system/services")
        async def get_services(username: str = Depends(require_permission(Permission.SERVICE_READ))):
            services = self.system_monitor.get_service_status()
            return [
                {
                    "name": s.name,
                    "status": s.status,
                    "uptime": s.uptime,
                    "last_restart": s.last_restart.isoformat() if s.last_restart else None,
                    "error_count": s.error_count,
                    "last_error": s.last_error
                }
                for s in services
            ]
        
        # User management routes
        @self.app.get("/api/users", response_model=List[UserProfileResponse])
        async def get_users(
            active_only: bool = False,
            limit: int = 100,
            username: str = Depends(require_permission(Permission.USER_READ))
        ):
            users = self.user_manager.get_all_users(active_only=active_only)[:limit]
            return [self._user_to_response(user) for user in users]
        
        @self.app.get("/api/users/{node_id}", response_model=UserProfileResponse)
        async def get_user(
            node_id: str,
            username: str = Depends(require_permission(Permission.USER_READ))
        ):
            user = self.user_manager.get_user(node_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return self._user_to_response(user)
        
        @self.app.put("/api/users/{node_id}")
        async def update_user(
            node_id: str,
            update_data: UserUpdateRequest,
            username: str = Depends(require_permission(Permission.USER_WRITE))
        ):
            user = self.user_manager.get_user(node_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            success = self.user_manager.update_user(node_id, **update_dict)
            
            if success:
                return {"success": True, "message": "User updated successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to update user")
        
        @self.app.delete("/api/users/{node_id}")
        async def delete_user(
            node_id: str,
            username: str = Depends(require_permission(Permission.USER_DELETE))
        ):
            success = self.user_manager.delete_user(node_id)
            if success:
                return {"success": True, "message": "User deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        @self.app.put("/api/users/{node_id}/permissions")
        async def update_user_permissions(
            node_id: str,
            permission_data: PermissionUpdateRequest,
            username: str = Depends(require_permission(Permission.USER_ADMIN))
        ):
            try:
                permissions = {PermissionLevel(p) for p in permission_data.permissions}
                success = self.user_manager.update_permissions(node_id, permissions)
                
                if success:
                    return {"success": True, "message": "Permissions updated successfully"}
                else:
                    raise HTTPException(status_code=404, detail="User not found")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid permission: {e}")
        
        @self.app.put("/api/users/{node_id}/subscriptions")
        async def update_user_subscriptions(
            node_id: str,
            subscription_data: SubscriptionUpdateRequest,
            username: str = Depends(require_permission(Permission.USER_WRITE))
        ):
            try:
                subscriptions = {SubscriptionType(s) for s in subscription_data.subscriptions}
                success = self.user_manager.update_subscriptions(node_id, subscriptions)
                
                if success:
                    return {"success": True, "message": "Subscriptions updated successfully"}
                else:
                    raise HTTPException(status_code=404, detail="User not found")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid subscription: {e}")
        
        @self.app.post("/api/users/{node_id}/tags")
        async def add_user_tag(
            node_id: str,
            tag_data: TagRequest,
            username: str = Depends(require_permission(Permission.USER_WRITE))
        ):
            success = self.user_manager.add_tag(node_id, tag_data.tag)
            if success:
                return {"success": True, "message": f"Tag '{tag_data.tag}' added successfully"}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        @self.app.delete("/api/users/{node_id}/tags/{tag}")
        async def remove_user_tag(
            node_id: str,
            tag: str,
            username: str = Depends(require_permission(Permission.USER_WRITE))
        ):
            success = self.user_manager.remove_tag(node_id, tag)
            if success:
                return {"success": True, "message": f"Tag '{tag}' removed successfully"}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        @self.app.get("/api/users/search/{query}")
        async def search_users(
            query: str,
            limit: int = 50,
            username: str = Depends(require_permission(Permission.USER_READ))
        ):
            users = self.user_manager.search_users(query, limit)
            return [self._user_to_response(user) for user in users]
        
        @self.app.get("/api/users/stats", response_model=UserStatsResponse)
        async def get_user_stats(username: str = Depends(require_permission(Permission.USER_READ))):
            stats = self.user_manager.get_user_stats()
            return UserStatsResponse(**stats)
        
        # Security and audit routes
        @self.app.get("/api/security/summary")
        async def get_security_summary(username: str = Depends(require_permission(Permission.AUDIT_READ))):
            """Get security summary and statistics"""
            summary = self.security_manager.get_security_summary()
            return summary
        
        @self.app.get("/api/security/audit-log")
        async def get_audit_log(
            limit: int = 100,
            event_type: Optional[str] = None,
            user_id: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            username: str = Depends(require_permission(Permission.AUDIT_READ))
        ):
            """Get audit log entries with filtering"""
            try:
                event_type_enum = AuditEventType(event_type) if event_type else None
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
            
            entries = self.security_manager.get_audit_log(
                limit=limit,
                event_type=event_type_enum,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return [
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": entry.event_type.value,
                    "user_id": entry.user_id,
                    "user_name": entry.user_name,
                    "ip_address": entry.ip_address,
                    "user_agent": entry.user_agent,
                    "resource": entry.resource,
                    "action": entry.action,
                    "details": entry.details,
                    "security_level": entry.security_level.value,
                    "success": entry.success,
                    "error_message": entry.error_message
                }
                for entry in entries
            ]
        
        @self.app.get("/api/security/audit-log/export")
        async def export_audit_log(
            format: str = "json",
            username: str = Depends(require_permission(Permission.AUDIT_EXPORT))
        ):
            """Export audit log"""
            if format.lower() not in ["json"]:
                raise HTTPException(status_code=400, detail="Unsupported export format")
            
            # Log the export action
            client_ip = "unknown"  # Would need request context
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=client_ip,
                user_agent="web_admin",
                resource="audit_log",
                action="export",
                details={"format": format},
                security_level=SecurityLevel.HIGH,
                success=True
            )
            
            exported_data = self.security_manager.export_audit_log(format)
            
            return JSONResponse(
                content=json.loads(exported_data),
                headers={
                    "Content-Disposition": f"attachment; filename=audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
                }
            )
        
        @self.app.get("/api/security/sessions")
        async def get_active_sessions(username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))):
            """Get active sessions"""
            sessions = [
                {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "is_active": session.is_active,
                    "permissions": list(session.permissions)
                }
                for session in self.security_manager.active_sessions.values()
                if session.is_active
            ]
            return sessions
        
        @self.app.delete("/api/security/sessions/{session_id}")
        async def terminate_session(
            session_id: str,
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Terminate a specific session"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            success = self.security_manager.invalidate_session(session_id)
            
            # Log the action
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=client_ip,
                user_agent=user_agent,
                resource="session_management",
                action="session_terminated",
                details={"terminated_session": session_id},
                security_level=SecurityLevel.HIGH,
                success=success
            )
            
            return {"success": success, "message": "Session terminated" if success else "Session not found"}
        
        @self.app.get("/api/security/login-attempts")
        async def get_login_attempts(
            limit: int = 100,
            username: str = Depends(require_permission(Permission.AUDIT_READ))
        ):
            """Get recent login attempts"""
            attempts = self.security_manager.login_attempts[-limit:]
            return [
                {
                    "ip_address": attempt.ip_address,
                    "user_id": attempt.user_id,
                    "timestamp": attempt.timestamp.isoformat(),
                    "success": attempt.success,
                    "user_agent": attempt.user_agent
                }
                for attempt in reversed(attempts)
            ]
        
        @self.app.get("/api/security/blocked-users")
        async def get_blocked_users(username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))):
            """Get currently blocked users"""
            blocked = []
            for user_id, blocked_until in self.security_manager.blocked_users.items():
                blocked.append({
                    "user_id": user_id,
                    "blocked_until": blocked_until.isoformat(),
                    "failed_attempts": self.security_manager.failed_login_counts.get(user_id, 0)
                })
            return blocked
        
        @self.app.delete("/api/security/blocked-users/{user_id}")
        async def unblock_user(
            user_id: str,
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Manually unblock a user"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            was_blocked = user_id in self.security_manager.blocked_users
            
            if was_blocked:
                del self.security_manager.blocked_users[user_id]
                self.security_manager.failed_login_counts.pop(user_id, None)
            
            # Log the action
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=client_ip,
                user_agent=user_agent,
                resource="user_management",
                action="user_unblocked",
                details={"unblocked_user": user_id},
                security_level=SecurityLevel.HIGH,
                success=was_blocked
            )
            
            return {"success": was_blocked, "message": "User unblocked" if was_blocked else "User was not blocked"}
        
        # User management with audit logging
        @self.app.post("/api/admin/users")
        async def create_admin_user(
            user_data: dict,
            req: Request,
            username: str = Depends(require_permission(Permission.USER_ADMIN))
        ):
            """Create new admin user"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            new_username = user_data.get("username")
            password = user_data.get("password")
            role = user_data.get("role", Role.VIEWER)
            
            if not new_username or not password:
                raise HTTPException(status_code=400, detail="Username and password are required")
            
            if role not in ROLE_PERMISSIONS:
                raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
            
            success = self.auth_manager.create_user(
                username=new_username,
                password=password,
                role=role,
                created_by=username,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            if success:
                return {"success": True, "message": f"User '{new_username}' created successfully"}
            else:
                raise HTTPException(status_code=400, detail="Failed to create user (user may already exist or password is too weak)")
        
        @self.app.put("/api/admin/users/{target_username}/password")
        async def change_user_password(
            target_username: str,
            password_data: dict,
            req: Request,
            username: str = Depends(require_permission(Permission.USER_ADMIN))
        ):
            """Change user password"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            new_password = password_data.get("password")
            if not new_password:
                raise HTTPException(status_code=400, detail="Password is required")
            
            success = self.auth_manager.update_user_password(
                username=target_username,
                new_password=new_password,
                updated_by=username,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            if success:
                return {"success": True, "message": f"Password updated for user '{target_username}'"}
            else:
                raise HTTPException(status_code=400, detail="Failed to update password (user not found or password too weak)")
        
        @self.app.delete("/api/admin/users/{target_username}")
        async def delete_admin_user(
            target_username: str,
            req: Request,
            username: str = Depends(require_permission(Permission.USER_ADMIN))
        ):
            """Delete admin user"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            if target_username == "admin":
                raise HTTPException(status_code=400, detail="Cannot delete admin user")
            
            success = self.auth_manager.delete_user(
                username=target_username,
                deleted_by=username,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            if success:
                return {"success": True, "message": f"User '{target_username}' deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        @self.app.get("/api/admin/users")
        async def list_admin_users(username: str = Depends(require_permission(Permission.USER_READ))):
            """List all admin users"""
            users = []
            for user_id, user_data in self.auth_manager.users.items():
                users.append({
                    "username": user_data["username"],
                    "role": user_data["role"],
                    "permissions": list(user_data["permissions"]),
                    "created_at": user_data["created_at"].isoformat(),
                    "last_login": user_data["last_login"].isoformat() if user_data["last_login"] else None,
                    "login_count": user_data.get("login_count", 0),
                    "is_active": user_data.get("is_active", True)
                })
            return users
            return UserStatsResponse(
                total_users=stats.total_users,
                active_users=stats.active_users,
                new_users_today=stats.new_users_today,
                total_messages=stats.total_messages,
                messages_today=stats.messages_today,
                top_users=stats.top_users,
                permission_distribution=stats.permission_distribution,
                subscription_distribution=stats.subscription_distribution
            )
        
        @self.app.get("/api/users/by-tag/{tag}")
        async def get_users_by_tag(
            tag: str,
            username: str = Depends(require_permission("read"))
        ):
            users = self.user_manager.get_users_by_tag(tag)
            return [self._user_to_response(user) for user in users]
        
        @self.app.get("/api/users/export")
        async def export_users(username: str = Depends(require_permission("admin"))):
            data = self.user_manager.export_users()
            return data
        
        @self.app.post("/api/users/import")
        async def import_users(
            import_data: Dict[str, Any],
            username: str = Depends(require_permission("admin"))
        ):
            success = self.user_manager.import_users(import_data)
            if success:
                return {"success": True, "message": "Users imported successfully"}
            else:
                raise HTTPException(status_code=400, detail="Failed to import users")
        
        # Broadcast and scheduling routes
        @self.app.get("/api/templates", response_model=List[MessageTemplateResponse])
        async def get_templates(
            category: Optional[str] = None,
            username: str = Depends(require_permission("read"))
        ):
            templates = self.scheduler.get_templates(category)
            return [self._template_to_response(t) for t in templates]
        
        @self.app.post("/api/templates")
        async def create_template(
            template_data: CreateTemplateRequest,
            username: str = Depends(require_permission("write"))
        ):
            template_id = self.scheduler.create_template(
                name=template_data.name,
                content=template_data.content,
                description=template_data.description,
                variables=template_data.variables,
                category=template_data.category,
                created_by=username
            )
            
            if template_id:
                return {"success": True, "template_id": template_id}
            else:
                raise HTTPException(status_code=500, detail="Failed to create template")
        
        @self.app.get("/api/templates/{template_id}", response_model=MessageTemplateResponse)
        async def get_template(
            template_id: str,
            username: str = Depends(require_permission("read"))
        ):
            template = self.scheduler.get_template(template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            return self._template_to_response(template)
        
        @self.app.put("/api/templates/{template_id}")
        async def update_template(
            template_id: str,
            template_data: CreateTemplateRequest,
            username: str = Depends(require_permission("write"))
        ):
            success = self.scheduler.update_template(
                template_id,
                name=template_data.name,
                content=template_data.content,
                description=template_data.description,
                variables=template_data.variables,
                category=template_data.category
            )
            
            if success:
                return {"success": True, "message": "Template updated successfully"}
            else:
                raise HTTPException(status_code=404, detail="Template not found")
        
        @self.app.delete("/api/templates/{template_id}")
        async def delete_template(
            template_id: str,
            username: str = Depends(require_permission("write"))
        ):
            success = self.scheduler.delete_template(template_id)
            if success:
                return {"success": True, "message": "Template deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Template not found")
        
        @self.app.get("/api/broadcasts", response_model=List[ScheduledBroadcastResponse])
        async def get_scheduled_broadcasts(
            active_only: bool = False,
            username: str = Depends(require_permission("read"))
        ):
            broadcasts = self.scheduler.get_scheduled_broadcasts(active_only)
            return [self._broadcast_to_response(b) for b in broadcasts]
        
        @self.app.post("/api/broadcasts")
        async def schedule_broadcast(
            broadcast_data: ScheduleBroadcastRequest,
            username: str = Depends(require_permission("write"))
        ):
            try:
                schedule_type = ScheduleType(broadcast_data.schedule_type)
                recurrence_pattern = None
                if broadcast_data.recurrence_pattern:
                    recurrence_pattern = RecurrencePattern(broadcast_data.recurrence_pattern)
                
                broadcast_id = self.scheduler.schedule_broadcast(
                    name=broadcast_data.name,
                    content=broadcast_data.content,
                    scheduled_time=broadcast_data.scheduled_time,
                    channel=broadcast_data.channel,
                    interface_id=broadcast_data.interface_id,
                    schedule_type=schedule_type,
                    recurrence_pattern=recurrence_pattern,
                    interval_minutes=broadcast_data.interval_minutes,
                    end_date=broadcast_data.end_date,
                    max_occurrences=broadcast_data.max_occurrences,
                    template_id=broadcast_data.template_id,
                    variables=broadcast_data.variables,
                    created_by=username
                )
                
                if broadcast_id:
                    return {"success": True, "broadcast_id": broadcast_id}
                else:
                    raise HTTPException(status_code=500, detail="Failed to schedule broadcast")
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid parameter: {e}")
        
        @self.app.get("/api/broadcasts/{broadcast_id}", response_model=ScheduledBroadcastResponse)
        async def get_broadcast(
            broadcast_id: str,
            username: str = Depends(require_permission("read"))
        ):
            broadcast = self.scheduler.get_broadcast(broadcast_id)
            if not broadcast:
                raise HTTPException(status_code=404, detail="Broadcast not found")
            return self._broadcast_to_response(broadcast)
        
        @self.app.put("/api/broadcasts/{broadcast_id}")
        async def update_broadcast(
            broadcast_id: str,
            broadcast_data: ScheduleBroadcastRequest,
            username: str = Depends(require_permission("write"))
        ):
            try:
                update_data = broadcast_data.dict(exclude_unset=True)
                
                # Convert enum strings
                if "schedule_type" in update_data:
                    update_data["schedule_type"] = ScheduleType(update_data["schedule_type"])
                if "recurrence_pattern" in update_data and update_data["recurrence_pattern"]:
                    update_data["recurrence_pattern"] = RecurrencePattern(update_data["recurrence_pattern"])
                
                success = self.scheduler.update_broadcast(broadcast_id, **update_data)
                
                if success:
                    return {"success": True, "message": "Broadcast updated successfully"}
                else:
                    raise HTTPException(status_code=404, detail="Broadcast not found")
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid parameter: {e}")
        
        @self.app.post("/api/broadcasts/{broadcast_id}/cancel")
        async def cancel_broadcast(
            broadcast_id: str,
            username: str = Depends(require_permission("write"))
        ):
            success = self.scheduler.cancel_broadcast(broadcast_id)
            if success:
                return {"success": True, "message": "Broadcast cancelled successfully"}
            else:
                raise HTTPException(status_code=404, detail="Broadcast not found")
        
        @self.app.delete("/api/broadcasts/{broadcast_id}")
        async def delete_broadcast(
            broadcast_id: str,
            username: str = Depends(require_permission("write"))
        ):
            success = self.scheduler.delete_broadcast(broadcast_id)
            if success:
                return {"success": True, "message": "Broadcast deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Broadcast not found")
        
        @self.app.get("/api/broadcasts/upcoming")
        async def get_upcoming_broadcasts(
            hours: int = 24,
            username: str = Depends(require_permission("read"))
        ):
            broadcasts = self.scheduler.get_upcoming_broadcasts(hours)
            return [self._broadcast_to_response(b) for b in broadcasts]
        
        @self.app.get("/api/broadcasts/history", response_model=List[BroadcastHistoryResponse])
        async def get_broadcast_history(
            limit: int = 100,
            username: str = Depends(require_permission("read"))
        ):
            history = self.scheduler.get_broadcast_history(limit)
            return [self._history_to_response(h) for h in history]
        
        @self.app.post("/api/broadcasts/send")
        async def send_immediate_broadcast(
            broadcast_data: ImmediateBroadcastRequest,
            username: str = Depends(require_permission("write"))
        ):
            success = await self.scheduler.send_immediate_broadcast(
                content=broadcast_data.content,
                channel=broadcast_data.channel,
                interface_id=broadcast_data.interface_id,
                sent_by=username
            )
            
            if success:
                return {"success": True, "message": "Broadcast sent successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to send broadcast")
        
        # Chat monitoring routes
        @self.app.get("/api/messages/search", response_model=List[MessageResponse])
        async def search_messages(
            query: Optional[str] = None,
            sender_id: Optional[str] = None,
            channel: Optional[int] = None,
            interface_id: Optional[str] = None,
            message_type: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            limit: int = 100,
            offset: int = 0,
            username: str = Depends(require_permission("read"))
        ):
            filtered_messages = self._filter_messages(
                query=query,
                sender_id=sender_id,
                channel=channel,
                interface_id=interface_id,
                message_type=message_type,
                start_date=start_date,
                end_date=end_date
            )
            
            # Apply pagination
            paginated = filtered_messages[offset:offset + limit]
            
            return [self._message_to_response(msg) for msg in paginated]
        
        @self.app.get("/api/messages/recent", response_model=List[MessageResponse])
        async def get_recent_messages(
            limit: int = 50,
            channel: Optional[int] = None,
            username: str = Depends(require_permission("read"))
        ):
            messages = self.messages_cache[-limit:] if self.messages_cache else []
            
            if channel is not None:
                messages = [msg for msg in messages if msg.channel == channel]
            
            # Sort by timestamp descending (most recent first)
            messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
            
            return [self._message_to_response(msg) for msg in messages]
        
        @self.app.get("/api/messages/live")
        async def get_live_messages(
            channel: Optional[int] = None,
            username: str = Depends(require_permission("read"))
        ):
            """Get live message feed via Server-Sent Events"""
            from fastapi.responses import StreamingResponse
            
            async def message_stream():
                last_message_count = len(self.messages_cache)
                
                while True:
                    current_count = len(self.messages_cache)
                    
                    if current_count > last_message_count:
                        # New messages available
                        new_messages = self.messages_cache[last_message_count:]
                        
                        for msg in new_messages:
                            if channel is None or msg.channel == channel:
                                message_data = self._message_to_response(msg)
                                yield f"data: {json.dumps(message_data.dict())}\n\n"
                        
                        last_message_count = current_count
                    
                    await asyncio.sleep(1)  # Check for new messages every second
            
            return StreamingResponse(
                message_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        
        @self.app.post("/api/messages/send")
        async def send_direct_message(
            message_data: DirectMessageRequest,
            username: str = Depends(require_permission("write"))
        ):
            success = await self._send_direct_message(
                recipient_id=message_data.recipient_id,
                content=message_data.content,
                interface_id=message_data.interface_id,
                sender=username
            )
            
            if success:
                return {"success": True, "message": "Message sent successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to send message")
        
        @self.app.get("/api/messages/stats", response_model=ChatStatsResponse)
        async def get_chat_stats(username: str = Depends(require_permission("read"))):
            return await self._get_chat_stats()
        
        @self.app.get("/api/messages/channels")
        async def get_active_channels(username: str = Depends(require_permission("read"))):
            channels = set()
            for msg in self.messages_cache:
                channels.add(msg.channel)
            
            return {
                "active_channels": sorted(list(channels)),
                "total_channels": len(channels)
            }
        
        @self.app.get("/api/messages/senders")
        async def get_active_senders(
            limit: int = 20,
            username: str = Depends(require_permission("read"))
        ):
            sender_counts = {}
            for msg in self.messages_cache:
                sender_counts[msg.sender_id] = sender_counts.get(msg.sender_id, 0) + 1
            
            # Sort by message count
            sorted_senders = sorted(
                sender_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Get sender names from user manager
            senders_info = []
            for sender_id, count in sorted_senders:
                user = self.user_manager.get_user(sender_id)
                senders_info.append({
                    "sender_id": sender_id,
                    "sender_name": user.short_name if user else f"User-{sender_id[-4:]}",
                    "message_count": count,
                    "last_seen": user.last_seen.isoformat() if user and user.last_seen else None
                })
            
            return {"senders": senders_info}
        
        @self.app.delete("/api/messages/{message_id}")
        async def delete_message(
            message_id: str,
            username: str = Depends(require_permission("admin"))
        ):
            # Find and remove message from cache
            for i, msg in enumerate(self.messages_cache):
                if msg.id == message_id:
                    del self.messages_cache[i]
                    return {"success": True, "message": "Message deleted successfully"}
            
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Configuration management routes
        @self.app.get("/api/config/sections")
        async def get_config_sections(username: str = Depends(require_permission("read"))):
            """Get all configuration sections"""
            return await self._get_config_sections()
        
        @self.app.get("/api/config/{section}")
        async def get_config_section(
            section: str,
            username: str = Depends(require_permission("read"))
        ):
            """Get configuration for a specific section"""
            config_data = await self._get_config_section(section)
            if not config_data:
                raise HTTPException(status_code=404, detail="Configuration section not found")
            return config_data
        
        @self.app.get("/api/config/{section}/{key}")
        async def get_config_value(
            section: str,
            key: str,
            username: str = Depends(require_permission("read"))
        ):
            """Get a specific configuration value"""
            value = await self._get_config_value(section, key)
            if value is None:
                raise HTTPException(status_code=404, detail="Configuration key not found")
            return {"section": section, "key": key, "value": value}
        
        @self.app.put("/api/config/{section}/{key}")
        async def update_config_value(
            section: str,
            key: str,
            update_data: Dict[str, Any],
            username: str = Depends(require_permission("admin"))
        ):
            """Update a configuration value"""
            value = update_data.get("value")
            if value is None:
                raise HTTPException(status_code=400, detail="Value is required")
            
            success = await self._update_config_value(section, key, value, username)
            if success:
                return {"success": True, "message": "Configuration updated successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to update configuration")
        
        @self.app.post("/api/config/validate")
        async def validate_config(
            config_data: Dict[str, Any],
            username: str = Depends(require_permission("admin"))
        ):
            """Validate configuration data"""
            validation_result = await self._validate_config(config_data)
            return validation_result
        
        @self.app.post("/api/config/test")
        async def test_config(
            config_data: Dict[str, Any],
            username: str = Depends(require_permission("admin"))
        ):
            """Test configuration without applying it"""
            test_result = await self._test_config(config_data)
            return test_result
        
        @self.app.get("/api/config/backups")
        async def get_config_backups(username: str = Depends(require_permission("read"))):
            """Get list of configuration backups"""
            backups = await self._get_config_backups()
            return backups
        
        @self.app.post("/api/config/backup")
        async def create_config_backup(
            backup_data: Dict[str, str],
            username: str = Depends(require_permission("admin"))
        ):
            """Create a configuration backup"""
            description = backup_data.get("description", "Manual backup")
            backup_id = await self._create_config_backup(description, username)
            
            if backup_id:
                return {"success": True, "backup_id": backup_id}
            else:
                raise HTTPException(status_code=500, detail="Failed to create backup")
        
        @self.app.post("/api/config/restore/{backup_id}")
        async def restore_config_backup(
            backup_id: str,
            username: str = Depends(require_permission("admin"))
        ):
            """Restore configuration from backup"""
            success = await self._restore_config_backup(backup_id, username)
            if success:
                return {"success": True, "message": "Configuration restored successfully"}
            else:
                raise HTTPException(status_code=404, detail="Backup not found or restore failed")
        
        @self.app.delete("/api/config/backups/{backup_id}")
        async def delete_config_backup(
            backup_id: str,
            username: str = Depends(require_permission("admin"))
        ):
            """Delete a configuration backup"""
            success = await self._delete_config_backup(backup_id)
            if success:
                return {"success": True, "message": "Backup deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Backup not found")
        
        # Plugin management routes
        @self.app.get("/api/plugins")
        async def get_plugins(username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))):
            """Get list of all plugins with status and metadata"""
            return await self._get_plugins()
        
        @self.app.get("/api/plugins/{plugin_name}")
        async def get_plugin_details(
            plugin_name: str,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            """Get detailed information about a specific plugin"""
            plugin_info = await self._get_plugin_details(plugin_name)
            if not plugin_info:
                raise HTTPException(status_code=404, detail="Plugin not found")
            return plugin_info
        
        @self.app.post("/api/plugins/{plugin_name}/enable")
        async def toggle_plugin_enabled(
            plugin_name: str,
            enable_data: Dict[str, Any],
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Enable or disable a plugin at startup"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            enabled = enable_data.get('enabled', False)
            success = await self._toggle_plugin_enabled(
                plugin_name, enabled, username, client_ip, user_agent
            )
            if success:
                action = "enabled" if enabled else "disabled"
                return {"success": True, "message": f"Plugin '{plugin_name}' will be {action} at next startup"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to update plugin '{plugin_name}' enabled state")
        
        @self.app.post("/api/plugins/{plugin_name}/disable")
        async def disable_plugin(
            plugin_name: str,
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Disable a plugin"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            success = await self._disable_plugin(plugin_name, username, client_ip, user_agent)
            if success:
                return {"success": True, "message": f"Plugin '{plugin_name}' disabled successfully"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to disable plugin '{plugin_name}'")
        
        @self.app.post("/api/plugins/{plugin_name}/restart")
        async def restart_plugin(
            plugin_name: str,
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Restart a plugin"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            success = await self._restart_plugin(plugin_name, username, client_ip, user_agent)
            if success:
                return {"success": True, "message": f"Plugin '{plugin_name}' restarted successfully"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to restart plugin '{plugin_name}'")
        
        @self.app.get("/api/plugins/{plugin_name}/config")
        async def get_plugin_config(
            plugin_name: str,
            username: str = Depends(require_permission(Permission.SYSTEM_CONFIG))
        ):
            """Get plugin configuration"""
            config = await self._get_plugin_config(plugin_name)
            if config is None:
                raise HTTPException(status_code=404, detail="Plugin not found")
            return config
        
        @self.app.put("/api/plugins/{plugin_name}/config")
        async def update_plugin_config(
            plugin_name: str,
            config_data: Dict[str, Any],
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_CONFIG))
        ):
            """Update plugin configuration"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            success = await self._update_plugin_config(
                plugin_name, config_data, username, client_ip, user_agent
            )
            if success:
                return {"success": True, "message": f"Configuration updated for plugin '{plugin_name}'"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to update configuration for plugin '{plugin_name}'")
        
        @self.app.get("/api/plugins/{plugin_name}/logs")
        async def get_plugin_logs(
            plugin_name: str,
            lines: int = 100,
            level: Optional[str] = None,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            """Get plugin logs"""
            logs = await self._get_plugin_logs(plugin_name, lines, level)
            return {"plugin": plugin_name, "logs": logs, "total": len(logs)}
        
        @self.app.get("/api/plugins/{plugin_name}/metrics")
        async def get_plugin_metrics(
            plugin_name: str,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            """Get plugin metrics and health information"""
            metrics = await self._get_plugin_metrics(plugin_name)
            if not metrics:
                raise HTTPException(status_code=404, detail="Plugin not found")
            return metrics
        
        @self.app.get("/api/plugins/{plugin_name}/errors")
        async def get_plugin_errors(
            plugin_name: str,
            limit: int = 50,
            username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))
        ):
            """Get recent plugin errors"""
            errors = await self._get_plugin_errors(plugin_name, limit)
            return {"plugin": plugin_name, "errors": errors, "total": len(errors)}
        
        @self.app.post("/api/plugins/install")
        async def install_plugin(
            plugin_data: Dict[str, Any],
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Install a new plugin from a path or URL"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            source = plugin_data.get("source")
            if not source:
                raise HTTPException(status_code=400, detail="Plugin source is required")
            
            result = await self._install_plugin(source, username, client_ip, user_agent)
            if result["success"]:
                return result
            else:
                raise HTTPException(status_code=500, detail=result.get("message", "Failed to install plugin"))
        
        @self.app.delete("/api/plugins/{plugin_name}")
        async def uninstall_plugin(
            plugin_name: str,
            req: Request,
            username: str = Depends(require_permission(Permission.SYSTEM_ADMIN))
        ):
            """Uninstall a plugin"""
            client_ip = req.client.host if req.client else "unknown"
            user_agent = req.headers.get("user-agent", "unknown")
            
            success = await self._uninstall_plugin(plugin_name, username, client_ip, user_agent)
            if success:
                return {"success": True, "message": f"Plugin '{plugin_name}' uninstalled successfully"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin '{plugin_name}'")
        
        @self.app.get("/api/plugins/available")
        async def get_available_plugins(username: str = Depends(require_permission(Permission.SYSTEM_MONITOR))):
            """Get list of available plugins that can be installed"""
            return await self._get_available_plugins()
        
        # Service management routes
        @self.app.get("/api/services", response_model=List[ServiceStatusResponse])
        async def get_services_status(username: str = Depends(require_permission(Permission.SERVICE_READ))):
            """Get status of all services"""
            return await self._get_services_status()
        
        @self.app.get("/api/services/{service_name}")
        async def get_service_status(
            service_name: str,
            username: str = Depends(require_permission("read"))
        ):
            """Get status of a specific service"""
            status = await self._get_service_status(service_name)
            if not status:
                raise HTTPException(status_code=404, detail="Service not found")
            return status
        
        @self.app.post("/api/services/{service_name}/action")
        async def service_action(
            service_name: str,
            action_data: ServiceActionRequest,
            username: str = Depends(require_permission("admin"))
        ):
            """Perform action on a service (start, stop, restart, enable, disable)"""
            success = await self._perform_service_action(service_name, action_data.action, username)
            if success:
                return {"success": True, "message": f"Service {action_data.action} completed successfully"}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to {action_data.action} service")
        
        @self.app.get("/api/services/{service_name}/logs")
        async def get_service_logs(
            service_name: str,
            lines: int = 100,
            level: Optional[str] = None,
            username: str = Depends(require_permission("read"))
        ):
            """Get service logs with optional level filtering"""
            logs = await self._get_service_logs(service_name, lines)
            
            # Filter by level if specified
            if level and level.upper() != "ALL":
                logs = [log for log in logs if log.get("level", "").upper() == level.upper()]
            
            return {"service": service_name, "logs": logs}
        
        @self.app.get("/api/system/health")
        async def get_system_health(username: str = Depends(require_permission("read"))):
            """Get comprehensive system health check"""
            health = await self._get_system_health()
            return health
        
        # Security and audit routes
        @self.app.get("/api/security/summary")
        async def get_security_summary(username: str = Depends(require_permission("admin"))):
            """Get security summary and statistics"""
            return self.security_manager.get_security_summary()
        
        @self.app.get("/api/security/audit-log")
        async def get_audit_log(
            limit: int = 100,
            event_type: Optional[str] = None,
            user_id: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            username: str = Depends(require_permission("admin"))
        ):
            """Get audit log entries"""
            audit_event_type = None
            if event_type:
                try:
                    audit_event_type = AuditEventType(event_type)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid event type")
            
            entries = self.security_manager.get_audit_log(
                limit=limit,
                event_type=audit_event_type,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return {
                "entries": [
                    {
                        "id": entry.id,
                        "timestamp": entry.timestamp.isoformat(),
                        "event_type": entry.event_type.value,
                        "user_id": entry.user_id,
                        "user_name": entry.user_name,
                        "ip_address": entry.ip_address,
                        "user_agent": entry.user_agent,
                        "resource": entry.resource,
                        "action": entry.action,
                        "details": entry.details,
                        "security_level": entry.security_level.value,
                        "success": entry.success,
                        "error_message": entry.error_message
                    }
                    for entry in entries
                ],
                "total": len(entries)
            }
        
        @self.app.get("/api/security/sessions")
        async def get_active_sessions(username: str = Depends(require_permission("admin"))):
            """Get active user sessions"""
            sessions = [
                {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "is_active": session.is_active
                }
                for session in self.security_manager.active_sessions.values()
                if session.is_active
            ]
            
            return {"sessions": sessions, "total": len(sessions)}
        
        @self.app.delete("/api/security/sessions/{session_id}")
        async def invalidate_session(
            session_id: str,
            username: str = Depends(require_permission("admin"))
        ):
            """Invalidate a user session"""
            success = self.security_manager.invalidate_session(session_id)
            if success:
                return {"success": True, "message": "Session invalidated successfully"}
            else:
                raise HTTPException(status_code=404, detail="Session not found")
        
        @self.app.get("/api/security/blocked-users")
        async def get_blocked_users(username: str = Depends(require_permission("admin"))):
            """Get list of blocked users"""
            blocked = []
            for user_id, lockout_time in self.security_manager.blocked_users.items():
                blocked.append({
                    "user_id": user_id,
                    "locked_until": lockout_time.isoformat(),
                    "failed_attempts": self.security_manager.failed_login_counts.get(user_id, 0)
                })
            
            return {"blocked_users": blocked, "total": len(blocked)}
        
        @self.app.delete("/api/security/blocked-users/{user_id}")
        async def unblock_user(
            user_id: str,
            username: str = Depends(require_permission("admin"))
        ):
            """Unblock a user"""
            if user_id in self.security_manager.blocked_users:
                del self.security_manager.blocked_users[user_id]
                self.security_manager.failed_login_counts.pop(user_id, None)
                
                # Log the unblock action
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    user_id=username,
                    user_name=username,
                    ip_address=None,
                    user_agent=None,
                    resource="user_management",
                    action="user_unblocked",
                    details={"unblocked_user": user_id},
                    security_level=SecurityLevel.MEDIUM,
                    success=True
                )
                
                return {"success": True, "message": "User unblocked successfully"}
            else:
                raise HTTPException(status_code=404, detail="User not found in blocked list")
        
        @self.app.get("/api/security/login-attempts")
        async def get_login_attempts(
            limit: int = 100,
            username: str = Depends(require_permission("admin"))
        ):
            """Get recent login attempts"""
            attempts = sorted(
                self.security_manager.login_attempts,
                key=lambda a: a.timestamp,
                reverse=True
            )[:limit]
            
            return {
                "attempts": [
                    {
                        "ip_address": attempt.ip_address,
                        "user_id": attempt.user_id,
                        "timestamp": attempt.timestamp.isoformat(),
                        "success": attempt.success,
                        "user_agent": attempt.user_agent
                    }
                    for attempt in attempts
                ],
                "total": len(attempts)
            }
        
        @self.app.post("/api/security/export-audit-log")
        async def export_audit_log(
            export_format: str = "json",
            username: str = Depends(require_permission("admin"))
        ):
            """Export audit log"""
            try:
                exported_data = self.security_manager.export_audit_log(export_format)
                
                # Log the export action
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SYSTEM_ACCESS,
                    user_id=username,
                    user_name=username,
                    ip_address=None,
                    user_agent=None,
                    resource="audit_log",
                    action="export",
                    details={"format": export_format},
                    security_level=SecurityLevel.HIGH,
                    success=True
                )
                
                return {"data": exported_data, "format": export_format}
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Export failed: {e}")
        
        @self.app.post("/api/security/cleanup")
        async def cleanup_security_data(username: str = Depends(require_permission("admin"))):
            """Clean up old security data"""
            self.security_manager.cleanup_expired_sessions()
            self.security_manager.cleanup_old_audit_logs()
            
            # Log the cleanup action
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=None,
                user_agent=None,
                resource="security",
                action="cleanup",
                details={},
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
            
            return {"success": True, "message": "Security data cleanup completed"}
        
        # Broadcast routes
        @self.app.post("/api/broadcast/send")
        async def send_broadcast(
            message: BroadcastMessage,
            username: str = Depends(require_permission("write"))
        ):
            return await self._send_broadcast(message, username)
        
        # Configuration routes
        @self.app.get("/api/config")
        async def get_config(username: str = Depends(require_permission("admin"))):
            return await self._get_config()
        
        @self.app.post("/api/config/update")
        async def update_config(
            update: ConfigUpdate,
            username: str = Depends(require_permission("admin"))
        ):
            return await self._update_config(update, username)
        
        # WebSocket endpoint
        @self.app.websocket("/ws/{client_id}")
        async def websocket_endpoint(websocket: WebSocket, client_id: str):
            # Note: In production, you'd want to authenticate WebSocket connections
            # For now, we'll assume admin permissions
            permissions = {"read", "write", "admin", "system"}
            
            await self.websocket_manager.connect(websocket, client_id, permissions)
            try:
                while True:
                    data = await websocket.receive_text()
                    # Handle WebSocket messages if needed
                    await self.websocket_manager.send_personal_message(
                        f"Echo: {data}", client_id
                    )
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(client_id)
        
        # Main dashboard route
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        # Plugin management page
        @self.app.get("/plugins", response_class=HTMLResponse)
        async def plugins_page(request: Request):
            return self.templates.TemplateResponse("plugins.html", {"request": request})
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}
    
    async def _real_time_update_loop(self):
        """Real-time update loop for WebSocket clients"""
        last_message_count = 0
        
        while self.is_running:
            try:
                # Check for new messages
                current_message_count = len(self.messages_cache)
                if current_message_count > last_message_count:
                    # New messages available
                    new_messages = self.messages_cache[last_message_count:]
                    
                    for message in new_messages:
                        message_data = self._message_to_response(message)
                        await self.websocket_manager.broadcast(
                            json.dumps({
                                "type": "new_message",
                                "data": message_data.dict()
                            }),
                            permission_required="read"
                        )
                    
                    last_message_count = current_message_count
                
                # Get current system data (every 30 seconds)
                if int(asyncio.get_event_loop().time()) % 30 == 0:
                    system_data = self.system_monitor.to_dict()
                    
                    # Broadcast to WebSocket clients
                    await self.websocket_manager.broadcast(
                        json.dumps({
                            "type": "system_update",
                            "data": system_data
                        }),
                        permission_required="read"
                    )
                
                # Wait for next update
                await asyncio.sleep(1)  # Check every second for messages
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in real-time update loop: {e}")
                await asyncio.sleep(1)
    
    async def _get_system_status(self) -> SystemStatus:
        """Get current system status"""
        summary = self.system_monitor.get_system_summary()
        
        return SystemStatus(
            status=summary["system_status"],
            uptime=summary["uptime"],
            active_plugins=["bbs", "emergency", "bot", "weather", "email", "web_admin"],
            node_count=summary["node_count"],
            message_count=len(self.messages_cache),
            active_incidents=summary["active_alerts"],
            last_updated=datetime.now(timezone.utc)
        )
    
    async def _get_nodes(self) -> List[NodeInfo]:
        """Get node information"""
        nodes = self.system_monitor.get_all_nodes()
        
        return [
            NodeInfo(
                node_id=node.node_id,
                short_name=node.short_name,
                long_name=node.long_name,
                hardware=node.hardware,
                role=node.role,
                battery_level=node.battery_level,
                snr=node.snr,
                last_seen=node.last_seen,
                location=node.location
            )
            for node in nodes
        ]
    
    async def _get_messages(self, limit: int, offset: int) -> List[MessageInfo]:
        """Get recent messages"""
        # This would integrate with actual message history
        return []  # Mock data for now
    
    async def _send_broadcast(self, message: BroadcastMessage, username: str) -> Dict[str, Any]:
        """Send broadcast message"""
        # This would integrate with the message router
        self.logger.info(f"Broadcast message from {username}: {message.content}")
        
        # Notify WebSocket clients
        await self.websocket_manager.broadcast(
            json.dumps({
                "type": "broadcast_sent",
                "content": message.content,
                "sender": username,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            permission_required="read"
        )
        
        return {"status": "sent", "message_id": str(uuid.uuid4())}
    
    async def _get_config(self) -> Dict[str, Any]:
        """Get system configuration"""
        # This would integrate with the configuration manager
        return {"status": "not_implemented"}
    
    async def _update_config(self, update: ConfigUpdate, username: str) -> Dict[str, Any]:
        """Update system configuration"""
        # This would integrate with the configuration manager
        self.logger.info(f"Config update by {username}: {update.key} = {update.value}")
        return {"status": "updated"}
    
    async def initialize(self) -> bool:
        """Initialize the web service"""
        try:
            # Any initialization logic here
            self.logger.info("WebAdminService initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize WebAdminService: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the web service"""
        try:
            # Start system monitor
            await self.system_monitor.start()
            
            # Start scheduler
            await self.scheduler.start()
            
            # Start real-time update task
            self.update_task = self.create_task(self._real_time_update_loop())
            
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info" if not self.debug else "debug"
            )
            self.server = uvicorn.Server(config)
            
            # Start server in background task
            self.server_task = self.create_task(self.server.serve())
            
            self.is_running = True
            self.logger.info(f"Web admin service started on http://{self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start web admin service: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the web service"""
        try:
            self.is_running = False
            
            # Stop system monitor
            await self.system_monitor.stop()
            
            # Stop scheduler
            await self.scheduler.stop()
            
            if self.server:
                self.server.should_exit = True
            
            if self.server_task:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            await self.cancel_tasks()
            self.logger.info("Web admin service stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping web admin service: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up web service resources"""
        try:
            # Close any remaining connections
            for client_id in list(self.websocket_manager.active_connections.keys()):
                self.websocket_manager.disconnect(client_id)
            
            self.logger.info("WebAdminService cleanup completed")
            return True
        except Exception as e:
            self.logger.error(f"Error during WebAdminService cleanup: {e}")
            return False
    
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata"""
        return PluginMetadata(
            name="web_admin",
            version="1.0.0",
            description="Web-based administration interface for ZephyrGate",
            author="ZephyrGate Team",
            dependencies=[],
            enabled=True,
            config_schema=self.get_config_schema()
        )
    
    async def handle_plugin_message(self, message: PluginMessage) -> Optional[Any]:
        """Handle inter-plugin messages"""
        if message.type == PluginMessageType.SYSTEM_EVENT:
            # Broadcast system events to WebSocket clients
            await self.websocket_manager.broadcast(
                json.dumps({
                    "type": "system_event",
                    "data": message.data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }),
                permission_required="read"
            )
        
        elif message.type == PluginMessageType.MESH_MESSAGE:
            # Update node status from mesh messages
            if isinstance(message.data, Message):
                self.system_monitor.update_node_status(message.data)
                # Store message for history
                self.messages_cache.append(message.data)
                # Limit cache size
                if len(self.messages_cache) > 1000:
                    self.messages_cache.pop(0)
        
        return None
    
    def handle_mesh_message(self, message: Message):
        """Handle incoming mesh messages for monitoring"""
        try:
            # Update node status
            self.system_monitor.update_node_status(message)
            
            # Update user activity
            self.user_manager.update_user_activity(message.sender_id, message)
            
            # Store message for history
            self.messages_cache.append(message)
            
            # Limit cache size
            if len(self.messages_cache) > 1000:
                self.messages_cache.pop(0)
                
        except Exception as e:
            self.logger.error(f"Error handling mesh message: {e}")
    
    def _user_to_response(self, user) -> UserProfileResponse:
        """Convert UserProfile to API response"""
        return UserProfileResponse(
            node_id=user.node_id,
            short_name=user.short_name,
            long_name=user.long_name,
            email=user.email,
            phone=user.phone,
            address=user.address,
            tags=list(user.tags),
            permissions=[p.value for p in user.permissions],
            subscriptions=[s.value for s in user.subscriptions],
            created_at=user.created_at,
            last_seen=user.last_seen,
            last_login=user.last_login,
            location=user.location,
            is_active=user.is_active,
            notes=user.notes,
            message_count=user.message_count,
            last_message_time=user.last_message_time,
            favorite_channels=user.favorite_channels
        )
    
    def _template_to_response(self, template) -> MessageTemplateResponse:
        """Convert MessageTemplate to API response"""
        return MessageTemplateResponse(
            id=template.id,
            name=template.name,
            content=template.content,
            description=template.description,
            variables=template.variables,
            category=template.category,
            created_at=template.created_at,
            created_by=template.created_by,
            usage_count=template.usage_count
        )
    
    def _broadcast_to_response(self, broadcast) -> ScheduledBroadcastResponse:
        """Convert ScheduledBroadcast to API response"""
        return ScheduledBroadcastResponse(
            id=broadcast.id,
            name=broadcast.name,
            content=broadcast.content,
            channel=broadcast.channel,
            interface_id=broadcast.interface_id,
            schedule_type=broadcast.schedule_type.value,
            scheduled_time=broadcast.scheduled_time,
            recurrence_pattern=broadcast.recurrence_pattern.value if broadcast.recurrence_pattern else None,
            interval_minutes=broadcast.interval_minutes,
            end_date=broadcast.end_date,
            max_occurrences=broadcast.max_occurrences,
            created_at=broadcast.created_at,
            created_by=broadcast.created_by,
            is_active=broadcast.is_active,
            template_id=broadcast.template_id,
            variables=broadcast.variables,
            last_sent=broadcast.last_sent,
            next_send=broadcast.next_send,
            send_count=broadcast.send_count,
            status=broadcast.status.value
        )
    
    def _history_to_response(self, history) -> BroadcastHistoryResponse:
        """Convert BroadcastHistory to API response"""
        return BroadcastHistoryResponse(
            id=history.id,
            schedule_id=history.schedule_id,
            content=history.content,
            channel=history.channel,
            interface_id=history.interface_id,
            sent_at=history.sent_at,
            sent_by=history.sent_by,
            status=history.status.value,
            error_message=history.error_message,
            recipient_count=history.recipient_count
        )
    
    async def _send_message_via_router(self, content: str, channel: Optional[int] = None, 
                                     interface_id: Optional[str] = None) -> bool:
        """Send message via the core message router"""
        try:
            # This would integrate with the actual message router
            # For now, just log the message
            self.logger.info(f"Sending broadcast: {content} (channel: {channel}, interface: {interface_id})")
            
            # In a real implementation, this would:
            # 1. Create a Message object
            # 2. Send it through the core message router
            # 3. Return success/failure status
            
            return True  # Mock success
            
        except Exception as e:
            self.logger.error(f"Error sending message via router: {e}")
            return False
    
    def _filter_messages(self, query: Optional[str] = None, sender_id: Optional[str] = None,
                        channel: Optional[int] = None, interface_id: Optional[str] = None,
                        message_type: Optional[str] = None, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[Message]:
        """Filter messages based on search criteria"""
        filtered = self.messages_cache.copy()
        
        if query:
            query_lower = query.lower()
            filtered = [
                msg for msg in filtered
                if (query_lower in msg.content.lower() or
                    query_lower in msg.sender_id.lower())
            ]
        
        if sender_id:
            filtered = [msg for msg in filtered if msg.sender_id == sender_id]
        
        if channel is not None:
            filtered = [msg for msg in filtered if msg.channel == channel]
        
        if interface_id:
            filtered = [msg for msg in filtered if msg.interface_id == interface_id]
        
        if message_type:
            try:
                msg_type = MessageType(message_type)
                filtered = [msg for msg in filtered if msg.message_type == msg_type]
            except ValueError:
                pass  # Invalid message type, ignore filter
        
        if start_date:
            filtered = [msg for msg in filtered if msg.timestamp >= start_date]
        
        if end_date:
            filtered = [msg for msg in filtered if msg.timestamp <= end_date]
        
        # Sort by timestamp descending (most recent first)
        return sorted(filtered, key=lambda m: m.timestamp, reverse=True)
    
    def _message_to_response(self, message: Message) -> MessageResponse:
        """Convert Message to API response"""
        # Get sender name from user manager
        user = self.user_manager.get_user(message.sender_id)
        sender_name = user.short_name if user else None
        
        return MessageResponse(
            id=message.id,
            sender_id=message.sender_id,
            sender_name=sender_name,
            recipient_id=message.recipient_id,
            channel=message.channel,
            content=message.content,
            timestamp=message.timestamp,
            message_type=message.message_type.value,
            interface_id=message.interface_id,
            hop_count=message.hop_count,
            snr=message.snr,
            rssi=message.rssi
        )
    
    async def _send_direct_message(self, recipient_id: str, content: str, 
                                 interface_id: Optional[str] = None, sender: str = "") -> bool:
        """Send a direct message to a specific user"""
        try:
            # This would integrate with the actual message router
            # For now, just log the message
            self.logger.info(f"Sending direct message from {sender} to {recipient_id}: {content}")
            
            # In a real implementation, this would:
            # 1. Create a Message object with recipient_id set
            # 2. Send it through the core message router
            # 3. Return success/failure status
            
            # Add to message cache for demonstration
            message = Message(
                id=str(uuid.uuid4()),
                sender_id=f"admin_{sender}",
                recipient_id=recipient_id,
                channel=0,  # Direct messages typically use channel 0
                content=content,
                timestamp=datetime.now(timezone.utc),
                message_type=MessageType.TEXT,
                interface_id=interface_id or "web_admin"
            )
            
            self.messages_cache.append(message)
            
            # Limit cache size
            if len(self.messages_cache) > 1000:
                self.messages_cache.pop(0)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending direct message: {e}")
            return False
    
    async def _get_chat_stats(self) -> ChatStatsResponse:
        """Get chat statistics"""
        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            total_messages = len(self.messages_cache)
            messages_today = len([
                msg for msg in self.messages_cache
                if msg.timestamp >= today_start
            ])
            
            # Active channels
            active_channels = list(set(msg.channel for msg in self.messages_cache))
            
            # Top senders
            sender_counts = {}
            for msg in self.messages_cache:
                sender_counts[msg.sender_id] = sender_counts.get(msg.sender_id, 0) + 1
            
            top_senders = []
            for sender_id, count in sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                user = self.user_manager.get_user(sender_id)
                top_senders.append({
                    "sender_id": sender_id,
                    "sender_name": user.short_name if user else f"User-{sender_id[-4:]}",
                    "message_count": count
                })
            
            # Message types
            message_types = {}
            for msg in self.messages_cache:
                msg_type = msg.message_type.value
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
            
            # Hourly activity (last 24 hours)
            hourly_activity = []
            for hour in range(24):
                hour_start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                hour_end = hour_start + timedelta(hours=1)
                
                hour_messages = len([
                    msg for msg in self.messages_cache
                    if hour_start <= msg.timestamp < hour_end
                ])
                
                hourly_activity.append({
                    "hour": hour,
                    "message_count": hour_messages
                })
            
            return ChatStatsResponse(
                total_messages=total_messages,
                messages_today=messages_today,
                active_channels=sorted(active_channels),
                top_senders=top_senders,
                message_types=message_types,
                hourly_activity=hourly_activity
            )
            
        except Exception as e:
            self.logger.error(f"Error getting chat stats: {e}")
            return ChatStatsResponse(
                total_messages=0,
                messages_today=0,
                active_channels=[],
                top_senders=[],
                message_types={},
                hourly_activity=[]
            )
    
    async def _get_config_sections(self) -> List[str]:
        """Get all configuration sections"""
        try:
            # This would integrate with the actual configuration manager
            # For now, return mock sections
            return [
                "core",
                "plugins",
                "interfaces",
                "security",
                "logging",
                "database",
                "web_admin",
                "emergency",
                "bbs",
                "weather",
                "email"
            ]
        except Exception as e:
            self.logger.error(f"Error getting config sections: {e}")
            return []
    
    async def _get_config_section(self, section: str) -> Dict[str, Any]:
        """Get configuration for a specific section"""
        try:
            # This would integrate with the actual configuration manager
            # For now, return mock configuration based on section
            mock_configs = {
                "core": {
                    "node_id": {"value": "!12345678", "type": "string", "required": True},
                    "region": {"value": "US", "type": "string", "required": True},
                    "channel": {"value": 0, "type": "integer", "required": False}
                },
                "web_admin": {
                    "host": {"value": self.host, "type": "string", "required": True},
                    "port": {"value": self.port, "type": "integer", "required": True},
                    "debug": {"value": self.debug, "type": "boolean", "required": False}
                },
                "security": {
                    "secret_key": {"value": "***hidden***", "type": "string", "required": True},
                    "session_timeout": {"value": 3600, "type": "integer", "required": False}
                }
            }
            
            return mock_configs.get(section, {})
            
        except Exception as e:
            self.logger.error(f"Error getting config section {section}: {e}")
            return {}
    
    async def _get_config_value(self, section: str, key: str) -> Any:
        """Get a specific configuration value"""
        try:
            section_config = await self._get_config_section(section)
            if key in section_config:
                return section_config[key]["value"]
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting config value {section}.{key}: {e}")
            return None
    
    async def _update_config_value(self, section: str, key: str, value: Any, username: str) -> bool:
        """Update a configuration value"""
        try:
            # This would integrate with the actual configuration manager
            self.logger.info(f"Config update by {username}: {section}.{key} = {value}")
            
            # For web_admin section, update local values
            if section == "web_admin":
                if key == "host":
                    self.host = str(value)
                elif key == "port":
                    self.port = int(value)
                elif key == "debug":
                    self.debug = bool(value)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating config {section}.{key}: {e}")
            return False
    
    async def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration data"""
        try:
            errors = []
            warnings = []
            
            # Basic validation logic
            for section, section_data in config_data.items():
                if not isinstance(section_data, dict):
                    errors.append(f"Section '{section}' must be an object")
                    continue
                
                for key, value in section_data.items():
                    # Type validation examples
                    if section == "web_admin":
                        if key == "port" and not isinstance(value, int):
                            errors.append(f"web_admin.port must be an integer")
                        elif key == "port" and (value < 1 or value > 65535):
                            errors.append(f"web_admin.port must be between 1 and 65535")
                        elif key == "debug" and not isinstance(value, bool):
                            warnings.append(f"web_admin.debug should be a boolean")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            self.logger.error(f"Error validating config: {e}")
            return {
                "valid": False,
                "errors": [f"Validation error: {e}"],
                "warnings": []
            }
    
    async def _test_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test configuration without applying it"""
        try:
            # First validate the config
            validation = await self._validate_config(config_data)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": "Configuration validation failed",
                    "validation": validation
                }
            
            # Perform test-specific checks
            test_results = []
            
            # Test web_admin configuration
            if "web_admin" in config_data:
                web_config = config_data["web_admin"]
                if "port" in web_config:
                    port = web_config["port"]
                    # Test if port is available (mock test)
                    if port == self.port:
                        test_results.append({
                            "test": "port_availability",
                            "status": "pass",
                            "message": f"Port {port} is currently in use by this service"
                        })
                    else:
                        test_results.append({
                            "test": "port_availability",
                            "status": "warning",
                            "message": f"Port {port} availability not tested"
                        })
            
            return {
                "success": True,
                "message": "Configuration test completed",
                "validation": validation,
                "test_results": test_results
            }
            
        except Exception as e:
            self.logger.error(f"Error testing config: {e}")
            return {
                "success": False,
                "message": f"Configuration test failed: {e}",
                "validation": {"valid": False, "errors": [str(e)], "warnings": []},
                "test_results": []
            }
    
    async def _get_config_backups(self) -> List[Dict[str, Any]]:
        """Get list of configuration backups"""
        try:
            # This would integrate with actual backup storage
            # For now, return mock backups
            now = datetime.now(timezone.utc)
            
            return [
                {
                    "backup_id": "backup_001",
                    "timestamp": (now - timedelta(days=1)).isoformat(),
                    "description": "Daily automatic backup",
                    "size": 2048,
                    "sections": ["core", "plugins", "interfaces"]
                },
                {
                    "backup_id": "backup_002",
                    "timestamp": (now - timedelta(hours=6)).isoformat(),
                    "description": "Pre-update backup",
                    "size": 2156,
                    "sections": ["core", "plugins", "interfaces", "web_admin"]
                }
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting config backups: {e}")
            return []
    
    async def _create_config_backup(self, description: str, username: str) -> Optional[str]:
        """Create a configuration backup"""
        try:
            backup_id = f"backup_{int(datetime.now(timezone.utc).timestamp())}"
            
            # This would create an actual backup
            self.logger.info(f"Creating config backup {backup_id} by {username}: {description}")
            
            return backup_id
            
        except Exception as e:
            self.logger.error(f"Error creating config backup: {e}")
            return None
    
    async def _restore_config_backup(self, backup_id: str, username: str) -> bool:
        """Restore configuration from backup"""
        try:
            # This would restore from actual backup
            self.logger.info(f"Restoring config backup {backup_id} by {username}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring config backup {backup_id}: {e}")
            return False
    
    async def _delete_config_backup(self, backup_id: str) -> bool:
        """Delete a configuration backup"""
        try:
            # This would delete actual backup
            self.logger.info(f"Deleting config backup {backup_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting config backup {backup_id}: {e}")
            return False
    
    async def _get_services_status(self) -> List[ServiceStatusResponse]:
        """Get status of all services"""
        try:
            # Get service status from system monitor
            services = self.system_monitor.get_service_status()
            
            service_responses = []
            for service in services:
                service_responses.append(ServiceStatusResponse(
                    name=service.name,
                    status=service.status,
                    uptime=service.uptime,
                    last_restart=service.last_restart,
                    error_count=service.error_count,
                    last_error=service.last_error,
                    is_enabled=service.status != "disabled",
                    dependencies=[]  # Would be populated from actual service config
                ))
            
            return service_responses
            
        except Exception as e:
            self.logger.error(f"Error getting services status: {e}")
            return []
    
    async def _get_service_status(self, service_name: str) -> Optional[ServiceStatusResponse]:
        """Get status of a specific service"""
        try:
            services = await self._get_services_status()
            for service in services:
                if service.name == service_name:
                    return service
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting service status for {service_name}: {e}")
            return None
    
    async def _perform_service_action(self, service_name: str, action: str, username: str) -> bool:
        """Perform action on a service"""
        try:
            valid_actions = ["start", "stop", "restart", "enable", "disable"]
            if action not in valid_actions:
                self.logger.error(f"Invalid service action: {action}")
                return False
            
            # This would integrate with actual service management
            self.logger.info(f"Service action by {username}: {action} {service_name}")
            
            # For web_admin service, handle special cases
            if service_name == "web_admin":
                if action == "restart":
                    # Would trigger a restart of the web service
                    self.logger.info("Web admin service restart requested")
                elif action == "stop":
                    # Would stop the web service
                    self.logger.info("Web admin service stop requested")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error performing service action {action} on {service_name}: {e}")
            return False
    
    async def _get_service_logs(self, service_name: str, lines: int) -> List[Dict[str, Any]]:
        """Get service logs from actual log files"""
        try:
            import os
            import re
            
            # Determine log file path
            log_dir = "logs"
            if service_name == "system":
                log_file = os.path.join(log_dir, "zephyrgate_dev.log")
            else:
                # Try plugin-specific log file first, fall back to main log
                plugin_log = os.path.join(log_dir, f"{service_name}.log")
                if os.path.exists(plugin_log):
                    log_file = plugin_log
                else:
                    log_file = os.path.join(log_dir, "zephyrgate_dev.log")
            
            if not os.path.exists(log_file):
                return [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "WARNING",
                    "message": f"Log file not found: {log_file}"
                }]
            
            # Read last N lines from log file
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if lines > 0 else all_lines
            
            # Parse log lines into structured format
            # Expected format: YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - message
            log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([^ ]+) - (\w+) - (.+)$')
            
            parsed_logs = []
            for line in log_lines:
                line = line.strip()
                if not line:
                    continue
                    
                match = log_pattern.match(line)
                if match:
                    timestamp_str, logger_name, level, message = match.groups()
                    
                    # Filter by service name if not "system"
                    if service_name != "system" and service_name not in logger_name.lower():
                        continue
                    
                    # Parse timestamp
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except:
                        timestamp = datetime.now(timezone.utc)
                    
                    parsed_logs.append({
                        "timestamp": timestamp.isoformat(),
                        "level": level,
                        "message": message,
                        "logger": logger_name
                    })
                else:
                    # If line doesn't match pattern, treat as continuation of previous message
                    if parsed_logs:
                        parsed_logs[-1]["message"] += "\n" + line
                    else:
                        # Unparsed line, add as-is
                        parsed_logs.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "INFO",
                            "message": line,
                            "logger": "unknown"
                        })
            
            return parsed_logs if parsed_logs else [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "message": "No logs available"
            }]
            
        except Exception as e:
            self.logger.error(f"Error getting logs for {service_name}: {e}", exc_info=True)
            return [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "message": f"Error reading logs: {str(e)}"
            }]
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health check"""
        try:
            # Get system metrics
            current_metrics = self.system_monitor.get_current_metrics()
            
            # Get service status
            services = await self._get_services_status()
            
            # Calculate health scores
            cpu_health = "good" if current_metrics and current_metrics.cpu_percent < 80 else "warning"
            memory_health = "good" if current_metrics and current_metrics.memory_percent < 80 else "warning"
            disk_health = "good" if current_metrics and current_metrics.disk_percent < 90 else "warning"
            
            running_services = len([s for s in services if s.status == "running"])
            total_services = len(services)
            service_health = "good" if running_services == total_services else "warning"
            
            # Overall health
            health_scores = [cpu_health, memory_health, disk_health, service_health]
            if "critical" in health_scores:
                overall_health = "critical"
            elif "warning" in health_scores:
                overall_health = "warning"
            else:
                overall_health = "good"
            
            return {
                "overall_health": overall_health,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system": {
                    "cpu": {
                        "usage_percent": current_metrics.cpu_percent if current_metrics else 0,
                        "health": cpu_health
                    },
                    "memory": {
                        "usage_percent": current_metrics.memory_percent if current_metrics else 0,
                        "health": memory_health
                    },
                    "disk": {
                        "usage_percent": current_metrics.disk_percent if current_metrics else 0,
                        "health": disk_health
                    }
                },
                "services": {
                    "running": running_services,
                    "total": total_services,
                    "health": service_health
                },
                "network": {
                    "active_nodes": len(self.system_monitor.get_online_nodes()),
                    "total_nodes": len(self.system_monitor.get_all_nodes())
                },
                "alerts": {
                    "active": len(self.system_monitor.get_active_alerts()),
                    "total": len(self.system_monitor.get_all_alerts())
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {
                "overall_health": "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
    
    async def _get_plugins(self) -> List[Dict[str, Any]]:
        """Get list of all plugins with status and metadata"""
        try:
            from datetime import timezone
            from core.plugin_manager import PluginStatus
            import yaml
            from pathlib import Path
            
            plugins = []
            
            # Read enabled_plugins from config.yaml
            enabled_in_config = set()
            try:
                config_path = Path("config/config.yaml")
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        if config and 'plugins' in config and 'enabled_plugins' in config['plugins']:
                            enabled_in_config = set(config['plugins']['enabled_plugins'])
            except Exception as e:
                self.logger.error(f"Error reading enabled_plugins from config: {e}")
            
            # Get all plugins from plugin manager
            if hasattr(self.plugin_manager, 'plugins'):
                self.logger.info(f"Found {len(self.plugin_manager.plugins)} plugins in plugin_manager.plugins")
                
                for plugin_name, plugin_info in self.plugin_manager.plugins.items():
                    try:
                        # plugin_info is a PluginInfo object, not the plugin instance
                        metadata = plugin_info.metadata if hasattr(plugin_info, 'metadata') else None
                        plugin_instance = plugin_info.instance if hasattr(plugin_info, 'instance') else None
                        
                        if metadata:
                            self.logger.info(f"Plugin {plugin_name} metadata: v={metadata.version}, desc={metadata.description[:50] if metadata.description else 'empty'}")
                        else:
                            self.logger.warning(f"Plugin {plugin_name} has no metadata")
                        
                        # Get plugin status from PluginInfo
                        status = plugin_info.status if hasattr(plugin_info, 'status') else PluginStatus.UNLOADED
                        is_running = status == PluginStatus.RUNNING
                        self.logger.info(f"Plugin {plugin_name}: status={status}, is_running={is_running}")
                        
                        # Get uptime from PluginInfo
                        uptime = 0
                        if hasattr(plugin_info, 'start_time') and plugin_info.start_time:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = plugin_info.start_time
                                
                                # Make start_time timezone-aware if it isn't
                                if start_time.tzinfo is None:
                                    start_time = start_time.replace(tzinfo=timezone.utc)
                                
                                uptime = int((now - start_time).total_seconds())
                            except Exception as e:
                                self.logger.debug(f"Error calculating uptime for {plugin_name}: {e}")
                                uptime = 0
                        
                        # Get health status from PluginInfo
                        health_status = "healthy"
                        if hasattr(plugin_info, 'health') and plugin_info.health:
                            if not plugin_info.health.is_healthy:
                                health_status = "unhealthy"
                        
                        # Check if plugin is enabled in config
                        is_enabled = plugin_name in enabled_in_config
                        
                        plugin_data = {
                            "name": plugin_name,
                            "version": getattr(metadata, 'version', 'unknown') if metadata else "unknown",
                            "description": getattr(metadata, 'description', '') if metadata else "",
                            "author": getattr(metadata, 'author', '') if metadata else "",
                            "status": "running" if is_running else "stopped",
                            "health": health_status,
                            "uptime": uptime,
                            "enabled": is_enabled,
                            "dependencies": getattr(metadata, 'dependencies', []) if metadata else [],
                        }
                        
                        plugins.append(plugin_data)
                        
                    except Exception as e:
                        self.logger.error(f"Error getting info for plugin {plugin_name}: {e}", exc_info=True)
                        plugins.append({
                            "name": plugin_name,
                            "version": "unknown",
                            "description": "",
                            "author": "",
                            "status": "error",
                            "health": "unknown",
                            "uptime": 0,
                            "enabled": plugin_name in enabled_in_config,
                            "dependencies": [],
                            "error": str(e)
                        })
            
            return plugins
            
        except Exception as e:
            self.logger.error(f"Error getting plugins list: {e}", exc_info=True)
            return []
    
    async def _get_plugin_details(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific plugin"""
        try:
            if not hasattr(self.plugin_manager, 'plugins'):
                return None
            
            plugin_instance = self.plugin_manager.plugins.get(plugin_name)
            if not plugin_instance:
                return None
            
            metadata = plugin_instance.get_metadata() if hasattr(plugin_instance, 'get_metadata') else None
            
            # Get plugin status
            is_running = plugin_instance.is_running if hasattr(plugin_instance, 'is_running') else False
            
            # Get uptime
            uptime = 0
            start_time = None
            if hasattr(plugin_instance, 'start_time') and plugin_instance.start_time:
                start_time = plugin_instance.start_time.isoformat()
                uptime = int((datetime.now(timezone.utc) - plugin_instance.start_time).total_seconds())
            
            # Get health information
            health_info = {}
            if hasattr(self.plugin_manager, 'health_monitor'):
                health_data = self.plugin_manager.health_monitor.get_plugin_health(plugin_name)
                if health_data:
                    health_info = {
                        "status": health_data.get('status', 'unknown'),
                        "failure_count": health_data.get('failure_count', 0),
                        "last_failure": health_data.get('last_failure'),
                        "restart_count": health_data.get('restart_count', 0),
                        "last_restart": health_data.get('last_restart'),
                    }
            
            # Get configuration
            config = {}
            if hasattr(plugin_instance, 'config'):
                config = plugin_instance.config
            
            # Get manifest information
            manifest_info = {}
            if hasattr(self.plugin_manager, 'manifests') and plugin_name in self.plugin_manager.manifests:
                manifest = self.plugin_manager.manifests[plugin_name]
                manifest_info = {
                    "commands": [{"name": cmd.name, "description": cmd.description, "usage": cmd.usage} 
                                for cmd in manifest.commands] if hasattr(manifest, 'commands') else [],
                    "scheduled_tasks": [{"name": task.name, "interval": task.interval} 
                                       for task in manifest.scheduled_tasks] if hasattr(manifest, 'scheduled_tasks') else [],
                    "menu_items": [{"menu": item.menu, "label": item.label, "command": item.command} 
                                  for item in manifest.menu_items] if hasattr(manifest, 'menu_items') else [],
                    "permissions": manifest.permissions if hasattr(manifest, 'permissions') else [],
                }
            
            return {
                "name": plugin_name,
                "version": metadata.version if metadata else "unknown",
                "description": metadata.description if metadata else "",
                "author": metadata.author if metadata else "",
                "status": "running" if is_running else "stopped",
                "enabled": metadata.enabled if metadata else True,
                "uptime": uptime,
                "start_time": start_time,
                "dependencies": metadata.dependencies if metadata else [],
                "health": health_info,
                "config": config,
                "manifest": manifest_info,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting details for plugin {plugin_name}: {e}")
            return None
    
    async def _enable_plugin(self, plugin_name: str, username: str, ip_address: str, user_agent: str) -> bool:
        """Enable a plugin"""
        try:
            if hasattr(self.plugin_manager, 'enable_plugin'):
                success = await self.plugin_manager.enable_plugin(plugin_name)
                
                # Log audit event
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SYSTEM_ACCESS,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="plugin_management",
                    action="plugin_enabled",
                    details={"plugin": plugin_name},
                    security_level=SecurityLevel.HIGH,
                    success=success
                )
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error enabling plugin {plugin_name}: {e}")
            return False
    
    async def _disable_plugin(self, plugin_name: str, username: str, ip_address: str, user_agent: str) -> bool:
        """Disable a plugin"""
        try:
            if hasattr(self.plugin_manager, 'disable_plugin'):
                success = await self.plugin_manager.disable_plugin(plugin_name)
                
                # Log audit event
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SYSTEM_ACCESS,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="plugin_management",
                    action="plugin_disabled",
                    details={"plugin": plugin_name},
                    security_level=SecurityLevel.HIGH,
                    success=success
                )
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error disabling plugin {plugin_name}: {e}")
            return False
    
    async def _restart_plugin(self, plugin_name: str, username: str, ip_address: str, user_agent: str) -> bool:
        """Restart a plugin"""
        try:
            # Disable then enable
            if hasattr(self.plugin_manager, 'disable_plugin') and hasattr(self.plugin_manager, 'enable_plugin'):
                await self.plugin_manager.disable_plugin(plugin_name)
                await asyncio.sleep(1)  # Brief pause
                success = await self.plugin_manager.enable_plugin(plugin_name)
                
                # Log audit event
                self.security_manager.log_audit_event(
                    event_type=AuditEventType.SYSTEM_ACCESS,
                    user_id=username,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="plugin_management",
                    action="plugin_restarted",
                    details={"plugin": plugin_name},
                    security_level=SecurityLevel.HIGH,
                    success=success
                )
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error restarting plugin {plugin_name}: {e}")
            return False
    
    async def _toggle_plugin_enabled(self, plugin_name: str, enabled: bool, username: str, ip_address: str, user_agent: str) -> bool:
        """Enable or disable a plugin at startup by updating config.yaml"""
        try:
            import yaml
            from pathlib import Path
            
            # Read current config.yaml
            config_path = Path("config/config.yaml")
            if not config_path.exists():
                self.logger.error("config.yaml not found")
                return False
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Get current enabled_plugins list
            if 'plugins' not in config:
                config['plugins'] = {}
            if 'enabled_plugins' not in config['plugins']:
                config['plugins']['enabled_plugins'] = []
            
            enabled_plugins = config['plugins']['enabled_plugins']
            
            # Update the list
            if enabled:
                # Add if not already in list
                if plugin_name not in enabled_plugins:
                    enabled_plugins.append(plugin_name)
            else:
                # Remove if in list
                if plugin_name in enabled_plugins:
                    enabled_plugins.remove(plugin_name)
            
            # Write back to config.yaml
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            # Also update plugin manager's internal state
            if hasattr(self.plugin_manager, '_enabled_plugins') and hasattr(self.plugin_manager, '_disabled_plugins'):
                if enabled:
                    self.plugin_manager._enabled_plugins.add(plugin_name)
                    self.plugin_manager._disabled_plugins.discard(plugin_name)
                else:
                    self.plugin_manager._disabled_plugins.add(plugin_name)
                    self.plugin_manager._enabled_plugins.discard(plugin_name)
                
                # Save plugin state
                if hasattr(self.plugin_manager, '_save_plugin_state'):
                    self.plugin_manager._save_plugin_state()
            
            # Log audit event
            action = "plugin_enabled" if enabled else "plugin_disabled"
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="plugin_management",
                action=action,
                details={"plugin": plugin_name, "enabled": enabled},
                security_level=SecurityLevel.HIGH,
                success=True
            )
            
            self.logger.info(f"Plugin {plugin_name} {'enabled' if enabled else 'disabled'} at startup by {username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error toggling plugin {plugin_name} enabled state: {e}", exc_info=True)
            return False
    
    async def _get_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get plugin configuration"""
        try:
            if not hasattr(self.plugin_manager, 'plugins'):
                return None
            
            plugin_instance = self.plugin_manager.plugins.get(plugin_name)
            if not plugin_instance:
                return None
            
            config = {}
            if hasattr(plugin_instance, 'config'):
                config = plugin_instance.config
            
            # Get config schema if available
            schema = {}
            if hasattr(plugin_instance, 'get_config_schema'):
                schema = plugin_instance.get_config_schema()
            
            return {
                "plugin": plugin_name,
                "config": config,
                "schema": schema
            }
            
        except Exception as e:
            self.logger.error(f"Error getting config for plugin {plugin_name}: {e}")
            return None
    
    async def _update_plugin_config(self, plugin_name: str, config_data: Dict[str, Any], 
                                   username: str, ip_address: str, user_agent: str) -> bool:
        """Update plugin configuration"""
        try:
            if not hasattr(self.plugin_manager, 'plugins'):
                return False
            
            plugin_instance = self.plugin_manager.plugins.get(plugin_name)
            if not plugin_instance:
                return False
            
            # Update config
            if hasattr(plugin_instance, 'config'):
                plugin_instance.config.update(config_data)
            
            # Notify plugin of config change
            if hasattr(plugin_instance, 'on_config_changed'):
                await plugin_instance.on_config_changed(config_data)
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="plugin_management",
                action="plugin_config_updated",
                details={"plugin": plugin_name, "config_keys": list(config_data.keys())},
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating config for plugin {plugin_name}: {e}")
            return False
    
    async def _get_plugin_logs(self, plugin_name: str, lines: int, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get plugin logs"""
        try:
            # This would integrate with the logging system to filter logs by plugin name
            # For now, return mock logs
            log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            if level:
                log_levels = [level.upper()]
            
            mock_logs = []
            for i in range(min(lines, 20)):
                log_level = log_levels[i % len(log_levels)]
                timestamp = datetime.now(timezone.utc) - timedelta(minutes=i*5)
                
                mock_logs.append({
                    "timestamp": timestamp.isoformat(),
                    "level": log_level,
                    "message": f"[{plugin_name}] Sample log message {i}",
                    "plugin": plugin_name
                })
            
            return mock_logs
            
        except Exception as e:
            self.logger.error(f"Error getting logs for plugin {plugin_name}: {e}")
            return []
    
    async def _get_plugin_metrics(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get plugin metrics and health information"""
        try:
            if not hasattr(self.plugin_manager, 'plugins'):
                return None
            
            plugin_instance = self.plugin_manager.plugins.get(plugin_name)
            if not plugin_instance:
                return None
            
            # Get health information
            health_info = {}
            if hasattr(self.plugin_manager, 'health_monitor'):
                health_data = self.plugin_manager.health_monitor.get_plugin_health(plugin_name)
                if health_data:
                    health_info = health_data
            
            # Get uptime
            uptime = 0
            if hasattr(plugin_instance, 'start_time') and plugin_instance.start_time:
                uptime = int((datetime.now(timezone.utc) - plugin_instance.start_time).total_seconds())
            
            # Get task count if available
            task_count = 0
            if hasattr(plugin_instance, 'tasks'):
                task_count = len(plugin_instance.tasks)
            
            return {
                "plugin": plugin_name,
                "status": "running" if plugin_instance.is_running else "stopped",
                "uptime": uptime,
                "health": health_info,
                "metrics": {
                    "task_count": task_count,
                    "failure_count": health_info.get('failure_count', 0),
                    "restart_count": health_info.get('restart_count', 0),
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting metrics for plugin {plugin_name}: {e}")
            return None
    
    async def _get_plugin_errors(self, plugin_name: str, limit: int) -> List[Dict[str, Any]]:
        """Get recent plugin errors"""
        try:
            errors = []
            
            # Get errors from health monitor
            if hasattr(self.plugin_manager, 'health_monitor'):
                health_data = self.plugin_manager.health_monitor.get_plugin_health(plugin_name)
                if health_data and 'errors' in health_data:
                    for error in health_data['errors'][-limit:]:
                        errors.append({
                            "timestamp": error.get('timestamp', datetime.now(timezone.utc).isoformat()),
                            "error_type": error.get('type', 'Unknown'),
                            "message": error.get('message', ''),
                            "traceback": error.get('traceback', '')
                        })
            
            # If no errors from health monitor, return mock data
            if not errors:
                errors = [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "NoErrors",
                    "message": "No recent errors recorded",
                    "traceback": ""
                }]
            
            return errors
            
        except Exception as e:
            self.logger.error(f"Error getting errors for plugin {plugin_name}: {e}")
            return []
    
    async def _install_plugin(self, source: str, username: str, ip_address: str, user_agent: str) -> Dict[str, Any]:
        """Install a new plugin from a path or URL"""
        try:
            # This would implement plugin installation logic
            # For now, return a mock response
            self.logger.info(f"Plugin installation requested by {username} from source: {source}")
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="plugin_management",
                action="plugin_install_attempted",
                details={"source": source},
                security_level=SecurityLevel.HIGH,
                success=False
            )
            
            return {
                "success": False,
                "message": "Plugin installation not yet implemented",
                "source": source
            }
            
        except Exception as e:
            self.logger.error(f"Error installing plugin from {source}: {e}")
            return {
                "success": False,
                "message": f"Installation failed: {str(e)}",
                "source": source
            }
    
    async def _uninstall_plugin(self, plugin_name: str, username: str, ip_address: str, user_agent: str) -> bool:
        """Uninstall a plugin"""
        try:
            # This would implement plugin uninstallation logic
            # For now, just log the attempt
            self.logger.info(f"Plugin uninstallation requested by {username} for: {plugin_name}")
            
            # Log audit event
            self.security_manager.log_audit_event(
                event_type=AuditEventType.SYSTEM_ACCESS,
                user_id=username,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="plugin_management",
                action="plugin_uninstall_attempted",
                details={"plugin": plugin_name},
                security_level=SecurityLevel.HIGH,
                success=False
            )
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error uninstalling plugin {plugin_name}: {e}")
            return False
    
    async def _get_available_plugins(self) -> Dict[str, Any]:
        """Get list of available plugins that can be installed"""
        try:
            # This would query a plugin repository or scan plugin directories
            # For now, return mock data
            available_plugins = [
                {
                    "name": "example_plugin",
                    "version": "1.0.0",
                    "description": "An example third-party plugin",
                    "author": "Community Developer",
                    "installed": False,
                    "source": "/path/to/example_plugin"
                }
            ]
            
            return {
                "available_plugins": available_plugins,
                "total": len(available_plugins)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting available plugins: {e}")
            return {
                "available_plugins": [],
                "total": 0
            }
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "default": "0.0.0.0",
                    "description": "Host to bind web server to"
                },
                "port": {
                    "type": "integer",
                    "default": 8080,
                    "description": "Port to bind web server to"
                },
                "secret_key": {
                    "type": "string",
                    "description": "Secret key for JWT tokens"
                },
                "debug": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable debug mode"
                }
            },
            "required": ["secret_key"]
        }
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "host": "0.0.0.0",
            "port": 8080,
            "debug": False
        }