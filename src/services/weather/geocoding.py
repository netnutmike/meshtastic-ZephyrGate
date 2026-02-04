"""
Geocoding utilities for weather service

Provides zipcode and location name lookup to coordinates.
"""

import logging
from typing import Optional, Dict, Any
from .models import Location


class GeocodingService:
    """Service for geocoding locations and zipcodes"""
    
    def __init__(self, openmeteo_client=None):
        self.logger = logging.getLogger(__name__)
        self.openmeteo_client = openmeteo_client
    
    async def geocode_zipcode(self, zipcode: str, country: str = "US") -> Optional[Location]:
        """
        Geocode a zipcode to coordinates using Zippopotam.us API
        
        Args:
            zipcode: Postal/ZIP code
            country: Country code (default: US)
            
        Returns:
            Location object or None if not found
        """
        if not self.openmeteo_client:
            self.logger.error("OpenMeteo client not available for geocoding")
            return None
        
        try:
            # First, try Zippopotam.us API for zipcode lookup (works great for US zipcodes)
            if country.upper() == "US":
                zippo_url = f"https://api.zippopotam.us/us/{zipcode}"
                self.logger.info(f"Looking up zipcode {zipcode} using Zippopotam.us API")
                
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(zippo_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                # Extract location data
                                if 'places' in data and len(data['places']) > 0:
                                    place = data['places'][0]
                                    city = place.get('place name', '')
                                    state = place.get('state abbreviation', '')
                                    latitude = float(place.get('latitude', 0))
                                    longitude = float(place.get('longitude', 0))
                                    
                                    location = Location(
                                        latitude=latitude,
                                        longitude=longitude,
                                        name=f"{city}, {state}",
                                        country="US",
                                        state=state
                                    )
                                    
                                    self.logger.info(f"✅ Geocoded zipcode {zipcode} to {location.name} ({latitude}, {longitude})")
                                    return location
                            elif response.status == 404:
                                self.logger.warning(f"Zipcode {zipcode} not found in Zippopotam.us database")
                            else:
                                self.logger.warning(f"Zippopotam.us API returned status {response.status}")
                except Exception as e:
                    self.logger.warning(f"Zippopotam.us API error: {e}, falling back to OpenMeteo")
            
            # Fallback to OpenMeteo geocoding (doesn't work well for zipcodes but try anyway)
            self.logger.info(f"Falling back to OpenMeteo geocoding for zipcode {zipcode}")
            
            # Try various query formats
            if country.upper() == "US":
                queries = [
                    zipcode,
                    f"{zipcode}, USA",
                    f"{zipcode}, United States",
                ]
            else:
                queries = [
                    f"{zipcode}, {country}",
                    zipcode
                ]
            
            # Try each query format
            for query in queries:
                self.logger.info(f"Trying OpenMeteo geocoding query: '{query}'")
                locations = await self.openmeteo_client.geocode_location(query, count=5)
                
                if locations:
                    # Filter results to match the country if possible
                    for location in locations:
                        if country.upper() == "US":
                            if location.country.upper() in ["USA", "US", "UNITED STATES"]:
                                self.logger.info(f"Geocoded {zipcode} to {location.name} ({location.latitude}, {location.longitude})")
                                return location
                        else:
                            if location.country.upper() == country.upper():
                                self.logger.info(f"Geocoded {zipcode} to {location.name} ({location.latitude}, {location.longitude})")
                                return location
                    
                    # If no country match, use first result
                    if locations:
                        location = locations[0]
                        self.logger.info(f"Geocoded {zipcode} to {location.name} ({location.latitude}, {location.longitude}) [no country match]")
                        return location
            
            self.logger.error(f"❌ Failed to geocode zipcode {zipcode} - no results from any service")
            self.logger.info(f"💡 Suggestion: Use location_name in config instead: location_name: 'The Villages, Florida'")
            return None
                
        except Exception as e:
            self.logger.error(f"Failed to geocode zipcode {zipcode}: {e}")
            return None
    
    async def geocode_location_name(self, name: str) -> Optional[Location]:
        """
        Geocode a location name to coordinates
        
        Args:
            name: Location name (city, address, etc.)
            
        Returns:
            Location object or None if not found
        """
        if not self.openmeteo_client:
            self.logger.error("OpenMeteo client not available for geocoding")
            return None
        
        try:
            locations = await self.openmeteo_client.geocode_location(name, count=1)
            
            if locations:
                location = locations[0]
                self.logger.info(f"Geocoded '{name}' to {location.name} ({location.latitude}, {location.longitude})")
                return location
            else:
                self.logger.warning(f"No results found for location: {name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to geocode location '{name}': {e}")
            return None
    
    async def parse_location_config(self, config: Dict[str, Any]) -> Optional[Location]:
        """
        Parse location from config, supporting multiple formats:
        - latitude/longitude
        - zipcode
        - location name
        
        Args:
            config: Location configuration dict
            
        Returns:
            Location object or None if invalid
        """
        self.logger.info(f"parse_location_config called with: {config}")
        
        if not config:
            self.logger.warning("Config is None or empty")
            return None
        
        # Check for zipcode first
        if 'zipcode' in config:
            zipcode = str(config['zipcode'])
            country = config.get('country', 'US')
            self.logger.info(f"Found zipcode in config: {zipcode}, country: {country}")
            location = await self.geocode_zipcode(zipcode, country)
            if location:
                # Override name if provided in config
                if 'name' in config:
                    location.name = config['name']
                self.logger.info(f"Successfully geocoded zipcode to: {location.name}")
                return location
            else:
                self.logger.error(f"Failed to geocode zipcode: {zipcode}")
        
        # Check for location name
        elif 'location_name' in config:
            self.logger.info(f"Found location_name in config: {config['location_name']}")
            location = await self.geocode_location_name(config['location_name'])
            if location:
                # Override name if provided in config
                if 'name' in config:
                    location.name = config['name']
                return location
        
        # Check for lat/lon
        elif 'latitude' in config and 'longitude' in config:
            self.logger.info(f"Found lat/lon in config: {config['latitude']}, {config['longitude']}")
            try:
                return Location(
                    latitude=float(config['latitude']),
                    longitude=float(config['longitude']),
                    name=config.get('name', 'Custom Location'),
                    country=config.get('country', ''),
                    state=config.get('state', '')
                )
            except (ValueError, TypeError) as e:
                self.logger.error(f"Invalid latitude/longitude in config: {e}")
                return None
        
        self.logger.warning(f"No valid location information in config. Keys found: {list(config.keys())}")
        return None
