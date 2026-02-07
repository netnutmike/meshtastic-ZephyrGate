"""
Villages Events Service Plugin

Fetches entertainment events from The Villages API and provides formatted event data.
This plugin integrates the villages-events functionality into ZephyrGate.

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.enhanced_plugin import EnhancedPlugin
from core.plugin_manager import PluginMetadata, PluginPriority

# Import villages-events modules from local directory
try:
    from .villages_events.config import Config as VillagesConfig
    from .villages_events.token_fetcher import fetch_auth_token
    from .villages_events.session_manager import SessionManager
    from .villages_events.api_client import fetch_events
    from .villages_events.event_processor import EventProcessor
    from .villages_events.output_formatter import OutputFormatter
    from .villages_events.exceptions import VillagesEventError
except ImportError as e:
    # Fallback if imports fail
    VillagesConfig = None
    fetch_auth_token = None
    SessionManager = None
    fetch_events = None
    EventProcessor = None
    OutputFormatter = None
    VillagesEventError = Exception


class VillagesEventsServicePlugin(EnhancedPlugin):
    """
    Villages Events Service Plugin
    
    Provides commands to fetch and display events from The Villages calendar.
    """
    
    async def initialize(self) -> bool:
        """
        Initialize the plugin.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing Villages Events Service plugin")
        
        # Get configuration
        self.enabled = self.get_config("enabled", False)
        
        if not self.enabled:
            self.logger.info("Plugin is disabled in configuration (location-specific plugin)")
            return False
        
        # Check if villages-events modules are available
        if VillagesConfig is None:
            self.logger.error(
                "Failed to import villages-events modules. "
                "Ensure python-villages-events is in the correct location."
            )
            return False
        
        # Load configuration
        self.format = self.get_config("format", "meshtastic")
        self.date_range = self.get_config("date_range", "today")
        self.category = self.get_config("category", "entertainment")
        self.location = self.get_config("location", "town-squares")
        self.timeout = self.get_config("timeout", 10)
        self.venue_mappings = self.get_config("venue_mappings", {
            "Brownwood": "Brownwood",
            "Sawgrass": "Sawgrass",
            "Spanish Springs": "Spanish Springs",
            "Lake Sumter": "Lake Sumter"
        })
        self.output_fields = self.get_config("output_fields", ["location.title", "title"])
        
        # Register commands
        self.register_command(
            command="villages-events",
            handler=self.handle_villages_events_command,
            help_text="Fetch events from The Villages calendar",
            priority=100
        )
        
        self.register_command(
            command="villages-help",
            handler=self.handle_help_command,
            help_text="Show help for Villages Events commands",
            priority=100
        )
        
        self.logger.info("Villages Events Service plugin initialized successfully")
        return True
    
    async def handle_villages_events_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the villages-events command.
        
        Args:
            args: Command arguments
            context: Command context (sender, channel, etc.)
            
        Returns:
            Response message with event data
        """
        # Parse arguments
        format_type = self.format
        date_range = self.date_range
        category = self.category
        location = self.location
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg == "--format" and i + 1 < len(args):
                format_type = args[i + 1]
                i += 2
            elif arg == "--date-range" and i + 1 < len(args):
                date_range = args[i + 1]
                i += 2
            elif arg == "--category" and i + 1 < len(args):
                category = args[i + 1]
                i += 2
            elif arg == "--location" and i + 1 < len(args):
                location = args[i + 1]
                i += 2
            else:
                i += 1
        
        # Validate arguments
        if format_type not in VillagesConfig.VALID_FORMATS:
            return f"Invalid format: {format_type}. Valid options: {', '.join(VillagesConfig.VALID_FORMATS)}"
        
        if date_range not in VillagesConfig.VALID_DATE_RANGES:
            return f"Invalid date range: {date_range}. Valid options: {', '.join(VillagesConfig.VALID_DATE_RANGES)}"
        
        if category not in VillagesConfig.VALID_CATEGORIES:
            return f"Invalid category: {category}. Valid options: {', '.join(VillagesConfig.VALID_CATEGORIES)}"
        
        if location not in VillagesConfig.VALID_LOCATIONS:
            return f"Invalid location: {location}. Valid options: {', '.join(VillagesConfig.VALID_LOCATIONS)}"
        
        try:
            # Fetch events
            self.logger.info(
                f"Fetching events: date_range={date_range}, category={category}, "
                f"location={location}, format={format_type}"
            )
            
            # Generate URLs
            calendar_url = VillagesConfig.get_calendar_url(date_range, category, location)
            api_url = VillagesConfig.get_api_url(date_range, category, location)
            
            # Fetch authentication token
            auth_token = fetch_auth_token(VillagesConfig.JS_URL, timeout=self.timeout)
            
            # Establish session and fetch events
            with SessionManager() as session_manager:
                session_manager.establish_session(calendar_url, timeout=self.timeout)
                session = session_manager.get_session()
                
                # Fetch events from API
                api_response = fetch_events(
                    session=session,
                    api_url=api_url,
                    auth_token=auth_token,
                    timeout=self.timeout
                )
                
                # Process events
                processor = EventProcessor(self.venue_mappings, output_fields=self.output_fields)
                processed_events = processor.process_events(api_response)
                
                # Format output
                formatted_output = OutputFormatter.format_events(
                    processed_events,
                    format_type=format_type,
                    field_names=self.output_fields
                )
                
                # Return formatted output
                if not processed_events:
                    return f"No events found for {date_range} in category '{category}' at location '{location}'"
                
                return formatted_output
        
        except VillagesEventError as e:
            self.logger.error(f"Villages Event Error: {e}")
            return f"Error fetching events: {e}"
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            return f"Unexpected error: {e}"
    
    async def handle_help_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the villages-help command.
        
        Args:
            args: Command arguments
            context: Command context
            
        Returns:
            Help message
        """
        help_text = """Villages Events Service Commands:

villages-events [options]
  Fetch events from The Villages calendar
  
  Options:
    --format <format>        Output format (meshtastic, json, csv, plain)
    --date-range <range>     Date range (today, tomorrow, this-week, next-week, this-month, next-month, all)
    --category <category>    Event category (entertainment, arts-and-crafts, health-and-wellness, recreation, social-clubs, special-events, sports, all)
    --location <location>    Event location (town-squares, all, or specific location)
  
  Examples:
    villages-events
    villages-events --format json --date-range this-week
    villages-events --category sports --location Brownwood+Paddock+Square
    
villages-help
  Show this help message
"""
        return help_text
    
    async def get_events_report(
        self,
        user_id: str = 'system',
        format_type: str = None,
        date_range: str = None,
        category: str = None,
        location: str = None,
        preamble: str = None
    ) -> str:
        """
        Get events report - exposed for scheduled broadcasts and plugin calls.
        
        Args:
            user_id: User ID (for logging, not used for filtering)
            format_type: Output format (meshtastic, json, csv, plain)
            date_range: Date range filter
            category: Category filter
            location: Location filter
            preamble: Optional prefix string to add before the output
            
        Returns:
            Formatted events report string
        """
        # Use provided values or fall back to config defaults
        format_type = format_type or self.format
        date_range = date_range or self.date_range
        category = category or self.category
        location = location or self.location
        
        try:
            self.logger.info(
                f"Getting events report for {user_id}: "
                f"format={format_type}, date_range={date_range}, "
                f"category={category}, location={location}"
            )
            
            # Generate URLs
            calendar_url = VillagesConfig.get_calendar_url(date_range, category, location)
            api_url = VillagesConfig.get_api_url(date_range, category, location)
            
            # Fetch authentication token
            auth_token = fetch_auth_token(VillagesConfig.JS_URL, timeout=self.timeout)
            
            # Establish session and fetch events
            with SessionManager() as session_manager:
                session_manager.establish_session(calendar_url, timeout=self.timeout)
                session = session_manager.get_session()
                
                # Fetch events from API
                api_response = fetch_events(
                    session=session,
                    api_url=api_url,
                    auth_token=auth_token,
                    timeout=self.timeout
                )
                
                # Process events
                processor = EventProcessor(self.venue_mappings, output_fields=self.output_fields)
                processed_events = processor.process_events(api_response)
                
                # Format output
                formatted_output = OutputFormatter.format_events(
                    processed_events,
                    format_type=format_type,
                    field_names=self.output_fields
                )
                
                # Return message if no events
                if not processed_events:
                    return f"No events found for {date_range}"
                
                # Add preamble if provided
                if preamble:
                    # Add separator based on format type
                    if format_type == 'meshtastic':
                        # For meshtastic, add # separator if preamble doesn't end with it
                        if not preamble.endswith('#'):
                            preamble += '#'
                    else:
                        # For other formats, add newline if preamble doesn't end with one
                        if not preamble.endswith('\n'):
                            preamble += '\n'
                    
                    formatted_output = preamble + formatted_output
                
                return formatted_output
        
        except VillagesEventError as e:
            self.logger.error(f"Villages Event Error in get_events_report: {e}")
            return f"Error fetching events: {e}"
        except Exception as e:
            self.logger.error(f"Unexpected error in get_events_report: {e}", exc_info=True)
            return f"Error getting events report: {e}"
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin.
        """
        self.logger.info("Shutting down Villages Events Service plugin")
        await super().shutdown()
    
    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.
        
        Returns:
            Plugin metadata
        """
        return PluginMetadata(
            name="villages_events_service",
            version="1.0.0",
            description="Fetches entertainment events from The Villages API",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL,
            enabled=self.get_config("enabled", False)
        )


def create_plugin(name: str, config: dict, plugin_manager):
    """
    Create and return plugin instance.
    
    Args:
        name: Plugin name
        config: Plugin configuration
        plugin_manager: Plugin manager instance
        
    Returns:
        Plugin instance
    """
    return VillagesEventsServicePlugin(name, config, plugin_manager)
