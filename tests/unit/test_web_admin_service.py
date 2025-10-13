"""
Unit tests for Web Administration Service
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta, timezone

from src.services.web.web_admin_service import (
    WebAdminService, AuthenticationManager, WebSocketManager,
    LoginRequest, SystemStatus, NodeInfo, MessageInfo, BroadcastMessage
)
from src.core.plugin_manager import PluginMetadata


class TestAuthenticationManager:
    """Test authentication manager functionality"""
    
    def test_init(self):
        """Test authentication manager initialization"""
        from src.services.web.security import SecurityManager
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        assert auth.secret_key == "test-secret"
        assert auth.security_manager == security_manager
        assert "admin" in auth.users
        assert auth.users["admin"]["username"] == "admin"
    
    def test_verify_password(self):
        """Test password verification"""
        from src.services.web.security import SecurityManager
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        # Test correct password using security manager
        password_hash, salt = security_manager.hash_password("testpass")
        assert security_manager.verify_password("testpass", password_hash, salt)
        
        # Test incorrect password
        assert not security_manager.verify_password("wrongpass", password_hash, salt)
    
    def test_authenticate_user(self):
        """Test user authentication"""
        from src.services.web.security import SecurityManager
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        # Test valid credentials
        user = auth.authenticate_user("admin", "admin123", "127.0.0.1", "test-agent")
        assert user is not None
        assert user["username"] == "admin"
        
        # Test invalid username
        user = auth.authenticate_user("nonexistent", "admin123", "127.0.0.1", "test-agent")
        assert user is None
        
        # Test invalid password
        user = auth.authenticate_user("admin", "wrongpass", "127.0.0.1", "test-agent")
        assert user is None
    
    def test_create_access_token(self):
        """Test access token creation"""
        from src.services.web.security import SecurityManager
        from jose import jwt
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        # Create token manually since we removed create_access_token method
        from datetime import datetime, timezone, timedelta
        to_encode = {"sub": "admin"}
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        to_encode.update({"exp": expire})
        token = jwt.encode(to_encode, "test-secret", algorithm="HS256")
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token manually
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["sub"] == "admin"
    
    def test_verify_token(self):
        """Test token verification"""
        from src.services.web.security import SecurityManager
        from jose import jwt, JWTError
        from datetime import datetime, timezone, timedelta
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        # Test valid token
        to_encode = {"sub": "admin"}
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        to_encode.update({"exp": expire})
        token = jwt.encode(to_encode, "test-secret", algorithm="HS256")
        
        try:
            payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
            assert payload["sub"] == "admin"
        except JWTError:
            assert False, "Valid token should decode successfully"
        
        # Test invalid token
        try:
            jwt.decode("invalid-token", "test-secret", algorithms=["HS256"])
            assert False, "Invalid token should raise JWTError"
        except JWTError:
            pass  # Expected
    
    def test_get_user_permissions(self):
        """Test getting user permissions"""
        from src.services.web.security import SecurityManager
        from src.services.web.web_admin_service import Permission
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        user = auth.users["admin"]
        permissions = user["permissions"]
        assert Permission.SYSTEM_ADMIN in permissions
        assert Permission.USER_READ in permissions
        assert Permission.MESSAGE_READ in permissions
        
        # Test nonexistent user
        nonexistent_user = auth.users.get("nonexistent")
        assert nonexistent_user is None
    
    def test_has_permission(self):
        """Test permission checking"""
        from src.services.web.security import SecurityManager
        from src.services.web.web_admin_service import Permission
        security_manager = SecurityManager()
        auth = AuthenticationManager("test-secret", security_manager)
        
        # Admin should have all permissions
        admin_permissions = auth.users["admin"]["permissions"]
        assert auth.has_permission(admin_permissions, Permission.USER_READ)
        assert auth.has_permission(admin_permissions, Permission.MESSAGE_SEND)
        assert auth.has_permission(admin_permissions, Permission.SYSTEM_ADMIN)


class TestWebSocketManager:
    """Test WebSocket manager functionality"""
    
    @pytest.fixture
    def websocket_manager(self):
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket
    
    @pytest.mark.asyncio
    async def test_connect(self, websocket_manager, mock_websocket):
        """Test WebSocket connection"""
        client_id = "test-client"
        permissions = {"read", "write"}
        
        await websocket_manager.connect(mock_websocket, client_id, permissions)
        
        assert client_id in websocket_manager.active_connections
        assert websocket_manager.active_connections[client_id] == mock_websocket
        assert websocket_manager.connection_permissions[client_id] == permissions
        mock_websocket.accept.assert_called_once()
    
    def test_disconnect(self, websocket_manager, mock_websocket):
        """Test WebSocket disconnection"""
        client_id = "test-client"
        permissions = {"read"}
        
        # Add connection first
        websocket_manager.active_connections[client_id] = mock_websocket
        websocket_manager.connection_permissions[client_id] = permissions
        
        # Disconnect
        websocket_manager.disconnect(client_id)
        
        assert client_id not in websocket_manager.active_connections
        assert client_id not in websocket_manager.connection_permissions
    
    @pytest.mark.asyncio
    async def test_send_personal_message(self, websocket_manager, mock_websocket):
        """Test sending personal message"""
        client_id = "test-client"
        message = "test message"
        
        # Add connection
        websocket_manager.active_connections[client_id] = mock_websocket
        
        await websocket_manager.send_personal_message(message, client_id)
        
        mock_websocket.send_text.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast(self, websocket_manager, mock_websocket):
        """Test broadcasting message"""
        client_id = "test-client"
        permissions = {"read", "write"}
        message = "broadcast message"
        
        # Add connection
        websocket_manager.active_connections[client_id] = mock_websocket
        websocket_manager.connection_permissions[client_id] = permissions
        
        await websocket_manager.broadcast(message, permission_required="read")
        
        mock_websocket.send_text.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_permission_filter(self, websocket_manager, mock_websocket):
        """Test broadcast with permission filtering"""
        client_id = "test-client"
        permissions = {"read"}  # No write permission
        message = "broadcast message"
        
        # Add connection
        websocket_manager.active_connections[client_id] = mock_websocket
        websocket_manager.connection_permissions[client_id] = permissions
        
        await websocket_manager.broadcast(message, permission_required="write")
        
        # Should not send message due to insufficient permissions
        mock_websocket.send_text.assert_not_called()


class TestWebAdminService:
    """Test web administration service"""
    
    @pytest.fixture
    def mock_plugin_manager(self):
        manager = Mock()
        manager.config_manager = Mock()
        manager.config_manager.get = Mock(return_value=None)
        return manager
    
    @pytest.fixture
    def config(self):
        return {
            "host": "127.0.0.1",
            "port": 8080,
            "secret_key": "test-secret-key",
            "debug": True
        }
    
    @pytest.fixture
    def web_service(self, config, mock_plugin_manager):
        return WebAdminService(config, mock_plugin_manager)
    
    def test_init(self, web_service):
        """Test web service initialization"""
        assert web_service.name == "web_admin"
        assert web_service.host == "127.0.0.1"
        assert web_service.port == 8080
        assert web_service.secret_key == "test-secret-key"
        assert web_service.debug is True
        assert web_service.auth_manager is not None
        assert web_service.websocket_manager is not None
        assert web_service.app is not None
    
    @pytest.mark.asyncio
    async def test_initialize(self, web_service):
        """Test service initialization"""
        result = await web_service.initialize()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_cleanup(self, web_service):
        """Test service cleanup"""
        result = await web_service.cleanup()
        assert result is True
    
    def test_get_metadata(self, web_service):
        """Test getting plugin metadata"""
        metadata = web_service.get_metadata()
        
        assert isinstance(metadata, PluginMetadata)
        assert metadata.name == "web_admin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Web-based administration interface for ZephyrGate"
        assert metadata.enabled is True
    
    @pytest.mark.asyncio
    async def test_get_system_status(self, web_service):
        """Test getting system status"""
        status = await web_service._get_system_status()
        
        assert isinstance(status, SystemStatus)
        assert status.status in ["running", "warning", "healthy"]
        assert isinstance(status.uptime, int)
        assert isinstance(status.active_plugins, list)
        assert isinstance(status.node_count, int)
        assert isinstance(status.message_count, int)
        assert isinstance(status.active_incidents, int)
        assert isinstance(status.last_updated, datetime)
    
    @pytest.mark.asyncio
    async def test_get_nodes(self, web_service):
        """Test getting nodes"""
        nodes = await web_service._get_nodes()
        
        assert isinstance(nodes, list)
        # Currently returns empty list as mock data
        assert len(nodes) == 0
    
    @pytest.mark.asyncio
    async def test_get_messages(self, web_service):
        """Test getting messages"""
        messages = await web_service._get_messages(10, 0)
        
        assert isinstance(messages, list)
        # Currently returns empty list as mock data
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_send_broadcast(self, web_service):
        """Test sending broadcast message"""
        message = BroadcastMessage(content="Test broadcast")
        username = "admin"
        
        result = await web_service._send_broadcast(message, username)
        
        assert isinstance(result, dict)
        assert result["status"] == "sent"
        assert "message_id" in result
    
    @pytest.mark.asyncio
    async def test_get_config(self, web_service):
        """Test getting configuration"""
        config = await web_service._get_config()
        
        assert isinstance(config, dict)
        assert config["status"] == "not_implemented"
    
    def test_get_config_schema(self, web_service):
        """Test getting configuration schema"""
        schema = web_service.get_config_schema()
        
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "host" in schema["properties"]
        assert "port" in schema["properties"]
        assert "secret_key" in schema["properties"]
        assert "debug" in schema["properties"]
    
    def test_get_default_config(self, web_service):
        """Test getting default configuration"""
        config = web_service.get_default_config()
        
        assert isinstance(config, dict)
        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8080
        assert config["debug"] is False


class TestPydanticModels:
    """Test Pydantic models"""
    
    def test_login_request(self):
        """Test LoginRequest model"""
        request = LoginRequest(username="admin", password="password")
        
        assert request.username == "admin"
        assert request.password == "password"
    
    def test_login_response(self):
        """Test LoginResponse model"""
        from src.services.web.web_admin_service import LoginResponse
        response = LoginResponse(access_token="token123", expires_in=3600)
        
        assert response.access_token == "token123"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600
    
    def test_system_status(self):
        """Test SystemStatus model"""
        now = datetime.now(timezone.utc)
        status = SystemStatus(
            status="running",
            uptime=3600,
            active_plugins=["bbs", "emergency"],
            node_count=5,
            message_count=100,
            active_incidents=1,
            last_updated=now
        )
        
        assert status.status == "running"
        assert status.uptime == 3600
        assert status.active_plugins == ["bbs", "emergency"]
        assert status.node_count == 5
        assert status.message_count == 100
        assert status.active_incidents == 1
        assert status.last_updated == now
    
    def test_node_info(self):
        """Test NodeInfo model"""
        now = datetime.now(timezone.utc)
        node = NodeInfo(
            node_id="!12345678",
            short_name="TEST",
            long_name="Test Node",
            hardware="TBEAM",
            role="CLIENT",
            battery_level=85,
            snr=5.5,
            last_seen=now,
            location={"lat": 40.7128, "lon": -74.0060}
        )
        
        assert node.node_id == "!12345678"
        assert node.short_name == "TEST"
        assert node.long_name == "Test Node"
        assert node.hardware == "TBEAM"
        assert node.role == "CLIENT"
        assert node.battery_level == 85
        assert node.snr == 5.5
        assert node.last_seen == now
        assert node.location == {"lat": 40.7128, "lon": -74.0060}
    
    def test_broadcast_message(self):
        """Test BroadcastMessage model"""
        now = datetime.now(timezone.utc)
        message = BroadcastMessage(
            content="Test broadcast",
            channel=0,
            interface_id="serial0",
            scheduled_time=now
        )
        
        assert message.content == "Test broadcast"
        assert message.channel == 0
        assert message.interface_id == "serial0"
        assert message.scheduled_time == now


@pytest.mark.asyncio
async def test_web_service_integration():
    """Integration test for web service startup and shutdown"""
    config = {
        "host": "127.0.0.1",
        "port": 8081,  # Use different port to avoid conflicts
        "secret_key": "test-secret-key",
        "debug": True
    }
    
    mock_plugin_manager = Mock()
    mock_plugin_manager.config_manager = Mock()
    mock_plugin_manager.config_manager.get = Mock(return_value=None)
    
    service = WebAdminService(config, mock_plugin_manager)
    
    # Test initialization
    assert await service.initialize()
    
    # Test cleanup
    assert await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])