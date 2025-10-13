"""
BBS Database Operations for ZephyrGate

Database operations for bulletins, mail, channels, and JS8Call integration.
Provides comprehensive CRUD operations with duplicate prevention and data integrity.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

from src.core.database import get_database, DatabaseError
from .models import (
    BBSBulletin, BBSMail, BBSChannel, JS8CallMessage, BBSSession,
    MailStatus, ChannelType, JS8CallPriority,
    generate_unique_id, validate_bulletin_subject, validate_bulletin_content,
    validate_mail_subject, validate_mail_content, validate_channel_name
)


class BBSDatabase:
    """BBS database operations manager"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
    
    # Bulletin Operations
    
    def create_bulletin(self, board: str, sender_id: str, sender_name: str, 
                       subject: str, content: str) -> Optional[BBSBulletin]:
        """Create a new bulletin"""
        try:
            # Validate input
            if not validate_bulletin_subject(subject):
                raise ValueError("Invalid bulletin subject")
            if not validate_bulletin_content(content):
                raise ValueError("Invalid bulletin content")
            
            # Create bulletin object
            bulletin = BBSBulletin(
                board=board,
                sender_id=sender_id,
                sender_name=sender_name,
                subject=subject.strip(),
                content=content.strip(),
                timestamp=datetime.utcnow(),
                unique_id=generate_unique_id(content, sender_id, datetime.utcnow())
            )
            
            # Insert into database
            query = """
                INSERT INTO bulletins (board, sender_id, sender_name, subject, content, 
                                     timestamp, unique_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            with self.db.transaction() as conn:
                cursor = conn.execute(query, (
                    bulletin.board, bulletin.sender_id, bulletin.sender_name,
                    bulletin.subject, bulletin.content, bulletin.timestamp.isoformat(),
                    bulletin.unique_id
                ))
                bulletin.id = cursor.lastrowid
            
            self.logger.info(f"Created bulletin {bulletin.id} on board '{board}' by {sender_name}")
            return bulletin
            
        except Exception as e:
            self.logger.error(f"Failed to create bulletin: {e}")
            return None
    
    def get_bulletin(self, bulletin_id: int) -> Optional[BBSBulletin]:
        """Get bulletin by ID"""
        try:
            query = "SELECT * FROM bulletins WHERE id = ?"
            rows = self.db.execute_query(query, (bulletin_id,))
            
            if rows:
                return self._row_to_bulletin(rows[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get bulletin {bulletin_id}: {e}")
            return None
    
    def get_bulletins_by_board(self, board: str, limit: int = 50, 
                              offset: int = 0) -> List[BBSBulletin]:
        """Get bulletins for a specific board"""
        try:
            query = """
                SELECT * FROM bulletins 
                WHERE board = ? 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            """
            rows = self.db.execute_query(query, (board, limit, offset))
            
            return [self._row_to_bulletin(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get bulletins for board '{board}': {e}")
            return []
    
    def get_all_bulletins(self, limit: int = 100, offset: int = 0) -> List[BBSBulletin]:
        """Get all bulletins across all boards"""
        try:
            query = """
                SELECT * FROM bulletins 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            """
            rows = self.db.execute_query(query, (limit, offset))
            
            return [self._row_to_bulletin(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get all bulletins: {e}")
            return []
    
    def delete_bulletin(self, bulletin_id: int, user_id: str) -> bool:
        """Delete bulletin (only by original sender or admin)"""
        try:
            # First check if user can delete this bulletin
            bulletin = self.get_bulletin(bulletin_id)
            if not bulletin:
                return False
            
            # Check permissions (sender or admin)
            if bulletin.sender_id != user_id:
                # TODO: Check if user is admin
                self.logger.warning(f"User {user_id} attempted to delete bulletin {bulletin_id} by {bulletin.sender_id}")
                return False
            
            query = "DELETE FROM bulletins WHERE id = ?"
            affected = self.db.execute_update(query, (bulletin_id,))
            
            if affected > 0:
                self.logger.info(f"Deleted bulletin {bulletin_id} by {user_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete bulletin {bulletin_id}: {e}")
            return False
    
    def get_bulletin_boards(self) -> List[str]:
        """Get list of all bulletin boards"""
        try:
            query = "SELECT DISTINCT board FROM bulletins ORDER BY board"
            rows = self.db.execute_query(query)
            
            return [row[0] for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get bulletin boards: {e}")
            return []
    
    def search_bulletins(self, search_term: str, board: Optional[str] = None) -> List[BBSBulletin]:
        """Search bulletins by subject or content"""
        try:
            search_term = f"%{search_term}%"
            
            if board:
                query = """
                    SELECT * FROM bulletins 
                    WHERE board = ? AND (subject LIKE ? OR content LIKE ?)
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (board, search_term, search_term))
            else:
                query = """
                    SELECT * FROM bulletins 
                    WHERE subject LIKE ? OR content LIKE ?
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (search_term, search_term))
            
            return [self._row_to_bulletin(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to search bulletins: {e}")
            return []
    
    # Mail Operations
    
    def send_mail(self, sender_id: str, sender_name: str, recipient_id: str,
                  subject: str, content: str) -> Optional[BBSMail]:
        """Send mail to a user"""
        try:
            # Validate input
            if not validate_mail_subject(subject):
                raise ValueError("Invalid mail subject")
            if not validate_mail_content(content):
                raise ValueError("Invalid mail content")
            
            # Create mail object
            mail = BBSMail(
                sender_id=sender_id,
                sender_name=sender_name,
                recipient_id=recipient_id,
                subject=subject.strip(),
                content=content.strip(),
                timestamp=datetime.utcnow(),
                unique_id=generate_unique_id(content, sender_id, datetime.utcnow())
            )
            
            # Insert into database
            query = """
                INSERT INTO mail (sender_id, sender_name, recipient_id, subject, 
                                content, timestamp, unique_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            with self.db.transaction() as conn:
                cursor = conn.execute(query, (
                    mail.sender_id, mail.sender_name, mail.recipient_id,
                    mail.subject, mail.content, mail.timestamp.isoformat(),
                    mail.unique_id
                ))
                mail.id = cursor.lastrowid
            
            self.logger.info(f"Sent mail {mail.id} from {sender_name} to {recipient_id}")
            return mail
            
        except Exception as e:
            self.logger.error(f"Failed to send mail: {e}")
            return None
    
    def get_mail(self, mail_id: int) -> Optional[BBSMail]:
        """Get mail by ID"""
        try:
            query = "SELECT * FROM mail WHERE id = ?"
            rows = self.db.execute_query(query, (mail_id,))
            
            if rows:
                return self._row_to_mail(rows[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get mail {mail_id}: {e}")
            return None
    
    def get_user_mail(self, user_id: str, include_read: bool = True) -> List[BBSMail]:
        """Get all mail for a user"""
        try:
            if include_read:
                query = """
                    SELECT * FROM mail 
                    WHERE recipient_id = ? 
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (user_id,))
            else:
                query = """
                    SELECT * FROM mail 
                    WHERE recipient_id = ? AND read_at IS NULL
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (user_id,))
            
            return [self._row_to_mail(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get mail for user {user_id}: {e}")
            return []
    
    def get_unread_mail_count(self, user_id: str) -> int:
        """Get count of unread mail for user"""
        try:
            query = "SELECT COUNT(*) FROM mail WHERE recipient_id = ? AND read_at IS NULL"
            rows = self.db.execute_query(query, (user_id,))
            
            return rows[0][0] if rows else 0
            
        except Exception as e:
            self.logger.error(f"Failed to get unread mail count for {user_id}: {e}")
            return 0
    
    def mark_mail_read(self, mail_id: int, user_id: str) -> bool:
        """Mark mail as read"""
        try:
            # Verify user can read this mail
            mail = self.get_mail(mail_id)
            if not mail or mail.recipient_id != user_id:
                return False
            
            query = "UPDATE mail SET read_at = ? WHERE id = ? AND recipient_id = ?"
            affected = self.db.execute_update(query, (
                datetime.utcnow().isoformat(), mail_id, user_id
            ))
            
            return affected > 0
            
        except Exception as e:
            self.logger.error(f"Failed to mark mail {mail_id} as read: {e}")
            return False
    
    def delete_mail(self, mail_id: int, user_id: str) -> bool:
        """Delete mail (only by recipient)"""
        try:
            # Verify user can delete this mail
            mail = self.get_mail(mail_id)
            if not mail or mail.recipient_id != user_id:
                return False
            
            query = "DELETE FROM mail WHERE id = ? AND recipient_id = ?"
            affected = self.db.execute_update(query, (mail_id, user_id))
            
            if affected > 0:
                self.logger.info(f"Deleted mail {mail_id} by {user_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete mail {mail_id}: {e}")
            return False
    
    # Channel Directory Operations
    
    def add_channel(self, name: str, frequency: str, description: str,
                   channel_type: str, location: str, coverage_area: str,
                   tone: str, offset: str, added_by: str) -> Optional[BBSChannel]:
        """Add channel to directory"""
        try:
            # Validate input
            if not validate_channel_name(name):
                raise ValueError("Invalid channel name")
            
            # Parse channel type
            try:
                ch_type = ChannelType(channel_type.lower())
            except ValueError:
                ch_type = ChannelType.OTHER
            
            # Create channel object
            channel = BBSChannel(
                name=name.strip(),
                frequency=frequency.strip(),
                description=description.strip(),
                channel_type=ch_type,
                location=location.strip(),
                coverage_area=coverage_area.strip(),
                tone=tone.strip(),
                offset=offset.strip(),
                added_by=added_by,
                added_at=datetime.utcnow()
            )
            
            # Insert into database
            query = """
                INSERT INTO channels (name, frequency, description, channel_type,
                                    location, coverage_area, tone, offset, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            with self.db.transaction() as conn:
                cursor = conn.execute(query, (
                    channel.name, channel.frequency, channel.description,
                    channel.channel_type.value, channel.location, channel.coverage_area,
                    channel.tone, channel.offset, channel.added_by,
                    channel.added_at.isoformat()
                ))
                channel.id = cursor.lastrowid
            
            self.logger.info(f"Added channel {channel.id}: {name} by {added_by}")
            return channel
            
        except Exception as e:
            self.logger.error(f"Failed to add channel: {e}")
            return None
    
    def get_channel(self, channel_id: int) -> Optional[BBSChannel]:
        """Get channel by ID"""
        try:
            query = "SELECT * FROM channels WHERE id = ?"
            rows = self.db.execute_query(query, (channel_id,))
            
            if rows:
                return self._row_to_channel(rows[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get channel {channel_id}: {e}")
            return None
    
    def get_all_channels(self, active_only: bool = True) -> List[BBSChannel]:
        """Get all channels"""
        try:
            if active_only:
                query = "SELECT * FROM channels WHERE active = 1 ORDER BY name"
            else:
                query = "SELECT * FROM channels ORDER BY name"
            
            rows = self.db.execute_query(query)
            return [self._row_to_channel(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get channels: {e}")
            return []
    
    def search_channels(self, search_term: str) -> List[BBSChannel]:
        """Search channels by name, frequency, or description"""
        try:
            search_term = f"%{search_term}%"
            query = """
                SELECT * FROM channels 
                WHERE active = 1 AND (
                    name LIKE ? OR 
                    frequency LIKE ? OR 
                    description LIKE ? OR
                    location LIKE ?
                )
                ORDER BY name
            """
            rows = self.db.execute_query(query, (search_term, search_term, search_term, search_term))
            
            return [self._row_to_channel(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to search channels: {e}")
            return []
    
    def update_channel(self, channel_id: int, **kwargs) -> bool:
        """Update channel information"""
        try:
            # Build update query dynamically
            valid_fields = [
                'name', 'frequency', 'description', 'channel_type',
                'location', 'coverage_area', 'tone', 'offset', 'verified', 'active'
            ]
            
            updates = []
            values = []
            
            for field, value in kwargs.items():
                if field in valid_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)
            
            if not updates:
                return False
            
            values.append(channel_id)
            query = f"UPDATE channels SET {', '.join(updates)} WHERE id = ?"
            
            affected = self.db.execute_update(query, tuple(values))
            return affected > 0
            
        except Exception as e:
            self.logger.error(f"Failed to update channel {channel_id}: {e}")
            return False
    
    def delete_channel(self, channel_id: int, user_id: str) -> bool:
        """Delete channel (mark as inactive)"""
        try:
            # For now, just mark as inactive rather than hard delete
            query = "UPDATE channels SET active = 0 WHERE id = ?"
            affected = self.db.execute_update(query, (channel_id,))
            
            if affected > 0:
                self.logger.info(f"Deactivated channel {channel_id} by {user_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete channel {channel_id}: {e}")
            return False
    
    # JS8Call Integration Operations
    
    def store_js8call_message(self, callsign: str, group: str, message: str,
                             frequency: str, priority: str = "normal") -> Optional[JS8CallMessage]:
        """Store JS8Call message"""
        try:
            # Parse priority
            try:
                js8_priority = JS8CallPriority(priority.lower())
            except ValueError:
                js8_priority = JS8CallPriority.NORMAL
            
            # Create JS8Call message object
            js8_msg = JS8CallMessage(
                callsign=callsign.strip(),
                group=group.strip(),
                message=message.strip(),
                frequency=frequency.strip(),
                timestamp=datetime.utcnow(),
                priority=js8_priority,
                unique_id=generate_unique_id(message, callsign, datetime.utcnow())
            )
            
            # Insert into database
            query = """
                INSERT INTO js8call_messages (callsign, group_name, message, frequency, 
                                            timestamp, priority, unique_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            with self.db.transaction() as conn:
                cursor = conn.execute(query, (
                    js8_msg.callsign, js8_msg.group, js8_msg.message,
                    js8_msg.frequency, js8_msg.timestamp.isoformat(),
                    js8_msg.priority.value, js8_msg.unique_id
                ))
                js8_msg.id = cursor.lastrowid
            
            self.logger.info(f"Stored JS8Call message {js8_msg.id} from {callsign} on {frequency}")
            return js8_msg
            
        except Exception as e:
            self.logger.error(f"Failed to store JS8Call message: {e}")
            return None
    
    def get_js8call_message(self, message_id: int) -> Optional[JS8CallMessage]:
        """Get JS8Call message by ID"""
        try:
            query = "SELECT * FROM js8call_messages WHERE id = ?"
            rows = self.db.execute_query(query, (message_id,))
            
            if rows:
                return self._row_to_js8call_message(rows[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get JS8Call message {message_id}: {e}")
            return None
    
    def get_recent_js8call_messages(self, limit: int = 50, 
                                   priority_filter: Optional[str] = None) -> List[JS8CallMessage]:
        """Get recent JS8Call messages"""
        try:
            if priority_filter:
                query = """
                    SELECT * FROM js8call_messages 
                    WHERE priority = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                rows = self.db.execute_query(query, (priority_filter, limit))
            else:
                query = """
                    SELECT * FROM js8call_messages 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                rows = self.db.execute_query(query, (limit,))
            
            return [self._row_to_js8call_message(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get recent JS8Call messages: {e}")
            return []
    
    def get_js8call_messages_by_group(self, group: str, limit: int = 50) -> List[JS8CallMessage]:
        """Get JS8Call messages for a specific group"""
        try:
            query = """
                SELECT * FROM js8call_messages 
                WHERE group_name = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            rows = self.db.execute_query(query, (group, limit))
            
            return [self._row_to_js8call_message(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get JS8Call messages for group '{group}': {e}")
            return []
    
    def get_urgent_js8call_messages(self, limit: int = 20) -> List[JS8CallMessage]:
        """Get urgent and emergency JS8Call messages"""
        try:
            query = """
                SELECT * FROM js8call_messages 
                WHERE priority IN ('urgent', 'emergency')
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            rows = self.db.execute_query(query, (limit,))
            
            return [self._row_to_js8call_message(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to get urgent JS8Call messages: {e}")
            return []
    
    def mark_js8call_message_forwarded(self, message_id: int) -> bool:
        """Mark JS8Call message as forwarded to mesh"""
        try:
            query = "UPDATE js8call_messages SET forwarded_to_mesh = 1 WHERE id = ?"
            affected = self.db.execute_update(query, (message_id,))
            
            return affected > 0
            
        except Exception as e:
            self.logger.error(f"Failed to mark JS8Call message {message_id} as forwarded: {e}")
            return False
    
    def search_js8call_messages(self, search_term: str, 
                               callsign_filter: Optional[str] = None) -> List[JS8CallMessage]:
        """Search JS8Call messages by content or callsign"""
        try:
            search_term = f"%{search_term}%"
            
            if callsign_filter:
                query = """
                    SELECT * FROM js8call_messages 
                    WHERE callsign = ? AND message LIKE ?
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (callsign_filter, search_term))
            else:
                query = """
                    SELECT * FROM js8call_messages 
                    WHERE message LIKE ? OR callsign LIKE ?
                    ORDER BY timestamp DESC
                """
                rows = self.db.execute_query(query, (search_term, search_term))
            
            return [self._row_to_js8call_message(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to search JS8Call messages: {e}")
            return []
    
    def get_js8call_statistics(self) -> Dict[str, Any]:
        """Get JS8Call message statistics"""
        try:
            stats = {}
            
            # Total messages
            total_rows = self.db.execute_query("SELECT COUNT(*) FROM js8call_messages")
            stats['total_messages'] = total_rows[0][0] if total_rows else 0
            
            # Messages by priority
            priority_rows = self.db.execute_query("""
                SELECT priority, COUNT(*) 
                FROM js8call_messages 
                GROUP BY priority
            """)
            stats['by_priority'] = {row[0]: row[1] for row in priority_rows}
            
            # Forwarded messages
            forwarded_rows = self.db.execute_query("""
                SELECT COUNT(*) FROM js8call_messages WHERE forwarded_to_mesh = 1
            """)
            stats['forwarded_messages'] = forwarded_rows[0][0] if forwarded_rows else 0
            
            # Unique callsigns
            callsign_rows = self.db.execute_query("""
                SELECT COUNT(DISTINCT callsign) FROM js8call_messages
            """)
            stats['unique_callsigns'] = callsign_rows[0][0] if callsign_rows else 0
            
            # Messages in last 24 hours
            yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
            recent_rows = self.db.execute_query("""
                SELECT COUNT(*) FROM js8call_messages WHERE timestamp > ?
            """, (yesterday,))
            stats['last_24h'] = recent_rows[0][0] if recent_rows else 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get JS8Call statistics: {e}")
            return {}
    
    # Utility Methods
    
    def _row_to_bulletin(self, row) -> BBSBulletin:
        """Convert database row to BBSBulletin"""
        bulletin = BBSBulletin()
        bulletin.id = row['id']
        bulletin.board = row['board']
        bulletin.sender_id = row['sender_id']
        bulletin.sender_name = row['sender_name']
        bulletin.subject = row['subject']
        bulletin.content = row['content']
        bulletin.unique_id = row['unique_id']
        
        # Parse timestamp
        if row['timestamp']:
            bulletin.timestamp = datetime.fromisoformat(row['timestamp'])
        
        return bulletin
    
    def _row_to_mail(self, row) -> BBSMail:
        """Convert database row to BBSMail"""
        mail = BBSMail()
        mail.id = row['id']
        mail.sender_id = row['sender_id']
        mail.sender_name = row['sender_name']
        mail.recipient_id = row['recipient_id']
        mail.subject = row['subject']
        mail.content = row['content']
        mail.unique_id = row['unique_id']
        
        # Parse timestamps
        if row['timestamp']:
            mail.timestamp = datetime.fromisoformat(row['timestamp'])
        
        if row['read_at']:
            mail.read_at = datetime.fromisoformat(row['read_at'])
            mail.status = MailStatus.READ
        else:
            mail.status = MailStatus.UNREAD
        
        return mail
    
    def _row_to_channel(self, row) -> BBSChannel:
        """Convert database row to BBSChannel"""
        channel = BBSChannel()
        channel.id = row['id']
        channel.name = row['name'] or ""
        channel.frequency = row['frequency'] or ""
        channel.description = row['description'] or ""
        channel.added_by = row['added_by'] or ""
        
        # Handle additional fields that might not exist in older schema
        try:
            channel.location = row['location'] or ""
        except (KeyError, IndexError):
            channel.location = ""
        
        try:
            channel.coverage_area = row['coverage_area'] or ""
        except (KeyError, IndexError):
            channel.coverage_area = ""
        
        try:
            channel.tone = row['tone'] or ""
        except (KeyError, IndexError):
            channel.tone = ""
        
        try:
            channel.offset = row['offset'] or ""
        except (KeyError, IndexError):
            channel.offset = ""
        
        try:
            channel.verified = bool(row['verified'])
        except (KeyError, IndexError):
            channel.verified = False
        
        try:
            channel.active = bool(row['active'])
        except (KeyError, IndexError):
            channel.active = True
        
        # Parse channel type
        try:
            channel_type_str = row['channel_type'] or 'other'
            try:
                channel.channel_type = ChannelType(channel_type_str)
            except ValueError:
                channel.channel_type = ChannelType.OTHER
        except (KeyError, IndexError):
            channel.channel_type = ChannelType.OTHER
        
        # Parse timestamp
        if row['added_at']:
            channel.added_at = datetime.fromisoformat(row['added_at'])
        
        return channel
    
    def _row_to_js8call_message(self, row) -> JS8CallMessage:
        """Convert database row to JS8CallMessage"""
        js8_msg = JS8CallMessage()
        js8_msg.id = row['id']
        js8_msg.callsign = row['callsign'] or ""
        js8_msg.group = row['group_name'] or ""
        js8_msg.message = row['message'] or ""
        js8_msg.frequency = row['frequency'] or ""
        js8_msg.unique_id = row['unique_id'] or ""
        js8_msg.forwarded_to_mesh = bool(row['forwarded_to_mesh'])
        
        # Parse priority
        priority_str = row['priority'] or 'normal'
        try:
            js8_msg.priority = JS8CallPriority(priority_str)
        except ValueError:
            js8_msg.priority = JS8CallPriority.NORMAL
        
        # Parse timestamp
        if row['timestamp']:
            js8_msg.timestamp = datetime.fromisoformat(row['timestamp'])
        
        return js8_msg
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get BBS statistics"""
        try:
            stats = {}
            
            # Bulletin statistics
            bulletin_rows = self.db.execute_query("SELECT COUNT(*) FROM bulletins")
            stats['total_bulletins'] = bulletin_rows[0][0] if bulletin_rows else 0
            
            board_rows = self.db.execute_query("SELECT COUNT(DISTINCT board) FROM bulletins")
            stats['bulletin_boards'] = board_rows[0][0] if board_rows else 0
            
            # Mail statistics
            mail_rows = self.db.execute_query("SELECT COUNT(*) FROM mail")
            stats['total_mail'] = mail_rows[0][0] if mail_rows else 0
            
            unread_rows = self.db.execute_query("SELECT COUNT(*) FROM mail WHERE read_at IS NULL")
            stats['unread_mail'] = unread_rows[0][0] if unread_rows else 0
            
            # Channel statistics
            channel_rows = self.db.execute_query("SELECT COUNT(*) FROM channels WHERE active = 1")
            stats['active_channels'] = channel_rows[0][0] if channel_rows else 0
            
            # JS8Call statistics
            stats['js8call'] = self.get_js8call_statistics()
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get BBS statistics: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old BBS data"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.isoformat()
            
            with self.db.transaction() as conn:
                # Clean up old bulletins
                cursor = conn.execute(
                    "DELETE FROM bulletins WHERE timestamp < ?",
                    (cutoff_str,)
                )
                bulletins_deleted = cursor.rowcount
                
                # Clean up old read mail
                cursor = conn.execute(
                    "DELETE FROM mail WHERE read_at IS NOT NULL AND timestamp < ?",
                    (cutoff_str,)
                )
                mail_deleted = cursor.rowcount
                
                # Clean up old JS8Call messages (keep urgent/emergency longer)
                cursor = conn.execute(
                    "DELETE FROM js8call_messages WHERE timestamp < ? AND priority = 'normal'",
                    (cutoff_str,)
                )
                js8call_deleted = cursor.rowcount
            
            self.logger.info(f"Cleaned up {bulletins_deleted} old bulletins, {mail_deleted} old mail, and {js8call_deleted} old JS8Call messages")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old BBS data: {e}")


# Global BBS database instance
bbs_db: Optional[BBSDatabase] = None


def get_bbs_database() -> BBSDatabase:
    """Get the global BBS database instance"""
    global bbs_db
    if bbs_db is None:
        bbs_db = BBSDatabase()
    return bbs_db