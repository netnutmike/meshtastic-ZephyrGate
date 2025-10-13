"""
Unit tests for Security Manager
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from src.services.web.security import (
    SecurityManager, SecurityPolicy, AuditEventType, SecurityLevel,
    AuditLogEntry, SessionInfo, LoginAttempt
)


class TestSecurityManager:
    """Test security manager functionality"""
    
    @pytest.fixture
    def security_policy(self):
        return SecurityPolicy(
            max_login_attempts=3,
            lockout_duration=300,  # 5 minutes
            session_timeout=1800,  # 30 minutes
            password_min_length=8,
            allowed_ip_ranges=["192.168.1.0/24", "10.0.0.0/8"],
            audit_retention_days=30
        )
    
    @pytest.fixture
    def security_manager(self, security_policy):
        return SecurityManager(security_policy)
    
    def test_init(self, security_manager):
        """Test security manager initialization"""
        assert security_manager.policy is not None
        assert security_manager.audit_log == []
        assert security_manager.active_sessions == {}
        assert security_manager.login_attempts == []
        assert security_manager.blocked_users == {}
    
    def test_generate_session_id(self, security_manager):
        """Test session ID generation"""
        session_id1 = security_manager.generate_session_id()
        session_id2 = security_manager.generate_session_id()
        
        assert isinstance(session_id1, str)
        assert isinstance(session_id2, str)
        assert len(session_id1) > 20  # Should be reasonably long
        assert session_id1 != session_id2  # Should be unique
    
    def test_hash_verify_password(self, security_manager):
        """Test password hashing and verification"""
        password = "test_password_123"
        
        # Hash password
        password_hash, salt = security_manager.hash_password(password)
        
        assert isinstance(password_hash, str)
        assert isinstance(salt, str)
        assert len(password_hash) > 0
        assert len(salt) > 0
        
        # Verify correct password
        assert security_manager.verify_password(password, password_hash, salt) is True
        
        # Verify incorrect password
        assert security_manager.verify_password("wrong_password", password_hash, salt) is False
    
    def test_validate_password_strength(self, security_manager):
        """Test password strength validation"""
        # Strong password
        result = security_manager.validate_password_strength("StrongPass123!")
        assert result["valid"] is True
        assert result["strength"] in ["strong", "medium"]
        assert len(result["issues"]) == 0
        
        # Weak password
        result = security_manager.validate_password_strength("weak")
        assert result["valid"] is False
        assert result["strength"] == "weak"
        assert len(result["issues"]) > 0
        
        # Password missing uppercase
        result = security_manager.validate_password_strength("lowercase123!")
        assert "uppercase" in str(result["issues"]).lower()
        
        # Password missing numbers
        result = security_manager.validate_password_strength("NoNumbers!")
        assert "number" in str(result["issues"]).lower()
        
        # Password missing special characters
        result = security_manager.validate_password_strength("NoSpecial123")
        assert "special" in str(result["issues"]).lower()
    
    def test_is_ip_allowed(self, security_manager):
        """Test IP address allowlist checking"""
        # IP in allowed range
        assert security_manager.is_ip_allowed("192.168.1.100") is True
        assert security_manager.is_ip_allowed("10.0.0.1") is True
        
        # IP not in allowed range
        assert security_manager.is_ip_allowed("172.16.0.1") is False
        assert security_manager.is_ip_allowed("8.8.8.8") is False
        
        # Blocked IP
        security_manager.policy.blocked_ip_addresses.add("192.168.1.100")
        assert security_manager.is_ip_allowed("192.168.1.100") is False
    
    def test_record_login_attempt_success(self, security_manager):
        """Test recording successful login attempt"""
        user_id = "test_user"
        ip_address = "192.168.1.100"
        
        result = security_manager.record_login_attempt(user_id, ip_address, True)
        
        assert result is True
        assert len(security_manager.login_attempts) == 1
        assert security_manager.login_attempts[0].success is True
        assert user_id not in security_manager.failed_login_counts
        assert user_id not in security_manager.blocked_users
    
    def test_record_login_attempt_failure(self, security_manager):
        """Test recording failed login attempts and lockout"""
        user_id = "test_user"
        ip_address = "192.168.1.100"
        
        # First two failed attempts
        for i in range(2):
            result = security_manager.record_login_attempt(user_id, ip_address, False)
            assert result is True
            assert security_manager.failed_login_counts[user_id] == i + 1
            assert user_id not in security_manager.blocked_users
        
        # Third failed attempt should trigger lockout
        result = security_manager.record_login_attempt(user_id, ip_address, False)
        assert result is False
        assert security_manager.failed_login_counts[user_id] == 3
        assert user_id in security_manager.blocked_users
        
        # User should be locked out
        assert security_manager.is_user_locked_out(user_id) is True
    
    def test_lockout_expiration(self, security_manager):
        """Test that lockout expires after the configured duration"""
        user_id = "test_user"
        ip_address = "192.168.1.100"
        
        # Trigger lockout
        for i in range(3):
            security_manager.record_login_attempt(user_id, ip_address, False)
        
        assert security_manager.is_user_locked_out(user_id) is True
        
        # Manually expire the lockout
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        security_manager.blocked_users[user_id] = past_time
        
        # Should no longer be locked out
        assert security_manager.is_user_locked_out(user_id) is False
        assert user_id not in security_manager.blocked_users
        assert user_id not in security_manager.failed_login_counts
    
    def test_create_session(self, security_manager):
        """Test session creation"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read", "write"}
        
        session = security_manager.create_session(
            user_id, user_name, ip_address, user_agent, permissions
        )
        
        assert session is not None
        assert session.user_id == user_id
        assert session.user_name == user_name
        assert session.ip_address == ip_address
        assert session.user_agent == user_agent
        assert session.permissions == permissions
        assert session.is_active is True
        assert session.session_id in security_manager.active_sessions
    
    def test_validate_session(self, security_manager):
        """Test session validation"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read"}
        
        # Create session
        session = security_manager.create_session(
            user_id, user_name, ip_address, user_agent, permissions
        )
        
        # Validate session
        validated_session = security_manager.validate_session(session.session_id, ip_address)
        assert validated_session is not None
        assert validated_session.session_id == session.session_id
        
        # Validate with wrong IP (should still work but log security event)
        validated_session = security_manager.validate_session(session.session_id, "192.168.1.200")
        assert validated_session is not None  # Still valid but logged
        
        # Validate non-existent session
        validated_session = security_manager.validate_session("invalid_session", ip_address)
        assert validated_session is None
    
    def test_session_expiration(self, security_manager):
        """Test session expiration"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read"}
        
        # Create session
        session = security_manager.create_session(
            user_id, user_name, ip_address, user_agent, permissions
        )
        
        # Manually expire the session
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Should be invalid now
        validated_session = security_manager.validate_session(session.session_id, ip_address)
        assert validated_session is None
        assert not session.is_active
    
    def test_invalidate_session(self, security_manager):
        """Test session invalidation"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read"}
        
        # Create session
        session = security_manager.create_session(
            user_id, user_name, ip_address, user_agent, permissions
        )
        
        assert session.is_active is True
        
        # Invalidate session
        result = security_manager.invalidate_session(session.session_id)
        assert result is True
        assert session.is_active is False
        
        # Try to invalidate again
        result = security_manager.invalidate_session(session.session_id)
        assert result is False  # Already invalidated
    
    def test_concurrent_session_limit(self, security_manager):
        """Test concurrent session limit enforcement"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read"}
        
        # Set low concurrent session limit
        security_manager.policy.max_concurrent_sessions = 2
        
        # Create sessions up to limit
        sessions = []
        for i in range(2):
            session = security_manager.create_session(
                user_id, user_name, f"{ip_address}{i}", user_agent, permissions
            )
            sessions.append(session)
            assert session is not None
        
        # Create one more session (should remove oldest)
        new_session = security_manager.create_session(
            user_id, user_name, "192.168.1.200", user_agent, permissions
        )
        
        assert new_session is not None
        
        # Check that oldest session was invalidated
        active_sessions = [s for s in security_manager.active_sessions.values() 
                          if s.user_id == user_id and s.is_active]
        assert len(active_sessions) == 2
    
    def test_log_audit_event(self, security_manager):
        """Test audit event logging"""
        security_manager.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="test_user",
            user_name="Test User",
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            resource="authentication",
            action="login",
            details={"method": "password"},
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        assert len(security_manager.audit_log) == 1
        entry = security_manager.audit_log[0]
        
        assert entry.event_type == AuditEventType.LOGIN_SUCCESS
        assert entry.user_id == "test_user"
        assert entry.user_name == "Test User"
        assert entry.ip_address == "192.168.1.100"
        assert entry.resource == "authentication"
        assert entry.action == "login"
        assert entry.success is True
        assert entry.details == {"method": "password"}
    
    def test_get_audit_log_filtering(self, security_manager):
        """Test audit log filtering"""
        # Add multiple audit entries
        events = [
            (AuditEventType.LOGIN_SUCCESS, "user1", True),
            (AuditEventType.LOGIN_FAILURE, "user1", False),
            (AuditEventType.LOGIN_SUCCESS, "user2", True),
            (AuditEventType.CONFIG_CHANGE, "user1", True),
        ]
        
        for event_type, user_id, success in events:
            security_manager.log_audit_event(
                event_type=event_type,
                user_id=user_id,
                user_name=user_id,
                ip_address="192.168.1.100",
                user_agent="Test",
                resource="test",
                action="test",
                details={},
                security_level=SecurityLevel.LOW,
                success=success
            )
        
        # Filter by event type
        login_events = security_manager.get_audit_log(event_type=AuditEventType.LOGIN_SUCCESS)
        assert len(login_events) == 2
        assert all(e.event_type == AuditEventType.LOGIN_SUCCESS for e in login_events)
        
        # Filter by user
        user1_events = security_manager.get_audit_log(user_id="user1")
        assert len(user1_events) == 3
        assert all(e.user_id == "user1" for e in user1_events)
        
        # Filter by limit
        limited_events = security_manager.get_audit_log(limit=2)
        assert len(limited_events) == 2
    
    def test_cleanup_expired_sessions(self, security_manager):
        """Test cleanup of expired sessions"""
        user_id = "test_user"
        user_name = "Test User"
        ip_address = "192.168.1.100"
        user_agent = "Test Browser"
        permissions = {"read"}
        
        # Create sessions
        session1 = security_manager.create_session(
            user_id, user_name, ip_address, user_agent, permissions
        )
        session2 = security_manager.create_session(
            user_id + "2", user_name, ip_address, user_agent, permissions
        )
        
        # Expire one session
        session1.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session1.is_active = False
        
        assert len(security_manager.active_sessions) == 2
        
        # Cleanup
        security_manager.cleanup_expired_sessions()
        
        # Should have removed expired session
        assert len(security_manager.active_sessions) == 1
        assert session2.session_id in security_manager.active_sessions
        assert session1.session_id not in security_manager.active_sessions
    
    def test_get_security_summary(self, security_manager):
        """Test security summary generation"""
        # Add some test data
        security_manager.create_session(
            "user1", "User 1", "192.168.1.100", "Browser", {"read"}
        )
        security_manager.record_login_attempt("user1", "192.168.1.100", True)
        security_manager.record_login_attempt("user2", "192.168.1.101", False)
        
        summary = security_manager.get_security_summary()
        
        assert "timestamp" in summary
        assert "active_sessions" in summary
        assert "blocked_users" in summary
        assert "recent_activity" in summary
        assert "security_policy" in summary
        assert "top_users" in summary
        
        assert summary["active_sessions"] == 1
        assert summary["blocked_users"] == 0
        assert summary["recent_activity"]["successful_logins"] == 1
        assert summary["recent_activity"]["failed_logins"] == 1
    
    def test_export_audit_log(self, security_manager):
        """Test audit log export"""
        # Add test audit entry
        security_manager.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="test_user",
            user_name="Test User",
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            resource="authentication",
            action="login",
            details={"method": "password"},
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        # Export as JSON
        exported_data = security_manager.export_audit_log("json")
        
        assert isinstance(exported_data, str)
        assert "test_user" in exported_data
        assert "login_success" in exported_data
        assert "authentication" in exported_data
        
        # Test invalid format
        exported_data = security_manager.export_audit_log("invalid")
        assert "error" in exported_data.lower()


if __name__ == "__main__":
    pytest.main([__file__])