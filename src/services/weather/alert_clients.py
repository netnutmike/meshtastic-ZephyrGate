"""
Emergency Alert System Clients

Provides clients for fetching emergency alerts from multiple sources:
- FEMA iPAWS/EAS alerts with FIPS/SAME filtering
- NOAA weather alerts
- USGS earthquake alerts with radius filtering
- USGS volcano alerts
- International alert systems (NINA)
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from .models import (
    WeatherAlert, Location, AlertType, AlertSeverity,
    EarthquakeData
)


class AlertClientError(Exception):
    """Base exception for alert client errors"""
    pass


class FEMAAlertClient:
    """
    FEMA iPAWS/EAS Alert Client
    
    Fetches emergency alerts from FEMA's Integrated Public Alert & Warning System
    with FIPS and SAME code filtering.
    """
    
    def __init__(self, user_agent: str = "ZephyrGate/1.0"):
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # FEMA IPAWS endpoints
        self.base_url = "https://api.weather.gov/alerts"  # NWS provides IPAWS alerts
        self.cap_feed_url = "https://alerts.weather.gov/cap/us.php?x=1"
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 1.0
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {'User-Agent': self.user_agent}
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_alerts(self, fips_codes: List[str] = None, 
                        same_codes: List[str] = None) -> List[WeatherAlert]:
        """
        Get emergency alerts filtered by FIPS/SAME codes
        
        Args:
            fips_codes: List of FIPS codes to filter by
            same_codes: List of SAME codes to filter by
            
        Returns:
            List of active emergency alerts
        """
        if not self.session:
            await self.start()
        
        try:
            params = {
                'status': 'actual',
                'message_type': 'alert'
            }
            
            # Add FIPS code filtering if provided
            if fips_codes:
                params['area'] = ','.join(fips_codes)
            
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    raise AlertClientError(f"FEMA API returned {response.status}")
                
                data = await response.json()
                features = data.get('features', [])
                
                alerts = []
                for feature in features:
                    alert = self._parse_cap_alert(feature)
                    if alert and self._filter_alert(alert, fips_codes, same_codes):
                        alerts.append(alert)
                
                return alerts
                
        except Exception as e:
            self.logger.error(f"Failed to fetch FEMA alerts: {e}")
            return []
    
    def _parse_cap_alert(self, feature: Dict[str, Any]) -> Optional[WeatherAlert]:
        """Parse CAP (Common Alerting Protocol) alert"""
        try:
            properties = feature.get('properties', {})
            
            # Extract basic information
            alert_id = properties.get('id', '')
            event = properties.get('event', 'Emergency Alert')
            headline = properties.get('headline', '')
            description = properties.get('description', '')
            severity = properties.get('severity', 'Moderate').lower()
            urgency = properties.get('urgency', 'Unknown').lower()
            certainty = properties.get('certainty', 'Unknown').lower()
            
            # Parse times
            onset_str = properties.get('onset', '')
            expires_str = properties.get('expires', '')
            
            start_time = datetime.utcnow()
            end_time = None
            
            try:
                if onset_str:
                    start_time = datetime.fromisoformat(onset_str.replace('Z', '+00:00'))
            except:
                pass
            
            try:
                if expires_str:
                    end_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            except:
                pass
            
            # Map severity
            severity_map = {
                'minor': AlertSeverity.MINOR,
                'moderate': AlertSeverity.MODERATE,
                'severe': AlertSeverity.SEVERE,
                'extreme': AlertSeverity.EXTREME
            }
            alert_severity = severity_map.get(severity, AlertSeverity.MODERATE)
            
            # Determine alert type based on event
            alert_type = self._classify_alert_type(event)
            
            # Get affected areas and codes
            affected_areas = properties.get('areaDesc', '').split(';')
            affected_areas = [area.strip() for area in affected_areas if area.strip()]
            
            geocode = properties.get('geocode', {})
            fips_codes = geocode.get('FIPS6', [])
            same_codes = geocode.get('SAME', [])
            
            alert = WeatherAlert(
                id=alert_id,
                alert_type=alert_type,
                severity=alert_severity,
                title=event,
                description=headline or description,
                affected_areas=affected_areas,
                start_time=start_time,
                end_time=end_time,
                issued_time=datetime.utcnow(),
                source="FEMA/IPAWS",
                fips_codes=fips_codes,
                same_codes=same_codes,
                metadata={
                    'urgency': urgency,
                    'certainty': certainty,
                    'category': properties.get('category'),
                    'response': properties.get('response')
                }
            )
            
            return alert
            
        except Exception as e:
            self.logger.warning(f"Failed to parse CAP alert: {e}")
            return None
    
    def _classify_alert_type(self, event: str) -> AlertType:
        """Classify alert type based on event name"""
        event_lower = event.lower()
        
        if any(word in event_lower for word in ['tornado', 'thunderstorm', 'flood', 'hurricane', 'blizzard']):
            return AlertType.WEATHER
        elif any(word in event_lower for word in ['earthquake', 'seismic']):
            return AlertType.EARTHQUAKE
        elif any(word in event_lower for word in ['volcano', 'volcanic']):
            return AlertType.VOLCANO
        elif any(word in event_lower for word in ['fire', 'wildfire']):
            return AlertType.FIRE
        elif any(word in event_lower for word in ['flood', 'dam', 'levee']):
            return AlertType.FLOOD
        else:
            return AlertType.EMERGENCY
    
    def _filter_alert(self, alert: WeatherAlert, fips_codes: List[str] = None,
                     same_codes: List[str] = None) -> bool:
        """Filter alert by FIPS/SAME codes"""
        if not fips_codes and not same_codes:
            return True
        
        # Check FIPS codes
        if fips_codes:
            if any(code in alert.fips_codes for code in fips_codes):
                return True
        
        # Check SAME codes
        if same_codes:
            if any(code in alert.same_codes for code in same_codes):
                return True
        
        return False


class USGSEarthquakeClient:
    """
    USGS Earthquake Alert Client
    
    Fetches earthquake data from USGS with radius filtering.
    """
    
    def __init__(self, user_agent: str = "ZephyrGate/1.0"):
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # USGS earthquake API
        self.base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {'User-Agent': self.user_agent}
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_earthquakes(self, location: Location, radius_km: float = 500.0,
                            min_magnitude: float = 4.0, hours_back: int = 24) -> List[EarthquakeData]:
        """
        Get recent earthquakes near a location
        
        Args:
            location: Center location for search
            radius_km: Search radius in kilometers
            min_magnitude: Minimum magnitude to include
            hours_back: How many hours back to search
            
        Returns:
            List of earthquake data
        """
        if not self.session:
            await self.start()
        
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours_back)
            
            params = {
                'format': 'geojson',
                'latitude': location.latitude,
                'longitude': location.longitude,
                'maxradius': radius_km / 111.0,  # Convert km to degrees (approximate)
                'minmagnitude': min_magnitude,
                'starttime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'endtime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'orderby': 'time'
            }
            
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    raise AlertClientError(f"USGS API returned {response.status}")
                
                data = await response.json()
                features = data.get('features', [])
                
                earthquakes = []
                for feature in features:
                    earthquake = self._parse_earthquake(feature)
                    if earthquake:
                        earthquakes.append(earthquake)
                
                return earthquakes
                
        except Exception as e:
            self.logger.error(f"Failed to fetch earthquake data: {e}")
            return []
    
    def _parse_earthquake(self, feature: Dict[str, Any]) -> Optional[EarthquakeData]:
        """Parse earthquake feature from USGS GeoJSON"""
        try:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            coordinates = geometry.get('coordinates', [])
            
            if len(coordinates) < 3:
                return None
            
            longitude, latitude, depth = coordinates[:3]
            
            # Convert depth from km to positive value
            depth = abs(depth) if depth else 0.0
            
            # Parse timestamp
            timestamp_ms = properties.get('time', 0)
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0) if timestamp_ms else datetime.utcnow()
            
            earthquake = EarthquakeData(
                id=properties.get('ids', '').split(',')[0] or str(timestamp_ms),
                magnitude=properties.get('mag', 0.0),
                location=Location(
                    latitude=latitude,
                    longitude=longitude,
                    name=properties.get('place', '')
                ),
                depth=depth,
                timestamp=timestamp,
                title=properties.get('title', ''),
                url=properties.get('url'),
                significance=properties.get('sig')
            )
            
            return earthquake
            
        except Exception as e:
            self.logger.warning(f"Failed to parse earthquake: {e}")
            return None
    
    async def get_earthquake_alerts(self, location: Location, radius_km: float = 500.0,
                                  min_magnitude: float = 5.0) -> List[WeatherAlert]:
        """
        Get earthquake alerts for significant earthquakes
        
        Args:
            location: Location to check around
            radius_km: Search radius
            min_magnitude: Minimum magnitude for alerts
            
        Returns:
            List of earthquake alerts
        """
        earthquakes = await self.get_earthquakes(
            location, radius_km, min_magnitude, hours_back=6
        )
        
        alerts = []
        for earthquake in earthquakes:
            # Only create alerts for significant earthquakes
            if earthquake.magnitude >= min_magnitude:
                severity = AlertSeverity.MODERATE
                if earthquake.magnitude >= 7.0:
                    severity = AlertSeverity.EXTREME
                elif earthquake.magnitude >= 6.0:
                    severity = AlertSeverity.SEVERE
                
                alert = WeatherAlert(
                    id=f"earthquake_{earthquake.id}",
                    alert_type=AlertType.EARTHQUAKE,
                    severity=severity,
                    title=f"Magnitude {earthquake.magnitude:.1f} Earthquake",
                    description=f"{earthquake.title} - Depth: {earthquake.depth:.1f}km",
                    location=earthquake.location,
                    start_time=earthquake.timestamp,
                    issued_time=datetime.utcnow(),
                    source="USGS",
                    source_url=earthquake.url,
                    metadata={
                        'magnitude': earthquake.magnitude,
                        'depth': earthquake.depth,
                        'significance': earthquake.significance
                    }
                )
                
                alerts.append(alert)
        
        return alerts


class USGSVolcanoClient:
    """
    USGS Volcano Alert Client
    
    Fetches volcano alerts and activity data from USGS.
    """
    
    def __init__(self, user_agent: str = "ZephyrGate/1.0"):
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # USGS volcano data (using RSS feeds as API is limited)
        self.volcano_rss_url = "https://volcanoes.usgs.gov/vsc/api/volcanoes"
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {'User-Agent': self.user_agent}
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_volcano_alerts(self, location: Location, radius_km: float = 200.0) -> List[WeatherAlert]:
        """
        Get volcano alerts near a location
        
        Args:
            location: Location to check around
            radius_km: Search radius
            
        Returns:
            List of volcano alerts
        """
        # This is a placeholder implementation
        # In a real implementation, you would fetch from USGS volcano APIs
        # or RSS feeds and parse volcano activity data
        
        self.logger.debug(f"Volcano alert check for {location} (radius: {radius_km}km) - placeholder")
        return []


class NINAAlertClient:
    """
    NINA (German Emergency Alert System) Client
    
    Fetches emergency alerts from Germany's NINA system.
    """
    
    def __init__(self, user_agent: str = "ZephyrGate/1.0"):
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # NINA API endpoints
        self.base_url = "https://warnung.bund.de/api31"
        self.warnings_url = f"{self.base_url}/warnings"
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {'User-Agent': self.user_agent}
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_alerts(self, location: Location, radius_km: float = 50.0) -> List[WeatherAlert]:
        """
        Get NINA alerts for a location in Germany
        
        Args:
            location: Location to check (should be in Germany)
            radius_km: Search radius
            
        Returns:
            List of emergency alerts
        """
        if not self.session:
            await self.start()
        
        try:
            # Get all current warnings
            async with self.session.get(self.warnings_url) as response:
                if response.status != 200:
                    raise AlertClientError(f"NINA API returned {response.status}")
                
                data = await response.json()
                
                alerts = []
                for warning_id, warning_data in data.items():
                    alert = self._parse_nina_warning(warning_id, warning_data, location, radius_km)
                    if alert:
                        alerts.append(alert)
                
                return alerts
                
        except Exception as e:
            self.logger.error(f"Failed to fetch NINA alerts: {e}")
            return []
    
    def _parse_nina_warning(self, warning_id: str, warning_data: Dict[str, Any],
                           location: Location, radius_km: float) -> Optional[WeatherAlert]:
        """Parse NINA warning data"""
        try:
            # Extract warning information
            title = warning_data.get('headline', 'Emergency Alert')
            description = warning_data.get('description', '')
            severity = warning_data.get('severity', 'Moderate').lower()
            
            # Parse times
            start_time = datetime.utcnow()
            end_time = None
            
            onset = warning_data.get('onset')
            expires = warning_data.get('expires')
            
            if onset:
                try:
                    start_time = datetime.fromisoformat(onset.replace('Z', '+00:00'))
                except:
                    pass
            
            if expires:
                try:
                    end_time = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                except:
                    pass
            
            # Map severity
            severity_map = {
                'minor': AlertSeverity.MINOR,
                'moderate': AlertSeverity.MODERATE,
                'severe': AlertSeverity.SEVERE,
                'extreme': AlertSeverity.EXTREME
            }
            alert_severity = severity_map.get(severity, AlertSeverity.MODERATE)
            
            # Check if warning affects the location
            # This is simplified - in reality you'd check the warning's geographic areas
            affected_areas = warning_data.get('areaDesc', '').split(';')
            affected_areas = [area.strip() for area in affected_areas if area.strip()]
            
            alert = WeatherAlert(
                id=f"nina_{warning_id}",
                alert_type=AlertType.EMERGENCY,
                severity=alert_severity,
                title=title,
                description=description,
                location=location,
                affected_areas=affected_areas,
                start_time=start_time,
                end_time=end_time,
                issued_time=datetime.utcnow(),
                source="NINA (Germany)",
                metadata={
                    'warning_id': warning_id,
                    'country': 'DE'
                }
            )
            
            return alert
            
        except Exception as e:
            self.logger.warning(f"Failed to parse NINA warning: {e}")
            return None


class AlertAggregator:
    """
    Aggregates alerts from multiple sources and provides unified access
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize clients
        self.fema_client = FEMAAlertClient()
        self.earthquake_client = USGSEarthquakeClient()
        self.volcano_client = USGSVolcanoClient()
        self.nina_client = NINAAlertClient()
        
        # Client status
        self.clients_started = False
    
    async def start(self):
        """Start all alert clients"""
        if self.clients_started:
            return
        
        try:
            await asyncio.gather(
                self.fema_client.start(),
                self.earthquake_client.start(),
                self.volcano_client.start(),
                self.nina_client.start(),
                return_exceptions=True
            )
            self.clients_started = True
            self.logger.info("Alert aggregator started")
        except Exception as e:
            self.logger.error(f"Failed to start alert clients: {e}")
    
    async def close(self):
        """Close all alert clients"""
        if not self.clients_started:
            return
        
        try:
            await asyncio.gather(
                self.fema_client.close(),
                self.earthquake_client.close(),
                self.volcano_client.close(),
                self.nina_client.close(),
                return_exceptions=True
            )
            self.clients_started = False
            self.logger.info("Alert aggregator closed")
        except Exception as e:
            self.logger.error(f"Failed to close alert clients: {e}")
    
    async def get_all_alerts(self, location: Location, radius_km: float = 50.0,
                           fips_codes: List[str] = None, same_codes: List[str] = None) -> List[WeatherAlert]:
        """
        Get alerts from all sources
        
        Args:
            location: Location to get alerts for
            radius_km: Search radius
            fips_codes: FIPS codes for US alerts
            same_codes: SAME codes for US alerts
            
        Returns:
            Combined list of alerts from all sources
        """
        if not self.clients_started:
            await self.start()
        
        # Fetch from all sources concurrently
        tasks = [
            self.fema_client.get_alerts(fips_codes, same_codes),
            self.earthquake_client.get_earthquake_alerts(location, radius_km),
            self.volcano_client.get_volcano_alerts(location, radius_km)
        ]
        
        # Add NINA for European locations
        if location.country in ['DE', 'Germany']:
            tasks.append(self.nina_client.get_alerts(location, radius_km))
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine all alerts
            all_alerts = []
            for result in results:
                if isinstance(result, list):
                    all_alerts.extend(result)
                elif isinstance(result, Exception):
                    self.logger.warning(f"Alert source failed: {result}")
            
            # Remove duplicates based on ID
            seen_ids = set()
            unique_alerts = []
            for alert in all_alerts:
                if alert.id not in seen_ids:
                    seen_ids.add(alert.id)
                    unique_alerts.append(alert)
            
            return unique_alerts
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate alerts: {e}")
            return []