"""
Ping Responder Plugin

A simple plugin that responds to ping and help commands to test
the ZephyrGate plugin system and Meshtastic integration.
"""

from typing import Dict, Any, List
from core.enhanced_plugin import EnhancedPlugin


class PingResponderPlugin(EnhancedPlugin):
    """Simple plugin that responds to ping messages"""
    
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        self.logger.info("Initializing Ping Responder plugin")
        
        # Register ping command
        self.register_command(
            "ping",
            self._handle_ping_command,
            "Test connectivity with a ping/pong response",
            priority=50  # Lower priority than bot_service
        )
        
        # Register help command
        self.register_command(
            "help",
            self._handle_help_command,
            "Show available commands",
            priority=50  # Lower priority than bot_service
        )
        
        self.logger.info("Ping Responder plugin initialized successfully")
        return True
    
    async def _handle_ping_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle ping command"""
        sender_id = context.get('sender_id', 'unknown')
        self.logger.info(f"Received ping from {sender_id}")
        return "🏓 Pong! ZephyrGate is alive and well!"
    
    async def _handle_help_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle help command"""
        sender_id = context.get('sender_id', 'unknown')
        self.logger.info(f"Received help request from {sender_id}")
        
        help_text = (
            "📋 ZephyrGate Commands:\n"
            "• ping - Test connectivity\n"
            "• help - Show this message"
        )
        return help_text
    
    async def cleanup(self):
        """Clean up plugin resources"""
        self.logger.info("Ping Responder plugin stopped")
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="ping_responder",
            version="1.0.0",
            description="Simple ping/pong responder for testing",
            author="ZephyrGate Team",
            priority=PluginPriority.LOW
        )

