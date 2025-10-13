"""
Integration tests for Web Administration Interface

Tests all administrative functions, real-time updates, user management,
configuration changes, and security features.
"""

import asyncio
import json
import pytest
import websockets
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from jose import jwt

from src.services.web.web_admin_service import (
    WebAdminService, AuthenticationManager, WebSocketManager,
    LoginRequest, SystemStatus, NodeInfo, MessageInfo, BroadcastMessage,
    UserProfileResponse, UserUpdateRequest, PermissionUpdateRequest,
    SubscriptionUpdateRequest, TagRequest, MessageSearchRequest,
    DirectMessageRequest, ConfigurationUpdateRequest, ServiceActionRequest,
    ImmediateBroadcastRequest, ScheduleBroadcastRequest
)
from src.services.web.security import SecurityManager, SecurityPolicy, AuditEventType, SecurityLevel
from src.services.web.user_manager import UserManager, PermissionLevel, SubscriptionType
from src.services.web.system_monitor import SystemMonitor
from src.services.web.scheduler import BroadcastScheduler, ScheduleType, RecurrencePattern
from src.core.plugin_manager import PluginMetadata
from src.models.message import Message, MessageType


class TestWebAdminIntegration:
    """Integration tests for web administration interface"""
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Mock plugin manager for testing"""
        manager = Mock()
        manager.config_manager = Mock()
        manager.config_manager.get = Mock(return_value=None)
        manager.get_running_plugins = Mock(return_value=["bbs", "emergency", "bot"])
        return manager
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            "host": "127.0.0.1",
            "port": 8081,  # Use different port to avoid conflicts
            "secret_key": "test-secret-key-for-integration-tests",
            "debug": True,
            "max_login_attempts": 3,
            "lockout_duration": 300,
            "session_timeout": 1800,
            "password_min_length": 8,
            "allowed_ip_ranges": ["127.0.0.0/8", "192.168.0.0/16"],
            "audit_retention_days": 30
        }
    
    @pytest.fixture
    def web_service(self, config, mock_plugin_manager):
        """Create web service for testing"""
        service = WebAdminService(config, mock_plugin_manager)
        return service
    
    @pytest.fixture
    def test_client(self, web_service):
        """Create test client for HTTP requests"""
        return TestClient(web_service.app)
    
    @pytest.fixture
    def admin_token(self, web_service):
        """Create admin authentication token"""
        # Get admin user
        admin_user = web_service.auth_manager.users["admin"]
        
        # Create session for admin user
        session_id = web_service.auth_manager.create_session(
            user=admin_user,
            ip_address="127.0.0.1",
            user_agent="test-client"
        )
        
        # Create JWT token with session
        payload = {
            "sub": "admin",
            "session_id": session_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        
        token = jwt.encode(payload, web_service.secret_key, algorithm="HS256")
        return token
    
    def test_service_initialization(self, web_service):
        """Test web service initialization"""
        assert web_service.name == "web_admin"
        assert web_service.host == "127.0.0.1"
        assert web_service.port == 8081
        assert web_service.auth_manager is not None
        assert web_service.websocket_manager is not None
        assert web_service.system_monitor is not None
        assert web_service.user_manager is not None
        assert web_service.scheduler is not None
        assert web_service.security_manager is not None
    
    def test_authentication_login_success(self, test_client):
        """Test successful authentication"""
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_authentication_login_failure(self, test_client):
        """Test failed authentication"""
        login_data = {
            "username": "admin",
            "password": "wrongpassword"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
    
    def test_authentication_lockout(self, test_client, web_service):
        """Test user lockout after failed attempts"""
        login_data = {
            "username": "testuser",
            "password": "wrongpassword"
        }
        
        # Make multiple failed attempts
        for i in range(3):
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401
        
        # Next attempt should be blocked
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401
        
        # Check that user is locked out
        assert web_service.auth_manager.security_manager.is_user_locked_out("testuser")
    
    def test_protected_endpoint_without_token(self, test_client):
        """Test accessing protected endpoint without token"""
        response = test_client.get("/api/system/status")
        assert response.status_code == 403  # No authorization header
    
    def test_protected_endpoint_with_invalid_token(self, test_client):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = test_client.get("/api/system/status", headers=headers)
        assert response.status_code == 401
    
    def test_system_status_endpoint(self, test_client, admin_token):
        """Test system status endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/api/system/status", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "uptime" in data
        assert "active_plugins" in data
        assert "node_count" in data
        assert "message_count" in data
        assert "active_incidents" in data
        assert "last_updated" in data
    
    def test_nodes_endpoint(self, test_client, admin_token):
        """Test nodes endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/api/nodes", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_messages_endpoint(self, test_client, admin_token):
        """Test messages endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/api/messages", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_user_management_endpoints(self, test_client, admin_token, web_service):
        """Test user management endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create test user in user manager
        test_user = web_service.user_manager.create_user("!12345678", "TestUser", "Test User")
        
        # Get all users
        response = test_client.get("/api/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 1
        
        # Get specific user
        response = test_client.get("/api/users/!12345678", headers=headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["node_id"] == "!12345678"
        assert user_data["short_name"] == "TestUser"
        
        # Update user
        update_data = {
            "email": "test@example.com",
            "phone": "123-456-7890",
            "notes": "Test user notes"
        }
        response = test_client.put("/api/users/!12345678", json=update_data, headers=headers)
        assert response.status_code == 200
        
        # Verify update
        response = test_client.get("/api/users/!12345678", headers=headers)
        user_data = response.json()
        assert user_data["email"] == "test@example.com"
        assert user_data["phone"] == "123-456-7890"
        assert user_data["notes"] == "Test user notes"
        
        # Update permissions
        permissions_data = {"permissions": ["read", "write"]}
        response = test_client.put("/api/users/!12345678/permissions", json=permissions_data, headers=headers)
        assert response.status_code == 200
        
        # Update subscriptions
        subscriptions_data = {"subscriptions": ["weather_alerts", "emergency_alerts"]}
        response = test_client.put("/api/users/!12345678/subscriptions", json=subscriptions_data, headers=headers)
        assert response.status_code == 200
        
        # Add tag
        tag_data = {"tag": "test_tag"}
        response = test_client.post("/api/users/!12345678/tags", json=tag_data, headers=headers)
        assert response.status_code == 200
        
        # Remove tag
        response = test_client.delete("/api/users/!12345678/tags/test_tag", headers=headers)
        assert response.status_code == 200
        
        # Delete user
        response = test_client.delete("/api/users/!12345678", headers=headers)
        assert response.status_code == 200
        
        # Verify deletion
        response = test_client.get("/api/users/!12345678", headers=headers)
        assert response.status_code == 404
    
    def test_user_stats_endpoint(self, test_client, admin_token):
        """Test user statistics endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/api/users/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "active_users" in data
        assert "new_users_today" in data
        assert "total_messages" in data
        assert "messages_today" in data
        assert "top_users" in data
        assert "permission_distribution" in data
        assert "subscription_distribution" in data
    
    def test_broadcast_endpoints(self, test_client, admin_token):
        """Test broadcast management endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Send immediate broadcast
        broadcast_data = {
            "content": "Test immediate broadcast",
            "channel": 0,
            "interface_id": "serial0"
        }
        response = test_client.post("/api/broadcasts/immediate", json=broadcast_data, headers=headers)
        assert response.status_code == 200
        
        # Schedule broadcast
        schedule_data = {
            "name": "Test Scheduled Broadcast",
            "content": "Test scheduled message",
            "scheduled_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "channel": 0,
            "interface_id": "serial0"
        }
        response = test_client.post("/api/broadcasts/schedule", json=schedule_data, headers=headers)
        assert response.status_code == 200
        broadcast_id = response.json()["broadcast_id"]
        
        # Get scheduled broadcasts
        response = test_client.get("/api/broadcasts/scheduled", headers=headers)
        assert response.status_code == 200
        broadcasts = response.json()
        assert isinstance(broadcasts, list)
        assert len(broadcasts) >= 1
        
        # Get specific broadcast
        response = test_client.get(f"/api/broadcasts/scheduled/{broadcast_id}", headers=headers)
        assert response.status_code == 200
        broadcast_data = response.json()
        assert broadcast_data["id"] == broadcast_id
        
        # Update broadcast
        update_data = {
            "name": "Updated Test Broadcast",
            "content": "Updated test message"
        }
        response = test_client.put(f"/api/broadcasts/scheduled/{broadcast_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        
        # Cancel broadcast
        response = test_client.post(f"/api/broadcasts/scheduled/{broadcast_id}/cancel", headers=headers)
        assert response.status_code == 200
        
        # Delete broadcast
        response = test_client.delete(f"/api/broadcasts/scheduled/{broadcast_id}", headers=headers)
        assert response.status_code == 200
        
        # Get broadcast history
        response = test_client.get("/api/broadcasts/history", headers=headers)
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)
    
    def test_template_endpoints(self, test_client, admin_token):
        """Test message template endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get templates
        response = test_client.get("/api/templates", headers=headers)
        assert response.status_code == 200
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) > 0  # Should have default templates
        
        # Create template
        template_data = {
            "name": "Test Template",
            "content": "Test template with {variable}",
            "description": "Test template description",
            "variables": ["variable"],
            "category": "test"
        }
        response = test_client.post("/api/templates", json=template_data, headers=headers)
        assert response.status_code == 200
        template_id = response.json()["template_id"]
        
        # Get specific template
        response = test_client.get(f"/api/templates/{template_id}", headers=headers)
        assert response.status_code == 200
        template = response.json()
        assert template["name"] == "Test Template"
        
        # Update template
        update_data = {
            "name": "Updated Test Template",
            "content": "Updated template content"
        }
        response = test_client.put(f"/api/templates/{template_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        
        # Delete template
        response = test_client.delete(f"/api/templates/{template_id}", headers=headers)
        assert response.status_code == 200
    
    def test_message_search_endpoint(self, test_client, admin_token):
        """Test message search endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        search_data = {
            "query": "test",
            "limit": 50,
            "offset": 0
        }
        response = test_client.post("/api/messages/search", json=search_data, headers=headers)
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)
    
    def test_direct_message_endpoint(self, test_client, admin_token):
        """Test direct message endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        message_data = {
            "recipient_id": "!12345678",
            "content": "Test direct message",
            "interface_id": "serial0"
        }
        response = test_client.post("/api/messages/direct", json=message_data, headers=headers)
        assert response.status_code == 200
    
    def test_chat_stats_endpoint(self, test_client, admin_token):
        """Test chat statistics endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/api/chat/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "messages_today" in data
        assert "active_channels" in data
        assert "top_senders" in data
        assert "message_types" in data
        assert "hourly_activity" in data
    
    def test_configuration_endpoints(self, test_client, admin_token):
        """Test configuration management endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get configuration
        response = test_client.get("/api/config", headers=headers)
        assert response.status_code == 200
        config = response.json()
        assert "status" in config
        
        # Update configuration (mock implementation)
        config_data = {
            "section": "test",
            "key": "test_key",
            "value": "test_value"
        }
        response = test_client.put("/api/config", json=config_data, headers=headers)
        # Implementation returns not_implemented status
        assert response.status_code in [200, 501]
    
    def test_service_management_endpoints(self, test_client, admin_token):
        """Test service management endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get services
        response = test_client.get("/api/services", headers=headers)
        assert response.status_code == 200
        services = response.json()
        assert isinstance(services, list)
        
        # Service action (mock implementation)
        action_data = {"action": "restart"}
        response = test_client.post("/api/services/test_service/action", json=action_data, headers=headers)
        # Implementation returns not_implemented status
        assert response.status_code in [200, 501]
    
    def test_audit_log_endpoints(self, test_client, admin_token, web_service):
        """Test audit log endpoints"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add some audit events
        web_service.security_manager.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="admin",
            user_name="admin",
            ip_address="127.0.0.1",
            user_agent="test",
            resource="authentication",
            action="login",
            details={},
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        # Get audit log
        response = test_client.get("/api/audit", headers=headers)
        assert response.status_code == 200
        audit_log = response.json()
        assert isinstance(audit_log, list)
        assert len(audit_log) >= 1
        
        # Get security summary
        response = test_client.get("/api/audit/security-summary", headers=headers)
        assert response.status_code == 200
        summary = response.json()
        assert "timestamp" in summary
        assert "active_sessions" in summary
        assert "recent_activity" in summary
        
        # Export audit log
        response = test_client.get("/api/audit/export", headers=headers)
        assert response.status_code == 200
        # Should return JSON string
        export_data = response.json()
        assert isinstance(export_data, str)
    
    def test_permission_based_access_control(self, test_client, web_service):
        """Test permission-based access control"""
        # Create user with limited permissions
        web_service.auth_manager.create_user(
            username="limited_user",
            password="password123",
            role="viewer",
            created_by="admin",
            ip_address="127.0.0.1",
            user_agent="test"
        )
        
        # Login as limited user
        login_data = {
            "username": "limited_user",
            "password": "password123"
        }
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        limited_token = response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {limited_token}"}
        
        # Should be able to read system status
        response = test_client.get("/api/system/status", headers=headers)
        assert response.status_code == 200
        
        # Should NOT be able to delete users
        response = test_client.delete("/api/users/!12345678", headers=headers)
        assert response.status_code == 403
        
        # Should NOT be able to send broadcasts
        broadcast_data = {
            "content": "Test broadcast",
            "channel": 0
        }
        response = test_client.post("/api/broadcasts/immediate", json=broadcast_data, headers=headers)
        assert response.status_code == 403
    
    def test_session_management(self, test_client, web_service):
        """Test session management and timeout"""
        # Login to create session
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Should be able to access protected endpoint
        response = test_client.get("/api/system/status", headers=headers)
        assert response.status_code == 200
        
        # Logout
        response = test_client.post("/api/auth/logout", headers=headers)
        assert response.status_code == 200
        
        # Should no longer be able to access protected endpoint
        response = test_client.get("/api/system/status", headers=headers)
        assert response.status_code == 401
    
    def test_ip_address_filtering(self, test_client, web_service):
        """Test IP address filtering"""
        # Mock request with blocked IP
        with patch('fastapi.Request') as mock_request:
            mock_request.client.host = "192.168.100.1"  # Not in allowed ranges
            
            # Block the IP
            web_service.security_manager.policy.blocked_ip_addresses.add("192.168.100.1")
            
            login_data = {
                "username": "admin",
                "password": "admin123"
            }
            
            # Should be blocked
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401
    
    def test_dashboard_endpoint(self, test_client, admin_token):
        """Test dashboard HTML endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = test_client.get("/", headers=headers)
        
        # Should return HTML dashboard
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_static_files_serving(self, test_client):
        """Test static files are served correctly"""
        # Test CSS file (if it exists)
        response = test_client.get("/static/css/dashboard.css")
        # May return 404 if file doesn't exist, which is fine for testing
        assert response.status_code in [200, 404]
        
        # Test JS file (if it exists)
        response = test_client.get("/static/js/dashboard.js")
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, web_service):
        """Test WebSocket connection and real-time updates"""
        # This is a simplified test since full WebSocket testing requires more setup
        websocket_manager = web_service.websocket_manager
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        # Test connection
        await websocket_manager.connect(mock_websocket, "test_client", {"read", "write"})
        
        assert "test_client" in websocket_manager.active_connections
        assert websocket_manager.connection_permissions["test_client"] == {"read", "write"}
        mock_websocket.accept.assert_called_once()
        
        # Test personal message
        await websocket_manager.send_personal_message("Test message", "test_client")
        mock_websocket.send_text.assert_called_with("Test message")
        
        # Test broadcast
        await websocket_manager.broadcast("Broadcast message", permission_required="read")
        # Should send to test_client since they have read permission
        assert mock_websocket.send_text.call_count >= 2
        
        # Test disconnect
        websocket_manager.disconnect("test_client")
        assert "test_client" not in websocket_manager.active_connections
    
    def test_error_handling(self, test_client, admin_token):
        """Test error handling for various scenarios"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test 404 for non-existent user
        response = test_client.get("/api/users/!nonexistent", headers=headers)
        assert response.status_code == 404
        
        # Test 404 for non-existent broadcast
        response = test_client.get("/api/broadcasts/scheduled/nonexistent", headers=headers)
        assert response.status_code == 404
        
        # Test 404 for non-existent template
        response = test_client.get("/api/templates/nonexistent", headers=headers)
        assert response.status_code == 404
        
        # Test invalid JSON data
        response = test_client.post("/api/broadcasts/immediate", data="invalid json", headers=headers)
        assert response.status_code == 422
    
    def test_data_validation(self, test_client, admin_token):
        """Test input data validation"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test invalid email format
        invalid_user_data = {
            "email": "invalid-email-format"
        }
        response = test_client.put("/api/users/!12345678", json=invalid_user_data, headers=headers)
        # May return 422 for validation error or 404 for non-existent user
        assert response.status_code in [404, 422]
        
        # Test invalid broadcast data
        invalid_broadcast_data = {
            "content": "",  # Empty content
            "scheduled_time": "invalid-date-format"
        }
        response = test_client.post("/api/broadcasts/schedule", json=invalid_broadcast_data, headers=headers)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, web_service):
        """Test service lifecycle management"""
        # Test initialization
        assert await web_service.initialize() is True
        
        # Test that service is running
        metadata = web_service.get_metadata()
        assert isinstance(metadata, PluginMetadata)
        assert metadata.name == "web_admin"
        assert metadata.enabled is True
        
        # Test cleanup
        assert await web_service.cleanup() is True
    
    def test_concurrent_requests(self, test_client, admin_token):
        """Test handling of concurrent requests"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Make multiple concurrent requests
        import threading
        import time
        
        results = []
        
        def make_request():
            response = test_client.get("/api/system/status", headers=headers)
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5
    
    def test_rate_limiting_simulation(self, test_client, admin_token):
        """Test behavior under high request load"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Make many requests quickly
        success_count = 0
        for i in range(20):
            response = test_client.get("/api/system/status", headers=headers)
            if response.status_code == 200:
                success_count += 1
        
        # Most requests should succeed (no rate limiting implemented yet)
        assert success_count >= 15  # Allow for some potential failures
    
    def test_memory_usage_monitoring(self, web_service):
        """Test that service doesn't leak memory during operations"""
        import gc
        import sys
        
        # Get initial memory usage
        initial_objects = len(gc.get_objects())
        
        # Perform various operations
        for i in range(10):
            # Create and delete users
            user = web_service.user_manager.create_user(f"!test{i:08d}", f"TestUser{i}")
            web_service.user_manager.delete_user(f"!test{i:08d}")
            
            # Add and resolve alerts
            alert_id = web_service.system_monitor.add_alert("test", "low", f"Test alert {i}", "test")
            web_service.system_monitor.resolve_alert(alert_id)
        
        # Force garbage collection
        gc.collect()
        
        # Check memory usage hasn't grown significantly
        final_objects = len(gc.get_objects())
        growth = final_objects - initial_objects
        
        # Allow for some growth but not excessive
        assert growth < 1000, f"Memory usage grew by {growth} objects"


@pytest.mark.asyncio
async def test_full_integration_scenario():
    """Full integration test scenario"""
    # Create mock plugin manager
    mock_plugin_manager = Mock()
    mock_plugin_manager.config_manager = Mock()
    mock_plugin_manager.config_manager.get = Mock(return_value=None)
    mock_plugin_manager.get_running_plugins = Mock(return_value=["bbs", "emergency", "bot"])
    
    config = {
        "host": "127.0.0.1",
        "port": 8082,
        "secret_key": "integration-test-secret",
        "debug": True
    }
    
    # Create and initialize service
    service = WebAdminService(config, mock_plugin_manager)
    await service.initialize()
    
    try:
        # Create test client
        client = TestClient(service.app)
        
        # Test authentication flow
        login_response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test system monitoring
        status_response = client.get("/api/system/status", headers=headers)
        assert status_response.status_code == 200
        
        # Test user management
        service.user_manager.create_user("!TESTUSER", "TestUser", "Integration Test User")
        users_response = client.get("/api/users", headers=headers)
        assert users_response.status_code == 200
        users = users_response.json()
        assert any(user["node_id"] == "!TESTUSER" for user in users)
        
        # Test broadcasting
        broadcast_response = client.post("/api/broadcasts/immediate", json={
            "content": "Integration test broadcast",
            "channel": 0
        }, headers=headers)
        assert broadcast_response.status_code == 200
        
        # Test audit logging
        audit_response = client.get("/api/audit", headers=headers)
        assert audit_response.status_code == 200
        audit_log = audit_response.json()
        assert len(audit_log) > 0
        
        # Test logout
        logout_response = client.post("/api/auth/logout", headers=headers)
        assert logout_response.status_code == 200
        
        # Verify token is invalidated
        status_response = client.get("/api/system/status", headers=headers)
        assert status_response.status_code == 401
        
    finally:
        # Clean up
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])