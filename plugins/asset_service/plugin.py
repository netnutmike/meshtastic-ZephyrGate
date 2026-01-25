"""
Asset Tracking Service Plugin

Wraps the Asset Tracking service as a plugin for the ZephyrGate plugin system.
This allows the asset tracking service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from asset.asset_tracking_service import AssetTrackingService
from models.message import Message


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
        # Track command
        self.register_command(
            "track",
            self._handle_track_command,
            "Track an asset",
            priority=50
        )
        
        # Locate command
        self.register_command(
            "locate",
            self._handle_locate_command,
            "Locate an asset",
            priority=50
        )
        
        # Status command
        self.register_command(
            "status",
            self._handle_status_command,
            "Get asset status",
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
            if content.startswith(('track', 'locate', 'status')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in asset tracking service: {e}", exc_info=True)
            return False
    
    async def _handle_track_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle track asset command"""
        try:
            if not args:
                return "Usage: track <asset_id> [latitude] [longitude]"
            
            asset_id = args[0]
            
            if len(args) >= 3:
                # Update location
                latitude = float(args[1])
                longitude = float(args[2])
                
                if hasattr(self.asset_service, 'update_asset_location'):
                    success = await self.asset_service.update_asset_location(asset_id, latitude, longitude)
                    return f"✅ Asset {asset_id} location updated" if success else f"❌ Failed to update asset {asset_id}"
                else:
                    return "Asset location update not available"
            else:
                # Register asset for tracking
                if hasattr(self.asset_service, 'register_asset'):
                    success = await self.asset_service.register_asset(asset_id)
                    return f"✅ Asset {asset_id} registered for tracking" if success else f"❌ Failed to register asset {asset_id}"
                else:
                    return "Asset registration not available"
            
        except Exception as e:
            self.logger.error(f"Error in track command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_locate_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle locate asset command"""
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
            self.logger.error(f"Error in locate command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_status_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle asset status command"""
        try:
            if not args:
                return "Usage: status <asset_id>"
            
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'get_asset_status'):
                status = await self.asset_service.get_asset_status(asset_id)
                if status:
                    return (
                        f"📊 Asset {asset_id} Status:\n"
                        f"Name: {status.get('name', 'Unknown')}\n"
                        f"Status: {status.get('status', 'Unknown')}\n"
                        f"Location: {status.get('latitude', 'N/A')}, {status.get('longitude', 'N/A')}\n"
                        f"Last Update: {status.get('last_update', 'N/A')}"
                    )
                else:
                    return f"Asset {asset_id} not found"
            else:
                return "Asset status lookup not available"
            
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
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
