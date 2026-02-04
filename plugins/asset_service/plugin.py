"""
Asset Tracking Service Plugin

Wraps the Asset Tracking service as a plugin for the ZephyrGate plugin system.
This allows the asset tracking service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import from src modules
from core.enhanced_plugin import EnhancedPlugin
from models.message import Message

# Import from local asset modules
from .asset.asset_tracking_service import AssetTrackingService
from .asset.menu_system import AssetMenuSystem


class AssetServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Asset Tracking Service.
    
    Provides:
    - Asset registration and tracking
    - Location updates
    - Asset status monitoring
    - Geofencing
    - Asset search and queries
    """
    
    async def initialize(self) -> bool:
        """Initialize the asset tracking service plugin"""
        self.logger.info("Initializing Asset Tracking Service Plugin")
        
        try:
            # Create the asset tracking service instance with plugin config
            self.asset_service = AssetTrackingService(self.config)
            
            # Initialize the asset tracking service
            await self.asset_service.start()
            
            # Create menu system
            self.menu_system = AssetMenuSystem(self.asset_service)
            
            # Register asset commands
            await self._register_asset_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            self.logger.info("Asset Tracking Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize asset tracking service: {e}", exc_info=True)
            return False
    
    async def _register_asset_commands(self):
        """Register asset tracking commands with the plugin system"""
        # Main asset menu command
        self.register_command(
            "asset",
            self._handle_asset_menu_command,
            "Access asset tracking system (submenu)",
            priority=50
        )
        
        # Quick locate command (always available at top level)
        self.register_command(
            "locate",
            self._handle_quick_locate_command,
            "Quick locate an asset",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for asset tracking service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is an asset-related message
            content = message.content.lower().strip()
            
            # Let asset commands be handled by command handlers
            if content.startswith(('asset', 'locate')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in asset tracking service: {e}", exc_info=True)
            return False
    
    async def _handle_asset_menu_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle asset menu command - enters asset submenu"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Build command string from args
            command = ' '.join(args) if args else ''
            
            # Process command through menu system
            return await self.menu_system.process_command(sender_id, command, context)
            
        except Exception as e:
            self.logger.error(f"Error in asset menu command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_locate_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick locate command (always available at top level)"""
        try:
            if not args:
                # List all tracked assets
                if hasattr(self.asset_service, 'list_assets'):
                    assets = await self.asset_service.list_assets()
                    if not assets:
                        return "No assets being tracked"
                    
                    result = "📍 Tracked Assets:\n"
                    for asset in assets:
                        result += f"{asset.id}: {asset.name} - Last seen: {asset.last_update}\n"
                    return result
                else:
                    return "Asset listing not available"
            
            # Locate specific asset
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'get_asset_location'):
                location = await self.asset_service.get_asset_location(asset_id)
                if location:
                    return f"📍 Asset {asset_id}: {location['latitude']}, {location['longitude']}"
                else:
                    return f"Asset {asset_id} not found or no location data"
            else:
                return "Asset location lookup not available"
            
        except Exception as e:
            self.logger.error(f"Error in quick locate command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up asset tracking service resources"""
        self.logger.info("Cleaning up Asset Tracking Service Plugin")
        
        try:
            if hasattr(self, 'asset_service') and self.asset_service:
                await self.asset_service.stop()
            
            self.logger.info("Asset Tracking Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up asset tracking service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get asset tracking service status"""
        status = {
            'service': 'asset',
            'running': hasattr(self, 'asset_service') and self.asset_service is not None,
            'features': {
                'tracking': True,
                'location_updates': True,
                'geofencing': True,
                'status_monitoring': True
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="asset_service",
            version="1.0.0",
            description="Asset tracking service with location monitoring and geofencing",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
