"""
Security Integration Tests for Web Administration Interface

Tests security features, access control, audit logging, and authentication.
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from jose import jwt

from src.services.web.web_admin_service import WebAdminService, AuthenticationManager
from src.services.web.security import (
    SecurityManager, SecurityPolicy, AuditEventType, SecurityLevel,
    AuditLogEntry, SessionInfo
)


class TestWebAdminSecurity:
    """Test security features and access control"""
    
    @pytest.fixture
    def security_policy(self):
        """Create security policy for testing"""
        return SecurityPolicy(
            max_login_attempts=3,
            lockout_duration=300,  # 5 minutes
            session_timeout=1800,  # 30 minutes
            password_min_length=8,
            password_require_special=True,
            password_require_numbers=True,
            password_require_uppercase=True,
            allowed_ip_ranges=["127.0.0.0/8", "192.168.0.0/16"],
            blocked_ip_addresses={"192.168.100.100"},
            require_2fa=False,
            max_concurrent_sessions=3,
            audit_retention_days=90
        )
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Mock plugin manager for testing"""
        manager = Mock()
        manager.config_manager = Mock()
        manager.config_manager.get = Mock(return_value=None)
        manager.get_running_plugins = Mock(return_value=["security_test"])
        return manager
    
    @pytest.fixture
    def config(self, security_policy):
        """Test configuration with security settings"""
        return {
            "host": "127.0.0.1",
            "port": 8084,
            "secret_key": "security-test-secret-key-very-long-and-secure",
            "debug": False,  # Disable debug for security tests
            "max_login_attempts": security_policy.max_login_attempts,
            "lockout_duration": security_policy.lockout_duration,
            "session_timeout": security_policy.session_timeout,
            "password_min_length": security_policy.password_min_length,
            "allowed_ip_ranges": security_policy.allowed_ip_ranges,
            "audit_retention_days": security_policy.audit_retention_days
        }
    
    @pytest.fixture
    def web_service(self, config, mock_plugin_manager):
        """Create web service for security testing"""
        service = WebAdminService(config, mock_plugin_manager)
        return service
    
    @pytest.fixture
    def test_client(self, web_service):
        """Create test client for HTTP requests"""
        return TestClient(web_service.app)
    
    def test_password_strength_validation(self, web_service):
        """Test password strength validation"""
        security_manager = web_service.security_manager
        
        # Test weak passwords
        weak_passwords = [
            "123456",           # Too short, no letters
            "password",         # No numbers, no special chars, no uppercase
            "Password",         # No numbers, no special chars
            "Password123",      # No special chars
            "password123!",     # No uppercase
            "Pp1!",            # Too short
            "aaaaaaaaA1!",     # Too many repeated characters
        ]
        
        for password in weak_passwords:
            result = security_manager.validate_password_strength(password)
            assert result["valid"] is False, f"Password '{password}' should be invalid"
            assert len(result["issues"]) > 0
        
        # Test strong passwords
        strong_passwords = [
            "MySecure123!",
            "Complex@Pass1",
            "Str0ng#P@ssw0rd",
            "Test!ng123$ecure"
        ]
        
        for password in strong_passwords:
            result = security_manager.validate_password_strength(password)
            assert result["valid"] is True, f"Password '{password}' should be valid"
            assert len(result["issues"]) == 0
    
    def test_ip_address_filtering(self, web_service, test_client):
        """Test IP address allowlist and blocklist"""
        # Test allowed IP ranges
        with patch('fastapi.Request') as mock_request_class:
            mock_request = Mock()
            mock_request.client.host = "127.0.0.1"  # Allowed IP
            mock_request_class.return_value = mock_request
            
            login_data = {"username": "admin", "password": "admin123"}
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 200
        
        # Test blocked IP
        with patch('fastapi.Request') as mock_request_class:
            mock_request = Mock()
            mock_request.client.host = "192.168.100.100"  # Blocked IP
            mock_request_class.return_value = mock_request
            
            login_data = {"username": "admin", "password": "admin123"}
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401
        
        # Test IP not in allowed ranges
        with patch('fastapi.Request') as mock_request_class:
            mock_request = Mock()
            mock_request.client.host = "10.0.0.1"  # Not in allowed ranges
            mock_request_class.return_value = mock_request
            
            login_data = {"username": "admin", "password": "admin123"}
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401
    
    def test_login_attempt_tracking_and_lockout(self, web_service, test_client):
        """Test login attempt tracking and user lockout"""
        security_manager = web_service.security_manager
        
        # Test successful login tracking
        assert security_manager.record_login_attempt("testuser", "127.0.0.1", True)
        assert "testuser" not in security_manager.failed_login_counts
        
        # Test failed login tracking
        for i in range(2):
            assert security_manager.record_login_attempt("testuser", "127.0.0.1", False)
            assert security_manager.failed_login_counts["testuser"] == i + 1
            assert not security_manager.is_user_locked_out("testuser")
        
        # Third failed attempt should trigger lockout
        assert not security_manager.record_login_attempt("testuser", "127.0.0.1", False)
        assert security_manager.is_user_locked_out("testuser")
        
        # Test lockout via API
        login_data = {"username": "lockeduser", "password": "wrongpassword"}
        
        # Make failed attempts
        for i in range(3):
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code in [401, 423]  # 401 for failed auth, 423 for locked
        
        # Next attempt should be blocked due to lockout
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code in [401, 423]  # Should be locked out
        
        # Even with correct password, should still be locked out
        login_data["password"] = "admin123"  # Assuming this would be correct
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code in [401, 423]  # Should still be locked out
    
    def test_session_management_and_timeout(self, web_service):
        """Test session creation, validation, and timeout"""
        security_manager = web_service.security_manager
        
        # Create session
        session = security_manager.create_session(
            user_id="testuser",
            user_name="Test User",
            ip_address="127.0.0.1",
            user_agent="Test Browser",
            permissions={"read", "write"}
        )
        
        assert session is not None
        assert session.user_id == "testuser"
        assert session.is_active
        assert session.session_id in security_manager.active_sessions
        
        # Validate session
        validated_session = security_manager.validate_session(session.session_id, "127.0.0.1")
        assert validated_session is not None
        assert validated_session.session_id == session.session_id
        
        # Test session timeout
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        validated_session = security_manager.validate_session(session.session_id, "127.0.0.1")
        assert validated_session is None
        assert not session.is_active
    
    def test_concurrent_session_limits(self, web_service):
        """Test concurrent session limits"""
        security_manager = web_service.security_manager
        user_id = "concurrent_test_user"
        
        # Create sessions up to limit
        sessions = []
        for i in range(3):  # Max concurrent sessions = 3
            session = security_manager.create_session(
                user_id=user_id,
                user_name="Test User",
                ip_address=f"127.0.0.{i+1}",
                user_agent="Test Browser",
                permissions={"read"}
            )
            sessions.append(session)
            assert session is not None
        
        # Create one more session (should remove oldest)
        new_session = security_manager.create_session(
            user_id=user_id,
            user_name="Test User",
            ip_address="127.0.0.10",
            user_agent="Test Browser",
            permissions={"read"}
        )
        
        assert new_session is not None
        
        # Check that we still have only 3 active sessions for this user
        active_sessions = [
            s for s in security_manager.active_sessions.values()
            if s.user_id == user_id and s.is_active
        ]
        assert len(active_sessions) == 3
    
    def test_audit_logging(self, web_service):
        """Test comprehensive audit logging"""
        security_manager = web_service.security_manager
        
        # Test login success logging
        security_manager.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="testuser",
            user_name="Test User",
            ip_address="127.0.0.1",
            user_agent="Test Browser",
            resource="authentication",
            action="login",
            details={"method": "password"},
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        # Test login failure logging
        security_manager.log_audit_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id="baduser",
            user_name="Bad User",
            ip_address="192.168.1.100",
            user_agent="Malicious Browser",
            resource="authentication",
            action="login_failed",
            details={"reason": "invalid_password"},
            security_level=SecurityLevel.HIGH,
            success=False,
            error_message="Invalid credentials"
        )
        
        # Test security violation logging
        security_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            user_id="attacker",
            user_name="Attacker",
            ip_address="10.0.0.1",
            user_agent="Attack Tool",
            resource="system",
            action="unauthorized_access",
            details={"attempted_resource": "/admin/secrets"},
            security_level=SecurityLevel.CRITICAL,
            success=False
        )
        
        # Verify audit log entries
        audit_log = security_manager.get_audit_log()
        assert len(audit_log) >= 3
        
        # Check specific entries
        login_success = next((e for e in audit_log if e.event_type == AuditEventType.LOGIN_SUCCESS), None)
        assert login_success is not None
        assert login_success.user_id == "testuser"
        assert login_success.success is True
        
        login_failure = next((e for e in audit_log if e.event_type == AuditEventType.LOGIN_FAILURE), None)
        assert login_failure is not None
        assert login_failure.user_id == "baduser"
        assert login_failure.success is False
        
        security_violation = next((e for e in audit_log if e.event_type == AuditEventType.SECURITY_VIOLATION), None)
        assert security_violation is not None
        assert security_violation.security_level == SecurityLevel.CRITICAL
    
    def test_audit_log_filtering(self, web_service):
        """Test audit log filtering capabilities"""
        security_manager = web_service.security_manager
        
        # Add various audit events
        events = [
            (AuditEventType.LOGIN_SUCCESS, "user1", True, SecurityLevel.LOW),
            (AuditEventType.LOGIN_FAILURE, "user1", False, SecurityLevel.MEDIUM),
            (AuditEventType.LOGIN_SUCCESS, "user2", True, SecurityLevel.LOW),
            (AuditEventType.CONFIG_CHANGE, "admin", True, SecurityLevel.HIGH),
            (AuditEventType.SECURITY_VIOLATION, "attacker", False, SecurityLevel.CRITICAL),
        ]
        
        for event_type, user_id, success, security_level in events:
            security_manager.log_audit_event(
                event_type=event_type,
                user_id=user_id,
                user_name=user_id,
                ip_address="127.0.0.1",
                user_agent="Test",
                resource="test",
                action="test",
                details={},
                security_level=security_level,
                success=success
            )
        
        # Test filtering by event type
        login_events = security_manager.get_audit_log(event_type=AuditEventType.LOGIN_SUCCESS)
        assert len(login_events) == 2
        assert all(e.event_type == AuditEventType.LOGIN_SUCCESS for e in login_events)
        
        # Test filtering by user
        user1_events = security_manager.get_audit_log(user_id="user1")
        assert len(user1_events) == 2
        assert all(e.user_id == "user1" for e in user1_events)
        
        # Test filtering by date range
        now = datetime.now(timezone.utc)
        recent_events = security_manager.get_audit_log(
            start_date=now - timedelta(minutes=1),
            end_date=now + timedelta(minutes=1)
        )
        assert len(recent_events) >= 5  # All our test events
        
        # Test limit
        limited_events = security_manager.get_audit_log(limit=3)
        assert len(limited_events) == 3
    
    def test_security_summary_generation(self, web_service):
        """Test security summary generation"""
        security_manager = web_service.security_manager
        
        # Create some test data
        security_manager.create_session("user1", "User 1", "127.0.0.1", "Browser", {"read"})
        security_manager.create_session("user2", "User 2", "127.0.0.2", "Browser", {"write"})
        
        security_manager.record_login_attempt("user1", "127.0.0.1", True)
        security_manager.record_login_attempt("user2", "127.0.0.2", True)
        security_manager.record_login_attempt("baduser", "10.0.0.1", False)
        
        security_manager.log_audit_event(
            AuditEventType.SECURITY_VIOLATION, "attacker", "Attacker",
            "10.0.0.1", "Tool", "system", "breach_attempt", {},
            SecurityLevel.HIGH, False
        )
        
        # Get security summary
        summary = security_manager.get_security_summary()
        
        assert "timestamp" in summary
        assert "active_sessions" in summary
        assert "blocked_users" in summary
        assert "recent_activity" in summary
        assert "security_policy" in summary
        assert "top_users" in summary
        
        assert summary["active_sessions"] == 2
        assert summary["recent_activity"]["successful_logins"] >= 2
        assert summary["recent_activity"]["failed_logins"] >= 1
        assert summary["recent_activity"]["security_violations"] >= 1
    
    def test_audit_log_export(self, web_service):
        """Test audit log export functionality"""
        security_manager = web_service.security_manager
        
        # Add test audit events
        security_manager.log_audit_event(
            AuditEventType.LOGIN_SUCCESS, "testuser", "Test User",
            "127.0.0.1", "Browser", "auth", "login", {"method": "password"},
            SecurityLevel.MEDIUM, True
        )
        
        # Export audit log
        exported_data = security_manager.export_audit_log("json")
        
        assert isinstance(exported_data, str)
        parsed_data = json.loads(exported_data)
        assert isinstance(parsed_data, list)
        assert len(parsed_data) >= 1
        
        # Check exported entry structure
        entry = parsed_data[0]
        assert "id" in entry
        assert "timestamp" in entry
        assert "event_type" in entry
        assert "user_id" in entry
        assert "success" in entry
        
        # Test invalid export format
        invalid_export = security_manager.export_audit_log("invalid_format")
        assert "error" in invalid_export.lower()
    
    def test_role_based_access_control(self, web_service, test_client):
        """Test role-based access control"""
        auth_manager = web_service.auth_manager
        
        # Create users with different roles
        auth_manager.create_user("viewer", "password123", "viewer", "admin", "127.0.0.1", "test")
        auth_manager.create_user("operator", "password123", "operator", "admin", "127.0.0.1", "test")
        
        # Test viewer permissions
        login_data = {"username": "viewer", "password": "password123"}
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        viewer_token = response.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Viewer should be able to read system status
        response = test_client.get("/api/system/status", headers=viewer_headers)
        assert response.status_code == 200
        
        # Viewer should NOT be able to delete users
        response = test_client.delete("/api/users/!testuser", headers=viewer_headers)
        assert response.status_code == 403
        
        # Viewer should NOT be able to send broadcasts
        broadcast_data = {"content": "Test broadcast"}
        response = test_client.post("/api/broadcasts/immediate", json=broadcast_data, headers=viewer_headers)
        assert response.status_code == 403
        
        # Test operator permissions
        login_data = {"username": "operator", "password": "password123"}
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        operator_token = response.json()["access_token"]
        operator_headers = {"Authorization": f"Bearer {operator_token}"}
        
        # Operator should be able to read system status
        response = test_client.get("/api/system/status", headers=operator_headers)
        assert response.status_code == 200
        
        # Operator should be able to send broadcasts
        response = test_client.post("/api/broadcasts/immediate", json=broadcast_data, headers=operator_headers)
        assert response.status_code == 200
        
        # Operator should NOT be able to delete users (admin only)
        response = test_client.delete("/api/users/!testuser", headers=operator_headers)
        assert response.status_code == 403
    
    def test_jwt_token_security(self, web_service, test_client):
        """Test JWT token security features"""
        # Login to get token
        login_data = {"username": "admin", "password": "admin123"}
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        # Verify token structure
        payload = jwt.decode(token, web_service.secret_key, algorithms=["HS256"])
        assert "sub" in payload
        assert "exp" in payload
        assert payload["sub"] == "admin"
        
        # Test token expiration
        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        expired_token = jwt.encode(expired_payload, web_service.secret_key, algorithm="HS256")
        expired_headers = {"Authorization": f"Bearer {expired_token}"}
        
        response = test_client.get("/api/system/status", headers=expired_headers)
        assert response.status_code == 401
        
        # Test token with wrong signature
        wrong_secret_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        wrong_headers = {"Authorization": f"Bearer {wrong_secret_token}"}
        
        response = test_client.get("/api/system/status", headers=wrong_headers)
        assert response.status_code == 401
        
        # Test malformed token
        malformed_headers = {"Authorization": "Bearer malformed.token.here"}
        response = test_client.get("/api/system/status", headers=malformed_headers)
        assert response.status_code == 401
    
    def test_session_hijacking_protection(self, web_service):
        """Test protection against session hijacking"""
        security_manager = web_service.security_manager
        
        # Create session from one IP
        session = security_manager.create_session(
            user_id="testuser",
            user_name="Test User",
            ip_address="127.0.0.1",
            user_agent="Browser",
            permissions={"read"}
        )
        
        # Try to use session from different IP
        validated_session = security_manager.validate_session(session.session_id, "192.168.1.100")
        
        # Session should still be valid but security event should be logged
        assert validated_session is not None
        
        # Check that security violation was logged
        audit_log = security_manager.get_audit_log(event_type=AuditEventType.SECURITY_VIOLATION)
        ip_mismatch_events = [
            e for e in audit_log 
            if e.action == "ip_address_mismatch" and e.details.get("session_id") == session.session_id
        ]
        assert len(ip_mismatch_events) >= 1
    
    def test_brute_force_protection(self, web_service, test_client):
        """Test protection against brute force attacks"""
        # Simulate brute force attack
        attacker_ip = "10.0.0.100"
        
        with patch('fastapi.Request') as mock_request_class:
            mock_request = Mock()
            mock_request.client.host = attacker_ip
            mock_request_class.return_value = mock_request
            
            # Make many failed login attempts
            for i in range(10):
                login_data = {"username": f"user{i}", "password": "wrongpassword"}
                response = test_client.post("/api/auth/login", json=login_data)
                assert response.status_code == 401
        
        # Check that multiple users are locked out
        security_manager = web_service.security_manager
        locked_users = [user for user in security_manager.blocked_users.keys()]
        assert len(locked_users) >= 3  # At least some users should be locked
        
        # Check audit log for security violations
        audit_log = security_manager.get_audit_log(event_type=AuditEventType.LOGIN_FAILURE)
        failed_attempts = [e for e in audit_log if e.ip_address == attacker_ip]
        assert len(failed_attempts) >= 10
    
    def test_audit_log_retention(self, web_service):
        """Test audit log retention policy"""
        security_manager = web_service.security_manager
        
        # Add old audit events
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=100)
        
        # Manually add old entry
        old_entry = AuditLogEntry(
            id="old_entry",
            timestamp=old_timestamp,
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="olduser",
            user_name="Old User",
            ip_address="127.0.0.1",
            user_agent="Old Browser",
            resource="auth",
            action="login",
            details={},
            security_level=SecurityLevel.LOW,
            success=True
        )
        security_manager.audit_log.append(old_entry)
        
        # Add recent entry
        security_manager.log_audit_event(
            AuditEventType.LOGIN_SUCCESS, "newuser", "New User",
            "127.0.0.1", "Browser", "auth", "login", {},
            SecurityLevel.LOW, True
        )
        
        initial_count = len(security_manager.audit_log)
        assert initial_count >= 2
        
        # Run cleanup
        security_manager.cleanup_old_audit_logs()
        
        # Old entries should be removed
        final_count = len(security_manager.audit_log)
        assert final_count < initial_count
        
        # Recent entries should remain
        remaining_entries = security_manager.get_audit_log()
        assert any(e.user_id == "newuser" for e in remaining_entries)
        assert not any(e.user_id == "olduser" for e in remaining_entries)
    
    def test_security_headers(self, test_client):
        """Test security headers in HTTP responses"""
        response = test_client.get("/")
        
        # Check for security headers (if implemented)
        # Note: These would need to be implemented in the actual service
        headers = response.headers
        
        # Basic security checks
        assert "server" not in headers.get("server", "").lower() or "fastapi" not in headers.get("server", "").lower()
        
        # CORS headers should be present
        assert "access-control-allow-origin" in headers
    
    @pytest.mark.asyncio
    async def test_security_cleanup_tasks(self, web_service):
        """Test security-related cleanup tasks"""
        security_manager = web_service.security_manager
        
        # Create expired sessions
        expired_session = security_manager.create_session(
            "expireduser", "Expired User", "127.0.0.1", "Browser", {"read"}
        )
        expired_session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_session.is_active = False
        
        # Create active session
        active_session = security_manager.create_session(
            "activeuser", "Active User", "127.0.0.1", "Browser", {"read"}
        )
        
        initial_session_count = len(security_manager.active_sessions)
        assert initial_session_count == 2
        
        # Run cleanup
        security_manager.cleanup_expired_sessions()
        
        # Expired session should be removed
        final_session_count = len(security_manager.active_sessions)
        assert final_session_count == 1
        assert active_session.session_id in security_manager.active_sessions
        assert expired_session.session_id not in security_manager.active_sessions


@pytest.mark.asyncio
async def test_comprehensive_security_scenario():
    """Comprehensive security test scenario"""
    # Create service with strict security policy
    security_policy = SecurityPolicy(
        max_login_attempts=2,
        lockout_duration=60,
        session_timeout=300,
        password_min_length=10,
        password_require_special=True,
        password_require_numbers=True,
        password_require_uppercase=True,
        allowed_ip_ranges=["127.0.0.0/8"],
        max_concurrent_sessions=2,
        audit_retention_days=30
    )
    
    mock_plugin_manager = Mock()
    mock_plugin_manager.config_manager = Mock()
    mock_plugin_manager.config_manager.get = Mock(return_value=None)
    
    config = {
        "host": "127.0.0.1",
        "port": 8085,
        "secret_key": "comprehensive-security-test-secret-key",
        "debug": False,
        "max_login_attempts": security_policy.max_login_attempts,
        "lockout_duration": security_policy.lockout_duration,
        "session_timeout": security_policy.session_timeout,
        "password_min_length": security_policy.password_min_length,
        "allowed_ip_ranges": security_policy.allowed_ip_ranges,
        "audit_retention_days": security_policy.audit_retention_days
    }
    
    service = WebAdminService(config, mock_plugin_manager)
    await service.initialize()
    
    try:
        client = TestClient(service.app)
        security_manager = service.security_manager
        
        # Test 1: Successful authentication and authorization
        login_data = {"username": "admin", "password": "admin123"}
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        admin_token = response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test 2: Access protected resource
        response = client.get("/api/system/status", headers=admin_headers)
        assert response.status_code == 200
        
        # Test 3: Create user with weak password (should fail)
        weak_password_result = security_manager.validate_password_strength("weak")
        assert weak_password_result["valid"] is False
        
        # Test 4: Failed login attempts and lockout
        bad_login_data = {"username": "testuser", "password": "wrongpassword"}
        for i in range(2):
            response = client.post("/api/auth/login", json=bad_login_data)
            assert response.status_code == 401
        
        # Next attempt should be blocked
        response = client.post("/api/auth/login", json=bad_login_data)
        assert response.status_code == 401
        assert security_manager.is_user_locked_out("testuser")
        
        # Test 5: Session management
        session_count_before = len(security_manager.active_sessions)
        
        # Create multiple sessions for same user
        for i in range(3):  # More than max_concurrent_sessions
            session = security_manager.create_session(
                f"multiuser", "Multi User", f"127.0.0.{i+1}", "Browser", {"read"}
            )
        
        # Should not exceed max concurrent sessions
        active_sessions = [
            s for s in security_manager.active_sessions.values()
            if s.user_id == "multiuser" and s.is_active
        ]
        assert len(active_sessions) <= security_policy.max_concurrent_sessions
        
        # Test 6: Audit logging verification
        audit_log = security_manager.get_audit_log()
        assert len(audit_log) > 0
        
        # Should have login success, login failures, and security violations
        event_types = [e.event_type for e in audit_log]
        assert AuditEventType.LOGIN_SUCCESS in event_types
        assert AuditEventType.LOGIN_FAILURE in event_types
        
        # Test 7: Security summary
        summary = security_manager.get_security_summary()
        assert summary["recent_activity"]["failed_logins"] >= 2
        assert summary["blocked_users"] >= 1
        
        # Test 8: Logout and token invalidation
        response = client.post("/api/auth/logout", headers=admin_headers)
        assert response.status_code == 200
        
        # Token should no longer work
        response = client.get("/api/system/status", headers=admin_headers)
        assert response.status_code == 401
        
        # Test 9: Cleanup operations
        initial_audit_count = len(security_manager.audit_log)
        security_manager.cleanup_expired_sessions()
        security_manager.cleanup_old_audit_logs()
        
        # Verify cleanup worked
        final_session_count = len([s for s in security_manager.active_sessions.values() if s.is_active])
        assert final_session_count <= session_count_before + 3  # Allow for test sessions
        
    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])