"""
Asset Tracking Menu System for ZephyrGate

Hierarchical menu system for asset tracking and management.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from services.bbs.models import BBSSession


class MenuType(Enum):
    """Menu types"""
    ASSET = "asset"
    TRACKING = "tracking"
    GEOFENCE = "geofence"


class MenuCommand:
    """Menu command definition"""
    
    def __init__(self, command: str, description: str, handler: Callable, 
                 requires_args: bool = False):
        self.command = command.lower()
        self.description = description
        self.handler = handler
        self.requires_args = requires_args


class AssetMenuSystem:
    """Asset tracking menu system with hierarchical navigation"""
    
    def __init__(self, asset_service):
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, BBSSession] = {}
        self.asset_service = asset_service
        self.session_timeout = 30  # minutes
        
        # Initialize menu commands
        self._init_menu_commands()
    
    def _init_menu_commands(self):
        """Initialize menu command handlers"""
        self.menu_commands = {
            MenuType.ASSET: {
                'list': MenuCommand('list', 'List all tracked assets', self._list_assets),
                'register': MenuCommand('register', 'Register new asset', self._register_asset, requires_args=True),
                'unregister': MenuCommand('unregister', 'Unregister asset', self._unregister_asset, requires_args=True),
                'locate': MenuCommand('locate', 'Locate an asset', self._locate_asset, requires_args=True),
                'status': MenuCommand('status', 'Get asset status', self._asset_status, requires_args=True),
                'update': MenuCommand('update', 'Update asset location', self._update_location, requires_args=True),
                'tracking': MenuCommand('tracking', 'Tracking management (submenu)', self._enter_tracking),
                'geofence': MenuCommand('geofence', 'Geofence management (submenu)', self._enter_geofence),
                'help': MenuCommand('help', 'Show help', self._show_help),
                'quit': MenuCommand('quit', 'Exit asset menu', self._quit_menu),
                'exit': MenuCommand('exit', 'Exit asset menu', self._quit_menu),
            },
            
            MenuType.TRACKING: {
                'start': MenuCommand('start', 'Start tracking asset', self._start_tracking, requires_args=True),
                'stop': MenuCommand('stop', 'Stop tracking asset', self._stop_tracking, requires_args=True),
                'history': MenuCommand('history', 'View tracking history', self._tracking_history, requires_args=True),
                'active': MenuCommand('active', 'List actively tracked assets', self._active_tracking),
                'stats': MenuCommand('stats', 'View tracking statistics', self._tracking_stats),
                'help': MenuCommand('help', 'Show tracking help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'main': MenuCommand('main', 'Return to asset menu', self._go_to_main),
                'quit': MenuCommand('quit', 'Exit asset menu', self._quit_menu),
            },
            
            MenuType.GEOFENCE: {
                'list': MenuCommand('list', 'List geofences', self._list_geofences),
                'create': MenuCommand('create', 'Create geofence', self._create_geofence, requires_args=True),
                'delete': MenuCommand('delete', 'Delete geofence', self._delete_geofence, requires_args=True),
                'check': MenuCommand('check', 'Check asset in geofence', self._check_geofence, requires_args=True),
                'alerts': MenuCommand('alerts', 'View geofence alerts', self._geofence_alerts),
                'help': MenuCommand('help', 'Show geofence help', self._show_help),
                'back': MenuCommand('back', 'Go back', self._go_back),
                'main': MenuCommand('main', 'Return to asset menu', self._go_to_main),
                'quit': MenuCommand('quit', 'Exit asset menu', self._quit_menu),
            }
        }
    
    def get_session(self, user_id: str) -> BBSSession:
        """Get or create user session"""
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        if user_id not in self.sessions:
            self.sessions[user_id] = BBSSession(user_id=user_id)
            self.sessions[user_id].current_menu = "asset"
        
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
            self.logger.debug(f"Cleaned up expired asset session for {user_id}")
    
    async def process_command(self, user_id: str, command: str, context: Dict[str, Any] = None) -> str:
        """Process asset command and return response"""
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
                menu_type = MenuType.ASSET
                session.current_menu = "asset"
            
            # Handle special commands that work in any menu
            if cmd in ['help', '?']:
                return self._show_help(session, args)
            elif cmd in ['quit', 'exit', 'bye']:
                return self._quit_menu(session, args)
            elif cmd in ['main'] and menu_type != MenuType.ASSET:
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
            self.logger.error(f"Error processing asset command '{command}' for {user_id}: {e}")
            return "An error occurred processing your command. Please try again."
    
    def _show_current_menu(self, session: BBSSession) -> str:
        """Show current menu options"""
        try:
            menu_type = MenuType(session.current_menu)
        except ValueError:
            menu_type = MenuType.ASSET
            session.current_menu = "asset"
        
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
            menu_type = MenuType.ASSET
        
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
    
    def _enter_tracking(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter tracking submenu"""
        session.push_menu("tracking")
        return "Asset Tracking Management\n\n" + self._show_current_menu(session)
    
    def _enter_geofence(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Enter geofence submenu"""
        session.push_menu("geofence")
        return "Geofence Management\n\n" + self._show_current_menu(session)
    
    def _go_back(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go back to previous menu"""
        previous_menu = session.pop_menu()
        return f"Returned to {previous_menu} menu.\n\n" + self._show_current_menu(session)
    
    def _go_to_main(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Go to main asset menu"""
        session.current_menu = "asset"
        session.menu_stack.clear()
        session.clear_context()
        return "Returned to asset menu.\n\n" + self._show_current_menu(session)
    
    def _quit_menu(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Quit asset menu system"""
        # Clean up session
        if session.user_id in self.sessions:
            del self.sessions[session.user_id]
        
        return "Exited asset menu."
    
    # Asset commands
    
    async def _list_assets(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List all tracked assets"""
        try:
            if hasattr(self.asset_service, 'list_assets'):
                assets = await self.asset_service.list_assets()
                if not assets:
                    return "No assets being tracked"
                
                result = ["📍 Tracked Assets:", "=" * 50]
                for asset in assets:
                    result.append(f"ID: {asset.id}")
                    result.append(f"Name: {asset.name}")
                    result.append(f"Status: {asset.status}")
                    result.append(f"Last Update: {asset.last_update}")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Asset listing not available"
            
        except Exception as e:
            self.logger.error(f"Error listing assets: {e}")
            return f"Error: {str(e)}"
    
    async def _register_asset(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Register new asset"""
        try:
            asset_id = args[0]
            asset_name = ' '.join(args[1:]) if len(args) > 1 else asset_id
            
            if hasattr(self.asset_service, 'register_asset'):
                success = await self.asset_service.register_asset(asset_id, name=asset_name)
                return f"✅ Asset {asset_id} registered for tracking" if success else f"❌ Failed to register asset {asset_id}"
            else:
                return "Asset registration not available"
            
        except Exception as e:
            self.logger.error(f"Error registering asset: {e}")
            return f"Error: {str(e)}"
    
    async def _unregister_asset(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Unregister asset"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'unregister_asset'):
                success = await self.asset_service.unregister_asset(asset_id)
                return f"✅ Asset {asset_id} unregistered" if success else f"❌ Failed to unregister asset {asset_id}"
            else:
                return "Asset unregistration not available"
            
        except Exception as e:
            self.logger.error(f"Error unregistering asset: {e}")
            return f"Error: {str(e)}"
    
    async def _locate_asset(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Locate an asset"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'get_asset_location'):
                location = await self.asset_service.get_asset_location(asset_id)
                if location:
                    return (
                        f"📍 Asset {asset_id} Location:\n"
                        f"Latitude: {location['latitude']}\n"
                        f"Longitude: {location['longitude']}\n"
                        f"Last Update: {location.get('timestamp', 'N/A')}"
                    )
                else:
                    return f"Asset {asset_id} not found or no location data"
            else:
                return "Asset location lookup not available"
            
        except Exception as e:
            self.logger.error(f"Error locating asset: {e}")
            return f"Error: {str(e)}"
    
    async def _asset_status(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Get asset status"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'get_asset_status'):
                status = await self.asset_service.get_asset_status(asset_id)
                if status:
                    return (
                        f"📊 Asset {asset_id} Status:\n"
                        f"Name: {status.get('name', 'Unknown')}\n"
                        f"Status: {status.get('status', 'Unknown')}\n"
                        f"Location: {status.get('latitude', 'N/A')}, {status.get('longitude', 'N/A')}\n"
                        f"Battery: {status.get('battery', 'N/A')}%\n"
                        f"Last Update: {status.get('last_update', 'N/A')}"
                    )
                else:
                    return f"Asset {asset_id} not found"
            else:
                return "Asset status lookup not available"
            
        except Exception as e:
            self.logger.error(f"Error getting asset status: {e}")
            return f"Error: {str(e)}"
    
    async def _update_location(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Update asset location"""
        try:
            if len(args) < 3:
                return "Usage: update <asset_id> <latitude> <longitude>"
            
            asset_id = args[0]
            latitude = float(args[1])
            longitude = float(args[2])
            
            if hasattr(self.asset_service, 'update_asset_location'):
                success = await self.asset_service.update_asset_location(asset_id, latitude, longitude)
                return f"✅ Asset {asset_id} location updated" if success else f"❌ Failed to update asset {asset_id}"
            else:
                return "Asset location update not available"
            
        except ValueError:
            return "Invalid coordinates. Use: update <asset_id> <latitude> <longitude>"
        except Exception as e:
            self.logger.error(f"Error updating location: {e}")
            return f"Error: {str(e)}"
    
    # Tracking commands
    
    async def _start_tracking(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Start tracking asset"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'start_tracking'):
                success = await self.asset_service.start_tracking(asset_id)
                return f"✅ Started tracking asset {asset_id}" if success else f"❌ Failed to start tracking {asset_id}"
            else:
                return "Tracking control not available"
            
        except Exception as e:
            self.logger.error(f"Error starting tracking: {e}")
            return f"Error: {str(e)}"
    
    async def _stop_tracking(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Stop tracking asset"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'stop_tracking'):
                success = await self.asset_service.stop_tracking(asset_id)
                return f"✅ Stopped tracking asset {asset_id}" if success else f"❌ Failed to stop tracking {asset_id}"
            else:
                return "Tracking control not available"
            
        except Exception as e:
            self.logger.error(f"Error stopping tracking: {e}")
            return f"Error: {str(e)}"
    
    async def _tracking_history(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View tracking history"""
        try:
            asset_id = args[0]
            
            if hasattr(self.asset_service, 'get_tracking_history'):
                history = await self.asset_service.get_tracking_history(asset_id, limit=10)
                if not history:
                    return f"No tracking history for asset {asset_id}"
                
                result = [f"📍 Tracking History for {asset_id}:", "=" * 50]
                for entry in history:
                    result.append(f"Time: {entry.timestamp}")
                    result.append(f"Location: {entry.latitude}, {entry.longitude}")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Tracking history not available"
            
        except Exception as e:
            self.logger.error(f"Error getting tracking history: {e}")
            return f"Error: {str(e)}"
    
    async def _active_tracking(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List actively tracked assets"""
        try:
            if hasattr(self.asset_service, 'get_active_tracking'):
                assets = await self.asset_service.get_active_tracking()
                if not assets:
                    return "No assets currently being tracked"
                
                result = ["📍 Actively Tracked Assets:", "=" * 50]
                for asset in assets:
                    result.append(f"ID: {asset.id} - {asset.name}")
                
                return "\n".join(result)
            else:
                return "Active tracking list not available"
            
        except Exception as e:
            self.logger.error(f"Error getting active tracking: {e}")
            return f"Error: {str(e)}"
    
    async def _tracking_stats(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View tracking statistics"""
        try:
            if hasattr(self.asset_service, 'get_tracking_stats'):
                stats = await self.asset_service.get_tracking_stats()
                
                result = ["📊 Tracking Statistics:", "=" * 50]
                result.append(f"Total Assets: {stats.get('total_assets', 0)}")
                result.append(f"Active Tracking: {stats.get('active_tracking', 0)}")
                result.append(f"Location Updates (24h): {stats.get('updates_24h', 0)}")
                
                return "\n".join(result)
            else:
                return "Tracking statistics not available"
            
        except Exception as e:
            self.logger.error(f"Error getting tracking stats: {e}")
            return f"Error: {str(e)}"
    
    # Geofence commands
    
    async def _list_geofences(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """List geofences"""
        try:
            if hasattr(self.asset_service, 'list_geofences'):
                geofences = await self.asset_service.list_geofences()
                if not geofences:
                    return "No geofences defined"
                
                result = ["🗺️ Geofences:", "=" * 50]
                for gf in geofences:
                    result.append(f"ID: {gf.id} - {gf.name}")
                    result.append(f"Center: {gf.latitude}, {gf.longitude}")
                    result.append(f"Radius: {gf.radius}m")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Geofence listing not available"
            
        except Exception as e:
            self.logger.error(f"Error listing geofences: {e}")
            return f"Error: {str(e)}"
    
    async def _create_geofence(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Create geofence"""
        try:
            if len(args) < 4:
                return "Usage: create <name> <latitude> <longitude> <radius_meters>"
            
            name = args[0]
            latitude = float(args[1])
            longitude = float(args[2])
            radius = float(args[3])
            
            if hasattr(self.asset_service, 'create_geofence'):
                success = await self.asset_service.create_geofence(name, latitude, longitude, radius)
                return f"✅ Geofence '{name}' created" if success else f"❌ Failed to create geofence"
            else:
                return "Geofence creation not available"
            
        except ValueError:
            return "Invalid parameters. Use: create <name> <latitude> <longitude> <radius_meters>"
        except Exception as e:
            self.logger.error(f"Error creating geofence: {e}")
            return f"Error: {str(e)}"
    
    async def _delete_geofence(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Delete geofence"""
        try:
            geofence_id = args[0]
            
            if hasattr(self.asset_service, 'delete_geofence'):
                success = await self.asset_service.delete_geofence(geofence_id)
                return f"✅ Geofence {geofence_id} deleted" if success else f"❌ Failed to delete geofence"
            else:
                return "Geofence deletion not available"
            
        except Exception as e:
            self.logger.error(f"Error deleting geofence: {e}")
            return f"Error: {str(e)}"
    
    async def _check_geofence(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """Check if asset is in geofence"""
        try:
            if len(args) < 2:
                return "Usage: check <asset_id> <geofence_id>"
            
            asset_id = args[0]
            geofence_id = args[1]
            
            if hasattr(self.asset_service, 'check_geofence'):
                result = await self.asset_service.check_geofence(asset_id, geofence_id)
                if result:
                    status = "inside" if result['inside'] else "outside"
                    return f"Asset {asset_id} is {status} geofence {geofence_id}"
                else:
                    return "Unable to check geofence status"
            else:
                return "Geofence checking not available"
            
        except Exception as e:
            self.logger.error(f"Error checking geofence: {e}")
            return f"Error: {str(e)}"
    
    async def _geofence_alerts(self, session: BBSSession, args: List[str], **kwargs) -> str:
        """View geofence alerts"""
        try:
            if hasattr(self.asset_service, 'get_geofence_alerts'):
                alerts = await self.asset_service.get_geofence_alerts(limit=10)
                if not alerts:
                    return "No recent geofence alerts"
                
                result = ["🚨 Recent Geofence Alerts:", "=" * 50]
                for alert in alerts:
                    result.append(f"Asset: {alert.asset_id}")
                    result.append(f"Geofence: {alert.geofence_id}")
                    result.append(f"Type: {alert.alert_type}")
                    result.append(f"Time: {alert.timestamp}")
                    result.append("-" * 50)
                
                return "\n".join(result)
            else:
                return "Geofence alerts not available"
            
        except Exception as e:
            self.logger.error(f"Error getting geofence alerts: {e}")
            return f"Error: {str(e)}"
