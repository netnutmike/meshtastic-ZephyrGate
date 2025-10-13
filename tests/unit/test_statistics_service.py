"""
Unit tests for BBS Statistics Service

Tests system statistics reporting, wall of shame functionality,
and fortune system with configurable fortune file support.
"""

import pytest
import tempfile
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.services.bbs.statistics_service import (
    StatisticsService, NodeHardwareInfo, SystemStatistics,
    get_statistics_service
)
from src.core.database import initialize_database, get_database
from tests.base import BaseTestCase


class TestStatisticsService(BaseTestCase):
    """Test BBS statistics service"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        
        # Initialize database
        initialize_database(':memory:')
        self.db = get_database()
        
        # Create additional test tables
        self.create_test_tables()
        
        # Create temporary fortune file
        self.temp_fortune_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
        self.temp_fortune_file.write("Test fortune 1\n%\nTest fortune 2\n%\nTest fortune 3")
        self.temp_fortune_file.close()
        
        # Initialize statistics service with test config
        config = {
            'fortune_file': self.temp_fortune_file.name
        }
        self.stats_service = StatisticsService(config)
    
    def teardown_method(self):
        """Clean up test environment"""
        super().teardown_method()
        
        # Clean up temporary fortune file
        if os.path.exists(self.temp_fortune_file.name):
            os.unlink(self.temp_fortune_file.name)
    
    def test_node_hardware_info_creation(self):
        """Test NodeHardwareInfo creation and methods"""
        node_info = NodeHardwareInfo(
            node_id="!12345678",
            hardware_model="TBEAM",
            firmware_version="2.3.2",
            battery_level=15,
            voltage=3.2,
            role="ROUTER"
        )
        
        assert node_info.node_id == "!12345678"
        assert node_info.hardware_model == "TBEAM"
        assert node_info.battery_level == 15
        assert node_info.is_low_battery() == True
        assert node_info.is_low_battery(20) == True
        assert node_info.is_low_battery(10) == False
    
    def test_uptime_string_formatting(self):
        """Test uptime string formatting"""
        # Test various uptime values
        node_info = NodeHardwareInfo(node_id="!12345678", uptime_seconds=3661)  # 1h 1m 1s
        uptime_str = node_info.get_uptime_string()
        assert uptime_str == "1h 1m"
        
        node_info.uptime_seconds = 90061  # 1d 1h 1m 1s
        uptime_str = node_info.get_uptime_string()
        assert uptime_str == "1d 1h 1m"
        
        node_info.uptime_seconds = 61  # 1m 1s
        uptime_str = node_info.get_uptime_string()
        assert uptime_str == "1m"
        
        node_info.uptime_seconds = None
        uptime_str = node_info.get_uptime_string()
        assert uptime_str == "Unknown"
    
    def test_update_node_hardware(self):
        """Test updating node hardware information"""
        # Create user first (required for foreign key)
        self.create_test_user("!12345678", "TestUser")
        
        hardware_info = {
            'hardware_model': 'TBEAM',
            'firmware_version': '2.3.2',
            'battery_level': 85,
            'voltage': 4.1,
            'role': 'ROUTER',
            'uptime_seconds': 3600
        }
        
        success = self.stats_service.update_node_hardware("!12345678", hardware_info)
        assert success == True
        
        # Retrieve and verify
        node_info = self.stats_service.get_node_hardware("!12345678")
        assert node_info is not None
        assert node_info.node_id == "!12345678"
        assert node_info.hardware_model == "TBEAM"
        assert node_info.battery_level == 85
        assert node_info.role == "ROUTER"
    
    def test_get_nonexistent_node_hardware(self):
        """Test getting hardware info for nonexistent node"""
        node_info = self.stats_service.get_node_hardware("!nonexistent")
        assert node_info is None
    
    def test_get_system_statistics(self):
        """Test getting system statistics"""
        # Add some test data
        self.create_test_user("!12345678", "TestUser1")
        self.create_test_user("!87654321", "TestUser2")
        
        # Add hardware info
        self.stats_service.update_node_hardware("!12345678", {
            'hardware_model': 'TBEAM',
            'battery_level': 85,
            'role': 'ROUTER'
        })
        self.stats_service.update_node_hardware("!87654321", {
            'hardware_model': 'HELTEC',
            'battery_level': 15,
            'role': 'CLIENT'
        })
        
        stats = self.stats_service.get_system_statistics()
        
        assert isinstance(stats, SystemStatistics)
        assert stats.total_nodes == 2
        assert stats.low_battery_nodes == 1
        assert 'ROUTER' in stats.nodes_by_role
        assert 'CLIENT' in stats.nodes_by_role
        assert 'TBEAM' in stats.nodes_by_hardware
        assert 'HELTEC' in stats.nodes_by_hardware
    
    def test_get_low_battery_nodes(self):
        """Test getting low battery nodes (wall of shame)"""
        # Add test nodes with different battery levels
        self.create_test_user("!12345678", "HighBattery")
        self.create_test_user("!87654321", "LowBattery1")
        self.create_test_user("!11111111", "LowBattery2")
        
        self.stats_service.update_node_hardware("!12345678", {'battery_level': 85})
        self.stats_service.update_node_hardware("!87654321", {'battery_level': 15})
        self.stats_service.update_node_hardware("!11111111", {'battery_level': 5})
        
        # Test default threshold (20%)
        low_battery_nodes = self.stats_service.get_low_battery_nodes()
        assert len(low_battery_nodes) == 2
        
        # Verify sorting (lowest battery first)
        assert low_battery_nodes[0].battery_level == 5
        assert low_battery_nodes[1].battery_level == 15
        
        # Test custom threshold
        low_battery_nodes = self.stats_service.get_low_battery_nodes(10)
        assert len(low_battery_nodes) == 1
        assert low_battery_nodes[0].battery_level == 5
    
    def test_fortune_system(self):
        """Test fortune system functionality"""
        # Test getting random fortune
        fortune = self.stats_service.get_random_fortune()
        assert isinstance(fortune, str)
        assert len(fortune) > 0
        
        # Test adding custom fortune
        success = self.stats_service.add_fortune("Test custom fortune", "test", "testuser")
        assert success == True
        
        # Test getting fortune by category
        fortune = self.stats_service.get_random_fortune("test")
        assert isinstance(fortune, str)
    
    def test_fortune_from_file(self):
        """Test loading fortunes from file"""
        # The service should load fortunes from the temp file we created
        fortune = self.stats_service.get_random_fortune()
        assert isinstance(fortune, str)
        
        # Should be one of our test fortunes or default fortunes
        assert len(fortune) > 0
    
    def test_format_statistics_report(self):
        """Test formatting statistics report"""
        stats = SystemStatistics()
        stats.total_nodes = 5
        stats.active_nodes = 3
        stats.nodes_by_role = {'ROUTER': 2, 'CLIENT': 3}
        stats.nodes_by_hardware = {'TBEAM': 3, 'HELTEC': 2}
        stats.low_battery_nodes = 1
        stats.average_battery_level = 75.5
        stats.total_bulletins = 10
        stats.total_mail = 5
        stats.active_sessions = 2
        
        report = self.stats_service.format_statistics_report(stats)
        
        assert "SYSTEM STATISTICS" in report
        assert "Total Nodes: 5" in report
        assert "Active (24h): 3" in report
        assert "ROUTER: 2" in report
        assert "CLIENT: 3" in report
        assert "TBEAM: 3" in report
        assert "Average Level: 75.5%" in report
        assert "Low Battery: 1 nodes" in report
        assert "Bulletins: 10" in report
    
    def test_format_wall_of_shame(self):
        """Test formatting wall of shame report"""
        # Create test nodes
        nodes = [
            NodeHardwareInfo(
                node_id="!12345678",
                battery_level=15,
                hardware_model="TBEAM",
                role="ROUTER"
            ),
            NodeHardwareInfo(
                node_id="!87654321",
                battery_level=5,
                voltage=3.1
            )
        ]
        
        # Add user names
        nodes[0].short_name = "TestNode1"
        nodes[1].short_name = "TestNode2"
        
        report = self.stats_service.format_wall_of_shame(nodes, 20)
        
        assert "WALL OF SHAME" in report
        assert "TestNode1" in report
        assert "TestNode2" in report
        assert "Battery: 15%" in report
        assert "Battery: 5%" in report
        assert "Hardware: TBEAM" in report
        assert "Role: ROUTER" in report
        assert "Voltage: 3.10V" in report
    
    def test_format_wall_of_shame_empty(self):
        """Test formatting wall of shame with no low battery nodes"""
        report = self.stats_service.format_wall_of_shame([], 20)
        
        assert "No nodes with battery below 20%" in report
        assert "Everyone is keeping their devices charged" in report
    
    def test_global_service_instance(self):
        """Test global service instance"""
        service1 = get_statistics_service()
        service2 = get_statistics_service()
        
        # Should return the same instance
        assert service1 is service2
    
    def create_test_user(self, node_id: str, short_name: str):
        """Helper to create test user"""
        query = """
            INSERT INTO users (node_id, short_name, last_seen)
            VALUES (?, ?, ?)
        """
        self.db.execute_update(query, (node_id, short_name, datetime.utcnow().isoformat()))
    
    def create_test_tables(self):
        """Create additional test tables needed for statistics"""
        # Create node_hardware table
        self.db.execute_update("""
            CREATE TABLE IF NOT EXISTS node_hardware (
                node_id TEXT PRIMARY KEY,
                hardware_model TEXT,
                firmware_version TEXT,
                battery_level INTEGER,
                voltage REAL,
                channel_utilization REAL,
                air_util_tx REAL,
                uptime_seconds INTEGER,
                role TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES users (node_id)
            )
        """)
        
        # Create fortunes table
        self.db.execute_update("""
            CREATE TABLE IF NOT EXISTS fortunes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                added_by TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        """)


if __name__ == '__main__':
    pytest.main([__file__])