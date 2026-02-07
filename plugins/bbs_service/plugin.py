"""
BBS Service Plugin

Wraps the BBS (Bulletin Board System) service as a plugin for the ZephyrGate plugin system.
This allows the BBS service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import from src modules
from core.enhanced_plugin import EnhancedPlugin
from models.message import Message

# Import from local bbs modules
from .bbs.bulletin_service import BulletinService
from .bbs.mail_service import MailService
from .bbs.channel_service import ChannelService
from .bbs.menu_system import BBSMenuSystem
from .bbs.database import BBSDatabase


class BBSServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the BBS (Bulletin Board System) Service.
    
    Provides:
    - Bulletin board for public messages
    - Private mail system
    - Channel directory
    - Menu-driven interface
    - Message synchronization
    """
    
    async def initialize(self) -> bool:
        """Initialize the BBS service plugin"""
        self.logger.info("Initializing BBS Service Plugin")
        
        try:
            # Initialize BBS database (it uses get_database() internally)
            self.bbs_db = BBSDatabase()
            
            # Create service instances and pass config
            self.bulletin_service = BulletinService(self.config)
            self.mail_service = MailService()
            self.channel_service = ChannelService()
            
            # Create menu system (it doesn't need the services passed in)
            self.menu_system = BBSMenuSystem()
            
            # Register BBS commands
            await self._register_bbs_commands()
            
            # Register message handler
            self.register_message_handler(
                self._handle_message,
                priority=50
            )
            
            self.logger.info("BBS Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize BBS service: {e}", exc_info=True)
            return False
    
    async def _register_bbs_commands(self):
        """Register BBS commands with the plugin system"""
        # Main BBS command
        self.register_command(
            "bbs",
            self._handle_bbs_command,
            "Access the Bulletin Board System",
            priority=50
        )
        
        # List bulletins command
        self.register_command(
            "list",
            self._handle_list_command,
            "List recent bulletins",
            priority=50
        )
        
        # Mail command - direct access to mail submenu
        self.register_command(
            "mail",
            self._handle_mail_menu_command,
            "Access mail system (submenu)",
            priority=50
        )
        
        # Read bulletin command
        self.register_command(
            "read",
            self._handle_read_command,
            "Read a bulletin by ID",
            priority=50
        )
        
        # Post bulletin command
        self.register_command(
            "post",
            self._handle_post_command,
            "Post a new bulletin",
            priority=50
        )
        
        # Directory command
        self.register_command(
            "directory",
            self._handle_directory_command,
            "View channel directory",
            priority=50
        )
        
        # Channels command - alias for directory
        self.register_command(
            "channels",
            self._handle_directory_command,
            "View channel directory",
            priority=50
        )
        
        # Channel-specific commands (with 'c' prefix to avoid conflicts)
        self.register_command(
            "clist",
            self._handle_clist_command,
            "List channels in directory",
            priority=50
        )
        
        self.register_command(
            "cadd",
            self._handle_cadd_command,
            "Add a new channel to directory",
            priority=50
        )
        
        self.register_command(
            "cinfo",
            self._handle_cinfo_command,
            "View detailed channel information: cinfo <ID>",
            priority=50
        )
        
        self.register_command(
            "csearch",
            self._handle_csearch_command,
            "Search channels: csearch <term>",
            priority=50
        )
        
        # Boards command - list available bulletin boards
        self.register_command(
            "boards",
            self._handle_boards_command,
            "List available bulletin boards",
            priority=50
        )
        
        # Board command - switch active board
        self.register_command(
            "board",
            self._handle_board_switch_command,
            "Switch to a different board: board <name>",
            priority=50
        )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages for BBS service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            # Check if this is a BBS-related message
            content = message.content.lower().strip()
            
            # Let BBS commands be handled by command handlers
            if content.startswith(('bbs', 'read', 'post', 'mail', 'directory')):
                return False  # Let command handlers process it
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in BBS service: {e}", exc_info=True)
            return False
    
    async def _handle_bbs_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle main BBS command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            user_name = context.get('sender_name', sender_id)
            
            # If no args, enter BBS menu; otherwise process subcommand
            if not args:
                command = 'bbs'
            else:
                command = ' '.join(args)
            
            # Process command through menu system
            return await self.menu_system.process_command(sender_id, command, user_name)
            
        except Exception as e:
            self.logger.error(f"Error in BBS command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_list_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle list bulletins command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Determine board - use arg if provided, otherwise user's active board
            if args:
                board = args[0].lower()
                # Validate board
                if not self._is_valid_board(board):
                    return f"Board '{board}' not found. Use 'boards' to see available boards."
            else:
                board = self._get_user_board(sender_id)
            
            # List bulletins
            success, result = self.bulletin_service.list_bulletins(board=board, limit=20, user_id=sender_id)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in list command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_read_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle read bulletin command"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            if not args:
                # List recent bulletins
                success, result = self.bulletin_service.list_bulletins(board="general", limit=10, user_id=sender_id)
                return result
            
            # Read specific bulletin
            try:
                bulletin_id = int(args[0])
            except ValueError:
                return "Invalid bulletin ID. Use: read <ID>"
            
            success, result = self.bulletin_service.get_bulletin(bulletin_id, sender_id)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in read command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_post_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle post bulletin command"""
        try:
            # Improved UX: Use | as delimiter between subject and content
            # Format: post <subject> | <content>
            # Example: post Weather Alert | Heavy rain expected tomorrow
            
            if not args:
                return (
                    "Usage: post <subject> | <content>\n"
                    "Example: post Weather Alert | Heavy rain expected tomorrow\n"
                    "The | character separates the subject from the message content."
                )
            
            # Join all args and split by |
            full_text = ' '.join(args)
            
            if '|' not in full_text:
                return (
                    "Please use | to separate subject and content.\n"
                    "Example: post Weather Alert | Heavy rain expected tomorrow"
                )
            
            parts = full_text.split('|', 1)
            subject = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            
            if not subject:
                return "Subject cannot be empty."
            
            if not content:
                return "Content cannot be empty."
            
            sender_id = context.get('sender_id', 'unknown')
            sender_name = context.get('sender_name') or sender_id  # Use sender_id if sender_name is None or empty
            
            # Get user's active board
            board = self._get_user_board(sender_id)
            
            # Post bulletin
            success, result = self.bulletin_service.post_bulletin(
                board=board,
                sender_id=sender_id,
                sender_name=sender_name,
                subject=subject,
                content=content
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in post command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_mail_menu_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle mail menu command - enters mail submenu"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            user_name = context.get('sender_name', sender_id)
            
            # Enter mail submenu directly
            if not args:
                # Show mail menu
                return await self.menu_system.process_command(sender_id, 'mail', user_name)
            else:
                # Process mail subcommand
                command = 'mail ' + ' '.join(args)
                return await self.menu_system.process_command(sender_id, command, user_name)
            
        except Exception as e:
            self.logger.error(f"Error in mail menu command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_directory_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle directory/channels command - show channel help"""
        try:
            help_text = """📻 Channels:
clist, cadd, cinfo <ID>, csearch <term>
Ex: cadd Name|Freq|Desc"""
            
            return help_text
            
        except Exception as e:
            self.logger.error(f"Error in directory command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_boards_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle boards command - list available bulletin boards"""
        try:
            success, result = self.bulletin_service.get_bulletin_boards()
            return result
            
        except Exception as e:
            self.logger.error(f"Error in boards command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_board_switch_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle board command - switch active board for user"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            if not args:
                # Show current board
                current_board = self._get_user_board(sender_id)
                return f"Current board: {current_board}\nUse 'board <name>' to switch or 'boards' to list all."
            
            # Switch to specified board
            board_name = args[0].lower()
            
            # Validate board exists in config
            if not self._is_valid_board(board_name):
                return f"Board '{board_name}' not found. Use 'boards' to see available boards."
            
            # Set user's active board
            self._set_user_board(sender_id, board_name)
            
            return f"Switched to '{board_name}' board. Use 'list' to see bulletins."
            
        except Exception as e:
            self.logger.error(f"Error in board switch command: {e}")
            return f"Error: {str(e)}"
    
    def _get_user_board(self, user_id: str) -> str:
        """Get user's current active board"""
        # For now, use a simple in-memory dict. Could be stored in DB later.
        if not hasattr(self, '_user_boards'):
            self._user_boards = {}
        
        return self._user_boards.get(user_id, self.get_config('bbs.default_board', 'general'))
    
    def _set_user_board(self, user_id: str, board: str):
        """Set user's active board"""
        if not hasattr(self, '_user_boards'):
            self._user_boards = {}
        
        self._user_boards[user_id] = board
    
    def _is_valid_board(self, board_name: str) -> bool:
        """Check if board name is valid (exists in config)"""
        boards = self.get_config('bbs.boards', [])
        board_names = [b.get('name', '').lower() for b in boards if isinstance(b, dict)]
        return board_name.lower() in board_names
    
    async def _handle_clist_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle clist command - list channels"""
        try:
            success, result = self.channel_service.list_channels()
            return result
            
        except Exception as e:
            self.logger.error(f"Error in clist command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_cadd_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle cadd command - add a new channel"""
        try:
            if not args:
                return (
                    "Usage: cadd <name> | <frequency> | <description>\n"
                    "Example: cadd Repeater 1 | 146.520 | Local repeater\n"
                    "Use | to separate name, frequency, and description."
                )
            
            # Join all args and split by |
            full_text = ' '.join(args)
            
            if '|' not in full_text:
                return (
                    "Please use | to separate name, frequency, and description.\n"
                    "Example: cadd Repeater 1 | 146.520 | Local repeater"
                )
            
            parts = [p.strip() for p in full_text.split('|')]
            
            if len(parts) < 3:
                return "Please provide name, frequency, and description separated by |"
            
            name = parts[0]
            frequency = parts[1]
            description = parts[2]
            
            if not name or not description:
                return "Name and description cannot be empty."
            
            sender_id = context.get('sender_id', 'unknown')
            
            # Add channel
            success, result = self.channel_service.add_channel(
                name=name,
                frequency=frequency,
                description=description,
                added_by=sender_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in cadd command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_cinfo_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle cinfo command - view channel details"""
        try:
            if not args:
                return "Usage: cinfo <ID>\nExample: cinfo 1"
            
            try:
                channel_id = int(args[0])
            except ValueError:
                return "Invalid channel ID. Use: cinfo <ID>"
            
            success, result = self.channel_service.get_channel(channel_id)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in cinfo command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_csearch_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle csearch command - search channels"""
        try:
            if not args:
                return "Usage: csearch <term>\nExample: csearch repeater"
            
            search_term = ' '.join(args)
            success, result = self.channel_service.search_channels(search_term)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in csearch command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up BBS service resources"""
        self.logger.info("Cleaning up BBS Service Plugin")
        
        try:
            if hasattr(self, 'bbs_db') and self.bbs_db:
                await self.bbs_db.close()
            
            self.logger.info("BBS Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up BBS service: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get BBS service status"""
        status = {
            'service': 'bbs',
            'running': True,
            'features': {
                'bulletins': True,
                'mail': True,
                'channels': True,
                'menu_system': True
            }
        }
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="bbs_service",
            version="1.0.0",
            description="Bulletin Board System with mail, bulletins, and channel directory",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL
        )
