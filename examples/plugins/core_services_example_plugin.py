"""
Example Plugin: Core Services Access

Demonstrates how to use core service access features:
- Message routing to mesh network
- System state queries
- Inter-plugin messaging
- Permission enforcement

This plugin requires the following permissions in its manifest:
- send_messages
- system_state_read
- inter_plugin_messaging
"""

import logging
from typing import Any, Dict, List
from datetime import datetime

from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_interfaces import PluginMessage
from src.core.plugin_core_services import PermissionDeniedError


class CoreServicesExamplePlugin(EnhancedPlugin):
    """Example plugin demonstrating core service access"""
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    async def start(self) -> bool:
        """Start the plugin and register handlers"""
        await super().start()
        
        # Register command handlers
        self.register_command("status", self.handle_status_command, 
                            "Get system status information")
        self.register_command("ping", self.handle_ping_command,
                            "Ping another plugin")
        self.register_command("broadcast", self.handle_broadcast_command,
                            "Broadcast a message to all plugins")
        self.register_command("mesh", self.handle_mesh_command,
                            "Send a message to the mesh network")
        
        # Register inter-plugin message handler
        self.register_inter_plugin_handler(self.handle_plugin_message)
        
        self.logger.info("Core Services Example Plugin started")
        return True
    
    async def handle_status_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle status command - demonstrates system state queries.
        
        Usage: status [node_id]
        """
        try:
            # Get network status
            network_status = self.get_network_status()
            response = f"Network Status:\n"
            response += f"  Connected: {network_status.get('connected', False)}\n"
            response += f"  Nodes: {network_status.get('node_count', 0)}\n"
            response += f"  Channel: {network_status.get('channel', 0)}\n"
            
            # Get list of running plugins
            plugins = self.get_plugin_list()
            response += f"\nRunning Plugins ({len(plugins)}):\n"
            for plugin in plugins[:5]:  # Show first 5
                response += f"  - {plugin}\n"
            
            # Get node info if node_id provided
            if args:
                node_id = args[0]
                node_info = self.get_node_info(node_id)
                if node_info:
                    response += f"\nNode {node_id}:\n"
                    response += f"  Status: {node_info.get('status', 'unknown')}\n"
                    response += f"  Last Seen: {node_info.get('last_seen', 'never')}\n"
            
            return response
            
        except PermissionDeniedError as e:
            return f"Permission denied: {e}"
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return f"Error: {e}"
    
    async def handle_ping_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle ping command - demonstrates inter-plugin messaging.
        
        Usage: ping <plugin_name>
        """
        if not args:
            return "Usage: ping <plugin_name>"
        
        target_plugin = args[0]
        
        try:
            # Send ping message to target plugin
            response = await self.send_to_plugin(
                target_plugin,
                "ping",
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "sender": self.name
                }
            )
            
            if response and response.success:
                return f"Pong from {target_plugin}: {response.data}"
            elif response:
                return f"Error from {target_plugin}: {response.error}"
            else:
                return f"No response from {target_plugin}"
                
        except PermissionDeniedError as e:
            return f"Permission denied: {e}"
        except Exception as e:
            self.logger.error(f"Error in ping command: {e}")
            return f"Error: {e}"
    
    async def handle_broadcast_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle broadcast command - demonstrates broadcasting to all plugins.
        
        Usage: broadcast <message>
        """
        if not args:
            return "Usage: broadcast <message>"
        
        message = " ".join(args)
        
        try:
            # Broadcast message to all plugins
            responses = await self.broadcast_to_plugins(
                "announcement",
                {
                    "message": message,
                    "sender": self.name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            success_count = sum(1 for r in responses if r.success)
            return f"Broadcast sent to {len(responses)} plugins, {success_count} acknowledged"
            
        except PermissionDeniedError as e:
            return f"Permission denied: {e}"
        except Exception as e:
            self.logger.error(f"Error in broadcast command: {e}")
            return f"Error: {e}"
    
    async def handle_mesh_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle mesh command - demonstrates sending messages to mesh network.
        
        Usage: mesh <message> [destination] [channel]
        """
        if not args:
            return "Usage: mesh <message> [destination] [channel]"
        
        message = args[0]
        destination = args[1] if len(args) > 1 else None
        channel = int(args[2]) if len(args) > 2 else None
        
        try:
            # Send message to mesh network
            success = await self.send_message(message, destination, channel)
            
            if success:
                dest_str = destination or "broadcast"
                chan_str = f"channel {channel}" if channel else "default channel"
                return f"Message sent to {dest_str} on {chan_str}"
            else:
                return "Failed to send message"
                
        except PermissionDeniedError as e:
            return f"Permission denied: {e}"
        except Exception as e:
            self.logger.error(f"Error in mesh command: {e}")
            return f"Error: {e}"
    
    async def handle_plugin_message(self, message: PluginMessage) -> Any:
        """
        Handle incoming inter-plugin messages.
        
        Args:
            message: The plugin message
            
        Returns:
            Response data
        """
        message_type = message.metadata.get('message_type')
        
        if message_type == 'ping':
            # Respond to ping
            self.logger.info(f"Received ping from {message.source_plugin}")
            return {
                "status": "pong",
                "timestamp": datetime.utcnow().isoformat(),
                "plugin": self.name
            }
        
        elif message_type == 'announcement':
            # Handle broadcast announcement
            announcement = message.data.get('message', '')
            sender = message.data.get('sender', 'unknown')
            self.logger.info(f"Received announcement from {sender}: {announcement}")
            return {"received": True, "plugin": self.name}
        
        else:
            # Unknown message type
            self.logger.warning(f"Unknown message type: {message_type}")
            return None
    
    async def stop(self) -> bool:
        """Stop the plugin"""
        self.logger.info("Core Services Example Plugin stopping")
        return await super().stop()


# Plugin factory function
def create_plugin(name: str, config: Dict[str, Any], plugin_manager) -> CoreServicesExamplePlugin:
    """Create and return plugin instance"""
    return CoreServicesExamplePlugin(name, config, plugin_manager)
