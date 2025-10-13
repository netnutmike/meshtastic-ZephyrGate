"""
Environmental Monitoring Services

Provides proximity detection, aircraft tracking, RF monitoring,
and other environmental monitoring capabilities.
"""

import asyncio
import aiohttp
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass

from .models import (
    Location, ProximityAlert, EnvironmentalReading
)


@dataclass
class AircraftData:
    """Aircraft information from OpenSky Network"""
    icao24: str
    callsign: Optional[str]
    origin_country: str
    time_position: Optional[datetime]
    last_contact: datetime
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]  # meters
    on_ground: bool
    velocity: Optional[float]  # m/s
    true_track: Optional[float]  # degrees
    vertical_rate: Optional[float]  # m/s
    geo_altitude: Optional[float]  # meters
    squawk: Optional[str]
    spi: bool
    position_source: int
    
    def get_location(self) -> Optional[Location]:
        """Get location if coordinates are available"""
        if self.latitude is not None and self.longitude is not None:
            return Location(
                latitude=self.latitude,
                longitude=self.longitude,
                name=self.callsign or self.icao24
            )
        return None
    
    def is_high_altitude(self, threshold_meters: float = 1000.0) -> bool:
        """Check if aircraft is at high altitude"""
        altitude = self.geo_altitude or self.baro_altitude
        return altitude is not None and altitude > threshold_meters


class ProximityMonitor:
    """
    Proximity detection and sentry system for monitoring nearby nodes
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Monitoring configuration
        self.enabled = config.get('enabled', False)
        self.detection_radius_km = config.get('detection_radius_km', 10.0)
        self.high_altitude_threshold_m = config.get('high_altitude_threshold_m', 1000.0)
        self.update_interval = config.get('update_interval_seconds', 60)
        
        # Tracked nodes
        self.tracked_nodes: Dict[str, Dict[str, Any]] = {}
        self.proximity_alerts: Dict[str, ProximityAlert] = {}
        
        # Callbacks
        self.alert_callback: Optional[Callable[[ProximityAlert], None]] = None
        
        # Background task
        self.monitor_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start proximity monitoring"""
        if not self.enabled or self.running:
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Proximity monitor started")
    
    async def stop(self):
        """Stop proximity monitoring"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Proximity monitor stopped")
    
    def set_alert_callback(self, callback: Callable[[ProximityAlert], None]):
        """Set callback for proximity alerts"""
        self.alert_callback = callback
    
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
        if not self.enabled:
            return
        
        now = datetime.utcnow()
        
        # Update tracked node
        self.tracked_nodes[node_id] = {
            'location': location,
            'altitude': altitude,
            'last_seen': now,
            'metadata': metadata or {}
        }
        
        # Check for proximity alerts
        self._check_proximity_alerts(node_id)
    
    def _check_proximity_alerts(self, node_id: str):
        """Check if node triggers proximity alerts"""
        node_data = self.tracked_nodes.get(node_id)
        if not node_data:
            return
        
        node_location = node_data['location']
        node_altitude = node_data.get('altitude')
        
        # Check against all other nodes
        for other_id, other_data in self.tracked_nodes.items():
            if other_id == node_id:
                continue
            
            other_location = other_data['location']
            distance = node_location.distance_to(other_location)
            
            # Check if within detection radius
            if distance <= self.detection_radius_km:
                alert_id = f"proximity_{min(node_id, other_id)}_{max(node_id, other_id)}"
                
                # Create or update proximity alert
                if alert_id not in self.proximity_alerts:
                    # Determine if this might be an aircraft
                    is_aircraft = (
                        node_altitude is not None and 
                        node_altitude > self.high_altitude_threshold_m
                    )
                    
                    alert = ProximityAlert(
                        id=alert_id,
                        node_id=node_id,
                        node_name=node_data.get('metadata', {}).get('name', node_id),
                        location=node_location,
                        distance=distance,
                        altitude=node_altitude,
                        is_aircraft=is_aircraft,
                        aircraft_data=node_data.get('metadata') if is_aircraft else None
                    )
                    
                    self.proximity_alerts[alert_id] = alert
                    
                    # Trigger callback
                    if self.alert_callback:
                        try:
                            self.alert_callback(alert)
                        except Exception as e:
                            self.logger.error(f"Error in proximity alert callback: {e}")
    
    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                await self._cleanup_old_nodes()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in proximity monitor loop: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_old_nodes(self):
        """Remove old node data"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        expired_nodes = []
        
        for node_id, node_data in self.tracked_nodes.items():
            if node_data['last_seen'] < cutoff_time:
                expired_nodes.append(node_id)
        
        for node_id in expired_nodes:
            del self.tracked_nodes[node_id]
        
        # Clean up related alerts
        expired_alerts = []
        for alert_id, alert in self.proximity_alerts.items():
            if alert.node_id in expired_nodes:
                expired_alerts.append(alert_id)
        
        for alert_id in expired_alerts:
            del self.proximity_alerts[alert_id]
    
    def get_proximity_alerts(self) -> List[ProximityAlert]:
        """Get current proximity alerts"""
        return list(self.proximity_alerts.values())
    
    def get_tracked_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get currently tracked nodes"""
        return self.tracked_nodes.copy()


class OpenSkyNetworkClient:
    """
    OpenSky Network client for aircraft tracking and correlation
    """
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        
        # OpenSky Network API
        self.base_url = "https://opensky-network.org/api"
        self.states_url = f"{self.base_url}/states/all"
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting (OpenSky has strict limits for anonymous users)
        self.last_request_time = 0.0
        self.min_request_interval = 10.0  # 10 seconds for anonymous users
    
    async def start(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {'User-Agent': 'ZephyrGate/1.0'}
            
            # Add authentication if provided
            auth = None
            if self.username and self.password:
                auth = aiohttp.BasicAuth(self.username, self.password)
                self.min_request_interval = 5.0  # Authenticated users get better rate limits
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
                auth=auth
            )
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_aircraft_in_area(self, location: Location, radius_km: float = 50.0) -> List[AircraftData]:
        """
        Get aircraft within a radius of a location
        
        Args:
            location: Center location
            radius_km: Search radius in kilometers
            
        Returns:
            List of aircraft data
        """
        if not self.session:
            await self.start()
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        try:
            # Calculate bounding box
            lat_delta = radius_km / 111.0  # Rough conversion
            lon_delta = radius_km / (111.0 * math.cos(math.radians(location.latitude)))
            
            params = {
                'lamin': location.latitude - lat_delta,
                'lamax': location.latitude + lat_delta,
                'lomin': location.longitude - lon_delta,
                'lomax': location.longitude + lon_delta
            }
            
            async with self.session.get(self.states_url, params=params) as response:
                self.last_request_time = asyncio.get_event_loop().time()
                
                if response.status != 200:
                    raise Exception(f"OpenSky API returned {response.status}")
                
                data = await response.json()
                states = data.get('states', [])
                
                aircraft_list = []
                for state in states:
                    aircraft = self._parse_aircraft_state(state)
                    if aircraft:
                        # Filter by actual distance
                        aircraft_location = aircraft.get_location()
                        if aircraft_location:
                            distance = location.distance_to(aircraft_location)
                            if distance <= radius_km:
                                aircraft_list.append(aircraft)
                
                return aircraft_list
                
        except Exception as e:
            self.logger.error(f"Failed to get aircraft data: {e}")
            return []
    
    def _parse_aircraft_state(self, state: List[Any]) -> Optional[AircraftData]:
        """Parse aircraft state vector from OpenSky API"""
        try:
            if len(state) < 17:
                return None
            
            # Parse timestamp
            last_contact = datetime.fromtimestamp(state[4]) if state[4] else datetime.utcnow()
            time_position = datetime.fromtimestamp(state[3]) if state[3] else None
            
            aircraft = AircraftData(
                icao24=state[0] or '',
                callsign=state[1].strip() if state[1] else None,
                origin_country=state[2] or '',
                time_position=time_position,
                last_contact=last_contact,
                longitude=state[5],
                latitude=state[6],
                baro_altitude=state[7],
                on_ground=state[8] or False,
                velocity=state[9],
                true_track=state[10],
                vertical_rate=state[11],
                geo_altitude=state[13],
                squawk=state[14],
                spi=state[15] or False,
                position_source=state[16] or 0
            )
            
            return aircraft
            
        except Exception as e:
            self.logger.warning(f"Failed to parse aircraft state: {e}")
            return None
    
    async def correlate_high_altitude_nodes(self, nodes: List[Dict[str, Any]], 
                                          altitude_threshold: float = 1000.0) -> Dict[str, AircraftData]:
        """
        Correlate high-altitude nodes with aircraft data
        
        Args:
            nodes: List of node data with location and altitude
            altitude_threshold: Minimum altitude to consider for correlation
            
        Returns:
            Dictionary mapping node IDs to aircraft data
        """
        correlations = {}
        
        # Filter high-altitude nodes
        high_altitude_nodes = [
            node for node in nodes 
            if node.get('altitude', 0) > altitude_threshold
        ]
        
        if not high_altitude_nodes:
            return correlations
        
        # Get aircraft data for each high-altitude node
        for node in high_altitude_nodes:
            node_location = node.get('location')
            if not node_location:
                continue
            
            try:
                aircraft_list = await self.get_aircraft_in_area(node_location, radius_km=5.0)
                
                # Find closest aircraft
                closest_aircraft = None
                min_distance = float('inf')
                
                for aircraft in aircraft_list:
                    aircraft_location = aircraft.get_location()
                    if aircraft_location:
                        distance = node_location.distance_to(aircraft_location)
                        if distance < min_distance:
                            min_distance = distance
                            closest_aircraft = aircraft
                
                # Correlate if aircraft is close enough (within 2km)
                if closest_aircraft and min_distance <= 2.0:
                    correlations[node['id']] = closest_aircraft
                    
            except Exception as e:
                self.logger.error(f"Failed to correlate node {node.get('id')}: {e}")
        
        return correlations


class RFMonitor:
    """
    Radio Frequency monitoring using Hamlib integration
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # RF monitoring configuration
        self.enabled = config.get('enabled', False)
        self.hamlib_host = config.get('hamlib_host', 'localhost')
        self.hamlib_port = config.get('hamlib_port', 4532)
        self.snr_threshold = config.get('snr_threshold_db', 10.0)
        self.monitor_frequencies = config.get('monitor_frequencies', [])
        
        # Monitoring state
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.rf_readings: Dict[str, EnvironmentalReading] = {}
        
        # Callbacks
        self.alert_callback: Optional[Callable[[EnvironmentalReading], None]] = None
    
    async def start(self):
        """Start RF monitoring"""
        if not self.enabled or self.running:
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("RF monitor started")
    
    async def stop(self):
        """Stop RF monitoring"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("RF monitor stopped")
    
    def set_alert_callback(self, callback: Callable[[EnvironmentalReading], None]):
        """Set callback for RF alerts"""
        self.alert_callback = callback
    
    async def _monitor_loop(self):
        """Background RF monitoring loop"""
        while self.running:
            try:
                await self._check_rf_activity()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in RF monitor loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_rf_activity(self):
        """Check RF activity on monitored frequencies"""
        if not self.monitor_frequencies:
            return
        
        for frequency in self.monitor_frequencies:
            try:
                # This is a placeholder for Hamlib integration
                # In a real implementation, you would:
                # 1. Connect to rigctld (Hamlib daemon)
                # 2. Set frequency
                # 3. Read signal strength/SNR
                # 4. Compare against thresholds
                
                # Simulated reading for now
                reading = EnvironmentalReading(
                    sensor_id=f"rf_monitor_{frequency}",
                    sensor_type="rf_monitor",
                    readings={
                        'frequency_hz': frequency,
                        'signal_strength_db': -80.0,  # Placeholder
                        'snr_db': 5.0,  # Placeholder
                        'noise_floor_db': -85.0  # Placeholder
                    },
                    metadata={
                        'hamlib_host': self.hamlib_host,
                        'hamlib_port': self.hamlib_port
                    }
                )
                
                # Check if SNR exceeds threshold
                if reading.is_threshold_exceeded('snr_db', self.snr_threshold, 'greater'):
                    self.rf_readings[f"rf_{frequency}"] = reading
                    
                    if self.alert_callback:
                        try:
                            self.alert_callback(reading)
                        except Exception as e:
                            self.logger.error(f"Error in RF alert callback: {e}")
                            
            except Exception as e:
                self.logger.error(f"Failed to check RF activity on {frequency}: {e}")
    
    def get_rf_readings(self) -> List[EnvironmentalReading]:
        """Get current RF readings"""
        return list(self.rf_readings.values())


class EnvironmentalMonitoringService:
    """
    Main environmental monitoring service that coordinates all monitoring components
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize monitoring components
        self.proximity_monitor = ProximityMonitor(config.get('proximity', {}))
        self.opensky_client = OpenSkyNetworkClient(
            username=config.get('opensky_username'),
            password=config.get('opensky_password')
        )
        self.rf_monitor = RFMonitor(config.get('rf_monitoring', {}))
        
        # Service state
        self.running = False
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[Any], None]] = []
    
    async def start(self):
        """Start all monitoring services"""
        if self.running:
            return
        
        self.running = True
        
        # Set up callbacks
        self.proximity_monitor.set_alert_callback(self._handle_proximity_alert)
        self.rf_monitor.set_alert_callback(self._handle_rf_alert)
        
        # Start components
        await asyncio.gather(
            self.proximity_monitor.start(),
            self.opensky_client.start(),
            self.rf_monitor.start(),
            return_exceptions=True
        )
        
        self.logger.info("Environmental monitoring service started")
    
    async def stop(self):
        """Stop all monitoring services"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop components
        await asyncio.gather(
            self.proximity_monitor.stop(),
            self.opensky_client.close(),
            self.rf_monitor.stop(),
            return_exceptions=True
        )
        
        self.logger.info("Environmental monitoring service stopped")
    
    def add_alert_callback(self, callback: Callable[[Any], None]):
        """Add alert callback"""
        self.alert_callbacks.append(callback)
    
    def update_node_position(self, node_id: str, location: Location, 
                           altitude: Optional[float] = None, metadata: Dict[str, Any] = None):
        """Update node position for proximity monitoring"""
        self.proximity_monitor.update_node_position(node_id, location, altitude, metadata)
    
    async def correlate_aircraft(self, nodes: List[Dict[str, Any]]) -> Dict[str, AircraftData]:
        """Correlate high-altitude nodes with aircraft data"""
        return await self.opensky_client.correlate_high_altitude_nodes(nodes)
    
    def get_proximity_alerts(self) -> List[ProximityAlert]:
        """Get current proximity alerts"""
        return self.proximity_monitor.get_proximity_alerts()
    
    def get_rf_readings(self) -> List[EnvironmentalReading]:
        """Get current RF readings"""
        return self.rf_monitor.get_rf_readings()
    
    def get_tracked_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get currently tracked nodes"""
        return self.proximity_monitor.get_tracked_nodes()
    
    def _handle_proximity_alert(self, alert: ProximityAlert):
        """Handle proximity alerts"""
        self.logger.info(f"Proximity alert: {alert.node_name} at {alert.distance:.1f}km")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def _handle_rf_alert(self, reading: EnvironmentalReading):
        """Handle RF alerts"""
        frequency = reading.get_reading('frequency_hz')
        snr = reading.get_reading('snr_db')
        self.logger.info(f"RF alert: High SNR ({snr:.1f}dB) on {frequency/1e6:.3f} MHz")
        
        for callback in self.alert_callbacks:
            try:
                callback(reading)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")