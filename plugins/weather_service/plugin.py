"""
Weather Service Plugin

Wraps the Weather service as a plugin for the ZephyrGate plugin system.
This allows the weather service to be loaded, managed, and monitored through the
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

# Import from local weather modules
from .weather.weather_service import WeatherService


class WeatherServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Weather Service.
    
    Provides:
    - Current weather conditions
    - Weather forecasts
    - Weather alerts
    - Location-based weather
    - Proximity monitoring
    """
    
    async def initialize(self) -> bool:
        """Initialize the weather service plugin"""
        self.logger.info("Initializing Weather Service Plugin")
        
        try:
            # Get weather_service specific config from the plugin config
            # Config structure: services.weather_service or just weather_service
            weather_config = self.config.get('weather_service', {})
            
            # If not found, try services.weather_service
            if not weather_config:
                services = self.config.get('services', {})
                weather_config = services.get('weather_service', {})
            
            # If still not found, use the whole config as fallback
            if not weather_config:
                weather_config = self.config
            
            self.logger.info(f"Weather service config keys: {list(weather_config.keys())}")
            self.logger.info(f"Default location config: {weather_config.get('default_location')}")
            
            # Create the weather service instance with proper arguments
            self.weather_service = WeatherService(
                name=self.name,
                config=weather_config,
                plugin_manager=self.plugin_manager
            )
            
            # Initialize the weather service (sets up clients, geocoding, location)
            init_success = await self.weather_service.initialize()
            if not init_success:
                self.logger.error("Failed to initialize weather service")
                return False
            
            # Start the weather service (starts background tasks)
            start_success = await self.weather_service.start()
            if not start_success:
                self.logger.error("Failed to start weather service")
                return False
            
            # Register weather commands
            await self._register_weather_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            self.logger.info("Weather Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize weather service: {e}", exc_info=True)
            return False
    
    async def _register_weather_commands(self):
        """Register weather commands with the plugin system"""
        # Current weather command
        self.register_command(
            "wx",
            self._handle_wx_command,
            "Get current weather conditions",
            priority=50
        )
        
        # Detailed weather command
        self.register_command(
            "weather",
            self._handle_weather_command,
            "Get detailed weather information",
            priority=50
        )
        
        # Forecast command
        self.register_command(
            "forecast",
            self._handle_forecast_command,
            "Get weather forecast",
            priority=50
        )
        
        # Alerts command
        self.register_command(
            "alerts",
            self._handle_alerts_command,
            "Get active weather alerts",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for weather service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is a weather-related message
            content = message.content.lower().strip()
            
            # Let weather commands be handled by command handlers
            if content.startswith(('wx', 'weather', 'forecast', 'alerts')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in weather service: {e}", exc_info=True)
            return False
    
    async def _handle_wx_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle wx (current weather) command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported by get_weather_report
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, detailed=False)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in wx command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_weather_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle weather (detailed) command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported by get_weather_report
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get detailed weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, detailed=True)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in weather command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_forecast_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle forecast command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Parse days from args
            days = 3
            
            if args:
                if args[0].isdigit():
                    days = int(args[0])
                    # Note: Additional location args are currently not supported
                    # TODO: Add support for custom location parameter
            
            # Get forecast report
            if hasattr(self.weather_service, 'get_forecast_report'):
                return await self.weather_service.get_forecast_report(sender_id, days)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in forecast command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_alerts_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle alerts command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Note: Location from args is currently not supported
            # The method uses the user's subscription location or default_location
            # TODO: Add support for custom location parameter
            
            # Get weather alerts
            if hasattr(self.weather_service, 'get_weather_alerts'):
                return await self.weather_service.get_weather_alerts(sender_id)
            else:
                return "Weather alerts not available"
            
        except Exception as e:
            self.logger.error(f"Error in alerts command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up weather service resources"""
        self.logger.info("Cleaning up Weather Service Plugin")
        
        try:
            if hasattr(self, 'weather_service') and self.weather_service:
                await self.weather_service.stop()
            
            self.logger.info("Weather Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up weather service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get weather service status"""
        status = {
            'service': 'weather',
            'running': hasattr(self, 'weather_service') and self.weather_service is not None,
            'features': {
                'current_conditions': True,
                'forecasts': True,
                'alerts': True,
                'location_based': True
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="weather_service",
            version="1.0.0",
            description="Weather service with current conditions, forecasts, and alerts",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
