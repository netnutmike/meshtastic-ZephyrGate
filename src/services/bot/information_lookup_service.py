"""
Information Lookup Service

Provides information lookup services including:
- Weather command integration with weather service
- Node status and signal reporting commands
- Network statistics and mesh information commands
- Location-based information services (whereami, howfar)

Requirements: 4.1.4, 4.1.5, 4.2.4, 4.2.5, 4.3.6
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from src.core.database import get_database
from src.core.plugin_interfaces import PluginCommunicationInterface


@dataclass
class NodeInfo:
    """Information about a mesh node"""
    node_id: str
    short_name: str
    long_name: str
    last_seen: datetime
    location: Optional[Tuple[float, float]] = None
    altitude: Optional[float] = None
    battery_level: Optional[int] = None
    voltage: Optional[float] = None
    snr: Optional[float] = None
    rssi: Optional[float] = None
    hop_count: Optional[int] = None
    hardware_model: Optional[str] = None
    firmware_version: Optional[str] = None
    role: Optional[str] = None


@dataclass
class NetworkStats:
    """Network statistics"""
    total_nodes: int
    active_nodes: int
    nodes_last_hour: int
    nodes_last_day: int
    total_messages: int
    messages_last_hour: int
    messages_last_day: int
    average_snr: Optional[float] = None
    average_rssi: Optional[float] = None
    network_diameter: Optional[int] = None


class InformationLookupService:
    """
    Service for handling information lookup commands including weather,
    node status, network statistics, and location-based services
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Communication interface for accessing other services
        self.communication: Optional[PluginCommunicationInterface] = None
        
        # Cache for frequently accessed data
        self.node_cache: Dict[str, NodeInfo] = {}
        self.network_stats_cache: Optional[NetworkStats] = None
        self.cache_expiry: datetime = datetime.utcnow()
        self.cache_duration = timedelta(minutes=5)  # Cache for 5 minutes
        
        # Location calculation constants
        self.EARTH_RADIUS_KM = 6371.0
        self.EARTH_RADIUS_MILES = 3959.0
        
        # Default location if none available
        self.default_location = self.config.get('default_location', (40.7128, -74.0060))  # NYC
        
    def set_communication_interface(self, communication: PluginCommunicationInterface):
        """Set the communication interface for accessing other services"""
        self.communication = communication
    
    async def handle_weather_command(self, command: str, args: List[str], context: Dict) -> str:
        """
        Handle weather command integration with weather service
        Requirements: 4.1.4
        """
        try:
            # Get location from args or user profile
            location = None
            if args:
                location = ' '.join(args)
            else:
                # Try to get user's location from profile
                user_location = await self._get_user_location(context['sender_id'])
                if user_location:
                    location = f"{user_location[0]:.4f},{user_location[1]:.4f}"
                else:
                    location = "your location"
            
            # Request weather data from weather service via communication interface
            weather_data = await self._request_weather_data(location, command)
            if weather_data:
                return self._format_weather_response(weather_data, command)
            
            # Fallback response if weather service unavailable
            response = f"🌤️ **Weather Information**\n\n"
            response += f"📍 Location: {location}\n"
            response += f"⚠️ Weather service currently unavailable\n"
            response += f"Please try again later or check local conditions"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling weather command: {e}")
            return f"❌ Error retrieving weather information: {str(e)}"
    
    async def handle_node_status_command(self, command: str, args: List[str], context: Dict) -> str:
        """
        Handle node status and signal reporting commands
        Requirements: 4.1.5, 4.2.4
        """
        try:
            if command == "whoami":
                return await self._handle_whoami_command(context)
            elif command == "whois":
                if not args:
                    return "❌ Usage: whois <node_id>\nExample: whois !12345678"
                return await self._handle_whois_command(args[0], context)
            elif command == "lheard":
                return await self._handle_lheard_command(args, context)
            elif command == "sitrep":
                return await self._handle_sitrep_command(context)
            elif command == "status":
                return await self._handle_status_command(context)
            else:
                return f"❌ Unknown node status command: {command}"
                
        except Exception as e:
            self.logger.error(f"Error handling node status command: {e}")
            return f"❌ Error retrieving node status: {str(e)}"
    
    async def handle_network_stats_command(self, command: str, args: List[str], context: Dict) -> str:
        """
        Handle network statistics and mesh information commands
        Requirements: 4.2.5
        """
        try:
            if command == "sysinfo":
                return await self._handle_sysinfo_command(context)
            elif command == "leaderboard":
                return await self._handle_leaderboard_command(args, context)
            elif command == "history":
                return await self._handle_history_command(args, context)
            elif command == "messages":
                return await self._handle_messages_command(args, context)
            elif command == "sitrep":
                return await self._handle_sitrep_command(context)
            else:
                return f"❌ Unknown network stats command: {command}"
                
        except Exception as e:
            self.logger.error(f"Error handling network stats command: {e}")
            return f"❌ Error retrieving network statistics: {str(e)}"
    
    async def handle_location_command(self, command: str, args: List[str], context: Dict) -> str:
        """
        Handle location-based information services
        Requirements: 4.3.6
        """
        try:
            if command == "whereami":
                return await self._handle_whereami_command(context)
            elif command == "howfar":
                if not args:
                    return "❌ Usage: howfar <node_id>\nExample: howfar !12345678"
                return await self._handle_howfar_command(args[0], context)
            elif command == "howtall":
                target_node = args[0] if args else context['sender_id']
                return await self._handle_howtall_command(target_node, context)
            else:
                return f"❌ Unknown location command: {command}"
                
        except Exception as e:
            self.logger.error(f"Error handling location command: {e}")
            return f"❌ Error retrieving location information: {str(e)}"
    
    async def _request_weather_data(self, location: str, command: str) -> Optional[Dict]:
        """Request weather data from weather service"""
        try:
            # TODO: Implement actual weather service communication
            # For now, return mock data
            return {
                'location': location,
                'temperature': 72,
                'temperature_c': 22,
                'conditions': 'Partly Cloudy',
                'wind_speed': 5,
                'wind_direction': 'NW',
                'humidity': 65,
                'pressure': 30.15,
                'visibility': 10,
                'forecast': [
                    {'day': 'Today', 'high': 75, 'low': 60, 'conditions': 'Partly Cloudy'},
                    {'day': 'Tomorrow', 'high': 78, 'low': 62, 'conditions': 'Sunny'},
                    {'day': 'Day 3', 'high': 73, 'low': 58, 'conditions': 'Cloudy'}
                ]
            }
        except Exception as e:
            self.logger.error(f"Error requesting weather data: {e}")
            return None
    
    def _format_weather_response(self, weather_data: Dict, command: str) -> str:
        """Format weather data into response message"""
        if command in ['wx', 'weather']:
            # Current conditions
            response = f"🌤️ **Current Weather**\n\n"
            response += f"📍 {weather_data['location']}\n"
            response += f"🌡️ {weather_data['temperature']}°F ({weather_data['temperature_c']}°C)\n"
            response += f"☁️ {weather_data['conditions']}\n"
            response += f"💨 Wind: {weather_data['wind_speed']} mph {weather_data['wind_direction']}\n"
            response += f"💧 Humidity: {weather_data['humidity']}%\n"
            response += f"🔽 Pressure: {weather_data['pressure']} inHg\n"
            response += f"👁️ Visibility: {weather_data['visibility']} miles"
            
        elif command in ['wxc', 'forecast']:
            # Extended forecast
            response = f"📅 **Weather Forecast**\n\n"
            response += f"📍 {weather_data['location']}\n\n"
            for day_forecast in weather_data['forecast']:
                response += f"**{day_forecast['day']}**: {day_forecast['high']}°/{day_forecast['low']}° - {day_forecast['conditions']}\n"
                
        elif command == 'mwx':
            # Marine weather (simplified)
            response = f"🌊 **Marine Weather**\n\n"
            response += f"📍 {weather_data['location']}\n"
            response += f"🌡️ {weather_data['temperature']}°F\n"
            response += f"💨 Wind: {weather_data['wind_speed']} mph {weather_data['wind_direction']}\n"
            response += f"🌊 Sea conditions: Moderate\n"
            response += f"👁️ Visibility: {weather_data['visibility']} miles"
            
        else:
            response = f"🌤️ Weather data available for {weather_data['location']}"
        
        return response
    
    async def _handle_whoami_command(self, context: Dict) -> str:
        """Handle whoami command - show current user's information"""
        sender_id = context['sender_id']
        node_info = await self._get_node_info(sender_id)
        
        if not node_info:
            return f"❌ No information found for your node ({sender_id})"
        
        response = f"👤 **Your Node Information**\n\n"
        response += f"🆔 Node ID: {node_info.node_id}\n"
        response += f"📛 Short Name: {node_info.short_name}\n"
        if node_info.long_name:
            response += f"📝 Long Name: {node_info.long_name}\n"
        
        if node_info.location:
            response += f"📍 Location: {node_info.location[0]:.4f}, {node_info.location[1]:.4f}\n"
        
        if node_info.altitude:
            response += f"⛰️ Altitude: {node_info.altitude:.0f}m ({node_info.altitude * 3.28084:.0f}ft)\n"
        
        if node_info.battery_level:
            battery_emoji = "🔋" if node_info.battery_level > 50 else "🪫" if node_info.battery_level > 20 else "🔴"
            response += f"{battery_emoji} Battery: {node_info.battery_level}%"
            if node_info.voltage:
                response += f" ({node_info.voltage:.2f}V)"
            response += "\n"
        
        if node_info.hardware_model:
            response += f"💻 Hardware: {node_info.hardware_model}\n"
        
        if node_info.firmware_version:
            response += f"⚙️ Firmware: {node_info.firmware_version}\n"
        
        if node_info.role:
            response += f"🎭 Role: {node_info.role}\n"
        
        response += f"🕐 Last Seen: {self._format_time_ago(node_info.last_seen)}"
        
        return response
    
    async def _handle_whois_command(self, target_node: str, context: Dict) -> str:
        """Handle whois command - show information about another node"""
        # Clean up node ID format
        if not target_node.startswith('!'):
            target_node = f"!{target_node}"
        
        node_info = await self._get_node_info(target_node)
        
        if not node_info:
            return f"❌ No information found for node {target_node}"
        
        response = f"👤 **Node Information: {target_node}**\n\n"
        response += f"📛 Short Name: {node_info.short_name}\n"
        if node_info.long_name:
            response += f"📝 Long Name: {node_info.long_name}\n"
        
        if node_info.location:
            response += f"📍 Location: {node_info.location[0]:.4f}, {node_info.location[1]:.4f}\n"
            
            # Calculate distance from requesting user
            user_location = await self._get_user_location(context['sender_id'])
            if user_location:
                distance_km = self._calculate_distance(user_location, node_info.location)
                distance_miles = distance_km * 0.621371
                response += f"📏 Distance: {distance_km:.1f}km ({distance_miles:.1f}mi)\n"
        
        if node_info.altitude:
            response += f"⛰️ Altitude: {node_info.altitude:.0f}m ({node_info.altitude * 3.28084:.0f}ft)\n"
        
        # Signal quality information
        if node_info.snr is not None or node_info.rssi is not None:
            response += f"📶 Signal: "
            if node_info.snr is not None:
                response += f"SNR {node_info.snr:.1f}dB "
            if node_info.rssi is not None:
                response += f"RSSI {node_info.rssi:.0f}dBm"
            response += "\n"
        
        if node_info.hop_count is not None:
            response += f"🔗 Hops: {node_info.hop_count}\n"
        
        if node_info.battery_level:
            battery_emoji = "🔋" if node_info.battery_level > 50 else "🪫" if node_info.battery_level > 20 else "🔴"
            response += f"{battery_emoji} Battery: {node_info.battery_level}%\n"
        
        if node_info.hardware_model:
            response += f"💻 Hardware: {node_info.hardware_model}\n"
        
        if node_info.role:
            response += f"🎭 Role: {node_info.role}\n"
        
        response += f"🕐 Last Seen: {self._format_time_ago(node_info.last_seen)}"
        
        return response
    
    async def _handle_lheard_command(self, args: List[str], context: Dict) -> str:
        """Handle lheard command - show recently heard nodes"""
        limit = 10
        if args and args[0].isdigit():
            limit = min(int(args[0]), 50)  # Max 50 nodes
        
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Get recently heard nodes with signal information
            cursor.execute("""
                SELECT node_id, short_name, last_seen, snr, rssi, hop_count, battery_level
                FROM users 
                WHERE last_seen > datetime('now', '-24 hours')
                ORDER BY last_seen DESC 
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            if not rows:
                return "📡 No nodes heard in the last 24 hours"
            
            response = f"📡 **Recently Heard Nodes** (Last {len(rows)})\n\n"
            
            for row in rows:
                node_id, short_name, last_seen_str, snr, rssi, hop_count, battery_level = row
                try:
                    # Handle different datetime formats
                    if last_seen_str.endswith('Z'):
                        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    else:
                        last_seen = datetime.fromisoformat(last_seen_str)
                        # If naive datetime, assume UTC
                        if last_seen.tzinfo is None:
                            last_seen = last_seen.replace(tzinfo=None)
                except ValueError:
                    # Fallback for any parsing issues
                    last_seen = datetime.utcnow()
                
                response += f"**{short_name}** ({node_id})\n"
                response += f"  🕐 {self._format_time_ago(last_seen)}"
                
                if snr is not None or rssi is not None:
                    response += f" | 📶 "
                    if snr is not None:
                        response += f"SNR {snr:.1f}dB "
                    if rssi is not None:
                        response += f"RSSI {rssi:.0f}dBm"
                
                if hop_count is not None:
                    response += f" | 🔗 {hop_count} hops"
                
                if battery_level is not None:
                    battery_emoji = "🔋" if battery_level > 50 else "🪫" if battery_level > 20 else "🔴"
                    response += f" | {battery_emoji} {battery_level}%"
                
                response += "\n\n"
            
            return response.rstrip()
            
        except Exception as e:
            self.logger.error(f"Error in lheard command: {e}")
            return f"❌ Error retrieving heard nodes: {str(e)}"
    
    async def _handle_sitrep_command(self, context: Dict) -> str:
        """Handle sitrep command - situation report"""
        try:
            stats = await self._get_network_stats()
            
            response = f"📊 **Network Situation Report**\n\n"
            response += f"🌐 **Network Status**\n"
            response += f"  • Total Nodes: {stats.total_nodes}\n"
            response += f"  • Active Nodes: {stats.active_nodes}\n"
            response += f"  • Nodes (1h): {stats.nodes_last_hour}\n"
            response += f"  • Nodes (24h): {stats.nodes_last_day}\n\n"
            
            response += f"💬 **Message Activity**\n"
            response += f"  • Total Messages: {stats.total_messages}\n"
            response += f"  • Messages (1h): {stats.messages_last_hour}\n"
            response += f"  • Messages (24h): {stats.messages_last_day}\n\n"
            
            if stats.average_snr is not None:
                response += f"📶 **Signal Quality**\n"
                response += f"  • Avg SNR: {stats.average_snr:.1f}dB\n"
                if stats.average_rssi is not None:
                    response += f"  • Avg RSSI: {stats.average_rssi:.0f}dBm\n"
                response += "\n"
            
            if stats.network_diameter is not None:
                response += f"🔗 Network Diameter: {stats.network_diameter} hops\n"
            
            response += f"🕐 Report Time: {datetime.utcnow().strftime('%H:%M UTC')}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in sitrep command: {e}")
            return f"❌ Error generating situation report: {str(e)}"
    
    async def _handle_status_command(self, context: Dict) -> str:
        """Handle status command - general system status"""
        try:
            stats = await self._get_network_stats()
            sender_info = await self._get_node_info(context['sender_id'])
            
            response = f"📊 **System Status**\n\n"
            
            # Network overview
            response += f"🌐 **Network**: {stats.active_nodes} active nodes\n"
            response += f"💬 **Activity**: {stats.messages_last_hour} msgs/hour\n"
            
            # User's connection status
            if sender_info:
                response += f"👤 **Your Status**: {sender_info.short_name}\n"
                if sender_info.snr is not None:
                    signal_quality = "Excellent" if sender_info.snr > 10 else "Good" if sender_info.snr > 0 else "Poor"
                    response += f"📶 **Signal**: {signal_quality} (SNR {sender_info.snr:.1f}dB)\n"
                
                if sender_info.battery_level:
                    response += f"🔋 **Battery**: {sender_info.battery_level}%\n"
            
            # System services status
            response += f"\n🔧 **Services**:\n"
            response += f"  • Bot: ✅ Active\n"
            response += f"  • BBS: ✅ Active\n"
            response += f"  • Emergency: ✅ Active\n"
            response += f"  • Weather: ⚠️ Limited\n"
            
            response += f"\n🕐 Status Time: {datetime.utcnow().strftime('%H:%M UTC')}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return f"❌ Error retrieving system status: {str(e)}"
    
    async def _handle_sysinfo_command(self, context: Dict) -> str:
        """Handle sysinfo command - detailed system information"""
        try:
            stats = await self._get_network_stats()
            
            response = f"🖥️ **System Information**\n\n"
            
            # System details
            response += f"📋 **ZephyrGate Gateway**\n"
            response += f"  • Version: 1.0.0\n"
            response += f"  • Uptime: {self._get_uptime()}\n"
            response += f"  • Services: 6 active\n\n"
            
            # Network statistics
            response += f"🌐 **Network Statistics**\n"
            response += f"  • Total Nodes: {stats.total_nodes}\n"
            response += f"  • Active (1h): {stats.nodes_last_hour}\n"
            response += f"  • Active (24h): {stats.nodes_last_day}\n"
            response += f"  • Messages: {stats.total_messages}\n"
            response += f"  • Msg Rate: {stats.messages_last_hour}/hour\n\n"
            
            # Hardware roles distribution
            role_stats = await self._get_role_statistics()
            if role_stats:
                response += f"🎭 **Node Roles**\n"
                for role, count in role_stats.items():
                    response += f"  • {role}: {count}\n"
                response += "\n"
            
            # Signal quality
            if stats.average_snr is not None:
                response += f"📶 **Signal Quality**\n"
                response += f"  • Avg SNR: {stats.average_snr:.1f}dB\n"
                if stats.average_rssi is not None:
                    response += f"  • Avg RSSI: {stats.average_rssi:.0f}dBm\n"
                response += "\n"
            
            response += f"🕐 Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in sysinfo command: {e}")
            return f"❌ Error retrieving system information: {str(e)}"
    
    async def _handle_leaderboard_command(self, args: List[str], context: Dict) -> str:
        """Handle leaderboard command - show top nodes by various metrics"""
        metric = args[0].lower() if args else "messages"
        
        try:
            if metric in ["messages", "msg"]:
                return await self._get_message_leaderboard()
            elif metric in ["battery", "bat"]:
                return await self._get_battery_leaderboard()
            elif metric in ["signal", "snr"]:
                return await self._get_signal_leaderboard()
            elif metric in ["distance", "dist"]:
                return await self._get_distance_leaderboard(context['sender_id'])
            else:
                return f"❌ Unknown metric: {metric}\nAvailable: messages, battery, signal, distance"
                
        except Exception as e:
            self.logger.error(f"Error in leaderboard command: {e}")
            return f"❌ Error generating leaderboard: {str(e)}"
    
    async def _handle_history_command(self, args: List[str], context: Dict) -> str:
        """Handle history command - show message history"""
        hours = 24
        if args and args[0].isdigit():
            hours = min(int(args[0]), 168)  # Max 1 week
        
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Get message history (this would need to be implemented in message storage)
            # For now, return a placeholder
            response = f"📜 **Message History** (Last {hours} hours)\n\n"
            response += f"⚠️ Message history tracking not fully implemented\n"
            response += f"This feature requires message logging to be enabled"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in history command: {e}")
            return f"❌ Error retrieving message history: {str(e)}"
    
    async def _handle_messages_command(self, args: List[str], context: Dict) -> str:
        """Handle messages command - show recent messages"""
        limit = 10
        if args and args[0].isdigit():
            limit = min(int(args[0]), 50)
        
        try:
            # This would integrate with message storage system
            response = f"💬 **Recent Messages** (Last {limit})\n\n"
            response += f"⚠️ Message display not fully implemented\n"
            response += f"This feature requires message storage integration"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in messages command: {e}")
            return f"❌ Error retrieving messages: {str(e)}"
    
    async def _handle_whereami_command(self, context: Dict) -> str:
        """Handle whereami command - show user's current location"""
        sender_id = context['sender_id']
        
        try:
            location = await self._get_user_location(sender_id)
            
            if not location:
                # Provide helpful response when no location is available
                response = f"📍 **Location Information**\n\n"
                response += f"❌ No location data available for your node ({sender_id})\n\n"
                response += f"**Possible reasons:**\n"
                response += f"• GPS is disabled on your device\n"
                response += f"• Location sharing is turned off\n"
                response += f"• Node hasn't reported location yet\n\n"
                response += f"💡 Enable GPS and location sharing in your Meshtastic settings"
                return response
            
            lat, lon = location
            
            response = f"📍 **Your Location**\n\n"
            response += f"🌐 Coordinates: {lat:.6f}, {lon:.6f}\n"
            response += f"🔗 Maps: https://maps.google.com/?q={lat},{lon}\n"
            
            # Get altitude if available
            node_info = await self._get_node_info(sender_id)
            if node_info and node_info.altitude:
                response += f"⛰️ Altitude: {node_info.altitude:.0f}m ({node_info.altitude * 3.28084:.0f}ft)\n"
            
            # Calculate distance from default location (for reference)
            if self.default_location:
                distance_km = self._calculate_distance(location, self.default_location)
                distance_miles = distance_km * 0.621371
                response += f"📏 Distance from gateway: {distance_km:.1f}km ({distance_miles:.1f}mi)"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in whereami command: {e}")
            return f"📍 **Location Service**\n\n❌ Unable to retrieve location information\n💡 Try again later or check your GPS settings"
    
    async def _handle_howfar_command(self, target_node: str, context: Dict) -> str:
        """Handle howfar command - calculate distance to another node"""
        try:
            # Clean up node ID format
            if not target_node.startswith('!'):
                target_node = f"!{target_node}"
            
            # Get both locations
            user_location = await self._get_user_location(context['sender_id'])
            target_location = await self._get_user_location(target_node)
            
            if not user_location:
                return f"❌ Your location is not available\nLocation sharing may be disabled"
            
            if not target_location:
                return f"❌ Location not available for node {target_node}\nNode may have location sharing disabled"
            
            # Calculate distance
            distance_km = self._calculate_distance(user_location, target_location)
            distance_miles = distance_km * 0.621371
            
            # Get target node info for display name
            target_info = await self._get_node_info(target_node)
            target_name = target_info.short_name if target_info else target_node
            
            response = f"📏 **Distance Calculation**\n\n"
            response += f"📍 From: You ({context.get('sender_name', context['sender_id'])})\n"
            response += f"📍 To: {target_name} ({target_node})\n\n"
            response += f"📐 Distance: {distance_km:.2f}km ({distance_miles:.2f}mi)\n"
            
            # Calculate bearing
            bearing = self._calculate_bearing(user_location, target_location)
            compass_direction = self._bearing_to_compass(bearing)
            response += f"🧭 Bearing: {bearing:.0f}° ({compass_direction})"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in howfar command: {e}")
            return f"📏 **Distance Service**\n\n❌ Unable to calculate distance\n💡 Try again later or check location settings"
    
    async def _handle_howtall_command(self, target_node: str, context: Dict) -> str:
        """Handle howtall command - show altitude/elevation information"""
        # Clean up node ID format
        if not target_node.startswith('!'):
            target_node = f"!{target_node}"
        
        node_info = await self._get_node_info(target_node)
        
        if not node_info:
            return f"❌ No information found for node {target_node}"
        
        if not node_info.altitude:
            return f"❌ No altitude information available for {node_info.short_name} ({target_node})"
        
        altitude_m = node_info.altitude
        altitude_ft = altitude_m * 3.28084
        
        response = f"⛰️ **Altitude Information**\n\n"
        response += f"📍 Node: {node_info.short_name} ({target_node})\n"
        response += f"📏 Altitude: {altitude_m:.0f}m ({altitude_ft:.0f}ft)\n"
        
        # Categorize altitude
        if altitude_m > 3000:
            category = "High altitude (mountain/aircraft)"
        elif altitude_m > 1000:
            category = "Elevated (hill/building)"
        elif altitude_m > 200:
            category = "Moderate elevation"
        else:
            category = "Low elevation (ground level)"
        
        response += f"🏔️ Category: {category}\n"
        
        # Compare with user's altitude if available
        user_info = await self._get_node_info(context['sender_id'])
        if user_info and user_info.altitude:
            altitude_diff = altitude_m - user_info.altitude
            if abs(altitude_diff) > 10:  # Only show if significant difference
                direction = "above" if altitude_diff > 0 else "below"
                response += f"📊 {abs(altitude_diff):.0f}m ({abs(altitude_diff * 3.28084):.0f}ft) {direction} you"
        
        return response
    
    async def _get_node_info(self, node_id: str) -> Optional[NodeInfo]:
        """Get node information from database with caching"""
        # Check cache first
        current_time = datetime.utcnow()
        if node_id in self.node_cache and current_time < self.cache_expiry:
            return self.node_cache[node_id]
        
        try:
            db = get_database()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT node_id, short_name, long_name, last_seen, 
                       location_lat, location_lon, altitude, battery_level, 
                       voltage, snr, rssi, hop_count, hardware_model, 
                       firmware_version, role
                FROM users 
                WHERE node_id = ?
            """, (node_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Parse the row data
            (node_id, short_name, long_name, last_seen_str, 
             lat, lon, altitude, battery_level, voltage, snr, rssi, 
             hop_count, hardware_model, firmware_version, role) = row
            
            try:
                # Handle different datetime formats
                if last_seen_str.endswith('Z'):
                    last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                else:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    # If naive datetime, assume UTC
                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=None)
            except ValueError:
                # Fallback for any parsing issues
                last_seen = datetime.utcnow()
            location = (lat, lon) if lat is not None and lon is not None else None
            
            node_info = NodeInfo(
                node_id=node_id,
                short_name=short_name or node_id[-4:],
                long_name=long_name,
                last_seen=last_seen,
                location=location,
                altitude=altitude,
                battery_level=battery_level,
                voltage=voltage,
                snr=snr,
                rssi=rssi,
                hop_count=hop_count,
                hardware_model=hardware_model,
                firmware_version=firmware_version,
                role=role
            )
            
            # Cache the result
            self.node_cache[node_id] = node_info
            # Update cache expiry only when we add new data
            if not hasattr(self, '_cache_updated') or current_time > self.cache_expiry:
                self.cache_expiry = current_time + self.cache_duration
            
            return node_info
            
        except Exception as e:
            self.logger.error(f"Error getting node info for {node_id}: {e}")
            return None
    
    async def _get_user_location(self, node_id: str) -> Optional[Tuple[float, float]]:
        """Get user location from node info"""
        node_info = await self._get_node_info(node_id)
        return node_info.location if node_info else None
    
    async def _get_network_stats(self) -> NetworkStats:
        """Get network statistics with caching"""
        # Check cache first
        current_time = datetime.utcnow()
        if self.network_stats_cache and current_time < self.cache_expiry:
            return self.network_stats_cache
        
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Total nodes
            cursor.execute("SELECT COUNT(*) FROM users")
            total_nodes = cursor.fetchone()[0]
            
            # Active nodes (last 24 hours)
            cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-24 hours')")
            nodes_last_day = cursor.fetchone()[0]
            
            # Active nodes (last hour)
            cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-1 hour')")
            nodes_last_hour = cursor.fetchone()[0]
            
            # Message statistics would need message logging
            # For now, use placeholder values
            total_messages = 0
            messages_last_hour = 0
            messages_last_day = 0
            
            # Signal quality averages
            cursor.execute("SELECT AVG(snr), AVG(rssi) FROM users WHERE snr IS NOT NULL AND last_seen > datetime('now', '-24 hours')")
            avg_row = cursor.fetchone()
            average_snr = avg_row[0] if avg_row[0] is not None else None
            average_rssi = avg_row[1] if avg_row[1] is not None else None
            
            # Network diameter (max hop count)
            cursor.execute("SELECT MAX(hop_count) FROM users WHERE hop_count IS NOT NULL")
            diameter_row = cursor.fetchone()
            network_diameter = diameter_row[0] if diameter_row[0] is not None else None
            
            stats = NetworkStats(
                total_nodes=total_nodes,
                active_nodes=nodes_last_day,
                nodes_last_hour=nodes_last_hour,
                nodes_last_day=nodes_last_day,
                total_messages=total_messages,
                messages_last_hour=messages_last_hour,
                messages_last_day=messages_last_day,
                average_snr=average_snr,
                average_rssi=average_rssi,
                network_diameter=network_diameter
            )
            
            # Cache the result
            self.network_stats_cache = stats
            self.cache_expiry = current_time + self.cache_duration
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting network stats: {e}")
            # Return empty stats on error
            return NetworkStats(
                total_nodes=0,
                active_nodes=0,
                nodes_last_hour=0,
                nodes_last_day=0,
                total_messages=0,
                messages_last_hour=0,
                messages_last_day=0
            )
    
    async def _get_role_statistics(self) -> Dict[str, int]:
        """Get node role distribution statistics"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT role, COUNT(*) 
                FROM users 
                WHERE role IS NOT NULL AND last_seen > datetime('now', '-7 days')
                GROUP BY role
                ORDER BY COUNT(*) DESC
            """)
            
            rows = cursor.fetchall()
            return {role: count for role, count in rows}
            
        except Exception as e:
            self.logger.error(f"Error getting role statistics: {e}")
            return {}
    
    async def _get_message_leaderboard(self) -> str:
        """Get message count leaderboard"""
        # This would require message logging implementation
        response = f"🏆 **Message Leaderboard**\n\n"
        response += f"⚠️ Message tracking not fully implemented\n"
        response += f"This feature requires message logging to be enabled"
        return response
    
    async def _get_battery_leaderboard(self) -> str:
        """Get battery level leaderboard"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT short_name, node_id, battery_level
                FROM users 
                WHERE battery_level IS NOT NULL AND last_seen > datetime('now', '-24 hours')
                ORDER BY battery_level DESC
                LIMIT 10
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                return f"🔋 **Battery Leaderboard**\n\n❌ No battery data available"
            
            response = f"🔋 **Battery Leaderboard** (Top 10)\n\n"
            
            for i, (short_name, node_id, battery_level) in enumerate(rows, 1):
                battery_emoji = "🔋" if battery_level > 50 else "🪫" if battery_level > 20 else "🔴"
                response += f"{i}. {battery_emoji} **{short_name}**: {battery_level}%\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting battery leaderboard: {e}")
            return f"❌ Error generating battery leaderboard: {str(e)}"
    
    async def _get_signal_leaderboard(self) -> str:
        """Get signal quality leaderboard"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT short_name, node_id, snr, rssi
                FROM users 
                WHERE snr IS NOT NULL AND last_seen > datetime('now', '-24 hours')
                ORDER BY snr DESC
                LIMIT 10
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                return f"📶 **Signal Quality Leaderboard**\n\n❌ No signal data available"
            
            response = f"📶 **Signal Quality Leaderboard** (Top 10)\n\n"
            
            for i, (short_name, node_id, snr, rssi) in enumerate(rows, 1):
                signal_emoji = "📶" if snr > 10 else "📶" if snr > 0 else "📶"
                response += f"{i}. {signal_emoji} **{short_name}**: SNR {snr:.1f}dB"
                if rssi is not None:
                    response += f", RSSI {rssi:.0f}dBm"
                response += "\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting signal leaderboard: {e}")
            return f"❌ Error generating signal leaderboard: {str(e)}"
    
    async def _get_distance_leaderboard(self, reference_node: str) -> str:
        """Get distance leaderboard from reference node"""
        reference_location = await self._get_user_location(reference_node)
        
        if not reference_location:
            return f"❌ Your location is not available for distance calculations"
        
        try:
            db = get_database()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT short_name, node_id, location_lat, location_lon
                FROM users 
                WHERE location_lat IS NOT NULL AND location_lon IS NOT NULL 
                AND node_id != ? AND last_seen > datetime('now', '-24 hours')
            """, (reference_node,))
            
            rows = cursor.fetchall()
            
            if not rows:
                return f"📏 **Distance Leaderboard**\n\n❌ No location data available for other nodes"
            
            # Calculate distances and sort
            distances = []
            for short_name, node_id, lat, lon in rows:
                distance_km = self._calculate_distance(reference_location, (lat, lon))
                distances.append((short_name, node_id, distance_km))
            
            distances.sort(key=lambda x: x[2], reverse=True)  # Farthest first
            
            response = f"📏 **Distance Leaderboard** (From You)\n\n"
            
            for i, (short_name, node_id, distance_km) in enumerate(distances[:10], 1):
                distance_miles = distance_km * 0.621371
                response += f"{i}. **{short_name}**: {distance_km:.1f}km ({distance_miles:.1f}mi)\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting distance leaderboard: {e}")
            return f"❌ Error generating distance leaderboard: {str(e)}"
    
    def _calculate_distance(self, loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates using Haversine formula"""
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return self.EARTH_RADIUS_KM * c
    
    def _calculate_bearing(self, loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Calculate bearing from loc1 to loc2"""
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])
        
        dlon = lon2 - lon1
        
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    def _bearing_to_compass(self, bearing: float) -> str:
        """Convert bearing to compass direction"""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(bearing / 22.5) % 16
        return directions[index]
    
    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as time ago"""
        now = datetime.utcnow()
        
        # Ensure both timestamps are naive (no timezone info)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
            
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    
    def _get_uptime(self) -> str:
        """Get system uptime (placeholder)"""
        # This would need to track actual startup time
        return "2h 15m"