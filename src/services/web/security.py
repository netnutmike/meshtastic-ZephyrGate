"""
Security and Access Control Module for Web Administration

Provides enhanced security features, audit logging, and access control.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import secrets
import ipaddress

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    CONFIG_CHANGE = "config_change"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PERMISSION_CHANGE = "permission_change"
    SERVICE_ACTION = "service_action"
    BROADCAST_SENT = "broadcast_sent"
    SYSTEM_ACCESS = "system_access"
    SECURITY_VIOLATION = "security_violation"
    PASSWORD_CHANGE = "password_change"
    SESSION_EXPIRED = "session_expired"


class SecurityLevel(Enum):
    """Security levels for different operations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditLogEntry:
    """Audit log entry"""
    id: str
    timestamp: datetime
    event_type: AuditEventType
    user_id: str
    user_name: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: str
    action: str
    details: Dict[str, Any]
    security_level: SecurityLevel
    success: bool
    error_message: Optional[str] = None


@dataclass
class SecurityPolicy:
    """Security policy configuration"""
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes
    session_timeout: int = 3600  # 1 hour
    password_min_length: int = 8
    password_require_special: bool = True
    password_require_numbers: bool = True
    password_require_uppercase: bool = True
    allowed_ip_ranges: List[str] = field(default_factory=list)
    blocked_ip_addresses: Set[str] = field(default_factory=set)
    require_2fa: bool = False
    max_concurrent_sessions: int = 5
    audit_retention_days: int = 90


@dataclass
class SessionInfo:
    """Session information"""
    session_id: str
    user_id: str
    user_name: str
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool = True
    permissions: Set[str] = field(default_factory=set)


@dataclass
class LoginAttempt:
    """Login attempt tracking"""
    ip_address: str
    user_id: str
    timestamp: datetime
    success: bool
    user_agent: Optional[str] = None


class SecurityManager:
    """
    Security manager for handling authentication, authorization,
    audit logging, and security policies.
    """
    
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.logger = logger
        
        # Storage
        self.audit_log: List[AuditLogEntry] = []
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.login_attempts: List[LoginAttempt] = []
        self.blocked_users: Dict[str, datetime] = {}
        
        # Security tracking
        self.failed_login_counts: Dict[str, int] = {}
        self.suspicious_activities: List[Dict[str, Any]] = []
        
        self.logger.info("SecurityManager initialized")
    
    def generate_session_id(self) -> str:
        """Generate a secure session ID"""
        return secrets.token_urlsafe(32)
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 for password hashing
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        return password_hash.hex(), salt
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash"""
        try:
            computed_hash, _ = self.hash_password(password, salt)
            return secrets.compare_digest(computed_hash, password_hash)
        except Exception as e:
            self.logger.error(f"Error verifying password: {e}")
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validate password strength against policy"""
        issues = []
        score = 0
        
        if len(password) < self.policy.password_min_length:
            issues.append(f"Password must be at least {self.policy.password_min_length} characters long")
        else:
            score += 1
        
        if self.policy.password_require_uppercase and not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        else:
            score += 1
        
        if self.policy.password_require_numbers and not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one number")
        else:
            score += 1
        
        if self.policy.password_require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password must contain at least one special character")
        else:
            score += 1
        
        # Additional strength checks
        if len(set(password)) < len(password) * 0.6:
            issues.append("Password has too many repeated characters")
        else:
            score += 1
        
        strength = "weak"
        if score >= 4:
            strength = "strong"
        elif score >= 2:
            strength = "medium"
        
        return {
            "valid": len(issues) == 0,
            "strength": strength,
            "score": score,
            "issues": issues
        }
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed"""
        try:
            # Check if IP is blocked
            if ip_address in self.policy.blocked_ip_addresses:
                return False
            
            # If no allowed ranges specified, allow all
            if not self.policy.allowed_ip_ranges:
                return True
            
            # Check against allowed ranges
            ip = ipaddress.ip_address(ip_address)
            for range_str in self.policy.allowed_ip_ranges:
                try:
                    network = ipaddress.ip_network(range_str, strict=False)
                    if ip in network:
                        return True
                except ValueError:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking IP allowlist for {ip_address}: {e}")
            return True  # Default to allow on error
    
    def is_user_locked_out(self, user_id: str) -> bool:
        """Check if user is locked out due to failed login attempts"""
        if user_id in self.blocked_users:
            lockout_time = self.blocked_users[user_id]
            if datetime.now(timezone.utc) < lockout_time:
                return True
            else:
                # Lockout expired, remove from blocked list
                del self.blocked_users[user_id]
                self.failed_login_counts.pop(user_id, None)
        
        return False
    
    def record_login_attempt(self, user_id: str, ip_address: str, success: bool, 
                           user_agent: Optional[str] = None) -> bool:
        """Record login attempt and handle lockout logic"""
        attempt = LoginAttempt(
            ip_address=ip_address,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            success=success,
            user_agent=user_agent
        )
        
        self.login_attempts.append(attempt)
        
        # Limit login attempts history
        if len(self.login_attempts) > 1000:
            self.login_attempts = self.login_attempts[-500:]
        
        if not success:
            # Increment failed login count
            self.failed_login_counts[user_id] = self.failed_login_counts.get(user_id, 0) + 1
            
            # Check if user should be locked out
            if self.failed_login_counts[user_id] >= self.policy.max_login_attempts:
                lockout_until = datetime.now(timezone.utc) + timedelta(seconds=self.policy.lockout_duration)
                self.blocked_users[user_id] = lockout_until
                
                self.log_audit_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    user_id=user_id,
                    user_name=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource="authentication",
                    action="user_locked_out",
                    details={"reason": "too_many_failed_attempts", "attempts": self.failed_login_counts[user_id]},
                    security_level=SecurityLevel.HIGH,
                    success=False
                )
                
                return False
        else:
            # Reset failed login count on successful login
            self.failed_login_counts.pop(user_id, None)
        
        return True
    
    def create_session(self, user_id: str, user_name: str, ip_address: str, 
                      user_agent: str, permissions: Set[str]) -> Optional[SessionInfo]:
        """Create a new user session"""
        try:
            # Check concurrent session limit
            user_sessions = [s for s in self.active_sessions.values() 
                           if s.user_id == user_id and s.is_active]
            
            if len(user_sessions) >= self.policy.max_concurrent_sessions:
                # Remove oldest session
                oldest_session = min(user_sessions, key=lambda s: s.last_activity)
                self.invalidate_session(oldest_session.session_id)
            
            session_id = self.generate_session_id()
            now = datetime.now(timezone.utc)
            
            session = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=now,
                last_activity=now,
                expires_at=now + timedelta(seconds=self.policy.session_timeout),
                permissions=permissions
            )
            
            self.active_sessions[session_id] = session
            
            self.log_audit_event(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                user_agent=user_agent,
                resource="authentication",
                action="session_created",
                details={"session_id": session_id},
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
            
            return session
            
        except Exception as e:
            self.logger.error(f"Error creating session for {user_id}: {e}")
            return None
    
    def validate_session(self, session_id: str, ip_address: str) -> Optional[SessionInfo]:
        """Validate and update session"""
        try:
            session = self.active_sessions.get(session_id)
            if not session or not session.is_active:
                return None
            
            now = datetime.now(timezone.utc)
            
            # Check if session expired
            if now > session.expires_at:
                self.invalidate_session(session_id)
                
                self.log_audit_event(
                    event_type=AuditEventType.SESSION_EXPIRED,
                    user_id=session.user_id,
                    user_name=session.user_name,
                    ip_address=ip_address,
                    user_agent=session.user_agent,
                    resource="authentication",
                    action="session_expired",
                    details={"session_id": session_id},
                    security_level=SecurityLevel.LOW,
                    success=False
                )
                
                return None
            
            # Check IP address consistency (optional security check)
            if session.ip_address != ip_address:
                self.log_audit_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    user_id=session.user_id,
                    user_name=session.user_name,
                    ip_address=ip_address,
                    user_agent=session.user_agent,
                    resource="authentication",
                    action="ip_address_mismatch",
                    details={
                        "session_id": session_id,
                        "original_ip": session.ip_address,
                        "current_ip": ip_address
                    },
                    security_level=SecurityLevel.HIGH,
                    success=False
                )
                
                # Optionally invalidate session on IP mismatch
                # self.invalidate_session(session_id)
                # return None
            
            # Update session activity
            session.last_activity = now
            session.expires_at = now + timedelta(seconds=self.policy.session_timeout)
            
            return session
            
        except Exception as e:
            self.logger.error(f"Error validating session {session_id}: {e}")
            return None
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session"""
        try:
            session = self.active_sessions.get(session_id)
            if session and session.is_active:
                session.is_active = False
                
                self.log_audit_event(
                    event_type=AuditEventType.LOGOUT,
                    user_id=session.user_id,
                    user_name=session.user_name,
                    ip_address=session.ip_address,
                    user_agent=session.user_agent,
                    resource="authentication",
                    action="session_invalidated",
                    details={"session_id": session_id},
                    security_level=SecurityLevel.LOW,
                    success=True
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error invalidating session {session_id}: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            now = datetime.now(timezone.utc)
            expired_sessions = []
            
            for session_id, session in self.active_sessions.items():
                if not session.is_active or now > session.expires_at:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.active_sessions[session_id]
            
            if expired_sessions:
                self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired sessions: {e}")
    
    def log_audit_event(self, event_type: AuditEventType, user_id: str, user_name: str,
                       ip_address: Optional[str], user_agent: Optional[str],
                       resource: str, action: str, details: Dict[str, Any],
                       security_level: SecurityLevel, success: bool,
                       error_message: Optional[str] = None):
        """Log an audit event"""
        try:
            entry = AuditLogEntry(
                id=secrets.token_hex(16),
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=resource,
                action=action,
                details=details,
                security_level=security_level,
                success=success,
                error_message=error_message
            )
            
            self.audit_log.append(entry)
            
            # Limit audit log size
            if len(self.audit_log) > 10000:
                self.audit_log = self.audit_log[-5000:]
            
            # Log high-security events immediately
            if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                self.logger.warning(
                    f"Security event: {event_type.value} by {user_name} ({user_id}) "
                    f"from {ip_address} - {action} on {resource}"
                )
            
        except Exception as e:
            self.logger.error(f"Error logging audit event: {e}")
    
    def get_audit_log(self, limit: int = 100, event_type: Optional[AuditEventType] = None,
                     user_id: Optional[str] = None, start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> List[AuditLogEntry]:
        """Get audit log entries with filtering"""
        try:
            filtered_log = self.audit_log.copy()
            
            if event_type:
                filtered_log = [entry for entry in filtered_log if entry.event_type == event_type]
            
            if user_id:
                filtered_log = [entry for entry in filtered_log if entry.user_id == user_id]
            
            if start_date:
                filtered_log = [entry for entry in filtered_log if entry.timestamp >= start_date]
            
            if end_date:
                filtered_log = [entry for entry in filtered_log if entry.timestamp <= end_date]
            
            # Sort by timestamp descending (most recent first)
            filtered_log.sort(key=lambda e: e.timestamp, reverse=True)
            
            return filtered_log[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting audit log: {e}")
            return []
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security summary and statistics"""
        try:
            now = datetime.now(timezone.utc)
            last_24h = now - timedelta(hours=24)
            
            # Recent audit events
            recent_events = [e for e in self.audit_log if e.timestamp >= last_24h]
            
            # Login statistics
            recent_logins = [e for e in recent_events if e.event_type == AuditEventType.LOGIN_SUCCESS]
            failed_logins = [e for e in recent_events if e.event_type == AuditEventType.LOGIN_FAILURE]
            
            # Also count failed login attempts from login_attempts list
            recent_failed_attempts = [
                a for a in self.login_attempts 
                if a.timestamp >= last_24h and not a.success
            ]
            
            # Security violations
            security_violations = [
                e for e in recent_events 
                if e.event_type == AuditEventType.SECURITY_VIOLATION
            ]
            
            # Active sessions
            active_sessions = [s for s in self.active_sessions.values() if s.is_active]
            
            return {
                "timestamp": now.isoformat(),
                "active_sessions": len(active_sessions),
                "blocked_users": len(self.blocked_users),
                "recent_activity": {
                    "successful_logins": len(recent_logins),
                    "failed_logins": max(len(failed_logins), len(recent_failed_attempts)),
                    "security_violations": len(security_violations),
                    "total_events": len(recent_events)
                },
                "security_policy": {
                    "max_login_attempts": self.policy.max_login_attempts,
                    "session_timeout": self.policy.session_timeout,
                    "lockout_duration": self.policy.lockout_duration,
                    "require_2fa": self.policy.require_2fa
                },
                "top_users": [
                    {"user_id": s.user_id, "user_name": s.user_name, "last_activity": s.last_activity.isoformat()}
                    for s in sorted(active_sessions, key=lambda s: s.last_activity, reverse=True)[:5]
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting security summary: {e}")
            return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
    
    def cleanup_old_audit_logs(self):
        """Clean up old audit log entries"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.policy.audit_retention_days)
            
            original_count = len(self.audit_log)
            self.audit_log = [entry for entry in self.audit_log if entry.timestamp >= cutoff_date]
            
            removed_count = original_count - len(self.audit_log)
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} old audit log entries")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old audit logs: {e}")
    
    def export_audit_log(self, format: str = "json") -> str:
        """Export audit log in specified format"""
        try:
            if format.lower() == "json":
                export_data = []
                for entry in self.audit_log:
                    export_data.append({
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
                    })
                
                return json.dumps(export_data, indent=2)
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
        except Exception as e:
            self.logger.error(f"Error exporting audit log: {e}")
            return f'{{"error": "{str(e)}"}}'