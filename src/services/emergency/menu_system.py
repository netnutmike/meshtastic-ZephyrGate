"""
Emergency Menu System for ZephyrGate

Hierarchical menu system for emergency/incident management.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from services.bbs.models import BBSSession


class MenuType(Enum):
    """Menu types"""
    EMERGENCY = "emergency"
    INCIDENTS = "incidents"


class MenuCommand:
    """Menu command definition"""
    
    def __init__(self, command: str, description: str, handler: Callable, 
                 requires_args: bool = False):
        self.command = command.lower()
        self.description = description
        self.handler = handler
        self.requires_args = requires_args


class EmergencyMenuSystem:
    """Emergency menu system with hierarchical navigation"""
    
    def __init__(self, emergency_service):
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, BBSSession] = {}
        self.emergency_service = emergency_service
        self.session_timeout = 30  # minutes
        
        # Initialize menu commands
        self._init_menu_commands()
    
    def _init_menu_commands(self):
        """Initialize menu command handlers"""
        self.menu_commands = {
            MenuType.EMERGENCY: {
                'sos': MenuCommand('sos', 'Send emergency SOS alert', self._handle_sos, requires_args=False),
                'cancel': MenuCommand('cancel', 'Cancel active SOS alert', self._handle_cancel),
                'respond': MenuCommand('respond', 'Respond to an SOS alert', self._handle_respond, requires_args=True),
                'status': MenuCommand('status', 'Check emergency status', self._handle_status),
                'incidents': MenuCommand('incidents', 'Manage incidents (submenu)', self._enter_incidents),
                'help': MenuCommand('help', 'Show help', self._show_help),
                'quit': MenuCommand('quit', 'Exit emergency menu', self._quit_menu),
                'exit': MenuCommand('exit', 'Exit emergency menu', self._quit_menu),
            },
            
            MenuType.INCIDENTS: {
                'list': MenuCommand('list', 'List active incidents', self._list_incidents),
                'view': MenuCommand('view', 'View incident details', self._view_incident, requires_args=True),
                'close': MenuCommand('close', 'Close an incident', self._close_incident, requires_args=True),
                'history': MenuCommand('history', 'View incident history', self._incident_history),
                'stats': MenuCommand('stats', 'View incident statistics', self._incident_stats),
                'help': MenuCommand('help', 'Show incidents help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'main': MenuCommand('main', 'Return to emergency menu', self._go_to_main),
                'quit': MenuCommand('quit', 'Exit emergency menu', self._quit_menu),
            }
        }
    
    def get_session(self, user_id: str) -> BBSSession:
        """Get or create user session"""
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        if user_id not in self.sessions:
            self.sessions[user_id] = BBSSession(user_id=user_id)
            self.sessions[user_id].current_menu = "emergency"
        
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
            self.logger.debug(f"Cleaned up expired emergency session for {user_id}")
    
    async def process_command(self, user_id: str, command: str, context: Dict[str, Any] = None) -> str:
        """Process emergency command and return response"""
        try:
            session = self.get_session(user_id)
            context = context or {}
            
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
                menu_type = MenuType.EMERGENCY
                session.current_menu = "emergency"
            
            # Handle special commands that work in any menu
            if cmd in ['help', '?']:
                return self._show_help(session, args)
            elif cmd in ['quit', 'exit', 'bye']:
                return self._quit_menu(session, args)
            elif cmd in ['main'] and menu_type != MenuType.EMERGENCY:
                return self._go_to_main(session, args)
            
            # Get menu commands for current menu
            menu_cmds = self.menu_commands.get(menu_type, {})
            
            if cmd in menu_cmds:
                menu_cmd = menu_cmds[cmd]
                
                # Check if command requires arguments
                if menu_cmd.requires_args and not args:
                    return f"Command '{cmd}' requires arguments. Type 'help' for usage."
                
                # Execute command
                return await menu_cmd.handler(session, args, context=context)
            else:
                return f"Unknown command '{cmd}'. Type 'help' for available commands."
        
        except Exception as e:
            self.logger.error(f"Error processing emergency command '{command}' for {user_id}: {e}")
            return "An error occurred processing your command. Please try again."
    
    def _show_current_menu(self, session: BBSSession) -> str:
        """Show current menu options"""
        try:
            menu_type = MenuType(session.current_menu)
        except ValueError:
            menu_type = MenuType.EMERGENCY
            session.current_menu = "emergency"
        
        menu_cmds = self.menu_commands.get(menu_type, {})
        
        # Build menu display
        lines = []
        lines.append(f"=== {menu_type.value.upper()} MENU ===")
        lines.append("")
        
        # Show built-in commands
        for cmd_name, menu_cmd in menu_cmds.items():
            lines.append(f"{cmd_name:12} - {menu_cmd.description}")
        
        lines.append("")
        lines.append("Type a command or 'help' for more information.")
        
        return "\n".join(lines)
    
    def _show_help(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Show help for current menu or specific command"""
        try:
            menu_type = MenuType(session.current_menu)
        except ValueError:
            menu_type = MenuType.EMERGENCY
        
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
    
    def _enter_incidents(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter incidents submenu"""
        session.push_menu("incidents")
        return "Incident Management\n\n" + self._show_current_menu(session)
    
    def _go_back(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go back to previous menu"""
        previous_menu = session.pop_menu()
        return f"Returned to {previous_menu} menu.\n\n" + self._show_current_menu(session)
    
    def _go_to_main(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go to main emergency menu"""
        session.current_menu = "emergency"
        session.menu_stack.clear()
        session.clear_context()
        return "Returned to emergency menu.\n\n" + self._show_current_menu(session)
    
    def _quit_menu(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Quit emergency menu system"""
        # Clean up session
        if session.user_id in self.sessions:
            del self.sessions[session.user_id]
        
        return "Exited emergency menu."
    
    # Emergency commands
    
    async def _handle_sos(self, session: BBSSession, args: List[str], context: Dict[str, Any] = None, **kwargs) -> str:
        """Handle SOS command"""
        try:
            from models.message import Message
            
            message_text = " ".join(args) if args else "Emergency assistance needed"
            context = context or {}
            
            # Create a message object for the emergency service
            message = Message(
                content=f"SOS {message_text}",
                sender_id=session.user_id,
                recipient_id=None,
                metadata=context.get('metadata', {})
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "🚨 SOS alert sent"
                
        except Exception as e:
            self.logger.error(f"Error in SOS command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_cancel(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Handle cancel command"""
        try:
            from models.message import Message
            
            # Create a message object for the emergency service
            message = Message(
                content="CANCEL",
                sender_id=session.user_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "No active SOS to cancel"
                
        except Exception as e:
            self.logger.error(f"Error in cancel command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_respond(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Handle respond command"""
        try:
            from models.message import Message
            
            incident_id = args[0]
            
            # Create a message object for the emergency service
            message = Message(
                content=f"RESPOND {incident_id}",
                sender_id=session.user_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return f"✅ Responded to incident {incident_id}"
                
        except Exception as e:
            self.logger.error(f"Error in respond command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_status(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Handle status command"""
        try:
            from models.message import Message
            
            # Create a message object for the emergency service
            message = Message(
                content="ACTIVE",
                sender_id=session.user_id,
                recipient_id=None
            )
            
            # Process through emergency service
            response = await self.emergency_service.handle_message(message)
            
            if response:
                return response.content
            else:
                return "No active incidents"
                
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return f"Error: {str(e)}"
    
    # Incident commands
    
    async def _list_incidents(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List active incidents"""
        try:
            if hasattr(self.emergency_service, 'incident_manager'):
                incidents = self.emergency_service.incident_manager.get_active_incidents()
                
                if not incidents:
                    return "No active incidents"
                
                result = ["Active Incidents:", "=" * 50]
                for incident in incidents:
                    result.append(f"ID: {incident.incident_id}")
                    result.append(f"Type: {incident.incident_type.value}")
                    result.append(f"From: {incident.sender_id}")
                    result.append(f"Status: {incident.status.value}")
                    result.append(f"Created: {incident.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error listing incidents: {e}")
            return f"Error: {str(e)}"
    
    async def _view_incident(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View incident details"""
        try:
            incident_id = args[0]
            
            if hasattr(self.emergency_service, 'incident_manager'):
                incident = self.emergency_service.incident_manager.get_incident(incident_id)
                
                if not incident:
                    return f"Incident {incident_id} not found"
                
                result = [f"Incident Details: {incident_id}", "=" * 50]
                result.append(f"Type: {incident.incident_type.value}")
                result.append(f"Status: {incident.status.value}")
                result.append(f"Sender: {incident.sender_id}")
                result.append(f"Location: {incident.location or 'Unknown'}")
                result.append(f"Created: {incident.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                result.append(f"Description: {incident.description}")
                
                if incident.responders:
                    result.append(f"\nResponders: {', '.join(incident.responders)}")
                
                return "\n".join(result)
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error viewing incident: {e}")
            return f"Error: {str(e)}"
    
    async def _close_incident(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Close an incident"""
        try:
            incident_id = args[0]
            
            if hasattr(self.emergency_service, 'incident_manager'):
                success = self.emergency_service.incident_manager.close_incident(incident_id)
                
                if success:
                    return f"✅ Incident {incident_id} closed"
                else:
                    return f"Could not close incident {incident_id}"
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error closing incident: {e}")
            return f"Error: {str(e)}"
    
    async def _incident_history(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View incident history"""
        try:
            if hasattr(self.emergency_service, 'incident_manager'):
                # Get closed incidents (last 10)
                all_incidents = self.emergency_service.incident_manager.get_all_incidents()
                closed = [i for i in all_incidents if i.status.value == 'resolved'][-10:]
                
                if not closed:
                    return "No incident history"
                
                result = ["Recent Incident History:", "=" * 50]
                for incident in closed:
                    result.append(f"ID: {incident.incident_id}")
                    result.append(f"Type: {incident.incident_type.value}")
                    result.append(f"Closed: {incident.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if incident.resolved_at else 'N/A'}")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error getting incident history: {e}")
            return f"Error: {str(e)}"
    
    async def _incident_stats(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View incident statistics"""
        try:
            if hasattr(self.emergency_service, 'incident_manager'):
                all_incidents = self.emergency_service.incident_manager.get_all_incidents()
                active = [i for i in all_incidents if i.status.value != 'resolved']
                resolved = [i for i in all_incidents if i.status.value == 'resolved']
                
                result = ["Incident Statistics:", "=" * 50]
                result.append(f"Total Incidents: {len(all_incidents)}")
                result.append(f"Active: {len(active)}")
                result.append(f"Resolved: {len(resolved)}")
                
                # Count by type
                types = {}
                for incident in all_incidents:
                    t = incident.incident_type.value
                    types[t] = types.get(t, 0) + 1
                
                if types:
                    result.append("\nBy Type:")
                    for t, count in types.items():
                        result.append(f"  {t}: {count}")
                
                return "\n".join(result)
            else:
                return "Incident manager not available"
                
        except Exception as e:
            self.logger.error(f"Error getting incident stats: {e}")
            return f"Error: {str(e)}"
