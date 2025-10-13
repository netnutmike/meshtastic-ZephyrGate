"""
Weather Service Foundation

Main weather service that provides comprehensive weather data fetching,
multi-source emergency alerting, proximity monitoring, and location-based filtering.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
import uuid

from src.core.plugin_manager import BasePlugin, PluginMetadata, PluginPriority
from src.core.plugin_interfaces import (
    BaseMessageHandler, BaseCommandHandler, 
    PluginCommunicationInterface
)
from src.models.message import Message, MessageType
from .models import (
    WeatherData, WeatherAlert, WeatherSubscription, WeatherCache,
    Location, AlertType, AlertSeverity, ProximityAlert, EarthquakeData,
    EnvironmentalReading, WeatherProvider
)
from .noaa_client import NOAAClient
from .openmeteo_client import OpenMeteoClient
from .cache_manager import WeatherCacheManager
from .alert_clients import AlertAggregator
from .environmental_monitoring import EnvironmentalMonitoringService
from .file_sensor_monitoring import FileSensorMonitoringService
from .location_filtering import LocationBasedFilteringService, LocationAccuracy


class WeatherMessageHandler(BaseMessageHandler):
    """Message handler for weather-related messages"""
    
    def __init__(self, weather_service: 'WeatherService'):
        super().__init__(priority=50)
        self.weather_service = weather_service
    
    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the message"""
        content = message.content.lower().strip()
        weather_commands = [
            'wx', 'weather', 'forecast', 'wxc', 'wxa', 'wxalert', 'mwx',
            'alerts', 'earthquake', 'proximity', 'sentry'
        ]
        return any(content.startswith(cmd) for cmd in weather_commands)
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Handle weather-related messages"""
        return await self.weather_service.handle_weather_command(message)


class WeatherCommandHandler(BaseCommandHandler):
    """Command handler for weather commands"""
    
    def __init__(self, weather_service: 'WeatherService'):
        commands = [
            'wx', 'weather', 'forecast', 'wxc', 'wxa', 'wxalert', 'mwx',
            'alerts', 'earthquake', 'proximity', 'sentry', 'subscribe_weather',
            'unsubscribe_weather', 'weather_status', 'set_location', 'get_location', 'nearby_users'
        ]
        super().__init__(commands)
        self.weather_service = weather_service
        
        # Add help text
        self.add_help('wx', 'Get current weather conditions')
        self.add_help('weather', 'Get detailed weather information')
        self.add_help('forecast', 'Get weather forecast')
        self.add_help('wxc', 'Get current conditions only')
        self.add_help('wxa', 'Get active weather alerts')
        self.add_help('wxalert', 'Get weather alerts for your area')
        self.add_help('mwx', 'Get marine weather conditions')
        self.add_help('alerts', 'Get all active alerts')
        self.add_help('earthquake', 'Get recent earthquake information')
        self.add_help('proximity', 'Get proximity alerts')
        self.add_help('sentry', 'Toggle sentry mode for proximity detection')
        self.add_help('subscribe_weather', 'Subscribe to weather updates')
        self.add_help('unsubscribe_weather', 'Unsubscribe from weather updates')
        self.add_help('weather_status', 'Get weather subscription status')
        self.add_help('set_location', 'Set your location for weather alerts')
        self.add_help('get_location', 'Get your current location')
        self.add_help('nearby_users', 'Find nearby users')
    
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """Handle weather commands"""
        sender_id = context.get('sender_id', '')
        
        if command in ['wx', 'weather']:
            return await self.weather_service.get_weather_report(sender_id, detailed=command=='weather')
        elif command == 'forecast':
            days = int(args[0]) if args and args[0].isdigit() else 3
            return await self.weather_service.get_forecast_report(sender_id, days)
        elif command == 'wxc':
            return await self.weather_service.get_current_conditions(sender_id)
        elif command in ['wxa', 'wxalert']:
            return await self.weather_service.get_weather_alerts(sender_id)
        elif command == 'mwx':
            return await self.weather_service.get_marine_weather(sender_id)
        elif command == 'alerts':
            return await self.weather_service.get_all_alerts(sender_id)
        elif command == 'earthquake':
            return await self.weather_service.get_earthquake_info(sender_id)
        elif command == 'proximity':
            return await self.weather_service.get_proximity_alerts(sender_id)
        elif command == 'sentry':
            action = args[0].lower() if args else 'status'
            return await self.weather_service.handle_sentry_command(sender_id, action)
        elif command == 'subscribe_weather':
            return await self.weather_service.subscribe_user(sender_id, args)
        elif command == 'unsubscribe_weather':
            return await self.weather_service.unsubscribe_user(sender_id)
        elif command == 'weather_status':
            return await self.weather_service.get_subscription_status(sender_id)
        elif command == 'set_location':
            if len(args) >= 2:
                try:
                    lat = float(args[0])
                    lon = float(args[1])
                    name = ' '.join(args[2:]) if len(args) > 2 else None
                    return await self.weather_service.set_user_location(sender_id, lat, lon, name)
                except ValueError:
                    return "❌ Invalid coordinates. Usage: set_location <latitude> <longitude> [name]"
            else:
                return "❌ Usage: set_location <latitude> <longitude> [name]"
        elif command == 'get_location':
            return await self.weather_service.get_user_location_info(sender_id)
        elif command == 'nearby_users':
            radius = float(args[0]) if args and args[0].replace('.', '').isdigit() else 10.0
            return await self.weather_service.get_nearby_users(sender_id, radius)
        
        return f"Unknown weather command: {command}"


class WeatherService(BasePlugin):
    """
    Main weather service providing comprehensive weather and alert functionality
    """
    
    def __init__(self, name: str, config: Dict[str, Any], plugin_manager):
        super().__init__(name, config, plugin_manager)
        
        # Service components
        self.cache_manager = WeatherCacheManager(
            cache_dir=self.data_dir / "cache",
            max_cache_size_mb=config.get('max_cache_size_mb', 100)
        )
        self.subscriptions: Dict[str, WeatherSubscription] = {}
        self.active_alerts: Dict[str, WeatherAlert] = {}
        self.proximity_alerts: Dict[str, ProximityAlert] = {}
        
        # API clients
        self.noaa_client: Optional[NOAAClient] = None
        self.openmeteo_client: Optional[OpenMeteoClient] = None
        self.alert_aggregator: Optional[AlertAggregator] = None
        self.environmental_monitor: Optional[EnvironmentalMonitoringService] = None
        self.file_sensor_monitor: Optional[FileSensorMonitoringService] = None
        self.location_filter: Optional[LocationBasedFilteringService] = None
        
        # Configuration
        self.cache_duration = timedelta(minutes=config.get('cache_duration_minutes', 30))
        self.update_interval = config.get('update_interval_minutes', 15)
        self.default_location = self._parse_location(config.get('default_location'))
        self.alert_radius_km = config.get('default_alert_radius_km', 50.0)
        
        # API configurations
        self.noaa_api_key = config.get('noaa_api_key')
        self.openmeteo_enabled = config.get('openmeteo_enabled', True)
        self.earthquake_enabled = config.get('earthquake_monitoring', True)
        self.proximity_enabled = config.get('proximity_monitoring', False)
        
        # Data storage paths
        self.data_dir = Path(config.get('data_directory', 'data/weather'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Background tasks
        self.update_task: Optional[asyncio.Task] = None
        self.alert_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Message handlers
        self.message_handler = WeatherMessageHandler(self)
        self.command_handler = WeatherCommandHandler(self)
        
        # Communication interface
        self.comm: Optional[PluginCommunicationInterface] = None
        
        self.logger.info(f"Weather service initialized with config: {config}")
    
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata"""
        return PluginMetadata(
            name="weather_service",
            version="1.0.0",
            description="Comprehensive weather and alert service",
            author="ZephyrGate",
            priority=PluginPriority.NORMAL
        )
    
    async def initialize(self) -> bool:
        """Initialize the weather service"""
        try:
            # Initialize API clients
            if self.noaa_api_key:
                self.noaa_client = NOAAClient(api_key=self.noaa_api_key)
                await self.noaa_client.start()
            
            if self.openmeteo_enabled:
                self.openmeteo_client = OpenMeteoClient()
                await self.openmeteo_client.start()
            
            # Initialize alert aggregator
            self.alert_aggregator = AlertAggregator()
            await self.alert_aggregator.start()
            
            # Initialize environmental monitoring
            env_config = config.get('environmental_monitoring', {})
            self.environmental_monitor = EnvironmentalMonitoringService(env_config)
            self.environmental_monitor.add_alert_callback(self._handle_environmental_alert)
            await self.environmental_monitor.start()
            
            # Initialize file and sensor monitoring
            file_sensor_config = config.get('file_sensor_monitoring', {})
            self.file_sensor_monitor = FileSensorMonitoringService(file_sensor_config)
            self.file_sensor_monitor.add_alert_callback(self._handle_file_sensor_alert)
            await self.file_sensor_monitor.start()
            
            # Initialize location-based filtering
            location_config = config.get('location_filtering', {})
            self.location_filter = LocationBasedFilteringService(location_config)
            self.location_filter.add_location_callback(self._handle_location_update)
            self.location_filter.add_geofence_callback(self._handle_geofence_event)
            await self.location_filter.start()
            
            # Initialize cache manager
            await self.cache_manager.start()
            
            # Load subscriptions
            await self._load_subscriptions()
            
            # Register message and command handlers
            if hasattr(self.plugin_manager, 'register_message_handler'):
                await self.plugin_manager.register_message_handler(
                    self.message_handler, self.name
                )
            
            if hasattr(self.plugin_manager, 'register_command_handler'):
                await self.plugin_manager.register_command_handler(
                    self.command_handler, self.name
                )
            
            self.logger.info("Weather service initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize weather service: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the weather service"""
        try:
            if self.is_running:
                return True
            
            # Start background tasks
            self.update_task = self.create_task(self._weather_update_loop())
            self.alert_task = self.create_task(self._alert_monitoring_loop())
            self.cleanup_task = self.create_task(self._cleanup_loop())
            
            self.is_running = True
            self.logger.info("Weather service started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start weather service: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the weather service"""
        try:
            if not self.is_running:
                return True
            
            self.is_running = False
            self.signal_stop()
            
            # Cancel background tasks
            await self.cancel_tasks()
            
            # Save data
            await self._save_subscriptions()
            
            self.logger.info("Weather service stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop weather service: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up weather service resources"""
        try:
            # Stop cache manager
            await self.cache_manager.stop()
            
            # Close API clients
            if self.noaa_client:
                await self.noaa_client.close()
            
            if self.openmeteo_client:
                await self.openmeteo_client.close()
            
            # Close alert aggregator
            if self.alert_aggregator:
                await self.alert_aggregator.close()
            
            # Stop environmental monitoring
            if self.environmental_monitor:
                await self.environmental_monitor.stop()
            
            # Stop file and sensor monitoring
            if self.file_sensor_monitor:
                await self.file_sensor_monitor.stop()
            
            # Stop location filtering
            if self.location_filter:
                await self.location_filter.stop()
            
            # Clear data
            self.active_alerts.clear()
            self.proximity_alerts.clear()
            
            self.logger.info("Weather service cleaned up")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup weather service: {e}")
            return False
    
    def set_communication_interface(self, comm: PluginCommunicationInterface):
        """Set the communication interface"""
        self.comm = comm
    
    # Weather data methods
    async def get_weather_data(self, location: Optional[Location] = None) -> Optional[WeatherData]:
        """
        Get weather data for a location
        
        Args:
            location: Location to get weather for (uses default if None)
            
        Returns:
            Weather data or None if unavailable
        """
        if not location:
            location = self.default_location
        
        if not location:
            self.logger.warning("No location provided and no default location configured")
            return None
        
        # Check cache first
        cached = await self.cache_manager.get(location, "weather")
        if cached:
            return cached
        
        # Fetch fresh data
        weather_data = await self._fetch_weather_data(location)
        if weather_data:
            await self.cache_manager.put(location, weather_data, "weather")
        
        return weather_data
    
    async def _fetch_weather_data(self, location: Location) -> Optional[WeatherData]:
        """
        Fetch weather data from external APIs
        
        Args:
            location: Location to fetch weather for
            
        Returns:
            Weather data or None if fetch failed
        """
        # Try NOAA first for US locations
        if self.noaa_client and location.country == "US":
            try:
                weather_data = await self.noaa_client.get_weather_data(location)
                if weather_data:
                    return weather_data
            except Exception as e:
                self.logger.warning(f"NOAA weather fetch failed: {e}")
        
        # Try Open-Meteo as fallback
        if self.openmeteo_client:
            try:
                weather_data = await self.openmeteo_client.get_weather_data(location)
                if weather_data:
                    return weather_data
            except Exception as e:
                self.logger.warning(f"Open-Meteo weather fetch failed: {e}")
        
        # Try offline cache as last resort
        offline_data = await self.cache_manager.get_offline_data(location)
        if offline_data:
            self.logger.info(f"Using offline weather data for {location.name}")
            return offline_data
        
        return None
    
    # Command handling methods
    async def handle_weather_command(self, message: Message) -> Optional[str]:
        """Handle weather-related commands"""
        content = message.content.strip()
        sender_id = message.sender_id
        
        # Parse command and arguments
        parts = content.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        context = {
            'sender_id': sender_id,
            'message': message
        }
        
        return await self.command_handler.handle_command(command, args, context)
    
    async def get_weather_report(self, user_id: str, detailed: bool = False) -> str:
        """Get weather report for user"""
        subscription = self.subscriptions.get(user_id)
        location = subscription.location if subscription else self.default_location
        
        if not location:
            return "❌ No location configured. Please set your location first."
        
        weather_data = await self.get_weather_data(location)
        if not weather_data:
            return "❌ Unable to fetch weather data at this time."
        
        return self._format_weather_report(weather_data, detailed)
    
    async def get_forecast_report(self, user_id: str, days: int = 3) -> str:
        """Get forecast report for user"""
        subscription = self.subscriptions.get(user_id)
        location = subscription.location if subscription else self.default_location
        
        if not location:
            return "❌ No location configured. Please set your location first."
        
        weather_data = await self.get_weather_data(location)
        if not weather_data or not weather_data.forecasts:
            return "❌ Unable to fetch forecast data at this time."
        
        return self._format_forecast_report(weather_data, days)
    
    async def get_current_conditions(self, user_id: str) -> str:
        """Get current conditions for user"""
        subscription = self.subscriptions.get(user_id)
        location = subscription.location if subscription else self.default_location
        
        if not location:
            return "❌ No location configured. Please set your location first."
        
        weather_data = await self.get_weather_data(location)
        if not weather_data:
            return "❌ Unable to fetch weather data at this time."
        
        return self._format_current_conditions(weather_data.current, location)
    
    async def get_weather_alerts(self, user_id: str) -> str:
        """Get weather alerts for user"""
        subscription = self.subscriptions.get(user_id)
        if not subscription:
            return "❌ No weather subscription found. Use 'subscribe_weather' first."
        
        relevant_alerts = []
        for alert in self.active_alerts.values():
            if alert.alert_type == AlertType.WEATHER and subscription.should_receive_alert(alert):
                relevant_alerts.append(alert)
        
        if not relevant_alerts:
            return "✅ No active weather alerts for your area."
        
        return self._format_alerts(relevant_alerts)
    
    async def get_marine_weather(self, user_id: str) -> str:
        """Get marine weather conditions"""
        # TODO: Implement marine weather
        return "🌊 Marine weather not implemented yet."
    
    async def get_all_alerts(self, user_id: str) -> str:
        """Get all active alerts for user"""
        subscription = self.subscriptions.get(user_id)
        if not subscription:
            return "❌ No subscription found. Use 'subscribe_weather' first."
        
        relevant_alerts = []
        for alert in self.active_alerts.values():
            if subscription.should_receive_alert(alert):
                relevant_alerts.append(alert)
        
        if not relevant_alerts:
            return "✅ No active alerts for your area."
        
        return self._format_alerts(relevant_alerts)
    
    async def get_earthquake_info(self, user_id: str) -> str:
        """Get earthquake information"""
        subscription = self.subscriptions.get(user_id)
        location = subscription.location if subscription else self.default_location
        
        if not location:
            return "❌ No location configured. Please set your location first."
        
        if not self.alert_aggregator:
            return "❌ Alert system not available."
        
        try:
            earthquakes = await self.alert_aggregator.earthquake_client.get_earthquakes(
                location, radius_km=500.0, min_magnitude=3.0, hours_back=24
            )
            
            if not earthquakes:
                return "🌍 No significant earthquakes detected in the last 24 hours."
            
            # Format earthquake report
            report_lines = [f"🌍 {len(earthquakes)} earthquake(s) in last 24 hours:"]
            
            for eq in earthquakes[:5]:  # Limit to 5 most recent
                distance = location.distance_to(eq.location)
                time_str = eq.timestamp.strftime('%H:%M UTC')
                report_lines.append(
                    f"• M{eq.magnitude:.1f} - {eq.location.name} ({distance:.0f}km) at {time_str}"
                )
            
            if len(earthquakes) > 5:
                report_lines.append(f"... and {len(earthquakes) - 5} more")
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"Failed to get earthquake info: {e}")
            return "❌ Unable to fetch earthquake information at this time."
    
    async def get_proximity_alerts(self, user_id: str) -> str:
        """Get proximity alerts"""
        if not self.proximity_enabled or not self.environmental_monitor:
            return "📡 Proximity monitoring is disabled."
        
        alerts = self.environmental_monitor.get_proximity_alerts()
        user_alerts = [
            alert for alert in alerts
            if alert.node_id != user_id  # Don't show user's own proximity
        ]
        
        if not user_alerts:
            return "📡 No proximity alerts detected."
        
        return self._format_proximity_alerts(user_alerts)
    
    async def handle_sentry_command(self, user_id: str, action: str) -> str:
        """Handle sentry mode commands"""
        if not self.proximity_enabled:
            return "📡 Proximity monitoring is disabled."
        
        subscription = self.subscriptions.get(user_id)
        if not subscription:
            subscription = WeatherSubscription(user_id=user_id)
            self.subscriptions[user_id] = subscription
        
        if action == 'on':
            subscription.proximity_alerts = True
            await self._save_subscriptions()
            return "📡 Sentry mode enabled. You'll receive proximity alerts."
        elif action == 'off':
            subscription.proximity_alerts = False
            await self._save_subscriptions()
            return "📡 Sentry mode disabled."
        else:
            status = "enabled" if subscription.proximity_alerts else "disabled"
            return f"📡 Sentry mode is currently {status}."
    
    # Subscription management
    async def subscribe_user(self, user_id: str, args: List[str]) -> str:
        """Subscribe user to weather updates"""
        subscription = self.subscriptions.get(user_id, WeatherSubscription(user_id=user_id))
        
        # Parse subscription options from args
        for arg in args:
            if arg.lower() in ['weather', 'wx']:
                subscription.weather_updates = True
            elif arg.lower() in ['forecast', 'fc']:
                subscription.forecast_updates = True
            elif arg.lower() in ['alerts', 'alert']:
                subscription.severe_weather_alerts = True
            elif arg.lower() in ['earthquake', 'eq']:
                subscription.earthquake_alerts = True
            elif arg.lower() in ['proximity', 'prox']:
                subscription.proximity_alerts = True
            elif arg.lower() in ['aircraft', 'air']:
                subscription.aircraft_alerts = True
        
        self.subscriptions[user_id] = subscription
        await self._save_subscriptions()
        
        return f"✅ Weather subscription updated for {user_id}"
    
    async def unsubscribe_user(self, user_id: str) -> str:
        """Unsubscribe user from weather updates"""
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            await self._save_subscriptions()
            return f"✅ Weather subscription removed for {user_id}"
        
        return "❌ No weather subscription found."
    
    async def get_subscription_status(self, user_id: str) -> str:
        """Get user's subscription status"""
        subscription = self.subscriptions.get(user_id)
        if not subscription:
            return "❌ No weather subscription found."
        
        status_lines = [
            f"📊 Weather subscription status for {user_id}:",
            f"Weather updates: {'✅' if subscription.weather_updates else '❌'}",
            f"Forecast updates: {'✅' if subscription.forecast_updates else '❌'}",
            f"Severe weather alerts: {'✅' if subscription.severe_weather_alerts else '❌'}",
            f"Earthquake alerts: {'✅' if subscription.earthquake_alerts else '❌'}",
            f"Proximity alerts: {'✅' if subscription.proximity_alerts else '❌'}",
            f"Aircraft alerts: {'✅' if subscription.aircraft_alerts else '❌'}",
            f"Alert radius: {subscription.alert_radius_km} km"
        ]
        
        return "\n".join(status_lines)
    
    # Background tasks
    async def _weather_update_loop(self):
        """Background task for weather updates"""
        while self.is_running:
            try:
                await self._update_weather_data()
                await asyncio.sleep(self.update_interval * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in weather update loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _alert_monitoring_loop(self):
        """Background task for alert monitoring"""
        while self.is_running:
            try:
                await self._check_for_alerts()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_loop(self):
        """Background task for cleanup"""
        while self.is_running:
            try:
                await self._cleanup_expired_data()
                await asyncio.sleep(3600)  # Cleanup every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)
    
    async def _update_weather_data(self):
        """Update weather data for all subscribed users"""
        locations_to_update = set()
        
        # Collect unique locations
        if self.default_location:
            locations_to_update.add(self.default_location)
        
        for subscription in self.subscriptions.values():
            if subscription.location:
                locations_to_update.add(subscription.location)
        
        # Update weather data for each location
        for location in locations_to_update:
            try:
                await self.get_weather_data(location)
            except Exception as e:
                self.logger.error(f"Failed to update weather for {location}: {e}")
    
    async def _check_for_alerts(self):
        """Check for new alerts from all sources"""
        if not self.alert_aggregator:
            return
        
        # Get unique locations from subscriptions
        locations_to_check = set()
        fips_codes = set()
        same_codes = set()
        
        if self.default_location:
            locations_to_check.add(self.default_location)
            if self.default_location.fips_code:
                fips_codes.add(self.default_location.fips_code)
            if self.default_location.same_code:
                same_codes.add(self.default_location.same_code)
        
        for subscription in self.subscriptions.values():
            if subscription.location:
                locations_to_check.add(subscription.location)
                if subscription.location.fips_code:
                    fips_codes.add(subscription.location.fips_code)
                if subscription.location.same_code:
                    same_codes.add(subscription.location.same_code)
        
        # Check alerts for each location
        for location in locations_to_check:
            try:
                new_alerts = await self.alert_aggregator.get_all_alerts(
                    location=location,
                    radius_km=self.alert_radius_km,
                    fips_codes=list(fips_codes),
                    same_codes=list(same_codes)
                )
                
                # Process new alerts
                for alert in new_alerts:
                    if alert.id not in self.active_alerts:
                        self.active_alerts[alert.id] = alert
                        await self._broadcast_alert(alert)
                        
            except Exception as e:
                self.logger.error(f"Failed to check alerts for {location}: {e}")
    
    async def _broadcast_alert(self, alert: WeatherAlert):
        """Broadcast alert to subscribed users"""
        if not self.comm:
            return
        
        # Find users who should receive this alert
        recipients = []
        for user_id, subscription in self.subscriptions.items():
            # Use location-based filtering if available
            if self.location_filter:
                filtered_alerts = self.location_filter.filter_alerts_for_user(user_id, [alert], subscription)
                if filtered_alerts:
                    recipients.append(user_id)
            else:
                # Fallback to basic subscription filtering
                if subscription.should_receive_alert(alert):
                    recipients.append(user_id)
        
        if not recipients:
            return
        
        # Format alert message
        severity_emoji = {
            AlertSeverity.MINOR: "🟡",
            AlertSeverity.MODERATE: "🟠",
            AlertSeverity.SEVERE: "🔴",
            AlertSeverity.EXTREME: "🚨"
        }.get(alert.severity, "⚠️")
        
        alert_message = f"{severity_emoji} {alert.title}\n{alert.description}"
        
        # Broadcast to recipients
        for user_id in recipients:
            try:
                # Create message for user
                from src.models.message import Message, MessageType
                message = Message(
                    id=f"alert_{alert.id}_{user_id}",
                    sender_id="weather_service",
                    recipient_id=user_id,
                    channel=0,  # Direct message
                    content=alert_message,
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.DIRECT_MESSAGE,
                    interface_id="weather"
                )
                
                await self.comm.send_mesh_message(message)
                
            except Exception as e:
                self.logger.error(f"Failed to send alert to {user_id}: {e}")
    
    def _handle_environmental_alert(self, alert_data: Any):
        """Handle environmental monitoring alerts"""
        try:
            from .models import ProximityAlert, EnvironmentalReading
            
            if isinstance(alert_data, ProximityAlert):
                # Store proximity alert
                self.proximity_alerts[alert_data.id] = alert_data
                self.logger.info(f"Proximity alert: {alert_data.node_name} at {alert_data.distance:.1f}km")
                
                # Broadcast to subscribed users
                asyncio.create_task(self._broadcast_proximity_alert(alert_data))
                
            elif isinstance(alert_data, EnvironmentalReading):
                # Handle RF or other environmental alerts
                self.logger.info(f"Environmental alert: {alert_data.sensor_type} - {alert_data.sensor_id}")
                
                # Broadcast to subscribed users
                asyncio.create_task(self._broadcast_environmental_alert(alert_data))
                
        except Exception as e:
            self.logger.error(f"Error handling environmental alert: {e}")
    
    async def _broadcast_proximity_alert(self, alert: ProximityAlert):
        """Broadcast proximity alert to subscribed users"""
        if not self.comm:
            return
        
        # Find users subscribed to proximity alerts
        recipients = []
        for user_id, subscription in self.subscriptions.items():
            if subscription.proximity_alerts and user_id != alert.node_id:
                recipients.append(user_id)
        
        if not recipients:
            return
        
        # Format alert message
        aircraft_str = " ✈️" if alert.is_aircraft else ""
        altitude_str = f" at {alert.altitude:.0f}m" if alert.altitude else ""
        
        alert_message = f"📡 Proximity Alert: {alert.node_name} detected {alert.distance:.1f}km away{altitude_str}{aircraft_str}"
        
        # Send to recipients
        for user_id in recipients:
            try:
                from src.models.message import Message, MessageType
                message = Message(
                    id=f"proximity_{alert.id}_{user_id}",
                    sender_id="weather_service",
                    recipient_id=user_id,
                    channel=0,
                    content=alert_message,
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.DIRECT_MESSAGE,
                    interface_id="weather"
                )
                
                await self.comm.send_mesh_message(message)
                
            except Exception as e:
                self.logger.error(f"Failed to send proximity alert to {user_id}: {e}")
    
    async def _broadcast_environmental_alert(self, reading: EnvironmentalReading):
        """Broadcast environmental alert to subscribed users"""
        if not self.comm:
            return
        
        # Find users subscribed to environmental alerts
        recipients = []
        for user_id, subscription in self.subscriptions.items():
            # For now, send to users with proximity alerts enabled
            if subscription.proximity_alerts:
                recipients.append(user_id)
        
        if not recipients:
            return
        
        # Format alert message based on sensor type
        if reading.sensor_type == "rf_monitor":
            frequency = reading.get_reading('frequency_hz') / 1e6  # Convert to MHz
            snr = reading.get_reading('snr_db')
            alert_message = f"📻 RF Alert: High signal ({snr:.1f}dB SNR) detected on {frequency:.3f} MHz"
        else:
            alert_message = f"🌡️ Environmental Alert: {reading.sensor_type} - {reading.sensor_id}"
        
        # Send to recipients
        for user_id in recipients:
            try:
                from src.models.message import Message, MessageType
                message = Message(
                    id=f"env_{reading.sensor_id}_{user_id}",
                    sender_id="weather_service",
                    recipient_id=user_id,
                    channel=0,
                    content=alert_message,
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.DIRECT_MESSAGE,
                    interface_id="weather"
                )
                
                await self.comm.send_mesh_message(message)
                
            except Exception as e:
                self.logger.error(f"Failed to send environmental alert to {user_id}: {e}")
    
    def update_node_position(self, node_id: str, location: Location, 
                           altitude: Optional[float] = None, metadata: Dict[str, Any] = None):
        """
        Update a node's position for proximity monitoring
        
        Args:
            node_id: Node identifier
            location: Node location
            altitude: Node altitude in meters
            metadata: Additional node metadata
        """
        if self.environmental_monitor:
            self.environmental_monitor.update_node_position(node_id, location, altitude, metadata)
    
    async def correlate_aircraft(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Correlate high-altitude nodes with aircraft data
        
        Args:
            nodes: List of node data with location and altitude
            
        Returns:
            Dictionary mapping node IDs to aircraft data
        """
        if not self.environmental_monitor:
            return {}
        
        return await self.environmental_monitor.correlate_aircraft(nodes)
    
    def _handle_file_sensor_alert(self, alert_data: Any):
        """Handle file and sensor monitoring alerts"""
        try:
            from .file_sensor_monitoring import FileChangeEvent
            from .models import EnvironmentalReading
            
            if isinstance(alert_data, FileChangeEvent):
                # Handle file change alert
                self.logger.info(f"File change alert: {alert_data.event_type} - {alert_data.file_path}")
                asyncio.create_task(self._broadcast_file_change_alert(alert_data))
                
            elif isinstance(alert_data, EnvironmentalReading):
                # Handle sensor alert
                self.logger.info(f"Sensor alert: {alert_data.sensor_type} - {alert_data.sensor_id}")
                asyncio.create_task(self._broadcast_sensor_alert(alert_data))
                
        except Exception as e:
            self.logger.error(f"Error handling file/sensor alert: {e}")
    
    async def _broadcast_file_change_alert(self, change_event):
        """Broadcast file change alert to subscribed users"""
        if not self.comm:
            return
        
        # Find users subscribed to file monitoring alerts
        recipients = []
        for user_id, subscription in self.subscriptions.items():
            # For now, send to users with proximity alerts enabled (could add specific file alert subscription)
            if subscription.proximity_alerts:
                recipients.append(user_id)
        
        if not recipients:
            return
        
        # Format alert message
        file_name = os.path.basename(change_event.file_path)
        alert_message = f"📁 File Alert: {file_name} was {change_event.event_type}"
        
        if change_event.file_size:
            size_kb = change_event.file_size / 1024
            alert_message += f" ({size_kb:.1f} KB)"
        
        # Send to recipients
        for user_id in recipients:
            try:
                from src.models.message import Message, MessageType
                message = Message(
                    id=f"file_{change_event.timestamp.timestamp()}_{user_id}",
                    sender_id="weather_service",
                    recipient_id=user_id,
                    channel=0,
                    content=alert_message,
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.DIRECT_MESSAGE,
                    interface_id="weather"
                )
                
                await self.comm.send_mesh_message(message)
                
            except Exception as e:
                self.logger.error(f"Failed to send file change alert to {user_id}: {e}")
    
    async def _broadcast_sensor_alert(self, reading):
        """Broadcast sensor alert to subscribed users"""
        if not self.comm:
            return
        
        # Find users subscribed to sensor alerts
        recipients = []
        for user_id, subscription in self.subscriptions.items():
            # For now, send to users with proximity alerts enabled
            if subscription.proximity_alerts:
                recipients.append(user_id)
        
        if not recipients:
            return
        
        # Format alert message
        sensor_name = reading.sensor_id
        sensor_type = reading.sensor_type
        
        # Get the most significant reading
        max_reading = max(reading.readings.values()) if reading.readings else 0
        max_param = max(reading.readings.keys(), key=lambda k: reading.readings[k]) if reading.readings else "value"
        
        alert_message = f"🌡️ Sensor Alert: {sensor_name} ({sensor_type}) - {max_param}: {max_reading:.2f}"
        
        # Send to recipients
        for user_id in recipients:
            try:
                from src.models.message import Message, MessageType
                message = Message(
                    id=f"sensor_{reading.sensor_id}_{user_id}",
                    sender_id="weather_service",
                    recipient_id=user_id,
                    channel=0,
                    content=alert_message,
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.DIRECT_MESSAGE,
                    interface_id="weather"
                )
                
                await self.comm.send_mesh_message(message)
                
            except Exception as e:
                self.logger.error(f"Failed to send sensor alert to {user_id}: {e}")
    
    def get_recent_file_changes(self, hours_back: int = 1) -> List[Any]:
        """Get recent file changes"""
        if not self.file_sensor_monitor:
            return []
        
        return self.file_sensor_monitor.get_recent_file_changes(hours_back)
    
    def get_sensor_readings(self) -> List[Any]:
        """Get current sensor readings"""
        if not self.file_sensor_monitor:
            return []
        
        return self.file_sensor_monitor.get_sensor_readings()
    
    def get_sensor_status(self) -> Dict[str, Dict[str, Any]]:
        """Get sensor status"""
        if not self.file_sensor_monitor:
            return {}
        
        return self.file_sensor_monitor.get_sensor_status()
    
    # Location management methods
    async def set_user_location(self, user_id: str, latitude: float, longitude: float, 
                              name: Optional[str] = None) -> str:
        """Set user location for weather alerts"""
        try:
            location = Location(
                latitude=latitude,
                longitude=longitude,
                name=name
            )
            
            # Update location in location filter
            if self.location_filter:
                updated = self.location_filter.update_user_location(
                    user_id, location, LocationAccuracy.MEDIUM, "manual"
                )
                
                if updated:
                    # Update subscription location
                    subscription = self.subscriptions.get(user_id)
                    if not subscription:
                        subscription = WeatherSubscription(user_id=user_id)
                        self.subscriptions[user_id] = subscription
                    
                    subscription.location = location
                    await self._save_subscriptions()
                    
                    location_str = f"{latitude:.4f}, {longitude:.4f}"
                    if name:
                        location_str += f" ({name})"
                    
                    return f"✅ Location set to {location_str}"
                else:
                    return "ℹ️ Location updated (minor change)"
            else:
                return "❌ Location services not available"
                
        except Exception as e:
            self.logger.error(f"Failed to set location for {user_id}: {e}")
            return "❌ Failed to set location"
    
    async def get_user_location_info(self, user_id: str) -> str:
        """Get user location information"""
        if not self.location_filter:
            return "❌ Location services not available"
        
        location_update = self.location_filter.get_user_location(user_id)
        if not location_update:
            return "❌ No location set. Use 'set_location <lat> <lon> [name]' to set your location."
        
        location = location_update.location
        age = datetime.utcnow() - location_update.timestamp
        
        location_str = f"{location.latitude:.4f}, {location.longitude:.4f}"
        if location.name:
            location_str += f" ({location.name})"
        
        info_lines = [
            f"📍 Your location: {location_str}",
            f"Accuracy: {location_update.accuracy.value}",
            f"Source: {location_update.source}",
            f"Updated: {age.total_seconds() / 3600:.1f} hours ago"
        ]
        
        return "\n".join(info_lines)
    
    async def get_nearby_users(self, user_id: str, radius_km: float = 10.0) -> str:
        """Get nearby users"""
        if not self.location_filter:
            return "❌ Location services not available"
        
        user_location_update = self.location_filter.get_user_location(user_id)
        if not user_location_update:
            return "❌ Your location is not set. Use 'set_location' first."
        
        nearby_users = self.location_filter.get_users_in_area(
            user_location_update.location, radius_km
        )
        
        # Filter out the requesting user
        nearby_users = [(uid, loc) for uid, loc in nearby_users if uid != user_id]
        
        if not nearby_users:
            return f"📡 No other users found within {radius_km:.1f}km"
        
        report_lines = [f"📡 {len(nearby_users)} user(s) within {radius_km:.1f}km:"]
        
        for other_user_id, location_update in nearby_users[:5]:  # Limit to 5 users
            distance = user_location_update.location.distance_to(location_update.location)
            age = datetime.utcnow() - location_update.timestamp
            
            user_name = location_update.location.name or other_user_id
            report_lines.append(f"• {user_name}: {distance:.1f}km away ({age.total_seconds() / 3600:.1f}h ago)")
        
        if len(nearby_users) > 5:
            report_lines.append(f"... and {len(nearby_users) - 5} more")
        
        return "\n".join(report_lines)
    
    def _handle_location_update(self, location_update):
        """Handle location update events"""
        self.logger.debug(f"Location update for {location_update.user_id}")
        
        # Update environmental monitoring with new location
        if self.environmental_monitor:
            self.environmental_monitor.update_node_position(
                location_update.user_id,
                location_update.location,
                metadata={'source': location_update.source, 'accuracy': location_update.accuracy.value}
            )
    
    def _handle_geofence_event(self, user_id: str, zone_id: str, entered: bool):
        """Handle geofence events"""
        action = "entered" if entered else "exited"
        self.logger.info(f"Geofence event: {user_id} {action} {zone_id}")
        
        # Could broadcast geofence alerts here if needed
        # For now, just log the event
    
    async def _cleanup_expired_data(self):
        """Clean up expired cache entries and old alerts"""
        # Cache cleanup is handled by cache manager
        
        # Clean up old alerts
        expired_alerts = []
        for alert_id, alert in self.active_alerts.items():
            if not alert.is_active():
                expired_alerts.append(alert_id)
        
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
        
        self.logger.debug(f"Cleaned up {len(expired_alerts)} alerts")
    
    # Utility methods
    def _parse_location(self, location_config: Any) -> Optional[Location]:
        """Parse location from configuration"""
        if not location_config:
            return None
        
        if isinstance(location_config, dict):
            return Location(
                latitude=location_config.get('latitude', 0.0),
                longitude=location_config.get('longitude', 0.0),
                name=location_config.get('name'),
                country=location_config.get('country'),
                state=location_config.get('state'),
                county=location_config.get('county'),
                fips_code=location_config.get('fips_code'),
                same_code=location_config.get('same_code')
            )
        
        return None
    

    
    def _format_weather_report(self, weather_data: WeatherData, detailed: bool) -> str:
        """Format weather data into a report"""
        current = weather_data.current
        location = weather_data.location
        
        # Basic report
        report_lines = [
            f"🌤️ Weather for {location.name or f'{location.latitude:.2f}, {location.longitude:.2f}'}",
            f"Temperature: {current.temperature:.1f}°C",
            f"Humidity: {current.humidity:.0f}%",
            f"Wind: {current.wind_speed:.1f} km/h"
        ]
        
        if current.description:
            report_lines.append(f"Conditions: {current.description}")
        
        if detailed:
            report_lines.extend([
                f"Pressure: {current.pressure:.1f} hPa",
                f"Visibility: {current.visibility or 'N/A'} km",
                f"Cloud cover: {current.cloud_cover or 'N/A'}%"
            ])
            
            if current.uv_index:
                report_lines.append(f"UV Index: {current.uv_index:.1f}")
        
        report_lines.append(f"Updated: {weather_data.timestamp.strftime('%H:%M UTC')}")
        
        return "\n".join(report_lines)
    
    def _format_forecast_report(self, weather_data: WeatherData, days: int) -> str:
        """Format forecast data into a report"""
        forecasts = weather_data.forecasts[:days]
        location = weather_data.location
        
        report_lines = [
            f"📅 {days}-day forecast for {location.name or f'{location.latitude:.2f}, {location.longitude:.2f}'}"
        ]
        
        for forecast in forecasts:
            date_str = forecast.timestamp.strftime('%m/%d')
            temp_range = f"{forecast.temperature_min:.0f}-{forecast.temperature_max:.0f}°C"
            precip = f"{forecast.precipitation_probability:.0f}%" if forecast.precipitation_probability > 0 else "0%"
            
            line = f"{date_str}: {temp_range}, {precip} rain"
            if forecast.description:
                line += f", {forecast.description}"
            
            report_lines.append(line)
        
        return "\n".join(report_lines)
    
    def _format_current_conditions(self, current, location: Location) -> str:
        """Format current conditions"""
        return f"🌡️ {location.name or 'Current location'}: {current.temperature:.1f}°C, {current.humidity:.0f}% humidity, {current.wind_speed:.1f} km/h wind"
    
    def _format_alerts(self, alerts: List[WeatherAlert]) -> str:
        """Format alerts into a report"""
        if not alerts:
            return "✅ No active alerts."
        
        report_lines = [f"⚠️ {len(alerts)} active alert(s):"]
        
        for alert in alerts[:5]:  # Limit to 5 alerts
            severity_emoji = {
                AlertSeverity.MINOR: "🟡",
                AlertSeverity.MODERATE: "🟠", 
                AlertSeverity.SEVERE: "🔴",
                AlertSeverity.EXTREME: "🚨"
            }.get(alert.severity, "⚠️")
            
            report_lines.append(f"{severity_emoji} {alert.title}")
            if alert.description and len(alert.description) < 100:
                report_lines.append(f"   {alert.description}")
        
        if len(alerts) > 5:
            report_lines.append(f"... and {len(alerts) - 5} more alerts")
        
        return "\n".join(report_lines)
    
    def _format_proximity_alerts(self, alerts: List[ProximityAlert]) -> str:
        """Format proximity alerts"""
        if not alerts:
            return "📡 No proximity alerts."
        
        report_lines = [f"📡 {len(alerts)} proximity alert(s):"]
        
        for alert in alerts[:3]:  # Limit to 3 alerts
            distance_str = f"{alert.distance:.1f} km"
            altitude_str = f", {alert.altitude:.0f}m" if alert.altitude else ""
            aircraft_str = " ✈️" if alert.is_aircraft else ""
            
            report_lines.append(f"• {alert.node_name or alert.node_id}: {distance_str}{altitude_str}{aircraft_str}")
        
        if len(alerts) > 3:
            report_lines.append(f"... and {len(alerts) - 3} more")
        
        return "\n".join(report_lines)
    
    # Data persistence
    
    async def _load_subscriptions(self):
        """Load user subscriptions from disk"""
        subs_file = self.data_dir / "subscriptions.json"
        if subs_file.exists():
            try:
                with open(subs_file, 'r') as f:
                    subs_data = json.load(f)
                
                for user_id, sub_data in subs_data.items():
                    # TODO: Deserialize subscription data
                    subscription = WeatherSubscription(user_id=user_id)
                    self.subscriptions[user_id] = subscription
                
                self.logger.debug(f"Loaded {len(self.subscriptions)} subscriptions")
            except Exception as e:
                self.logger.warning(f"Failed to load subscriptions: {e}")
    
    async def _save_subscriptions(self):
        """Save user subscriptions to disk"""
        subs_file = self.data_dir / "subscriptions.json"
        try:
            subs_data = {}
            for user_id, subscription in self.subscriptions.items():
                # TODO: Serialize subscription data
                subs_data[user_id] = {
                    'user_id': user_id,
                    'weather_updates': subscription.weather_updates,
                    'forecast_updates': subscription.forecast_updates,
                    'severe_weather_alerts': subscription.severe_weather_alerts,
                    'earthquake_alerts': subscription.earthquake_alerts,
                    'proximity_alerts': subscription.proximity_alerts,
                    'aircraft_alerts': subscription.aircraft_alerts,
                    'alert_radius_km': subscription.alert_radius_km
                }
            
            with open(subs_file, 'w') as f:
                json.dump(subs_data, f, indent=2)
            
            self.logger.debug(f"Saved {len(subs_data)} subscriptions")
        except Exception as e:
            self.logger.warning(f"Failed to save subscriptions: {e}")