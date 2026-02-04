"""
Web Admin Service Plugin

Wraps the Web Admin service as a plugin for the ZephyrGate plugin system.
This allows the web admin service to be loaded, managed, and monitored through the
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
from services.web.web_admin_service import WebAdminService
from models.message import Message


class WebServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Web Admin Service.
    
    Provides:
    - Web-based administration interface
    - System monitoring dashboard
    - Plugin management UI
    - Configuration management
    - Real-time statistics
    """
    
    async def initialize(self) -> bool:
        """Initialize the web admin service plugin"""
        self.logger.info("Initializing Web Admin Service Plugin")
        
        try:
            # Create the web admin service instance with plugin config
            self.web_service = WebAdminService(self.config, self.plugin_manager)
            
            # Set plugin manager reference for web interface
            if hasattr(self, 'plugin_manager'):
                self.web_service.plugin_manager = self.plugin_manager
            
            # Initialize the web admin service
            await self.web_service.start()
            
            self.logger.info("Web Admin Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize web admin service: {e}", exc_info=True)
            return False
    
    async def cleanup(self):
        """Clean up web admin service resources"""
        self.logger.info("Cleaning up Web Admin Service Plugin")
        
        try:
            if hasattr(self, 'web_service') and self.web_service:
                await self.web_service.stop()
            
            self.logger.info("Web Admin Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up web admin service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get web admin service status"""
        status = {
            'service': 'web',
            'running': hasattr(self, 'web_service') and self.web_service is not None,
            'features': {
                'dashboard': True,
                'plugin_management': True,
                'configuration': True,
                'monitoring': True,
                'websocket': self.get_config('websocket.enabled', True)
            }
        }
        
        # Add web service specific status
        if hasattr(self, 'web_service') and hasattr(self.web_service, 'get_status'):
            try:
                web_status = self.web_service.get_status()
                status.update(web_status)
            except:
                pass
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="web_service",
            version="1.0.0",
            description="Web-based administration interface with monitoring and plugin management",
            author="ZephyrGate Team",
            priority=PluginPriority.HIGH
        )
