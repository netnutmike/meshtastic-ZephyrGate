"""
Weather Alert Plugin - Example of HTTP requests and scheduled tasks

This plugin demonstrates:
- Making HTTP requests to external APIs
- Scheduled task execution
- Data caching with TTL
- Configuration management
- Error handling for network requests

The plugin fetches weather data from an API and sends alerts when
certain conditions are met (e.g., severe weather warnings).
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
from src.core.enhanced_plugin import EnhancedPlugin


class WeatherAlertPlugin(EnhancedPlugin):
    """
    Weather alert plugin that fetches weather data and sends alerts.
    
    Features:
    - Periodic weather data fetching via HTTP
    - Configurable alert thresholds
    - Data caching to reduce API calls
    - Command interface for manual checks
    """
    
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        self.logger.info("Initializing Weather Alert Plugin")
        
        # Register commands
        self.register_command(
            "weather",
            self.handle_weather_command,
            "Get current weather for a location",
            priority=100
        )
        
        self.register_command(
            "weatheralert",
            self.handle_alert_command,
            "Check for weather alerts",
            priority=100
        )
        
        self.register_command(
            "weatherconfig",
            self.handle_config_command,
            "Show weather alert configuration",
            priority=100
        )
        
        # Register scheduled tasks
        check_interval = self.get_config("check_interval", 1800)  # Default: 30 minutes
        self.register_scheduled_task(
            "weather_check",
            check_interval,
            self.check_weather_task
        )
        
        # Register hourly cleanup task
        self.register_scheduled_task(
            "cache_cleanup",
            3600,  # 1 hour
            self.cleanup_cache_task
        )
        
        return True
    
    async def handle_weather_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'weather' command to get current weather.
        
        Usage: weather <location>
        """
        if not args:
            return "Usage: weather <location>"
        
        location = " ".join(args)
        
        try:
            # Check cache first
            cache_key = f"weather_{location}"
            cached_data = await self.retrieve_data(cache_key)
            
            if cached_data:
                self.logger.info(f"Using cached weather data for {location}")
                return self._format_weather_response(cached_data, from_cache=True)
            
            # Fetch fresh data
            weather_data = await self._fetch_weather(location)
            
            if weather_data:
                # Cache for 30 minutes
                await self.store_data(cache_key, weather_data, ttl=1800)
                return self._format_weather_response(weather_data, from_cache=False)
            else:
                return f"Could not fetch weather data for {location}"
                
        except Exception as e:
            self.logger.error(f"Error fetching weather: {e}")
            return f"Error: {str(e)}"
    
    async def handle_alert_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'weatheralert' command to check for alerts.
        
        Usage: weatheralert [location]
        """
        location = " ".join(args) if args else self.get_config("default_location", "")
        
        if not location:
            return "Usage: weatheralert <location> or configure default_location"
        
        try:
            alerts = await self._check_alerts(location)
            
            if not alerts:
                return f"No weather alerts for {location}"
            
            response = [f"Weather Alerts for {location}:"]
            response.append("=" * 40)
            
            for alert in alerts:
                response.append(f"• {alert['type']}: {alert['description']}")
                response.append(f"  Severity: {alert['severity']}")
                response.append("")
            
            return "\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Error checking alerts: {e}")
            return f"Error: {str(e)}"
    
    async def handle_config_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Show current weather alert configuration"""
        config_items = [
            "Weather Alert Configuration:",
            "=" * 40,
            f"Default Location: {self.get_config('default_location', 'Not set')}",
            f"Check Interval: {self.get_config('check_interval', 1800)}s",
            f"Alert Enabled: {self.get_config('alerts_enabled', True)}",
            f"Temperature Threshold: {self.get_config('temp_threshold', 35)}°C",
            f"Wind Speed Threshold: {self.get_config('wind_threshold', 50)} km/h",
            "",
            "Alert Types:",
        ]
        
        alert_types = self.get_config('alert_types', ['severe', 'warning'])
        for alert_type in alert_types:
            config_items.append(f"  • {alert_type}")
        
        return "\n".join(config_items)
    
    async def check_weather_task(self):
        """
        Scheduled task to check weather and send alerts.
        
        This runs periodically based on check_interval configuration.
        """
        self.logger.info("Running scheduled weather check")
        
        # Check if alerts are enabled
        if not self.get_config("alerts_enabled", True):
            self.logger.info("Weather alerts are disabled")
            return
        
        # Get default location
        location = self.get_config("default_location", "")
        if not location:
            self.logger.warning("No default location configured")
            return
        
        try:
            # Check for alerts
            alerts = await self._check_alerts(location)
            
            if alerts:
                # Send alert message to mesh
                alert_message = self._format_alert_message(location, alerts)
                await self.send_message(alert_message)
                self.logger.info(f"Sent weather alert for {location}")
                
                # Store alert history
                await self._store_alert_history(location, alerts)
            else:
                self.logger.info(f"No alerts for {location}")
                
        except Exception as e:
            self.logger.error(f"Error in weather check task: {e}")
    
    async def cleanup_cache_task(self):
        """
        Scheduled task to clean up old cached data.
        
        This runs hourly to remove expired cache entries.
        """
        self.logger.info("Running cache cleanup")
        
        try:
            # Get all cached weather keys
            # Note: In a real implementation, you'd track cache keys
            cleanup_count = 0
            
            # Store cleanup timestamp
            await self.store_data("last_cleanup", datetime.utcnow().isoformat())
            
            self.logger.info(f"Cache cleanup completed: {cleanup_count} entries removed")
            
        except Exception as e:
            self.logger.error(f"Error in cache cleanup: {e}")
    
    async def _fetch_weather(self, location: str) -> Dict[str, Any]:
        """
        Fetch weather data from API.
        
        In a real implementation, this would call an actual weather API.
        For this example, we simulate the API call.
        """
        self.logger.info(f"Fetching weather data for {location}")
        
        # Simulate API call with delay
        await asyncio.sleep(0.1)
        
        # Simulate weather data
        # In production, use: data = await self.http_get(api_url, params={'location': location})
        weather_data = {
            'location': location,
            'temperature': 25,
            'humidity': 65,
            'wind_speed': 15,
            'conditions': 'Partly Cloudy',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return weather_data
    
    async def _check_alerts(self, location: str) -> List[Dict[str, Any]]:
        """
        Check for weather alerts.
        
        Returns list of active alerts for the location.
        """
        self.logger.info(f"Checking alerts for {location}")
        
        # Get weather data
        weather_data = await self._fetch_weather(location)
        
        alerts = []
        
        # Check temperature threshold
        temp_threshold = self.get_config('temp_threshold', 35)
        if weather_data['temperature'] > temp_threshold:
            alerts.append({
                'type': 'High Temperature',
                'description': f"Temperature {weather_data['temperature']}°C exceeds threshold {temp_threshold}°C",
                'severity': 'warning'
            })
        
        # Check wind speed threshold
        wind_threshold = self.get_config('wind_threshold', 50)
        if weather_data['wind_speed'] > wind_threshold:
            alerts.append({
                'type': 'High Wind',
                'description': f"Wind speed {weather_data['wind_speed']} km/h exceeds threshold {wind_threshold} km/h",
                'severity': 'warning'
            })
        
        return alerts
    
    def _format_weather_response(self, data: Dict[str, Any], from_cache: bool = False) -> str:
        """Format weather data for display"""
        cache_note = " (cached)" if from_cache else ""
        
        response = [
            f"Weather for {data['location']}{cache_note}:",
            "=" * 40,
            f"Temperature: {data['temperature']}°C",
            f"Humidity: {data['humidity']}%",
            f"Wind Speed: {data['wind_speed']} km/h",
            f"Conditions: {data['conditions']}",
            f"Updated: {data['timestamp']}"
        ]
        
        return "\n".join(response)
    
    def _format_alert_message(self, location: str, alerts: List[Dict[str, Any]]) -> str:
        """Format alert message for mesh broadcast"""
        alert_count = len(alerts)
        alert_types = ", ".join(a['type'] for a in alerts)
        
        return f"⚠️ Weather Alert for {location}: {alert_count} alert(s) - {alert_types}"
    
    async def _store_alert_history(self, location: str, alerts: List[Dict[str, Any]]):
        """Store alert history for tracking"""
        history_key = f"alert_history_{location}"
        
        # Get existing history
        history = await self.retrieve_data(history_key, [])
        
        # Add new entry
        history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'alerts': alerts
        })
        
        # Keep only last 10 entries
        history = history[-10:]
        
        # Store updated history (keep for 7 days)
        await self.store_data(history_key, history, ttl=604800)


# Example configuration for this plugin (in config.yaml):
"""
plugins:
  weather_alert:
    enabled: true
    default_location: "San Francisco"
    check_interval: 1800  # 30 minutes
    alerts_enabled: true
    temp_threshold: 35  # Celsius
    wind_threshold: 50  # km/h
    alert_types:
      - severe
      - warning
"""
