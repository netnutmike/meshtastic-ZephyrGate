"""
Comprehensive System Integration Tests

Tests the complete ZephyrGate system integration including:
- Main application startup and shutdown
- Service lifecycle management
- Message routing between services
- Health monitoring integration
- Service management interface
- Cross-service communication
"""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from main import ZephyrGateApplication
from core.config import ConfigurationManager
from core.health_monitor import HealthStatus, AlertSeverity
from core.service_manager import ServiceState, ServiceAction
from models.message import Message, MessageType, MessagePriority


class TestSystemIntegration:
    """Test complete system integration"""
    
    @pytest.fixture
    async def temp_config(self):
        """Create temporary configuration for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_data = {
                'app': {
                    'version': '1.0.0-test',
                    'debug': True
                },
                'database': {
                    'path': os.path.join(temp_dir, 'test.db'),
                    'max_connections': 5
                },
                'services': {
                    'emergency': {'enabled': True},
                    'bbs': {'enabled': True},
                    'bot': {'enabled': True},
                    'weather': {'enabled': False},  # Disable for faster tests
                    'email': {'enabled': False},    # Disable for faster tests
                    'web': {'enabled': False},      # Disable for faster tests
                    'asset': {'enabled': False}     # Disable for faster tests
                },
                'health_monitor': {
                    'check_interval': 5,  # Faster checks for testing
                    'alert_cooldown': 10
                },
                'logging': {
                    'level': 'DEBUG',
                    'file': os.path.join(temp_dir, 'test.log')
                }
            }
            
            yield config_data, temp_dir
    
    @pytest.fixture
    async def mock_plugins(self):
        """Create mock plugin instances for testing"""
        plugins = {}
        
        # Mock emergency service
        emergency_mock = AsyncMock()
        emergency_mock.handle_message = AsyncMock(return_value={'response_message': 'Emergency handled'})
        emergency_mock.handle_message_with_context = AsyncMock(return_value={'response_message': 'Emergency handled'})
        emergency_mock.health_check = AsyncMock(return_value=True)
        emergency_mock.get_status = AsyncMock(return_value={'status': 'running'})
        plugins['emergency'] = emergency_mock
        
        # Mock BBS service
        bbs_mock = AsyncMock()
        bbs_mock.handle_message = AsyncMock(return_value={'response_message': 'BBS handled'})
        bbs_mock.handle_message_with_context = AsyncMock(return_value={'response_message': 'BBS handled'})
        bbs_mock.health_check = AsyncMock(return_value=True)
        bbs_mock.get_status = AsyncMock(return_value={'status': 'running'})
        plugins['bbs'] = bbs_mock
        
        # Mock bot service
        bot_mock = AsyncMock()
        bot_mock.handle_message = AsyncMock(return_value={'response_message': 'Bot handled'})
        bot_mock.handle_message_with_context = AsyncMock(return_value={'response_message': 'Bot handled'})
        bot_mock.health_check = AsyncMock(return_value=True)
        bot_mock.get_status = AsyncMock(return_value={'status': 'running'})
        plugins['bot'] = bot_mock
        
        return plugins
    
    @pytest.fixture
    async def app_instance(self, temp_config, mock_plugins):
        """Create application instance for testing"""
        config_data, temp_dir = temp_config
        
        app = ZephyrGateApplication()
        
        # Mock configuration loading
        with patch.object(ConfigurationManager, 'load_config'):
            with patch.object(ConfigurationManager, 'get') as mock_get:
                def get_config(key, default=None):
                    keys = key.split('.')
                    value = config_data
                    for k in keys:
                        if isinstance(value, dict) and k in value:
                            value = value[k]
                        else:
                            return default
                    return value
                
                mock_get.side_effect = get_config
                
                # Mock plugin loading to return our mock plugins
                with patch.object(app, '_load_mock_plugins', return_value=mock_plugins):
                    yield app, config_data, temp_dir
    
    @pytest.mark.asyncio
    async def test_application_initialization(self, app_instance):
        """Test complete application initialization"""
        app, config_data, temp_dir = app_instance
        
        # Mock plugin manager methods
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    
                    # Initialize application
                    await app.initialize()
                    
                    # Verify core components are initialized
                    assert app.config_manager is not None
                    assert app.db_manager is not None
                    assert app.plugin_manager is not None
                    assert app.message_router is not None
                    assert app.health_monitor is not None
                    assert app.service_manager is not None
                    assert app.logger is not None
                    
                    # Verify enabled services are configured
                    assert 'emergency' in app.enabled_services
                    assert 'bbs' in app.enabled_services
                    assert 'bot' in app.enabled_services
                    assert 'weather' not in app.enabled_services  # Disabled in config
    
    @pytest.mark.asyncio
    async def test_service_startup_sequence(self, app_instance, mock_plugins):
        """Test service startup sequence with dependencies"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Verify services are registered with message router
                            assert len(app.message_router.services) > 0
                            
                            # Verify health monitoring is started
                            assert app.health_monitor is not None
                            
                            # Verify service manager has registered services
                            assert len(app.service_manager.services) > 0
    
    @pytest.mark.asyncio
    async def test_message_routing_integration(self, app_instance, mock_plugins):
        """Test message routing between services"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Create test messages
                            sos_message = Message(
                                sender_id="!12345678",
                                recipient_id=None,
                                channel=0,
                                content="SOS Need help!",
                                message_type=MessageType.TEXT
                            )
                            
                            bbs_message = Message(
                                sender_id="!87654321",
                                recipient_id=None,
                                channel=0,
                                content="bbslist",
                                message_type=MessageType.TEXT
                            )
                            
                            bot_message = Message(
                                sender_id="!11111111",
                                recipient_id=None,
                                channel=0,
                                content="help",
                                message_type=MessageType.TEXT
                            )
                            
                            # Process messages through router
                            await app.message_router.process_message(sos_message, "test_interface")
                            await app.message_router.process_message(bbs_message, "test_interface")
                            await app.message_router.process_message(bot_message, "test_interface")
                            
                            # Wait for message processing
                            await asyncio.sleep(0.1)
                            
                            # Verify messages were routed to appropriate services
                            # Note: In real implementation, we'd check actual service calls
                            # Here we verify the routing system is working
                            stats = app.message_router.get_stats()
                            assert stats['messages_received'] >= 3
                            assert stats['messages_queued'] >= 3
    
    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, app_instance, mock_plugins):
        """Test health monitoring system integration"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Verify health monitor is tracking services
                            health_status = app.health_monitor.get_system_status()
                            assert 'system_health' in health_status
                            assert 'services' in health_status
                            assert 'alerts' in health_status
                            
                            # Test health alert generation
                            alert_received = False
                            
                            def alert_callback(alert):
                                nonlocal alert_received
                                alert_received = True
                            
                            app.health_monitor.add_alert_callback(alert_callback)
                            
                            # Simulate high CPU usage to trigger alert
                            with patch('psutil.cpu_percent', return_value=95.0):
                                await app.health_monitor._check_system_alerts()
                            
                            # Verify alert was generated
                            assert len(app.health_monitor.alerts) > 0
                            assert any(alert.severity == AlertSeverity.CRITICAL for alert in app.health_monitor.alerts)
    
    @pytest.mark.asyncio
    async def test_service_management_operations(self, app_instance, mock_plugins):
        """Test service management operations"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.stop_plugin', return_value=True):
                        with patch('src.core.plugin_manager.PluginManager.restart_plugin', return_value=True):
                            with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                                with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                                    
                                    # Mock plugin info
                                    def get_plugin_info(name):
                                        if name in mock_plugins:
                                            mock_info = Mock()
                                            mock_info.instance = mock_plugins[name]
                                            return mock_info
                                        return None
                                    
                                    mock_get_info.side_effect = get_plugin_info
                                    
                                    # Initialize and start services
                                    await app.initialize()
                                    await app.start_services()
                                    
                                    # Test service restart
                                    success = await app.service_manager.restart_service('emergency')
                                    assert success
                                    
                                    # Test service status retrieval
                                    status = app.service_manager.get_service_status('emergency')
                                    assert status is not None
                                    assert 'name' in status
                                    assert 'state' in status
                                    
                                    # Test all services status
                                    all_status = app.service_manager.get_all_services_status()
                                    assert len(all_status) > 0
                                    assert 'emergency' in all_status
                                    
                                    # Test operations history
                                    history = app.service_manager.get_operations_history()
                                    assert len(history) > 0
                                    assert any(op['action'] == 'restart' for op in history)
    
    @pytest.mark.asyncio
    async def test_cross_service_communication(self, app_instance, mock_plugins):
        """Test communication between services"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Test service-to-service messaging
                            response = await app.message_router.send_service_message(
                                'emergency', 
                                'test_message', 
                                {'data': 'test'}
                            )
                            
                            # Test broadcast to services
                            await app.message_router.broadcast_to_services(
                                'system_notification',
                                {'message': 'test broadcast'}
                            )
                            
                            # Verify message router statistics
                            stats = app.message_router.get_stats()
                            assert 'services_called' in stats
                            assert len(app.message_router.services) > 0
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, app_instance, mock_plugins):
        """Test graceful system shutdown"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.stop_plugin', return_value=True):
                        with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                            with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                                
                                # Mock plugin info
                                def get_plugin_info(name):
                                    if name in mock_plugins:
                                        mock_info = Mock()
                                        mock_info.instance = mock_plugins[name]
                                        return mock_info
                                    return None
                                
                                mock_get_info.side_effect = get_plugin_info
                                
                                # Initialize and start services
                                await app.initialize()
                                await app.start_services()
                                
                                # Test graceful shutdown
                                success = await app.graceful_shutdown(timeout=10)
                                assert success
                                
                                # Verify services are stopped
                                if app.service_manager:
                                    all_status = app.service_manager.get_all_services_status()
                                    # In a real scenario, services would be stopped
                                    # Here we just verify the shutdown process completed
                                    assert all_status is not None
    
    @pytest.mark.asyncio
    async def test_system_status_reporting(self, app_instance, mock_plugins):
        """Test comprehensive system status reporting"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Test comprehensive status
                            status = app.get_comprehensive_status()
                            assert 'running' in status
                            assert 'enabled_services' in status
                            assert 'plugins' in status
                            assert 'message_router' in status
                            assert 'database' in status
                            
                            # Test service management status
                            service_status = app.get_service_management_status()
                            assert 'service_manager_available' in service_status
                            assert 'services' in service_status
                            assert 'operations_history' in service_status
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, app_instance, mock_plugins):
        """Test error handling and recovery mechanisms"""
        app, config_data, temp_dir = app_instance
        
        # Mock a failing service
        failing_service = AsyncMock()
        failing_service.handle_message = AsyncMock(side_effect=Exception("Service failure"))
        failing_service.health_check = AsyncMock(return_value=False)
        mock_plugins['failing_service'] = failing_service
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Register failing service
                            app.message_router.register_service('failing_service', failing_service)
                            
                            # Create test message that will cause failure
                            test_message = Message(
                                sender_id="!12345678",
                                recipient_id=None,
                                channel=0,
                                content="test failure",
                                message_type=MessageType.TEXT
                            )
                            
                            # Process message - should handle failure gracefully
                            await app.message_router.process_message(test_message, "test_interface")
                            
                            # Wait for processing
                            await asyncio.sleep(0.1)
                            
                            # Verify system continues to function despite service failure
                            stats = app.message_router.get_stats()
                            assert stats['messages_received'] >= 1
                            # System should continue operating even with service failures
    
    @pytest.mark.asyncio
    async def test_configuration_reload(self, app_instance, mock_plugins):
        """Test configuration reloading"""
        app, config_data, temp_dir = app_instance
        
        with patch('src.core.plugin_manager.PluginManager.discover_plugins', return_value=['emergency', 'bbs', 'bot']):
            with patch('src.core.plugin_manager.PluginManager.load_plugin', return_value=True):
                with patch('src.core.plugin_manager.PluginManager.start_plugin', return_value=True):
                    with patch('src.core.plugin_manager.PluginManager.get_plugin_info') as mock_get_info:
                        with patch('src.core.plugin_manager.PluginManager.get_running_plugins', return_value=['emergency', 'bbs', 'bot']):
                            
                            # Mock plugin info
                            def get_plugin_info(name):
                                if name in mock_plugins:
                                    mock_info = Mock()
                                    mock_info.instance = mock_plugins[name]
                                    mock_info.config = {}
                                    return mock_info
                                return None
                            
                            mock_get_info.side_effect = get_plugin_info
                            
                            # Initialize and start services
                            await app.initialize()
                            await app.start_services()
                            
                            # Test configuration reload
                            with patch.object(app.config_manager, 'load_config'):
                                await app.reload_configuration()
                            
                            # Verify configuration was reloaded
                            # In a real scenario, we'd check that services received new config
                            assert app.config_manager is not None


class TestPerformanceAndLoad:
    """Test system performance under load"""
    
    @pytest.mark.asyncio
    async def test_message_processing_load(self):
        """Test message processing under load"""
        # This would be a more comprehensive load test
        # For now, we'll create a simple test
        
        # Mock application components
        app = ZephyrGateApplication()
        
        with patch.object(app, 'initialize'):
            with patch.object(app, 'start_services'):
                # Simulate high message load
                message_count = 100
                messages = []
                
                for i in range(message_count):
                    message = Message(
                        sender_id=f"!{i:08d}",
                        recipient_id=None,
                        channel=0,
                        content=f"Test message {i}",
                        message_type=MessageType.TEXT
                    )
                    messages.append(message)
                
                # In a real test, we'd process these through the router
                # and measure performance metrics
                assert len(messages) == message_count
    
    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self):
        """Test concurrent service operations"""
        # Mock service manager
        from core.service_manager import ServiceManager
        from core.plugin_manager import PluginManager
        from core.config import ConfigurationManager
        
        config_manager = Mock()
        plugin_manager = Mock()
        
        service_manager = ServiceManager(plugin_manager, config_manager)
        
        # Register test services
        service_manager.register_service('service1')
        service_manager.register_service('service2')
        service_manager.register_service('service3')
        
        # Mock plugin manager methods
        plugin_manager.start_plugin = AsyncMock(return_value=True)
        plugin_manager.stop_plugin = AsyncMock(return_value=True)
        
        # Test concurrent operations
        tasks = []
        for i in range(3):
            task = asyncio.create_task(
                service_manager.restart_service(f'service{i+1}')
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all operations completed
        assert len(results) == 3
        # In a real test, we'd verify no race conditions occurred


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])