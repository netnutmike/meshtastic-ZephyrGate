"""
BBS Menu System for ZephyrGate

Hierarchical menu system for BBS navigation with session management.
Provides main menu, BBS menu, and utilities menu with command parsing.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum

from .models import BBSSession
from .database import get_bbs_database
from ...core.plugin_menu_registry import PluginMenuRegistry


class MenuType(Enum):
    """Menu types"""
    MAIN = "main"
    BBS = "bbs"
    MAIL = "mail"
    BULLETINS = "bulletins"
    CHANNELS = "channels"
    UTILITIES = "utilities"
    JS8CALL = "js8call"
    COMPOSE = "compose"
    READ = "read"


class MenuCommand:
    """Menu command definition"""
    
    def __init__(self, command: str, description: str, handler: Callable, 
                 requires_args: bool = False, admin_only: bool = False):
        self.command = command.lower()
        self.description = description
        self.handler = handler
        self.requires_args = requires_args
        self.admin_only = admin_only


class BBSMenuSystem:
    """BBS menu system with hierarchical navigation"""
    
    def __init__(self, plugin_menu_registry: Optional[PluginMenuRegistry] = None):
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, BBSSession] = {}
        self.bbs_db = get_bbs_database()
        self.session_timeout = 30  # minutes
        
        # Plugin menu integration
        self.plugin_menu_registry = plugin_menu_registry or PluginMenuRegistry()
        
        # Initialize menu commands
        self._init_menu_commands()
    
    def _init_menu_commands(self):
        """Initialize menu command handlers"""
        self.menu_commands = {
            MenuType.MAIN: {
                'bbs': MenuCommand('bbs', 'Enter BBS system', self._enter_bbs),
                'utilities': MenuCommand('utilities', 'System utilities', self._enter_utilities),
                'help': MenuCommand('help', 'Show help', self._show_help),
                'quit': MenuCommand('quit', 'Exit BBS', self._quit_bbs),
                'exit': MenuCommand('exit', 'Exit BBS', self._quit_bbs),
            },
            
            MenuType.BBS: {
                'mail': MenuCommand('mail', 'Personal mail system', self._enter_mail),
                'bulletins': MenuCommand('bulletins', 'Public bulletins', self._enter_bulletins),
                'channels': MenuCommand('channels', 'Channel directory', self._enter_channels),
                'js8call': MenuCommand('js8call', 'JS8Call integration', self._enter_js8call),
                'help': MenuCommand('help', 'Show BBS help', self._show_help),
                'main': MenuCommand('main', 'Return to main menu', self._go_to_main),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'quit': MenuCommand('quit', 'Exit BBS', self._quit_bbs),
            },
            
            MenuType.MAIL: {
                'list': MenuCommand('list', 'List mail messages', self._list_mail),
                'read': MenuCommand('read', 'Read mail by ID', self._read_mail, requires_args=True),
                'send': MenuCommand('send', 'Send new mail', self._compose_mail),
                'delete': MenuCommand('delete', 'Delete mail by ID', self._delete_mail, requires_args=True),
                'help': MenuCommand('help', 'Show mail help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'bbs': MenuCommand('bbs', 'Return to BBS menu', self._go_to_bbs),
                'main': MenuCommand('main', 'Return to main menu', self._go_to_main),
            },
            
            MenuType.BULLETINS: {
                'list': MenuCommand('list', 'List bulletins', self._list_bulletins),
                'read': MenuCommand('read', 'Read bulletin by ID', self._read_bulletin, requires_args=True),
                'post': MenuCommand('post', 'Post new bulletin', self._compose_bulletin),
                'boards': MenuCommand('boards', 'List bulletin boards', self._list_boards),
                'board': MenuCommand('board', 'Switch to board', self._switch_board, requires_args=True),
                'delete': MenuCommand('delete', 'Delete bulletin by ID', self._delete_bulletin, requires_args=True),
                'search': MenuCommand('search', 'Search bulletins', self._search_bulletins, requires_args=True),
                'help': MenuCommand('help', 'Show bulletin help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'bbs': MenuCommand('bbs', 'Return to BBS menu', self._go_to_bbs),
                'main': MenuCommand('main', 'Return to main menu', self._go_to_main),
            },
            
            MenuType.CHANNELS: {
                'list': MenuCommand('list', 'List channels', self._list_channels),
                'add': MenuCommand('add', 'Add new channel', self._add_channel),
                'info': MenuCommand('info', 'Channel info by ID', self._channel_info, requires_args=True),
                'search': MenuCommand('search', 'Search channels', self._search_channels, requires_args=True),
                'help': MenuCommand('help', 'Show channel help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'bbs': MenuCommand('bbs', 'Return to BBS menu', self._go_to_bbs),
                'main': MenuCommand('main', 'Return to main menu', self._go_to_main),
            },
            
            MenuType.UTILITIES: {
                'stats': MenuCommand('stats', 'System statistics', self._show_stats),
                'shame': MenuCommand('shame', 'Wall of shame (low battery)', self._show_wall_of_shame),
                'fortune': MenuCommand('fortune', 'Random fortune', self._show_fortune),
                'time': MenuCommand('time', 'Current time', self._show_time),
                'help': MenuCommand('help', 'Show utilities help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'main': MenuCommand('main', 'Return to main menu', self._go_to_main),
            }
        }
    
    def get_session(self, user_id: str) -> BBSSession:
        """Get or create user session"""
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        if user_id not in self.sessions:
            self.sessions[user_id] = BBSSession(user_id=user_id)
        
        session = self.sessions[user_id]
        session.last_activity = datetime.utcnow()
        return session
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        expired_users = []
        for user_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout):
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.sessions[user_id]
            self.logger.debug(f"Cleaned up expired BBS session for {user_id}")
    
    async def process_command(self, user_id: str, command: str, user_name: str = "") -> str:
        """Process BBS command and return response"""
        try:
            session = self.get_session(user_id)
            
            # Parse command and arguments
            parts = command.strip().split()
            if not parts:
                return self._show_current_menu(session)
            
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Get current menu type
            try:
                menu_type = MenuType(session.current_menu)
            except ValueError:
                menu_type = MenuType.MAIN
                session.current_menu = "main"
            
            # Handle special commands that work in any menu
            if cmd in ['help', '?']:
                return self._show_help(session, args)
            elif cmd in ['quit', 'exit', 'bye']:
                return self._quit_bbs(session, args)
            elif cmd in ['main']:
                return self._go_to_main(session, args)
            
            # Get menu commands for current menu
            menu_cmds = self.menu_commands.get(menu_type, {})
            
            if cmd in menu_cmds:
                menu_cmd = menu_cmds[cmd]
                
                # Check if command requires arguments
                if menu_cmd.requires_args and not args:
                    return f"Command '{cmd}' requires arguments. Type 'help' for usage."
                
                # Execute command
                return menu_cmd.handler(session, args, user_name=user_name)
            else:
                # Check plugin menu items
                plugin_result = await self._handle_plugin_menu_command(
                    cmd, session, args, user_name
                )
                if plugin_result is not None:
                    return plugin_result
                
                return f"Unknown command '{cmd}'. Type 'help' for available commands."
        
        except Exception as e:
            self.logger.error(f"Error processing BBS command '{command}' for {user_id}: {e}")
            return "An error occurred processing your command. Please try again."
    
    def _show_current_menu(self, session: BBSSession) -> str:
        """Show current menu options"""
        try:
            menu_type = MenuType(session.current_menu)
        except ValueError:
            menu_type = MenuType.MAIN
            session.current_menu = "main"
        
        menu_cmds = self.menu_commands.get(menu_type, {})
        
        # Build menu display
        lines = []
        lines.append(f"=== {menu_type.value.upper()} MENU ===")
        lines.append("")
        
        # Show built-in commands
        for cmd_name, menu_cmd in menu_cmds.items():
            lines.append(f"{cmd_name:12} - {menu_cmd.description}")
        
        # Show plugin menu items
        plugin_items = self.plugin_menu_registry.get_menu_items(menu_type.value)
        if plugin_items:
            lines.append("")
            lines.append("--- Plugin Commands ---")
            for item in plugin_items:
                lines.append(f"{item.command:12} - {item.description or item.label}")
        
        lines.append("")
        lines.append("Type a command or 'help' for more information.")
        
        return "\n".join(lines)
    
    async def _handle_plugin_menu_command(
        self,
        command: str,
        session: BBSSession,
        args: List[str],
        user_name: str
    ) -> Optional[str]:
        """
        Handle plugin menu command.
        
        Args:
            command: Command to handle
            session: User session
            args: Command arguments
            user_name: User name
            
        Returns:
            Command result or None if not a plugin command
        """
        # Build context for plugin handler
        context = {
            'user_id': session.user_id,
            'user_name': user_name,
            'session': session,
            'args': args,
            'menu': session.current_menu,
            'is_admin': False,  # TODO: Add admin check
            'timestamp': datetime.utcnow()
        }
        
        # Try to handle via plugin menu registry
        result = await self.plugin_menu_registry.handle_menu_command(command, context)
        return result
    
    def _show_help(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show help for current menu or specific command"""
        try:
            menu_type = MenuType(session.current_menu)
        except ValueError:
            menu_type = MenuType.MAIN
        
        if args:
            # Show help for specific command
            cmd = args[0].lower()
            menu_cmds = self.menu_commands.get(menu_type, {})
            
            if cmd in menu_cmds:
                menu_cmd = menu_cmds[cmd]
                help_text = f"Command: {cmd}\n"
                help_text += f"Description: {menu_cmd.description}\n"
                if menu_cmd.requires_args:
                    help_text += "Requires arguments: Yes\n"
                return help_text
            else:
                return f"Unknown command '{cmd}'"
        else:
            # Show general help
            return self._show_current_menu(session)
    
    # Navigation commands
    
    def _enter_bbs(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter BBS system"""
        session.push_menu("bbs")
        return "Welcome to the BBS system!\n\n" + self._show_current_menu(session)
    
    def _enter_utilities(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter utilities menu"""
        session.push_menu("utilities")
        return "System Utilities\n\n" + self._show_current_menu(session)
    
    def _enter_mail(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter mail system"""
        session.push_menu("mail")
        
        # Show unread mail count
        unread_count = self.bbs_db.get_unread_mail_count(session.user_id)
        welcome_msg = f"Personal Mail System\nYou have {unread_count} unread message(s).\n\n"
        
        return welcome_msg + self._show_current_menu(session)
    
    def _enter_bulletins(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter bulletin system"""
        session.push_menu("bulletins")
        session.set_context("current_board", "general")  # Default board
        
        return "Public Bulletin System\nCurrent board: general\n\n" + self._show_current_menu(session)
    
    def _enter_channels(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter channel directory"""
        session.push_menu("channels")
        
        # Show channel count
        channels = self.bbs_db.get_all_channels()
        channel_count = len(channels)
        welcome_msg = f"Channel Directory\n{channel_count} channels available.\n\n"
        
        return welcome_msg + self._show_current_menu(session)
    
    def _enter_js8call(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter JS8Call integration"""
        session.push_menu("js8call")
        return "JS8Call Integration\n(Feature coming soon)\n\n" + self._show_current_menu(session)
    
    def _go_back(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go back to previous menu"""
        previous_menu = session.pop_menu()
        return f"Returned to {previous_menu} menu.\n\n" + self._show_current_menu(session)
    
    def _go_to_main(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go to main menu"""
        session.current_menu = "main"
        session.menu_stack.clear()
        session.clear_context()
        return "Returned to main menu.\n\n" + self._show_current_menu(session)
    
    def _go_to_bbs(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go to BBS menu"""
        session.current_menu = "bbs"
        # Clear stack up to BBS level
        while session.menu_stack and session.menu_stack[-1] != "main":
            session.menu_stack.pop()
        return "Returned to BBS menu.\n\n" + self._show_current_menu(session)
    
    def _quit_bbs(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Quit BBS system"""
        # Clean up session
        if session.user_id in self.sessions:
            del self.sessions[session.user_id]
        
        return "Thank you for using the BBS system. Goodbye!"
    
    # Mail commands
    
    def _list_mail(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List user's mail"""
        try:
            mail_list = self.bbs_db.get_user_mail(session.user_id)
            
            if not mail_list:
                return "No mail messages found."
            
            lines = ["Your Mail Messages:"]
            lines.append("ID  | From        | Subject                    | Age     | Status")
            lines.append("-" * 70)
            
            for mail in mail_list[:20]:  # Limit to 20 messages
                status = "READ" if mail.is_read() else "NEW"
                age = mail.get_age_string()
                subject = mail.subject[:25] + "..." if len(mail.subject) > 25 else mail.subject
                sender = mail.sender_name[:10] + "..." if len(mail.sender_name) > 10 else mail.sender_name
                
                lines.append(f"{mail.id:3} | {sender:11} | {subject:26} | {age:7} | {status}")
            
            if len(mail_list) > 20:
                lines.append(f"\n... and {len(mail_list) - 20} more messages")
            
            lines.append(f"\nTotal: {len(mail_list)} messages")
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error listing mail for {session.user_id}: {e}")
            return "Error retrieving mail list."
    
    def _read_mail(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Read mail by ID"""
        try:
            mail_id = int(args[0])
            mail = self.bbs_db.get_mail(mail_id)
            
            if not mail:
                return f"Mail message {mail_id} not found."
            
            if mail.recipient_id != session.user_id:
                return "You can only read your own mail."
            
            # Mark as read
            self.bbs_db.mark_mail_read(mail_id, session.user_id)
            
            # Format message
            lines = []
            lines.append(f"Message ID: {mail.id}")
            lines.append(f"From: {mail.sender_name} ({mail.sender_id})")
            lines.append(f"Subject: {mail.subject}")
            lines.append(f"Date: {mail.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("-" * 50)
            lines.append(mail.content)
            lines.append("-" * 50)
            
            return "\n".join(lines)
            
        except (ValueError, IndexError):
            return "Invalid mail ID. Use: read <ID>"
        except Exception as e:
            self.logger.error(f"Error reading mail {args[0]} for {session.user_id}: {e}")
            return "Error reading mail message."
    
    def _compose_mail(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Start mail composition"""
        session.push_menu("compose")
        session.set_context("compose_type", "mail")
        session.set_context("compose_step", "recipient")
        
        return "Compose New Mail\nEnter recipient node ID (e.g., !12345678) or 'cancel' to abort:"
    
    def _delete_mail(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Delete mail by ID"""
        try:
            mail_id = int(args[0])
            success = self.bbs_db.delete_mail(mail_id, session.user_id)
            
            if success:
                return f"Mail message {mail_id} deleted."
            else:
                return f"Could not delete mail message {mail_id}. Check ID and permissions."
                
        except (ValueError, IndexError):
            return "Invalid mail ID. Use: delete <ID>"
        except Exception as e:
            self.logger.error(f"Error deleting mail {args[0]} for {session.user_id}: {e}")
            return "Error deleting mail message."
    
    # Bulletin commands
    
    def _list_bulletins(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List bulletins for current board"""
        try:
            current_board = session.get_context("current_board", "general")
            bulletins = self.bbs_db.get_bulletins_by_board(current_board, limit=20)
            
            if not bulletins:
                return f"No bulletins found on board '{current_board}'."
            
            lines = [f"Bulletins on '{current_board}' board:"]
            lines.append("ID  | From        | Subject                    | Age")
            lines.append("-" * 60)
            
            for bulletin in bulletins:
                age_delta = datetime.utcnow() - bulletin.timestamp
                if age_delta.days > 0:
                    age = f"{age_delta.days}d"
                elif age_delta.seconds > 3600:
                    age = f"{age_delta.seconds // 3600}h"
                else:
                    age = f"{age_delta.seconds // 60}m"
                
                subject = bulletin.subject[:25] + "..." if len(bulletin.subject) > 25 else bulletin.subject
                sender = bulletin.sender_name[:10] + "..." if len(bulletin.sender_name) > 10 else bulletin.sender_name
                
                lines.append(f"{bulletin.id:3} | {sender:11} | {subject:26} | {age:3}")
            
            lines.append(f"\nTotal: {len(bulletins)} bulletins")
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error listing bulletins for {session.user_id}: {e}")
            return "Error retrieving bulletin list."
    
    def _read_bulletin(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Read bulletin by ID"""
        try:
            bulletin_id = int(args[0])
            bulletin = self.bbs_db.get_bulletin(bulletin_id)
            
            if not bulletin:
                return f"Bulletin {bulletin_id} not found."
            
            # Format bulletin
            lines = []
            lines.append(f"Bulletin ID: {bulletin.id}")
            lines.append(f"Board: {bulletin.board}")
            lines.append(f"From: {bulletin.sender_name} ({bulletin.sender_id})")
            lines.append(f"Subject: {bulletin.subject}")
            lines.append(f"Date: {bulletin.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("-" * 50)
            lines.append(bulletin.content)
            lines.append("-" * 50)
            
            return "\n".join(lines)
            
        except (ValueError, IndexError):
            return "Invalid bulletin ID. Use: read <ID>"
        except Exception as e:
            self.logger.error(f"Error reading bulletin {args[0]} for {session.user_id}: {e}")
            return "Error reading bulletin."
    
    def _compose_bulletin(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Start bulletin composition"""
        session.push_menu("compose")
        session.set_context("compose_type", "bulletin")
        session.set_context("compose_step", "subject")
        session.set_context("compose_board", session.get_context("current_board", "general"))
        
        current_board = session.get_context("current_board", "general")
        return f"Compose New Bulletin for '{current_board}' board\nEnter subject or 'cancel' to abort:"
    
    def _delete_bulletin(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Delete bulletin by ID"""
        try:
            bulletin_id = int(args[0])
            success = self.bbs_db.delete_bulletin(bulletin_id, session.user_id)
            
            if success:
                return f"Bulletin {bulletin_id} deleted."
            else:
                return f"Could not delete bulletin {bulletin_id}. You can only delete your own bulletins."
                
        except (ValueError, IndexError):
            return "Invalid bulletin ID. Use: delete <ID>"
        except Exception as e:
            self.logger.error(f"Error deleting bulletin {args[0]} for {session.user_id}: {e}")
            return "Error deleting bulletin."
    
    def _list_boards(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List available bulletin boards"""
        try:
            boards = self.bbs_db.get_bulletin_boards()
            
            if not boards:
                return "No bulletin boards found."
            
            current_board = session.get_context("current_board", "general")
            lines = ["Available bulletin boards:"]
            
            for board in boards:
                marker = " *" if board == current_board else "  "
                lines.append(f"{marker} {board}")
            
            lines.append(f"\nCurrent board: {current_board}")
            lines.append("Use 'board <name>' to switch boards.")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error listing boards for {session.user_id}: {e}")
            return "Error retrieving board list."
    
    def _switch_board(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Switch to different bulletin board"""
        try:
            new_board = args[0].lower()
            session.set_context("current_board", new_board)
            
            return f"Switched to '{new_board}' board."
            
        except IndexError:
            return "Board name required. Use: board <name>"
    
    def _search_bulletins(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Search bulletins"""
        try:
            search_term = " ".join(args)
            current_board = session.get_context("current_board")
            
            results = self.bbs_db.search_bulletins(search_term, current_board)
            
            if not results:
                return f"No bulletins found matching '{search_term}'."
            
            lines = [f"Search results for '{search_term}':"]
            lines.append("ID  | Board   | From        | Subject")
            lines.append("-" * 50)
            
            for bulletin in results[:10]:  # Limit to 10 results
                subject = bulletin.subject[:20] + "..." if len(bulletin.subject) > 20 else bulletin.subject
                sender = bulletin.sender_name[:10] + "..." if len(bulletin.sender_name) > 10 else bulletin.sender_name
                board = bulletin.board[:8] + "..." if len(bulletin.board) > 8 else bulletin.board
                
                lines.append(f"{bulletin.id:3} | {board:7} | {sender:11} | {subject}")
            
            if len(results) > 10:
                lines.append(f"\n... and {len(results) - 10} more results")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error searching bulletins for {session.user_id}: {e}")
            return "Error searching bulletins."
    
    # Channel commands
    
    def _list_channels(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List channels in directory"""
        try:
            channels = self.bbs_db.get_all_channels()
            
            if not channels:
                return "No channels found in directory."
            
            lines = ["Channel Directory:"]
            lines.append("ID  | Name            | Frequency  | Type      | Location")
            lines.append("-" * 65)
            
            for channel in channels[:20]:  # Limit to 20 channels
                name = channel.name[:15] + "..." if len(channel.name) > 15 else channel.name
                freq = channel.frequency[:10] + "..." if len(channel.frequency) > 10 else channel.frequency
                ch_type = channel.channel_type.value[:9] + "..." if len(channel.channel_type.value) > 9 else channel.channel_type.value
                location = channel.location[:12] + "..." if len(channel.location) > 12 else channel.location
                
                lines.append(f"{channel.id:3} | {name:15} | {freq:10} | {ch_type:9} | {location}")
            
            if len(channels) > 20:
                lines.append(f"\n... and {len(channels) - 20} more channels")
            
            lines.append(f"\nTotal: {len(channels)} channels")
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error listing channels for {session.user_id}: {e}")
            return "Error retrieving channel list."
    
    def _add_channel(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Start channel addition process"""
        session.push_menu("compose")
        session.set_context("compose_type", "channel")
        session.set_context("compose_step", "name")
        
        return "Add New Channel\nEnter channel name or 'cancel' to abort:"
    
    def _channel_info(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show detailed channel information"""
        try:
            channel_id = int(args[0])
            channel = self.bbs_db.get_channel(channel_id)
            
            if not channel:
                return f"Channel {channel_id} not found."
            
            lines = []
            lines.append(f"Channel ID: {channel.id}")
            lines.append(f"Name: {channel.name}")
            lines.append(f"Frequency: {channel.frequency}")
            lines.append(f"Type: {channel.channel_type.value}")
            lines.append(f"Location: {channel.location}")
            lines.append(f"Coverage: {channel.coverage_area}")
            lines.append(f"Tone: {channel.tone}")
            lines.append(f"Offset: {channel.offset}")
            lines.append(f"Description: {channel.description}")
            lines.append(f"Added by: {channel.added_by}")
            lines.append(f"Added: {channel.added_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Verified: {'Yes' if channel.verified else 'No'}")
            
            return "\n".join(lines)
            
        except (ValueError, IndexError):
            return "Invalid channel ID. Use: info <ID>"
        except Exception as e:
            self.logger.error(f"Error getting channel info {args[0]} for {session.user_id}: {e}")
            return "Error retrieving channel information."
    
    def _search_channels(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Search channels"""
        try:
            search_term = " ".join(args)
            results = self.bbs_db.search_channels(search_term)
            
            if not results:
                return f"No channels found matching '{search_term}'."
            
            lines = [f"Search results for '{search_term}':"]
            lines.append("ID  | Name            | Frequency  | Location")
            lines.append("-" * 50)
            
            for channel in results[:10]:  # Limit to 10 results
                name = channel.name[:15] + "..." if len(channel.name) > 15 else channel.name
                freq = channel.frequency[:10] + "..." if len(channel.frequency) > 10 else channel.frequency
                location = channel.location[:12] + "..." if len(channel.location) > 12 else channel.location
                
                lines.append(f"{channel.id:3} | {name:15} | {freq:10} | {location}")
            
            if len(results) > 10:
                lines.append(f"\n... and {len(results) - 10} more results")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Error searching channels for {session.user_id}: {e}")
            return "Error searching channels."
    
    # Utility commands
    
    def _show_stats(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show system statistics"""
        try:
            from .statistics_service import get_statistics_service
            
            stats_service = get_statistics_service()
            stats = stats_service.get_system_statistics()
            
            # Add active sessions count
            stats.active_sessions = len(self.sessions)
            
            return stats_service.format_statistics_report(stats)
            
        except Exception as e:
            self.logger.error(f"Error getting stats for {session.user_id}: {e}")
            return "Error retrieving statistics."
    
    def _show_fortune(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show random fortune"""
        try:
            from .statistics_service import get_statistics_service
            
            stats_service = get_statistics_service()
            
            # Check if user specified a category
            category = args[0] if args else None
            
            fortune = stats_service.get_random_fortune(category)
            return f"🔮 Fortune: {fortune}"
            
        except Exception as e:
            self.logger.error(f"Error getting fortune for {session.user_id}: {e}")
            return "🔮 Fortune: The mesh connects us all, one hop at a time."
    
    def _show_wall_of_shame(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show wall of shame for low battery devices"""
        try:
            from .statistics_service import get_statistics_service
            
            stats_service = get_statistics_service()
            
            # Check if user specified a custom threshold
            threshold = 20  # Default threshold
            if args:
                try:
                    threshold = int(args[0])
                    if threshold < 1 or threshold > 100:
                        return "Battery threshold must be between 1 and 100."
                except ValueError:
                    return "Invalid threshold. Use: shame [threshold]"
            
            low_battery_nodes = stats_service.get_low_battery_nodes(threshold)
            return stats_service.format_wall_of_shame(low_battery_nodes, threshold)
            
        except Exception as e:
            self.logger.error(f"Error getting wall of shame for {session.user_id}: {e}")
            return "Error retrieving low battery information."
    
    def _show_time(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show current time"""
        now = datetime.utcnow()
        return f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def handle_compose_input(self, user_id: str, input_text: str, user_name: str = "") -> str:
        """Handle input during composition process"""
        session = self.get_session(user_id)
        
        if session.current_menu != "compose":
            return "Not in compose mode."
        
        compose_type = session.get_context("compose_type")
        compose_step = session.get_context("compose_step")
        
        # Handle cancel
        if input_text.lower().strip() == "cancel":
            session.pop_menu()  # Return to previous menu
            session.clear_context()
            return "Composition cancelled."
        
        if compose_type == "mail":
            return self._handle_mail_compose(session, input_text, user_name)
        elif compose_type == "bulletin":
            return self._handle_bulletin_compose(session, input_text, user_name)
        elif compose_type == "channel":
            return self._handle_channel_compose(session, input_text, user_name)
        else:
            session.pop_menu()
            return "Unknown composition type."
    
    def _handle_mail_compose(self, session: BBSSession, input_text: str, user_name: str) -> str:
        """Handle mail composition steps"""
        step = session.get_context("compose_step")
        
        if step == "recipient":
            # Validate recipient format
            recipient = input_text.strip()
            if not recipient.startswith("!") or len(recipient) != 9:
                return "Invalid node ID format. Use format like !12345678 or 'cancel':"
            
            session.set_context("compose_recipient", recipient)
            session.set_context("compose_step", "subject")
            return "Enter subject:"
        
        elif step == "subject":
            subject = input_text.strip()
            if not subject:
                return "Subject cannot be empty. Enter subject or 'cancel':"
            
            session.set_context("compose_subject", subject)
            session.set_context("compose_step", "content")
            return "Enter message content (end with '.' on a line by itself):"
        
        elif step == "content":
            content = session.get_context("compose_content", "")
            
            if input_text.strip() == ".":
                # Finish composition
                recipient = session.get_context("compose_recipient")
                subject = session.get_context("compose_subject")
                
                if not content.strip():
                    return "Message cannot be empty. Continue typing or 'cancel':"
                
                # Send mail
                mail = self.bbs_db.send_mail(
                    sender_id=session.user_id,
                    sender_name=user_name or session.user_id,
                    recipient_id=recipient,
                    subject=subject,
                    content=content.strip()
                )
                
                # Clean up and return to previous menu
                session.pop_menu()
                session.clear_context()
                
                if mail:
                    return f"Mail sent to {recipient}."
                else:
                    return "Failed to send mail. Please try again."
            else:
                # Accumulate content
                content += input_text + "\n"
                session.set_context("compose_content", content)
                return "Continue typing (end with '.' on a line by itself):"
        
        return "Unknown composition step."
    
    def _handle_bulletin_compose(self, session: BBSSession, input_text: str, user_name: str) -> str:
        """Handle bulletin composition steps"""
        step = session.get_context("compose_step")
        
        if step == "subject":
            subject = input_text.strip()
            if not subject:
                return "Subject cannot be empty. Enter subject or 'cancel':"
            
            session.set_context("compose_subject", subject)
            session.set_context("compose_step", "content")
            return "Enter bulletin content (end with '.' on a line by itself):"
        
        elif step == "content":
            content = session.get_context("compose_content", "")
            
            if input_text.strip() == ".":
                # Finish composition
                board = session.get_context("compose_board", "general")
                subject = session.get_context("compose_subject")
                
                if not content.strip():
                    return "Bulletin cannot be empty. Continue typing or 'cancel':"
                
                # Post bulletin
                bulletin = self.bbs_db.create_bulletin(
                    board=board,
                    sender_id=session.user_id,
                    sender_name=user_name or session.user_id,
                    subject=subject,
                    content=content.strip()
                )
                
                # Clean up and return to previous menu
                session.pop_menu()
                session.clear_context()
                
                if bulletin:
                    return f"Bulletin posted to '{board}' board."
                else:
                    return "Failed to post bulletin. Please try again."
            else:
                # Accumulate content
                content += input_text + "\n"
                session.set_context("compose_content", content)
                return "Continue typing (end with '.' on a line by itself):"
        
        return "Unknown composition step."
    
    def _handle_channel_compose(self, session: BBSSession, input_text: str, user_name: str) -> str:
        """Handle channel addition steps"""
        step = session.get_context("compose_step")
        
        if step == "name":
            name = input_text.strip()
            if not name:
                return "Channel name cannot be empty. Enter name or 'cancel':"
            
            session.set_context("compose_name", name)
            session.set_context("compose_step", "frequency")
            return "Enter frequency (optional, press Enter to skip):"
        
        elif step == "frequency":
            frequency = input_text.strip()
            session.set_context("compose_frequency", frequency)
            session.set_context("compose_step", "description")
            return "Enter description:"
        
        elif step == "description":
            description = input_text.strip()
            if not description:
                return "Description cannot be empty. Enter description or 'cancel':"
            
            # Add channel with collected information
            name = session.get_context("compose_name")
            frequency = session.get_context("compose_frequency", "")
            
            channel = self.bbs_db.add_channel(
                name=name,
                frequency=frequency,
                description=description,
                channel_type="other",  # Default type
                location="",
                coverage_area="",
                tone="",
                offset="",
                added_by=session.user_id
            )
            
            # Clean up and return to previous menu
            session.pop_menu()
            session.clear_context()
            
            if channel:
                return f"Channel '{name}' added to directory."
            else:
                return "Failed to add channel. Please try again."
        
        return "Unknown composition step."