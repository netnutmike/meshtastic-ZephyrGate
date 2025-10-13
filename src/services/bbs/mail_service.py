"""
BBS Mail Service for ZephyrGate

Handles private mail sending, receiving, reading, and deletion functionality.
Integrates with the menu system and database operations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import BBSMail, MailStatus, validate_mail_subject, validate_mail_content
from .database import get_bbs_database


class MailService:
    """Service for managing private mail operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bbs_db = get_bbs_database()
    
    def send_mail(self, sender_id: str, sender_name: str, recipient_id: str,
                  subject: str, content: str) -> Tuple[bool, str]:
        """
        Send a private mail message
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate input
            if not validate_mail_subject(subject):
                return False, "Invalid subject. Must be 1-100 characters."
            
            if not validate_mail_content(content):
                return False, "Invalid content. Must be 1-1000 characters."
            
            # Validate recipient format
            if not recipient_id.startswith("!") or len(recipient_id) != 9:
                return False, "Invalid recipient node ID format. Use format like !12345678"
            
            # Check if sender is trying to send to themselves
            if sender_id == recipient_id:
                return False, "You cannot send mail to yourself."
            
            # Send mail
            mail = self.bbs_db.send_mail(
                sender_id=sender_id,
                sender_name=sender_name,
                recipient_id=recipient_id,
                subject=subject.strip(),
                content=content.strip()
            )
            
            if mail:
                self.logger.info(f"Mail {mail.id} sent from {sender_name} to {recipient_id}")
                return True, f"Mail sent to {recipient_id} successfully."
            else:
                return False, "Failed to send mail. Please try again."
                
        except Exception as e:
            self.logger.error(f"Error sending mail: {e}")
            return False, "An error occurred while sending the mail."
    
    def get_mail(self, mail_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Get and display a specific mail message
        
        Returns:
            Tuple of (success: bool, formatted_mail: str)
        """
        try:
            mail = self.bbs_db.get_mail(mail_id)
            
            if not mail:
                return False, f"Mail #{mail_id} not found."
            
            # Check if user can read this mail
            if mail.recipient_id != user_id:
                return False, "You can only read your own mail."
            
            # Mark as read
            self.bbs_db.mark_mail_read(mail_id, user_id)
            
            # Format mail for display
            formatted = self._format_mail_display(mail)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting mail {mail_id}: {e}")
            return False, "An error occurred while retrieving the mail."
    
    def list_mail(self, user_id: str, include_read: bool = True, 
                  limit: int = 20, offset: int = 0) -> Tuple[bool, str]:
        """
        List mail messages for a user
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            mail_list = self.bbs_db.get_user_mail(user_id, include_read)
            
            if not mail_list:
                return True, "No mail messages found."
            
            # Apply limit and offset
            total_count = len(mail_list)
            mail_list = mail_list[offset:offset + limit]
            
            # Format mail list
            formatted = self._format_mail_list(mail_list, include_read, total_count, offset, limit)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error listing mail for {user_id}: {e}")
            return False, "An error occurred while retrieving mail."
    
    def list_unread_mail(self, user_id: str) -> Tuple[bool, str]:
        """
        List only unread mail messages for a user
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        return self.list_mail(user_id, include_read=False)
    
    def delete_mail(self, mail_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Delete a mail message (only by recipient)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if mail exists and user can delete it
            mail = self.bbs_db.get_mail(mail_id)
            
            if not mail:
                return False, f"Mail #{mail_id} not found."
            
            if mail.recipient_id != user_id:
                return False, "You can only delete your own mail."
            
            # Delete mail
            success = self.bbs_db.delete_mail(mail_id, user_id)
            
            if success:
                self.logger.info(f"Mail {mail_id} deleted by {user_id}")
                return True, f"Mail #{mail_id} deleted successfully."
            else:
                return False, f"Failed to delete mail #{mail_id}."
                
        except Exception as e:
            self.logger.error(f"Error deleting mail {mail_id}: {e}")
            return False, "An error occurred while deleting the mail."
    
    def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread mail for user
        
        Returns:
            Number of unread messages
        """
        try:
            return self.bbs_db.get_unread_mail_count(user_id)
        except Exception as e:
            self.logger.error(f"Error getting unread count for {user_id}: {e}")
            return 0
    
    def mark_mail_read(self, mail_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Mark a mail message as read
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if mail exists and user can mark it
            mail = self.bbs_db.get_mail(mail_id)
            
            if not mail:
                return False, f"Mail #{mail_id} not found."
            
            if mail.recipient_id != user_id:
                return False, "You can only mark your own mail as read."
            
            if mail.is_read():
                return True, f"Mail #{mail_id} is already marked as read."
            
            # Mark as read
            success = self.bbs_db.mark_mail_read(mail_id, user_id)
            
            if success:
                return True, f"Mail #{mail_id} marked as read."
            else:
                return False, f"Failed to mark mail #{mail_id} as read."
                
        except Exception as e:
            self.logger.error(f"Error marking mail {mail_id} as read: {e}")
            return False, "An error occurred while marking the mail as read."
    
    def get_mail_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get mail statistics for a user
        
        Returns:
            Dictionary with mail statistics
        """
        try:
            stats = {}
            
            # Get all mail for user
            all_mail = self.bbs_db.get_user_mail(user_id, include_read=True)
            stats['total_mail'] = len(all_mail)
            
            # Count unread
            unread_mail = self.bbs_db.get_user_mail(user_id, include_read=False)
            stats['unread_mail'] = len(unread_mail)
            stats['read_mail'] = stats['total_mail'] - stats['unread_mail']
            
            if all_mail:
                # Calculate date range
                dates = [m.timestamp for m in all_mail]
                stats['oldest_mail'] = min(dates)
                stats['newest_mail'] = max(dates)
                
                # Count unique senders
                senders = set(m.sender_id for m in all_mail)
                stats['unique_senders'] = len(senders)
                
                # Most active sender
                sender_counts = {}
                for mail in all_mail:
                    sender_counts[mail.sender_id] = sender_counts.get(mail.sender_id, 0) + 1
                
                most_active_sender = max(sender_counts.items(), key=lambda x: x[1])
                stats['most_active_sender'] = {
                    'sender_id': most_active_sender[0],
                    'message_count': most_active_sender[1]
                }
            else:
                stats['oldest_mail'] = None
                stats['newest_mail'] = None
                stats['unique_senders'] = 0
                stats['most_active_sender'] = None
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting mail stats for {user_id}: {e}")
            return {}
    
    def search_mail(self, user_id: str, search_term: str) -> Tuple[bool, str]:
        """
        Search user's mail by subject or content
        
        Returns:
            Tuple of (success: bool, formatted_results: str)
        """
        try:
            if not search_term.strip():
                return False, "Search term cannot be empty."
            
            # Get all user's mail
            all_mail = self.bbs_db.get_user_mail(user_id, include_read=True)
            
            # Filter by search term
            search_term_lower = search_term.strip().lower()
            results = []
            
            for mail in all_mail:
                if (search_term_lower in mail.subject.lower() or 
                    search_term_lower in mail.content.lower() or
                    search_term_lower in mail.sender_name.lower()):
                    results.append(mail)
            
            if not results:
                return True, f"No mail found matching '{search_term}'."
            
            # Format search results
            formatted = self._format_search_results(results, search_term)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error searching mail for {user_id}: {e}")
            return False, "An error occurred while searching mail."
    
    def get_conversation(self, user_id: str, other_user_id: str, 
                        limit: int = 10) -> Tuple[bool, str]:
        """
        Get conversation thread between two users
        
        Returns:
            Tuple of (success: bool, formatted_conversation: str)
        """
        try:
            # Get all mail for user
            all_mail = self.bbs_db.get_user_mail(user_id, include_read=True)
            
            # Filter for conversation with specific user
            conversation = []
            for mail in all_mail:
                if mail.sender_id == other_user_id:
                    conversation.append(mail)
            
            if not conversation:
                return True, f"No conversation found with {other_user_id}."
            
            # Sort by timestamp (newest first)
            conversation.sort(key=lambda m: m.timestamp, reverse=True)
            
            # Apply limit
            conversation = conversation[:limit]
            
            # Format conversation
            formatted = self._format_conversation(conversation, other_user_id)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting conversation for {user_id}: {e}")
            return False, "An error occurred while retrieving conversation."
    
    def _format_mail_display(self, mail: BBSMail) -> str:
        """Format mail for detailed display"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"Mail #{mail.id}")
        lines.append("=" * 60)
        lines.append(f"From: {mail.sender_name} ({mail.sender_id})")
        lines.append(f"To: {mail.recipient_id}")
        lines.append(f"Subject: {mail.subject}")
        lines.append(f"Sent: {mail.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        if mail.read_at:
            lines.append(f"Read: {mail.read_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            lines.append("Status: UNREAD")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append(mail.content)
        lines.append("-" * 60)
        lines.append(f"Message ID: {mail.unique_id}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _format_mail_list(self, mail_list: List[BBSMail], include_read: bool,
                         total_count: int, offset: int, limit: int) -> str:
        """Format mail list for display"""
        lines = []
        
        if include_read:
            lines.append("Your Mail Messages:")
        else:
            lines.append("Your Unread Mail Messages:")
        
        lines.append("=" * 75)
        lines.append(f"{'ID':<4} | {'From':<15} | {'Subject':<25} | {'Age':<8} | {'Status':<6}")
        lines.append("-" * 75)
        
        for mail in mail_list:
            # Calculate age
            age = self._calculate_age(mail.timestamp)
            
            # Truncate long fields
            sender = mail.sender_name[:14] + "…" if len(mail.sender_name) > 15 else mail.sender_name
            subject = mail.subject[:24] + "…" if len(mail.subject) > 25 else mail.subject
            
            # Status
            status = "READ" if mail.is_read() else "NEW"
            
            lines.append(f"{mail.id:<4} | {sender:<15} | {subject:<25} | {age:<8} | {status:<6}")
        
        lines.append("-" * 75)
        
        # Show pagination info
        if total_count > len(mail_list):
            start = offset + 1
            end = min(offset + limit, total_count)
            lines.append(f"Showing {start}-{end} of {total_count} messages")
        else:
            lines.append(f"Total: {len(mail_list)} messages")
        
        lines.append("")
        lines.append("Use 'read <ID>' to read a message")
        
        return "\n".join(lines)
    
    def _format_search_results(self, results: List[BBSMail], search_term: str) -> str:
        """Format search results for display"""
        lines = []
        lines.append(f"Mail search results for '{search_term}':")
        lines.append("=" * 70)
        lines.append(f"{'ID':<4} | {'From':<12} | {'Subject':<25} | {'Age':<8} | {'Status':<6}")
        lines.append("-" * 70)
        
        for mail in results[:20]:  # Limit to 20 results
            # Calculate age
            age = self._calculate_age(mail.timestamp)
            
            # Truncate long fields
            sender = mail.sender_name[:11] + "…" if len(mail.sender_name) > 12 else mail.sender_name
            subject = mail.subject[:24] + "…" if len(mail.subject) > 25 else mail.subject
            
            # Status
            status = "READ" if mail.is_read() else "NEW"
            
            lines.append(f"{mail.id:<4} | {sender:<12} | {subject:<25} | {age:<8} | {status:<6}")
        
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more results")
        
        lines.append("-" * 70)
        lines.append(f"Found: {len(results)} messages")
        lines.append("")
        lines.append("Use 'read <ID>' to read a message")
        
        return "\n".join(lines)
    
    def _format_conversation(self, conversation: List[BBSMail], other_user_id: str) -> str:
        """Format conversation thread for display"""
        lines = []
        lines.append(f"Conversation with {other_user_id}:")
        lines.append("=" * 60)
        
        for mail in reversed(conversation):  # Show oldest first in conversation
            age = self._calculate_age(mail.timestamp)
            status = " (NEW)" if not mail.is_read() else ""
            
            lines.append(f"[{age}] #{mail.id}: {mail.subject}{status}")
            lines.append(f"From: {mail.sender_name}")
            lines.append("-" * 40)
            
            # Show preview of content
            preview = mail.content[:100] + "..." if len(mail.content) > 100 else mail.content
            lines.append(preview)
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("Use 'read <ID>' to read full message")
        
        return "\n".join(lines)
    
    def _calculate_age(self, timestamp: datetime) -> str:
        """Calculate human-readable age from timestamp"""
        now = datetime.utcnow()
        delta = now - timestamp
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years}y"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months}mo"
        elif delta.days > 0:
            return f"{delta.days}d"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours}h"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes}m"
        else:
            return "now"
    
    def get_recent_activity(self, user_id: str, hours: int = 24) -> Tuple[bool, str]:
        """
        Get recent mail activity for user
        
        Returns:
            Tuple of (success: bool, formatted_activity: str)
        """
        try:
            from datetime import timedelta
            
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            # Get all mail for user
            all_mail = self.bbs_db.get_user_mail(user_id, include_read=True)
            
            # Filter by time
            recent_mail = [
                m for m in all_mail 
                if m.timestamp >= cutoff
            ]
            
            if not recent_mail:
                return True, f"No mail activity in the last {hours} hours."
            
            # Format activity summary
            lines = []
            lines.append(f"Mail activity in the last {hours} hours:")
            lines.append("-" * 50)
            
            for mail in recent_mail[:10]:  # Show last 10
                age = self._calculate_age(mail.timestamp)
                subject = mail.subject[:30] + "…" if len(mail.subject) > 30 else mail.subject
                status = " (NEW)" if not mail.is_read() else ""
                lines.append(f"  {age:<4} - {mail.sender_name}: {subject}{status}")
            
            if len(recent_mail) > 10:
                lines.append(f"  ... and {len(recent_mail) - 10} more")
            
            lines.append("")
            lines.append(f"Total: {len(recent_mail)} new messages")
            
            return True, "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error getting recent mail activity: {e}")
            return False, "An error occurred while retrieving recent activity."


# Global mail service instance
mail_service: Optional[MailService] = None


def get_mail_service() -> MailService:
    """Get the global mail service instance"""
    global mail_service
    if mail_service is None:
        mail_service = MailService()
    return mail_service