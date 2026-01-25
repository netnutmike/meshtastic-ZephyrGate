"""
BBS Statistics and Utilities Service for ZephyrGate

Provides system statistics reporting, wall of shame for low battery devices,
and fortune system with configurable fortune file support.
"""

import logging
import random
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from core.database import get_database, DatabaseError
from .database import get_bbs_database


@dataclass
class NodeHardwareInfo:
    """Node hardware information"""
    node_id: str
    hardware_model: str = ""
    firmware_version: str = ""
    battery_level: Optional[int] = None
    voltage: Optional[float] = None
    channel_utilization: Optional[float] = None
    air_util_tx: Optional[float] = None
    uptime_seconds: Optional[int] = None
    role: str = "CLIENT"
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()
    
    def is_low_battery(self, threshold: int = 20) -> bool:
        """Check if node has low battery"""
        return self.battery_level is not None and self.battery_level <= threshold
    
    def get_uptime_string(self) -> str:
        """Get human-readable uptime"""
        if self.uptime_seconds is None:
            return "Unknown"
        
        days = self.uptime_seconds // 86400
        hours = (self.uptime_seconds % 86400) // 3600
        minutes = (self.uptime_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


@dataclass
class SystemStatistics:
    """System statistics data"""
    total_nodes: int = 0
    active_nodes: int = 0  # Seen in last 24 hours
    nodes_by_role: Dict[str, int] = None
    nodes_by_hardware: Dict[str, int] = None
    low_battery_nodes: int = 0
    average_battery_level: Optional[float] = None
    total_bulletins: int = 0
    total_mail: int = 0
    unread_mail: int = 0
    active_channels: int = 0
    js8call_messages: int = 0
    active_sessions: int = 0
    
    def __post_init__(self):
        if self.nodes_by_role is None:
            self.nodes_by_role = {}
        if self.nodes_by_hardware is None:
            self.nodes_by_hardware = {}


class StatisticsService:
    """BBS statistics and utilities service"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        self.bbs_db = get_bbs_database()
        self.config = config or {}
        
        # Fortune system configuration
        self.fortune_file = self.config.get('fortune_file', 'data/fortunes.txt')
        self.default_fortunes = [
            "The best way to predict the future is to invent it. - Alan Kay",
            "In the world of mesh networking, every node matters.",
            "Communication is the key to community resilience.",
            "When the internet fails, the mesh prevails.",
            "73 and keep meshing!",
            "A mesh network is only as strong as its weakest link.",
            "Redundancy is the mother of reliability.",
            "In emergency communications, preparation meets opportunity.",
            "The mesh connects us all, one hop at a time.",
            "Digital modes: because sometimes less is more."
        ]
        
        # Initialize fortune database if needed
        self._initialize_fortunes()
    
    def update_node_hardware(self, node_id: str, hardware_info: Dict[str, Any]) -> bool:
        """Update node hardware information"""
        try:
            # Extract hardware information
            hardware_model = hardware_info.get('hardware_model', '')
            firmware_version = hardware_info.get('firmware_version', '')
            battery_level = hardware_info.get('battery_level')
            voltage = hardware_info.get('voltage')
            channel_utilization = hardware_info.get('channel_utilization')
            air_util_tx = hardware_info.get('air_util_tx')
            uptime_seconds = hardware_info.get('uptime_seconds')
            role = hardware_info.get('role', 'CLIENT')
            
            # Insert or update node hardware information
            query = """
                INSERT OR REPLACE INTO node_hardware 
                (node_id, hardware_model, firmware_version, battery_level, voltage,
                 channel_utilization, air_util_tx, uptime_seconds, role, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            affected = self.db.execute_update(query, (
                node_id, hardware_model, firmware_version, battery_level, voltage,
                channel_utilization, air_util_tx, uptime_seconds, role,
                datetime.utcnow().isoformat()
            ))
            
            if affected > 0:
                self.logger.debug(f"Updated hardware info for node {node_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update node hardware for {node_id}: {e}")
            return False
    
    def get_node_hardware(self, node_id: str) -> Optional[NodeHardwareInfo]:
        """Get node hardware information"""
        try:
            query = "SELECT * FROM node_hardware WHERE node_id = ?"
            rows = self.db.execute_query(query, (node_id,))
            
            if rows:
                row = rows[0]
                return NodeHardwareInfo(
                    node_id=row['node_id'],
                    hardware_model=row['hardware_model'] or '',
                    firmware_version=row['firmware_version'] or '',
                    battery_level=row['battery_level'],
                    voltage=row['voltage'],
                    channel_utilization=row['channel_utilization'],
                    air_util_tx=row['air_util_tx'],
                    uptime_seconds=row['uptime_seconds'],
                    role=row['role'] or 'CLIENT',
                    last_updated=datetime.fromisoformat(row['last_updated']) if row['last_updated'] else datetime.utcnow()
                )
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get node hardware for {node_id}: {e}")
            return None
    
    def get_system_statistics(self) -> SystemStatistics:
        """Get comprehensive system statistics"""
        try:
            stats = SystemStatistics()
            
            # Get basic BBS statistics
            bbs_stats = self.bbs_db.get_statistics()
            stats.total_bulletins = bbs_stats.get('total_bulletins', 0)
            stats.total_mail = bbs_stats.get('total_mail', 0)
            stats.unread_mail = bbs_stats.get('unread_mail', 0)
            stats.active_channels = bbs_stats.get('active_channels', 0)
            stats.js8call_messages = bbs_stats.get('js8call', {}).get('total_messages', 0)
            
            # Get node statistics
            self._get_node_statistics(stats)
            
            # Get hardware statistics
            self._get_hardware_statistics(stats)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get system statistics: {e}")
            return SystemStatistics()
    
    def _get_node_statistics(self, stats: SystemStatistics):
        """Get node-related statistics"""
        try:
            # Total nodes
            total_rows = self.db.execute_query("SELECT COUNT(*) FROM users")
            stats.total_nodes = total_rows[0][0] if total_rows else 0
            
            # Active nodes (seen in last 24 hours)
            yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
            active_rows = self.db.execute_query(
                "SELECT COUNT(*) FROM users WHERE last_seen > ?", (yesterday,)
            )
            stats.active_nodes = active_rows[0][0] if active_rows else 0
            
        except Exception as e:
            self.logger.error(f"Failed to get node statistics: {e}")
    
    def _get_hardware_statistics(self, stats: SystemStatistics):
        """Get hardware-related statistics"""
        try:
            # Nodes by role
            role_rows = self.db.execute_query("""
                SELECT role, COUNT(*) 
                FROM node_hardware 
                GROUP BY role
            """)
            stats.nodes_by_role = {row[0]: row[1] for row in role_rows}
            
            # Nodes by hardware model
            hardware_rows = self.db.execute_query("""
                SELECT hardware_model, COUNT(*) 
                FROM node_hardware 
                WHERE hardware_model != ''
                GROUP BY hardware_model
            """)
            stats.nodes_by_hardware = {row[0]: row[1] for row in hardware_rows}
            
            # Low battery nodes
            low_battery_rows = self.db.execute_query("""
                SELECT COUNT(*) 
                FROM node_hardware 
                WHERE battery_level IS NOT NULL AND battery_level <= 20
            """)
            stats.low_battery_nodes = low_battery_rows[0][0] if low_battery_rows else 0
            
            # Average battery level
            avg_battery_rows = self.db.execute_query("""
                SELECT AVG(battery_level) 
                FROM node_hardware 
                WHERE battery_level IS NOT NULL
            """)
            if avg_battery_rows and avg_battery_rows[0][0] is not None:
                stats.average_battery_level = round(avg_battery_rows[0][0], 1)
            
        except Exception as e:
            self.logger.error(f"Failed to get hardware statistics: {e}")
    
    def get_low_battery_nodes(self, threshold: int = 20) -> List[NodeHardwareInfo]:
        """Get nodes with low battery levels (wall of shame)"""
        try:
            query = """
                SELECT nh.*, u.short_name, u.long_name
                FROM node_hardware nh
                LEFT JOIN users u ON nh.node_id = u.node_id
                WHERE nh.battery_level IS NOT NULL AND nh.battery_level <= ?
                ORDER BY nh.battery_level ASC, nh.last_updated DESC
            """
            
            rows = self.db.execute_query(query, (threshold,))
            
            low_battery_nodes = []
            for row in rows:
                node_info = NodeHardwareInfo(
                    node_id=row['node_id'],
                    hardware_model=row['hardware_model'] or '',
                    firmware_version=row['firmware_version'] or '',
                    battery_level=row['battery_level'],
                    voltage=row['voltage'],
                    channel_utilization=row['channel_utilization'],
                    air_util_tx=row['air_util_tx'],
                    uptime_seconds=row['uptime_seconds'],
                    role=row['role'] or 'CLIENT',
                    last_updated=datetime.fromisoformat(row['last_updated']) if row['last_updated'] else datetime.utcnow()
                )
                # Add user info if available - set as attributes on the object
                try:
                    if row['short_name']:
                        setattr(node_info, 'short_name', row['short_name'])
                except (KeyError, IndexError):
                    pass
                try:
                    if row['long_name']:
                        setattr(node_info, 'long_name', row['long_name'])
                except (KeyError, IndexError):
                    pass
                
                low_battery_nodes.append(node_info)
            
            return low_battery_nodes
            
        except Exception as e:
            self.logger.error(f"Failed to get low battery nodes: {e}")
            return []
    
    def get_random_fortune(self, category: str = None) -> str:
        """Get a random fortune message"""
        try:
            # Try to get fortune from database first
            if category:
                query = "SELECT message FROM fortunes WHERE active = 1 AND category = ? ORDER BY RANDOM() LIMIT 1"
                rows = self.db.execute_query(query, (category,))
            else:
                query = "SELECT message FROM fortunes WHERE active = 1 ORDER BY RANDOM() LIMIT 1"
                rows = self.db.execute_query(query)
            
            if rows:
                return rows[0][0]
            
            # Fall back to file-based fortunes
            fortune_from_file = self._get_fortune_from_file()
            if fortune_from_file:
                return fortune_from_file
            
            # Fall back to default fortunes
            return random.choice(self.default_fortunes)
            
        except Exception as e:
            self.logger.error(f"Failed to get random fortune: {e}")
            return random.choice(self.default_fortunes)
    
    def add_fortune(self, message: str, category: str = 'general', added_by: str = None) -> bool:
        """Add a new fortune message"""
        try:
            query = """
                INSERT INTO fortunes (message, category, added_by, added_at)
                VALUES (?, ?, ?, ?)
            """
            
            affected = self.db.execute_update(query, (
                message.strip(), category, added_by, datetime.utcnow().isoformat()
            ))
            
            if affected > 0:
                self.logger.info(f"Added fortune: {message[:50]}...")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to add fortune: {e}")
            return False
    
    def _initialize_fortunes(self):
        """Initialize fortune database with default fortunes"""
        try:
            # Check if we have any fortunes in the database
            count_rows = self.db.execute_query("SELECT COUNT(*) FROM fortunes WHERE active = 1")
            if count_rows and count_rows[0][0] > 0:
                return  # Already have fortunes
            
            # Add default fortunes
            for fortune in self.default_fortunes:
                self.add_fortune(fortune, 'default', 'system')
            
            # Try to load fortunes from file
            self._load_fortunes_from_file()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize fortunes: {e}")
    
    def _load_fortunes_from_file(self):
        """Load fortunes from configured fortune file"""
        try:
            fortune_path = Path(self.fortune_file)
            if not fortune_path.exists():
                self.logger.debug(f"Fortune file not found: {fortune_path}")
                return
            
            with open(fortune_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split fortunes by double newline or % delimiter (common fortune format)
            if '%' in content:
                fortunes = [f.strip() for f in content.split('%') if f.strip()]
            else:
                fortunes = [f.strip() for f in content.split('\n\n') if f.strip()]
            
            # Add fortunes to database
            for fortune in fortunes:
                if fortune and len(fortune) > 10:  # Skip very short entries
                    self.add_fortune(fortune, 'file', 'system')
            
            self.logger.info(f"Loaded {len(fortunes)} fortunes from {fortune_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load fortunes from file: {e}")
    
    def _get_fortune_from_file(self) -> Optional[str]:
        """Get a random fortune directly from file (fallback)"""
        try:
            fortune_path = Path(self.fortune_file)
            if not fortune_path.exists():
                return None
            
            with open(fortune_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split fortunes by double newline or % delimiter
            if '%' in content:
                fortunes = [f.strip() for f in content.split('%') if f.strip()]
            else:
                fortunes = [f.strip() for f in content.split('\n\n') if f.strip()]
            
            if fortunes:
                return random.choice(fortunes)
            
        except Exception as e:
            self.logger.debug(f"Could not read fortune from file: {e}")
        
        return None
    
    def format_statistics_report(self, stats: SystemStatistics) -> str:
        """Format statistics into a readable report"""
        lines = []
        lines.append("=== SYSTEM STATISTICS ===")
        lines.append("")
        
        # Node statistics
        lines.append("📡 Node Information:")
        lines.append(f"  Total Nodes: {stats.total_nodes}")
        lines.append(f"  Active (24h): {stats.active_nodes}")
        
        if stats.nodes_by_role:
            lines.append("  Roles:")
            for role, count in sorted(stats.nodes_by_role.items()):
                lines.append(f"    {role}: {count}")
        
        if stats.nodes_by_hardware:
            lines.append("  Hardware:")
            for hw, count in sorted(stats.nodes_by_hardware.items()):
                lines.append(f"    {hw}: {count}")
        
        # Battery statistics
        if stats.average_battery_level is not None:
            lines.append("")
            lines.append("🔋 Battery Status:")
            lines.append(f"  Average Level: {stats.average_battery_level}%")
            lines.append(f"  Low Battery: {stats.low_battery_nodes} nodes")
        
        # BBS statistics
        lines.append("")
        lines.append("📋 BBS Statistics:")
        lines.append(f"  Bulletins: {stats.total_bulletins}")
        lines.append(f"  Mail Messages: {stats.total_mail}")
        lines.append(f"  Unread Mail: {stats.unread_mail}")
        lines.append(f"  Channels: {stats.active_channels}")
        
        if stats.js8call_messages > 0:
            lines.append(f"  JS8Call Messages: {stats.js8call_messages}")
        
        lines.append(f"  Active Sessions: {stats.active_sessions}")
        
        return "\n".join(lines)
    
    def format_wall_of_shame(self, low_battery_nodes: List[NodeHardwareInfo], threshold: int = 20) -> str:
        """Format wall of shame report for low battery nodes"""
        if not low_battery_nodes:
            return f"🎉 No nodes with battery below {threshold}%! Everyone is keeping their devices charged."
        
        lines = []
        lines.append(f"⚠️  WALL OF SHAME - Low Battery Nodes (≤{threshold}%)")
        lines.append("=" * 50)
        lines.append("")
        
        for i, node in enumerate(low_battery_nodes, 1):
            name = getattr(node, 'short_name', node.node_id)
            if hasattr(node, 'long_name') and node.long_name:
                name = f"{name} ({node.long_name})"
            
            battery_icon = "🔴" if node.battery_level <= 10 else "🟡"
            lines.append(f"{i:2}. {battery_icon} {name}")
            lines.append(f"    Battery: {node.battery_level}%")
            if node.voltage:
                lines.append(f"    Voltage: {node.voltage:.2f}V")
            if node.hardware_model:
                lines.append(f"    Hardware: {node.hardware_model}")
            if node.role != 'CLIENT':
                lines.append(f"    Role: {node.role}")
            
            # Time since last update
            if node.last_updated:
                delta = datetime.utcnow() - node.last_updated
                if delta.days > 0:
                    time_str = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    time_str = f"{delta.seconds // 3600}h ago"
                else:
                    time_str = f"{delta.seconds // 60}m ago"
                lines.append(f"    Last seen: {time_str}")
            
            lines.append("")
        
        lines.append("💡 Tip: Keep your devices charged for better mesh reliability!")
        
        return "\n".join(lines)


# Global instance
_statistics_service = None

def get_statistics_service(config: Optional[Dict[str, Any]] = None) -> StatisticsService:
    """Get global statistics service instance"""
    global _statistics_service
    if _statistics_service is None:
        _statistics_service = StatisticsService(config)
    return _statistics_service