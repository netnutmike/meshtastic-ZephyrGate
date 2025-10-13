"""
Integration tests for BBS Statistics functionality

Tests the complete statistics system including menu integration,
database operations, and report formatting.
"""

import pytest
import tempfile
import os
from datetime import datetime

from src.core.database import initialize_database, get_database
from src.services.bbs.menu_system import BBSMenuSystem
from src.services.bbs.statistics_service import get_statistics_service
from tests.base import BaseTestCase


class TestStatisticsIntegration(BaseTestCase):
    """Integration tests for statistics functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        super().setup_method()
        
        # Initialize database
        initialize_database(':memory:')
        self.db = get_database()
        
        # Create BBS menu system
        self.menu_system = BBSMenuSystem()
        
        # Create test data
        self.create_test_data()
    
    def create_test_data(self):
        """Create test data for statistics"""
        # Create test users
        users = [
            ("!12345678", "TestUser1", "Test User One"),
            ("!87654321", "TestUser2", "Test User Two"),
            ("!11111111", "TestUser3", "Test User Three"),
        ]
        
        for node_id, short_name, long_name in users:
            query = """
                INSERT INTO users (node_id, short_name, long_name, last_seen)
                VALUES (?, ?, ?, ?)
            """
            self.db.execute_update(query, (
                node_id, short_name, long_name, datetime.utcnow().isoformat()
            ))
        
        # Add hardware information
        stats_service = get_statistics_service()
        stats_service.update_node_hardware("!12345678", {
            'hardware_model': 'TBEAM',
            'battery_level': 85,
            'role': 'ROUTER',
            'firmware_version': '2.3.2'
        })
        stats_service.update_node_hardware("!87654321", {
            'hardware_model': 'HELTEC',
            'battery_level': 15,  # Low battery
            'role': 'CLIENT'
        })
        stats_service.update_node_hardware("!11111111", {
            'hardware_model': 'TBEAM',
            'battery_level': 5,   # Very low battery
            'role': 'CLIENT'
        })    

    def test_statistics_menu_command(self):
        """Test statistics command through menu system"""
        session = self.menu_system.get_session("!12345678")
        
        # Navigate to utilities menu
        response = self.menu_system.process_command("!12345678", "utilities")
        assert "UTILITIES MENU" in response
        
        # Execute stats command
        response = self.menu_system.process_command("!12345678", "stats")
        
        # Verify statistics report content
        assert "SYSTEM STATISTICS" in response
        assert "Total Nodes: 3" in response
        assert "ROUTER: 1" in response
        assert "CLIENT: 2" in response
        assert "TBEAM: 2" in response
        assert "HELTEC: 1" in response
        assert "Low Battery: 2 nodes" in response
    
    def test_wall_of_shame_menu_command(self):
        """Test wall of shame command through menu system"""
        session = self.menu_system.get_session("!12345678")
        
        # Navigate to utilities menu
        self.menu_system.process_command("!12345678", "utilities")
        
        # Execute shame command
        response = self.menu_system.process_command("!12345678", "shame")
        
        # Verify wall of shame content
        assert "WALL OF SHAME" in response
        assert "TestUser3" in response  # User with 5% battery
        assert "TestUser2" in response  # User with 15% battery
        assert "Battery: 5%" in response
        assert "Battery: 15%" in response
        
        # Test with custom threshold
        response = self.menu_system.process_command("!12345678", "shame 10")
        assert "TestUser3" in response  # Only 5% battery user
        assert "TestUser2" not in response  # 15% is above 10% threshold
    
    def test_fortune_menu_command(self):
        """Test fortune command through menu system"""
        session = self.menu_system.get_session("!12345678")
        
        # Navigate to utilities menu
        self.menu_system.process_command("!12345678", "utilities")
        
        # Execute fortune command
        response = self.menu_system.process_command("!12345678", "fortune")
        
        # Verify fortune response
        assert "🔮 Fortune:" in response
        assert len(response) > 20  # Should have actual fortune content
    
    def test_statistics_service_integration(self):
        """Test statistics service integration with database"""
        stats_service = get_statistics_service()
        
        # Test system statistics
        stats = stats_service.get_system_statistics()
        assert stats.total_nodes == 3
        assert stats.low_battery_nodes == 2
        assert 'ROUTER' in stats.nodes_by_role
        assert 'CLIENT' in stats.nodes_by_role
        assert stats.nodes_by_role['ROUTER'] == 1
        assert stats.nodes_by_role['CLIENT'] == 2
        
        # Test low battery nodes
        low_battery_nodes = stats_service.get_low_battery_nodes(20)
        assert len(low_battery_nodes) == 2
        
        # Verify sorting (lowest battery first)
        assert low_battery_nodes[0].battery_level == 5
        assert low_battery_nodes[1].battery_level == 15
        
        # Test fortune system
        fortune = stats_service.get_random_fortune()
        assert isinstance(fortune, str)
        assert len(fortune) > 0
    
    def test_menu_navigation_with_statistics(self):
        """Test complete menu navigation to statistics"""
        # Start from main menu
        response = self.menu_system.process_command("!12345678", "help")
        assert "MAIN MENU" in response
        
        # Go to utilities
        response = self.menu_system.process_command("!12345678", "utilities")
        assert "UTILITIES MENU" in response
        assert "stats" in response.lower()
        assert "shame" in response.lower()
        assert "fortune" in response.lower()
        
        # Test each statistics command
        commands = ["stats", "shame", "fortune"]
        for cmd in commands:
            response = self.menu_system.process_command("!12345678", cmd)
            assert len(response) > 10  # Should have meaningful content
            
            # Verify we're still in utilities menu after command
            session = self.menu_system.get_session("!12345678")
            assert session.current_menu == "utilities"


if __name__ == '__main__':
    pytest.main([__file__])