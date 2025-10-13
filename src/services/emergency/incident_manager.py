"""
SOS Incident Management

Handles creation, tracking, and management of SOS incidents including:
- SOS command parsing for different alert types (SOS, SOSP, SOSF, SOSM)
- Incident creation and logging with location tracking
- Database operations for incident persistence
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

from src.models.message import SOSIncident, SOSType, IncidentStatus, UserProfile
from src.core.database import get_database, DatabaseError


class IncidentManager:
    """Manages SOS incidents and database operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        
        # SOS command patterns - order matters, longer matches first
        self.sos_commands = {
            'SOSP': SOSType.SOSP,
            'SOSF': SOSType.SOSF,
            'SOSM': SOSType.SOSM,
            'SOS': SOSType.SOS
        }
    
    def parse_sos_command(self, message_content: str) -> Optional[Tuple[SOSType, str]]:
        """
        Parse SOS command from message content
        
        Args:
            message_content: The message content to parse
            
        Returns:
            Tuple of (SOSType, additional_message) or None if not an SOS command
        """
        content = message_content.strip().upper()
        
        for command, sos_type in self.sos_commands.items():
            if content.startswith(command):
                # Extract additional message after the command
                additional_message = message_content[len(command):].strip()
                return sos_type, additional_message
        
        return None
    
    def create_incident(
        self,
        incident_type: SOSType,
        sender_id: str,
        message: str = "",
        location: Optional[Tuple[float, float]] = None
    ) -> SOSIncident:
        """
        Create a new SOS incident
        
        Args:
            incident_type: Type of SOS alert
            sender_id: Node ID of the person sending the alert
            message: Additional message content
            location: Optional location coordinates (lat, lon)
            
        Returns:
            Created SOSIncident object
        """
        incident = SOSIncident(
            incident_type=incident_type,
            sender_id=sender_id,
            message=message,
            location=location,
            timestamp=datetime.utcnow(),
            status=IncidentStatus.ACTIVE
        )
        
        try:
            # Store incident in database
            self._save_incident_to_db(incident)
            self.logger.info(f"Created SOS incident {incident.id} for user {sender_id}")
            return incident
            
        except DatabaseError as e:
            self.logger.error(f"Failed to create SOS incident: {e}")
            raise
    
    def get_incident(self, incident_id: str) -> Optional[SOSIncident]:
        """
        Get incident by ID
        
        Args:
            incident_id: The incident ID to retrieve
            
        Returns:
            SOSIncident object or None if not found
        """
        try:
            rows = self.db.execute_query(
                "SELECT * FROM sos_incidents WHERE id = ?",
                (incident_id,)
            )
            
            if rows:
                return self._row_to_incident(rows[0])
            return None
            
        except DatabaseError as e:
            self.logger.error(f"Failed to get incident {incident_id}: {e}")
            return None
    
    def get_active_incidents(self) -> List[SOSIncident]:
        """
        Get all active incidents
        
        Returns:
            List of active SOSIncident objects
        """
        try:
            rows = self.db.execute_query(
                "SELECT * FROM sos_incidents WHERE status IN (?, ?, ?) ORDER BY timestamp DESC",
                (IncidentStatus.ACTIVE.value, IncidentStatus.ACKNOWLEDGED.value, IncidentStatus.RESPONDING.value)
            )
            
            return [self._row_to_incident(row) for row in rows]
            
        except DatabaseError as e:
            self.logger.error(f"Failed to get active incidents: {e}")
            return []
    
    def get_incidents_by_sender(self, sender_id: str) -> List[SOSIncident]:
        """
        Get all incidents for a specific sender
        
        Args:
            sender_id: Node ID of the sender
            
        Returns:
            List of SOSIncident objects for the sender
        """
        try:
            rows = self.db.execute_query(
                "SELECT * FROM sos_incidents WHERE sender_id = ? ORDER BY timestamp DESC",
                (sender_id,)
            )
            
            return [self._row_to_incident(row) for row in rows]
            
        except DatabaseError as e:
            self.logger.error(f"Failed to get incidents for sender {sender_id}: {e}")
            return []
    
    def update_incident_status(self, incident_id: str, status: IncidentStatus) -> bool:
        """
        Update incident status
        
        Args:
            incident_id: The incident ID to update
            status: New status for the incident
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            rows_affected = self.db.execute_update(
                "UPDATE sos_incidents SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, datetime.utcnow().isoformat(), incident_id)
            )
            
            if rows_affected > 0:
                self.logger.info(f"Updated incident {incident_id} status to {status.value}")
                return True
            else:
                self.logger.warning(f"No incident found with ID {incident_id}")
                return False
                
        except DatabaseError as e:
            self.logger.error(f"Failed to update incident {incident_id} status: {e}")
            return False
    
    def add_responder(self, incident_id: str, responder_id: str) -> bool:
        """
        Add a responder to an incident
        
        Args:
            incident_id: The incident ID
            responder_id: Node ID of the responder
            
        Returns:
            True if responder was added successfully, False otherwise
        """
        incident = self.get_incident(incident_id)
        if not incident:
            return False
        
        incident.add_responder(responder_id)
        return self._update_incident_in_db(incident)
    
    def add_acknowledger(self, incident_id: str, acknowledger_id: str) -> bool:
        """
        Add an acknowledger to an incident
        
        Args:
            incident_id: The incident ID
            acknowledger_id: Node ID of the acknowledger
            
        Returns:
            True if acknowledger was added successfully, False otherwise
        """
        incident = self.get_incident(incident_id)
        if not incident:
            return False
        
        incident.add_acknowledger(acknowledger_id)
        
        # Update status to acknowledged if it was active
        if incident.status == IncidentStatus.ACTIVE:
            incident.status = IncidentStatus.ACKNOWLEDGED
        
        return self._update_incident_in_db(incident)
    
    def escalate_incident(self, incident_id: str) -> bool:
        """
        Mark an incident as escalated
        
        Args:
            incident_id: The incident ID to escalate
            
        Returns:
            True if escalation was successful, False otherwise
        """
        try:
            rows_affected = self.db.execute_update(
                "UPDATE sos_incidents SET escalated = TRUE, updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), incident_id)
            )
            
            if rows_affected > 0:
                self.logger.info(f"Escalated incident {incident_id}")
                return True
            else:
                self.logger.warning(f"No incident found with ID {incident_id}")
                return False
                
        except DatabaseError as e:
            self.logger.error(f"Failed to escalate incident {incident_id}: {e}")
            return False
    
    def clear_incident(self, incident_id: str, cleared_by: str, status: IncidentStatus = IncidentStatus.CLEARED) -> bool:
        """
        Clear an incident
        
        Args:
            incident_id: The incident ID to clear
            cleared_by: Node ID of who cleared the incident
            status: Status to set (CLEARED or CANCELLED)
            
        Returns:
            True if incident was cleared successfully, False otherwise
        """
        try:
            rows_affected = self.db.execute_update(
                """UPDATE sos_incidents 
                   SET status = ?, cleared_by = ?, cleared_at = ?, updated_at = ? 
                   WHERE id = ?""",
                (status.value, cleared_by, datetime.utcnow().isoformat(), 
                 datetime.utcnow().isoformat(), incident_id)
            )
            
            if rows_affected > 0:
                self.logger.info(f"Cleared incident {incident_id} by {cleared_by}")
                return True
            else:
                self.logger.warning(f"No incident found with ID {incident_id}")
                return False
                
        except DatabaseError as e:
            self.logger.error(f"Failed to clear incident {incident_id}: {e}")
            return False
    
    def get_incident_summary(self) -> Dict[str, int]:
        """
        Get summary statistics of incidents
        
        Returns:
            Dictionary with incident counts by status
        """
        try:
            rows = self.db.execute_query(
                "SELECT status, COUNT(*) as count FROM sos_incidents GROUP BY status"
            )
            
            summary = {status.value: 0 for status in IncidentStatus}
            for row in rows:
                summary[row['status']] = row['count']
            
            return summary
            
        except DatabaseError as e:
            self.logger.error(f"Failed to get incident summary: {e}")
            return {}
    
    def _save_incident_to_db(self, incident: SOSIncident) -> None:
        """Save incident to database"""
        location_lat = incident.location[0] if incident.location else None
        location_lon = incident.location[1] if incident.location else None
        
        self.db.execute_update(
            """INSERT INTO sos_incidents 
               (id, incident_type, sender_id, message, location_lat, location_lon, 
                timestamp, status, responders, acknowledgers, escalated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                incident.id,
                incident.incident_type.value,
                incident.sender_id,
                incident.message,
                location_lat,
                location_lon,
                incident.timestamp.isoformat(),
                incident.status.value,
                json.dumps(incident.responders),
                json.dumps(incident.acknowledgers),
                incident.escalated
            )
        )
    
    def _update_incident_in_db(self, incident: SOSIncident) -> bool:
        """Update incident in database"""
        try:
            location_lat = incident.location[0] if incident.location else None
            location_lon = incident.location[1] if incident.location else None
            
            rows_affected = self.db.execute_update(
                """UPDATE sos_incidents 
                   SET incident_type = ?, message = ?, location_lat = ?, location_lon = ?,
                       status = ?, responders = ?, acknowledgers = ?, escalated = ?,
                       cleared_by = ?, cleared_at = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    incident.incident_type.value,
                    incident.message,
                    location_lat,
                    location_lon,
                    incident.status.value,
                    json.dumps(incident.responders),
                    json.dumps(incident.acknowledgers),
                    incident.escalated,
                    incident.cleared_by,
                    incident.cleared_at.isoformat() if incident.cleared_at else None,
                    datetime.utcnow().isoformat(),
                    incident.id
                )
            )
            
            return rows_affected > 0
            
        except DatabaseError as e:
            self.logger.error(f"Failed to update incident {incident.id}: {e}")
            return False
    
    def _row_to_incident(self, row) -> SOSIncident:
        """Convert database row to SOSIncident object"""
        location = None
        if row['location_lat'] is not None and row['location_lon'] is not None:
            location = (row['location_lat'], row['location_lon'])
        
        cleared_at = None
        if row['cleared_at']:
            cleared_at = datetime.fromisoformat(row['cleared_at'])
        
        return SOSIncident(
            id=row['id'],
            incident_type=SOSType(row['incident_type']),
            sender_id=row['sender_id'],
            message=row['message'] or "",
            location=location,
            timestamp=datetime.fromisoformat(row['timestamp']),
            status=IncidentStatus(row['status']),
            responders=json.loads(row['responders']) if row['responders'] else [],
            acknowledgers=json.loads(row['acknowledgers']) if row['acknowledgers'] else [],
            escalated=bool(row['escalated']),
            cleared_by=row['cleared_by'],
            cleared_at=cleared_at
        )