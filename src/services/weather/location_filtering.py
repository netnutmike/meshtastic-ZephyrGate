"""
Location-Based Filtering Services

Provides geographic radius calculations, location-specific filtering,
user location tracking, and alert subscription management by location.
"""

import asyncio
import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .models import Location, WeatherAlert, WeatherSubscription, AlertType, AlertSeverity


class LocationAccuracy(Enum):
    """Location accuracy levels"""
    UNKNOWN = "unknown"
    LOW = "low"          # > 10km accuracy
    MEDIUM = "medium"    # 1-10km accuracy  
    HIGH = "high"        # < 1km accuracy
    PRECISE = "precise"  # < 100m accuracy


@dataclass
class LocationUpdate:
    """Location update event"""
    user_id: str
    location: Location
    accuracy: LocationAccuracy = LocationAccuracy.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "manual"  # manual, gps, network, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeofenceZone:
    """Geofence zone definition"""
    zone_id: str
    name: str
    center: Location
    radius_km: float
    zone_type: str = "circular"  # circular, polygon (future)
    enabled: bool = True
    alert_on_enter: bool = True
    alert_on_exit: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def contains_location(self, location: Location) -> bool:
        """Check if location is within this geofence"""
        if self.zone_type == "circular":
            distance = self.center.distance_to(location)
            return distance <= self.radius_km
        
        # Future: implement polygon geofences
        return False


class LocationTracker:
    """
    User location tracking and management system
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Configuration
        self.enabled = config.get('enabled', True)
        self.max_location_age_hours = config.get('max_location_age_hours', 24)
        self.location_update_threshold_km = config.get('location_update_threshold_km', 1.0)
        self.auto_geocode = config.get('auto_geocode', False)
        
        # Location data
        self.user_locations: Dict[str, LocationUpdate] = {}
        self.location_history: Dict[str, List[LocationUpdate]] = {}
        self.max_history_entries = config.get('max_history_entries', 100)
        
        # Geofences
        self.geofences: Dict[str, GeofenceZone] = {}
        self.user_geofence_status: Dict[str, Dict[str, bool]] = {}  # user_id -> {zone_id: inside}
        
        # Callbacks
        self.location_update_callbacks: List[Callable[[LocationUpdate], None]] = []
        self.geofence_callbacks: List[Callable[[str, str, bool], None]] = []  # user_id, zone_id, entered
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Data persistence
        self.data_dir = Path(config.get('data_directory', 'data/weather'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start location tracking"""
        if not self.enabled or self.running:
            return
        
        self.running = True
        
        # Load persisted data
        await self._load_location_data()
        await self._load_geofences()
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Location tracker started")
    
    async def stop(self):
        """Stop location tracking"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save data
        await self._save_location_data()
        await self._save_geofences()
        
        self.logger.info("Location tracker stopped")
    
    def add_location_update_callback(self, callback: Callable[[LocationUpdate], None]):
        """Add callback for location updates"""
        self.location_update_callbacks.append(callback)
    
    def add_geofence_callback(self, callback: Callable[[str, str, bool], None]):
        """Add callback for geofence events"""
        self.geofence_callbacks.append(callback)
    
    def update_user_location(self, user_id: str, location: Location, 
                           accuracy: LocationAccuracy = LocationAccuracy.UNKNOWN,
                           source: str = "manual", metadata: Dict[str, Any] = None) -> bool:
        """
        Update user location
        
        Args:
            user_id: User identifier
            location: New location
            accuracy: Location accuracy
            source: Location source
            metadata: Additional metadata
            
        Returns:
            True if location was updated (significant change)
        """
        if not self.enabled:
            return False
        
        # Check if this is a significant location change
        current_location = self.user_locations.get(user_id)
        if current_location:
            distance = current_location.location.distance_to(location)
            if distance < self.location_update_threshold_km:
                # Update timestamp but don't trigger callbacks for minor changes
                current_location.timestamp = datetime.utcnow()
                return False
        
        # Create location update
        location_update = LocationUpdate(
            user_id=user_id,
            location=location,
            accuracy=accuracy,
            source=source,
            metadata=metadata or {}
        )
        
        # Update current location
        self.user_locations[user_id] = location_update
        
        # Add to history
        if user_id not in self.location_history:
            self.location_history[user_id] = []
        
        self.location_history[user_id].append(location_update)
        
        # Trim history
        if len(self.location_history[user_id]) > self.max_history_entries:
            self.location_history[user_id] = self.location_history[user_id][-self.max_history_entries:]
        
        # Check geofences
        self._check_geofences(user_id, location)
        
        # Trigger callbacks
        for callback in self.location_update_callbacks:
            try:
                callback(location_update)
            except Exception as e:
                self.logger.error(f"Error in location update callback: {e}")
        
        self.logger.debug(f"Updated location for {user_id}: {location.latitude:.4f}, {location.longitude:.4f}")
        return True
    
    def get_user_location(self, user_id: str) -> Optional[LocationUpdate]:
        """Get current user location"""
        location_update = self.user_locations.get(user_id)
        
        # Check if location is too old
        if location_update:
            age = datetime.utcnow() - location_update.timestamp
            if age.total_seconds() > self.max_location_age_hours * 3600:
                return None
        
        return location_update
    
    def get_user_location_history(self, user_id: str, hours_back: int = 24) -> List[LocationUpdate]:
        """Get user location history"""
        if user_id not in self.location_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        return [
            update for update in self.location_history[user_id]
            if update.timestamp > cutoff_time
        ]
    
    def get_users_in_area(self, center: Location, radius_km: float) -> List[Tuple[str, LocationUpdate]]:
        """Get users within a radius of a location"""
        users_in_area = []
        
        for user_id, location_update in self.user_locations.items():
            distance = center.distance_to(location_update.location)
            if distance <= radius_km:
                users_in_area.append((user_id, location_update))
        
        return users_in_area
    
    def add_geofence(self, zone: GeofenceZone):
        """Add a geofence zone"""
        self.geofences[zone.zone_id] = zone
        
        # Initialize user status for this geofence
        for user_id in self.user_locations.keys():
            if user_id not in self.user_geofence_status:
                self.user_geofence_status[user_id] = {}
            
            # Check if user is currently in the zone
            location_update = self.user_locations[user_id]
            inside = zone.contains_location(location_update.location)
            self.user_geofence_status[user_id][zone.zone_id] = inside
        
        self.logger.info(f"Added geofence: {zone.name} ({zone.zone_id})")
    
    def remove_geofence(self, zone_id: str):
        """Remove a geofence zone"""
        if zone_id in self.geofences:
            del self.geofences[zone_id]
            
            # Clean up user status
            for user_status in self.user_geofence_status.values():
                if zone_id in user_status:
                    del user_status[zone_id]
            
            self.logger.info(f"Removed geofence: {zone_id}")
    
    def _check_geofences(self, user_id: str, location: Location):
        """Check geofence status for user location"""
        if user_id not in self.user_geofence_status:
            self.user_geofence_status[user_id] = {}
        
        for zone_id, zone in self.geofences.items():
            if not zone.enabled:
                continue
            
            # Check if user is in zone
            inside = zone.contains_location(location)
            previous_status = self.user_geofence_status[user_id].get(zone_id, False)
            
            # Update status
            self.user_geofence_status[user_id][zone_id] = inside
            
            # Check for zone entry/exit
            if inside and not previous_status and zone.alert_on_enter:
                # User entered zone
                self._trigger_geofence_event(user_id, zone_id, True)
            elif not inside and previous_status and zone.alert_on_exit:
                # User exited zone
                self._trigger_geofence_event(user_id, zone_id, False)
    
    def _trigger_geofence_event(self, user_id: str, zone_id: str, entered: bool):
        """Trigger geofence event callbacks"""
        zone = self.geofences.get(zone_id)
        if not zone:
            return
        
        action = "entered" if entered else "exited"
        self.logger.info(f"User {user_id} {action} geofence {zone.name}")
        
        for callback in self.geofence_callbacks:
            try:
                callback(user_id, zone_id, entered)
            except Exception as e:
                self.logger.error(f"Error in geofence callback: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup task"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_locations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in location cleanup: {e}")
    
    async def _cleanup_old_locations(self):
        """Clean up old location data"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.max_location_age_hours)
        
        # Clean up current locations
        expired_users = []
        for user_id, location_update in self.user_locations.items():
            if location_update.timestamp < cutoff_time:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_locations[user_id]
            if user_id in self.user_geofence_status:
                del self.user_geofence_status[user_id]
        
        # Clean up history
        for user_id, history in self.location_history.items():
            self.location_history[user_id] = [
                update for update in history
                if update.timestamp > cutoff_time
            ]
        
        # Remove empty histories
        empty_histories = [
            user_id for user_id, history in self.location_history.items()
            if not history
        ]
        
        for user_id in empty_histories:
            del self.location_history[user_id]
        
        if expired_users or empty_histories:
            self.logger.debug(f"Cleaned up {len(expired_users)} expired locations and {len(empty_histories)} empty histories")
    
    async def _load_location_data(self):
        """Load location data from disk"""
        location_file = self.data_dir / "user_locations.json"
        if not location_file.exists():
            return
        
        try:
            with open(location_file, 'r') as f:
                data = json.load(f)
            
            # Load current locations
            for user_id, location_data in data.get('current_locations', {}).items():
                try:
                    location = Location(
                        latitude=location_data['latitude'],
                        longitude=location_data['longitude'],
                        name=location_data.get('name'),
                        country=location_data.get('country'),
                        state=location_data.get('state')
                    )
                    
                    location_update = LocationUpdate(
                        user_id=user_id,
                        location=location,
                        accuracy=LocationAccuracy(location_data.get('accuracy', 'unknown')),
                        timestamp=datetime.fromisoformat(location_data['timestamp']),
                        source=location_data.get('source', 'manual'),
                        metadata=location_data.get('metadata', {})
                    )
                    
                    self.user_locations[user_id] = location_update
                    
                except Exception as e:
                    self.logger.warning(f"Failed to load location for {user_id}: {e}")
            
            self.logger.debug(f"Loaded {len(self.user_locations)} user locations")
            
        except Exception as e:
            self.logger.error(f"Failed to load location data: {e}")
    
    async def _save_location_data(self):
        """Save location data to disk"""
        location_file = self.data_dir / "user_locations.json"
        
        try:
            data = {
                'current_locations': {},
                'saved_at': datetime.utcnow().isoformat()
            }
            
            # Save current locations
            for user_id, location_update in self.user_locations.items():
                data['current_locations'][user_id] = {
                    'latitude': location_update.location.latitude,
                    'longitude': location_update.location.longitude,
                    'name': location_update.location.name,
                    'country': location_update.location.country,
                    'state': location_update.location.state,
                    'accuracy': location_update.accuracy.value,
                    'timestamp': location_update.timestamp.isoformat(),
                    'source': location_update.source,
                    'metadata': location_update.metadata
                }
            
            with open(location_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Saved {len(self.user_locations)} user locations")
            
        except Exception as e:
            self.logger.error(f"Failed to save location data: {e}")
    
    async def _load_geofences(self):
        """Load geofences from disk"""
        geofence_file = self.data_dir / "geofences.json"
        if not geofence_file.exists():
            return
        
        try:
            with open(geofence_file, 'r') as f:
                data = json.load(f)
            
            for zone_id, zone_data in data.get('geofences', {}).items():
                try:
                    center = Location(
                        latitude=zone_data['center']['latitude'],
                        longitude=zone_data['center']['longitude'],
                        name=zone_data['center'].get('name')
                    )
                    
                    zone = GeofenceZone(
                        zone_id=zone_id,
                        name=zone_data['name'],
                        center=center,
                        radius_km=zone_data['radius_km'],
                        zone_type=zone_data.get('zone_type', 'circular'),
                        enabled=zone_data.get('enabled', True),
                        alert_on_enter=zone_data.get('alert_on_enter', True),
                        alert_on_exit=zone_data.get('alert_on_exit', True),
                        metadata=zone_data.get('metadata', {})
                    )
                    
                    self.geofences[zone_id] = zone
                    
                except Exception as e:
                    self.logger.warning(f"Failed to load geofence {zone_id}: {e}")
            
            self.logger.debug(f"Loaded {len(self.geofences)} geofences")
            
        except Exception as e:
            self.logger.error(f"Failed to load geofences: {e}")
    
    async def _save_geofences(self):
        """Save geofences to disk"""
        geofence_file = self.data_dir / "geofences.json"
        
        try:
            data = {
                'geofences': {},
                'saved_at': datetime.utcnow().isoformat()
            }
            
            for zone_id, zone in self.geofences.items():
                data['geofences'][zone_id] = {
                    'name': zone.name,
                    'center': {
                        'latitude': zone.center.latitude,
                        'longitude': zone.center.longitude,
                        'name': zone.center.name
                    },
                    'radius_km': zone.radius_km,
                    'zone_type': zone.zone_type,
                    'enabled': zone.enabled,
                    'alert_on_enter': zone.alert_on_enter,
                    'alert_on_exit': zone.alert_on_exit,
                    'metadata': zone.metadata
                }
            
            with open(geofence_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Saved {len(self.geofences)} geofences")
            
        except Exception as e:
            self.logger.error(f"Failed to save geofences: {e}")


class AlertFilter:
    """
    Location-based alert filtering system
    """
    
    def __init__(self, location_tracker: LocationTracker):
        self.location_tracker = location_tracker
        self.logger = logging.getLogger(__name__)
    
    def filter_alerts_for_user(self, user_id: str, alerts: List[WeatherAlert], 
                              subscription: WeatherSubscription) -> List[WeatherAlert]:
        """
        Filter alerts based on user location and subscription preferences
        
        Args:
            user_id: User identifier
            alerts: List of alerts to filter
            subscription: User's subscription preferences
            
        Returns:
            Filtered list of alerts relevant to the user
        """
        # Get user location
        location_update = self.location_tracker.get_user_location(user_id)
        if not location_update:
            # No location available, use subscription location if available
            if subscription.location:
                user_location = subscription.location
            else:
                # No location available, return all alerts
                return alerts
        else:
            user_location = location_update.location
        
        filtered_alerts = []
        
        for alert in alerts:
            if self._should_user_receive_alert(user_id, alert, subscription, user_location):
                filtered_alerts.append(alert)
        
        return filtered_alerts
    
    def _should_user_receive_alert(self, user_id: str, alert: WeatherAlert, 
                                 subscription: WeatherSubscription, user_location: Location) -> bool:
        """
        Determine if user should receive a specific alert
        
        Args:
            user_id: User identifier
            alert: Alert to check
            subscription: User subscription
            user_location: User's current location
            
        Returns:
            True if user should receive the alert
        """
        # Check if alert type is subscribed
        if alert.alert_type not in subscription.alert_types:
            return False
        
        # Check quiet hours for non-extreme alerts
        if alert.severity != AlertSeverity.EXTREME and subscription.is_quiet_time():
            return False
        
        # Check location-based filtering
        if not self._alert_affects_location(alert, user_location, subscription.alert_radius_km):
            return False
        
        return True
    
    def _alert_affects_location(self, alert: WeatherAlert, location: Location, radius_km: float) -> bool:
        """
        Check if alert affects a specific location
        
        Args:
            alert: Alert to check
            location: Location to check
            radius_km: Alert radius
            
        Returns:
            True if alert affects the location
        """
        # Check FIPS codes if available
        if location.fips_code and alert.fips_codes:
            if location.fips_code in alert.fips_codes:
                return True
        
        # Check SAME codes if available
        if location.same_code and alert.same_codes:
            if location.same_code in alert.same_codes:
                return True
        
        # Check geographic proximity
        if alert.location:
            distance = location.distance_to(alert.location)
            return distance <= radius_km
        
        # Check affected areas by name matching
        if alert.affected_areas and location.name:
            location_name_lower = location.name.lower()
            for area in alert.affected_areas:
                if location_name_lower in area.lower() or area.lower() in location_name_lower:
                    return True
        
        # Default to not affected if no criteria match
        return False
    
    def get_alerts_for_area(self, center: Location, radius_km: float, 
                          alerts: List[WeatherAlert]) -> List[WeatherAlert]:
        """
        Get alerts that affect a specific geographic area
        
        Args:
            center: Center location
            radius_km: Search radius
            alerts: List of alerts to filter
            
        Returns:
            Alerts affecting the area
        """
        area_alerts = []
        
        for alert in alerts:
            if self._alert_affects_location(alert, center, radius_km):
                area_alerts.append(alert)
        
        return area_alerts


class LocationBasedFilteringService:
    """
    Main location-based filtering service
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize components
        self.location_tracker = LocationTracker(config.get('location_tracking', {}))
        self.alert_filter = AlertFilter(self.location_tracker)
        
        # Service state
        self.running = False
        
        # Callbacks
        self.location_callbacks: List[Callable[[LocationUpdate], None]] = []
        self.geofence_callbacks: List[Callable[[str, str, bool], None]] = []
    
    async def start(self):
        """Start location-based filtering service"""
        if self.running:
            return
        
        self.running = True
        
        # Set up callbacks
        self.location_tracker.add_location_update_callback(self._handle_location_update)
        self.location_tracker.add_geofence_callback(self._handle_geofence_event)
        
        # Start location tracker
        await self.location_tracker.start()
        
        self.logger.info("Location-based filtering service started")
    
    async def stop(self):
        """Stop location-based filtering service"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop location tracker
        await self.location_tracker.stop()
        
        self.logger.info("Location-based filtering service stopped")
    
    def add_location_callback(self, callback: Callable[[LocationUpdate], None]):
        """Add location update callback"""
        self.location_callbacks.append(callback)
    
    def add_geofence_callback(self, callback: Callable[[str, str, bool], None]):
        """Add geofence event callback"""
        self.geofence_callbacks.append(callback)
    
    def update_user_location(self, user_id: str, location: Location, 
                           accuracy: LocationAccuracy = LocationAccuracy.UNKNOWN,
                           source: str = "manual", metadata: Dict[str, Any] = None) -> bool:
        """Update user location"""
        return self.location_tracker.update_user_location(user_id, location, accuracy, source, metadata)
    
    def get_user_location(self, user_id: str) -> Optional[LocationUpdate]:
        """Get user location"""
        return self.location_tracker.get_user_location(user_id)
    
    def filter_alerts_for_user(self, user_id: str, alerts: List[WeatherAlert], 
                              subscription: WeatherSubscription) -> List[WeatherAlert]:
        """Filter alerts for user based on location"""
        return self.alert_filter.filter_alerts_for_user(user_id, alerts, subscription)
    
    def get_users_in_area(self, center: Location, radius_km: float) -> List[Tuple[str, LocationUpdate]]:
        """Get users in area"""
        return self.location_tracker.get_users_in_area(center, radius_km)
    
    def add_geofence(self, zone: GeofenceZone):
        """Add geofence zone"""
        self.location_tracker.add_geofence(zone)
    
    def remove_geofence(self, zone_id: str):
        """Remove geofence zone"""
        self.location_tracker.remove_geofence(zone_id)
    
    def _handle_location_update(self, location_update: LocationUpdate):
        """Handle location update events"""
        self.logger.debug(f"Location update: {location_update.user_id}")
        
        for callback in self.location_callbacks:
            try:
                callback(location_update)
            except Exception as e:
                self.logger.error(f"Error in location callback: {e}")
    
    def _handle_geofence_event(self, user_id: str, zone_id: str, entered: bool):
        """Handle geofence events"""
        action = "entered" if entered else "exited"
        self.logger.info(f"Geofence event: {user_id} {action} {zone_id}")
        
        for callback in self.geofence_callbacks:
            try:
                callback(user_id, zone_id, entered)
            except Exception as e:
                self.logger.error(f"Error in geofence callback: {e}")