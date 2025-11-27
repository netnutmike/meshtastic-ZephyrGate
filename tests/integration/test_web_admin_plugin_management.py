"""
Integration tests for Web Admin Plugin Management

Tests the plugin management functionality in the web admin interface.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from src.services.web.web_admin_service import WebAdminService
from src.core.plugin_manager import PluginMetadata


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager with test plugins"""
    manager = Mock()
    
    # Create mock plugins
    plugin1 = Mock()
    plugin1.get_metadata.return_value = PluginMetadata(
        name="test_plugin_1",
        version="1.0.0",
        description="Test Plugin 1",
        author="Test Author",
        dependencies=[],
        enabled=True,
        config_schema={}
    )
    plugin1.is_running = True
    plugin1.start_time = datetime.now(timezone.utc)
    plugin1.config = {"enabled": True}
    plugin1.tasks = []  # Add tasks attribute
    plugin1.on_config_changed = AsyncMock()  # Add async method
    
    plugin2 = Mock()
    plugin2.get_metadata.return_value = PluginMetadata(
        name="test_plugin_2",
        version="2.0.0",
        description="Test Plugin 2",
        author="Another Author",
        dependencies=["test_plugin_1"],
        enabled=False,
        config_schema={}
    )
    plugin2.is_running = False
    plugin2.start_time = None
    plugin2.config = {"enabled": False}
    plugin2.tasks = []
    plugin2.on_config_changed = AsyncMock()
    
    manager.plugins = {
        "test_plugin_1": plugin1,
        "test_plugin_2": plugin2
    }
    
    # Mock manifests
    manager.manifests = {}
    
    # Mock health monitor
    health_monitor = Mock()
    health_monitor.get_plugin_health.return_value = {
        "status": "healthy",
        "failure_count": 0,
        "restart_count": 0,
        "errors": []
    }
    manager.health_monitor = health_monitor
    
    # Mock enable/disable methods
    manager.enable_plugin = AsyncMock(return_value=True)
    manager.disable_plugin = AsyncMock(return_value=True)
    
    return manager


@pytest_asyncio.fixture
async def web_admin_service(mock_plugin_manager):
    """Create a web admin service instance for testing"""
    config = {
        "host": "127.0.0.1",
        "port": 8081,
        "secret_key": "test-secret-key",
        "debug": True
    }
    
    service = WebAdminService(config, mock_plugin_manager)
    
    # Initialize but don't start the server
    await service.initialize()
    
    yield service
    
    # Cleanup
    await service.cleanup()


@pytest.mark.asyncio
async def test_get_plugins_list(web_admin_service):
    """Test getting list of all plugins"""
    plugins = await web_admin_service._get_plugins()
    
    assert len(plugins) == 2
    assert plugins[0]["name"] == "test_plugin_1"
    assert plugins[0]["version"] == "1.0.0"
    assert plugins[0]["status"] == "running"
    assert plugins[0]["health"] == "healthy"
    
    assert plugins[1]["name"] == "test_plugin_2"
    assert plugins[1]["version"] == "2.0.0"
    assert plugins[1]["status"] == "stopped"


@pytest.mark.asyncio
async def test_get_plugin_details(web_admin_service):
    """Test getting detailed information about a specific plugin"""
    details = await web_admin_service._get_plugin_details("test_plugin_1")
    
    assert details is not None
    assert details["name"] == "test_plugin_1"
    assert details["version"] == "1.0.0"
    assert details["description"] == "Test Plugin 1"
    assert details["author"] == "Test Author"
    assert details["status"] == "running"
    assert details["enabled"] is True
    assert "health" in details
    assert "config" in details


@pytest.mark.asyncio
async def test_get_plugin_details_not_found(web_admin_service):
    """Test getting details for non-existent plugin"""
    details = await web_admin_service._get_plugin_details("nonexistent_plugin")
    
    assert details is None


@pytest.mark.asyncio
async def test_enable_plugin(web_admin_service):
    """Test enabling a plugin"""
    success = await web_admin_service._enable_plugin(
        "test_plugin_2",
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    assert success is True
    web_admin_service.plugin_manager.enable_plugin.assert_called_once_with("test_plugin_2")


@pytest.mark.asyncio
async def test_disable_plugin(web_admin_service):
    """Test disabling a plugin"""
    success = await web_admin_service._disable_plugin(
        "test_plugin_1",
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    assert success is True
    web_admin_service.plugin_manager.disable_plugin.assert_called_once_with("test_plugin_1")


@pytest.mark.asyncio
async def test_restart_plugin(web_admin_service):
    """Test restarting a plugin"""
    success = await web_admin_service._restart_plugin(
        "test_plugin_1",
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    assert success is True
    # Should call disable then enable
    assert web_admin_service.plugin_manager.disable_plugin.call_count == 1
    assert web_admin_service.plugin_manager.enable_plugin.call_count == 1


@pytest.mark.asyncio
async def test_get_plugin_config(web_admin_service):
    """Test getting plugin configuration"""
    config = await web_admin_service._get_plugin_config("test_plugin_1")
    
    assert config is not None
    assert config["plugin"] == "test_plugin_1"
    assert "config" in config
    assert config["config"]["enabled"] is True


@pytest.mark.asyncio
async def test_update_plugin_config(web_admin_service):
    """Test updating plugin configuration"""
    new_config = {"enabled": False, "api_key": "test-key"}
    
    success = await web_admin_service._update_plugin_config(
        "test_plugin_1",
        new_config,
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    assert success is True


@pytest.mark.asyncio
async def test_get_plugin_logs(web_admin_service):
    """Test getting plugin logs"""
    logs = await web_admin_service._get_plugin_logs("test_plugin_1", 10)
    
    assert isinstance(logs, list)
    assert len(logs) <= 10
    
    if len(logs) > 0:
        assert "timestamp" in logs[0]
        assert "level" in logs[0]
        assert "message" in logs[0]
        assert "plugin" in logs[0]


@pytest.mark.asyncio
async def test_get_plugin_metrics(web_admin_service):
    """Test getting plugin metrics"""
    metrics = await web_admin_service._get_plugin_metrics("test_plugin_1")
    
    assert metrics is not None
    assert metrics["plugin"] == "test_plugin_1"
    assert metrics["status"] == "running"
    assert "uptime" in metrics
    assert "health" in metrics
    assert "metrics" in metrics


@pytest.mark.asyncio
async def test_get_plugin_errors(web_admin_service):
    """Test getting plugin errors"""
    errors = await web_admin_service._get_plugin_errors("test_plugin_1", 10)
    
    assert isinstance(errors, list)
    assert len(errors) <= 10


@pytest.mark.asyncio
async def test_get_available_plugins(web_admin_service):
    """Test getting available plugins"""
    result = await web_admin_service._get_available_plugins()
    
    assert "available_plugins" in result
    assert "total" in result
    assert isinstance(result["available_plugins"], list)


@pytest.mark.asyncio
async def test_install_plugin(web_admin_service):
    """Test plugin installation (mock)"""
    result = await web_admin_service._install_plugin(
        "/path/to/plugin",
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    assert "success" in result
    assert "message" in result
    # Currently returns False as installation is not implemented
    assert result["success"] is False


@pytest.mark.asyncio
async def test_uninstall_plugin(web_admin_service):
    """Test plugin uninstallation (mock)"""
    success = await web_admin_service._uninstall_plugin(
        "test_plugin_1",
        "admin",
        "127.0.0.1",
        "test-agent"
    )
    
    # Currently returns False as uninstallation is not implemented
    assert success is False


@pytest.mark.asyncio
async def test_plugin_list_with_error(web_admin_service):
    """Test plugin list when a plugin raises an error"""
    # Make one plugin raise an error
    web_admin_service.plugin_manager.plugins["test_plugin_1"].get_metadata.side_effect = Exception("Test error")
    
    plugins = await web_admin_service._get_plugins()
    
    # Should still return plugins, with error plugin marked
    assert len(plugins) == 2
    error_plugin = next(p for p in plugins if p["name"] == "test_plugin_1")
    assert error_plugin["status"] == "error"
    assert "error" in error_plugin


@pytest.mark.asyncio
async def test_plugin_details_with_manifest(web_admin_service, mock_plugin_manager):
    """Test plugin details includes manifest information"""
    # Add manifest to plugin manager
    manifest = Mock()
    manifest.commands = [Mock(name="test_cmd", description="Test command", usage="test_cmd [args]")]
    manifest.scheduled_tasks = [Mock(name="test_task", interval=60)]
    manifest.menu_items = [Mock(menu="main", label="Test", command="test")]
    manifest.permissions = ["read", "write"]
    
    mock_plugin_manager.manifests = {"test_plugin_1": manifest}
    
    details = await web_admin_service._get_plugin_details("test_plugin_1")
    
    assert details is not None
    assert "manifest" in details
    assert len(details["manifest"]["commands"]) == 1
    assert len(details["manifest"]["scheduled_tasks"]) == 1
    assert len(details["manifest"]["menu_items"]) == 1
    assert len(details["manifest"]["permissions"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
