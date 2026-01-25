"""
Weather Service Plugin

Wraps the Weather service as a plugin for the ZephyrGate plugin system.
This allows the weather service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from weather.weather_service import WeatherService
from models.message import Message


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
            # Create the weather service instance with plugin config
            self.weather_service = WeatherService(self.config)
            
            # Initialize the weather service
            await self.weather_service.start()
            
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
            
            # Get location from args or use sender's location
            location = ' '.join(args) if args else None
            
            # Get weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, location, detailed=False)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in wx command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_weather_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle weather (detailed) command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Get location from args or use sender's location
            location = ' '.join(args) if args else None
            
            # Get detailed weather report
            if hasattr(self.weather_service, 'get_weather_report'):
                return await self.weather_service.get_weather_report(sender_id, location, detailed=True)
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
            location = None
            
            if args:
                if args[0].isdigit():
                    days = int(args[0])
                    location = ' '.join(args[1:]) if len(args) > 1 else None
                else:
                    location = ' '.join(args)
            
            # Get forecast report
            if hasattr(self.weather_service, 'get_forecast_report'):
                return await self.weather_service.get_forecast_report(sender_id, location, days)
            else:
                return "Weather service not available"
            
        except Exception as e:
            self.logger.error(f"Error in forecast command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_alerts_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle alerts command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Get location from args or use sender's location
            location = ' '.join(args) if args else None
            
            # Get weather alerts
            if hasattr(self.weather_service, 'get_alerts_report'):
                return await self.weather_service.get_alerts_report(sender_id, location)
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
