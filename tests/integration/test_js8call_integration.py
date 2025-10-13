"""
Integration tests for JS8Call service
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.services.bbs.js8call_service import JS8CallConfig, JS8CallService
from src.services.bbs.models import JS8CallMessage, JS8CallPriority
from src.services.bbs.database import get_bbs_database
from tests.base import BaseTestCase


class TestJS8CallIntegration(BaseTestCase):
    """Integration tests for JS8Call service with database"""
    
    def setUp(self):
        super().setUp()
        self.config = JS8CallConfig(
            enabled=True,
            monitored_groups=["@ALLCALL", "@TEST"],
            urgent_keywords=["urgent", "priority"],
            emergency_keywords=["emergency", "mayday", "sos"]
        )
        self.mesh_callback = AsyncMock()
        self.service = JS8CallService(self.config, self.mesh_callback)
        self.db = get_bbs_database()
    
    def test_store_and_retrieve_js8call_message(self):
        """Test storing and retrieving JS8Call messages"""
        # Store a message
        stored_msg = self.db.store_js8call_message(
            callsign="KI7ABC",
            group="@ALLCALL",
            message="Test message from JS8Call",
            frequency="14078000",
            priority="normal"
        )
        
        self.assertIsNotNone(stored_msg)
        self.assertEqual(stored_msg.callsign, "KI7ABC")
        self.assertEqual(stored_msg.group, "@ALLCALL")
        self.assertEqual(stored_msg.message, "Test message from JS8Call")
        self.assertEqual(stored_msg.frequency, "14078000")
        self.assertEqual(stored_msg.priority, JS8CallPriority.NORMAL)
        self.assertIsNotNone(stored_msg.id)
        
        # Retrieve the message
        retrieved_msg = self.db.get_js8call_message(stored_msg.id)
        self.assertIsNotNone(retrieved_msg)
        self.assertEqual(retrieved_msg.callsign, stored_msg.callsign)
        self.assertEqual(retrieved_msg.message, stored_msg.message)
    
    def test_store_urgent_message(self):
        """Test storing urgent JS8Call message"""
        stored_msg = self.db.store_js8call_message(
            callsign="KI7XYZ",
            group="@ALLCALL",
            message="This is an urgent message",
            frequency="14078000",
            priority="urgent"
        )
        
        self.assertIsNotNone(stored_msg)
        self.assertEqual(stored_msg.priority, JS8CallPriority.URGENT)
        self.assertTrue(stored_msg.is_urgent())
    
    def test_store_emergency_message(self):
        """Test storing emergency JS8Call message"""
        stored_msg = self.db.store_js8call_message(
            callsign="KI7EMG",
            group="@ALLCALL",
            message="Emergency situation at grid CN87",
            frequency="14078000",
            priority="emergency"
        )
        
        self.assertIsNotNone(stored_msg)
        self.assertEqual(stored_msg.priority, JS8CallPriority.EMERGENCY)
        self.assertTrue(stored_msg.is_emergency())
    
    def test_get_recent_messages(self):
        """Test retrieving recent JS8Call messages"""
        # Store multiple messages
        messages = []
        for i in range(5):
            msg = self.db.store_js8call_message(
                callsign=f"KI7{i:03d}",
                group="@ALLCALL",
                message=f"Test message {i}",
                frequency="14078000",
                priority="normal"
            )
            messages.append(msg)
        
        # Retrieve recent messages
        recent = self.db.get_recent_js8call_messages(3)
        self.assertEqual(len(recent), 3)
        
        # Should be in reverse chronological order
        self.assertEqual(recent[0].callsign, "KI7004")
        self.assertEqual(recent[1].callsign, "KI7003")
        self.assertEqual(recent[2].callsign, "KI7002")
    
    def test_get_messages_by_group(self):
        """Test retrieving messages by group"""
        # Store messages for different groups
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Message 1", "14078000")
        self.db.store_js8call_message("KI7DEF", "@TEST", "Message 2", "14078000")
        self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Message 3", "14078000")
        
        # Get messages for specific group
        allcall_msgs = self.db.get_js8call_messages_by_group("@ALLCALL")
        test_msgs = self.db.get_js8call_messages_by_group("@TEST")
        
        self.assertEqual(len(allcall_msgs), 2)
        self.assertEqual(len(test_msgs), 1)
        self.assertEqual(test_msgs[0].callsign, "KI7DEF")
    
    def test_get_urgent_messages(self):
        """Test retrieving urgent messages"""
        # Store messages with different priorities
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Normal", "14078000", "normal")
        self.db.store_js8call_message("KI7DEF", "@ALLCALL", "Urgent", "14078000", "urgent")
        self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Emergency", "14078000", "emergency")
        
        # Get urgent messages
        urgent_msgs = self.db.get_urgent_js8call_messages()
        
        self.assertEqual(len(urgent_msgs), 2)  # urgent + emergency
        priorities = [msg.priority for msg in urgent_msgs]
        self.assertIn(JS8CallPriority.URGENT, priorities)
        self.assertIn(JS8CallPriority.EMERGENCY, priorities)
    
    def test_search_messages(self):
        """Test searching JS8Call messages"""
        # Store test messages
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Weather report", "14078000")
        self.db.store_js8call_message("KI7DEF", "@TEST", "Traffic update", "14078000")
        self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Weather forecast", "14078000")
        
        # Search by content
        weather_msgs = self.db.search_js8call_messages("weather")
        self.assertEqual(len(weather_msgs), 2)
        
        # Search by callsign
        abc_msgs = self.db.search_js8call_messages("report", "KI7ABC")
        self.assertEqual(len(abc_msgs), 1)
        self.assertEqual(abc_msgs[0].callsign, "KI7ABC")
    
    def test_mark_message_forwarded(self):
        """Test marking message as forwarded"""
        # Store message
        msg = self.db.store_js8call_message(
            "KI7ABC", "@ALLCALL", "Test message", "14078000", "urgent"
        )
        
        self.assertFalse(msg.forwarded_to_mesh)
        
        # Mark as forwarded
        success = self.db.mark_js8call_message_forwarded(msg.id)
        self.assertTrue(success)
        
        # Verify it's marked as forwarded
        retrieved = self.db.get_js8call_message(msg.id)
        self.assertTrue(retrieved.forwarded_to_mesh)
    
    def test_js8call_statistics(self):
        """Test JS8Call statistics"""
        # Store various messages
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Normal", "14078000", "normal")
        self.db.store_js8call_message("KI7DEF", "@ALLCALL", "Urgent", "14078000", "urgent")
        self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Emergency", "14078000", "emergency")
        
        # Mark one as forwarded
        msg = self.db.store_js8call_message("KI7JKL", "@ALLCALL", "Forward me", "14078000", "urgent")
        self.db.mark_js8call_message_forwarded(msg.id)
        
        # Get statistics
        stats = self.db.get_js8call_statistics()
        
        self.assertEqual(stats['total_messages'], 4)
        self.assertEqual(stats['forwarded_messages'], 1)
        self.assertEqual(stats['unique_callsigns'], 4)
        self.assertIn('by_priority', stats)
        self.assertEqual(stats['by_priority']['normal'], 1)
        self.assertEqual(stats['by_priority']['urgent'], 2)
        self.assertEqual(stats['by_priority']['emergency'], 1)
    
    async def test_service_message_handling(self):
        """Test service message handling integration"""
        # Create JS8Call message
        js8_message = JS8CallMessage(
            callsign="KI7ABC",
            group="@ALLCALL",
            message="This is an urgent test message",
            frequency="14078000",
            priority=JS8CallPriority.URGENT
        )
        
        # Handle the message
        await self.service._handle_js8call_message(js8_message)
        
        # Verify message was stored
        recent_msgs = self.db.get_recent_js8call_messages(1)
        self.assertEqual(len(recent_msgs), 1)
        stored_msg = recent_msgs[0]
        self.assertEqual(stored_msg.callsign, "KI7ABC")
        self.assertEqual(stored_msg.message, "This is an urgent test message")
        self.assertEqual(stored_msg.priority, JS8CallPriority.URGENT)
        
        # Verify message was forwarded to mesh
        self.mesh_callback.assert_called_once()
        mesh_message = self.mesh_callback.call_args[0][0]
        self.assertIn("⚠️ URGENT JS8Call:", mesh_message)
        self.assertIn("KI7ABC", mesh_message)
        
        # Verify message was marked as forwarded
        self.assertTrue(stored_msg.forwarded_to_mesh)
    
    async def test_service_emergency_handling(self):
        """Test service emergency message handling"""
        # Create emergency JS8Call message
        js8_message = JS8CallMessage(
            callsign="KI7EMG",
            group="@ALLCALL",
            message="Emergency at grid square CN87",
            frequency="14078000",
            priority=JS8CallPriority.EMERGENCY
        )
        
        # Handle the message
        await self.service._handle_js8call_message(js8_message)
        
        # Verify emergency message was forwarded with proper prefix
        self.mesh_callback.assert_called_once()
        mesh_message = self.mesh_callback.call_args[0][0]
        self.assertIn("🚨 EMERGENCY JS8Call:", mesh_message)
        self.assertIn("KI7EMG", mesh_message)
        self.assertIn("Emergency at grid square CN87", mesh_message)
    
    def test_service_database_integration(self):
        """Test service database method integration"""
        # Store some test messages
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Message 1", "14078000", "normal")
        self.db.store_js8call_message("KI7DEF", "@TEST", "Message 2", "14078000", "urgent")
        self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Message 3", "14078000", "emergency")
        
        # Test service methods
        recent = self.service.get_recent_messages(2)
        self.assertEqual(len(recent), 2)
        
        allcall_msgs = self.service.get_messages_by_group("@ALLCALL")
        self.assertEqual(len(allcall_msgs), 2)
        
        urgent_msgs = self.service.get_urgent_messages()
        self.assertEqual(len(urgent_msgs), 2)  # urgent + emergency
        
        search_results = self.service.search_messages("Message")
        self.assertEqual(len(search_results), 3)
    
    def test_service_statistics_integration(self):
        """Test service statistics integration"""
        # Store test messages
        self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Test", "14078000", "normal")
        self.db.store_js8call_message("KI7DEF", "@ALLCALL", "Urgent", "14078000", "urgent")
        
        # Mock client connection
        mock_client = Mock()
        mock_client.connected = True
        self.service.client = mock_client
        
        # Get service statistics
        stats = self.service.get_statistics()
        
        self.assertTrue(stats["enabled"])
        self.assertTrue(stats["connected"])
        self.assertEqual(stats["total_messages"], 2)
        self.assertIn("by_priority", stats)
    
    def test_cleanup_old_js8call_messages(self):
        """Test cleanup of old JS8Call messages"""
        # Store messages with different priorities
        normal_msg = self.db.store_js8call_message("KI7ABC", "@ALLCALL", "Normal", "14078000", "normal")
        urgent_msg = self.db.store_js8call_message("KI7DEF", "@ALLCALL", "Urgent", "14078000", "urgent")
        emergency_msg = self.db.store_js8call_message("KI7GHI", "@ALLCALL", "Emergency", "14078000", "emergency")
        
        # Verify all messages exist
        self.assertEqual(len(self.db.get_recent_js8call_messages(10)), 3)
        
        # Run cleanup (this would normally clean up old messages)
        # For testing, we'll just verify the method exists and runs
        self.db.cleanup_old_data(days_to_keep=90)
        
        # Messages should still exist since they're recent
        self.assertEqual(len(self.db.get_recent_js8call_messages(10)), 3)


if __name__ == '__main__':
    pytest.main([__file__])