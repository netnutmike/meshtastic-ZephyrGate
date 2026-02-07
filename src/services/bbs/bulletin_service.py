"""
BBS Bulletin Service for ZephyrGate

Handles bulletin posting, reading, listing, and deletion functionality.
Integrates with the menu system and database operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services.bbs.models import BBSBulletin, validate_bulletin_subject, validate_bulletin_content
from services.bbs.database import get_bbs_database


class BulletinService:
    """Service for managing bulletin board operations"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(__name__)
        self.bbs_db = get_bbs_database()
        self.config = config or {}
    
    def post_bulletin(self, board: str, sender_id: str, sender_name: str,
                     subject: str, content: str) -> Tuple[bool, str]:
        """
        Post a new bulletin to the specified board
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate input
            if not validate_bulletin_subject(subject):
                return False, "Invalid subject. Must be 1-100 characters."
            
            if not validate_bulletin_content(content):
                return False, "Invalid content. Must be 1-2000 characters."
            
            # Clean board name
            board = board.strip().lower()
            if not board:
                board = "general"
            
            # Create bulletin
            bulletin = self.bbs_db.create_bulletin(
                board=board,
                sender_id=sender_id,
                sender_name=sender_name,
                subject=subject.strip(),
                content=content.strip()
            )
            
            if bulletin:
                self.logger.info(f"Bulletin {bulletin.id} posted to '{board}' by {sender_name}")
                return True, f"Bulletin #{bulletin.id} posted to '{board}' board successfully."
            else:
                return False, "Failed to post bulletin. Please try again."
                
        except Exception as e:
            self.logger.error(f"Error posting bulletin: {e}")
            return False, "An error occurred while posting the bulletin."
    
    def get_bulletin(self, bulletin_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Get and display a specific bulletin
        
        Returns:
            Tuple of (success: bool, formatted_bulletin: str)
        """
        try:
            bulletin = self.bbs_db.get_bulletin(bulletin_id)
            
            if not bulletin:
                return False, f"Bulletin #{bulletin_id} not found."
            
            # Format bulletin for display
            formatted = self._format_bulletin_display(bulletin)
            
            # Mark as read by user (for future read tracking)
            bulletin.mark_read_by(user_id)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting bulletin {bulletin_id}: {e}")
            return False, "An error occurred while retrieving the bulletin."
    
    def list_bulletins(self, board: str = "general", limit: int = 20, 
                      offset: int = 0, user_id: str = "") -> Tuple[bool, str]:
        """
        List bulletins for a specific board
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            bulletins = self.bbs_db.get_bulletins_by_board(board, limit, offset)
            
            if not bulletins:
                return True, f"No bulletins found on '{board}' board."
            
            # Format bulletin list
            formatted = self._format_bulletin_list(bulletins, board)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error listing bulletins for board '{board}': {e}")
            return False, "An error occurred while retrieving bulletins."
    
    def list_all_bulletins(self, limit: int = 50, offset: int = 0, 
                          user_id: str = "") -> Tuple[bool, str]:
        """
        List bulletins from all boards
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            bulletins = self.bbs_db.get_all_bulletins(limit, offset)
            
            if not bulletins:
                return True, "No bulletins found."
            
            # Format bulletin list with board names
            formatted = self._format_all_bulletins_list(bulletins)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error listing all bulletins: {e}")
            return False, "An error occurred while retrieving bulletins."
    
    def delete_bulletin(self, bulletin_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Delete a bulletin (only by original poster or admin)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if bulletin exists and user can delete it
            bulletin = self.bbs_db.get_bulletin(bulletin_id)
            
            if not bulletin:
                return False, f"Bulletin #{bulletin_id} not found."
            
            if bulletin.sender_id != user_id:
                # TODO: Check if user is admin
                return False, "You can only delete your own bulletins."
            
            # Delete bulletin
            success = self.bbs_db.delete_bulletin(bulletin_id, user_id)
            
            if success:
                self.logger.info(f"Bulletin {bulletin_id} deleted by {user_id}")
                return True, f"Bulletin #{bulletin_id} deleted successfully."
            else:
                return False, f"Failed to delete bulletin #{bulletin_id}."
                
        except Exception as e:
            self.logger.error(f"Error deleting bulletin {bulletin_id}: {e}")
            return False, "An error occurred while deleting the bulletin."
    
    def search_bulletins(self, search_term: str, board: Optional[str] = None,
                        user_id: str = "") -> Tuple[bool, str]:
        """
        Search bulletins by subject or content
        
        Returns:
            Tuple of (success: bool, formatted_results: str)
        """
        try:
            if not search_term.strip():
                return False, "Search term cannot be empty."
            
            results = self.bbs_db.search_bulletins(search_term.strip(), board)
            
            if not results:
                board_text = f" on '{board}' board" if board else ""
                return True, f"No bulletins found matching '{search_term}'{board_text}."
            
            # Format search results
            formatted = self._format_search_results(results, search_term, board)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error searching bulletins: {e}")
            return False, "An error occurred while searching bulletins."
    
    def get_bulletin_boards(self) -> Tuple[bool, str]:
        """
        Get list of available bulletin boards from configuration
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            # Try to get boards from instance config first
            boards_config = self.config.get('boards', [])
            self.logger.info(f"Boards from instance config: {boards_config}")
            
            if not boards_config:
                # Fallback to ConfigurationManager
                from core.config import ConfigurationManager
                config = ConfigurationManager()
                config.load_config()
                
                # Try multiple config paths for compatibility
                boards_config = config.get('services.bbs.boards', [])
                self.logger.info(f"Boards from 'services.bbs.boards': {boards_config}")
                
                if not boards_config:
                    boards_config = config.get('bbs.boards', [])
                    self.logger.info(f"Boards from 'bbs.boards': {boards_config}")
            
            if not boards_config:
                self.logger.warning("No boards found in config, checking database")
                # Fallback to database boards if no config
                boards = self.bbs_db.get_bulletin_boards()
                if not boards:
                    return True, "No bulletin boards configured."
                
                lines = ["📋 Boards:"]
                for board in sorted(boards):
                    board_bulletins = self.bbs_db.get_bulletins_by_board(board, limit=1000)
                    count = len(board_bulletins)
                    lines.append(f"• {board} ({count})")
                
                return True, "\n".join(lines)
            
            # Format board list from config (compact for Meshtastic)
            self.logger.info(f"Formatting {len(boards_config)} boards from config")
            lines = ["📋 Boards:"]
            
            for board_info in boards_config:
                if isinstance(board_info, dict):
                    board_name = board_info.get('name', '')
                    board_desc = board_info.get('description', '')
                    
                    # Get bulletin count for each board
                    board_bulletins = self.bbs_db.get_bulletins_by_board(board_name, limit=1000)
                    count = len(board_bulletins)
                    
                    lines.append(f"• {board_name} ({count})")
            
            return True, "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error getting bulletin boards: {e}", exc_info=True)
            return False, "An error occurred while retrieving bulletin boards."
    
    def get_bulletin_stats(self, board: Optional[str] = None) -> Dict[str, Any]:
        """
        Get bulletin statistics
        
        Returns:
            Dictionary with bulletin statistics
        """
        try:
            stats = {}
            
            if board:
                # Board-specific stats
                bulletins = self.bbs_db.get_bulletins_by_board(board, limit=1000)
                stats['board'] = board
                stats['total_bulletins'] = len(bulletins)
                
                if bulletins:
                    # Calculate date range
                    dates = [b.timestamp for b in bulletins]
                    stats['oldest_bulletin'] = min(dates)
                    stats['newest_bulletin'] = max(dates)
                    
                    # Count unique posters
                    posters = set(b.sender_id for b in bulletins)
                    stats['unique_posters'] = len(posters)
                else:
                    stats['oldest_bulletin'] = None
                    stats['newest_bulletin'] = None
                    stats['unique_posters'] = 0
            else:
                # Global stats
                all_bulletins = self.bbs_db.get_all_bulletins(limit=1000)
                stats['total_bulletins'] = len(all_bulletins)
                
                boards = self.bbs_db.get_bulletin_boards()
                stats['total_boards'] = len(boards)
                
                if all_bulletins:
                    dates = [b.timestamp for b in all_bulletins]
                    stats['oldest_bulletin'] = min(dates)
                    stats['newest_bulletin'] = max(dates)
                    
                    posters = set(b.sender_id for b in all_bulletins)
                    stats['unique_posters'] = len(posters)
                else:
                    stats['oldest_bulletin'] = None
                    stats['newest_bulletin'] = None
                    stats['unique_posters'] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting bulletin stats: {e}")
            return {}
    
    def _format_bulletin_display(self, bulletin: BBSBulletin) -> str:
        """Format bulletin for detailed display (compact for Meshtastic)"""
        lines = []
        lines.append(f"📋 #{bulletin.id}: {bulletin.subject}")
        lines.append(f"From: {bulletin.sender_name}")
        lines.append(f"Date: {bulletin.timestamp.strftime('%m/%d %H:%M')}")
        lines.append("")
        lines.append(bulletin.content)
        
        return "\n".join(lines)
    
    def _format_bulletin_list(self, bulletins: List[BBSBulletin], board: str) -> str:
        """Format bulletin list for display (compact for Meshtastic)"""
        lines = []
        lines.append(f"📋 {board} ({len(bulletins)})")
        
        for bulletin in bulletins:
            # Calculate age
            age = self._calculate_age(bulletin.timestamp)
            
            # Truncate long fields for compact display
            sender = bulletin.sender_name[:8] if len(bulletin.sender_name) > 8 else bulletin.sender_name
            subject = bulletin.subject[:25] if len(bulletin.subject) > 25 else bulletin.subject
            
            # Compact format: ID From: Subject (age)
            lines.append(f"{bulletin.id} {sender}: {subject} ({age})")
        
        lines.append(f"read <ID> to view")
        
        return "\n".join(lines)
    
    def _format_all_bulletins_list(self, bulletins: List[BBSBulletin]) -> str:
        """Format bulletin list from all boards (compact for Meshtastic)"""
        lines = []
        lines.append(f"📋 All ({len(bulletins)})")
        
        for bulletin in bulletins:
            # Calculate age
            age = self._calculate_age(bulletin.timestamp)
            
            # Truncate long fields for compact display
            board = bulletin.board[:6] if len(bulletin.board) > 6 else bulletin.board
            sender = bulletin.sender_name[:8] if len(bulletin.sender_name) > 8 else bulletin.sender_name
            subject = bulletin.subject[:20] if len(bulletin.subject) > 20 else bulletin.subject
            
            # Compact format: ID [board] From: Subject (age)
            lines.append(f"{bulletin.id} [{board}] {sender}: {subject} ({age})")
        
        lines.append(f"read <ID> to view")
        
        return "\n".join(lines)
    
    def _format_search_results(self, results: List[BBSBulletin], search_term: str, 
                              board: Optional[str]) -> str:
        """Format search results for display"""
        lines = []
        board_text = f" on '{board}' board" if board else ""
        lines.append(f"Search results for '{search_term}'{board_text}:")
        lines.append("=" * 70)
        lines.append(f"{'ID':<4} | {'Board':<8} | {'From':<12} | {'Subject':<25} | {'Age':<8}")
        lines.append("-" * 70)
        
        for bulletin in results[:20]:  # Limit to 20 results
            # Calculate age
            age = self._calculate_age(bulletin.timestamp)
            
            # Truncate long fields
            board_name = bulletin.board[:7] + "…" if len(bulletin.board) > 8 else bulletin.board
            sender = bulletin.sender_name[:11] + "…" if len(bulletin.sender_name) > 12 else bulletin.sender_name
            subject = bulletin.subject[:24] + "…" if len(bulletin.subject) > 25 else bulletin.subject
            
            lines.append(f"{bulletin.id:<4} | {board_name:<8} | {sender:<12} | {subject:<25} | {age:<8}")
        
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more results")
        
        lines.append("-" * 70)
        lines.append(f"Found: {len(results)} bulletins")
        lines.append("")
        lines.append("Use 'read <ID>' to read a bulletin")
        
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
    
    def get_recent_activity(self, board: Optional[str] = None, 
                           hours: int = 24) -> Tuple[bool, str]:
        """
        Get recent bulletin activity
        
        Returns:
            Tuple of (success: bool, formatted_activity: str)
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            # Get recent bulletins
            if board:
                all_bulletins = self.bbs_db.get_bulletins_by_board(board, limit=100)
            else:
                all_bulletins = self.bbs_db.get_all_bulletins(limit=100)
            
            # Filter by time
            recent_bulletins = [
                b for b in all_bulletins 
                if b.timestamp >= cutoff
            ]
            
            if not recent_bulletins:
                board_text = f" on '{board}' board" if board else ""
                return True, f"No bulletin activity in the last {hours} hours{board_text}."
            
            # Format activity summary
            lines = []
            board_text = f" on '{board}' board" if board else ""
            lines.append(f"Bulletin activity in the last {hours} hours{board_text}:")
            lines.append("-" * 50)
            
            for bulletin in recent_bulletins[:10]:  # Show last 10
                age = self._calculate_age(bulletin.timestamp)
                subject = bulletin.subject[:30] + "…" if len(bulletin.subject) > 30 else bulletin.subject
                lines.append(f"  {age:<4} - {bulletin.sender_name}: {subject}")
            
            if len(recent_bulletins) > 10:
                lines.append(f"  ... and {len(recent_bulletins) - 10} more")
            
            lines.append("")
            lines.append(f"Total: {len(recent_bulletins)} new bulletins")
            
            return True, "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {e}")
            return False, "An error occurred while retrieving recent activity."


# Global bulletin service instance
bulletin_service: Optional[BulletinService] = None


def get_bulletin_service() -> BulletinService:
    """Get the global bulletin service instance"""
    global bulletin_service
    if bulletin_service is None:
        bulletin_service = BulletinService()
    return bulletin_service