"""Configuration module for Villages Event Scraper.

This module contains all configuration constants including URLs,
venue mappings, HTTP settings, valid output formats, and configurable
output fields for customizing which data fields are included in the output.
"""

"""
Copyright (C) 2025

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""



class Config:
    """Application configuration and constants."""
    
    # URLs (base URLs with placeholders)
    JS_URL = "https://cdn.thevillages.com/web_components/myvillages-auth-forms/main.js"
    
    # Date range options
    VALID_DATE_RANGES = [
        "today",
        "tomorrow",
        "this-week",
        "next-week",
        "this-month",
        "next-month",
        "all"  # No date range filter
    ]
    DEFAULT_DATE_RANGE = "today"
    
    # Category options
    VALID_CATEGORIES = [
        "entertainment",
        "arts-and-crafts",
        "health-and-wellness",
        "recreation",
        "social-clubs",
        "special-events",
        "sports",
        "all"  # All event types (no category filter)
    ]
    DEFAULT_CATEGORY = "entertainment"
    
    # Location options
    VALID_LOCATIONS = [
        "town-squares",
        "Lake+Sumter+Landing+Market+Square",
        "Spanish+Springs+Town+Square",
        "Brownwood+Paddock+Square",
        "Sawgrass+Grove",
        "The+Show+Kitchen+at+Sawgrass+Grove",
        "entertainment",
        "The+Sharon",
        "The+Studio+Theatre+at+Tierra+Del+Sol",
        "sports-recreation",
        "Savannah+Recreation",
        "sports",
        "executive-golf",
        "Polo+Club",
        "all"  # All locations (no location filter)
    ]
    DEFAULT_LOCATION = "town-squares"
    
    # Default venue mappings
    DEFAULT_VENUE_MAPPINGS = {
        "Brownwood": "Brownwood",
        "Sawgrass": "Sawgrass",
        "Spanish Springs": "Spanish Springs",
        "Lake Sumter": "Lake Sumter"
    }
    
    # HTTP settings
    DEFAULT_TIMEOUT = 10
    USER_AGENT = "Mozilla/5.0"
    
    # Output formats
    VALID_FORMATS = ["meshtastic", "json", "csv", "plain"]
    DEFAULT_FORMAT = "meshtastic"
    
    # Preamble
    DEFAULT_PREAMBLE = ""
    
    # Output fields configuration
    # Default fields maintain backward compatibility with original implementation
    DEFAULT_OUTPUT_FIELDS = ["location.title", "title"]
    
    # Available fields from API response that can be included in output
    # These field paths use dot notation for nested fields (e.g., "location.title", "start.date")
    AVAILABLE_FIELDS = [
        "title",
        "description",
        "excerpt",
        "category",
        "subcategories",
        "start.date",
        "end.date",
        "allDay",
        "cancelled",
        "featured",
        "location.title",
        "location.category",
        "location.id",
        "address.streetAddress",
        "address.locality",
        "address.region",
        "address.postalCode",
        "address.country",
        "image",
        "url",
        "otherInfo",
        "id"
    ]
    
    @staticmethod
    def get_calendar_url(
        date_range: str = DEFAULT_DATE_RANGE,
        category: str = DEFAULT_CATEGORY,
        location: str = DEFAULT_LOCATION
    ) -> str:
        """Generate calendar URL with specified filters.
        
        Args:
            date_range: Date range parameter (e.g., 'today', 'this-week')
            category: Category parameter (e.g., 'entertainment', 'sports')
            location: Location parameter (e.g., 'town-squares', 'Brownwood+Paddock+Square')
            
        Returns:
            Complete calendar URL with filters
        """
        base = "https://www.thevillages.com/calendar/#/?"
        params = []
        
        # Add date range parameter if not 'all'
        if date_range != "all":
            params.append(f"dateRange={date_range}")
        
        # Add category parameter if not 'all'
        if category != "all":
            params.append(f"categories={category}")
        
        # Add location parameter if not 'all'
        if location != "all":
            params.append(f"locationCategories={location}")
        
        return base + "&".join(params) if params else base.rstrip("?")
    
    @staticmethod
    def get_api_url(
        date_range: str = DEFAULT_DATE_RANGE,
        category: str = DEFAULT_CATEGORY,
        location: str = DEFAULT_LOCATION
    ) -> str:
        """Generate API URL with specified filters.
        
        Args:
            date_range: Date range parameter (e.g., 'today', 'this-week')
            category: Category parameter (e.g., 'entertainment', 'sports')
            location: Location parameter (e.g., 'town-squares', 'Brownwood+Paddock+Square')
            
        Returns:
            Complete API URL with filters
        """
        base = "https://api.v2.thevillages.com/events/?"
        params = ["cancelled=false", "startRow=0", "endRow=24"]
        
        # Add date range parameter if not 'all'
        if date_range != "all":
            params.append(f"dateRange={date_range}")
        
        # Add category parameter if not 'all'
        if category != "all":
            params.append(f"categories={category}")
        
        # Add location parameter if not 'all'
        if location != "all":
            params.append(f"locationCategories={location}")
        
        # Always add subcategories query type
        params.append("subcategoriesQueryType=and")
        
        return base + "&".join(params)
