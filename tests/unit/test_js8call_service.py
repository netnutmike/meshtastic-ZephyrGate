"""
Unit tests for JS8Call integration service
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import unittest

from src.services.bbs.js8call_service import (
    JS8CallConfig, JS8CallClient, JS8CallService
)
from src.services.bbs.models import JS8CallMessage, JS8CallPriority
from tests.base import BaseTestCase


class TestJS8CallConfig(unittest.TestCase):
    """Test JS8Call configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = JS8CallConfig()
        
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 2442)
        self.assertIn("@ALLCALL", config.monitored_groups)
        self.assertIn("@CQ", config.monitored_groups)
        self.assertIn("urgent", config.urgent_keywords)
        self.assertIn("emergency", config.emergency_keywords)
        self.assertTrue(config.auto_forward_urgent)
        self.assertTrue(config.auto_forward_emergency)
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = JS8CallConfig(
            enabled=True,
            host="192.168.1.100",
            port=2443,
            monitored_groups=["@TEST", "@CUSTOM"],
            urgent_keywords=["priority", "important"],
            emergency_keywords=["mayday", "sos"],
            auto_forward_urgent=False,
            auto_forward_emergency=True
        )
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "192.168.1.100")
        self.assertEqual(config.port, 2443)
        self.assertEqual(config.monitored_groups, ["@TEST", "@CUSTOM"])
        self.assertEqual(config.urgent_keywords, ["priority", "important"])
        self.assertEqual(config.emergency_keywords, ["mayday", "sos"])
        self.assertFalse(config.auto_forward_urgent)
        self.assertTrue(config.auto_forward_emergency)


class TestJS8CallClient(unittest.TestCase):
    """Test JS8Call TCP client"""
    
    def setUp(self):
        self.config = JS8CallConfig(
            enabled=True,
            monitored_groups=["@ALLCALL", "@TEST"],
            urgent_keywords=["urgent"],
            emergency_keywords=["emergency", "mayday"]
        )
        self.client = JS8CallClient(self.config)
    
    def test_initialization(self):
        """Test client initialization"""
        self.assertEqual(self.client.config, self.config)
        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.running)
        self.assertEqual(len(self.client.message_handlers), 0)
    
    def test_is_monitored_group(self):
        """Test group monitoring check"""
        self.assertTrue(self.client._is_monitored_group("@ALLCALL"))
        self.assertTrue(self.client._is_monitored_group("@allcall"))  # Case insensitive
        self.assertTrue(self.client._is_monitored_group("@TEST"))
        self.assertFalse(self.client._is_monitored_group("@NOTMONITORED"))
        self.assertFalse(self.client._is_monitored_group(""))
    
    def test_contains_monitored_content(self):
        """Test monitored content detection"""
        self.assertTrue(self.client._contains_monitored_content("Message to @ALLCALL"))
        self.assertTrue(self.client._contains_monitored_content("This is urgent"))
        self.assertTrue(self.client._contains_monitored_content("EMERGENCY situation"))
        self.assertFalse(self.client._contains_monitored_content("Regular message"))
        self.assertFalse(self.client._contains_monitored_content(""))
    
    def test_determine_priority(self):
        """Test message priority determination"""
        self.assertEqual(
            self.client._determine_priority("This is an emergency"),
            JS8CallPriority.EMERGENCY
        )
        self.assertEqual(
            self.client._determine_priority("Mayday mayday"),
            JS8CallPriority.EMERGENCY
        )
        self.assertEqual(
            self.client._determine_priority("This is urgent"),
            JS8CallPriority.URGENT
        )
        self.assertEqual(
            self.client._determine_priority("Regular message"),
            JS8CallPriority.NORMAL
        )
        self.assertEqual(
            self.client._determine_priority(""),
            JS8CallPriority.NORMAL
        )
    
    def test_message_handler_management(self):
        """Test message handler management"""
        handler1 = Mock()
        handler2 = Mock()
        
        # Add handlers
        self.client.add_message_handler(handler1)
        self.client.add_message_handler(handler2)
        self.assertEqual(len(self.client.message_handlers), 2)
        
        # Remove handler
        self.client.remove_message_handler(handler1)
        self.assertEqual(len(self.client.message_handlers), 1)
        self.assertIn(handler2, self.client.message_handlers)
        self.assertNotIn(handler1, self.client.message_handlers)
    
    @patch('asyncio.open_connection')
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_open_connection):
        """Test successful connection"""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        result = await self.client.connect()
        
        self.assertTrue(result)
        self.assertTrue(self.client.connected)
        mock_open_connection.assert_called_once_with("localhost", 2442)
    
    @patch('asyncio.open_connection')
    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_open_connection):
        """Test connection failure"""
        mock_open_connection.side_effect = Exception("Connection failed")
        
        result = await self.client.connect()
        
        self.assertFalse(result)
        self.assertFalse(self.client.connected)
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection"""
        # Mock connected state
        self.client.connected = True
        self.client.running = True
        mock_writer = AsyncMock()
        self.client.writer = mock_writer
        
        await self.client.disconnect()
        
        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.running)
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_directed_message(self):
        """Test processing directed JS8Call message"""
        handler = AsyncMock()
        self.client.add_message_handler(handler)
        
        message = {
            "type": "RX.DIRECTED",
            "params": {
                "FROM": "KI7ABC",
                "TO": "@ALLCALL",
                "TEXT": "This is an urgent message",
                "FREQ": "14078000"
            }
        }
        
        await self.client._process_directed_message(message)
        
        handler.assert_called_once()
        js8_message = handler.call_args[0][0]
        self.assertEqual(js8_message.callsign, "KI7ABC")
        self.assertEqual(js8_message.group, "@ALLCALL")
        self.assertEqual(js8_message.message, "This is an urgent message")
        self.assertEqual(js8_message.frequency, "14078000")
        self.assertEqual(js8_message.priority, JS8CallPriority.URGENT)
    
    @pytest.mark.asyncio
    async def test_process_activity_message(self):
        """Test processing JS8Call activity message"""
        handler = AsyncMock()
        self.client.add_message_handler(handler)
        
        message = {
            "type": "RX.ACTIVITY",
            "params": {
                "FROM": "KI7XYZ",
                "TEXT": "Emergency at grid square CN87",
                "FREQ": "14078000"
            }
        }
        
        await self.client._process_activity_message(message)
        
        handler.assert_called_once()
        js8_message = handler.call_args[0][0]
        self.assertEqual(js8_message.callsign, "KI7XYZ")
        self.assertEqual(js8_message.group, "ACTIVITY")
        self.assertEqual(js8_message.message, "Emergency at grid square CN87")
        self.assertEqual(js8_message.priority, JS8CallPriority.EMERGENCY)


class TestJS8CallService(unittest.TestCase):
    """Test JS8Call integration service"""
    
    def setUp(self):
        self.config = JS8CallConfig(enabled=True)
        self.mesh_callback = AsyncMock()
        
        # Mock database
        self.mock_db = Mock()
        self.mock_db.store_js8call_message.return_value = JS8CallMessage(
            id=1,
            callsign="KI7ABC",
            group="@ALLCALL",
            message="Test message",
            frequency="14078000",
            priority=JS8CallPriority.NORMAL
        )
        self.mock_db.get_recent_js8call_messages.return_value = []
        self.mock_db.get_js8call_statistics.return_value = {
            "total_messages": 10,
            "forwarded_messages": 5
        }
        
        with patch('src.services.bbs.js8call_service.get_bbs_database', return_value=self.mock_db):
            self.service = JS8CallService(self.config, self.mesh_callback)
    
    def test_initialization(self):
        """Test service initialization"""
        self.assertEqual(self.service.config, self.config)
        self.assertEqual(self.service.mesh_callback, self.mesh_callback)
        self.assertFalse(self.service.running)
        self.assertIsNone(self.service.client)
    
    @pytest.mark.asyncio
    async def test_start_disabled(self):
        """Test starting service when disabled"""
        self.config.enabled = False
        
        await self.service.start()
        
        self.assertIsNone(self.service.client)
        self.assertFalse(self.service.running)
    
    @patch('src.services.bbs.js8call_service.JS8CallClient')
    @pytest.mark.asyncio
    async def test_start_enabled(self, mock_client_class):
        """Test starting service when enabled"""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        await self.service.start()
        
        self.assertTrue(self.service.running)
        self.assertIsNotNone(self.service.client)
        mock_client.add_message_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping service"""
        # Mock running state
        self.service.running = True
        mock_client = AsyncMock()
        self.service.client = mock_client
        mock_task = AsyncMock()
        self.service.client_task = mock_task
        
        await self.service.stop()
        
        self.assertFalse(self.service.running)
        mock_task.cancel.assert_called_once()
        mock_client.stop.assert_called_once()
        self.assertIsNone(self.service.client)
    
    @pytest.mark.asyncio
    async def test_handle_js8call_message(self):
        """Test handling JS8Call message"""
        js8_message = JS8CallMessage(
            callsign="KI7ABC",
            group="@ALLCALL",
            message="Test message",
            frequency="14078000",
            priority=JS8CallPriority.NORMAL
        )
        
        await self.service._handle_js8call_message(js8_message)
        
        self.mock_db.store_js8call_message.assert_called_once_with(
            "KI7ABC", "@ALLCALL", "Test message", "14078000", "normal"
        )
    
    @pytest.mark.asyncio
    async def test_handle_urgent_message_forwarding(self):
        """Test forwarding urgent JS8Call message to mesh"""
        js8_message = JS8CallMessage(
            id=1,
            callsign="KI7ABC",
            group="@ALLCALL",
            message="This is urgent",
            frequency="14078000",
            priority=JS8CallPriority.URGENT
        )
        
        await self.service._handle_js8call_message(js8_message)
        
        # Should store message
        self.mock_db.store_js8call_message.assert_called_once()
        
        # Should forward to mesh
        self.mesh_callback.assert_called_once()
        mesh_message = self.mesh_callback.call_args[0][0]
        self.assertIn("⚠️ URGENT JS8Call:", mesh_message)
        self.assertIn("KI7ABC", mesh_message)
        
        # Should mark as forwarded
        self.mock_db.mark_js8call_message_forwarded.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_handle_emergency_message_forwarding(self):
        """Test forwarding emergency JS8Call message to mesh"""
        js8_message = JS8CallMessage(
            id=2,
            callsign="KI7XYZ",
            group="@ALLCALL",
            message="Emergency situation",
            frequency="14078000",
            priority=JS8CallPriority.EMERGENCY
        )
        
        await self.service._handle_js8call_message(js8_message)
        
        # Should forward to mesh
        self.mesh_callback.assert_called_once()
        mesh_message = self.mesh_callback.call_args[0][0]
        self.assertIn("🚨 EMERGENCY JS8Call:", mesh_message)
        self.assertIn("KI7XYZ", mesh_message)
    
    def test_should_forward_to_mesh(self):
        """Test message forwarding logic"""
        # Normal message - should not forward
        normal_msg = JS8CallMessage(priority=JS8CallPriority.NORMAL)
        self.assertFalse(self.service._should_forward_to_mesh(normal_msg))
        
        # Urgent message - should forward if enabled
        urgent_msg = JS8CallMessage(priority=JS8CallPriority.URGENT)
        self.assertTrue(self.service._should_forward_to_mesh(urgent_msg))
        
        # Emergency message - should forward if enabled
        emergency_msg = JS8CallMessage(priority=JS8CallPriority.EMERGENCY)
        self.assertTrue(self.service._should_forward_to_mesh(emergency_msg))
        
        # Test with forwarding disabled
        self.config.auto_forward_urgent = False
        self.config.auto_forward_emergency = False
        self.assertFalse(self.service._should_forward_to_mesh(urgent_msg))
        self.assertFalse(self.service._should_forward_to_mesh(emergency_msg))
    
    def test_get_statistics(self):
        """Test getting service statistics"""
        # Mock client
        mock_client = Mock()
        mock_client.connected = True
        self.service.client = mock_client
        
        stats = self.service.get_statistics()
        
        self.assertTrue(stats["enabled"])
        self.assertTrue(stats["connected"])
        self.assertEqual(stats["total_messages"], 10)
        self.assertEqual(stats["forwarded_messages"], 5)
    
    def test_is_connected(self):
        """Test connection status check"""
        # No client
        self.assertFalse(self.service.is_connected())
        
        # Client not connected
        mock_client = Mock()
        mock_client.connected = False
        self.service.client = mock_client
        self.assertFalse(self.service.is_connected())
        
        # Client connected
        mock_client.connected = True
        self.assertTrue(self.service.is_connected())
    
    def test_monitored_group_management(self):
        """Test monitored group management"""
        initial_groups = self.service.get_monitored_groups()
        
        # Add group
        self.service.add_monitored_group("@NEWGROUP")
        self.assertIn("@NEWGROUP", self.service.config.monitored_groups)
        
        # Remove group
        self.service.remove_monitored_group("@NEWGROUP")
        self.assertNotIn("@NEWGROUP", self.service.config.monitored_groups)
        
        # Don't add duplicate
        original_count = len(self.service.config.monitored_groups)
        self.service.add_monitored_group(initial_groups[0])
        self.assertEqual(len(self.service.config.monitored_groups), original_count)
    
    def test_database_methods(self):
        """Test database method delegation"""
        # Test get_recent_messages
        self.service.get_recent_messages(25)
        self.mock_db.get_recent_js8call_messages.assert_called_with(25)
        
        # Test get_messages_by_group
        self.service.get_messages_by_group("@TEST", 30)
        self.mock_db.get_js8call_messages_by_group.assert_called_with("@TEST", 30)
        
        # Test get_urgent_messages
        self.service.get_urgent_messages(15)
        self.mock_db.get_urgent_js8call_messages.assert_called_with(15)
        
        # Test search_messages
        self.service.search_messages("test", "KI7ABC")
        self.mock_db.search_js8call_messages.assert_called_with("test", "KI7ABC")
    
    def test_set_mesh_callback(self):
        """Test setting mesh callback"""
        new_callback = AsyncMock()
        self.service.set_mesh_callback(new_callback)
        self.assertEqual(self.service.mesh_callback, new_callback)


if __name__ == '__main__':
    pytest.main([__file__])